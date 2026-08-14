#!/usr/bin/env python3
"""MALTS Result Contract v1-to-v2 migration planner (pure, deterministic).

This module implements the frozen `migrate-result-contract-v1-to-v2` semantics.
It builds the v2 revision one, the sequence-one LEGACY_SNAPSHOT_IMPORTED event,
and the resulting lineage projection without modifying the v1 source file and
without fabricating typed history. Workspace orchestration (transaction, phase
bindings, receipts) remains the caller's responsibility in `long_workspace.py`.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import malts_user_contracts as contracts
import result_controller as controller


MALTS_ROOT = Path(__file__).resolve().parents[1]
INVARIANT_SET_ID = "malts-v1.3.0-lifecycle-invariants"
V1_EXECUTION_TERMINAL = {"DONE", "PARTIAL", "BLOCKED", "FAILED"}
V2_TASK_STATUS_BY_V1_TERMINAL = {"DONE": "DONE", "PARTIAL": "PARTIAL", "BLOCKED": "BLOCKED", "FAILED": "FAILED"}


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_payload(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def invariant_source_sha256(malts_root: Path) -> str:
    path = malts_root / "tools" / "lifecycle_invariants.json"
    if not path.is_file():
        raise ValueError("Canonical invariant source is missing: " + str(path))
    return sha256_payload(path.read_bytes())


def _translate_budgets(v1_budgets: dict[str, Any]) -> dict[str, Any]:
    translated = copy.deepcopy(v1_budgets)
    for field in ("max_attempts", "max_invocations", "max_request_intents", "max_physical_requests"):
        translated[field] = None
    translated["hard_limits"] = [
        item for item in translated.get("hard_limits", [])
        if item in {"rounds", "tokens", "cost", "concurrency", "time"}
    ]
    return translated


def _translate_continuation_policy(v1_policy: dict[str, Any]) -> dict[str, Any]:
    mode = v1_policy.get("mode")
    if mode not in {"manual-checkpoint", "bounded-auto", "single-round"}:
        raise ValueError("Unsupported v1 continuation mode: " + repr(mode))
    v2_mode = "manual-checkpoint" if mode == "single-round" else mode
    return {
        "mode": v2_mode,
        "requires_new_attempt_authorization": v2_mode != "bounded-auto",
    }


def _translate_recovery_ref(v1_recovery_point: dict[str, Any]) -> str:
    summary = str(v1_recovery_point.get("summary", "")).strip()
    if summary:
        return summary
    last_event = str(v1_recovery_point.get("last_event_id", "")).strip()
    if last_event:
        return f"v1-last-event:{last_event}"
    return "v1-recovery-point"


def build_v2_revision_one(
    v1_contract: dict[str, Any],
    *,
    lineage_id: str,
    task_id: str,
    phase_id: str,
    phase_boundary_revision_id: str,
    phase_boundary_revision_sha256: str,
    revision_id: str,
    invariant_sha256: str,
    review_ref: str,
    authorization_ref: str,
    accepted_at: str,
) -> dict[str, Any]:
    return {
        "contract_version": "2",
        "lineage_id": lineage_id,
        "task_id": task_id,
        "phase_id": phase_id,
        "revision_id": revision_id,
        "revision_number": 1,
        "previous_revision": None,
        "accepted_phase_boundary": {
            "revision_id": phase_boundary_revision_id,
            "sha256": phase_boundary_revision_sha256,
        },
        "invariant_set_id": INVARIANT_SET_ID,
        "invariant_source_sha256": invariant_sha256,
        "goal": v1_contract["goal"],
        "authorized_scope": copy.deepcopy(v1_contract["authorized_scope"]),
        "prohibited_scope": copy.deepcopy(v1_contract["prohibited_scope"]),
        "non_goals": copy.deepcopy(v1_contract["non_goals"]),
        "acceptance_criteria": copy.deepcopy(v1_contract["acceptance_criteria"]),
        "budgets": _translate_budgets(v1_contract["budgets"]),
        "risk_policy": copy.deepcopy(v1_contract["risk_policy"]),
        "continuation_policy": _translate_continuation_policy(v1_contract["continuation_policy"]),
        "revision_reason": "Legacy Result Contract v1 snapshot imported as revision one; no typed history is fabricated.",
        "review_ref": review_ref,
        "authorization_ref": authorization_ref,
        "accepted_at": accepted_at,
    }


def _legacy_usage(v1_budget_usage: dict[str, Any]) -> dict[str, Any]:
    return {
        "rounds": int(v1_budget_usage.get("rounds_used", 0) or 0),
        "attempts": 0,
        "invocations": 0,
        "request_intents": 0,
        "physical_requests": 0,
        "tokens": int(v1_budget_usage.get("tokens_used", 0) or 0),
        "cost_units": float(v1_budget_usage.get("cost_units_used", 0) or 0),
        "elapsed_seconds": float(v1_budget_usage.get("elapsed_seconds", 0) or 0),
        "concurrency": int(v1_budget_usage.get("peak_concurrency", 0) or 0),
    }


def build_legacy_import_event(
    v2_contract: dict[str, Any],
    *,
    contract_relative: str,
    contract_sha256: str,
    v1_contract: dict[str, Any],
    source_relative: str,
    source_sha256: str,
    event_id: str,
    operation_id: str,
    recorded_at: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    legacy_status = str(v1_contract.get("execution_status", ""))
    terminal = v1_contract.get("terminal_status")
    if terminal:
        legacy_status = f"{legacy_status};TERMINAL:{terminal}"
    return {
        "event_version": 1,
        "lineage_id": v2_contract["lineage_id"],
        "task_id": v2_contract["task_id"],
        "phase_id": v2_contract["phase_id"],
        "sequence": 1,
        "event_id": event_id,
        "operation_id": operation_id,
        "event_kind": "LEGACY_SNAPSHOT_IMPORTED",
        "recorded_at": recorded_at,
        "previous_event": None,
        "contract_revision": {
            "revision_id": v2_contract["revision_id"],
            "path": contract_relative,
            "sha256": contract_sha256,
        },
        "phase_boundary_revision": copy.deepcopy(v2_contract["accepted_phase_boundary"]),
        "actor": {"kind": "MIGRATION", "id": "MALTS-MIGRATION"},
        "session_lease_id": None,
        "payload": {
            "source_contract_path": source_relative,
            "source_contract_sha256": source_sha256,
            "legacy_status": legacy_status,
            "legacy_usage": _legacy_usage(v1_contract.get("budget_usage", {})),
            "legacy_recovery_ref": _translate_recovery_ref(v1_contract.get("recovery_point", {})),
            "reason": "Explicit v1-to-v2 cold migration of one declared Result Contract.",
        },
        "evidence_refs": list(evidence_refs),
    }


def plan_result_contract_migration(
    malts_root: Path,
    v1_contract: dict[str, Any],
    *,
    v1_relative: str,
    v1_sha256: str,
    lineage_id: str,
    task_id: str,
    phase_id: str,
    phase_boundary_revision_id: str,
    phase_boundary_revision_sha256: str,
    revision_id: str,
    event_id: str,
    operation_id: str,
    review_ref: str,
    authorization_ref: str,
    recorded_at: str,
) -> dict[str, Any]:
    if v1_contract.get("contract_version") != "1":
        raise ValueError("Only Result Contract v1 can migrate to v2.")
    schema_issues = contracts.validate_instance(malts_root, "result-contract", v1_contract)
    if schema_issues:
        codes = [item.code for item in schema_issues]
        raise ValueError("v1 contract validation failed: " + ", ".join(codes))
    execution_status = str(v1_contract.get("execution_status", ""))
    if execution_status in {"EXECUTING", "VERIFYING"}:
        raise ValueError("Result Contract migration rejects EXECUTING or VERIFYING v1 contracts.")
    if v1_contract.get("terminal_status") is not None and execution_status in V1_EXECUTION_TERMINAL:
        task_status = V2_TASK_STATUS_BY_V1_TERMINAL[str(v1_contract["terminal_status"])]
        terminal_status = v1_contract["terminal_status"]
    else:
        task_status = "AWAITING_ATTEMPT_AUTHORIZATION"
        terminal_status = None
    invariant_sha256 = invariant_source_sha256(malts_root)
    v2_contract = build_v2_revision_one(
        v1_contract,
        lineage_id=lineage_id,
        task_id=task_id,
        phase_id=phase_id,
        phase_boundary_revision_id=phase_boundary_revision_id,
        phase_boundary_revision_sha256=phase_boundary_revision_sha256,
        revision_id=revision_id,
        invariant_sha256=invariant_sha256,
        review_ref=review_ref,
        authorization_ref=authorization_ref,
        accepted_at=recorded_at,
    )
    v2_schema_issues = contracts.validate_instance(malts_root, "result-contract", v2_contract)
    if v2_schema_issues:
        codes = [item.code for item in v2_schema_issues]
        raise ValueError("v2 revision-one validation failed: " + ", ".join(codes))
    contract_relative = f"task-state/{task_id}/contracts/{revision_id}.json"
    contract_payload = canonical_json(v2_contract)
    contract_sha256 = sha256_payload(contract_payload)
    import_event = build_legacy_import_event(
        v2_contract,
        contract_relative=contract_relative,
        contract_sha256=contract_sha256,
        v1_contract=v1_contract,
        source_relative=v1_relative,
        source_sha256=v1_sha256,
        event_id=event_id,
        operation_id=operation_id,
        recorded_at=recorded_at,
        evidence_refs=[review_ref, authorization_ref],
    )
    projection, decision = controller.apply_event_batch_v2(
        v2_contract,
        [import_event],
        None,
        [],
        malts_root,
        contract_sha256,
    )
    if projection is None:
        issues = decision.get("issues") or [{"code": "RC_LINEAGE_STALE", "message": "Import event denied."}]
        first = issues[0]
        raise ValueError(f"{first.get('code')}: {first.get('message')}")
    return {
        "v2_contract": v2_contract,
        "contract_relative": contract_relative,
        "contract_payload": contract_payload,
        "contract_sha256": contract_sha256,
        "import_event": import_event,
        "event_relative": f"task-state/{task_id}/events/1-{event_id}.json",
        "event_payload": canonical_json(import_event),
        "event_sha256": sha256_payload(canonical_json(import_event)),
        "projection": projection,
        "projection_relative": f"task-state/{task_id}/RESULT_LINEAGE.json",
        "task_status": task_status,
        "terminal_status": terminal_status,
    }
