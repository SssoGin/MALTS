#!/usr/bin/env python3
"""Deterministic MALTS Capability Catalog generation and advisory routing.

This W3 component is deliberately read-only with respect to Skill sources and
tool installations. Generated Catalogs are operator state and must be written
outside the MALTS package tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from malts_user_contracts import ContractIssue, load_json, validate_instance


TOOLS = ("codex", "claude-code", "opencode")
RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
FRONT_MATTER = re.compile(r"\A---\r?\n(?P<body>.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)
FRONT_MATTER_FIELD = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
MACHINE_LOCATOR = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/]{1,2}|~[\\/]|[A-Za-z][A-Za-z0-9+.-]*://|git@)")


class CapabilityError(ValueError):
    """Stable fail-closed error for Catalog, routing, or collision input."""


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def iter_tree_files(root: Path) -> Iterable[Path]:
    root = root.resolve()
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        directories[:] = [
            name
            for name in sorted(directories, key=str.casefold)
            if name not in {".git", "__pycache__", ".pytest_cache", ".mypy_cache"}
            and not (current_path / name).is_symlink()
        ]
        for name in sorted(filenames, key=str.casefold):
            path = current_path / name
            if path.is_file() and not path.is_symlink() and path.suffix.lower() != ".pyc":
                yield path


def tree_sha256(root: Path) -> str:
    root = root.resolve()
    records = []
    for path in iter_tree_files(root):
        relative = path.relative_to(root).as_posix()
        records.append((relative, path.stat().st_size, sha256_file(path)))
    records.sort(key=lambda item: (item[0].casefold(), item[0]))
    payload = "".join(f"{relative}\t{size}\t{digest}\n" for relative, size, digest in records).encode("utf-8")
    return sha256_bytes(payload)


def _parse_scalar(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        if raw[0] == '"':
            return str(json.loads(raw))
        return raw[1:-1].replace("''", "'")
    return raw


def parse_skill_front_matter(path: Path, *, allow_bom: bool = True) -> dict[str, str]:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf") and not allow_bom:
        raise CapabilityError(f"CAP_DESCRIPTOR_FRONTMATTER: UTF-8 BOM is not supported: {path}")
    text = data.decode("utf-8-sig" if allow_bom else "utf-8")
    match = FRONT_MATTER.match(text)
    if not match:
        raise CapabilityError(f"CAP_DESCRIPTOR_FRONTMATTER: malformed SKILL.md front matter: {path}")
    values: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        field = FRONT_MATTER_FIELD.fullmatch(line)
        if not field:
            raise CapabilityError(f"CAP_DESCRIPTOR_FRONTMATTER: unsupported front matter line: {path}")
        key, raw = field.groups()
        if key in values or not raw.strip():
            raise CapabilityError(f"CAP_DESCRIPTOR_FRONTMATTER: duplicate or empty `{key}`: {path}")
        values[key] = _parse_scalar(raw)
    if not values.get("name") or not values.get("description"):
        raise CapabilityError(f"CAP_DESCRIPTOR_FRONTMATTER: name and description are required: {path}")
    return values


def _render_issues(issues: list[ContractIssue]) -> str:
    return "; ".join(issue.render() for issue in issues)


def _path_inside(path: Path, parent: Path) -> bool:
    path = path.resolve()
    parent = parent.resolve()
    return path == parent or parent in path.parents


def _require_package_relative(value: str, label: str) -> None:
    if MACHINE_LOCATOR.match(value) or ".." in Path(value.replace("\\", "/")).parts:
        raise CapabilityError(f"CAP_PUBLIC_LOCATOR: {label} must be package-relative: {value}")


def load_capability_descriptor(malts_root: Path, descriptor_path: Path) -> dict[str, Any]:
    descriptor = load_json(descriptor_path)
    issues = validate_instance(malts_root, "capability-descriptor", descriptor)
    if issues:
        raise CapabilityError(_render_issues(issues))
    skill_dir = descriptor_path.parent
    skill_path = skill_dir / "SKILL.md"
    if not skill_path.is_file():
        raise CapabilityError(f"CAP_DESCRIPTOR_FRONTMATTER: missing SKILL.md: {skill_path}")
    front_matter = parse_skill_front_matter(skill_path)
    if skill_dir.name != descriptor["skill_id"]:
        raise CapabilityError(
            f"CAP_DESCRIPTOR_PATH: descriptor skill_id `{descriptor['skill_id']}` does not match directory `{skill_dir.name}`"
        )
    if front_matter["name"] != descriptor["declared_name"]:
        raise CapabilityError(
            f"CAP_DESCRIPTOR_FRONTMATTER: declared_name `{descriptor['declared_name']}` does not match `{front_matter['name']}`"
        )
    projected = descriptor["projected_names"]
    if set(projected) != set(TOOLS) or len({projected[tool].casefold() for tool in TOOLS}) != 1:
        raise CapabilityError("CAP_DESCRIPTOR_PROJECTION_NAME: all three tools require one stable MALTS-prefixed name")
    if not projected["codex"].startswith("malts-"):
        raise CapabilityError("CAP_DESCRIPTOR_PROJECTION_NAME: projected names must use the malts- prefix")
    if descriptor["tool_metadata"]["codex"]["include_openai_metadata"] is not True:
        raise CapabilityError("CAP_DESCRIPTOR_TOOL_METADATA: Codex projection requires agents/openai.yaml metadata")
    if any(descriptor["tool_metadata"][tool]["include_openai_metadata"] for tool in ("claude-code", "opencode")):
        raise CapabilityError("CAP_DESCRIPTOR_TOOL_METADATA: Claude Code and OpenCode must not inherit Codex-only metadata")
    return descriptor


def discover_capability_descriptors(malts_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    skills_root = malts_root / "skills"
    found: list[tuple[Path, dict[str, Any]]] = []
    for descriptor_path in sorted(skills_root.glob("*/capability.json"), key=lambda path: path.as_posix().casefold()):
        found.append((descriptor_path, load_capability_descriptor(malts_root, descriptor_path)))
    if not found:
        raise CapabilityError(f"CAP_DESCRIPTOR_MISSING: no capability.json files found under {skills_root}")
    ids = [descriptor["capability_id"].casefold() for _, descriptor in found]
    if len(ids) != len(set(ids)):
        raise CapabilityError("CAP_DUPLICATE_ID: descriptor capability_id values must be unique")
    return found


def validate_descriptor_dependencies(
    malts_root: Path,
    descriptors: list[tuple[Path, dict[str, Any]]],
) -> None:
    ids = {descriptor["capability_id"] for _, descriptor in descriptors}
    graph: dict[str, set[str]] = {capability_id: set() for capability_id in ids}
    for _, descriptor in descriptors:
        for dependency in descriptor["dependencies"]:
            relative = dependency["source_relative_path"]
            if relative:
                _require_package_relative(relative, f"{descriptor['capability_id']} dependency")
                if dependency["required"] and not (malts_root / relative).is_file():
                    raise CapabilityError(
                        f"CAP_DEPENDENCY_MISSING: {descriptor['capability_id']} requires missing source `{relative}`"
                    )
            if dependency["type"] in {"skill", "agent"} and dependency["required"]:
                if dependency["id"] not in ids:
                    raise CapabilityError(
                        f"CAP_DEPENDENCY_MISSING: {descriptor['capability_id']} requires `{dependency['id']}`"
                    )
                graph[descriptor["capability_id"]].add(dependency["id"])
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise CapabilityError(f"CAP_DEPENDENCY_CYCLE: dependency cycle includes `{node}`")
        if node in visited:
            return
        visiting.add(node)
        for target in graph[node]:
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for capability_id in sorted(graph):
        visit(capability_id)


def _descriptor_catalog_entry(
    malts_root: Path,
    descriptor_path: Path,
    descriptor: dict[str, Any],
    source_revision: str,
    package_variant: str,
) -> dict[str, Any]:
    skill_dir = descriptor_path.parent
    skill_path = skill_dir / "SKILL.md"
    skill_relative = skill_path.relative_to(malts_root).as_posix()
    descriptor_relative = descriptor_path.relative_to(malts_root).as_posix()
    projected_name = descriptor["projected_names"]["codex"]
    dependencies = [
        {
            "id": dependency["id"],
            "type": dependency["type"],
            "required": dependency["required"],
            "source_relative_path": dependency["source_relative_path"],
        }
        for dependency in descriptor["dependencies"]
    ]
    verification = [
        {
            "level": level,
            "status": "pass" if level in descriptor["verification"]["levels"] else "pending",
            "tool": None,
            "evidence_ref": descriptor["verification"]["evidence_refs"][0],
        }
        for level in ("static", "discovery", "invocation", "behavior")
    ]
    return {
        "id": descriptor["capability_id"],
        "skill_id": descriptor["skill_id"],
        "name": projected_name,
        "declared_name": descriptor["declared_name"],
        "aliases": [],
        "capability_kind": "skill",
        "ownership": "malts",
        "owner": "MALTS",
        "managed_by": "MALTS",
        "source": {
            "type": "package",
            "locator": skill_dir.relative_to(malts_root).as_posix(),
            "revision": source_revision,
            "package_variant": package_variant,
            "source_relative_path": skill_relative,
        },
        "content": {"source_sha256": sha256_file(skill_path), "tree_sha256": tree_sha256(skill_dir)},
        "descriptor": {"relative_path": descriptor_relative, "sha256": sha256_file(descriptor_path)},
        "interface": {
            "inputs": descriptor["inputs"],
            "outputs": descriptor["outputs"],
            "required_permissions": descriptor["required_permissions"],
        },
        "package_variants": descriptor["package_variants"],
        "compatibility": {
            "platforms": ["windows"],
            "tools": descriptor["supported_tools"],
            "protocol_versions": ["malts-capability-v1"],
            "constraints": [],
        },
        "adapters": [
            {"tool": tool, "projection": "native", "locator": f"skills/{descriptor['projected_names'][tool]}/SKILL.md"}
            for tool in TOOLS
        ],
        "dependencies": dependencies,
        "source_trust": "first-party",
        "review_status": "static-reviewed",
        "execution_risk": descriptor["risks"]["risk_class"],
        "risk_factors": descriptor["risks"]["factors"],
        "exposure_policy": {
            "default": "visible",
            "tools": {tool: "visible" for tool in TOOLS},
            "catalog_budget_class": "core",
            "reason": "MALTS-owned capability with a validated canonical descriptor.",
        },
        "routing": {
            "triggers": descriptor["triggers"],
            "task_types": descriptor["applicability"]["task_types"],
            "modes": descriptor["applicability"]["modes"],
            "conditions": descriptor["applicability"]["conditions"],
            "contraindications": descriptor["applicability"]["contraindications"],
        },
        "lifecycle": {
            "state": "active",
            "legacy_aliases": [descriptor["declared_name"]] if descriptor["declared_name"] != projected_name else [],
        },
        "projection_plan": [
            {
                "tool": tool,
                "projection": "native",
                "target": f"skills/{descriptor['projected_names'][tool]}/SKILL.md",
                "required": True,
                "projected_name": descriptor["projected_names"][tool],
                "package_variant": package_variant,
                "metadata_type": (
                    "skill-with-openai-metadata"
                    if descriptor["tool_metadata"][tool]["include_openai_metadata"]
                    else "skill-only"
                ),
            }
            for tool in TOOLS
        ],
        "verification": verification,
        "last_verified": None,
        "evidence_refs": descriptor["verification"]["evidence_refs"],
        "rollback": {
            "strategy": "remove-projection",
            "reference": f"catalog:{descriptor['capability_id']}:{source_revision}",
        },
    }


def validate_external_sidecar(malts_root: Path, sidecar_path: Path) -> dict[str, Any]:
    sidecar = load_json(sidecar_path)
    issues = validate_instance(malts_root, "external-capability-sidecar", sidecar)
    if issues:
        raise CapabilityError(_render_issues(issues))
    policy = sidecar["lifecycle_policy"]
    if policy["install"] or policy["update"] or policy["delete"]:
        raise CapabilityError("CAP_EXTERNAL_OWNERSHIP: external sidecars cannot authorize lifecycle writes")
    return sidecar


def _external_catalog_entry(sidecar_path: Path, sidecar: dict[str, Any], source_revision: str) -> dict[str, Any]:
    aliases = sidecar["user_aliases"]
    verification_status = "static-reviewed" if sidecar["verified_at"] and sidecar["evidence_refs"] else "pending"
    slug = re.sub(r"[^a-z0-9-]+", "-", sidecar["declared_name"].casefold()).strip("-") or "external-skill"
    return {
        "id": sidecar["capability_id"],
        "skill_id": slug,
        "name": sidecar["declared_name"],
        "declared_name": sidecar["declared_name"],
        "aliases": aliases,
        "capability_kind": "skill",
        "ownership": "external",
        "owner": "external-owner",
        "managed_by": "external-owner",
        "source": {
            "type": "bundled",
            "locator": sidecar["skill_path"],
            "revision": source_revision,
            "package_variant": "local",
            "source_relative_path": sidecar["skill_path"],
        },
        "content": {"source_sha256": sidecar["source_hash"], "tree_sha256": sidecar["source_hash"]},
        "descriptor": {"relative_path": str(sidecar_path), "sha256": sha256_file(sidecar_path)},
        "interface": {
            "inputs": ["task context"],
            "outputs": ["external capability result"],
            "required_permissions": ["tool-invocation"],
        },
        "package_variants": ["local"],
        "compatibility": {
            "platforms": ["windows"],
            "tools": sidecar["tool_scope"],
            "protocol_versions": ["external-sidecar-v1"],
            "constraints": ["external-owned source is protected"],
        },
        "adapters": [
            {"tool": tool, "projection": "none", "locator": sidecar["skill_path"]}
            for tool in sidecar["tool_scope"]
        ],
        "dependencies": [],
        "source_trust": "unverified",
        "review_status": verification_status,
        "execution_risk": sidecar["risk_class"],
        "risk_factors": ["external-runtime"],
        "exposure_policy": {
            "default": "advisory",
            "tools": {tool: ("advisory" if tool in sidecar["tool_scope"] else "hidden") for tool in TOOLS},
            "catalog_budget_class": "protected",
            "reason": "External-owned capability remains discover-and-route only.",
        },
        "routing": {
            "triggers": sidecar["capability_tags"],
            "task_types": sidecar["capability_tags"],
            "modes": ["review-only"],
            "conditions": ["External source remains installed and user-authorized."],
            "contraindications": ["No MALTS-managed install, update, projection, or delete."],
        },
        "lifecycle": {"state": "active", "legacy_aliases": aliases},
        "projection_plan": [
            {
                "tool": tool,
                "projection": "none",
                "target": None,
                "required": False,
                "projected_name": f"malts-{slug}",
                "package_variant": "local",
                "metadata_type": "skill-only",
            }
            for tool in sidecar["tool_scope"]
        ],
        "verification": [
            {
                "level": level,
                "status": "pass" if level == "static" and verification_status == "static-reviewed" else "pending",
                "tool": None,
                "evidence_ref": sidecar["evidence_refs"][0] if sidecar["evidence_refs"] else "external-sidecar:pending",
            }
            for level in ("static", "discovery", "invocation", "behavior")
        ],
        "last_verified": sidecar["verified_at"],
        "evidence_refs": sidecar["evidence_refs"],
        "rollback": {"strategy": "manual-review", "reference": f"sidecar:{sidecar['sidecar_id']}"},
    }


def generate_catalog(
    malts_root: Path,
    *,
    source_revision: str,
    package_variant: str,
    generated_at: str,
    external_sidecar_paths: Iterable[Path] = (),
) -> dict[str, Any]:
    malts_root = malts_root.resolve()
    if package_variant not in {"local", "public"}:
        raise CapabilityError(f"CAP_PACKAGE_VARIANT: unsupported package variant `{package_variant}`")
    descriptors = discover_capability_descriptors(malts_root)
    validate_descriptor_dependencies(malts_root, descriptors)
    entries = [
        _descriptor_catalog_entry(malts_root, path, descriptor, source_revision, package_variant)
        for path, descriptor in descriptors
        if package_variant in descriptor["package_variants"]
    ]
    for sidecar_path in external_sidecar_paths:
        sidecar = validate_external_sidecar(malts_root, sidecar_path)
        entries.append(_external_catalog_entry(sidecar_path, sidecar, source_revision))
    entries.sort(key=lambda entry: (entry["id"].casefold(), entry["id"]))
    catalog = {
        "schema_version": 1,
        "registry_version": "1",
        "design_status": "active",
        "registry_scope": "operator-state",
        "generated_at": generated_at,
        "entries": entries,
    }
    issues = validate_instance(malts_root, "capability-registry", catalog)
    if issues:
        raise CapabilityError(_render_issues(issues))
    return catalog


def _candidate_tokens(entry: dict[str, Any]) -> set[str]:
    tokens = {str(entry.get("name", "")).casefold(), str(entry.get("declared_name", "")).casefold()}
    tokens.update(str(value).casefold() for value in entry.get("aliases", []))
    tokens.update(str(value).casefold() for value in entry.get("lifecycle", {}).get("legacy_aliases", []))
    return {token for token in tokens if token}


def detect_inventory_collisions(catalog: dict[str, Any], inventory: list[dict[str, Any]]) -> dict[str, Any]:
    collisions: list[dict[str, Any]] = []
    migration_candidates: list[dict[str, Any]] = []
    unclassified = [
        {"reason": "unknown-tool", "inventory": item}
        for item in inventory
        if item.get("tool") not in TOOLS
    ]
    classified_inventory = [item for item in inventory if item.get("tool") in TOOLS]
    for entry in catalog.get("entries", []):
        if entry.get("ownership") != "malts":
            continue
        tokens = _candidate_tokens(entry)
        planned = {
            plan["tool"]: str(plan.get("target") or "").replace("\\", "/").casefold()
            for plan in entry.get("projection_plan", [])
        }
        for item in classified_inventory:
            tool = item.get("tool")
            item_path = str(item.get("path", "")).replace("\\", "/").casefold()
            item_tokens = {
                str(item.get("name", "")).casefold(),
                str(item.get("declared_name", "")).casefold(),
                *(str(value).casefold() for value in item.get("aliases", [])),
            }
            item_tokens.discard("")
            same_path = bool(planned.get(tool)) and item_path == planned[tool]
            token_overlap = sorted(tokens & item_tokens)
            managed_bridge = (
                item.get("ownership") == "malts"
                and item.get("managed_bridge") is True
                and item.get("capability_id") == entry["id"]
            )
            if managed_bridge and same_path:
                migration_candidates.append(
                    {"capability_id": entry["id"], "tool": tool, "path": item.get("path"), "reason": "managed-bridge"}
                )
                continue
            reasons: list[str] = []
            if same_path:
                reasons.append("path")
            if token_overlap:
                reasons.append("name-or-alias")
            if item.get("nested_suite") and token_overlap:
                reasons.append("nested-suite")
            if item.get("origin") == "plugin-cache" and token_overlap:
                reasons.append("plugin-cache")
            if reasons:
                collisions.append(
                    {
                        "capability_id": entry["id"],
                        "tool": tool,
                        "path": item.get("path"),
                        "reasons": sorted(set(reasons)),
                        "tokens": token_overlap,
                        "ownership": item.get("ownership", "unknown"),
                    }
                )
    return {
        "schema_version": 1,
        "collisions": sorted(collisions, key=lambda item: (item["capability_id"], item["tool"], str(item["path"]))),
        "migration_candidates": sorted(
            migration_candidates, key=lambda item: (item["capability_id"], item["tool"], str(item["path"]))
        ),
        "unclassified": unclassified,
    }


def resolve_capability(catalog: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    tool = request.get("tool")
    if tool not in TOOLS:
        raise CapabilityError(f"CAP_RESOLVER_TOOL: unsupported tool `{tool}`")
    task_intent = str(request.get("task_intent", "")).strip()
    task_type = str(request.get("task_type", "")).strip()
    if not task_intent or not task_type:
        raise CapabilityError("CAP_RESOLVER_INPUT: task_intent and task_type are required")
    mode = str(request.get("mode", "single-agent"))
    authorized_permissions = set(request.get("authorized_permissions", []))
    required_capabilities = set(request.get("required_capabilities", []))
    installed = set(request.get("installed_capability_ids", []))
    exposed = set(request.get("exposed_capability_ids", []))
    blocked = set(request.get("blocked_capability_ids", []))
    max_risk = request.get("max_risk", "medium")
    if max_risk not in RISK_ORDER:
        raise CapabilityError(f"CAP_RESOLVER_RISK: unsupported max_risk `{max_risk}`")
    user_override = request.get("user_override")
    intent_folded = task_intent.casefold()
    candidates: list[dict[str, Any]] = []
    catalog_ids = {entry.get("id") for entry in catalog.get("entries", [])}
    for entry in catalog.get("entries", []):
        capability_id = entry["id"]
        reasons: list[str] = []
        missing_dependencies: list[str] = []
        contraindications: list[str] = []
        score = 0
        compatibility = entry.get("compatibility", {})
        exposure = entry.get("exposure_policy", {}).get("tools", {}).get(tool, "hidden")
        if tool not in compatibility.get("tools", []):
            reasons.append("tool-unsupported")
        if exposure == "hidden":
            reasons.append("not-exposed")
        if capability_id in blocked:
            reasons.append("collision-blocked")
        if installed and capability_id not in installed:
            reasons.append("not-installed")
        if exposed and capability_id not in exposed:
            reasons.append("not-in-effective-catalog")
        permissions = set(entry.get("interface", {}).get("required_permissions", []))
        missing_permissions = sorted(permissions - authorized_permissions)
        if missing_permissions:
            reasons.append("authorization-required:" + ",".join(missing_permissions))
        risk = entry.get("execution_risk", "critical")
        if RISK_ORDER.get(risk, 99) > RISK_ORDER[max_risk]:
            reasons.append(f"risk-exceeds-policy:{risk}")
        for dependency in entry.get("dependencies", []):
            if dependency.get("required") and dependency.get("type") in {"skill", "agent"}:
                target = dependency.get("id")
                if target not in catalog_ids or (installed and target not in installed):
                    missing_dependencies.append(str(target))
        if missing_dependencies:
            reasons.append("missing-dependency")
        routing = entry.get("routing", {})
        if task_type in routing.get("task_types", []):
            score += 60
        for trigger in routing.get("triggers", []):
            if str(trigger).casefold() in intent_folded:
                score += 20
        if mode in routing.get("modes", []):
            score += 10
        if capability_id in required_capabilities:
            score += 40
        if user_override == capability_id:
            score += 100
        for contraindication in routing.get("contraindications", []):
            if str(contraindication).casefold() in intent_folded:
                contraindications.append(str(contraindication))
        if contraindications:
            reasons.append("contraindicated")
        if score == 0:
            reasons.append("task-mismatch")
        verification = "runtime-verified" if entry.get("review_status") == "runtime-verified" else "static-only"
        candidates.append(
            {
                "capability_id": capability_id,
                "score": score,
                "status": "rejected" if reasons else "eligible",
                "reasons": reasons or ["matched-within-authorized-scope"],
                "missing_dependencies": sorted(missing_dependencies),
                "contraindications": contraindications,
                "verification_freshness": verification,
                "projection_required": capability_id not in exposed if exposed else True,
            }
        )
    candidates.sort(key=lambda item: (-item["score"], item["capability_id"].casefold(), item["capability_id"]))
    eligible = [candidate for candidate in candidates if candidate["status"] == "eligible"]
    selected = eligible[0]["capability_id"] if eligible else None
    if user_override and selected != user_override:
        selected = None
    return {
        "schema_version": 1,
        "selected": selected,
        "no_skill_needed": selected is None,
        "candidates": candidates,
        "authorization_preserved": True,
        "execution_performed": False,
    }


def _write_generated(path: Path, value: Any, *, malts_root: Path | None = None) -> None:
    resolved = path.resolve()
    if malts_root is not None and _path_inside(resolved, malts_root):
        raise CapabilityError(f"CAP_PUBLIC_GENERATED_STATE: generated operator state cannot be written under {malts_root}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_bytes(canonical_json_bytes(value))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and resolve the MALTS Capability Catalog.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--malts-root", type=Path, required=True)
    generate.add_argument("--source-revision", required=True)
    generate.add_argument("--package-variant", choices=["local", "public"], required=True)
    generate.add_argument("--generated-at", required=True)
    generate.add_argument("--external-sidecar", type=Path, action="append", default=[])
    generate.add_argument("--out", type=Path, required=True)
    resolve = subparsers.add_parser("resolve")
    resolve.add_argument("--catalog", type=Path, required=True)
    resolve.add_argument("--request", type=Path, required=True)
    resolve.add_argument("--out", type=Path)
    collisions = subparsers.add_parser("check-collisions")
    collisions.add_argument("--catalog", type=Path, required=True)
    collisions.add_argument("--inventory", type=Path, required=True)
    collisions.add_argument("--out", type=Path)
    return parser


def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "generate":
            catalog = generate_catalog(
                args.malts_root,
                source_revision=args.source_revision,
                package_variant=args.package_variant,
                generated_at=args.generated_at,
                external_sidecar_paths=args.external_sidecar,
            )
            _write_generated(args.out, catalog, malts_root=args.malts_root)
            print(f"PASS: generated {len(catalog['entries'])} capability entries -> {args.out}")
            return 0
        if args.command == "resolve":
            result = resolve_capability(load_json(args.catalog), load_json(args.request))
        else:
            inventory = load_json(args.inventory)
            if not isinstance(inventory, list):
                raise CapabilityError("CAP_COLLISION_INPUT: inventory root must be an array")
            result = detect_inventory_collisions(load_json(args.catalog), inventory)
        if args.out:
            _write_generated(args.out, result)
        else:
            sys.stdout.buffer.write(canonical_json_bytes(result))
        return 0
    except (CapabilityError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
