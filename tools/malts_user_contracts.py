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
    "lifecycle-invariants": "lifecycle_invariants.schema.json",
    "result-contract": "result_contract.schema.json",
    "result-event": "result_event.schema.json",
    "result-lineage-projection": "result_lineage_projection.schema.json",
    "phase-boundary-revision": "phase_boundary_revision.schema.json",
    "workspace-transaction-journal": "workspace_transaction_journal.schema.json",
    "workspace-migration-plan": "workspace_migration_plan.schema.json",
    "workspace-reorganization-plan": "workspace_reorganization_plan.schema.json",
    "result-migration-plan": "result_migration_plan.schema.json",
    "result-reorganization-plan": "result_reorganization_plan.schema.json",
    "growth-signal": "growth_signal.schema.json",
    "growth-candidate": "growth_candidate.schema.json",
    "future-use-validation": "future_use_validation.schema.json",
    "growth-ledger": "growth_ledger.schema.json",
    "model-profile": "model_profile.schema.json",
    "runtime-capability-evidence": "runtime_capability_evidence.schema.json",
    "agent-task-requirements": "agent_task_requirements.schema.json",
    "agent-route-policy": "agent_route_policy.schema.json",
    "capability-descriptor": "capability_descriptor.schema.json",
    "external-capability-sidecar": "external_capability_sidecar.schema.json",
    "capability-registry": "capability_registry.schema.json",
    "projection-manifest": "projection_manifest.schema.json",
    "tool-projection-manifest": "tool_projection_manifest.schema.json",
    "workspace-control": "workspace_control.schema.json",
    "resource-locator": "resource_locator.schema.json",
    "workspace-coordination": "workspace_coordination.schema.json",
    "workspace-coordination-event": "workspace_coordination_event.schema.json",
    "workspace-entry-report": "workspace_entry_report.schema.json",
    "user-status-labels": "user_status_labels.schema.json",
    "user-status-report": "user_status_report.schema.json",
    "workspace-artifact-snapshot": "workspace_artifact_snapshot.schema.json",
    "generation-manifest": "generation_manifest.schema.json",
    "release-manifest": "release_manifest.schema.json",
    "installation-registry": "installation_registry.schema.json",
    "update-plan": "update_plan.schema.json",
    "lifecycle-doctor-report": "lifecycle_doctor_report.schema.json",
    "lifecycle-audit-record": "lifecycle_audit_record.schema.json",
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
SEMANTIC_GENERATION_ID = re.compile(
    r"^malts-v(?P<version>(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))"
    r"(?:-preview\.(?P<sequence>[1-9][0-9]*))?$"
)
LIFECYCLE_INVARIANTS_FILE = "lifecycle_invariants.json"
RESULT_EVENT_REQUIRED_FIELDS: dict[str, set[str]] = {
    "CONTRACT_REVISION_ACCEPTED": {"revision_id"},
    "LEGACY_SNAPSHOT_IMPORTED": {"source_contract_path", "source_contract_sha256", "legacy_status", "legacy_usage", "legacy_recovery_ref"},
    "STATUS_TRANSITION": {"from_status", "to_status", "reason"},
    "AUTHORIZATION_ENVELOPE_GRANTED": {"authorization_envelope"},
    "AUTHORIZATION_ENVELOPE_REVOKED": {"envelope_id", "reason"},
    "ROUND_STARTED": {"round_id", "envelope_id"},
    "ATTEMPT_PLANNED": {"round_id", "attempt_id", "plan_ref"},
    "ATTEMPT_STARTED": {"round_id", "attempt_id", "envelope_id"},
    "ATTEMPT_COMPLETED": {"attempt_id", "attempt_state"},
    "INVOCATION_PLANNED": {"attempt_id", "invocation_id", "plan_ref"},
    "INVOCATION_STARTED": {"attempt_id", "invocation_id", "envelope_id"},
    "INVOCATION_COMPLETED": {"invocation_id", "invocation_state", "dispatch_summary"},
    "EXTERNAL_REQUEST_INTENT_RESERVED": {"invocation_id", "request_intent_id", "provider_locator", "side_effect_class", "idempotency_key_ref", "envelope_id", "provider_retry_bound_proven", "physical_request_limit"},
    "EXTERNAL_REQUEST_OBSERVED": {"invocation_id", "request_intent_id", "observed_request_id", "provider_request_id_ref", "outcome_state", "charge_state", "idempotency_replay"},
    "USAGE_OBSERVED": {"usage_delta", "envelope_id"},
    "RECOVERY_OBSERVATION": {"observation"},
    "CORRECTION_APPENDED": {"target_event_id", "target_event_sha256", "reason", "affected_fields"},
}
RESULT_EVENT_OPTIONAL_FIELDS: dict[str, set[str]] = {
    "CONTRACT_REVISION_ACCEPTED": {"reason"},
    "LEGACY_SNAPSHOT_IMPORTED": {"reason"},
    "STATUS_TRANSITION": set(),
    "AUTHORIZATION_ENVELOPE_GRANTED": {"reason"},
    "AUTHORIZATION_ENVELOPE_REVOKED": set(),
    "ROUND_STARTED": {"reason"},
    "ATTEMPT_PLANNED": {"reason"},
    "ATTEMPT_STARTED": {"reason"},
    "ATTEMPT_COMPLETED": {"reason"},
    "INVOCATION_PLANNED": {"reason"},
    "INVOCATION_STARTED": {"reason"},
    "INVOCATION_COMPLETED": {"reason"},
    "EXTERNAL_REQUEST_INTENT_RESERVED": {"reason"},
    "EXTERNAL_REQUEST_OBSERVED": {"sent_at", "response_at", "physical_request_bound_proven", "coordination_quarantine_id", "reason"},
    "USAGE_OBSERVED": {"reason"},
    "RECOVERY_OBSERVATION": {"unresolved_side_effects", "recovery_required", "reconciled_quarantine_ids", "coordination_reconcile_refs", "reason"},
    "CORRECTION_APPENDED": {"unresolved_side_effects", "recovery_required", "reconciled_quarantine_ids", "coordination_reconcile_refs", "observation"},
}


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

def _parse_datetime(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("date-time requires timezone")
    return parsed


def _valid_datetime(value: str) -> bool:
    try:
        _parse_datetime(value)
        return True
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
            code = "SCHEMA_VERSION_UNSUPPORTED" if current_path.endswith((".contract_id", ".schema_version", ".contract_version", ".event_version", ".projection_schema", ".revision_schema", ".journal_schema")) else "SCHEMA_CONST"
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


def load_lifecycle_invariants(malts_root: Path) -> tuple[dict[str, Any] | None, list[ContractIssue]]:
    """Load and validate the sole shared lifecycle model used by v2/v4 semantics."""

    model_path = malts_root / "tools" / LIFECYCLE_INVARIANTS_FILE
    try:
        model = load_json(model_path)
        schema = load_json(malts_root / "tools" / USER_CONTRACTS["lifecycle-invariants"])
    except (OSError, json.JSONDecodeError) as exc:
        return None, [_issue("LIFECYCLE_INVARIANT_LOAD", "$", str(exc))]
    issues = validate_against_schema(model, schema)
    if issues:
        return None, issues
    invariant_ids = [str(item.get("id", "")) for item in model.get("invariants", [])]
    if len(invariant_ids) != len(set(invariant_ids)):
        issues.append(_issue("LIFECYCLE_INVARIANT_DUPLICATE", "$.invariants", "Invariant IDs must be unique."))
    event_kinds = [str(item) for item in model.get("event_kinds", [])]
    if len(event_kinds) != len(set(event_kinds)):
        issues.append(_issue("LIFECYCLE_EVENT_DUPLICATE", "$.event_kinds", "Event kinds must be unique."))
    for key in ("task_state_machine", "attempt_state_machine", "invocation_state_machine"):
        machine = model.get(key, {})
        states = [str(item) for item in machine.get("states", [])]
        terminal = set(machine.get("terminal_states", []))
        transitions = machine.get("transitions", [])
        sources = [str(item.get("from", "")) for item in transitions]
        if len(states) != len(set(states)) or len(sources) != len(set(sources)):
            issues.append(_issue("LIFECYCLE_GRAPH_DUPLICATE", f"$.{key}", "States and transition sources must be unique."))
        if not terminal.issubset(set(states)) or terminal.intersection(sources):
            issues.append(_issue("LIFECYCLE_GRAPH_TERMINAL", f"$.{key}", "Terminal states must be declared and have no outgoing transition."))
        for index, transition in enumerate(transitions):
            if transition.get("from") not in states or not set(transition.get("to", [])).issubset(set(states)):
                issues.append(_issue("LIFECYCLE_GRAPH_REFERENCE", f"$.{key}.transitions.{index}", "Transition references an undeclared state."))
    compatible = model.get("compatible_invariant_bindings", [])
    compatible_keys = [
        (str(item.get("invariant_set_id", "")), str(item.get("invariant_source_sha256", "")))
        for item in compatible
        if isinstance(item, dict)
    ]
    if len(compatible_keys) != len(set(compatible_keys)):
        issues.append(_issue("LIFECYCLE_COMPATIBLE_BINDING_DUPLICATE", "$.compatible_invariant_bindings", "Compatible invariant bindings must be unique."))
    active_hash = hashlib.sha256(model_path.read_bytes()).hexdigest().upper()
    if (str(model.get("invariant_set_id", "")), active_hash) in set(compatible_keys):
        issues.append(_issue("LIFECYCLE_COMPATIBLE_BINDING_ACTIVE", "$.compatible_invariant_bindings", "The active invariant binding must not also be declared as legacy-compatible."))
    return (model if not issues else None), issues


def _accepted_invariant_bindings(model: dict[str, Any], active_sha256: str, contract_version: str) -> set[tuple[str, str]]:
    accepted = {(str(model.get("invariant_set_id", "")), active_sha256)}
    for item in model.get("compatible_invariant_bindings", []):
        if not isinstance(item, dict) or contract_version not in item.get("result_contract_versions", []):
            continue
        accepted.add((str(item.get("invariant_set_id", "")), str(item.get("invariant_source_sha256", ""))))
    return accepted


def _semantic_execution_authority(value: Any, path: str) -> list[ContractIssue]:
    if not isinstance(value, dict):
        return [_issue("RC_EXECUTION_AUTHORITY_REQUIRED", path, "Result v3 requires one closed execution-authority binding.")]
    issues: list[ContractIssue] = []
    profile = value.get("profile")
    tokens = value.get("fencing_tokens", [])
    if profile == "NONE":
        if value.get("admission_id") is not None or value.get("actor_id") is not None or value.get("phase_control_sha256") is not None or tokens:
            issues.append(_issue("RC_EXECUTION_AUTHORITY_NONE", path, "NONE authority must use null Admission/actor/Phase bindings and no fencing tokens."))
    elif profile == "RESOURCE_ADMISSION":
        if not value.get("admission_id") or not value.get("actor_id") or not value.get("phase_control_sha256") or not tokens:
            issues.append(_issue("RC_EXECUTION_AUTHORITY_REQUIRED", path, "RESOURCE_ADMISSION requires Admission, actor, Phase hash, and at least one fencing token."))
        domains = [str(item.get("domain_id", "")) for item in tokens if isinstance(item, dict)]
        if len(domains) != len(set(domains)) or domains != sorted(domains):
            issues.append(_issue("RC_FENCING_TOKEN_ORDER", f"{path}.fencing_tokens", "Fencing tokens must use unique domain IDs in deterministic order."))
    return issues


def _semantic_result_contract_v2(value: dict[str, Any], model: dict[str, Any], invariant_sha256: str) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    previous = value.get("previous_revision")
    revision_number = value.get("revision_number")
    if revision_number == 1 and previous is not None:
        issues.append(_issue("RC_REVISION_CHAIN", "$.previous_revision", "Revision one must have no previous revision."))
    elif isinstance(revision_number, int) and revision_number > 1 and not isinstance(previous, dict):
        issues.append(_issue("RC_REVISION_CHAIN", "$.previous_revision", "Revision two or later must bind the exact previous revision."))
    version = str(value.get("contract_version", ""))
    observed_binding = (str(value.get("invariant_set_id", "")), str(value.get("invariant_source_sha256", "")))
    accepted_bindings = _accepted_invariant_bindings(model, invariant_sha256, version)
    if version == "3":
        accepted_bindings = {(str(model.get("invariant_set_id", "")), invariant_sha256)}
    if observed_binding not in accepted_bindings:
        issues.append(_issue("RC_INVARIANT_BINDING", "$.invariant_set_id", "Result revision must bind either the active invariant source or an exact version-scoped compatible binding."))
    resources = value.get("authorized_scope", {}).get("resources", [])
    locators = [str(item.get("locator", "")) for item in resources if isinstance(item, dict)]
    if _duplicates(locators):
        issues.append(_issue("RC_SCOPE_DUPLICATE", "$.authorized_scope.resources", "Authorized resource locators must be unique."))
    criteria = value.get("acceptance_criteria", [])
    criterion_ids = [str(item.get("criterion_id", "")) for item in criteria if isinstance(item, dict)]
    if _duplicates(criterion_ids):
        issues.append(_issue("RC_DUPLICATE_CRITERION", "$.acceptance_criteria", "Criterion IDs must be unique."))
    budgets = value.get("budgets", {})
    field_for_limit = {
        "rounds": "max_rounds", "attempts": "max_attempts", "invocations": "max_invocations",
        "request_intents": "max_request_intents", "physical_requests": "max_physical_requests", "tokens": "max_tokens", "cost": "max_cost_units",
        "concurrency": "max_concurrency", "time": "max_elapsed_seconds",
    }
    for hard_limit in budgets.get("hard_limits", []):
        if budgets.get(field_for_limit.get(hard_limit, "")) is None:
            issues.append(_issue("RC_BUDGET_CONFIG", "$.budgets", f"Hard {hard_limit} budget requires a finite configured maximum."))
    if version == "2" and "execution_authority" in value:
        issues.append(_issue("RC_V2_AUTHORITY_FORBIDDEN", "$.execution_authority", "Result v2 cannot carry the v3 execution-authority field."))
    elif version == "3":
        issues.extend(_semantic_execution_authority(value.get("execution_authority"), "$.execution_authority"))
    return issues


def _semantic_lifecycle_invariants(value: dict[str, Any]) -> list[ContractIssue]:
    # The graph is checked by load_lifecycle_invariants; direct fixture validation
    # repeats the same checks without reading a second model.
    issues: list[ContractIssue] = []
    invariant_ids = [str(item.get("id", "")) for item in value.get("invariants", [])]
    if len(invariant_ids) != len(set(invariant_ids)):
        issues.append(_issue("LIFECYCLE_INVARIANT_DUPLICATE", "$.invariants", "Invariant IDs must be unique."))
    compatible = value.get("compatible_invariant_bindings", [])
    compatible_keys = [
        (str(item.get("invariant_set_id", "")), str(item.get("invariant_source_sha256", "")))
        for item in compatible
        if isinstance(item, dict)
    ]
    if len(compatible_keys) != len(set(compatible_keys)):
        issues.append(_issue("LIFECYCLE_COMPATIBLE_BINDING_DUPLICATE", "$.compatible_invariant_bindings", "Compatible invariant bindings must be unique."))
    for key in ("task_state_machine", "attempt_state_machine", "invocation_state_machine"):
        machine = value.get(key, {})
        states = set(machine.get("states", []))
        terminal = set(machine.get("terminal_states", []))
        transitions = machine.get("transitions", [])
        sources = [item.get("from") for item in transitions]
        if len(sources) != len(set(sources)):
            issues.append(_issue("LIFECYCLE_GRAPH_DUPLICATE", f"$.{key}.transitions", "Transition sources must be unique."))
        if not terminal.issubset(states) or terminal.intersection(sources):
            issues.append(_issue("LIFECYCLE_GRAPH_TERMINAL", f"$.{key}", "Terminal states must be declared and have no outgoing transition."))
    return issues


def _semantic_phase_boundary_revision(value: dict[str, Any]) -> list[ContractIssue]:
    revision_number = value.get("revision_number")
    previous = value.get("previous_revision")
    if revision_number == 1 and previous is not None:
        return [_issue("WS_PHASE_REVISION_CHAIN", "$.previous_revision", "Phase boundary revision one must have no predecessor.")]
    if isinstance(revision_number, int) and revision_number > 1 and not isinstance(previous, dict):
        return [_issue("WS_PHASE_REVISION_CHAIN", "$.previous_revision", "Later Phase boundary revisions require the exact predecessor binding.")]
    return []


def _semantic_result_event(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    sequence = value.get("sequence")
    previous = value.get("previous_event")
    if sequence == 1 and previous is not None:
        issues.append(_issue("RC_LINEAGE_STALE", "$.previous_event", "Sequence one must have no previous event."))
    elif isinstance(sequence, int) and sequence > 1 and not isinstance(previous, dict):
        issues.append(_issue("RC_LINEAGE_STALE", "$.previous_event", "Sequence two or later must bind the exact previous event."))
    kind = value.get("event_kind")
    payload = value.get("payload", {})
    event_version = value.get("event_version")
    if event_version == 1 and "execution_authority" in value:
        issues.append(_issue("RC_V1_EVENT_AUTHORITY_FORBIDDEN", "$.execution_authority", "Result event v1 cannot carry a v2 execution-authority field."))
    elif event_version == 2:
        issues.extend(_semantic_execution_authority(value.get("execution_authority"), "$.execution_authority"))
    required = RESULT_EVENT_REQUIRED_FIELDS.get(str(kind), set())
    missing = sorted(required.difference(payload))
    if missing:
        issues.append(_issue("RC_EVENT_PAYLOAD_REQUIRED", "$.payload", f"{kind} requires: {', '.join(missing)}"))
    unknown = sorted(set(payload).difference(required.union(RESULT_EVENT_OPTIONAL_FIELDS.get(str(kind), set()))))
    if unknown:
        issues.append(_issue("RC_EVENT_PAYLOAD_CLOSED", "$.payload", f"{kind} forbids payload fields: {', '.join(unknown)}"))
    if kind == "INVOCATION_COMPLETED" and isinstance(payload.get("dispatch_summary"), dict):
        summary = payload["dispatch_summary"]
        minimum, maximum = summary.get("confirmed_request_count_min"), summary.get("confirmed_request_count_max")
        if isinstance(minimum, int) and isinstance(maximum, int) and maximum < minimum:
            issues.append(_issue("RC_REQUEST_OBSERVATION_INVALID", "$.payload.dispatch_summary", "Confirmed request maximum cannot be below the known minimum."))
        if summary.get("dispatch_assessment") == "CONFIRMED_NOT_SENT" and not summary.get("direct_evidence_refs"):
            issues.append(_issue("RC_REQUEST_NOT_SENT_EVIDENCE_REQUIRED", "$.payload.dispatch_summary.direct_evidence_refs", "CONFIRMED_NOT_SENT requires direct dispatch-order evidence."))
    if kind == "EXTERNAL_REQUEST_INTENT_RESERVED" and payload.get("physical_request_limit") is not None and not payload.get("provider_retry_bound_proven"):
        issues.append(_issue("RC_PHYSICAL_REQUEST_BOUND_UNPROVABLE", "$.payload.provider_retry_bound_proven", "Finite physical-request bounds require bounded observable provider retries."))
    if kind == "EXTERNAL_REQUEST_OBSERVED":
        quarantine_id = payload.get("coordination_quarantine_id")
        if event_version == 2 and payload.get("outcome_state") == "UNKNOWN" and value.get("execution_authority", {}).get("profile") == "RESOURCE_ADMISSION" and not quarantine_id:
            issues.append(_issue("RC_UNKNOWN_QUARANTINE_REQUIRED", "$.payload.coordination_quarantine_id", "UNKNOWN external side effects under resource Admission require the exact coordination quarantine ID."))
        if payload.get("outcome_state") != "UNKNOWN" and quarantine_id is not None:
            issues.append(_issue("RC_UNKNOWN_QUARANTINE_INVALID", "$.payload.coordination_quarantine_id", "Only UNKNOWN external outcomes may bind a coordination quarantine."))
    reconciled_ids = payload.get("reconciled_quarantine_ids")
    reconcile_refs = payload.get("coordination_reconcile_refs")
    if event_version == 2 and reconciled_ids is not None:
        authority_profile = value.get("execution_authority", {}).get("profile")
        if authority_profile == "RESOURCE_ADMISSION":
            ref_ids = [item.get("quarantine_id") for item in reconcile_refs or [] if isinstance(item, dict)]
            if not reconciled_ids or ref_ids != sorted(ref_ids) or ref_ids != sorted(reconciled_ids):
                issues.append(_issue("RC_RECONCILE_EVIDENCE_REQUIRED", "$.payload.coordination_reconcile_refs", "Resource Admission quarantine reconciliation requires one sorted exact coordination event reference per reconciled quarantine ID."))
        elif reconcile_refs is not None:
            issues.append(_issue("RC_RECONCILE_EVIDENCE_INVALID", "$.payload.coordination_reconcile_refs", "Only RESOURCE_ADMISSION authority may bind coordination reconcile evidence."))
    elif reconcile_refs is not None:
        issues.append(_issue("RC_RECONCILE_EVIDENCE_INVALID", "$.payload.coordination_reconcile_refs", "Coordination reconcile evidence requires reconciled_quarantine_ids."))
    if event_version != 2 and (
        payload.get("coordination_quarantine_id") is not None
        or payload.get("reconciled_quarantine_ids") is not None
        or payload.get("coordination_reconcile_refs") is not None
    ):
        issues.append(_issue("RC_V2_EVENT_REQUIRED", "$.event_version", "Coordination quarantine fields require Result event v2."))
    if kind == "AUTHORIZATION_ENVELOPE_GRANTED" and isinstance(payload.get("authorization_envelope"), dict):
        envelope = payload["authorization_envelope"]
        units = [str(item.get("unit")) for item in envelope.get("limits", []) if isinstance(item, dict)]
        if len(units) != len(set(units)):
            issues.append(_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.authorization_envelope.limits", "Authorization limit units must be unique."))
        granted = envelope.get("granted_at")
        expires = envelope.get("expires_at")
        if isinstance(granted, str) and isinstance(expires, str) and _valid_datetime(granted) and _valid_datetime(expires):
            if _parse_datetime(expires) <= _parse_datetime(granted):
                issues.append(_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.authorization_envelope.expires_at", "Authorization expiry must be later than grant time."))
    if kind in {"ROUND_STARTED", "ATTEMPT_STARTED", "INVOCATION_STARTED", "EXTERNAL_REQUEST_INTENT_RESERVED", "USAGE_OBSERVED"} and payload.get("envelope_id") is None:
        issues.append(_issue("RC_AUTHORIZATION_REQUIRED", "$.payload.envelope_id", "Execution and counted-usage events require an authorization envelope reference."))
    revision = value.get("contract_revision", {})
    expected_prefix = f"task-state/{value.get('task_id')}/contracts/"
    if isinstance(revision, dict) and (
        not str(revision.get("path", "")).replace("\\", "/").startswith(expected_prefix)
        or not str(revision.get("path", "")).replace("\\", "/").endswith(f"/{revision.get('revision_id')}.json")
    ):
        issues.append(_issue("RC_LINEAGE_PATH", "$.contract_revision.path", "Contract revision path must be inside the declared Task lineage and match revision_id."))
    return issues


def _semantic_result_lineage_projection(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    latest_event = value.get("latest_event")
    inputs = value.get("rebuild_inputs", [])
    roles = [item.get("role") for item in inputs]
    if roles.count("CONTRACT_REVISION") != 1:
        issues.append(_issue("RC_PROJECTION_REBUILD_INPUT", "$.rebuild_inputs", "Projection requires exactly one latest contract revision input."))
    event_inputs = [item for item in inputs if item.get("role") == "RESULT_EVENT"]
    if latest_event is None and event_inputs:
        issues.append(_issue("RC_PROJECTION_HEAD", "$.latest_event", "No latest event requires no event rebuild inputs."))
    elif isinstance(latest_event, dict) and not any(item.get("path") == latest_event.get("path") and item.get("sha256") == latest_event.get("sha256") for item in event_inputs):
        issues.append(_issue("RC_PROJECTION_HEAD", "$.latest_event", "Latest event must be present in exact rebuild inputs."))
    terminal = value.get("terminal_status")
    status = value.get("task_status")
    if (status in TERMINAL_STATUSES and terminal != status) or (status not in TERMINAL_STATUSES and terminal is not None):
        issues.append(_issue("RC_TERMINAL_STATUS", "$.terminal_status", "Projection terminal status must agree with Task status."))
    expected_root = f"task-state/{value.get('task_id')}/"
    for path, field in (
        (value.get("latest_contract_revision", {}).get("path"), "$.latest_contract_revision.path"),
        (value.get("latest_event", {}).get("path") if isinstance(value.get("latest_event"), dict) else None, "$.latest_event.path"),
    ):
        if path is not None and not str(path).replace("\\", "/").startswith(expected_root):
            issues.append(_issue("RC_LINEAGE_PATH", field, "Projection bindings must stay inside the declared Task lineage."))
    projection_schema = value.get("projection_schema")
    if projection_schema == 1 and ("execution_authority" in value or "coordination_quarantine_ids" in value):
        issues.append(_issue("RC_V1_PROJECTION_AUTHORITY_FORBIDDEN", "$", "Projection v1 cannot carry Result v3 coordination fields."))
    elif projection_schema == 2:
        issues.extend(_semantic_execution_authority(value.get("execution_authority"), "$.execution_authority"))
        quarantines = value.get("coordination_quarantine_ids")
        if not isinstance(quarantines, list):
            issues.append(_issue("RC_PROJECTION_QUARANTINES_REQUIRED", "$.coordination_quarantine_ids", "Projection v2 requires an exact quarantine ID set."))
        elif quarantines and (not value.get("unresolved_side_effects") or not value.get("recovery_required")):
            issues.append(_issue("RC_PROJECTION_QUARANTINE_STATE", "$.coordination_quarantine_ids", "Bound quarantines require unresolved side effects and recovery_required."))
    return issues

def _semantic_result_contract_v1(value: dict[str, Any]) -> list[ContractIssue]:
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


def _semantic_agent_task_requirements(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    requested = value.get("requested_route", {})
    if requested.get("model_constraint") == "HARD" and requested.get("model_id") is None:
        issues.append(_issue("AR_REQ_HARD_MODEL", "$.requested_route.model_id", "A hard model constraint requires an exact model_id."))
    if requested.get("effort_constraint") == "HARD" and requested.get("reasoning_effort") is None:
        issues.append(_issue("AR_REQ_HARD_EFFORT", "$.requested_route.reasoning_effort", "A hard effort constraint requires an exact reasoning_effort."))
    if value.get("workload_class") == "INDEPENDENT_VERIFICATION" and value.get("independent_verification") is not True:
        issues.append(_issue("AR_REQ_VERIFICATION_FLAG", "$.independent_verification", "Independent-verification workload must set independent_verification=true."))
    return issues


def _semantic_agent_route_policy(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    routes = value.get("route_classes", [])
    names = [str(item.get("route_class", "")) for item in routes if isinstance(item, dict)]
    ranks = [item.get("rank") for item in routes if isinstance(item, dict)]
    if names != ["ECONOMY", "BALANCED", "ADVANCED", "FLAGSHIP"] or ranks != [1, 2, 3, 4]:
        issues.append(_issue("AR_POLICY_ROUTE_ORDER", "$.route_classes", "Route classes must be ECONOMY through FLAGSHIP in increasing rank order."))
    for index, route in enumerate(routes):
        if isinstance(route, dict) and route.get("default_effort") not in route.get("allowed_efforts", []):
            issues.append(_issue("AR_POLICY_DEFAULT_EFFORT", f"$.route_classes.{index}.default_effort", "Default effort must be allowed by its route class."))
    thresholds = value.get("thresholds", {})
    threshold_values = [thresholds.get("balanced_min"), thresholds.get("advanced_min"), thresholds.get("flagship_min")]
    if all(isinstance(item, int) for item in threshold_values) and threshold_values != sorted(set(threshold_values)):
        issues.append(_issue("AR_POLICY_THRESHOLDS", "$.thresholds", "Route thresholds must be unique and strictly increasing."))
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
    if effective.get("delegation_mode") in {"sub-agent", "nested", "peer-task"} and binding_status in verified_bindings and value.get("effective_concurrency") is None:
        issues.append(_issue("RT_EFFECTIVE_CONCURRENCY", "$.effective_concurrency", "Verified delegated routing requires effective concurrency evidence."))
    if effective.get("reasoning_effort") == "ultra":
        authorization = value.get("ultra_authorization", {})
        if not all(authorization.get(key) for key in ("explicitly_authorized", "observable", "budgeted")):
            code = "RT_ULTRA_NESTED_POLICY" if effective.get("delegation_mode") in {"sub-agent", "nested", "peer-task"} else "RT_ULTRA_POLICY"
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
    permission_routes = value.get("permission_routes")
    if permission_routes is not None:
        baseline = permission_routes.get("baseline", {})
        conditional = permission_routes.get("conditional", [])
        route_ids = [baseline.get("route_id")] + [route.get("route_id") for route in conditional]
        if len(route_ids) != len(set(route_ids)):
            issues.append(_issue("CAP_DESCRIPTOR_PERMISSION_ROUTE", "$.permission_routes", "Permission route IDs must be unique."))
        if baseline.get("required_permissions") != value.get("required_permissions"):
            issues.append(_issue("CAP_DESCRIPTOR_PERMISSION_ROUTE", "$.permission_routes.baseline", "Baseline permissions must equal required_permissions."))
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
    active_phase_rows = [item for item in phases if item.get("status") == "ACTIVE"]
    if len(active_phase_rows) > 1:
        issues.append(_issue("WS_MULTIPLE_ACTIVE_PHASES", "$.phase_controls", "At most one Phase may have ACTIVE status."))
    elif active_phase is None and active_phase_rows:
        issues.append(_issue("WS_ACTIVE_PHASE_INDEX_MISSING", "$.active_phase_id", "An ACTIVE Phase requires active_phase_id."))
    elif active_phase is not None:
        indexed = next((item for item in phases if item.get("phase_id") == active_phase), None)
        if indexed is not None and indexed.get("status") != "ACTIVE":
            issues.append(_issue("WS_ACTIVE_PHASE_STATUS", "$.active_phase_id", "active_phase_id must reference an ACTIVE Phase row."))
    is_current = value.get("contract_id") == "malts.workspace.current"
    schema_version = 5 if is_current else value.get("schema_version")
    open_phase_rows = [item for item in phases if item.get("status") == "OPEN"]
    if schema_version == 5:
        governance = value.get("phase_governance")
        profile = governance.get("profile") if isinstance(governance, dict) else None
        coordination_path = governance.get("coordination_path") if isinstance(governance, dict) else None
        single_profile = "single_phase" if is_current else "single_phase_v1"
        resource_profile = "resource_admission" if is_current else "resource_admission_v1"
        if profile == single_profile:
            if coordination_path is not None:
                issues.append(_issue("WS_COORDINATION_PROFILE", "$.phase_governance.coordination_path", f"{single_profile} cannot bind coordination state."))
        elif profile == resource_profile:
            if coordination_path != "runtime/workspace_coordination.json":
                issues.append(_issue("WS_COORDINATION_PROFILE", "$.phase_governance.coordination_path", f"{resource_profile} requires the canonical coordination path."))
            if open_phase_rows and active_phase is None:
                issues.append(_issue("WS_OPEN_PHASE_PRIMARY_REQUIRED", "$.active_phase_id", "Concurrent OPEN Phases require one primary ACTIVE Phase."))
        if open_phase_rows and profile != resource_profile:
            issues.append(_issue("WS_OPEN_PHASE_PROFILE", "$.phase_controls", f"Concurrent OPEN Phases require {resource_profile}."))
    if value.get("schema_version") == 1 and any(item.get("status") in {"PAUSED", "SUPERSEDED"} for item in phases):
        issues.append(_issue("WS_LEGACY_PHASE_STATUS", "$.phase_controls", "PAUSED and SUPERSEDED require workspace-control schema v2."))
    session_map = {item.get("session_id"): item for item in sessions}
    if active_session is not None and active_session not in session_map:
        issues.append(_issue("WS_ACTIVE_SESSION_MISSING", "$.active_session_id", "Active session must reference session_controls."))
    elif active_session is not None and session_map[active_session].get("phase_id") != active_phase:
        issues.append(_issue("WS_SESSION_PHASE_MISMATCH", "$.active_session_id", "Active session must belong to the active phase."))
    elif active_session is not None and session_map[active_session].get("status") != "ACTIVE":
        issues.append(_issue("WS_ACTIVE_SESSION_STATUS", "$.active_session_id", "active_session_id must reference an ACTIVE Session row."))
    if schema_version in {3, 4, 5}:
        binding = value.get("current_phase_binding")
        if active_phase is None and binding is not None:
            issues.append(_issue("WS_CURRENT_BINDING_TOPOLOGY", "$.current_phase_binding", "No active Phase requires a null current_phase_binding."))
        elif active_phase is not None and (
            not isinstance(binding, dict) or binding.get("active_phase_id") != active_phase
        ):
            issues.append(_issue("WS_CURRENT_BINDING_TOPOLOGY", "$.current_phase_binding", "current_phase_binding must identify the active Phase."))
        recovery = value.get("recovery_binding")
        if isinstance(recovery, dict):
            source_kind = recovery.get("source_kind")
            if active_session is not None and (
                source_kind != "ACTIVE_SESSION_CHECKPOINT"
                or recovery.get("source_session_id") != active_session
                or recovery.get("source_phase_id") != active_phase
            ):
                issues.append(_issue("WS_RECOVERY_BINDING_TOPOLOGY", "$.recovery_binding", "An active Session must own the runtime recovery binding."))
            elif active_session is None and active_phase is not None and (
                source_kind != "ACTIVE_PHASE_RECOVERY"
                or recovery.get("source_phase_id") != active_phase
                or recovery.get("source_session_id") is not None
            ):
                issues.append(_issue("WS_RECOVERY_BINDING_TOPOLOGY", "$.recovery_binding", "An active Phase without an active Session must own the runtime recovery binding."))
            elif active_session is None and active_phase is None and source_kind == "PROJECT_RECOVERY" and (
                recovery.get("source_phase_id") is not None or recovery.get("source_session_id") is not None
            ):
                issues.append(_issue("WS_RECOVERY_BINDING_TOPOLOGY", "$.recovery_binding", "Project recovery cannot claim a Phase or Session source."))
            elif active_session is None and active_phase is None and source_kind == "TERMINAL_PHASE_RECOVERY":
                source_phase = next((item for item in phases if item.get("phase_id") == recovery.get("source_phase_id")), None)
                if source_phase is None or source_phase.get("status") == "ACTIVE" or recovery.get("source_session_id") is not None:
                    issues.append(_issue("WS_RECOVERY_BINDING_TOPOLOGY", "$.recovery_binding", "Terminal Phase recovery must bind an existing non-active Phase and no Session."))
    if schema_version in {4, 5}:
        binding = value.get("current_phase_binding")
        session_binding = value.get("current_session_binding")
        task_bindings = value.get("current_task_bindings", [])
        if active_phase is None and binding is not None:
            issues.append(_issue("WS_CURRENT_BINDING_TOPOLOGY", "$.current_phase_binding", "No active Phase requires a null current_phase_binding."))
        elif active_phase is not None and (not isinstance(binding, dict) or binding.get("active_phase_id") != active_phase):
            issues.append(_issue("WS_CURRENT_BINDING_TOPOLOGY", "$.current_phase_binding", "v4 current_phase_binding must identify the active Phase."))
        if active_session is None and session_binding is not None:
            issues.append(_issue("WS_SESSION_BINDING_TOPOLOGY", "$.current_session_binding", "No active Session requires a null current_session_binding."))
        elif active_session is not None and (
            not isinstance(session_binding, dict)
            or session_binding.get("session_id") != active_session
            or session_binding.get("phase_id") != active_phase
            or session_binding.get("lease_state") != "ACTIVE"
        ):
            issues.append(_issue("WS_SESSION_BINDING_TOPOLOGY", "$.current_session_binding", "The active Session requires its exact active lease binding."))
        active_rows = [item for item in sessions if item.get("status") == "ACTIVE"]
        if len(active_rows) > 1 or (active_session is None and active_rows) or (active_session is not None and len(active_rows) != 1):
            issues.append(_issue("WS_ACTIVE_SESSION_TOPOLOGY", "$.session_controls", "v4 permits exactly one ACTIVE Session row when and only when active_session_id is set."))
        if active_session is not None:
            row = session_map.get(active_session, {})
            lease = row.get("lease", {}) if isinstance(row, dict) else {}
            binding = session_binding if isinstance(session_binding, dict) else {}
            if lease.get("state") != "ACTIVE" or row.get("owner_kind") != binding.get("owner_kind") or row.get("owner_id") != binding.get("owner_id") or lease.get("lease_id") != binding.get("lease_id"):
                issues.append(_issue("WS_SESSION_LEASE_REQUIRED", "$.session_controls", "Active Session row and current_session_binding must identify the same active lease owner."))
        task_ids = [str(item.get("task_id", "")) for item in task_bindings if isinstance(item, dict)]
        lineage_ids = [str(item.get("lineage_id", "")) for item in task_bindings if isinstance(item, dict)]
        if len(task_ids) != len(set(task_ids)) or _duplicates(task_ids):
            issues.append(_issue("WS_TASK_BINDING_DUPLICATE", "$.current_task_bindings", "Task IDs must be unique and case-portable."))
        if len(lineage_ids) != len(set(lineage_ids)) or _duplicates(lineage_ids):
            issues.append(_issue("WS_LINEAGE_BINDING_DUPLICATE", "$.current_task_bindings", "Lineage IDs must be unique and case-portable."))
        for index, task in enumerate(task_bindings):
            if task.get("phase_id") != active_phase:
                issues.append(_issue("WS_TASK_PHASE_MISMATCH", f"$.current_task_bindings.{index}.phase_id", "Current Task binding must belong to the active Phase."))
        recovery = value.get("recovery_binding")
        if isinstance(recovery, dict):
            source_kind = recovery.get("source_kind")
            resume_required = recovery.get("resume_required")
            expected_source = {
                "ACTIVE_SESSION_CHECKPOINT": (active_phase, active_session),
                "ACTIVE_PHASE_RECOVERY": (active_phase, None),
                "PROJECT_RECOVERY": (None, None),
            }.get(source_kind)
            if expected_source is not None and (recovery.get("source_phase_id"), recovery.get("source_session_id")) != expected_source:
                issues.append(_issue("WS_RECOVERY_BINDING_TOPOLOGY", "$.recovery_binding", "Recovery source IDs do not match the active workspace topology."))
            if source_kind == "ACTIVE_SESSION_CHECKPOINT" and active_session is None:
                issues.append(_issue("WS_RECOVERY_BINDING_TOPOLOGY", "$.recovery_binding", "Session checkpoint recovery requires an active Session."))
            if source_kind == "ACTIVE_PHASE_RECOVERY" and (active_phase is None or active_session is not None):
                issues.append(_issue("WS_RECOVERY_BINDING_TOPOLOGY", "$.recovery_binding", "Active Phase recovery requires an active Phase and no active Session."))
            if source_kind in {"PAUSED_PHASE_RECOVERY", "TERMINAL_PHASE_RECOVERY"}:
                source_row = next((item for item in phases if item.get("phase_id") == recovery.get("source_phase_id")), None)
                allowed_status = {"PAUSED"} if source_kind == "PAUSED_PHASE_RECOVERY" else {"DONE", "SUPERSEDED", "BLOCKED", "FAILED"}
                if active_phase is not None or active_session is not None or source_row is None or source_row.get("status") not in allowed_status or recovery.get("source_session_id") is not None:
                    issues.append(_issue("WS_RECOVERY_BINDING_TOPOLOGY", "$.recovery_binding", "Paused/terminal recovery must bind one matching non-active Phase and no Session."))
            if source_kind == "PAUSED_PHASE_RECOVERY" and not resume_required:
                issues.append(_issue("WS_RECOVERY_BINDING_TOPOLOGY", "$.recovery_binding.resume_required", "Paused Phase recovery requires resume_required=true."))
            if source_kind != "PAUSED_PHASE_RECOVERY" and resume_required:
                issues.append(_issue("WS_RECOVERY_BINDING_TOPOLOGY", "$.recovery_binding.resume_required", "Only paused Phase recovery may require resume."))
    return issues


def _semantic_resource_locator(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    kind = value.get("kind")
    scope = value.get("scope")
    values = [value.get("value"), *value.get("aliases", [])]

    def validate_path(item: Any, item_scope: Any, path: str) -> None:
        if not isinstance(item, str):
            return
        normalized = item.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part not in {"", "."}]
        dynamic = item.startswith("~") or "%" in item or "${" in item or "$env:" in item.casefold()
        absolute = bool(re.match(r"^[A-Za-z]:[/\\]", item)) or item.startswith(("/", "\\\\"))
        if dynamic:
            issues.append(_issue("LOCATOR_PATH_DYNAMIC", path, "PATH locators cannot contain home or environment expansion syntax."))
        if item_scope == "WORKSPACE" and (absolute or ".." in parts):
            issues.append(_issue("LOCATOR_PATH_ESCAPE", path, "WORKSPACE PATH locators must remain workspace-relative."))
        if item_scope == "EXTERNAL" and not absolute:
            issues.append(_issue("LOCATOR_PATH_ABSOLUTE_REQUIRED", path, "EXTERNAL PATH locators must be absolute."))

    if kind == "PATH":
        if scope not in {"WORKSPACE", "EXTERNAL"}:
            issues.append(_issue("LOCATOR_SCOPE_INVALID", "$.scope", "PATH locators use WORKSPACE or EXTERNAL scope."))
        for index, item in enumerate(values):
            path = "$.value" if index == 0 else f"$.aliases.{index - 1}"
            validate_path(item, scope, path)
    elif kind in {"ARTIFACT", "RECORD", "SERVICE", "DEVICE", "ENVIRONMENT"} and scope not in {"WORKSPACE", "GLOBAL"}:
        issues.append(_issue("LOCATOR_SCOPE_INVALID", "$.scope", f"{kind} locators use WORKSPACE or GLOBAL scope."))
    backing_paths = value.get("backing_paths", [])
    if kind != "ARTIFACT" and backing_paths:
        issues.append(_issue("LOCATOR_BACKING_PATH_KIND_INVALID", "$.backing_paths", "Only ARTIFACT locators may declare backing_paths."))
    if isinstance(backing_paths, list):
        for index, item in enumerate(backing_paths):
            if not isinstance(item, dict):
                continue
            backing_scope = item.get("scope")
            if backing_scope not in {"WORKSPACE", "EXTERNAL"}:
                issues.append(_issue("LOCATOR_SCOPE_INVALID", f"$.backing_paths.{index}.scope", "Backing paths use WORKSPACE or EXTERNAL scope."))
            validate_path(item.get("value"), backing_scope, f"$.backing_paths.{index}.value")
    return issues


def _semantic_workspace_coordination(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    admissions = value.get("active_admissions", [])
    queue = value.get("queue", [])
    quarantines = value.get("quarantines", [])
    domains = value.get("fencing_domains", [])
    admission_ids = [str(item.get("admission_id", "")) for item in admissions if isinstance(item, dict)]
    queued_ids = [str(item.get("request", {}).get("admission_id", "")) for item in queue if isinstance(item, dict)]
    quarantine_ids = [str(item.get("quarantine_id", "")) for item in quarantines if isinstance(item, dict)]
    if _duplicates(admission_ids):
        issues.append(_issue("COORD_ADMISSION_DUPLICATE", "$.active_admissions", "Active Admission IDs must be unique."))
    if _duplicates(queued_ids):
        issues.append(_issue("COORD_QUEUE_DUPLICATE", "$.queue", "Queued Admission IDs must be unique."))
    if {item.casefold() for item in admission_ids} & {item.casefold() for item in queued_ids}:
        issues.append(_issue("COORD_ADMISSION_QUEUE_OVERLAP", "$.queue", "An Admission cannot be active and queued simultaneously."))
    if _duplicates(quarantine_ids):
        issues.append(_issue("COORD_QUARANTINE_DUPLICATE", "$.quarantines", "Quarantine IDs must be unique."))
    domain_ids = [str(item.get("domain_id", "")) for item in domains if isinstance(item, dict)]
    if _duplicates(domain_ids):
        issues.append(_issue("COORD_FENCING_DOMAIN_DUPLICATE", "$.fencing_domains", "Fencing domain IDs must be unique."))
    epochs = {str(item.get("domain_id")): item.get("epoch") for item in domains if isinstance(item, dict)}
    for admission_index, admission in enumerate(admissions):
        token_ids: list[str] = []
        for token_index, token in enumerate(admission.get("fencing_tokens", [])):
            domain_id = str(token.get("domain_id", ""))
            token_ids.append(domain_id)
            if epochs.get(domain_id) != token.get("epoch"):
                issues.append(_issue("COORD_FENCING_STATE_DRIFT", f"$.active_admissions.{admission_index}.fencing_tokens.{token_index}", "Active Admission fencing tokens must equal current domain epochs."))
        if _duplicates(token_ids):
            issues.append(_issue("COORD_FENCING_TOKEN_DUPLICATE", f"$.active_admissions.{admission_index}.fencing_tokens", "Admission fencing tokens must be unique by domain."))
    for index, item in enumerate(queue):
        request = item.get("request") if isinstance(item, dict) else None
        if isinstance(request, dict) and item.get("request_sha256") != hashlib.sha256(canonical_json(request)).hexdigest().upper():
            issues.append(_issue("COORD_QUEUE_REQUEST_HASH", f"$.queue.{index}.request_sha256", "Queued request hash must bind the canonical request."))
    next_sequence = value.get("next_event_sequence")
    last_event = value.get("last_event")
    if last_event is None and next_sequence != 1:
        issues.append(_issue("COORD_EVENT_HEAD", "$.next_event_sequence", "A missing event head requires next_event_sequence=1."))
    elif isinstance(last_event, dict) and last_event.get("sequence") != next_sequence - 1:
        issues.append(_issue("COORD_EVENT_HEAD", "$.last_event.sequence", "last_event must immediately precede next_event_sequence."))
    return issues


def _semantic_workspace_coordination_event(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    sequence = value.get("sequence")
    previous = value.get("previous_event")
    if sequence == 1 and previous is not None:
        issues.append(_issue("COORD_EVENT_PREDECESSOR", "$.previous_event", "The first coordination event cannot have a predecessor."))
    elif isinstance(sequence, int) and sequence > 1 and (
        not isinstance(previous, dict) or previous.get("sequence") != sequence - 1
    ):
        issues.append(_issue("COORD_EVENT_PREDECESSOR", "$.previous_event", "A coordination event must bind its immediate predecessor."))
    if isinstance(value.get("revision_before"), int) and value.get("revision_after") != value["revision_before"] + 1:
        issues.append(_issue("COORD_EVENT_REVISION", "$.revision_after", "Coordination events advance the state revision by exactly one."))
    required_details = {
        "ADMISSION_GRANTED": {"admission_id", "conflicts", "fencing_tokens"},
        "ADMISSION_QUEUED": {"admission_id", "conflicts", "fencing_tokens"},
        "ADMISSION_RENEWED": {"admission_id", "previous_expires_at", "expires_at", "fencing_tokens"},
        "ADMISSION_RELEASED": {"admission_id", "released_tokens"},
        "LEASES_EXPIRED": {"expired_admission_ids", "quarantine_ids"},
        "EXTERNAL_SIDE_EFFECT_UNKNOWN": {"admission_id", "affected_scope", "quarantine_id"},
        "QUARANTINE_RECONCILED": {"quarantine_id", "admission_id", "resolution", "authorization_ref"},
    }.get(value.get("event_kind"), set())
    details = value.get("details")
    if isinstance(details, dict) and set(details) != required_details:
        issues.append(_issue("COORD_EVENT_DETAILS", "$.details", "Coordination event details must match the event-kind contract exactly."))
    return issues


def _semantic_workspace_entry_report(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    read_set = value.get("read_set", [])
    metrics = value.get("metrics", {})
    paths = [str(item.get("path", "")) for item in read_set if isinstance(item, dict)]
    if len(paths) != len(set(paths)) or len({item.casefold() for item in paths}) != len(paths):
        issues.append(_issue("ENTRY_READ_SET_DUPLICATE", "$.read_set", "Daily entry paths must be unique and Windows-portable."))
    if metrics.get("workspace_files_read") != len(read_set):
        issues.append(_issue("ENTRY_METRIC_FILE_COUNT", "$.metrics.workspace_files_read", "Read count must match read_set."))
    expected_bytes = sum(int(item.get("bytes", 0)) for item in read_set if isinstance(item, dict))
    if metrics.get("workspace_bytes_read") != expected_bytes:
        issues.append(_issue("ENTRY_METRIC_BYTE_COUNT", "$.metrics.workspace_bytes_read", "Read bytes must match read_set."))
    considered_files = metrics.get("workspace_files_considered")
    considered_bytes = metrics.get("workspace_bytes_considered")
    if not isinstance(considered_files, int) or considered_files < len(read_set):
        issues.append(_issue("ENTRY_METRIC_CONSIDERED_FILE_COUNT", "$.metrics.workspace_files_considered", "Considered file count cannot be smaller than the successful read set."))
    if not isinstance(considered_bytes, int) or considered_bytes < expected_bytes:
        issues.append(_issue("ENTRY_METRIC_CONSIDERED_BYTE_COUNT", "$.metrics.workspace_bytes_considered", "Considered bytes cannot be smaller than successful read bytes."))
    limits = value.get("fast_path_limits", {})
    within = (
        isinstance(considered_files, int)
        and isinstance(considered_bytes, int)
        and considered_files <= int(limits.get("max_workspace_files", 0))
        and considered_bytes <= int(limits.get("max_workspace_bytes", 0))
    )
    if value.get("within_fast_path_budget") is not within:
        issues.append(_issue("ENTRY_BUDGET_FLAG", "$.within_fast_path_budget", "Budget flag must match all current-state files considered, including a rejected read."))
    findings = value.get("findings", [])
    blocked = any(item.get("severity") == "BLOCKED" for item in findings if isinstance(item, dict))
    warnings = any(item.get("severity") == "WARNING" for item in findings if isinstance(item, dict))
    gates = value.get("required_gates", [])
    expected_decision = "BLOCKED" if blocked else "REVIEW_REQUIRED" if gates else "PROCEED_WITH_WARNINGS" if warnings else "PROCEED"
    if value.get("decision") != expected_decision:
        issues.append(_issue("ENTRY_DECISION_DRIFT", "$.decision", "Decision must derive from blocking findings, gates, and warnings."))
    expected_status = "FAIL" if blocked else "PASS"
    if value.get("status") != expected_status:
        issues.append(_issue("ENTRY_STATUS_DRIFT", "$.status", "Status must fail exactly when a blocking finding exists."))
    return issues


def _semantic_user_status_labels(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    labels = value.get("labels", [])
    codes = [str(item.get("code", "")) for item in labels if isinstance(item, dict)]
    if codes != sorted(codes):
        issues.append(_issue("USER_STATUS_CATALOG_ORDER", "$.labels", "User status codes must be sorted for deterministic review."))
    if len(codes) != len(set(codes)):
        issues.append(_issue("USER_STATUS_CATALOG_DUPLICATE", "$.labels", "User status codes must be unique."))
    return issues


def _semantic_user_status_report(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    language = value.get("language")
    items = value.get("items", [])
    expected_positions = list(range(1, len(items) + 1))
    positions = [item.get("position") for item in items if isinstance(item, dict)]
    if positions != expected_positions:
        issues.append(_issue("USER_STATUS_POSITION_ORDER", "$.items", "User status positions must be consecutive and ordered."))
    rendered_items: list[str] = []
    unknown_codes: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", ""))
        label = str(item.get("label", ""))
        expected = f"{label}（{code}）" if language == "zh-CN" else f"{label} ({code})"
        rendered_items.append(expected)
        if item.get("rendered") != expected:
            issues.append(_issue("USER_STATUS_RENDERED_MISMATCH", f"$.items.{index}.rendered", "Rendered status must preserve its stable machine code."))
        if item.get("known") is False:
            unknown_codes.append(code)
    if value.get("rendered_chain") != " / ".join(rendered_items):
        issues.append(_issue("USER_STATUS_CHAIN_MISMATCH", "$.rendered_chain", "Rendered chain must be the ordered item join."))
    if value.get("unknown_codes") != sorted(set(unknown_codes)):
        issues.append(_issue("USER_STATUS_UNKNOWN_CODES", "$.unknown_codes", "unknown_codes must exactly list unknown item codes."))
    return issues

def _semantic_workspace_artifact_snapshot(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    findings = value.get("findings", [])
    expected_counts = {
        "owner_registries": len(value.get("owners", [])),
        "artifact_rows": len(value.get("artifacts", [])),
        "issues": sum(item.get("severity") == "ISSUE" for item in findings),
        "warnings": sum(item.get("severity") == "WARNING" for item in findings),
        "candidates": sum(item.get("severity") == "CANDIDATE" for item in findings),
    }
    counts = value.get("counts", {})
    for field, expected in expected_counts.items():
        if counts.get(field) != expected:
            issues.append(_issue("ART_SNAPSHOT_COUNT", f"$.counts.{field}", "Snapshot count does not match its canonical array content."))
    input_keys = [f"{item.get('kind', '')}:{item.get('path', '')}" for item in value.get("input_hashes", [])]
    if _duplicates(input_keys):
        issues.append(_issue("ART_SNAPSHOT_DUPLICATE_INPUT", "$.input_hashes", "Snapshot input kind/path pairs must be unique."))
    enrollment = value.get("enrollment", {})
    fingerprint_payload = {
        "captured_at": value.get("captured_at"),
        "enrollment": enrollment,
        "input_hashes": value.get("input_hashes", []),
        "artifacts": value.get("artifacts", []),
        "findings": findings,
    }
    expected_fingerprint = hashlib.sha256(canonical_json(fingerprint_payload) + b"\n").hexdigest().upper()
    if value.get("capture_fingerprint") != expected_fingerprint:
        issues.append(_issue("ART_SNAPSHOT_FINGERPRINT", "$.capture_fingerprint", "Snapshot fingerprint does not bind the declared frozen capture inputs."))
    return issues


def _semantic_workspace_transaction_journal(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    targets = value.get("targets", [])
    roles = {
        "IMMUTABLE_RECORD": 1,
        "RESULT_PROJECTION": 2,
        "SESSION_CONTROL": 3,
        "PHASE_CONTROL": 4,
        "REPORT": 5,
        "HANDOFF": 6,
        "PROJECT_CONTROL": 7,
        "COORDINATION_STATE": 8,
        "RUNTIME_STATE": 9,
    }
    orders = [item.get("order") for item in targets if isinstance(item, dict)]
    if orders != list(range(1, len(targets) + 1)):
        issues.append(_issue("WS_TRANSACTION_ROLE_ORDER_INVALID", "$.targets", "Workspace journal target order must be consecutive from one."))
    role_values = [roles.get(str(item.get("role")), 0) for item in targets if isinstance(item, dict)]
    if role_values != sorted(role_values):
        issues.append(_issue("WS_TRANSACTION_ROLE_ORDER_INVALID", "$.targets", "Workspace journal targets must follow the frozen replacement role order."))
    paths = [str(item.get("path", "")) for item in targets if isinstance(item, dict)]
    if len(paths) != len(set(paths)) or len({item.casefold() for item in paths}) != len(paths):
        issues.append(_issue("WS_TRANSACTION_TARGET_DUPLICATE", "$.targets", "Workspace journal target paths must be unique and Windows-portable."))
    if int(value.get("replacement_cursor", -1)) > len(targets) or int(value.get("replacement_count", -1)) > len(targets):
        issues.append(_issue("WS_TRANSACTION_CURSOR_INVALID", "$.replacement_cursor", "Workspace journal cursor/count exceeds the target cardinality."))
    if value.get("state") == "COMMITTED" and (
        value.get("replacement_cursor") != len(targets)
        or value.get("replacement_count") != len(targets)
        or value.get("completed_at") is None
    ):
        issues.append(_issue("WS_TRANSACTION_COMMIT_INVALID", "$.state", "COMMITTED requires all targets replaced, a final cursor, and completed_at."))
    for index, item in enumerate(targets):
        if not isinstance(item, dict):
            continue
        existed = item.get("original_existed")
        original_fields = (item.get("original_bytes"), item.get("original_sha256"), item.get("original_base64"))
        if existed is True and any(field is None for field in original_fields):
            issues.append(_issue("WS_TRANSACTION_PREIMAGE_INVALID", f"$.targets.{index}", "Existing targets require exact original bytes and hash."))
        if existed is False and any(field is not None for field in original_fields):
            issues.append(_issue("WS_TRANSACTION_PREIMAGE_INVALID", f"$.targets.{index}", "ABSENT targets cannot carry original bytes or a preimage hash."))
    return issues


def _semantic_workspace_migration_plan(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    expected_versions = {
        "migrate-workspace-v3-to-v4": (3, 4),
        "migrate-workspace-v4-to-v5": (4, 5),
        "migrate-workspace-v5-to-v4": (5, 4),
    }
    operation = value.get("operation")
    if operation in expected_versions and (
        value.get("source_schema_version"), value.get("target_schema_version")
    ) != expected_versions[operation]:
        issues.append(_issue("WMIG_VERSION_DIRECTION", "$", "Migration operation must match its exact source and target schema versions."))
    target_profile = value.get("target_profile")
    if operation == "migrate-workspace-v4-to-v5":
        if target_profile not in {"single_phase_v1", "resource_admission_v1"}:
            issues.append(_issue("WMIG_TARGET_PROFILE", "$.target_profile", "v4-to-v5 requires one explicit v5 governance profile."))
    elif target_profile is not None:
        issues.append(_issue("WMIG_TARGET_PROFILE", "$.target_profile", "Only v4-to-v5 declares a target governance profile."))
    if value.get("operation_id") != value.get("plan_id"):
        issues.append(_issue("WMIG_PLAN_ID", "$.plan_id", "plan_id must equal operation_id."))
    binding = value.get("implementation_binding", {})
    input_rows = value.get("inputs", [])
    input_map = {(row.get("path"), row.get("role")): row.get("sha256") for row in input_rows if isinstance(row, dict)}
    if input_map.get((binding.get("tool_path"), "TOOL_SOURCE")) != binding.get("tool_sha256"):
        issues.append(_issue("WMIG_TOOL_BINDING", "$.implementation_binding.tool_sha256", "Tool binding must match the declared TOOL_SOURCE input."))
    if input_map.get((binding.get("invariant_path"), "INVARIANT_SOURCE")) != binding.get("invariant_sha256"):
        issues.append(_issue("WMIG_INVARIANT_BINDING", "$.implementation_binding.invariant_sha256", "Invariant binding must match the declared INVARIANT_SOURCE input."))
    outputs = {row.get("path") for row in value.get("outputs", []) if isinstance(row, dict)}
    preimages = {row.get("path"): row.get("sha256") for row in value.get("rollback", {}).get("preimages", []) if isinstance(row, dict)}
    if outputs != set(preimages):
        issues.append(_issue("WMIG_ROLLBACK_COVERAGE", "$.rollback.preimages", "Rollback preimages must cover exactly every migration output."))
    created = set(value.get("rollback", {}).get("created_outputs", []))
    if created != {path for path, digest in preimages.items() if digest is None}:
        issues.append(_issue("WMIG_CREATED_OUTPUTS", "$.rollback.created_outputs", "Created outputs must exactly match null-preimage outputs."))
    return issues


def _semantic_result_migration_plan(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    operation = value.get("operation")
    source = value.get("source", {})
    target = value.get("target", {})
    created = value.get("created", {})
    binding_mode = value.get("binding_mode")
    preconditions = value.get("preconditions", {})
    if value.get("operation_id") != value.get("plan_id"):
        issues.append(_issue("RMIG_PLAN_ID", "$.plan_id", "plan_id must equal operation_id."))

    created_fields = {
        "v2_contract_path": created.get("v2_contract_path"),
        "v3_contract_path": created.get("v3_contract_path"),
        "import_event_path": created.get("import_event_path"),
        "projection_path": created.get("projection_path"),
    }
    if operation == "migrate-result-contract-v1-to-v2":
        if source.get("contract_version") != "1":
            issues.append(_issue("RMIG_VERSION_DIRECTION", "$.source.contract_version", "v1-to-v2 migration requires a Result Contract v1 source."))
        if target.get("source_revision_id") is not None or target.get("target_revision_id") is None:
            issues.append(_issue("RMIG_REVISION_DIRECTION", "$.target", "v1-to-v2 migration has no typed source revision and requires one target revision ID."))
        if target.get("execution_authority") is not None:
            issues.append(_issue("RMIG_AUTHORITY_INVALID", "$.target.execution_authority", "Result Contract v2 cannot carry execution authority."))
        expected_presence = {
            "v2_contract_path": True,
            "v3_contract_path": False,
            "import_event_path": True,
            "projection_path": True,
        }
        if binding_mode not in {"V4_BOUND", "V5_NONE", "PENDING_WORKSPACE_BINDING"}:
            issues.append(_issue("RMIG_BINDING_MODE", "$.binding_mode", "v1-to-v2 migration requires V4_BOUND, V5_NONE, or PENDING_WORKSPACE_BINDING."))
    elif operation == "migrate-result-contract-v2-to-v3":
        if source.get("contract_version") != "2":
            issues.append(_issue("RMIG_VERSION_DIRECTION", "$.source.contract_version", "v2-to-v3 migration requires a Result Contract v2 source."))
        if target.get("source_revision_id") is None or target.get("target_revision_id") is None:
            issues.append(_issue("RMIG_REVISION_DIRECTION", "$.target", "v2-to-v3 migration requires exact source and target revision IDs."))
        elif target.get("source_revision_id") == target.get("target_revision_id"):
            issues.append(_issue("RMIG_REVISION_DIRECTION", "$.target.target_revision_id", "The target Result revision must differ from its source revision."))
        authority = target.get("execution_authority")
        if not isinstance(authority, dict):
            issues.append(_issue("RMIG_AUTHORITY_REQUIRED", "$.target.execution_authority", "v2-to-v3 migration requires an explicit execution-authority snapshot."))
        else:
            issues.extend(_semantic_execution_authority(authority, "$.target.execution_authority"))
            expected_mode = "V5_ADMISSION_BOUND" if authority.get("profile") == "RESOURCE_ADMISSION" else None
            if expected_mode is not None and binding_mode != expected_mode:
                issues.append(_issue("RMIG_BINDING_MODE", "$.binding_mode", "RESOURCE_ADMISSION authority requires V5_ADMISSION_BOUND."))
            if authority.get("profile") == "RESOURCE_ADMISSION" and preconditions.get("coordination_sha256") is None:
                issues.append(_issue("RMIG_COORDINATION_BINDING", "$.preconditions.coordination_sha256", "Admission-bound migration requires the exact coordination-state preimage."))
            if authority.get("profile") == "RESOURCE_ADMISSION" and authority.get("phase_control_sha256") != preconditions.get("phase_control_sha256"):
                issues.append(_issue("RMIG_PHASE_BINDING", "$.preconditions.phase_control_sha256", "Migration and Result execution authority must bind the same exact Phase control bytes."))
            if authority.get("profile") == "NONE" and binding_mode not in {"V4_NONE", "V5_NONE"}:
                issues.append(_issue("RMIG_BINDING_MODE", "$.binding_mode", "NONE authority requires V4_NONE or V5_NONE."))
            if authority.get("profile") == "NONE" and preconditions.get("coordination_sha256") is not None:
                issues.append(_issue("RMIG_COORDINATION_BINDING", "$.preconditions.coordination_sha256", "NONE authority cannot bind coordination state."))
        expected_presence = {
            "v2_contract_path": False,
            "v3_contract_path": True,
            "import_event_path": False,
            "projection_path": False,
        }
    else:
        expected_presence = {}

    for field, required in expected_presence.items():
        if (created_fields.get(field) is not None) != required:
            issues.append(_issue("RMIG_CREATED_OUTPUT", f"$.created.{field}", f"{operation} has an invalid {field} declaration."))
    preimages = {
        row.get("path"): row.get("sha256")
        for row in value.get("rollback", {}).get("preimages", [])
        if isinstance(row, dict)
    }
    rollback_created = set(value.get("rollback", {}).get("created_outputs", []))
    if rollback_created != {path for path, digest in preimages.items() if digest is None}:
        issues.append(_issue("RMIG_CREATED_OUTPUTS", "$.rollback.created_outputs", "Created outputs must exactly match null-preimage outputs."))
    for field, path in created_fields.items():
        if path is not None and (preimages.get(path, "MISSING") is not None or path not in rollback_created):
            issues.append(_issue("RMIG_ROLLBACK_COVERAGE", f"$.created.{field}", "Each declared immutable migration output requires a null preimage and created-output rollback row."))
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
    if value.get("schema_version") == 2:
        match = SEMANTIC_GENERATION_ID.fullmatch(str(value.get("generation_id", "")))
        if match is None:
            issues.append(_issue("GEN_SEMANTIC_ID", "$.generation_id", "Schema v2 requires a canonical stable or preview semantic generation ID."))
        elif match.group("version") != value.get("version"):
            issues.append(_issue("GEN_ID_VERSION", "$.generation_id", "Semantic generation ID must bind the declared version."))
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
    disposition = value.get("disposition")
    if disposition == "NO_OP":
        if value.get("expected_cleanup"):
            issues.append(_issue("TX_NO_OP_CLEANUP", "$.expected_cleanup", "NO_OP plans cannot retain cleanup targets."))
        if any(action.get("kind") != "verify" for action in value.get("actions", [])):
            issues.append(_issue("TX_NO_OP_ACTION", "$.actions", "NO_OP plans may contain verification actions only."))
    if value.get("operation") != "uninstall" and value.get("source_artifact_sha256") is None:
            issues.append(_issue("TX_SOURCE_ARTIFACT", "$.source_artifact_sha256", "Install/update/repair/finalize require a source artifact hash."))
    release_identity = value.get("release_identity", {})
    if value.get("operation") != "uninstall" and release_identity.get("release_root") is None:
            issues.append(_issue("TX_RELEASE_ROOT", "$.release_identity.release_root", "Install/update/repair/finalize require the verified outer release root."))
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
        "COMMIT": {"ROLLBACK", "FAILED"},
        "ROLLBACK": {"FAILED"},
        "FAILED": {"ROLLBACK"},
    }
    for previous, current in zip(history, history[1:]):
        if current.get("state") not in allowed.get(previous.get("state"), set()):
            issues.append(_issue("TX_STATE_TRANSITION", "$.state_history", f"Invalid transaction transition {previous.get('state')} -> {current.get('state')}."))
            break
    return issues


def _semantic_audit_record(value: dict[str, Any]) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    payload = copy.deepcopy(value)
    observed_hash = payload.pop("record_sha256", None)
    expected_hash = hashlib.sha256(canonical_json(payload)).hexdigest().upper()
    if observed_hash != expected_hash:
        issues.append(_issue("AUDIT_RECORD_HASH", "$.record_sha256", "record_sha256 does not bind the canonical audit record."))
    created_at = value.get("created_at")
    if isinstance(created_at, str) and value.get("month") != created_at[:7]:
        issues.append(_issue("AUDIT_MONTH", "$.month", "month must match the UTC created_at calendar month."))
    details = value.get("details")
    if not isinstance(details, dict):
        return issues
    record_type = value.get("record_type")
    operation_id = value.get("operation_id")
    operation = value.get("operation")
    outcome = value.get("outcome")
    plan_hash = details.get("plan_hash")
    generation_id = details.get("generation_id")
    binding_sha256 = details.get("binding_sha256")
    plan_sha256 = details.get("plan_sha256")
    journal_sha256 = details.get("journal_sha256")
    counts = (details.get("success_count"), details.get("failure_count"), details.get("uninstall_count"))
    last_operation_id = details.get("last_operation_id")
    valid = False
    if record_type == "current-binding":
        valid = (
            operation_id is not None and operation in {"install", "update", "repair", "finalize"} and outcome == "ACTIVE"
            and plan_hash is not None and generation_id is not None and binding_sha256 is not None
            and plan_sha256 is None and journal_sha256 is None and counts == (None, None, None)
            and last_operation_id is None
        )
    elif record_type == "operation-receipt":
        valid = (
            operation_id is not None and operation in {"install", "update", "repair", "finalize", "uninstall"}
            and outcome in {"SUCCESS", "UNINSTALLED"} and plan_hash is not None
            and ((outcome == "SUCCESS" and generation_id is not None and binding_sha256 is not None)
                 or (outcome == "UNINSTALLED" and generation_id is None and binding_sha256 is None))
            and plan_sha256 is None and journal_sha256 is None and counts == (None, None, None)
            and last_operation_id is None
        )
    elif record_type == "failure-bundle":
        valid = (
            operation_id is not None and operation in {"install", "update", "repair", "finalize", "uninstall"}
            and outcome == "RECOVERED" and plan_hash is not None and generation_id is None
            and binding_sha256 is None and plan_sha256 is not None and journal_sha256 is not None
            and counts == (None, None, None) and last_operation_id is None
        )
    elif record_type == "monthly-summary":
        valid = (
            operation_id is None and operation is None and outcome == "SUMMARY" and plan_hash is None
            and generation_id is None and binding_sha256 is None and plan_sha256 is None
            and journal_sha256 is None and all(isinstance(item, int) for item in counts)
            and last_operation_id is not None
        )
    if not valid:
        issues.append(_issue("AUDIT_RECORD_SHAPE", "$", "Audit record fields do not match record_type and outcome semantics."))
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
    "lifecycle-invariants": _semantic_lifecycle_invariants,
    "result-event": _semantic_result_event,
    "result-lineage-projection": _semantic_result_lineage_projection,
    "phase-boundary-revision": _semantic_phase_boundary_revision,
    "growth-signal": _semantic_growth_signal,
    "future-use-validation": _semantic_future_validation,
    "growth-candidate": _semantic_growth_candidate,
    "growth-ledger": _semantic_growth_ledger,
    "model-profile": _semantic_model_profile,
    "runtime-capability-evidence": _semantic_runtime,
    "agent-task-requirements": _semantic_agent_task_requirements,
    "agent-route-policy": _semantic_agent_route_policy,
    "capability-descriptor": _semantic_capability_descriptor,
    "external-capability-sidecar": _semantic_external_sidecar,
    "capability-registry": _semantic_capability_registry,
    "projection-manifest": _semantic_projection,
    "workspace-control": _semantic_workspace,
    "resource-locator": _semantic_resource_locator,
    "workspace-coordination": _semantic_workspace_coordination,
    "workspace-coordination-event": _semantic_workspace_coordination_event,
    "workspace-entry-report": _semantic_workspace_entry_report,
    "user-status-labels": _semantic_user_status_labels,
    "user-status-report": _semantic_user_status_report,
    "workspace-transaction-journal": _semantic_workspace_transaction_journal,
    "workspace-migration-plan": _semantic_workspace_migration_plan,
    "result-migration-plan": _semantic_result_migration_plan,
    "workspace-artifact-snapshot": _semantic_workspace_artifact_snapshot,
    "generation-manifest": _semantic_generation,
    "release-manifest": _semantic_release,
    "installation-registry": _semantic_installation,
    "update-plan": _semantic_update_plan,
    "lifecycle-audit-record": _semantic_audit_record,
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
    validation_schema = schema
    if (
        schema_override is None
        and contract_id == "lifecycle-invariants"
        and isinstance(instance, dict)
    ):
        version = instance.get("schema_version")
        if version == 2:
            validation_schema = schema
        elif version == 1:
            validation_schema = copy.deepcopy(schema)
            validation_schema["properties"]["schema_version"] = {"const": 1}
            validation_schema["properties"]["target_release"] = {"const": "1.3.0"}
            validation_schema["properties"]["status"] = {"const": "DESIGN_FROZEN"}
            validation_schema["required"] = [field for field in validation_schema["required"] if field != "compatible_invariant_bindings"]
            validation_schema["properties"].pop("compatible_invariant_bindings", None)
            validation_schema["properties"]["terminology"]["minItems"] = 8
            validation_schema["properties"]["invariants"]["minItems"] = 12
            validation_schema["properties"]["contract_versions"] = {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "workspace_control", "result_contract", "result_event", "result_lineage_projection",
                    "phase_boundary_revision", "workspace_transaction_journal", "workspace_migration_plan", "result_migration_plan",
                ],
                "properties": {
                    "workspace_control": {"const": 4},
                    "result_contract": {"const": 2},
                    "result_event": {"const": 1},
                    "result_lineage_projection": {"const": 1},
                    "phase_boundary_revision": {"const": 1},
                    "workspace_transaction_journal": {"const": 1},
                    "workspace_migration_plan": {"const": 1},
                    "result_migration_plan": {"const": 1},
                },
            }
        else:
            return [_issue("SCHEMA_VERSION_UNSUPPORTED", "$.schema_version", f"Unsupported lifecycle-invariants schema_version: {version!r}.")]
    elif (
        schema_override is None
        and contract_id == "result-contract"
        and isinstance(instance, dict)
    ):
        version = instance.get("contract_version")
        definition = {"1": "resultContractV1"}.get(version)
        if instance.get("contract_id") == "malts.result.current":
            validation_schema = schema
        elif version in {"2", "3"}:
            validation_schema = copy.deepcopy(schema)
            validation_schema["properties"].pop("contract_id", None)
            validation_schema["properties"]["contract_version"] = {"const": version}
            validation_schema["required"] = [
                "contract_version" if field == "contract_id" else field
                for field in validation_schema["required"]
                if version == "3" or field != "execution_authority"
            ]
        elif definition is None:
            return [_issue("SCHEMA_VERSION_UNSUPPORTED", "$.contract_version", f"Unsupported result-contract contract_version: {version!r}.")]
        else:
            selected = schema.get("$defs", {}).get(definition)
            if not isinstance(selected, dict):
                return [_issue("SCHEMA_REF", "$", f"Missing result-contract compatibility definition: {definition}")]
            validation_schema = copy.deepcopy(selected)
            validation_schema["$defs"] = copy.deepcopy(schema["$defs"])
    elif (
        schema_override is None
        and contract_id == "result-event"
        and isinstance(instance, dict)
        and instance.get("event_version") == 1
    ):
        validation_schema = copy.deepcopy(schema)
        validation_schema["properties"]["event_version"] = {"const": 1}
        validation_schema["required"] = [field for field in validation_schema["required"] if field != "execution_authority"]
    elif (
        schema_override is None
        and contract_id == "result-lineage-projection"
        and isinstance(instance, dict)
        and instance.get("projection_schema") == 1
    ):
        validation_schema = copy.deepcopy(schema)
        validation_schema["properties"]["projection_schema"] = {"const": 1}
        validation_schema["required"] = [
            field for field in validation_schema["required"]
            if field not in {"execution_authority", "coordination_quarantine_ids"}
        ]
    elif (
        schema_override is None
        and contract_id == "workspace-control"
        and isinstance(instance, dict)
    ):
        if instance.get("contract_id") == "malts.workspace.current":
            validation_schema = schema
        else:
            version = instance.get("schema_version")
            definition = {1: "workspaceControlV1", 2: "workspaceControlV2", 3: "workspaceControlV3", 4: "workspaceControlV4", 5: "workspaceControlV5"}.get(version)
            if definition is None:
                return [_issue("SCHEMA_VERSION_UNSUPPORTED", "$.schema_version", f"Unsupported legacy workspace-control schema_version: {version!r}; use reorganize-workspace for a supported legacy layout.")]
            selected = schema.get("$defs", {}).get(definition)
            if not isinstance(selected, dict):
                return [_issue("SCHEMA_REF", "$", f"Missing workspace-control compatibility definition: {definition}")]
            validation_schema = copy.deepcopy(selected)
            validation_schema["$defs"] = copy.deepcopy(schema["$defs"])
    elif (
        schema_override is None
        and contract_id in {"generation-manifest", "tool-projection-manifest"}
        and isinstance(instance, dict)
        and instance.get("schema_version") == 1
    ):
        # Legacy generation and installed tool-projection manifests remain
        # readable migration inputs; current writers emit canonical v2.
        validation_schema = copy.deepcopy(schema)
        validation_schema["properties"]["schema_version"] = {"const": 1}
    issues = validate_against_schema(instance, validation_schema)
    if isinstance(instance, dict):
        if contract_id == "result-contract":
            if instance.get("contract_version") == "1":
                issues.extend(_semantic_result_contract_v1(instance))
            elif instance.get("contract_version") in {"2", "3"} or instance.get("contract_id") == "malts.result.current":
                model, model_issues = load_lifecycle_invariants(malts_root)
                issues.extend(model_issues)
                if model is not None:
                    invariant_sha256 = hashlib.sha256((malts_root / "tools" / LIFECYCLE_INVARIANTS_FILE).read_bytes()).hexdigest().upper()
                    issues.extend(_semantic_result_contract_v2(instance, model, invariant_sha256))
        else:
            validator = SEMANTIC_VALIDATORS.get(contract_id)
            if validator is not None:
                issues.extend(validator(instance))
        if contract_id == "result-lineage-projection":
            model, model_issues = load_lifecycle_invariants(malts_root)
            issues.extend(model_issues)
            if model is not None:
                invariant_sha256 = hashlib.sha256((malts_root / "tools" / LIFECYCLE_INVARIANTS_FILE).read_bytes()).hexdigest().upper()
                observed_binding = (str(instance.get("invariant_set_id", "")), str(instance.get("invariant_source_sha256", "")))
                if instance.get("projection_schema") == 2:
                    accepted_bindings = {(str(model.get("invariant_set_id", "")), invariant_sha256)}
                else:
                    accepted_bindings = _accepted_invariant_bindings(model, invariant_sha256, "2")
                if observed_binding not in accepted_bindings:
                    issues.append(_issue("RC_INVARIANT_BINDING", "$.invariant_set_id", "Result projection must bind the active source or an exact compatible Result v2 invariant binding."))
    return issues
