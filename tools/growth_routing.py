#!/usr/bin/env python3
"""Deterministic, no-write Growth Routing Gate for final delivery."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class GrowthRoutingError(ValueError):
    """Raised when a routing request is structurally invalid."""


SIGNALS = frozenset(
    {
        "USER_CORRECTION",
        "VERIFICATION_REVERSAL",
        "REPEATED_FAILURE",
        "REWORK",
        "RECOVERY_OR_ROLLBACK",
        "TOOL_FACT_CONFLICT",
        "MATERIALLY_SUCCESSFUL_METHOD",
        "PHASE_OR_LONG_TASK_COMPLETION",
        "DELIVERY_FAILURE",
    }
)

RETROSPECTIVE_SIGNALS = frozenset(
    {
        "REPEATED_FAILURE",
        "REWORK",
        "PHASE_OR_LONG_TASK_COMPLETION",
        "DELIVERY_FAILURE",
    }
)


def _require_bool(request: dict[str, Any], key: str, default: bool = False) -> bool:
    value = request.get(key, default)
    if not isinstance(value, bool):
        raise GrowthRoutingError(f"GRT_INPUT: `{key}` must be boolean")
    return value


def _require_optional_text(request: dict[str, Any], key: str) -> str | None:
    value = request.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise GrowthRoutingError(f"GRT_INPUT: `{key}` must be non-empty text when supplied")
    return value.strip()


def classify_growth_route(request: dict[str, Any]) -> dict[str, Any]:
    """Classify one final-delivery Growth decision without writing durable state."""
    if not isinstance(request, dict):
        raise GrowthRoutingError("GRT_INPUT: request must be an object")
    trivial = _require_bool(request, "trivial")
    retrospective_authorized = _require_bool(request, "retrospective_authorized")
    retrospective_declined = _require_bool(request, "retrospective_declined")
    high_impact = _require_bool(request, "high_impact")
    workspace_initialized = _require_bool(request, "workspace_initialized", default=True)
    project_write_authorized = _require_bool(request, "project_write_authorized")
    global_promotion_requested = _require_bool(request, "global_promotion_requested")
    global_promotion_authorized = _require_bool(request, "global_promotion_authorized")
    _require_optional_text(request, "project_authorization_ref")
    _require_optional_text(request, "global_authorization_ref")
    plan_gate = request.get("plan_gate", "N/A")
    if plan_gate not in {"PASS", "N/A", "BLOCKED"}:
        raise GrowthRoutingError("GRT_INPUT: `plan_gate` must be PASS, N/A, or BLOCKED")
    raw_signals = request.get("signals", [])
    if not isinstance(raw_signals, list) or not all(isinstance(item, str) for item in raw_signals):
        raise GrowthRoutingError("GRT_INPUT: `signals` must be an array of strings")
    signals = sorted(set(raw_signals))
    unknown = sorted(set(signals) - SIGNALS)
    if unknown:
        raise GrowthRoutingError("GRT_UNKNOWN_SIGNAL: " + ", ".join(unknown))

    if plan_gate == "BLOCKED":
        route = "BLOCKED"
        reason = "Applicable Plan Recheck is blocked; Growth cannot bypass final-delivery safety gates."
    elif retrospective_authorized:
        route = "RETROSPECTIVE_AUTHORIZED"
        reason = "A full retrospective is explicitly authorized."
    elif retrospective_declined:
        route = "LIGHT_REPORT"
        reason = "A full retrospective was declined; keep the bounded L1 result without repeating the recommendation."
    elif high_impact or RETROSPECTIVE_SIGNALS.intersection(signals):
        route = "RETROSPECTIVE_RECOMMENDED"
        reason = "Repeated, high-impact, delivery, or phase-level evidence warrants a retrospective recommendation."
    elif trivial and not signals:
        route = "NO_OUTPUT"
        reason = "Trivial work has no Growth signal."
    else:
        route = "LIGHT_REPORT"
        reason = "Non-trivial work or a concrete signal requires a short no-write L1 Growth Review."

    durable_write_authorized = route == "RETROSPECTIVE_AUTHORIZED" and project_write_authorized
    l3_confirmation_required = global_promotion_requested and not global_promotion_authorized
    evidence_state = "CANDIDATE" if "MATERIALLY_SUCCESSFUL_METHOD" in signals else "NONE"
    return {
        "schema_version": 1,
        "route": route,
        "signals": signals,
        "reason": reason,
        "l1_in_context_only": route in {"NO_OUTPUT", "LIGHT_REPORT", "RETROSPECTIVE_RECOMMENDED"},
        "l1_confirmation_required": False,
        # This router only classifies and renders a route.  It never writes a
        # Growth record; an L2/L3 command owns any later durable mutation.
        "durable_write_performed": False,
        "durable_write_authorized": durable_write_authorized,
        "l2_or_l3_authorization_required": route == "RETROSPECTIVE_AUTHORIZED" and not durable_write_authorized,
        "l3_confirmation_required": l3_confirmation_required,
        "workspace_initialized": workspace_initialized,
        "evidence_state": evidence_state,
        # Execution is a separate L2/L3 command, even when the caller has
        # already supplied the required authorization.
        "full_retrospective_execution": False,
        "full_retrospective_authorized": durable_write_authorized,
        "creates_workspace_entities": False,
        "starts_background_process": False,
    }


def require_user_visible_growth_summary(result: dict[str, Any], final_reply: str) -> None:
    """Reject a delivery that hides a required non-durable Growth result in a file only."""
    if not isinstance(final_reply, str):
        raise GrowthRoutingError("GRT_VISIBILITY: final_reply must be text")
    route = result.get("route")
    if route == "NO_OUTPUT":
        return
    if route not in {"BLOCKED", "LIGHT_REPORT", "RETROSPECTIVE_RECOMMENDED", "RETROSPECTIVE_AUTHORIZED"}:
        raise GrowthRoutingError("GRT_VISIBILITY: route is invalid")
    if route not in final_reply:
        raise GrowthRoutingError("GRT_VISIBILITY: required Growth route is absent from the final user reply")


def render_user_summary(result: dict[str, Any], language: str) -> str | None:
    """Render the bounded user-facing L1 outcome without inventing durable facts."""
    route = result["route"]
    if route == "NO_OUTPUT":
        return None
    if language == "zh-CN":
        labels = {
            "BLOCKED": "成长路由已阻塞（BLOCKED）",
            "LIGHT_REPORT": "轻量成长复核（LIGHT_REPORT）",
            "RETROSPECTIVE_RECOMMENDED": "建议完整复盘（RETROSPECTIVE_RECOMMENDED）",
            "RETROSPECTIVE_AUTHORIZED": "已授权完整复盘（RETROSPECTIVE_AUTHORIZED）",
        }
        return f"{labels[route]}：{result['reason']} 此路由判断不执行持久化写入。"
    return f"Growth routing ({route}): {result['reason']} This routing decision performs no durable write."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the MALTS no-write Growth Routing Gate.")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--language", choices=("en", "zh-CN"), default="en")
    args = parser.parse_args(argv)
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        result = classify_growth_route(request)
        result["user_summary"] = render_user_summary(result, args.language)
    except (OSError, json.JSONDecodeError, GrowthRoutingError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
