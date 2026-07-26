#!/usr/bin/env python3
"""Generate deterministic tool-native MALTS Skill projections in isolation.

W3 intentionally refuses live tool targets. Production activation, fault
handling, and lifecycle cleanup remain W6 responsibilities.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from capability_router import (
    CapabilityError,
    TOOLS,
    canonical_json_bytes,
    load_json,
    parse_skill_front_matter,
    sha256_bytes,
    sha256_file,
)
from malts_user_contracts import validate_instance


BRIDGE_MARKER = "MALTS_SKILL_BRIDGE:"
FRONT_MATTER = re.compile(r"\A---\r?\n(?P<body>.*?)\r?\n---(?P<tail>\r?\n|\Z)", re.DOTALL)
NAME_LINE = re.compile(r"(?m)^name:\s*.*$")


class ProjectionError(ValueError):
    """Stable fail-closed native projection error."""


def _path_inside(path: Path, parent: Path) -> bool:
    path = path.resolve()
    parent = parent.resolve()
    return path == parent or parent in path.parents


def _safe_relative(value: str, label: str) -> Path:
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ProjectionError(f"PROJ_PATH: {label} must be a safe relative path: {value}")
    return path


def render_native_skill(source_path: Path, projected_name: str) -> bytes:
    data = source_path.read_bytes()
    text = data.decode("utf-8-sig").replace("\r\n", "\n")
    match = FRONT_MATTER.match(text)
    if not match or not NAME_LINE.search(match.group("body")):
        raise ProjectionError(f"PROJ_SOURCE_FRONTMATTER: invalid source Skill: {source_path}")
    body = NAME_LINE.sub(f"name: {projected_name}", match.group("body"), count=1)
    rendered = f"---\n{body}\n---\n{text[match.end():]}"
    if BRIDGE_MARKER in rendered:
        raise ProjectionError(f"PROJ_BRIDGE_MARKER: canonical source unexpectedly contains a bridge marker: {source_path}")
    return rendered.encode("utf-8")


def render_openai_metadata(display_name: str, short_description: str) -> bytes:
    value = (
        "interface:\n"
        f"  display_name: {json.dumps(display_name, ensure_ascii=False)}\n"
        f"  short_description: {json.dumps(short_description, ensure_ascii=False)}\n"
    )
    return value.encode("utf-8")


def _tree_hash_from_files(files: dict[str, bytes]) -> str:
    records = []
    for relative, data in files.items():
        records.append((relative.replace("\\", "/"), len(data), sha256_bytes(data)))
    records.sort(key=lambda item: (item[0].casefold(), item[0]))
    payload = "".join(f"{relative}\t{size}\t{digest}\n" for relative, size, digest in records).encode("utf-8")
    return sha256_bytes(payload)


def _source_tree_hash(entries: list[dict[str, Any]]) -> str:
    source_records = [
        {
            "capability_id": entry["id"],
            "source_relative_path": entry["source"]["source_relative_path"],
            "source_sha256": entry["content"]["source_sha256"],
            "tree_sha256": entry["content"]["tree_sha256"],
            "descriptor_sha256": entry["descriptor"]["sha256"],
        }
        for entry in entries
    ]
    return sha256_bytes(canonical_json_bytes(source_records))


def _projection_plan(entry: dict[str, Any], tool: str) -> dict[str, Any]:
    matches = [item for item in entry.get("projection_plan", []) if item.get("tool") == tool]
    if len(matches) != 1:
        raise ProjectionError(f"PROJ_TOOL_BINDING: {entry['id']} requires exactly one projection plan for {tool}")
    plan = matches[0]
    if plan.get("projection") != "native" or not plan.get("required"):
        raise ProjectionError(f"PROJ_TOOL_BINDING: {entry['id']} does not declare a required native projection for {tool}")
    return plan


def _classify_existing(
    skill_dir: Path,
    *,
    skill_id: str,
    projected_name: str,
    expected_files: dict[str, bytes],
) -> str:
    if not skill_dir.exists():
        return "absent"
    if not skill_dir.is_dir():
        raise ProjectionError(f"PROJ_TARGET_COLLISION: target is not a directory: {skill_dir}")
    skill_path = skill_dir / "SKILL.md"
    if not skill_path.is_file():
        raise ProjectionError(f"PROJ_TARGET_COLLISION: target directory lacks SKILL.md: {skill_dir}")
    data = skill_path.read_bytes()
    actual_files = {
        path.relative_to(skill_dir).as_posix(): path.read_bytes()
        for path in skill_dir.rglob("*")
        if path.is_file()
    }
    if actual_files == expected_files:
        return "native-identical"
    text = data.decode("utf-8-sig", errors="replace")
    if f"{BRIDGE_MARKER} {skill_id}" in text:
        try:
            front_matter = parse_skill_front_matter(skill_path, allow_bom=False)
        except CapabilityError as exc:
            raise ProjectionError(f"PROJ_UNOWNED_TARGET: invalid managed bridge candidate: {exc}") from exc
        if front_matter.get("name") == projected_name:
            extras = sorted(set(actual_files) - {"SKILL.md", "agents/openai.yaml"})
            if not extras:
                return "managed-bridge"
    raise ProjectionError(f"PROJ_UNOWNED_TARGET: refuse to replace unknown or modified target: {skill_dir}")


def build_projection_bundle(
    catalog: dict[str, Any],
    *,
    malts_root: Path,
    tool: str,
    target_root: Path,
    source_revision: str,
    package_variant: str,
    generated_at: str,
    target_tool_version: str,
    adapter_version: str,
    generation_id: str,
) -> dict[str, Any]:
    if tool not in TOOLS:
        raise ProjectionError(f"PROJ_TOOL_BINDING: unsupported tool `{tool}`")
    malts_root = malts_root.resolve()
    target_root = target_root.resolve()
    catalog_issues = validate_instance(malts_root, "capability-registry", catalog)
    if catalog_issues:
        raise ProjectionError("; ".join(issue.render() for issue in catalog_issues))
    files: dict[str, bytes] = {}
    manifest_entries: list[dict[str, Any]] = []
    migration_candidates: list[str] = []
    source_entries = [entry for entry in catalog.get("entries", []) if entry.get("ownership") == "malts"]
    source_entries.sort(key=lambda entry: (entry["id"].casefold(), entry["id"]))
    if not source_entries:
        raise ProjectionError("PROJ_EMPTY: Catalog contains no MALTS-owned capabilities")

    for entry in source_entries:
        source = entry["source"]
        if source.get("revision") != source_revision:
            raise ProjectionError(f"PROJ_SOURCE_BINDING: source revision mismatch for {entry['id']}")
        if source.get("package_variant") != package_variant or package_variant not in entry.get("package_variants", []):
            raise ProjectionError(f"PROJ_PACKAGE_VARIANT: package variant mismatch for {entry['id']}")
        plan = _projection_plan(entry, tool)
        if plan.get("package_variant") != package_variant:
            raise ProjectionError(f"PROJ_PACKAGE_VARIANT: projection plan variant mismatch for {entry['id']}")
        source_relative = _safe_relative(source["source_relative_path"], "source_relative_path")
        source_path = (malts_root / source_relative).resolve()
        if not _path_inside(source_path, malts_root) or not source_path.is_file():
            raise ProjectionError(f"PROJ_SOURCE_BINDING: source path is missing or outside MALTS_ROOT: {source_relative}")
        if sha256_file(source_path) != entry["content"]["source_sha256"].upper():
            raise ProjectionError(f"PROJ_SOURCE_BINDING: source hash mismatch for {entry['id']}")
        descriptor_relative = _safe_relative(entry["descriptor"]["relative_path"], "descriptor.relative_path")
        descriptor_path = (malts_root / descriptor_relative).resolve()
        if not descriptor_path.is_file() or sha256_file(descriptor_path) != entry["descriptor"]["sha256"].upper():
            raise ProjectionError(f"PROJ_SOURCE_BINDING: descriptor hash mismatch for {entry['id']}")
        required_dependencies: list[str] = []
        for dependency in entry.get("dependencies", []):
            relative = dependency.get("source_relative_path")
            if dependency.get("required") and relative:
                dependency_relative = _safe_relative(relative, "dependency.source_relative_path")
                if not (malts_root / dependency_relative).is_file():
                    raise ProjectionError(f"PROJ_DEPENDENCY_BINDING: missing dependency `{relative}` for {entry['id']}")
                required_dependencies.append(dependency_relative.as_posix())

        projected_name = plan["projected_name"]
        target_relative = _safe_relative(plan["target"], "projection target")
        expected_target = Path("skills") / projected_name / "SKILL.md"
        if target_relative.as_posix().casefold() != expected_target.as_posix().casefold():
            raise ProjectionError(f"PROJ_TOOL_BINDING: target/name mismatch for {entry['id']}")
        rendered_skill = render_native_skill(source_path, projected_name)
        files[target_relative.as_posix()] = rendered_skill
        if plan["metadata_type"] == "skill-with-openai-metadata":
            descriptor = load_json(descriptor_path)
            metadata_relative = (target_relative.parent / "agents" / "openai.yaml").as_posix()
            files[metadata_relative] = render_openai_metadata(descriptor["display_name"], descriptor["short_description"])
        elif plan["metadata_type"] != "skill-only":
            raise ProjectionError(f"PROJ_TOOL_BINDING: unknown metadata type for {entry['id']}")
        skill_files = {
            Path(relative).relative_to(target_relative.parent).as_posix(): data
            for relative, data in files.items()
            if target_relative.parent in Path(relative).parents
        }
        classification = _classify_existing(
            target_root / target_relative.parent,
            skill_id=entry["skill_id"],
            projected_name=projected_name,
            expected_files=skill_files,
        )
        if classification == "managed-bridge":
            migration_candidates.append(target_relative.parent.as_posix())
        manifest_entries.append(
            {
                "capability_id": entry["id"],
                "source_relative_path": source_relative.as_posix(),
                "source_sha256": entry["content"]["source_sha256"].upper(),
                "target": target_relative.as_posix(),
                "projection_type": "native",
                "generated_sha256": sha256_bytes(rendered_skill),
                "ownership": "malts",
                "created_by": "native_skill_projection.py",
                "required_dependencies": sorted(required_dependencies, key=str.casefold),
                "verification_refs": ["w3:static-projection"],
            }
        )

    manifest = {
        "schema_version": 1,
        "projection_schema_version": 1,
        "manifest_id": f"projection.{tool}.{generation_id}",
        "active_generation": generation_id,
        "tool": tool,
        "target_tool": tool,
        "target_tool_version": target_tool_version,
        "adapter_version": adapter_version,
        "source_revision": source_revision,
        "malts_version": (malts_root / "VERSION").read_text(encoding="utf-8-sig").strip(),
        "package_variant": package_variant,
        "source_tree_sha256": _source_tree_hash(source_entries),
        "projected_tree_sha256": _tree_hash_from_files(files),
        "generated_at": generated_at,
        "created_by": "native_skill_projection.py",
        "entries": manifest_entries,
    }
    issues = validate_instance(malts_root, "projection-manifest", manifest)
    if issues:
        raise ProjectionError("; ".join(issue.render() for issue in issues))
    return {
        "manifest": manifest,
        "files": files,
        "migration_candidates": sorted(migration_candidates, key=str.casefold),
        "target_root": str(target_root),
        "skill_bindings": {entry["skill_id"]: entry["id"] for entry in source_entries},
    }


def _write_file(root: Path, relative: str, data: bytes) -> None:
    target = (root / _safe_relative(relative, "generated file")).resolve()
    if not _path_inside(target, root):
        raise ProjectionError(f"PROJ_PATH: generated target escapes root: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def _verify_files(root: Path, files: dict[str, bytes]) -> None:
    for relative, expected in files.items():
        path = root / _safe_relative(relative, "verification file")
        if not path.is_file() or path.read_bytes() != expected:
            raise ProjectionError(f"PROJ_POSTVALIDATION: generated file mismatch: {path}")
        if path.name == "SKILL.md" and BRIDGE_MARKER in path.read_text(encoding="utf-8"):
            raise ProjectionError(f"PROJ_POSTVALIDATION: bridge marker remains: {path}")


def apply_projection_bundle(bundle: dict[str, Any], *, isolation_root: Path, target_root: Path) -> dict[str, Any]:
    isolation_root = isolation_root.resolve()
    target_root = target_root.resolve()
    if not _path_inside(target_root, isolation_root):
        raise ProjectionError(
            f"PROJ_ISOLATION_REQUIRED: target root `{target_root}` must stay inside isolation root `{isolation_root}`"
        )
    manifest = bundle["manifest"]
    if Path(bundle["target_root"]).resolve() != target_root:
        raise ProjectionError("PROJ_PLAN_TARGET: bundle target root differs from apply target root")
    stage_root = isolation_root / f".malts-w3-stage-{manifest['manifest_id']}"
    backup_root = isolation_root / f".malts-w3-backup-{manifest['manifest_id']}"
    if stage_root.exists() or backup_root.exists():
        raise ProjectionError("PROJ_ISOLATION_DIRTY: staging or backup path already exists")
    stage_root.mkdir(parents=True)
    activated: list[tuple[Path, Path | None]] = []
    try:
        for relative, data in bundle["files"].items():
            _write_file(stage_root, relative, data)
        _verify_files(stage_root, bundle["files"])
        skill_dirs = sorted({Path(relative).parent for relative in bundle["files"] if Path(relative).name == "SKILL.md"})
        for skill_relative in skill_dirs:
            staged_dir = stage_root / skill_relative
            final_dir = target_root / skill_relative
            entry = next(item for item in manifest["entries"] if Path(item["target"]).parent == skill_relative)
            projected_name = skill_relative.name
            skill_id = next(
                catalog_skill_id
                for catalog_skill_id, capability_id in bundle["skill_bindings"].items()
                if capability_id == entry["capability_id"]
            )
            expected_files = {
                Path(relative).relative_to(skill_relative).as_posix(): data
                for relative, data in bundle["files"].items()
                if skill_relative in Path(relative).parents
            }
            classification = _classify_existing(
                final_dir,
                skill_id=skill_id,
                projected_name=projected_name,
                expected_files=expected_files,
            )
            if classification == "native-identical":
                continue
            prior: Path | None = None
            if classification == "managed-bridge":
                prior = backup_root / skill_relative
                prior.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(final_dir), str(prior))
            final_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staged_dir), str(final_dir))
            activated.append((final_dir, prior))
        _verify_files(target_root, bundle["files"])
        manifest_path = isolation_root / "manifests" / f"{manifest['tool']}.projection_manifest.generated.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        if backup_root.exists():
            shutil.rmtree(backup_root)
        if stage_root.exists():
            shutil.rmtree(stage_root)
        return {
            "schema_version": 1,
            "status": "PASS",
            "tool": manifest["tool"],
            "projected_entries": len(manifest["entries"]),
            "migration_cleanup_count": len(bundle["migration_candidates"]),
            "legacy_bridge_markers": 0,
            "manifest_path": str(manifest_path),
        }
    except Exception:
        for final_dir, prior in reversed(activated):
            if final_dir.exists():
                shutil.rmtree(final_dir)
            if prior is not None and prior.exists():
                final_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(prior), str(final_dir))
        if stage_root.exists():
            shutil.rmtree(stage_root)
        if backup_root.exists():
            shutil.rmtree(backup_root)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan or apply an isolated MALTS native Skill projection.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "apply"):
        child = subparsers.add_parser(command)
        child.add_argument("--catalog", type=Path, required=True)
        child.add_argument("--malts-root", type=Path, required=True)
        child.add_argument("--tool", choices=list(TOOLS), required=True)
        child.add_argument("--target-root", type=Path, required=True)
        child.add_argument("--source-revision", required=True)
        child.add_argument("--package-variant", choices=["local", "public"], required=True)
        child.add_argument("--generated-at", required=True)
        child.add_argument("--tool-version", required=True)
        child.add_argument("--adapter-version", required=True)
        child.add_argument("--generation", required=True)
        child.add_argument("--manifest-out", type=Path)
        if command == "apply":
            child.add_argument("--isolation-root", type=Path, required=True)
    return parser


def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    try:
        catalog = load_json(args.catalog)
        bundle = build_projection_bundle(
            catalog,
            malts_root=args.malts_root,
            tool=args.tool,
            target_root=args.target_root,
            source_revision=args.source_revision,
            package_variant=args.package_variant,
            generated_at=args.generated_at,
            target_tool_version=args.tool_version,
            adapter_version=args.adapter_version,
            generation_id=args.generation,
        )
        if args.command == "apply":
            result = apply_projection_bundle(bundle, isolation_root=args.isolation_root, target_root=args.target_root)
            sys.stdout.buffer.write(canonical_json_bytes(result))
        else:
            sys.stdout.buffer.write(canonical_json_bytes(bundle["manifest"]))
        if args.manifest_out:
            out = args.manifest_out.resolve()
            if _path_inside(out, args.malts_root.resolve()):
                raise ProjectionError("PROJ_PUBLIC_STATE: generated ProjectionManifest cannot be written under MALTS_ROOT")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(canonical_json_bytes(bundle["manifest"]))
        return 0
    except (ProjectionError, CapabilityError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
