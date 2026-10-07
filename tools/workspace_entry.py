#!/usr/bin/env python3
"""Bounded, read-only daily entry for initialized MALTS long workspaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.dont_write_bytecode = True

from malts_user_contracts import validate_instance
import workspace_coordination as coordination_runtime


TOOLS_ROOT = Path(__file__).resolve().parent
MALTS_ROOT = TOOLS_ROOT.parent
STATE_RELATIVE = "runtime/workspace_control.json"
COORDINATION_RELATIVE = "runtime/workspace_coordination.json"
CURRENT_WORKSPACE_CONTRACT = "malts.workspace.current"
CURRENT_PROFILES = {"single_phase", "resource_admission"}
LEGACY_PROFILE_MAP = {
    "single_phase_v1": "single_phase",
    "resource_admission_v1": "resource_admission",
}
WRITE_TASK_CLASSES = {"LOW_RISK", "WRITE_EXISTING_SCOPE", "NEW_WRITE_SCOPE", "HIGH_RISK"}
TASK_CLASSES = {"READ_ONLY", *WRITE_TASK_CLASSES, "CONTEXT_RECOVERY"}
GATE_ORDER = (
    "FULL_VALIDATE",
    "FULL_RECOVER",
    "PLAN_RECHECK",
    "PHASE_BOUNDARY_REVIEW",
    "PHASE_SWITCH_REVIEW",
    "RESOURCE_ADMISSION",
)
SECTION_LINE = re.compile(
    r"^[ \t]*<!-- MALTS:section=(?P<name>[a-z0-9-]+) -->[ \t]*\r?$",
    re.IGNORECASE | re.MULTILINE,
)


class EntryError(RuntimeError):
    def __init__(self, code: str, message: str, path: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path


def _timestamp(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise EntryError("ENTRY_TIMESTAMP_INVALID", "evaluated-at must be ISO 8601.") from exc
    if parsed.tzinfo is None:
        raise EntryError("ENTRY_TIMESTAMP_INVALID", "evaluated-at requires an explicit timezone.")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


@dataclass
class BoundedReader:
    root: Path
    max_files: int = 8
    max_bytes: int = 131072

    def __post_init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self._payloads: dict[str, bytes] = {}
        self._considered: dict[str, int] = {}
        self.budget_exceeded = False

    @property
    def bytes_read(self) -> int:
        return sum(row["bytes"] for row in self.rows)

    @property
    def files_considered(self) -> int:
        return len(self._considered)

    @property
    def bytes_considered(self) -> int:
        return sum(self._considered.values())

    def configure(self, *, max_files: int, max_bytes: int) -> None:
        self.max_files = max_files
        self.max_bytes = max_bytes

    def read(self, relative: str, role: str) -> bytes:
        normalized = Path(relative).as_posix()
        if normalized in self._payloads:
            return self._payloads[normalized]
        candidate = self.root / Path(normalized)
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(self.root)
        except FileNotFoundError as exc:
            raise EntryError("ENTRY_REQUIRED_FILE_MISSING", "A required current-state file is missing.", normalized) from exc
        except (OSError, ValueError) as exc:
            raise EntryError("ENTRY_PATH_INVALID", "A required current-state path escapes the Workspace or cannot be resolved.", normalized) from exc
        if not resolved.is_file():
            raise EntryError("ENTRY_PATH_INVALID", "A required current-state path is not a regular file.", normalized)
        size = resolved.stat().st_size
        self._considered.setdefault(normalized, size)
        if self.files_considered > self.max_files:
            self.budget_exceeded = True
            raise EntryError("ENTRY_FILE_BUDGET_EXCEEDED", "Daily entry file-count budget would be exceeded.", normalized)
        if self.bytes_considered > self.max_bytes:
            self.budget_exceeded = True
            raise EntryError("ENTRY_BYTE_BUDGET_EXCEEDED", "Daily entry byte budget would be exceeded.", normalized)
        payload = resolved.read_bytes()
        self.rows.append({"path": normalized, "role": role, "bytes": len(payload), "sha256": _sha256(payload)})
        self._payloads[normalized] = payload
        return payload


def current_fast_path_limits(profile: str, active_session: bool) -> tuple[int, int]:
    if profile == "resource_admission":
        return (6, 36864) if active_session else (5, 28672)
    return (5, 32768) if active_session else (4, 24576)


def _decode(payload: bytes, path: str) -> str:
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise EntryError("ENTRY_TEXT_ENCODING_INVALID", "Current-state Markdown must be valid UTF-8.", path) from exc


def _normalized_section_sha256(payload: bytes, section_name: str, path: str) -> str:
    text = _decode(payload, path)
    markers = list(SECTION_LINE.finditer(text))
    matches = [index for index, marker in enumerate(markers) if marker.group("name").casefold() == section_name.casefold()]
    if len(matches) != 1:
        raise EntryError("ENTRY_SAFETY_SECTION_INVALID", f"Required safety section must appear exactly once: {section_name}.", path)
    index = matches[0]
    start = markers[index].start()
    end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
    section = text[start:end]
    normalized_lines = [line.rstrip() for line in section.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    normalized = "\n".join(normalized_lines).rstrip("\n") + "\n"
    return _sha256(normalized.encode("utf-8"))


def _json(payload: bytes, path: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EntryError("ENTRY_JSON_INVALID", "Current-state JSON is not valid UTF-8 JSON.", path) from exc
    if not isinstance(value, dict):
        raise EntryError("ENTRY_JSON_INVALID", "Current-state JSON must be an object.", path)
    return value


def _markdown_field(text: str, label: str) -> str | None:
    match = re.search(rf"(?m)^-\s+{re.escape(label)}:\s*`?([^`\r\n]+?)`?\s*$", text)
    return match.group(1).strip() if match else None


def _tokens(values: Sequence[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in values:
        if "=" not in value:
            raise EntryError("ENTRY_FENCING_TOKEN_INVALID", "Fencing tokens use DOMAIN_ID=EPOCH.")
        domain_id, raw_epoch = value.rsplit("=", 1)
        try:
            epoch = int(raw_epoch)
        except ValueError as exc:
            raise EntryError("ENTRY_FENCING_TOKEN_INVALID", "Fencing epoch must be an integer.") from exc
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", domain_id) or epoch < 1:
            raise EntryError("ENTRY_FENCING_TOKEN_INVALID", "Fencing token domain and epoch are invalid.")
        rows.append({"domain_id": domain_id, "epoch": epoch})
    if len({row["domain_id"].casefold() for row in rows}) != len(rows):
        raise EntryError("ENTRY_FENCING_TOKEN_INVALID", "Fencing token domains must be unique.")
    return sorted(rows, key=lambda row: row["domain_id"].casefold())


def _base_report(root: Path, task_class: str, evaluated_at: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "operation": "workspace-entry",
        "status": "FAIL",
        "mode": "READ_ONLY",
        "workspace": str(root),
        "evaluated_at": evaluated_at,
        "workspace_schema_version": None,
        "profile": "unknown",
        "task_class": task_class,
        "entry_path": "FULL_RECOVERY_REQUIRED",
        "decision": "BLOCKED",
        "primary_phase_id": None,
        "selected_phase_id": None,
        "active_session_id": None,
        "read_set": [],
        "metrics": {
            "workspace_files_read": 0,
            "workspace_bytes_read": 0,
            "workspace_files_considered": 0,
            "workspace_bytes_considered": 0,
            "history_files_read": 0,
            "control_files_written": 0,
            "user_confirmations_requested": 0,
            "output_budget_bytes": 12288,
        },
        "fast_path_limits": {"max_workspace_files": 8, "max_workspace_bytes": 131072, "max_history_files": 0},
        "within_fast_path_budget": True,
        "findings": [],
        "required_gates": [],
        "planned_changes": [],
        "writes_performed": False,
        "entities_created": {"workspace": False, "phase": False, "session": False, "artifact": False, "agent": False},
        "safety": {
            "state_contract_valid": False,
            "primary_binding_valid": None,
            "session_binding_valid": None,
            "coordination_valid": None,
            "report_or_handoff_required": False,
            "full_history_loaded": False,
            "raw_write_bypass_prevented": False,
        },
    }


def assess(
    workspace: Path,
    *,
    task_class: str = "LOW_RISK",
    phase_id: str | None = None,
    evaluated_at: str | None = None,
    admission_id: str | None = None,
    actor_id: str | None = None,
    fencing_tokens: Sequence[str] = (),
) -> dict[str, Any]:
    if task_class not in TASK_CLASSES:
        raise EntryError("ENTRY_TASK_CLASS_INVALID", "Unsupported task class.")
    try:
        root = workspace.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise EntryError("ENTRY_WORKSPACE_MISSING", "Workspace root does not exist.", str(workspace)) from exc
    if not root.is_dir():
        raise EntryError("ENTRY_WORKSPACE_INVALID", "Workspace root must be a directory.", str(root))
    evaluated = _timestamp(evaluated_at)
    report = _base_report(root, task_class, evaluated)
    reader = BoundedReader(root)

    def finding(code: str, severity: str, scope: str, message: str, action: str, path: str | None = None) -> None:
        if len(report["findings"]) < 32:
            report["findings"].append({
                "code": code,
                "severity": severity,
                "scope": scope,
                "path": path,
                "message": message,
                "required_action": action,
            })

    def read_required(relative: str, role: str, scope: str = "WORKSPACE") -> bytes | None:
        try:
            return reader.read(relative, role)
        except EntryError as exc:
            finding(exc.code, "BLOCKED", scope, exc.message, "Run full read-only recover/validate and reconcile the exact current-state file.", exc.path)
            return None

    state_payload = read_required(STATE_RELATIVE, "WORKSPACE_STATE")
    state: dict[str, Any] | None = None
    if state_payload is not None:
        try:
            state = _json(state_payload, STATE_RELATIVE)
        except EntryError as exc:
            finding(exc.code, "BLOCKED", "WORKSPACE", exc.message, "Run full read-only recovery; do not mutate malformed runtime state.", exc.path)

    selected_phase_payload: bytes | None = None
    selected_phase: dict[str, Any] | None = None
    coordination: dict[str, Any] | None = None
    if state is not None:
        version = state.get("schema_version")
        is_current = state.get("contract_id") == CURRENT_WORKSPACE_CONTRACT
        report["workspace_schema_version"] = None if is_current else version if isinstance(version, int) else None
        if is_current:
            governance = state.get("phase_governance") if isinstance(state.get("phase_governance"), dict) else {}
            profile = governance.get("profile")
            report["profile"] = profile if profile in CURRENT_PROFILES else "unknown"
            active_session = isinstance(state.get("active_session_id"), str)
            limits = current_fast_path_limits(str(profile), active_session)
        elif version == 5:
            governance = state.get("phase_governance") if isinstance(state.get("phase_governance"), dict) else {}
            profile = LEGACY_PROFILE_MAP.get(governance.get("profile"), governance.get("profile"))
            report["profile"] = profile if profile in CURRENT_PROFILES else "unknown"
            limits = (7, 98304) if profile == "resource_admission" else (5, 65536)
        elif version == 4:
            report["profile"] = "legacy_v4"
            limits = (6, 98304)
        else:
            report["profile"] = "unsupported"
            limits = (8, 131072)
            report["entry_path"] = "MIGRATION_REQUIRED"
            finding(
                "ENTRY_SCHEMA_MIGRATION_REQUIRED",
                "BLOCKED",
                "WORKSPACE",
                "Daily entry supports the CURRENT contract and supported legacy layouts only.",
                "Use explicit one-hop reorganization or recovery for this legacy layout; do not reorganize silently.",
                STATE_RELATIVE,
            )
        reader.configure(max_files=limits[0], max_bytes=limits[1])
        report["fast_path_limits"] = {"max_workspace_files": limits[0], "max_workspace_bytes": limits[1], "max_history_files": 0}
        state_issues = validate_instance(MALTS_ROOT, "workspace-control", state)
        if state_issues:
            for issue in state_issues[:12]:
                finding("ENTRY_STATE_CONTRACT_INVALID", "BLOCKED", "WORKSPACE", issue.render(), "Run full read-only validation and explicit reconcile.", STATE_RELATIVE)
        else:
            report["safety"]["state_contract_valid"] = True

        maintenance = state.get("maintenance_state", {}).get("state") if isinstance(state.get("maintenance_state"), dict) else None
        if maintenance == "recovery-required":
            finding("ENTRY_RECOVERY_STATE", "BLOCKED", "WORKSPACE", "Workspace maintenance state requires recovery.", "Run full read-only recover before business writes.", STATE_RELATIVE)
        elif maintenance in {"maintenance-required", "compaction-required"}:
            finding("ENTRY_MAINTENANCE_DEFERRED", "WARNING", "MAINTENANCE", f"Workspace reports {maintenance}.", "Continue unrelated work and schedule maintenance without rewriting unchanged controls.", STATE_RELATIVE)

        if (root / "runtime" / "workspace_transaction.lock.json").exists():
            finding("ENTRY_TRANSACTION_INCOMPLETE", "BLOCKED", "WORKSPACE", "A Workspace transaction lock is present.", "Run hash-bound transaction recovery before any write.", "runtime/workspace_transaction.lock.json")

        # CURRENT daily entry deliberately consumes only the operational current
        # binding plus the selected Phase (and Session/coordination when present).
        # Applicable instruction files are loaded by the host before this tool is
        # invoked, while Project-control and full consistency are covered by the
        # explicit gates for new-scope/high-risk work.  Keeping those views out of
        # the ordinary read set prevents root/history growth from turning a clean
        # long-running Workspace into a false global block.  Legacy layouts retain
        # their established read set because they do not carry the CURRENT binding
        # contract.
        project_payload: bytes | None = None
        if not is_current:
            read_required("AGENTS.md", "INSTRUCTIONS")
            project_payload = read_required(str(state.get("project_control", "PROJECT_CONTROL.md")), "PROJECT_CONTROL")
        primary_id = state.get("active_phase_id")
        report["primary_phase_id"] = primary_id if isinstance(primary_id, str) else None
        report["active_session_id"] = state.get("active_session_id") if isinstance(state.get("active_session_id"), str) else None
        selected_id = phase_id or primary_id
        report["selected_phase_id"] = selected_id if isinstance(selected_id, str) else None
        phases = state.get("phase_controls") if isinstance(state.get("phase_controls"), list) else []
        rows = [row for row in phases if isinstance(row, dict) and row.get("phase_id") == selected_id]
        if selected_id is None:
            if phases:
                report["entry_path"] = "PHASE_REQUIRED"
                if task_class in WRITE_TASK_CLASSES:
                    finding("ENTRY_ACTIVE_PHASE_REQUIRED", "BLOCKED", "PHASE", "Initialized long work has no active Phase for a write task.", "Open a new Phase explicitly; do not create a Session or Artifact implicitly.")
                else:
                    finding("ENTRY_NO_ACTIVE_PHASE", "INFO", "PHASE", "Initialized long work currently has no active Phase.", "Read-only inspection may continue; open a new Phase explicitly before governed business writes.")
            else:
                report["entry_path"] = "INITIALIZATION_REQUIRED"
                finding("ENTRY_ACTIVE_PHASE_REQUIRED", "BLOCKED", "PHASE", "Long-project initialization requires its first active Phase.", "Open the initial Phase explicitly; do not create a Session or Artifact implicitly.")
        elif len(rows) != 1:
            finding("ENTRY_PHASE_REGISTRY_INVALID", "BLOCKED", "PHASE", "Selected Phase must have exactly one registry row.", "Run full validation and reconcile the Phase registry.", STATE_RELATIVE)
        else:
            selected_phase = rows[0]
            allowed = selected_phase.get("status") == "ACTIVE" or (
                (is_current or version == 5) and report["profile"] == "resource_admission" and selected_phase.get("status") == "OPEN"
            )
            if not allowed:
                finding("ENTRY_PHASE_NOT_EXECUTABLE", "BLOCKED", "PHASE", "Selected Phase is not ACTIVE or concurrency-eligible OPEN.", "Use explicit Phase switch/resume review.", selected_phase.get("path"))
            selected_phase_payload = read_required(str(selected_phase.get("path", "")), "PHASE_CONTROL", "PHASE")
            if selected_phase_payload is not None:
                try:
                    phase_text = _decode(selected_phase_payload, str(selected_phase.get("path")))
                    if _markdown_field(phase_text, "Phase ID") != selected_id:
                        finding("ENTRY_PHASE_ID_DRIFT", "BLOCKED", "PHASE", "Phase Markdown identity disagrees with the registry.", "Run full validation and explicit Phase reconcile.", selected_phase.get("path"))
                    if _markdown_field(phase_text, "Status") != selected_phase.get("status"):
                        finding("ENTRY_PHASE_STATUS_DRIFT", "BLOCKED", "PHASE", "Phase Markdown status disagrees with the registry.", "Run full validation and explicit Phase reconcile.", selected_phase.get("path"))
                except EntryError as exc:
                    finding(exc.code, "BLOCKED", "PHASE", exc.message, "Run full validation and explicit Phase reconcile.", exc.path)

        if project_payload is not None and primary_id is not None:
            try:
                project_text = _decode(project_payload, str(state.get("project_control", "PROJECT_CONTROL.md")))
                root_phase = _markdown_field(project_text, "Active Phase")
                if root_phase not in {primary_id, None}:
                    finding("ENTRY_PROJECT_PHASE_DRIFT", "BLOCKED", "WORKSPACE", "Project control active Phase disagrees with runtime state.", "Run full validation and hash-bound reconcile.", str(state.get("project_control", "PROJECT_CONTROL.md")))
            except EntryError as exc:
                finding(exc.code, "BLOCKED", "WORKSPACE", exc.message, "Run full validation and hash-bound reconcile.", exc.path)

        if primary_id is None and state.get("current_phase_binding") is not None:
            report["safety"]["primary_binding_valid"] = False
            finding("ENTRY_PRIMARY_BINDING_DRIFT", "BLOCKED", "WORKSPACE", "Workspace has no active Phase but retains a current Phase binding.", "Run full read-only recover and hash-bound consistency reconcile.", STATE_RELATIVE)
        elif selected_phase is not None and selected_phase_payload is not None and selected_id == primary_id and (is_current or version in {4, 5}):
            binding = state.get("current_phase_binding")
            identity_valid = isinstance(binding, dict) and all((
                binding.get("active_phase_id") == selected_id,
                binding.get("phase_control_path") == selected_phase.get("path"),
            ))
            full_hash_valid = isinstance(binding, dict) and binding.get("phase_control_sha256") == _sha256(selected_phase_payload)
            section_bound = is_current or version == 5
            valid = identity_valid and (full_hash_valid or section_bound)
            if valid and section_bound:
                try:
                    for section_name, field in (
                        ("phase-boundary", "phase_boundary_sha256"),
                        ("phase-boundary-review", "boundary_review_sha256"),
                        ("phase-recovery", "phase_recovery_sha256"),
                    ):
                        if _normalized_section_sha256(selected_phase_payload, section_name, str(selected_phase.get("path"))) != binding.get(field):
                            valid = False
                except EntryError as exc:
                    valid = False
                    finding(exc.code, "BLOCKED", "PHASE", exc.message, "Run full validation and reconcile the safety-critical Phase binding.", exc.path)
            report["safety"]["primary_binding_valid"] = valid
            if not valid:
                finding("ENTRY_PRIMARY_BINDING_DRIFT", "BLOCKED", "PHASE", "Primary Phase identity or safety-critical boundary/review/recovery binding drifted.", "Run full read-only recover and hash-bound consistency reconcile.", selected_phase.get("path"))
            elif section_bound and not full_hash_valid:
                finding("ENTRY_PHASE_FULL_HASH_REFRESH_DUE", "WARNING", "MAINTENANCE", "The whole Phase-control hash is stale while safety-critical section bindings remain exact.", "Continue unrelated work; refresh the derived hash on the next authorized lifecycle mutation or explicit maintenance.", selected_phase.get("path"))

        active_session_id = state.get("active_session_id")
        if isinstance(active_session_id, str) and selected_id == primary_id:
            sessions = state.get("session_controls") if isinstance(state.get("session_controls"), list) else []
            session_rows = [row for row in sessions if isinstance(row, dict) and row.get("session_id") == active_session_id]
            if len(session_rows) != 1:
                report["safety"]["session_binding_valid"] = False
                finding("ENTRY_SESSION_REGISTRY_INVALID", "BLOCKED", "WORKSPACE", "Active Session must have exactly one registry row.", "Run full recovery and Session reconcile.", STATE_RELATIVE)
            else:
                session_row = session_rows[0]
                session_payload = read_required(str(session_row.get("path", "")), "SESSION_CONTROL")
                binding = state.get("current_session_binding")
                valid = session_payload is not None and isinstance(binding, dict) and all((
                    binding.get("session_id") == active_session_id,
                    binding.get("phase_id") == primary_id,
                    binding.get("session_control_path") == session_row.get("path"),
                    binding.get("session_control_sha256") == _sha256(session_payload),
                ))
                report["safety"]["session_binding_valid"] = valid
                if not valid:
                    finding("ENTRY_SESSION_BINDING_DRIFT", "BLOCKED", "WORKSPACE", "Active Session bytes do not match the exact lease binding.", "Run full recovery before continuing the Session.", session_row.get("path"))

        if (is_current or version == 5) and report["profile"] == "resource_admission":
            coordination_payload = read_required(COORDINATION_RELATIVE, "COORDINATION_STATE", "RESOURCE")
            if coordination_payload is not None:
                try:
                    coordination = _json(coordination_payload, COORDINATION_RELATIVE)
                    coordination_issues = validate_instance(MALTS_ROOT, "workspace-coordination", coordination)
                    if coordination_issues:
                        for issue in coordination_issues[:8]:
                            finding("ENTRY_COORDINATION_INVALID", "BLOCKED", "RESOURCE", issue.render(), "Run coordination recovery or explicit reconcile.", COORDINATION_RELATIVE)
                    else:
                        coordination_runtime._validate_state(coordination, state)
                        report["safety"]["coordination_valid"] = True
                except (EntryError, coordination_runtime.CoordinationError) as exc:
                    code = exc.code if hasattr(exc, "code") else "ENTRY_COORDINATION_INVALID"
                    message = exc.message if hasattr(exc, "message") else str(exc)
                    path = exc.path if isinstance(exc, EntryError) else COORDINATION_RELATIVE
                    finding(code, "BLOCKED", "RESOURCE", message, "Run coordination recovery or explicit reconcile.", path)

    required_gates: set[str] = set()
    if task_class == "NEW_WRITE_SCOPE":
        required_gates.update({"PLAN_RECHECK", "PHASE_BOUNDARY_REVIEW"})
    elif task_class == "HIGH_RISK":
        required_gates.update({"FULL_VALIDATE", "PLAN_RECHECK", "PHASE_BOUNDARY_REVIEW"})
    elif task_class == "CONTEXT_RECOVERY" and report["selected_phase_id"] is not None:
        required_gates.add("PLAN_RECHECK")
    if phase_id is not None and state is not None and phase_id != state.get("active_phase_id"):
        required_gates.add("PHASE_SWITCH_REVIEW")

    if state is not None and report["profile"] == "resource_admission" and task_class in WRITE_TASK_CLASSES:
        required_gates.add("RESOURCE_ADMISSION")
        if admission_id is None:
            finding("ENTRY_RESOURCE_ADMISSION_REQUIRED", "INFO", "RESOURCE", "Governed writes require an exact active Admission.", "Acquire an Admission after required Plan/boundary reviews; no background Agent or service is created.", COORDINATION_RELATIVE)
        elif coordination is not None and selected_phase_payload is not None:
            admissions = [row for row in coordination.get("active_admissions", []) if isinstance(row, dict) and row.get("admission_id") == admission_id]
            if len(admissions) != 1:
                queued = [row for row in coordination.get("queue", []) if isinstance(row, dict) and row.get("request", {}).get("admission_id") == admission_id]
                code = "ENTRY_ADMISSION_QUEUED" if queued else "ENTRY_ADMISSION_MISSING"
                finding(code, "INFO", "RESOURCE", "The requested Admission is not currently active.", "Wait for/retry explicit Admission after conflicts clear.", COORDINATION_RELATIVE)
            else:
                admission = admissions[0]
                admission_issues: list[str] = []
                if admission.get("phase_id") != report["selected_phase_id"]:
                    admission_issues.append("phase")
                if actor_id is None or admission.get("actor", {}).get("id") != actor_id:
                    admission_issues.append("actor")
                try:
                    if _parse_timestamp(str(admission.get("expires_at"))) <= _parse_timestamp(evaluated):
                        admission_issues.append("expiry")
                except ValueError:
                    admission_issues.append("expiry")
                if admission.get("phase_control_sha256") != _sha256(selected_phase_payload):
                    admission_issues.append("phase-control-hash")
                try:
                    observed_tokens = _tokens(fencing_tokens)
                except EntryError as exc:
                    observed_tokens = []
                    admission_issues.append(exc.code)
                expected_tokens = sorted(admission.get("fencing_tokens", []), key=lambda row: str(row.get("domain_id", "")).casefold())
                if observed_tokens != expected_tokens:
                    admission_issues.append("fencing-token")
                epochs = {row.get("domain_id"): row.get("epoch") for row in coordination.get("fencing_domains", []) if isinstance(row, dict)}
                if any(epochs.get(token.get("domain_id")) != token.get("epoch") for token in expected_tokens):
                    admission_issues.append("fencing-epoch")
                if admission_issues:
                    finding("ENTRY_ADMISSION_STALE", "BLOCKED", "RESOURCE", f"Admission verification failed: {', '.join(sorted(set(admission_issues)))}.", "Stop this executor and acquire/reconcile an exact fresh Admission.", COORDINATION_RELATIVE)
                else:
                    required_gates.discard("RESOURCE_ADMISSION")

    if coordination is not None:
        selected = report["selected_phase_id"]
        try:
            now = _parse_timestamp(evaluated)
        except ValueError:
            now = datetime.max.replace(tzinfo=timezone.utc)
        for admission in coordination.get("active_admissions", []):
            try:
                expired = _parse_timestamp(str(admission.get("expires_at"))) <= now
            except ValueError:
                expired = True
            if expired:
                severity = "BLOCKED" if admission.get("phase_id") == selected and task_class in WRITE_TASK_CLASSES else "WARNING"
                finding("ENTRY_EXPIRED_ADMISSION", severity, "RESOURCE", f"Admission {admission.get('admission_id')} is expired.", "Reap and reconcile only the affected Admission/resource domains.", COORDINATION_RELATIVE)
        if coordination.get("workspace_quarantine") is not None:
            finding("ENTRY_WORKSPACE_QUARANTINED", "BLOCKED", "WORKSPACE", "Workspace authority is quarantined after an unknown external side effect.", "Complete explicit evidence-backed reconcile before any write.", COORDINATION_RELATIVE)
        for quarantine in coordination.get("quarantines", []):
            severity = "BLOCKED" if quarantine.get("phase_id") == selected and task_class in WRITE_TASK_CLASSES else "WARNING"
            finding("ENTRY_RESOURCE_QUARANTINED", severity, "RESOURCE", f"Resource quarantine {quarantine.get('quarantine_id')} remains unresolved.", "Reconcile only the affected resource domains; unrelated work may continue.", COORDINATION_RELATIVE)

    report["read_set"] = reader.rows
    report["metrics"]["workspace_files_read"] = len(reader.rows)
    report["metrics"]["workspace_bytes_read"] = reader.bytes_read
    report["metrics"]["workspace_files_considered"] = reader.files_considered
    report["metrics"]["workspace_bytes_considered"] = reader.bytes_considered
    limits = report["fast_path_limits"]
    report["within_fast_path_budget"] = (
        not reader.budget_exceeded
        and reader.files_considered <= limits["max_workspace_files"]
        and reader.bytes_considered <= limits["max_workspace_bytes"]
    )
    if not report["within_fast_path_budget"]:
        finding("ENTRY_FAST_PATH_BUDGET_EXCEEDED", "BLOCKED", "MAINTENANCE", "Current-state entry exceeded its bounded read budget; unread state is unverified, not proven corrupt.", "Read the identified current-state files separately within the authorized read scope. Validate affected bindings before writes; do not compact or reconcile merely because of size.")
        budget_codes = {"ENTRY_FILE_BUDGET_EXCEEDED", "ENTRY_BYTE_BUDGET_EXCEEDED", "ENTRY_FAST_PATH_BUDGET_EXCEEDED"}
        blocking_findings = [item for item in report["findings"] if item["severity"] == "BLOCKED"]
        if blocking_findings and all(item["code"] in budget_codes for item in blocking_findings):
            report["entry_path"] = "BOUNDED_READ_REQUIRED"
            for item in blocking_findings:
                item["required_action"] = "Read the identified current-state file separately; budget exhaustion alone does not require repair or full-history recovery. No write authority is granted."
    report["required_gates"] = [gate for gate in GATE_ORDER if gate in required_gates]
    blocked = any(item["severity"] == "BLOCKED" for item in report["findings"])
    warnings = any(item["severity"] == "WARNING" for item in report["findings"])
    if blocked:
        report["status"] = "FAIL"
        report["decision"] = "BLOCKED"
        if report["entry_path"] == "FAST_PATH":
            report["entry_path"] = "FULL_RECOVERY_REQUIRED"
    elif required_gates:
        report["status"] = "PASS"
        report["decision"] = "REVIEW_REQUIRED"
        if report["entry_path"] not in {"INITIALIZATION_REQUIRED", "PHASE_REQUIRED"}:
            report["entry_path"] = "FAST_PATH"
    else:
        report["status"] = "PASS"
        report["decision"] = "PROCEED_WITH_WARNINGS" if warnings else "PROCEED"
        if report["entry_path"] not in {"INITIALIZATION_REQUIRED", "PHASE_REQUIRED"}:
            report["entry_path"] = "FAST_PATH"

    schema_issues = validate_instance(MALTS_ROOT, "workspace-entry-report", report)
    if schema_issues:
        raise EntryError("ENTRY_REPORT_INVALID", "; ".join(issue.render() for issue in schema_issues[:5]))
    encoded = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(encoded) > report["metrics"]["output_budget_bytes"]:
        raise EntryError("ENTRY_OUTPUT_BUDGET_EXCEEDED", "Workspace entry report exceeds its 12 KiB output budget.")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MALTS bounded read-only daily Workspace entry.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--task-class", choices=tuple(sorted(TASK_CLASSES)), default="LOW_RISK")
    parser.add_argument("--phase-id")
    parser.add_argument("--evaluated-at")
    parser.add_argument("--admission-id")
    parser.add_argument("--actor-id")
    parser.add_argument("--token", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = assess(
            Path(args.workspace),
            task_class=args.task_class,
            phase_id=args.phase_id,
            evaluated_at=args.evaluated_at,
            admission_id=args.admission_id,
            actor_id=args.actor_id,
            fencing_tokens=args.token,
        )
    except EntryError as exc:
        print(json.dumps({"status": "FAIL", "error_code": exc.code, "message": exc.message, "path": exc.path}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
