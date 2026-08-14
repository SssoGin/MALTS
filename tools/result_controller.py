#!/usr/bin/env python3
"""Deterministic authorization-aware Result Contract controller for MALTS W4.

The controller never executes a business command or dispatches an Agent. It validates
one declared event, including an optional approved dispatch record, applies it to a
copy of a Result Contract, and writes only an explicitly requested new output file
when used through the CLI.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import hashlib
from datetime import datetime

sys.dont_write_bytecode = True

from malts_user_contracts import (
    ContractIssue, RESULT_EVENT_OPTIONAL_FIELDS, RESULT_EVENT_REQUIRED_FIELDS,
    canonical_json, load_json, load_lifecycle_invariants, validate_instance,
)


MALTS_ROOT = Path(__file__).resolve().parent.parent
TERMINAL_STATUSES = {"DONE", "PARTIAL", "BLOCKED", "FAILED"}
WRITE_OPERATIONS = {"write", "create", "delete", "move", "install", "git-write", "remote-write"}
EVENT_FIELDS = {
    "event_id",
    "target_status",
    "at",
    "reason",
    "evidence_refs",
    "strategy_id",
    "scope_locators",
    "new_information_refs",
    "retry_basis",
    "failure_class",
    "operation",
    "command",
    "budget_delta",
    "attempt",
    "recovery_summary",
    "next_action",
    "blockers",
    "failure_evidence",
    "remaining_work",
    "dispatch",
}
EVENT_REQUIRED = EVENT_FIELDS.difference({"dispatch"})
OPERATIONS = {
    "none",
    "read",
    "write",
    "create",
    "delete",
    "move",
    "execute",
    "install",
    "git-read",
    "git-write",
    "network",
    "remote-write",
    "dispatch",
}
DISPATCH_FIELDS = {"batch_id", "runtime_capacity", "agents"}
DISPATCH_AGENT_FIELDS = {"agent_key", "task_contract_ref", "route_evidence_ref", "binding_status", "leases"}
LEASE_FIELDS = {"locator", "access"}
VERIFIED_BINDINGS = {"effective_verified", "fallback_verified"}
V2_TERMINAL_TASK_STATUSES = {"DONE", "PARTIAL", "BLOCKED", "FAILED"}
V2_EXECUTION_EVENT_KINDS = {
    "ROUND_STARTED", "ATTEMPT_STARTED", "INVOCATION_STARTED", "EXTERNAL_REQUEST_INTENT_RESERVED",
}
V2_USAGE_ZERO = {
    "rounds": 0, "attempts": 0, "invocations": 0, "request_intents": 0,
    "physical_requests": 0, "tokens": 0, "cost_units": 0, "elapsed_seconds": 0, "concurrency": 0,
}


@dataclass(frozen=True)
class ControllerIssue:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def _issue(code: str, path: str, message: str) -> ControllerIssue:
    return ControllerIssue(code, path, message)


def _contract_issues(malts_root: Path, contract: Any) -> list[ControllerIssue]:
    return [ControllerIssue(item.code, item.path, item.message) for item in validate_instance(malts_root, "result-contract", contract)]


def _event_shape_issues(event: Any) -> list[ControllerIssue]:
    if not isinstance(event, dict):
        return [_issue("RC_EVENT_SHAPE", "$", "Controller event must be an object.")]
    issues: list[ControllerIssue] = []
    missing = sorted(EVENT_REQUIRED.difference(event))
    unknown = sorted(set(event).difference(EVENT_FIELDS))
    if missing:
        issues.append(_issue("RC_EVENT_REQUIRED", "$", f"Missing event fields: {', '.join(missing)}"))
    if unknown:
        issues.append(_issue("RC_EVENT_CLOSED", "$", f"Unknown event fields: {', '.join(unknown)}"))
    if event.get("operation") not in OPERATIONS:
        issues.append(_issue("RC_EVENT_OPERATION", "$.operation", "Unsupported controller operation."))
    delta = event.get("budget_delta")
    expected_delta = {"elapsed_seconds", "tokens_used", "cost_units_used", "concurrency_observed"}
    if not isinstance(delta, dict) or set(delta) != expected_delta:
        issues.append(_issue("RC_EVENT_BUDGET", "$.budget_delta", "budget_delta must be a closed usage delta object."))
    elif any(not isinstance(delta[key], (int, float)) or isinstance(delta[key], bool) or delta[key] < 0 for key in expected_delta):
        issues.append(_issue("RC_EVENT_BUDGET", "$.budget_delta", "Budget deltas must be non-negative numbers."))
    if not isinstance(event.get("attempt"), int) or isinstance(event.get("attempt"), bool) or event.get("attempt", -1) < 0:
        issues.append(_issue("RC_EVENT_ATTEMPT", "$.attempt", "attempt must be a non-negative integer."))
    dispatch = event.get("dispatch")
    if event.get("operation") == "dispatch":
        issues.extend(_dispatch_shape_issues(dispatch))
    elif dispatch is not None:
        issues.append(_issue("RC_DISPATCH_STATE", "$.dispatch", "dispatch is only valid when operation is dispatch."))
    return issues


def _dispatch_shape_issues(dispatch: Any) -> list[ControllerIssue]:
    if not isinstance(dispatch, dict):
        return [_issue("RC_DISPATCH_REQUIRED", "$.dispatch", "dispatch operation requires a closed dispatch record.")]
    issues: list[ControllerIssue] = []
    if set(dispatch) != DISPATCH_FIELDS:
        issues.append(_issue("RC_DISPATCH_SHAPE", "$.dispatch", "Dispatch fields must be batch_id, runtime_capacity, and agents."))
    batch_id = dispatch.get("batch_id")
    if not isinstance(batch_id, str) or not batch_id:
        issues.append(_issue("RC_DISPATCH_BATCH", "$.dispatch.batch_id", "Dispatch batch_id must be a non-empty string."))
    capacity = dispatch.get("runtime_capacity")
    if capacity is not None and (not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1):
        issues.append(_issue("RC_DISPATCH_CAPACITY", "$.dispatch.runtime_capacity", "Runtime capacity must be null or a positive integer."))
    agents = dispatch.get("agents")
    if not isinstance(agents, list) or not agents:
        issues.append(_issue("RC_DISPATCH_AGENTS", "$.dispatch.agents", "Dispatch requires at least one Agent record."))
        return issues
    for agent_index, agent in enumerate(agents):
        path = f"$.dispatch.agents.{agent_index}"
        if not isinstance(agent, dict) or set(agent) != DISPATCH_AGENT_FIELDS:
            issues.append(_issue("RC_DISPATCH_AGENT_SHAPE", path, "Each Agent record must be closed and complete."))
            continue
        for field in ("agent_key", "task_contract_ref", "route_evidence_ref"):
            if not isinstance(agent.get(field), str) or not agent.get(field):
                issues.append(_issue("RC_DISPATCH_AGENT_REF", f"{path}.{field}", f"{field} must be a non-empty string."))
        if agent.get("binding_status") not in {
            "effective_verified", "configured_unverified", "static_binding", "inherited",
            "fallback_verified", "unsupported", "unknown",
        }:
            issues.append(_issue("RC_DISPATCH_BINDING", f"{path}.binding_status", "Unknown runtime binding status."))
        leases = agent.get("leases")
        if not isinstance(leases, list) or not leases:
            issues.append(_issue("RC_DISPATCH_LEASE", f"{path}.leases", "Each Agent requires at least one locator lease."))
            continue
        for lease_index, lease in enumerate(leases):
            lease_path = f"{path}.leases.{lease_index}"
            if not isinstance(lease, dict) or set(lease) != LEASE_FIELDS:
                issues.append(_issue("RC_DISPATCH_LEASE_SHAPE", lease_path, "Lease fields must be locator and access."))
                continue
            if not isinstance(lease.get("locator"), str) or not lease.get("locator"):
                issues.append(_issue("RC_DISPATCH_LEASE", f"{lease_path}.locator", "Lease locator must be a non-empty string."))
            if lease.get("access") not in {"read", "write"}:
                issues.append(_issue("RC_DISPATCH_LEASE", f"{lease_path}.access", "Lease access must be read or write."))
    return issues


def _dispatch_authorization_issues(contract: dict[str, Any], event: dict[str, Any]) -> list[ControllerIssue]:
    issues: list[ControllerIssue] = []
    dispatch = event["dispatch"]
    agents = dispatch["agents"]
    multi = contract.get("authorized_scope", {}).get("multi_agent", {})
    if contract.get("execution_status") != "PLANNING":
        issues.append(_issue("RC_DISPATCH_PLANNING", "$.execution_status", "Dispatch records are accepted only from PLANNING."))
    if not multi.get("allowed") or not multi.get("launch_review_ref"):
        issues.append(_issue("RC_DISPATCH_AUTH", "$.authorized_scope.multi_agent", "Dispatch requires multi-agent authorization and a launch review reference."))
    if dispatch.get("batch_id") not in set(multi.get("approved_batches", [])):
        issues.append(_issue("RC_DISPATCH_BATCH", "$.dispatch.batch_id", "Dispatch batch is not approved by the Result Contract."))

    limits = [multi.get("max_agents", 0), contract.get("budgets", {}).get("max_concurrency", 0)]
    capacity = dispatch.get("runtime_capacity")
    if capacity is not None:
        limits.append(capacity)
    if len(agents) > min(limits):
        issues.append(_issue("RC_DISPATCH_LIMIT", "$.dispatch.agents", "Agent count exceeds an authorization, contract, or runtime concurrency limit."))
    if len(agents) > 1:
        if capacity is None:
            issues.append(_issue("RC_DISPATCH_CAPACITY", "$.dispatch.runtime_capacity", "N-agent dispatch requires verified runtime capacity."))
        if any(agent.get("binding_status") not in VERIFIED_BINDINGS for agent in agents):
            issues.append(_issue("RC_DISPATCH_EFFECTIVE_BINDING", "$.dispatch.agents", "N-agent dispatch requires effective or verified-fallback bindings for every Agent."))
    if any(agent.get("binding_status") in {"unsupported", "unknown"} for agent in agents):
        issues.append(_issue("RC_DISPATCH_BINDING_UNAVAILABLE", "$.dispatch.agents", "Unsupported or unknown bindings cannot authorize dispatch."))

    agent_keys = [agent.get("agent_key") for agent in agents]
    contract_refs = [agent.get("task_contract_ref") for agent in agents]
    if len(agent_keys) != len(set(agent_keys)):
        issues.append(_issue("RC_DISPATCH_DUPLICATE_AGENT", "$.dispatch.agents", "Agent keys must be unique within a batch."))
    if len(contract_refs) != len(set(contract_refs)):
        issues.append(_issue("RC_DISPATCH_DUPLICATE_CONTRACT", "$.dispatch.agents", "Task Contract references must be unique within a batch."))

    resources = {
        item.get("locator"): set(item.get("operations", []))
        for item in contract.get("authorized_scope", {}).get("resources", [])
        if isinstance(item, dict)
    }
    lease_owners: dict[str, list[tuple[str, str]]] = {}
    lease_locators: set[str] = set()
    for agent in agents:
        for lease in agent.get("leases", []):
            locator = lease.get("locator")
            access = lease.get("access")
            lease_locators.add(locator)
            if locator not in resources or access not in resources.get(locator, set()):
                issues.append(_issue("RC_DISPATCH_LEASE_AUTH", "$.dispatch.agents", f"Lease {locator!r} with {access!r} access is outside authorized resources."))
            lease_owners.setdefault(locator, []).append((agent.get("agent_key"), access))
    for locator, owners in lease_owners.items():
        if len({owner for owner, _ in owners}) > 1 and any(access == "write" for _, access in owners):
            issues.append(_issue("RC_DISPATCH_LEASE_CONFLICT", "$.dispatch.agents", f"Conflicting write lease for {locator!r}."))
    if set(event.get("scope_locators", [])) != lease_locators:
        issues.append(_issue("RC_DISPATCH_SCOPE", "$.scope_locators", "Dispatch scope_locators must exactly match the declared lease locators."))
    if int(event.get("budget_delta", {}).get("concurrency_observed", 0)) != len(agents):
        issues.append(_issue("RC_DISPATCH_BUDGET", "$.budget_delta.concurrency_observed", "Dispatch concurrency observation must equal the Agent count."))
    return issues


def _authorized_operation_issues(contract: dict[str, Any], event: dict[str, Any]) -> list[ControllerIssue]:
    issues: list[ControllerIssue] = []
    operation = event.get("operation")
    status = contract.get("execution_status")
    if operation == "dispatch":
        return _dispatch_authorization_issues(contract, event)
    if status == "AWAITING_AUTHORIZATION" and operation in WRITE_OPERATIONS:
        issues.append(_issue("RC_PREAUTH_WRITE", "$.operation", "AWAITING_AUTHORIZATION cannot perform a write operation."))

    resources = {
        item.get("locator"): set(item.get("operations", []))
        for item in contract.get("authorized_scope", {}).get("resources", [])
        if isinstance(item, dict)
    }
    for index, locator in enumerate(event.get("scope_locators", [])):
        if locator not in resources:
            issues.append(_issue("RC_ACTION_SCOPE", f"$.scope_locators.{index}", "Action locator is outside authorized_scope."))
        elif operation != "none" and operation not in resources[locator]:
            issues.append(_issue("RC_ACTION_OPERATION", f"$.scope_locators.{index}", f"Operation {operation} is not authorized for {locator}."))
    if operation != "none" and not event.get("scope_locators"):
        issues.append(_issue("RC_ACTION_SCOPE", "$.scope_locators", "A non-empty operation requires at least one authorized locator."))

    command = event.get("command")
    allowed_commands = set(contract.get("authorized_scope", {}).get("commands", []))
    if command is not None and command not in allowed_commands:
        issues.append(_issue("RC_ACTION_COMMAND", "$.command", "Command is outside authorized_scope.commands."))
    if operation == "execute" and command is None:
        issues.append(_issue("RC_ACTION_COMMAND", "$.command", "execute requires an explicitly authorized command."))
    return issues


def _next_usage(contract: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    current = copy.deepcopy(contract["budget_usage"])
    delta = event["budget_delta"]
    if event["target_status"] == "EXECUTING" and contract.get("execution_status") != "EXECUTING":
        current["rounds_used"] += 1
    current["elapsed_seconds"] += delta["elapsed_seconds"]
    current["tokens_used"] += int(delta["tokens_used"])
    current["cost_units_used"] += delta["cost_units_used"]
    current["peak_concurrency"] = max(current["peak_concurrency"], int(delta["concurrency_observed"]))
    return current


def _hard_budget_issues(contract: dict[str, Any], usage: dict[str, Any]) -> list[ControllerIssue]:
    budgets = contract.get("budgets", {})
    fields = {
        "rounds": ("max_rounds", "rounds_used"),
        "time": ("max_elapsed_seconds", "elapsed_seconds"),
        "tokens": ("max_tokens", "tokens_used"),
        "cost": ("max_cost_units", "cost_units_used"),
        "concurrency": ("max_concurrency", "peak_concurrency"),
    }
    issues: list[ControllerIssue] = []
    for hard_limit in budgets.get("hard_limits", []):
        limit_field, usage_field = fields[hard_limit]
        limit = budgets.get(limit_field)
        if limit is None or usage[usage_field] > limit:
            issues.append(_issue("RC_HARD_BUDGET_STOP", f"$.budget_usage.{usage_field}", f"Hard {hard_limit} budget would be exceeded."))
    return issues


def apply_event(
    contract: dict[str, Any],
    event: dict[str, Any],
    malts_root: Path = MALTS_ROOT,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Apply one deterministic event or return a fail-closed decision."""

    input_issues = _contract_issues(malts_root, contract)
    if input_issues:
        return None, {"decision": "INVALID_INPUT", "issues": [item.as_dict() for item in input_issues]}
    if contract.get("execution_status") in TERMINAL_STATUSES:
        issue = _issue("RC_TERMINAL_IMMUTABLE", "$.execution_status", "A terminal contract cannot accept another event.")
        return None, {"decision": "DENIED", "issues": [issue.as_dict()]}

    event_issues = _event_shape_issues(event)
    if not event_issues:
        event_issues.extend(_authorized_operation_issues(contract, event))
    if event_issues:
        return None, {"decision": "DENIED", "issues": [item.as_dict() for item in event_issues]}

    usage = _next_usage(contract, event)
    budget_issues = _hard_budget_issues(contract, usage)
    if budget_issues:
        return None, {"decision": "STOP", "issues": [item.as_dict() for item in budget_issues]}

    updated = copy.deepcopy(contract)
    target = event["target_status"]
    status_event = {
        "event_id": event["event_id"],
        "status": target,
        "at": event["at"],
        "reason": event["reason"],
        "evidence_refs": copy.deepcopy(event["evidence_refs"]),
        "strategy_id": event["strategy_id"],
        "scope_locators": copy.deepcopy(event["scope_locators"]),
        "new_information_refs": copy.deepcopy(event["new_information_refs"]),
        "retry_basis": event["retry_basis"],
        "failure_class": event["failure_class"],
    }
    updated["status_history"].append(status_event)
    updated["execution_status"] = target
    updated["terminal_status"] = target if target in TERMINAL_STATUSES else None
    updated["budget_usage"] = usage
    if target in TERMINAL_STATUSES:
        updated["remaining_work"] = copy.deepcopy(event["remaining_work"])
    updated["recovery_point"] = {
        "status": target,
        "summary": event["recovery_summary"],
        "next_action": event["next_action"],
        "blockers": copy.deepcopy(event["blockers"]),
        "failure_evidence": copy.deepcopy(event["failure_evidence"]),
        "round": usage["rounds_used"],
        "attempt": event["attempt"],
        "strategy_id": event["strategy_id"],
        "budget_usage": copy.deepcopy(usage),
        "last_event_id": event["event_id"],
    }

    output_issues = _contract_issues(malts_root, updated)
    if output_issues:
        return None, {"decision": "DENIED", "issues": [item.as_dict() for item in output_issues]}
    return updated, {"decision": "APPLIED", "issues": []}


def _sha256(value: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest().upper()


def _instant(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamp requires an explicit timezone")
    return parsed


def _transition_map(model: dict[str, Any], machine: str) -> dict[str, set[str]]:
    return {str(row["from"]): set(row["to"]) for row in model[machine]["transitions"]}


def _v2_issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _event_payload_issues(event: dict[str, Any], projection: dict[str, Any]) -> list[dict[str, str]]:
    kind = event.get("event_kind")
    payload = event.get("payload", {})
    required = RESULT_EVENT_REQUIRED_FIELDS.get(str(kind), set())
    missing = sorted(required.difference(payload))
    if missing:
        return [_v2_issue("RC_EVENT_PAYLOAD_REQUIRED", "$.payload", f"{kind} requires: {', '.join(missing)}")]
    unknown = sorted(set(payload).difference(required.union(RESULT_EVENT_OPTIONAL_FIELDS.get(str(kind), set()))))
    if unknown:
        return [_v2_issue("RC_EVENT_PAYLOAD_CLOSED", "$.payload", f"{kind} forbids payload fields: {', '.join(unknown)}")]
    issues: list[dict[str, str]] = []
    if kind == "STATUS_TRANSITION" and payload.get("from_status") != projection.get("task_status"):
        issues.append(_v2_issue("RC_TRANSITION_INVALID", "$.payload.from_status", "Transition source must equal the projected Task status."))
    if kind in {"ATTEMPT_PLANNED", "ATTEMPT_STARTED"} and payload.get("round_id") != projection.get("current_round_id"):
        issues.append(_v2_issue("RC_EVENT_CARDINALITY", "$.payload.round_id", "Attempt must belong to the current Round."))
    if kind in {"INVOCATION_PLANNED", "INVOCATION_STARTED"} and payload.get("attempt_id") != projection.get("current_attempt_id"):
        issues.append(_v2_issue("RC_EVENT_CARDINALITY", "$.payload.attempt_id", "Invocation must belong to the current Attempt."))
    if kind in {"EXTERNAL_REQUEST_INTENT_RESERVED", "EXTERNAL_REQUEST_OBSERVED"} and payload.get("invocation_id") != projection.get("current_invocation_id"):
        issues.append(_v2_issue("RC_EVENT_CARDINALITY", "$.payload.invocation_id", "Request facts must belong to the current Invocation."))
    if kind == "INVOCATION_COMPLETED":
        summary = payload.get("dispatch_summary", {})
        minimum = summary.get("confirmed_request_count_min")
        maximum = summary.get("confirmed_request_count_max")
        if isinstance(minimum, int) and isinstance(maximum, int) and maximum < minimum:
            issues.append(_v2_issue("RC_REQUEST_OBSERVATION_INVALID", "$.payload.dispatch_summary", "Confirmed maximum cannot be below the known minimum."))
        if summary.get("dispatch_assessment") == "CONFIRMED_NOT_SENT" and not summary.get("direct_evidence_refs"):
            issues.append(_v2_issue("RC_REQUEST_NOT_SENT_EVIDENCE_REQUIRED", "$.payload.dispatch_summary.direct_evidence_refs", "CONFIRMED_NOT_SENT requires direct dispatch-order evidence."))
    if kind == "EXTERNAL_REQUEST_INTENT_RESERVED" and payload.get("physical_request_limit") is not None and not payload.get("provider_retry_bound_proven"):
        issues.append(_v2_issue("RC_PHYSICAL_REQUEST_BOUND_UNPROVABLE", "$.payload.provider_retry_bound_proven", "A finite physical-request limit requires bounded observable provider retries."))
    if kind == "CORRECTION_APPENDED":
        target = projection.setdefault("event_hashes", {}).get(str(payload.get("target_event_id")))
        if target is None or target != payload.get("target_event_sha256"):
            issues.append(_v2_issue("RC_LINEAGE_STALE", "$.payload.target_event_sha256", "Correction must bind one exact committed target event hash."))
    return issues


def _find_envelope(projection: dict[str, Any], envelope_id: str | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    grants = projection.get("authorization_envelopes", {})
    envelope = grants.get(str(envelope_id)) if isinstance(grants, dict) else None
    usage = next((row.get("usage") for row in projection.get("envelope_usage", []) if row.get("envelope_id") == envelope_id), None)
    return envelope, usage


def _authorization_issues(
    contract: dict[str, Any],
    event: dict[str, Any],
    projection: dict[str, Any],
    contract_sha256: str,
) -> list[dict[str, str]]:
    if event.get("event_kind") not in V2_EXECUTION_EVENT_KINDS:
        return []
    if projection.get("unresolved_side_effects") or projection.get("recovery_required"):
        return [_v2_issue("RC_SIDE_EFFECT_UNKNOWN", "$", "Unresolved side-effect or recovery state blocks further execution.")]
    envelope_id = event.get("payload", {}).get("envelope_id")
    envelope, usage = _find_envelope(projection, envelope_id)
    if envelope is None or envelope_id not in projection.get("active_authorization_envelope_ids", []):
        return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.envelope_id", "Execution event requires an active applicable authorization envelope.")]
    if envelope.get("contract_revision_id") != contract.get("revision_id") or envelope.get("contract_revision_sha256") != contract_sha256:
        return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.envelope_id", "Authorization envelope binds a stale Result Contract revision.")]
    boundary = contract.get("accepted_phase_boundary", {})
    if envelope.get("phase_boundary_revision_id") != boundary.get("revision_id") or envelope.get("phase_boundary_revision_sha256") != boundary.get("sha256"):
        return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.envelope_id", "Authorization envelope binds a stale Phase boundary revision.")]
    event_time = _instant(str(event["recorded_at"]))
    granted_time = _instant(str(envelope["granted_at"]))
    expires_time = _instant(str(envelope["expires_at"])) if envelope.get("expires_at") is not None else None
    if event_time < granted_time or (expires_time is not None and event_time >= expires_time):
        return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.recorded_at", "Authorization envelope is not valid at the event time.")]
    if int(event.get("sequence", 0)) <= int(envelope.get("effective_after_event_sequence", -1)):
        return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.sequence", "Authorization envelope is not yet effective for this event sequence.")]
    if envelope.get("session_lease_id") != event.get("session_lease_id"):
        return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.session_lease_id", "Event Session lease does not match the authorization envelope.")]
    if event.get("event_kind") not in set(envelope.get("allowed_operations", [])):
        return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.event_kind", "Event kind is outside the envelope's allowed operations.")]
    if contract.get("risk_policy", {}).get("risk_level") not in set(envelope.get("allowed_risk_classes", [])):
        return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.envelope_id", "Contract risk class is outside the envelope allowance.")]
    task_locator = f"task-state/{contract['task_id']}"
    contract_resources = contract.get("authorized_scope", {}).get("resources", [])
    task_operations = {
        str(operation)
        for resource in contract_resources
        if resource.get("locator") == task_locator
        for operation in resource.get("operations", [])
    }
    if task_locator not in set(envelope.get("scope_locators", [])) or "write" not in task_operations:
        return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.envelope_id", "Execution events require the Task lineage in both the contract and envelope scope.")]
    if event.get("event_kind") == "EXTERNAL_REQUEST_INTENT_RESERVED":
        payload = event.get("payload", {})
        provider = payload.get("provider_locator")
        external_systems = set(contract.get("authorized_scope", {}).get("external_systems", []))
        if provider not in set(envelope.get("scope_locators", [])) or provider not in external_systems:
            return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.provider_locator", "Provider locator must be declared in both the contract external-system scope and authorization envelope scope.")]
        if payload.get("side_effect_class") not in set(envelope.get("allowed_side_effect_classes", [])):
            return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.side_effect_class", "Side-effect class is outside the envelope allowance.")]
        hard_physical = "physical_requests" in contract.get("budgets", {}).get("hard_limits", [])
        if hard_physical and (payload.get("physical_request_limit") is None or not payload.get("provider_retry_bound_proven")):
            return [_v2_issue("RC_PHYSICAL_REQUEST_BOUND_UNPROVABLE", "$.payload.physical_request_limit", "Finite hard physical-request bounds require a proven per-invocation upper bound.")]
        if hard_physical:
            maximum = contract.get("budgets", {}).get("max_physical_requests")
            used = projection.get("hard_budget_usage", {}).get("physical_requests", 0)
            reserved = sum(
                max(
                    int(row.get("physical_request_limit") or 0)
                    - sum(1 for intent_id in projection.get("observed_requests", {}).values() if intent_id == request_intent_id),
                    0,
                )
                for request_intent_id, row in projection.get("request_intent_records", {}).items()
            )
            if maximum is None or used + reserved + int(payload["physical_request_limit"]) > maximum:
                return [_v2_issue("RC_HARD_BUDGET_EXHAUSTED", "$.payload.physical_request_limit", "The proven physical-request upper bound exceeds the remaining hard contract budget.")]
    unit_by_kind = {"ROUND_STARTED": "ROUNDS", "ATTEMPT_STARTED": "ATTEMPTS", "INVOCATION_STARTED": "INVOCATIONS", "EXTERNAL_REQUEST_INTENT_RESERVED": "REQUEST_INTENTS"}
    field_by_unit = {"ROUNDS": "rounds", "ATTEMPTS": "attempts", "INVOCATIONS": "invocations", "REQUEST_INTENTS": "request_intents"}
    unit = unit_by_kind[event["event_kind"]]
    current = (usage or V2_USAGE_ZERO).get(field_by_unit[unit], 0)
    limit_rows = [row for row in envelope.get("limits", []) if row.get("unit") == unit]
    if len(limit_rows) != 1:
        return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.envelope_id", f"Authorization envelope requires exactly one {unit} limit row.")]
    limit = limit_rows[0].get("maximum")
    if limit is None and contract.get("risk_policy", {}).get("risk_level") in {"high", "critical"}:
        return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.envelope_id", f"High-risk execution cannot infer an unlimited {unit} authorization.")]
    if limit is not None and current >= limit:
        code = "RC_AUTHORIZED_ROUNDS_EXHAUSTED" if unit == "ROUNDS" else "RC_AUTHORIZATION_REQUIRED"
        return [_v2_issue(code, "$.payload.envelope_id", f"Authorization limit for {unit} is exhausted.")]
    return []


def _usage_authorization_issues(contract: dict[str, Any], event: dict[str, Any], projection: dict[str, Any]) -> list[dict[str, str]]:
    if event.get("event_kind") != "USAGE_OBSERVED":
        return []
    envelope_id = event.get("payload", {}).get("envelope_id")
    envelope, usage = _find_envelope(projection, envelope_id)
    if envelope is None:
        return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.envelope_id", "Observed usage must bind an existing authorization envelope.")]
    delta = event["payload"]["usage_delta"]
    checks = {
        "TOKENS": ("tokens", delta["tokens"], "sum"),
        "COST_UNITS": ("cost_units", delta["cost_units"], "sum"),
        "ELAPSED_SECONDS": ("elapsed_seconds", delta["elapsed_seconds"], "sum"),
        "CONCURRENCY": ("concurrency", delta["concurrency"], "max"),
    }
    for unit, (field, increment, mode) in checks.items():
        rows = [row for row in envelope.get("limits", []) if row.get("unit") == unit]
        if len(rows) != 1:
            return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.envelope_id", f"Observed usage requires exactly one {unit} limit row.")]
        maximum = rows[0].get("maximum")
        if maximum is None and contract.get("risk_policy", {}).get("risk_level") in {"high", "critical"}:
            return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.envelope_id", f"High-risk usage cannot infer an unlimited {unit} authorization.")]
        current = (usage or V2_USAGE_ZERO).get(field, 0)
        next_value = current + increment if mode == "sum" else max(current, increment)
        if maximum is not None and next_value > maximum:
            projection["unresolved_side_effects"] = True
            projection["recovery_required"] = True
    return []


def _hard_budget_issues_v2(contract: dict[str, Any], usage: dict[str, Any]) -> list[dict[str, str]]:
    budgets = contract.get("budgets", {})
    mapping = {
        "rounds": ("max_rounds", "rounds"), "attempts": ("max_attempts", "attempts"), "invocations": ("max_invocations", "invocations"),
        "request_intents": ("max_request_intents", "request_intents"), "physical_requests": ("max_physical_requests", "physical_requests"),
        "tokens": ("max_tokens", "tokens"), "cost": ("max_cost_units", "cost_units"), "concurrency": ("max_concurrency", "concurrency"), "time": ("max_elapsed_seconds", "elapsed_seconds"),
    }
    for hard in budgets.get("hard_limits", []):
        maximum_field, usage_field = mapping[hard]
        maximum = budgets.get(maximum_field)
        if maximum is None or usage.get(usage_field, 0) > maximum:
            return [_v2_issue("RC_HARD_BUDGET_EXHAUSTED", f"$.hard_budget_usage.{usage_field}", f"Hard {hard} budget would be exceeded.")]
    return []


def _increment_usage(projection: dict[str, Any], event: dict[str, Any]) -> None:
    usage = projection["hard_budget_usage"]
    unit = {"ROUND_STARTED": "rounds", "ATTEMPT_STARTED": "attempts", "INVOCATION_STARTED": "invocations", "EXTERNAL_REQUEST_INTENT_RESERVED": "request_intents"}.get(event["event_kind"])
    if unit:
        usage[unit] += 1
    if event["event_kind"] == "EXTERNAL_REQUEST_OBSERVED":
        usage["physical_requests"] += 1
    if event["event_kind"] == "USAGE_OBSERVED":
        delta = event["payload"]["usage_delta"]
        for field in ("tokens", "cost_units", "elapsed_seconds"):
            usage[field] += delta[field]
        usage["concurrency"] = max(usage["concurrency"], delta["concurrency"])


def _apply_v2_event(
    contract: dict[str, Any],
    event: dict[str, Any],
    projection: dict[str, Any],
    model: dict[str, Any],
    contract_sha256: str,
) -> list[dict[str, str]]:
    issues = _event_payload_issues(event, projection)
    issues.extend(_authorization_issues(contract, event, projection, contract_sha256))
    issues.extend(_usage_authorization_issues(contract, event, projection))
    if issues:
        return issues
    kind = event["event_kind"]
    payload = event["payload"]
    if kind == "CONTRACT_REVISION_ACCEPTED":
        if payload["revision_id"] != contract["revision_id"]:
            return [_v2_issue("RC_LINEAGE_STALE", "$.payload.revision_id", "Contract acceptance event must identify the exact bound Result Contract revision.")]
    elif kind == "STATUS_TRANSITION":
        allowed = _transition_map(model, "task_state_machine").get(payload["from_status"], set())
        if payload["to_status"] not in allowed:
            return [_v2_issue("RC_TRANSITION_INVALID", "$.payload.to_status", f"Invalid Task transition {payload['from_status']} -> {payload['to_status']}.")]
        projection["task_status"] = payload["to_status"]
        projection["terminal_status"] = payload["to_status"] if payload["to_status"] in V2_TERMINAL_TASK_STATUSES else None
    elif kind == "AUTHORIZATION_ENVELOPE_GRANTED":
        envelope = copy.deepcopy(payload["authorization_envelope"])
        if envelope["contract_revision_id"] != contract["revision_id"] or envelope["contract_revision_sha256"] != contract_sha256 or envelope["phase_boundary_revision_id"] != contract["accepted_phase_boundary"]["revision_id"] or envelope["phase_boundary_revision_sha256"] != contract["accepted_phase_boundary"]["sha256"]:
            return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.authorization_envelope", "Grant must bind the exact current contract and Phase boundary revisions.")]
        if envelope["envelope_id"] in projection.setdefault("authorization_envelopes", {}):
            return [_v2_issue("RC_EVENT_REPLAY_CONFLICT", "$.payload.authorization_envelope.envelope_id", "Authorization envelope ID already exists.")]
        grant_time = _instant(str(envelope["granted_at"]))
        expires_time = _instant(str(envelope["expires_at"])) if envelope.get("expires_at") is not None else None
        if expires_time is not None and expires_time <= grant_time:
            return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.authorization_envelope.expires_at", "Authorization expiry must be later than its grant time.")]
        limit_units = [str(row.get("unit")) for row in envelope.get("limits", [])]
        if len(limit_units) != len(set(limit_units)):
            return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.authorization_envelope.limits", "Authorization envelope limit units must be unique.")]
        projection.setdefault("authorization_envelopes", {})[envelope["envelope_id"]] = envelope
        projection["active_authorization_envelope_ids"].append(envelope["envelope_id"])
        projection["envelope_usage"].append({"envelope_id": envelope["envelope_id"], "usage": copy.deepcopy(V2_USAGE_ZERO)})
    elif kind == "AUTHORIZATION_ENVELOPE_REVOKED":
        if payload["envelope_id"] not in projection["active_authorization_envelope_ids"]:
            return [_v2_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.envelope_id", "Only an active envelope may be revoked.")]
        projection["active_authorization_envelope_ids"].remove(payload["envelope_id"])
    elif kind == "ROUND_STARTED":
        if projection.get("task_status") == "EXECUTING":
            return [_v2_issue("RC_TRANSITION_INVALID", "$.event_kind", "ROUND_STARTED is only valid before entering EXECUTING from a different state.")]
        projection["current_round_id"] = payload["round_id"]
    elif kind == "ATTEMPT_STARTED":
        if projection.get("task_status") != "EXECUTING":
            return [_v2_issue("RC_TRANSITION_INVALID", "$.event_kind", "Attempt may start only while the Task is EXECUTING.")]
        if projection.setdefault("attempt_states", {}).get(payload["attempt_id"]) != "PLANNED":
            return [_v2_issue("RC_TRANSITION_INVALID", "$.payload.attempt_id", "Attempt must be PLANNED before it starts.")]
        running_attempts = [attempt_id for attempt_id, state in projection["attempt_states"].items() if state == "RUNNING"]
        if running_attempts:
            return [_v2_issue("RC_EVENT_CARDINALITY", "$.payload.attempt_id", "Only one Attempt may be RUNNING in this lineage projection.")]
        projection["current_attempt_id"] = payload["attempt_id"]
        projection["attempt_states"][payload["attempt_id"]] = "RUNNING"
    elif kind == "ATTEMPT_COMPLETED":
        if payload["attempt_state"] not in set(model["attempt_state_machine"]["terminal_states"]):
            return [_v2_issue("RC_TRANSITION_INVALID", "$.payload.attempt_state", "Attempt completion requires a terminal Attempt state.")]
        source_state = projection.setdefault("attempt_states", {}).get(payload["attempt_id"])
        if source_state == "RUNNING" and payload["attempt_id"] != projection.get("current_attempt_id"):
            return [_v2_issue("RC_EVENT_CARDINALITY", "$.payload.attempt_id", "A running completion must identify the current Attempt.")]
        allowed_attempt_targets = _transition_map(model, "attempt_state_machine").get(str(source_state), set())
        if payload["attempt_state"] not in allowed_attempt_targets:
            return [_v2_issue("RC_TRANSITION_INVALID", "$.payload.attempt_state", f"Invalid Attempt transition {source_state} -> {payload['attempt_state']}.")]
        projection["attempt_states"][payload["attempt_id"]] = payload["attempt_state"]
    elif kind == "ATTEMPT_PLANNED":
        if payload["attempt_id"] in projection.setdefault("attempt_states", {}):
            return [_v2_issue("RC_EVENT_REPLAY_CONFLICT", "$.payload.attempt_id", "Attempt ID already exists.")]
        projection["attempt_states"][payload["attempt_id"]] = "PLANNED"
    elif kind == "INVOCATION_PLANNED":
        if payload["invocation_id"] in projection.setdefault("invocation_states", {}):
            return [_v2_issue("RC_EVENT_REPLAY_CONFLICT", "$.payload.invocation_id", "Invocation ID already exists.")]
        projection["invocation_states"][payload["invocation_id"]] = "PLANNED"
    elif kind == "INVOCATION_STARTED":
        if projection.setdefault("invocation_states", {}).get(payload["invocation_id"]) != "PLANNED":
            return [_v2_issue("RC_TRANSITION_INVALID", "$.payload.invocation_id", "Invocation must be PLANNED before it starts.")]
        running_invocations = [invocation_id for invocation_id, state in projection["invocation_states"].items() if state == "RUNNING"]
        if running_invocations:
            return [_v2_issue("RC_EVENT_CARDINALITY", "$.payload.invocation_id", "Only one Invocation may be RUNNING in this lineage projection.")]
        projection["current_invocation_id"] = payload["invocation_id"]
        projection["invocation_states"][payload["invocation_id"]] = "RUNNING"
    elif kind == "INVOCATION_COMPLETED":
        if payload["invocation_state"] not in set(model["invocation_state_machine"]["terminal_states"]):
            return [_v2_issue("RC_TRANSITION_INVALID", "$.payload.invocation_state", "Invocation completion requires a terminal Invocation state.")]
        source_state = projection.setdefault("invocation_states", {}).get(payload["invocation_id"])
        if source_state == "RUNNING" and payload["invocation_id"] != projection.get("current_invocation_id"):
            return [_v2_issue("RC_EVENT_CARDINALITY", "$.payload.invocation_id", "A running completion must identify the current Invocation.")]
        allowed_invocation_targets = _transition_map(model, "invocation_state_machine").get(str(source_state), set())
        if payload["invocation_state"] not in allowed_invocation_targets:
            return [_v2_issue("RC_TRANSITION_INVALID", "$.payload.invocation_state", f"Invalid Invocation transition {source_state} -> {payload['invocation_state']}.")]
        projection["invocation_states"][payload["invocation_id"]] = payload["invocation_state"]
        summary = payload["dispatch_summary"]
        observed_count = sum(
            1
            for intent_id in projection.setdefault("observed_requests", {}).values()
            if projection.setdefault("request_intents", {}).get(str(intent_id)) == payload["invocation_id"]
        )
        if observed_count < summary["confirmed_request_count_min"] or (summary["confirmed_request_count_max"] is not None and observed_count > summary["confirmed_request_count_max"]):
            return [_v2_issue("RC_REQUEST_OBSERVATION_INVALID", "$.payload.dispatch_summary", "Dispatch summary bounds must include every declared physical Request entity.")]
        if summary["dispatch_assessment"] == "CONFIRMED_SENT" and summary["confirmed_request_count_min"] < 1:
            return [_v2_issue("RC_REQUEST_OBSERVATION_INVALID", "$.payload.dispatch_summary", "CONFIRMED_SENT requires at least one confirmed physical Request.")]
        if summary["dispatch_assessment"] == "CONFIRMED_NOT_SENT" and (summary["confirmed_request_count_min"] != 0 or summary["confirmed_request_count_max"] != 0):
            return [_v2_issue("RC_REQUEST_OBSERVATION_INVALID", "$.payload.dispatch_summary", "CONFIRMED_NOT_SENT requires exact zero request bounds.")]
        finite_risk = any(key in contract.get("budgets", {}).get("hard_limits", []) for key in ("physical_requests", "cost"))
        uncertain = summary.get("dispatch_assessment") == "UNKNOWN" or summary.get("observation_completeness") != "COMPLETE" or summary.get("confirmed_request_count_max") is None or summary.get("outcome_state") == "UNKNOWN" or summary.get("charge_state") == "UNKNOWN"
        if finite_risk and uncertain:
            projection["unresolved_side_effects"] = True
            projection["recovery_required"] = True
    elif kind == "EXTERNAL_REQUEST_INTENT_RESERVED":
        intents = projection.setdefault("request_intents", {})
        if payload["request_intent_id"] in intents:
            return [_v2_issue("RC_EVENT_REPLAY_CONFLICT", "$.payload.request_intent_id", "Request Intent ID already exists.")]
        intents[payload["request_intent_id"]] = payload["invocation_id"]
        projection.setdefault("request_intent_records", {})[payload["request_intent_id"]] = copy.deepcopy(payload)
    elif kind == "EXTERNAL_REQUEST_OBSERVED":
        if payload["request_intent_id"] not in projection.setdefault("request_intents", {}):
            return [_v2_issue("RC_EVENT_CARDINALITY", "$.payload.request_intent_id", "Observed Request must bind a declared Request Intent.")]
        if projection["request_intents"][payload["request_intent_id"]] != payload["invocation_id"]:
            return [_v2_issue("RC_EVENT_CARDINALITY", "$.payload.request_intent_id", "Observed Request and Request Intent must belong to the same Invocation.")]
        requests = projection.setdefault("observed_requests", {})
        if payload["observed_request_id"] in requests:
            return [_v2_issue("RC_EVENT_REPLAY_CONFLICT", "$.payload.observed_request_id", "Observed Request ID already exists.")]
        requests[payload["observed_request_id"]] = payload["request_intent_id"]
        projection.setdefault("observed_request_intents", set()).add(payload["request_intent_id"])
    elif kind in {"RECOVERY_OBSERVATION", "CORRECTION_APPENDED"}:
        if (payload.get("unresolved_side_effects") is False or payload.get("recovery_required") is False) and not event.get("evidence_refs"):
            return [_v2_issue("RC_SIDE_EFFECT_UNKNOWN", "$.evidence_refs", "Clearing an unknown side effect or recovery state requires direct appended evidence.")]
        if "unresolved_side_effects" in payload:
            projection["unresolved_side_effects"] = payload["unresolved_side_effects"]
        if "recovery_required" in payload:
            projection["recovery_required"] = payload["recovery_required"]
    _increment_usage(projection, event)
    envelope_id = payload.get("envelope_id")
    if envelope_id:
        row = next((item for item in projection["envelope_usage"] if item["envelope_id"] == envelope_id), None)
        if row is not None:
            temp = {"hard_budget_usage": row["usage"]}
            _increment_usage(temp, event)
    hard_issues = _hard_budget_issues_v2(contract, projection["hard_budget_usage"])
    if hard_issues and kind in {"EXTERNAL_REQUEST_OBSERVED", "USAGE_OBSERVED", "INVOCATION_COMPLETED", "RECOVERY_OBSERVATION", "CORRECTION_APPENDED"}:
        projection["unresolved_side_effects"] = True
        projection["recovery_required"] = True
        return []
    return hard_issues


def _hydrate_internal_state(projection: dict[str, Any], committed: list[dict[str, Any]]) -> None:
    projection.setdefault("authorization_envelopes", {})
    projection.setdefault("attempt_states", {})
    projection.setdefault("invocation_states", {})
    projection.setdefault("request_intents", {})
    projection.setdefault("request_intent_records", {})
    projection.setdefault("observed_requests", {})
    projection.setdefault("observed_request_intents", set())
    projection.setdefault("event_hashes", {})
    for event in committed:
        kind = event.get("event_kind")
        payload = event.get("payload", {})
        projection["event_hashes"][str(event.get("event_id"))] = _sha256(event)
        if kind == "AUTHORIZATION_ENVELOPE_GRANTED" and isinstance(payload.get("authorization_envelope"), dict):
            envelope = copy.deepcopy(payload["authorization_envelope"])
            projection["authorization_envelopes"][envelope["envelope_id"]] = envelope
        elif kind == "AUTHORIZATION_ENVELOPE_REVOKED":
            projection["authorization_envelopes"].setdefault(str(payload.get("envelope_id")), {})
        elif kind == "ATTEMPT_PLANNED":
            projection["attempt_states"][str(payload.get("attempt_id"))] = "PLANNED"
        elif kind == "ATTEMPT_STARTED":
            projection["attempt_states"][str(payload.get("attempt_id"))] = "RUNNING"
        elif kind == "ATTEMPT_COMPLETED":
            projection["attempt_states"][str(payload.get("attempt_id"))] = payload.get("attempt_state")
        elif kind == "INVOCATION_PLANNED":
            projection["invocation_states"][str(payload.get("invocation_id"))] = "PLANNED"
        elif kind == "INVOCATION_STARTED":
            projection["invocation_states"][str(payload.get("invocation_id"))] = "RUNNING"
        elif kind == "INVOCATION_COMPLETED":
            projection["invocation_states"][str(payload.get("invocation_id"))] = payload.get("invocation_state")
        elif kind == "EXTERNAL_REQUEST_INTENT_RESERVED":
            projection["request_intents"][str(payload.get("request_intent_id"))] = payload.get("invocation_id")
            projection["request_intent_records"][str(payload.get("request_intent_id"))] = copy.deepcopy(payload)
        elif kind == "EXTERNAL_REQUEST_OBSERVED":
            projection["observed_requests"][str(payload.get("observed_request_id"))] = payload.get("request_intent_id")
            projection["observed_request_intents"].add(str(payload.get("request_intent_id")))


def _public_projection(value: dict[str, Any]) -> dict[str, Any]:
    public = copy.deepcopy(value)
    for internal_key in (
        "authorization_envelopes", "attempt_states", "invocation_states",
        "request_intents", "request_intent_records", "observed_requests", "observed_request_intents", "event_hashes",
    ):
        public.pop(internal_key, None)
    return public


def _new_v2_projection(
    contract: dict[str, Any],
    model: dict[str, Any],
    invariant_sha256: str,
    projected_at: str,
    contract_sha256: str,
) -> dict[str, Any]:
    return {
        "projection_schema": 1,
        "canonical": False,
        "lineage_id": contract["lineage_id"],
        "task_id": contract["task_id"],
        "phase_id": contract["phase_id"],
        "latest_contract_revision": {
            "revision_id": contract["revision_id"],
            "path": f"task-state/{contract['task_id']}/contracts/{contract['revision_id']}.json",
            "sha256": contract_sha256,
        },
        "latest_event": None,
        "task_status": "DRAFT",
        "terminal_status": None,
        "current_round_id": None,
        "current_attempt_id": None,
        "current_invocation_id": None,
        "hard_budget_usage": copy.deepcopy(V2_USAGE_ZERO),
        "envelope_usage": [],
        "active_authorization_envelope_ids": [],
        "authorization_envelopes": {},
        "unresolved_side_effects": False,
        "recovery_required": False,
        "request_intents": {},
        "request_intent_records": {},
        "observed_requests": {},
        "observed_request_intents": set(),
        "attempt_states": {},
        "invocation_states": {},
        "event_hashes": {},
        "rebuild_inputs": [
            {
                "role": "CONTRACT_REVISION",
                "path": f"task-state/{contract['task_id']}/contracts/{contract['revision_id']}.json",
                "sha256": contract_sha256,
            }
        ],
        "invariant_set_id": model["invariant_set_id"],
        "invariant_source_sha256": invariant_sha256,
        "projected_at": projected_at,
    }


def _semantic_batch_issues(
    contract: dict[str, Any],
    events: list[dict[str, Any]],
    projection: dict[str, Any],
    model: dict[str, Any],
    contract_sha256: str,
) -> list[dict[str, str]]:
    pending_round = False
    pending_attempt_exit = False
    for index, event in enumerate(events):
        kind = event.get("event_kind")
        if pending_attempt_exit and not (
            kind == "STATUS_TRANSITION"
            and event.get("payload", {}).get("from_status") == "EXECUTING"
            and event.get("payload", {}).get("to_status") != "EXECUTING"
        ):
            return [_v2_issue("RC_EVENT_CARDINALITY", f"$.events.{index}", "ATTEMPT_COMPLETED must be followed by an honest transition out of EXECUTING in the same batch.")]
        if pending_attempt_exit:
            pending_attempt_exit = False
        if kind == "ROUND_STARTED":
            if pending_round:
                return [_v2_issue("RC_EVENT_CARDINALITY", f"$.events.{index}", "A pending Round must be paired with its EXECUTING transition before another Round starts.")]
            pending_round = True
        elif kind == "STATUS_TRANSITION" and event.get("payload", {}).get("to_status") == "EXECUTING" and event.get("payload", {}).get("from_status") != "EXECUTING":
            if not pending_round:
                return [_v2_issue("RC_EVENT_CARDINALITY", f"$.events.{index}", "Entering EXECUTING requires a preceding ROUND_STARTED event in the same batch.")]
            pending_round = False
        elif kind == "ATTEMPT_COMPLETED":
            pending_attempt_exit = True
        event_issues = _apply_v2_event(contract, event, projection, model, contract_sha256)
        if event_issues:
            return event_issues
        projection["event_hashes"][event["event_id"]] = _sha256(event)
    if pending_round:
        return [_v2_issue("RC_EVENT_CARDINALITY", "$", "ROUND_STARTED must be paired with the transition into EXECUTING in the same batch.")]
    if pending_attempt_exit:
        return [_v2_issue("RC_EVENT_CARDINALITY", "$", "ATTEMPT_COMPLETED must be paired with a transition out of EXECUTING in the same batch.")]
    return []


def _committed_chain_issues(
    contract: dict[str, Any],
    committed: list[dict[str, Any]],
    projection: dict[str, Any],
    malts_root: Path,
    contract_sha256: str,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    public = _public_projection(projection)
    projection_issues = validate_instance(malts_root, "result-lineage-projection", public)
    if projection_issues:
        return [_v2_issue("RC_LINEAGE_STALE", item.path, item.message) for item in projection_issues]
    if public.get("lineage_id") != contract.get("lineage_id") or public.get("task_id") != contract.get("task_id") or public.get("phase_id") != contract.get("phase_id"):
        return [_v2_issue("RC_LINEAGE_STALE", "$", "Projection identity does not match the Result Contract lineage.")]
    latest_contract = public.get("latest_contract_revision", {})
    contract_sha = contract_sha256
    expected_contract_path = f"task-state/{contract['task_id']}/contracts/{contract['revision_id']}.json"
    if latest_contract != {"revision_id": contract["revision_id"], "path": expected_contract_path, "sha256": contract_sha}:
        return [_v2_issue("RC_LINEAGE_STALE", "$.latest_contract_revision", "Projection does not bind the exact supplied Result Contract revision.")]
    if not committed:
        if public.get("latest_event") is not None:
            return [_v2_issue("RC_LINEAGE_STALE", "$.latest_event", "Projection claims an event head but no committed chain was supplied.")]
        return []
    seen_event_ids: set[str] = set()
    operation_positions: dict[str, list[int]] = {}
    previous_path: str | None = None
    previous_hash: str | None = None
    previous_time: datetime | None = None
    for index, event in enumerate(committed):
        schema_issues = validate_instance(malts_root, "result-event", event)
        if schema_issues:
            return [{"code": item.code, "path": f"$.committed_events.{index}{item.path[1:]}", "message": item.message} for item in schema_issues]
        if event.get("sequence") != index + 1:
            return [_v2_issue("RC_LINEAGE_STALE", f"$.committed_events.{index}.sequence", "Committed event sequence must start at one and remain consecutive.")]
        kind = event.get("event_kind")
        if index == 0 and kind not in {"CONTRACT_REVISION_ACCEPTED", "LEGACY_SNAPSHOT_IMPORTED"}:
            return [_v2_issue("RC_LINEAGE_STALE", "$.committed_events.0.event_kind", "Committed sequence one must establish the accepted contract revision or explicit legacy snapshot.")]
        if index > 0 and kind in {"CONTRACT_REVISION_ACCEPTED", "LEGACY_SNAPSHOT_IMPORTED"}:
            return [_v2_issue("RC_EVENT_CARDINALITY", f"$.committed_events.{index}.event_kind", "Committed contract acceptance or legacy snapshot is valid only at sequence one.")]
        event_id = str(event.get("event_id"))
        if event_id in seen_event_ids:
            return [_v2_issue("RC_EVENT_REPLAY_CONFLICT", f"$.committed_events.{index}.event_id", "Committed event IDs must be unique.")]
        seen_event_ids.add(event_id)
        operation_positions.setdefault(str(event.get("operation_id")), []).append(index)
        expected_previous = None if previous_path is None else {"path": previous_path, "sha256": previous_hash}
        if event.get("previous_event") != expected_previous:
            return [_v2_issue("RC_LINEAGE_STALE", f"$.committed_events.{index}.previous_event", "Committed previous-event hash chain is invalid.")]
        if event.get("lineage_id") != contract.get("lineage_id") or event.get("task_id") != contract.get("task_id") or event.get("phase_id") != contract.get("phase_id"):
            return [_v2_issue("RC_LINEAGE_STALE", f"$.committed_events.{index}", "Committed event identity does not match the Result lineage.")]
        revision = event.get("contract_revision", {})
        if revision.get("revision_id") != contract.get("revision_id") or revision.get("sha256") != contract_sha:
            return [_v2_issue("RC_LINEAGE_STALE", f"$.committed_events.{index}.contract_revision", "Committed event binds a different Result Contract revision.")]
        if event.get("phase_boundary_revision") != contract.get("accepted_phase_boundary"):
            return [_v2_issue("RC_LINEAGE_STALE", f"$.committed_events.{index}.phase_boundary_revision", "Committed event binds a different Phase boundary revision.")]
        recorded_at = _instant(str(event.get("recorded_at")))
        if previous_time is not None and recorded_at <= previous_time:
            return [_v2_issue("RC_LINEAGE_STALE", f"$.committed_events.{index}.recorded_at", "Committed event times must be strictly increasing.")]
        previous_time = recorded_at
        event_path = f"task-state/{contract['task_id']}/events/{event['sequence']}-{event_id}.json"
        previous_path, previous_hash = event_path, _sha256(event)
    if any(positions != list(range(positions[0], positions[-1] + 1)) for positions in operation_positions.values()):
        return [_v2_issue("RC_EVENT_REPLAY_CONFLICT", "$.committed_events", "Events sharing an operation_id must form one contiguous committed batch.")]
    expected_head = {
        "sequence": len(committed), "event_id": committed[-1]["event_id"],
        "path": previous_path, "sha256": previous_hash,
    }
    if public.get("latest_event") != expected_head:
        return [_v2_issue("RC_LINEAGE_STALE", "$.latest_event", "Projection head does not match the exact committed event chain.")]
    event_inputs = [item for item in public.get("rebuild_inputs", []) if item.get("role") == "RESULT_EVENT"]
    expected_inputs = [
        {
            "role": "RESULT_EVENT",
            "path": f"task-state/{contract['task_id']}/events/{event['sequence']}-{event['event_id']}.json",
            "sha256": _sha256(event),
        }
        for event in committed
    ]
    if event_inputs != expected_inputs:
        return [_v2_issue("RC_LINEAGE_STALE", "$.rebuild_inputs", "Projection rebuild inputs do not exactly match the committed event chain.")]
    model, model_issues = load_lifecycle_invariants(malts_root)
    if model is None:
        return [{"code": item.code, "path": item.path, "message": item.message} for item in model_issues]
    invariant_sha256 = hashlib.sha256((malts_root / "tools" / "lifecycle_invariants.json").read_bytes()).hexdigest().upper()
    replay = _new_v2_projection(contract, model, invariant_sha256, committed[-1]["recorded_at"], contract_sha256)
    operation_groups: list[list[dict[str, Any]]] = []
    for event in committed:
        if not operation_groups or operation_groups[-1][0]["operation_id"] != event["operation_id"]:
            operation_groups.append([])
        operation_groups[-1].append(event)
    for group in operation_groups:
        semantic_issues = _semantic_batch_issues(contract, group, replay, model, contract_sha256)
        if semantic_issues:
            return semantic_issues
        for event in group:
            event_path = f"task-state/{contract['task_id']}/events/{event['sequence']}-{event['event_id']}.json"
            event_hash = _sha256(event)
            replay["latest_event"] = {
                "sequence": event["sequence"],
                "event_id": event["event_id"],
                "path": event_path,
                "sha256": event_hash,
            }
            replay["rebuild_inputs"].append({"role": "RESULT_EVENT", "path": event_path, "sha256": event_hash})
    replay["projected_at"] = committed[-1]["recorded_at"]
    if _public_projection(replay) != public:
        return [_v2_issue("RC_LINEAGE_STALE", "$", "Projection does not exactly match semantic replay of the committed event chain.")]
    return issues


def apply_event_batch_v2(
    contract: dict[str, Any],
    events: list[dict[str, Any]],
    projection: dict[str, Any] | None = None,
    committed_events: list[dict[str, Any]] | None = None,
    malts_root: Path = MALTS_ROOT,
    contract_sha256: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Pure, all-or-nothing v2 event replay/application. It performs no I/O."""

    if contract.get("contract_version") != "2":
        return None, {"decision": "DENIED", "issues": [_v2_issue("RC_V2_MIGRATION_REQUIRED", "$.contract_version", "Result v2 event commands require an explicit v1-to-v2 migration.")]}
    contract_issues = _contract_issues(malts_root, contract)
    if contract_issues:
        return None, {"decision": "INVALID_INPUT", "issues": [item.as_dict() for item in contract_issues]}
    if not isinstance(events, list) or not events:
        return None, {"decision": "DENIED", "issues": [_v2_issue("RC_EVENT_BATCH_EMPTY", "$", "A Result event batch must be non-empty.")]}
    effective_contract_sha256 = contract_sha256 or _sha256(contract)
    if not isinstance(effective_contract_sha256, str) or not re.fullmatch(r"[A-F0-9]{64}", effective_contract_sha256):
        return None, {"decision": "INVALID_INPUT", "issues": [_v2_issue("RC_LINEAGE_STALE", "$.contract_sha256", "Contract revision SHA-256 must be 64 uppercase hexadecimal characters.")]}
    model, model_issues = load_lifecycle_invariants(malts_root)
    if model is None:
        return None, {"decision": "INVALID_INPUT", "issues": [{"code": item.code, "path": item.path, "message": item.message} for item in model_issues]}
    invariant_sha256 = hashlib.sha256((malts_root / "tools" / "lifecycle_invariants.json").read_bytes()).hexdigest().upper()
    base = copy.deepcopy(projection) if projection is not None else _new_v2_projection(
        contract, model, invariant_sha256, events[-1].get("recorded_at"), effective_contract_sha256
    )
    if base.get("invariant_set_id") != model.get("invariant_set_id") or base.get("invariant_source_sha256") != invariant_sha256:
        return None, {"decision": "DENIED", "issues": [_v2_issue("RC_LINEAGE_STALE", "$.invariant_source_sha256", "Projection does not bind the exact active lifecycle invariant source.")]}
    committed = list(committed_events or [])
    if projection is None and committed:
        return None, {"decision": "DENIED", "issues": [_v2_issue("RC_LINEAGE_STALE", "$.committed_events", "Committed events require their exact current projection.")]}
    if projection is not None:
        chain_issues = _committed_chain_issues(contract, committed, base, malts_root, effective_contract_sha256)
        if chain_issues:
            return None, {"decision": "DENIED", "issues": chain_issues}
    _hydrate_internal_state(base, committed)
    existing_by_id = {item.get("event_id"): item for item in committed}
    batch_ids = [item.get("event_id") for item in events]
    if len(batch_ids) != len(set(batch_ids)):
        return None, {"decision": "DENIED", "issues": [_v2_issue("RC_EVENT_REPLAY_CONFLICT", "$", "Event IDs within a batch must be unique.")]}
    replayed = [event_id in existing_by_id for event_id in batch_ids]
    if any(replayed):
        operation_ids = {str(event.get("operation_id")) for event in events}
        committed_operation = [item for item in committed if str(item.get("operation_id")) in operation_ids]
        if (
            not all(replayed)
            or len(operation_ids) != 1
            or len(committed_operation) != len(events)
            or [canonical_json(item) for item in committed_operation] != [canonical_json(item) for item in events]
        ):
            return None, {"decision": "DENIED", "issues": [_v2_issue("RC_EVENT_REPLAY_CONFLICT", "$", "A partially replayed or different event batch conflicts with committed history.")]}
        return _public_projection(base), {"decision": "IDEMPOTENT_REPLAY", "issues": [], "accepted_events": 0}
    expected_sequence = 1 if base.get("latest_event") is None else int(base["latest_event"]["sequence"]) + 1
    previous_path = None if base.get("latest_event") is None else base["latest_event"]["path"]
    previous_hash = None if base.get("latest_event") is None else base["latest_event"]["sha256"]
    previous_time = _instant(str(committed[-1]["recorded_at"])) if committed else None
    operation_ids = {str(item.get("operation_id")) for item in committed}
    batch_operation_ids = {str(item.get("operation_id")) for item in events}
    if len(batch_operation_ids) != 1:
        return None, {"decision": "DENIED", "issues": [_v2_issue("RC_EVENT_REPLAY_CONFLICT", "$", "Every event in one batch must share one operation_id.")]}
    batch_operation_id = next(iter(batch_operation_ids))
    if batch_operation_id in operation_ids:
        return None, {"decision": "DENIED", "issues": [_v2_issue("RC_EVENT_REPLAY_CONFLICT", "$", "Operation ID already belongs to a committed batch.")]}
    pending_round = False
    pending_attempt_exit = False
    for index, event in enumerate(events):
        schema_issues = validate_instance(malts_root, "result-event", event)
        if schema_issues:
            return None, {"decision": "DENIED", "issues": [{"code": item.code, "path": item.path, "message": item.message} for item in schema_issues]}
        if event.get("sequence") != expected_sequence:
            return None, {"decision": "DENIED", "issues": [_v2_issue("RC_LINEAGE_STALE", f"$.events.{index}.sequence", "Event sequence is not consecutive from the current head.")]}
        event_time = _instant(str(event.get("recorded_at")))
        if previous_time is not None and event_time <= previous_time:
            return None, {"decision": "DENIED", "issues": [_v2_issue("RC_LINEAGE_STALE", f"$.events.{index}.recorded_at", "Event times must be strictly increasing by instant.")]}
        previous_time = event_time
        if expected_sequence == 1 and event.get("event_kind") not in {"CONTRACT_REVISION_ACCEPTED", "LEGACY_SNAPSHOT_IMPORTED"}:
            return None, {"decision": "DENIED", "issues": [_v2_issue("RC_LINEAGE_STALE", f"$.events.{index}.event_kind", "Sequence one must establish the accepted contract revision or explicit legacy snapshot.")]}
        if expected_sequence > 1 and event.get("event_kind") in {"CONTRACT_REVISION_ACCEPTED", "LEGACY_SNAPSHOT_IMPORTED"}:
            return None, {"decision": "DENIED", "issues": [_v2_issue("RC_EVENT_CARDINALITY", f"$.events.{index}.event_kind", "Contract acceptance or legacy snapshot is permitted only as the sequence-one lineage initializer.")]}
        expected_previous = None if previous_path is None else {"path": previous_path, "sha256": previous_hash}
        if event.get("previous_event") != expected_previous:
            return None, {"decision": "DENIED", "issues": [_v2_issue("RC_LINEAGE_STALE", f"$.events.{index}.previous_event", "Event previous binding does not match the exact current head.")]}
        revision = event.get("contract_revision", {})
        if revision.get("revision_id") != contract.get("revision_id") or revision.get("sha256") != effective_contract_sha256:
            return None, {"decision": "DENIED", "issues": [_v2_issue("RC_LINEAGE_STALE", f"$.events.{index}.contract_revision", "Event binds a stale Result Contract revision.")]}
        boundary = event.get("phase_boundary_revision", {})
        if boundary != contract.get("accepted_phase_boundary"):
            return None, {"decision": "DENIED", "issues": [_v2_issue("RC_LINEAGE_STALE", f"$.events.{index}.phase_boundary_revision", "Event binds a stale Phase boundary revision.")]}
        kind = event.get("event_kind")
        if pending_attempt_exit and not (
            kind == "STATUS_TRANSITION"
            and event.get("payload", {}).get("from_status") == "EXECUTING"
            and event.get("payload", {}).get("to_status") != "EXECUTING"
        ):
            return None, {"decision": "DENIED", "issues": [_v2_issue("RC_EVENT_CARDINALITY", f"$.events.{index}", "ATTEMPT_COMPLETED must be followed by an honest transition out of EXECUTING in the same batch.")]}
        if pending_attempt_exit:
            pending_attempt_exit = False
        if kind == "ROUND_STARTED":
            if pending_round:
                return None, {"decision": "DENIED", "issues": [_v2_issue("RC_EVENT_CARDINALITY", f"$.events.{index}", "A pending Round must be paired with its EXECUTING transition before another Round starts.")]}
            pending_round = True
        elif kind == "STATUS_TRANSITION" and event.get("payload", {}).get("to_status") == "EXECUTING" and event.get("payload", {}).get("from_status") != "EXECUTING":
            if not pending_round:
                return None, {"decision": "DENIED", "issues": [_v2_issue("RC_EVENT_CARDINALITY", f"$.events.{index}", "Entering EXECUTING requires a preceding ROUND_STARTED event in the same batch.")]}
            pending_round = False
        elif kind == "ATTEMPT_COMPLETED":
            pending_attempt_exit = True
        event_issues = _apply_v2_event(contract, event, base, model, effective_contract_sha256)
        if event_issues:
            return None, {"decision": "DENIED", "issues": event_issues}
        event_path = f"task-state/{contract['task_id']}/events/{event['sequence']}-{event['event_id']}.json"
        event_hash = _sha256(event)
        base["event_hashes"][event["event_id"]] = event_hash
        base["latest_event"] = {"sequence": event["sequence"], "event_id": event["event_id"], "path": event_path, "sha256": event_hash}
        previous_path, previous_hash = event_path, event_hash
        expected_sequence += 1
        base["rebuild_inputs"].append({"role": "RESULT_EVENT", "path": event_path, "sha256": event_hash})
    if pending_round:
        return None, {"decision": "DENIED", "issues": [_v2_issue("RC_EVENT_CARDINALITY", "$", "ROUND_STARTED must be paired with the transition into EXECUTING in the same batch.")]}
    if pending_attempt_exit:
        return None, {"decision": "DENIED", "issues": [_v2_issue("RC_EVENT_CARDINALITY", "$", "ATTEMPT_COMPLETED must be paired with a transition out of EXECUTING in the same batch.")]}
    base["projected_at"] = events[-1]["recorded_at"]
    public_projection = _public_projection(base)
    projection_issues = validate_instance(malts_root, "result-lineage-projection", public_projection)
    if projection_issues:
        return None, {"decision": "DENIED", "issues": [{"code": item.code, "path": item.path, "message": item.message} for item in projection_issues]}
    return public_projection, {"decision": "APPLIED", "issues": [], "accepted_events": len(events), "latest_event": copy.deepcopy(base["latest_event"])}


def rebuild_lineage_projection_v2(
    contract: dict[str, Any],
    committed_events: list[dict[str, Any]],
    malts_root: Path = MALTS_ROOT,
    contract_sha256: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Rebuild one Result v2 projection from an explicitly supplied chain.

    The function is pure. Callers remain responsible for proving that the supplied
    objects came from the declared regular files and that their canonical bytes
    match the hashes bound into the chain.
    """

    if contract.get("contract_version") != "2":
        return None, {"decision": "DENIED", "issues": [_v2_issue("RC_V2_MIGRATION_REQUIRED", "$.contract_version", "Result v2 lineage rebuild requires an explicit v1-to-v2 migration.")]}
    contract_issues = _contract_issues(malts_root, contract)
    if contract_issues:
        return None, {"decision": "INVALID_INPUT", "issues": [item.as_dict() for item in contract_issues]}
    effective_contract_sha256 = contract_sha256 or _sha256(contract)
    if not isinstance(effective_contract_sha256, str) or not re.fullmatch(r"[A-F0-9]{64}", effective_contract_sha256):
        return None, {"decision": "INVALID_INPUT", "issues": [_v2_issue("RC_LINEAGE_STALE", "$.contract_sha256", "Contract revision SHA-256 must be 64 uppercase hexadecimal characters.")]}
    model, model_issues = load_lifecycle_invariants(malts_root)
    if model is None:
        return None, {"decision": "INVALID_INPUT", "issues": [{"code": item.code, "path": item.path, "message": item.message} for item in model_issues]}
    invariant_sha256 = hashlib.sha256((malts_root / "tools" / "lifecycle_invariants.json").read_bytes()).hexdigest().upper()
    if not committed_events:
        projected_at = str(contract.get("accepted_at", "1970-01-01T00:00:00Z"))
        projection = _public_projection(
            _new_v2_projection(contract, model, invariant_sha256, projected_at, effective_contract_sha256)
        )
        projection_issues = validate_instance(malts_root, "result-lineage-projection", projection)
        if projection_issues:
            return None, {"decision": "DENIED", "issues": [{"code": item.code, "path": item.path, "message": item.message} for item in projection_issues]}
        return projection, {"decision": "REBUILT", "issues": [], "accepted_events": 0}

    projection: dict[str, Any] | None = None
    accepted: list[dict[str, Any]] = []
    index = 0
    while index < len(committed_events):
        operation_id = committed_events[index].get("operation_id")
        end = index + 1
        while end < len(committed_events) and committed_events[end].get("operation_id") == operation_id:
            end += 1
        group = committed_events[index:end]
        projection, decision = apply_event_batch_v2(
            contract,
            group,
            projection,
            accepted,
            malts_root,
            effective_contract_sha256,
        )
        if projection is None:
            return None, decision
        accepted.extend(copy.deepcopy(group))
        index = end
    return projection, {"decision": "REBUILT", "issues": [], "accepted_events": len(accepted), "latest_event": copy.deepcopy(projection.get("latest_event"))}


def _write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {path}")
    if not path.parent.is_dir():
        raise FileNotFoundError(f"Output parent does not exist: {path.parent}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MALTS deterministic Result Contract controller")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="Validate one Result Contract")
    validate.add_argument("--contract", required=True, type=Path)
    advance = subparsers.add_parser("advance", help="Apply one event and write a new Result Contract")
    advance.add_argument("--contract", required=True, type=Path)
    advance.add_argument("--event", required=True, type=Path)
    advance.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        contract = load_json(args.contract)
        if args.command == "validate":
            issues = _contract_issues(MALTS_ROOT, contract)
            print(json.dumps({"status": "PASS" if not issues else "FAIL", "issues": [item.as_dict() for item in issues]}, ensure_ascii=False, indent=2))
            return 0 if not issues else 2
        event = load_json(args.event)
        updated, result = apply_event(contract, event)
        if updated is None:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2
        _write_new_json(args.output, updated)
        print(json.dumps({**result, "output": str(args.output), "execution_status": updated["execution_status"]}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"decision": "ERROR", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
