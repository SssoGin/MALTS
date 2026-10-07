#!/usr/bin/env python3
"""Opt-in, resource-scoped MALTS workspace Admission and fencing runtime."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

sys.dont_write_bytecode = True

from resource_locators import (
    LocatorError,
    find_conflicts,
    locator_conflict,
    locator_domains,
    normalize_locator,
    normalize_locators,
)
from workspace_transactions import (
    TransactionError,
    TransactionProfile,
    execute_transaction,
    inspect_transaction_state,
    recover_transaction,
    sha256_bytes,
)


COORDINATION_RELATIVE = Path("runtime") / "workspace_coordination.json"
EVENTS_RELATIVE = Path("runtime") / "workspace_coordination_events"
CURRENT_WORKSPACE_CONTRACT = "malts.workspace.current"
COORDINATION_TRANSACTION_PROFILE = TransactionProfile(
    domain="Workspace-coordination",
    code_prefix="COORD_TRANSACTION",
    # Coordination and canonical Workspace mutations share one writer lock.
    # Their journals and error prefixes remain distinguishable, but an
    # Admission cannot be released or fenced between another operation's
    # post-lock authority check and commit.
    lock_relative=Path("runtime") / "workspace_transaction.lock.json",
    journal_directory_relative=Path("runtime") / "workspace_transactions",
)
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SHA256 = re.compile(r"^[A-F0-9]{64}$")
ACTOR_KINDS = {"MAIN_CONTROLLER", "DELEGATED_AGENT", "TOOL_ADAPTER", "SYSTEM_RECOVERY"}
CAPABILITY_MODES = {"SHARED", "EXCLUSIVE", "QUEUED", "ISOLATE_REQUIRED"}
RECONCILE_RESOLUTIONS = {"CONFIRMED_NOT_APPLIED", "CONFIRMED_APPLIED", "ISOLATED_TERMINATED"}


class CoordinationError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _hash_value(value: Any) -> str:
    return sha256_bytes(_canonical_bytes(value))


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoordinationError(code, "A required coordination JSON file is unreadable.", str(path)) from exc
    if not isinstance(value, dict):
        raise CoordinationError(code, "A required coordination JSON file must contain an object.", str(path))
    return value


def _parse_time(value: str, *, code: str = "COORD_TIMESTAMP_INVALID") -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CoordinationError(code, "Timestamp must be a valid ISO 8601 date-time.", value) from exc
    if parsed.tzinfo is None:
        raise CoordinationError(code, "Timestamp must include an explicit UTC offset.", value)
    return parsed.astimezone(timezone.utc)


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or ID.fullmatch(value) is None:
        raise CoordinationError("COORD_ID_INVALID", f"{field} violates the stable identifier contract.", value)
    return value


def _require_sha256(value: Any, field: str) -> str:
    normalized = str(value).upper()
    if SHA256.fullmatch(normalized) is None:
        raise CoordinationError("COORD_HASH_INVALID", f"{field} must be an exact SHA-256.", value)
    return normalized


def _require_actor(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != {"kind", "id"}:
        raise CoordinationError("COORD_ACTOR_INVALID", "actor must contain only kind and id.", value)
    kind = value.get("kind")
    if kind not in ACTOR_KINDS:
        raise CoordinationError("COORD_ACTOR_INVALID", "Unknown coordination actor kind.", kind)
    return {"kind": str(kind), "id": _require_id(value.get("id"), "actor.id")}


def _normalize_capabilities(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        raise CoordinationError("COORD_CAPABILITIES_INVALID", "capabilities must be an array.", values)
    normalized: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, Mapping) or set(value) != {"capability_id", "mode", "fenceable", "isolation_key"}:
            raise CoordinationError("COORD_CAPABILITY_INVALID", "A capability declaration has missing or unknown fields.", value)
        capability_id = _require_id(value.get("capability_id"), "capability_id")
        mode = value.get("mode")
        fenceable = value.get("fenceable")
        isolation_key = value.get("isolation_key")
        if mode not in CAPABILITY_MODES:
            raise CoordinationError("COORD_CAPABILITY_INVALID", "Unknown capability mode.", mode)
        if not isinstance(fenceable, bool):
            raise CoordinationError("COORD_CAPABILITY_INVALID", "fenceable must be boolean.", fenceable)
        if isolation_key is not None:
            isolation_key = _require_id(isolation_key, "isolation_key")
        if mode == "ISOLATE_REQUIRED" and isolation_key is None:
            raise CoordinationError("COORD_ISOLATION_KEY_REQUIRED", "ISOLATE_REQUIRED capabilities require an isolation_key.", capability_id)
        if mode != "ISOLATE_REQUIRED" and isolation_key is not None:
            raise CoordinationError("COORD_CAPABILITY_INVALID", "Only ISOLATE_REQUIRED capabilities accept isolation_key.", capability_id)
        if mode == "SHARED" and not fenceable:
            raise CoordinationError(
                "COORD_NON_FENCEABLE_SHARED_UNSAFE",
                "A non-fenceable external capability cannot use SHARED mode; declare EXCLUSIVE, QUEUED, or ISOLATE_REQUIRED.",
                capability_id,
            )
        normalized.append(
            {
                "capability_id": capability_id,
                "mode": str(mode),
                "fenceable": fenceable,
                "isolation_key": isolation_key,
            }
        )
    capability_ids = [item["capability_id"] for item in normalized]
    if len(capability_ids) != len(set(capability_ids)):
        raise CoordinationError("COORD_CAPABILITY_DUPLICATE", "capability_id values must be unique within one request.", capability_ids)
    return sorted(normalized, key=lambda item: item["capability_id"].casefold())


def normalize_admission_request(workspace: Path, value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CoordinationError("COORD_REQUEST_INVALID", "An Admission request must be an object.")
    expected = {
        "request_version", "admission_id", "phase_id", "phase_control_sha256", "actor", "expires_at",
        "authorization_ref", "locators", "capabilities", "evidence_refs",
    }
    if set(value) != expected:
        raise CoordinationError(
            "COORD_REQUEST_INVALID",
            "An Admission request has missing or unknown fields.",
            {"missing": sorted(expected - set(value)), "unknown": sorted(set(value) - expected)},
        )
    if value.get("request_version") != 1:
        raise CoordinationError("COORD_REQUEST_VERSION_UNSUPPORTED", "Only Admission request_version 1 is supported.", value.get("request_version"))
    authorization_ref = value.get("authorization_ref")
    evidence_refs = value.get("evidence_refs")
    if not isinstance(authorization_ref, str) or not authorization_ref.strip():
        raise CoordinationError("COORD_AUTHORIZATION_REQUIRED", "Admission requires a non-empty authorization_ref.")
    if not isinstance(evidence_refs, list) or len(evidence_refs) != len(set(evidence_refs)) or any(not isinstance(item, str) or not item for item in evidence_refs):
        raise CoordinationError("COORD_EVIDENCE_INVALID", "evidence_refs must be a unique string array.", evidence_refs)
    try:
        locators = normalize_locators(workspace, value.get("locators") if isinstance(value.get("locators"), list) else [])
    except LocatorError as exc:
        raise CoordinationError(exc.code, exc.message, exc.detail) from exc
    capabilities = _normalize_capabilities(value.get("capabilities"))
    unknown_write_locators = [
        {
            "locator_id": item["locator_id"],
            "errors": item["physical_identity_errors"],
        }
        for item in locators
        if item["access"] == "WRITE" and item["physical_identity_status"] == "UNKNOWN"
    ]
    if unknown_write_locators:
        raise CoordinationError(
            "LOCATOR_PHYSICAL_IDENTITY_UNKNOWN",
            "A write Admission requires known physical path identity; repair the declaration or use a separately isolated Workspace.",
            unknown_write_locators,
        )
    if not locators and not capabilities:
        raise CoordinationError("COORD_EMPTY_SCOPE", "Admission requires at least one locator or capability.")
    expires_at = value.get("expires_at")
    if not isinstance(expires_at, str):
        raise CoordinationError("COORD_EXPIRY_INVALID", "expires_at must be an ISO 8601 string.", expires_at)
    _parse_time(expires_at, code="COORD_EXPIRY_INVALID")
    return {
        "request_version": 1,
        "admission_id": _require_id(value.get("admission_id"), "admission_id"),
        "phase_id": _require_id(value.get("phase_id"), "phase_id"),
        "phase_control_sha256": _require_sha256(value.get("phase_control_sha256"), "phase_control_sha256"),
        "actor": _require_actor(value.get("actor")),
        "expires_at": expires_at,
        "authorization_ref": authorization_ref,
        "locators": locators,
        "capabilities": capabilities,
        "evidence_refs": list(evidence_refs),
    }


def new_coordination_state(workspace_id: str, recorded_at: str) -> dict[str, Any]:
    _parse_time(recorded_at)
    return {
        "schema_version": 1,
        "workspace_schema_version": 5,
        "workspace_id": _require_id(workspace_id, "workspace_id"),
        "profile": "resource_admission",
        "revision": 0,
        "updated_at": recorded_at,
        "next_event_sequence": 1,
        "fencing_domains": [],
        "active_admissions": [],
        "queue": [],
        "quarantines": [],
        "workspace_quarantine": None,
        "last_event": None,
    }


def _workspace_context(root: Path) -> tuple[dict[str, Any], bytes, dict[str, Any], bytes]:
    root = root.resolve(strict=True)
    workspace_path = root / "runtime" / "workspace_control.json"
    coordination_path = root / COORDINATION_RELATIVE
    workspace_bytes = workspace_path.read_bytes() if workspace_path.is_file() else b""
    if not workspace_bytes:
        raise CoordinationError("COORD_WORKSPACE_STATE_MISSING", "runtime/workspace_control.json is required.", str(workspace_path))
    workspace_state = _read_json(workspace_path, "COORD_WORKSPACE_STATE_INVALID")
    if workspace_state.get("contract_id") == CURRENT_WORKSPACE_CONTRACT:
        workspace_state = copy.deepcopy(workspace_state)
        workspace_state["schema_version"] = 5
        current_governance = workspace_state.get("phase_governance")
        if isinstance(current_governance, dict) and current_governance.get("profile") == "resource_admission":
            current_governance["profile"] = "resource_admission_v1"
    governance = workspace_state.get("phase_governance")
    if workspace_state.get("schema_version") != 5 or not isinstance(governance, dict):
        raise CoordinationError("COORD_SCHEMA_V5_REQUIRED", "Resource Admission requires workspace-control schema v5.")
    if governance.get("profile") != "resource_admission_v1" or governance.get("coordination_path") != COORDINATION_RELATIVE.as_posix():
        raise CoordinationError("COORD_PROFILE_REQUIRED", "Workspace is not explicitly enrolled in resource_admission.")
    coordination_bytes = coordination_path.read_bytes() if coordination_path.is_file() else b""
    if not coordination_bytes:
        raise CoordinationError("COORD_STATE_MISSING", "The enrolled coordination state is missing.", str(coordination_path))
    coordination = _read_json(coordination_path, "COORD_STATE_INVALID")
    _validate_state(coordination, workspace_state)
    return workspace_state, workspace_bytes, coordination, coordination_bytes


def _validate_state(state: Mapping[str, Any], workspace_state: Mapping[str, Any] | None = None) -> None:
    required = {
        "schema_version", "workspace_schema_version", "workspace_id", "profile", "revision", "updated_at",
        "next_event_sequence", "fencing_domains", "active_admissions", "queue", "quarantines", "workspace_quarantine", "last_event",
    }
    if set(state) != required:
        raise CoordinationError("COORD_STATE_INVALID", "Coordination state has missing or unknown fields.", {"missing": sorted(required - set(state)), "unknown": sorted(set(state) - required)})
    if state.get("schema_version") != 1 or state.get("workspace_schema_version") != 5 or state.get("profile") not in {"resource_admission", "resource_admission_v1"}:
        raise CoordinationError("COORD_STATE_INVALID", "Coordination identity fields are invalid.")
    _require_id(state.get("workspace_id"), "workspace_id")
    if workspace_state is not None and state.get("workspace_id") != workspace_state.get("project_id"):
        raise CoordinationError("COORD_WORKSPACE_ID_DRIFT", "Coordination and workspace identities disagree.")
    if not isinstance(state.get("revision"), int) or state["revision"] < 0:
        raise CoordinationError("COORD_STATE_INVALID", "revision must be a non-negative integer.")
    _parse_time(str(state.get("updated_at")))
    if not isinstance(state.get("next_event_sequence"), int) or state["next_event_sequence"] < 1:
        raise CoordinationError("COORD_STATE_INVALID", "next_event_sequence must be positive.")
    for field in ("fencing_domains", "active_admissions", "queue", "quarantines"):
        if not isinstance(state.get(field), list):
            raise CoordinationError("COORD_STATE_INVALID", f"{field} must be an array.")
    domain_ids = [item.get("domain_id") for item in state["fencing_domains"] if isinstance(item, dict)]
    admission_ids = [item.get("admission_id") for item in state["active_admissions"] if isinstance(item, dict)]
    queued_ids = [item.get("request", {}).get("admission_id") for item in state["queue"] if isinstance(item, dict)]
    quarantine_ids = [item.get("quarantine_id") for item in state["quarantines"] if isinstance(item, dict)]
    for label, values in (("domain", domain_ids), ("admission", admission_ids), ("queued admission", queued_ids), ("quarantine", quarantine_ids)):
        if len(values) != len(set(values)) or any(not isinstance(item, str) for item in values):
            raise CoordinationError("COORD_STATE_INVALID", f"Duplicate or invalid {label} identifiers exist.", values)
    if set(admission_ids) & set(queued_ids):
        raise CoordinationError("COORD_STATE_INVALID", "An Admission cannot be active and queued simultaneously.")
    epochs = {item["domain_id"]: item.get("epoch") for item in state["fencing_domains"]}
    for admission in state["active_admissions"]:
        if not isinstance(admission, dict):
            raise CoordinationError("COORD_STATE_INVALID", "Active Admission rows must be objects.")
        for token in admission.get("fencing_tokens", []):
            if epochs.get(token.get("domain_id")) != token.get("epoch"):
                raise CoordinationError("COORD_FENCING_STATE_DRIFT", "An active Admission carries a stale fencing token.", admission.get("admission_id"))
    last_event = state.get("last_event")
    if last_event is None:
        if state["next_event_sequence"] != 1 or state["revision"] != 0:
            raise CoordinationError("COORD_EVENT_HEAD_DRIFT", "Empty event head disagrees with revision counters.")
    elif not isinstance(last_event, dict) or last_event.get("sequence") != state["next_event_sequence"] - 1 or state["revision"] != last_event.get("sequence"):
        raise CoordinationError("COORD_EVENT_HEAD_DRIFT", "Event head and revision counters disagree.")


def _phase_is_open(workspace_state: Mapping[str, Any], phase_id: str) -> bool:
    rows = [item for item in workspace_state.get("phase_controls", []) if isinstance(item, dict) and item.get("phase_id") == phase_id]
    return len(rows) == 1 and rows[0].get("status") in {"ACTIVE", "OPEN"}


def _phase_control_sha256(root: Path, workspace_state: Mapping[str, Any], phase_id: str) -> str:
    rows = [item for item in workspace_state.get("phase_controls", []) if isinstance(item, dict) and item.get("phase_id") == phase_id]
    if len(rows) != 1:
        raise CoordinationError("COORD_PHASE_REGISTRY_INVALID", "Admission phase must have exactly one Workspace registry row.", phase_id)
    relative = rows[0].get("path")
    if not isinstance(relative, str) or not relative:
        raise CoordinationError("COORD_PHASE_REGISTRY_INVALID", "Admission phase registry path is invalid.", phase_id)
    candidate = root / Path(relative)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise CoordinationError("COORD_PHASE_CONTROL_INVALID", "Admission phase control is missing or escapes the Workspace.", relative) from exc
    if not resolved.is_file():
        raise CoordinationError("COORD_PHASE_CONTROL_INVALID", "Admission phase control must be a regular file.", relative)
    return sha256_bytes(resolved.read_bytes())


def _require_phase_control_binding(root: Path, workspace_state: Mapping[str, Any], admission: Mapping[str, Any]) -> None:
    observed = _phase_control_sha256(root, workspace_state, str(admission["phase_id"]))
    if observed != admission.get("phase_control_sha256"):
        raise CoordinationError(
            "COORD_PHASE_BINDING_STALE",
            "Phase control bytes changed after the Admission scope was reviewed.",
            {"phase_id": admission.get("phase_id"), "expected": admission.get("phase_control_sha256"), "observed": observed},
        )


def _capability_canonical_value(capability: Mapping[str, Any]) -> str:
    base = str(capability["capability_id"]).casefold()
    if capability.get("mode") == "ISOLATE_REQUIRED":
        return f"{base}#isolation={str(capability['isolation_key']).casefold()}"
    return base


def _capability_domain(capability: Mapping[str, Any]) -> dict[str, Any]:
    canonical_value = _capability_canonical_value(capability)
    domain_id = "CAP-" + hashlib.sha256(canonical_value.encode("utf-8")).hexdigest().upper()[:32]
    return {
        "domain_id": domain_id,
        "domain_kind": "CAPABILITY",
        "resource_kind": "CAPABILITY",
        "scope": "GLOBAL",
        "canonical_value": canonical_value,
        "epoch": 0,
    }


def _locator_domain_rows(locator: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "domain_id": item["domain_id"],
            "domain_kind": "LOCATOR",
            "resource_kind": item["kind"],
            "scope": item["scope"],
            "canonical_value": item["canonical_value"],
            "epoch": 0,
        }
        for item in locator_domains(locator)
    ]


def _domain_as_locator(domain: Mapping[str, Any], locator_id: str) -> dict[str, Any]:
    return {
        "locator_id": locator_id,
        "kind": domain["resource_kind"],
        "scope": domain["scope"],
        "access": "WRITE",
        "canonical_value": domain["canonical_value"],
        "canonical_aliases": [],
        "canonical_backing_paths": [],
        "physical_paths": [],
        "physical_file_ids": [],
    }


def _raw_locator(locator: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": locator["schema_version"],
        "locator_id": locator["locator_id"],
        "kind": locator["kind"],
        "scope": locator["scope"],
        "access": locator["access"],
        "value": locator["value"],
        "aliases": list(locator.get("aliases", [])),
        "backing_paths": [dict(item) for item in locator.get("backing_paths", [])],
    }


def _physical_identity_issues(root: Path, admission: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for locator in admission.get("locators", []):
        if locator.get("access") != "WRITE" or locator.get("physical_identity_status") == "NOT_APPLICABLE":
            continue
        try:
            observed = normalize_locator(root, _raw_locator(locator))
        except LocatorError as exc:
            issues.append({"code": exc.code, "locator_id": locator.get("locator_id"), "detail": exc.detail})
            continue
        if observed["physical_identity_status"] == "UNKNOWN":
            issues.append(
                {
                    "code": "LOCATOR_PHYSICAL_IDENTITY_UNKNOWN",
                    "locator_id": locator.get("locator_id"),
                    "errors": observed["physical_identity_errors"],
                }
            )
            continue
        expected_paths = sorted(str(item) for item in locator.get("physical_paths", []))
        observed_paths = sorted(str(item) for item in observed.get("physical_paths", []))
        if expected_paths != observed_paths:
            issues.append(
                {
                    "code": "COORD_LOCATOR_PHYSICAL_TARGET_CHANGED",
                    "locator_id": locator.get("locator_id"),
                    "expected": expected_paths,
                    "observed": observed_paths,
                }
            )
    return issues


def _increment_grant_domains(state: dict[str, Any], request: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = {item["domain_id"]: dict(item) for item in state["fencing_domains"]}
    affected: set[str] = set()
    token_ids: set[str] = set()
    write_locators = [item for item in request["locators"] if item["access"] == "WRITE"]
    for locator in write_locators:
        exact_rows = _locator_domain_rows(locator)
        for row in exact_rows:
            rows.setdefault(row["domain_id"], row)
            affected.add(row["domain_id"])
            token_ids.add(row["domain_id"])
        for row in rows.values():
            if row["domain_kind"] != "LOCATOR":
                continue
            if locator_conflict(locator, _domain_as_locator(row, row["domain_id"])) is not None:
                affected.add(row["domain_id"])
    for capability in request["capabilities"]:
        if capability["mode"] == "SHARED":
            continue
        row = _capability_domain(capability)
        rows.setdefault(row["domain_id"], row)
        affected.add(row["domain_id"])
        token_ids.add(row["domain_id"])
    for domain_id in affected:
        rows[domain_id]["epoch"] = int(rows[domain_id].get("epoch", 0)) + 1
    state["fencing_domains"] = sorted(rows.values(), key=lambda item: item["domain_id"])
    return [{"domain_id": domain_id, "epoch": rows[domain_id]["epoch"]} for domain_id in sorted(token_ids)]


def _bump_tokens(state: dict[str, Any], admission: Mapping[str, Any]) -> None:
    rows = {item["domain_id"]: dict(item) for item in state["fencing_domains"]}
    for token in admission.get("fencing_tokens", []):
        domain_id = token["domain_id"]
        if domain_id not in rows:
            raise CoordinationError("COORD_FENCING_STATE_DRIFT", "A fencing domain disappeared.", domain_id)
        rows[domain_id]["epoch"] = int(rows[domain_id]["epoch"]) + 1
    state["fencing_domains"] = sorted(rows.values(), key=lambda item: item["domain_id"])


def _capability_conflict(requested: Mapping[str, Any], held: Mapping[str, Any]) -> str | None:
    if requested["capability_id"] != held["capability_id"]:
        return None
    if requested["mode"] == held["mode"] == "SHARED":
        return None
    if requested["mode"] == "ISOLATE_REQUIRED" and held["mode"] == "ISOLATE_REQUIRED":
        if requested["isolation_key"] != held["isolation_key"]:
            return None
        return "ISOLATION_KEY_COLLISION"
    if "QUEUED" in {requested["mode"], held["mode"]}:
        return "QUEUED"
    if "ISOLATE_REQUIRED" in {requested["mode"], held["mode"]}:
        return "ISOLATION_REQUIRED"
    return "EXCLUSIVE"


def _active_conflicts(request: Mapping[str, Any], admissions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for admission in admissions:
        for item in find_conflicts(request["locators"], admission["locators"]):
            conflicts.append(
                {
                    "conflict_class": "LOCATOR",
                    "held_admission_id": admission["admission_id"],
                    "requested_id": item["left_locator_id"],
                    "held_id": item["right_locator_id"],
                    "relationship": item["relationship"],
                }
            )
        for requested in request["capabilities"]:
            for held in admission["capabilities"]:
                relationship = _capability_conflict(requested, held)
                if relationship is not None:
                    conflicts.append(
                        {
                            "conflict_class": "CAPABILITY",
                            "held_admission_id": admission["admission_id"],
                            "requested_id": requested["capability_id"],
                            "held_id": held["capability_id"],
                            "relationship": relationship,
                        }
                    )
    return conflicts


def _quarantine_domains(admission: Mapping[str, Any]) -> list[dict[str, str]]:
    rows: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for locator in admission["locators"]:
        for item in _locator_domain_rows(locator):
            row = {
                "domain_kind": "LOCATOR",
                "resource_kind": item["resource_kind"],
                "scope": item["scope"],
                "canonical_value": item["canonical_value"],
            }
            rows[tuple(row.values())] = row
    for capability in admission["capabilities"]:
        row = {
            "domain_kind": "CAPABILITY",
            "resource_kind": "CAPABILITY",
            "scope": "GLOBAL",
            "canonical_value": _capability_canonical_value(capability),
        }
        rows[tuple(row.values())] = row
    return sorted(rows.values(), key=lambda item: tuple(item.values()))


def _quarantine_conflicts(request: Mapping[str, Any], state: Mapping[str, Any]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    if state.get("workspace_quarantine") is not None:
        quarantine = state["workspace_quarantine"]
        conflicts.append(
            {
                "conflict_class": "WORKSPACE_QUARANTINE",
                "held_admission_id": quarantine["admission_id"],
                "requested_id": request["admission_id"],
                "held_id": quarantine["quarantine_id"],
                "relationship": "WORKSPACE_AUTHORITY_UNKNOWN",
            }
        )
        return conflicts
    for quarantine in state["quarantines"]:
        for domain_index, domain in enumerate(quarantine["domains"]):
            if domain["domain_kind"] == "LOCATOR":
                held = _domain_as_locator(domain, f"{quarantine['quarantine_id']}-{domain_index}")
                for locator in request["locators"]:
                    relationship = locator_conflict(locator, held)
                    if relationship is not None:
                        conflicts.append(
                            {
                                "conflict_class": "QUARANTINE",
                                "held_admission_id": quarantine["admission_id"],
                                "requested_id": locator["locator_id"],
                                "held_id": quarantine["quarantine_id"],
                                "relationship": relationship.relationship,
                            }
                        )
            else:
                for capability in request["capabilities"]:
                    if _capability_canonical_value(capability) == domain["canonical_value"]:
                        conflicts.append(
                            {
                                "conflict_class": "QUARANTINE",
                                "held_admission_id": quarantine["admission_id"],
                                "requested_id": capability["capability_id"],
                                "held_id": quarantine["quarantine_id"],
                                "relationship": "CAPABILITY_UNKNOWN",
                            }
                        )
    return conflicts


def _queue_order_conflicts(request: Mapping[str, Any], queue: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    requested_queued = {item["capability_id"] for item in request["capabilities"] if item["mode"] == "QUEUED"}
    if not requested_queued:
        return []
    conflicts = []
    for row in queue:
        queued = row["request"]
        if queued["admission_id"] == request["admission_id"]:
            break
        held_queued = {item["capability_id"] for item in queued["capabilities"] if item["mode"] == "QUEUED"}
        for capability_id in sorted(requested_queued & held_queued):
            conflicts.append(
                {
                    "conflict_class": "QUEUE_ORDER",
                    "held_admission_id": queued["admission_id"],
                    "requested_id": capability_id,
                    "held_id": capability_id,
                    "relationship": "QUEUED",
                }
            )
    return conflicts


def _expired_admissions(state: Mapping[str, Any], now: datetime) -> list[dict[str, Any]]:
    return [item for item in state["active_admissions"] if _parse_time(item["expires_at"], code="COORD_EXPIRY_INVALID") <= now]


def _event_path(root: Path, operation_id: str) -> Path:
    return root / EVENTS_RELATIVE / f"{_require_id(operation_id, 'operation_id')}.json"


def _existing_receipt(root: Path, operation_id: str, request_sha256: str) -> dict[str, Any] | None:
    event_path = _event_path(root, operation_id)
    journal_path = root / COORDINATION_TRANSACTION_PROFILE.journal_directory_relative / f"{operation_id}.json"
    if not event_path.is_file() and not journal_path.is_file():
        return None
    if journal_path.is_file():
        journal = _read_json(journal_path, "COORD_TRANSACTION_JOURNAL_INVALID")
        if journal.get("status") == "ROLLED_BACK" and not event_path.exists():
            return None
    else:
        journal = None
    if not event_path.is_file() or journal is None:
        raise CoordinationError("COORD_REPLAY_INCOMPLETE", "Operation evidence is incomplete and requires transaction recovery.", operation_id)
    event = _read_json(event_path, "COORD_EVENT_INVALID")
    if event.get("operation_id") != operation_id or event.get("request_sha256") != request_sha256:
        raise CoordinationError("COORD_REPLAY_CONFLICT", "Operation ID is bound to a different coordination request.", operation_id)
    if journal.get("status") != "COMMITTED":
        raise CoordinationError("COORD_REPLAY_INCOMPLETE", "Operation journal is not committed.", {"operation_id": operation_id, "status": journal.get("status")})
    return {
        "status": "PASS",
        "operation": event["event_kind"],
        "mode": "APPLY",
        "outcome": event["outcome"],
        "operation_id": operation_id,
        "plan_sha256": event["plan_sha256"],
        "event": event_path.relative_to(root).as_posix(),
        "idempotent": True,
        "writes_performed": False,
        "planned_changes": [],
        "details": event["details"],
    }


def _prepare_mutation(
    root: Path,
    *,
    workspace_state: Mapping[str, Any],
    workspace_bytes: bytes,
    state_before: Mapping[str, Any],
    state_bytes: bytes,
    state_after: dict[str, Any],
    operation: str,
    operation_id: str,
    event_kind: str,
    recorded_at: str,
    actor: Mapping[str, str],
    phase_id: str | None,
    admission_id: str | None,
    request_sha256: str,
    outcome: str,
    details: Mapping[str, Any],
    evidence_refs: Sequence[str],
) -> dict[str, Any]:
    sequence = int(state_before["next_event_sequence"])
    event_id = f"CE-{sequence}-{hashlib.sha256(operation_id.encode('utf-8')).hexdigest().upper()[:16]}"
    event_relative = (EVENTS_RELATIVE / f"{operation_id}.json").as_posix()
    next_state_core = copy.deepcopy(state_after)
    next_state_core.update(
        {
            "revision": int(state_before["revision"]) + 1,
            "updated_at": recorded_at,
            "next_event_sequence": sequence + 1,
            "last_event": None,
        }
    )
    event_without_plan = {
        "event_version": 1,
        "sequence": sequence,
        "event_id": event_id,
        "operation_id": operation_id,
        "workspace_id": state_before["workspace_id"],
        "event_kind": event_kind,
        "recorded_at": recorded_at,
        "actor": dict(actor),
        "phase_id": phase_id,
        "admission_id": admission_id,
        "previous_event": copy.deepcopy(state_before.get("last_event")),
        "coordination_preimage_sha256": sha256_bytes(state_bytes),
        "revision_before": state_before["revision"],
        "revision_after": next_state_core["revision"],
        "request_sha256": request_sha256,
        "outcome": outcome,
        "details": copy.deepcopy(dict(details)),
        "evidence_refs": list(evidence_refs),
    }
    plan_body = {
        "plan_version": 1,
        "operation": operation,
        "operation_id": operation_id,
        "workspace_id": state_before["workspace_id"],
        "workspace_control_sha256": sha256_bytes(workspace_bytes),
        "coordination_preimage_sha256": sha256_bytes(state_bytes),
        "request_sha256": request_sha256,
        "event": event_without_plan,
        "next_state": next_state_core,
    }
    plan_sha256 = _hash_value(plan_body)
    event = {**event_without_plan, "plan_sha256": plan_sha256}
    event_bytes = _json_bytes(event)
    next_state = copy.deepcopy(next_state_core)
    next_state["last_event"] = {
        "sequence": sequence,
        "event_id": event_id,
        "path": event_relative,
        "sha256": sha256_bytes(event_bytes),
    }
    _validate_state(next_state, workspace_state)
    return {
        "plan_sha256": plan_sha256,
        "plan": plan_body,
        "state": next_state,
        "state_bytes": _json_bytes(next_state),
        "event": event,
        "event_bytes": event_bytes,
        "event_path": root / Path(event_relative),
        "outcome": outcome,
        "details": dict(details),
    }


def _finish_mutation(
    root: Path,
    *,
    prepared: Mapping[str, Any],
    workspace_bytes: bytes,
    state_bytes: bytes,
    operation: str,
    operation_id: str,
    apply: bool,
    expected_plan_sha256: str | None,
) -> dict[str, Any]:
    expected_plan = prepared["plan_sha256"]
    if apply:
        if expected_plan_sha256 is None or _require_sha256(expected_plan_sha256, "expected_plan_sha256") != expected_plan:
            raise CoordinationError(
                "COORD_PLAN_STALE",
                "Apply requires the exact current dry-run plan SHA-256.",
                {"expected": expected_plan_sha256, "observed": expected_plan},
            )
        coordination_path = root / COORDINATION_RELATIVE
        event_path = prepared["event_path"]

        def post_validate() -> None:
            observed = _read_json(coordination_path, "COORD_STATE_INVALID")
            _validate_state(observed)
            event = _read_json(event_path, "COORD_EVENT_INVALID")
            if event.get("plan_sha256") != expected_plan:
                raise CoordinationError("COORD_EVENT_PLAN_DRIFT", "Persisted event does not bind the reviewed plan.")

        receipt = execute_transaction(
            root,
            operation_id=operation_id,
            operation=operation,
            changes={coordination_path: prepared["state_bytes"], event_path: prepared["event_bytes"]},
            expected_input_hashes={
                coordination_path: sha256_bytes(state_bytes),
                event_path: None,
                root / "runtime" / "workspace_control.json": sha256_bytes(workspace_bytes),
            },
            post_validate=post_validate,
            profile=COORDINATION_TRANSACTION_PROFILE,
            fault_point=os.environ.get("MALTS_TEST_COORDINATION_FAULT_POINT"),
            fail_after_replacements=(
                int(os.environ["MALTS_TEST_COORDINATION_FAIL_AFTER_REPLACEMENTS"])
                if os.environ.get("MALTS_TEST_COORDINATION_FAIL_AFTER_REPLACEMENTS")
                else None
            ),
            crash_after_replacements=(
                int(os.environ["MALTS_TEST_COORDINATION_CRASH_AFTER_REPLACEMENTS"])
                if os.environ.get("MALTS_TEST_COORDINATION_CRASH_AFTER_REPLACEMENTS")
                else None
            ),
        )
    else:
        receipt = None
    return {
        "status": "PASS" if prepared["outcome"] not in {"QUEUED"} else "QUEUED",
        "operation": operation,
        "mode": "APPLY" if apply else "DRY_RUN",
        "outcome": prepared["outcome"],
        "operation_id": operation_id,
        "plan_sha256": expected_plan,
        "event": prepared["event_path"].relative_to(root).as_posix(),
        "idempotent": False,
        "writes_performed": apply,
        "planned_changes": [COORDINATION_RELATIVE.as_posix(), prepared["event_path"].relative_to(root).as_posix()],
        "details": prepared["details"],
        "transaction": receipt,
    }


def admit(
    root: Path,
    request_value: Any,
    *,
    operation_id: str,
    recorded_at: str,
    apply: bool = False,
    expected_plan_sha256: str | None = None,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    now = _parse_time(recorded_at)
    request = normalize_admission_request(root, request_value)
    if _parse_time(request["expires_at"], code="COORD_EXPIRY_INVALID") <= now:
        raise CoordinationError("COORD_EXPIRY_INVALID", "Admission expiry must be later than recorded_at.", request["expires_at"])
    request_sha256 = _hash_value(request)
    replay = _existing_receipt(root, operation_id, request_sha256)
    if replay is not None:
        return replay
    workspace_state, workspace_bytes, state, state_bytes = _workspace_context(root)
    if not _phase_is_open(workspace_state, request["phase_id"]):
        raise CoordinationError("COORD_PHASE_NOT_OPEN", "Admission phase must be registered with ACTIVE or OPEN status.", request["phase_id"])
    _require_phase_control_binding(root, workspace_state, request)
    active_same = [item for item in state["active_admissions"] if item["admission_id"] == request["admission_id"]]
    if active_same:
        if active_same[0].get("request_sha256") != request_sha256:
            raise CoordinationError("COORD_ADMISSION_REPLAY_CONFLICT", "admission_id is active with a different request.", request["admission_id"])
        return {
            "status": "PASS", "operation": "admit", "mode": "READ_ONLY", "outcome": "ADMITTED",
            "operation_id": operation_id, "plan_sha256": None, "idempotent": True, "writes_performed": False,
            "planned_changes": [], "details": {"admission": active_same[0], "conflicts": []},
        }
    queued_same = [item for item in state["queue"] if item["request"]["admission_id"] == request["admission_id"]]
    if queued_same and queued_same[0]["request_sha256"] != request_sha256:
        raise CoordinationError("COORD_ADMISSION_REPLAY_CONFLICT", "admission_id is queued with a different request.", request["admission_id"])

    conflicts = _quarantine_conflicts(request, state)
    conflicts.extend(_active_conflicts(request, state["active_admissions"]))
    conflicts.extend(_queue_order_conflicts(request, state["queue"]))
    conflicts = sorted(conflicts, key=lambda item: (item["conflict_class"], str(item["held_admission_id"]), item["requested_id"], item["held_id"]))
    if conflicts:
        queueable = all(item["conflict_class"] in {"CAPABILITY", "QUEUE_ORDER"} and item["relationship"] == "QUEUED" for item in conflicts)
        if not queueable:
            return {
                "status": "BLOCKED", "operation": "admit", "mode": "READ_ONLY", "outcome": "BLOCKED_CONFLICT",
                "operation_id": operation_id, "plan_sha256": None, "idempotent": False, "writes_performed": False,
                "planned_changes": [], "details": {"admission_id": request["admission_id"], "conflicts": conflicts},
            }
        if queued_same:
            return {
                "status": "QUEUED", "operation": "admit", "mode": "READ_ONLY", "outcome": "QUEUED",
                "operation_id": operation_id, "plan_sha256": None, "idempotent": True, "writes_performed": False,
                "planned_changes": [], "details": {"admission_id": request["admission_id"], "conflicts": conflicts},
            }
        next_state = copy.deepcopy(state)
        if len(next_state["queue"]) >= 1024:
            raise CoordinationError("COORD_QUEUE_CAPACITY", "Coordination queue reached its closed capacity.")
        next_state["queue"].append(
            {"queued_at": recorded_at, "request_sha256": request_sha256, "request": request, "conflicts": conflicts}
        )
        outcome = "QUEUED"
        event_kind = "ADMISSION_QUEUED"
        details = {"admission_id": request["admission_id"], "conflicts": conflicts, "fencing_tokens": []}
    else:
        next_state = copy.deepcopy(state)
        next_state["queue"] = [item for item in next_state["queue"] if item["request"]["admission_id"] != request["admission_id"]]
        tokens = _increment_grant_domains(next_state, request)
        admission = {
            **request,
            "request_sha256": request_sha256,
            "granted_at": recorded_at,
            "fencing_tokens": tokens,
            "requires_explicit_reconcile_on_expiry": any(
                item["mode"] != "SHARED" and not item["fenceable"] for item in request["capabilities"]
            ),
        }
        next_state["active_admissions"].append(admission)
        next_state["active_admissions"].sort(key=lambda item: item["admission_id"])
        outcome = "ADMITTED"
        event_kind = "ADMISSION_GRANTED"
        details = {"admission_id": request["admission_id"], "conflicts": [], "fencing_tokens": tokens}
    prepared = _prepare_mutation(
        root,
        workspace_state=workspace_state,
        workspace_bytes=workspace_bytes,
        state_before=state,
        state_bytes=state_bytes,
        state_after=next_state,
        operation="admit",
        operation_id=operation_id,
        event_kind=event_kind,
        recorded_at=recorded_at,
        actor=request["actor"],
        phase_id=request["phase_id"],
        admission_id=request["admission_id"],
        request_sha256=request_sha256,
        outcome=outcome,
        details=details,
        evidence_refs=request["evidence_refs"],
    )
    return _finish_mutation(
        root,
        prepared=prepared,
        workspace_bytes=workspace_bytes,
        state_bytes=state_bytes,
        operation="admit",
        operation_id=operation_id,
        apply=apply,
        expected_plan_sha256=expected_plan_sha256,
    )


def _active_admission(state: Mapping[str, Any], admission_id: str) -> dict[str, Any]:
    rows = [item for item in state["active_admissions"] if item["admission_id"] == admission_id]
    if len(rows) != 1:
        raise CoordinationError("COORD_ADMISSION_NOT_ACTIVE", "Exactly one active Admission is required.", admission_id)
    return rows[0]


def _simple_request_hash(operation: str, payload: Mapping[str, Any]) -> str:
    return _hash_value({"operation": operation, **dict(payload)})


def renew(
    root: Path,
    *,
    admission_id: str,
    actor_id: str,
    expires_at: str,
    operation_id: str,
    recorded_at: str,
    apply: bool = False,
    expected_plan_sha256: str | None = None,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    now = _parse_time(recorded_at)
    new_expiry = _parse_time(expires_at, code="COORD_EXPIRY_INVALID")
    payload = {"admission_id": _require_id(admission_id, "admission_id"), "actor_id": _require_id(actor_id, "actor_id"), "expires_at": expires_at}
    request_sha = _simple_request_hash("renew", payload)
    replay = _existing_receipt(root, operation_id, request_sha)
    if replay is not None:
        return replay
    workspace_state, workspace_bytes, state, state_bytes = _workspace_context(root)
    admission = _active_admission(state, admission_id)
    if admission["actor"]["id"] != actor_id:
        raise CoordinationError("COORD_ACTOR_MISMATCH", "Only the owning actor can renew an Admission.", actor_id)
    _require_phase_control_binding(root, workspace_state, admission)
    if _parse_time(admission["expires_at"], code="COORD_EXPIRY_INVALID") <= now:
        raise CoordinationError("COORD_LEASE_EXPIRED", "An expired Admission cannot be renewed; reap and reacquire it.", admission_id)
    if new_expiry <= now or new_expiry <= _parse_time(admission["expires_at"], code="COORD_EXPIRY_INVALID"):
        raise CoordinationError("COORD_EXPIRY_INVALID", "Renewal must extend the current expiry beyond recorded_at.", expires_at)
    next_state = copy.deepcopy(state)
    next_admission = _active_admission(next_state, admission_id)
    next_admission["expires_at"] = expires_at
    details = {"admission_id": admission_id, "previous_expires_at": admission["expires_at"], "expires_at": expires_at, "fencing_tokens": admission["fencing_tokens"]}
    prepared = _prepare_mutation(
        root, workspace_state=workspace_state, workspace_bytes=workspace_bytes, state_before=state, state_bytes=state_bytes,
        state_after=next_state, operation="renew", operation_id=operation_id, event_kind="ADMISSION_RENEWED",
        recorded_at=recorded_at, actor=admission["actor"], phase_id=admission["phase_id"], admission_id=admission_id,
        request_sha256=request_sha, outcome="RENEWED", details=details, evidence_refs=admission["evidence_refs"],
    )
    return _finish_mutation(root, prepared=prepared, workspace_bytes=workspace_bytes, state_bytes=state_bytes, operation="renew", operation_id=operation_id, apply=apply, expected_plan_sha256=expected_plan_sha256)


def release(
    root: Path,
    *,
    admission_id: str,
    actor_id: str,
    operation_id: str,
    recorded_at: str,
    evidence_refs: Sequence[str],
    apply: bool = False,
    expected_plan_sha256: str | None = None,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    now = _parse_time(recorded_at)
    payload = {"admission_id": _require_id(admission_id, "admission_id"), "actor_id": _require_id(actor_id, "actor_id"), "evidence_refs": list(evidence_refs)}
    request_sha = _simple_request_hash("release", payload)
    replay = _existing_receipt(root, operation_id, request_sha)
    if replay is not None:
        return replay
    workspace_state, workspace_bytes, state, state_bytes = _workspace_context(root)
    admission = _active_admission(state, admission_id)
    if admission["actor"]["id"] != actor_id:
        raise CoordinationError("COORD_ACTOR_MISMATCH", "Only the owning actor can release an Admission.", actor_id)
    if _parse_time(admission["expires_at"], code="COORD_EXPIRY_INVALID") <= now and admission["requires_explicit_reconcile_on_expiry"]:
        raise CoordinationError("COORD_EXPIRED_RECONCILE_REQUIRED", "An expired non-fenceable Admission must be reaped into quarantine before reconcile.", admission_id)
    next_state = copy.deepcopy(state)
    _bump_tokens(next_state, admission)
    next_state["active_admissions"] = [item for item in next_state["active_admissions"] if item["admission_id"] != admission_id]
    details = {"admission_id": admission_id, "released_tokens": admission["fencing_tokens"]}
    prepared = _prepare_mutation(
        root, workspace_state=workspace_state, workspace_bytes=workspace_bytes, state_before=state, state_bytes=state_bytes,
        state_after=next_state, operation="release", operation_id=operation_id, event_kind="ADMISSION_RELEASED",
        recorded_at=recorded_at, actor=admission["actor"], phase_id=admission["phase_id"], admission_id=admission_id,
        request_sha256=request_sha, outcome="RELEASED", details=details, evidence_refs=list(evidence_refs),
    )
    return _finish_mutation(root, prepared=prepared, workspace_bytes=workspace_bytes, state_bytes=state_bytes, operation="release", operation_id=operation_id, apply=apply, expected_plan_sha256=expected_plan_sha256)


def reap_expired(
    root: Path,
    *,
    actor: Mapping[str, str],
    operation_id: str,
    recorded_at: str,
    evidence_refs: Sequence[str],
    apply: bool = False,
    expected_plan_sha256: str | None = None,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    now = _parse_time(recorded_at)
    normalized_actor = _require_actor(actor)
    payload = {"actor": normalized_actor, "recorded_at": recorded_at, "evidence_refs": list(evidence_refs)}
    request_sha = _simple_request_hash("reap-expired", payload)
    replay = _existing_receipt(root, operation_id, request_sha)
    if replay is not None:
        return replay
    workspace_state, workspace_bytes, state, state_bytes = _workspace_context(root)
    expired = _expired_admissions(state, now)
    if not expired:
        return {
            "status": "PASS", "operation": "reap-expired", "mode": "READ_ONLY", "outcome": "NO_CHANGES",
            "operation_id": operation_id, "plan_sha256": None, "idempotent": True, "writes_performed": False,
            "planned_changes": [], "details": {"expired_admission_ids": [], "quarantine_ids": []},
        }
    next_state = copy.deepcopy(state)
    expired_ids = {item["admission_id"] for item in expired}
    quarantine_ids: list[str] = []
    for admission in expired:
        _bump_tokens(next_state, admission)
        if admission["requires_explicit_reconcile_on_expiry"]:
            quarantine_id = "QEXP-" + hashlib.sha256(f"{admission['admission_id']}:{recorded_at}".encode("utf-8")).hexdigest().upper()[:24]
            next_state["quarantines"].append(
                {
                    "quarantine_id": quarantine_id,
                    "admission_id": admission["admission_id"],
                    "phase_id": admission["phase_id"],
                    "reason": "NON_FENCEABLE_LEASE_EXPIRED",
                    "recorded_at": recorded_at,
                    "domains": _quarantine_domains(admission),
                    "evidence_refs": list(evidence_refs),
                }
            )
            quarantine_ids.append(quarantine_id)
    next_state["active_admissions"] = [item for item in next_state["active_admissions"] if item["admission_id"] not in expired_ids]
    next_state["quarantines"].sort(key=lambda item: item["quarantine_id"])
    details = {"expired_admission_ids": sorted(expired_ids), "quarantine_ids": sorted(quarantine_ids)}
    prepared = _prepare_mutation(
        root, workspace_state=workspace_state, workspace_bytes=workspace_bytes, state_before=state, state_bytes=state_bytes,
        state_after=next_state, operation="reap-expired", operation_id=operation_id, event_kind="LEASES_EXPIRED",
        recorded_at=recorded_at, actor=normalized_actor, phase_id=None, admission_id=None,
        request_sha256=request_sha, outcome="EXPIRED_REAPED", details=details, evidence_refs=list(evidence_refs),
    )
    return _finish_mutation(root, prepared=prepared, workspace_bytes=workspace_bytes, state_bytes=state_bytes, operation="reap-expired", operation_id=operation_id, apply=apply, expected_plan_sha256=expected_plan_sha256)


def record_unknown(
    root: Path,
    *,
    admission_id: str,
    actor_id: str,
    affected_scope: str,
    operation_id: str,
    recorded_at: str,
    evidence_refs: Sequence[str],
    apply: bool = False,
    expected_plan_sha256: str | None = None,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    _parse_time(recorded_at)
    if affected_scope not in {"RESOURCE_DOMAINS", "WORKSPACE_AUTHORITY"}:
        raise CoordinationError("COORD_UNKNOWN_SCOPE_INVALID", "Unknown side effects must identify RESOURCE_DOMAINS or WORKSPACE_AUTHORITY.", affected_scope)
    payload = {"admission_id": _require_id(admission_id, "admission_id"), "actor_id": _require_id(actor_id, "actor_id"), "affected_scope": affected_scope, "evidence_refs": list(evidence_refs)}
    request_sha = _simple_request_hash("record-unknown", payload)
    replay = _existing_receipt(root, operation_id, request_sha)
    if replay is not None:
        return replay
    workspace_state, workspace_bytes, state, state_bytes = _workspace_context(root)
    admission = _active_admission(state, admission_id)
    if admission["actor"]["id"] != actor_id:
        raise CoordinationError("COORD_ACTOR_MISMATCH", "Only the owning actor can report its external result as UNKNOWN.", actor_id)
    if not evidence_refs:
        raise CoordinationError("COORD_EVIDENCE_INVALID", "UNKNOWN requires at least one direct evidence reference.")
    next_state = copy.deepcopy(state)
    _bump_tokens(next_state, admission)
    next_state["active_admissions"] = [item for item in next_state["active_admissions"] if item["admission_id"] != admission_id]
    quarantine_id = "QUNK-" + hashlib.sha256(f"{admission_id}:{recorded_at}".encode("utf-8")).hexdigest().upper()[:24]
    if affected_scope == "WORKSPACE_AUTHORITY":
        if next_state["workspace_quarantine"] is not None:
            raise CoordinationError("COORD_WORKSPACE_QUARANTINED", "Workspace authority is already quarantined.")
        next_state["workspace_quarantine"] = {
            "quarantine_id": quarantine_id,
            "admission_id": admission_id,
            "phase_id": admission["phase_id"],
            "reason": "WORKSPACE_AUTHORITY_UNKNOWN",
            "recorded_at": recorded_at,
            "evidence_refs": list(evidence_refs),
        }
    else:
        next_state["quarantines"].append(
            {
                "quarantine_id": quarantine_id,
                "admission_id": admission_id,
                "phase_id": admission["phase_id"],
                "reason": "EXTERNAL_SIDE_EFFECT_UNKNOWN",
                "recorded_at": recorded_at,
                "domains": _quarantine_domains(admission),
                "evidence_refs": list(evidence_refs),
            }
        )
        next_state["quarantines"].sort(key=lambda item: item["quarantine_id"])
    details = {"admission_id": admission_id, "affected_scope": affected_scope, "quarantine_id": quarantine_id}
    prepared = _prepare_mutation(
        root, workspace_state=workspace_state, workspace_bytes=workspace_bytes, state_before=state, state_bytes=state_bytes,
        state_after=next_state, operation="record-unknown", operation_id=operation_id, event_kind="EXTERNAL_SIDE_EFFECT_UNKNOWN",
        recorded_at=recorded_at, actor=admission["actor"], phase_id=admission["phase_id"], admission_id=admission_id,
        request_sha256=request_sha, outcome="QUARANTINED", details=details, evidence_refs=list(evidence_refs),
    )
    return _finish_mutation(root, prepared=prepared, workspace_bytes=workspace_bytes, state_bytes=state_bytes, operation="record-unknown", operation_id=operation_id, apply=apply, expected_plan_sha256=expected_plan_sha256)


def reconcile_quarantine(
    root: Path,
    *,
    quarantine_id: str,
    resolution: str,
    actor: Mapping[str, str],
    authorization_ref: str,
    operation_id: str,
    recorded_at: str,
    evidence_refs: Sequence[str],
    apply: bool = False,
    expected_plan_sha256: str | None = None,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    _parse_time(recorded_at)
    normalized_actor = _require_actor(actor)
    quarantine_id = _require_id(quarantine_id, "quarantine_id")
    if resolution not in RECONCILE_RESOLUTIONS:
        raise CoordinationError("COORD_RECONCILE_RESOLUTION_INVALID", "Unknown quarantine reconciliation resolution.", resolution)
    if not authorization_ref or not evidence_refs:
        raise CoordinationError("COORD_RECONCILE_EVIDENCE_REQUIRED", "Reconcile requires authorization and direct evidence.")
    payload = {"quarantine_id": quarantine_id, "resolution": resolution, "actor": normalized_actor, "authorization_ref": authorization_ref, "evidence_refs": list(evidence_refs)}
    request_sha = _simple_request_hash("reconcile", payload)
    replay = _existing_receipt(root, operation_id, request_sha)
    if replay is not None:
        return replay
    workspace_state, workspace_bytes, state, state_bytes = _workspace_context(root)
    next_state = copy.deepcopy(state)
    admission_id: str | None = None
    phase_id: str | None = None
    if next_state["workspace_quarantine"] is not None and next_state["workspace_quarantine"]["quarantine_id"] == quarantine_id:
        admission_id = next_state["workspace_quarantine"]["admission_id"]
        phase_id = next_state["workspace_quarantine"]["phase_id"]
        next_state["workspace_quarantine"] = None
    else:
        matches = [item for item in next_state["quarantines"] if item["quarantine_id"] == quarantine_id]
        if len(matches) != 1:
            raise CoordinationError("COORD_QUARANTINE_NOT_FOUND", "Exactly one quarantine record is required.", quarantine_id)
        admission_id = matches[0]["admission_id"]
        phase_id = matches[0]["phase_id"]
        next_state["quarantines"] = [item for item in next_state["quarantines"] if item["quarantine_id"] != quarantine_id]
    details = {"quarantine_id": quarantine_id, "admission_id": admission_id, "resolution": resolution, "authorization_ref": authorization_ref}
    prepared = _prepare_mutation(
        root, workspace_state=workspace_state, workspace_bytes=workspace_bytes, state_before=state, state_bytes=state_bytes,
        state_after=next_state, operation="reconcile", operation_id=operation_id, event_kind="QUARANTINE_RECONCILED",
        recorded_at=recorded_at, actor=normalized_actor, phase_id=phase_id, admission_id=admission_id,
        request_sha256=request_sha, outcome="RECONCILED", details=details, evidence_refs=list(evidence_refs),
    )
    return _finish_mutation(root, prepared=prepared, workspace_bytes=workspace_bytes, state_bytes=state_bytes, operation="reconcile", operation_id=operation_id, apply=apply, expected_plan_sha256=expected_plan_sha256)


def verify_quarantine_reconciliation_evidence(
    root: Path,
    *,
    phase_id: str,
    admission_id: str,
    evidence_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Verify exact committed reconcile events without loading coordination history wholesale."""

    root = root.resolve(strict=True)
    phase_id = _require_id(phase_id, "phase_id")
    admission_id = _require_id(admission_id, "admission_id")
    _, _, state, _ = _workspace_context(root)
    transaction = inspect_transaction_state(root, COORDINATION_TRANSACTION_PROFILE)
    issues: list[dict[str, Any]] = []
    if transaction["status"] != "PASS":
        issues.append({"code": "COORD_RECONCILE_TRANSACTION_INCOMPLETE", "detail": transaction["findings"]})
    normalized_rows: list[dict[str, str]] = []
    for raw in evidence_rows:
        if not isinstance(raw, Mapping):
            raise CoordinationError("COORD_RECONCILE_EVIDENCE_INVALID", "Reconcile evidence rows must be objects.")
        quarantine_id = _require_id(raw.get("quarantine_id"), "quarantine_id")
        relative = str(raw.get("event_path", "")).replace("\\", "/")
        expected_hash = _require_sha256(raw.get("event_sha256"), "event_sha256")
        if not re.fullmatch(r"runtime/workspace_coordination_events/[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.json", relative):
            raise CoordinationError("COORD_RECONCILE_EVIDENCE_INVALID", "Reconcile evidence must name one direct coordination event file.", relative)
        normalized_rows.append({"quarantine_id": quarantine_id, "event_path": relative, "event_sha256": expected_hash})
    if not normalized_rows or normalized_rows != sorted(normalized_rows, key=lambda item: item["quarantine_id"]):
        raise CoordinationError("COORD_RECONCILE_EVIDENCE_INVALID", "Reconcile evidence must be non-empty and sorted by quarantine_id.")
    if len({item["quarantine_id"] for item in normalized_rows}) != len(normalized_rows):
        raise CoordinationError("COORD_RECONCILE_EVIDENCE_INVALID", "Reconcile evidence quarantine IDs must be unique.")
    live_ids = {item["quarantine_id"] for item in state["quarantines"]}
    if state["workspace_quarantine"] is not None:
        live_ids.add(state["workspace_quarantine"]["quarantine_id"])
    for row in normalized_rows:
        quarantine_id = row["quarantine_id"]
        if quarantine_id in live_ids:
            issues.append({"code": "COORD_QUARANTINE_STILL_ACTIVE", "quarantine_id": quarantine_id})
            continue
        event_path = root / Path(row["event_path"])
        if not event_path.is_file() or event_path.is_symlink():
            issues.append({"code": "COORD_RECONCILE_EVENT_MISSING", "path": row["event_path"]})
            continue
        event_bytes = event_path.read_bytes()
        if sha256_bytes(event_bytes) != row["event_sha256"]:
            issues.append({"code": "COORD_RECONCILE_EVENT_DRIFT", "path": row["event_path"]})
            continue
        event = _read_json(event_path, "COORD_RECONCILE_EVENT_INVALID")
        if (
            event.get("event_kind") != "QUARANTINE_RECONCILED"
            or event.get("outcome") != "RECONCILED"
            or event.get("phase_id") != phase_id
            or event.get("admission_id") != admission_id
            or event.get("details", {}).get("quarantine_id") != quarantine_id
            or event.get("details", {}).get("admission_id") != admission_id
        ):
            issues.append({"code": "COORD_RECONCILE_EVENT_MISMATCH", "path": row["event_path"], "quarantine_id": quarantine_id})
            continue
        operation_id = event.get("operation_id")
        expected_event_path = (EVENTS_RELATIVE / f"{operation_id}.json").as_posix()
        journal_path = root / COORDINATION_TRANSACTION_PROFILE.journal_directory_relative / f"{operation_id}.json"
        if row["event_path"] != expected_event_path or not journal_path.is_file():
            issues.append({"code": "COORD_RECONCILE_JOURNAL_MISSING", "path": str(journal_path.relative_to(root)).replace("\\", "/")})
            continue
        journal = _read_json(journal_path, "COORD_RECONCILE_JOURNAL_INVALID")
        observed_outputs = {
            item.get("path"): item.get("sha256")
            for item in journal.get("observed_outputs", [])
            if isinstance(item, dict)
        }
        if journal.get("status") != "COMMITTED" or observed_outputs.get(row["event_path"]) != row["event_sha256"]:
            issues.append({"code": "COORD_RECONCILE_JOURNAL_MISMATCH", "path": str(journal_path.relative_to(root)).replace("\\", "/")})
    return {
        "status": "BLOCKED" if issues else "PASS",
        "operation": "verify-quarantine-reconciliation",
        "mode": "READ_ONLY",
        "writes_performed": False,
        "phase_id": phase_id,
        "admission_id": admission_id,
        "verified_quarantine_ids": [item["quarantine_id"] for item in normalized_rows] if not issues else [],
        "issues": issues,
    }


def phase_close_gate(root: Path, phase_id: str) -> dict[str, Any]:
    """Return exact coordination blockers before an OPEN/ACTIVE Phase can close."""

    root = root.resolve(strict=True)
    phase_id = _require_id(phase_id, "phase_id")
    _, _, state, _ = _workspace_context(root)
    blockers: list[dict[str, Any]] = []
    for admission in state["active_admissions"]:
        if admission["phase_id"] == phase_id:
            blockers.append({"kind": "ACTIVE_ADMISSION", "id": admission["admission_id"]})
    for row in state["queue"]:
        request = row["request"]
        if request["phase_id"] == phase_id:
            blockers.append({"kind": "QUEUED_ADMISSION", "id": request["admission_id"]})
    for quarantine in state["quarantines"]:
        if quarantine["phase_id"] == phase_id:
            blockers.append({"kind": "RESOURCE_QUARANTINE", "id": quarantine["quarantine_id"]})
    if state["workspace_quarantine"] is not None:
        blockers.append({"kind": "WORKSPACE_QUARANTINE", "id": state["workspace_quarantine"]["quarantine_id"]})
    blockers.sort(key=lambda item: (item["kind"], item["id"]))
    return {
        "status": "BLOCKED" if blockers else "PASS",
        "phase_id": phase_id,
        "blockers": blockers,
        "writes_performed": False,
    }


def verify_admission(
    root: Path,
    *,
    admission_id: str,
    phase_id: str,
    actor_id: str,
    fencing_tokens: Sequence[Mapping[str, Any]],
    observed_at: str,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    now = _parse_time(observed_at)
    workspace_state, _, state, _ = _workspace_context(root)
    if not _phase_is_open(workspace_state, phase_id):
        return {"status": "BLOCKED", "operation": "verify", "writes_performed": False, "issues": [{"code": "COORD_PHASE_NOT_OPEN", "phase_id": phase_id}]}
    try:
        admission = _active_admission(state, admission_id)
    except CoordinationError as exc:
        return {"status": "BLOCKED", "operation": "verify", "writes_performed": False, "issues": [{"code": exc.code, "detail": exc.detail}]}
    issues: list[dict[str, Any]] = []
    if admission["phase_id"] != phase_id:
        issues.append({"code": "COORD_PHASE_MISMATCH", "expected": admission["phase_id"], "observed": phase_id})
    if admission["actor"]["id"] != actor_id:
        issues.append({"code": "COORD_ACTOR_MISMATCH", "expected": admission["actor"]["id"], "observed": actor_id})
    try:
        _require_phase_control_binding(root, workspace_state, admission)
    except CoordinationError as exc:
        issues.append({"code": exc.code, "detail": exc.detail})
    issues.extend(_physical_identity_issues(root, admission))
    if _parse_time(admission["expires_at"], code="COORD_EXPIRY_INVALID") <= now:
        issues.append({"code": "COORD_LEASE_EXPIRED", "expires_at": admission["expires_at"], "observed_at": observed_at})
    expected_tokens = sorted(admission["fencing_tokens"], key=lambda item: item["domain_id"])
    observed_tokens = sorted(
        [{"domain_id": _require_id(item.get("domain_id"), "domain_id"), "epoch": int(item.get("epoch"))} for item in fencing_tokens],
        key=lambda item: item["domain_id"],
    )
    if observed_tokens != expected_tokens:
        issues.append({"code": "COORD_FENCING_TOKEN_MISMATCH", "expected": expected_tokens, "observed": observed_tokens})
    epochs = {item["domain_id"]: item["epoch"] for item in state["fencing_domains"]}
    stale = [token for token in expected_tokens if epochs.get(token["domain_id"]) != token["epoch"]]
    if stale:
        issues.append({"code": "COORD_FENCING_TOKEN_STALE", "tokens": stale})
    return {
        "status": "BLOCKED" if issues else "PASS",
        "operation": "verify",
        "mode": "READ_ONLY",
        "writes_performed": False,
        "admission_id": admission_id,
        "phase_id": phase_id,
        "issues": issues,
        "non_fenceable_external_capability": any(item["mode"] != "SHARED" and not item["fenceable"] for item in admission["capabilities"]),
        "bypass_writes_prevented": False,
    }


def inspect(root: Path, *, observed_at: str) -> dict[str, Any]:
    root = root.resolve(strict=True)
    now = _parse_time(observed_at)
    workspace_state, _, state, state_bytes = _workspace_context(root)
    expired = [item["admission_id"] for item in _expired_admissions(state, now)]
    transaction = inspect_transaction_state(root, COORDINATION_TRANSACTION_PROFILE)
    issues = []
    if expired:
        issues.append({"code": "COORD_EXPIRED_RECONCILE_REQUIRED", "admission_ids": expired})
    if state["workspace_quarantine"] is not None:
        issues.append({"code": "COORD_WORKSPACE_QUARANTINED", "quarantine_id": state["workspace_quarantine"]["quarantine_id"]})
    if state["quarantines"]:
        issues.append({"code": "COORD_RESOURCE_QUARANTINES", "quarantine_ids": [item["quarantine_id"] for item in state["quarantines"]]})
    if transaction["status"] != "PASS":
        issues.extend(transaction["findings"])
    return {
        "status": "WARNING" if issues else "PASS",
        "operation": "inspect",
        "mode": "READ_ONLY",
        "workspace": str(root),
        "workspace_id": workspace_state["project_id"],
        "profile": "resource_admission",
        "coordination_sha256": sha256_bytes(state_bytes),
        "revision": state["revision"],
        "counts": {
            "active_admissions": len(state["active_admissions"]),
            "queued": len(state["queue"]),
            "quarantines": len(state["quarantines"]),
            "fencing_domains": len(state["fencing_domains"]),
        },
        "issues": issues,
        "transaction_recovery": transaction,
        "writes_performed": False,
        "background_service_created": False,
    }


def _load_request(path: str) -> dict[str, Any]:
    return _read_json(Path(path).resolve(strict=True), "COORD_REQUEST_INVALID")


def _tokens(values: Iterable[str]) -> list[dict[str, Any]]:
    rows = []
    for value in values:
        if "=" not in value:
            raise CoordinationError("COORD_FENCING_TOKEN_INVALID", "Fencing tokens use DOMAIN_ID=EPOCH.", value)
        domain_id, raw_epoch = value.rsplit("=", 1)
        try:
            epoch = int(raw_epoch)
        except ValueError as exc:
            raise CoordinationError("COORD_FENCING_TOKEN_INVALID", "Fencing epoch must be an integer.", value) from exc
        if epoch < 1:
            raise CoordinationError("COORD_FENCING_TOKEN_INVALID", "Fencing epoch must be positive.", value)
        rows.append({"domain_id": _require_id(domain_id, "domain_id"), "epoch": epoch})
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MALTS resource Admission, capability queue, lease, fencing, and reconcile runtime.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--workspace", required=True)
    inspect_parser.add_argument("--timestamp", default=None)

    admit_parser = subparsers.add_parser("admit")
    admit_parser.add_argument("--workspace", required=True)
    admit_parser.add_argument("--request", required=True)
    admit_parser.add_argument("--operation-id", required=True)
    admit_parser.add_argument("--timestamp", required=True)
    admit_parser.add_argument("--expected-plan-sha256")
    admit_parser.add_argument("--apply", action="store_true")

    renew_parser = subparsers.add_parser("renew")
    renew_parser.add_argument("--workspace", required=True)
    renew_parser.add_argument("--admission-id", required=True)
    renew_parser.add_argument("--actor-id", required=True)
    renew_parser.add_argument("--expires-at", required=True)
    renew_parser.add_argument("--operation-id", required=True)
    renew_parser.add_argument("--timestamp", required=True)
    renew_parser.add_argument("--expected-plan-sha256")
    renew_parser.add_argument("--apply", action="store_true")

    release_parser = subparsers.add_parser("release")
    release_parser.add_argument("--workspace", required=True)
    release_parser.add_argument("--admission-id", required=True)
    release_parser.add_argument("--actor-id", required=True)
    release_parser.add_argument("--operation-id", required=True)
    release_parser.add_argument("--timestamp", required=True)
    release_parser.add_argument("--evidence-ref", action="append", default=[])
    release_parser.add_argument("--expected-plan-sha256")
    release_parser.add_argument("--apply", action="store_true")

    reap_parser = subparsers.add_parser("reap-expired")
    reap_parser.add_argument("--workspace", required=True)
    reap_parser.add_argument("--actor-kind", choices=sorted(ACTOR_KINDS), required=True)
    reap_parser.add_argument("--actor-id", required=True)
    reap_parser.add_argument("--operation-id", required=True)
    reap_parser.add_argument("--timestamp", required=True)
    reap_parser.add_argument("--evidence-ref", action="append", default=[])
    reap_parser.add_argument("--expected-plan-sha256")
    reap_parser.add_argument("--apply", action="store_true")

    unknown_parser = subparsers.add_parser("record-unknown")
    unknown_parser.add_argument("--workspace", required=True)
    unknown_parser.add_argument("--admission-id", required=True)
    unknown_parser.add_argument("--actor-id", required=True)
    unknown_parser.add_argument("--affected-scope", choices=["RESOURCE_DOMAINS", "WORKSPACE_AUTHORITY"], required=True)
    unknown_parser.add_argument("--operation-id", required=True)
    unknown_parser.add_argument("--timestamp", required=True)
    unknown_parser.add_argument("--evidence-ref", action="append", default=[])
    unknown_parser.add_argument("--expected-plan-sha256")
    unknown_parser.add_argument("--apply", action="store_true")

    reconcile_parser = subparsers.add_parser("reconcile")
    reconcile_parser.add_argument("--workspace", required=True)
    reconcile_parser.add_argument("--quarantine-id", required=True)
    reconcile_parser.add_argument("--resolution", choices=sorted(RECONCILE_RESOLUTIONS), required=True)
    reconcile_parser.add_argument("--actor-kind", choices=sorted(ACTOR_KINDS), required=True)
    reconcile_parser.add_argument("--actor-id", required=True)
    reconcile_parser.add_argument("--authorization-ref", required=True)
    reconcile_parser.add_argument("--operation-id", required=True)
    reconcile_parser.add_argument("--timestamp", required=True)
    reconcile_parser.add_argument("--evidence-ref", action="append", default=[])
    reconcile_parser.add_argument("--expected-plan-sha256")
    reconcile_parser.add_argument("--apply", action="store_true")

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--workspace", required=True)
    verify_parser.add_argument("--admission-id", required=True)
    verify_parser.add_argument("--phase-id", required=True)
    verify_parser.add_argument("--actor-id", required=True)
    verify_parser.add_argument("--token", action="append", default=[])
    verify_parser.add_argument("--timestamp", required=True)

    recover_parser = subparsers.add_parser("recover")
    recover_parser.add_argument("--workspace", required=True)
    recover_parser.add_argument("--operation-id", required=True)
    recover_parser.add_argument("--expected-journal-sha256", required=True)
    recover_parser.add_argument("--apply", action="store_true")
    return parser


def _dispatch(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.workspace).resolve(strict=True)
    if args.command == "inspect":
        return inspect(root, observed_at=args.timestamp or _timestamp())
    if args.command == "admit":
        return admit(root, _load_request(args.request), operation_id=args.operation_id, recorded_at=args.timestamp, apply=args.apply, expected_plan_sha256=args.expected_plan_sha256)
    if args.command == "renew":
        return renew(root, admission_id=args.admission_id, actor_id=args.actor_id, expires_at=args.expires_at, operation_id=args.operation_id, recorded_at=args.timestamp, apply=args.apply, expected_plan_sha256=args.expected_plan_sha256)
    if args.command == "release":
        return release(root, admission_id=args.admission_id, actor_id=args.actor_id, operation_id=args.operation_id, recorded_at=args.timestamp, evidence_refs=args.evidence_ref, apply=args.apply, expected_plan_sha256=args.expected_plan_sha256)
    if args.command == "reap-expired":
        return reap_expired(root, actor={"kind": args.actor_kind, "id": args.actor_id}, operation_id=args.operation_id, recorded_at=args.timestamp, evidence_refs=args.evidence_ref, apply=args.apply, expected_plan_sha256=args.expected_plan_sha256)
    if args.command == "record-unknown":
        return record_unknown(root, admission_id=args.admission_id, actor_id=args.actor_id, affected_scope=args.affected_scope, operation_id=args.operation_id, recorded_at=args.timestamp, evidence_refs=args.evidence_ref, apply=args.apply, expected_plan_sha256=args.expected_plan_sha256)
    if args.command == "reconcile":
        return reconcile_quarantine(root, quarantine_id=args.quarantine_id, resolution=args.resolution, actor={"kind": args.actor_kind, "id": args.actor_id}, authorization_ref=args.authorization_ref, operation_id=args.operation_id, recorded_at=args.timestamp, evidence_refs=args.evidence_ref, apply=args.apply, expected_plan_sha256=args.expected_plan_sha256)
    if args.command == "verify":
        return verify_admission(root, admission_id=args.admission_id, phase_id=args.phase_id, actor_id=args.actor_id, fencing_tokens=_tokens(args.token), observed_at=args.timestamp)
    if args.command == "recover":
        return recover_transaction(root, operation_id=args.operation_id, expected_journal_sha256=args.expected_journal_sha256, apply=args.apply, profile=COORDINATION_TRANSACTION_PROFILE)
    raise CoordinationError("COORD_COMMAND_INVALID", "Unknown coordination command.", args.command)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = _dispatch(args)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=False))
        return 2 if result.get("status") == "BLOCKED" else 0
    except (CoordinationError, LocatorError, TransactionError) as exc:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "operation": getattr(args, "command", None),
                    "mode": "APPLY" if getattr(args, "apply", False) else "READ_ONLY_OR_DRY_RUN",
                    "error_code": exc.code,
                    "message": exc.message,
                    "detail": exc.detail,
                    "writes_performed": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
