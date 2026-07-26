#!/usr/bin/env python3
"""Validate and classify pre-collected runtime capability evidence for MALTS W4.

This component does not invoke a runtime or provider. Real behavior probing and G4
validation require a separately authorized launch review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from malts_user_contracts import load_json, validate_instance


MALTS_ROOT = Path(__file__).resolve().parent.parent
VERIFIED_BINDINGS = {"effective_verified", "fallback_verified"}


def classify_runtime_evidence(evidence: dict[str, Any], malts_root: Path = MALTS_ROOT) -> dict[str, Any]:
    """Return a fail-closed classification of one evidence document."""

    issues = [
        {"code": item.code, "path": item.path, "message": item.message}
        for item in validate_instance(malts_root, "runtime-capability-evidence", evidence)
    ]
    if issues:
        return {
            "status": "FAIL",
            "classification": "invalid",
            "component_route_eligible": False,
            "g4_precondition_met": False,
            "g4_status": "NOT_RUN",
            "agent_count_ceiling": 0,
            "evidence_strengths": [],
            "issues": issues,
        }

    binding = evidence["binding_status"]
    test_state = evidence["test_state"]
    outcome = evidence["effective"]["outcome"]
    strengths = sorted({source["strength"] for source in evidence["probe_sources"]})
    effective_proof = (
        binding in VERIFIED_BINDINGS
        and test_state == "behavior_verified"
        and outcome == "effective"
        and "effective" in strengths
        and bool(evidence["usage_evidence"])
    )
    if binding == "unsupported":
        classification = "runtime_unsupported"
        ceiling = 0
    elif test_state == "provider_unconfigured":
        classification = "provider_unconfigured"
        ceiling = 0
    elif effective_proof:
        classification = binding
        ceiling = evidence["effective_concurrency"] or 1
    elif binding == "configured_unverified":
        classification = "configured_unverified"
        ceiling = 1
    elif binding in {"static_binding", "inherited"}:
        classification = binding
        ceiling = 1
    else:
        classification = "effective_unknown"
        ceiling = 1

    return {
        "status": "PASS",
        "classification": classification,
        "component_route_eligible": ceiling > 0,
        "g4_precondition_met": effective_proof and evidence["effective_concurrency"] is not None,
        "g4_status": "NOT_RUN",
        "agent_count_ceiling": ceiling,
        "evidence_strengths": strengths,
        "issues": [],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify existing MALTS runtime capability evidence without provider calls")
    parser.add_argument("--evidence", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = classify_runtime_evidence(load_json(args.evidence))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "PASS" else 2
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
