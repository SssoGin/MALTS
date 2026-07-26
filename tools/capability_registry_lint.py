#!/usr/bin/env python3
"""Validation helpers for the staged MALTS capability-governance contract."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from malts_user_contracts import validate_instance


REQUIRED_ENTRY_FIELDS = {
    "id",
    "skill_id",
    "name",
    "declared_name",
    "aliases",
    "capability_kind",
    "ownership",
    "owner",
    "managed_by",
    "source",
    "content",
    "descriptor",
    "interface",
    "package_variants",
    "compatibility",
    "adapters",
    "dependencies",
    "source_trust",
    "review_status",
    "execution_risk",
    "risk_factors",
    "exposure_policy",
    "routing",
    "lifecycle",
    "projection_plan",
    "verification",
    "last_verified",
    "evidence_refs",
    "rollback",
}

CAPABILITY_KINDS = {"skill", "agent", "tool-adapter", "workflow", "verifier", "checklist"}
SOURCE_TRUST = {"unknown", "unverified", "community", "verified", "first-party"}
REVIEW_STATUS = {"pending", "static-reviewed", "runtime-verified", "rejected"}
EXECUTION_RISK = {"low", "medium", "high", "critical"}
RISK_FACTORS = {
    "scripts",
    "write",
    "network",
    "credentials",
    "destructive",
    "self-modifying",
    "external-runtime",
}
TOOLS = {"codex", "claude-code", "opencode"}
EXPOSURE = {"hidden", "advisory", "visible"}
LIFECYCLE = {"candidate", "active", "deprecated", "quarantined", "blocked"}
MACHINE_LOCATOR = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/]{1,2}|~[\\/]|[A-Za-z][A-Za-z0-9+.-]*://|git@)")
SHA256 = re.compile(r"^[A-Fa-f0-9]{64}$")
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]+$")
SKILL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]+$")


def _load_json(path: Path, label: str, errors: list[str]) -> Any:
    if not path.exists():
        errors.append(f"Missing {label}: {path}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Invalid {label}: {path} ({exc})")
        return None


def _require_mapping(value: Any, label: str, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object.")
        return None
    return value


def _check_public_locator(value: Any, label: str, errors: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value:
        errors.append(f"{label} must be a non-empty string or null.")
        return
    if MACHINE_LOCATOR.match(value):
        errors.append(f"{label} must be package-relative in a public contract.")


def _validate_schema(schema: Any, errors: list[str]) -> None:
    root = _require_mapping(schema, "Capability Registry Schema", errors)
    if root is None:
        return
    if root.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("Capability Registry Schema must use JSON Schema draft 2020-12.")
    if root.get("type") != "object" or root.get("additionalProperties") is not False:
        errors.append("Capability Registry Schema root must be a closed object.")
    required = set(root.get("required", []))
    expected_root = {"schema_version", "registry_version", "design_status", "registry_scope", "generated_at", "entries"}
    if not expected_root.issubset(required):
        errors.append("Capability Registry Schema is missing required root fields.")
    definitions = root.get("$defs", {})
    capability = definitions.get("capability", {}) if isinstance(definitions, dict) else {}
    if not REQUIRED_ENTRY_FIELDS.issubset(set(capability.get("required", []))):
        errors.append("Capability Registry Schema is missing required capability fields.")


def _validate_entry(entry: Any, index: int, public_contract: bool, errors: list[str]) -> str | None:
    item = _require_mapping(entry, f"entries[{index}]", errors)
    if item is None:
        return None

    missing = sorted(REQUIRED_ENTRY_FIELDS - set(item))
    if missing:
        errors.append(f"entries[{index}] is missing fields: {', '.join(missing)}")

    capability_id = item.get("id")
    if not isinstance(capability_id, str) or not ID_PATTERN.fullmatch(capability_id):
        errors.append(f"entries[{index}].id is invalid.")
        capability_id = None
    if not isinstance(item.get("skill_id"), str) or not SKILL_ID_PATTERN.fullmatch(item["skill_id"]):
        errors.append(f"entries[{index}].skill_id is invalid.")
    for field in ("name", "declared_name", "owner", "managed_by"):
        if not isinstance(item.get(field), str) or not item[field]:
            errors.append(f"entries[{index}].{field} must be a non-empty string.")
    if item.get("capability_kind") not in CAPABILITY_KINDS:
        errors.append(f"entries[{index}].capability_kind is invalid.")
    if item.get("ownership") not in {"malts", "external", "tool", "user"}:
        errors.append(f"entries[{index}].ownership is invalid.")
    if not isinstance(item.get("aliases"), list):
        errors.append(f"entries[{index}].aliases must be an array.")
    if item.get("source_trust") not in SOURCE_TRUST:
        errors.append(f"entries[{index}].source_trust is invalid.")
    if item.get("review_status") not in REVIEW_STATUS:
        errors.append(f"entries[{index}].review_status is invalid.")
    if item.get("execution_risk") not in EXECUTION_RISK:
        errors.append(f"entries[{index}].execution_risk is invalid.")

    factors = item.get("risk_factors")
    if not isinstance(factors, list) or any(factor not in RISK_FACTORS for factor in factors):
        errors.append(f"entries[{index}].risk_factors contains an invalid value.")

    source = _require_mapping(item.get("source"), f"entries[{index}].source", errors)
    if source is not None:
        for field in ("type", "locator", "revision", "source_relative_path"):
            if not isinstance(source.get(field), str) or not source[field]:
                errors.append(f"entries[{index}].source.{field} must be a non-empty string.")
        if source.get("package_variant") not in {"local", "public"}:
            errors.append(f"entries[{index}].source.package_variant is invalid.")
        if public_contract:
            _check_public_locator(source.get("locator"), f"entries[{index}].source.locator", errors)
            _check_public_locator(
                source.get("source_relative_path"),
                f"entries[{index}].source.source_relative_path",
                errors,
            )

    content = _require_mapping(item.get("content"), f"entries[{index}].content", errors)
    if content is not None:
        for field in ("source_sha256", "tree_sha256"):
            if not SHA256.fullmatch(str(content.get(field, ""))):
                errors.append(f"entries[{index}].content.{field} must be a SHA-256 value.")

    descriptor = _require_mapping(item.get("descriptor"), f"entries[{index}].descriptor", errors)
    if descriptor is not None:
        if not isinstance(descriptor.get("relative_path"), str) or not descriptor["relative_path"]:
            errors.append(f"entries[{index}].descriptor.relative_path must be a non-empty string.")
        elif public_contract:
            _check_public_locator(
                descriptor["relative_path"],
                f"entries[{index}].descriptor.relative_path",
                errors,
            )
        if not SHA256.fullmatch(str(descriptor.get("sha256", ""))):
            errors.append(f"entries[{index}].descriptor.sha256 must be a SHA-256 value.")

    interface = _require_mapping(item.get("interface"), f"entries[{index}].interface", errors)
    if interface is not None:
        for field in ("inputs", "outputs", "required_permissions"):
            if not isinstance(interface.get(field), list):
                errors.append(f"entries[{index}].interface.{field} must be an array.")

    package_variants = item.get("package_variants")
    if (
        not isinstance(package_variants, list)
        or not package_variants
        or any(value not in {"local", "public"} for value in package_variants)
    ):
        errors.append(f"entries[{index}].package_variants is invalid.")
    elif source is not None and source.get("package_variant") not in package_variants:
        errors.append(f"entries[{index}].source.package_variant must appear in package_variants.")

    compatibility = _require_mapping(item.get("compatibility"), f"entries[{index}].compatibility", errors)
    if compatibility is not None:
        compatible_tools = compatibility.get("tools")
        if not isinstance(compatible_tools, list) or any(tool not in TOOLS for tool in compatible_tools):
            errors.append(f"entries[{index}].compatibility.tools contains an invalid tool.")

    adapters = item.get("adapters")
    if not isinstance(adapters, list):
        errors.append(f"entries[{index}].adapters must be an array.")
    else:
        adapter_tools: list[str] = []
        for adapter_index, adapter_value in enumerate(adapters):
            adapter = _require_mapping(
                adapter_value,
                f"entries[{index}].adapters[{adapter_index}]",
                errors,
            )
            if adapter is None:
                continue
            if adapter.get("tool") not in TOOLS:
                errors.append(f"entries[{index}].adapters[{adapter_index}].tool is invalid.")
            elif adapter["tool"] in adapter_tools:
                errors.append(f"entries[{index}].adapters declares tool {adapter['tool']} more than once.")
            else:
                adapter_tools.append(adapter["tool"])
            if public_contract:
                _check_public_locator(
                    adapter.get("locator"),
                    f"entries[{index}].adapters[{adapter_index}].locator",
                    errors,
                )

    dependencies = item.get("dependencies")
    if not isinstance(dependencies, list):
        errors.append(f"entries[{index}].dependencies must be an array.")
    elif public_contract:
        for dependency_index, dependency in enumerate(dependencies):
            if isinstance(dependency, dict):
                _check_public_locator(
                    dependency.get("source_relative_path"),
                    f"entries[{index}].dependencies[{dependency_index}].source_relative_path",
                    errors,
                )

    exposure = _require_mapping(item.get("exposure_policy"), f"entries[{index}].exposure_policy", errors)
    if exposure is not None:
        if exposure.get("default") not in EXPOSURE:
            errors.append(f"entries[{index}].exposure_policy.default is invalid.")
        tool_exposure = exposure.get("tools")
        if not isinstance(tool_exposure, dict) or set(tool_exposure) != TOOLS:
            errors.append(f"entries[{index}].exposure_policy.tools must declare all three tools exactly once.")
        elif any(value not in EXPOSURE for value in tool_exposure.values()):
            errors.append(f"entries[{index}].exposure_policy.tools contains an invalid exposure value.")

    lifecycle = _require_mapping(item.get("lifecycle"), f"entries[{index}].lifecycle", errors)
    if lifecycle is not None and lifecycle.get("state") not in LIFECYCLE:
        errors.append(f"entries[{index}].lifecycle.state is invalid.")

    if not isinstance(item.get("evidence_refs"), list):
        errors.append(f"entries[{index}].evidence_refs must be an array.")
    projection_plan = item.get("projection_plan")
    if not isinstance(projection_plan, list):
        errors.append(f"entries[{index}].projection_plan must be an array.")
    else:
        projection_tools: set[str] = set()
        for projection_index, projection in enumerate(projection_plan):
            if not isinstance(projection, dict):
                continue
            tool = projection.get("tool")
            if tool in projection_tools:
                errors.append(f"entries[{index}].projection_plan declares tool {tool} more than once.")
            elif isinstance(tool, str):
                projection_tools.add(tool)
            if public_contract:
                _check_public_locator(
                    projection.get("target"),
                    f"entries[{index}].projection_plan[{projection_index}].target",
                    errors,
                )
    if not isinstance(item.get("verification"), list):
        errors.append(f"entries[{index}].verification must be an array.")
    _require_mapping(item.get("rollback"), f"entries[{index}].rollback", errors)
    return capability_id


def validate_skill_governance(
    malts_root: Path,
    schema_path: Path | None = None,
    registry_path: Path | None = None,
) -> list[str]:
    """Return contract validation errors; an empty list means PASS."""

    errors: list[str] = []
    required_docs = (
        malts_root / "docs" / "CAPABILITY_AND_SKILL_GOVERNANCE.md",
        malts_root / "docs" / "zh-CN" / "CAPABILITY_AND_SKILL_GOVERNANCE.md",
    )
    for path in required_docs:
        if not path.exists():
            errors.append(f"Missing capability-governance document: {path}")

    resolved_schema = schema_path or malts_root / "tools" / "capability_registry.schema.json"
    resolved_registry = registry_path or malts_root / "tools" / "capability_registry.example.json"
    schema = _load_json(resolved_schema, "Capability Registry Schema", errors)
    registry = _load_json(resolved_registry, "Capability Registry example/state", errors)
    if schema is not None:
        _validate_schema(schema, errors)

    root = _require_mapping(registry, "Capability Registry example/state", errors) if registry is not None else None
    if root is None:
        return errors
    if not isinstance(root.get("schema_version"), int) or root["schema_version"] < 1:
        errors.append("Capability Registry schema_version must be a positive integer.")
    if not isinstance(root.get("registry_version"), str) or not root["registry_version"]:
        errors.append("Capability Registry registry_version must be a non-empty string.")
    if root.get("design_status") not in {"v1.0-target", "active"}:
        errors.append("Capability Registry design_status is invalid.")
    if root.get("registry_scope") not in {"public-contract", "operator-state"}:
        errors.append("Capability Registry registry_scope is invalid.")

    entries = root.get("entries")
    if not isinstance(entries, list):
        errors.append("Capability Registry entries must be an array.")
        return errors
    if registry_path is None and not entries:
        errors.append("Public Capability Registry example must contain at least one entry.")

    seen: set[str] = set()
    public_contract = root.get("registry_scope") == "public-contract"
    for index, entry in enumerate(entries):
        capability_id = _validate_entry(entry, index, public_contract, errors)
        if capability_id in seen:
            errors.append(f"Duplicate capability id: {capability_id}")
        if capability_id:
            seen.add(capability_id)

    if schema is not None:
        errors.extend(issue.render() for issue in validate_instance(malts_root, "capability-registry", registry, schema_override=schema))

    if registry_path is None:
        if root.get("design_status") != "v1.0-target" or not public_contract:
            errors.append("Bundled example must remain a v1.0-target public contract example.")
        if root.get("generated_at") is not None:
            errors.append("Bundled example must not carry generated operator state.")

    return errors
