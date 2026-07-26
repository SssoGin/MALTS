#!/usr/bin/env python3
"""Transactional MALTS v1 lifecycle engine.

The engine consumes a verified closed release root, produces a hash-bound plan,
and applies install/update/repair/uninstall through a journaled state machine.
All mutation commands require an explicit apply flag at the CLI boundary.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from malts_user_contracts import canonical_plan_hash, validate_instance


MALTS_ROOT = Path(__file__).resolve().parents[1]
TOOLS = ("codex", "claude-code", "opencode")
PROJECTION_MANIFEST = ".malts-v1-projection.json"
LEGACY_PROJECTION_MANIFEST = ".malts-managed-files.json"
REGISTRY_RELATIVE = Path("registry") / "installation_registry.json"
POINTER_RELATIVE = Path("registry") / "active_generation.json"
LOCK_RELATIVE = Path("runtime") / "lifecycle.lock.json"
TRANSACTIONS_RELATIVE = Path("runtime") / "transactions"
AUDIT_RELATIVE = Path("state") / "audit"
LEGACY_RESIDUE_RELATIVE = Path("state") / "legacy_residue.json"
PLAN_ALGORITHM = "SHA256-UTF8-CANONICAL-JSON-v1-EXCLUDING-plan_hash"
ARTIFACT_ALGORITHM = "MALTS-IMMUTABLE-ARTIFACT-v1"
PLAN_ENVELOPE_VERSION = 1
HASH_PATTERN = re.compile(r"^[A-Fa-f0-9]{64}$")
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MANAGED_START = "<!-- MALTS:BEGIN managed instruction -->"
MANAGED_END = "<!-- MALTS:END managed instruction -->"
ACTIVE_GENERATION_TOKEN = "{{MALTS_ACTIVE_GENERATION_ROOT}}"
SECRET_PATTERN = re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S+")
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
STATES = ("DISCOVER", "LOCK", "PLAN", "STAGE", "SNAPSHOT", "PREVALIDATE", "ACTIVATE", "POSTVALIDATE", "CLEAN", "COMMIT")
INSTALLED_GENERATION_METADATA = (
    "artifact_identity.json",
    "generation_manifest.json",
    "release_identity.json",
)
RELEASE_ROOT_ENTRIES = {
    "lifecycle_artifact",
    "RELEASE_NOTES.md",
    "release_inventory.json",
    "release_manifest.json",
}


class LifecycleError(RuntimeError):
    def __init__(self, code: str, message: str, path: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"status": "FAIL", "error_code": self.code, "message": self.message}
        if self.path is not None:
            result["path"] = self.path
        return result


class InjectedCrash(LifecycleError):
    def __init__(self, state: str) -> None:
        super().__init__("TX_INJECTED_CRASH", f"Injected process-loss boundary at {state}.")
        self.state = state


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _now(value: str | None = None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LifecycleError("TX_TIMESTAMP_INVALID", "Timestamp must be ISO 8601 with timezone.") from exc
    if parsed.tzinfo is None:
        raise LifecycleError("TX_TIMESTAMP_INVALID", "Timestamp must include timezone.")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LifecycleError("TX_JSON_INVALID", f"Invalid UTF-8 JSON: {exc}", str(path)) from exc


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".malts-{uuid.uuid4().hex[:12]}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json_bytes(value))


def _absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _is_inside(root: Path, path: Path) -> bool:
    root_text = os.path.normcase(str(_absolute(root)))
    path_text = os.path.normcase(str(_absolute(path)))
    try:
        return os.path.commonpath((root_text, path_text)) == root_text
    except ValueError:
        return False


def _file_attributes(path: Path) -> int:
    try:
        return int(getattr(path.lstat(), "st_file_attributes", 0))
    except OSError:
        return 0


def _is_reparse(path: Path) -> bool:
    return path.is_symlink() or bool(_file_attributes(path) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _assert_no_reparse(root: Path, path: Path) -> None:
    root = _absolute(root)
    path = _absolute(path)
    if not _is_inside(root, path):
        raise LifecycleError("TX_PATH_ESCAPE", "Path escapes its managed root.", str(path))
    current = root
    try:
        parts = path.relative_to(root).parts
    except ValueError as exc:
        raise LifecycleError("TX_PATH_ESCAPE", "Path escapes its managed root.", str(path)) from exc
    for part in parts:
        current /= part
        if current.exists() and (current.is_symlink() or (_file_attributes(current) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))):
            raise LifecycleError("TX_REPARSE_POINT", "Reparse points are forbidden on managed lifecycle paths.", str(current))


def _validate_relative(value: str) -> str:
    path = Path(value.replace("/", os.sep))
    if not value or path.is_absolute() or ".." in path.parts or any(":" in part for part in path.parts):
        raise LifecycleError("TX_PATH_TRAVERSAL", "Artifact and projection paths must be safe relative paths.", value)
    if len(value) > 32760 or any(len(part) > 255 for part in path.parts):
        raise LifecycleError("TX_PATH_TOO_LONG", "Artifact and projection paths exceed the supported Windows path bounds.", value)
    for part in path.parts:
        stem = part.split(".", 1)[0].upper().rstrip(" .")
        if stem in RESERVED_NAMES or part.endswith((" ", ".")):
            raise LifecycleError("TX_RESERVED_PATH", "Windows reserved or trailing-dot/space path is forbidden.", value)
    return Path(*path.parts).as_posix()


def _safe_target(root: Path, relative: str) -> Path:
    normalized = _validate_relative(relative)
    target = _absolute(root / Path(normalized))
    _assert_no_reparse(root, target)
    return target


def _path_digest(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    if path.is_file():
        return file_sha256(path)
    if not path.is_dir():
        raise LifecycleError("TX_PATH_TYPE", "Unsupported managed path type.", str(path))
    records: list[dict[str, Any]] = []
    for item in sorted((entry for entry in path.rglob("*") if entry.is_file()), key=lambda entry: entry.relative_to(path).as_posix().casefold()):
        _assert_no_reparse(path, item)
        records.append({"path": item.relative_to(path).as_posix(), "bytes": item.stat().st_size, "sha256": file_sha256(item)})
    return sha256_bytes(canonical_json(records))


def _remove_managed(root: Path, path: Path) -> None:
    path = _absolute(path)
    _assert_no_reparse(root, path)
    if not path.exists():
        return
    if path.is_file():
        path.unlink()
        return
    for item in sorted(path.rglob("*"), key=lambda entry: len(entry.parts), reverse=True):
        _assert_no_reparse(root, item)
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            item.rmdir()
        else:
            raise LifecycleError("TX_PATH_TYPE", "Unsupported managed path type during cleanup.", str(item))
    path.rmdir()


def _copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        raise LifecycleError("TX_TARGET_EXISTS", "Copy target already exists.", str(target))
    target.mkdir(parents=True)
    for source_path in sorted(source.rglob("*"), key=lambda entry: entry.relative_to(source).as_posix().casefold()):
        relative = source_path.relative_to(source)
        target_path = target / relative
        if source_path.is_symlink() or (_file_attributes(source_path) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise LifecycleError("TX_REPARSE_POINT", "Artifact or managed source contains a reparse point.", str(source_path))
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
        elif source_path.is_file():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, target_path)
        else:
            raise LifecycleError("TX_PATH_TYPE", "Unsupported source path type.", str(source_path))


def _inventory_records(artifact_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for parent_name in ("payload", "projections"):
        parent = artifact_root / parent_name
        if not parent.is_dir():
            raise LifecycleError("ARTIFACT_LAYOUT", f"Artifact is missing {parent_name}/.", str(parent))
        for path in sorted((item for item in parent.rglob("*") if item.is_file()), key=lambda item: item.relative_to(artifact_root).as_posix().casefold()):
            if path.is_symlink() or (_file_attributes(path) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                raise LifecycleError("ARTIFACT_REPARSE", "Artifact cannot contain links or reparse points.", str(path))
            relative = _validate_relative(path.relative_to(artifact_root).as_posix())
            folded = relative.casefold()
            if folded in seen:
                raise LifecycleError("ARTIFACT_CASE_COLLISION", "Artifact paths collide under Windows case folding.", relative)
            seen.add(folded)
            records.append({"path": relative, "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    return records


def artifact_digest(version: str, inventory_sha256: str, tree_sha256: str) -> str:
    value = {"algorithm": ARTIFACT_ALGORITHM, "version": version, "package_inventory_sha256": inventory_sha256, "package_tree_sha256": tree_sha256}
    return sha256_bytes(canonical_json(value))


def _validate_contract(contract_id: str, value: dict[str, Any]) -> None:
    issues = validate_instance(MALTS_ROOT, contract_id, value)
    if issues:
        raise LifecycleError("TX_CONTRACT_INVALID", "; ".join(issue.render() for issue in issues), contract_id)


def verify_artifact(root_value: str | Path) -> dict[str, Any]:
    root = _absolute(root_value)
    if not root.is_dir():
        raise LifecycleError("ARTIFACT_MISSING", "Artifact root is missing.", str(root))
    if root.is_symlink() or (_file_attributes(root) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
        raise LifecycleError("ARTIFACT_REPARSE", "Artifact root cannot be a link or reparse point.", str(root))
    for item in root.rglob("*"):
        if item.is_symlink() or (_file_attributes(item) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise LifecycleError("ARTIFACT_REPARSE", "Artifact cannot contain links or reparse points.", str(item))
    allowed_root_entries = {"payload", "projections", "package_inventory.json", "generation_manifest.json"}
    actual_root_entries = {item.name for item in root.iterdir()}
    if actual_root_entries != allowed_root_entries:
        raise LifecycleError("ARTIFACT_LAYOUT", f"Unexpected artifact root entries: {sorted(actual_root_entries ^ allowed_root_entries)}", str(root))
    inventory_path = root / "package_inventory.json"
    manifest_path = root / "generation_manifest.json"
    inventory = load_json(inventory_path)
    manifest = load_json(manifest_path)
    if not isinstance(inventory, dict) or inventory.get("schema_version") != 1 or not isinstance(inventory.get("files"), list):
        raise LifecycleError("ARTIFACT_INVENTORY", "Package inventory has an invalid shape.", str(inventory_path))
    actual_records = _inventory_records(root)
    if inventory["files"] != actual_records:
        raise LifecycleError("ARTIFACT_CHECKSUM", "Package inventory does not match exact artifact files.", str(inventory_path))
    inventory_sha = file_sha256(inventory_path)
    tree_sha = sha256_bytes(canonical_json(actual_records))
    _validate_contract("generation-manifest", manifest)
    if manifest["package_inventory_sha256"].upper() != inventory_sha or manifest["package_tree_sha256"].upper() != tree_sha:
        raise LifecycleError("ARTIFACT_CHECKSUM", "Generation manifest hash fields do not match the artifact.", str(manifest_path))
    computed_artifact = artifact_digest(manifest["version"], inventory_sha, tree_sha)
    if manifest["artifact_sha256"].upper() != computed_artifact:
        raise LifecycleError("ARTIFACT_CHECKSUM", "Artifact digest does not match generation manifest.", str(manifest_path))
    if (root / "payload" / "VERSION").read_text(encoding="utf-8-sig").strip() != manifest["version"]:
        raise LifecycleError("ARTIFACT_VERSION", "payload/VERSION does not match generation manifest.")
    _verify_user_purity(manifest, _user_records(root / "payload"), str(manifest_path))

    projections: dict[str, dict[str, Any]] = {}
    inventory_paths = {record["path"] for record in actual_records}
    for tool in TOOLS:
        descriptor_path = root / "projections" / tool / "projection_files.json"
        descriptor = load_json(descriptor_path)
        if not isinstance(descriptor, dict) or descriptor.get("schema_version") != 1 or descriptor.get("tool") != tool:
            raise LifecycleError("ARTIFACT_PROJECTION", "Projection descriptor has invalid identity.", str(descriptor_path))
        entries = descriptor.get("entries")
        if not isinstance(entries, list) or not entries:
            raise LifecycleError("ARTIFACT_PROJECTION", "Projection descriptor must contain entries.", str(descriptor_path))
        targets: set[str] = set()
        for entry in entries:
            if set(entry) != {"path", "source", "mode", "sha256"} or entry["mode"] not in {"replace", "managed-block", "boot-pointer"}:
                raise LifecycleError("ARTIFACT_PROJECTION", "Projection entry has an invalid shape.", str(descriptor_path))
            target = _validate_relative(entry["path"])
            source = _validate_relative(entry["source"])
            if target.casefold() in targets:
                raise LifecycleError("ARTIFACT_PROJECTION", "Projection target collision.", target)
            targets.add(target.casefold())
            source_relative = f"projections/{tool}/{source}"
            if source_relative not in inventory_paths:
                raise LifecycleError("ARTIFACT_PROJECTION", "Projection source is not in package inventory.", source_relative)
            source_path = root / source_relative
            if file_sha256(source_path) != entry["sha256"].upper():
                raise LifecycleError("ARTIFACT_CHECKSUM", "Projection source hash mismatch.", source_relative)
            if entry["mode"] == "managed-block":
                text = source_path.read_text(encoding="utf-8-sig")
                if text.count(MANAGED_START) != 1 or text.count(MANAGED_END) != 1 or text.index(MANAGED_START) > text.index(MANAGED_END):
                    raise LifecycleError("ARTIFACT_MANAGED_BLOCK", "Managed instruction source requires one ordered marker pair.", source_relative)
            elif entry["mode"] == "boot-pointer":
                text = source_path.read_text(encoding="utf-8-sig")
                if target != "MALTS_BOOT.md" or text.count(ACTIVE_GENERATION_TOKEN) != 1:
                    raise LifecycleError("ARTIFACT_BOOT_POINTER", "Boot projection requires MALTS_BOOT.md and one active-generation token.", source_relative)
        projections[tool] = descriptor
    return {"root": root, "manifest": manifest, "inventory": inventory, "records": actual_records, "artifact_sha256": computed_artifact, "projections": projections}


def _release_inventory_records(root: Path) -> list[dict[str, Any]]:
    paths = [root / "RELEASE_NOTES.md"]
    paths.extend(
        sorted(
            (item for item in (root / "lifecycle_artifact").rglob("*") if item.is_file()),
            key=lambda item: item.relative_to(root).as_posix().casefold(),
        )
    )
    return [
        {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": file_sha256(path)}
        for path in paths
    ]


def _release_package_identity(manifest_path: Path, inventory_path: Path) -> str:
    value = {
        "algorithm": "MALTS-RELEASE-PACKAGE-v1",
        "release_manifest_sha256": file_sha256(manifest_path),
        "release_inventory_sha256": file_sha256(inventory_path),
    }
    return sha256_bytes(canonical_json(value))


def _user_records(root: Path, excluded: set[str] | None = None) -> list[dict[str, Any]]:
    excluded = excluded or set()
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix().casefold()):
        relative = _validate_relative(path.relative_to(root).as_posix())
        if relative in excluded:
            continue
        if _is_reparse(path):
            raise LifecycleError("TX_USER_REPARSE", "User payload cannot contain links or reparse points.", str(path))
        folded = relative.casefold()
        if folded in seen:
            raise LifecycleError("TX_USER_CASE_COLLISION", "User payload paths collide under Windows case folding.", relative)
        seen.add(folded)
        records.append({"path": relative, "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    return records


def _verify_user_purity(manifest: dict[str, Any], records: list[dict[str, Any]], context: str) -> None:
    purity = manifest["user_purity"]
    tree_sha256 = sha256_bytes(canonical_json(records))
    if purity["file_count"] != len(records) or purity["tree_sha256"].upper() != tree_sha256:
        raise LifecycleError(
            "TX_USER_PURITY_BINDING",
            "User-purity inventory does not bind the exact user payload.",
            context,
        )
    expected_revision = f"local-tree-sha256:{tree_sha256}"
    if manifest["source_revision"].casefold() != expected_revision.casefold():
        raise LifecycleError(
            "TX_USER_SOURCE_BINDING",
            "User-purity tree does not match generation source_revision.",
            context,
        )


def verify_release_package(root_value: str | Path) -> dict[str, Any]:
    root = _absolute(root_value)
    if not root.is_dir() or _is_reparse(root):
        raise LifecycleError("TX_RELEASE_PACKAGE_ROOT", "Release package root is missing or is a reparse point.", str(root))
    actual_entries = {item.name for item in root.iterdir()}
    if actual_entries != RELEASE_ROOT_ENTRIES:
        raise LifecycleError("TX_RELEASE_PACKAGE_LAYOUT", f"Unexpected release root entries: {sorted(actual_entries ^ RELEASE_ROOT_ENTRIES)}", str(root))
    for path in root.rglob("*"):
        if _is_reparse(path):
            raise LifecycleError("TX_RELEASE_REPARSE", "Release package cannot contain links or reparse points.", str(path))

    artifact = verify_artifact(root / "lifecycle_artifact")
    inventory_path = root / "release_inventory.json"
    manifest_path = root / "release_manifest.json"
    inventory = load_json(inventory_path)
    manifest = load_json(manifest_path)
    if not isinstance(inventory, dict) or inventory.get("schema_version") != 1 or not isinstance(inventory.get("files"), list):
        raise LifecycleError("TX_RELEASE_INVENTORY", "Release inventory has an invalid shape.", str(inventory_path))
    actual_records = _release_inventory_records(root)
    if inventory["files"] != actual_records:
        raise LifecycleError("TX_RELEASE_INVENTORY_MISMATCH", "Release inventory does not match exact package files.", str(inventory_path))
    _validate_contract("release-manifest", manifest)
    generation = artifact["manifest"]
    expected = {
        "artifact_sha256": artifact["artifact_sha256"],
        "generation_id": generation["generation_id"],
        "generation_manifest_sha256": file_sha256(root / "lifecycle_artifact" / "generation_manifest.json"),
        "package_inventory_sha256": generation["package_inventory_sha256"],
        "package_tree_sha256": generation["package_tree_sha256"],
        "release_inventory_sha256": file_sha256(inventory_path),
        "release_file_count": len(actual_records) + 2,
    }
    if manifest["artifact"] != {"root": "lifecycle_artifact", **expected}:
        raise LifecycleError("TX_RELEASE_ARTIFACT_BINDING", "ReleaseManifest does not bind the exact lifecycle artifact and release inventory.", str(manifest_path))
    if manifest["version"] != generation["version"] or manifest["source"]["revision"] != generation["source_revision"]:
        raise LifecycleError("TX_RELEASE_SOURCE_BINDING", "Release and generation manifests disagree on version or source revision.", str(manifest_path))
    if manifest["source"]["tree_sha256"].upper() != generation["source_revision"].rsplit(":", 1)[-1].upper():
        raise LifecycleError("TX_RELEASE_SOURCE_BINDING", "Release source tree does not match generation provenance.", str(manifest_path))
    if manifest["user_purity"] != generation["user_purity"]:
        raise LifecycleError("TX_RELEASE_USER_PURITY", "Release and generation manifests disagree on user-purity binding.", str(manifest_path))
    _verify_user_purity(generation, _user_records(root / "lifecycle_artifact" / "payload"), str(manifest_path))
    if file_sha256(root / manifest["release_notes"]["path"]) != manifest["release_notes"]["sha256"].upper():
        raise LifecycleError("TX_RELEASE_NOTES_BINDING", "Release notes hash does not match ReleaseManifest.", str(root / "RELEASE_NOTES.md"))
    return {
        "status": "PASS",
        "release_root": str(root),
        "release_id": manifest["release_id"],
        "version": manifest["version"],
        "release_state": manifest["release_state"],
        "artifact_sha256": artifact["artifact_sha256"],
        "generation_id": generation["generation_id"],
        "generation_manifest_sha256": file_sha256(root / "lifecycle_artifact" / "generation_manifest.json"),
        "release_manifest_sha256": file_sha256(manifest_path),
        "release_inventory_sha256": file_sha256(inventory_path),
        "release_package_sha256": _release_package_identity(manifest_path, inventory_path),
        "release_file_count": len(actual_records) + 2,
    }


def verify_installed_generation_envelope(root_value: str | Path) -> dict[str, Any]:
    root = _absolute(root_value)
    if not root.is_dir() or _is_reparse(root):
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_ROOT",
            "Installed generation root must be a real directory, not a link or reparse point.",
            str(root),
        )

    expected = set(INSTALLED_GENERATION_METADATA)
    present = {name for name in expected if (root / name).exists()}
    if present != expected or any(not (root / name).is_file() for name in present):
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_LAYOUT",
            f"Installed generation envelope must contain exactly three metadata files; missing or invalid: {sorted(expected - present)}.",
            str(root),
        )
    for name in INSTALLED_GENERATION_METADATA:
        path = root / name
        if _is_reparse(path):
            raise LifecycleError(
                "TX_INSTALLED_ENVELOPE_REPARSE",
                "Installed generation envelope metadata cannot be a link or reparse point.",
                str(path),
            )

    artifact_identity = load_json(root / "artifact_identity.json")
    generation_manifest = load_json(root / "generation_manifest.json")
    release_identity = load_json(root / "release_identity.json")

    try:
        _validate_contract("generation-manifest", generation_manifest)
    except LifecycleError as exc:
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_CONTRACT",
            exc.message,
            str(root / "generation_manifest.json"),
        ) from exc

    artifact_fields = {"artifact_sha256", "package_tree_sha256"}
    release_fields = {
        "release_root",
        "release_id",
        "release_manifest_sha256",
        "release_package_sha256",
        "artifact_sha256",
        "generation_id",
        "generation_manifest_sha256",
    }
    if not isinstance(artifact_identity, dict) or set(artifact_identity) != artifact_fields:
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_CONTRACT",
            "artifact_identity.json must use the exact installed-generation identity shape.",
            str(root / "artifact_identity.json"),
        )
    if not isinstance(release_identity, dict) or set(release_identity) != release_fields:
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_CONTRACT",
            "release_identity.json must use the exact installed-generation release identity shape.",
            str(root / "release_identity.json"),
        )

    hash_fields = (
        artifact_identity.get("artifact_sha256"),
        artifact_identity.get("package_tree_sha256"),
        release_identity.get("release_manifest_sha256"),
        release_identity.get("release_package_sha256"),
        release_identity.get("artifact_sha256"),
        release_identity.get("generation_manifest_sha256"),
    )
    if any(not isinstance(value, str) or not HASH_PATTERN.fullmatch(value) for value in hash_fields):
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_CONTRACT",
            "Installed generation identity hash fields must be SHA-256 values.",
            str(root),
        )
    release_root = release_identity.get("release_root")
    if not isinstance(release_root, str) or not Path(release_root).is_absolute():
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_CONTRACT",
            "Installed generation release_root must retain an absolute provenance locator.",
            str(root / "release_identity.json"),
        )

    version = generation_manifest["version"]
    generation_id = generation_manifest["generation_id"]
    source_revision = generation_manifest["source_revision"]
    if not re.fullmatch(r"local-tree-sha256:[A-Fa-f0-9]{64}", source_revision):
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_CONTRACT",
            "Installed generation source_revision must bind a local-tree SHA-256.",
            str(root / "generation_manifest.json"),
        )
    if root.name != generation_id:
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_BINDING",
            "Installed generation directory name does not match generation_id.",
            str(root),
        )
    version_path = root / "VERSION"
    if not version_path.is_file() or version_path.read_text(encoding="utf-8-sig").strip() != version:
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_BINDING",
            "Installed generation VERSION does not match generation_manifest.json.",
            str(version_path),
        )
    if release_identity.get("release_id") != f"MALTS-{version}" or release_identity.get("generation_id") != generation_id:
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_BINDING",
            "Release identity does not match the installed generation ID and version.",
            str(root / "release_identity.json"),
        )
    if (
        artifact_identity["artifact_sha256"].upper() != generation_manifest["artifact_sha256"].upper()
        or release_identity["artifact_sha256"].upper() != generation_manifest["artifact_sha256"].upper()
        or artifact_identity["package_tree_sha256"].upper() != generation_manifest["package_tree_sha256"].upper()
        or release_identity["generation_manifest_sha256"].upper()
        != file_sha256(root / "generation_manifest.json")
    ):
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_BINDING",
            "Installed generation envelope hashes do not bind the same artifact and generation manifest.",
            str(root),
        )

    _verify_user_purity(
        generation_manifest,
        _user_records(root, set(INSTALLED_GENERATION_METADATA)),
        str(root / "generation_manifest.json"),
    )

    return {
        "root": root,
        "artifact_identity": artifact_identity,
        "generation_manifest": generation_manifest,
        "release_identity": release_identity,
        "metadata_files": list(INSTALLED_GENERATION_METADATA),
    }


def verify_release_root(root_value: str | Path) -> dict[str, Any]:
    root = _absolute(root_value)
    verified = verify_release_package(root)
    artifact = verify_artifact(root / "lifecycle_artifact")
    manifest = load_json(root / "release_manifest.json")
    identity = {
        "release_root": str(root),
        "release_id": verified["release_id"],
        "release_manifest_sha256": verified["release_manifest_sha256"],
        "release_package_sha256": verified["release_package_sha256"],
        "artifact_sha256": verified["artifact_sha256"],
        "generation_id": verified["generation_id"],
        "generation_manifest_sha256": verified["generation_manifest_sha256"],
    }
    if set(manifest.get("supported_tools", [])) != set(TOOLS):
        raise LifecycleError("TX_RELEASE_TOOL_SUPPORT", "The release root must support Codex, Claude Code, and OpenCode.", str(root))
    return {"root": root, "manifest": manifest, "artifact": artifact, "identity": identity, "verified": verified}


def _registry_path(root: Path) -> Path:
    return root / REGISTRY_RELATIVE


def _pointer_path(root: Path) -> Path:
    return root / POINTER_RELATIVE


def _upgrade_legacy_registry(value: dict[str, Any], path: Path) -> dict[str, Any]:
    has_profile = "release_binding_profile" in value
    has_tools = "selected_tools" in value
    if has_profile != has_tools:
        raise LifecycleError("INST_REGISTRY_INVALID", "Installation registry has a partial release-binding extension.", str(path))
    if has_profile:
        return value
    required = {
        "schema_version", "install_id", "active_generation_id", "lifecycle_state", "generations",
        "persistent_state_roots", "user_data_roots", "updated_at",
    }
    if set(value) != required or value.get("schema_version") != 1 or not isinstance(value.get("generations"), list):
        raise LifecycleError("INST_REGISTRY_INVALID", "Legacy installation registry has an unsupported closed shape.", str(path))
    upgraded = copy.deepcopy(value)
    selected: list[str] = []
    for index, generation in enumerate(upgraded["generations"]):
        if not isinstance(generation, dict):
            raise LifecycleError("INST_REGISTRY_INVALID", f"Legacy generation record {index} is invalid.", str(path))
        for field in ("release_id", "release_manifest_sha256", "release_package_sha256", "generation_manifest_sha256"):
            generation[field] = None
        for ref in generation.get("projection_manifests", []):
            parts = str(ref).split(":", 2)
            if len(parts) == 3 and parts[0] == "projection" and parts[1] in TOOLS and parts[1] not in selected:
                selected.append(parts[1])
    upgraded["release_binding_profile"] = "legacy-inner-artifact"
    upgraded["selected_tools"] = [tool for tool in TOOLS if tool in selected] or list(TOOLS)
    return upgraded


def _load_registry(root: Path) -> dict[str, Any] | None:
    path = _registry_path(root)
    if not path.is_file():
        return None
    registry = load_json(path)
    if not isinstance(registry, dict):
        raise LifecycleError("INST_REGISTRY_INVALID", "Installation registry must be an object.", str(path))
    registry = _upgrade_legacy_registry(registry, path)
    _validate_contract("installation-registry", registry)
    return registry


def _registry_digest(root: Path) -> str:
    path = _registry_path(root)
    return file_sha256(path) if path.is_file() else "MISSING"


def _initial_registry(root: Path, now: str, selected_tools: Iterable[str]) -> dict[str, Any]:
    selected = [tool for tool in TOOLS if tool in set(selected_tools)]
    if not selected:
        raise LifecycleError("TX_SELECTED_TOOLS", "Initial registry requires at least one selected tool.")
    return {
        "schema_version": 1,
        "install_id": "MALTS-INSTALL-V1",
        "active_generation_id": None,
        "lifecycle_state": "uninstalled",
        "release_binding_profile": "release-package-v1",
        "selected_tools": selected,
        "generations": [],
        "persistent_state_roots": [str(_absolute(root / "state"))],
        "user_data_roots": [str(_absolute(root / "user-data"))],
        "updated_at": now,
    }


def _normalize_tool_roots(tool_roots: dict[str, str | Path]) -> dict[str, Path]:
    if not isinstance(tool_roots, dict):
        raise LifecycleError("TX_TOOL_ROOTS", "Tool roots must be a keyed mapping.")
    unknown = [tool for tool in tool_roots if tool not in TOOLS]
    if unknown:
        raise LifecycleError("TX_TOOL_ROOTS", "Tool root key is unsupported.", str(unknown[0]))
    selected = [tool for tool in TOOLS if tool in tool_roots]
    if not selected:
        raise LifecycleError("TX_TOOL_ROOTS", "At least one selected tool root is required.")
    normalized = {tool: _absolute(tool_roots[tool]) for tool in selected}
    paths = list(normalized.items())
    for index, (left_tool, left_root) in enumerate(paths):
        for right_tool, right_root in paths[index + 1:]:
            if _is_inside(left_root, right_root) or _is_inside(right_root, left_root):
                raise LifecycleError(
                    "TX_ROOT_OVERLAP",
                    f"Selected tool roots must be separate ({left_tool}, {right_tool}).",
                    str(right_root),
                )
    return normalized


def _load_residue_records(root: Path) -> list[dict[str, Any]]:
    path = root / LEGACY_RESIDUE_RELATIVE
    if not path.is_file():
        return []
    value = load_json(path)
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("records"), list):
        raise LifecycleError("RS_LEDGER_INVALID", "Legacy residue ledger has invalid shape.", str(path))
    records: list[dict[str, Any]] = []
    for record in value["records"]:
        if not isinstance(record, dict):
            raise LifecycleError("RS_LEDGER_INVALID", "Residue record must be an object.", str(path))
        _validate_contract("residue-tombstone", record)
        records.append(record)
    return records


def _projection_manifest(tool_root: Path) -> dict[str, Any] | None:
    path = tool_root / PROJECTION_MANIFEST
    if not path.is_file():
        return None
    value = load_json(path)
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("entries"), list):
        raise LifecycleError("PROJECTION_MANIFEST_INVALID", "Installed projection manifest is invalid.", str(path))
    return value


def _detected_hash(path: Path) -> str:
    return file_sha256(path) if path.is_file() else "MISSING"


def _managed_block_profile(path: Path) -> str:
    if not path.is_file():
        return "missing"
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return "invalid"
    starts = text.count(MANAGED_START)
    ends = text.count(MANAGED_END)
    if starts == 0 and ends == 0:
        return "user-only"
    if starts == 1 and ends == 1 and text.index(MANAGED_START) < text.index(MANAGED_END):
        return "managed"
    return "incomplete"


def _load_legacy_projection_manifest(root: Path) -> dict[str, Any] | None:
    path = root / LEGACY_PROJECTION_MANIFEST
    if not path.is_file():
        return None
    value = load_json(path)
    if not isinstance(value, dict) or value.get("SchemaVersion") != 1:
        raise LifecycleError("MG_LEGACY_MANIFEST_INVALID", "Legacy managed-file manifest has an unsupported schema.", str(path))
    source_version = value.get("SourceVersion")
    files = value.get("Files")
    if not isinstance(source_version, str) or not re.fullmatch(r"0\.1\.\d+", source_version) or not isinstance(files, list):
        raise LifecycleError("MG_LEGACY_MANIFEST_INVALID", "Legacy managed-file manifest has an invalid version or file list.", str(path))
    entries: dict[str, dict[str, Any]] = {}
    allowed_categories = {"Shared", "ToolInstruction", "ToolSupport", "ToolBridge", "ToolBoot"}
    for index, entry in enumerate(files):
        if not isinstance(entry, dict) or not isinstance(entry.get("Path"), str) or entry.get("Category") not in allowed_categories:
            raise LifecycleError("MG_LEGACY_MANIFEST_INVALID", f"Legacy managed-file entry {index} is invalid.", str(path))
        relative = _validate_relative(entry["Path"])
        key = relative.casefold()
        if key in entries:
            raise LifecycleError("MG_LEGACY_MANIFEST_INVALID", "Legacy managed-file paths collide under Windows case folding.", str(path))
        installed_sha = entry.get("InstalledSha256")
        if installed_sha is not None and (not isinstance(installed_sha, str) or not HASH_PATTERN.fullmatch(installed_sha)):
            raise LifecycleError("MG_LEGACY_MANIFEST_INVALID", f"Legacy managed-file entry {index} has an invalid hash.", str(path))
        entries[key] = {
            "path": relative,
            "category": entry["Category"],
            "installed_sha256": installed_sha.upper() if installed_sha else None,
        }
    return {
        "path": path,
        "sha256": file_sha256(path),
        "source_version": source_version,
        "entries": entries,
    }


def _boot_pointer_root(tool_root: Path) -> Path | None:
    path = tool_root / "MALTS_BOOT.md"
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise LifecycleError("MG_BOOT_POINTER_INVALID", "Selected-tool MALTS_BOOT.md is not valid UTF-8.", str(path)) from exc
    matches = re.findall(r"(?m)^MALTS_ROOT:\s*(.+?)\s*$", text)
    if not matches:
        return None
    if len(matches) != 1:
        raise LifecycleError("MG_BOOT_POINTER_INVALID", "Selected-tool MALTS_BOOT.md has an ambiguous MALTS_ROOT pointer.", str(path))
    return _absolute(matches[0])


def _legacy_root_specs(
    *,
    lifecycle_root: Path,
    tool_roots: dict[str, Path],
    release_root: Path | None,
    explicit_roots: Iterable[str | Path] | None,
    default_root: str | Path | None,
) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}

    def add(value: str | Path, source: str) -> None:
        path = _absolute(value)
        key = os.path.normcase(str(path))
        entry = candidates.setdefault(key, {"locator": str(path), "discovery_sources": []})
        if source not in entry["discovery_sources"]:
            entry["discovery_sources"].append(source)

    for value in explicit_roots or []:
        add(value, "explicit")
    for tool_root in tool_roots.values():
        pointed = _boot_pointer_root(tool_root)
        if pointed is not None:
            add(pointed, "selected-tool-boot")
    if default_root is not None:
        add(default_root, "default-user-profile")

    protected = [lifecycle_root, *tool_roots.values()]
    if release_root is not None:
        protected.append(release_root)
    selected: list[dict[str, Any]] = []
    for entry in candidates.values():
        path = Path(entry["locator"])
        overlaps = [root for root in protected if _is_inside(root, path) or _is_inside(path, root)]
        if overlaps:
            if entry["discovery_sources"] == ["selected-tool-boot"] and any(_is_inside(lifecycle_root, path) for _ in overlaps):
                continue
            raise LifecycleError("MG_LEGACY_ROOT_OVERLAP", "Legacy-root candidates must be separate from lifecycle, release, and selected-tool roots.", str(path))
        entry["discovery_sources"] = [
            source for source in ("explicit", "selected-tool-boot", "default-user-profile")
            if source in entry["discovery_sources"]
        ]
        selected.append(entry)
    selected.sort(key=lambda item: item["locator"].casefold())
    for index, left in enumerate(selected):
        for right in selected[index + 1:]:
            if _is_inside(Path(left["locator"]), Path(right["locator"])) or _is_inside(Path(right["locator"]), Path(left["locator"])):
                raise LifecycleError("MG_LEGACY_ROOT_OVERLAP", "Legacy-root candidates cannot overlap each other.", right["locator"])
    return selected


def _legacy_root_summary(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        field: observation[field]
        for field in (
            "locator", "discovery_sources", "manifest_sha256", "source_version", "classification",
            "planned_action", "managed_file_count", "exact_match_count", "missing_count", "drift_count", "extra_count",
        )
    }


def _observe_legacy_root(spec: dict[str, Any]) -> dict[str, Any]:
    root = Path(spec["locator"])
    base: dict[str, Any] = {
        "locator": str(root),
        "discovery_sources": list(spec["discovery_sources"]),
        "manifest_sha256": None,
        "source_version": None,
        "classification": "missing",
        "planned_action": "none",
        "managed_file_count": 0,
        "exact_match_count": 0,
        "missing_count": 0,
        "drift_count": 0,
        "extra_count": 0,
        "exact_paths": [],
        "missing_paths": [],
        "drift_paths": [],
        "extra_paths": [],
        "root_digest": "MISSING",
        "reason": None,
    }
    if not root.exists():
        return base
    if not root.is_dir() or _is_reparse(root):
        base.update({"classification": "untrusted", "planned_action": "manual-review", "root_digest": _path_digest(root), "reason": "candidate is not a real non-reparse directory"})
        return base
    try:
        manifest = _load_legacy_projection_manifest(root)
    except LifecycleError as exc:
        base.update({"classification": "untrusted", "planned_action": "manual-review", "root_digest": _path_digest(root), "reason": f"{exc.code}:{exc.message}"})
        return base
    if manifest is None:
        base.update({"classification": "untrusted", "planned_action": "manual-review", "root_digest": _path_digest(root), "reason": "trusted managed manifest is missing"})
        return base
    actual: dict[str, Path] = {}
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix().casefold()):
        _assert_no_reparse(root, path)
        relative = path.relative_to(root).as_posix()
        if relative.casefold() == LEGACY_PROJECTION_MANIFEST.casefold():
            continue
        actual[relative.casefold()] = path
    exact_paths: list[dict[str, str]] = []
    missing_paths: list[str] = []
    drift_paths: list[str] = []
    for folded, entry in manifest["entries"].items():
        path = actual.get(folded)
        installed = entry["installed_sha256"]
        if path is None:
            missing_paths.append(entry["path"])
        elif installed is not None and file_sha256(path) == installed:
            exact_paths.append({"path": entry["path"], "sha256": installed})
        else:
            drift_paths.append(entry["path"])
    extra_paths = sorted(
        (path.relative_to(root).as_posix() for folded, path in actual.items() if folded not in manifest["entries"]),
        key=str.casefold,
    )
    managed_count = len(manifest["entries"])
    exact_count = len(exact_paths)
    exact_root = exact_count == managed_count and not missing_paths and not drift_paths and not extra_paths
    base.update(
        {
            "manifest_sha256": manifest["sha256"],
            "source_version": manifest["source_version"],
            "classification": "exact-managed-root" if exact_root else "partial-managed-root",
            "planned_action": "delete-whole-root" if exact_root else "delete-exact-managed-paths",
            "managed_file_count": managed_count,
            "exact_match_count": exact_count,
            "missing_count": len(missing_paths),
            "drift_count": len(drift_paths),
            "extra_count": len(extra_paths),
            "exact_paths": exact_paths,
            "missing_paths": sorted(missing_paths, key=str.casefold),
            "drift_paths": sorted(drift_paths, key=str.casefold),
            "extra_paths": extra_paths,
            "root_digest": _path_digest(root),
        }
    )
    return base


def _observe_legacy_roots(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_observe_legacy_root(spec) for spec in specs]


def _legacy_root_residue_records(observations: list[dict[str, Any]], retire_version: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for observation in observations:
        root = Path(observation["locator"])
        digest = sha256_bytes(str(root).casefold().encode("utf-8"))[:12]
        coverage = {
            "managed_file_count": observation["managed_file_count"],
            "exact_match_count": observation["exact_match_count"],
            "missing_count": observation["missing_count"],
            "drift_count": observation["drift_count"],
            "extra_count": observation["extra_count"],
        }
        if observation["classification"] == "exact-managed-root":
            records.append(
                {
                    "schema_version": 1,
                    "residue_id": f"LEGACY-ROOT-{digest}",
                    "owner": "malts",
                    "kind": "generation",
                    "locator": str(root),
                    "source_generation": observation["source_version"],
                    "retire_version": retire_version,
                    "action": "delete",
                    "ownership_evidence_refs": [
                        f"legacy-managed-manifest:{observation['manifest_sha256']}",
                        f"sha256:{observation['root_digest']}",
                        "coverage:exact-all-zero-extra",
                    ],
                    "user_decision_ref": None,
                    "preserve_reason": None,
                    "evidence_refs": [*map(lambda source: f"legacy-discovery:{source}", observation["discovery_sources"])],
                    "cleanup_scope": "whole-root",
                    "manifest_sha256": observation["manifest_sha256"],
                    "coverage": coverage,
                }
            )
        elif observation["classification"] == "partial-managed-root":
            for item in observation["exact_paths"]:
                target = _safe_target(root, item["path"])
                records.append(
                    {
                        "schema_version": 1,
                        "residue_id": f"LEGACY-FILE-{digest}-{sha256_bytes(item['path'].casefold().encode('utf-8'))[:12]}",
                        "owner": "malts",
                        "kind": "other",
                        "locator": str(target),
                        "source_generation": observation["source_version"],
                        "retire_version": retire_version,
                        "action": "delete",
                        "ownership_evidence_refs": [
                            f"legacy-managed-manifest:{observation['manifest_sha256']}",
                            f"sha256:{item['sha256']}",
                        ],
                        "user_decision_ref": None,
                        "preserve_reason": None,
                        "evidence_refs": ["legacy-root:exact-managed-path"],
                        "cleanup_scope": "path",
                        "manifest_sha256": observation["manifest_sha256"],
                        "coverage": None,
                    }
                )
            manifest_path = root / LEGACY_PROJECTION_MANIFEST
            records.append(
                {
                    "schema_version": 1,
                    "residue_id": f"LEGACY-MANIFEST-{digest}",
                    "owner": "malts",
                    "kind": "manifest",
                    "locator": str(manifest_path),
                    "source_generation": observation["source_version"],
                    "retire_version": retire_version,
                    "action": "delete",
                    "ownership_evidence_refs": [
                        f"legacy-managed-manifest:{observation['manifest_sha256']}",
                        f"sha256:{observation['manifest_sha256']}",
                    ],
                    "user_decision_ref": None,
                    "preserve_reason": None,
                    "evidence_refs": ["legacy-root:retire-trusted-manifest"],
                    "cleanup_scope": "path",
                    "manifest_sha256": observation["manifest_sha256"],
                    "coverage": None,
                }
            )
    for record in records:
        _validate_contract("residue-tombstone", record)
    return records


def _validate_modification_policy(modification: dict[str, Any]) -> None:
    classification = modification["classification"]
    decision = modification["decision"]
    allowed = {
        "U0": {"replace"},
        "U1": {"merge"},
        "U2": {"merge"},
        "U3": {"ask", "preserve"},
        "U4": {"fail-closed"},
    }
    if decision not in allowed.get(classification, set()):
        raise LifecycleError(
            "TX_MODIFICATION_POLICY",
            f"Unsupported {classification}/{decision} modification decision.",
            modification.get("locator"),
        )
    if classification == "U3" and decision != "ask" and not any(
        ref.startswith("user-decision:") for ref in modification["evidence_refs"]
    ):
        raise LifecycleError(
            "TX_USER_DECISION_EVIDENCE",
            "Resolved U3 conflicts require an explicit user-decision evidence reference.",
            modification["locator"],
        )
    if classification == "U2" and not any(
        ref.startswith("merge-validation:") for ref in modification["evidence_refs"]
    ):
        raise LifecycleError(
            "TX_MERGE_EVIDENCE",
            "U2 automatic merge requires deterministic merge-validation evidence.",
            modification["locator"],
        )


def _apply_modification_override(
    target: Path,
    classification: str,
    decision: str,
    override: dict[str, Any] | None,
    evidence_refs: list[str],
) -> tuple[str, str, list[str]]:
    if override is None:
        result = {
            "locator": str(_absolute(target)),
            "classification": classification,
            "decision": decision,
            "evidence_refs": evidence_refs,
        }
        _validate_modification_policy(result)
        return classification, decision, []

    requested_class = override.get("classification")
    requested_decision = override.get("decision")
    extra_refs = override.get("evidence_refs")
    if requested_class not in {"U0", "U1", "U2", "U3", "U4"} or not isinstance(extra_refs, list):
        raise LifecycleError("TX_OVERRIDE_FORMAT", "Modification override has an invalid shape.", str(target))
    if classification == "U4" and (requested_class != "U4" or requested_decision != "fail-closed"):
        raise LifecycleError("TX_U4_OVERRIDE", "U4 safety conflicts cannot be downgraded by an override.", str(target))
    if classification == "U3" and requested_class != "U3":
        raise LifecycleError("TX_U3_OVERRIDE", "U3 conflicts require an explicit U3 decision, not reclassification.", str(target))
    if classification == "U1" and requested_class not in {"U1", "U2"}:
        raise LifecycleError("TX_OVERRIDE_CLASS", "A detected U1 target may only remain U1 or become evidence-backed U2.", str(target))
    if classification == "U0" and requested_class != "U0":
        raise LifecycleError("TX_OVERRIDE_CLASS", "A detected U0 target cannot be reclassified by an override.", str(target))
    result = {
        "locator": str(_absolute(target)),
        "classification": requested_class,
        "decision": requested_decision,
        "evidence_refs": [*evidence_refs, *extra_refs],
    }
    _validate_modification_policy(result)
    return requested_class, requested_decision, list(extra_refs)


def _legacy_residue_id(tool: str, relative: str, kind: str) -> str:
    digest = sha256_bytes(relative.casefold().encode("utf-8"))[:12]
    return f"LEGACY-{kind}-{tool.upper()}-{digest}"


def _closed_legacy_directories(
    tool_root: Path,
    desired_targets: list[Path],
    exact_candidates: list[dict[str, Any]],
) -> list[Path]:
    exact_paths = {os.path.normcase(str(_absolute(item["target"]))) for item in exact_candidates}
    candidates: set[Path] = set()
    for item in exact_candidates:
        parent = Path(item["target"]).parent
        while parent != tool_root and _is_inside(tool_root, parent):
            candidates.add(parent)
            parent = parent.parent

    eligible: list[Path] = []
    for directory in candidates:
        _assert_no_reparse(tool_root, directory)
        if any(_is_inside(directory, target) for target in desired_targets):
            continue
        files = [path for path in directory.rglob("*") if path.is_file()]
        if not files:
            continue
        if all(os.path.normcase(str(_absolute(path))) in exact_paths for path in files):
            eligible.append(directory)

    selected: list[Path] = []
    for directory in sorted(eligible, key=lambda path: (len(path.parts), str(path).casefold())):
        if not any(_is_inside(parent, directory) for parent in selected):
            selected.append(directory)
    return selected


def _legacy_projection_residue_record(
    *,
    residue_id: str,
    owner: str,
    locator: Path,
    source_generation: str,
    retire_version: str,
    action: str,
    ownership_evidence_refs: list[str],
    user_decision_ref: str | None,
    preserve_reason: str | None,
    evidence_refs: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "residue_id": residue_id,
        "owner": owner,
        "kind": "projection",
        "locator": str(_absolute(locator)),
        "source_generation": source_generation,
        "retire_version": retire_version,
        "action": action,
        "ownership_evidence_refs": list(dict.fromkeys(ownership_evidence_refs)),
        "user_decision_ref": user_decision_ref,
        "preserve_reason": preserve_reason,
        "evidence_refs": list(dict.fromkeys(evidence_refs)),
    }


def _classify_projection_modifications(
    artifact: dict[str, Any] | None,
    tool_roots: dict[str, Path],
    overrides: list[dict[str, Any]] | None,
    operation: str,
    target_version: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    override_map: dict[str, dict[str, Any]] = {}
    for item in overrides or []:
        if not isinstance(item, dict) or not isinstance(item.get("locator"), str):
            raise LifecycleError("TX_OVERRIDE_FORMAT", "Modification overrides require an absolute locator.")
        key = os.path.normcase(str(_absolute(item["locator"])))
        if key in override_map:
            raise LifecycleError("TX_OVERRIDE_DUPLICATE", "Modification override locator is duplicated.", item["locator"])
        override_map[key] = item
    modifications: list[dict[str, Any]] = []
    legacy_residue_records: list[dict[str, Any]] = []
    for tool in tool_roots:
        root = tool_roots[tool]
        installed = _projection_manifest(root)
        installed_map = {entry["path"].casefold(): entry for entry in installed.get("entries", [])} if installed else {}
        legacy = _load_legacy_projection_manifest(root)
        legacy_map = legacy["entries"] if legacy else {}
        desired = artifact["projections"][tool]["entries"] if artifact is not None and operation != "uninstall" else []
        desired_paths = {entry["path"].casefold() for entry in desired}
        for entry in desired:
            target = _safe_target(root, entry["path"])
            digest = _detected_hash(target)
            if entry["mode"] == "managed-block":
                profile = _managed_block_profile(target)
                if profile in {"missing", "user-only", "managed"}:
                    classification, decision = ("U0", "replace") if profile == "missing" else ("U1", "merge")
                else:
                    classification, decision = "U4", "fail-closed"
            elif not target.exists():
                classification, decision = "U0", "replace"
            else:
                previous = installed_map.get(entry["path"].casefold())
                legacy_previous = legacy_map.get(entry["path"].casefold())
                if previous and previous.get("installed_sha256") == digest:
                    classification, decision = "U0", "replace"
                elif legacy_previous and legacy_previous.get("installed_sha256") == digest:
                    classification, decision = "U0", "replace"
                elif SECRET_PATTERN.search(target.read_text(encoding="utf-8-sig", errors="ignore")) or re.search(r"(?i)(credential|secret|auth)", entry["path"]):
                    classification, decision = "U4", "fail-closed"
                else:
                    classification, decision = "U3", "ask"
            locator_key = os.path.normcase(str(_absolute(target)))
            override = override_map.pop(locator_key, None)
            base_refs = [f"detected-sha256:{digest}", f"projection:{tool}:{entry['path']}"]
            if legacy and entry["path"].casefold() in legacy_map:
                base_refs.append(f"legacy-managed-manifest:{legacy['sha256']}")
            classification, decision, extra_refs = _apply_modification_override(
                target, classification, decision, override, base_refs
            )
            modifications.append(
                {
                    "locator": str(_absolute(target)),
                    "classification": classification,
                    "decision": decision,
                    "evidence_refs": [*base_refs, *extra_refs],
                }
            )
        for folded, previous in installed_map.items():
            if folded in desired_paths:
                continue
            target = _safe_target(root, previous["path"])
            digest = _detected_hash(target)
            if previous.get("mode") == "managed-block":
                profile = _managed_block_profile(target)
                if profile == "missing":
                    classification, decision = "U0", "replace"
                elif profile == "managed":
                    classification, decision = "U1", "merge"
                else:
                    classification, decision = "U4", "fail-closed"
            else:
                classification = "U0" if digest in {"MISSING", previous.get("installed_sha256")} else "U3"
                decision = "replace" if classification == "U0" else "ask"
            locator_key = os.path.normcase(str(_absolute(target)))
            override = override_map.pop(locator_key, None)
            base_refs = [f"detected-sha256:{digest}", f"projection-stale:{tool}:{previous['path']}"]
            classification, decision, extra_refs = _apply_modification_override(
                target, classification, decision, override, base_refs
            )
            modifications.append(
                {
                    "locator": str(_absolute(target)),
                    "classification": classification,
                    "decision": decision,
                    "evidence_refs": [*base_refs, *extra_refs],
                }
            )
        legacy_only: list[dict[str, Any]] = []
        for folded, previous in legacy_map.items():
            if folded in desired_paths or folded in installed_map:
                continue
            target = _safe_target(root, previous["path"])
            digest = _detected_hash(target)
            installed_sha = previous["installed_sha256"]
            base_refs = [
                f"detected-sha256:{digest}",
                f"projection-legacy-only:{tool}:{previous['path']}",
                f"legacy-managed-manifest:{legacy['sha256']}",
            ]
            if installed_sha is None:
                if target.exists():
                    legacy_residue_records.append(
                        _legacy_projection_residue_record(
                            residue_id=_legacy_residue_id(tool, previous["path"], "USER"),
                            owner="user",
                            locator=target,
                            source_generation=legacy["source_version"],
                            retire_version=target_version,
                            action="preserve",
                            ownership_evidence_refs=[
                                f"legacy-managed-manifest:{legacy['sha256']}",
                                "legacy-null-installed-sha256",
                            ],
                            user_decision_ref=None,
                            preserve_reason="Legacy manifest has no installed hash; the path is user-managed and excluded from the v1 projection.",
                            evidence_refs=[f"lifecycle:legacy-null-hash-preserve:{tool}"],
                        )
                    )
                continue
            if target.exists() and not target.is_file():
                classification, decision = "U4", "fail-closed"
            elif digest in {"MISSING", installed_sha}:
                classification, decision = "U0", "replace"
            elif SECRET_PATTERN.search(target.read_text(encoding="utf-8-sig", errors="ignore")) or re.search(
                r"(?i)(credential|secret|auth)", previous["path"]
            ):
                classification, decision = "U4", "fail-closed"
            else:
                classification, decision = "U3", "ask"
            locator_key = os.path.normcase(str(_absolute(target)))
            override = override_map.pop(locator_key, None)
            classification, decision, extra_refs = _apply_modification_override(
                target, classification, decision, override, base_refs
            )
            observation = {
                "locator": str(_absolute(target)),
                "classification": classification,
                "decision": decision,
                "evidence_refs": [*base_refs, *extra_refs],
            }
            modifications.append(observation)
            legacy_only.append(
                {
                    "target": target,
                    "relative": previous["path"],
                    "installed_sha256": installed_sha,
                    "detected_sha256": digest,
                    "classification": classification,
                    "decision": decision,
                    "evidence_refs": observation["evidence_refs"],
                }
            )

        exact_candidates = [
            item for item in legacy_only
            if item["classification"] == "U0"
            and item["decision"] == "replace"
            and item["detected_sha256"] == item["installed_sha256"]
            and Path(item["target"]).is_file()
        ]
        desired_targets = [_safe_target(root, entry["path"]) for entry in desired]
        closed_directories = _closed_legacy_directories(root, desired_targets, exact_candidates)
        covered_paths: set[str] = set()
        for directory in closed_directories:
            covered = [item for item in exact_candidates if _is_inside(directory, Path(item["target"]))]
            covered_paths.update(os.path.normcase(str(_absolute(item["target"]))) for item in covered)
            relative = directory.relative_to(root).as_posix()
            legacy_residue_records.append(
                _legacy_projection_residue_record(
                    residue_id=_legacy_residue_id(tool, relative, "DIR"),
                    owner="malts",
                    locator=directory,
                    source_generation=legacy["source_version"],
                    retire_version=target_version,
                    action="delete",
                    ownership_evidence_refs=[
                        f"legacy-managed-manifest:{legacy['sha256']}",
                        f"sha256:{_path_digest(directory)}",
                        *(f"legacy-installed-sha256:{item['installed_sha256']}" for item in covered),
                    ],
                    user_decision_ref=None,
                    preserve_reason=None,
                    evidence_refs=[
                        f"lifecycle:legacy-only-closed-directory:{tool}",
                        *(f"legacy-path:{item['relative']}" for item in covered),
                    ],
                )
            )
        for item in legacy_only:
            target_key = os.path.normcase(str(_absolute(item["target"])))
            if target_key in covered_paths:
                continue
            if item["classification"] == "U0" and item["decision"] == "replace":
                owner, action = "malts", "delete"
                user_decision_ref = preserve_reason = None
            elif item["classification"] == "U3" and item["decision"] == "preserve":
                owner, action = "user", "preserve"
                user_decision_ref = next(
                    (ref for ref in item["evidence_refs"] if ref.startswith("user-decision:")),
                    None,
                )
                preserve_reason = "Explicit user decision preserves a drifted legacy-only path."
            else:
                owner, action = "unknown", "manual-review"
                user_decision_ref = None
                preserve_reason = "Legacy-only path differs from the installed hash or is safety-sensitive; execution fails closed."
            legacy_residue_records.append(
                _legacy_projection_residue_record(
                    residue_id=_legacy_residue_id(tool, item["relative"], "PATH"),
                    owner=owner,
                    locator=Path(item["target"]),
                    source_generation=legacy["source_version"],
                    retire_version=target_version,
                    action=action,
                    ownership_evidence_refs=[
                        f"legacy-managed-manifest:{legacy['sha256']}",
                        f"sha256:{item['installed_sha256']}",
                    ],
                    user_decision_ref=user_decision_ref,
                    preserve_reason=preserve_reason,
                    evidence_refs=[f"lifecycle:legacy-only-path:{tool}", *item["evidence_refs"]],
                )
            )
    if override_map:
        raise LifecycleError("TX_OVERRIDE_TARGET", "Modification override does not match a planned projection target.", next(iter(override_map)))
    for modification in modifications:
        _validate_modification_policy(modification)
    return modifications, legacy_residue_records


def _record_digest_reference(record: dict[str, Any], root: Path) -> dict[str, Any]:
    value = copy.deepcopy(record)
    locator = Path(value["locator"])
    if not locator.is_absolute():
        locator = _safe_target(root, value["locator"])
        value["locator"] = str(locator)
    digest_ref = f"sha256:{_path_digest(locator)}"
    if digest_ref not in value["ownership_evidence_refs"]:
        value["ownership_evidence_refs"].append(digest_ref)
    _validate_contract("residue-tombstone", value)
    return value


def _current_generation_records(root: Path, registry: dict[str, Any] | None, operation: str, target_generation_id: str | None) -> list[dict[str, Any]]:
    if registry is None:
        return []
    records: list[dict[str, Any]] = []
    for generation in registry["generations"]:
        if generation["generation_id"] == target_generation_id:
            continue
        path = Path(generation["root"])
        records.append(
            {
                "schema_version": 1,
                "residue_id": f"GEN-{generation['generation_id']}",
                "owner": "malts",
                "kind": "generation",
                "locator": str(path),
                "source_generation": generation["version"],
                "retire_version": "1.0.0",
                "action": "delete",
                "ownership_evidence_refs": [f"registry:{generation['generation_id']}", f"sha256:{_path_digest(path)}"],
                "user_decision_ref": None,
                "preserve_reason": None,
                "evidence_refs": ["lifecycle:planned-cleanup"],
            }
        )
    return records


def _operation_actions(context_hash: str, context: dict[str, Any], operation: str) -> list[dict[str, Any]]:
    targets = context["tool_roots"]
    actions = [
        {"action_id": "ACT-CONTEXT", "kind": "verify", "target": f"context-sha256:{context_hash}", "dependencies": [], "destructive": False},
        {"action_id": "ACT-STAGE", "kind": "copy" if operation != "uninstall" else "verify", "target": context["staging_root"], "dependencies": ["ACT-CONTEXT"], "destructive": False},
        {"action_id": "ACT-SNAPSHOT", "kind": "copy", "target": context["snapshot_root"], "dependencies": ["ACT-STAGE"], "destructive": False},
        {"action_id": "ACT-PREVALIDATE", "kind": "verify", "target": context["lifecycle_root"], "dependencies": ["ACT-SNAPSHOT"], "destructive": False},
        {"action_id": "ACT-ACTIVATE", "kind": "activate", "target": context.get("generation_root") or context["lifecycle_root"], "dependencies": ["ACT-PREVALIDATE"], "destructive": operation in {"update", "repair", "uninstall"}},
    ]
    previous = "ACT-ACTIVATE"
    for index, tool in enumerate(targets, start=1):
        action_id = f"ACT-PROJECT-{index}"
        actions.append({"action_id": action_id, "kind": "merge", "target": targets[tool], "dependencies": [previous], "destructive": operation == "uninstall"})
        previous = action_id
    actions.append({"action_id": "ACT-POSTVALIDATE", "kind": "verify", "target": context["lifecycle_root"], "dependencies": [previous], "destructive": False})
    for index, locator in enumerate(context["expected_cleanup"], start=1):
        actions.append({"action_id": f"ACT-CLEAN-{index}", "kind": "delete", "target": locator, "dependencies": ["ACT-POSTVALIDATE"], "destructive": True})
    dependencies = ["ACT-POSTVALIDATE", *(f"ACT-CLEAN-{index}" for index in range(1, len(context["expected_cleanup"]) + 1))]
    actions.append({"action_id": "ACT-ZERO-RESIDUE", "kind": "verify", "target": context["lifecycle_root"], "dependencies": dependencies, "destructive": False})
    return actions


def make_plan(
    *,
    operation: str,
    lifecycle_root: str | Path,
    tool_roots: dict[str, str | Path],
    release_root: str | Path | None = None,
    legacy_roots: Iterable[str | Path] | None = None,
    default_legacy_root: str | Path | None = None,
    operation_id: str | None = None,
    created_at: str | None = None,
    modification_overrides: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if operation not in {"install", "update", "repair", "uninstall"}:
        raise LifecycleError("TX_OPERATION", "Unsupported lifecycle operation.")
    now = _now(created_at)
    operation_id = operation_id or f"OP-{uuid.uuid4().hex[:12].upper()}"
    if not ID_PATTERN.fullmatch(operation_id):
        raise LifecycleError("TX_OPERATION_ID", "operation_id has an invalid format.")
    root = _absolute(lifecycle_root)
    normalized_tools = _normalize_tool_roots(tool_roots)
    for tool_root in normalized_tools.values():
        if _is_inside(root, tool_root) or _is_inside(tool_root, root):
            raise LifecycleError("TX_ROOT_OVERLAP", "Lifecycle and tool roots must be separate.", str(tool_root))

    if operation == "uninstall" and release_root is not None:
        raise LifecycleError("TX_RELEASE_ROOT", "Uninstall must not consume a release root.")
    if operation != "uninstall" and release_root is None:
        raise LifecycleError("TX_RELEASE_ROOT", "Install, update, and repair require a verified closed release root.")
    release = None if operation == "uninstall" else verify_release_root(release_root or "")
    artifact = release["artifact"] if release is not None else None
    registry = _load_registry(root)
    selected_tools = list(normalized_tools)
    if registry and registry["lifecycle_state"] != "uninstalled" and registry["selected_tools"] != selected_tools:
        raise LifecycleError(
            "TX_TOOL_SELECTION_CHANGE",
            "Update, repair, and uninstall must use the installed selected-tool set; change selection through a fresh install.",
        )

    if release is not None:
        release_identity = copy.deepcopy(release["identity"])
    else:
        active = next((item for item in registry["generations"] if item["state"] == "active"), None) if registry else None
        required_binding = (
            "release_id", "release_manifest_sha256", "release_package_sha256",
            "artifact_sha256", "generation_id", "generation_manifest_sha256",
        )
        if active is None or registry["release_binding_profile"] != "release-package-v1" or any(active.get(field) is None for field in required_binding):
            raise LifecycleError("TX_RELEASE_BINDING", "Uninstall requires an active generation with complete outer release provenance.")
        release_identity = {
            "release_root": None,
            "release_id": active["release_id"],
            "release_manifest_sha256": active["release_manifest_sha256"],
            "release_package_sha256": active["release_package_sha256"],
            "artifact_sha256": active["artifact_sha256"],
            "generation_id": active["generation_id"],
            "generation_manifest_sha256": active["generation_manifest_sha256"],
        }

    target_generation_id = artifact["manifest"]["generation_id"] if artifact is not None else None
    active_record = next((item for item in registry["generations"] if item["state"] == "active"), None) if registry else None
    target_version = artifact["manifest"]["version"] if artifact is not None else (active_record["version"] if active_record else None)
    transaction_root = root / TRANSACTIONS_RELATIVE / operation_id
    release_path = Path(release_identity["release_root"]) if release_identity["release_root"] is not None else None
    legacy_specs = _legacy_root_specs(
        lifecycle_root=root,
        tool_roots=normalized_tools,
        release_root=release_path,
        explicit_roots=legacy_roots,
        default_root=default_legacy_root,
    )
    legacy_observations = _observe_legacy_roots(legacy_specs)
    legacy_residue_records = _load_residue_records(root)
    legacy_projection_detected = any(
        _load_legacy_projection_manifest(tool_root) is not None
        for tool_root in normalized_tools.values()
    )
    if registry and registry["lifecycle_state"] != "uninstalled":
        detected_generation = "v1"
    elif legacy_residue_records or legacy_projection_detected or any(
        observation["classification"] != "missing" for observation in legacy_observations
    ):
        detected_generation = "legacy"
    else:
        detected_generation = "none"
    if operation == "install" and detected_generation == "v1":
        raise LifecycleError("TX_ALREADY_INSTALLED", "Use update or repair for an existing v1 installation.")
    if operation in {"update", "repair", "uninstall"} and detected_generation == "none":
        raise LifecycleError("TX_NOT_INSTALLED", f"Cannot {operation} an uninstalled target.")
    if operation == "repair" and detected_generation != "v1":
        raise LifecycleError("TX_REPAIR_GENERATION", "Repair requires an active v1 generation; use update for a legacy installation.")
    context: dict[str, Any] = {
        "schema_version": 1,
        "operation_id": operation_id,
        "operation": operation,
        "lifecycle_root": str(root),
        "release_root": release_identity["release_root"],
        "release_identity": release_identity,
        "artifact_sha256": release_identity["artifact_sha256"],
        "target_generation_id": target_generation_id,
        "target_version": target_version,
        "generation_root": str(root / "generations" / target_generation_id) if target_generation_id else None,
        "tool_roots": {tool: str(path) for tool, path in normalized_tools.items()},
        "selected_tools": selected_tools,
        "registry_sha256": _registry_digest(root),
        "legacy_root_specs": legacy_specs,
        "legacy_root_observations": legacy_observations,
        "transaction_root": str(transaction_root),
        "staging_root": str(transaction_root / "staging" / target_generation_id) if target_generation_id else str(transaction_root / "staging"),
        "snapshot_root": str(transaction_root / "snapshot"),
    }
    residue_records = [_record_digest_reference(record, root) for record in legacy_residue_records]
    legacy_ledger = root / LEGACY_RESIDUE_RELATIVE
    if legacy_ledger.is_file():
        residue_records.append(
            {
                "schema_version": 1,
                "residue_id": "LEGACY-RESIDUE-LEDGER",
                "owner": "malts",
                "kind": "manifest",
                "locator": str(legacy_ledger),
                "source_generation": "legacy",
                "retire_version": target_version or "1.0.0",
                "action": "delete",
                "ownership_evidence_refs": ["state:legacy-residue-ledger", f"sha256:{_path_digest(legacy_ledger)}"],
                "user_decision_ref": None,
                "preserve_reason": None,
                "evidence_refs": ["lifecycle:planned-cleanup"],
            }
        )
    residue_records.extend(_current_generation_records(root, registry, operation, target_generation_id))
    residue_records.extend(_legacy_root_residue_records(legacy_observations, target_version or "1.0.0"))
    for tool, tool_root in normalized_tools.items():
        legacy_manifest = _load_legacy_projection_manifest(tool_root)
        if legacy_manifest is None:
            continue
        residue_records.append(
            {
                "schema_version": 1,
                "residue_id": f"LEGACY-MANIFEST-{tool.upper()}",
                "owner": "malts",
                "kind": "manifest",
                "locator": str(legacy_manifest["path"]),
                "source_generation": legacy_manifest["source_version"],
                "retire_version": target_version or "1.0.0",
                "action": "delete",
                "ownership_evidence_refs": [
                    f"legacy-managed-manifest:{legacy_manifest['sha256']}",
                    f"sha256:{legacy_manifest['sha256']}",
                ],
                "user_decision_ref": None,
                "preserve_reason": None,
                "evidence_refs": [f"lifecycle:legacy-manifest-import:{tool}"],
            }
        )
    modifications, legacy_projection_records = _classify_projection_modifications(
        artifact,
        normalized_tools,
        modification_overrides,
        operation,
        target_version or "1.0.0",
    )
    residue_records.extend(_record_digest_reference(record, root) for record in legacy_projection_records)
    for record in residue_records:
        _validate_contract("residue-tombstone", record)
    expected_cleanup = sorted({record["locator"] for record in residue_records if record["action"] == "delete"}, key=str.casefold)
    context["residue_records"] = residue_records
    context["expected_cleanup"] = expected_cleanup
    context["modification_observations"] = modifications
    context_hash = sha256_bytes(canonical_json(context))
    actions = _operation_actions(context_hash, context, operation)
    plan_contract = {
        "schema_version": 1,
        "operation_id": operation_id,
        "operation": operation,
        "source_artifact_sha256": release_identity["artifact_sha256"],
        "release_identity": release_identity,
        "detected_generation": detected_generation,
        "tool_targets": selected_tools,
        "legacy_roots": [_legacy_root_summary(observation) for observation in legacy_observations],
        "actions": actions,
        "user_modifications": modifications,
        "expected_cleanup": expected_cleanup,
        "acceptance_matrix": [
            {"criterion_id": "AC-RELEASE", "hard": True, "verification": "closed release, outer manifest, logical package, inner artifact, and generation-manifest identity", "expected_result": "PASS"},
            {"criterion_id": "AC-PROJECTION", "hard": True, "verification": "selected one-to-three-tool managed projection verification", "expected_result": "PASS"},
            {"criterion_id": "AC-RECOVERY", "hard": True, "verification": "transaction recovery and detected legacy-root ownership", "expected_result": "PASS"},
            {"criterion_id": "AC-RESIDUE", "hard": True, "verification": "manifest-proven legacy-root cleanup with drift and unknown ownership preserved", "expected_result": "PASS"},
        ],
        "plan_hash_algorithm": PLAN_ALGORITHM,
        "plan_hash": "0" * 64,
        "created_at": now,
    }
    plan_contract["plan_hash"] = canonical_plan_hash(plan_contract)
    _validate_contract("update-plan", plan_contract)
    return {
        "schema_version": PLAN_ENVELOPE_VERSION,
        "plan_contract": plan_contract,
        "execution_context": context,
        "context_sha256": context_hash,
    }


def validate_plan_envelope(envelope: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(envelope, dict) or set(envelope) != {"schema_version", "plan_contract", "execution_context", "context_sha256"}:
        raise LifecycleError("TX_PLAN_ENVELOPE", "Lifecycle plan envelope has an invalid closed shape.")
    if envelope["schema_version"] != PLAN_ENVELOPE_VERSION:
        raise LifecycleError("TX_PLAN_ENVELOPE", "Unsupported lifecycle plan envelope version.")
    plan = envelope["plan_contract"]
    context = envelope["execution_context"]
    if not isinstance(plan, dict) or not isinstance(context, dict):
        raise LifecycleError("TX_PLAN_ENVELOPE", "Plan contract and execution context must be objects.")
    _validate_contract("update-plan", plan)
    context_hash = sha256_bytes(canonical_json(context))
    if context_hash != envelope["context_sha256"]:
        raise LifecycleError("TX_CONTEXT_HASH", "Execution context hash drifted.")
    target = f"context-sha256:{context_hash}"
    if not any(action["kind"] == "verify" and action["target"] == target for action in plan["actions"]):
        raise LifecycleError("TX_CONTEXT_BINDING", "UpdatePlan does not bind the execution context hash.")
    if plan["operation_id"] != context["operation_id"] or plan["operation"] != context["operation"]:
        raise LifecycleError("TX_CONTEXT_BINDING", "Plan/context operation identity mismatch.")
    if plan["source_artifact_sha256"] != context["artifact_sha256"]:
        raise LifecycleError("TX_CONTEXT_BINDING", "Plan/context artifact mismatch.")
    if canonical_json(plan["release_identity"]) != canonical_json(context["release_identity"]):
        raise LifecycleError("TX_CONTEXT_BINDING", "Plan/context outer release identity mismatch.")
    if plan["tool_targets"] != context["selected_tools"] or list(context["tool_roots"]) != context["selected_tools"]:
        raise LifecycleError("TX_CONTEXT_BINDING", "Plan/context selected-tool set mismatch.")
    expected_legacy = [_legacy_root_summary(observation) for observation in context["legacy_root_observations"]]
    if canonical_json(plan["legacy_roots"]) != canonical_json(expected_legacy):
        raise LifecycleError("TX_CONTEXT_BINDING", "Plan/context legacy-root observation mismatch.")
    if sorted(plan["expected_cleanup"], key=str.casefold) != sorted(context["expected_cleanup"], key=str.casefold):
        raise LifecycleError("TX_CONTEXT_BINDING", "Plan/context cleanup mismatch.")
    return plan, context


def _modification_digest_ref(modification: dict[str, Any]) -> str:
    refs = [ref for ref in modification["evidence_refs"] if ref.startswith("detected-sha256:")]
    if len(refs) != 1:
        raise LifecycleError("TX_MODIFICATION_EVIDENCE", "Modification requires one detected hash reference.", modification["locator"])
    return refs[0].split(":", 1)[1]


def _verify_plan_inputs(plan: dict[str, Any], context: dict[str, Any], expected_plan_hash: str) -> dict[str, Any] | None:
    if plan["plan_hash"] != expected_plan_hash.upper():
        raise LifecycleError("TX_EXPECTED_PLAN_HASH", "Explicit expected plan hash does not match the plan.")
    root = _absolute(context["lifecycle_root"])
    if _registry_digest(root) != context["registry_sha256"]:
        raise LifecycleError("TX_INPUT_DRIFT", "Installation registry changed after planning.", str(_registry_path(root)))
    artifact = None
    if context["release_root"] is not None:
        release = verify_release_root(context["release_root"])
        if canonical_json(release["identity"]) != canonical_json(context["release_identity"]):
            raise LifecycleError("TX_INPUT_DRIFT", "Closed release identity changed after planning.", context["release_root"])
        artifact = release["artifact"]
    else:
        registry = _load_registry(root)
        active = next((item for item in registry["generations"] if item["state"] == "active"), None) if registry else None
        current_identity = None if active is None else {
            "release_root": None,
            "release_id": active["release_id"],
            "release_manifest_sha256": active["release_manifest_sha256"],
            "release_package_sha256": active["release_package_sha256"],
            "artifact_sha256": active["artifact_sha256"],
            "generation_id": active["generation_id"],
            "generation_manifest_sha256": active["generation_manifest_sha256"],
        }
        if current_identity is None or canonical_json(current_identity) != canonical_json(context["release_identity"]):
            raise LifecycleError("TX_INPUT_DRIFT", "Installed outer release identity changed after uninstall planning.")
    current_legacy = _observe_legacy_roots(context["legacy_root_specs"])
    if canonical_json(current_legacy) != canonical_json(context["legacy_root_observations"]):
        raise LifecycleError("TX_INPUT_DRIFT", "Legacy-root ownership or content changed after planning.")
    ambiguous = [item["locator"] for item in current_legacy if item["classification"] == "untrusted"]
    if ambiguous:
        raise LifecycleError("TX_LEGACY_ROOT_UNTRUSTED", "A discovered legacy root has ambiguous ownership and requires manual resolution.", ambiguous[0])
    for modification in plan["user_modifications"]:
        path = Path(modification["locator"])
        if _detected_hash(path) != _modification_digest_ref(modification):
            raise LifecycleError("TX_INPUT_DRIFT", "Projection target changed after planning.", str(path))
        if modification["classification"] == "U3" and modification["decision"] == "ask":
            raise LifecycleError("TX_USER_DECISION_REQUIRED", "U3 conflict requires explicit preservation or external resolution followed by replanning.", str(path))
        if modification["classification"] == "U3" and modification["decision"] == "preserve" and any(
            ref.startswith("projection:") for ref in modification["evidence_refs"]
        ):
            raise LifecycleError(
                "TX_USER_DECISION_REQUIRED",
                "A required projection collision must be resolved outside the target path and replanned; preserve cannot satisfy the projection.",
                str(path),
            )
        if modification["classification"] == "U4":
            raise LifecycleError("TX_U4_BLOCKED", "U4 safety-critical modification fails closed.", str(path))
    return artifact


def _lock_path(root: Path) -> Path:
    return root / LOCK_RELATIVE


def _transaction_root(context: dict[str, Any]) -> Path:
    return Path(context["transaction_root"])


def _acquire_lock(root: Path, operation_id: str, now: str, *, ttl_minutes: int = 30) -> dict[str, Any]:
    path = _lock_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    stale_replaced = False
    if path.exists():
        existing = load_json(path)
        expires = datetime.fromisoformat(existing["expires_at"].replace("Z", "+00:00"))
        if expires > datetime.now(timezone.utc):
            raise LifecycleError("TX_LOCK_ACTIVE", "Another lifecycle operation holds the lock.", str(path))
        if existing.get("operation_id") and (_transaction_root({"transaction_root": str(root / TRANSACTIONS_RELATIVE / existing["operation_id"])})).exists():
            raise LifecycleError("TX_STALE_LOCK_RECOVERY", "Expired lock has transaction state; recover it before starting another operation.", str(path))
        path.unlink()
        stale_replaced = True
    created = datetime.fromisoformat(now.replace("Z", "+00:00"))
    lock = {
        "schema_version": 1,
        "operation_id": operation_id,
        "pid": os.getpid(),
        "created_at": now,
        "expires_at": (created + timedelta(minutes=ttl_minutes)).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(lock, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except FileExistsError as exc:
        raise LifecycleError("TX_LOCK_ACTIVE", "Lifecycle lock acquisition raced with another operation.", str(path)) from exc
    return {"lock": lock, "stale_replaced": stale_replaced}


def _release_lock(root: Path, operation_id: str) -> None:
    path = _lock_path(root)
    if not path.exists():
        return
    value = load_json(path)
    if value.get("operation_id") != operation_id:
        raise LifecycleError("TX_LOCK_OWNER", "Refusing to release another operation's lock.", str(path))
    path.unlink()


def _journal_path(transaction_root: Path) -> Path:
    return transaction_root / "transaction_journal.json"


def _plan_path(transaction_root: Path) -> Path:
    return transaction_root / "update_plan.json"


def _new_journal(plan: dict[str, Any], now: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "journal_id": f"J-{plan['operation_id']}",
        "operation_id": plan["operation_id"],
        "plan_hash": plan["plan_hash"],
        "state": "DISCOVER",
        "state_history": [{"state": "DISCOVER", "at": now, "evidence_refs": ["lifecycle:discover"]}],
        "last_completed_action": None,
        "recovery_actions": [],
        "updated_at": now,
    }


def _set_state(transaction_root: Path, journal: dict[str, Any], state: str, *, evidence: str, fault_at: str | None = None) -> None:
    now = _now()
    if journal["state"] != state:
        journal["state"] = state
        journal["state_history"].append({"state": state, "at": now, "evidence_refs": [evidence]})
    journal["last_completed_action"] = f"STATE-{state}"
    journal["updated_at"] = now
    _validate_contract("transaction-journal", journal)
    write_json(_journal_path(transaction_root), journal)
    if fault_at == state:
        raise InjectedCrash(state)


def _snapshot(
    root: Path,
    tool_roots: dict[str, Path],
    transaction_root: Path,
    modifications: list[dict[str, Any]],
    residue_records: list[dict[str, Any]],
    legacy_root_observations: list[dict[str, Any]],
) -> None:
    snapshot = transaction_root / "snapshot"
    snapshot.mkdir(parents=True, exist_ok=False)
    meta: dict[str, Any] = {
        "registry_exists": _registry_path(root).is_file(),
        "pointer_exists": _pointer_path(root).is_file(),
        "tools": {},
        "external_residue": [],
    }
    if meta["registry_exists"]:
        shutil.copyfile(_registry_path(root), snapshot / "registry.json")
    if meta["pointer_exists"]:
        shutil.copyfile(_pointer_path(root), snapshot / "pointer.json")
    generations = root / "generations"
    if generations.is_dir():
        _copy_tree(generations, snapshot / "generations")
    for tool, tool_root in tool_roots.items():
        manifest = _projection_manifest(tool_root)
        tool_snapshot = snapshot / "tools" / tool
        tool_meta = {"manifest_exists": manifest is not None, "entries": []}
        captured: set[str] = set()
        if manifest is not None:
            tool_snapshot.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(tool_root / PROJECTION_MANIFEST, tool_snapshot / "manifest.json")
            for entry in manifest["entries"]:
                source = _safe_target(tool_root, entry["path"])
                record = {"path": entry["path"], "exists": source.is_file()}
                tool_meta["entries"].append(record)
                captured.add(entry["path"].casefold())
                if source.is_file():
                    destination = tool_snapshot / "files" / Path(entry["path"])
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
        for modification in modifications:
            locator = Path(modification["locator"])
            if not _is_inside(tool_root, locator):
                continue
            relative = locator.relative_to(tool_root).as_posix()
            if relative.casefold() in captured:
                continue
            source = _safe_target(tool_root, relative)
            record = {"path": relative, "exists": source.is_file()}
            tool_meta["entries"].append(record)
            captured.add(relative.casefold())
            if source.is_file():
                tool_snapshot.mkdir(parents=True, exist_ok=True)
                destination = tool_snapshot / "files" / Path(relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
        meta["tools"][tool] = tool_meta
    internal_roots = [root, *tool_roots.values()]
    legacy_roots = [
        Path(observation["locator"])
        for observation in legacy_root_observations
        if observation["classification"] in {"exact-managed-root", "partial-managed-root"}
    ]
    for index, record in enumerate(residue_records, start=1):
        if record["action"] != "delete":
            continue
        locator = Path(record["locator"])
        if any(_is_inside(managed_root, locator) for managed_root in internal_roots):
            continue
        matching_root = next((candidate for candidate in legacy_roots if _is_inside(candidate, locator)), None)
        if matching_root is None:
            raise LifecycleError("TX_SNAPSHOT_BOUNDARY", "External cleanup target lacks a trusted legacy root.", str(locator))
        item = {
            "locator": str(locator),
            "managed_root": str(matching_root),
            "exists": locator.exists(),
            "kind": None,
            "snapshot_relative": None,
            "sha256": _path_digest(locator),
        }
        if locator.exists():
            target = snapshot / "external-residue" / f"{index:04d}"
            if locator.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(locator, target)
                item["kind"] = "file"
            elif locator.is_dir():
                _copy_tree(locator, target)
                item["kind"] = "directory"
            else:
                raise LifecycleError("TX_PATH_TYPE", "Unsupported external cleanup snapshot type.", str(locator))
            item["snapshot_relative"] = target.relative_to(snapshot).as_posix()
        meta["external_residue"].append(item)
    write_json(snapshot / "snapshot_meta.json", meta)


def _stage_artifact(artifact: dict[str, Any], release_identity: dict[str, Any], staging_root: Path) -> None:
    _copy_tree(artifact["root"] / "payload", staging_root)
    shutil.copyfile(artifact["root"] / "generation_manifest.json", staging_root / "generation_manifest.json")
    write_json(staging_root / "artifact_identity.json", {"artifact_sha256": artifact["artifact_sha256"], "package_tree_sha256": artifact["manifest"]["package_tree_sha256"]})
    write_json(staging_root / "release_identity.json", release_identity)


def _verify_stage(artifact: dict[str, Any], release_identity: dict[str, Any], staging_root: Path) -> None:
    payload_records = [record for record in artifact["records"] if record["path"].startswith("payload/")]
    actual: list[dict[str, Any]] = []
    metadata_names = {"generation_manifest.json", "artifact_identity.json", "release_identity.json"}
    for path in sorted((item for item in staging_root.rglob("*") if item.is_file() and item.name not in metadata_names), key=lambda item: item.relative_to(staging_root).as_posix().casefold()):
        actual.append({"path": f"payload/{path.relative_to(staging_root).as_posix()}", "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    if actual != payload_records:
        raise LifecycleError("TX_STAGE_VERIFY", "Staged generation differs from the verified artifact.", str(staging_root))
    if load_json(staging_root / "release_identity.json") != release_identity:
        raise LifecycleError("TX_STAGE_VERIFY", "Staged generation release identity differs from the bound plan.", str(staging_root))
    if file_sha256(staging_root / "generation_manifest.json") != release_identity["generation_manifest_sha256"]:
        raise LifecycleError("TX_STAGE_VERIFY", "Staged generation manifest differs from the bound release identity.", str(staging_root))


def _merge_managed_block(existing: bytes | None, managed: bytes) -> tuple[bytes, dict[str, Any]]:
    managed_text = managed.decode("utf-8-sig")
    start = managed_text.index(MANAGED_START)
    end = managed_text.index(MANAGED_END) + len(MANAGED_END)
    block = managed_text[start:end]
    if existing is None:
        return (block + "\n").encode("utf-8"), {"insertion": "created"}
    bom = existing.startswith(b"\xef\xbb\xbf")
    text = existing.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    block = block.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)
    starts = text.count(MANAGED_START)
    ends = text.count(MANAGED_END)
    if starts == 0 and ends == 0:
        separator = "" if not text or text.endswith(("\n", "\r")) else newline
        merged = text + separator + block + newline
        insertion = "append-ended-newline" if not separator else "append-added-newline"
        metadata = {"insertion": insertion}
    elif starts == 1 and ends == 1 and text.index(MANAGED_START) < text.index(MANAGED_END):
        old_start = text.index(MANAGED_START)
        old_end = text.index(MANAGED_END) + len(MANAGED_END)
        merged = text[:old_start] + block + text[old_end:]
        metadata = {"insertion": "preexisting-marker"}
    else:
        raise LifecycleError("TX_MANAGED_MARKER", "Managed instruction markers are incomplete or duplicated.")
    payload = merged.encode("utf-8")
    return ((b"\xef\xbb\xbf" + payload) if bom else payload), metadata


def _strip_managed_block(existing: bytes, metadata: dict[str, Any] | None) -> bytes | None:
    bom = existing.startswith(b"\xef\xbb\xbf")
    text = existing.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    starts = text.count(MANAGED_START)
    ends = text.count(MANAGED_END)
    if starts != 1 or ends != 1 or text.index(MANAGED_START) > text.index(MANAGED_END):
        raise LifecycleError("TX_MANAGED_MARKER", "Managed instruction markers are incomplete or duplicated.")
    start = text.index(MANAGED_START)
    end = text.index(MANAGED_END) + len(MANAGED_END)
    prefix = text[:start]
    suffix = text[end:]
    insertion = (metadata or {}).get("insertion", "preexisting-marker")
    if insertion in {"created", "append-ended-newline", "append-added-newline"} and suffix.startswith(newline):
        suffix = suffix[len(newline):]
    if insertion == "append-added-newline" and prefix.endswith(newline):
        prefix = prefix[:-len(newline)]
    remaining = prefix + suffix
    if not remaining.strip():
        return None
    payload = remaining.encode("utf-8")
    return (b"\xef\xbb\xbf" + payload) if bom else payload


def _modification_map(modifications: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for modification in modifications:
        _validate_modification_policy(modification)
        result[os.path.normcase(str(_absolute(modification["locator"])))] = modification
    return result


def _apply_projections(
    artifact: dict[str, Any] | None,
    generation_id: str | None,
    active_generation_root: Path | None,
    tool_roots: dict[str, Path],
    operation: str,
    modifications: list[dict[str, Any]],
) -> None:
    decisions = _modification_map(modifications)
    for tool in tool_roots:
        root = tool_roots[tool]
        root.mkdir(parents=True, exist_ok=True)
        old = _projection_manifest(root)
        old_entries = {entry["path"].casefold(): entry for entry in old.get("entries", [])} if old else {}
        desired = artifact["projections"][tool]["entries"] if artifact is not None and operation != "uninstall" else []
        desired_paths = {entry["path"].casefold() for entry in desired}
        new_entries: list[dict[str, Any]] = []
        for entry in desired:
            target = _safe_target(root, entry["path"])
            modification = decisions[os.path.normcase(str(_absolute(target)))]
            decision = modification["decision"]
            source = artifact["root"] / "projections" / tool / entry["source"]
            merge_metadata = None
            if entry["mode"] == "managed-block":
                if decision not in {"replace", "merge"}:
                    raise LifecycleError("TX_PROJECTION_DECISION", "Required managed instruction projection must use replace or merge.", str(target))
                payload, merge_metadata = _merge_managed_block(target.read_bytes() if target.is_file() else None, source.read_bytes())
                previous = old_entries.get(entry["path"].casefold())
                if previous and previous.get("merge_metadata"):
                    merge_metadata = previous["merge_metadata"]
            elif entry["mode"] == "boot-pointer":
                if decision != "replace" or active_generation_root is None:
                    raise LifecycleError("TX_PROJECTION_DECISION", "Boot projection requires replace and an active generation root.", str(target))
                template = source.read_text(encoding="utf-8-sig")
                if template.count(ACTIVE_GENERATION_TOKEN) != 1:
                    raise LifecycleError("ARTIFACT_BOOT_POINTER", "Boot projection template token is missing or ambiguous.", str(source))
                payload = template.replace(ACTIVE_GENERATION_TOKEN, str(_absolute(active_generation_root))).encode("utf-8")
            else:
                if decision != "replace":
                    raise LifecycleError("TX_PROJECTION_DECISION", "Required file projection must use replace.", str(target))
                payload = source.read_bytes()
            _atomic_write(target, payload)
            installed_entry = {
                "path": entry["path"],
                "mode": entry["mode"],
                "source_sha256": entry["sha256"],
                "installed_sha256": file_sha256(target),
            }
            if merge_metadata is not None:
                installed_entry["merge_metadata"] = merge_metadata
            new_entries.append(installed_entry)
        for folded, previous in old_entries.items():
            if folded in desired_paths:
                continue
            target = _safe_target(root, previous["path"])
            modification = decisions[os.path.normcase(str(_absolute(target)))]
            decision = modification["decision"]
            if target.is_file():
                if previous.get("mode") == "managed-block":
                    if decision not in {"merge", "replace", "drop"}:
                        raise LifecycleError("TX_PROJECTION_DECISION", "Managed instruction removal must strip the managed block.", str(target))
                    payload = _strip_managed_block(target.read_bytes(), previous.get("merge_metadata"))
                    if payload is None:
                        target.unlink()
                    else:
                        _atomic_write(target, payload)
                elif decision == "preserve":
                    pass
                elif decision in {"replace", "drop"}:
                    target.unlink()
                else:
                    raise LifecycleError("TX_PROJECTION_DECISION", "Stale file projection requires preserve, replace, or drop.", str(target))
        manifest_path = root / PROJECTION_MANIFEST
        if operation == "uninstall":
            if manifest_path.exists():
                manifest_path.unlink()
        else:
            manifest = {
                "schema_version": 1,
                "tool": tool,
                "generation_id": generation_id,
                "artifact_sha256": artifact["artifact_sha256"],
                "entries": new_entries,
                "created_at": _now(),
            }
            write_json(manifest_path, manifest)


def _verify_projections(artifact: dict[str, Any] | None, tool_roots: dict[str, Path], operation: str) -> None:
    for tool in tool_roots:
        manifest = _projection_manifest(tool_roots[tool])
        if operation == "uninstall":
            if manifest is not None:
                raise LifecycleError("TX_POSTVALIDATE", "Projection manifest remains after uninstall.", tool)
            continue
        if manifest is None or manifest.get("artifact_sha256") != artifact["artifact_sha256"]:
            raise LifecycleError("TX_POSTVALIDATE", "Projection manifest is missing or stale.", tool)
        desired = artifact["projections"][tool]["entries"]
        if {entry["path"] for entry in manifest["entries"]} != {entry["path"] for entry in desired}:
            raise LifecycleError("TX_POSTVALIDATE", "Projection entries differ from artifact plan.", tool)
        for entry in manifest["entries"]:
            target = _safe_target(tool_roots[tool], entry["path"])
            if not target.is_file() or file_sha256(target) != entry["installed_sha256"]:
                raise LifecycleError("TX_POSTVALIDATE", "Projected file verification failed.", str(target))


def _activate(root: Path, artifact: dict[str, Any] | None, context: dict[str, Any], operation: str, transaction_root: Path) -> None:
    registry = _load_registry(root) or _initial_registry(root, _now(), context["selected_tools"])
    if operation == "uninstall":
        for item in registry["generations"]:
            if item["state"] == "active":
                item["state"] = "retiring"
        registry["active_generation_id"] = None
        # The uninstall activation point atomically retires the active pointer.
        # Keeping lifecycle_state=transaction-active with zero active generations
        # would violate the closed InstallationRegistry invariant.
        registry["lifecycle_state"] = "uninstalled"
        registry["updated_at"] = _now()
        write_json(_registry_path(root), registry)
        if _pointer_path(root).exists():
            _pointer_path(root).unlink()
        return

    target = Path(context["generation_root"])
    staging = Path(context["staging_root"])
    generations_root = root / "generations"
    generations_root.mkdir(parents=True, exist_ok=True)
    if target.exists():
        _remove_managed(generations_root, target)
    os.replace(staging, target)
    old_records = [item for item in registry["generations"] if item["generation_id"] != context["target_generation_id"]]
    for item in old_records:
        item["state"] = "retiring"
    new_record = {
        "generation_id": context["target_generation_id"],
        "version": context["target_version"],
        "artifact_sha256": artifact["artifact_sha256"],
        "release_id": context["release_identity"]["release_id"],
        "release_manifest_sha256": context["release_identity"]["release_manifest_sha256"],
        "release_package_sha256": context["release_identity"]["release_package_sha256"],
        "generation_manifest_sha256": context["release_identity"]["generation_manifest_sha256"],
        "root": str(target),
        "state": "active",
        "generation_manifest_ref": f"generation-manifest:{context['target_generation_id']}",
        "projection_manifests": [f"projection:{tool}:{context['target_generation_id']}" for tool in context["selected_tools"]],
        "created_at": _now(),
    }
    registry["generations"] = [*old_records, new_record]
    registry["active_generation_id"] = context["target_generation_id"]
    registry["lifecycle_state"] = "transaction-active"
    registry["release_binding_profile"] = "release-package-v1"
    registry["selected_tools"] = context["selected_tools"]
    registry["updated_at"] = _now()
    write_json(_registry_path(root), registry)
    write_json(
        _pointer_path(root),
        {
            "schema_version": 1,
            "generation_id": context["target_generation_id"],
            "version": context["target_version"],
            "root": str(target),
            "artifact_sha256": artifact["artifact_sha256"],
            "release_id": context["release_identity"]["release_id"],
            "release_manifest_sha256": context["release_identity"]["release_manifest_sha256"],
            "release_package_sha256": context["release_identity"]["release_package_sha256"],
            "generation_manifest_sha256": context["release_identity"]["generation_manifest_sha256"],
        },
    )


def _allowed_cleanup_roots(context: dict[str, Any]) -> list[Path]:
    roots = [Path(context["lifecycle_root"]), *(Path(value) for value in context["tool_roots"].values())]
    roots.extend(
        Path(observation["locator"])
        for observation in context["legacy_root_observations"]
        if observation["classification"] in {"exact-managed-root", "partial-managed-root"}
    )
    return roots


def _cleanup_records(context: dict[str, Any]) -> dict[str, Any]:
    deleted: list[str] = []
    preserved: list[dict[str, Any]] = []
    roots = _allowed_cleanup_roots(context)
    for record in context["residue_records"]:
        path = Path(record["locator"])
        matching_root = next((root for root in roots if _is_inside(root, path)), None)
        if record["action"] == "delete":
            if record["owner"] != "malts" or matching_root is None:
                raise LifecycleError("RS_DELETE_BOUNDARY", "Deletion requires MALTS ownership and an allowed managed root.", str(path))
            if record.get("cleanup_scope") == "whole-root":
                coverage = record.get("coverage") or {}
                if (
                    coverage.get("managed_file_count") != coverage.get("exact_match_count")
                    or coverage.get("missing_count") != 0
                    or coverage.get("drift_count") != 0
                    or coverage.get("extra_count") != 0
                    or not record.get("manifest_sha256")
                ):
                    raise LifecycleError("RS_WHOLE_ROOT_PROOF", "Whole-root deletion requires complete exact manifest coverage with zero extras.", str(path))
            digest_refs = [ref.split(":", 1)[1] for ref in record["ownership_evidence_refs"] if ref.startswith("sha256:")]
            if digest_refs and _path_digest(path) not in digest_refs and _path_digest(path) != "MISSING":
                raise LifecycleError("RS_OWNERSHIP_DRIFT", "Residue content changed after planning.", str(path))
            _remove_managed(matching_root, path)
            deleted.append(str(path))
        else:
            preserved.append({"locator": str(path), "owner": record["owner"], "reason": record["preserve_reason"]})
    return {"deleted": deleted, "preserved": preserved}


def _clean(root: Path, context: dict[str, Any], operation: str, transaction_root: Path) -> dict[str, Any]:
    registry = _load_registry(root) or _initial_registry(root, _now(), context["selected_tools"])
    active_id = registry["active_generation_id"]
    if operation == "uninstall":
        for item in list(registry["generations"]):
            path = Path(item["root"])
            if path.exists():
                _remove_managed(root / "generations", path)
        registry["generations"] = []
        registry["lifecycle_state"] = "uninstalled"
    else:
        for item in list(registry["generations"]):
            if item["generation_id"] == active_id:
                continue
            path = Path(item["root"])
            if path.exists():
                _remove_managed(root / "generations", path)
        registry["generations"] = [item for item in registry["generations"] if item["generation_id"] == active_id]
    registry["updated_at"] = _now()
    write_json(_registry_path(root), registry)
    result = _cleanup_records(context)
    legacy_ledger = root / LEGACY_RESIDUE_RELATIVE
    if legacy_ledger.is_file():
        legacy_ledger.unlink()
    return result


def _commit(root: Path, context: dict[str, Any], journal: dict[str, Any], envelope: dict[str, Any], transaction_root: Path) -> None:
    registry = _load_registry(root) or _initial_registry(root, _now(), context["selected_tools"])
    registry["lifecycle_state"] = "uninstalled" if context["operation"] == "uninstall" else "stable"
    registry["updated_at"] = _now()
    write_json(_registry_path(root), registry)
    audit = root / AUDIT_RELATIVE
    audit.mkdir(parents=True, exist_ok=True)
    write_json(audit / f"{context['operation_id']}.journal.json", journal)
    write_json(audit / f"{context['operation_id']}.plan.json", envelope)
    if transaction_root.exists():
        _remove_managed(root / "runtime", transaction_root)
    _release_lock(root, context["operation_id"])


def _restore_snapshot(root: Path, tool_roots: dict[str, Path], transaction_root: Path) -> None:
    snapshot = transaction_root / "snapshot"
    if not snapshot.is_dir():
        return
    meta = load_json(snapshot / "snapshot_meta.json")
    generations = root / "generations"
    if generations.exists():
        _remove_managed(root, generations)
    if (snapshot / "generations").is_dir():
        _copy_tree(snapshot / "generations", generations)
    registry_path = _registry_path(root)
    if meta["registry_exists"]:
        _atomic_write(registry_path, (snapshot / "registry.json").read_bytes())
    elif registry_path.exists():
        registry_path.unlink()
    pointer_path = _pointer_path(root)
    if meta["pointer_exists"]:
        _atomic_write(pointer_path, (snapshot / "pointer.json").read_bytes())
    elif pointer_path.exists():
        pointer_path.unlink()
    for tool in meta["tools"]:
        tool_root = tool_roots[tool]
        current = _projection_manifest(tool_root)
        if current:
            for entry in current["entries"]:
                target = _safe_target(tool_root, entry["path"])
                if target.is_file():
                    target.unlink()
            manifest_path = tool_root / PROJECTION_MANIFEST
            if manifest_path.exists():
                manifest_path.unlink()
        tool_meta = meta["tools"][tool]
        tool_snapshot = snapshot / "tools" / tool
        for entry in tool_meta["entries"]:
            if entry["exists"]:
                source = tool_snapshot / "files" / Path(entry["path"])
                target = _safe_target(tool_root, entry["path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        if tool_meta["manifest_exists"]:
            shutil.copyfile(tool_snapshot / "manifest.json", tool_root / PROJECTION_MANIFEST)
    for item in meta.get("external_residue", []):
        locator = Path(item["locator"])
        managed_root = Path(item["managed_root"])
        if not item["exists"]:
            if locator.exists():
                raise LifecycleError("TX_ROLLBACK_DRIFT", "An originally absent cleanup target appeared during rollback.", str(locator))
            continue
        source = snapshot / Path(item["snapshot_relative"])
        if locator.exists() and _path_digest(locator) == item["sha256"]:
            continue
        if locator.exists():
            if item["kind"] != "directory" or not locator.is_dir():
                raise LifecycleError("TX_ROLLBACK_DRIFT", "External cleanup target changed during rollback.", str(locator))
            saved_entries: dict[str, tuple[str, str | None]] = {}
            for saved in source.rglob("*"):
                relative = saved.relative_to(source).as_posix().casefold()
                saved_entries[relative] = ("file", file_sha256(saved)) if saved.is_file() else ("directory", None)
            for current in locator.rglob("*"):
                _assert_no_reparse(locator, current)
                relative = current.relative_to(locator).as_posix().casefold()
                actual = ("file", file_sha256(current)) if current.is_file() else ("directory", None)
                if saved_entries.get(relative) != actual:
                    raise LifecycleError("TX_ROLLBACK_DRIFT", "External cleanup target gained or changed content during rollback.", str(current))
            _remove_managed(managed_root, locator)
        if item["kind"] == "file":
            locator.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, locator)
        elif item["kind"] == "directory":
            _copy_tree(source, locator)
        else:
            raise LifecycleError("TX_ROLLBACK_SNAPSHOT", "External cleanup snapshot metadata is invalid.", str(locator))


def _archive_failure(root: Path, context: dict[str, Any], journal: dict[str, Any], envelope: dict[str, Any], transaction_root: Path) -> None:
    audit = root / AUDIT_RELATIVE
    audit.mkdir(parents=True, exist_ok=True)
    write_json(audit / f"{context['operation_id']}.journal.json", journal)
    write_json(audit / f"{context['operation_id']}.plan.json", envelope)
    if transaction_root.exists():
        _remove_managed(root / "runtime", transaction_root)
    if _lock_path(root).exists():
        lock = load_json(_lock_path(root))
        if lock.get("operation_id") == context["operation_id"]:
            _release_lock(root, context["operation_id"])


def _rollback(root: Path, context: dict[str, Any], journal: dict[str, Any], envelope: dict[str, Any], transaction_root: Path, *, fault_at: str | None = None) -> dict[str, Any]:
    if journal["state"] not in {"DISCOVER", "LOCK"} and journal["state"] != "ROLLBACK":
        _set_state(transaction_root, journal, "ROLLBACK", evidence="lifecycle:rollback", fault_at=fault_at)
    elif journal["state"] == "ROLLBACK" and fault_at == "ROLLBACK":
        raise InjectedCrash("ROLLBACK")
    _restore_snapshot(root, {tool: Path(value) for tool, value in context["tool_roots"].items()}, transaction_root)
    staging = Path(context["staging_root"])
    if staging.exists():
        _remove_managed(transaction_root, staging)
    now = _now()
    journal["recovery_actions"].append({"action": "restore pre-transaction registry, generation, and managed projections", "status": "completed", "evidence_refs": ["snapshot:restored"]})
    if journal["state"] != "FAILED":
        journal["state"] = "FAILED"
        journal["state_history"].append({"state": "FAILED", "at": now, "evidence_refs": ["rollback:completed"]})
    journal["updated_at"] = now
    _validate_contract("transaction-journal", journal)
    write_json(_journal_path(transaction_root), journal)
    _archive_failure(root, context, journal, envelope, transaction_root)
    return {"status": "RECOVERED_ROLLBACK", "operation_id": context["operation_id"], "active_state_restored": True}


def scan_residue(
    root_value: str | Path,
    tool_roots: dict[str, str | Path],
    *,
    plan_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = _absolute(root_value)
    normalized_tools = _normalize_tool_roots(tool_roots)
    selected_tools = list(normalized_tools)
    issues: list[dict[str, Any]] = []
    registry = _load_registry(root)
    active: list[dict[str, Any]] = []
    if registry is None:
        has_managed_install = (root / "generations").is_dir() and any((root / "generations").iterdir())
        has_managed_install = has_managed_install or _pointer_path(root).exists()
        has_managed_install = has_managed_install or any(_projection_manifest(tool_root) is not None for tool_root in normalized_tools.values())
        if has_managed_install:
            issues.append({"code": "RS_REGISTRY_MISSING", "path": str(_registry_path(root))})
    else:
        active = [item for item in registry["generations"] if item["state"] == "active"]
        expected_active = 0 if registry["lifecycle_state"] == "uninstalled" else 1
        if len(active) != expected_active or any(item["state"] != "active" for item in registry["generations"]):
            issues.append({"code": "RS_GENERATION_STATE", "path": str(root / "generations")})
        if registry["selected_tools"] != selected_tools:
            issues.append({"code": "RS_TOOL_SELECTION", "expected": registry["selected_tools"], "observed": selected_tools})
        if registry["lifecycle_state"] != "uninstalled" and registry["release_binding_profile"] != "release-package-v1":
            issues.append({"code": "RS_RELEASE_BINDING", "path": str(_registry_path(root))})
        if active and registry["release_binding_profile"] == "release-package-v1":
            required = ("release_id", "release_manifest_sha256", "release_package_sha256", "generation_manifest_sha256")
            if any(active[0].get(field) is None for field in required):
                issues.append({"code": "RS_RELEASE_BINDING", "path": str(_registry_path(root))})
    if _lock_path(root).exists():
        issues.append({"code": "RS_STALE_LOCK", "path": str(_lock_path(root))})
    transactions = root / TRANSACTIONS_RELATIVE
    if transactions.is_dir() and any(transactions.iterdir()):
        issues.append({"code": "RS_TRANSACTION_STATE", "path": str(transactions)})
    if (root / LEGACY_RESIDUE_RELATIVE).exists():
        issues.append({"code": "RS_LEGACY_LEDGER", "path": str(root / LEGACY_RESIDUE_RELATIVE)})

    ignored_audit_plan: dict[str, Any] | None = None
    context = plan_context
    if context is None:
        latest_plans = sorted((root / AUDIT_RELATIVE).glob("*.plan.json"), key=lambda path: path.stat().st_mtime) if (root / AUDIT_RELATIVE).is_dir() else []
        if latest_plans:
            try:
                envelope = load_json(latest_plans[-1])
                _, context = validate_plan_envelope(envelope)
            except LifecycleError as exc:
                ignored_audit_plan = {"path": str(latest_plans[-1]), "reason": exc.code}
                context = None

    preserved: list[dict[str, Any]] = []
    if context is not None:
        for record in context["residue_records"]:
            path = Path(record["locator"])
            if record["action"] == "delete" and path.exists():
                issues.append({"code": "RS_DELETE_REMAINS", "path": str(path), "residue_id": record["residue_id"]})
            elif record["action"] != "delete":
                preserved.append({"path": str(path), "owner": record["owner"], "reason": record["preserve_reason"]})
        for observation in context["legacy_root_observations"]:
            if observation["classification"] == "untrusted":
                preserved.append({"path": observation["locator"], "owner": "unknown", "reason": observation["reason"]})
            elif observation["classification"] == "partial-managed-root":
                for relative in observation["drift_paths"]:
                    preserved.append({"path": str(Path(observation["locator"]) / Path(relative)), "owner": "user", "reason": "legacy managed path drifted from its trusted installed hash"})
                for relative in observation["extra_paths"]:
                    preserved.append({"path": str(Path(observation["locator"]) / Path(relative)), "owner": "unknown", "reason": "path is outside the trusted legacy manifest"})

    for tool, tool_root in normalized_tools.items():
        manifest = _projection_manifest(tool_root)
        if registry and registry["lifecycle_state"] == "uninstalled":
            if manifest is not None:
                issues.append({"code": "RS_PROJECTION_MANIFEST", "path": str(tool_root / PROJECTION_MANIFEST)})
        elif registry and registry["lifecycle_state"] == "stable":
            if manifest is None:
                issues.append({"code": "RS_PROJECTION_MISSING", "path": str(tool_root / PROJECTION_MANIFEST)})
            else:
                for entry in manifest["entries"]:
                    target = _safe_target(tool_root, entry["path"])
                    if not target.is_file() or file_sha256(target) != entry["installed_sha256"]:
                        issues.append({"code": "RS_PROJECTION_DRIFT", "path": str(target)})
    return {
        "status": "PASS" if not issues else "FAIL",
        "zero_active_malts_owned_legacy_residue": not issues,
        "issues": issues,
        "preserved_user_or_external": preserved,
        "registry_state": registry["lifecycle_state"] if registry else None,
        "active_generation_id": registry["active_generation_id"] if registry else None,
        "selected_tools": registry["selected_tools"] if registry else selected_tools,
        "ignored_legacy_audit_plan": ignored_audit_plan,
    }


def execute_plan(envelope: dict[str, Any], expected_plan_hash: str, *, apply: bool, fault_at: str | None = None) -> dict[str, Any]:
    plan, context = validate_plan_envelope(envelope)
    artifact = _verify_plan_inputs(plan, context, expected_plan_hash)
    if not apply:
        return {"status": "PASS", "mode": "DRY_RUN", "operation_id": plan["operation_id"], "plan_hash": plan["plan_hash"], "writes_performed": False}
    root = _absolute(context["lifecycle_root"])
    root.mkdir(parents=True, exist_ok=True)
    for relative in ("registry", "generations", "runtime", "state", "user-data"):
        (root / relative).mkdir(parents=True, exist_ok=True)
    transaction_root = _transaction_root(context)
    if transaction_root.exists():
        raise LifecycleError("TX_TRANSACTION_EXISTS", "Transaction directory already exists.", str(transaction_root))
    transaction_root.mkdir(parents=True)
    write_json(_plan_path(transaction_root), envelope)
    journal = _new_journal(plan, _now())
    write_json(_journal_path(transaction_root), journal)
    try:
        _set_state(transaction_root, journal, "DISCOVER", evidence="lifecycle:discover", fault_at=fault_at)
        lock_result = _acquire_lock(root, plan["operation_id"], _now())
        _set_state(transaction_root, journal, "LOCK", evidence="lifecycle:lock", fault_at=fault_at)
        _verify_plan_inputs(plan, context, expected_plan_hash)
        _set_state(transaction_root, journal, "PLAN", evidence="lifecycle:plan-hash", fault_at=fault_at)
        if artifact is not None:
            _stage_artifact(artifact, context["release_identity"], Path(context["staging_root"]))
        else:
            Path(context["staging_root"]).mkdir(parents=True, exist_ok=True)
        _set_state(transaction_root, journal, "STAGE", evidence="lifecycle:stage", fault_at=fault_at)
        _snapshot(
            root,
            {tool: Path(value) for tool, value in context["tool_roots"].items()},
            transaction_root,
            plan["user_modifications"],
            context["residue_records"],
            context["legacy_root_observations"],
        )
        _set_state(transaction_root, journal, "SNAPSHOT", evidence="lifecycle:snapshot", fault_at=fault_at)
        if artifact is not None:
            _verify_stage(artifact, context["release_identity"], Path(context["staging_root"]))
        _verify_plan_inputs(plan, context, expected_plan_hash)
        _set_state(transaction_root, journal, "PREVALIDATE", evidence="lifecycle:prevalidate", fault_at=fault_at)
        _activate(root, artifact, context, plan["operation"], transaction_root)
        _set_state(transaction_root, journal, "ACTIVATE", evidence="lifecycle:activate", fault_at=fault_at)
        tool_paths = {tool: Path(value) for tool, value in context["tool_roots"].items()}
        _apply_projections(
            artifact,
            context["target_generation_id"],
            Path(context["generation_root"]) if context["generation_root"] else None,
            tool_paths,
            plan["operation"],
            plan["user_modifications"],
        )
        _verify_projections(artifact, tool_paths, plan["operation"])
        _set_state(transaction_root, journal, "POSTVALIDATE", evidence="lifecycle:postvalidate", fault_at=fault_at)
        _set_state(transaction_root, journal, "CLEAN", evidence="lifecycle:clean-ready", fault_at=fault_at)
        cleanup_result = _clean(root, context, plan["operation"], transaction_root)
        precommit = scan_residue(root, context["tool_roots"], plan_context=context)
        allowed_precommit = {"RS_STALE_LOCK", "RS_TRANSACTION_STATE"}
        nontransaction_issues = [issue for issue in precommit["issues"] if issue["code"] not in allowed_precommit]
        if nontransaction_issues:
            raise LifecycleError("TX_ZERO_RESIDUE", f"Precommit residue scan failed: {nontransaction_issues}")
        registry = _load_registry(root)
        registry["lifecycle_state"] = "uninstalled" if plan["operation"] == "uninstall" else "stable"
        registry["updated_at"] = _now()
        write_json(_registry_path(root), registry)
        _set_state(transaction_root, journal, "COMMIT", evidence="lifecycle:commit", fault_at=fault_at)
        _commit(root, context, journal, envelope, transaction_root)
        final_scan = scan_residue(root, context["tool_roots"], plan_context=context)
        if final_scan["status"] != "PASS":
            raise LifecycleError("TX_ZERO_RESIDUE", f"Final residue scan failed: {final_scan['issues']}")
        return {
            "status": "PASS",
            "mode": "APPLY",
            "operation_id": plan["operation_id"],
            "operation": plan["operation"],
            "plan_hash": plan["plan_hash"],
            "stale_lock_replaced": lock_result["stale_replaced"],
            "cleanup": cleanup_result,
            "residue_scan": final_scan,
            "writes_performed": True,
        }
    except InjectedCrash:
        raise
    except Exception as operation_exc:
        try:
            current = load_json(_journal_path(transaction_root)) if _journal_path(transaction_root).is_file() else journal
            _rollback(root, context, current, envelope, transaction_root)
        except Exception as recovery_exc:
            if _journal_path(transaction_root).is_file():
                current = load_json(_journal_path(transaction_root))
                now = _now()
                if current["state"] != "FAILED":
                    current["state"] = "FAILED"
                    current["state_history"].append({"state": "FAILED", "at": now, "evidence_refs": ["rollback:failed"]})
                current["recovery_actions"].append({"action": "automatic rollback", "status": "failed", "evidence_refs": [f"error:{type(recovery_exc).__name__}"]})
                current["updated_at"] = now
                write_json(_journal_path(transaction_root), current)
            raise LifecycleError("TX_ROLLBACK_FAILED", f"Lifecycle operation failed and rollback also failed: {recovery_exc}") from recovery_exc
        if isinstance(operation_exc, LifecycleError):
            raise
        if isinstance(operation_exc, OSError):
            raise LifecycleError("TX_IO_FAILURE", f"Lifecycle I/O failed and the prior state was restored: {operation_exc}") from operation_exc
        raise LifecycleError(
            "TX_INTERNAL_ERROR",
            f"Lifecycle operation failed and the prior state was restored: {type(operation_exc).__name__}: {operation_exc}",
        ) from operation_exc


def _load_transaction(root: Path, operation_id: str | None = None) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    transactions = root / TRANSACTIONS_RELATIVE
    if operation_id is not None:
        candidates = [transactions / operation_id]
    else:
        candidates = [path for path in transactions.iterdir() if path.is_dir()] if transactions.is_dir() else []
    candidates = [path for path in candidates if path.is_dir()]
    if len(candidates) != 1:
        raise LifecycleError("TX_RECOVERY_SELECTION", "Recovery requires exactly one selected active transaction.", str(transactions))
    transaction_root = candidates[0]
    envelope = load_json(_plan_path(transaction_root))
    plan, context = validate_plan_envelope(envelope)
    journal = load_json(_journal_path(transaction_root))
    _validate_contract("transaction-journal", journal)
    if journal["plan_hash"] != plan["plan_hash"] or journal["operation_id"] != plan["operation_id"]:
        raise LifecycleError("TX_RECOVERY_BINDING", "Journal does not match the bound plan.")
    return transaction_root, envelope, context, journal


def recover_transaction(root_value: str | Path, *, operation_id: str | None = None, fault_at: str | None = None) -> dict[str, Any]:
    root = _absolute(root_value)
    transaction_root, envelope, context, journal = _load_transaction(root, operation_id)
    plan = envelope["plan_contract"]
    tool_roots = {tool: Path(value) for tool, value in context["tool_roots"].items()}
    state = journal["state"]
    if state in {"CLEAN", "COMMIT"}:
        if state == "CLEAN":
            cleanup_result = _clean(root, context, plan["operation"], transaction_root)
            registry = _load_registry(root)
            registry["lifecycle_state"] = "uninstalled" if plan["operation"] == "uninstall" else "stable"
            registry["updated_at"] = _now()
            write_json(_registry_path(root), registry)
            _set_state(transaction_root, journal, "COMMIT", evidence="recovery:resume-clean", fault_at=fault_at)
        else:
            cleanup_result = {"deleted": [], "preserved": []}
        _commit(root, context, journal, envelope, transaction_root)
        final = scan_residue(root, context["tool_roots"], plan_context=context)
        if final["status"] != "PASS":
            raise LifecycleError("TX_ZERO_RESIDUE", f"Recovery commit residue scan failed: {final['issues']}")
        return {"status": "RECOVERED_COMMIT", "operation_id": plan["operation_id"], "cleanup": cleanup_result, "residue_scan": final}
    if state == "FAILED":
        return {"status": "FAILED", "operation_id": plan["operation_id"], "requires_manual_recovery": True}
    return _rollback(root, context, journal, envelope, transaction_root, fault_at=fault_at)


def semantic_state(root_value: str | Path, tool_roots: dict[str, str | Path]) -> dict[str, Any]:
    root = _absolute(root_value)
    normalized_tools = _normalize_tool_roots(tool_roots)
    registry = _load_registry(root)
    if registry is None:
        return {"installed": False, "registry": None}
    active = next((item for item in registry["generations"] if item["state"] == "active"), None)
    projection: dict[str, Any] = {}
    for tool, tool_root in normalized_tools.items():
        manifest = _projection_manifest(tool_root)
        projection[tool] = None if manifest is None else {
            "artifact_sha256": manifest["artifact_sha256"],
            "entries": sorted((entry["path"], entry["mode"], entry["source_sha256"]) for entry in manifest["entries"]),
        }
    user_data = root / "user-data"
    return {
        "installed": registry["lifecycle_state"] == "stable",
        "lifecycle_state": registry["lifecycle_state"],
        "active_version": active["version"] if active else None,
        "active_generation_id": active["generation_id"] if active else None,
        "artifact_sha256": active["artifact_sha256"] if active else None,
        "release_id": active["release_id"] if active else None,
        "release_manifest_sha256": active["release_manifest_sha256"] if active else None,
        "release_package_sha256": active["release_package_sha256"] if active else None,
        "generation_manifest_sha256": active["generation_manifest_sha256"] if active else None,
        "selected_tools": registry["selected_tools"],
        "generation_digest": _path_digest(Path(active["root"])) if active else None,
        "projection": projection,
        "user_data_digest": _path_digest(user_data),
        "residue": scan_residue(root, normalized_tools),
    }


def _parse_tool_roots(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise LifecycleError("TX_TOOL_ROOTS", "Tool roots use tool=absolute-path syntax.")
        tool, path = value.split("=", 1)
        if tool not in TOOLS or tool in result:
            raise LifecycleError("TX_TOOL_ROOTS", "Tool root key is invalid or duplicated.", tool)
        result[tool] = path
    if not result:
        raise LifecycleError("TX_TOOL_ROOTS", "At least one selected tool root is required.")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan")
    plan.add_argument("--operation", required=True, choices=("install", "update", "repair", "uninstall"))
    plan.add_argument("--lifecycle-root", required=True)
    plan.add_argument("--tool-root", action="append", default=[], required=True)
    plan.add_argument("--release-root")
    plan.add_argument("--legacy-root", action="append", default=[])
    plan.add_argument("--default-legacy-root", default=str(Path.home() / ".malts"))
    plan.add_argument("--operation-id")
    plan.add_argument("--timestamp")
    plan.add_argument("--modification-overrides")
    plan.add_argument("--out")
    plan.add_argument("--apply", action="store_true")

    execute = subparsers.add_parser("execute")
    execute.add_argument("--plan", required=True)
    execute.add_argument("--expected-plan-hash", required=True)
    execute.add_argument("--fault-at", choices=(*STATES, "ROLLBACK"))
    execute.add_argument("--apply", action="store_true")

    recover = subparsers.add_parser("recover")
    recover.add_argument("--lifecycle-root", required=True)
    recover.add_argument("--operation-id")
    recover.add_argument("--fault-at", choices=("ROLLBACK", "COMMIT"))
    recover.add_argument("--apply", action="store_true")

    scan = subparsers.add_parser("scan")
    scan.add_argument("--lifecycle-root", required=True)
    scan.add_argument("--tool-root", action="append", default=[], required=True)

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--lifecycle-root", required=True)
    inspect.add_argument("--tool-root", action="append", default=[], required=True)

    verify_release = subparsers.add_parser("verify-release")
    verify_release.add_argument("--release-root", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "plan":
            overrides = load_json(_absolute(args.modification_overrides)) if args.modification_overrides else None
            envelope = make_plan(
                operation=args.operation,
                lifecycle_root=args.lifecycle_root,
                tool_roots=_parse_tool_roots(args.tool_root),
                release_root=args.release_root,
                legacy_roots=args.legacy_root,
                default_legacy_root=args.default_legacy_root,
                operation_id=args.operation_id,
                created_at=args.timestamp,
                modification_overrides=overrides,
            )
            if args.apply:
                if not args.out:
                    raise LifecycleError("TX_PLAN_OUTPUT", "--apply requires --out for a plan.")
                output = _absolute(args.out)
                if output.exists():
                    raise LifecycleError("TX_PLAN_OUTPUT", "Refusing to overwrite an existing plan.", str(output))
                write_json(output, envelope)
            result = {"status": "PASS", "mode": "APPLY" if args.apply else "DRY_RUN", "writes_performed": args.apply, "plan_hash": envelope["plan_contract"]["plan_hash"], "plan": envelope}
        elif args.command == "execute":
            envelope = load_json(_absolute(args.plan))
            result = execute_plan(envelope, args.expected_plan_hash, apply=args.apply, fault_at=args.fault_at)
        elif args.command == "recover":
            if not args.apply:
                root = _absolute(args.lifecycle_root)
                transaction_root, envelope, context, journal = _load_transaction(root, args.operation_id)
                result = {"status": "PASS", "mode": "DRY_RUN", "writes_performed": False, "operation_id": context["operation_id"], "current_state": journal["state"], "planned_recovery": "resume-commit" if journal["state"] in {"CLEAN", "COMMIT"} else "rollback"}
            else:
                result = recover_transaction(args.lifecycle_root, operation_id=args.operation_id, fault_at=args.fault_at)
                result["mode"] = "APPLY"
                result["writes_performed"] = True
        elif args.command == "scan":
            result = scan_residue(args.lifecycle_root, _parse_tool_roots(args.tool_root))
            result.update({"mode": "READ_ONLY", "writes_performed": False})
        elif args.command == "verify-release":
            result = verify_release_root(args.release_root)
            result = {**result["verified"], "mode": "READ_ONLY", "writes_performed": False}
        else:
            result = semantic_state(args.lifecycle_root, _parse_tool_roots(args.tool_root))
            result.update({"status": "PASS", "mode": "READ_ONLY", "writes_performed": False})
    except InjectedCrash as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 42
    except LifecycleError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    except Exception as exc:
        failure = LifecycleError("TX_INTERNAL_ERROR", f"{type(exc).__name__}: {exc}")
        print(json.dumps(failure.as_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"PASS", "RECOVERED_COMMIT", "RECOVERED_ROLLBACK"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
