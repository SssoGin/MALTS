#!/usr/bin/env python3
"""Deterministic advisory 0/1/N Agent route planner for MALTS W4.

The planner validates current contracts and returns a proposed dispatch record. It
never calls an Agent runtime, provider, network, or filesystem write interface.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from malts_user_contracts import load_json, validate_instance


MALTS_ROOT = Path(__file__).resolve().parent.parent
TASK_SIZES = {"S0", "S1", "S2", "S3"}
LANE_FIELDS = {"lane_id", "task_contract_ref", "route_evidence_ref", "leases"}
LEASE_FIELDS = {"locator", "access"}
VERIFIED_BINDINGS = {"effective_verified", "fallback_verified"}


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _base_result(decision: str, route_status: str, reasons: list[str], issues: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "decision": decision,
        "agent_count": 0,
        "selected_lanes": [],
        "deferred_lanes": [],
        "route_status": route_status,
        "reasons": reasons,
        "issues": issues or [],
        "dispatch": None,
    }


def _lane_issues(contract: dict[str, Any], lanes: Any) -> list[dict[str, str]]:
    if not isinstance(lanes, list):
        return [_issue("AR_LANES_SHAPE", "$.lanes", "lanes must be an array.")]
    issues: list[dict[str, str]] = []
    resources = {
        item.get("locator"): set(item.get("operations", []))
        for item in contract.get("authorized_scope", {}).get("resources", [])
        if isinstance(item, dict)
    }
    lane_ids: list[str] = []
    contract_refs: list[str] = []
    for index, lane in enumerate(lanes):
        path = f"$.lanes.{index}"
        if not isinstance(lane, dict) or set(lane) != LANE_FIELDS:
            issues.append(_issue("AR_LANE_SHAPE", path, "Each lane must be a closed lane record."))
            continue
        lane_id = lane.get("lane_id")
        task_ref = lane.get("task_contract_ref")
        route_ref = lane.get("route_evidence_ref")
        if not isinstance(lane_id, str) or not lane_id:
            issues.append(_issue("AR_LANE_REF", f"{path}.lane_id", "lane_id must be a non-empty string."))
        else:
            lane_ids.append(lane_id)
        if not isinstance(task_ref, str) or not task_ref:
            issues.append(_issue("AR_LANE_REF", f"{path}.task_contract_ref", "task_contract_ref must be a non-empty string."))
        else:
            contract_refs.append(task_ref)
        if not isinstance(route_ref, str) or not route_ref:
            issues.append(_issue("AR_LANE_REF", f"{path}.route_evidence_ref", "route_evidence_ref must be a non-empty string."))
        leases = lane.get("leases")
        if not isinstance(leases, list) or not leases:
            issues.append(_issue("AR_LANE_LEASE", f"{path}.leases", "Each lane requires at least one locator lease."))
            continue
        for lease_index, lease in enumerate(leases):
            lease_path = f"{path}.leases.{lease_index}"
            if not isinstance(lease, dict) or set(lease) != LEASE_FIELDS:
                issues.append(_issue("AR_LANE_LEASE_SHAPE", lease_path, "Lease fields must be locator and access."))
                continue
            locator = lease.get("locator")
            access = lease.get("access")
            if not isinstance(locator, str) or not locator or access not in {"read", "write"}:
                issues.append(_issue("AR_LANE_LEASE", lease_path, "Lease requires a non-empty locator and read/write access."))
            elif locator not in resources or access not in resources[locator]:
                issues.append(_issue("AR_LANE_LEASE_AUTH", lease_path, "Lane lease is outside the Result Contract authorization envelope."))
    if len(lane_ids) != len(set(lane_ids)):
        issues.append(_issue("AR_DUPLICATE_LANE", "$.lanes", "lane_id values must be unique."))
    if len(contract_refs) != len(set(contract_refs)):
        issues.append(_issue("AR_DUPLICATE_CONTRACT", "$.lanes", "task_contract_ref values must be unique."))
    return issues


def _conflicts(candidate: dict[str, Any], selected: list[dict[str, Any]]) -> bool:
    candidate_leases = {lease["locator"]: lease["access"] for lease in candidate["leases"]}
    for lane in selected:
        for lease in lane["leases"]:
            access = candidate_leases.get(lease["locator"])
            if access is not None and (access == "write" or lease["access"] == "write"):
                return True
    return False


def plan_route(
    contract: dict[str, Any],
    runtime_evidence: dict[str, Any],
    lanes: list[dict[str, Any]],
    task_size: str,
    requires_independent_verification: bool,
    batch_id: str,
    malts_root: Path = MALTS_ROOT,
) -> dict[str, Any]:
    """Return a deterministic advisory route without performing dispatch."""

    issues = [
        _issue(item.code, f"$.contract{item.path[1:]}", item.message)
        for item in validate_instance(malts_root, "result-contract", contract)
    ]
    issues.extend(
        _issue(item.code, f"$.runtime_evidence{item.path[1:]}", item.message)
        for item in validate_instance(malts_root, "runtime-capability-evidence", runtime_evidence)
    )
    if task_size not in TASK_SIZES:
        issues.append(_issue("AR_TASK_SIZE", "$.task_size", "task_size must be S0, S1, S2, or S3."))
    if not isinstance(requires_independent_verification, bool):
        issues.append(_issue("AR_INDEPENDENT_FLAG", "$.requires_independent_verification", "Independent verification flag must be boolean."))
    if not isinstance(batch_id, str) or not batch_id:
        issues.append(_issue("AR_BATCH_ID", "$.batch_id", "batch_id must be a non-empty string."))
    issues.extend(_lane_issues(contract, lanes))
    if issues:
        return _base_result("BLOCKED", "invalid_input", ["route_input_invalid"], issues)

    lane_ids = [lane["lane_id"] for lane in sorted(lanes, key=lambda item: item["lane_id"])]
    if task_size in {"S0", "S1"} and not requires_independent_verification:
        result = _base_result("MAIN_ONLY", "main_only", ["small_task_main_controller_preferred"])
        result["deferred_lanes"] = lane_ids
        return result

    if not lanes:
        if requires_independent_verification:
            return _base_result("BLOCKED", "no_eligible_lane", ["independent_verification_lane_required"])
        return _base_result("MAIN_ONLY", "main_only", ["no_delegation_lane_declared"])

    multi = contract["authorized_scope"]["multi_agent"]
    authorized = multi["allowed"] and multi["launch_review_ref"] and batch_id in multi["approved_batches"]
    if not authorized:
        if requires_independent_verification:
            result = _base_result("BLOCKED", "authorization_required", ["independent_verification_requires_approved_batch"])
        else:
            result = _base_result("MAIN_ONLY", "main_only", ["multi_agent_batch_not_authorized"])
        result["deferred_lanes"] = lane_ids
        return result

    binding = runtime_evidence["binding_status"]
    unavailable_status = None
    if binding == "unsupported" or runtime_evidence["effective"]["outcome"] == "runtime_unsupported":
        unavailable_status = "runtime_unsupported"
    elif runtime_evidence["test_state"] == "provider_unconfigured":
        unavailable_status = "provider_unconfigured"
    elif binding == "unknown":
        unavailable_status = "effective_unknown"
    if unavailable_status is not None:
        if requires_independent_verification:
            result = _base_result("BLOCKED", unavailable_status, [f"independent_verification_{unavailable_status}"])
        else:
            result = _base_result("MAIN_ONLY", unavailable_status, [f"delegation_{unavailable_status}"])
        result["deferred_lanes"] = lane_ids
        return result

    verified = binding in VERIFIED_BINDINGS and runtime_evidence["effective_concurrency"] is not None
    runtime_cap = runtime_evidence["effective_concurrency"] if verified else 1
    hard_cap = min(multi["max_agents"], contract["budgets"]["max_concurrency"], runtime_cap)
    desired = 1 if task_size in {"S0", "S1", "S2"} else hard_cap
    desired = min(desired, hard_cap)

    selected: list[dict[str, Any]] = []
    deferred: list[str] = []
    for lane in sorted(lanes, key=lambda item: item["lane_id"]):
        if len(selected) >= desired or _conflicts(lane, selected):
            deferred.append(lane["lane_id"])
        else:
            selected.append(lane)
    if not selected:
        return _base_result("BLOCKED", "lease_conflict", ["no_conflict_free_authorized_lane"])
    if requires_independent_verification and len(selected) < 1:
        return _base_result("BLOCKED", "independent_verification_unavailable", ["independent_verification_lane_unavailable"])

    route_status = binding if verified else "routing_degraded"
    reasons = ["dynamic_route_selected"]
    if not verified:
        reasons.append("runtime_binding_not_effective; capped_at_one_agent")
    if deferred:
        reasons.append("capacity_or_lease_constraints_deferred_lanes")
    dispatch = {
        "batch_id": batch_id,
        "runtime_capacity": runtime_evidence["effective_concurrency"] if verified else None,
        "agents": [
            {
                "agent_key": lane["lane_id"],
                "task_contract_ref": lane["task_contract_ref"],
                "route_evidence_ref": lane["route_evidence_ref"],
                "binding_status": binding,
                "leases": [dict(lease) for lease in lane["leases"]],
            }
            for lane in selected
        ],
    }
    return {
        "decision": "DISPATCH",
        "agent_count": len(selected),
        "selected_lanes": [lane["lane_id"] for lane in selected],
        "deferred_lanes": deferred,
        "route_status": route_status,
        "reasons": reasons,
        "issues": [],
        "dispatch": dispatch,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MALTS deterministic advisory Agent route planner")
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--runtime-evidence", required=True, type=Path)
    parser.add_argument("--lanes", required=True, type=Path)
    parser.add_argument("--task-size", required=True, choices=sorted(TASK_SIZES))
    parser.add_argument("--requires-independent-verification", action="store_true")
    parser.add_argument("--batch-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = plan_route(
            load_json(args.contract),
            load_json(args.runtime_evidence),
            load_json(args.lanes),
            args.task_size,
            args.requires_independent_verification,
            args.batch_id,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["decision"] != "BLOCKED" else 2
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"decision": "ERROR", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
