#!/usr/bin/env python3
"""Deterministic advisory 0/1/N Agent route planner for MALTS CURRENT.

The planner validates current contracts and returns a proposed dispatch record. It
never calls an Agent runtime, provider, network, or filesystem write interface.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.dont_write_bytecode = True

from malts_user_contracts import load_json, validate_instance
from resource_locators import legacy_lease_conflict


MALTS_ROOT = Path(__file__).resolve().parent.parent
TASK_SIZES = {"S0", "S1", "S2", "S3"}
LANE_REQUIRED_FIELDS = {"lane_id", "task_contract_ref", "route_evidence_ref", "leases"}
LANE_OPTIONAL_FIELDS = {"task_requirements"}
LEASE_FIELDS = {"locator", "access"}
VERIFIED_BINDINGS = {"effective_verified", "fallback_verified"}
ROUTE_POLICY_RELATIVE = Path("runtime") / "agent-routing" / "model_effort_policy.json"
ROUTE_CLASSES = ("ECONOMY", "BALANCED", "ADVANCED", "FLAGSHIP")
NORMALIZED_EFFORT = {"none": "none", "minimal": "light", "low": "light", "medium": "standard", "high": "deep", "xhigh": "deep", "max": "maximum", "ultra": "maximum"}


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
        "route_recommendations": [],
        "dispatch": None,
    }


def _lane_issues(contract: dict[str, Any], lanes: Any, malts_root: Path = MALTS_ROOT) -> list[dict[str, str]]:
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
        if (
            not isinstance(lane, dict)
            or not LANE_REQUIRED_FIELDS.issubset(lane)
            or not set(lane).issubset(LANE_REQUIRED_FIELDS | LANE_OPTIONAL_FIELDS)
        ):
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
        requirements = lane.get("task_requirements")
        if requirements is not None:
            issues.extend(
                _issue(item.code, f"{path}.task_requirements{item.path[1:]}", item.message)
                for item in validate_instance(malts_root, "agent-task-requirements", requirements)
            )
    if len(lane_ids) != len(set(lane_ids)):
        issues.append(_issue("AR_DUPLICATE_LANE", "$.lanes", "lane_id values must be unique."))
    if len(contract_refs) != len(set(contract_refs)):
        issues.append(_issue("AR_DUPLICATE_CONTRACT", "$.lanes", "task_contract_ref values must be unique."))
    return issues


def _conflicts(candidate: dict[str, Any], selected: list[dict[str, Any]]) -> bool:
    for lane in selected:
        for lease in lane["leases"]:
            for proposed in candidate["leases"]:
                if legacy_lease_conflict(proposed, lease):
                    return True
    return False


def load_route_policy(malts_root: Path = MALTS_ROOT) -> dict[str, Any]:
    return load_json(malts_root / ROUTE_POLICY_RELATIVE)


def _default_task_requirements(lane_id: str, task_size: str, independent: bool) -> dict[str, Any]:
    workload = "INDEPENDENT_VERIFICATION" if independent else (
        "MECHANICAL" if task_size in {"S0", "S1"} else "BOUNDED_IMPLEMENTATION" if task_size == "S2" else "SEMANTIC_ANALYSIS"
    )
    level = "LOW" if task_size in {"S0", "S1"} else "MEDIUM" if task_size == "S2" else "HIGH"
    return {
        "contract_id": "malts.agent-task-requirements.current",
        "task_id": lane_id,
        "responsibility": f"Default cost-aware route requirement for {lane_id}",
        "workload_class": workload,
        "semantic_complexity": level,
        "uncertainty": level,
        "write_risk": "LOW" if task_size in {"S0", "S1"} else "MEDIUM",
        "recovery_risk": "LOW" if task_size in {"S0", "S1", "S2"} else "MEDIUM",
        "audit_importance": "HIGH" if independent else level,
        "independent_verification": independent,
        "budget_priority": "BALANCED",
        "budget_pressure": "UNKNOWN",
        "latency_priority": "BALANCED",
        "failure_count": 0,
        "scope_expanded": False,
        "required_capabilities": [],
        "requested_route": {"model_id": None, "reasoning_effort": None, "model_constraint": "NONE", "effort_constraint": "NONE"},
        "parent_route": None,
    }


def _route_index_from_score(score: int, thresholds: Mapping[str, Any]) -> int:
    if score >= int(thresholds["flagship_min"]):
        return 3
    if score >= int(thresholds["advanced_min"]):
        return 2
    if score >= int(thresholds["balanced_min"]):
        return 1
    return 0


def _profile_eligible(profile: Mapping[str, Any], required_capabilities: set[str], effort: str) -> bool:
    return (
        profile.get("runtime_verified") is True
        and effort in profile.get("reasoning_efforts", [])
        and required_capabilities.issubset(set(profile.get("capabilities", [])))
        and profile.get("delegation_behavior", {}).get("supported") == "supported"
        and "sub-agent" in profile.get("delegation_behavior", {}).get("modes", [])
    )


def _profile_candidates(
    profiles: Sequence[Mapping[str, Any]],
    route: Mapping[str, Any],
    required_capabilities: set[str],
    effort: str,
) -> list[Mapping[str, Any]]:
    tier_order = {value: index for index, value in enumerate(route["preferred_capability_tiers"])}
    cost_order = {"low": 0, "medium": 1, "high": 2, "unknown": 3}
    candidates = [
        profile for profile in profiles
        if _profile_eligible(profile, required_capabilities, effort)
        and profile.get("base_capability_tier") in tier_order
        and profile.get("cost_class") in route["allowed_cost_classes"]
    ]
    return sorted(
        candidates,
        key=lambda profile: (
            tier_order.get(str(profile.get("base_capability_tier")), 99),
            cost_order.get(str(profile.get("cost_class")), 99),
            str(profile.get("profile_id")),
        ),
    )


def recommend_model_route(
    task_requirements: dict[str, Any],
    runtime_evidence: dict[str, Any],
    model_profiles: Sequence[dict[str, Any]] | None = None,
    route_policy: dict[str, Any] | None = None,
    malts_root: Path = MALTS_ROOT,
) -> dict[str, Any]:
    """Recommend a cost-aware model/effort route without dispatching or claiming effective use."""

    policy = route_policy or load_route_policy(malts_root)
    profiles = list(model_profiles or [])
    issues = [
        _issue(item.code, f"$.task_requirements{item.path[1:]}", item.message)
        for item in validate_instance(malts_root, "agent-task-requirements", task_requirements)
    ]
    issues.extend(
        _issue(item.code, f"$.route_policy{item.path[1:]}", item.message)
        for item in validate_instance(malts_root, "agent-route-policy", policy)
    )
    issues.extend(
        _issue(item.code, f"$.runtime_evidence{item.path[1:]}", item.message)
        for item in validate_instance(malts_root, "runtime-capability-evidence", runtime_evidence)
    )
    for index, profile in enumerate(profiles):
        issues.extend(
            _issue(item.code, f"$.model_profiles.{index}{item.path[1:]}", item.message)
            for item in validate_instance(malts_root, "model-profile", profile)
        )
    if issues:
        return {"decision": "BLOCKED", "route_status": "invalid_input", "issues": issues}

    weights = policy["weights"]
    score = int(weights["workload"][task_requirements["workload_class"]])
    score += int(weights["level"][task_requirements["semantic_complexity"]])
    score += int(weights["level"][task_requirements["uncertainty"]])
    score += int(weights["risk"][task_requirements["write_risk"]])
    score += int(weights["risk"][task_requirements["recovery_risk"]])
    score += int(weights["level"][task_requirements["audit_importance"]])
    if task_requirements["independent_verification"]:
        score += int(weights["independent_verification"])
    score += min(int(task_requirements["failure_count"]), 2) * int(weights["failure"])
    if task_requirements["scope_expanded"]:
        score += int(weights["scope_expanded"])

    route_by_name = {item["route_class"]: item for item in policy["route_classes"]}
    route_index = _route_index_from_score(score, policy["thresholds"])
    floor_index = 0
    floor_reasons: list[str] = []
    if task_requirements["workload_class"] == "ARCHITECTURE_SECURITY":
        floor_index = max(floor_index, ROUTE_CLASSES.index(policy["safety_floors"]["architecture_security"]))
        floor_reasons.append("architecture_security_floor")
    if task_requirements["recovery_risk"] == "HIGH":
        floor_index = max(floor_index, ROUTE_CLASSES.index(policy["safety_floors"]["high_recovery_risk"]))
        floor_reasons.append("high_recovery_risk_floor")
    if task_requirements["independent_verification"] and task_requirements["audit_importance"] == "HIGH":
        floor_index = max(floor_index, ROUTE_CLASSES.index(policy["safety_floors"]["high_importance_independent_verification"]))
        floor_reasons.append("high_importance_independent_verification_floor")
    route_index = max(route_index, floor_index)

    escalation_reasons: list[str] = []
    escalation = policy["escalation"]
    if int(task_requirements["failure_count"]) >= int(escalation["failure_count_threshold"]):
        escalation_reasons.append("failure_threshold_reached")
    if task_requirements["scope_expanded"] and escalation["scope_expansion_escalates"]:
        escalation_reasons.append("scope_expanded")
    if task_requirements["uncertainty"] == "HIGH" and escalation["high_uncertainty_escalates"]:
        escalation_reasons.append("high_uncertainty")
    if escalation_reasons:
        route_index = min(3, route_index + 1)
    if task_requirements["budget_priority"] == "QUALITY_FIRST" or task_requirements["latency_priority"] == "QUALITY_FIRST":
        route_index = min(3, route_index + 1)
    cost_pressure = task_requirements["budget_priority"] == "MINIMIZE_COST" or task_requirements["budget_pressure"] in {"HIGH", "CRITICAL"}
    if cost_pressure:
        route_index = max(floor_index, route_index - 1)

    route_class = ROUTE_CLASSES[route_index]
    route = route_by_name[route_class]
    requested = task_requirements["requested_route"]
    effort = str(requested["reasoning_effort"]) if requested["effort_constraint"] == "HARD" and requested["reasoning_effort"] is not None else str(route["default_effort"])
    max_reasons: list[str] = []
    if effort == "max":
        if requested["effort_constraint"] == "HARD":
            max_reasons.append("explicit_hard_max_override")
        elif task_requirements["workload_class"] in policy["max_effort"]["permitted_workloads"]:
            max_reasons.append("high_risk_or_independent_verification_justifies_max")
        else:
            effort = "high"
            max_reasons.append("max_rejected_without_complexity_or_risk_basis")

    required_capabilities = set(task_requirements["required_capabilities"])
    candidates = _profile_candidates(profiles, route, required_capabilities, effort)
    selected_profile: Mapping[str, Any] | None = None
    requested_model = requested["model_id"]
    if requested_model is not None:
        exact = [profile for profile in profiles if profile.get("model_id") == requested_model and _profile_eligible(profile, required_capabilities, effort)]
        if requested["model_constraint"] == "HARD":
            if not exact:
                issues.append(_issue("AR_HARD_MODEL_UNAVAILABLE", "$.task_requirements.requested_route.model_id", "The hard-requested model/effort is absent from the verified model catalog."))
            else:
                selected_profile = sorted(exact, key=lambda profile: str(profile.get("profile_id")))[0]
        elif exact:
            selected_profile = sorted(exact, key=lambda profile: str(profile.get("profile_id")))[0]
    if selected_profile is None and candidates:
        selected_profile = candidates[0]

    model_source = "VERIFIED_MODEL_PROFILE"
    if selected_profile is not None:
        model_id = str(selected_profile["model_id"])
        profile_id = str(selected_profile["profile_id"])
    else:
        recommended_runtime = runtime_evidence.get("recommended", {})
        model_id = recommended_runtime.get("model_id")
        profile_id = runtime_evidence.get("runtime_binding", {}).get("profile_id")
        model_source = "RUNTIME_RECOMMENDATION_UNVERIFIED" if model_id else "MODEL_CATALOG_REQUIRED"

    if requested["model_constraint"] == "HARD" and requested_model != model_id:
        issues.append(_issue("AR_HARD_MODEL_MISMATCH", "$.recommended.model_id", "Hard model constraints cannot be silently substituted."))
    if requested["effort_constraint"] == "HARD" and requested["reasoning_effort"] != effort:
        issues.append(_issue("AR_HARD_EFFORT_MISMATCH", "$.recommended.reasoning_effort", "Hard effort constraints cannot be silently substituted."))
    configured = runtime_evidence["configured"]
    effective = runtime_evidence["effective"]
    if requested["model_constraint"] == "HARD" and configured.get("model_id") not in {None, requested_model}:
        issues.append(_issue("AR_HARD_CONFIGURED_MODEL_MISMATCH", "$.configured.model_id", "Configured model does not satisfy the hard request."))
    if requested["effort_constraint"] == "HARD" and configured.get("reasoning_effort") not in {None, requested["reasoning_effort"]}:
        issues.append(_issue("AR_HARD_CONFIGURED_EFFORT_MISMATCH", "$.configured.reasoning_effort", "Configured effort does not satisfy the hard request."))
    if effective.get("outcome") == "effective":
        if requested["model_constraint"] == "HARD" and effective.get("model_id") != requested_model:
            issues.append(_issue("AR_HARD_EFFECTIVE_MODEL_MISMATCH", "$.effective.model_id", "Effective model violates the hard request."))
        if requested["effort_constraint"] == "HARD" and effective.get("reasoning_effort") != requested["reasoning_effort"]:
            issues.append(_issue("AR_HARD_EFFECTIVE_EFFORT_MISMATCH", "$.effective.reasoning_effort", "Effective effort violates the hard request."))
    if issues:
        return {"decision": "BLOCKED", "route_status": "hard_constraint_unsatisfied", "score": score, "issues": issues}

    parent = task_requirements["parent_route"]
    if parent is None:
        inheritance = {"decision": "NOT_APPLICABLE", "reason": "no_parent_route"}
    elif parent["model_id"] == model_id and parent["reasoning_effort"] == effort and parent["route_class"] == route_class:
        inheritance = {"decision": "ALLOWED", "reason": "exact_cost_route_match"}
    else:
        inheritance = {"decision": "REJECTED", "reason": "parent_route_does_not_match_task_cost"}

    reasons = ["cost_and_risk_scored", *floor_reasons, *escalation_reasons, *max_reasons]
    if cost_pressure:
        reasons.append("budget_pressure_applied_without_crossing_safety_floor")
    if inheritance["decision"] == "REJECTED":
        reasons.append("default_parent_inheritance_rejected")
    return {
        "decision": "RECOMMEND",
        "route_status": "recommended",
        "policy_id": policy["policy_id"],
        "task_id": task_requirements["task_id"],
        "score": score,
        "route_class": route_class,
        "requested": dict(requested),
        "recommended": {
            "model_id": model_id,
            "profile_id": profile_id,
            "reasoning_effort": effort,
            "normalized_reasoning_tier": NORMALIZED_EFFORT.get(effort, "unknown"),
            "model_source": model_source,
        },
        "configured": dict(configured),
        "effective": dict(effective),
        "inheritance": inheritance,
        "hard_constraint_status": "SATISFIED" if "HARD" in {requested["model_constraint"], requested["effort_constraint"]} else "NOT_REQUESTED",
        "escalation_reasons": escalation_reasons,
        "reasons": reasons,
        "issues": [],
    }


def plan_route(
    contract: dict[str, Any],
    runtime_evidence: dict[str, Any],
    lanes: list[dict[str, Any]],
    task_size: str,
    requires_independent_verification: bool,
    batch_id: str,
    malts_root: Path = MALTS_ROOT,
    model_profiles: Sequence[dict[str, Any]] | None = None,
    route_policy: dict[str, Any] | None = None,
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
    issues.extend(_lane_issues(contract, lanes, malts_root))
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

    route_recommendations: list[dict[str, Any]] = []
    for lane in selected:
        requirements = lane.get("task_requirements") or _default_task_requirements(lane["lane_id"], task_size, requires_independent_verification)
        recommendation = recommend_model_route(requirements, runtime_evidence, model_profiles, route_policy, malts_root)
        recommendation["lane_id"] = lane["lane_id"]
        route_recommendations.append(recommendation)
        if recommendation["decision"] == "BLOCKED":
            result = _base_result("BLOCKED", recommendation["route_status"], ["cost_aware_route_blocked"], recommendation.get("issues", []))
            result["deferred_lanes"] = lane_ids
            result["route_recommendations"] = route_recommendations
            return result

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
        "route_recommendations": route_recommendations,
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
    parser.add_argument("--model-profiles", type=Path, help="Optional JSON array of verified model-profile contracts.")
    parser.add_argument("--route-policy", type=Path, help="Optional current route policy; defaults to the bundled policy.")
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
            MALTS_ROOT,
            load_json(args.model_profiles) if args.model_profiles else None,
            load_json(args.route_policy) if args.route_policy else None,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["decision"] != "BLOCKED" else 2
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"decision": "ERROR", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
