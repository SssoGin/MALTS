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
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

sys.dont_write_bytecode = True

from malts_user_contracts import validate_instance
from malts_user_contracts import canonical_json, load_json
import migrate_result_contract as result_migration
from result_controller import apply_event_batch_v2, rebuild_lineage_projection_v2
from workspace_artifacts import (
    ArtifactMutationError,
    artifact_close_gate,
    artifact_references_in_text,
    artifact_snapshot_preconditions,
    audit_workspace,
    enrollment_preview,
    plan_enrollment_apply,
    plan_promote,
    plan_reconcile,
    plan_register,
    plan_supersede,
)
from workspace_transactions import (
    TransactionError,
    WORKSPACE_TRANSACTION_PROFILE,
    execute_transaction,
    inspect_transaction_state,
    recover_transaction,
    sha256_bytes,
)

try:
    from workspace_transactions import plan_transaction
except ImportError:  # Wave-B transaction implementation is integrated independently.
    plan_transaction = None


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
PHASE_REVIEW_RESULTS = frozenset(
    {"KEEP", "REBASE_PLAN", "RESCOPE_REVIEW", "TRANSITION_REVIEW", "USER_DECISION_REQUIRED"}
)
CANDIDATE_MAPPINGS = frozenset({"SAME_PHASE", "UNCLEAR", "OUTSIDE_EXPLICIT_SCOPE"})
PHASE_ACTIVE_TASK_STATES = frozenset({"TODO", "READY", "IN_PROGRESS", "REVIEW", "ACTIVE", "BLOCKED"})
PHASE_TERMINAL_TASK_STATES = frozenset({"DONE", "FAILED", "CANCELLED", "N/A"})
PHASE_BOUNDARY_FIELDS = (
    ("milestone", "Milestone", "PHASE_MILESTONE"),
    ("in_scope", "In Scope", "PHASE_IN_SCOPE"),
    ("out_of_scope", "Explicitly Out of Scope", "PHASE_OUT_OF_SCOPE"),
    ("exit_criteria", "Exit Criteria", "PHASE_EXIT_CRITERIA"),
    ("carry_over_policy", "Carry-over Policy", "PHASE_CARRY_OVER_POLICY"),
    ("boundary_review_triggers", "Boundary Review Triggers", "PHASE_BOUNDARY_REVIEW_TRIGGERS"),
)
PHASE_BOUNDARY_MARKERS = (
    "phase-boundary",
    "phase-scope-changes",
    "phase-carry-over",
    "phase-carried-in",
    "phase-boundary-review",
    "phase-lifecycle",
)
TRANSITION_PLAN_PREFIX = Path("runtime") / "phase-transitions"
V4_ONLY_OPERATIONS = frozenset(
    {
        "record-result-events",
        "rebuild-result-lineage",
        "plan-phase-boundary-amendment",
        "apply-phase-boundary-amendment",
        "transfer-session-lease",
    }
)
V4_TERMINAL_PHASE_STATES = frozenset({"DONE", "SUPERSEDED", "BLOCKED", "FAILED"})
BOUNDARY_INDEX_MARKER = "phase-boundary-revision-index"
TASK_INDEX_MARKER = "phase-task-lineage-index"


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


def _io_path(path: Path) -> Path:
    """Return an explicit extended-length Windows path for filesystem I/O."""
    if os.name != "nt" or not path.is_absolute():
        return path
    value = str(path)
    if value.startswith("\\\\?\\"):
        return path
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


def _path_is_file(path: Path) -> bool:
    return _io_path(path).is_file()


def _path_read_bytes(path: Path) -> bytes:
    return _io_path(path).read_bytes()


def _read_bytes(root: Path, relative: str | Path) -> bytes:
    path = _target(root, relative)
    if not _path_is_file(path):
        raise WorkspaceError("WS_FILE_MISSING", "Required workspace file is missing.", _relative(root, path))
    return _path_read_bytes(path)


def _decode_markdown(data: bytes) -> tuple[str, bool]:
    has_bom = data.startswith(b"\xef\xbb\xbf")
    return data.decode("utf-8-sig"), has_bom


def _encode_markdown(text: str, has_bom: bool) -> bytes:
    payload = text.encode("utf-8")
    return (b"\xef\xbb\xbf" + payload) if has_bom else payload


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _canonical_json_file_bytes(value: Any) -> bytes:
    """Bytes used by immutable Result records and their exact SHA-256 bindings."""

    return canonical_json(value)


def _sha256_payload(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _sha256_path(path: Path) -> str:
    return _sha256_payload(_path_read_bytes(path))


def _canonical_string_array(values: Iterable[str]) -> bytes:
    return canonical_json(sorted({_single_line(value) for value in values if _single_line(value)}))


def _require_schema_v4(state: dict[str, Any], operation: str) -> None:
    if state.get("schema_version") != 4:
        raise WorkspaceError(
            "WS_SCHEMA_V4_MIGRATION_REQUIRED",
            f"{operation} requires workspace-control schema v4; legacy schemas remain read-only compatible.",
            STATE_RELATIVE.as_posix(),
        )


def _require_no_incomplete_workspace_transaction(root: Path) -> None:
    try:
        inspection = inspect_transaction_state(root, WORKSPACE_TRANSACTION_PROFILE)
    except TransactionError as exc:
        raise WorkspaceError("WS_TRANSACTION_INCOMPLETE", exc.message, str(exc.detail)) from exc
    if inspection.get("status") != "PASS":
        raise WorkspaceError(
            "WS_TRANSACTION_INCOMPLETE",
            "An incomplete workspace transaction blocks governed reads and mutations.",
            WORKSPACE_TRANSACTION_PROFILE.lock_relative.as_posix(),
        )


def _atomic_write(path: Path, payload: bytes) -> None:
    io_path = _io_path(path)
    io_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_path = tempfile.mkstemp(prefix=".m-", suffix=".tmp", dir=str(io_path.parent))
    temporary = Path(raw_path)
    stream = None
    try:
        stream = os.fdopen(descriptor, "wb")
        descriptor = -1
        with stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, io_path)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        raise
    finally:
        if temporary.exists():
            temporary.unlink()


def _transaction_write(
    root: Path,
    changes: dict[Path, bytes],
    *,
    must_be_new: Iterable[Path] = (),
    operation: str = "workspace-write",
    operation_id: str | None = None,
    expected_plan_sha256: str | None = None,
    target_roles: dict[Path, str] | None = None,
) -> dict[str, Any]:
    must_be_new_set = set(must_be_new)
    preconditions: dict[Path, str | None] = {}
    for path in changes:
        _inside(root, path)
        if path in must_be_new_set and path.exists():
            raise WorkspaceError("WS_FILE_EXISTS", "Refusing to overwrite an existing file.", _relative(root, path))
        if path.exists() and not path.is_file():
            raise WorkspaceError("WS_PATH_TYPE", "Expected a file path.", _relative(root, path))
        preconditions[path] = hashlib.sha256(path.read_bytes()).hexdigest().upper() if path.exists() else None
    if operation_id is None:
        digest = hashlib.sha256(operation.encode("utf-8"))
        for path in sorted(changes, key=lambda item: _relative(root, item)):
            digest.update(b"\0")
            digest.update(_relative(root, path).encode("utf-8"))
            digest.update(b"\0")
            digest.update((preconditions[path] or "N/A").encode("ascii"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(changes[path]).hexdigest().upper().encode("ascii"))
        operation_id = f"{operation}-{digest.hexdigest()[:24]}"
    try:
        transaction_arguments: dict[str, Any] = {
            "operation_id": operation_id,
            "operation": operation,
            "changes": changes,
            "expected_input_hashes": preconditions,
            "profile": WORKSPACE_TRANSACTION_PROFILE,
        }
        if expected_plan_sha256 is not None:
            transaction_arguments["plan_sha256"] = expected_plan_sha256
        if target_roles is not None:
            transaction_arguments["target_roles"] = target_roles
        return execute_transaction(root, **transaction_arguments)
    except TransactionError as exc:
        raise WorkspaceError(exc.code, exc.message, exc.detail) from exc


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


def _parse_state_bytes(root: Path, payload: bytes) -> dict[str, Any]:
    try:
        state = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkspaceError("WS_STATE_PARSE", "Workspace state is not valid UTF-8 JSON.", STATE_RELATIVE.as_posix()) from exc
    if not isinstance(state, dict):
        raise WorkspaceError("WS_STATE_PARSE", "Workspace state root must be an object.", STATE_RELATIVE.as_posix())
    _validate_state(root, state)
    return state


def _load_state(root: Path) -> dict[str, Any]:
    path = _state_path(root)
    if not path.is_file():
        raise WorkspaceError("WS_STATE_MISSING", "Workspace is not initialized.", STATE_RELATIVE.as_posix())
    return _parse_state_bytes(root, path.read_bytes())


def _load_state_capture(root: Path) -> tuple[dict[str, Any], bytes]:
    payload = _read_bytes(root, STATE_RELATIVE)
    return _parse_state_bytes(root, payload), payload


def _default_state(project_id: str, now: str) -> dict[str, Any]:
    return {
        "schema_version": 4,
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
        "current_phase_binding": None,
        "current_session_binding": None,
        "current_task_bindings": [],
        "recovery_binding": None,
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


def _phase_boundary_values(args: argparse.Namespace, *, required: bool) -> dict[str, str]:
    values: dict[str, str] = {}
    provided = []
    for attribute, label, placeholder in PHASE_BOUNDARY_FIELDS:
        raw = getattr(args, attribute, None)
        value = _single_line(raw) if isinstance(raw, str) else ""
        values[placeholder] = value
        provided.append(bool(value))
        if value.upper() in {"N/A", "NA", "TBD", "TODO", "UNKNOWN"}:
            raise WorkspaceError("WS_PHASE_BOUNDARY_PLACEHOLDER", f"Boundary field must be substantive: {label}")
    if required and not all(provided):
        missing = [label for present, (_, label, _) in zip(provided, PHASE_BOUNDARY_FIELDS) if not present]
        raise WorkspaceError(
            "WS_PHASE_BOUNDARY_REQUIRED",
            "Every new Phase requires a complete Boundary Contract; missing: " + ", ".join(missing),
        )
    if any(provided) and not all(provided):
        raise WorkspaceError("WS_PHASE_BOUNDARY_INCOMPLETE", "Provide all Phase Boundary fields together, or omit all of them.")
    return values


def _split_boundary_list(value: str) -> list[str]:
    values = [_single_line(item) for item in re.split(r"\s*(?:;|；)\s*", value) if _single_line(item)]
    return values or [_single_line(value)]


def _boundary_revision_document(
    *,
    phase_id: str,
    revision_id: str,
    revision_number: int,
    previous_revision: dict[str, str] | None,
    boundary_values: dict[str, str],
    review_id: str,
    review_evidence_refs: list[str],
    authorization_ref: str,
    accepted_at: str,
) -> dict[str, Any]:
    return {
        "revision_schema": 1,
        "phase_id": phase_id,
        "revision_id": revision_id,
        "revision_number": revision_number,
        "previous_revision": previous_revision,
        "milestone": boundary_values["PHASE_MILESTONE"],
        "in_scope": _split_boundary_list(boundary_values["PHASE_IN_SCOPE"]),
        "out_of_scope": _split_boundary_list(boundary_values["PHASE_OUT_OF_SCOPE"]),
        "exit_criteria": _split_boundary_list(boundary_values["PHASE_EXIT_CRITERIA"]),
        "carry_over_policy": boundary_values["PHASE_CARRY_OVER_POLICY"],
        "boundary_review_triggers": _split_boundary_list(boundary_values["PHASE_BOUNDARY_REVIEW_TRIGGERS"]),
        "review_id": review_id,
        "review_evidence_refs": review_evidence_refs,
        "authorization_ref": authorization_ref,
        "accepted_at": accepted_at,
    }


def _insert_before_marker(text: str, target_marker: str, block: str, code: str) -> str:
    marker = f"<!-- MALTS:section={target_marker} -->"
    index = text.find(marker)
    if index < 0:
        raise WorkspaceError(code, f"Required MALTS insertion marker is missing: {target_marker}")
    newline = "\r\n" if "\r\n" in text else "\n"
    normalized = block.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline).rstrip("\r\n")
    return text[:index] + normalized + newline + newline + text[index:]


def _boundary_index_block(revision: dict[str, Any], path: str, sha256: str) -> str:
    return (
        f"<!-- MALTS:section={BOUNDARY_INDEX_MARKER} -->\n"
        "## Phase Boundary Revision Index\n\n"
        f"- Current revision ID: `{revision['revision_id']}`\n"
        f"- Current revision number: `{revision['revision_number']}`\n"
        f"- Current revision path: `{path}`\n"
        f"- Current revision SHA-256: `{sha256}`\n"
        f"- Accepted at: `{revision['accepted_at']}`\n"
    )


def _task_index_block(rows: list[dict[str, Any]], recorded_at: str) -> str:
    lines = [
        f"<!-- MALTS:section={TASK_INDEX_MARKER} -->",
        "## Task Lineage Index",
        "",
        "| Task ID | Lineage ID | Status | Contract revision | Latest event | Projection |",
        "|---|---|---|---|---|---|",
    ]
    for row in sorted(rows, key=lambda item: item["task_id"]):
        latest_event = row.get("latest_event")
        event_value = "N/A" if latest_event is None else f"{latest_event['path']}#{latest_event['sha256']}"
        revision = row["latest_contract_revision"]
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    row["task_id"], row["lineage_id"], row["task_status"],
                    f"{revision['path']}#{revision['sha256']}", event_value,
                    f"{row['projection_path']}#{row['projection_sha256']}",
                )
            )
            + " |"
        )
    lines.extend(["", f"- Projected at: `{recorded_at}`"])
    return "\n".join(lines) + "\n"


def _replace_or_insert_section(text: str, section_name: str, block: str, before_marker: str, code: str) -> str:
    existing = _marked_section(text, section_name)
    if existing is not None:
        newline = "\r\n" if "\r\n" in text else "\n"
        normalized = block.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)
        return text.replace(existing, normalized, 1)
    return _insert_before_marker(text, before_marker, block, code)


def _render_phase_control(
    language: str,
    phase_id: str,
    goal: str,
    now: str,
    boundary_values: dict[str, str],
) -> bytes:
    template = (
        f"runtime/{'EN' if language == 'en' else 'CH'}/templates/"
        f"PHASE_CONTROL.template.{'en' if language == 'en' else 'zh-CN'}.md"
    )
    return _render_named_template(
        template,
        {
            "PHASE_ID": phase_id,
            "PHASE_GOAL": goal,
            "TIMESTAMP": now,
            **boundary_values,
        },
    )


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


def _render_work_report(
    language: str,
    project_id: str,
    goal: str,
    phase_id: str,
    phase_relative: str,
    phase_sha256: str,
    phase_boundary_sha256: str,
    boundary_review_id: str,
    boundary_review_sha256: str,
    candidate_mapping: str,
    recommendation: str,
    phase_recovery_sha256: str,
    now: str,
) -> bytes:
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
    for placeholder, value in {
        "<CURRENT_PHASE_ID>": phase_id,
        "<CURRENT_PHASE_CONTROL>": phase_relative,
        "<CURRENT_PHASE_SHA256>": phase_sha256,
        "<CURRENT_PHASE_BOUNDARY_SHA256>": phase_boundary_sha256,
        "<CURRENT_BOUNDARY_REVIEW_ID>": boundary_review_id,
        "<CURRENT_BOUNDARY_REVIEW_SHA256>": boundary_review_sha256,
        "<CURRENT_BOUNDARY_CANDIDATE_MAPPING>": candidate_mapping,
        "<CURRENT_BOUNDARY_RECOMMENDATION>": recommendation,
        "<CURRENT_PHASE_RECOVERY_SHA256>": phase_recovery_sha256,
        "<CURRENT_PHASE_RECORDED_AT>": now,
    }.items():
        text = text.replace(placeholder, value, 1)
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


def _transaction_preview(
    root: Path,
    *,
    operation_id: str,
    operation: str,
    changes: dict[Path, bytes],
    preconditions: dict[Path, str | None],
    target_roles: dict[Path, str],
) -> dict[str, Any]:
    if plan_transaction is None:
        canonical = {
            "plan_schema": 1,
            "operation_id": operation_id,
            "operation": operation,
            "inputs": [
                {"path": _relative(root, path), "expected_preimage": expected or "ABSENT"}
                for path, expected in sorted(preconditions.items(), key=lambda item: _relative(root, item[0]))
            ],
            "targets": [
                {
                    "path": _relative(root, path),
                    "role": target_roles[path],
                    "planned_sha256": _sha256_payload(changes[path]),
                    "planned_bytes": len(changes[path]),
                }
                for path in sorted(changes, key=lambda item: _relative(root, item))
            ],
        }
        canonical["plan_sha256"] = _sha256_payload(canonical_json(canonical))
        return canonical
    try:
        return plan_transaction(
            root,
            operation_id=operation_id,
            operation=operation,
            changes=changes,
            expected_input_hashes=preconditions,
            target_roles=target_roles,
        )
    except TransactionError as exc:
        raise WorkspaceError(exc.code, exc.message, str(exc.detail)) from exc


def _apply_transaction_plan(
    root: Path,
    *,
    operation_id: str,
    operation: str,
    changes: dict[Path, bytes],
    preconditions: dict[Path, str | None],
    target_roles: dict[Path, str],
    expected_plan_sha256: str,
    fault_point: str | None = None,
) -> dict[str, Any]:
    try:
        return execute_transaction(
            root,
            operation_id=operation_id,
            operation=operation,
            changes=changes,
            expected_input_hashes=preconditions,
            profile=WORKSPACE_TRANSACTION_PROFILE,
            target_roles=target_roles,
            plan_sha256=expected_plan_sha256,
            fault_point=fault_point,
        )
    except TransactionError as exc:
        raise WorkspaceError(exc.code, exc.message, str(exc.detail)) from exc


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
    boundary_values = _phase_boundary_values(args, required=not has_registered_phase)

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
        rendered[initial_phase_relative] = _render_phase_control(
            language,
            initial_phase_id,
            initial_phase_goal,
            now,
            boundary_values,
        )
        if existing_state is None:
            revision_id = f"{initial_phase_id}-boundary-r001"
            revision_relative = f"phases/{initial_phase_id}/boundary-revisions/{revision_id}.json"
            revision = _boundary_revision_document(
                phase_id=initial_phase_id,
                revision_id=revision_id,
                revision_number=1,
                previous_revision=None,
                boundary_values=boundary_values,
                review_id=f"{initial_phase_id}-initial-boundary",
                review_evidence_refs=["workspace:init"],
                authorization_ref="workspace:init-explicit",
                accepted_at=now,
            )
            revision_payload = _canonical_json_file_bytes(revision)
            rendered[revision_relative] = revision_payload
            phase_text, phase_bom = _decode_markdown(rendered[initial_phase_relative])
            phase_text = _insert_before_marker(
                phase_text,
                "phase-plan-recheck",
                _boundary_index_block(revision, revision_relative, _sha256_payload(revision_payload)),
                "WS_TEMPLATE_INVALID",
            )
            phase_text = _insert_before_marker(
                phase_text,
                "phase-queue",
                _task_index_block([], now),
                "WS_TEMPLATE_INVALID",
            )
            rendered[initial_phase_relative] = _encode_markdown(phase_text, phase_bom)
        updated_state["schema_version"] = 4 if existing_state is None else 2
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

    if not (root / "WORK_TASK_REPORT.md").exists():
        phase_payload = rendered.get(initial_phase_relative)
        if phase_payload is None and initial_phase_path.is_file():
            phase_payload = initial_phase_path.read_bytes()
        phase_sha256 = hashlib.sha256(phase_payload).hexdigest().upper() if phase_payload is not None else "N/A"
        phase_boundary_sha256 = "N/A"
        boundary_review_id = "N/A"
        boundary_review_sha256 = "N/A"
        candidate_mapping = "N/A"
        recommendation = "N/A"
        phase_recovery_sha256 = "N/A"
        if phase_payload is not None:
            try:
                review = _boundary_review_record(phase_payload, initial_phase_relative)
                phase_boundary_sha256 = _normalized_section_sha256(phase_payload, "phase-boundary", "WS_PHASE_BOUNDARY_RECORD_MISSING", initial_phase_relative)
                boundary_review_id = review["Review ID"]
                boundary_review_sha256 = _normalized_section_sha256(phase_payload, "phase-boundary-review", "WS_PHASE_BOUNDARY_RECORD_MISSING", initial_phase_relative)
                candidate_mapping = review["Candidate mapping"]
                recommendation = review["Recommended review"]
                phase_recovery_sha256 = _normalized_section_sha256(phase_payload, "phase-recovery", "WS_RECOVERY_RECORD_DRIFT", initial_phase_relative)
            except WorkspaceError:
                pass
        rendered["WORK_TASK_REPORT.md"] = _render_work_report(
            language,
            project_id,
            args.goal,
            initial_phase_id,
            initial_phase_relative,
            phase_sha256,
            phase_boundary_sha256,
            boundary_review_id,
            boundary_review_sha256,
            candidate_mapping,
            recommendation,
            phase_recovery_sha256,
            now,
        )

    for name in FIXED_FILES:
        path = root / name
        if path.exists() and not path.is_file():
            raise WorkspaceError("WS_PATH_TYPE", "Expected a file path.", name)

    changes = {_target(root, relative): payload for relative, payload in rendered.items()}
    if not has_registered_phase:
        if updated_state["schema_version"] in {3, 4}:
            _finalize_v3_consistency(root, updated_state, changes, now)
        else:
            changes[_state_path(root)] = _json_bytes(updated_state)
        _validate_state(root, updated_state)
    elif "WORK_TASK_REPORT.md" in rendered:
        _refresh_current_phase_bindings(root, updated_state, changes, now)
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
        roles = {
            path: "IMMUTABLE_RECORD" if "boundary-revisions" in _relative(root, path) else
            "PHASE_CONTROL" if _relative(root, path).endswith("PHASE_CONTROL.md") else
            "REPORT" if _relative(root, path) == "WORK_TASK_REPORT.md" else
            "PROJECT_CONTROL" if _relative(root, path) == "PROJECT_CONTROL.md" else
            "RUNTIME_STATE" if path == _state_path(root) else "PROJECT_CONTROL"
            for path in changes
        }
        _transaction_write(root, changes, must_be_new=must_be_new, operation="init", target_roles=roles)
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


def _phase_entry(state: dict[str, Any], phase_id: str) -> dict[str, Any]:
    match = next((item for item in state["phase_controls"] if item["phase_id"] == phase_id), None)
    if match is None:
        raise WorkspaceError("WS_PHASE_MISSING", "Phase ID is not registered.", phase_id)
    return match


def _phase_boundary_contract(text: str) -> dict[str, Any]:
    section = _marked_section(text, "phase-boundary")
    if section is None:
        return {"status": "LEGACY", "fields": {}, "missing_fields": [item[1] for item in PHASE_BOUNDARY_FIELDS]}
    fields: dict[str, str] = {}
    missing: list[str] = []
    for _, label, _ in PHASE_BOUNDARY_FIELDS:
        try:
            value = _control_value(section, label, "WS_PHASE_BOUNDARY_INVALID")
        except WorkspaceError:
            missing.append(label)
            continue
        if value.upper() in {"N/A", "NA", "TBD", "TODO", "UNKNOWN"}:
            missing.append(label)
        else:
            fields[label] = value
    return {"status": "COMPLETE" if not missing else "INCOMPLETE", "fields": fields, "missing_fields": missing}


def _markdown_table_rows(section: str | None) -> list[dict[str, str]]:
    if section is None:
        return []
    table_lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|") and line.strip().endswith("|")]
    if len(table_lines) < 2:
        return []

    def cells(line: str) -> list[str]:
        return [value.strip().replace("\\|", "|") for value in line.strip().strip("|").split("|")]

    headers = cells(table_lines[0])
    if not all(re.fullmatch(r":?-{3,}:?", value.replace(" ", "")) for value in cells(table_lines[1])):
        return []
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        values = cells(line)
        if len(values) != len(headers):
            continue
        rows.append(dict(zip(headers, values)))
    return rows


def _phase_table_summary(text: str, section_name: str, status_header: str) -> dict[str, Any]:
    rows = _markdown_table_rows(_marked_section(text, section_name))
    active_rows = [row for row in rows if row.get(status_header, "").upper() in PHASE_ACTIVE_TASK_STATES]
    return {"rows": rows, "count": len(rows), "active_count": len(active_rows), "active_rows": active_rows}


def _structured_closure(text: str) -> dict[str, str] | None:
    section = _marked_section(text, "phase-close")
    if section is None:
        return None
    labels = (
        "Close result",
        "Exit criteria status",
        "Carry-over disposition",
        "Superseded by",
        "Closure evidence",
        "Closed at",
    )
    values: dict[str, str] = {}
    for label in labels:
        try:
            values[label] = _control_value(section, label, "WS_PHASE_CLOSURE_INVALID")
        except WorkspaceError:
            return None
    return values


def _phase_lifecycle_warnings(root: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if state.get("schema_version") == 1:
        warnings.append(
            {
                "code": "WS_WORKSPACE_SCHEMA_LEGACY",
                "path": STATE_RELATIVE.as_posix(),
                "message": "workspace-control schema v1 remains readable but requires explicit migration before v2-only Phase mutations.",
            }
        )
    project_path = _target(root, "PROJECT_CONTROL.md")
    if project_path.is_file():
        try:
            project_text, _ = _decode_markdown(project_path.read_bytes())
            if _marked_section(project_text, "current-stage") is None:
                raise WorkspaceError("WS_ROOT_PHASE_INDEX_LEGACY", "PROJECT_CONTROL lacks the current-stage section.")
            _project_active_phase_value(project_text)
        except WorkspaceError:
            warnings.append(
                {
                    "code": "WS_ROOT_PHASE_INDEX_LEGACY",
                    "path": "PROJECT_CONTROL.md",
                    "message": "Canonical root Active Phase index is absent or incomplete; legacy reads remain allowed, but Phase mutations require explicit migration.",
                }
            )
    for phase in state["phase_controls"]:
        path = _target(root, phase["path"])
        if not path.is_file():
            continue
        text, _ = _decode_markdown(path.read_bytes())
        boundary = _phase_boundary_contract(text)
        if boundary["status"] != "COMPLETE":
            warnings.append(
                {
                    "code": "WS_PHASE_BOUNDARY_LEGACY" if boundary["status"] == "LEGACY" else "WS_PHASE_BOUNDARY_INCOMPLETE",
                    "path": phase["path"],
                    "message": (
                        "Phase Boundary Contract is absent; run a read-only boundary review and explicit migrate-phase-control before v2-only mutations."
                        if boundary["status"] == "LEGACY"
                        else "Phase Boundary Contract is incomplete: " + ", ".join(boundary["missing_fields"])
                    ),
                }
            )
        elif _structured_closure(text) is None:
            warnings.append(
                {
                    "code": "WS_PHASE_CLOSURE_INCOMPLETE",
                    "path": phase["path"],
                    "message": "Phase Boundary is v2-complete but the structured Closure contract is absent or incomplete; reads remain allowed and close is blocked.",
                }
            )
        try:
            binding = _phase_plan_binding(root, phase)
        except WorkspaceError:
            binding = None
        if (
            binding is not None
            and binding["Active plan"] != "N/A"
            and binding["Last recheck trigger"] not in PLAN_RECHECK_TRIGGERS
        ):
            warnings.append(
                {
                    "code": "WS_PHASE_PLAN_TRIGGER_MIGRATION_REQUIRED",
                    "path": phase["path"],
                    "message": "Plan trigger is noncanonical and requires explicit reviewed repair; it is not silently accepted.",
                }
            )
    return warnings


def _append_table_rows(text: str, section_name: str, rows: list[list[str]], code: str) -> str:
    if not rows:
        return text
    section = _marked_section(text, section_name, required=True)
    assert section is not None
    rendered_rows = "".join("| " + " | ".join(_markdown_cell(value) for value in row) + " |\n" for row in rows)
    delimiter = re.compile(r"(?m)^(?P<line>\|[ \t]*---[^\r\n]*\|)(?P<ending>\r?)$")
    if delimiter.search(section) is None:
        raise WorkspaceError(code, f"Section {section_name} lacks a canonical Markdown table delimiter.")
    updated_section = delimiter.sub(
        lambda match: match.group("line") + match.group("ending") + "\n" + rendered_rows.rstrip("\n"),
        section,
        count=1,
    )
    return text.replace(section, updated_section, 1)


def _phase_control_info(root: Path, phase: dict[str, Any]) -> tuple[Path, bytes, str, bool]:
    path = _target(root, phase["path"])
    data = _read_bytes(root, phase["path"])
    text, bom = _decode_markdown(data)
    return path, data, text, bom


def _phase_plan_binding(
    root: Path,
    phase: dict[str, Any],
    payload: bytes | None = None,
) -> dict[str, str] | None:
    phase_path = _target(root, phase["path"])
    source = payload if payload is not None else _path_read_bytes(phase_path)
    text, _ = _decode_markdown(source)
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
    _require_consistent_mutation(root, state)
    phase_id = _validate_id(args.phase_id, "Phase ID")
    if state["active_phase_id"] is not None:
        raise WorkspaceError("WS_PHASE_ACTIVE", "Close the active Phase before opening another one.")
    if any(item["phase_id"] == phase_id for item in state["phase_controls"]):
        raise WorkspaceError("WS_PHASE_EXISTS", "Phase ID already exists.", phase_id)
    if not args.goal.strip():
        raise WorkspaceError("WS_GOAL_EMPTY", "Phase goal must not be empty.")
    boundary_values = _phase_boundary_values(args, required=True)
    now = _timestamp(args.timestamp)
    language = _language(args, root)
    relative = f"phases/{phase_id}/PHASE_CONTROL.md"
    phase_path = _target(root, relative)
    if phase_path.exists():
        raise WorkspaceError("WS_FILE_EXISTS", "Refusing to adopt or overwrite an unregistered Phase control.", relative)
    control = _render_phase_control(language, phase_id, args.goal.strip(), now, boundary_values)
    project_path = _target(root, "PROJECT_CONTROL.md")
    project_text, project_bom = _decode_markdown(_read_bytes(root, "PROJECT_CONTROL.md"))
    project_text = _replace_project_active_phase(project_text, phase_id)
    updated = json.loads(json.dumps(state))
    if updated["schema_version"] == 1:
        updated["schema_version"] = 2
    updated["phase_controls"].append({"phase_id": phase_id, "path": relative, "status": "ACTIVE"})
    updated["active_phase_id"] = phase_id
    updated["maintenance_state"].update({"state": "clean", "last_action": "open-phase", "last_checked_at": now})
    updated["recovery_point"] = {
        "summary": f"Phase {phase_id} is active; no Session is active.",
        "next_action": "Open a Session only for an explicit bounded work-session boundary.",
        "evidence_refs": [f"phase:{phase_id}"],
    }
    boundary_path: Path | None = None
    if updated["schema_version"] == 4:
        revision_id = f"{phase_id}-boundary-r001"
        revision_relative = f"phases/{phase_id}/boundary-revisions/{revision_id}.json"
        boundary_path = _target(root, revision_relative)
        if boundary_path.exists():
            raise WorkspaceError("WS_FILE_EXISTS", "Refusing to overwrite an existing Phase boundary revision.", revision_relative)
        revision = _boundary_revision_document(
            phase_id=phase_id,
            revision_id=revision_id,
            revision_number=1,
            previous_revision=None,
            boundary_values=boundary_values,
            review_id=f"{phase_id}-initial-boundary",
            review_evidence_refs=[f"phase:{phase_id}:open"],
            authorization_ref="open-phase:explicit",
            accepted_at=now,
        )
        revision_payload = _canonical_json_file_bytes(revision)
        control_text, control_bom = _decode_markdown(control)
        control_text = _insert_before_marker(
            control_text,
            "phase-plan-recheck",
            _boundary_index_block(revision, revision_relative, _sha256_payload(revision_payload)),
            "WS_TEMPLATE_INVALID",
        )
        control_text = _insert_before_marker(control_text, "phase-queue", _task_index_block([], now), "WS_TEMPLATE_INVALID")
        control = _encode_markdown(control_text, control_bom)
    changes = {
        phase_path: control,
        project_path: _encode_markdown(project_text, project_bom),
        _state_path(root): _json_bytes(updated),
    }
    if boundary_path is not None:
        changes[boundary_path] = revision_payload
    _finalize_v3_consistency(root, updated, changes, now)
    _validate_state(root, updated)
    result = _plan("open-phase", root, changes, args.apply, phase_id=phase_id, implicit_session_created=False)
    if args.apply:
        must_be_new = (phase_path,) if boundary_path is None else (phase_path, boundary_path)
        roles = {
            path: "IMMUTABLE_RECORD" if path == boundary_path else
            "PHASE_CONTROL" if path == phase_path else
            "PROJECT_CONTROL" if path == project_path else "RUNTIME_STATE"
            for path in changes
        }
        _transaction_write(root, changes, must_be_new=must_be_new, operation="open-phase", target_roles=roles)
    return result


def _replace_line(text: str, source: str, target: str, code: str) -> str:
    pattern = re.compile(rf"(?m)^{re.escape(source)}[^\r\n]*(?P<ending>\r?)$")
    if pattern.search(text) is None:
        raise WorkspaceError(code, f"Expected control token is missing: {source}")
    return pattern.sub(lambda match: target + match.group("ending"), text, count=1)


def _final_payload(root: Path, changes: dict[Path, bytes], relative: str) -> bytes | None:
    path = _target(root, relative)
    if path in changes:
        return changes[path]
    if path.is_file():
        return path.read_bytes()
    return None


def _replace_current_phase_binding(payload: bytes, values: dict[str, str], relative: str) -> bytes:
    text, bom = _decode_markdown(payload)
    section = _marked_section(text, "current-phase-binding")
    if section is None:
        raise WorkspaceError(
            "WS_CURRENT_BINDING_MISSING",
            "Current Phase binding section is required for a current report or declared handoff.",
            relative,
        )
    updated_section = section
    for label, value in values.items():
        updated_section = _replace_line(
            updated_section,
            f"- {label}:",
            f"- {label}: `{value}`",
            "WS_CURRENT_BINDING_INVALID",
        )
    return _encode_markdown(text.replace(section, updated_section, 1), bom)


def _refresh_current_phase_bindings(
    root: Path,
    state: dict[str, Any],
    changes: dict[Path, bytes],
    now: str,
) -> None:
    """Atomically project the final active Phase identity into current report/handoff files."""

    if state["schema_version"] == 1:
        return
    if state["schema_version"] in {3, 4}:
        binding = state.get("current_phase_binding")
        values = {
            "Binding schema": "3" if state["schema_version"] == 4 else "2",
            "Active Phase ID": binding["active_phase_id"] if binding is not None else "N/A",
            "Active Phase control": binding["phase_control_path"] if binding is not None else "N/A",
            "Phase control SHA-256": binding["phase_control_sha256"] if binding is not None else "N/A",
            "Phase boundary SHA-256": binding["phase_boundary_sha256"] if binding is not None else "N/A",
            "Boundary review ID": binding["boundary_review_id"] if binding is not None and binding["boundary_review_id"] is not None else "N/A",
            "Boundary review SHA-256": binding["boundary_review_sha256"] if binding is not None else "N/A",
            "Candidate mapping": binding["candidate_mapping"] if binding is not None and binding["candidate_mapping"] is not None else "N/A",
            "Recommendation": binding["recommendation"] if binding is not None and binding["recommendation"] is not None else "N/A",
            "Phase recovery SHA-256": binding["phase_recovery_sha256"] if binding is not None else "N/A",
            "Recorded at": binding["recorded_at"] if binding is not None else "N/A",
        }
    elif state["active_phase_id"] is None:
        values = {
            "Active Phase ID": "N/A",
            "Active Phase control": "N/A",
            "Phase control SHA-256": "N/A",
            "Recorded at": "N/A",
        }
    else:
        phase = _phase_entry(state, state["active_phase_id"])
        phase_payload = _final_payload(root, changes, phase["path"])
        if phase_payload is None:
            raise WorkspaceError("WS_FILE_MISSING", "Active Phase control is missing.", phase["path"])
        values = {
            "Active Phase ID": phase["phase_id"],
            "Active Phase control": phase["path"],
            "Phase control SHA-256": hashlib.sha256(phase_payload).hexdigest().upper(),
            "Recorded at": now,
        }
    for relative, required in (("WORK_TASK_REPORT.md", True), ("PROJECT_HANDOFF.md", False)):
        payload = _final_payload(root, changes, relative)
        if payload is None:
            if required:
                raise WorkspaceError("WS_FILE_MISSING", "Required current report is missing.", relative)
            continue
        changes[_target(root, relative)] = _replace_current_phase_binding(payload, values, relative)


def _normalized_section_sha256(payload: bytes, section_name: str, code: str, relative: str) -> str:
    text, _ = _decode_markdown(payload)
    try:
        section = _marked_section(text, section_name, required=True)
    except WorkspaceError as exc:
        raise WorkspaceError(code, f"Required structured section is missing or duplicated: {section_name}", relative) from exc
    assert section is not None
    normalized_lines = [line.rstrip() for line in section.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    normalized = "\n".join(normalized_lines).rstrip("\n") + "\n"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest().upper()


def _boundary_review_record(payload: bytes, relative: str) -> dict[str, str]:
    text, _ = _decode_markdown(payload)
    try:
        section = _marked_section(text, "phase-boundary-review", required=True)
        assert section is not None
        values = {
            label: _control_value(section, label, "WS_PHASE_BOUNDARY_RECORD_MISSING")
            for label in (
                "Review schema",
                "Review ID",
                "Review status",
                "Candidate mapping",
                "Recommended review",
                "Reviewed at",
                "Evidence reference",
                "Authorization reference",
            )
        }
    except WorkspaceError as exc:
        raise WorkspaceError("WS_PHASE_BOUNDARY_RECORD_MISSING", exc.message, relative) from exc
    if values["Review schema"] != "1" or values["Review status"] not in {"NOT_RUN", "RECORDED", "SUPERSEDED"}:
        raise WorkspaceError("WS_PHASE_BOUNDARY_RECORD_DRIFT", "Boundary Review record schema or status is invalid.", relative)
    if values["Candidate mapping"] not in CANDIDATE_MAPPINGS or values["Recommended review"] not in PHASE_REVIEW_RESULTS:
        raise WorkspaceError("WS_PHASE_BOUNDARY_RECORD_DRIFT", "Boundary Review mapping or recommendation is invalid.", relative)
    if values["Review status"] == "RECORDED":
        if values["Review ID"] == "N/A" or values["Reviewed at"] == "N/A" or values["Evidence reference"] == "N/A":
            raise WorkspaceError("WS_PHASE_BOUNDARY_RECORD_DRIFT", "A recorded Boundary Review requires ID, timestamp, and evidence.", relative)
        _timestamp(values["Reviewed at"])
    return values


def _load_json_object(root: Path, relative: str, code: str) -> tuple[Path, bytes, dict[str, Any]]:
    path = _target(root, relative)
    if not _path_is_file(path):
        raise WorkspaceError(code, "Required JSON file is missing.", relative)
    payload = _path_read_bytes(path)
    try:
        value = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkspaceError(code, "Required JSON file is not valid UTF-8 JSON.", relative) from exc
    if not isinstance(value, dict):
        raise WorkspaceError(code, "Required JSON root must be an object.", relative)
    return path, payload, value


def _load_event_chain(root: Path, contract: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[Path, str]]:
    task_id = str(contract["task_id"])
    directory = _target(root, f"task-state/{task_id}/events")
    if not directory.exists():
        return [], {}
    if not directory.is_dir() or directory.is_symlink():
        raise WorkspaceError("RC_LINEAGE_STALE", "Declared Result event directory must be a regular directory.", _relative(root, directory))
    rows: list[tuple[int, Path, dict[str, Any], bytes]] = []
    with os.scandir(_io_path(directory)) as entries:
        names = sorted((entry.name for entry in entries if entry.name.endswith(".json")), key=str.casefold)
    for name in names:
        match = re.fullmatch(r"([1-9][0-9]*)-([A-Za-z0-9][A-Za-z0-9._-]{0,127})\.json", name)
        if match is None:
            raise WorkspaceError("RC_LINEAGE_STALE", "Declared event directory contains an ambiguous event filename.", f"task-state/{task_id}/events/{name}")
        relative = f"task-state/{task_id}/events/{name}"
        path, payload, value = _load_json_object(root, relative, "RC_LINEAGE_STALE")
        if canonical_json(value) != payload:
            raise WorkspaceError("RC_LINEAGE_STALE", "Canonical Result event bytes do not match the required canonical JSON encoding.", relative)
        rows.append((int(match.group(1)), path, value, payload))
    rows.sort(key=lambda item: item[0])
    return [row[2] for row in rows], {row[1]: _sha256_payload(row[3]) for row in rows}


def _phase_task_control_payload(
    root: Path,
    state: dict[str, Any],
    changes: dict[Path, bytes],
    now: str,
) -> tuple[Path, bytes]:
    phase = _active_phase(state)
    phase_path = _target(root, phase["path"])
    phase_payload = _final_payload(root, changes, phase["path"])
    if phase_payload is None:
        raise WorkspaceError("WS_FILE_MISSING", "Active Phase control is missing.", phase["path"])
    text, bom = _decode_markdown(phase_payload)
    block = _task_index_block(state.get("current_task_bindings", []), now)
    text = _replace_or_insert_section(text, TASK_INDEX_MARKER, block, "phase-queue", "WS_PHASE_TASK_INDEX_INVALID")
    return phase_path, _encode_markdown(text, bom)


def _replace_task_binding(state: dict[str, Any], projection: dict[str, Any], projection_sha256: str) -> dict[str, Any]:
    row = {
        "task_id": projection["task_id"],
        "lineage_id": projection["lineage_id"],
        "phase_id": projection["phase_id"],
        "latest_contract_revision": projection["latest_contract_revision"],
        "latest_event": projection["latest_event"],
        "projection_path": f"task-state/{projection['task_id']}/RESULT_LINEAGE.json",
        "projection_sha256": projection_sha256,
        "task_status": projection["task_status"],
        "current_round_id": projection["current_round_id"],
        "current_attempt_id": projection["current_attempt_id"],
        "current_invocation_id": projection["current_invocation_id"],
        "projected_at": projection["projected_at"],
    }
    rows = [item for item in state.get("current_task_bindings", []) if item.get("task_id") != projection["task_id"]]
    if any(item.get("lineage_id") == projection["lineage_id"] for item in rows):
        raise WorkspaceError("WS_LINEAGE_BINDING_DUPLICATE", "Lineage ID is already bound to another active Task.", projection["lineage_id"])
    rows.append(row)
    state["current_task_bindings"] = sorted(rows, key=lambda item: item["task_id"])
    return row


def _v4_lease_gate(
    state: dict[str, Any],
    *,
    operation: str,
    actor_kind: str,
    actor_id: str,
    target_relatives: Iterable[str],
    lineage_id: str | None,
    at: str,
) -> None:
    if state["active_session_id"] is None:
        return
    session = _active_session(state)
    lease = session.get("lease", {})
    if lease.get("state") != "ACTIVE":
        raise WorkspaceError("WS_SESSION_LEASE_REQUIRED", "Active Session lacks an ACTIVE structured lease.", session["path"])
    if session.get("owner_kind") != actor_kind or session.get("owner_id") != actor_id:
        raise WorkspaceError("WS_SESSION_LEASE_OWNER_MISMATCH", "Actor is not the exact active Session lease owner.", session["path"])
    expiry = lease.get("expires_at")
    if expiry is not None and datetime.fromisoformat(at.replace("Z", "+00:00")) >= datetime.fromisoformat(str(expiry).replace("Z", "+00:00")):
        raise WorkspaceError("WS_SESSION_LEASE_REQUIRED", "Active Session lease is expired.", session["path"])
    if operation not in set(lease.get("allowed_operations", [])):
        raise WorkspaceError("WS_SESSION_SCOPE_VIOLATION", "Operation is outside the active Session lease.", operation)
    touch = set(lease.get("touch_set", []))
    write_scope = set(lease.get("write_scope", []))
    excluded = set(lease.get("excluded_surfaces", []))
    own_control = str(session["path"]).replace("\\", "/")
    for relative in target_relatives:
        normalized = relative.replace("\\", "/")
        in_scope = any(normalized == scope or normalized.startswith(scope.rstrip("/") + "/") for scope in write_scope)
        if normalized in excluded or not in_scope:
            raise WorkspaceError("WS_SESSION_SCOPE_VIOLATION", "Transaction target is outside the active Session lease touch set/scope.", relative)
        if normalized != own_control and normalized not in touch:
            raise WorkspaceError("WS_SESSION_SCOPE_VIOLATION", "Transaction target is outside the active Session lease touch set/scope.", relative)
    if lineage_id is not None and lineage_id not in set(lease.get("bound_lineage_ids", [])):
        raise WorkspaceError("WS_SESSION_SCOPE_VIOLATION", "Result lineage is not bound to the active Session lease.", lineage_id)


def _result_operation_id(events: list[dict[str, Any]]) -> str:
    operation_ids = {str(event.get("operation_id")) for event in events}
    if len(operation_ids) != 1:
        raise WorkspaceError("RC_EVENT_REPLAY_CONFLICT", "Every Result event in one batch must share one operation_id.")
    return next(iter(operation_ids))


def _expected_hash(value: str | None, observed: str, code: str, path: str) -> None:
    if value is not None and value.upper() != observed:
        raise WorkspaceError(code, "Expected SHA-256 no longer matches the reviewed input.", path)


def _build_result_orchestration(
    args: argparse.Namespace,
    *,
    rebuild: bool,
) -> tuple[Path, dict[str, Any], dict[Path, bytes], dict[Path, str | None], dict[Path, str], dict[str, Any], str]:
    root = _workspace(args.workspace)
    state, state_payload = _load_state_capture(root)
    _require_schema_v4(state, "rebuild-result-lineage" if rebuild else "record-result-events")
    contract_relative = args.contract
    normalized_contract = contract_relative.replace("\\", "/")
    rebuild_projection: str | None = None
    if rebuild:
        match = re.fullmatch(r"task-state/([A-Za-z0-9][A-Za-z0-9._-]{0,127})/contracts/[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.json", normalized_contract)
        if match is not None:
            rebuild_projection = f"task-state/{match.group(1)}/RESULT_LINEAGE.json"
    if rebuild_projection is not None:
        _require_consistent_mutation(root, state, allowed_paths={rebuild_projection})
    else:
        _require_consistent_mutation(root, state)
    phase = _active_phase(state)
    contract_path, contract_payload, contract = _load_json_object(root, contract_relative, "RC_LINEAGE_STALE")
    contract_hash = _sha256_payload(contract_payload)
    _expected_hash(getattr(args, "expected_contract_sha256", None), contract_hash, "RC_LINEAGE_STALE", contract_relative)
    if contract.get("contract_version") != "2":
        raise WorkspaceError("RC_V2_MIGRATION_REQUIRED", "Result event orchestration requires Result Contract v2.", contract_relative)
    if contract.get("phase_id") != phase["phase_id"]:
        raise WorkspaceError("RC_LINEAGE_STALE", "Result Contract belongs to a different Phase.", contract_relative)
    expected_contract_path = f"task-state/{contract['task_id']}/contracts/{contract['revision_id']}.json"
    if contract_relative.replace("\\", "/") != expected_contract_path:
        raise WorkspaceError("RC_LINEAGE_STALE", "Result Contract locator is not its declared canonical owner path.", contract_relative)
    committed, event_hashes = _load_event_chain(root, contract)
    projection_relative = f"task-state/{contract['task_id']}/RESULT_LINEAGE.json"
    projection_path = _target(root, projection_relative)
    projection_payload = _path_read_bytes(projection_path) if _path_is_file(projection_path) else None
    projection = None if projection_payload is None else json.loads(projection_payload.decode("utf-8-sig"))
    expected_projection = getattr(args, "expected_projection_sha256", None)
    if expected_projection is not None:
        observed_projection = "ABSENT" if projection_payload is None else _sha256_payload(projection_payload)
        if expected_projection.upper() != observed_projection:
            raise WorkspaceError("RC_LINEAGE_STALE", "Expected Result lineage projection preimage no longer matches.", projection_relative)
    if rebuild and rebuild_projection is not None:
        binding_row = next((item for item in state.get("current_task_bindings", []) if item.get("task_id") == contract["task_id"]), None)
        if binding_row is not None:
            bound_observed = "ABSENT" if projection_payload is None else _sha256_payload(projection_payload)
            if bound_observed != binding_row["projection_sha256"] and expected_projection is None:
                raise WorkspaceError("RC_LINEAGE_STALE", "Stale lineage projection requires --expected-projection-sha256 to bind the reviewed preimage.", projection_relative)
    if rebuild:
        updated_projection, decision = rebuild_lineage_projection_v2(contract, committed, MALTS_ROOT, contract_hash)
        operation_id = _validate_id(args.operation_id, "Operation ID")
    else:
        events_value = load_json(Path(args.events))
        if not isinstance(events_value, list):
            raise WorkspaceError("RC_EVENT_BATCH_EMPTY", "--events must identify a non-empty JSON array.", str(args.events))
        events = events_value
        operation_id = _result_operation_id(events)
        updated_projection, decision = apply_event_batch_v2(contract, events, projection, committed, MALTS_ROOT, contract_hash)
    if updated_projection is None:
        issue = (decision.get("issues") or [{"code": "RC_LINEAGE_STALE", "message": "Result controller denied the operation."}])[0]
        raise WorkspaceError(str(issue.get("code")), str(issue.get("message")), str(issue.get("path", contract_relative)))
    now = _timestamp(args.timestamp or updated_projection["projected_at"])
    projection_bytes = _canonical_json_file_bytes(updated_projection)
    projection_hash = _sha256_payload(projection_bytes)
    updated = json.loads(json.dumps(state))
    _replace_task_binding(updated, updated_projection, projection_hash)
    changes: dict[Path, bytes] = {projection_path: projection_bytes}
    roles: dict[Path, str] = {projection_path: "RESULT_PROJECTION"}
    if not rebuild and decision.get("decision") != "IDEMPOTENT_REPLAY":
        for event in events:
            relative = f"task-state/{contract['task_id']}/events/{event['sequence']}-{event['event_id']}.json"
            path = _target(root, relative)
            payload = _canonical_json_file_bytes(event)
            if _path_is_file(path):
                if _path_read_bytes(path) != payload:
                    raise WorkspaceError("RC_EVENT_REPLAY_CONFLICT", "Existing event path contains different bytes.", relative)
                continue
            changes[path] = payload
            roles[path] = "IMMUTABLE_RECORD"
    phase_path, phase_payload = _phase_task_control_payload(root, updated, changes, now)
    changes[phase_path] = phase_payload
    roles[phase_path] = "PHASE_CONTROL"
    updated["maintenance_state"].update({"state": "clean", "last_action": "rebuild-result-lineage" if rebuild else "record-result-events", "last_checked_at": now})
    updated["recovery_point"] = {
        "summary": f"Task {contract['task_id']} lineage head is bound at {updated_projection['latest_event']['event_id'] if updated_projection['latest_event'] else 'NO_EVENTS'}.",
        "next_action": "Continue only from the exact Result lineage head and current Phase boundary revision.",
        "evidence_refs": [f"lineage:{contract['lineage_id']}", f"projection:{projection_relative}"],
    }
    _finalize_v4_consistency(root, updated, changes, now)
    for relative, role in (("WORK_TASK_REPORT.md", "REPORT"), ("PROJECT_HANDOFF.md", "HANDOFF"), ("PROJECT_CONTROL.md", "PROJECT_CONTROL")):
        path = _target(root, relative)
        if path in changes:
            roles[path] = role
    roles[_state_path(root)] = "RUNTIME_STATE"
    target_relatives = [_relative(root, path) for path in changes]
    actor_kind = str(getattr(args, "actor_kind", "MAIN_CONTROLLER"))
    actor_id = str(getattr(args, "actor_id", "MAIN_CONTROLLER"))
    _v4_lease_gate(
        updated,
        operation="rebuild-result-lineage" if rebuild else "record-result-events",
        actor_kind=actor_kind,
        actor_id=actor_id,
        target_relatives=target_relatives,
        lineage_id=str(contract["lineage_id"]),
        at=now,
    )
    preconditions = {
        path: _sha256_path(path) if _path_is_file(path) else None
        for path in changes
    }
    preconditions[contract_path] = contract_hash
    for path, event_hash in event_hashes.items():
        preconditions[path] = event_hash
    preconditions[_state_path(root)] = _sha256_payload(state_payload)
    return root, updated, changes, preconditions, roles, decision, operation_id


def command_record_result_events(args: argparse.Namespace) -> dict[str, Any]:
    root, _, changes, preconditions, roles, decision, operation_id = _build_result_orchestration(args, rebuild=False)
    preview = _transaction_preview(root, operation_id=operation_id, operation="record-result-events", changes=changes, preconditions=preconditions, target_roles=roles)
    if args.apply:
        expected = _require_expected_sha256(args.expected_plan_sha256, "WS_TRANSACTION_PLAN_STALE", "Expected transaction plan SHA-256")
        if expected != preview["plan_sha256"]:
            raise WorkspaceError("WS_TRANSACTION_PLAN_STALE", "Apply plan SHA-256 differs from the deterministic current preview.")
        receipt = _apply_transaction_plan(root, operation_id=operation_id, operation="record-result-events", changes=changes, preconditions=preconditions, target_roles=roles, expected_plan_sha256=expected)
    else:
        receipt = None
    return {
        "status": "PASS", "operation": "record-result-events", "mode": "APPLY" if args.apply else "DRY_RUN",
        "workspace": str(root), "writes_performed": bool(args.apply and receipt and receipt.get("writes_performed")),
        "plan": preview, "controller_decision": decision, "receipt": receipt, "implicit_session_created": False,
    }


def command_rebuild_result_lineage(args: argparse.Namespace) -> dict[str, Any]:
    root, _, changes, preconditions, roles, decision, operation_id = _build_result_orchestration(args, rebuild=True)
    preview = _transaction_preview(root, operation_id=operation_id, operation="rebuild-result-lineage", changes=changes, preconditions=preconditions, target_roles=roles)
    if args.apply:
        expected = _require_expected_sha256(args.expected_plan_sha256, "WS_TRANSACTION_PLAN_STALE", "Expected transaction plan SHA-256")
        if expected != preview["plan_sha256"]:
            raise WorkspaceError("WS_TRANSACTION_PLAN_STALE", "Apply plan SHA-256 differs from the deterministic current preview.")
        receipt = _apply_transaction_plan(root, operation_id=operation_id, operation="rebuild-result-lineage", changes=changes, preconditions=preconditions, target_roles=roles, expected_plan_sha256=expected)
    else:
        receipt = None
    return {
        "status": "PASS", "operation": "rebuild-result-lineage", "mode": "APPLY" if args.apply else "DRY_RUN",
        "workspace": str(root), "writes_performed": bool(args.apply and receipt and receipt.get("writes_performed")),
        "plan": preview, "controller_decision": decision, "receipt": receipt, "implicit_session_created": False,
    }


def _replace_phase_boundary_projection(text: str, boundary_values: dict[str, str]) -> str:
    section = _marked_section(text, "phase-boundary", required=True)
    assert section is not None
    updated = section
    for _, label, placeholder in PHASE_BOUNDARY_FIELDS:
        updated = _replace_line(updated, f"- {label}:", f"- {label}: {boundary_values[placeholder]}", "WS_PHASE_BOUNDARY_RECORD_MISSING")
    return text.replace(section, updated, 1)


def _build_phase_amendment(args: argparse.Namespace) -> tuple[Path, dict[Path, bytes], dict[Path, str | None], dict[Path, str], dict[str, Any], str]:
    root = _workspace(args.workspace)
    state, state_payload = _load_state_capture(root)
    _require_schema_v4(state, "phase-boundary-amendment")
    _require_consistent_mutation(root, state)
    phase = _active_phase(state)
    if phase.get("status") in V4_TERMINAL_PHASE_STATES:
        raise WorkspaceError("WS_PHASE_TERMINAL_IMMUTABLE", "A terminal Phase boundary is immutable.", phase["path"])
    phase_path, phase_payload, phase_text, phase_bom = _phase_control_info(root, phase)
    current = _boundary_revision_binding(root, phase_payload, phase)
    current_path, current_payload, current_document = _load_json_object(root, current["path"], "WS_PHASE_AMENDMENT_STALE")
    _expected_hash(getattr(args, "expected_phase_sha256", None), _sha256_payload(phase_payload), "WS_PHASE_AMENDMENT_STALE", phase["path"])
    _expected_hash(getattr(args, "expected_boundary_sha256", None), _sha256_payload(current_payload), "WS_PHASE_AMENDMENT_STALE", current["path"])
    binding = state["current_phase_binding"]
    if binding.get("active_plan_path") is not None:
        plan_path = _target(root, binding["active_plan_path"])
        if not _path_is_file(plan_path) or _sha256_path(plan_path) != binding["active_plan_sha256"]:
            raise WorkspaceError("WS_PHASE_AMENDMENT_STALE", "Active Phase plan changed or is missing.", binding["active_plan_path"])
    boundary_values = _phase_boundary_values(args, required=True)
    revision_id = _validate_id(args.revision_id, "Boundary revision ID")
    revision_relative = f"phases/{phase['phase_id']}/boundary-revisions/{revision_id}.json"
    revision_path = _target(root, revision_relative)
    accepted_at = _timestamp(args.accepted_at)
    revision = _boundary_revision_document(
        phase_id=phase["phase_id"],
        revision_id=revision_id,
        revision_number=int(current_document["revision_number"]) + 1,
        previous_revision={"revision_id": current["revision_id"], "path": current["path"], "sha256": current["sha256"]},
        boundary_values=boundary_values,
        review_id=_validate_id(args.review_id, "Boundary review ID"),
        review_evidence_refs=[_require_reference(value, "WS_PHASE_AMENDMENT_STALE", "Review evidence") for value in args.review_evidence_ref],
        authorization_ref=_require_reference(args.authorization_ref, "WS_PHASE_AMENDMENT_STALE", "Authorization reference"),
        accepted_at=accepted_at,
    )
    issues = validate_instance(MALTS_ROOT, "phase-boundary-revision", revision)
    if issues:
        first = issues[0]
        raise WorkspaceError("WS_PHASE_AMENDMENT_STALE", first.message, first.path)
    revision_payload = _canonical_json_file_bytes(revision)
    revision_hash = _sha256_payload(revision_payload)
    phase_text = _replace_phase_boundary_projection(phase_text, boundary_values)
    phase_text = _replace_or_insert_section(
        phase_text,
        BOUNDARY_INDEX_MARKER,
        _boundary_index_block(revision, revision_relative, revision_hash),
        "phase-plan-recheck",
        "WS_PHASE_BOUNDARY_RECORD_MISSING",
    )
    phase_text = _replace_line(phase_text, "- Updated at:", f"- Updated at: {accepted_at}", "WS_PHASE_CONTROL_INVALID")
    updated_phase_payload = _encode_markdown(phase_text, phase_bom)
    updated = json.loads(json.dumps(state))
    updated["maintenance_state"].update({"state": "clean", "last_action": "apply-phase-boundary-amendment", "last_checked_at": accepted_at})
    changes: dict[Path, bytes] = {revision_path: revision_payload, phase_path: updated_phase_payload}
    _finalize_v4_consistency(root, updated, changes, accepted_at)
    roles = {
        path: "IMMUTABLE_RECORD" if path == revision_path else
        "PHASE_CONTROL" if path == phase_path else
        "REPORT" if _relative(root, path) == "WORK_TASK_REPORT.md" else
        "HANDOFF" if _relative(root, path) == "PROJECT_HANDOFF.md" else
        "PROJECT_CONTROL" if _relative(root, path) == "PROJECT_CONTROL.md" else "RUNTIME_STATE"
        for path in changes
    }
    _v4_lease_gate(
        updated,
        operation="apply-phase-boundary-amendment",
        actor_kind=args.actor_kind,
        actor_id=args.actor_id,
        target_relatives=[_relative(root, path) for path in changes],
        lineage_id=None,
        at=accepted_at,
    )
    preconditions = {path: _sha256_path(path) if _path_is_file(path) else None for path in changes}
    preconditions[_state_path(root)] = _sha256_payload(state_payload)
    preconditions[current_path] = _sha256_payload(current_payload)
    if binding.get("active_plan_path") is not None:
        preconditions[_target(root, binding["active_plan_path"])] = binding["active_plan_sha256"]
    operation_id = _validate_id(args.operation_id, "Operation ID")
    return root, changes, preconditions, roles, revision, operation_id


def command_plan_phase_boundary_amendment(args: argparse.Namespace) -> dict[str, Any]:
    root, changes, preconditions, roles, revision, operation_id = _build_phase_amendment(args)
    preview = _transaction_preview(root, operation_id=operation_id, operation="phase-boundary-amendment", changes=changes, preconditions=preconditions, target_roles=roles)
    return {
        "status": "PASS", "operation": "plan-phase-boundary-amendment", "mode": "DRY_RUN",
        "workspace": str(root), "writes_performed": False, "proposed_revision": revision,
        "proposed_revision_sha256": _sha256_payload(_canonical_json_file_bytes(revision)), "plan": preview,
        "implicit_session_created": False,
    }


def command_apply_phase_boundary_amendment(args: argparse.Namespace) -> dict[str, Any]:
    root, changes, preconditions, roles, revision, operation_id = _build_phase_amendment(args)
    preview = _transaction_preview(root, operation_id=operation_id, operation="phase-boundary-amendment", changes=changes, preconditions=preconditions, target_roles=roles)
    receipt = None
    if args.apply:
        expected = _require_expected_sha256(args.expected_plan_sha256, "WS_PHASE_AMENDMENT_STALE", "Expected amendment plan SHA-256")
        if expected != preview["plan_sha256"]:
            raise WorkspaceError("WS_PHASE_AMENDMENT_STALE", "Apply amendment plan differs from its exact reviewed preview.")
        receipt = _apply_transaction_plan(root, operation_id=operation_id, operation="phase-boundary-amendment", changes=changes, preconditions=preconditions, target_roles=roles, expected_plan_sha256=expected)
    return {
        "status": "PASS", "operation": "apply-phase-boundary-amendment", "mode": "APPLY" if args.apply else "DRY_RUN",
        "workspace": str(root), "writes_performed": bool(receipt and receipt.get("writes_performed")),
        "proposed_revision": revision, "plan": preview, "receipt": receipt, "implicit_session_created": False,
    }


def _replace_or_insert_lease_section(text: str, session: dict[str, Any]) -> str:
    lease = session["lease"]
    block = (
        "<!-- MALTS:section=session-lease -->\n"
        "## Structured Session Lease\n\n"
        f"- Owner kind: `{session['owner_kind']}`\n"
        f"- Owner ID: `{session['owner_id']}`\n"
        f"- Lease ID: `{lease['lease_id']}`\n"
        f"- Lease state: `{lease['state']}`\n"
        f"- Granted at: `{lease['granted_at']}`\n"
        f"- Expires at: `{lease['expires_at'] if lease['expires_at'] is not None else 'N/A'}`\n"
        f"- Authorization reference: `{lease['authorization_ref']}`\n"
        f"- Allowed operations: `{';'.join(lease['allowed_operations'])}`\n"
        f"- Read scope: `{';'.join(lease['read_scope']) if lease['read_scope'] else 'N/A'}`\n"
        f"- Write scope: `{';'.join(lease['write_scope'])}`\n"
        f"- Touch set: `{';'.join(lease['touch_set'])}`\n"
        f"- Excluded surfaces: `{';'.join(lease['excluded_surfaces']) if lease['excluded_surfaces'] else 'N/A'}`\n"
        f"- Bound lineage IDs: `{';'.join(lease['bound_lineage_ids']) if lease['bound_lineage_ids'] else 'N/A'}`\n"
        f"- Checkpoint SHA-256: `{lease['checkpoint_sha256']}`\n"
        f"- Evidence references: `{';'.join(lease['evidence_refs'])}`\n"
    )
    return _replace_or_insert_section(text, "session-lease", block, "session-plan-binding", "WS_SESSION_CONTROL_INVALID")


def command_transfer_session_lease(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state, state_payload = _load_state_capture(root)
    _require_schema_v4(state, "transfer-session-lease")
    _require_consistent_mutation(root, state)
    session = _active_session(state)
    now = _timestamp(args.timestamp)
    if session["lease"]["state"] != "ACTIVE":
        raise WorkspaceError("WS_SESSION_LEASE_REQUIRED", "Only an ACTIVE Session lease may transfer.", session["path"])
    if session["owner_kind"] != args.actor_kind or session["owner_id"] != args.actor_id:
        raise WorkspaceError("WS_SESSION_LEASE_OWNER_MISMATCH", "Only the current exact Session lease owner may transfer ownership.", session["path"])
    session_path, session_payload, session_text, session_bom = _phase_control_info(root, {"path": session["path"]})
    _expected_hash(args.expected_session_sha256, _sha256_payload(session_payload), "WS_TRANSACTION_PLAN_STALE", session["path"])
    new_owner_kind = args.new_owner_kind
    new_owner_id = _validate_id(args.new_owner_id, "New owner ID")
    new_lease_id = _validate_id(args.new_lease_id, "New lease ID")
    authorization_ref = _require_reference(args.authorization_ref, "WS_SESSION_LEASE_REQUIRED", "New owner authorization")
    updated = json.loads(json.dumps(state))
    row = next(item for item in updated["session_controls"] if item["session_id"] == session["session_id"])
    row["owner_kind"] = new_owner_kind
    row["owner_id"] = new_owner_id
    row["updated_at"] = now
    row["lease"]["lease_id"] = new_lease_id
    row["lease"]["granted_at"] = now
    row["lease"]["expires_at"] = args.expires_at
    row["lease"]["authorization_ref"] = authorization_ref
    row["lease"]["evidence_refs"] = [_require_reference(value, "WS_SESSION_LEASE_REQUIRED", "Transfer evidence") for value in args.evidence_ref]
    session_text = _replace_line(session_text, "- Updated at:", f"- Updated at: {now}", "WS_SESSION_CONTROL_INVALID")
    session_text = _replace_or_insert_lease_section(session_text, row)
    changes: dict[Path, bytes] = {session_path: _encode_markdown(session_text, session_bom)}
    updated["maintenance_state"].update({"state": "clean", "last_action": "transfer-session-lease", "last_checked_at": now})
    _finalize_v4_consistency(root, updated, changes, now)
    roles = {
        path: "SESSION_CONTROL" if path == session_path else
        "PHASE_CONTROL" if _relative(root, path).endswith("PHASE_CONTROL.md") else
        "REPORT" if _relative(root, path) == "WORK_TASK_REPORT.md" else
        "HANDOFF" if _relative(root, path) == "PROJECT_HANDOFF.md" else
        "PROJECT_CONTROL" if _relative(root, path) == "PROJECT_CONTROL.md" else "RUNTIME_STATE"
        for path in changes
    }
    preconditions = {path: _sha256_path(path) if _path_is_file(path) else None for path in changes}
    preconditions[_state_path(root)] = _sha256_payload(state_payload)
    operation_id = _validate_id(args.operation_id, "Operation ID")
    preview = _transaction_preview(root, operation_id=operation_id, operation="transfer-session-lease", changes=changes, preconditions=preconditions, target_roles=roles)
    receipt = None
    if args.apply:
        expected = _require_expected_sha256(args.expected_plan_sha256, "WS_TRANSACTION_PLAN_STALE", "Expected lease transfer plan SHA-256")
        if expected != preview["plan_sha256"]:
            raise WorkspaceError("WS_TRANSACTION_PLAN_STALE", "Lease transfer plan differs from its exact reviewed preview.")
        receipt = _apply_transaction_plan(root, operation_id=operation_id, operation="transfer-session-lease", changes=changes, preconditions=preconditions, target_roles=roles, expected_plan_sha256=expected)
    return {
        "status": "PASS", "operation": "transfer-session-lease", "mode": "APPLY" if args.apply else "DRY_RUN",
        "workspace": str(root), "writes_performed": bool(receipt and receipt.get("writes_performed")),
        "session_id": session["session_id"], "new_owner_kind": new_owner_kind, "new_owner_id": new_owner_id,
        "new_lease_id": new_lease_id, "plan": preview, "receipt": receipt, "implicit_session_created": False,
    }


def _artifact_transaction_incomplete(root: Path) -> bool:
    lock_path = _target(root, "runtime/artifact_transaction.lock.json")
    return _path_is_file(lock_path)


def _declared_lineage_rows(root: Path, values: list[str] | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for value in values or []:
        if "=" not in value:
            raise WorkspaceError("WS_MIGRATION_LINEAGE_INPUT_INVALID", "Declared lineage rows must use RELATIVE=SHA256.", value)
        relative, expected = value.split("=", 1)
        relative = relative.replace("\\", "/")
        path = _target(root, relative)
        if not _path_is_file(path):
            raise WorkspaceError("WS_MIGRATION_LINEAGE_INPUT_INVALID", "Declared lineage file is missing.", relative)
        observed = _sha256_path(path)
        if expected.upper() != observed:
            raise WorkspaceError("WS_TRANSACTION_PLAN_STALE", "Declared lineage hash does not match the reviewed input.", relative)
        try:
            document = json.loads(_path_read_bytes(path).decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            document = None
        if isinstance(document, dict) and document.get("execution_status") in {"EXECUTING", "VERIFYING"}:
            raise WorkspaceError("WS_MIGRATION_NOT_QUIESCENT", "A declared lineage is still EXECUTING or VERIFYING.", relative)
        rows.append({"path": relative, "role": "DECLARED_LINEAGE", "sha256": observed})
    return rows


def _migration_plan_document(values: dict[str, Any]) -> dict[str, Any]:
    plan_sha256 = _sha256_payload(canonical_json(values))
    document = json.loads(json.dumps(values))
    document["plan_sha256"] = plan_sha256
    return document


def command_migrate_workspace_v3_to_v4(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state, state_payload = _load_state_capture(root)
    if state["schema_version"] != 3:
        raise WorkspaceError(
            "WS_MIGRATION_SOURCE_SCHEMA",
            "migrate-workspace-v3-to-v4 requires workspace-control schema exactly 3.",
            STATE_RELATIVE.as_posix(),
        )
    expected_state = _require_expected_sha256(args.expected_state_sha256, "WS_TRANSACTION_PLAN_STALE", "Expected workspace state SHA-256")
    if expected_state != _sha256_payload(state_payload):
        raise WorkspaceError("WS_TRANSACTION_PLAN_STALE", "Workspace state changed after review.", STATE_RELATIVE.as_posix())
    _require_no_incomplete_workspace_transaction(root)
    if _artifact_transaction_incomplete(root):
        raise WorkspaceError("WS_MIGRATION_NOT_QUIESCENT", "An incomplete Artifact transaction blocks workspace migration.")
    if state["active_session_id"] is not None:
        raise WorkspaceError("WS_MIGRATION_NOT_QUIESCENT", "Close the active Session before workspace migration.")
    if state["active_phase_id"] is not None:
        raise WorkspaceError("WS_MIGRATION_NOT_QUIESCENT", "Pause the active Phase before workspace migration.")
    declared_lineages = _declared_lineage_rows(root, getattr(args, "declared_lineage", None))
    now = _timestamp(args.timestamp)
    updated = json.loads(json.dumps(state))
    updated["schema_version"] = 4
    updated["current_task_bindings"] = []
    updated["current_session_binding"] = None
    updated["maintenance_state"].update({"state": "clean", "last_action": "migrate-workspace-v3-to-v4", "last_checked_at": now})
    changes: dict[Path, bytes] = {}
    paused_phase: dict[str, Any] | None = None
    paused_plan_sha256: str | None = None
    paused_boundary_sha256: str | None = None
    paused_recovery_sha256: str | None = None
    revision_relative: str | None = None
    revision_document: dict[str, Any] | None = None
    review_ref = "migration:v3-to-v4"
    authorization_ref = "migration:v3-to-v4"
    if getattr(args, "paused_phase_id", None) is not None:
        paused_phase = _phase_entry(state, args.paused_phase_id)
        if paused_phase["status"] != "PAUSED":
            raise WorkspaceError("WS_MIGRATION_NOT_QUIESCENT", "The declared Phase must be PAUSED before workspace migration.", paused_phase["path"])
        phase_path, phase_payload, phase_text, phase_bom = _phase_control_info(root, paused_phase)
        _expected_hash(args.expected_phase_sha256, _sha256_payload(phase_payload), "WS_TRANSACTION_PLAN_STALE", paused_phase["path"])
        if _markdown_phase_status(phase_text) != "PAUSED":
            raise WorkspaceError("WS_PHASE_CONTROL_DRIFT", "Runtime and Markdown Phase status disagree.", paused_phase["path"])
        boundary = _phase_boundary_contract(phase_text)
        if boundary["status"] != "COMPLETE":
            raise WorkspaceError("WS_MIGRATION_NOT_QUIESCENT", "The paused Phase requires a complete Boundary Contract.", paused_phase["path"])
        paused_boundary_sha256 = _normalized_section_sha256(phase_payload, "phase-boundary", "WS_PHASE_BOUNDARY_RECORD_MISSING", paused_phase["path"])
        _expected_hash(args.expected_boundary_sha256, paused_boundary_sha256, "WS_TRANSACTION_PLAN_STALE", paused_phase["path"])
        paused_recovery_sha256 = _normalized_section_sha256(phase_payload, "phase-recovery", "WS_RECOVERY_RECORD_DRIFT", paused_phase["path"])
        _expected_hash(args.expected_recovery_sha256, paused_recovery_sha256, "WS_TRANSACTION_PLAN_STALE", paused_phase["path"])
        plan_binding = _phase_plan_binding(root, paused_phase)
        expected_plan = (getattr(args, "expected_paused_plan_sha256", None) or "N/A").upper()
        if plan_binding is None or plan_binding["Active plan"] == "N/A":
            if expected_plan != "N/A":
                raise WorkspaceError("WS_PHASE_PLAN_STALE", "A Phase without an active plan must use --expected-plan-sha256 N/A.", paused_phase["path"])
            paused_plan_sha256 = None
        else:
            plan_path = _target(root, plan_binding["Active plan"])
            if not _path_is_file(plan_path):
                raise WorkspaceError("WS_PHASE_PLAN_STALE", "The active plan file is missing.", plan_binding["Active plan"])
            observed_plan = _sha256_path(plan_path)
            if expected_plan != observed_plan or plan_binding["Plan content SHA-256"].upper() != expected_plan:
                raise WorkspaceError("WS_PHASE_PLAN_STALE", "Active plan bytes or binding disagree with the reviewed SHA-256.", plan_binding["Active plan"])
            paused_plan_sha256 = expected_plan
        review_ref = _require_reference(getattr(args, "pause_review_ref", None), "WS_MIGRATION_REVIEW_REQUIRED", "Pause review reference")
        authorization_ref = _require_reference(getattr(args, "pause_authorization_ref", None), "WS_MIGRATION_AUTHORIZATION_REQUIRED", "Pause authorization reference")
        revision_id = f"{paused_phase['phase_id']}-boundary-r001"
        revision_relative = f"phases/{paused_phase['phase_id']}/boundary-revisions/{revision_id}.json"
        revision_path = _target(root, revision_relative)
        if revision_path.exists():
            raise WorkspaceError("WS_FILE_EXISTS", "Refusing to overwrite an existing Phase boundary revision.", revision_relative)
        boundary_values = {placeholder: boundary["fields"][label] for _, label, placeholder in PHASE_BOUNDARY_FIELDS}
        revision_document = _boundary_revision_document(
            phase_id=paused_phase["phase_id"],
            revision_id=revision_id,
            revision_number=1,
            previous_revision=None,
            boundary_values=boundary_values,
            review_id=review_ref,
            review_evidence_refs=[review_ref, "migration:v3-to-v4"],
            authorization_ref=authorization_ref,
            accepted_at=now,
        )
        revision_payload = _canonical_json_file_bytes(revision_document)
        changes[revision_path] = revision_payload
        phase_text = _replace_or_insert_section(
            phase_text,
            BOUNDARY_INDEX_MARKER,
            _boundary_index_block(revision_document, revision_relative, _sha256_payload(revision_payload)),
            "phase-plan-recheck",
            "WS_TEMPLATE_INVALID",
        )
        phase_text = _replace_or_insert_section(phase_text, TASK_INDEX_MARKER, _task_index_block([], now), "phase-queue", "WS_TEMPLATE_INVALID")
        changes[phase_path] = _encode_markdown(phase_text, phase_bom)
        updated["recovery_point"] = {
            "summary": f"Phase {paused_phase['phase_id']} remains PAUSED across the explicit workspace v4 migration.",
            "next_action": "Validate v4, cold-recover, then explicitly resume with reviewed boundary, plan, and authorization.",
            "evidence_refs": [review_ref, authorization_ref, "migration:v3-to-v4"],
        }
        terminal_phase_id: str | None = paused_phase["phase_id"]
    else:
        updated["recovery_point"] = {
            "summary": "Workspace migrated to schema v4 with no active or paused Phase.",
            "next_action": "Open a new outcome-oriented Phase or explicitly resume an existing one.",
            "evidence_refs": ["migration:v3-to-v4"],
        }
        updated["recovery_binding"] = None
        terminal_phase_id = None
    _finalize_v4_consistency(root, updated, changes, now, terminal_phase_id=terminal_phase_id)
    state_bytes = changes[_state_path(root)]
    input_rows: list[dict[str, str]] = [
        {"path": STATE_RELATIVE.as_posix(), "role": "WORKSPACE_STATE", "sha256": _sha256_payload(state_payload)},
    ]
    input_rows.extend(declared_lineages)
    invariant_source_path = MALTS_ROOT / "tools" / "lifecycle_invariants.json"
    input_rows.append({"path": "tools/lifecycle_invariants.json", "role": "INVARIANT_SOURCE", "sha256": _sha256_path(invariant_source_path)})
    if paused_phase is not None:
        input_rows.append({"path": paused_phase["path"], "role": "PHASE_CONTROL", "sha256": args.expected_phase_sha256.upper()})
    report_path = _target(root, "WORK_TASK_REPORT.md")
    report_hash = _sha256_path(report_path)
    input_rows.append({"path": "WORK_TASK_REPORT.md", "role": "REPORT", "sha256": report_hash})
    handoff_path = _target(root, "PROJECT_HANDOFF.md")
    handoff_hash: str | None = None
    if _path_is_file(handoff_path):
        handoff_hash = _sha256_path(handoff_path)
        input_rows.append({"path": "PROJECT_HANDOFF.md", "role": "HANDOFF", "sha256": handoff_hash})
    output_rows: list[dict[str, Any]] = []
    preimage_rows: list[dict[str, str | None]] = []
    created_outputs: list[str] = []
    for path in sorted(changes, key=lambda item: _relative(root, item)):
        relative = _relative(root, path)
        payload = changes[path]
        role = "BOUNDARY_REVISION" if path == _target(root, revision_relative or "none") else (
            "PHASE_CONTROL" if relative.endswith("PHASE_CONTROL.md") else
            "REPORT" if relative == "WORK_TASK_REPORT.md" else
            "HANDOFF" if relative == "PROJECT_HANDOFF.md" else "WORKSPACE_STATE"
        )
        output_rows.append({"path": relative, "role": role, "bytes": len(payload), "sha256": _sha256_payload(payload)})
        preimage_rows.append({"path": relative, "sha256": _sha256_path(path) if _path_is_file(path) else None})
        if not _path_is_file(path):
            created_outputs.append(relative)
    plan_values: dict[str, Any] = {
        "schema_version": 1,
        "operation_id": args.operation_id,
        "operation": "migrate-workspace-v3-to-v4",
        "plan_id": args.operation_id,
        "workspace_identity": {"project_id": state["project_id"]},
        "source_schema_version": 3,
        "target_schema_version": 4,
        "inputs": input_rows,
        "outputs": output_rows,
        "paused_phase": None if paused_phase is None else {
            "phase_id": paused_phase["phase_id"],
            "path": paused_phase["path"],
            "status": "PAUSED",
            "phase_control_sha256": args.expected_phase_sha256.upper(),
            "phase_boundary_sha256": paused_boundary_sha256,
            "plan_sha256": paused_plan_sha256,
            "phase_recovery_sha256": paused_recovery_sha256,
            "pause_review_ref": review_ref,
            "pause_authorization_ref": authorization_ref,
            "resume_required": True,
        },
        "compatibility": {
            "result": "COMPATIBLE",
            "added_fields": ["current_session_binding", "current_task_bindings", "phase-boundary-revision-index", "task-lineage-index"],
            "changed_fields": ["schema_version", "current_phase_binding", "recovery_binding"],
            "legacy_read_preserved": True,
        },
        "rollback": {"preimages": preimage_rows, "created_outputs": created_outputs},
        "declarations": {
            "implicit_session_created": False,
            "recursive_discovery_performed": False,
            "git_or_network_performed": False,
            "active_runtime_or_public_touched": False,
        },
    }
    migration_plan = _migration_plan_document(plan_values)
    plan_issues = validate_instance(MALTS_ROOT, "workspace-migration-plan", migration_plan)
    if plan_issues:
        first = plan_issues[0]
        raise WorkspaceError("WS_MIGRATION_PLAN_INVALID", f"{first.code}: {first.message}", first.path)
    preconditions = {
        path: _sha256_path(path) if _path_is_file(path) else None
        for path in changes
    }
    preconditions[_state_path(root)] = _sha256_payload(state_payload)
    if paused_phase is not None:
        preconditions[_target(root, paused_phase["path"])] = args.expected_phase_sha256.upper()
    roles: dict[Path, str] = {}
    for path in changes:
        relative = _relative(root, path)
        if "/boundary-revisions/" in relative:
            roles[path] = "IMMUTABLE_RECORD"
        elif relative.endswith("PHASE_CONTROL.md"):
            roles[path] = "PHASE_CONTROL"
        elif relative == "WORK_TASK_REPORT.md":
            roles[path] = "REPORT"
        elif relative == "PROJECT_HANDOFF.md":
            roles[path] = "HANDOFF"
        else:
            roles[path] = "RUNTIME_STATE"
    preview = _transaction_preview(root, operation_id=args.operation_id, operation="migrate-workspace-v3-to-v4", changes=changes, preconditions=preconditions, target_roles=roles)
    receipt = None
    if args.apply:
        expected = _require_expected_sha256(args.expected_plan_sha256, "WS_TRANSACTION_PLAN_STALE", "Expected migration plan SHA-256")
        if expected != migration_plan["plan_sha256"]:
            raise WorkspaceError("WS_TRANSACTION_PLAN_STALE", "Migration plan SHA-256 differs from the reviewed plan.")
        receipt = _apply_transaction_plan(root, operation_id=args.operation_id, operation="migrate-workspace-v3-to-v4", changes=changes, preconditions=preconditions, target_roles=roles, expected_plan_sha256=preview["plan_sha256"], fault_point=os.environ.get("MALTS_TEST_WORKSPACE_FAULT_POINT"))
    return {
        "status": "PASS",
        "operation": "migrate-workspace-v3-to-v4",
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "workspace": str(root),
        "writes_performed": bool(receipt and receipt.get("writes_performed")),
        "source_schema_version": 3,
        "target_schema_version": 4,
        "paused_phase_id": None if paused_phase is None else paused_phase["phase_id"],
        "migration_plan": migration_plan,
        "transaction": preview,
        "receipt": receipt,
        "implicit_session_created": False,
    }


def command_migrate_result_contract_v1_to_v2(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state, state_payload = _load_state_capture(root)
    if state["schema_version"] not in {3, 4}:
        raise WorkspaceError(
            "WS_SCHEMA_V4_MIGRATION_REQUIRED",
            "Result Contract migration requires workspace-control schema v3 or v4.",
            STATE_RELATIVE.as_posix(),
        )
    _require_consistent_mutation(root, state)
    contract_relative = args.contract.replace("\\", "/")
    contract_path, contract_payload, v1_contract = _load_json_object(root, contract_relative, "RC_V2_MIGRATION_REQUIRED")
    v1_sha256 = _sha256_payload(contract_payload)
    _expected_hash(args.expected_contract_sha256, v1_sha256, "RC_V2_MIGRATION_REQUIRED", contract_relative)
    if v1_contract.get("contract_version") != "1":
        raise WorkspaceError("RC_V2_MIGRATION_REQUIRED", "Only Result Contract v1 can migrate to v2.", contract_relative)
    task_id = _validate_id(args.task_id, "Task ID")
    lineage_id = _validate_id(args.lineage_id, "Lineage ID")
    phase_id = _validate_id(args.phase_id, "Phase ID")
    phase_entry = _phase_entry(state, phase_id)
    if state["schema_version"] == 4:
        binding = state["current_phase_binding"]
        if binding is None or binding["active_phase_id"] != phase_id:
            raise WorkspaceError("RC_V2_MIGRATION_REQUIRED", "A v4 workspace requires the active Phase to own the migrated Task.", phase_entry["path"])
        boundary_revision_id = binding["boundary_revision_id"]
        boundary_revision_sha256 = binding["boundary_revision_sha256"]
        _expected_hash(args.expected_phase_boundary_sha256, boundary_revision_sha256, "RC_V2_MIGRATION_REQUIRED", binding["boundary_revision_path"])
        binding_mode = "V4_BOUND"
    else:
        phase_path, phase_payload, phase_text, _ = _phase_control_info(root, phase_entry)
        boundary = _phase_boundary_contract(phase_text)
        if boundary["status"] != "COMPLETE":
            raise WorkspaceError("RC_V2_MIGRATION_REQUIRED", "The target Phase requires a complete Boundary Contract.", phase_entry["path"])
        boundary_revision_id = f"{phase_id}-boundary-pending"
        boundary_revision_sha256 = _normalized_section_sha256(phase_payload, "phase-boundary", "WS_PHASE_BOUNDARY_RECORD_MISSING", phase_entry["path"])
        _expected_hash(args.expected_phase_boundary_sha256, boundary_revision_sha256, "RC_V2_MIGRATION_REQUIRED", phase_entry["path"])
        binding_mode = "PENDING_WORKSPACE_BINDING"
    now = _timestamp(args.timestamp)
    review_ref = _require_reference(args.review_ref, "RC_V2_MIGRATION_REQUIRED", "Migration review reference")
    authorization_ref = _require_reference(args.authorization_ref, "RC_V2_MIGRATION_REQUIRED", "Migration authorization reference")
    revision_id = args.revision_id or f"{task_id}-RCV2-001"
    revision_id = _validate_id(revision_id, "Result Contract revision ID")
    event_id = args.event_id or f"{task_id}-LEGACY-IMPORT-001"
    event_id = _validate_id(event_id, "Import event ID")
    try:
        planned = result_migration.plan_result_contract_migration(
            MALTS_ROOT,
            v1_contract,
            v1_relative=contract_relative,
            v1_sha256=v1_sha256,
            lineage_id=lineage_id,
            task_id=task_id,
            phase_id=phase_id,
            phase_boundary_revision_id=boundary_revision_id,
            phase_boundary_revision_sha256=boundary_revision_sha256,
            revision_id=revision_id,
            event_id=event_id,
            operation_id=args.operation_id,
            review_ref=review_ref,
            authorization_ref=authorization_ref,
            recorded_at=now,
        )
    except ValueError as exc:
        raise WorkspaceError("RC_V2_MIGRATION_REQUIRED", str(exc), contract_relative) from exc
    changes: dict[Path, bytes] = {
        _target(root, planned["contract_relative"]): planned["contract_payload"],
        _target(root, planned["event_relative"]): planned["event_payload"],
        _target(root, planned["projection_relative"]): _canonical_json_file_bytes(planned["projection"]),
    }
    roles = {
        _target(root, planned["contract_relative"]): "IMMUTABLE_RECORD",
        _target(root, planned["event_relative"]): "IMMUTABLE_RECORD",
        _target(root, planned["projection_relative"]): "RESULT_PROJECTION",
    }
    updated = json.loads(json.dumps(state))
    if binding_mode == "V4_BOUND":
        _replace_task_binding(
            updated,
            planned["projection"],
            _sha256_payload(_canonical_json_file_bytes(planned["projection"])),
        )
        phase_path, phase_payload = _phase_task_control_payload(root, updated, changes, now)
        changes[phase_path] = phase_payload
        roles[phase_path] = "PHASE_CONTROL"
        updated["maintenance_state"].update({"state": "clean", "last_action": "migrate-result-contract-v1-to-v2", "last_checked_at": now})
        updated["recovery_point"] = {
            "summary": f"Result Contract {revision_id} migrated from v1 with one legacy import event.",
            "next_action": "Continue only from the exact Result lineage head and current Phase boundary revision.",
            "evidence_refs": [review_ref, authorization_ref, f"lineage:{lineage_id}"],
        }
        _finalize_v4_consistency(root, updated, changes, now)
        for relative, role in (("WORK_TASK_REPORT.md", "REPORT"), ("PROJECT_HANDOFF.md", "HANDOFF")):
            path = _target(root, relative)
            if path in changes:
                roles[path] = role
    else:
        receipt_document = {
            "receipt_schema": 1,
            "operation_id": args.operation_id,
            "operation": "migrate-result-contract-v1-to-v2",
            "binding_mode": "PENDING_WORKSPACE_BINDING",
            "v1_source": {"path": contract_relative, "sha256": v1_sha256},
            "v2_contract": {"path": planned["contract_relative"], "sha256": planned["contract_sha256"]},
            "import_event": {"path": planned["event_relative"], "sha256": planned["event_sha256"]},
            "target_phase": {"phase_id": phase_id, "boundary_revision_id": boundary_revision_id, "boundary_revision_sha256": boundary_revision_sha256},
            "recorded_at": now,
            "review_ref": review_ref,
            "authorization_ref": authorization_ref,
        }
        receipt_relative = f"task-state/{task_id}/MIGRATION_RECEIPT.json"
        receipt_payload = _canonical_json_file_bytes(receipt_document)
        changes[_target(root, receipt_relative)] = receipt_payload
        roles[_target(root, receipt_relative)] = "IMMUTABLE_RECORD"
    plan_values: dict[str, Any] = {
        "schema_version": 1,
        "operation_id": args.operation_id,
        "operation": "migrate-result-contract-v1-to-v2",
        "plan_id": args.operation_id,
        "source": {
            "path": contract_relative,
            "sha256": v1_sha256,
            "contract_version": "1",
            "execution_status": v1_contract.get("execution_status"),
            "terminal_status": v1_contract.get("terminal_status"),
        },
        "target": {
            "task_id": task_id,
            "lineage_id": lineage_id,
            "phase_id": phase_id,
            "phase_boundary_revision_id": boundary_revision_id,
            "phase_boundary_revision_sha256": boundary_revision_sha256,
        },
        "created": {
            "v2_contract_path": planned["contract_relative"],
            "import_event_path": planned["event_relative"],
            "projection_path": planned["projection_relative"],
        },
        "binding_mode": binding_mode,
        "declarations": {
            "source_bytes_unchanged": True,
            "fabricated_history": False,
            "implicit_session_created": False,
            "recursive_discovery_performed": False,
            "git_or_network_performed": False,
        },
        "rollback": {
            "preimages": [
                {"path": _relative(root, path), "sha256": _sha256_path(path) if _path_is_file(path) else None}
                for path in sorted(changes, key=lambda item: _relative(root, item))
            ],
            "created_outputs": [
                _relative(root, path)
                for path in sorted(changes, key=lambda item: _relative(root, item))
                if not _path_is_file(path)
            ],
        },
    }
    migration_plan = _migration_plan_document(plan_values)
    plan_issues = validate_instance(MALTS_ROOT, "result-migration-plan", migration_plan)
    if plan_issues:
        first = plan_issues[0]
        raise WorkspaceError("WS_MIGRATION_PLAN_INVALID", f"{first.code}: {first.message}", first.path)
    preconditions: dict[Path, str | None] = {
        path: _sha256_path(path) if _path_is_file(path) else None
        for path in changes
    }
    preconditions[contract_path] = v1_sha256
    if binding_mode == "V4_BOUND":
        preconditions[_state_path(root)] = _sha256_payload(state_payload)
    preview = _transaction_preview(root, operation_id=args.operation_id, operation="migrate-result-contract-v1-to-v2", changes=changes, preconditions=preconditions, target_roles=roles)
    receipt = None
    if args.apply:
        expected = _require_expected_sha256(args.expected_plan_sha256, "WS_TRANSACTION_PLAN_STALE", "Expected migration plan SHA-256")
        if expected != migration_plan["plan_sha256"]:
            raise WorkspaceError("WS_TRANSACTION_PLAN_STALE", "Migration plan SHA-256 differs from the reviewed plan.")
        receipt = _apply_transaction_plan(root, operation_id=args.operation_id, operation="migrate-result-contract-v1-to-v2", changes=changes, preconditions=preconditions, target_roles=roles, expected_plan_sha256=preview["plan_sha256"], fault_point=os.environ.get("MALTS_TEST_WORKSPACE_FAULT_POINT"))
    return {
        "status": "PASS",
        "operation": "migrate-result-contract-v1-to-v2",
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "workspace": str(root),
        "writes_performed": bool(receipt and receipt.get("writes_performed")),
        "binding_mode": binding_mode,
        "task_id": task_id,
        "lineage_id": lineage_id,
        "migration_plan": migration_plan,
        "transaction": preview,
        "receipt": receipt,
        "implicit_session_created": False,
    }


PROJECT_MARKER_PREFIX = "MALTS-PROJECT:"
PROJECT_INSTRUCTION_TARGETS = ("AGENTS.md", "CLAUDE.md")


def _project_marker_lines(marker_id: str, begin: bool) -> str:
    kind = "BEGIN" if begin else "END"
    return f"<!-- {PROJECT_MARKER_PREFIX}{kind} {marker_id} -->"


def _instruction_eol(text: str) -> str:
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    return "\r\n" if crlf >= lf and crlf > 0 else "\n"


def _instruction_file_issues(root: Path, relative: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    path = _target(root, relative)
    if not _path_is_file(path):
        issues.append({"code": "WS_INSTRUCTION_TARGET_INVALID", "path": relative, "message": "Instruction target is missing."})
        return issues
    stat_result = os.stat(_io_path(path))
    if stat_result.st_nlink > 1:
        issues.append({"code": "WS_INSTRUCTION_TARGET_INVALID", "path": relative, "message": "Hardlinked instruction target is not supported."})
    try:
        path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        issues.append({"code": "WS_INSTRUCTION_TARGET_INVALID", "path": relative, "message": "Instruction target must be valid UTF-8."})
    return issues


def _instruction_marker_parse(text: str, relative: str) -> tuple[list[tuple[str, bool, int]], list[dict[str, str]]]:
    pattern = re.compile(
        rf"^[ \t]*<!-- {re.escape(PROJECT_MARKER_PREFIX)}(BEGIN|END) (?P<id>[A-Za-z0-9][A-Za-z0-9._-]{{0,63}}) -->[ \t]*\r?$",
        re.MULTILINE,
    )
    tokens = [(match.group("id"), match.group(1) == "BEGIN", match.start()) for match in pattern.finditer(text)]
    issues: list[dict[str, str]] = []
    stack: list[str] = []
    seen_ids: set[str] = set()
    for marker_id, is_begin, _ in tokens:
        if is_begin:
            if marker_id in stack or marker_id in seen_ids:
                issues.append({"code": "WS_INSTRUCTION_MARKER_AMBIGUOUS", "path": relative, "message": f"Duplicate or nested begin marker: {marker_id}"})
            stack.append(marker_id)
        else:
            if not stack or stack[-1] != marker_id:
                issues.append({"code": "WS_INSTRUCTION_MARKER_AMBIGUOUS", "path": relative, "message": f"Unbalanced project marker: {marker_id}"})
                return tokens, issues
            stack.pop()
            seen_ids.add(marker_id)
    if stack:
        issues.append({"code": "WS_INSTRUCTION_MARKER_AMBIGUOUS", "path": relative, "message": f"Unclosed project marker: {stack[-1]}"})
    return tokens, issues


def _refresh_instruction_target(
    root: Path,
    relative: str,
    expected_sha256: str,
    blocks: list[tuple[str, str]],
) -> tuple[Path, bytes, dict[str, Any]]:
    path = _target(root, relative)
    issues = _instruction_file_issues(root, relative)
    if issues:
        raise WorkspaceError(issues[0]["code"], issues[0]["message"], issues[0]["path"])
    raw = _path_read_bytes(path)
    observed = _sha256_payload(raw)
    if observed != expected_sha256.upper():
        raise WorkspaceError("WS_INSTRUCTION_PLAN_STALE", "Instruction target changed after review.", relative)
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    tokens, marker_issues = _instruction_marker_parse(text, relative)
    if marker_issues:
        raise WorkspaceError(marker_issues[0]["code"], marker_issues[0]["message"], marker_issues[0]["path"])
    owned_ids = {marker_id for marker_id, _, _ in tokens}
    if not owned_ids:
        raise WorkspaceError(
            "WS_INSTRUCTION_MANUAL_MIGRATION_REQUIRED",
            "The instruction file has no MALTS-PROJECT markers. Custom markerless files are never claimed automatically; use a reviewed manual migration instead.",
            relative,
        )
    eol = _instruction_eol(text)
    updated = text
    target_rows: list[dict[str, Any]] = []
    for marker_id, block_text in blocks:
        begin_line = _project_marker_lines(marker_id, True)
        end_line = _project_marker_lines(marker_id, False)
        normalized_block = block_text.replace("\r\n", "\n").replace("\r", "\n")
        if normalized_block.endswith("\n"):
            normalized_block = normalized_block[:-1]
        rendered = begin_line + eol + normalized_block.replace("\n", eol) + eol + end_line + eol
        begin_pattern = re.compile(rf"(?m)^[ \t]*<!-- {re.escape(PROJECT_MARKER_PREFIX)}BEGIN {re.escape(marker_id)} -->[ \t]*\r?\n?")
        end_pattern = re.compile(rf"(?m)^[ \t]*<!-- {re.escape(PROJECT_MARKER_PREFIX)}END {re.escape(marker_id)} -->[ \t]*\r?\n?")
        begin_match = begin_pattern.search(updated)
        end_match = end_pattern.search(updated)
        if begin_match is not None and end_match is not None and end_match.start() > begin_match.start():
            updated = updated[:begin_match.start()] + rendered + updated[end_match.end():]
        else:
            updated = updated.rstrip("\r\n") + eol + eol + rendered
        target_rows.append({
            "path": relative,
            "marker_id": marker_id,
            "inserted": begin_match is None or end_match is None or end_match.start() <= begin_match.start(),
        })
    if updated == text:
        return path, raw, {"changed": False, "rows": target_rows}
    final_payload = (b"\xef\xbb\xbf" if has_bom else b"") + updated.encode("utf-8")
    return path, final_payload, {"changed": True, "rows": target_rows}


def command_scoped_readiness(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    reasons: list[str] = []
    checks: dict[str, Any] = {}
    consistency_ok = True
    drift_code = None
    try:
        _require_consistent_mutation(root, state)
    except WorkspaceError as exc:
        consistency_ok = False
        drift_code = exc.code
        reasons.append(f"consistency-drift:{drift_code}")
    checks["consistency"] = "PASS" if consistency_ok else f"DRIFT:{drift_code}"
    checks["active_session"] = state["active_session_id"] is not None
    if state["active_session_id"] is not None:
        reasons.append("active-session-lease")
    artifact_status = "UNKNOWN"
    try:
        snapshot = _artifact_snapshot(root, state, captured_at=_timestamp(None))
        artifact_status = str(snapshot.get("enrollment", {}).get("status", "UNKNOWN"))
    except Exception:
        artifact_status = "UNKNOWN"
    checks["artifact_enrollment"] = artifact_status
    if artifact_status == "UNKNOWN":
        reasons.append("artifact-status-unknown")
    if artifact_status not in {"NOT_ENROLLED", "LEGACY_UNDECLARED", "UNKNOWN"}:
        reasons.append("artifact-enrolled")
    unresolved = False
    for row in state.get("current_task_bindings", []):
        projection_path = _target(root, row["projection_path"])
        if not _path_is_file(projection_path):
            continue
        try:
            projection = json.loads(_path_read_bytes(projection_path).decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            unresolved = True
            break
        if projection.get("unresolved_side_effects") or projection.get("recovery_required"):
            unresolved = True
            break
    checks["unresolved_side_effects"] = unresolved
    if unresolved:
        reasons.append("unresolved-side-effects")
    durable_delta = args.durable_delta
    checks["durable_delta"] = durable_delta
    if durable_delta == "UNKNOWN":
        reasons.append("durable-delta-unknown")
    if reasons:
        route = "ESCALATE"
    elif durable_delta == "DURABLE":
        route = "S2_GOVERNED"
    elif state["active_phase_id"] is not None:
        route = "S1_SAME_SCOPE_NO_DELTA"
    else:
        route = "S0_UNRELATED"
    return {
        "status": "PASS",
        "operation": "scoped-readiness",
        "mode": "READ_ONLY",
        "workspace": str(root),
        "subject": args.subject,
        "route": route,
        "reasons": reasons,
        "checks": checks,
        "writes_performed": False,
        "authorization_conferred": False,
        "dispatch_performed": False,
        "implicit_session_created": False,
    }


def command_refresh_project_instructions(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    _load_state(root)
    targets: list[tuple[str, str]] = []
    for value in args.target:
        if "=" not in value:
            raise WorkspaceError("WS_INSTRUCTION_TARGET_INVALID", "Target rows must use RELATIVE=SHA256.", value)
        relative, expected = value.split("=", 1)
        relative = relative.replace("\\", "/")
        if relative not in PROJECT_INSTRUCTION_TARGETS:
            raise WorkspaceError("WS_INSTRUCTION_TARGET_INVALID", "Only AGENTS.md and CLAUDE.md are supported targets.", relative)
        if not re.fullmatch(r"[0-9A-F]{64}", expected, re.IGNORECASE):
            raise WorkspaceError("WS_INSTRUCTION_TARGET_INVALID", "Target SHA-256 must be 64 hexadecimal characters.", relative)
        targets.append((relative, expected.upper()))
    blocks: list[tuple[str, str]] = []
    source_rows: list[dict[str, str]] = []
    for value in args.block:
        parts = value.split("=", 2)
        if len(parts) != 3:
            raise WorkspaceError("WS_INSTRUCTION_SOURCE_INVALID", "Block rows must use MARKER_ID=SOURCE_PATH=SHA256.", value)
        marker_id, source_relative, expected = parts
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", marker_id):
            raise WorkspaceError("WS_INSTRUCTION_SOURCE_INVALID", "Invalid project marker ID.", marker_id)
        source_relative = source_relative.replace("\\", "/")
        source_path = _target(root, source_relative)
        if not _path_is_file(source_path):
            raise WorkspaceError("WS_INSTRUCTION_SOURCE_INVALID", "Block source file is missing.", source_relative)
        source_stat = os.stat(_io_path(source_path))
        if source_stat.st_nlink > 1:
            raise WorkspaceError("WS_INSTRUCTION_SOURCE_INVALID", "Hardlinked block source is not supported.", source_relative)
        source_raw = _path_read_bytes(source_path)
        observed_source = _sha256_payload(source_raw)
        if observed_source != expected.upper():
            raise WorkspaceError("WS_INSTRUCTION_PLAN_STALE", "Block source changed after review.", source_relative)
        block_text = source_raw.decode("utf-8-sig")
        blocks.append((marker_id, block_text))
        source_rows.append({"path": source_relative, "marker_id": marker_id, "sha256": observed_source})
    now = _timestamp(args.timestamp)
    changes: dict[Path, bytes] = {}
    target_rows: list[dict[str, Any]] = []
    for relative, expected_sha256 in targets:
        path, payload, detail = _refresh_instruction_target(root, relative, expected_sha256, blocks)
        target_rows.extend(detail["rows"])
        if detail["changed"]:
            changes[path] = payload
    plan_values: dict[str, Any] = {
        "plan_schema": 1,
        "operation_id": args.operation_id,
        "operation": "refresh-project-instructions",
        "targets": [
            {"path": relative, "expected_sha256": expected_sha256, "planned_sha256": _sha256_payload(changes[_target(root, relative)]) if _target(root, relative) in changes else expected_sha256}
            for relative, expected_sha256 in targets
        ],
        "blocks": source_rows,
        "target_rows": target_rows,
        "recorded_at": now,
    }
    plan_sha256 = _sha256_payload(canonical_json(plan_values))
    plan_values["plan_sha256"] = plan_sha256
    if args.apply:
        expected_plan = _require_expected_sha256(args.expected_plan_sha256, "WS_INSTRUCTION_PLAN_STALE", "Expected instruction refresh plan SHA-256")
        if expected_plan != plan_sha256:
            raise WorkspaceError("WS_INSTRUCTION_PLAN_STALE", "Instruction refresh plan differs from its exact reviewed preview.")
        expected_inputs = {_target(root, relative): expected_sha256 for relative, expected_sha256 in targets}
        for path in changes:
            if _sha256_path(path) != expected_inputs[path]:
                raise WorkspaceError("WS_INSTRUCTION_PLAN_STALE", "Instruction target changed after review.", _relative(root, path))
        for path, payload in changes.items():
            _io_path(path).write_bytes(payload)
    return {
        "status": "PASS",
        "operation": "refresh-project-instructions",
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "workspace": str(root),
        "writes_performed": bool(args.apply and changes),
        "plan": plan_values,
        "planned_changes": sorted(_relative(root, path) for path in changes),
        "implicit_session_created": False,
    }


def _recovery_record(payload: bytes, section_name: str, relative: str) -> dict[str, Any]:
    text, _ = _decode_markdown(payload)
    try:
        section = _marked_section(text, section_name, required=True)
        assert section is not None
        values = {
            label: _control_value(section, label, "WS_RECOVERY_RECORD_DRIFT")
            for label in ("Recovery schema", "Record ID", "Summary", "Next action", "Evidence references", "Recorded at")
        }
    except WorkspaceError as exc:
        raise WorkspaceError("WS_RECOVERY_RECORD_DRIFT", exc.message, relative) from exc
    if values["Recovery schema"] != "1" or any(values[label] == "N/A" for label in ("Record ID", "Summary", "Next action", "Evidence references", "Recorded at")):
        raise WorkspaceError("WS_RECOVERY_RECORD_DRIFT", "Structured recovery record is incomplete.", relative)
    _timestamp(values["Recorded at"])
    evidence_refs = [item.strip() for item in values["Evidence references"].split(";") if item.strip()]
    if not evidence_refs:
        raise WorkspaceError("WS_RECOVERY_RECORD_DRIFT", "Structured recovery record requires evidence references.", relative)
    return {
        "record_id": values["Record ID"],
        "summary": values["Summary"],
        "next_action": values["Next action"],
        "evidence_refs": evidence_refs,
        "recorded_at": values["Recorded at"],
    }


def _replace_recovery_record(
    payload: bytes,
    section_name: str,
    relative: str,
    *,
    record_id: str,
    summary: str,
    next_action: str,
    evidence_refs: Iterable[str],
    recorded_at: str,
) -> bytes:
    text, bom = _decode_markdown(payload)
    section = _marked_section(text, section_name, required=True)
    assert section is not None
    normalized_evidence = [_single_line(item) for item in evidence_refs if _single_line(item)]
    if not normalized_evidence:
        raise WorkspaceError("WS_RECOVERY_RECORD_DRIFT", "Structured recovery record requires evidence references.", relative)
    replacements = {
        "Recovery schema": "1",
        "Record ID": _require_reference(record_id, "WS_RECOVERY_RECORD_DRIFT", "Recovery record ID"),
        "Summary": _require_reference(summary, "WS_RECOVERY_RECORD_DRIFT", "Recovery summary"),
        "Next action": _require_reference(next_action, "WS_RECOVERY_RECORD_DRIFT", "Recovery next action"),
        "Evidence references": "; ".join(normalized_evidence),
        "Recorded at": _timestamp(recorded_at),
    }
    updated_section = section
    for label, value in replacements.items():
        updated_section = _replace_line(
            updated_section,
            f"- {label}:",
            f"- {label}: `{value}`",
            "WS_RECOVERY_RECORD_DRIFT",
        )
    return _encode_markdown(text.replace(section, updated_section, 1), bom)


def _select_recovery_source(state: dict[str, Any], terminal_phase_id: str | None) -> tuple[str, str | None, str | None, str, str]:
    if state["active_session_id"] is not None:
        session = _active_session(state)
        return "ACTIVE_SESSION_CHECKPOINT", session["phase_id"], session["session_id"], session["path"], "session-checkpoint"
    if state["active_phase_id"] is not None:
        phase = _active_phase(state)
        return "ACTIVE_PHASE_RECOVERY", phase["phase_id"], None, phase["path"], "phase-recovery"
    if terminal_phase_id is not None:
        phase = _phase_entry(state, terminal_phase_id)
        if state.get("schema_version") == 4 and phase.get("status") == "PAUSED":
            return "PAUSED_PHASE_RECOVERY", phase["phase_id"], None, phase["path"], "phase-recovery"
        return "TERMINAL_PHASE_RECOVERY", phase["phase_id"], None, phase["path"], "phase-recovery"
    prior = state.get("recovery_binding")
    if isinstance(prior, dict) and prior.get("source_kind") in {"PAUSED_PHASE_RECOVERY", "TERMINAL_PHASE_RECOVERY"}:
        phase_id = prior.get("source_phase_id")
        phase = next((item for item in state["phase_controls"] if item["phase_id"] == phase_id and item["status"] != "ACTIVE"), None)
        if phase is not None:
            return prior["source_kind"], phase["phase_id"], None, phase["path"], "phase-recovery"
    return "PROJECT_RECOVERY", None, None, "PROJECT_CONTROL.md", "recovery-notes"


def _finalize_v3_consistency(
    root: Path,
    state: dict[str, Any],
    changes: dict[Path, bytes],
    now: str,
    *,
    terminal_phase_id: str | None = None,
) -> None:
    if state["schema_version"] == 4:
        _finalize_v4_consistency(root, state, changes, now, terminal_phase_id=terminal_phase_id)
        return
    if state["schema_version"] != 3:
        changes[_state_path(root)] = _json_bytes(state)
        _refresh_current_phase_bindings(root, state, changes, now)
        return
    source_kind, source_phase_id, source_session_id, source_relative, source_section = _select_recovery_source(state, terminal_phase_id)
    source_payload = _final_payload(root, changes, source_relative)
    if source_payload is None:
        raise WorkspaceError("WS_FILE_MISSING", "Canonical recovery source is missing.", source_relative)
    record_id = (
        f"session:{source_session_id}:checkpoint"
        if source_session_id is not None
        else f"phase:{source_phase_id}:recovery"
        if source_phase_id is not None
        else "project:recovery"
    )
    source_payload = _replace_recovery_record(
        source_payload,
        source_section,
        source_relative,
        record_id=record_id,
        summary=state["recovery_point"]["summary"],
        next_action=state["recovery_point"]["next_action"],
        evidence_refs=state["recovery_point"]["evidence_refs"],
        recorded_at=now,
    )
    changes[_target(root, source_relative)] = source_payload
    source_recovery_sha256 = _normalized_section_sha256(source_payload, source_section, "WS_RECOVERY_RECORD_DRIFT", source_relative)
    state["recovery_binding"] = {
        "record_schema": 1,
        "record_id": record_id,
        "source_kind": source_kind,
        "source_phase_id": source_phase_id,
        "source_session_id": source_session_id,
        "source_control_path": source_relative,
        "source_control_sha256": hashlib.sha256(source_payload).hexdigest().upper(),
        "source_recovery_sha256": source_recovery_sha256,
        "summary": state["recovery_point"]["summary"],
        "next_action": state["recovery_point"]["next_action"],
        "evidence_refs": list(state["recovery_point"]["evidence_refs"]),
        "projected_at": now,
    }
    if state["active_phase_id"] is None:
        state["current_phase_binding"] = None
    else:
        phase = _active_phase(state)
        phase_payload = _final_payload(root, changes, phase["path"])
        if phase_payload is None:
            raise WorkspaceError("WS_FILE_MISSING", "Active Phase control is missing.", phase["path"])
        review = _boundary_review_record(phase_payload, phase["path"])
        state["current_phase_binding"] = {
            "binding_schema": 2,
            "active_phase_id": phase["phase_id"],
            "phase_control_path": phase["path"],
            "phase_control_sha256": hashlib.sha256(phase_payload).hexdigest().upper(),
            "phase_boundary_sha256": _normalized_section_sha256(phase_payload, "phase-boundary", "WS_PHASE_BOUNDARY_RECORD_MISSING", phase["path"]),
            "boundary_review_id": None if review["Review ID"] == "N/A" else review["Review ID"],
            "boundary_review_sha256": _normalized_section_sha256(phase_payload, "phase-boundary-review", "WS_PHASE_BOUNDARY_RECORD_MISSING", phase["path"]),
            "candidate_mapping": review["Candidate mapping"],
            "recommendation": review["Recommended review"],
            "phase_recovery_sha256": _normalized_section_sha256(phase_payload, "phase-recovery", "WS_RECOVERY_RECORD_DRIFT", phase["path"]),
            "recorded_at": now,
        }
    changes[_state_path(root)] = _json_bytes(state)
    _refresh_current_phase_bindings(root, state, changes, now)
    _validate_state(root, state)


def _boundary_revision_binding(
    root: Path,
    phase_payload: bytes,
    phase: dict[str, Any],
    changes: dict[Path, bytes] | None = None,
) -> dict[str, str]:
    text, _ = _decode_markdown(phase_payload)
    section = _marked_section(text, BOUNDARY_INDEX_MARKER, required=True)
    assert section is not None
    revision_id = _control_value(section, "Current revision ID", "WS_PHASE_BOUNDARY_RECORD_MISSING")
    revision_path = _control_value(section, "Current revision path", "WS_PHASE_BOUNDARY_RECORD_MISSING")
    revision_sha256 = _control_value(section, "Current revision SHA-256", "WS_PHASE_BOUNDARY_RECORD_MISSING").upper()
    path = _target(root, revision_path)
    revision_payload = (changes or {}).get(path)
    if revision_payload is None and _path_is_file(path):
        revision_payload = _path_read_bytes(path)
    if revision_payload is None:
        raise WorkspaceError("WS_PHASE_BOUNDARY_RECORD_MISSING", "Current immutable Phase boundary revision is missing.", revision_path)
    if _sha256_payload(revision_payload) != revision_sha256:
        raise WorkspaceError("WS_PHASE_BOUNDARY_RECORD_STALE", "Immutable Phase boundary revision bytes drifted.", revision_path)
    document = json.loads(revision_payload.decode("utf-8-sig"))
    if document.get("phase_id") != phase["phase_id"] or document.get("revision_id") != revision_id:
        raise WorkspaceError("WS_PHASE_BOUNDARY_RECORD_STALE", "Phase boundary revision identity disagrees with its Phase index.", revision_path)
    return {"revision_id": revision_id, "path": revision_path, "sha256": revision_sha256}


def _task_binding_index_sha256(rows: list[dict[str, Any]]) -> str:
    return _sha256_payload(canonical_json(sorted(rows, key=lambda item: item["task_id"])))


def _v4_session_binding(root: Path, state: dict[str, Any], changes: dict[Path, bytes], now: str) -> dict[str, Any] | None:
    if state["active_session_id"] is None:
        return None
    session = _active_session(state)
    lease = session["lease"]
    payload = _final_payload(root, changes, session["path"])
    if payload is None:
        raise WorkspaceError("WS_FILE_MISSING", "Active Session control is missing.", session["path"])
    heads = [
        {"lineage_id": row["lineage_id"], "latest_event_sha256": row["latest_event"]["sha256"]}
        for row in state.get("current_task_bindings", [])
        if row.get("latest_event") is not None and row["lineage_id"] in set(lease.get("bound_lineage_ids", []))
    ]
    return {
        "session_id": session["session_id"],
        "phase_id": session["phase_id"],
        "session_control_path": session["path"],
        "session_control_sha256": _sha256_payload(payload),
        "lease_id": lease["lease_id"],
        "owner_kind": session["owner_kind"],
        "owner_id": session["owner_id"],
        "lease_state": lease["state"],
        "granted_at": lease["granted_at"],
        "expires_at": lease["expires_at"],
        "scope_sha256": _sha256_payload(canonical_json({"read": lease["read_scope"], "write": lease["write_scope"]})),
        "touch_set_sha256": _sha256_payload(_canonical_string_array(lease["touch_set"])),
        "allowed_operations_sha256": _sha256_payload(_canonical_string_array(lease["allowed_operations"])),
        "checkpoint_sha256": lease["checkpoint_sha256"],
        "bound_lineage_heads": sorted(heads, key=lambda item: item["lineage_id"]),
        "recorded_at": now,
    }


def _finalize_v4_consistency(
    root: Path,
    state: dict[str, Any],
    changes: dict[Path, bytes],
    now: str,
    *,
    terminal_phase_id: str | None = None,
) -> None:
    source_kind, source_phase_id, source_session_id, source_relative, source_section = _select_recovery_source(state, terminal_phase_id)
    source_payload = _final_payload(root, changes, source_relative)
    if source_payload is None:
        raise WorkspaceError("WS_FILE_MISSING", "Canonical recovery source is missing.", source_relative)
    record_id = f"session:{source_session_id}:checkpoint" if source_session_id is not None else f"phase:{source_phase_id}:recovery" if source_phase_id is not None else "project:recovery"
    source_payload = _replace_recovery_record(
        source_payload,
        source_section,
        source_relative,
        record_id=record_id,
        summary=state["recovery_point"]["summary"],
        next_action=state["recovery_point"]["next_action"],
        evidence_refs=state["recovery_point"]["evidence_refs"],
        recorded_at=now,
    )
    changes[_target(root, source_relative)] = source_payload
    source_boundary_revision: dict[str, str] | None = None
    if source_phase_id is not None:
        source_phase = _phase_entry(state, source_phase_id)
        phase_payload = _final_payload(root, changes, source_phase["path"])
        if phase_payload is None:
            raise WorkspaceError("WS_FILE_MISSING", "Recovery Phase control is missing.", source_phase["path"])
        source_boundary_revision = _boundary_revision_binding(root, phase_payload, source_phase, changes)
    state["recovery_binding"] = {
        "record_schema": 2,
        "record_id": record_id,
        "source_kind": source_kind,
        "source_phase_id": source_phase_id,
        "source_session_id": source_session_id,
        "source_control_path": source_relative,
        "source_control_sha256": _sha256_payload(source_payload),
        "source_boundary_revision": None if source_boundary_revision is None else {"path": source_boundary_revision["path"], "sha256": source_boundary_revision["sha256"]},
        "source_recovery_sha256": _normalized_section_sha256(source_payload, source_section, "WS_RECOVERY_RECORD_DRIFT", source_relative),
        "summary": state["recovery_point"]["summary"],
        "next_action": state["recovery_point"]["next_action"],
        "evidence_refs": list(state["recovery_point"]["evidence_refs"]),
        "resume_required": source_kind == "PAUSED_PHASE_RECOVERY",
        "projected_at": now,
    }
    if state["active_phase_id"] is None:
        state["current_phase_binding"] = None
    else:
        phase = _active_phase(state)
        phase_payload = _final_payload(root, changes, phase["path"])
        if phase_payload is None:
            raise WorkspaceError("WS_FILE_MISSING", "Active Phase control is missing.", phase["path"])
        revision = _boundary_revision_binding(root, phase_payload, phase, changes)
        review = _boundary_review_record(phase_payload, phase["path"])
        plan = _phase_plan_binding(root, phase, phase_payload)
        state["current_phase_binding"] = {
            "binding_schema": 3,
            "active_phase_id": phase["phase_id"],
            "phase_control_path": phase["path"],
            "phase_control_sha256": _sha256_payload(phase_payload),
            "boundary_revision_id": revision["revision_id"],
            "boundary_revision_path": revision["path"],
            "boundary_revision_sha256": revision["sha256"],
            "phase_boundary_sha256": _normalized_section_sha256(phase_payload, "phase-boundary", "WS_PHASE_BOUNDARY_RECORD_MISSING", phase["path"]),
            "boundary_review_id": None if review["Review ID"] == "N/A" else review["Review ID"],
            "boundary_review_sha256": _normalized_section_sha256(phase_payload, "phase-boundary-review", "WS_PHASE_BOUNDARY_RECORD_MISSING", phase["path"]),
            "candidate_mapping": review["Candidate mapping"],
            "recommendation": review["Recommended review"],
            "active_plan_path": None if plan is None or plan["Active plan"] == "N/A" else plan["Active plan"],
            "active_plan_revision": None if plan is None or plan["Active plan"] == "N/A" else plan["Plan revision"],
            "active_plan_sha256": None if plan is None or plan["Active plan"] == "N/A" else plan["Plan content SHA-256"],
            "phase_recovery_sha256": _normalized_section_sha256(phase_payload, "phase-recovery", "WS_RECOVERY_RECORD_DRIFT", phase["path"]),
            "task_binding_index_sha256": _task_binding_index_sha256(state.get("current_task_bindings", [])),
            "recorded_at": now,
        }
    state["current_session_binding"] = _v4_session_binding(root, state, changes, now)
    if state["current_session_binding"] is not None:
        session_relative = state["current_session_binding"]["session_control_path"]
        final_session_payload = _final_payload(root, changes, session_relative)
        if final_session_payload is not None:
            state["current_session_binding"]["session_control_sha256"] = _sha256_payload(final_session_payload)
    changes[_state_path(root)] = _json_bytes(state)
    _refresh_current_phase_bindings(root, state, changes, now)
    _validate_state(root, state)


def _project_active_phase_value(text: str) -> str:
    section = _marked_section(text, "current-stage", required=True)
    assert section is not None
    pattern = re.compile(r"(?m)^- Active Phase(?P<separator>:|：)[ \t]*(?P<value>[^\r\n]*?)[ \t]*\r?$")
    matches = list(pattern.finditer(section))
    if len(matches) != 1:
        raise WorkspaceError("WS_ROOT_PHASE_INDEX_INVALID", "PROJECT_CONTROL must contain exactly one Active Phase field in current-stage.")
    value = matches[0].group("value").strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    if not value:
        raise WorkspaceError("WS_ROOT_PHASE_INDEX_INVALID", "PROJECT_CONTROL Active Phase field must not be empty.")
    return value


def _replace_project_active_phase(text: str, phase_id: str | None) -> str:
    section = _marked_section(text, "current-stage", required=True)
    assert section is not None
    pattern = re.compile(r"(?m)^- Active Phase(?P<separator>:|：)[ \t]*[^\r\n]*(?P<ending>\r?)$")
    matches = list(pattern.finditer(section))
    if len(matches) != 1:
        raise WorkspaceError("WS_ROOT_PHASE_INDEX_INVALID", "PROJECT_CONTROL must contain exactly one Active Phase field in current-stage.")
    value = phase_id or "N/A"
    updated_section = pattern.sub(
        lambda match: f"- Active Phase{match.group('separator')} {value}{match.group('ending')}",
        section,
        count=1,
    )
    return text.replace(section, updated_section, 1)


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


def _close_operation_id(operation: str, root: Path, changes: dict[Path, bytes]) -> str:
    digest = hashlib.sha256()
    digest.update(operation.encode("utf-8"))
    for path in sorted(changes, key=lambda item: _relative(root, item)):
        digest.update(b"\0")
        digest.update(_relative(root, path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_bytes(changes[path]).encode("ascii"))
    return f"{operation}-{digest.hexdigest()[:24]}"


def _artifact_aware_close(
    operation: str,
    root: Path,
    state: dict[str, Any],
    artifact_gate: dict[str, Any],
    changes: dict[Path, bytes],
    render_inputs: dict[Path, bytes],
    apply: bool,
    **extra: Any,
) -> dict[str, Any]:
    enrolled = artifact_gate["snapshot"]["enrollment"]["status"] == "ENROLLED"
    if not enrolled:
        result = _plan(
            operation,
            root,
            changes,
            apply,
            artifact_transaction_required=False,
            transaction=None,
            implicit_session_created=False,
            **extra,
        )
        if apply:
            _transaction_write(root, changes, operation=operation)
        return result

    preconditions = artifact_snapshot_preconditions(root, artifact_gate["snapshot"])
    for path, original in render_inputs.items():
        expected = sha256_bytes(original)
        if path in preconditions and preconditions[path] != expected:
            raise WorkspaceError(
                "ART_CLOSE_PRECONDITION_DRIFT",
                "A canonical input changed after the enrolled Artifact close gate was captured.",
                {"path": _relative(root, path), "gate": preconditions[path], "render": expected},
            )
        preconditions[path] = expected
    for path in changes:
        if path not in preconditions:
            preconditions[path] = sha256_bytes(path.read_bytes()) if path.is_file() else None
    missing_targets = sorted(_relative(root, path) for path in changes if path not in preconditions)
    if missing_targets:
        raise WorkspaceError(
            "ART_CLOSE_PRECONDITION_MISSING",
            "Every enrolled close target requires an exact render-time precondition.",
            missing_targets,
        )
    drift = []
    for path in sorted(preconditions, key=lambda item: _relative(root, item)):
        observed = sha256_bytes(path.read_bytes()) if path.is_file() else None
        if observed != preconditions[path]:
            drift.append(
                {
                    "path": _relative(root, path),
                    "expected": preconditions[path],
                    "observed": observed,
                }
            )
    if drift:
        raise WorkspaceError(
            "ART_CLOSE_PRECONDITION_DRIFT",
            "A canonical input changed while the enrolled close plan was rendered.",
            drift,
        )

    operation_id = _close_operation_id(operation, root, changes)
    result = _plan(
        operation,
        root,
        changes,
        apply,
        artifact_transaction_required=True,
        precondition_hashes=[
            {"path": _relative(root, path), "sha256": preconditions[path]}
            for path in sorted(preconditions, key=lambda item: _relative(root, item))
        ],
        transaction_control_paths=[
            "runtime/artifact_transaction.lock.json",
            f"runtime/artifact_transactions/{operation_id}.json",
        ],
        transaction=None,
        implicit_session_created=False,
        **extra,
    )
    if not apply:
        return result
    try:
        transaction = execute_transaction(
            root,
            operation_id=operation_id,
            operation=operation,
            changes=changes,
            expected_input_hashes=preconditions,
            post_validate=lambda: _artifact_post_validate(root, state),
        )
    except TransactionError as exc:
        raise WorkspaceError(exc.code, exc.message, exc.detail) from exc
    result["transaction"] = transaction
    result["writes_performed"] = bool(transaction["writes_performed"])
    return result


def command_close_phase(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state_data = _read_bytes(root, STATE_RELATIVE)
    state = _parse_state_bytes(root, state_data)
    _require_consistent_mutation(root, state)
    if state["active_session_id"] is not None:
        raise WorkspaceError("WS_SESSION_ACTIVE", "Close the active Session before closing its Phase.")
    phase = _active_phase(state)
    now = _timestamp(args.timestamp)
    artifact_gate = artifact_close_gate(root, state, f"phase:{phase['phase_id']}", captured_at=now)
    if artifact_gate["status"] == "BLOCKED":
        return {
            "status": "BLOCKED",
            "operation": "close-phase",
            "mode": "BLOCKED",
            "workspace": str(root),
            "writes_performed": False,
            "phase_id": phase["phase_id"],
            "reason_code": artifact_gate["reason_code"],
            "unresolved_artifacts": artifact_gate["unresolved"],
            "artifact_issues": artifact_gate.get("issues", []),
            "required_action": "Reconcile every enrolled Artifact disposition and validation issue before closing the Phase.",
            "implicit_session_created": False,
        }
    path = _target(root, phase["path"])
    data = _read_bytes(root, phase["path"])
    text, bom = _decode_markdown(data)
    boundary = _phase_boundary_contract(text)
    closure = _structured_closure(text)
    queue = _phase_table_summary(text, "phase-queue", "Status")
    if boundary["status"] == "COMPLETE":
        if closure is None:
            raise WorkspaceError("WS_PHASE_CLOSURE_INVALID", "A v2 Phase requires the complete structured Closure contract before close.", phase["path"])
        if not _single_line(args.closure_evidence or ""):
            raise WorkspaceError("WS_PHASE_CLOSURE_EVIDENCE_REQUIRED", "A v2 Phase closure requires --closure-evidence.")
        if args.status == "DONE":
            if args.exit_criteria_status != "SATISFIED":
                raise WorkspaceError("WS_PHASE_EXIT_CRITERIA_UNSATISFIED", "DONE requires --exit-criteria-status SATISFIED.")
            if queue["active_rows"]:
                unfinished = ", ".join(row.get("Task ID", "UNKNOWN") for row in queue["active_rows"])
                raise WorkspaceError("WS_PHASE_UNFINISHED_TASKS", f"DONE is blocked by unfinished Phase queue rows: {unfinished}")
    text = _replace_active_status(text, args.status, "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Updated at:", f"- Updated at: {now}", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Close result:", f"- Close result: {args.status}", "WS_PHASE_CONTROL_INVALID")
    if closure is not None:
        exit_status = args.exit_criteria_status or ("SATISFIED" if args.status == "DONE" else "NOT_SATISFIED")
        text = _replace_line(text, "- Exit criteria status:", f"- Exit criteria status: {exit_status}", "WS_PHASE_CONTROL_INVALID")
        text = _replace_line(
            text,
            "- Carry-over disposition:",
            f"- Carry-over disposition: {_single_line(args.carry_over_disposition or 'N/A')}",
            "WS_PHASE_CONTROL_INVALID",
        )
        text = _replace_line(text, "- Superseded by:", "- Superseded by: N/A", "WS_PHASE_CONTROL_INVALID")
        text = _replace_line(
            text,
            "- Closure evidence:",
            f"- Closure evidence: {_single_line(args.closure_evidence or 'N/A')}",
            "WS_PHASE_CONTROL_INVALID",
        )
        text = _replace_line(text, "- Closed at:", f"- Closed at: {now}", "WS_PHASE_CONTROL_INVALID")
    updated = json.loads(json.dumps(state))
    next(item for item in updated["phase_controls"] if item["phase_id"] == phase["phase_id"])["status"] = args.status
    updated["active_phase_id"] = None
    updated["maintenance_state"].update({"last_action": "close-phase", "last_checked_at": now})
    updated["recovery_point"] = {
        "summary": f"Phase {phase['phase_id']} closed with {args.status}.",
        "next_action": args.next_action,
        "evidence_refs": [f"phase:{phase['phase_id']}:{args.status.lower()}"],
    }
    project_path = _target(root, "PROJECT_CONTROL.md")
    project_data = _read_bytes(root, "PROJECT_CONTROL.md")
    project_text, project_bom = _decode_markdown(project_data)
    project_text = _replace_project_active_phase(project_text, None)
    changes = {
        path: _encode_markdown(text, bom),
        project_path: _encode_markdown(project_text, project_bom),
        _state_path(root): _json_bytes(updated),
    }
    _finalize_v3_consistency(root, updated, changes, now, terminal_phase_id=phase["phase_id"])
    _validate_state(root, updated)
    return _artifact_aware_close(
        "close-phase",
        root,
        updated,
        artifact_gate,
        changes,
        {path: data, project_path: project_data, _state_path(root): state_data},
        args.apply,
        phase_id=phase["phase_id"],
        terminal_status=args.status,
    )


def command_phase_boundary_review(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    phase = _phase_entry(state, args.phase_id) if args.phase_id else _active_phase(state)
    path, data, text, _ = _phase_control_info(root, phase)
    boundary = _phase_boundary_contract(text)
    queue = _phase_table_summary(text, "phase-queue", "Status")
    deliverables = _phase_table_summary(text, "phase-deliverables", "Status")
    scope_changes = _markdown_table_rows(_marked_section(text, "phase-scope-changes"))
    carry_over = _markdown_table_rows(_marked_section(text, "phase-carry-over"))
    carried_in = _markdown_table_rows(_marked_section(text, "phase-carried-in"))

    plan_evidence: dict[str, Any] = {"status": "NONE", "binding": None}
    try:
        binding = _phase_plan_binding(root, phase)
    except WorkspaceError as exc:
        binding = None
        plan_evidence = {"status": "INVALID", "error_code": exc.code, "message": exc.message}
    if binding is not None and binding["Active plan"] != "N/A":
        plan_evidence = {"status": "CURRENT", "binding": binding}
        if binding["Last recheck trigger"] not in PLAN_RECHECK_TRIGGERS:
            plan_evidence["status"] = "MIGRATION_REQUIRED"
            plan_evidence["required_action"] = "Run migrate-phase-control with a reviewed canonical --plan-trigger; no silent normalization is allowed."
        try:
            plan_path = _target(root, binding["Active plan"])
            observed = hashlib.sha256(_path_read_bytes(plan_path)).hexdigest().upper() if _path_is_file(plan_path) else None
            plan_evidence["path"] = binding["Active plan"]
            plan_evidence["observed_sha256"] = observed
            plan_evidence["expected_sha256"] = binding["Plan content SHA-256"].upper()
            if observed is None or observed != plan_evidence["expected_sha256"]:
                plan_evidence["status"] = "STALE"
        except WorkspaceError as exc:
            plan_evidence.update({"status": "INVALID", "error_code": exc.code, "message": exc.message})

    recommendation = args.recommendation or "USER_DECISION_REQUIRED"
    candidate_mapping = args.candidate_mapping or "UNCLEAR"
    review_outcome = (
        "RESOLVED"
        if candidate_mapping != "UNCLEAR" and recommendation != "USER_DECISION_REQUIRED"
        else "UNRESOLVED"
    )
    required_decisions = ["Agent/Skill semantic confirmation of the recommended review."]
    if boundary["status"] != "COMPLETE":
        required_decisions.append("Review and explicitly migrate the Phase Boundary Contract; do not infer missing scope fields.")
    if plan_evidence["status"] in {"MIGRATION_REQUIRED", "STALE", "INVALID"}:
        required_decisions.append("Repair or rebind the active Plan before relying on it as current evidence.")
    return {
        "status": "PASS",
        "operation_status": "PASS",
        "status_semantics": "OPERATION_EXECUTION_ONLY",
        "review_outcome": review_outcome,
        "candidate_mapping": candidate_mapping,
        "recommendation": recommendation,
        "persisted": False,
        "operation": "phase-boundary-review",
        "mode": "READ_ONLY",
        "workspace": str(root),
        "writes_performed": False,
        "phase": {
            "phase_id": phase["phase_id"],
            "path": phase["path"],
            "status": phase["status"],
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest().upper(),
        },
        "workspace_state": {
            "path": STATE_RELATIVE.as_posix(),
            "schema_version": state["schema_version"],
            "sha256": hashlib.sha256(_read_bytes(root, STATE_RELATIVE)).hexdigest().upper(),
            "active_phase_id": state["active_phase_id"],
            "active_session_id": state["active_session_id"],
        },
        "boundary_contract": boundary,
        "queue": queue,
        "deliverables": deliverables,
        "scope_changes": scope_changes,
        "carry_over": carry_over,
        "carried_in": carried_in,
        "plan_binding": plan_evidence,
        "candidate": {
            "goal": _single_line(args.candidate_goal or ""),
            "touch_set": list(args.candidate_touch_set or []),
            "mapping": args.candidate_mapping,
        },
        "recommended_review": recommendation,
        "recommendation_source": "AGENT_OR_SKILL_INPUT" if args.recommendation else "DEFAULT_NO_SEMANTIC_INPUT",
        "semantic_judgment_performed": False,
        "automatic_transition_performed": False,
        "required_user_decisions": required_decisions,
        "warnings": _phase_lifecycle_warnings(root, state),
    }


def _insert_before_section(text: str, target_section: str, block: str, code: str) -> str:
    marker = f"<!-- MALTS:section={target_section} -->"
    if text.count(marker) != 1:
        raise WorkspaceError(code, f"Expected exactly one target section marker: {target_section}")
    return text.replace(marker, block.rstrip("\r\n") + "\n\n" + marker, 1)


def _rendered_phase_section(language: str, values: dict[str, str], section_name: str) -> str:
    rendered = _render_phase_control(language, values["PHASE_ID"], values["PHASE_GOAL"], values["TIMESTAMP"], values)
    text, _ = _decode_markdown(rendered)
    section = _marked_section(text, section_name, required=True)
    assert section is not None
    return section


def command_migrate_phase_control(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    phase = _phase_entry(state, args.phase_id)
    path, _, text, bom = _phase_control_info(root, phase)
    now = _timestamp(args.timestamp)
    language = _language(args, root)
    boundary = _phase_boundary_contract(text)
    boundary_values = _phase_boundary_values(args, required=boundary["status"] == "LEGACY")
    if boundary["status"] == "INCOMPLETE":
        raise WorkspaceError(
            "WS_PHASE_BOUNDARY_MANUAL_REPAIR",
            "An existing incomplete Boundary Contract is user-owned; review it manually instead of overwriting fields.",
            phase["path"],
        )
    values = {
        "PHASE_ID": phase["phase_id"],
        "PHASE_GOAL": "Explicitly migrated legacy Phase.",
        "TIMESTAMP": now,
        **boundary_values,
    }
    changes_made = False
    if boundary["status"] == "LEGACY":
        text = _insert_before_section(text, "phase-plan-recheck", _rendered_phase_section(language, values, "phase-boundary"), "WS_PHASE_MIGRATION_INVALID")
        changes_made = True
    insertion_targets = {
        "phase-scope-changes": "phase-recovery",
        "phase-carry-over": "phase-recovery",
        "phase-carried-in": "phase-recovery",
        "phase-boundary-review": "phase-recovery",
    }
    for section_name, target in insertion_targets.items():
        if _marked_section(text, section_name) is None:
            text = _insert_before_section(text, target, _rendered_phase_section(language, values, section_name), "WS_PHASE_MIGRATION_INVALID")
            changes_made = True
    if _marked_section(text, "phase-lifecycle") is None:
        text = _insert_before_section(text, "phase-close", _rendered_phase_section(language, values, "phase-lifecycle"), "WS_PHASE_MIGRATION_INVALID")
        changes_made = True

    plan_values = (args.plan_trigger, args.plan_result, args.plan_reviewed_at)
    if any(plan_values) and not all(plan_values):
        raise WorkspaceError("WS_PHASE_PLAN_REPAIR_INCOMPLETE", "Plan trigger repair requires --plan-trigger, --plan-result, and --plan-reviewed-at together.")
    project_path = _target(root, "PROJECT_CONTROL.md")
    project_data = _read_bytes(root, "PROJECT_CONTROL.md")
    project_text, project_bom = _decode_markdown(project_data)
    project_changed = False
    normalized_project_text = _replace_project_active_phase(project_text, state["active_phase_id"])
    if normalized_project_text != project_text:
        project_text = normalized_project_text
        project_changed = True
        changes_made = True
    if all(plan_values):
        reviewed_at = _timestamp(args.plan_reviewed_at)
        text = _replace_line(text, "- Last recheck trigger:", f"- Last recheck trigger: `{args.plan_trigger}`", "WS_PHASE_PLAN_REPAIR_INVALID")
        text = _replace_line(text, "- Last recheck result:", f"- Last recheck result: `{args.plan_result}`", "WS_PHASE_PLAN_REPAIR_INVALID")
        text = _replace_line(text, "- Last rechecked at:", f"- Last rechecked at: `{reviewed_at}`", "WS_PHASE_PLAN_REPAIR_INVALID")
        root_plan = _marked_section(project_text, "plan-recheck-index")
        if root_plan is not None:
            project_text = _replace_line(project_text, "- Latest recheck trigger:", f"- Latest recheck trigger: `{args.plan_trigger}`", "WS_PHASE_PLAN_REPAIR_INVALID")
            project_text = _replace_line(project_text, "- Latest recheck result:", f"- Latest recheck result: `{args.plan_result}`", "WS_PHASE_PLAN_REPAIR_INVALID")
            project_changed = True
        changes_made = True

    if _marked_section(project_text, "phase-carry-over-index") is None:
        template_relative = (
            f"runtime/{'EN' if language == 'en' else 'CH'}/templates/"
            f"PROJECT_CONTROL.template.{'en' if language == 'en' else 'zh-CN'}.md"
        )
        template_text, _ = _template_bytes(template_relative)
        carry_index = _marked_section(template_text, "phase-carry-over-index", required=True)
        assert carry_index is not None
        project_text = _insert_before_section(project_text, "task-queue", carry_index, "WS_PHASE_MIGRATION_INVALID")
        project_changed = True
        changes_made = True

    text = _replace_line(text, "- Updated at:", f"- Updated at: {now}", "WS_PHASE_CONTROL_INVALID") if changes_made else text
    updated = json.loads(json.dumps(state))
    if updated["schema_version"] == 1:
        updated["schema_version"] = 2
        changes_made = True
    if changes_made:
        updated["maintenance_state"].update({"state": "clean", "last_action": "migrate-phase-control", "last_checked_at": now})
        updated["recovery_point"] = {
            "summary": f"Phase {phase['phase_id']} completed an explicit v2 control migration.",
            "next_action": "Run validate and a read-only phase-boundary-review before the next mutation.",
            "evidence_refs": [f"phase:{phase['phase_id']}:migration"],
        }
    changes: dict[Path, bytes] = {}
    if changes_made:
        changes[path] = _encode_markdown(text, bom)
        changes[_state_path(root)] = _json_bytes(updated)
    if project_changed:
        changes[project_path] = _encode_markdown(project_text, project_bom)
    if changes_made:
        terminal_phase_id = phase["phase_id"] if updated["active_phase_id"] is None and phase["status"] != "ACTIVE" else None
        _finalize_v3_consistency(root, updated, changes, now, terminal_phase_id=terminal_phase_id)
        _validate_state(root, updated)
    result = _plan(
        "migrate-phase-control",
        root,
        changes,
        args.apply,
        phase_id=phase["phase_id"],
        boundary_before=boundary["status"],
        boundary_after="COMPLETE" if boundary["status"] == "LEGACY" else boundary["status"],
        workspace_schema_version=updated["schema_version"],
        implicit_session_created=False,
    )
    if args.apply and changes:
        _transaction_write(root, changes, operation="migrate-phase-control")
    return result


def _ensure_section_fields(payload: bytes, section_name: str, fields: list[tuple[str, str]], relative: str) -> bytes:
    text, bom = _decode_markdown(payload)
    section = _marked_section(text, section_name, required=True)
    assert section is not None
    missing = [(label, value) for label, value in fields if re.search(rf"(?m)^- {re.escape(label)}:", section) is None]
    if not missing:
        return payload
    heading = re.search(r"(?m)^## [^\r\n]+\r?$", section)
    if heading is None:
        raise WorkspaceError("WS_CONSISTENCY_MIGRATION_INVALID", f"Structured section lacks a level-2 heading: {section_name}", relative)
    ending = "\r\n" if "\r\n" in section else "\n"
    insertion = ending + ending.join(f"- {label}: `{value}`" for label, value in missing) + ending
    updated_section = section[: heading.end()] + insertion + section[heading.end():]
    return _encode_markdown(text.replace(section, updated_section, 1), bom)


def _remove_empty_duplicate_section_markers(payload: bytes, section_names: Iterable[str], relative: str) -> bytes:
    text, bom = _decode_markdown(payload)
    marker_pattern = re.compile(SECTION_LINE.pattern, re.IGNORECASE | re.MULTILINE)
    for section_name in section_names:
        while True:
            markers = list(marker_pattern.finditer(text))
            matching_indexes = [
                index for index, marker in enumerate(markers) if marker.group("name").lower() == section_name.lower()
            ]
            if len(matching_indexes) <= 1:
                break
            removable: tuple[int, int] | None = None
            for index in matching_indexes:
                marker = markers[index]
                section_end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
                if not text[marker.end():section_end].strip():
                    removable = (marker.start(), section_end)
                    break
            if removable is None:
                raise WorkspaceError(
                    "WS_CONSISTENCY_MIGRATION_CONFLICT",
                    f"Duplicate structured sections contain non-empty competing records: {section_name}",
                    relative,
                )
            text = text[: removable[0]] + text[removable[1]:]
    return _encode_markdown(text, bom)


def _ensure_current_binding_section(payload: bytes, relative: str) -> bytes:
    text, bom = _decode_markdown(payload)
    section = _marked_section(text, "current-phase-binding")
    fields = [
        ("Binding schema", "2"),
        ("Active Phase ID", "N/A"),
        ("Active Phase control", "N/A"),
        ("Phase control SHA-256", "N/A"),
        ("Phase boundary SHA-256", "N/A"),
        ("Boundary review ID", "N/A"),
        ("Boundary review SHA-256", "N/A"),
        ("Candidate mapping", "N/A"),
        ("Recommendation", "N/A"),
        ("Phase recovery SHA-256", "N/A"),
        ("Recorded at", "N/A"),
    ]
    if section is None:
        ending = "\r\n" if "\r\n" in text else "\n"
        block = ending.join(
            ["<!-- MALTS:section=current-phase-binding -->", "## Current Phase Binding", ""]
            + [f"- {label}: `{value}`" for label, value in fields]
        )
        return _encode_markdown(text.rstrip("\r\n") + ending + ending + block + ending, bom)
    return _ensure_section_fields(payload, "current-phase-binding", fields, relative)


def _migration_recovery_fields(record_id: str, recovery_point: dict[str, Any], now: str) -> list[tuple[str, str]]:
    evidence = [_single_line(str(item)) for item in recovery_point["evidence_refs"] if _single_line(str(item))]
    if not evidence:
        raise WorkspaceError("WS_CONSISTENCY_MIGRATION_INVALID", "Runtime recovery point requires evidence before migration.")
    return [
        ("Recovery schema", "1"),
        ("Record ID", record_id),
        ("Summary", _require_reference(recovery_point["summary"], "WS_CONSISTENCY_MIGRATION_INVALID", "Recovery summary")),
        ("Next action", _require_reference(recovery_point["next_action"], "WS_CONSISTENCY_MIGRATION_INVALID", "Recovery next action")),
        ("Evidence references", "; ".join(evidence)),
        ("Recorded at", now),
    ]


def _ensure_project_consistency_sections(payload: bytes, state: dict[str, Any], now: str) -> bytes:
    text, bom = _decode_markdown(payload)
    ending = "\r\n" if "\r\n" in text else "\n"
    active_phase_id = state["active_phase_id"]
    if _marked_section(text, "current-stage") is None:
        block = ending.join(
            [
                "<!-- MALTS:section=current-stage -->",
                "## Current Stage",
                "",
                f"- Active Phase: {active_phase_id or 'N/A'}",
            ]
        )
        text = text.rstrip("\r\n") + ending + ending + block + ending
    else:
        text = _replace_project_active_phase(text, active_phase_id)
    payload = _encode_markdown(text, bom)
    text, bom = _decode_markdown(payload)
    if state["active_phase_id"] is None and state["active_session_id"] is None:
        recovery_fields = _migration_recovery_fields("project:migration:recovery", state["recovery_point"], now)
    else:
        recovery_fields = [
            ("Recovery schema", "1"),
            ("Record ID", "project:recovery"),
            ("Summary", "Project recovery is current only when no applicable Phase or Session recovery source exists."),
            ("Next action", "Use the active Phase or Session recovery source while one exists."),
            ("Evidence references", "project:recovery"),
            ("Recorded at", now),
        ]
    if _marked_section(text, "recovery-notes") is None:
        block = ending.join(
            [
                "<!-- MALTS:section=recovery-notes -->",
                "## Recovery Notes",
                "",
                *[f"- {label}: `{value}`" for label, value in recovery_fields],
            ]
        )
        return _encode_markdown(text.rstrip("\r\n") + ending + ending + block + ending, bom)
    payload = _ensure_section_fields(payload, "recovery-notes", recovery_fields, "PROJECT_CONTROL.md")
    recovery_values = dict(recovery_fields)
    return _replace_recovery_record(
        payload,
        "recovery-notes",
        "PROJECT_CONTROL.md",
        record_id=recovery_values["Record ID"],
        summary=recovery_values["Summary"],
        next_action=recovery_values["Next action"],
        evidence_refs=recovery_values["Evidence references"].split("; "),
        recorded_at=recovery_values["Recorded at"],
    )


def _ensure_phase_v3_fields(
    payload: bytes,
    relative: str,
    phase_id: str,
    recovery_point: dict[str, Any],
    now: str,
) -> bytes:
    payload = _remove_empty_duplicate_section_markers(payload, ("phase-recovery",), relative)
    text, _ = _decode_markdown(payload)
    if _phase_boundary_contract(text)["status"] != "COMPLETE":
        raise WorkspaceError(
            "WS_PHASE_BOUNDARY_RECORD_MISSING",
            "Consistency migration requires a complete Phase Boundary Contract; migrate the Phase control explicitly first.",
            relative,
        )
    review_section = _marked_section(text, "phase-boundary-review", required=True)
    assert review_section is not None
    review_status = _control_value(review_section, "Review status", "WS_PHASE_BOUNDARY_RECORD_MIGRATION_REQUIRED")
    recommendation = _control_value(review_section, "Recommended review", "WS_PHASE_BOUNDARY_RECORD_MIGRATION_REQUIRED")
    reviewed_at = _control_value(review_section, "Reviewed at", "WS_PHASE_BOUNDARY_RECORD_MIGRATION_REQUIRED")
    evidence_ref = _control_value(review_section, "Evidence reference", "WS_PHASE_BOUNDARY_RECORD_MIGRATION_REQUIRED")
    authorization_ref = _control_value(review_section, "Authorization reference", "WS_PHASE_BOUNDARY_RECORD_MIGRATION_REQUIRED")
    if recommendation not in PHASE_REVIEW_RESULTS:
        raise WorkspaceError(
            "WS_PHASE_BOUNDARY_RECORD_MIGRATION_REQUIRED",
            "Legacy Boundary Review recommendation is not a supported structured value.",
            relative,
        )
    migration_status = review_status
    review_id = "N/A"
    if review_status == "NOT_RUN":
        if recommendation != "USER_DECISION_REQUIRED" or any(
            value != "N/A" for value in (reviewed_at, evidence_ref, authorization_ref)
        ):
            raise WorkspaceError(
                "WS_PHASE_BOUNDARY_RECORD_MIGRATION_REQUIRED",
                "A NOT_RUN legacy Boundary Review contains decision evidence and requires explicit reconciliation.",
                relative,
            )
    elif review_status in {"COMPLETED", "PASS"}:
        if any(value == "N/A" for value in (reviewed_at, evidence_ref, authorization_ref)):
            raise WorkspaceError(
                "WS_PHASE_BOUNDARY_RECORD_MIGRATION_REQUIRED",
                "Legacy COMPLETED/PASS Boundary Review lacks structured evidence, authorization, or review time.",
                relative,
            )
        _timestamp(reviewed_at)
        migration_status = "RECORDED"
        review_id = f"legacy-review:{phase_id}:{hashlib.sha256(payload).hexdigest()[:16]}"
    elif review_status not in {"RECORDED", "SUPERSEDED"}:
        raise WorkspaceError(
            "WS_PHASE_BOUNDARY_RECORD_MIGRATION_REQUIRED",
            "Legacy Boundary Review status requires an explicit reviewed migration decision.",
            relative,
        )
    payload = _ensure_section_fields(
        payload,
        "phase-boundary-review",
        [("Review schema", "1"), ("Review ID", review_id), ("Candidate mapping", "UNCLEAR")],
        relative,
    )
    if migration_status != review_status:
        text, bom = _decode_markdown(payload)
        section = _marked_section(text, "phase-boundary-review", required=True)
        assert section is not None
        updated_section = _replace_line(section, "- Review ID:", f"- Review ID: `{review_id}`", "WS_PHASE_BOUNDARY_RECORD_MIGRATION_REQUIRED")
        updated_section = _replace_line(updated_section, "- Review status:", "- Review status: `RECORDED`", "WS_PHASE_BOUNDARY_RECORD_MIGRATION_REQUIRED")
        payload = _encode_markdown(text.replace(section, updated_section, 1), bom)
    _boundary_review_record(payload, relative)
    recovery_fields = _migration_recovery_fields(f"phase:{phase_id}:migration:recovery", recovery_point, now)
    payload = _ensure_section_fields(
        payload,
        "phase-recovery",
        recovery_fields,
        relative,
    )
    recovery_values = dict(recovery_fields)
    return _replace_recovery_record(
        payload,
        "phase-recovery",
        relative,
        record_id=recovery_values["Record ID"],
        summary=recovery_values["Summary"],
        next_action=recovery_values["Next action"],
        evidence_refs=recovery_values["Evidence references"].split("; "),
        recorded_at=recovery_values["Recorded at"],
    )


def _ensure_session_v3_fields(
    payload: bytes,
    relative: str,
    session_id: str,
    recovery_point: dict[str, Any],
    now: str,
) -> bytes:
    payload = _remove_empty_duplicate_section_markers(payload, ("session-checkpoint",), relative)
    recovery_fields = _migration_recovery_fields(f"session:{session_id}:migration:checkpoint", recovery_point, now)
    payload = _ensure_section_fields(
        payload,
        "session-checkpoint",
        recovery_fields,
        relative,
    )
    recovery_values = dict(recovery_fields)
    return _replace_recovery_record(
        payload,
        "session-checkpoint",
        relative,
        record_id=recovery_values["Record ID"],
        summary=recovery_values["Summary"],
        next_action=recovery_values["Next action"],
        evidence_refs=recovery_values["Evidence references"].split("; "),
        recorded_at=recovery_values["Recorded at"],
    )


def _require_expected_sha256(value: str, code: str, label: str) -> str:
    normalized = value.upper()
    if re.fullmatch(r"[A-F0-9]{64}", normalized) is None:
        raise WorkspaceError(code, f"{label} must be an exact 64-character SHA-256.")
    return normalized


def command_migrate_consistency_records(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state, state_payload = _load_state_capture(root)
    if state["schema_version"] == 3:
        raise WorkspaceError("WS_CONSISTENCY_MIGRATION_NOT_REQUIRED", "Workspace already uses schema v3; use reconcile-consistency-records for drift.")
    expected_state = _require_expected_sha256(args.expected_state_sha256, "WS_CONSISTENCY_STATE_HASH", "Expected state hash")
    observed_state = hashlib.sha256(state_payload).hexdigest().upper()
    if observed_state != expected_state:
        raise WorkspaceError("WS_CONSISTENCY_STATE_HASH", "workspace_control.json changed after review.", STATE_RELATIVE.as_posix())
    now = _timestamp(args.timestamp)
    changes: dict[Path, bytes] = {}
    project_payload = _ensure_project_consistency_sections(_read_bytes(root, "PROJECT_CONTROL.md"), state, now)
    changes[_target(root, "PROJECT_CONTROL.md")] = project_payload
    if state["active_phase_id"] is not None:
        phase = _active_phase(state)
        phase_recovery = state["recovery_point"]
        if state["active_session_id"] is not None:
            phase_recovery = {
                "summary": f"Phase {phase['phase_id']} remains active while Session {state['active_session_id']} owns the current checkpoint.",
                "next_action": "Resume from the active Session checkpoint before returning recovery authority to the Phase.",
                "evidence_refs": [f"phase:{phase['phase_id']}:migration", f"session:{state['active_session_id']}"],
            }
        changes[_target(root, phase["path"])] = _ensure_phase_v3_fields(
            _read_bytes(root, phase["path"]),
            phase["path"],
            phase["phase_id"],
            phase_recovery,
            now,
        )
    if state["active_session_id"] is not None:
        session = _active_session(state)
        changes[_target(root, session["path"])] = _ensure_session_v3_fields(
            _read_bytes(root, session["path"]),
            session["path"],
            session["session_id"],
            state["recovery_point"],
            now,
        )
    report_payload = _read_bytes(root, "WORK_TASK_REPORT.md")
    changes[_target(root, "WORK_TASK_REPORT.md")] = _ensure_current_binding_section(report_payload, "WORK_TASK_REPORT.md")
    handoff_path = _target(root, "PROJECT_HANDOFF.md")
    if handoff_path.is_file():
        changes[handoff_path] = _ensure_current_binding_section(handoff_path.read_bytes(), "PROJECT_HANDOFF.md")
    updated = json.loads(json.dumps(state))
    updated["schema_version"] = 3
    updated["current_phase_binding"] = None
    updated["recovery_binding"] = None
    updated["maintenance_state"].update({"state": "clean", "last_action": "migrate-consistency-records", "last_checked_at": now})
    _finalize_v3_consistency(root, updated, changes, now)
    _validate_state(root, updated)
    result = _plan(
        "migrate-consistency-records",
        root,
        changes,
        args.apply,
        operation_id=args.operation_id,
        authority=args.authority,
        workspace_schema_before=state["schema_version"],
        workspace_schema_after=3,
        expected_state_sha256=expected_state,
        implicit_session_created=False,
    )
    if args.apply:
        _transaction_write(root, changes, operation="migrate-consistency-records", operation_id=args.operation_id)
    return result


def command_record_phase_boundary_review(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    _require_consistent_mutation(root, state, allowed_codes={"WS_REVIEW_OUTCOME_UNRESOLVED"})
    if state["schema_version"] not in {3, 4}:
        raise WorkspaceError("WS_CONSISTENCY_MIGRATION_REQUIRED", "Boundary Review records require explicit workspace schema v3 or v4.")
    phase = _phase_entry(state, args.phase_id) if args.phase_id else _active_phase(state)
    path = _target(root, phase["path"])
    payload = _read_bytes(root, phase["path"])
    expected_phase = _require_expected_sha256(args.expected_phase_sha256, "WS_PHASE_BOUNDARY_RECORD_STALE", "Expected Phase hash")
    if hashlib.sha256(payload).hexdigest().upper() != expected_phase:
        raise WorkspaceError("WS_PHASE_BOUNDARY_RECORD_STALE", "Phase control changed after Boundary Review.", phase["path"])
    now = _timestamp(args.timestamp)
    text, bom = _decode_markdown(payload)
    replacements = {
        "Review schema": "1",
        "Review ID": _require_reference(args.review_id, "WS_PHASE_REVIEW_ID_REQUIRED", "Review ID"),
        "Review status": "RECORDED",
        "Candidate mapping": args.candidate_mapping,
        "Recommended review": args.recommendation,
        "Reviewed at": now,
        "Evidence reference": _require_reference(args.evidence_ref, "WS_PHASE_REVIEW_EVIDENCE_REQUIRED", "Evidence reference"),
        "Authorization reference": _single_line(args.authorization_ref or "N/A"),
    }
    section = _marked_section(text, "phase-boundary-review", required=True)
    assert section is not None
    updated_section = section
    for label, value in replacements.items():
        updated_section = _replace_line(updated_section, f"- {label}:", f"- {label}: `{value}`", "WS_PHASE_BOUNDARY_RECORD_MISSING")
    changes = {path: _encode_markdown(text.replace(section, updated_section, 1), bom)}
    updated = json.loads(json.dumps(state))
    updated["maintenance_state"].update({"state": "clean", "last_action": "record-phase-boundary-review", "last_checked_at": now})
    terminal_phase_id = phase["phase_id"] if state["active_phase_id"] is None and phase["status"] != "ACTIVE" else None
    _finalize_v3_consistency(root, updated, changes, now, terminal_phase_id=terminal_phase_id)
    result = _plan(
        "record-phase-boundary-review",
        root,
        changes,
        args.apply,
        operation_id=args.operation_id,
        review_id=replacements["Review ID"],
        review_outcome="UNRESOLVED" if args.candidate_mapping == "UNCLEAR" or args.recommendation == "USER_DECISION_REQUIRED" else "RESOLVED",
        decision_authorized=False,
        expected_phase_sha256=expected_phase,
        implicit_session_created=False,
    )
    if args.apply:
        _transaction_write(root, changes, operation="record-phase-boundary-review", operation_id=args.operation_id)
    return result


def command_reconcile_consistency_records(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state, state_payload = _load_state_capture(root)
    if state["schema_version"] not in {3, 4}:
        raise WorkspaceError("WS_CONSISTENCY_MIGRATION_REQUIRED", "Reconciliation requires workspace schema v3 or v4.")
    expected_state = _require_expected_sha256(args.expected_state_sha256, "WS_CONSISTENCY_STATE_HASH", "Expected state hash")
    if hashlib.sha256(state_payload).hexdigest().upper() != expected_state:
        raise WorkspaceError("WS_CONSISTENCY_STATE_HASH", "workspace_control.json changed after reconciliation review.", STATE_RELATIVE.as_posix())
    recovery = state["recovery_binding"]
    source_relative = recovery["source_control_path"]
    source_payload = _read_bytes(root, source_relative)
    expected_source = _require_expected_sha256(args.expected_source_sha256, "WS_RECOVERY_PHASE_BINDING_STALE", "Expected source hash")
    if hashlib.sha256(source_payload).hexdigest().upper() != expected_source:
        raise WorkspaceError("WS_RECOVERY_PHASE_BINDING_STALE", "Canonical recovery source changed after review.", source_relative)
    if state["active_phase_id"] is not None:
        phase = _active_phase(state)
        expected_phase = _require_expected_sha256(args.expected_phase_sha256, "WS_CURRENT_BINDING_STALE", "Expected active Phase hash")
        if hashlib.sha256(_read_bytes(root, phase["path"])).hexdigest().upper() != expected_phase:
            raise WorkspaceError("WS_CURRENT_BINDING_STALE", "Active Phase changed after reconciliation review.", phase["path"])
    now = _timestamp(args.timestamp)
    section_name = "session-checkpoint" if recovery["source_kind"] == "ACTIVE_SESSION_CHECKPOINT" else "phase-recovery" if recovery["source_kind"] in {"ACTIVE_PHASE_RECOVERY", "PAUSED_PHASE_RECOVERY", "TERMINAL_PHASE_RECOVERY"} else "recovery-notes"
    canonical = _recovery_record(source_payload, section_name, source_relative)
    updated = json.loads(json.dumps(state))
    updated["recovery_point"] = {
        "summary": canonical["summary"],
        "next_action": canonical["next_action"],
        "evidence_refs": canonical["evidence_refs"],
    }
    updated["maintenance_state"].update({"state": "clean", "last_action": "reconcile-consistency-records", "last_checked_at": now})
    changes: dict[Path, bytes] = {}
    terminal_phase_id = recovery["source_phase_id"] if recovery["source_kind"] in {"PAUSED_PHASE_RECOVERY", "TERMINAL_PHASE_RECOVERY"} else None
    _finalize_v3_consistency(root, updated, changes, now, terminal_phase_id=terminal_phase_id)
    result = _plan(
        "reconcile-consistency-records",
        root,
        changes,
        args.apply,
        operation_id=args.operation_id,
        authority=args.authority,
        expected_state_sha256=expected_state,
        expected_source_sha256=expected_source,
        implicit_session_created=False,
    )
    if args.apply:
        _transaction_write(root, changes, operation="reconcile-consistency-records", operation_id=args.operation_id)
    return result


def command_rebind_v4_consistency(args: argparse.Namespace) -> dict[str, Any]:
    """Explicitly rebind v4 derived consistency records after reviewed canonical edits."""

    root = _workspace(args.workspace)
    state, state_payload = _load_state_capture(root)
    _require_schema_v4(state, "rebind-v4-consistency")
    expected_state = _require_expected_sha256(args.expected_state_sha256, "WS_CONSISTENCY_STATE_HASH", "Expected state hash")
    if _sha256_payload(state_payload) != expected_state:
        raise WorkspaceError("WS_CONSISTENCY_STATE_HASH", "workspace_control.json changed after rebind review.", STATE_RELATIVE.as_posix())
    phase = _active_phase(state)
    phase_payload = _read_bytes(root, phase["path"])
    expected_phase = _require_expected_sha256(args.expected_phase_sha256, "WS_CURRENT_BINDING_STALE", "Expected active Phase hash")
    if _sha256_payload(phase_payload) != expected_phase:
        raise WorkspaceError("WS_CURRENT_BINDING_STALE", "Active Phase changed after rebind review.", phase["path"])
    now = _timestamp(args.timestamp)
    updated = json.loads(json.dumps(state))
    canonical = _recovery_record(phase_payload, "phase-recovery", phase["path"])
    updated["recovery_point"] = {"summary": canonical["summary"], "next_action": canonical["next_action"], "evidence_refs": canonical["evidence_refs"]}
    updated["maintenance_state"].update({"state": "clean", "last_action": "rebind-v4-consistency", "last_checked_at": now})
    changes: dict[Path, bytes] = {}
    _finalize_v4_consistency(root, updated, changes, now)
    result = _plan("rebind-v4-consistency", root, changes, args.apply, expected_state_sha256=expected_state, expected_phase_sha256=expected_phase, implicit_session_created=False)
    if args.apply:
        _transaction_write(root, changes, operation="rebind-v4-consistency", operation_id=args.operation_id)
    return result


def command_recover_workspace_transaction(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    try:
        recovery_arguments: dict[str, Any] = {
            "operation_id": args.operation_id,
            "expected_journal_sha256": args.expected_journal_sha256,
            "apply": args.apply,
            "profile": WORKSPACE_TRANSACTION_PROFILE,
        }
        if getattr(args, "expected_lock_sha256", None) is not None:
            recovery_arguments["expected_lock_sha256"] = args.expected_lock_sha256
        recovery = recover_transaction(root, **recovery_arguments)
    except TransactionError as exc:
        raise WorkspaceError(exc.code, exc.message, exc.detail) from exc
    return {
        "status": "PASS",
        "operation": "recover-workspace-transaction",
        "mode": recovery["mode"],
        "workspace": str(root),
        "writes_performed": recovery["writes_performed"],
        "recovery": recovery,
        "implicit_session_created": False,
    }


def _require_reference(value: str | None, code: str, label: str) -> str:
    normalized = _single_line(value or "")
    if not normalized or normalized.upper() in {"N/A", "NA", "UNKNOWN", "TBD"}:
        raise WorkspaceError(code, f"{label} must be an explicit non-placeholder reference.")
    return normalized


def _markdown_phase_status(text: str) -> str:
    matches = re.findall(r"(?m)^- Status:[ \t]*([A-Z_]+)[ \t]*\r?$", text)
    if len(matches) != 1:
        raise WorkspaceError("WS_PHASE_CONTROL_INVALID", "Phase control must contain exactly one machine-readable Status field.")
    return matches[0]


def command_pause_phase(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    _require_consistent_mutation(root, state)
    if state["schema_version"] not in {2, 3, 4}:
        raise WorkspaceError("WS_PHASE_MIGRATION_REQUIRED", "Pause requires explicit workspace/Phase migration to schema v2.")
    if state["active_session_id"] is not None:
        raise WorkspaceError("WS_SESSION_ACTIVE", "Close the active Session before pausing its Phase.")
    phase = _active_phase(state)
    path, _, text, bom = _phase_control_info(root, phase)
    if _phase_boundary_contract(text)["status"] != "COMPLETE":
        raise WorkspaceError("WS_PHASE_MIGRATION_REQUIRED", "Pause requires a complete Phase Boundary Contract.", phase["path"])
    if _markdown_phase_status(text) != "ACTIVE":
        raise WorkspaceError("WS_PHASE_CONTROL_DRIFT", "Only an ACTIVE Phase can be paused.", phase["path"])
    reason = _require_reference(args.reason, "WS_PHASE_PAUSE_REASON_REQUIRED", "Pause reason")
    review_ref = _require_reference(args.boundary_review_ref, "WS_PHASE_REVIEW_REQUIRED", "Boundary review reference")
    authorization = _require_reference(args.authorization_ref, "WS_AUTHORIZATION_REQUIRED", "Authorization reference")
    now = _timestamp(args.timestamp)
    text = _replace_line(text, "- Status:", "- Status: PAUSED", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Updated at:", f"- Updated at: {now}", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Pause reason:", f"- Pause reason: `{reason}`", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Paused at:", f"- Paused at: `{now}`", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Review ID:", f"- Review ID: `{review_ref}`", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Review status:", "- Review status: `RECORDED`", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Candidate mapping:", "- Candidate mapping: `SAME_PHASE`", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Recommended review:", "- Recommended review: `KEEP`", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Reviewed at:", f"- Reviewed at: `{now}`", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Evidence reference:", f"- Evidence reference: `{review_ref}`", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Authorization reference:", f"- Authorization reference: `{authorization}`", "WS_PHASE_CONTROL_INVALID")
    updated = json.loads(json.dumps(state))
    _phase_entry(updated, phase["phase_id"])["status"] = "PAUSED"
    updated["active_phase_id"] = None
    updated["maintenance_state"].update({"state": "clean", "last_action": "pause-phase", "last_checked_at": now})
    updated["recovery_point"] = {
        "summary": f"Phase {phase['phase_id']} is PAUSED and provides no execution authorization.",
        "next_action": "Open another Phase or explicitly resume this Phase after boundary, plan, and authorization review.",
        "evidence_refs": [review_ref, authorization],
    }
    project_path = _target(root, "PROJECT_CONTROL.md")
    project_text, project_bom = _decode_markdown(_read_bytes(root, "PROJECT_CONTROL.md"))
    project_text = _replace_project_active_phase(project_text, None)
    changes = {
        path: _encode_markdown(text, bom),
        project_path: _encode_markdown(project_text, project_bom),
        _state_path(root): _json_bytes(updated),
    }
    _finalize_v3_consistency(root, updated, changes, now, terminal_phase_id=phase["phase_id"])
    _validate_state(root, updated)
    result = _plan("pause-phase", root, changes, args.apply, phase_id=phase["phase_id"], phase_status="PAUSED", implicit_session_created=False)
    if args.apply:
        _transaction_write(root, changes, operation="pause-phase")
    return result


def command_resume_phase(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    _require_consistent_mutation(root, state)
    if state["schema_version"] not in {2, 3, 4}:
        raise WorkspaceError("WS_PHASE_MIGRATION_REQUIRED", "Resume requires explicit workspace/Phase migration to schema v2.")
    if state["active_phase_id"] is not None:
        raise WorkspaceError("WS_PHASE_ACTIVE", "Close or pause the active Phase before resuming another one.")
    if state["active_session_id"] is not None:
        raise WorkspaceError("WS_SESSION_ACTIVE", "An active Session is inconsistent with a resumable Phase boundary.")
    review_ref = _require_reference(args.boundary_review_ref, "WS_PHASE_REVIEW_REQUIRED", "Boundary review reference")
    plan_review_ref = _require_reference(args.plan_review_ref, "WS_PHASE_PLAN_REVIEW_REQUIRED", "Plan review reference")
    authorization = _require_reference(args.authorization_ref, "WS_AUTHORIZATION_REQUIRED", "Authorization reference")
    phase = _phase_entry(state, args.phase_id)
    if phase["status"] != "PAUSED":
        raise WorkspaceError("WS_PHASE_NOT_PAUSED", "Only a PAUSED Phase can be resumed.", phase["path"])
    path, _, text, bom = _phase_control_info(root, phase)
    if _markdown_phase_status(text) != "PAUSED":
        raise WorkspaceError("WS_PHASE_CONTROL_DRIFT", "Runtime and Markdown Phase status disagree.", phase["path"])
    if _phase_boundary_contract(text)["status"] != "COMPLETE":
        raise WorkspaceError("WS_PHASE_MIGRATION_REQUIRED", "Resume requires a complete Phase Boundary Contract.", phase["path"])
    expected = args.expected_plan_sha256.upper()
    binding = _phase_plan_binding(root, phase)
    if binding is None or binding["Active plan"] == "N/A":
        if expected != "N/A":
            raise WorkspaceError("WS_PHASE_PLAN_STALE", "A Phase without an active plan must use --expected-plan-sha256 N/A.")
    else:
        if binding["Last recheck trigger"] not in PLAN_RECHECK_TRIGGERS:
            raise WorkspaceError(
                "WS_PHASE_PLAN_TRIGGER_MIGRATION_REQUIRED",
                "Resume blocked: the active Plan uses a noncanonical recheck trigger and requires explicit reviewed migration.",
                phase["path"],
            )
        if not re.fullmatch(r"[0-9A-F]{64}", expected):
            raise WorkspaceError("WS_PHASE_PLAN_STALE", "A bound active plan requires its exact 64-character SHA-256.")
        plan_path = _target(root, binding["Active plan"])
        observed = hashlib.sha256(_path_read_bytes(plan_path)).hexdigest().upper() if _path_is_file(plan_path) else None
        if observed != expected or binding["Plan content SHA-256"].upper() != expected:
            raise WorkspaceError("WS_PHASE_PLAN_STALE", "Resume blocked: active Plan bytes or binding do not match the reviewed SHA-256.", binding["Active plan"])
        if binding["Plan status"] != "ACTIVE" or binding["Last recheck result"] not in {"PASS", "UPDATED"} or binding["Launch review invalidated"] != "No":
            raise WorkspaceError("WS_PHASE_PLAN_STALE", "Resume blocked: Plan status, recheck result, or launch-review binding is not current.", phase["path"])
    now = _timestamp(args.timestamp)
    text = _replace_line(text, "- Status:", "- Status: ACTIVE", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Updated at:", f"- Updated at: {now}", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Resume boundary review:", f"- Resume boundary review: `{review_ref}`", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Resume plan review:", f"- Resume plan review: `{plan_review_ref}`", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Resume authorization:", f"- Resume authorization: `{authorization}`", "WS_PHASE_CONTROL_INVALID")
    text = _replace_line(text, "- Resumed at:", f"- Resumed at: `{now}`", "WS_PHASE_CONTROL_INVALID")
    updated = json.loads(json.dumps(state))
    _phase_entry(updated, phase["phase_id"])["status"] = "ACTIVE"
    updated["active_phase_id"] = phase["phase_id"]
    updated["maintenance_state"].update({"state": "clean", "last_action": "resume-phase", "last_checked_at": now})
    updated["recovery_point"] = {
        "summary": f"Phase {phase['phase_id']} resumed after explicit boundary, plan, and authorization review.",
        "next_action": "Continue only within the resumed Phase Boundary Contract and reviewed authorization.",
        "evidence_refs": [review_ref, plan_review_ref, authorization],
    }
    project_path = _target(root, "PROJECT_CONTROL.md")
    project_text, project_bom = _decode_markdown(_read_bytes(root, "PROJECT_CONTROL.md"))
    project_text = _replace_project_active_phase(project_text, phase["phase_id"])
    changes = {
        path: _encode_markdown(text, bom),
        project_path: _encode_markdown(project_text, project_bom),
        _state_path(root): _json_bytes(updated),
    }
    _finalize_v3_consistency(root, updated, changes, now)
    _validate_state(root, updated)
    result = _plan("resume-phase", root, changes, args.apply, phase_id=phase["phase_id"], active_status="ACTIVE", implicit_session_created=False)
    if args.apply:
        _transaction_write(root, changes, operation="resume-phase")
    return result


def _load_transition_array(root: Path, relative: str, label: str) -> tuple[list[dict[str, Any]], str]:
    data = _read_bytes(root, relative)
    try:
        value = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkspaceError("WS_PHASE_TRANSITION_INPUT_INVALID", f"{label} must be a UTF-8 JSON array.", relative) from exc
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise WorkspaceError("WS_PHASE_TRANSITION_INPUT_INVALID", f"{label} must be a JSON array of objects.", relative)
    return value, hashlib.sha256(data).hexdigest().upper()


def _transition_plan_path(root: Path, relative: str) -> Path:
    path = _target(root, relative)
    normalized = Path(relative.replace("\\", "/"))
    try:
        normalized.relative_to(TRANSITION_PLAN_PREFIX)
    except ValueError as exc:
        raise WorkspaceError("WS_PHASE_TRANSITION_PLAN_PATH", "Transition plans must be workspace-relative under runtime/phase-transitions/.", relative) from exc
    if not normalized.name.endswith(".plan.json"):
        raise WorkspaceError("WS_PHASE_TRANSITION_PLAN_PATH", "Transition plan path must end with .plan.json.", relative)
    return path


def command_plan_phase_transition(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    _require_consistent_mutation(root, state)
    if state["schema_version"] not in {2, 3, 4}:
        raise WorkspaceError("WS_PHASE_MIGRATION_REQUIRED", "Phase transition planning requires workspace-control schema v2.")
    if state["active_session_id"] is not None:
        raise WorkspaceError("WS_SESSION_ACTIVE", "Close the active Session before planning a Phase transition.")
    source = _phase_entry(state, args.source_phase_id)
    if source["status"] not in {"ACTIVE", "PAUSED"}:
        raise WorkspaceError("WS_PHASE_TRANSITION_STATE", "Only ACTIVE or PAUSED Phases can be superseded.", source["path"])
    if state["active_phase_id"] not in {None, source["phase_id"]}:
        raise WorkspaceError("WS_PHASE_ACTIVE", "Another active Phase prevents this transition.")
    if any(item["phase_id"] == args.target_phase_id for item in state["phase_controls"]):
        raise WorkspaceError("WS_PHASE_EXISTS", "Target Phase ID is already registered.", args.target_phase_id)
    target_id = _validate_id(args.target_phase_id, "Target Phase ID")
    if not _single_line(args.target_goal):
        raise WorkspaceError("WS_GOAL_EMPTY", "Target Phase goal must not be empty.")
    boundary_values = _phase_boundary_values(args, required=True)
    review_ref = _require_reference(args.boundary_review_ref, "WS_PHASE_REVIEW_REQUIRED", "Boundary review reference")
    authorization = _require_reference(args.authorization_ref, "WS_AUTHORIZATION_REQUIRED", "Authorization reference")
    source_path, source_data, source_text, _ = _phase_control_info(root, source)
    if _phase_boundary_contract(source_text)["status"] != "COMPLETE":
        raise WorkspaceError("WS_PHASE_MIGRATION_REQUIRED", "Source Phase requires explicit boundary migration before transition.", source["path"])
    carry_over, carry_hash = _load_transition_array(root, args.carry_over_file, "Carry-over input")
    dispositions, disposition_hash = _load_transition_array(root, args.disposition_file, "Disposition input")
    queue = _phase_table_summary(source_text, "phase-queue", "Status")
    active_by_id = {row.get("Task ID", ""): row for row in queue["active_rows"]}
    covered: list[str] = []
    required_carry_fields = {
        "task_id", "source_status", "remaining_work", "evidence", "recovery", "authorization_state", "target_phase", "reason"
    }
    for item in carry_over:
        if set(item) != required_carry_fields or any(not _single_line(str(item[field])) for field in required_carry_fields):
            raise WorkspaceError("WS_PHASE_CARRY_OVER_INVALID", "Every Carry-over row must contain the exact non-empty transfer fields.")
        task_id = _validate_id(str(item["task_id"]), "Carry-over Task ID")
        if task_id not in active_by_id:
            raise WorkspaceError("WS_PHASE_CARRY_OVER_INVALID", "Carry-over Task ID is not an unfinished source queue row.", task_id)
        if str(item["target_phase"]) != target_id:
            raise WorkspaceError("WS_PHASE_CARRY_OVER_INVALID", "Carry-over target_phase must equal the planned target Phase.", task_id)
        if str(item["source_status"]).upper() != active_by_id[task_id].get("Status", "").upper():
            raise WorkspaceError("WS_PHASE_CARRY_OVER_INVALID", "Carry-over source_status must preserve the source queue status.", task_id)
        covered.append(task_id)
    required_disposition_fields = {"task_id", "disposition", "reason"}
    for item in dispositions:
        if set(item) != required_disposition_fields or not _single_line(str(item.get("reason", ""))):
            raise WorkspaceError("WS_PHASE_DISPOSITION_INVALID", "Each disposition needs task_id, disposition, and reason.")
        task_id = _validate_id(str(item["task_id"]), "Disposition Task ID")
        if task_id not in active_by_id or str(item["disposition"]) not in {"CANCELLED", "DEFERRED_OUTSIDE_MALTS"}:
            raise WorkspaceError("WS_PHASE_DISPOSITION_INVALID", "Disposition must cover an unfinished source Task with an explicit terminal disposition.", task_id)
        covered.append(task_id)
    if len(covered) != len(set(covered)):
        raise WorkspaceError("WS_PHASE_DISPOSITION_DUPLICATE", "An unfinished Task may have exactly one Carry-over or disposition row.")
    missing = sorted(set(active_by_id) - set(covered))
    if missing:
        raise WorkspaceError("WS_PHASE_DISPOSITION_INCOMPLETE", "Every unfinished source Task requires explicit Carry-over or disposition: " + ", ".join(missing))
    now = _timestamp(args.timestamp)
    state_bytes = _read_bytes(root, STATE_RELATIVE)
    project_bytes = _read_bytes(root, "PROJECT_CONTROL.md")
    plan = {
        "schema_version": 1,
        "operation": "phase-transition",
        "created_at": now,
        "source_phase": {
            "phase_id": source["phase_id"],
            "path": source["path"],
            "status": source["status"],
            "sha256": hashlib.sha256(source_data).hexdigest().upper(),
        },
        "target_phase": {
            "phase_id": target_id,
            "path": f"phases/{target_id}/PHASE_CONTROL.md",
            "goal": _single_line(args.target_goal),
            "boundary_values": boundary_values,
        },
        "carry_over": carry_over,
        "dispositions": dispositions,
        "boundary_review_ref": review_ref,
        "authorization_ref": authorization,
        "preconditions": {
            "workspace_state_sha256": hashlib.sha256(state_bytes).hexdigest().upper(),
            "project_control_sha256": hashlib.sha256(project_bytes).hexdigest().upper(),
            "carry_over_input_sha256": carry_hash,
            "disposition_input_sha256": disposition_hash,
        },
    }
    plan_payload = _json_bytes(plan)
    plan_sha256 = hashlib.sha256(plan_payload).hexdigest().upper()
    plan_path = _transition_plan_path(root, args.plan_out)
    changes = {plan_path: plan_payload}
    result = _plan(
        "plan-phase-transition",
        root,
        changes,
        args.apply,
        plan_path=_relative(root, plan_path),
        plan_sha256=plan_sha256,
        source_phase_id=source["phase_id"],
        target_phase_id=target_id,
        transition_performed=False,
        implicit_session_created=False,
    )
    if args.apply:
        _transaction_write(root, changes, must_be_new=(plan_path,), operation="plan-phase-transition")
    return result


def command_apply_phase_transition(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    _require_consistent_mutation(root, state)
    plan_path = _transition_plan_path(root, args.plan)
    if not plan_path.is_file():
        raise WorkspaceError("WS_PHASE_TRANSITION_PLAN_MISSING", "Persisted transition plan is missing.", args.plan)
    plan_payload = _path_read_bytes(plan_path)
    observed_plan_hash = hashlib.sha256(plan_payload).hexdigest().upper()
    expected_plan_hash = args.expected_plan_sha256.upper()
    if not re.fullmatch(r"[0-9A-F]{64}", expected_plan_hash) or expected_plan_hash != observed_plan_hash:
        raise WorkspaceError("WS_PHASE_TRANSITION_PLAN_HASH", "Persisted transition plan does not match --expected-plan-sha256.", args.plan)
    try:
        plan = json.loads(plan_payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkspaceError("WS_PHASE_TRANSITION_PLAN_INVALID", "Transition plan is not valid UTF-8 JSON.", args.plan) from exc
    if not isinstance(plan, dict) or plan.get("schema_version") != 1 or plan.get("operation") != "phase-transition":
        raise WorkspaceError("WS_PHASE_TRANSITION_PLAN_INVALID", "Transition plan identity is invalid.", args.plan)
    preconditions = plan.get("preconditions", {})
    current_state_bytes = _read_bytes(root, STATE_RELATIVE)
    current_project_bytes = _read_bytes(root, "PROJECT_CONTROL.md")
    if hashlib.sha256(current_state_bytes).hexdigest().upper() != preconditions.get("workspace_state_sha256"):
        raise WorkspaceError("WS_PHASE_TRANSITION_STATE_DRIFT", "Workspace state changed after transition planning.", STATE_RELATIVE.as_posix())
    if hashlib.sha256(current_project_bytes).hexdigest().upper() != preconditions.get("project_control_sha256"):
        raise WorkspaceError("WS_PHASE_TRANSITION_PROJECT_DRIFT", "PROJECT_CONTROL changed after transition planning.", "PROJECT_CONTROL.md")
    source_plan = plan["source_phase"]
    target_plan = plan["target_phase"]
    source = _phase_entry(state, source_plan["phase_id"])
    if source["path"] != source_plan["path"] or source["status"] != source_plan["status"]:
        raise WorkspaceError("WS_PHASE_TRANSITION_STATE_DRIFT", "Source Phase registration changed after planning.", source["path"])
    source_path, source_data, source_text, source_bom = _phase_control_info(root, source)
    if hashlib.sha256(source_data).hexdigest().upper() != source_plan["sha256"]:
        raise WorkspaceError("WS_PHASE_TRANSITION_SOURCE_DRIFT", "Source Phase control changed after transition planning.", source["path"])
    target_id = target_plan["phase_id"]
    if any(item["phase_id"] == target_id for item in state["phase_controls"]):
        raise WorkspaceError("WS_PHASE_EXISTS", "Target Phase was registered after planning.", target_id)
    target_path = _target(root, target_plan["path"])
    if target_path.exists():
        raise WorkspaceError("WS_FILE_EXISTS", "Target Phase control path already exists.", target_plan["path"])
    if state["active_session_id"] is not None or state["active_phase_id"] not in {None, source["phase_id"]}:
        raise WorkspaceError("WS_PHASE_TRANSITION_STATE_DRIFT", "Active Phase/Session topology changed after planning.")
    language = _language(args, root)
    target_payload = _render_phase_control(
        language,
        target_id,
        target_plan["goal"],
        plan["created_at"],
        target_plan["boundary_values"],
    )
    target_text, target_bom = _decode_markdown(target_payload)
    source_rows: list[list[str]] = []
    target_provenance_rows: list[list[str]] = []
    target_queue_rows: list[list[str]] = []
    for item in plan["carry_over"]:
        source_rows.append(
            [
                str(item["task_id"]),
                str(item["source_status"]),
                str(item["remaining_work"]),
                str(item["evidence"]),
                str(item["recovery"]),
                str(item["authorization_state"]),
                str(item["target_phase"]),
                str(item["reason"]),
            ]
        )
        target_provenance_rows.append(
            [
                str(item["task_id"]),
                source["phase_id"],
                str(item["source_status"]),
                str(item["remaining_work"]),
                str(item["evidence"]),
                str(item["recovery"]),
                str(item["authorization_state"]),
                "TODO",
            ]
        )
        target_queue_rows.append(
            [
                str(item["task_id"]),
                str(item["remaining_work"]),
                "TODO",
                f"{item['evidence']}; Carried from {source['phase_id']}",
            ]
        )
    source_queue_by_id = {
        row.get("Task ID", ""): row for row in _phase_table_summary(source_text, "phase-queue", "Status")["rows"]
    }
    for item in plan["dispositions"]:
        source_row = source_queue_by_id.get(str(item["task_id"]), {})
        source_rows.append(
            [
                str(item["task_id"]),
                str(source_row.get("Status", "UNKNOWN")),
                f"Disposition: {item['disposition']}",
                str(source_row.get("Evidence", "N/A")),
                "N/A",
                str(plan["authorization_ref"]),
                "N/A",
                str(item["reason"]),
            ]
        )
    source_text = _append_table_rows(source_text, "phase-carry-over", source_rows, "WS_PHASE_CARRY_OVER_INVALID")
    source_text = _replace_line(source_text, "- Status:", "- Status: SUPERSEDED", "WS_PHASE_CONTROL_INVALID")
    source_text = _replace_line(source_text, "- Updated at:", f"- Updated at: {plan['created_at']}", "WS_PHASE_CONTROL_INVALID")
    source_text = _replace_line(source_text, "- Close result:", "- Close result: SUPERSEDED", "WS_PHASE_CONTROL_INVALID")
    source_text = _replace_line(source_text, "- Exit criteria status:", "- Exit criteria status: NOT_SATISFIED", "WS_PHASE_CONTROL_INVALID")
    disposition_summary = f"{len(plan['carry_over'])} carried; {len(plan['dispositions'])} explicitly disposed"
    source_text = _replace_line(source_text, "- Carry-over disposition:", f"- Carry-over disposition: {disposition_summary}", "WS_PHASE_CONTROL_INVALID")
    source_text = _replace_line(source_text, "- Superseded by:", f"- Superseded by: {target_id}", "WS_PHASE_CONTROL_INVALID")
    source_text = _replace_line(
        source_text,
        "- Closure evidence:",
        f"- Closure evidence: {plan['boundary_review_ref']}; {plan['authorization_ref']}; transition-plan:{observed_plan_hash}",
        "WS_PHASE_CONTROL_INVALID",
    )
    source_text = _replace_line(source_text, "- Closed at:", f"- Closed at: {plan['created_at']}", "WS_PHASE_CONTROL_INVALID")
    target_text = _append_table_rows(target_text, "phase-carried-in", target_provenance_rows, "WS_PHASE_CARRY_OVER_INVALID")
    target_text = _append_table_rows(target_text, "phase-queue", target_queue_rows, "WS_PHASE_CARRY_OVER_INVALID")
    target_revision_path: Path | None = None
    target_revision_payload: bytes | None = None
    if state["schema_version"] == 4:
        revision_id = f"{target_id}-boundary-r001"
        revision_relative = f"phases/{target_id}/boundary-revisions/{revision_id}.json"
        target_revision_path = _target(root, revision_relative)
        revision = _boundary_revision_document(
            phase_id=target_id,
            revision_id=revision_id,
            revision_number=1,
            previous_revision=None,
            boundary_values=target_plan["boundary_values"],
            review_id=f"{target_id}-transition-boundary",
            review_evidence_refs=[plan["boundary_review_ref"]],
            authorization_ref=plan["authorization_ref"],
            accepted_at=plan["created_at"],
        )
        target_revision_payload = _canonical_json_file_bytes(revision)
        target_text = _insert_before_marker(
            target_text,
            "phase-plan-recheck",
            _boundary_index_block(revision, revision_relative, _sha256_payload(target_revision_payload)),
            "WS_PHASE_TRANSITION_PLAN_INVALID",
        )
        target_text = _insert_before_marker(target_text, "phase-queue", _task_index_block([], plan["created_at"]), "WS_PHASE_TRANSITION_PLAN_INVALID")
    project_text, project_bom = _decode_markdown(current_project_bytes)
    if _marked_section(project_text, "phase-carry-over-index") is None:
        raise WorkspaceError("WS_PHASE_MIGRATION_REQUIRED", "PROJECT_CONTROL requires an explicit v2 carry-over index migration.", "PROJECT_CONTROL.md")
    project_text = _replace_project_active_phase(project_text, target_id)
    project_text = _append_table_rows(
        project_text,
        "phase-carry-over-index",
        [[source["phase_id"], target_id, observed_plan_hash, source["path"], target_plan["path"], "TRANSFERRED"]],
        "WS_PHASE_CARRY_OVER_INVALID",
    )
    updated = json.loads(json.dumps(state))
    _phase_entry(updated, source["phase_id"])["status"] = "SUPERSEDED"
    updated["phase_controls"].append({"phase_id": target_id, "path": target_plan["path"], "status": "ACTIVE"})
    updated["active_phase_id"] = target_id
    if updated["schema_version"] == 1:
        updated["schema_version"] = 2
    updated["maintenance_state"].update({"state": "clean", "last_action": "apply-phase-transition", "last_checked_at": plan["created_at"]})
    transition_evidence = [plan["boundary_review_ref"], plan["authorization_ref"], f"transition-plan:{observed_plan_hash}"]
    source_summary = f"Phase {source['phase_id']} was SUPERSEDED by {target_id} through reviewed plan {observed_plan_hash}."
    target_summary = f"Phase {target_id} is active after superseding Phase {source['phase_id']} through reviewed plan {observed_plan_hash}."
    updated["recovery_point"] = {
        "summary": target_summary,
        "next_action": f"Continue only in active Phase {target_id}; source carry-over rows are immutable provenance.",
        "evidence_refs": transition_evidence,
    }
    source_payload = _replace_recovery_record(
        _encode_markdown(source_text, source_bom),
        "phase-recovery",
        source["path"],
        record_id=f"phase:{source['phase_id']}:recovery:{plan['created_at']}",
        summary=source_summary,
        next_action=f"Continue only in successor Phase {target_id}; this source Phase is immutable provenance.",
        evidence_refs=transition_evidence,
        recorded_at=plan["created_at"],
    )
    changes = {
        source_path: source_payload,
        target_path: _encode_markdown(target_text, target_bom),
        _target(root, "PROJECT_CONTROL.md"): _encode_markdown(project_text, project_bom),
        _state_path(root): _json_bytes(updated),
    }
    if target_revision_path is not None and target_revision_payload is not None:
        changes[target_revision_path] = target_revision_payload
    _finalize_v3_consistency(root, updated, changes, plan["created_at"])
    _validate_state(root, updated)
    result = _plan(
        "apply-phase-transition",
        root,
        changes,
        args.apply,
        plan_path=args.plan,
        plan_sha256=observed_plan_hash,
        source_phase_id=source["phase_id"],
        source_terminal_status="SUPERSEDED",
        target_phase_id=target_id,
        target_status="ACTIVE",
        carry_over_count=len(plan["carry_over"]),
        disposition_count=len(plan["dispositions"]),
        implicit_session_created=False,
    )
    if args.apply:
        must_be_new = (target_path,) if target_revision_path is None else (target_revision_path, target_path)
        roles = {
            path: "IMMUTABLE_RECORD" if path == target_revision_path else
            "PHASE_CONTROL" if path in {source_path, target_path} else
            "REPORT" if _relative(root, path) == "WORK_TASK_REPORT.md" else
            "HANDOFF" if _relative(root, path) == "PROJECT_HANDOFF.md" else
            "PROJECT_CONTROL" if _relative(root, path) == "PROJECT_CONTROL.md" else "RUNTIME_STATE"
            for path in changes
        }
        _transaction_write(root, changes, must_be_new=must_be_new, operation="apply-phase-transition", target_roles=roles)
    return result


def command_open_session(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    _require_consistent_mutation(root, state)
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
    structured_lease: dict[str, Any] | None = None
    owner_kind = getattr(args, "owner_kind", "MAIN_CONTROLLER")
    owner_id = _validate_id(getattr(args, "owner_id", "MAIN_CONTROLLER"), "Session owner ID")
    if state["schema_version"] == 4:
        lease_id = _validate_id(args.lease_id, "Session lease ID")
        allowed_operations = list(dict.fromkeys(args.allowed_operation))
        write_scope = list(dict.fromkeys(args.write_scope))
        touch_set = list(dict.fromkeys(args.touch_set))
        if not allowed_operations or not write_scope or not touch_set:
            raise WorkspaceError("WS_SESSION_LEASE_REQUIRED", "v4 Session requires non-empty allowed operations, write scope, and exact touch set.")
        checkpoint_hash = _sha256_payload(
            canonical_json({"session_id": session_id, "phase_id": phase["phase_id"], "goal": args.goal.strip(), "at": now})
        )
        structured_lease = {
            "lease_id": lease_id,
            "state": "ACTIVE",
            "granted_at": now,
            "expires_at": args.expires_at,
            "authorization_ref": _require_reference(args.authorization_ref, "WS_SESSION_LEASE_REQUIRED", "Session authorization"),
            "allowed_operations": allowed_operations,
            "read_scope": list(dict.fromkeys(args.read_scope)),
            "write_scope": write_scope,
            "touch_set": touch_set,
            "excluded_surfaces": list(dict.fromkeys(args.excluded_surface)),
            "bound_lineage_ids": list(dict.fromkeys(args.bound_lineage_id)),
            "checkpoint_sha256": checkpoint_hash,
            "evidence_refs": [_require_reference(value, "WS_SESSION_LEASE_REQUIRED", "Session lease evidence") for value in args.evidence_ref],
        }
        control_text, control_bom = _decode_markdown(control)
        control = _encode_markdown(
            _replace_or_insert_lease_section(
                control_text,
                {"owner_kind": owner_kind, "owner_id": owner_id, "lease": structured_lease},
            ),
            control_bom,
        )
    updated = json.loads(json.dumps(state))
    session_row = {
            "session_id": session_id,
            "phase_id": phase["phase_id"],
            "path": relative,
            "status": "ACTIVE",
            "reason": args.reason,
            "created_at": now,
        }
    if structured_lease is not None:
        session_row.update({"updated_at": now, "owner_kind": owner_kind, "owner_id": owner_id, "lease": structured_lease})
    updated["session_controls"].append(session_row)
    updated["active_session_id"] = session_id
    updated["maintenance_state"].update({"last_action": "open-session", "last_checked_at": now})
    updated["recovery_point"] = {
        "summary": f"Session {session_id} is active in Phase {phase['phase_id']}.",
        "next_action": args.goal.strip(),
        "evidence_refs": [f"session:{session_id}"],
    }
    changes = {session_path: control, _state_path(root): _json_bytes(updated)}
    _finalize_v3_consistency(root, updated, changes, now)
    _validate_state(root, updated)
    result = _plan("open-session", root, changes, args.apply, session_id=session_id, phase_id=phase["phase_id"])
    if args.apply:
        _transaction_write(root, changes, must_be_new=(session_path,), operation="open-session")
    return result


def command_close_session(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state_data = _read_bytes(root, STATE_RELATIVE)
    state = _parse_state_bytes(root, state_data)
    _require_consistent_mutation(root, state)
    session = _active_session(state)
    now = _timestamp(args.timestamp)
    artifact_gate = artifact_close_gate(root, state, f"session:{session['session_id']}", captured_at=now)
    if artifact_gate["status"] == "BLOCKED":
        return {
            "status": "BLOCKED",
            "operation": "close-session",
            "mode": "BLOCKED",
            "workspace": str(root),
            "writes_performed": False,
            "session_id": session["session_id"],
            "reason_code": artifact_gate["reason_code"],
            "unresolved_artifacts": artifact_gate["unresolved"],
            "artifact_issues": artifact_gate.get("issues", []),
            "required_action": "Reconcile every enrolled Artifact disposition and validation issue before closing the Session.",
            "implicit_session_created": False,
        }
    path = _target(root, session["path"])
    data = _read_bytes(root, session["path"])
    text, bom = _decode_markdown(data)
    text = _replace_line(text, "- Status: ACTIVE", f"- Status: {args.status}", "WS_SESSION_CONTROL_INVALID")
    text = _replace_line(text, "- Updated at:", f"- Updated at: {now}", "WS_SESSION_CONTROL_INVALID")
    updated = json.loads(json.dumps(state))
    updated_session = next(item for item in updated["session_controls"] if item["session_id"] == session["session_id"])
    updated_session["status"] = args.status
    if updated["schema_version"] == 4:
        updated_session["updated_at"] = now
        updated_session["lease"]["state"] = "RELEASED"
    updated["active_session_id"] = None
    updated["maintenance_state"].update({"last_action": "close-session", "last_checked_at": now})
    updated["recovery_point"] = {
        "summary": f"Session {session['session_id']} closed with {args.status}; Phase {session['phase_id']} remains active.",
        "next_action": args.next_action,
        "evidence_refs": [f"session:{session['session_id']}:{args.status.lower()}"],
    }
    session_payload = _replace_recovery_record(
        _encode_markdown(text, bom),
        "session-checkpoint",
        session["path"],
        record_id=f"session:{session['session_id']}:checkpoint:{now}",
        summary=f"Session {session['session_id']} closed with {args.status} in Phase {session['phase_id']}.",
        next_action=args.next_action,
        evidence_refs=updated["recovery_point"]["evidence_refs"],
        recorded_at=now,
    )
    changes = {
        path: session_payload,
        _state_path(root): _json_bytes(updated),
    }
    _finalize_v3_consistency(root, updated, changes, now)
    _validate_state(root, updated)
    return _artifact_aware_close(
        "close-session",
        root,
        updated,
        artifact_gate,
        changes,
        {path: data, _state_path(root): state_data},
        args.apply,
        session_id=session["session_id"],
        terminal_status=args.status,
    )


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
    for phase in state["phase_controls"]:
        phase_path = _target(root, phase["path"])
        if not phase_path.is_file():
            continue
        phase_text, _ = _decode_markdown(phase_path.read_bytes())
        status_matches = re.findall(r"(?m)^- Status:[ \t]*([A-Z_]+)[ \t]*\r?$", phase_text)
        is_active_index = phase["phase_id"] == state["active_phase_id"]
        if len(status_matches) != 1:
            issues.append(
                {
                    "code": "WS_ACTIVE_PHASE_CONTROL_INVALID" if is_active_index else "WS_PHASE_CONTROL_INVALID",
                    "path": phase["path"],
                    "message": "Phase control must contain exactly one machine-readable Status field.",
                }
            )
            continue
        markdown_status = status_matches[0]
        if markdown_status != phase["status"]:
            action = None
            if is_active_index:
                action = (
                    f"Run close-phase --status {markdown_status} --workspace \"{root}\" "
                    '--closure-evidence "<reviewed evidence>" --next-action "Open the next Phase when authorized." --apply '
                    "only if the Markdown terminal state is factually correct; otherwise repair the canonical Phase control explicitly."
                )
            issue = {
                "code": "WS_ACTIVE_PHASE_CONTROL_DRIFT" if is_active_index else "WS_PHASE_CONTROL_DRIFT",
                "path": phase["path"],
                "message": f"Runtime status {phase['status']} disagrees with Markdown status {markdown_status}.",
            }
            if action is not None:
                issue["required_action"] = action
            issues.append(issue)
        closure = _structured_closure(phase_text)
        if closure is not None:
            if phase["status"] in {"ACTIVE", "PAUSED", "PLANNED"}:
                expected_placeholders = {
                    "Close result": "N/A",
                    "Exit criteria status": "NOT_EVALUATED",
                    "Carry-over disposition": "N/A",
                    "Superseded by": "N/A",
                    "Closure evidence": "N/A",
                    "Closed at": "N/A",
                }
                if any(closure[label] != expected for label, expected in expected_placeholders.items()):
                    issues.append(
                        {
                            "code": "WS_ACTIVE_PHASE_CLOSURE_CONFLICT",
                            "path": phase["path"],
                            "message": "A nonterminal Phase has a non-placeholder structured Closure record.",
                        }
                    )
            elif phase["status"] == "DONE" and (
                closure["Close result"] != "DONE" or closure["Exit criteria status"] != "SATISFIED"
            ):
                issues.append(
                    {
                        "code": "WS_PHASE_DONE_CLOSURE_INVALID",
                        "path": phase["path"],
                        "message": "DONE requires Close result DONE and Exit criteria status SATISFIED.",
                    }
                )
            elif phase["status"] == "SUPERSEDED" and (
                closure["Close result"] != "SUPERSEDED"
                or closure["Superseded by"] == "N/A"
                or closure["Carry-over disposition"] == "N/A"
            ):
                issues.append(
                    {
                        "code": "WS_PHASE_SUPERSEDED_CLOSURE_INVALID",
                        "path": phase["path"],
                        "message": "SUPERSEDED requires a target Phase and explicit Carry-over/disposition summary.",
                    }
                )
    if state["active_phase_id"] is not None:
        active = _phase_entry(state, state["active_phase_id"])
        if active["status"] != "ACTIVE":
            issues.append({"code": "WS_ACTIVE_PHASE_STATUS", "path": active["path"], "message": "Active Phase index must have ACTIVE status."})
    project_path = _target(root, "PROJECT_CONTROL.md")
    if state["schema_version"] >= 2 and project_path.is_file():
        try:
            project_text, _ = _decode_markdown(project_path.read_bytes())
            recorded_active_phase = (
                _project_active_phase_value(project_text)
                if _marked_section(project_text, "current-stage") is not None
                else None
            )
        except WorkspaceError:
            recorded_active_phase = None
        if recorded_active_phase is not None:
            expected_active_phase = state["active_phase_id"] or "N/A"
            if recorded_active_phase != expected_active_phase:
                issues.append(
                    {
                        "code": "WS_ROOT_PHASE_INDEX_DRIFT",
                        "path": "PROJECT_CONTROL.md",
                        "message": (
                            f"Canonical root Active Phase {recorded_active_phase!r} disagrees with "
                            f"workspace-control {expected_active_phase!r}."
                        ),
                        "required_action": "Review and explicitly reconcile the canonical PROJECT_CONTROL Active Phase index before continuation.",
                    }
                )
    for session in state["session_controls"]:
        session_path = _target(root, session["path"])
        if not session_path.is_file():
            continue
        session_text, _ = _decode_markdown(session_path.read_bytes())
        status_matches = re.findall(r"(?m)^- Status:[ \t]*([A-Z_]+)[ \t]*\r?$", session_text)
        session_id_matches = re.findall(r"(?m)^- Session ID:[ \t]*([^\r\n]+?)[ \t]*\r?$", session_text)
        phase_id_matches = re.findall(r"(?m)^- Phase ID:[ \t]*([^\r\n]+?)[ \t]*\r?$", session_text)
        if len(status_matches) != 1 or len(session_id_matches) != 1 or len(phase_id_matches) != 1:
            issues.append({"code": "WS_SESSION_CONTROL_INVALID", "path": session["path"], "message": "Session control metadata is malformed."})
            continue
        if (
            status_matches[0] != session["status"]
            or session_id_matches[0].strip("` ") != session["session_id"]
            or phase_id_matches[0].strip("` ") != session["phase_id"]
        ):
            issues.append(
                {
                    "code": "WS_SESSION_CONTROL_DRIFT",
                    "path": session["path"],
                    "message": "Session Markdown metadata disagrees with runtime registration; reconcile it explicitly before recovery or Phase closure.",
                }
            )
    if state["active_session_id"] is not None:
        active = next(item for item in state["session_controls"] if item["session_id"] == state["active_session_id"])
        if active["status"] != "ACTIVE":
            issues.append({"code": "WS_ACTIVE_SESSION_STATUS", "path": active["path"], "message": "Active Session index must have ACTIVE status."})
    metrics = _collect_metrics(root, state) if not issues else {"root": {}, "phases": [], "sessions": []}
    _, breaches = _budget_assessment(metrics, state["capacity_budget"]) if not issues else ("recovery-required", [])
    return issues, metrics, breaches


def _current_binding_issues(root: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    if state["schema_version"] == 1:
        return []
    issues: list[dict[str, str]] = []
    active = _phase_entry(state, state["active_phase_id"]) if state["active_phase_id"] is not None else None
    expected_hash = None
    if active is not None and _target(root, active["path"]).is_file():
        expected_hash = hashlib.sha256(_target(root, active["path"]).read_bytes()).hexdigest().upper()
    for relative in ("WORK_TASK_REPORT.md", "PROJECT_HANDOFF.md"):
        path = _target(root, relative)
        if not path.is_file():
            continue
        text, _ = _decode_markdown(path.read_bytes())
        section = _marked_section(text, "current-phase-binding")
        if section is None:
            binding_required = relative == "WORK_TASK_REPORT.md" or state["schema_version"] >= 3
            if binding_required:
                issues.append(
                    {
                        "code": "WS_CURRENT_BINDING_MISSING",
                        "path": relative,
                        "message": "The canonical current report is missing the current-phase-binding section.",
                        "required_action": "Run migrate-consistency-records in dry-run mode, review the exact authority and hashes, then apply explicitly.",
                    }
                )
            continue
        labels = ["Active Phase ID", "Active Phase control", "Phase control SHA-256", "Recorded at"]
        if state["schema_version"] in {3, 4}:
            labels = [
                "Binding schema",
                "Active Phase ID",
                "Active Phase control",
                "Phase control SHA-256",
                "Phase boundary SHA-256",
                "Boundary review ID",
                "Boundary review SHA-256",
                "Candidate mapping",
                "Recommendation",
                "Phase recovery SHA-256",
                "Recorded at",
            ]
        try:
            fields = {label: _control_value(section, label, "WS_CURRENT_BINDING_INVALID") for label in labels}
        except WorkspaceError as exc:
            issues.append(
                {
                    "code": "WS_CURRENT_BINDING_MISSING" if state["schema_version"] in {3, 4} else exc.code,
                    "path": relative,
                    "message": exc.message,
                    "required_action": "Run migrate-consistency-records or reconcile-consistency-records with exact reviewed hashes.",
                }
            )
            continue
        if state["schema_version"] in {3, 4}:
            binding = state.get("current_phase_binding")
            expected = {
                "Binding schema": "3" if state["schema_version"] == 4 else "2",
                "Active Phase ID": binding["active_phase_id"] if binding is not None else "N/A",
                "Active Phase control": binding["phase_control_path"] if binding is not None else "N/A",
                "Phase control SHA-256": binding["phase_control_sha256"] if binding is not None else "N/A",
                "Phase boundary SHA-256": binding["phase_boundary_sha256"] if binding is not None else "N/A",
                "Boundary review ID": binding["boundary_review_id"] if binding is not None and binding["boundary_review_id"] is not None else "N/A",
                "Boundary review SHA-256": binding["boundary_review_sha256"] if binding is not None else "N/A",
                "Candidate mapping": binding["candidate_mapping"] if binding is not None and binding["candidate_mapping"] is not None else "N/A",
                "Recommendation": binding["recommendation"] if binding is not None and binding["recommendation"] is not None else "N/A",
                "Phase recovery SHA-256": binding["phase_recovery_sha256"] if binding is not None else "N/A",
                "Recorded at": binding["recorded_at"] if binding is not None else "N/A",
            }
        else:
            expected = {
                "Active Phase ID": active["phase_id"] if active is not None else "N/A",
                "Active Phase control": active["path"] if active is not None else "N/A",
                "Phase control SHA-256": expected_hash or "N/A",
            }
        mismatched = [label for label, value in expected.items() if fields[label] != value]
        if mismatched:
            review_labels = {"Boundary review ID", "Boundary review SHA-256", "Candidate mapping", "Recommendation"}
            code = "WS_CURRENT_BINDING_REVIEW_DRIFT" if set(mismatched).issubset(review_labels) else "WS_CURRENT_BINDING_STALE"
            issues.append(
                {
                    "code": code,
                    "path": relative,
                    "message": "Current Phase projection disagrees with its runtime binding: " + ", ".join(mismatched),
                    "required_action": f"Reconcile the current Phase binding in {relative} from exact canonical bytes before continuation or recovery.",
                }
            )
    return issues


def _deterministic_consistency_issues(root: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    if state["schema_version"] == 4:
        return _deterministic_v4_consistency_issues(root, state)
    if state["schema_version"] != 3:
        return []
    issues: list[dict[str, str]] = []

    def add(code: str, path: str, message: str) -> None:
        issues.append(
            {
                "code": code,
                "path": path,
                "message": message,
                "required_action": "Run reconcile-consistency-records in dry-run mode with explicit authority and exact full-state/source hashes.",
            }
        )

    workspace_transaction = inspect_transaction_state(root, WORKSPACE_TRANSACTION_PROFILE)
    for finding in workspace_transaction["findings"]:
        add(finding["code"], finding["path"], finding["message"])

    binding = state.get("current_phase_binding")
    if state["active_phase_id"] is not None and isinstance(binding, dict):
        phase = _phase_entry(state, state["active_phase_id"])
        path = _target(root, phase["path"])
        if not path.is_file():
            add("WS_CURRENT_BINDING_STALE", phase["path"], "Active Phase control is missing.")
        else:
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest().upper() != binding["phase_control_sha256"]:
                add("WS_CURRENT_BINDING_STALE", phase["path"], "Active Phase full-control SHA-256 disagrees with runtime binding.")
            section_checks = (
                ("phase-boundary", "phase_boundary_sha256", "WS_PHASE_BOUNDARY_RECORD_STALE"),
                ("phase-boundary-review", "boundary_review_sha256", "WS_PHASE_BOUNDARY_RECORD_STALE"),
                ("phase-recovery", "phase_recovery_sha256", "WS_RECOVERY_RECORD_DRIFT"),
            )
            for section_name, field, code in section_checks:
                try:
                    observed = _normalized_section_sha256(payload, section_name, code, phase["path"])
                except WorkspaceError as exc:
                    add(exc.code, phase["path"], exc.message)
                    continue
                if observed != binding[field]:
                    add(code, phase["path"], f"Normalized {section_name} SHA-256 disagrees with runtime binding.")
            try:
                review = _boundary_review_record(payload, phase["path"])
                expected_review = {
                    "Review ID": binding["boundary_review_id"] or "N/A",
                    "Candidate mapping": binding["candidate_mapping"] or "N/A",
                    "Recommended review": binding["recommendation"] or "N/A",
                }
                if any(review[label] != value for label, value in expected_review.items()):
                    add("WS_CURRENT_BINDING_REVIEW_DRIFT", phase["path"], "Boundary Review values disagree with current_phase_binding.")
                if review["Review status"] == "RECORDED" and (
                    review["Candidate mapping"] == "UNCLEAR" or review["Recommended review"] == "USER_DECISION_REQUIRED"
                ):
                    add("WS_REVIEW_OUTCOME_UNRESOLVED", phase["path"], "Recorded Boundary Review remains semantically unresolved.")
            except WorkspaceError as exc:
                add(exc.code, phase["path"], exc.message)
    elif state["active_phase_id"] is not None:
        add("WS_CURRENT_BINDING_MISSING", STATE_RELATIVE.as_posix(), "Active v3 workspace lacks current_phase_binding.")
    elif binding is not None:
        add("WS_CURRENT_BINDING_STALE", STATE_RELATIVE.as_posix(), "No active Phase exists but current_phase_binding is non-null.")

    recovery = state.get("recovery_binding")
    if not isinstance(recovery, dict):
        add("WS_RECOVERY_RECORD_DRIFT", STATE_RELATIVE.as_posix(), "v3 workspace lacks recovery_binding.")
        return issues
    source_relative = recovery["source_control_path"]
    source_path = _target(root, source_relative)
    if not source_path.is_file():
        add("WS_RECOVERY_PHASE_BINDING_STALE", source_relative, "Bound recovery source control is missing.")
        return issues
    source_payload = source_path.read_bytes()
    if hashlib.sha256(source_payload).hexdigest().upper() != recovery["source_control_sha256"]:
        add("WS_RECOVERY_PHASE_BINDING_STALE", source_relative, "Recovery source full-control SHA-256 is stale.")
    section_name = "session-checkpoint" if recovery["source_kind"] == "ACTIVE_SESSION_CHECKPOINT" else "phase-recovery" if recovery["source_kind"] in {"ACTIVE_PHASE_RECOVERY", "TERMINAL_PHASE_RECOVERY"} else "recovery-notes"
    try:
        observed_section = _normalized_section_sha256(source_payload, section_name, "WS_RECOVERY_RECORD_DRIFT", source_relative)
        if observed_section != recovery["source_recovery_sha256"]:
            add("WS_RECOVERY_RECORD_DRIFT", source_relative, "Normalized recovery section SHA-256 is stale.")
        record = _recovery_record(source_payload, section_name, source_relative)
        expected_record = {
            "record_id": recovery["record_id"],
            "summary": recovery["summary"],
            "next_action": recovery["next_action"],
            "evidence_refs": recovery["evidence_refs"],
        }
        if any(record[key] != value for key, value in expected_record.items()):
            add("WS_RECOVERY_RECORD_DRIFT", source_relative, "Canonical recovery record disagrees with runtime recovery_binding.")
        if any(state["recovery_point"][key] != recovery[key] for key in ("summary", "next_action", "evidence_refs")):
            add("WS_RECOVERY_RECORD_DRIFT", STATE_RELATIVE.as_posix(), "Legacy recovery_point projection disagrees with recovery_binding.")
    except WorkspaceError as exc:
        add(exc.code, source_relative, exc.message)
    return issues


def _deterministic_v4_consistency_issues(root: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    def add(code: str, path: str, message: str) -> None:
        issues.append({"code": code, "path": path, "message": message})

    binding = state.get("current_phase_binding")
    if state.get("active_phase_id") is not None and isinstance(binding, dict):
        phase = _active_phase(state)
        phase_path = _target(root, phase["path"])
        if not _path_is_file(phase_path):
            add("WS_CURRENT_BINDING_STALE", phase["path"], "Active Phase control is missing.")
        else:
            payload = _path_read_bytes(phase_path)
            if _sha256_payload(payload) != binding.get("phase_control_sha256"):
                add("WS_CURRENT_BINDING_STALE", phase["path"], "Active Phase full-control hash disagrees with current_phase_binding.")
            try:
                revision = _boundary_revision_binding(root, payload, phase)
                if revision["revision_id"] != binding.get("boundary_revision_id") or revision["path"] != binding.get("boundary_revision_path") or revision["sha256"] != binding.get("boundary_revision_sha256"):
                    add("WS_PHASE_BOUNDARY_RECORD_STALE", phase["path"], "Current Phase immutable boundary revision binding drifted.")
                if _normalized_section_sha256(payload, "phase-boundary", "WS_PHASE_BOUNDARY_RECORD_STALE", phase["path"]) != binding.get("phase_boundary_sha256"):
                    add("WS_PHASE_BOUNDARY_RECORD_STALE", phase["path"], "Rendered Phase boundary projection drifted.")
                if _normalized_section_sha256(payload, "phase-recovery", "WS_RECOVERY_PHASE_BINDING_STALE", phase["path"]) != binding.get("phase_recovery_sha256"):
                    add("WS_RECOVERY_PHASE_BINDING_STALE", phase["path"], "Phase recovery binding drifted.")
            except WorkspaceError as exc:
                add(exc.code, exc.path or phase["path"], exc.message)
            if _task_binding_index_sha256(state.get("current_task_bindings", [])) != binding.get("task_binding_index_sha256"):
                add("WS_CURRENT_BINDING_STALE", STATE_RELATIVE.as_posix(), "Task binding index hash drifted.")
    for row in state.get("current_task_bindings", []):
        projection_path = _target(root, row["projection_path"])
        if not _path_is_file(projection_path) or _sha256_path(projection_path) != row["projection_sha256"]:
            add("RC_LINEAGE_STALE", row["projection_path"], "Task lineage projection is missing or hash-drifted.")
        contract_path = _target(root, row["latest_contract_revision"]["path"])
        if not _path_is_file(contract_path) or _sha256_path(contract_path) != row["latest_contract_revision"]["sha256"]:
            add("RC_LINEAGE_STALE", row["latest_contract_revision"]["path"], "Latest contract revision is missing or hash-drifted.")
        latest_event = row.get("latest_event")
        if latest_event is not None:
            event_path = _target(root, latest_event["path"])
            if not _path_is_file(event_path) or _sha256_path(event_path) != latest_event["sha256"]:
                add("RC_LINEAGE_STALE", latest_event["path"], "Latest Result event is missing or hash-drifted.")
    recovery = state.get("recovery_binding")
    if isinstance(recovery, dict):
        source_path = _target(root, recovery["source_control_path"])
        if not _path_is_file(source_path) or _sha256_path(source_path) != recovery.get("source_control_sha256"):
            add("WS_RECOVERY_PHASE_BINDING_STALE", recovery["source_control_path"], "Canonical recovery source full-control hash drifted.")
        boundary = recovery.get("source_boundary_revision")
        if isinstance(boundary, dict):
            boundary_path = _target(root, boundary["path"])
            if not _path_is_file(boundary_path) or _sha256_path(boundary_path) != boundary["sha256"]:
                add("WS_RECOVERY_PHASE_BINDING_STALE", boundary["path"], "Recovery boundary revision hash drifted.")
    return issues


def _mutation_consistency_issues(root: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    structural, _, _ = _validate_workspace(root, state)
    return [*structural, *_current_binding_issues(root, state), *_deterministic_consistency_issues(root, state)]


def _require_consistent_mutation(
    root: Path,
    state: dict[str, Any],
    *,
    allowed_codes: set[str] | None = None,
    allowed_paths: set[str] | None = None,
) -> None:
    _require_no_incomplete_workspace_transaction(root)
    allowed = allowed_codes or set()
    allowed_relatives = {value.replace("\\", "/") for value in (allowed_paths or set())}
    issues = [
        item
        for item in _mutation_consistency_issues(root, state)
        if item["code"] not in allowed and str(item.get("path", "")).replace("\\", "/") not in allowed_relatives
    ]
    if issues:
        first = issues[0]
        raise WorkspaceError(
            first["code"],
            "State-changing operation is blocked until deterministic consistency is explicitly reconciled. " + first["message"],
            first.get("path"),
        )


def command_validate(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    _require_no_incomplete_workspace_transaction(root)
    state = _load_state(root)
    structural_issues, metrics, breaches = _validate_workspace(root, state)
    artifact_audit = _artifact_snapshot(root, state, captured_at=_timestamp(None))
    artifact_issues = [
        {key: value for key, value in item.items() if key != "severity"}
        for item in artifact_audit["findings"]
        if item["severity"] == "ISSUE"
    ]
    artifact_notices = [item for item in artifact_audit["findings"] if item["severity"] != "ISSUE"]
    runtime_reference_warnings = _runtime_reference_warnings(root, state)
    runtime_reference_issues = [
        {
            "code": item["code"],
            "path": item["path"],
            "message": item["message"],
        }
        for item in runtime_reference_warnings
    ]
    current_binding_issues = _current_binding_issues(root, state)
    deterministic_issues = _deterministic_consistency_issues(root, state)
    phase_lifecycle_warnings = _phase_lifecycle_warnings(root, state)
    structural_issues = [*structural_issues, *runtime_reference_issues, *artifact_issues]
    issues = [*structural_issues, *current_binding_issues, *deterministic_issues]
    control_drift = [
        item
        for item in issues
        if item["code"]
        in {
            "WS_ACTIVE_PHASE_CONTROL_DRIFT",
            "WS_ACTIVE_PHASE_CONTROL_INVALID",
            "WS_PHASE_CONTROL_DRIFT",
            "WS_PHASE_CONTROL_INVALID",
            "WS_SESSION_CONTROL_DRIFT",
            "WS_SESSION_CONTROL_INVALID",
            "WS_ACTIVE_PHASE_CLOSURE_CONFLICT",
            "WS_PHASE_DONE_CLOSURE_INVALID",
            "WS_PHASE_SUPERSEDED_CLOSURE_INVALID",
            "WS_ROOT_PHASE_INDEX_DRIFT",
        }
    ]
    initialization_status = (
        "NEEDS_INITIAL_PHASE"
        if not state["phase_controls"]
        else "NEEDS_CONTROL_RECONCILIATION"
        if control_drift
        else "NEEDS_CONSISTENCY_RECONCILIATION"
        if current_binding_issues or deterministic_issues
        else "READY"
    )
    required_actions: list[str] = []
    if initialization_status == "NEEDS_INITIAL_PHASE":
        required_actions.append("Create the initial Phase before treating this as an initialized long-project workspace.")
    if runtime_reference_warnings:
        required_actions.append("Refresh generated PROJECT_CONTROL runtime metadata, or manually review every static generation reference outside that generated metadata.")
    required_actions.extend(item["required_action"] for item in control_drift if item.get("required_action"))
    required_actions.extend(item["required_action"] for item in artifact_issues if item.get("required_action"))
    if artifact_audit["counts"]["issues"] and not any(item.get("required_action") for item in artifact_issues):
        required_actions.append("Review and correct every Artifact ISSUE finding before relying on the enrolled contract.")
    if current_binding_issues and not any(
        "Refresh the current Phase binding" in action for action in required_actions
    ):
        required_actions.extend(item["required_action"] for item in current_binding_issues if item.get("required_action"))
    required_actions.extend(
        item["required_action"] for item in deterministic_issues
        if item.get("required_action") and item["required_action"] not in required_actions
    )
    return {
        "status": "PASS" if not issues else "FAIL",
        "operation": "validate",
        "mode": "READ_ONLY",
        "workspace": str(root),
        "writes_performed": False,
        "issues": issues,
        "structural_validation": structural_issues,
        "binding_validation": current_binding_issues,
        "deterministic_consistency_validation": deterministic_issues,
        "advisory_semantic_review": phase_lifecycle_warnings,
        "runtime_reference_warnings": runtime_reference_warnings,
        "phase_lifecycle_warnings": phase_lifecycle_warnings,
        "current_binding_warnings": [],
        "artifact_notices": artifact_notices,
        "artifact_audit": artifact_audit,
        "capacity_warnings": breaches,
        "metrics": metrics,
        "active_phase_id": state["active_phase_id"],
        "active_session_id": state["active_session_id"],
        "initialization_status": initialization_status,
        "workspace_schema_class": (
            "CURRENT_V4"
            if state["schema_version"] == 4
            else "RECONCILIATION_REQUIRED_V3"
            if state["schema_version"] == 3 and (current_binding_issues or deterministic_issues)
            else "CURRENT_V3"
            if state["schema_version"] == 3
            else "MIGRATION_REQUIRED_V2"
            if state["schema_version"] == 2 and current_binding_issues
            else "CURRENT_V2"
            if state["schema_version"] == 2
            else "LEGACY_V1"
        ),
        "required_action": " ".join(required_actions) if required_actions else None,
        "implicit_session_created": False,
    }


def _artifact_snapshot(
    root: Path,
    state: dict[str, Any],
    *,
    captured_at: str,
    candidate_roots: list[str] | None = None,
    owners: list[str] | None = None,
    scope: str = "current",
) -> dict[str, Any]:
    try:
        snapshot = audit_workspace(
            root,
            state,
            captured_at=captured_at,
            candidate_roots=candidate_roots,
            owners=owners,
            scope=scope,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise WorkspaceError("ART_AUDIT_INPUT_INVALID", str(exc)) from exc
    contract_issues = validate_instance(MALTS_ROOT, "workspace-artifact-snapshot", snapshot)
    if contract_issues:
        rendered = "; ".join(issue.render() for issue in contract_issues)
        raise WorkspaceError("ART_SNAPSHOT_CONTRACT_INVALID", rendered)
    return snapshot


def _artifact_required_action(snapshot: dict[str, Any]) -> str | None:
    actions = [
        item["required_action"]
        for item in snapshot["findings"]
        if item["severity"] == "ISSUE" and item.get("required_action")
    ]
    if snapshot["counts"]["issues"] and not actions:
        actions.append("Review and correct every Artifact ISSUE finding before relying on the enrolled contract.")
    return " ".join(dict.fromkeys(actions)) if actions else None


def command_artifact_audit(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    snapshot = _artifact_snapshot(
        root,
        state,
        captured_at=_timestamp(args.captured_at),
        candidate_roots=args.candidate_root,
        owners=args.owner,
        scope=args.scope,
    )
    return {
        "status": "PASS" if snapshot["counts"]["issues"] == 0 else "FAIL",
        "operation": "artifact-audit",
        "mode": "READ_ONLY",
        "workspace": str(root),
        "writes_performed": False,
        "snapshot": snapshot,
        "required_action": _artifact_required_action(snapshot),
        "implicit_session_created": False,
    }


def command_artifact_enrollment_preview(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    captured_at = _timestamp(args.captured_at)
    try:
        preview = enrollment_preview(
            root,
            state,
            captured_at=captured_at,
            shared_index=args.shared_index,
            archive_index=args.archive_index,
            candidate_roots=args.candidate_root,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise WorkspaceError("ART_ENROLLMENT_PREVIEW_INVALID", str(exc)) from exc
    snapshot = preview["snapshot"]
    contract_issues = validate_instance(MALTS_ROOT, "workspace-artifact-snapshot", snapshot)
    if contract_issues:
        rendered = "; ".join(issue.render() for issue in contract_issues)
        raise WorkspaceError("ART_SNAPSHOT_CONTRACT_INVALID", rendered)
    actions = list(preview["required_actions"])
    issue_action = _artifact_required_action(snapshot)
    if issue_action is not None:
        actions.insert(0, issue_action)
    return {
        "status": "PASS" if snapshot["counts"]["issues"] == 0 else "FAIL",
        "operation": "artifact-enrollment-preview",
        "mode": "READ_ONLY_PREVIEW",
        "workspace": str(root),
        "writes_performed": False,
        "snapshot": snapshot,
        "proposed_root_section": preview["proposed_root_section"],
        "planned_changes": preview["planned_changes"],
        "apply_supported": False,
        "required_actions": actions,
        "required_action": " ".join(dict.fromkeys(actions)),
        "implicit_session_created": False,
    }


def _artifact_blocked(operation: str, root: Path, error: ArtifactMutationError) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "BLOCKED",
        "operation": operation,
        "mode": "BLOCKED",
        "workspace": str(root),
        "writes_performed": False,
        "reason_code": error.code,
        "message": error.message,
        "detail": error.detail,
        "planned_changes": [],
        "payload_moves_performed": False,
        "payload_deletes_performed": False,
        "vcs_commands_performed": False,
        "implicit_session_created": False,
    }
    if error.code == "ART_ACTIVE_REFERENCE_UPDATE_REQUIRED" and isinstance(error.detail, list):
        result["stale_reference_paths"] = error.detail
    return result


def _artifact_prepare(operation: str, root: Path, planner: Any) -> dict[str, Any]:
    try:
        return planner()
    except ArtifactMutationError as exc:
        if exc.blocked:
            return _artifact_blocked(operation, root, exc)
        raise WorkspaceError(exc.code, exc.message, exc.detail) from exc


def _artifact_post_validate(root: Path, state: dict[str, Any]) -> None:
    observed_state = _load_state(root)
    if observed_state != state:
        raise TransactionError(
            "ART_TRANSACTION_STATE_DRIFT",
            "Workspace runtime state changed during the Artifact transaction.",
        )
    workspace_issues, _, _ = _validate_workspace(root, observed_state)
    if workspace_issues:
        raise TransactionError("ART_TRANSACTION_WORKSPACE_POSTVALIDATE", "Proposed Artifact state failed full workspace validation.", workspace_issues)
    snapshot = _artifact_snapshot(root, observed_state, captured_at=_timestamp(None))
    issues = [item for item in snapshot["findings"] if item["severity"] == "ISSUE"]
    if issues:
        raise TransactionError("ART_TRANSACTION_POSTVALIDATE", "Proposed Artifact state failed post-validation.", issues)


def _artifact_mutation_result(
    operation: str,
    root: Path,
    state: dict[str, Any],
    args: argparse.Namespace,
    plan: dict[str, Any],
    state_payload: bytes,
) -> dict[str, Any]:
    if plan.get("status") == "BLOCKED":
        return plan
    changes: dict[Path, bytes] = plan.pop("changes")
    preconditions: dict[Path, str | None] = plan.pop("precondition_hashes", {})
    post_state = state
    if changes and state["schema_version"] in (3, 4):
        updated_state = json.loads(json.dumps(state))
        consistency_time = _timestamp(getattr(args, "captured_at", None))
        _finalize_v3_consistency(root, updated_state, changes, consistency_time)
        post_state = updated_state
        for path in changes:
            if path not in preconditions:
                preconditions[path] = sha256_bytes(path.read_bytes()) if path.is_file() else None
    if changes:
        state_path = _state_path(root)
        state_hash = sha256_bytes(state_payload)
        if state_path in preconditions and preconditions[state_path] != state_hash:
            raise WorkspaceError(
                "ART_TRANSACTION_PRECONDITION_DRIFT",
                "Workspace runtime state changed while the mutation plan was rendered.",
                {"path": STATE_RELATIVE.as_posix(), "expected": state_hash, "observed": preconditions[state_path]},
            )
        preconditions[state_path] = state_hash
    if not set(changes).issubset(preconditions):
        raise WorkspaceError("ART_TRANSACTION_PRECONDITION_SET", "Every mutation target requires a render-time precondition.")
    ordered_paths = sorted(changes, key=lambda path: _relative(root, path))
    ordered_input_paths = sorted(preconditions, key=lambda path: _relative(root, path))
    observed_before_lock: dict[Path, str | None] = {}
    for path in ordered_input_paths:
        if path.exists() and not path.is_file():
            raise WorkspaceError(
                "ART_TRANSACTION_TARGET_TYPE",
                "Transaction inputs and targets must be absent or regular files.",
                _relative(root, path),
            )
        observed_before_lock[path] = sha256_bytes(path.read_bytes()) if path.is_file() else None
    drift = [
        {
            "path": _relative(root, path),
            "expected": preconditions[path],
            "observed": observed_before_lock[path],
        }
        for path in ordered_input_paths
        if observed_before_lock[path] != preconditions[path]
    ]
    if drift:
        raise WorkspaceError("ART_TRANSACTION_PRECONDITION_DRIFT", "Canonical input changed while the mutation plan was rendered.", drift)
    _require_consistent_mutation(root, state)
    planned_inputs = [
        {"path": _relative(root, path), "sha256": preconditions[path]}
        for path in ordered_input_paths
    ]
    planned_outputs = [
        {"path": _relative(root, path), "bytes": len(changes[path]), "sha256": sha256_bytes(changes[path])}
        for path in ordered_paths
    ]
    base: dict[str, Any] = {
        "status": "PASS",
        "operation": operation,
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "workspace": str(root),
        "planned_changes": [_relative(root, path) for path in ordered_paths],
        "precondition_hashes": planned_inputs,
        "planned_output_hashes": planned_outputs,
        "writes_performed": False,
        "idempotent": bool(plan.get("idempotent", False)),
        "transaction": None,
        "transaction_control_paths": [
            "runtime/artifact_transaction.lock.json",
            f"runtime/artifact_transactions/{args.operation_id}.json",
        ] if changes else [],
        "payload_moves_performed": False,
        "payload_deletes_performed": False,
        "vcs_commands_performed": False,
        "implicit_session_created": False,
    }
    base.update({key: value for key, value in plan.items() if key != "idempotent"})
    if not args.apply or not changes:
        return base
    try:
        transaction = execute_transaction(
            root,
            operation_id=args.operation_id,
            operation=operation,
            changes=changes,
            expected_input_hashes=preconditions,
            post_validate=lambda: _artifact_post_validate(root, post_state),
        )
    except TransactionError as exc:
        raise WorkspaceError(exc.code, exc.message, exc.detail) from exc
    base["transaction"] = transaction
    base["writes_performed"] = bool(transaction["writes_performed"])
    base["idempotent"] = bool(transaction["idempotent"])
    return base


def command_artifact_enrollment_apply(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state, state_payload = _load_state_capture(root)
    plan = _artifact_prepare(
        "artifact-enrollment-apply",
        root,
        lambda: plan_enrollment_apply(
            root,
            state,
            captured_at=_timestamp(args.captured_at),
            shared_index=args.shared_index,
            archive_index=args.archive_index,
        ),
    )
    return _artifact_mutation_result("artifact-enrollment-apply", root, state, args, plan, state_payload)


def command_artifact_register(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state, state_payload = _load_state_capture(root)
    plan = _artifact_prepare(
        "artifact-register",
        root,
        lambda: plan_register(
            root,
            state,
            owner_ref=args.owner,
            artifact_id=args.artifact_id,
            role=args.role,
            locator=args.locator,
            authority=args.authority,
            vcs=args.vcs,
            verification=args.verification,
            retention=args.retention,
            disposition=args.disposition,
            relationships=args.relationships,
            role_contract=args.role_contract,
            purpose=args.purpose,
            applies_to=args.applies_to,
            source=args.source,
            maintainer=args.maintainer,
            last_verified=args.last_verified,
            shared_status=args.shared_status,
            original_owner=args.original_owner,
            archived_at=args.archived_at,
            archive_reason=args.archive_reason,
            successor=args.successor,
            manifest=args.manifest,
        ),
    )
    return _artifact_mutation_result("artifact-register", root, state, args, plan, state_payload)


def command_artifact_promote(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state, state_payload = _load_state_capture(root)
    plan = _artifact_prepare(
        "artifact-promote",
        root,
        lambda: plan_promote(
            root,
            state,
            source_ref=args.source,
            shared_id=args.shared_id,
            purpose=args.purpose,
            applies_to=args.applies_to,
            maintainer=args.maintainer,
            retention=args.retention,
            last_verified=_timestamp(args.last_verified),
        ),
    )
    return _artifact_mutation_result("artifact-promote", root, state, args, plan, state_payload)


def command_artifact_supersede(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state, state_payload = _load_state_capture(root)
    plan = _artifact_prepare(
        "artifact-supersede",
        root,
        lambda: plan_supersede(
            root,
            state,
            old_ref=args.old,
            new_ref=args.new,
            update_reference_paths=args.update_reference,
            captured_at=_timestamp(args.captured_at),
        ),
    )
    return _artifact_mutation_result("artifact-supersede", root, state, args, plan, state_payload)


def _disposition_map(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise WorkspaceError("ART_RECONCILE_DECISION_INVALID", "Disposition must use ART-001=KEEP_OWNED form.", value)
        artifact_id, disposition = (item.strip() for item in value.split("=", 1))
        if not artifact_id or not disposition or artifact_id in result:
            raise WorkspaceError("ART_RECONCILE_DECISION_INVALID", "Disposition decisions must be non-empty and unique.", value)
        result[artifact_id] = disposition
    return result


def command_artifact_reconcile(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state, state_payload = _load_state_capture(root)
    decisions = _disposition_map(args.disposition)
    plan = _artifact_prepare(
        "artifact-reconcile",
        root,
        lambda: plan_reconcile(root, state, owner_ref=args.owner, decisions=decisions),
    )
    return _artifact_mutation_result("artifact-reconcile", root, state, args, plan, state_payload)


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
        if not _path_is_file(plan_path):
            issue("WS_ACTIVE_PLAN_MISSING", plan_relative, "The Phase-owned active plan file is missing.")
        else:
            observed_sha256 = hashlib.sha256(_path_read_bytes(plan_path)).hexdigest().upper()
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
    _require_consistent_mutation(root, state)
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
    if changed and state["schema_version"] == 3 and state["recovery_binding"]["source_control_path"] == "PROJECT_CONTROL.md":
        updated = json.loads(json.dumps(state))
        _finalize_v3_consistency(root, updated, changes, _timestamp(args.timestamp))
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
        _transaction_write(root, changes, operation="refresh-runtime-references")
    return result


def command_maintain(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    _require_consistent_mutation(root, state)
    issues, metrics, _ = _validate_workspace(root, state)
    if issues:
        raise WorkspaceError("WS_VALIDATION_FAILED", "Workspace validation must pass before maintenance.")
    maintenance_state, breaches = _budget_assessment(metrics, state["capacity_budget"])
    now = _timestamp(args.timestamp)
    artifact_audit = _artifact_snapshot(root, state, captured_at=now)
    if artifact_audit["counts"]["issues"]:
        raise WorkspaceError(
            "ART_VALIDATION_FAILED",
            _artifact_required_action(artifact_audit) or "Artifact audit contains unresolved ISSUE findings.",
        )
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
        phase_lifecycle_warnings=_phase_lifecycle_warnings(root, state),
        current_binding_warnings=_current_binding_issues(root, state),
        artifact_audit=artifact_audit,
        semantic_judgment_performed=False,
        implicit_session_created=False,
    )
    if args.apply:
        _transaction_write(root, changes, operation="maintain")
    return result


def command_compact(args: argparse.Namespace) -> dict[str, Any]:
    root = _workspace(args.workspace)
    state = _load_state(root)
    _require_consistent_mutation(root, state)
    now = _timestamp(args.timestamp)
    project_path = _target(root, "PROJECT_CONTROL.md")
    project_data = _read_bytes(root, "PROJECT_CONTROL.md")
    text, bom = _decode_markdown(project_data)
    blocks = _history_blocks(text)
    if not blocks:
        return _plan("compact", root, (), args.apply, compacted_blocks=0, artifact_refs_preserved=[], implicit_session_created=False)

    archive_relative = "history/PROJECT_CONTROL_HISTORY.md"
    archive_path = _target(root, archive_relative)
    if archive_path.exists() and not archive_path.is_file():
        raise WorkspaceError("WS_PATH_TYPE", "History archive path is not a file.", archive_relative)
    archive_data = archive_path.read_bytes() if archive_path.is_file() else b"# PROJECT_CONTROL History\n\n"
    archive_text, archive_bom = _decode_markdown(archive_data)
    for history_id, _, _, _ in blocks:
        if re.search(rf"(?m)^## {re.escape(history_id)}$", archive_text):
            raise WorkspaceError("WS_HISTORY_DUPLICATE", "History archive already contains this ID.", history_id)

    artifact_refs_by_history = {
        history_id: artifact_references_in_text(block)
        for history_id, _, _, block in blocks
    }
    artifact_refs_preserved = sorted({reference for references in artifact_refs_by_history.values() for reference in references})
    compacted = text
    for history_id, start, end, block in reversed(blocks):
        marker = f"<!-- MALTS:history:archived id={history_id} path={archive_relative} -->"
        pointer_markers = [
            f"<!-- MALTS:artifact-history-ref ref={reference} path={archive_relative}#{history_id} -->"
            for reference in artifact_refs_by_history[history_id]
        ]
        if pointer_markers:
            marker += "\n" + "\n".join(pointer_markers)
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
    _finalize_v3_consistency(root, updated, changes, now)
    _validate_state(root, updated)
    result = _plan(
        "compact",
        root,
        changes,
        args.apply,
        compacted_blocks=len(blocks),
        history_ids=[item[0] for item in blocks],
        protected_sections_moved=False,
        artifact_refs_preserved=artifact_refs_preserved,
        implicit_session_created=False,
    )
    if args.apply:
        must_be_new = (archive_path,) if not archive_path.exists() else ()
        _transaction_write(root, changes, must_be_new=must_be_new, operation="compact")
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
    _require_no_incomplete_workspace_transaction(root)
    state = _load_state(root)
    artifact_transaction_recovery = inspect_transaction_state(root)
    workspace_transaction_recovery = inspect_transaction_state(root, WORKSPACE_TRANSACTION_PROFILE)
    transaction_recovery = {
        "status": "PASS" if artifact_transaction_recovery["status"] == "PASS" and workspace_transaction_recovery["status"] == "PASS" else "REVIEW_REQUIRED",
        "required_actions": [
            *artifact_transaction_recovery["required_actions"],
            *workspace_transaction_recovery["required_actions"],
        ],
        "artifact": artifact_transaction_recovery,
        "workspace_control": workspace_transaction_recovery,
        "writes_performed": False,
        "recursive_scan_performed": False,
    }
    validation_issues, _, _ = _validate_workspace(root, state)
    artifact_audit = _artifact_snapshot(root, state, captured_at=_timestamp(None))
    artifact_issues = [item for item in artifact_audit["findings"] if item["severity"] == "ISSUE"]
    phase_lifecycle_warnings = _phase_lifecycle_warnings(root, state)
    current_binding_issues = _current_binding_issues(root, state)
    deterministic_issues = _deterministic_consistency_issues(root, state)
    validation_issues = [*validation_issues, *current_binding_issues, *deterministic_issues]
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
    if state["schema_version"] in {3, 4} and isinstance(state.get("recovery_binding"), dict):
        add(_target(root, state["recovery_binding"]["source_control_path"]))
    for item in artifact_audit["input_hashes"]:
        if item["kind"] in {"CANONICAL_SHARED_INDEX", "CANONICAL_ARCHIVE_INDEX"}:
            add(_target(root, item["path"]))
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
        if item["code"]
        in {
            "WS_ACTIVE_PHASE_CONTROL_DRIFT",
            "WS_ACTIVE_PHASE_CONTROL_INVALID",
            "WS_PHASE_CONTROL_DRIFT",
            "WS_PHASE_CONTROL_INVALID",
            "WS_SESSION_CONTROL_DRIFT",
            "WS_SESSION_CONTROL_INVALID",
            "WS_ACTIVE_PHASE_CLOSURE_CONFLICT",
            "WS_PHASE_DONE_CLOSURE_INVALID",
            "WS_PHASE_SUPERSEDED_CLOSURE_INVALID",
            "WS_ROOT_PHASE_INDEX_DRIFT",
        }
    ]
    initialization_status = (
        "NEEDS_INITIAL_PHASE"
        if not state["phase_controls"]
        else "NEEDS_CONTROL_RECONCILIATION"
        if control_drift
        else "NEEDS_CONSISTENCY_RECONCILIATION"
        if current_binding_issues or deterministic_issues
        else "READY"
    )
    required_actions = [item["required_action"] for item in control_drift if item.get("required_action")]
    if initialization_status == "NEEDS_INITIAL_PHASE":
        required_actions.append("Run init with --initial-phase-id and --initial-phase-goal, or explicitly open the first Phase.")
    required_actions.extend(item["required_action"] for item in artifact_issues if item.get("required_action"))
    if artifact_issues and not any(item.get("required_action") for item in artifact_issues):
        required_actions.append("Review and correct every Artifact ISSUE finding before relying on the enrolled contract.")
    required_actions.extend(transaction_recovery["required_actions"])
    required_actions.extend(item["required_action"] for item in current_binding_issues if item.get("required_action"))
    required_actions.extend(
        item["required_action"] for item in deterministic_issues
        if item.get("required_action") and item["required_action"] not in required_actions
    )
    if state["schema_version"] in {3, 4} and isinstance(state.get("recovery_binding"), dict):
        recovery = state["recovery_binding"]
        recovery_source = {
            "kind": recovery["source_kind"],
            "phase_id": recovery["source_phase_id"],
            "session_id": recovery["source_session_id"],
            "path": recovery["source_control_path"],
            "record_id": recovery["record_id"],
            "source_control_sha256": recovery["source_control_sha256"],
            "source_recovery_sha256": recovery["source_recovery_sha256"],
        }
    elif state["active_session_id"] is not None:
        active_session = _active_session(state)
        recovery_source = {
            "kind": "ACTIVE_SESSION_CHECKPOINT",
            "phase_id": active_session["phase_id"],
            "session_id": active_session["session_id"],
            "path": active_session["path"],
        }
    elif state["active_phase_id"] is not None:
        active_phase = _active_phase(state)
        recovery_source = {
            "kind": "ACTIVE_PHASE_RECOVERY",
            "phase_id": active_phase["phase_id"],
            "session_id": None,
            "path": active_phase["path"],
        }
    else:
        recovery_source = {
            "kind": "PROJECT_RECOVERY",
            "phase_id": None,
            "session_id": None,
            "path": "PROJECT_CONTROL.md",
        }
    return {
        "status": "PASS" if initialization_status == "READY" and not validation_issues and not artifact_issues and transaction_recovery["status"] == "PASS" else "FAIL",
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
        "recovery_source": recovery_source,
        "runtime_is_canonical": False,
        "summary_replaces_current_facts": False,
        "phase_lifecycle_warnings": phase_lifecycle_warnings,
        "current_binding_warnings": [],
        "binding_validation": current_binding_issues,
        "deterministic_consistency_validation": deterministic_issues,
        "artifact_audit": artifact_audit,
        "transaction_recovery": transaction_recovery,
        "semantic_judgment_performed": False,
        "implicit_session_created": False,
    }


def _add_common_write_arguments(parser: argparse.ArgumentParser, *, language: bool = False) -> None:
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--apply", action="store_true", help="Apply the planned state changes; default is dry-run.")
    parser.add_argument("--timestamp", help="Optional deterministic ISO 8601 timestamp for tests/evidence.")
    if language:
        parser.add_argument("--language", choices=("auto", "en", "zh-CN"), default="auto")


def _add_phase_boundary_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--milestone")
    parser.add_argument("--in-scope")
    parser.add_argument("--out-of-scope")
    parser.add_argument("--exit-criteria")
    parser.add_argument("--carry-over-policy")
    parser.add_argument("--boundary-review-triggers")


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
    _add_phase_boundary_arguments(init)
    init.set_defaults(handler=command_init)

    open_phase = subparsers.add_parser("open-phase")
    _add_common_write_arguments(open_phase, language=True)
    open_phase.add_argument("--phase-id", required=True)
    open_phase.add_argument("--goal", required=True)
    _add_phase_boundary_arguments(open_phase)
    open_phase.set_defaults(handler=command_open_phase)

    close_phase = subparsers.add_parser("close-phase")
    _add_common_write_arguments(close_phase)
    close_phase.add_argument("--status", choices=("DONE", "BLOCKED", "FAILED"), required=True)
    close_phase.add_argument("--exit-criteria-status", choices=("SATISFIED", "NOT_SATISFIED", "NOT_APPLICABLE"))
    close_phase.add_argument("--carry-over-disposition", default="N/A")
    close_phase.add_argument("--closure-evidence")
    close_phase.add_argument("--next-action", default="Open the next Phase when authorized.")
    close_phase.set_defaults(handler=command_close_phase)

    phase_review = subparsers.add_parser("phase-boundary-review")
    phase_review.add_argument("--workspace", required=True)
    phase_review.add_argument("--phase-id")
    phase_review.add_argument("--candidate-goal")
    phase_review.add_argument("--candidate-touch-set", action="append", default=[])
    phase_review.add_argument("--candidate-mapping", choices=tuple(sorted(CANDIDATE_MAPPINGS)), default="UNCLEAR")
    phase_review.add_argument("--recommendation", choices=tuple(sorted(PHASE_REVIEW_RESULTS)))
    phase_review.set_defaults(handler=command_phase_boundary_review)

    migrate_phase = subparsers.add_parser("migrate-phase-control")
    _add_common_write_arguments(migrate_phase, language=True)
    migrate_phase.add_argument("--phase-id", required=True)
    _add_phase_boundary_arguments(migrate_phase)
    migrate_phase.add_argument("--plan-trigger", choices=tuple(sorted(PLAN_RECHECK_TRIGGERS)))
    migrate_phase.add_argument("--plan-result", choices=tuple(sorted(PLAN_RECHECK_RESULTS)))
    migrate_phase.add_argument("--plan-reviewed-at")
    migrate_phase.set_defaults(handler=command_migrate_phase_control)

    migrate_consistency = subparsers.add_parser("migrate-consistency-records")
    _add_common_write_arguments(migrate_consistency)
    migrate_consistency.add_argument("--authority", choices=("workspace-state",), required=True)
    migrate_consistency.add_argument("--expected-state-sha256", required=True)
    migrate_consistency.add_argument("--operation-id", required=True)
    migrate_consistency.set_defaults(handler=command_migrate_consistency_records)

    record_review = subparsers.add_parser("record-phase-boundary-review")
    _add_common_write_arguments(record_review)
    record_review.add_argument("--phase-id")
    record_review.add_argument("--review-id", required=True)
    record_review.add_argument("--candidate-mapping", choices=tuple(sorted(CANDIDATE_MAPPINGS)), required=True)
    record_review.add_argument("--recommendation", choices=tuple(sorted(PHASE_REVIEW_RESULTS)), required=True)
    record_review.add_argument("--evidence-ref", required=True)
    record_review.add_argument("--authorization-ref", default="N/A")
    record_review.add_argument("--expected-phase-sha256", required=True)
    record_review.add_argument("--operation-id", required=True)
    record_review.set_defaults(handler=command_record_phase_boundary_review)

    reconcile_consistency = subparsers.add_parser("reconcile-consistency-records")
    _add_common_write_arguments(reconcile_consistency)
    reconcile_consistency.add_argument("--authority", choices=("canonical-controls",), required=True)
    reconcile_consistency.add_argument("--expected-state-sha256", required=True)
    reconcile_consistency.add_argument("--expected-source-sha256", required=True)
    reconcile_consistency.add_argument("--expected-phase-sha256", required=True)
    reconcile_consistency.add_argument("--operation-id", required=True)
    reconcile_consistency.set_defaults(handler=command_reconcile_consistency_records)

    rebind_v4 = subparsers.add_parser("rebind-v4-consistency", help="Explicitly rebind derived v4 controls after reviewed canonical edits.")
    _add_common_write_arguments(rebind_v4)
    rebind_v4.add_argument("--expected-state-sha256", required=True)
    rebind_v4.add_argument("--expected-phase-sha256", required=True)
    rebind_v4.add_argument("--operation-id", required=True)
    rebind_v4.set_defaults(handler=command_rebind_v4_consistency)

    recover_workspace_transaction = subparsers.add_parser("recover-workspace-transaction")
    recover_workspace_transaction.add_argument("--workspace", required=True)
    recover_workspace_transaction.add_argument("--operation-id", required=True)
    recover_workspace_transaction.add_argument("--expected-journal-sha256")
    recover_workspace_transaction.add_argument("--expected-lock-sha256")
    recover_workspace_transaction.add_argument("--apply", action="store_true")
    recover_workspace_transaction.set_defaults(handler=command_recover_workspace_transaction)

    pause_phase = subparsers.add_parser("pause-phase")
    _add_common_write_arguments(pause_phase)
    pause_phase.add_argument("--reason", required=True)
    pause_phase.add_argument("--boundary-review-ref", required=True)
    pause_phase.add_argument("--authorization-ref", required=True)
    pause_phase.set_defaults(handler=command_pause_phase)

    resume_phase = subparsers.add_parser("resume-phase")
    _add_common_write_arguments(resume_phase)
    resume_phase.add_argument("--phase-id", required=True)
    resume_phase.add_argument("--boundary-review-ref", required=True)
    resume_phase.add_argument("--plan-review-ref", required=True)
    resume_phase.add_argument("--expected-plan-sha256", required=True)
    resume_phase.add_argument("--authorization-ref", required=True)
    resume_phase.set_defaults(handler=command_resume_phase)

    plan_transition = subparsers.add_parser("plan-phase-transition")
    _add_common_write_arguments(plan_transition)
    plan_transition.add_argument("--source-phase-id", required=True)
    plan_transition.add_argument("--target-phase-id", required=True)
    plan_transition.add_argument("--target-goal", required=True)
    _add_phase_boundary_arguments(plan_transition)
    plan_transition.add_argument("--carry-over-file", required=True)
    plan_transition.add_argument("--disposition-file", required=True)
    plan_transition.add_argument("--boundary-review-ref", required=True)
    plan_transition.add_argument("--authorization-ref", required=True)
    plan_transition.add_argument("--plan-out", required=True)
    plan_transition.set_defaults(handler=command_plan_phase_transition)

    apply_transition = subparsers.add_parser("apply-phase-transition")
    _add_common_write_arguments(apply_transition, language=True)
    apply_transition.add_argument("--plan", required=True)
    apply_transition.add_argument("--expected-plan-sha256", required=True)
    apply_transition.set_defaults(handler=command_apply_phase_transition)

    open_session = subparsers.add_parser("open-session")
    _add_common_write_arguments(open_session, language=True)
    open_session.add_argument("--session-id", required=True)
    open_session.add_argument("--goal", required=True)
    open_session.add_argument("--reason", choices=("bounded-work-session", "recovery", "manual-checkpoint"), default="bounded-work-session")
    open_session.add_argument("--owner-kind", choices=("MAIN_CONTROLLER", "DELEGATED_AGENT"), default="MAIN_CONTROLLER")
    open_session.add_argument("--owner-id", default="MAIN_CONTROLLER")
    open_session.add_argument("--lease-id", default="LEASE-001")
    open_session.add_argument("--authorization-ref", default="explicit-open-session")
    open_session.add_argument("--expires-at")
    open_session.add_argument("--allowed-operation", action="append", default=["record-result-events"])
    open_session.add_argument("--read-scope", action="append", default=[])
    open_session.add_argument("--write-scope", action="append", default=["task-state", "phases", "sessions", "runtime"])
    open_session.add_argument("--touch-set", action="append", default=["runtime/workspace_control.json"])
    open_session.add_argument("--excluded-surface", action="append", default=[])
    open_session.add_argument("--bound-lineage-id", action="append", default=[])
    open_session.add_argument("--evidence-ref", action="append", default=["session:explicit-open"])
    open_session.set_defaults(handler=command_open_session)

    close_session = subparsers.add_parser("close-session")
    _add_common_write_arguments(close_session)
    close_session.add_argument("--status", choices=("DONE", "BLOCKED", "FAILED"), required=True)
    close_session.add_argument("--next-action", required=True)
    close_session.set_defaults(handler=command_close_session)

    record_events = subparsers.add_parser("record-result-events", help="Dry-run/apply one typed Result v2 event batch and all governed bindings.")
    _add_common_write_arguments(record_events)
    record_events.add_argument("--contract", required=True, help="Workspace-relative immutable Result Contract v2 path.")
    record_events.add_argument("--events", required=True, type=Path, help="JSON file containing the non-empty event batch.")
    record_events.add_argument("--expected-contract-sha256")
    record_events.add_argument("--expected-projection-sha256")
    record_events.add_argument("--expected-plan-sha256")
    record_events.add_argument("--actor-kind", choices=("MAIN_CONTROLLER", "DELEGATED_AGENT"), default="MAIN_CONTROLLER")
    record_events.add_argument("--actor-id", default="MAIN_CONTROLLER")
    record_events.set_defaults(handler=command_record_result_events)

    rebuild_lineage = subparsers.add_parser("rebuild-result-lineage", help="Rebuild one declared Result v2 projection from its immutable chain.")
    _add_common_write_arguments(rebuild_lineage)
    rebuild_lineage.add_argument("--contract", required=True)
    rebuild_lineage.add_argument("--operation-id", required=True)
    rebuild_lineage.add_argument("--expected-contract-sha256")
    rebuild_lineage.add_argument("--expected-projection-sha256")
    rebuild_lineage.add_argument("--expected-plan-sha256")
    rebuild_lineage.add_argument("--actor-kind", choices=("MAIN_CONTROLLER", "DELEGATED_AGENT"), default="MAIN_CONTROLLER")
    rebuild_lineage.add_argument("--actor-id", default="MAIN_CONTROLLER")
    rebuild_lineage.set_defaults(handler=command_rebuild_result_lineage)

    def add_amendment_arguments(amendment: argparse.ArgumentParser, *, include_apply: bool) -> None:
        if include_apply:
            _add_common_write_arguments(amendment)
        else:
            amendment.add_argument("--workspace", required=True)
            amendment.add_argument("--timestamp")
        _add_phase_boundary_arguments(amendment)
        amendment.add_argument("--operation-id", required=True)
        amendment.add_argument("--revision-id", required=True)
        amendment.add_argument("--review-id", required=True)
        amendment.add_argument("--review-evidence-ref", action="append", required=True)
        amendment.add_argument("--authorization-ref", required=True)
        amendment.add_argument("--accepted-at", required=True)
        amendment.add_argument("--expected-phase-sha256")
        amendment.add_argument("--expected-boundary-sha256")
        amendment.add_argument("--expected-plan-sha256")
        amendment.add_argument("--actor-kind", choices=("MAIN_CONTROLLER", "DELEGATED_AGENT"), default="MAIN_CONTROLLER")
        amendment.add_argument("--actor-id", default="MAIN_CONTROLLER")

    plan_amendment = subparsers.add_parser("plan-phase-boundary-amendment", help="Preview an immutable Phase boundary revision.")
    add_amendment_arguments(plan_amendment, include_apply=False)
    plan_amendment.set_defaults(handler=command_plan_phase_boundary_amendment, apply=False)

    apply_amendment = subparsers.add_parser("apply-phase-boundary-amendment", help="Dry-run/apply one exact reviewed Phase boundary revision.")
    add_amendment_arguments(apply_amendment, include_apply=True)
    apply_amendment.set_defaults(handler=command_apply_phase_boundary_amendment)

    transfer_lease = subparsers.add_parser("transfer-session-lease", help="Dry-run/apply one exact structured Session lease transfer.")
    _add_common_write_arguments(transfer_lease)
    transfer_lease.add_argument("--operation-id", required=True)
    transfer_lease.add_argument("--expected-session-sha256", required=True)
    transfer_lease.add_argument("--expected-plan-sha256")
    transfer_lease.add_argument("--actor-kind", choices=("MAIN_CONTROLLER", "DELEGATED_AGENT"), required=True)
    transfer_lease.add_argument("--actor-id", required=True)
    transfer_lease.add_argument("--new-owner-kind", choices=("MAIN_CONTROLLER", "DELEGATED_AGENT"), required=True)
    transfer_lease.add_argument("--new-owner-id", required=True)
    transfer_lease.add_argument("--new-lease-id", required=True)
    transfer_lease.add_argument("--authorization-ref", required=True)
    transfer_lease.add_argument("--expires-at")
    transfer_lease.add_argument("--evidence-ref", action="append", required=True)
    transfer_lease.set_defaults(handler=command_transfer_session_lease)

    migrate_workspace = subparsers.add_parser("migrate-workspace-v3-to-v4", help="Dry-run/apply one explicit cold workspace v3-to-v4 migration.")
    _add_common_write_arguments(migrate_workspace)
    migrate_workspace.add_argument("--operation-id", required=True)
    migrate_workspace.add_argument("--expected-state-sha256", required=True)
    migrate_workspace.add_argument("--paused-phase-id")
    migrate_workspace.add_argument("--expected-phase-sha256")
    migrate_workspace.add_argument("--expected-boundary-sha256")
    migrate_workspace.add_argument("--expected-paused-plan-sha256")
    migrate_workspace.add_argument("--expected-plan-sha256")
    migrate_workspace.add_argument("--expected-recovery-sha256")
    migrate_workspace.add_argument("--pause-review-ref")
    migrate_workspace.add_argument("--pause-authorization-ref")
    migrate_workspace.add_argument("--declared-lineage", action="append")
    migrate_workspace.set_defaults(handler=command_migrate_workspace_v3_to_v4)

    migrate_result = subparsers.add_parser("migrate-result-contract-v1-to-v2", help="Dry-run/apply one declared Result Contract v1-to-v2 migration.")
    _add_common_write_arguments(migrate_result)
    migrate_result.add_argument("--contract", required=True)
    migrate_result.add_argument("--expected-contract-sha256", required=True)
    migrate_result.add_argument("--task-id", required=True)
    migrate_result.add_argument("--lineage-id", required=True)
    migrate_result.add_argument("--phase-id", required=True)
    migrate_result.add_argument("--expected-phase-boundary-sha256", required=True)
    migrate_result.add_argument("--operation-id", required=True)
    migrate_result.add_argument("--revision-id")
    migrate_result.add_argument("--event-id")
    migrate_result.add_argument("--review-ref", required=True)
    migrate_result.add_argument("--authorization-ref", required=True)
    migrate_result.add_argument("--expected-plan-sha256")
    migrate_result.set_defaults(handler=command_migrate_result_contract_v1_to_v2)

    scoped_readiness = subparsers.add_parser("scoped-readiness", help="Read-only Fast Path route probe; advises only and never authorizes or writes.")
    scoped_readiness.add_argument("--workspace", required=True)
    scoped_readiness.add_argument("--subject")
    scoped_readiness.add_argument("--durable-delta", choices=("NONE", "DURABLE", "UNKNOWN"), default="UNKNOWN")
    scoped_readiness.set_defaults(handler=command_scoped_readiness)

    refresh_instructions = subparsers.add_parser("refresh-project-instructions", help="Dry-run/apply exact project-owned managed instruction blocks.")
    _add_common_write_arguments(refresh_instructions)
    refresh_instructions.add_argument("--operation-id", required=True)
    refresh_instructions.add_argument("--target", action="append", required=True, help="RELATIVE=SHA256 for AGENTS.md or CLAUDE.md; repeatable.")
    refresh_instructions.add_argument("--block", action="append", required=True, help="MARKER_ID=SOURCE_PATH=SHA256; repeatable.")
    refresh_instructions.add_argument("--expected-plan-sha256")
    refresh_instructions.set_defaults(handler=command_refresh_project_instructions)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--workspace", required=True)
    validate.set_defaults(handler=command_validate)

    artifact = subparsers.add_parser("artifact")
    artifact_operations = artifact.add_subparsers(dest="artifact_operation", required=True)

    artifact_audit = artifact_operations.add_parser("audit")
    artifact_audit.add_argument("--workspace", required=True)
    artifact_audit.add_argument("--captured-at")
    artifact_audit.add_argument("--scope", choices=("current",), default="current")
    artifact_audit.add_argument("--owner", action="append", default=[])
    artifact_audit.add_argument("--candidate-root", action="append", default=[])
    artifact_audit.set_defaults(handler=command_artifact_audit)

    artifact_preview = artifact_operations.add_parser("enrollment-preview")
    artifact_preview.add_argument("--workspace", required=True)
    artifact_preview.add_argument("--captured-at")
    artifact_preview.add_argument("--shared-index", default="N/A")
    artifact_preview.add_argument("--archive-index", default="N/A")
    artifact_preview.add_argument("--candidate-root", action="append", default=[])
    artifact_preview.set_defaults(handler=command_artifact_enrollment_preview)

    artifact_enrollment_apply = artifact_operations.add_parser("enrollment-apply")
    artifact_enrollment_apply.add_argument("--workspace", required=True)
    artifact_enrollment_apply.add_argument("--operation-id", required=True)
    artifact_enrollment_apply.add_argument("--captured-at")
    artifact_enrollment_apply.add_argument("--shared-index", default="N/A")
    artifact_enrollment_apply.add_argument("--archive-index", default="N/A")
    artifact_enrollment_apply.add_argument("--apply", action="store_true")
    artifact_enrollment_apply.set_defaults(handler=command_artifact_enrollment_apply)

    artifact_register = artifact_operations.add_parser("register")
    artifact_register.add_argument("--workspace", required=True)
    artifact_register.add_argument("--owner", required=True)
    artifact_register.add_argument("--artifact-id", required=True)
    artifact_register.add_argument("--role", choices=tuple(sorted({"WORKING", "DELIVERABLE", "EVIDENCE", "RECOVERY"})), required=True)
    artifact_register.add_argument("--locator", required=True)
    artifact_register.add_argument("--authority", choices=tuple(sorted({"WORKSPACE", "SOURCE_PROJECT", "EXTERNAL", "GENERATED"})), required=True)
    artifact_register.add_argument("--vcs", choices=tuple(sorted({"LOCAL_ONLY", "GIT_TRACKED", "SVN_TRACKED", "UNTRACKED", "EXTERNAL", "UNKNOWN"})), required=True)
    artifact_register.add_argument("--verification", required=True)
    artifact_register.add_argument("--retention", required=True)
    artifact_register.add_argument("--disposition", choices=tuple(sorted({"KEEP_OWNED", "PROMOTE_SHARED", "ARCHIVE", "RUNTIME_RECREATABLE", "SUPERSEDED", "UNRESOLVED"})), required=True)
    artifact_register.add_argument("--relationships", default="N/A")
    artifact_register.add_argument("--role-contract", default="N/A")
    artifact_register.add_argument("--purpose")
    artifact_register.add_argument("--applies-to")
    artifact_register.add_argument("--source")
    artifact_register.add_argument("--maintainer")
    artifact_register.add_argument("--last-verified")
    artifact_register.add_argument("--shared-status", choices=("CURRENT", "SUPERSEDED"), default="CURRENT")
    artifact_register.add_argument("--original-owner")
    artifact_register.add_argument("--archived-at")
    artifact_register.add_argument("--archive-reason")
    artifact_register.add_argument("--successor", default="N/A")
    artifact_register.add_argument("--manifest", default="N/A")
    artifact_register.add_argument("--operation-id", required=True)
    artifact_register.add_argument("--apply", action="store_true")
    artifact_register.set_defaults(handler=command_artifact_register)

    artifact_promote = artifact_operations.add_parser("promote")
    artifact_promote.add_argument("--workspace", required=True)
    artifact_promote.add_argument("--source", required=True)
    artifact_promote.add_argument("--shared-id", required=True)
    artifact_promote.add_argument("--purpose", required=True)
    artifact_promote.add_argument("--applies-to", required=True)
    artifact_promote.add_argument("--maintainer", required=True)
    artifact_promote.add_argument("--retention", required=True)
    artifact_promote.add_argument("--last-verified", required=True)
    artifact_promote.add_argument("--operation-id", required=True)
    artifact_promote.add_argument("--apply", action="store_true")
    artifact_promote.set_defaults(handler=command_artifact_promote)

    artifact_supersede = artifact_operations.add_parser("supersede")
    artifact_supersede.add_argument("--workspace", required=True)
    artifact_supersede.add_argument("--old", required=True)
    artifact_supersede.add_argument("--new", required=True)
    artifact_supersede.add_argument("--update-reference", action="append", default=[])
    artifact_supersede.add_argument("--captured-at")
    artifact_supersede.add_argument("--operation-id", required=True)
    artifact_supersede.add_argument("--apply", action="store_true")
    artifact_supersede.set_defaults(handler=command_artifact_supersede)

    artifact_reconcile = artifact_operations.add_parser("reconcile")
    artifact_reconcile.add_argument("--workspace", required=True)
    artifact_reconcile.add_argument("--owner", required=True)
    artifact_reconcile.add_argument("--disposition", action="append", default=[])
    artifact_reconcile.add_argument("--operation-id", required=True)
    artifact_reconcile.add_argument("--apply", action="store_true")
    artifact_reconcile.set_defaults(handler=command_artifact_reconcile)

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
