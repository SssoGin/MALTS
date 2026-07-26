#!/usr/bin/env python3
"""Project-local Growth ledger, retrieval, and future-use validation for MALTS W2."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from malts_user_contracts import load_json, validate_instance


MALTS_ROOT = Path(__file__).resolve().parent.parent
ELIGIBLE_RETRIEVAL_STATES = {"PROJECT_EXPERIMENTAL", "FUTURE_USE_VALIDATING", "VALIDATED"}
RETRIEVAL_DIMENSIONS = ("task_types", "risk_levels", "tools", "workspace_keys", "failure_signatures")


@dataclass(frozen=True)
class LedgerIssue:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def _issue(code: str, path: str, message: str) -> LedgerIssue:
    return LedgerIssue(code, path, message)


def _contract_issues(malts_root: Path, contract_id: str, value: Any) -> list[LedgerIssue]:
    return [LedgerIssue(item.code, item.path, item.message) for item in validate_instance(malts_root, contract_id, value)]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _resolve_record(base: Path, relative: str) -> Path | None:
    if not isinstance(relative, str) or "\\" in relative:
        return None
    root = base.resolve()
    candidate = (root / relative).resolve()
    if candidate == root or root not in candidate.parents:
        return None
    return candidate


def validate_ledger_bundle(
    ledger: dict[str, Any],
    ledger_path: Path,
    malts_root: Path = MALTS_ROOT,
) -> tuple[list[LedgerIssue], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Validate a ledger plus all referenced project-local records."""

    issues = _contract_issues(malts_root, "growth-ledger", ledger)
    signals: dict[str, dict[str, Any]] = {}
    candidates: dict[str, dict[str, Any]] = {}
    base = ledger_path.resolve().parent

    for collection_name, contract_id, id_field, target in (
        ("signal_records", "growth-signal", "signal_id", signals),
        ("candidate_records", "growth-candidate", "candidate_id", candidates),
    ):
        for index, record in enumerate(ledger.get(collection_name, [])):
            path = _resolve_record(base, record.get("relative_path"))
            record_path = f"$.{collection_name}.{index}"
            if path is None:
                issues.append(_issue("GL_PATH_ESCAPE", f"{record_path}.relative_path", "Record path escapes the ledger directory or is not normalized."))
                continue
            if not path.is_file():
                issues.append(_issue("GL_RECORD_MISSING", f"{record_path}.relative_path", f"Referenced record does not exist: {record.get('relative_path')}"))
                continue
            actual_hash = _sha256(path)
            if actual_hash.casefold() != str(record.get("sha256", "")).casefold():
                issues.append(_issue("GL_RECORD_HASH", f"{record_path}.sha256", "Referenced record hash does not match."))
                continue
            try:
                value = load_json(path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                issues.append(_issue("GL_RECORD_LOAD", record_path, str(exc)))
                continue
            issues.extend(_contract_issues(malts_root, contract_id, value))
            record_id = record.get("record_id")
            if value.get(id_field) != record_id:
                issues.append(_issue("GL_RECORD_ID", f"{record_path}.record_id", f"record_id must equal {id_field}."))
            if isinstance(record_id, str):
                target[record_id] = value

    source_task_ids: dict[str, str] = {
        signal_id: signal.get("source_task_id", "") for signal_id, signal in signals.items()
    }
    for candidate_id, candidate in candidates.items():
        missing = set(candidate.get("source_signals", [])).difference(signals)
        if missing:
            issues.append(_issue("GL_SOURCE_SIGNAL_MISSING", f"$.candidate_records.{candidate_id}", f"Missing source signals: {sorted(missing)}"))
        source_tasks = {source_task_ids[item] for item in candidate.get("source_signals", []) if item in source_task_ids}
        for index, validation in enumerate(candidate.get("future_use_validations", [])):
            if validation.get("validation_kind") == "future_use" and validation.get("future_task_id") in source_tasks:
                issues.append(_issue("GR_SOURCE_EVENT_REUSED", f"$.candidate_records.{candidate_id}.future_use_validations.{index}.future_task_id", "The original source task cannot count as future-use validation."))
    return issues, signals, candidates


def analyze_signal(
    signal: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
    malts_root: Path = MALTS_ROOT,
) -> dict[str, Any]:
    """Perform L1 analysis without a durable write."""

    if signal is None or candidate is None:
        return {"decision": "NO_SIGNAL", "durable_write": False, "issues": []}
    issues = _contract_issues(malts_root, "growth-signal", signal)
    issues.extend(_contract_issues(malts_root, "growth-candidate", candidate))
    if candidate.get("authority_level") != "L1" or candidate.get("status") not in {"OBSERVED", "CANDIDATE"}:
        issues.append(_issue("GR_L1_BOUNDARY", "$", "L1 analysis can only inspect an OBSERVED/CANDIDATE L1 candidate."))
    return {
        "decision": "ANALYZED" if not issues else "REJECTED",
        "durable_write": False,
        "issues": [item.as_dict() for item in issues],
    }


def _normalized(values: list[Any]) -> set[str]:
    return {str(item).strip().casefold() for item in values if str(item).strip()}


def _query_issues(query: Any) -> list[LedgerIssue]:
    if not isinstance(query, dict) or set(query) != set(RETRIEVAL_DIMENSIONS):
        return [_issue("GL_QUERY_SHAPE", "$", "Retrieval query must be a closed five-dimension object.")]
    issues: list[LedgerIssue] = []
    for key in RETRIEVAL_DIMENSIONS:
        if not isinstance(query.get(key), list):
            issues.append(_issue("GL_QUERY_SHAPE", f"$.{key}", "Retrieval dimensions must be arrays."))
    if not issues and not any(query[key] for key in RETRIEVAL_DIMENSIONS):
        issues.append(_issue("GL_QUERY_EMPTY", "$", "Retrieval requires at least one relevance dimension."))
    return issues


def retrieve_candidates(
    ledger: dict[str, Any],
    ledger_path: Path,
    query: dict[str, Any],
    malts_root: Path = MALTS_ROOT,
) -> dict[str, Any]:
    """Return relevant candidates without recording adoption or writing files."""

    issues, _, candidates = validate_ledger_bundle(ledger, ledger_path, malts_root)
    issues.extend(_query_issues(query))
    if issues:
        return {"decision": "REJECTED", "matched_candidate_ids": [], "issues": [item.as_dict() for item in issues]}

    normalized_query = {key: _normalized(query[key]) for key in RETRIEVAL_DIMENSIONS}
    matched: list[str] = []
    for candidate_id, candidate in sorted(candidates.items()):
        if candidate.get("status") not in ELIGIBLE_RETRIEVAL_STATES:
            continue
        profile = candidate.get("retrieval_profile", {})
        relevant = True
        for key in RETRIEVAL_DIMENSIONS:
            declared = _normalized(profile.get(key, []))
            if declared and not declared.intersection(normalized_query[key]):
                relevant = False
                break
        if relevant:
            matched.append(candidate_id)
    return {"decision": "MATCHED" if matched else "NO_MATCH", "matched_candidate_ids": matched, "issues": []}


def record_retrieval_event(
    ledger: dict[str, Any],
    event: dict[str, Any],
    authorization_ref: str | None,
    malts_root: Path = MALTS_ROOT,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Append one L2 retrieval event to a copy of the ledger."""

    issues = _contract_issues(malts_root, "growth-ledger", ledger)
    if ledger.get("mode") != "project_maintain" or not authorization_ref or authorization_ref != ledger.get("authorization_ref"):
        issues.append(_issue("GL_L2_AUTH", "$.authorization_ref", "Recording retrieval requires the ledger's one-time L2 authorization."))
    for index, decision in enumerate(event.get("decisions", []) if isinstance(event, dict) else []):
        if decision.get("decision") == "adopted" and decision.get("authorization_ref") != authorization_ref:
            issues.append(_issue("GL_ADOPTION_AUTH", f"$.decisions.{index}.authorization_ref", "Adoption must reference the active L2 authorization."))
    if issues:
        return None, {"decision": "DENIED", "issues": [item.as_dict() for item in issues]}
    updated = copy.deepcopy(ledger)
    updated["retrieval_events"].append(copy.deepcopy(event))
    updated["updated_at"] = event.get("recorded_at")
    output_issues = _contract_issues(malts_root, "growth-ledger", updated)
    if output_issues:
        return None, {"decision": "DENIED", "issues": [item.as_dict() for item in output_issues]}
    return updated, {"decision": "RECORDED", "issues": []}


def apply_future_validation(
    candidate: dict[str, Any],
    validation: dict[str, Any],
    source_signals: list[dict[str, Any]],
    malts_root: Path = MALTS_ROOT,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Apply one future-use result and deterministically update candidate lifecycle."""

    issues = _contract_issues(malts_root, "growth-candidate", candidate)
    issues.extend(_contract_issues(malts_root, "future-use-validation", validation))
    signal_ids = {item.get("signal_id") for item in source_signals}
    for signal in source_signals:
        issues.extend(_contract_issues(malts_root, "growth-signal", signal))
    if validation.get("candidate_id") != candidate.get("candidate_id"):
        issues.append(_issue("GR_VALIDATION_CANDIDATE", "$.candidate_id", "Validation candidate_id does not match."))
    if set(candidate.get("source_signals", [])).difference(signal_ids):
        issues.append(_issue("GR_SOURCE_SIGNAL_MISSING", "$.source_signals", "All candidate source signals must be provided."))
    source_tasks = {item.get("source_task_id") for item in source_signals}
    if validation.get("validation_kind") == "future_use" and validation.get("future_task_id") in source_tasks:
        issues.append(_issue("GR_SOURCE_EVENT_REUSED", "$.future_task_id", "The original source task cannot count as a future use."))
    if issues:
        return None, {"decision": "DENIED", "issues": [item.as_dict() for item in issues]}

    updated = copy.deepcopy(candidate)
    embedded = {key: copy.deepcopy(value) for key, value in validation.items() if key not in {"schema_version", "candidate_id"}}
    updated["future_use_validations"].append(embedded)
    outcome = validation.get("outcome")
    severity = validation.get("severity")
    if outcome == "harmful":
        updated["status"] = "SUSPENDED" if severity in {"high", "critical"} else "CHALLENGED"
        challenge_ref = f"validation:{validation.get('validation_id')}"
        if challenge_ref not in updated["challenge_refs"]:
            updated["challenge_refs"].append(challenge_ref)
        updated["status_reason"] = "Harmful future evidence opened a challenge and stopped automatic application."
    else:
        helped = [
            item for item in updated["future_use_validations"]
            if item.get("validation_kind") == "future_use" and item.get("outcome") == "helped"
        ]
        future_tasks = {item.get("future_task_id") for item in helped}
        independence = {item.get("independence_key") for item in helped}
        supplemental = [
            item for item in updated["future_use_validations"]
            if item.get("validation_kind") in {"independent_review", "negative_test", "counterexample"}
            and item.get("outcome") in {"helped", "neutral"}
        ]
        threshold = len(future_tasks) >= 2 and len(independence) >= 2
        high_risk_ready = updated.get("risk_level") not in {"high", "critical"} or bool(supplemental)
        if threshold and high_risk_ready:
            updated["status"] = "VALIDATED"
            updated["status_reason"] = "The source event plus two independent helped future tasks satisfy three total validations."
        elif updated.get("status") in {"OBSERVED", "CANDIDATE", "PROJECT_EXPERIMENTAL"}:
            updated["status"] = "FUTURE_USE_VALIDATING"
            updated["status_reason"] = "Future-use validation is in progress."

    output_issues = _contract_issues(malts_root, "growth-candidate", updated)
    if output_issues:
        return None, {"decision": "DENIED", "issues": [item.as_dict() for item in output_issues]}
    return updated, {"decision": "UPDATED", "status": updated["status"], "issues": []}


def review_candidate_lifecycle(
    candidate: dict[str, Any],
    action: str,
    reason: str,
    authorization_ref: str | None,
    project_authorization_ref: str | None,
    replacement_ref: str | None = None,
    malts_root: Path = MALTS_ROOT,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Apply one project-authorized challenge/deprecation lifecycle decision."""

    issues = _contract_issues(malts_root, "growth-candidate", candidate)
    if not authorization_ref or authorization_ref != project_authorization_ref:
        issues.append(_issue("GL_L2_AUTH", "$.authorization_ref", "Lifecycle maintenance requires the exact current-project L2 authorization."))
    if not isinstance(reason, str) or not reason.strip():
        issues.append(_issue("GR_LIFECYCLE_REASON", "$.reason", "Lifecycle maintenance requires a non-empty reason."))
    if action not in {"revise", "deprecate", "remove"}:
        issues.append(_issue("GR_LIFECYCLE_ACTION", "$.action", "Unsupported lifecycle maintenance action."))
    current = candidate.get("status")
    if action == "revise":
        if current not in {"CHALLENGED", "SUSPENDED"}:
            issues.append(_issue("GR_LIFECYCLE_TRANSITION", "$.status", "Only challenged or suspended candidates can enter revision review."))
        if not isinstance(replacement_ref, str) or not replacement_ref.strip() or replacement_ref == candidate.get("candidate_id"):
            issues.append(_issue("GR_REPLACEMENT_REF", "$.replacement_ref", "Revision requires a distinct replacement candidate reference."))
    elif action == "deprecate" and current in {"DEPRECATED", "REMOVED"}:
        issues.append(_issue("GR_LIFECYCLE_TRANSITION", "$.status", "Only an active, challenged, suspended, rejected, or accepted candidate can be deprecated."))
    elif action == "remove" and current != "DEPRECATED":
        issues.append(_issue("GR_LIFECYCLE_TRANSITION", "$.status", "Removal requires a prior DEPRECATED state."))
    if issues:
        return None, {"decision": "DENIED", "issues": [item.as_dict() for item in issues]}

    updated = copy.deepcopy(candidate)
    if action == "revise":
        updated["replacement_ref"] = replacement_ref
        updated["status_reason"] = reason.strip()
    elif action == "deprecate":
        updated["status"] = "DEPRECATED"
        updated["status_reason"] = reason.strip()
        if replacement_ref is not None:
            updated["replacement_ref"] = replacement_ref
    else:
        updated["status"] = "REMOVED"
        updated["status_reason"] = reason.strip()

    output_issues = _contract_issues(malts_root, "growth-candidate", updated)
    if output_issues:
        return None, {"decision": "DENIED", "issues": [item.as_dict() for item in output_issues]}
    return updated, {"decision": "UPDATED", "status": updated["status"], "issues": []}


def _write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {path}")
    if not path.parent.is_dir():
        raise FileNotFoundError(f"Output parent does not exist: {path.parent}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MALTS project-local Growth ledger")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--ledger", required=True, type=Path)
    retrieve = subparsers.add_parser("retrieve")
    retrieve.add_argument("--ledger", required=True, type=Path)
    retrieve.add_argument("--query", required=True, type=Path)
    record = subparsers.add_parser("record")
    record.add_argument("--ledger", required=True, type=Path)
    record.add_argument("--event", required=True, type=Path)
    record.add_argument("--authorization-ref", required=True)
    record.add_argument("--output", required=True, type=Path)
    apply_validation = subparsers.add_parser("apply-validation")
    apply_validation.add_argument("--candidate", required=True, type=Path)
    apply_validation.add_argument("--validation", required=True, type=Path)
    apply_validation.add_argument("--source-signal", action="append", required=True, type=Path)
    apply_validation.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            ledger = load_json(args.ledger)
            issues, _, _ = validate_ledger_bundle(ledger, args.ledger)
            print(json.dumps({"status": "PASS" if not issues else "FAIL", "issues": [item.as_dict() for item in issues]}, ensure_ascii=False, indent=2))
            return 0 if not issues else 2
        if args.command == "retrieve":
            result = retrieve_candidates(load_json(args.ledger), args.ledger, load_json(args.query))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["decision"] in {"MATCHED", "NO_MATCH"} else 2
        if args.command == "record":
            updated, result = record_retrieval_event(load_json(args.ledger), load_json(args.event), args.authorization_ref)
        else:
            signals = [load_json(path) for path in args.source_signal]
            updated, result = apply_future_validation(load_json(args.candidate), load_json(args.validation), signals)
        if updated is None:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2
        _write_new_json(args.output, updated)
        print(json.dumps({**result, "output": str(args.output)}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"decision": "ERROR", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
