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
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from malts_user_contracts import ContractIssue, load_json, validate_instance


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
