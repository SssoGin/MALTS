#!/usr/bin/env python3
"""Runtime contract validation required by installed MALTS users.

This module validates only the contracts used by user-side MALTS capabilities.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


USER_CONTRACTS = {
    "result-contract": "result_contract.schema.json",
    "growth-signal": "growth_signal.schema.json",
    "growth-candidate": "growth_candidate.schema.json",
    "future-use-validation": "future_use_validation.schema.json",
    "growth-ledger": "growth_ledger.schema.json",
    "model-profile": "model_profile.schema.json",
    "runtime-capability-evidence": "runtime_capability_evidence.schema.json",
    "capability-descriptor": "capability_descriptor.schema.json",
    "external-capability-sidecar": "external_capability_sidecar.schema.json",
    "capability-registry": "capability_registry.schema.json",
    "projection-manifest": "projection_manifest.schema.json",
    "workspace-control": "workspace_control.schema.json",
    "generation-manifest": "generation_manifest.schema.json",
    "release-manifest": "release_manifest.schema.json",
    "installation-registry": "installation_registry.schema.json",
    "update-plan": "update_plan.schema.json",
    "transaction-journal": "transaction_journal.schema.json",
    "residue-tombstone": "residue_tombstone.schema.json",
}
TERMINAL_STATUSES = {"DONE", "PARTIAL", "BLOCKED", "FAILED"}
EVIDENCE_STRENGTH = {"D": 1, "C": 2, "B": 3, "A": 4}
MACHINE_LOCATOR = re.compile(r"^(?:[A-Za-z]:[\/]|[\/]{2}|~[\/]|[A-Za-z][A-Za-z0-9+.-]*://|git@)")
PRIVATE_PATH_LITERAL = re.compile(r"(?:[A-Za-z]:[\/]|\\)")
SECRET_ASSIGNMENT = re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S+")
RELEASE_TOOL_NAMES = {"codex": "Codex", "claude-code": "Claude Code", "opencode": "OpenCode"}
RELEASE_HOST_PREREQUISITES = {"windows", "powershell", "python"}


@dataclass(frozen=True)
class ContractIssue:
    code: str
    path: str
    message: str

    def render(self) -> str:
        return f"[{self.code}] {self.path}: {self.message}"

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def canonical_plan_hash(plan: dict[str, Any]) -> str:
    payload = copy.deepcopy(plan)
    payload.pop("plan_hash", None)
    return hashlib.sha256(canonical_json(payload)).hexdigest().upper()

def _issue(code: str, path: str, message: str) -> ContractIssue:
    return ContractIssue(code, path, message)

def _resolve_ref(schema_root: dict[str, Any], ref: str) -> dict[str, Any] | None:
    if not ref.startswith("#/"):
        return None
    current: Any = schema_root
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current if isinstance(current, dict) else None

def _matches_type(value: Any, declared: str) -> bool:
    if declared == "null":
        return value is None
    if declared == "object":
        return isinstance(value, dict)
    if declared == "array":
        return isinstance(value, list)
    if declared == "string":
        return isinstance(value, str)
    if declared == "boolean":
        return isinstance(value, bool)
    if declared == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False

def _valid_datetime(value: str) -> bool:
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
        return parsed.tzinfo is not None
    except ValueError:
        return False

def validate_against_schema(instance: Any, schema: dict[str, Any], path: str = "$") -> list[ContractIssue]:
    issues: list[ContractIssue] = []

    def visit(value: Any, node: dict[str, Any], current_path: str) -> None:
        if "$ref" in node:
            resolved = _resolve_ref(schema, str(node["$ref"]))
            if resolved is None:
                issues.append(_issue("SCHEMA_REF", current_path, f"Cannot resolve {node['$ref']}"))
                return
            visit(value, resolved, current_path)
            return

        declared = node.get("type")
        if declared is not None:
            allowed = [declared] if isinstance(declared, str) else list(declared)
            if not any(_matches_type(value, item) for item in allowed):
                issues.append(_issue("SCHEMA_TYPE", current_path, f"Expected type {allowed}, found {type(value).__name__}."))
                return

        if "const" in node and value != node["const"]:
            code = "SCHEMA_VERSION_UNSUPPORTED" if current_path.endswith((".schema_version", ".contract_version")) else "SCHEMA_CONST"
            issues.append(_issue(code, current_path, f"Expected constant {node['const']!r}."))
        if "enum" in node and value not in node["enum"]:
            issues.append(_issue("SCHEMA_ENUM", current_path, f"Value {value!r} is not in the allowed enumeration."))

        if isinstance(value, dict):
            required = node.get("required", [])
            for key in required:
                if key not in value:
                    issues.append(_issue("SCHEMA_REQUIRED", f"{current_path}.{key}", "Required property is missing."))
            properties = node.get("properties", {})
            if node.get("additionalProperties") is False:
                for key in value:
                    if key not in properties:
                        issues.append(_issue("SCHEMA_CLOSED_OBJECT", f"{current_path}.{key}", "Unknown property is forbidden."))
            for key, child in value.items():
                if key in properties:
                    visit(child, properties[key], f"{current_path}.{key}")

        if isinstance(value, list):
            if "minItems" in node and len(value) < node["minItems"]:
                issues.append(_issue("SCHEMA_MIN_ITEMS", current_path, f"Expected at least {node['minItems']} items."))
            if "maxItems" in node and len(value) > node["maxItems"]:
                issues.append(_issue("SCHEMA_MAX_ITEMS", current_path, f"Expected at most {node['maxItems']} items."))
            if node.get("uniqueItems"):
                canonical = [canonical_json(item) for item in value]
                if len(canonical) != len(set(canonical)):
                    issues.append(_issue("SCHEMA_UNIQUE_ITEMS", current_path, "Array items must be unique."))
            item_schema = node.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(value):
                    visit(item, item_schema, f"{current_path}.{index}")

        if isinstance(value, str):
            if "minLength" in node and len(value) < node["minLength"]:
                issues.append(_issue("SCHEMA_MIN_LENGTH", current_path, f"Expected length >= {node['minLength']}."))
            if "pattern" in node and re.fullmatch(node["pattern"], value) is None:
                issues.append(_issue("SCHEMA_PATTERN", current_path, f"Value does not match {node['pattern']}"))
            if node.get("format") == "date-time" and not _valid_datetime(value):
                issues.append(_issue("SCHEMA_FORMAT", current_path, "Value must be an ISO-8601 date-time with timezone."))

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in node and value < node["minimum"]:
                issues.append(_issue("SCHEMA_MINIMUM", current_path, f"Value must be >= {node['minimum']}."))
            if "maximum" in node and value > node["maximum"]:
                issues.append(_issue("SCHEMA_MAXIMUM", current_path, f"Value must be <= {node['maximum']}."))

    visit(instance, schema, path)
    return issues

def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        normalized = value.casefold()
        if normalized in seen:
            duplicates.add(normalized)
        seen.add(normalized)
    return duplicates

def _graph_has_cycle(graph: dict[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for target in graph.get(node, set()):
            if target in graph and visit(target):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)

def _semantic_result_contract(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    status = value.get("execution_status")
    terminal = value.get("terminal_status")
    if status in TERMINAL_STATUSES:
        if terminal != status:
            issues.append(_issue("RC_TERMINAL_STATUS", "$.terminal_status", "Terminal status must equal execution_status."))
    elif terminal is not None:
        issues.append(_issue("RC_TERMINAL_STATUS", "$.terminal_status", "Non-terminal execution must use null terminal_status."))

    history = value.get("status_history", [])
    if history and history[-1].get("status") != status:
        issues.append(_issue("RC_STATUS_HISTORY", "$.status_history", "Last history state must equal execution_status."))
    if history and history[0].get("status") != "DRAFT":
        issues.append(_issue("RC_HISTORY_START", "$.status_history.0.status", "Result history must start at DRAFT."))
    event_ids = [item.get("event_id", "") for item in history]
    if _duplicates(event_ids):
        issues.append(_issue("RC_DUPLICATE_EVENT", "$.status_history", "Status event IDs must be unique."))
    parsed_times: list[datetime] = []
    for item in history:
        raw = item.get("at")
        if not isinstance(raw, str) or not _valid_datetime(raw):
            continue
        normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        parsed_times.append(datetime.fromisoformat(normalized))
    if len(parsed_times) == len(history) and any(current <= previous for previous, current in zip(parsed_times, parsed_times[1:])):
        issues.append(_issue("RC_HISTORY_TIME_ORDER", "$.status_history", "Status event times must be strictly increasing."))
    if any(item.get("status") in TERMINAL_STATUSES for item in history[:-1]):
        issues.append(_issue("RC_TERMINAL_IMMUTABLE", "$.status_history", "No event may follow a terminal status."))
    allowed = {
        "DRAFT": {"PREFLIGHT", "BLOCKED", "FAILED"},
        "PREFLIGHT": {"AWAITING_AUTHORIZATION", "BLOCKED", "FAILED"},
        "AWAITING_AUTHORIZATION": {"AUTHORIZED", "BLOCKED"},
        "AUTHORIZED": {"PLANNING", "BLOCKED", "FAILED"},
        "PLANNING": {"EXECUTING", "BLOCKED", "FAILED"},
        "EXECUTING": {"VERIFYING", "REPLANNING", "PARTIAL", "BLOCKED", "FAILED"},
        "VERIFYING": {"FINALIZING", "REPLANNING", "EXECUTING", "PARTIAL", "BLOCKED", "FAILED"},
        "REPLANNING": {"EXECUTING", "BLOCKED", "FAILED"},
        "FINALIZING": TERMINAL_STATUSES,
    }
    for previous, current in zip(history, history[1:]):
        if current.get("status") not in allowed.get(previous.get("status"), set()):
            issues.append(_issue("RC_STATUS_TRANSITION", "$.status_history", f"Invalid transition {previous.get('status')} -> {current.get('status')}."))
            break

    authorized_locators = {
        item.get("locator") for item in value.get("authorized_scope", {}).get("resources", []) if isinstance(item, dict)
    }
    for index, event in enumerate(history):
        event_status = event.get("status")
        event_scope = set(event.get("scope_locators", []))
        if event_scope.difference(authorized_locators):
            issues.append(_issue("RC_SCOPE_OUTSIDE_AUTH", f"$.status_history.{index}.scope_locators", "Event scope must stay inside authorized resources."))
        if event_status in {"DRAFT", "PREFLIGHT", "AWAITING_AUTHORIZATION"} and event_scope:
            issues.append(_issue("RC_PREAUTH_SCOPE", f"$.status_history.{index}.scope_locators", "Pre-authorization states cannot carry executable scope."))
        retry_basis = event.get("retry_basis")
        if event_status == "REPLANNING":
            if retry_basis is None:
                issues.append(_issue("RC_RETRY_NOVELTY", f"$.status_history.{index}.retry_basis", "Replanning requires new information, a new strategy, or a smaller scope."))
            elif index == 0:
                issues.append(_issue("RC_RETRY_NOVELTY", f"$.status_history.{index}.retry_basis", "Replanning requires a prior attempt."))
            else:
                previous = history[index - 1]
                if retry_basis == "new_information" and not event.get("new_information_refs"):
                    issues.append(_issue("RC_RETRY_NOVELTY", f"$.status_history.{index}.new_information_refs", "new_information retry requires direct references."))
                if retry_basis == "new_strategy" and (not event.get("strategy_id") or event.get("strategy_id") == previous.get("strategy_id")):
                    issues.append(_issue("RC_RETRY_NOVELTY", f"$.status_history.{index}.strategy_id", "new_strategy retry must change strategy_id."))
                if retry_basis == "smaller_scope":
                    previous_scope = set(previous.get("scope_locators", []))
                    if not event_scope or not previous_scope or not event_scope < previous_scope:
                        issues.append(_issue("RC_RETRY_NOVELTY", f"$.status_history.{index}.scope_locators", "smaller_scope retry must be a strict non-empty subset."))
        elif retry_basis is not None:
            issues.append(_issue("RC_RETRY_BASIS_STATE", f"$.status_history.{index}.retry_basis", "retry_basis is only valid on REPLANNING events."))
        if event_status in {"REPLANNING", "BLOCKED", "FAILED"} and event.get("failure_class") is None:
            issues.append(_issue("RC_FAILURE_CLASS", f"$.status_history.{index}.failure_class", "Failure, blocker, and replan events require a failure classification."))

    criteria = value.get("acceptance_criteria", [])
    criterion_ids = [item.get("criterion_id", "") for item in criteria]
    if _duplicates(criterion_ids):
        issues.append(_issue("RC_DUPLICATE_CRITERION", "$.acceptance_criteria", "Criterion IDs must be unique."))
    verification = value.get("verification", [])
    by_criterion: dict[str, list[dict[str, Any]]] = {}
    for entry in verification:
        by_criterion.setdefault(entry.get("criterion_id", ""), []).append(entry)
        if entry.get("criterion_id") not in criterion_ids:
            issues.append(_issue("RC_UNKNOWN_CRITERION", "$.verification", f"Verification references unknown criterion {entry.get('criterion_id')}."))

    if status == "DONE":
        if any(item.get("hard") and item.get("status") != "PASS" for item in criteria):
            issues.append(_issue("RC_DONE_HARD_CRITERIA", "$.acceptance_criteria", "DONE requires every hard criterion to PASS."))
        for item in criteria:
            if not item.get("hard"):
                continue
            candidates = [entry for entry in by_criterion.get(item.get("criterion_id", ""), []) if entry.get("result") == "PASS"]
            minimum = EVIDENCE_STRENGTH.get(item.get("minimum_evidence_level"), 99)
            if not any(EVIDENCE_STRENGTH.get(entry.get("evidence_level"), 0) >= minimum and entry.get("evidence_refs") for entry in candidates):
                issues.append(_issue("RC_DONE_EVIDENCE", "$.verification", f"Hard criterion {item.get('criterion_id')} lacks sufficient PASS evidence."))
        if value.get("remaining_work"):
            issues.append(_issue("RC_DONE_REMAINING_WORK", "$.remaining_work", "DONE requires no remaining work."))
        if not value.get("deliverables") or any(item.get("status") != "verified" or item.get("sha256") is None for item in value.get("deliverables", [])):
            issues.append(_issue("RC_DONE_DELIVERABLES", "$.deliverables", "DONE requires hashed verified deliverables."))
    if status == "PARTIAL" and not value.get("remaining_work"):
        issues.append(_issue("RC_PARTIAL_REMAINING_WORK", "$.remaining_work", "PARTIAL requires explicit remaining work."))
    recovery = value.get("recovery_point", {})
    if recovery.get("status") != status:
        issues.append(_issue("RC_RECOVERY_STATUS", "$.recovery_point.status", "Recovery status must equal execution_status."))
    if status == "BLOCKED" and not recovery.get("blockers"):
        issues.append(_issue("RC_BLOCKED_EVIDENCE", "$.recovery_point.blockers", "BLOCKED requires blocker evidence."))
    if status == "FAILED" and not recovery.get("failure_evidence"):
        issues.append(_issue("RC_FAILED_EVIDENCE", "$.recovery_point.failure_evidence", "FAILED requires failure evidence."))

    budgets = value.get("budgets", {})
    usage = value.get("budget_usage", {})
    budget_fields = {
        "rounds": ("max_rounds", "rounds_used"),
        "time": ("max_elapsed_seconds", "elapsed_seconds"),
        "tokens": ("max_tokens", "tokens_used"),
        "cost": ("max_cost_units", "cost_units_used"),
        "concurrency": ("max_concurrency", "peak_concurrency"),
    }
    for hard_limit in budgets.get("hard_limits", []):
        limit_field, usage_field = budget_fields[hard_limit]
        limit = budgets.get(limit_field)
        if limit is None:
            issues.append(_issue("RC_BUDGET_CONFIG", f"$.budgets.{limit_field}", f"Hard limit {hard_limit} requires a numeric maximum."))
        elif usage.get(usage_field, 0) > limit:
            issues.append(_issue("RC_HARD_BUDGET_EXCEEDED", f"$.budget_usage.{usage_field}", f"Hard {hard_limit} budget has been exceeded."))
    if recovery.get("budget_usage") != usage:
        issues.append(_issue("RC_RECOVERY_BUDGET", "$.recovery_point.budget_usage", "Recovery point must persist the current budget usage."))
    if history and recovery.get("last_event_id") != history[-1].get("event_id"):
        issues.append(_issue("RC_RECOVERY_EVENT", "$.recovery_point.last_event_id", "Recovery point must reference the latest status event."))
    if recovery.get("round") != usage.get("rounds_used"):
        issues.append(_issue("RC_RECOVERY_ROUND", "$.recovery_point.round", "Recovery round must equal rounds_used."))
    if history and recovery.get("strategy_id") != history[-1].get("strategy_id"):
        issues.append(_issue("RC_RECOVERY_STRATEGY", "$.recovery_point.strategy_id", "Recovery strategy must equal the latest status event strategy."))

    continuation = value.get("continuation_policy", {})
    unattended = value.get("authorized_scope", {}).get("unattended", {})
    if continuation.get("mode") == "bounded-auto" and (
        not continuation.get("authorization_ref")
        or not continuation.get("max_authorized_rounds")
        or not unattended.get("allowed")
    ):
        issues.append(_issue("RC_BOUNDED_AUTO_AUTH", "$.continuation_policy", "bounded-auto requires explicit authorization, a round bound, and unattended scope."))
    if continuation.get("mode") == "bounded-auto":
        bounds = [
            continuation.get("max_authorized_rounds"),
            unattended.get("max_rounds"),
            budgets.get("max_rounds"),
        ]
        numeric_bounds = [item for item in bounds if isinstance(item, int)]
        if len(numeric_bounds) != 3 or continuation.get("max_authorized_rounds") > min(numeric_bounds[1:]):
            issues.append(_issue("RC_BOUNDED_AUTO_BUDGET", "$.continuation_policy.max_authorized_rounds", "bounded-auto rounds must not exceed unattended or contract round budgets."))
    multi = value.get("authorized_scope", {}).get("multi_agent", {})
    if (multi.get("allowed") and multi.get("max_agents", 0) < 1) or (not multi.get("allowed") and multi.get("max_agents") != 0):
        issues.append(_issue("RC_MULTI_AGENT_SCOPE", "$.authorized_scope.multi_agent", "max_agents must match the multi-agent authorization flag."))
    if multi.get("allowed") and not multi.get("launch_review_ref"):
        issues.append(_issue("RC_MULTI_AGENT_LAUNCH_REVIEW", "$.authorized_scope.multi_agent.launch_review_ref", "Multi-agent authorization requires a launch review reference."))
    if not multi.get("allowed") and multi.get("launch_review_ref") is not None:
        issues.append(_issue("RC_MULTI_AGENT_LAUNCH_REVIEW", "$.authorized_scope.multi_agent.launch_review_ref", "Single-agent scope must not imply launch review authorization."))
    if not multi.get("allowed") and multi.get("approved_batches"):
        issues.append(_issue("RC_MULTI_AGENT_BATCH_SCOPE", "$.authorized_scope.multi_agent.approved_batches", "Single-agent scope cannot approve dispatch batches."))
    locators = {item.get("locator") for item in value.get("authorized_scope", {}).get("resources", [])}
    if locators.intersection(set(value.get("prohibited_scope", []))):
        issues.append(_issue("RC_SCOPE_CONFLICT", "$.authorized_scope", "An exact resource locator is both authorized and prohibited."))
    return issues

def _semantic_growth_signal(value: dict[str, Any]) -> list[ContractIssue]:
    if value.get("sensitivity") == "secret" and not value.get("redacted"):
        return [_issue("GR_SECRET_UNREDACTED", "$.redacted", "Secret growth evidence must be redacted.")]
    return []

def _semantic_future_validation(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    harmful = value.get("outcome") == "harmful"
    if harmful and not value.get("challenge_case"):
        issues.append(_issue("GR_HARMFUL_UNCHALLENGED", "$.challenge_case", "Harmful outcomes must open a challenge case."))
    if harmful and value.get("severity") == "none":
        issues.append(_issue("GR_HARMFUL_SEVERITY", "$.severity", "Harmful evidence requires a non-none severity."))
    if not harmful and value.get("severity") != "none":
        issues.append(_issue("GR_NONHARMFUL_SEVERITY", "$.severity", "Non-harmful validation must use severity none."))
    if value.get("validation_kind") == "counterexample" and not value.get("challenge_case"):
        issues.append(_issue("GR_COUNTEREXAMPLE_CHALLENGE", "$.challenge_case", "Counterexample validation must open a challenge case."))
    return issues

def _semantic_growth_candidate(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    validations = value.get("future_use_validations", [])
    indices = [item.get("use_index") for item in validations]
    if len(indices) != len(set(indices)):
        issues.append(_issue("GR_DUPLICATE_USE_INDEX", "$.future_use_validations", "use_index values must be unique."))
    validation_ids = [item.get("validation_id", "") for item in validations]
    if _duplicates(validation_ids):
        issues.append(_issue("GR_DUPLICATE_VALIDATION", "$.future_use_validations", "Validation IDs must be unique."))
    for index, validation in enumerate(validations):
        for issue in _semantic_future_validation(validation):
            issues.append(_issue(issue.code, f"$.future_use_validations.{index}{issue.path[1:]}", issue.message))
    validated_states = {"VALIDATED", "SYSTEM_PROMOTION_PROPOSED", "ACCEPTED"}
    if value.get("status") in validated_states:
        helped = [item for item in validations if item.get("validation_kind") == "future_use" and item.get("outcome") == "helped"]
        future_tasks = {item.get("future_task_id") for item in helped}
        independence = {item.get("independence_key") for item in helped}
        if len(helped) < 2 or len(future_tasks) < 2 or len(independence) < 2:
            issues.append(_issue("GR_VALIDATION_THRESHOLD", "$.future_use_validations", "Validated growth requires two helped future tasks across two independent contexts; the source event is the third total validation."))
        if value.get("risk_level") in {"high", "critical"}:
            supplemental = [
                item for item in validations
                if item.get("validation_kind") in {"independent_review", "negative_test", "counterexample"}
                and item.get("outcome") in {"helped", "neutral"}
            ]
            if not supplemental:
                issues.append(_issue("GR_HIGH_RISK_VALIDATION", "$.future_use_validations", "High-risk candidates require an independent review or negative/counterexample test."))
        if any(item.get("outcome") == "harmful" for item in validations):
            issues.append(_issue("GR_HARMFUL_VALIDATED", "$.future_use_validations", "A candidate with harmful evidence cannot remain validated."))
    harmful = [item for item in validations if item.get("outcome") == "harmful"]
    severe = [item for item in harmful if item.get("severity") in {"high", "critical"}]
    if severe and value.get("status") not in {"SUSPENDED", "REJECTED", "DEPRECATED", "REMOVED"}:
        issues.append(_issue("GR_SEVERE_NOT_SUSPENDED", "$.status", "Severe harmful evidence must suspend or retire the candidate."))
    if harmful and not severe and value.get("status") not in {"CHALLENGED", "SUSPENDED", "REJECTED", "DEPRECATED", "REMOVED"}:
        issues.append(_issue("GR_HARMFUL_UNCHALLENGED", "$.status", "Harmful evidence must challenge, suspend, reject, deprecate, or remove the candidate."))
    if value.get("status") in {"CHALLENGED", "SUSPENDED"} and not value.get("challenge_refs"):
        issues.append(_issue("GR_CHALLENGE_REFS", "$.challenge_refs", "Challenged and suspended candidates require challenge evidence."))
    if value.get("status") in {"SYSTEM_PROMOTION_PROPOSED", "ACCEPTED"}:
        if value.get("authority_level") != "L3":
            issues.append(_issue("GR_PROMOTION_AUTHORITY", "$.authority_level", "System promotion requires L3 authority."))
        if not value.get("promotion_authorization_ref"):
            issues.append(_issue("GR_PROMOTION_AUTHORIZATION", "$.promotion_authorization_ref", "System promotion requires a separate authorization reference."))
    if value.get("status") in {"CHALLENGED", "SUSPENDED", "REJECTED", "DEPRECATED", "REMOVED", "ACCEPTED"} and not value.get("status_reason"):
        issues.append(_issue("GR_STATUS_REASON", "$.status_reason", "Terminal lifecycle decisions require a reason."))

    profile = value.get("retrieval_profile", {})
    if not any(profile.get(key) for key in ("task_types", "risk_levels", "tools", "workspace_keys", "failure_signatures")):
        issues.append(_issue("GR_RETRIEVAL_PROFILE", "$.retrieval_profile", "At least one retrieval dimension must be declared."))
    review = value.get("anti_pollution_review", {})
    advancing_states = {"PROJECT_EXPERIMENTAL", "FUTURE_USE_VALIDATING", "VALIDATED", "SYSTEM_PROMOTION_PROPOSED", "ACCEPTED"}
    if value.get("status") in advancing_states:
        if review.get("dedup_conflict_status") == "conflict":
            issues.append(_issue("GR_ANTI_POLLUTION_CONFLICT", "$.anti_pollution_review.dedup_conflict_status", "Conflicting candidates cannot advance."))
        if review.get("sensitivity_status") == "fail":
            issues.append(_issue("GR_ANTI_POLLUTION_SENSITIVE", "$.anti_pollution_review.sensitivity_status", "Candidates that fail sensitivity review cannot advance."))
        if review.get("automation_safety_status") == "fail":
            issues.append(_issue("GR_ANTI_POLLUTION_AUTOMATION", "$.anti_pollution_review.automation_safety_status", "Candidates that fail automation safety review cannot advance."))
    if review.get("dedup_conflict_status") in {"related", "conflict"} and not review.get("dedup_conflict_refs"):
        issues.append(_issue("GR_DEDUP_REFS", "$.anti_pollution_review.dedup_conflict_refs", "Related or conflicting rules require references."))

    def strings(node: Any) -> list[str]:
        if isinstance(node, str):
            return [node]
        if isinstance(node, list):
            return [item for child in node for item in strings(child)]
        if isinstance(node, dict):
            return [item for child in node.values() for item in strings(child)]
        return []

    if any(PRIVATE_PATH_LITERAL.search(item) or SECRET_ASSIGNMENT.search(item) for item in strings(value)):
        issues.append(_issue("GR_PRIVATE_LITERAL", "$", "Growth candidates must not contain machine-private paths or secret assignments."))
    return issues

def _semantic_growth_ledger(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    mode = value.get("mode")
    authorization_ref = value.get("authorization_ref")
    if mode == "project_maintain" and not authorization_ref:
        issues.append(_issue("GL_L2_AUTH", "$.authorization_ref", "Project-maintain mode requires a one-time project authorization reference."))
    if mode == "analysis_only" and authorization_ref is not None:
        issues.append(_issue("GL_ANALYSIS_AUTH", "$.authorization_ref", "Analysis-only mode must not imply durable-write authorization."))

    records = list(value.get("signal_records", [])) + list(value.get("candidate_records", []))
    record_ids = [item.get("record_id", "") for item in records]
    record_paths = [item.get("relative_path", "") for item in records]
    if _duplicates(record_ids) or _duplicates(record_paths):
        issues.append(_issue("GL_DUPLICATE_RECORD", "$", "Ledger record IDs and paths must be unique across signals and candidates."))
    for index, record in enumerate(records):
        relative = record.get("relative_path")
        if not isinstance(relative, str) or MACHINE_LOCATOR.match(relative) or "\\" in relative or ".." in Path(relative).parts or Path(relative).is_absolute():
            issues.append(_issue("GL_PATH", f"$.records.{index}.relative_path", "Ledger record paths must be normalized project-relative paths."))

    candidate_ids = {item.get("record_id") for item in value.get("candidate_records", [])}
    event_ids = [item.get("event_id", "") for item in value.get("retrieval_events", [])]
    if _duplicates(event_ids):
        issues.append(_issue("GL_DUPLICATE_EVENT", "$.retrieval_events", "Retrieval event IDs must be unique."))
    for index, event in enumerate(value.get("retrieval_events", [])):
        query = event.get("query", {})
        if not any(query.get(key) for key in ("task_types", "risk_levels", "tools", "workspace_keys", "failure_signatures")):
            issues.append(_issue("GL_QUERY_EMPTY", f"$.retrieval_events.{index}.query", "Retrieval queries require at least one relevance dimension."))
        matched = set(event.get("matched_candidate_ids", []))
        if matched.difference(candidate_ids):
            issues.append(_issue("GL_MATCH_UNKNOWN", f"$.retrieval_events.{index}.matched_candidate_ids", "Matched candidates must exist in candidate_records."))
        decision_ids = [item.get("candidate_id") for item in event.get("decisions", [])]
        if set(decision_ids) != matched or len(decision_ids) != len(set(decision_ids)):
            issues.append(_issue("GL_DECISION_MISMATCH", f"$.retrieval_events.{index}.decisions", "Each matched candidate requires exactly one decision."))
        for decision_index, decision in enumerate(event.get("decisions", [])):
            if decision.get("decision") == "adopted" and not decision.get("authorization_ref"):
                issues.append(_issue("GL_ADOPTION_AUTH", f"$.retrieval_events.{index}.decisions.{decision_index}.authorization_ref", "Adoption requires an authorization reference."))
    return issues

def _semantic_model_profile(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    efforts = value.get("reasoning_efforts", [])
    default_effort = value.get("default_reasoning_effort")
    mappings = value.get("effort_mappings", [])
    mapping_ids = [item.get("runtime_effort_id") for item in mappings]
    if "ultra" in value.get("reasoning_efforts", []) and "ultra-explicit-only" not in value.get("safety_constraints", []):
        issues.append(_issue("MODEL_ULTRA_POLICY", "$.safety_constraints", "Profiles exposing ultra must declare ultra-explicit-only."))
    if default_effort not in efforts:
        issues.append(_issue("MODEL_DEFAULT_EFFORT", "$.default_reasoning_effort", "Default effort must be one of reasoning_efforts."))
    if _duplicates([str(item) for item in mapping_ids]):
        issues.append(_issue("MODEL_EFFORT_MAPPING_DUPLICATE", "$.effort_mappings", "Each runtime effort ID requires exactly one mapping."))
    if set(mapping_ids) != set(efforts):
        issues.append(_issue("MODEL_EFFORT_MAPPING_COVERAGE", "$.effort_mappings", "Effort mappings must exactly cover reasoning_efforts."))
    runtime_source = value.get("runtime_source", {})
    if value.get("runtime_verified") and runtime_source.get("type") != "runtime-probe":
        issues.append(_issue("MODEL_RUNTIME_VERIFICATION", "$.runtime_verified", "runtime_verified requires a runtime-probe source."))
    return issues

def _semantic_runtime(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    support = value.get("support", {})
    configured = value.get("configured", {})
    effective = value.get("effective", {})
    requested = value.get("requested", {})
    strength = value.get("constraint_strength", {})
    binding_status = value.get("binding_status")
    test_state = value.get("test_state")
    effective_sources = [source for source in value.get("probe_sources", []) if source.get("strength") == "effective"]
    if support.get("model_override") == "unsupported" and configured.get("model_id") is not None:
        issues.append(_issue("RT_UNSUPPORTED_CONFIGURED_MODEL", "$.configured.model_id", "Unsupported model override cannot be recorded as configured."))
    if support.get("effort_override") == "unsupported" and configured.get("reasoning_effort") is not None:
        issues.append(_issue("RT_UNSUPPORTED_CONFIGURED_EFFORT", "$.configured.reasoning_effort", "Unsupported effort override cannot be recorded as configured."))
    if support.get("effective_reporting") in {"unsupported", "unknown"} and effective.get("outcome") not in {"effective_unknown", "runtime_unsupported", "routing_degraded"}:
        issues.append(_issue("RT_EFFECTIVE_TRUTH", "$.effective.outcome", "Missing effective reporting must be represented honestly."))
    comparisons = {
        "model": ("model_id", "RT_HARD_MODEL_MISMATCH"),
        "effort": ("reasoning_effort", "RT_HARD_EFFORT_MISMATCH"),
        "delegation": ("delegation_mode", "RT_HARD_DELEGATION_MISMATCH"),
        "concurrency": ("concurrency_policy", "RT_HARD_CONCURRENCY_MISMATCH"),
    }
    changed: list[str] = []
    for dimension, (field, code) in comparisons.items():
        if requested.get(field) == effective.get(field):
            continue
        changed.append(dimension)
        if strength.get(dimension) == "hard" and effective.get("outcome") not in {"requested_unavailable", "runtime_unsupported", "blocked"}:
            issues.append(_issue(code, "$.effective", f"Hard {dimension} mismatch must fail closed."))

    verified_bindings = {"effective_verified", "fallback_verified"}
    if binding_status in verified_bindings:
        if test_state != "behavior_verified":
            issues.append(_issue("RT_BINDING_BEHAVIOR_EVIDENCE", "$.test_state", "Verified runtime binding requires behavior_verified test state."))
        if effective.get("outcome") != "effective":
            issues.append(_issue("RT_BINDING_EFFECTIVE_OUTCOME", "$.effective.outcome", "Verified runtime binding requires an effective outcome."))
        if not effective_sources:
            issues.append(_issue("RT_BINDING_EFFECTIVE_SOURCE", "$.probe_sources", "Verified runtime binding requires an effective-strength probe source."))
        if not value.get("usage_evidence"):
            issues.append(_issue("RT_BINDING_USAGE_EVIDENCE", "$.usage_evidence", "Verified runtime binding requires direct usage evidence."))
    if binding_status in {"configured_unverified", "static_binding", "inherited", "unknown"} and effective.get("outcome") == "effective":
        issues.append(_issue("RT_UNVERIFIED_EFFECTIVE_CLAIM", "$.effective.outcome", "Configured, static, inherited, or unknown bindings cannot claim effective use."))
    if binding_status == "fallback_verified":
        if not value.get("fallback_reason"):
            issues.append(_issue("RT_FALLBACK_REASON", "$.fallback_reason", "Verified fallback requires an explicit reason."))
        if value.get("selection_source") != "fallback":
            issues.append(_issue("RT_FALLBACK_SOURCE", "$.selection_source", "Verified fallback must identify fallback as the selection source."))
        for dimension in changed:
            if strength.get(dimension) != "soft":
                issues.append(_issue("RT_FALLBACK_CONSTRAINT", f"$.constraint_strength.{dimension}", "Every changed fallback dimension must be a soft constraint."))
    elif value.get("fallback_reason") is not None:
        issues.append(_issue("RT_FALLBACK_REASON_STATE", "$.fallback_reason", "fallback_reason is only valid for fallback_verified bindings."))

    unsupported_state = binding_status == "unsupported" or test_state == "runtime_unsupported" or effective.get("outcome") == "runtime_unsupported"
    if unsupported_state and not (
        binding_status == "unsupported"
        and test_state == "runtime_unsupported"
        and effective.get("outcome") == "runtime_unsupported"
    ):
        issues.append(_issue("RT_UNSUPPORTED_STATE", "$", "Unsupported binding, test, and effective outcome states must agree."))
    if test_state == "provider_unconfigured" and effective.get("outcome") != "effective_unknown":
        issues.append(_issue("RT_PROVIDER_UNCONFIGURED_STATE", "$.effective.outcome", "Unconfigured providers must record effective_unknown."))
    if effective.get("delegation_mode") in {"sub-agent", "nested"} and binding_status in verified_bindings and value.get("effective_concurrency") is None:
        issues.append(_issue("RT_EFFECTIVE_CONCURRENCY", "$.effective_concurrency", "Verified delegated routing requires effective concurrency evidence."))
    if effective.get("reasoning_effort") == "ultra":
        authorization = value.get("ultra_authorization", {})
        if not all(authorization.get(key) for key in ("explicitly_authorized", "observable", "budgeted")):
            code = "RT_ULTRA_NESTED_POLICY" if effective.get("delegation_mode") in {"sub-agent", "nested"} else "RT_ULTRA_POLICY"
            issues.append(_issue(code, "$.ultra_authorization", "ultra requires explicit, observable, budgeted authorization."))
    return issues

def _semantic_capability_registry(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    entries = value.get("entries", [])
    ids = [entry.get("id", "") for entry in entries]
    if _duplicates(ids):
        issues.append(_issue("CAP_DUPLICATE_ID", "$.entries", "Capability IDs must be unique case-insensitively."))

    token_owner: dict[str, int] = {}
    for index, entry in enumerate(entries):
        tokens = [entry.get("name", ""), entry.get("declared_name", "")]
        tokens.extend(entry.get("aliases", []))
        tokens.extend(entry.get("lifecycle", {}).get("legacy_aliases", []))
        for token in tokens:
            normalized = str(token).casefold()
            previous = token_owner.get(normalized)
            if previous is not None and previous != index:
                issues.append(_issue("CAP_NAME_COLLISION", f"$.entries.{index}", f"Name or alias collides with entries[{previous}]: {token}"))
                break
            token_owner[normalized] = index
        adapter_tools = [item.get("tool", "") for item in entry.get("adapters", [])]
        if _duplicates(adapter_tools):
            issues.append(_issue("CAP_DUPLICATE_ADAPTER_TOOL", f"$.entries.{index}.adapters", "Each tool may have only one adapter record."))
        projection_tools = [item.get("tool", "") for item in entry.get("projection_plan", [])]
        if _duplicates(projection_tools):
            issues.append(_issue("CAP_DUPLICATE_PROJECTION_TOOL", f"$.entries.{index}.projection_plan", "Each tool may have only one projection plan."))
        if entry.get("review_status") == "runtime-verified":
            passed = {item.get("level") for item in entry.get("verification", []) if item.get("status") == "pass"}
            if passed != {"static", "discovery", "invocation", "behavior"}:
                issues.append(_issue("CAP_RUNTIME_EVIDENCE", f"$.entries.{index}.verification", "runtime-verified requires all four verification levels to PASS."))
        source = entry.get("source", {})
        if source.get("package_variant") not in entry.get("package_variants", []):
            issues.append(_issue("CAP_PACKAGE_VARIANT", f"$.entries.{index}.source.package_variant", "Source package_variant must appear in package_variants."))
        if entry.get("ownership") == "external":
            mutating_projection = any(
                item.get("required") or item.get("projection") not in {"none"}
                for item in entry.get("projection_plan", [])
            )
            if entry.get("managed_by") == "MALTS" or mutating_projection:
                issues.append(_issue("CAP_EXTERNAL_OWNERSHIP", f"$.entries.{index}", "External-owned capabilities cannot be MALTS-managed or projected."))
        if value.get("registry_scope") == "public-contract":
            locators = [entry.get("source", {}).get("locator")]
            locators.extend(item.get("locator") for item in entry.get("adapters", []))
            locators.extend(
                [
                    entry.get("source", {}).get("source_relative_path"),
                    entry.get("descriptor", {}).get("relative_path"),
                ]
            )
            if any(isinstance(locator, str) and MACHINE_LOCATOR.match(locator) for locator in locators if locator is not None):
                issues.append(_issue("CAP_PUBLIC_LOCATOR", f"$.entries.{index}", "Public contract locators must be package-relative."))
    if value.get("registry_scope") == "public-contract" and value.get("generated_at") is not None:
        issues.append(_issue("CAP_PUBLIC_GENERATED_STATE", "$.generated_at", "Public contract examples must not carry generated operator state."))

    id_set = set(ids)
    graph: dict[str, set[str]] = {entry.get("id", ""): set() for entry in entries}
    for index, entry in enumerate(entries):
        for dependency in entry.get("dependencies", []):
            if dependency.get("type") not in {"skill", "agent"} or not dependency.get("required"):
                continue
            target = dependency.get("id")
            if target not in id_set:
                issues.append(_issue("CAP_DEPENDENCY_MISSING", f"$.entries.{index}.dependencies", f"Required capability dependency is missing: {target}"))
            else:
                graph.setdefault(entry.get("id", ""), set()).add(target)
    if _graph_has_cycle(graph):
        issues.append(_issue("CAP_DEPENDENCY_CYCLE", "$.entries", "Capability dependency graph contains a cycle."))
    target_owner: dict[tuple[str, str], int] = {}
    for index, entry in enumerate(entries):
        for projection in entry.get("projection_plan", []):
            target = projection.get("target")
            if not target:
                continue
            key = (str(projection.get("tool", "")).casefold(), str(target).replace("\\", "/").casefold())
            previous = target_owner.get(key)
            if previous is not None and previous != index:
                issues.append(_issue("CAP_PATH_COLLISION", f"$.entries.{index}.projection_plan", f"Projection target collides with entries[{previous}]: {target}"))
            target_owner[key] = index
    return issues

def _semantic_capability_descriptor(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    projected = value.get("projected_names", {})
    names = [projected.get(tool, "") for tool in ("codex", "claude-code", "opencode")]
    if len({str(name).casefold() for name in names}) != 1 or not all(str(name).startswith("malts-") for name in names):
        issues.append(_issue("CAP_DESCRIPTOR_PROJECTION_NAME", "$.projected_names", "All tools require one stable MALTS-prefixed projected name."))
    if set(value.get("supported_tools", [])) != set(projected):
        issues.append(_issue("CAP_DESCRIPTOR_TOOL_COVERAGE", "$.supported_tools", "supported_tools must match projected_names."))
    metadata = value.get("tool_metadata", {})
    if metadata.get("codex", {}).get("include_openai_metadata") is not True or any(
        metadata.get(tool, {}).get("include_openai_metadata") is not False for tool in ("claude-code", "opencode")
    ):
        issues.append(_issue("CAP_DESCRIPTOR_TOOL_METADATA", "$.tool_metadata", "Only Codex uses agents/openai.yaml metadata in the W3 projection contract."))
    levels = set(value.get("verification", {}).get("levels", []))
    status = value.get("verification", {}).get("status")
    required_levels = {
        "static-validated": {"static"},
        "discovered": {"static", "discovery"},
        "invocation-verified": {"static", "discovery", "invocation"},
        "behavior-verified": {"static", "discovery", "invocation", "behavior"},
    }.get(status, set())
    if required_levels and not required_levels.issubset(levels):
        issues.append(_issue("CAP_DESCRIPTOR_VERIFICATION", "$.verification", "Descriptor status requires its preceding verification levels."))
    return issues

def _semantic_external_sidecar(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    policy = value.get("lifecycle_policy", {})
    if policy.get("install") or policy.get("update") or policy.get("delete"):
        issues.append(_issue("CAP_EXTERNAL_OWNERSHIP", "$.lifecycle_policy", "External-owned sidecars cannot authorize install, update, or delete."))
    if value.get("verified_at") is not None and not value.get("evidence_refs"):
        issues.append(_issue("CAP_EXTERNAL_EVIDENCE", "$.evidence_refs", "verified_at requires evidence_refs."))
    return issues

def _semantic_projection(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    entries = value.get("entries", [])
    if _duplicates([item.get("capability_id", "") for item in entries]):
        issues.append(_issue("PROJ_CAPABILITY_COLLISION", "$.entries", "Capability IDs must be unique within a projection manifest."))
    if _duplicates([item.get("target", "") for item in entries]):
        issues.append(_issue("PROJ_TARGET_COLLISION", "$.entries", "Projection targets must be unique case-insensitively."))
    if value.get("tool") != value.get("target_tool"):
        issues.append(_issue("PROJ_TOOL_BINDING", "$.target_tool", "tool and target_tool must match."))
    for index, entry in enumerate(entries):
        source = str(entry.get("source_relative_path", ""))
        target = str(entry.get("target", ""))
        if MACHINE_LOCATOR.match(source) or ".." in Path(source.replace("\\", "/")).parts:
            issues.append(_issue("PROJ_SOURCE_BINDING", f"$.entries.{index}.source_relative_path", "Projection sources must be package-relative."))
        if MACHINE_LOCATOR.match(target) or ".." in Path(target.replace("\\", "/")).parts or not target.replace("\\", "/").startswith("skills/"):
            issues.append(_issue("PROJ_TARGET_PATH", f"$.entries.{index}.target", "Projection targets must be package-relative under skills/."))
        if entry.get("created_by") != value.get("created_by"):
            issues.append(_issue("PROJ_CREATED_BY", f"$.entries.{index}.created_by", "Entry created_by must match manifest created_by."))
        for dependency in entry.get("required_dependencies", []):
            if MACHINE_LOCATOR.match(str(dependency)) or ".." in Path(str(dependency).replace("\\", "/")).parts:
                issues.append(_issue("PROJ_DEPENDENCY_BINDING", f"$.entries.{index}.required_dependencies", "Projection dependencies must be package-relative."))
    return issues

def _semantic_workspace(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    phases = value.get("phase_controls", [])
    sessions = value.get("session_controls", [])
    phase_ids = [item.get("phase_id", "") for item in phases]
    session_ids = [item.get("session_id", "") for item in sessions]
    if _duplicates(phase_ids):
        issues.append(_issue("WS_DUPLICATE_PHASE", "$.phase_controls", "Phase IDs must be unique."))
    if _duplicates(session_ids):
        issues.append(_issue("WS_DUPLICATE_SESSION", "$.session_controls", "Session IDs must be unique."))
    active_phase = value.get("active_phase_id")
    active_session = value.get("active_session_id")
    if active_phase is not None and active_phase not in phase_ids:
        issues.append(_issue("WS_ACTIVE_PHASE_MISSING", "$.active_phase_id", "Active phase must reference phase_controls."))
    session_map = {item.get("session_id"): item for item in sessions}
    if active_session is not None and active_session not in session_map:
        issues.append(_issue("WS_ACTIVE_SESSION_MISSING", "$.active_session_id", "Active session must reference session_controls."))
    elif active_session is not None and session_map[active_session].get("phase_id") != active_phase:
        issues.append(_issue("WS_SESSION_PHASE_MISMATCH", "$.active_session_id", "Active session must belong to the active phase."))
    return issues

def _semantic_prerequisites(value: dict[str, Any], prefix: str) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    prerequisites = value.get("minimum_prerequisites", [])
    always = [item for item in prerequisites if item.get("applicability") == "always"]
    selected = [item for item in prerequisites if item.get("applicability") == "selected-tool"]
    host_names = {str(item.get("name", "")).casefold() for item in always}
    if not RELEASE_HOST_PREREQUISITES.issubset(host_names):
        issues.append(
            _issue(
                f"{prefix}_PREREQUISITE_HOST_COVERAGE",
                "$.minimum_prerequisites",
                "Always-applicable prerequisites must include Windows, PowerShell, and Python.",
            )
        )

    selected_tools = [str(item.get("tool", "")) for item in selected]
    if _duplicates(selected_tools) or set(selected_tools) != set(RELEASE_TOOL_NAMES):
        issues.append(
            _issue(
                f"{prefix}_PREREQUISITE_TOOL_COVERAGE",
                "$.minimum_prerequisites",
                "Selected-tool prerequisites must contain exactly one Codex, Claude Code, and OpenCode row.",
            )
        )
    for index, item in enumerate(prerequisites):
        if item.get("required") is not True:
            issues.append(
                _issue(
                    f"{prefix}_PREREQUISITE_REQUIRED",
                    f"$.minimum_prerequisites[{index}].required",
                    "Every declared minimum prerequisite must be required in its applicability scope.",
                )
            )
        tool = item.get("tool")
        if item.get("applicability") == "selected-tool" and tool in RELEASE_TOOL_NAMES:
            if item.get("name") != RELEASE_TOOL_NAMES[tool]:
                issues.append(
                    _issue(
                        f"{prefix}_PREREQUISITE_TOOL_NAME",
                        f"$.minimum_prerequisites[{index}].name",
                        "Selected-tool prerequisite name must match its canonical tool identifier.",
                    )
                )
    return issues

def _semantic_generation(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    if set(value.get("supported_tools", [])) != {"codex", "claude-code", "opencode"}:
        issues.append(_issue("GEN_TOOL_COVERAGE", "$.supported_tools", "Generation manifest must cover all three release tools."))
    if set(value.get("migration_handlers", [])) != {"A", "B", "C", "D"}:
        issues.append(_issue("GEN_MIGRATION_COVERAGE", "$.migration_handlers", "Generation manifest must declare A-D handlers."))
    issues.extend(_semantic_prerequisites(value, "GEN"))
    return issues

def _semantic_release(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    version = value.get("version")
    if value.get("release_id") != f"MALTS-{version}":
        issues.append(_issue("REL_ID_VERSION", "$.release_id", "release_id must bind the declared version."))
    if set(value.get("supported_platforms", [])) != {"windows"}:
        issues.append(_issue("REL_PLATFORM_COVERAGE", "$.supported_platforms", "Release manifest must declare Windows as the complete platform set."))
    if set(value.get("supported_tools", [])) != {"codex", "claude-code", "opencode"}:
        issues.append(_issue("REL_TOOL_COVERAGE", "$.supported_tools", "Release manifest must cover all three release tools."))
    if set(value.get("migration_handlers", [])) != {"A", "B", "C", "D"}:
        issues.append(_issue("REL_MIGRATION_COVERAGE", "$.migration_handlers", "Release manifest must declare A-D handlers."))
    issues.extend(_semantic_prerequisites(value, "REL"))
    transport = value.get("transport_contract", {})
    if transport.get("top_level_directory") != value.get("release_id"):
        issues.append(_issue("REL_TRANSPORT_ROOT", "$.transport_contract.top_level_directory", "Transport top-level directory must equal release_id."))
    if transport.get("verification_mode") != "extract-and-verify-release-package":
        issues.append(_issue("REL_TRANSPORT_VERIFY", "$.transport_contract.verification_mode", "Transport verification must extract the archive and verify the embedded release package."))
    if transport.get("hosted_asset_kinds") != ["archive"]:
        issues.append(_issue("REL_TRANSPORT_ASSETS", "$.transport_contract.hosted_asset_kinds", "Hosted asset policy must contain exactly one archive."))

    gates = value.get("gates", [])
    gate_ids = [item.get("gate_id", "") for item in gates]
    expected_gate_ids = ["G0", "G1", "G2", "G3", "G4", "G5"]
    if gate_ids != expected_gate_ids:
        issues.append(_issue("REL_GATE_COVERAGE", "$.gates", "Release manifest must contain exactly one ordered row for each G0-G5 gate."))
    gate_status = {item.get("gate_id"): item.get("status") for item in gates}
    if value.get("remote_publication_status") != "not-performed":
        issues.append(_issue("REL_REMOTE_PUBLICATION_EXTERNAL", "$.remote_publication_status", "Immutable ReleaseManifest cannot record an external remote result."))
    if gate_status.get("G5") != "PENDING_REMOTE_CONFIRMATION":
        issues.append(_issue("REL_G5_EXTERNAL", "$.gates", "Immutable ReleaseManifest must leave G5 at PENDING_REMOTE_CONFIRMATION until remote confirmation is separately recorded."))
    for gate in ("G0", "G1", "G2", "G3", "G4"):
        if gate_status.get(gate) == "PENDING_REMOTE_CONFIRMATION":
            issues.append(_issue("REL_GATE_STATUS_SCOPE", "$.gates", f"{gate} cannot use the remote-only PENDING_REMOTE_CONFIRMATION status."))
    state = value.get("release_state")
    if state == "release-ready":
        if any(gate_status.get(gate) != "PASS" for gate in ("G0", "G1", "G2", "G3", "G4")) or gate_status.get("G5") != "PENDING_REMOTE_CONFIRMATION":
            issues.append(_issue("REL_RELEASE_READY_GATES", "$.gates", "release-ready requires G0-G4 PASS and G5 PENDING_REMOTE_CONFIRMATION."))
        if value.get("known_blockers"):
            issues.append(_issue("REL_KNOWN_BLOCKERS", "$.known_blockers", "release-ready cannot contain a known blocker."))

    inspected_strings = [
        str(value.get("source", {}).get("revision", "")),
        *[str(item) for item in value.get("projection_classification", {}).get("local_only_patterns", [])],
        *[str(ref) for gate in gates for ref in gate.get("evidence_refs", [])],
        *[str(ref) for ref in value.get("release_notes", {}).get("safety_evidence_refs", [])],
    ]
    if any(PRIVATE_PATH_LITERAL.search(item) or SECRET_ASSIGNMENT.search(item) for item in inspected_strings):
        issues.append(_issue("REL_PRIVATE_LITERAL", "$", "Release manifest must not contain machine-private paths or secret assignments."))
    return issues

def _normalize_windows_path(value: str) -> str:
    return value.replace("/", "\\").rstrip("\\").casefold()

def _paths_overlap(left: str, right: str) -> bool:
    a = _normalize_windows_path(left)
    b = _normalize_windows_path(right)
    return a == b or a.startswith(b + "\\") or b.startswith(a + "\\")

def _semantic_installation(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    generations = value.get("generations", [])
    ids = [item.get("generation_id", "") for item in generations]
    roots = [item.get("root", "") for item in generations]
    if _duplicates(ids):
        issues.append(_issue("INST_DUPLICATE_GENERATION", "$.generations", "Generation IDs must be unique."))
    if _duplicates(roots):
        issues.append(_issue("INST_DUPLICATE_ROOT", "$.generations", "Generation roots must be unique."))
    active = [item for item in generations if item.get("state") == "active"]
    if value.get("lifecycle_state") == "uninstalled":
        if active or value.get("active_generation_id") is not None:
            issues.append(_issue("INST_UNINSTALLED_ACTIVE", "$.active_generation_id", "Uninstalled registry cannot retain an active generation."))
    elif len(active) != 1:
        issues.append(_issue("INST_ACTIVE_COUNT", "$.generations", "Exactly one generation must be active."))
    if value.get("active_generation_id") is not None and not any(item.get("generation_id") == value.get("active_generation_id") and item.get("state") == "active" for item in generations):
        issues.append(_issue("INST_ACTIVE_REFERENCE", "$.active_generation_id", "active_generation_id must reference the active generation."))
    selected_tools = set(value.get("selected_tools", []))
    if value.get("release_binding_profile") == "release-package-v1":
        for index, item in enumerate(active):
            required_binding = (
                item.get("release_id"), item.get("release_manifest_sha256"),
                item.get("release_package_sha256"), item.get("generation_manifest_sha256")
            )
            if any(field is None for field in required_binding):
                issues.append(_issue("INST_RELEASE_BINDING", f"$.generations.{index}", "The active release-package-v1 generation requires complete outer and generation manifest identity."))
            projected_tools = {
                str(ref).split(":", 2)[1]
                for ref in item.get("projection_manifests", [])
                if str(ref).startswith("projection:") and str(ref).count(":") >= 2
            }
            if projected_tools != selected_tools:
                issues.append(_issue("INST_SELECTED_TOOL_BINDING", f"$.generations.{index}.projection_manifests", "Active projection manifests must match selected_tools exactly."))
    protected = value.get("persistent_state_roots", []) + value.get("user_data_roots", [])
    if any(_paths_overlap(root, state_root) for root in roots for state_root in protected):
        issues.append(_issue("INST_ROOT_OVERLAP", "$.generations", "Generation roots must not overlap persistent or user data roots."))
    return issues

def _semantic_update_plan(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    if value.get("operation") != "uninstall" and value.get("source_artifact_sha256") is None:
        issues.append(_issue("TX_SOURCE_ARTIFACT", "$.source_artifact_sha256", "Install/update/repair require a source artifact hash."))
    release_identity = value.get("release_identity", {})
    if value.get("operation") != "uninstall" and release_identity.get("release_root") is None:
        issues.append(_issue("TX_RELEASE_ROOT", "$.release_identity.release_root", "Install/update/repair require the verified outer release root."))
    if value.get("operation") != "uninstall" and release_identity.get("artifact_sha256") != value.get("source_artifact_sha256"):
        issues.append(_issue("TX_RELEASE_ARTIFACT_BINDING", "$.release_identity.artifact_sha256", "Release identity must bind source_artifact_sha256."))
    selected_tools = value.get("tool_targets", [])
    if not selected_tools or len(selected_tools) > 3 or not set(selected_tools).issubset({"codex", "claude-code", "opencode"}):
        issues.append(_issue("TX_SELECTED_TOOLS", "$.tool_targets", "A lifecycle plan requires a non-empty supported tool subset of size one through three."))
    for index, legacy in enumerate(value.get("legacy_roots", [])):
        managed = legacy.get("managed_file_count", 0)
        exact = legacy.get("exact_match_count", 0)
        missing = legacy.get("missing_count", 0)
        drift = legacy.get("drift_count", 0)
        extra = legacy.get("extra_count", 0)
        classification = legacy.get("classification")
        action = legacy.get("planned_action")
        if exact + missing + drift != managed:
            issues.append(_issue("TX_LEGACY_COVERAGE", f"$.legacy_roots.{index}", "Exact, missing, and drift counts must cover every managed manifest entry."))
        if classification == "exact-managed-root" and (action != "delete-whole-root" or missing or drift or extra or exact != managed):
            issues.append(_issue("TX_LEGACY_WHOLE_ROOT", f"$.legacy_roots.{index}", "Whole-root deletion requires complete exact coverage with zero missing, drift, or extras."))
        elif classification == "partial-managed-root" and (action != "delete-exact-managed-paths" or not (missing or drift or extra)):
            issues.append(_issue("TX_LEGACY_PARTIAL_ROOT", f"$.legacy_roots.{index}", "Partial roots delete exact managed paths only and require a non-exact condition."))
        elif classification == "missing" and (action != "none" or any((managed, exact, missing, drift, extra)) or legacy.get("manifest_sha256") is not None):
            issues.append(_issue("TX_LEGACY_MISSING_ROOT", f"$.legacy_roots.{index}", "Missing roots require no action, no manifest, and zero counts."))
        elif classification == "untrusted" and (action != "manual-review" or legacy.get("manifest_sha256") is not None):
            issues.append(_issue("TX_LEGACY_UNTRUSTED_ROOT", f"$.legacy_roots.{index}", "Untrusted roots must be preserved for manual review without a trusted manifest claim."))
    actions = value.get("actions", [])
    ids = [item.get("action_id", "") for item in actions]
    if _duplicates(ids):
        issues.append(_issue("TX_DUPLICATE_ACTION", "$.actions", "Action IDs must be unique."))
    id_set = set(ids)
    graph: dict[str, set[str]] = {item.get("action_id", ""): set() for item in actions}
    for index, action in enumerate(actions):
        for dependency in action.get("dependencies", []):
            if dependency not in id_set:
                issues.append(_issue("TX_DEPENDENCY_MISSING", f"$.actions.{index}.dependencies", f"Missing action dependency: {dependency}"))
            else:
                graph[action.get("action_id", "")].add(dependency)
        if action.get("kind") == "delete" and action.get("target") not in value.get("expected_cleanup", []):
            issues.append(_issue("TX_DELETE_NOT_PLANNED", f"$.actions.{index}", "Delete action must appear in expected_cleanup."))
    if _graph_has_cycle(graph):
        issues.append(_issue("TX_DEPENDENCY_CYCLE", "$.actions", "Action dependency graph contains a cycle."))
    for index, modification in enumerate(value.get("user_modifications", [])):
        classification = modification.get("classification")
        decision = modification.get("decision")
        if classification == "U3" and decision not in {"preserve", "ask"}:
            issues.append(_issue("TX_USER_MODIFICATION_POLICY", f"$.user_modifications.{index}", "U3 requires preserve or ask."))
        if classification == "U4" and decision != "fail-closed":
            issues.append(_issue("TX_USER_MODIFICATION_POLICY", f"$.user_modifications.{index}", "U4 must fail closed."))
    if value.get("plan_hash") != canonical_plan_hash(value):
        issues.append(_issue("TX_PLAN_HASH", "$.plan_hash", "plan_hash does not match the canonical plan payload."))
    return issues

def _semantic_journal(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    history = value.get("state_history", [])
    if history and history[-1].get("state") != value.get("state"):
        issues.append(_issue("TX_JOURNAL_STATE", "$.state_history", "Last journal event must equal current state."))
    allowed = {
        "DISCOVER": {"LOCK", "FAILED"},
        "LOCK": {"PLAN", "FAILED"},
        "PLAN": {"STAGE", "ROLLBACK", "FAILED"},
        "STAGE": {"SNAPSHOT", "ROLLBACK", "FAILED"},
        "SNAPSHOT": {"PREVALIDATE", "ROLLBACK", "FAILED"},
        "PREVALIDATE": {"ACTIVATE", "ROLLBACK", "FAILED"},
        "ACTIVATE": {"POSTVALIDATE", "ROLLBACK", "FAILED"},
        "POSTVALIDATE": {"CLEAN", "ROLLBACK", "FAILED"},
        "CLEAN": {"COMMIT", "ROLLBACK", "FAILED"},
        "ROLLBACK": {"FAILED"},
    }
    for previous, current in zip(history, history[1:]):
        if current.get("state") not in allowed.get(previous.get("state"), set()):
            issues.append(_issue("TX_STATE_TRANSITION", "$.state_history", f"Invalid transaction transition {previous.get('state')} -> {current.get('state')}."))
            break
    return issues

def _semantic_residue(value: dict[str, Any]) -> list[ContractIssue]:
    owner = value.get("owner")
    action = value.get("action")
    if owner == "unknown" and action == "delete":
        return [_issue("RS_OWNER_DELETE", "$.action", "Unknown ownership can never be auto-deleted.")]
    if owner in {"external", "user"} and action == "delete":
        return [_issue("RS_EXTERNAL_DELETE", "$.action", "External or user-owned residue cannot be auto-deleted.")]
    if owner == "malts" and action == "delete" and not value.get("ownership_evidence_refs"):
        return [_issue("RS_OWNERSHIP_EVIDENCE", "$.ownership_evidence_refs", "MALTS deletion requires ownership evidence.")]
    if action == "preserve" and not value.get("preserve_reason"):
        return [_issue("RS_PRESERVE_REASON", "$.preserve_reason", "Preserved residue requires a reason.")]
    if value.get("cleanup_scope") == "whole-root" and action == "delete":
        coverage = value.get("coverage") or {}
        if not value.get("manifest_sha256"):
            return [_issue("RS_WHOLE_ROOT_MANIFEST", "$.manifest_sha256", "Whole-root deletion requires a trusted managed-manifest hash.")]
        if coverage.get("managed_file_count") != coverage.get("exact_match_count") or any(
            coverage.get(field, 0) for field in ("missing_count", "drift_count", "extra_count")
        ):
            return [_issue("RS_WHOLE_ROOT_COVERAGE", "$.coverage", "Whole-root deletion requires complete exact manifest coverage and zero extras.")]
    return []

SEMANTIC_VALIDATORS = {
    "result-contract": _semantic_result_contract,
    "growth-signal": _semantic_growth_signal,
    "future-use-validation": _semantic_future_validation,
    "growth-candidate": _semantic_growth_candidate,
    "growth-ledger": _semantic_growth_ledger,
    "model-profile": _semantic_model_profile,
    "runtime-capability-evidence": _semantic_runtime,
    "capability-descriptor": _semantic_capability_descriptor,
    "external-capability-sidecar": _semantic_external_sidecar,
    "capability-registry": _semantic_capability_registry,
    "projection-manifest": _semantic_projection,
    "workspace-control": _semantic_workspace,
    "generation-manifest": _semantic_generation,
    "release-manifest": _semantic_release,
    "installation-registry": _semantic_installation,
    "update-plan": _semantic_update_plan,
    "transaction-journal": _semantic_journal,
    "residue-tombstone": _semantic_residue,
}


def validate_instance(
    malts_root: Path,
    contract_id: str,
    instance: Any,
    schema_override: dict[str, Any] | None = None,
) -> list[ContractIssue]:
    schema_file = USER_CONTRACTS.get(contract_id)
    if schema_file is None:
        return [_issue("USER_CONTRACT_UNKNOWN", "$", f"Unknown user-runtime contract_id: {contract_id}")]
    schema = schema_override or load_json(malts_root / "tools" / schema_file)
    issues = validate_against_schema(instance, schema)
    if isinstance(instance, dict):
        validator = SEMANTIC_VALIDATORS.get(contract_id)
        if validator is not None:
            issues.extend(validator(instance))
    return issues
