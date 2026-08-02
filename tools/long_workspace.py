#!/usr/bin/env python3
"""Phase-ready long-project workspace lifecycle for MALTS v1.

Read-only commands never write. State-changing commands are dry-run by default
and require an explicit --apply flag.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from malts_user_contracts import validate_instance


MALTS_ROOT = Path(__file__).resolve().parents[1]
STATE_RELATIVE = Path("runtime") / "workspace_control.json"
FIXED_FILES = ("AGENTS.md", "PROJECT_CONTROL.md", "WORK_TASK_REPORT.md", "CLAUDE.md")
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
HISTORY_TOKEN = re.compile(
    r"<!-- MALTS:history:(?:start id=(?P<id>[A-Za-z0-9][A-Za-z0-9._-]{0,127})|(?P<end>end)) -->"
)
SECTION_LINE = re.compile(
    r"^[ \t]*<!-- MALTS:section=(?P<name>[a-z0-9-]+) -->[ \t]*\r?$",
    re.IGNORECASE,
)
TASK_QUEUE_SECTIONS = frozenset({"task-queue", "phase-queue", "session-queue"})
DECISION_SECTIONS = frozenset({"decisions", "phase-decisions", "session-decisions"})
ACTIVE_TASK_STATES = frozenset({"TODO", "READY", "IN_PROGRESS", "ACTIVE", "BLOCKED"})
PROTECTED_HISTORY_SECTION = re.compile(
    r"MALTS:section=(?:user-original-goal|current-interpreted-goal|completion-definition|"
    r"acceptance-criteria|current-stage|current-state|task-queue|risks?|recovery[^ ]*)",
    re.IGNORECASE,
)
STATIC_GENERATION_REFERENCE = re.compile(
    r"(?i)[A-Z]:[\\/][^\r\n`\"']*?[\\/]lifecycle[\\/]generations[\\/]malts-[A-Za-z0-9._-]+"
)
DEFAULT_BUDGET = {
    "max_root_lines": 1200,
    "max_root_bytes": 262144,
    "max_active_tasks": 50,
    "max_open_decisions": 50,
    "max_evidence_refs": 500,
    "max_stale_history_ratio": 0.65,
}
PLAN_RECHECK_TRIGGERS = frozenset(
    {
        "PHASE_SWITCH",
        "BEFORE_LAUNCH_REVIEW",
        "BEFORE_NEW_WRITE_SCOPE",
        "AFTER_WORKER_RETURN",
        "BEFORE_VERIFIER",
        "AFTER_VERIFIER",
        "USER_CHANGE",
        "CONTEXT_RECOVERY",
        "FAILURE_OR_ROLLBACK",
        "FINAL_DELIVERY",
    }
)
PLAN_RECHECK_RESULTS = frozenset({"PASS", "UPDATED", "BLOCKED", "N/A"})


class WorkspaceError(RuntimeError):
    def __init__(self, code: str, message: str, path: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path

    def as_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"status": "FAIL", "error_code": self.code, "message": self.message}
        if self.path is not None:
            value["path"] = self.path
        return value


def _timestamp(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WorkspaceError("WS_TIMESTAMP_INVALID", "Timestamp must be an ISO 8601 date-time.") from exc
    if parsed.tzinfo is None:
        raise WorkspaceError("WS_TIMESTAMP_INVALID", "Timestamp must include a timezone.")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _workspace(value: str, *, may_not_exist: bool = False) -> Path:
    root = Path(value).expanduser().resolve(strict=False)
    if root.exists() and not root.is_dir():
        raise WorkspaceError("WS_ROOT_NOT_DIRECTORY", "Workspace root is not a directory.", str(root))
    if not root.exists() and not may_not_exist:
        raise WorkspaceError("WS_ROOT_MISSING", "Workspace root does not exist.", str(root))
    return root


def _inside(root: Path, path: Path) -> Path:
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise WorkspaceError("WS_PATH_ESCAPE", "Path escapes the workspace boundary.", str(path)) from exc
    return resolved


def _target(root: Path, relative: str | Path) -> Path:
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise WorkspaceError("WS_PATH_ESCAPE", "Only workspace-relative paths are allowed.", str(relative))
    return _inside(root, root / relative_path)


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _read_bytes(root: Path, relative: str | Path) -> bytes:
    path = _target(root, relative)
    if not path.is_file():
        raise WorkspaceError("WS_FILE_MISSING", "Required workspace file is missing.", _relative(root, path))
    return path.read_bytes()


def _decode_markdown(data: bytes) -> tuple[str, bool]:
    has_bom = data.startswith(b"\xef\xbb\xbf")
    return data.decode("utf-8-sig"), has_bom


def _encode_markdown(text: str, has_bom: bool) -> bytes:
    payload = text.encode("utf-8")
    return (b"\xef\xbb\xbf" + payload) if has_bom else payload


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.malts-write-{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _transaction_write(root: Path, changes: dict[Path, bytes], *, must_be_new: Iterable[Path] = ()) -> None:
    must_be_new_set = set(must_be_new)
    originals: dict[Path, bytes | None] = {}
    for path in changes:
        _inside(root, path)
        if path in must_be_new_set and path.exists():
            raise WorkspaceError("WS_FILE_EXISTS", "Refusing to overwrite an existing file.", _relative(root, path))
        if path.exists() and not path.is_file():
            raise WorkspaceError("WS_PATH_TYPE", "Expected a file path.", _relative(root, path))
        originals[path] = path.read_bytes() if path.exists() else None

    written: list[Path] = []
    try:
        for path, payload in changes.items():
            _atomic_write(path, payload)
            written.append(path)
    except Exception:
        for path in reversed(written):
            original = originals[path]
            if original is None:
                if path.exists():
                    path.unlink()
            else:
                _atomic_write(path, original)
        raise


def _validate_id(value: str, kind: str) -> str:
    if not ID_PATTERN.fullmatch(value):
        raise WorkspaceError("WS_ID_INVALID", f"{kind} must match {ID_PATTERN.pattern}.")
    return value


def _state_path(root: Path) -> Path:
    return _target(root, STATE_RELATIVE)


def _validate_state(root: Path, state: dict[str, Any]) -> None:
    issues = validate_instance(MALTS_ROOT, "workspace-control", state)
    if issues:
        message = "; ".join(issue.render() for issue in issues)
        raise WorkspaceError("WS_STATE_INVALID", message, STATE_RELATIVE.as_posix())
    for item in state["phase_controls"]:
        _target(root, item["path"])
    for item in state["session_controls"]:
        _target(root, item["path"])


def _load_state(root: Path) -> dict[str, Any]:
    path = _state_path(root)
    if not path.is_file():
        raise WorkspaceError("WS_STATE_MISSING", "Workspace is not initialized.", STATE_RELATIVE.as_posix())
    try:
        state = json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkspaceError("WS_STATE_PARSE", "Workspace state is not valid UTF-8 JSON.", STATE_RELATIVE.as_posix()) from exc
    if not isinstance(state, dict):
        raise WorkspaceError("WS_STATE_PARSE", "Workspace state root must be an object.", STATE_RELATIVE.as_posix())
    _validate_state(root, state)
    return state


def _default_state(project_id: str, now: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "project_id": project_id,
        "active_phase_id": None,
        "active_session_id": None,
        "project_control": "PROJECT_CONTROL.md",
        "phase_controls": [],
        "session_controls": [],
        "capacity_budget": dict(DEFAULT_BUDGET),
        "maintenance_state": {
            "state": "clean",
            "last_action": "init",
            "last_checked_at": now,
            "runtime_is_canonical": False,
        },
        "recovery_point": {
            "summary": "Long-project workspace state prepared for its required initial Phase.",
            "next_action": "Create the initial Phase before reporting initialization complete.",
            "evidence_refs": ["workspace:init-prepared"],
        },
    }


def _template_bytes(relative: str) -> tuple[str, bool]:
    path = MALTS_ROOT / relative
    if not path.is_file():
        raise WorkspaceError("WS_TEMPLATE_MISSING", "Required MALTS template is missing.", relative)
    return _decode_markdown(path.read_bytes())


def _language(args: argparse.Namespace, root: Path) -> str:
    requested = getattr(args, "language", "auto")
    if requested != "auto":
        return requested
    control = root / "PROJECT_CONTROL.md"
    if control.is_file():
        text, _ = _decode_markdown(control.read_bytes())
        if any("\u4e00" <= character <= "\u9fff" for character in text):
            return "zh-CN"
    return "en"


def _replace_metadata(text: str, language: str, project_id: str, now: str) -> str:
    version = (MALTS_ROOT / "VERSION").read_text(encoding="utf-8-sig").strip()
    replacements = {
        "en": {
            "- Project:": f"- Project: {project_id}",
            "- Control version: <MALTS_VERSION>": f"- Control version: MALTS {version}",
            "- Current round:": "- Current round: INIT-001",
            "- Last updated:": f"- Last updated: {now}",
            "- Current mode: Single-Agent / Multi-Agent Long-Task": "- Current mode: Single-Agent",
        },
        "zh-CN": {
            "- 项目：": f"- 项目：{project_id}",
            "- 控制文件版本：<MALTS_VERSION>": f"- 控制文件版本：MALTS {version}",
            "- 当前轮次：": "- 当前轮次：INIT-001",
            "- 最后更新：": f"- 最后更新：{now}",
            "- 当前模式：Single-Agent / Multi-Agent Long-Task": "- 当前模式：Single-Agent",
        },
    }[language]
    for source, target in replacements.items():
        text = text.replace(source, target, 1)
    return text


def _insert_locked_goal(text: str, goal: str) -> str:
    marker = "<!-- MALTS:section=user-original-goal -->"
    start = text.find(marker)
    if start < 0:
        raise WorkspaceError("WS_TEMPLATE_INVALID", "Project template lacks the original-goal marker.")
    next_marker = text.find("<!-- MALTS:section=", start + len(marker))
    if next_marker < 0:
        raise WorkspaceError("WS_TEMPLATE_INVALID", "Project template lacks the next canonical marker.")
    newline = "\r\n" if "\r\n" in text else "\n"
    segment = text[start:next_marker].rstrip("\r\n")
    safe_goal = " ".join(goal.splitlines()).strip()
    segment += f"{newline}{newline}> Original goal (locked): {safe_goal}{newline}{newline}"
    return text[:start] + segment + text[next_marker:]


def _single_line(value: str) -> str:
    return " ".join(value.splitlines()).strip()


def _markdown_cell(value: str) -> str:
    return _single_line(value).replace("|", "\\|")


def _populate_initial_phase(text: str, language: str, goal: str, phase_id: str, phase_goal: str) -> str:
    safe_goal = _single_line(goal)
    safe_phase_goal = _single_line(phase_goal)
    phase_cell = _markdown_cell(phase_goal)
    replacements = {
        "en": {
            "- Current understanding:": f"- Current understanding: {safe_goal}",
            "- Stage:": f"- Stage: {phase_id}",
            "- Active Phase:": f"- Active Phase: {phase_id}",
            "- Stage goal:": f"- Stage goal: {safe_phase_goal}",
            "- Exit condition:": "- Exit condition: The initial Phase goal is accepted and its evidence is recorded.",
            "|  |  | TODO / PASS / FAIL / N/A |  |": "| Initial Phase goal is completed | Review the active Phase control and recorded evidence | TODO |  |",
            "| T001 | P0 | TODO | Main Controller |  | None |  |  |": f"| T001 | P0 | TODO | Main Controller | {phase_cell} | None | Project workspace | Active Phase evidence |",
        },
        "zh-CN": {
            "- 当前理解：": f"- 当前理解：{safe_goal}",
            "- 阶段：": f"- 阶段：{phase_id}",
            "- Active Phase：": f"- Active Phase：{phase_id}",
            "- 阶段目标：": f"- 阶段目标：{safe_phase_goal}",
            "- 退出条件：": "- 退出条件：首个 Phase 目标通过验收并记录证据。",
            "|  |  | TODO / PASS / FAIL / N/A |  |": "| 首个 Phase 目标完成 | 审阅 active Phase control 与已记录证据 | TODO |  |",
            "| T001 | P0 | TODO | Main Controller |  | 无 |  |  |": f"| T001 | P0 | TODO | Main Controller | {phase_cell} | 无 | 项目工作区 | Active Phase evidence |",
        },
    }[language]
    for source, target in replacements.items():
        if source not in text:
            raise WorkspaceError("WS_TEMPLATE_INVALID", f"Project template lacks the required initial-Phase token: {source}")
        text = text.replace(source, target, 1)
    return text


def _render_project_control(
    language: str,
    project_id: str,
    goal: str,
    phase_id: str,
    phase_goal: str,
    now: str,
) -> bytes:
    suffix = "en.md" if language == "en" else "zh-CN.md"
    text, bom = _template_bytes(f"runtime/{'EN' if language == 'en' else 'CH'}/templates/PROJECT_CONTROL.template.{suffix}")
    text = _replace_metadata(text, language, project_id, now)
    text = _insert_locked_goal(text, goal)
    text = _populate_initial_phase(text, language, goal, phase_id, phase_goal)
    return _encode_markdown(text, bom)


def _render_work_report(language: str, project_id: str, goal: str, phase_id: str) -> bytes:
    suffix = "en.md" if language == "en" else "zh-CN.md"
    text, bom = _template_bytes(f"runtime/{'EN' if language == 'en' else 'CH'}/templates/WORK_TASK_REPORT.template.{suffix}")
    if language == "en":
        text = text.replace("- Status: DONE / PARTIAL / BLOCKED / FAILED", "- Status: PARTIAL", 1)
        text = text.replace(
            "- Plain-language conclusion:",
            f"- Plain-language conclusion: Long-project workspace initialized with active Phase {phase_id}; no Session is active.",
            1,
        )
        text = text.replace("- User original goal addressed:", f"- User original goal addressed: {goal}", 1)
    else:
        text = text.replace("- 状态：DONE / PARTIAL / BLOCKED / FAILED", "- 状态：PARTIAL", 1)
        text = text.replace("- 直白结论：", f"- 直白结论：长项目工作区已初始化，active Phase 为 {phase_id}；当前没有 active Session。", 1)
        text = text.replace("- 已处理的用户原始目标：", f"- 已处理的用户原始目标：{goal}", 1)
    text = text.replace("- Result ID:", f"- Result ID: {project_id}-INIT-001", 1)
    return _encode_markdown(text, bom)


def _render_named_template(relative: str, values: dict[str, str]) -> bytes:
    text, bom = _template_bytes(relative)
    for key, value in values.items():
        text = text.replace(f"<{key}>", value)
    if re.search(r"<[A-Z][A-Z0-9_]+>", text):
        raise WorkspaceError("WS_TEMPLATE_INVALID", "Template contains unresolved required placeholders.", relative)
    return _encode_markdown(text, bom)


def _plan(operation: str, root: Path, changes: Iterable[Path], apply: bool, **extra: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "status": "PASS",
        "operation": operation,
        "mode": "APPLY" if apply else "DRY_RUN",
        "workspace": str(root),
        "planned_changes": [_relative(root, path) for path in changes],
        "writes_performed": bool(apply),
    }
    value.update(extra)
    return value


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace, may_not_exist=True)
    project_id = _validate_id(args.project_id, "Project ID")
    now = _timestamp(args.timestamp)
    language = args.language
    if not args.goal.strip():
        raise WorkspaceError("WS_GOAL_EMPTY", "Original goal must not be empty.")

    existing_state: dict[str, Any] | None = None
    if _state_path(root).is_file():
        existing_state = _load_state(root)
        if existing_state["project_id"] != project_id:
            raise WorkspaceError("WS_PROJECT_MISMATCH", "Existing workspace state belongs to another project.", STATE_RELATIVE.as_posix())

    phase_id_arg = args.initial_phase_id
    phase_goal_arg = args.initial_phase_goal
    has_registered_phase = bool(existing_state and existing_state["phase_controls"])
    if not has_registered_phase and (not phase_id_arg or not phase_goal_arg or not phase_goal_arg.strip()):
        raise WorkspaceError(
            "WS_INITIAL_PHASE_REQUIRED",
            "Long-project initialization requires both --initial-phase-id and --initial-phase-goal. No files were written.",
        )
    if has_registered_phase and bool(phase_id_arg) != bool(phase_goal_arg):
        raise WorkspaceError(
            "WS_INITIAL_PHASE_REQUIRED",
            "Provide both initial Phase arguments together, or omit both for an already initialized workspace.",
        )

    initial_phase_id: str
    initial_phase_goal: str
    if has_registered_phase:
        first_registered = existing_state["phase_controls"][0]
        initial_phase_id = first_registered["phase_id"]
        initial_phase_goal = phase_goal_arg.strip() if phase_goal_arg else "Existing initialized Phase."
        if phase_id_arg is not None:
            requested_phase_id = _validate_id(phase_id_arg, "Initial Phase ID")
            if requested_phase_id != initial_phase_id:
                raise WorkspaceError(
                    "WS_INITIAL_PHASE_CONFLICT",
                    "The requested initial Phase does not match the registered initial Phase.",
                    first_registered["path"],
                )
    else:
        initial_phase_id = _validate_id(phase_id_arg, "Initial Phase ID")
        initial_phase_goal = phase_goal_arg.strip()

    if (root / "runtime").exists() and not (root / "runtime").is_dir():
        raise WorkspaceError("WS_PATH_TYPE", "runtime must be a directory.", "runtime")

    rendered: dict[str, bytes] = {}
    if not (root / "AGENTS.md").exists():
        template = f"runtime/{'EN' if language == 'en' else 'CH'}/templates/LONG_PROJECT_AGENTS.template.{'en' if language == 'en' else 'zh-CN'}.md"
        text, bom = _template_bytes(template)
        rendered["AGENTS.md"] = _encode_markdown(text, bom)
    if not (root / "PROJECT_CONTROL.md").exists():
        rendered["PROJECT_CONTROL.md"] = _render_project_control(
            language,
            project_id,
            args.goal,
            initial_phase_id,
            initial_phase_goal,
            now,
        )
    if not (root / "WORK_TASK_REPORT.md").exists():
        rendered["WORK_TASK_REPORT.md"] = _render_work_report(language, project_id, args.goal, initial_phase_id)
    if not (root / "CLAUDE.md").exists():
        rendered["CLAUDE.md"] = b"@AGENTS.md\n"
    updated_state = json.loads(json.dumps(existing_state)) if existing_state is not None else _default_state(project_id, now)
    initial_phase_relative = f"phases/{initial_phase_id}/PHASE_CONTROL.md"
    initial_phase_path = _target(root, initial_phase_relative)
    if not has_registered_phase:
        if initial_phase_path.exists():
            raise WorkspaceError(
                "WS_FILE_EXISTS",
                "Refusing to adopt or overwrite an unregistered initial Phase control.",
                initial_phase_relative,
            )
        template = f"runtime/{'EN' if language == 'en' else 'CH'}/templates/PHASE_CONTROL.template.{'en' if language == 'en' else 'zh-CN'}.md"
        rendered[initial_phase_relative] = _render_named_template(
            template,
            {"PHASE_ID": initial_phase_id, "PHASE_GOAL": initial_phase_goal, "TIMESTAMP": now},
        )
        updated_state["phase_controls"].append(
            {"phase_id": initial_phase_id, "path": initial_phase_relative, "status": "ACTIVE"}
        )
        updated_state["active_phase_id"] = initial_phase_id
        updated_state["maintenance_state"].update(
            {"state": "clean", "last_action": "init-with-phase", "last_checked_at": now}
        )
        updated_state["recovery_point"] = {
            "summary": f"Initial Phase {initial_phase_id} is active; no Session is active.",
            "next_action": "Open a Session only for an explicit bounded work-session boundary.",
            "evidence_refs": ["workspace:init", f"phase:{initial_phase_id}"],
        }
        _validate_state(root, updated_state)
        rendered[STATE_RELATIVE.as_posix()] = _json_bytes(updated_state)

    for name in FIXED_FILES:
        path = root / name
        if path.exists() and not path.is_file():
            raise WorkspaceError("WS_PATH_TYPE", "Expected a file path.", name)

    changes = {_target(root, relative): payload for relative, payload in rendered.items()}
    preserved_existing = [name for name in (*FIXED_FILES, STATE_RELATIVE.as_posix()) if (root / name).exists()]
    if has_registered_phase and initial_phase_path.is_file():
        preserved_existing.append(initial_phase_relative)
    result = _plan(
        "init",
        root,
        changes,
        args.apply,
        project_id=project_id,
        language=language,
        initialization_status="READY",
        active_phase_id=updated_state["active_phase_id"],
        active_session_id=updated_state["active_session_id"],
        created_controls=[relative for relative in rendered if relative.endswith("_CONTROL.md")],
        preserved_existing=preserved_existing,
        implicit_session_created=False,
        session_status="NOT_CREATED_BY_DESIGN" if updated_state["active_session_id"] is None else "ACTIVE",
        next_action=updated_state["recovery_point"]["next_action"],
    )
    if args.apply:
        root.mkdir(parents=True, exist_ok=True)
        must_be_new = tuple(path for path in changes if not path.exists())
        _transaction_write(root, changes, must_be_new=must_be_new)
    return result


def _active_phase(state: dict[str, Any]) -> dict[str, Any]:
    phase_id = state["active_phase_id"]
    if phase_id is None:
        raise WorkspaceError("WS_NO_ACTIVE_PHASE", "No active Phase exists.")
    return next(item for item in state["phase_controls"] if item["phase_id"] == phase_id)


def _active_session(state: dict[str, Any]) -> dict[str, Any]:
    session_id = state["active_session_id"]
    if session_id is None:
        raise WorkspaceError("WS_NO_ACTIVE_SESSION", "No active Session exists.")
    return next(item for item in state["session_controls"] if item["session_id"] == session_id)


def _marked_section(text: str, name: str, *, required: bool = False) -> str | None:
    marker_pattern = re.compile(SECTION_LINE.pattern, re.IGNORECASE | re.MULTILINE)
    markers = list(marker_pattern.finditer(text))
    matches = [index for index, marker in enumerate(markers) if marker.group("name").lower() == name.lower()]
    if not matches:
        if required:
            raise WorkspaceError("WS_PLAN_SECTION_MISSING", f"Required MALTS section is missing: {name}")
        return None
    if len(matches) != 1:
        raise WorkspaceError("WS_PLAN_SECTION_DUPLICATE", f"MALTS section must appear exactly once: {name}")
    index = matches[0]
    start = markers[index].start()
    end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
    return text[start:end]


def _control_value(section: str, label: str, code: str = "WS_PLAN_FIELD_INVALID") -> str:
    pattern = re.compile(rf"(?m)^- {re.escape(label)}:[ \t]*(?P<value>[^\r\n]*?)[ \t]*\r?$")
    matches = list(pattern.finditer(section))
    if len(matches) != 1:
        raise WorkspaceError(code, f"Expected exactly one '- {label}:' field.")
    value = matches[0].group("value").strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    if not value:
        raise WorkspaceError(code, f"Field must not be empty: {label}")
    return value


def _phase_plan_binding(root: Path, phase: dict[str, Any]) -> dict[str, str] | None:
    phase_path = _target(root, phase["path"])
    text, _ = _decode_markdown(phase_path.read_bytes())
    section = _marked_section(text, "phase-plan-recheck")
    if section is None:
        return None
    labels = (
        "Active plan",
        "Plan revision",
        "Plan content SHA-256",
        "Plan updated at",
        "Supersedes",
        "Plan status",
        "Last recheck trigger",
        "Last recheck result",
        "Last rechecked at",
        "Launch review invalidated",
    )
    return {label: _control_value(section, label) for label in labels}


def _session_plan_values(binding: dict[str, str] | None) -> dict[str, str]:
    if binding is None or binding["Active plan"] == "N/A":
        return {
            "ACTIVE_PLAN_REFERENCE": "N/A",
            "PLAN_REVISION": "N/A",
            "PLAN_SHA256": "N/A",
            "AUTHORIZATION_SCOPE_RECHECKED": "N/A",
            "LAUNCH_REVIEW_REFERENCE": "N/A",
        }
    return {
        "ACTIVE_PLAN_REFERENCE": binding["Active plan"],
        "PLAN_REVISION": binding["Plan revision"],
        "PLAN_SHA256": binding["Plan content SHA-256"],
        "AUTHORIZATION_SCOPE_RECHECKED": "Yes",
        "LAUNCH_REVIEW_REFERENCE": "N/A",
    }


def command_open_phase(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    phase_id = _validate_id(args.phase_id, "Phase ID")
    if state["active_phase_id"] is not None:
        raise WorkspaceError("WS_PHASE_ACTIVE", "Close the active Phase before opening another one.")
    if any(item["phase_id"] == phase_id for item in state["phase_controls"]):
        raise WorkspaceError("WS_PHASE_EXISTS", "Phase ID already exists.", phase_id)
    if not args.goal.strip():
        raise WorkspaceError("WS_GOAL_EMPTY", "Phase goal must not be empty.")
    now = _timestamp(args.timestamp)
    language = _language(args, root)
    relative = f"phases/{phase_id}/PHASE_CONTROL.md"
    phase_path = _target(root, relative)
    if phase_path.exists():
        raise WorkspaceError("WS_FILE_EXISTS", "Refusing to adopt or overwrite an unregistered Phase control.", relative)
    template = f"runtime/{'EN' if language == 'en' else 'CH'}/templates/PHASE_CONTROL.template.{'en' if language == 'en' else 'zh-CN'}.md"
    control = _render_named_template(template, {"PHASE_ID": phase_id, "PHASE_GOAL": args.goal.strip(), "TIMESTAMP": now})
    updated = json.loads(json.dumps(state))
    updated["phase_controls"].append({"phase_id": phase_id, "path": relative, "status": "ACTIVE"})
    updated["active_phase_id"] = phase_id
    updated["maintenance_state"].update({"state": "clean", "last_action": "open-phase", "last_checked_at": now})
    updated["recovery_point"] = {
        "summary": f"Phase {phase_id} is active; no Session is active.",
        "next_action": "Open a Session only for an explicit bounded work-session boundary.",
        "evidence_refs": [f"phase:{phase_id}"],
    }
    _validate_state(root, updated)
    changes = {phase_path: control, _state_path(root): _json_bytes(updated)}
    result = _plan("open-phase", root, changes, args.apply, phase_id=phase_id, implicit_session_created=False)
    if args.apply:
        _transaction_write(root, changes, must_be_new=(phase_path,))
    return result


def _replace_line(text: str, source: str, target: str, code: str) -> str:
    pattern = re.compile(rf"(?m)^{re.escape(source)}[^\r\n]*(?P<ending>\r?)$")
    if pattern.search(text) is None:
        raise WorkspaceError(code, f"Expected control token is missing: {source}")
    return pattern.sub(lambda match: target + match.group("ending"), text, count=1)


def _replace_active_status(text: str, target_status: str, code: str) -> str:
    pattern = re.compile(r"(?m)^- Status:[ \t]*([A-Z_]+)[ \t]*(?P<ending>\r?)$")
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise WorkspaceError(code, "Expected exactly one '- Status:' control token.")
    current_status = matches[0].group(1)
    if current_status not in {"ACTIVE", target_status}:
        raise WorkspaceError(
            code,
            f"Phase control status {current_status} conflicts with requested terminal status {target_status}.",
        )
    return pattern.sub(lambda match: f"- Status: {target_status}{match.group('ending')}", text, count=1)


def command_close_phase(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    if state["active_session_id"] is not None:
        raise WorkspaceError("WS_SESSION_ACTIVE", "Close the active Session before closing its Phase.")
    phase = _active_phase(state)
    now = _timestamp(args.timestamp)
    path = _target(root, phase["path"])
    data = _read_bytes(root, phase["path"])
    text, bom = _decode_markdown(data)
    text = _replace_active_status(text, args.status, "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Updated at:", f"- Updated at: {now}", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Close result:", f"- Close result: {args.status}", "WS_PHASE_CONTROL_INVALID")
    updated = json.loads(json.dumps(state))
    next(item for item in updated["phase_controls"] if item["phase_id"] == phase["phase_id"])["status"] = args.status
    updated["active_phase_id"] = None
    updated["maintenance_state"].update({"last_action": "close-phase", "last_checked_at": now})
    updated["recovery_point"] = {
        "summary": f"Phase {phase['phase_id']} closed with {args.status}.",
        "next_action": args.next_action,
        "evidence_refs": [f"phase:{phase['phase_id']}:{args.status.lower()}"],
    }
    _validate_state(root, updated)
    changes = {path: _encode_markdown(text, bom), _state_path(root): _json_bytes(updated)}
    result = _plan("close-phase", root, changes, args.apply, phase_id=phase["phase_id"], terminal_status=args.status)
    if args.apply:
        _transaction_write(root, changes)
    return result


def command_open_session(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    phase = _active_phase(state)
    if state["active_session_id"] is not None:
        raise WorkspaceError("WS_SESSION_ACTIVE", "Close the active Session before opening another one.")
    session_id = _validate_id(args.session_id, "Session ID")
    if any(item["session_id"] == session_id for item in state["session_controls"]):
        raise WorkspaceError("WS_SESSION_EXISTS", "Session ID already exists.", session_id)
    if not args.goal.strip():
        raise WorkspaceError("WS_GOAL_EMPTY", "Session goal must not be empty.")
    now = _timestamp(args.timestamp)
    language = _language(args, root)
    relative = f"sessions/{session_id}/SESSION_CONTROL.md"
    session_path = _target(root, relative)
    if session_path.exists():
        raise WorkspaceError("WS_FILE_EXISTS", "Refusing to adopt or overwrite an unregistered Session control.", relative)
    template = f"runtime/{'EN' if language == 'en' else 'CH'}/templates/SESSION_CONTROL.template.{'en' if language == 'en' else 'zh-CN'}.md"
    plan_values = _session_plan_values(_phase_plan_binding(root, phase))
    control = _render_named_template(
        template,
        {
            "SESSION_ID": session_id,
            "PHASE_ID": phase["phase_id"],
            "SESSION_REASON": args.reason,
            "SESSION_GOAL": args.goal.strip(),
            "TIMESTAMP": now,
            **plan_values,
        },
    )
    updated = json.loads(json.dumps(state))
    updated["session_controls"].append(
        {
            "session_id": session_id,
            "phase_id": phase["phase_id"],
            "path": relative,
            "status": "ACTIVE",
            "reason": args.reason,
            "created_at": now,
        }
    )
    updated["active_session_id"] = session_id
    updated["maintenance_state"].update({"last_action": "open-session", "last_checked_at": now})
    updated["recovery_point"] = {
        "summary": f"Session {session_id} is active in Phase {phase['phase_id']}.",
        "next_action": args.goal.strip(),
        "evidence_refs": [f"session:{session_id}"],
    }
    _validate_state(root, updated)
    changes = {session_path: control, _state_path(root): _json_bytes(updated)}
    result = _plan("open-session", root, changes, args.apply, session_id=session_id, phase_id=phase["phase_id"])
    if args.apply:
        _transaction_write(root, changes, must_be_new=(session_path,))
    return result


def command_close_session(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    session = _active_session(state)
    now = _timestamp(args.timestamp)
    path = _target(root, session["path"])
    data = _read_bytes(root, session["path"])
    text, bom = _decode_markdown(data)
    text = _replace_line(text, "- Status: ACTIVE", f"- Status: {args.status}", "WS_SESSION_CONTROL_INVALID")
    text = _replace_line(text, "- Updated at:", f"- Updated at: {now}", "WS_SESSION_CONTROL_INVALID")
    text = _replace_line(text, "- Next action:", f"- Next action: {args.next_action}", "WS_SESSION_CONTROL_INVALID")
    updated = json.loads(json.dumps(state))
    next(item for item in updated["session_controls"] if item["session_id"] == session["session_id"])["status"] = args.status
    updated["active_session_id"] = None
    updated["maintenance_state"].update({"last_action": "close-session", "last_checked_at": now})
    updated["recovery_point"] = {
        "summary": f"Session {session['session_id']} closed with {args.status}; Phase {session['phase_id']} remains active.",
        "next_action": args.next_action,
        "evidence_refs": [f"session:{session['session_id']}:{args.status.lower()}"],
    }
    _validate_state(root, updated)
    changes = {path: _encode_markdown(text, bom), _state_path(root): _json_bytes(updated)}
    result = _plan("close-session", root, changes, args.apply, session_id=session["session_id"], terminal_status=args.status)
    if args.apply:
        _transaction_write(root, changes)
    return result


def _history_blocks(text: str) -> list[tuple[str, int, int, str]]:
    tokens = list(HISTORY_TOKEN.finditer(text))
    raw_start_count = text.count("<!-- MALTS:history:start")
    raw_end_count = text.count("<!-- MALTS:history:end")
    recognized_starts = sum(1 for token in tokens if token.group("id") is not None)
    recognized_ends = sum(1 for token in tokens if token.group("end") is not None)
    if raw_start_count != recognized_starts or raw_end_count != recognized_ends:
        raise WorkspaceError("WS_HISTORY_MARKER_INVALID", "History markers are malformed.")
    blocks: list[tuple[str, int, int, str]] = []
    opened: tuple[str, int] | None = None
    for token in tokens:
        history_id = token.group("id")
        if history_id is not None:
            if opened is not None:
                raise WorkspaceError("WS_HISTORY_MARKER_INVALID", "Nested history blocks are forbidden.")
            opened = (history_id, token.start())
        else:
            if opened is None:
                raise WorkspaceError("WS_HISTORY_MARKER_INVALID", "History end marker has no start marker.")
            history_id, start = opened
            block = text[start:token.end()]
            if PROTECTED_HISTORY_SECTION.search(block):
                raise WorkspaceError("WS_HISTORY_PROTECTED_CONTENT", "History block contains a protected active canonical section.", history_id)
            blocks.append((history_id, start, token.end(), block))
            opened = None
    if opened is not None:
        raise WorkspaceError("WS_HISTORY_MARKER_INVALID", "History start marker has no end marker.")
    ids = [item[0] for item in blocks]
    if len(ids) != len(set(ids)):
        raise WorkspaceError("WS_HISTORY_DUPLICATE", "History block IDs must be unique.")
    return blocks


def _scoped_lines(text: str, section_names: frozenset[str]) -> tuple[list[tuple[int, str]], bool]:
    selected: list[tuple[int, str]] = []
    current_section: str | None = None
    marker_found = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        marker = SECTION_LINE.fullmatch(line)
        if marker is not None:
            marker_found = True
            current_section = marker.group("name").casefold()
            continue
        if current_section in section_names:
            selected.append((line_number, line))
    return selected, marker_found


def _table_cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def _count_canonical_active_tasks(lines: list[tuple[int, str]]) -> int:
    active_tasks = 0
    status_index: int | None = None
    for _, line in lines:
        cells = _table_cells(line)
        if cells is None:
            status_index = None
            continue
        normalized = [cell.casefold() for cell in cells]
        if "status" in normalized:
            status_index = normalized.index("status")
            continue
        if "状态" in normalized:
            status_index = normalized.index("状态")
            continue
        if status_index is None or status_index >= len(cells):
            continue
        if re.fullmatch(r":?-{3,}:?", cells[status_index]):
            continue
        if cells[status_index].strip().upper() in ACTIVE_TASK_STATES:
            active_tasks += 1
    return active_tasks


def _metrics(data: bytes) -> dict[str, Any]:
    text, _ = _decode_markdown(data)
    blocks = _history_blocks(text)
    stale_bytes = sum(len(block.encode("utf-8")) for _, _, _, block in blocks)
    total_bytes = len(data)
    task_lines, has_section_markers = _scoped_lines(text, TASK_QUEUE_SECTIONS)
    if has_section_markers:
        active_tasks = _count_canonical_active_tasks(task_lines)
    else:
        active_tasks = len(re.findall(r"(?im)^\|.*\|\s*(?:TODO|READY|IN_PROGRESS|ACTIVE|BLOCKED)\s*\|", text))
    decision_lines, _ = _scoped_lines(text, DECISION_SECTIONS)
    decision_line_numbers = {line_number for line_number, _ in decision_lines}
    open_decision_lines: set[int] = set()
    decision_label = re.compile(r"^-[ \t]*(?:Open decision(?:s)?|待确认(?:决策|问题))[ \t]*[：:][ \t]*(.*)$", re.IGNORECASE)
    closed_values = {"", "none", "n/a", "na", "no", "无", "暂无", "没有"}
    for line_number, line in enumerate(text.splitlines(), start=1):
        if (not has_section_markers or line_number in decision_line_numbers) and re.search(
            r"\[OPEN\]|\|[ \t]*OPEN[ \t]*\|",
            line,
            re.IGNORECASE,
        ):
            open_decision_lines.add(line_number)
        match = decision_label.match(line)
        if match is None:
            continue
        value = match.group(1).strip().rstrip(".。;；").strip().casefold()
        closed_prefix = re.match(r"^(?:none|n/a|na|no|无|暂无|没有)(?=$|[\s.;。；,，、—-])", value, re.IGNORECASE)
        if value not in closed_values and closed_prefix is None:
            open_decision_lines.add(line_number)
    open_decisions = len(open_decision_lines)
    evidence_refs = len(set(re.findall(r"(?i)(?:evidence|证据)[/:=：\s]+([A-Za-z0-9][A-Za-z0-9._:/\\-]+)", text)))
    return {
        "lines": len(text.splitlines()),
        "bytes": total_bytes,
        "active_tasks": active_tasks,
        "open_decisions": open_decisions,
        "evidence_refs": evidence_refs,
        "stale_history_ratio": round(stale_bytes / total_bytes, 6) if total_bytes else 0.0,
        "history_blocks": len(blocks),
    }


def _collect_metrics(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    def item(relative: str) -> dict[str, Any]:
        result = {"path": relative}
        result.update(_metrics(_read_bytes(root, relative)))
        return result

    active_phase = (
        [next(entry for entry in state["phase_controls"] if entry["phase_id"] == state["active_phase_id"])]
        if state["active_phase_id"] is not None
        else []
    )
    active_session = (
        [next(entry for entry in state["session_controls"] if entry["session_id"] == state["active_session_id"])]
        if state["active_session_id"] is not None
        else []
    )
    return {
        "root": item("PROJECT_CONTROL.md"),
        "phases": [item(entry["path"]) for entry in active_phase],
        "sessions": [item(entry["path"]) for entry in active_session],
    }


def _budget_assessment(metrics: dict[str, Any], budget: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    controls = [metrics["root"], *metrics["phases"], *metrics["sessions"]]
    breaches: list[dict[str, Any]] = []
    total_tasks = sum(item["active_tasks"] for item in controls)
    total_decisions = sum(item["open_decisions"] for item in controls)
    total_evidence = sum(item["evidence_refs"] for item in controls)
    for item in controls:
        for metric, budget_key in (("lines", "max_root_lines"), ("bytes", "max_root_bytes"), ("stale_history_ratio", "max_stale_history_ratio")):
            if item[metric] > budget[budget_key]:
                breaches.append({"path": item["path"], "metric": metric, "actual": item[metric], "limit": budget[budget_key]})
    for metric, actual, budget_key in (
        ("active_tasks", total_tasks, "max_active_tasks"),
        ("open_decisions", total_decisions, "max_open_decisions"),
        ("evidence_refs", total_evidence, "max_evidence_refs"),
    ):
        if actual > budget[budget_key]:
            breaches.append({"path": "all-controls", "metric": metric, "actual": actual, "limit": budget[budget_key]})
    if any(item["metric"] in {"lines", "bytes", "stale_history_ratio"} for item in breaches):
        return "compaction-required", breaches
    if breaches:
        return "maintenance-required", breaches
    return "clean", breaches


def _runtime_reference_warnings(root: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    references = ["PROJECT_CONTROL.md", "WORK_TASK_REPORT.md", "AGENTS.md", "CLAUDE.md"]
    references.extend(entry["path"] for entry in state["phase_controls"])
    references.extend(entry["path"] for entry in state["session_controls"])
    warnings: list[dict[str, str]] = []
    for relative in dict.fromkeys(references):
        path = _target(root, relative)
        if not path.is_file():
            continue
        text, _ = _decode_markdown(path.read_bytes())
        for line_number, line in enumerate(text.splitlines(), start=1):
            if STATIC_GENERATION_REFERENCE.search(line):
                warnings.append(
                    {
                        "code": "WS_STALE_RUNTIME_REFERENCE",
                        "path": relative,
                        "line": str(line_number),
                        "message": "A physical MALTS generation path is stale-prone; resolve MALTS_BOOT.md dynamically instead.",
                    }
                )
    return warnings


def _validate_workspace(root: Path, state: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any], list[dict[str, Any]]]:
    issues: list[dict[str, str]] = []
    for relative in (*FIXED_FILES, "runtime"):
        path = _target(root, relative)
        expected = "directory" if relative == "runtime" else "file"
        valid = path.is_dir() if expected == "directory" else path.is_file()
        if not valid:
            issues.append({"code": "WS_SKELETON_MISSING", "path": relative, "message": f"Expected {expected}."})
    for entry in [*state["phase_controls"], *state["session_controls"]]:
        if not _target(root, entry["path"]).is_file():
            issues.append({"code": "WS_CONTROL_MISSING", "path": entry["path"], "message": "Registered control file is missing."})
    if not state["phase_controls"]:
        issues.append(
            {
                "code": "WS_INITIAL_PHASE_MISSING",
                "path": STATE_RELATIVE.as_posix(),
                "message": "Long-project initialization is incomplete until its initial Phase is registered.",
            }
        )
    if state["active_phase_id"] is not None:
        active = next(item for item in state["phase_controls"] if item["phase_id"] == state["active_phase_id"])
        if active["status"] != "ACTIVE":
            issues.append({"code": "WS_ACTIVE_PHASE_STATUS", "path": active["path"], "message": "Active Phase index must have ACTIVE status."})
        active_path = _target(root, active["path"])
        if active_path.is_file():
            active_text, _ = _decode_markdown(active_path.read_bytes())
            status_matches = re.findall(r"(?m)^- Status:[ \t]*([A-Z_]+)[ \t]*\r?$", active_text)
            if len(status_matches) != 1:
                issues.append(
                    {
                        "code": "WS_ACTIVE_PHASE_CONTROL_INVALID",
                        "path": active["path"],
                        "message": "Active Phase control must contain exactly one machine-readable Status field.",
                    }
                )
            elif status_matches[0] != "ACTIVE":
                terminal_status = status_matches[0]
                action = (
                    f"Run close-phase --status {terminal_status} --workspace \"{root}\" "
                    '--next-action "Open the next Phase when authorized." --apply '
                    "to reconcile runtime state with the terminal Phase control."
                )
                issues.append(
                    {
                        "code": "WS_ACTIVE_PHASE_CONTROL_DRIFT",
                        "path": active["path"],
                        "message": f"Runtime marks this Phase ACTIVE but its control status is {terminal_status}.",
                        "required_action": action,
                    }
                )
    if state["active_session_id"] is not None:
        active = next(item for item in state["session_controls"] if item["session_id"] == state["active_session_id"])
        if active["status"] != "ACTIVE":
            issues.append({"code": "WS_ACTIVE_SESSION_STATUS", "path": active["path"], "message": "Active Session index must have ACTIVE status."})
    metrics = _collect_metrics(root, state) if not issues else {"root": {}, "phases": [], "sessions": []}
    _, breaches = _budget_assessment(metrics, state["capacity_budget"]) if not issues else ("recovery-required", [])
    return issues, metrics, breaches


def command_validate(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    issues, metrics, breaches = _validate_workspace(root, state)
    runtime_reference_warnings = _runtime_reference_warnings(root, state)
    runtime_reference_issues = [
        {
            "code": item["code"],
            "path": item["path"],
            "message": item["message"],
        }
        for item in runtime_reference_warnings
    ]
    issues = [*issues, *runtime_reference_issues]
    control_drift = [item for item in issues if item["code"] in {"WS_ACTIVE_PHASE_CONTROL_DRIFT", "WS_ACTIVE_PHASE_CONTROL_INVALID"}]
    initialization_status = (
        "NEEDS_INITIAL_PHASE"
        if not state["phase_controls"]
        else "NEEDS_CONTROL_RECONCILIATION"
        if control_drift
        else "READY"
    )
    required_actions: list[str] = []
    if initialization_status == "NEEDS_INITIAL_PHASE":
        required_actions.append("Create the initial Phase before treating this as an initialized long-project workspace.")
    if runtime_reference_warnings:
        required_actions.append("Refresh generated PROJECT_CONTROL runtime metadata, or manually review every static generation reference outside that generated metadata.")
    required_actions.extend(item["required_action"] for item in control_drift if item.get("required_action"))
    return {
        "status": "PASS" if not issues else "FAIL",
        "operation": "validate",
        "mode": "READ_ONLY",
        "workspace": str(root),
        "writes_performed": False,
        "issues": issues,
        "runtime_reference_warnings": runtime_reference_warnings,
        "capacity_warnings": breaches,
        "metrics": metrics,
        "active_phase_id": state["active_phase_id"],
        "active_session_id": state["active_session_id"],
        "initialization_status": initialization_status,
        "required_action": " ".join(required_actions) if required_actions else None,
        "implicit_session_created": False,
    }


def _plan_recheck_response(
    root: Path,
    trigger: str,
    result: str,
    *,
    issues: list[dict[str, str]] | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    problems = issues or []
    return {
        "status": "FAIL" if result == "BLOCKED" else "PASS",
        "operation": "plan-recheck",
        "mode": "READ_ONLY",
        "workspace": str(root),
        "writes_performed": False,
        "trigger": trigger,
        "recheck_result": result,
        "issues": problems,
        "evidence": evidence or {},
    }


def command_plan_recheck(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    phase = _active_phase(state)
    try:
        binding = _phase_plan_binding(root, phase)
    except WorkspaceError as exc:
        return _plan_recheck_response(
            root,
            args.trigger,
            "BLOCKED",
            issues=[{"code": exc.code, "path": phase["path"], "message": exc.message}],
        )
    if binding is None or binding["Active plan"] == "N/A":
        if args.require_active_plan:
            return _plan_recheck_response(
                root,
                args.trigger,
                "BLOCKED",
                issues=[
                    {
                        "code": "WS_ACTIVE_PLAN_REQUIRED",
                        "path": phase["path"],
                        "message": "This gate requires an active Phase-owned plan binding.",
                    }
                ],
            )
        return _plan_recheck_response(
            root,
            args.trigger,
            "N/A",
            evidence={"phase_control": phase["path"], "reason": "No active plan is bound to the Phase."},
        )

    issues: list[dict[str, str]] = []

    def issue(code: str, path: str, message: str) -> None:
        issues.append({"code": code, "path": path, "message": message})

    plan_relative = binding["Active plan"]
    plan_path: Path | None = None
    try:
        plan_path = _target(root, plan_relative)
    except WorkspaceError as exc:
        issue(exc.code, plan_relative, exc.message)
    observed_sha256: str | None = None
    if plan_path is not None:
        if not plan_path.is_file():
            issue("WS_ACTIVE_PLAN_MISSING", plan_relative, "The Phase-owned active plan file is missing.")
        else:
            observed_sha256 = hashlib.sha256(plan_path.read_bytes()).hexdigest().upper()
    expected_sha256 = binding["Plan content SHA-256"].upper()
    if not re.fullmatch(r"[0-9A-F]{64}", expected_sha256):
        issue("WS_PLAN_SHA256_INVALID", phase["path"], "Plan content SHA-256 must be 64 uppercase hexadecimal characters.")
    elif observed_sha256 is not None and observed_sha256 != expected_sha256:
        issue("WS_PLAN_CONTENT_DRIFT", plan_relative, "Active plan bytes do not match the Phase-bound SHA-256.")

    if binding["Plan status"] != "ACTIVE":
        issue("WS_PLAN_STATUS", phase["path"], "A required active plan must have Plan status ACTIVE.")
    if binding["Last recheck trigger"] not in PLAN_RECHECK_TRIGGERS:
        issue("WS_PLAN_TRIGGER_INVALID", phase["path"], "Last recheck trigger is not a canonical event value.")
    elif binding["Last recheck trigger"] != args.trigger:
        issue("WS_PLAN_TRIGGER_DRIFT", phase["path"], "Requested trigger does not match the recorded Phase recheck trigger.")
    if binding["Last recheck result"] not in PLAN_RECHECK_RESULTS:
        issue("WS_PLAN_RESULT_INVALID", phase["path"], "Last recheck result is not canonical.")
    elif binding["Last recheck result"] == "BLOCKED":
        issue("WS_PLAN_RECORDED_BLOCKED", phase["path"], "The Phase records a blocked Plan Recheck.")
    for label in ("Plan updated at", "Last rechecked at"):
        try:
            _timestamp(binding[label])
        except WorkspaceError:
            issue("WS_PLAN_TIMESTAMP_INVALID", phase["path"], f"{label} must be a timezone-qualified ISO 8601 timestamp.")
    if binding["Launch review invalidated"] not in {"Yes", "No"}:
        issue("WS_PLAN_LAUNCH_INVALIDATION", phase["path"], "Launch review invalidated must be Yes or No.")
    elif binding["Launch review invalidated"] == "Yes":
        issue("WS_PLAN_LAUNCH_REVIEW_INVALIDATED", phase["path"], "The current launch review is explicitly invalidated.")

    root_text, _ = _decode_markdown(_read_bytes(root, "PROJECT_CONTROL.md"))
    try:
        root_section = _marked_section(root_text, "plan-recheck-index")
        if root_section is not None:
            root_fields = {
                label: _control_value(root_section, label)
                for label in (
                    "Active plan",
                    "Active Phase owner",
                    "Plan revision",
                    "Plan content SHA-256",
                    "Latest recheck trigger",
                    "Latest recheck result",
                    "Launch review invalidated",
                )
            }
            expected_root_fields = {
                "Active plan": plan_relative,
                "Active Phase owner": phase["path"],
                "Plan revision": binding["Plan revision"],
                "Plan content SHA-256": expected_sha256,
                "Latest recheck trigger": binding["Last recheck trigger"],
                "Latest recheck result": binding["Last recheck result"],
                "Launch review invalidated": binding["Launch review invalidated"],
            }
            for label, expected in expected_root_fields.items():
                if root_fields[label] != expected:
                    issue("WS_PLAN_ROOT_INDEX_DRIFT", "PROJECT_CONTROL.md", f"Root Plan Recheck index disagrees on {label}.")
    except WorkspaceError as exc:
        issue(exc.code, "PROJECT_CONTROL.md", exc.message)

    session_path_relative: str | None = None
    if state["active_session_id"] is not None:
        session = _active_session(state)
        session_path_relative = session["path"]
        session_text, _ = _decode_markdown(_read_bytes(root, session["path"]))
        try:
            session_section = _marked_section(session_text, "session-plan-binding", required=True)
            assert session_section is not None
            session_fields = {
                label: _control_value(session_section, label)
                for label in (
                    "Active plan reference",
                    "Plan revision",
                    "Plan content SHA-256",
                    "Authorization/scope rechecked",
                    "Launch review reference",
                )
            }
            expected_session_fields = {
                "Active plan reference": plan_relative,
                "Plan revision": binding["Plan revision"],
                "Plan content SHA-256": expected_sha256,
            }
            for label, expected in expected_session_fields.items():
                if session_fields[label] != expected:
                    issue("WS_PLAN_SESSION_BINDING_DRIFT", session["path"], f"Session plan binding disagrees on {label}.")
            if session_fields["Authorization/scope rechecked"] != "Yes":
                issue("WS_PLAN_SESSION_AUTHORIZATION", session["path"], "Active Session must record Authorization/scope rechecked as Yes.")
        except WorkspaceError as exc:
            issue(exc.code, session["path"], exc.message)

    evidence = {
        "phase_control": phase["path"],
        "session_control": session_path_relative,
        "active_plan": plan_relative,
        "plan_revision": binding["Plan revision"],
        "expected_sha256": expected_sha256,
        "observed_sha256": observed_sha256,
        "recorded_result": binding["Last recheck result"],
    }
    return _plan_recheck_response(root, args.trigger, "BLOCKED" if issues else "PASS", issues=issues, evidence=evidence)


def command_refresh_runtime_references(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    warnings = _runtime_reference_warnings(root, state)
    unsupported = [item for item in warnings if item["path"] != "PROJECT_CONTROL.md"]
    if unsupported:
        raise WorkspaceError(
            "WS_RUNTIME_REFERENCE_SCOPE",
            "Only generated PROJECT_CONTROL metadata can be refreshed automatically; review other static generation references manually.",
            unsupported[0]["path"],
        )
    control = _target(root, "PROJECT_CONTROL.md")
    text, has_bom = _decode_markdown(control.read_bytes())
    replacement_en = "- Version source: resolve `MALTS_BOOT.md` first, then read the active `MALTS_ROOT` `VERSION`; do not copy a physical generation path or current MALTS version from old control/report/handoff/template files."
    replacement_zh = "- 版本来源：先解析 `MALTS_BOOT.md`，再读取 active `MALTS_ROOT` 的 `VERSION`；不要从旧 control/report/handoff/template 文件复制物理 generation 路径或当前 MALTS 版本。"
    lines = text.splitlines(keepends=True)
    changed = False
    for index, line in enumerate(lines):
        body = line.rstrip("\r\n")
        suffix = line[len(body):]
        if body.startswith("- Version source:") and STATIC_GENERATION_REFERENCE.search(body):
            lines[index] = replacement_en + suffix
            changed = True
        elif body.startswith("- 版本来源：") and STATIC_GENERATION_REFERENCE.search(body):
            lines[index] = replacement_zh + suffix
            changed = True
    if warnings and not changed:
        raise WorkspaceError(
            "WS_RUNTIME_REFERENCE_SCOPE",
            "Static generation reference exists outside a generated version-source metadata line and requires manual review.",
            "PROJECT_CONTROL.md",
        )
    changes = {control: _encode_markdown("".join(lines), has_bom)} if changed else {}
    result = _plan(
        "refresh-runtime-references",
        root,
        changes,
        args.apply,
        detected_warning_count=len(warnings),
        unresolved_warning_count=0,
        dynamic_boot_reference="MALTS_BOOT.md -> active MALTS_ROOT -> VERSION",
    )
    if args.apply and changes:
        _transaction_write(root, changes)
    return result


def command_maintain(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    issues, metrics, _ = _validate_workspace(root, state)
    if issues:
        raise WorkspaceError("WS_VALIDATION_FAILED", "Workspace validation must pass before maintenance.")
    maintenance_state, breaches = _budget_assessment(metrics, state["capacity_budget"])
    now = _timestamp(args.timestamp)
    updated = json.loads(json.dumps(state))
    updated["maintenance_state"].update(
        {"state": maintenance_state, "last_action": "maintain", "last_checked_at": now, "runtime_is_canonical": False}
    )
    changes = {_state_path(root): _json_bytes(updated)}
    result = _plan(
        "maintain",
        root,
        changes,
        args.apply,
        maintenance_state=maintenance_state,
        capacity_warnings=breaches,
        metrics=metrics,
        implicit_session_created=False,
    )
    if args.apply:
        _transaction_write(root, changes)
    return result


def command_compact(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    now = _timestamp(args.timestamp)
    project_path = _target(root, "PROJECT_CONTROL.md")
    project_data = _read_bytes(root, "PROJECT_CONTROL.md")
    text, bom = _decode_markdown(project_data)
    blocks = _history_blocks(text)
    if not blocks:
        return _plan("compact", root, (), args.apply, compacted_blocks=0, implicit_session_created=False)

    archive_relative = "history/PROJECT_CONTROL_HISTORY.md"
    archive_path = _target(root, archive_relative)
    if archive_path.exists() and not archive_path.is_file():
        raise WorkspaceError("WS_PATH_TYPE", "History archive path is not a file.", archive_relative)
    archive_data = archive_path.read_bytes() if archive_path.is_file() else b"# PROJECT_CONTROL History\n\n"
    archive_text, archive_bom = _decode_markdown(archive_data)
    for history_id, _, _, _ in blocks:
        if re.search(rf"(?m)^## {re.escape(history_id)}$", archive_text):
            raise WorkspaceError("WS_HISTORY_DUPLICATE", "History archive already contains this ID.", history_id)

    compacted = text
    for history_id, start, end, block in reversed(blocks):
        marker = f"<!-- MALTS:history:archived id={history_id} path={archive_relative} -->"
        compacted = compacted[:start] + marker + compacted[end:]
    if not archive_text.endswith("\n"):
        archive_text += "\n"
    for history_id, _, _, block in blocks:
        archive_text += f"\n## {history_id}\n\n{block.rstrip()}\n"

    updated = json.loads(json.dumps(state))
    updated["maintenance_state"].update({"state": "clean", "last_action": "compact", "last_checked_at": now})
    updated["recovery_point"] = {
        "summary": f"Compacted {len(blocks)} explicitly marked historical block(s).",
        "next_action": state["recovery_point"]["next_action"],
        "evidence_refs": [f"history:{history_id}" for history_id, _, _, _ in blocks],
    }
    changes = {
        archive_path: _encode_markdown(archive_text, archive_bom),
        project_path: _encode_markdown(compacted, bom),
        _state_path(root): _json_bytes(updated),
    }
    result = _plan(
        "compact",
        root,
        changes,
        args.apply,
        compacted_blocks=len(blocks),
        history_ids=[item[0] for item in blocks],
        protected_sections_moved=False,
        implicit_session_created=False,
    )
    if args.apply:
        must_be_new = (archive_path,) if not archive_path.exists() else ()
        _transaction_write(root, changes, must_be_new=must_be_new)
    return result


def _nearest_instruction(root: Path, state: dict[str, Any]) -> Path | None:
    start = root
    if state["active_session_id"] is not None:
        start = _target(root, _active_session(state)["path"]).parent
    elif state["active_phase_id"] is not None:
        start = _target(root, _active_phase(state)["path"]).parent
    current = start
    while True:
        candidate = current / "AGENTS.md"
        if candidate.is_file():
            return _inside(root, candidate)
        if current == root:
            break
        current = current.parent
    return None


def command_recover(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    validation_issues, _, _ = _validate_workspace(root, state)
    ordered: list[Path] = []

    def add(path: Path) -> None:
        path = _inside(root, path)
        if path.is_file() and path not in ordered:
            ordered.append(path)

    nearest = _nearest_instruction(root, state)
    if nearest is not None:
        add(nearest)
    add(_target(root, "PROJECT_CONTROL.md"))
    if state["active_phase_id"] is not None:
        add(_target(root, _active_phase(state)["path"]))
    if state["active_session_id"] is not None:
        add(_target(root, _active_session(state)["path"]))
    elif state["session_controls"]:
        latest = max(state["session_controls"], key=lambda item: item["created_at"])
        add(_target(root, latest["path"]))
    add(_target(root, "WORK_TASK_REPORT.md"))
    add(_target(root, "PROJECT_HANDOFF.md"))
    add(_state_path(root))

    evidence = []
    for index, path in enumerate(ordered, start=1):
        data = path.read_bytes()
        evidence.append(
            {
                "order": index,
                "path": _relative(root, path),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest().upper(),
                "canonical": not _relative(root, path).startswith("runtime/"),
            }
        )
    control_drift = [
        item
        for item in validation_issues
        if item["code"] in {"WS_ACTIVE_PHASE_CONTROL_DRIFT", "WS_ACTIVE_PHASE_CONTROL_INVALID"}
    ]
    initialization_status = (
        "NEEDS_INITIAL_PHASE"
        if not state["phase_controls"]
        else "NEEDS_CONTROL_RECONCILIATION"
        if control_drift
        else "READY"
    )
    required_actions = [item["required_action"] for item in control_drift if item.get("required_action")]
    if initialization_status == "NEEDS_INITIAL_PHASE":
        required_actions.append("Run init with --initial-phase-id and --initial-phase-goal, or explicitly open the first Phase.")
    return {
        "status": "PASS" if initialization_status == "READY" else "FAIL",
        "operation": "recover",
        "mode": "READ_ONLY_COLD_START",
        "workspace": str(root),
        "writes_performed": False,
        "read_order": evidence,
        "active_phase_id": state["active_phase_id"],
        "active_session_id": state["active_session_id"],
        "initialization_status": initialization_status,
        "required_action": " ".join(required_actions) if required_actions else None,
        "recovery_point": state["recovery_point"],
        "runtime_is_canonical": False,
        "summary_replaces_current_facts": False,
    }


def _add_common_write_arguments(parser: argparse.ArgumentParser, *, language: bool = False) -> None:
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--apply", action="store_true", help="Apply the planned state changes; default is dry-run.")
    parser.add_argument("--timestamp", help="Optional deterministic ISO 8601 timestamp for tests/evidence.")
    if language:
        parser.add_argument("--language", choices=("auto", "en", "zh-CN"), default="auto")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init")
    _add_common_write_arguments(init)
    init.add_argument("--project-id", required=True)
    init.add_argument("--goal", required=True)
    init.add_argument("--language", choices=("en", "zh-CN"), default="en")
    init.add_argument("--initial-phase-id", help="Required initial Phase ID for a new or legacy-minimal workspace.")
    init.add_argument("--initial-phase-goal", help="Required initial Phase goal for a new or legacy-minimal workspace.")
    init.set_defaults(handler=command_init)

    open_phase = subparsers.add_parser("open-phase")
    _add_common_write_arguments(open_phase, language=True)
    open_phase.add_argument("--phase-id", required=True)
    open_phase.add_argument("--goal", required=True)
    open_phase.set_defaults(handler=command_open_phase)

    close_phase = subparsers.add_parser("close-phase")
    _add_common_write_arguments(close_phase)
    close_phase.add_argument("--status", choices=("DONE", "BLOCKED", "FAILED"), required=True)
    close_phase.add_argument("--next-action", default="Open the next Phase when authorized.")
    close_phase.set_defaults(handler=command_close_phase)

    open_session = subparsers.add_parser("open-session")
    _add_common_write_arguments(open_session, language=True)
    open_session.add_argument("--session-id", required=True)
    open_session.add_argument("--goal", required=True)
    open_session.add_argument("--reason", choices=("bounded-work-session", "recovery", "manual-checkpoint"), default="bounded-work-session")
    open_session.set_defaults(handler=command_open_session)

    close_session = subparsers.add_parser("close-session")
    _add_common_write_arguments(close_session)
    close_session.add_argument("--status", choices=("DONE", "BLOCKED", "FAILED"), required=True)
    close_session.add_argument("--next-action", required=True)
    close_session.set_defaults(handler=command_close_session)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--workspace", required=True)
    validate.set_defaults(handler=command_validate)

    plan_recheck = subparsers.add_parser("plan-recheck")
    plan_recheck.add_argument("--workspace", required=True)
    plan_recheck.add_argument("--trigger", choices=tuple(sorted(PLAN_RECHECK_TRIGGERS)), required=True)
    plan_recheck.add_argument("--require-active-plan", action="store_true")
    plan_recheck.set_defaults(handler=command_plan_recheck)

    refresh_runtime_references = subparsers.add_parser("refresh-runtime-references")
    _add_common_write_arguments(refresh_runtime_references)
    refresh_runtime_references.set_defaults(handler=command_refresh_runtime_references)

    maintain = subparsers.add_parser("maintain")
    _add_common_write_arguments(maintain)
    maintain.set_defaults(handler=command_maintain)

    compact = subparsers.add_parser("compact")
    _add_common_write_arguments(compact)
    compact.set_defaults(handler=command_compact)

    recover = subparsers.add_parser("recover")
    recover.add_argument("--workspace", required=True)
    recover.set_defaults(handler=command_recover)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
    except WorkspaceError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    except Exception as exc:
        failure = WorkspaceError("WS_INTERNAL_ERROR", f"{type(exc).__name__}: {exc}")
        print(json.dumps(failure.as_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
