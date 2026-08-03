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
import tempfile
import uuid
from contextlib import contextmanager
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
AUDIT_SUCCESS_LIMIT = 20
AUDIT_FAILURE_LIMIT = 10
AUDIT_MONTHLY_LIMIT = 12
AUDIT_CURRENT_FILENAME = "current-binding.audit.json"
AUDIT_PRE_RETENTION_DIRECTORY = "legacy-pre-retention"
AUDIT_EVENT_NAME_PATTERN = re.compile(
    r"^(?P<token>[0-9]{8}T[0-9]{6}Z)--(?P<operation_id>[A-Za-z0-9][A-Za-z0-9._-]{0,127})"
    r"\.(?P<kind>audit|plan|journal)\.json$"
)
AUDIT_MONTH_NAME_PATTERN = re.compile(r"^(?P<month>[0-9]{4}-(?:0[1-9]|1[0-2]))\.audit\.json$")
AUDIT_LEGACY_NAME_PATTERN = re.compile(
    r"^(?P<operation_id>[A-Za-z0-9][A-Za-z0-9._-]{0,127})\.(?P<kind>plan|journal)\.json$"
)
AUDIT_PRE_RETENTION_PLAN_KEYS = frozenset(
    {
        "schema_version", "operation_id", "operation", "source_artifact_sha256", "detected_generation",
        "tool_targets", "actions", "user_modifications", "expected_cleanup", "acceptance_matrix",
        "plan_hash_algorithm", "plan_hash", "created_at",
    }
)
AUDIT_PRE_RETENTION_CONTEXT_KEYS = frozenset(
    {
        "schema_version", "operation_id", "operation", "lifecycle_root", "artifact_root", "artifact_sha256",
        "target_generation_id", "target_version", "generation_root", "tool_roots", "registry_sha256",
        "legacy_fixture", "legacy_fixture_sha256", "transaction_root", "staging_root", "snapshot_root",
        "residue_records", "expected_cleanup", "modification_observations",
    }
)
AUDIT_PRE_RETENTION_JOURNAL_KEYS = frozenset(
    {
        "schema_version", "journal_id", "operation_id", "plan_hash", "state", "state_history",
        "last_completed_action", "recovery_actions", "updated_at",
    }
)
LEGACY_RESIDUE_RELATIVE = Path("state") / "legacy_residue.json"
PLAN_ALGORITHM = "SHA256-UTF8-CANONICAL-JSON-v1-EXCLUDING-plan_hash"
ARTIFACT_ALGORITHM = "MALTS-IMMUTABLE-ARTIFACT-v1"
PUBLIC_REPOSITORY_PROFILE = "MALTS-USER-PAYLOAD-PLUS-REPOSITORY-ONLY-v1"
REPOSITORY_IDENTITY_NAME = "MALTS_RELEASE.json"
REPOSITORY_IDENTITY_SCHEMA_VERSION = 1
REPOSITORY_CI_WORKFLOW = ".github/workflows/ci.yml"
REPOSITORY_IDENTITY_REPOSITORY_ONLY = (
    ".gitattributes",
    REPOSITORY_CI_WORKFLOW,
    ".gitignore",
    REPOSITORY_IDENTITY_NAME,
)
REPOSITORY_ARTIFACT_PROFILE = "MALTS-REPOSITORY-SOURCE-v1"
PLAN_ENVELOPE_VERSION = 1
WINDOWS_MAX_PATH = 259
ATOMIC_TEMP_PROBE = ".~00000000"
HASH_PATTERN = re.compile(r"^[A-Fa-f0-9]{64}$")
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SEMVER_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
STABLE_GENERATION_PATTERN = re.compile(r"^malts-v(?P<version>(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))$")
PREVIEW_GENERATION_PATTERN = re.compile(r"^malts-v(?P<version>(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))-preview\.(?P<sequence>[1-9][0-9]*)$")
LEGACY_GENERATION_PATTERN = re.compile(r"^malts-(?P<version>[0-9]+\.[0-9]+\.[0-9]+)-(?P<digest>[A-Fa-f0-9]{12})$")
MANAGED_START = "<!-- MALTS:BEGIN managed instruction -->"
MANAGED_END = "<!-- MALTS:END managed instruction -->"
ACTIVE_GENERATION_TOKEN = "{{MALTS_ACTIVE_GENERATION_ROOT}}"
GLOBAL_BOOT_FILENAME = "GLOBAL_BOOT.md"
PREVIEW_MANIFEST_FILENAME = "preview_manifest.json"
PREVIEW_CONTRACT_VERSION = 1
GLOBAL_BOOT_POINTER_PATTERN = re.compile(
    r"(?ms)(^Resolved `MALTS_ROOT` on this machine:\s*\r?\n\s*```text\s*\r?\n)(.+?)(\r?\n\s*```)",
)
GLOBAL_BOOT_UNINSTALLED = "UNINSTALLED — no active MALTS generation; reinstall MALTS before use."
SECRET_PATTERN = re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S+")
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
STATES = ("DISCOVER", "LOCK", "PLAN", "STAGE", "SNAPSHOT", "PREVALIDATE", "ACTIVATE", "POSTVALIDATE", "CLEAN", "COMMIT")
INSTALLED_GENERATION_METADATA = (
    "artifact_identity.json",
    "generation_manifest.json",
    "release_identity.json",
)
INSTALLED_RELEASE_IDENTITY_SCHEMA_VERSION = 2
INSTALLED_RELEASE_IDENTITY_FIELDS = {
    "schema_version",
    "source_kind",
    "release_id",
    "release_manifest_sha256",
    "release_package_sha256",
    "artifact_sha256",
    "generation_id",
    "generation_manifest_sha256",
}
LEGACY_INSTALLED_RELEASE_IDENTITY_FIELDS = {
    "release_root",
    "release_id",
    "release_manifest_sha256",
    "release_package_sha256",
    "artifact_sha256",
    "generation_id",
    "generation_manifest_sha256",
}
INSTALLED_RELEASE_SOURCE_KINDS = {"release-package", "repository"}
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


def build_generation_id(version: str, *, preview_sequence: int | None = None) -> str:
    """Return the one canonical human-readable generation identity."""
    if not isinstance(version, str) or SEMVER_PATTERN.fullmatch(version) is None:
        raise LifecycleError("TX_GENERATION_VERSION", "Generation version must be canonical major.minor.patch SemVer text.")
    if preview_sequence is None:
        return f"malts-v{version}"
    if isinstance(preview_sequence, bool) or not isinstance(preview_sequence, int) or preview_sequence < 1:
        raise LifecycleError("TX_PREVIEW_SEQUENCE", "Preview sequence must be a positive integer.")
    return f"malts-v{version}-preview.{preview_sequence}"


def classify_generation_id(generation_id: str, *, expected_version: str | None = None) -> dict[str, Any]:
    """Classify stable, preview, and readable legacy hash-suffix identities."""
    if not isinstance(generation_id, str):
        raise LifecycleError("TX_GENERATION_ID", "generation_id must be text.")
    stable = STABLE_GENERATION_PATTERN.fullmatch(generation_id)
    preview = PREVIEW_GENERATION_PATTERN.fullmatch(generation_id)
    legacy = LEGACY_GENERATION_PATTERN.fullmatch(generation_id)
    if stable is not None:
        result: dict[str, Any] = {"kind": "stable", "version": stable.group("version"), "preview_sequence": None}
    elif preview is not None:
        result = {
            "kind": "preview",
            "version": preview.group("version"),
            "preview_sequence": int(preview.group("sequence")),
        }
    elif legacy is not None:
        result = {"kind": "legacy-hash", "version": legacy.group("version"), "preview_sequence": None}
    else:
        result = {"kind": "legacy-opaque", "version": expected_version, "preview_sequence": None}
    if expected_version is not None and result["version"] != expected_version:
        raise LifecycleError(
            "TX_GENERATION_ID_VERSION",
            "generation_id does not bind the declared version.",
            generation_id,
        )
    return result


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
    _assert_no_hardlink(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep the same-directory atomic temporary name shorter than typical target
    # file names. This prevents the safety wrapper itself from crossing the
    # traditional Win32 260-character boundary for otherwise valid targets.
    temporary = path.parent / f".~{uuid.uuid4().hex[:8]}"
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


def _read_discovery_file(path_value: str | Path, surface: str) -> tuple[Path, str]:
    raw = Path(path_value)
    if not raw.is_absolute():
        raise LifecycleError(f"DISCOVERY_{surface}_PATH", f"{surface} locator must be absolute.", str(raw))
    path = _absolute(raw)
    if not path.exists():
        raise LifecycleError(f"DISCOVERY_{surface}_MISSING", f"{surface} file is missing.", str(path))
    if not path.is_file() or _is_reparse(path):
        raise LifecycleError(f"DISCOVERY_{surface}_TYPE", f"{surface} must be a regular non-reparse file.", str(path))
    try:
        return path, path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise LifecycleError(f"DISCOVERY_{surface}_ENCODING", f"{surface} must be readable valid UTF-8.", str(path)) from exc


def parse_tool_boot(path_value: str | Path) -> dict[str, Any]:
    """Parse the strict tool-adjacent MALTS_BOOT.md discovery schema."""
    path, text = _read_discovery_file(path_value, "TOOL_BOOT")
    matches = re.findall(r"(?m)^MALTS_ROOT:[ \t]*(.+?)[ \t]*\r?$", text)
    if len(matches) != 1:
        raise LifecycleError(
            "DISCOVERY_TOOL_BOOT_FORMAT",
            "Tool MALTS_BOOT.md must contain exactly one MALTS_ROOT: line.",
            str(path),
        )
    target_text = matches[0].strip()
    target = Path(target_text)
    if not target.is_absolute() or "\n" in target_text or "\r" in target_text:
        raise LifecycleError(
            "DISCOVERY_TOOL_BOOT_TARGET",
            "Tool MALTS_ROOT must be one absolute path.",
            str(path),
        )
    return {
        "schema": "tool-local-malts-boot-v1",
        "boot_path": str(path),
        "malts_root": str(_absolute(target)),
        "sha256": file_sha256(path),
    }


def parse_global_boot(path_value: str | Path) -> dict[str, Any]:
    """Parse the separate machine-global/recovery GLOBAL_BOOT.md schema."""
    path, text = _read_discovery_file(path_value, "GLOBAL_BOOT")
    matches = list(GLOBAL_BOOT_POINTER_PATTERN.finditer(text))
    if len(matches) != 1:
        raise LifecycleError(
            "DISCOVERY_GLOBAL_BOOT_FORMAT",
            "GLOBAL_BOOT.md must contain exactly one resolved MALTS_ROOT fenced block.",
            str(path),
        )
    target_text = matches[0].group(2).strip()
    if target_text == GLOBAL_BOOT_UNINSTALLED:
        return {
            "schema": "machine-global-malts-boot-v1",
            "boot_path": str(path),
            "state": "UNINSTALLED",
            "malts_root": None,
            "sha256": file_sha256(path),
        }
    target = Path(target_text)
    if not target.is_absolute() or "\n" in target_text or "\r" in target_text:
        raise LifecycleError(
            "DISCOVERY_GLOBAL_BOOT_TARGET",
            "Resolved GLOBAL_BOOT MALTS_ROOT must be one absolute path or the canonical UNINSTALLED marker.",
            str(path),
        )
    return {
        "schema": "machine-global-malts-boot-v1",
        "boot_path": str(path),
        "state": "ACTIVE",
        "malts_root": str(_absolute(target)),
        "sha256": file_sha256(path),
    }


def _same_locator(left: str | Path, right: str | Path) -> bool:
    return os.path.normcase(str(_absolute(left))) == os.path.normcase(str(_absolute(right)))


def resolve_discovery(
    tool_root_value: str | Path,
    *,
    lifecycle_root: str | Path | None = None,
    global_boot: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve ordinary startup from tool-local boot and fail closed on split brain."""
    raw_tool_root = Path(tool_root_value)
    if not raw_tool_root.is_absolute():
        raise LifecycleError("DISCOVERY_TOOL_ROOT_PATH", "Tool root must be absolute.", str(raw_tool_root))
    tool_root = _absolute(raw_tool_root)
    if not tool_root.is_dir() or _is_reparse(tool_root):
        raise LifecycleError("DISCOVERY_TOOL_ROOT_TYPE", "Tool root must be a regular non-reparse directory.", str(tool_root))
    tool_boot = parse_tool_boot(tool_root / "MALTS_BOOT.md")
    active_root = Path(tool_boot["malts_root"])

    if lifecycle_root is None:
        if active_root.parent.name.casefold() != "generations" or active_root.name in {"", ".", ".."}:
            raise LifecycleError(
                "DISCOVERY_LIFECYCLE_DERIVATION",
                "Tool MALTS_ROOT must use the exact <lifecycle>/generations/<generation-id> layout when lifecycle root is omitted.",
                str(active_root),
            )
        root = _absolute(active_root.parent.parent)
    else:
        raw_root = Path(lifecycle_root)
        if not raw_root.is_absolute():
            raise LifecycleError("DISCOVERY_LIFECYCLE_PATH", "Lifecycle root must be absolute.", str(raw_root))
        root = _absolute(raw_root)
    if not root.is_dir() or _is_reparse(root):
        raise LifecycleError("DISCOVERY_LIFECYCLE_TYPE", "Lifecycle root must be a regular non-reparse directory.", str(root))

    expected_layout_root = root / "generations" / active_root.name
    if not _same_locator(active_root, expected_layout_root):
        raise LifecycleError(
            "DISCOVERY_TOOL_BOOT_MISMATCH",
            "Tool MALTS_ROOT does not belong to the selected lifecycle generations directory.",
            str(active_root),
        )
    if not active_root.is_dir() or _is_reparse(active_root):
        raise LifecycleError("DISCOVERY_ACTIVE_ROOT_TYPE", "Active MALTS_ROOT must be a regular non-reparse directory.", str(active_root))

    try:
        registry = _load_registry(root)
    except LifecycleError as exc:
        code = "DISCOVERY_REGISTRY_ACTIVE_MISMATCH" if "INST_ACTIVE_REFERENCE" in exc.message else "DISCOVERY_REGISTRY_INVALID"
        raise LifecycleError(code, exc.message, str(_registry_path(root))) from exc
    if registry is None:
        raise LifecycleError("DISCOVERY_REGISTRY_MISSING", "Installation registry is missing.", str(_registry_path(root)))
    active_records = [item for item in registry["generations"] if item["state"] == "active"]
    if registry["lifecycle_state"] != "stable" or len(active_records) != 1:
        raise LifecycleError(
            "DISCOVERY_REGISTRY_STATE",
            "Discovery requires one stable active registry generation.",
            str(_registry_path(root)),
        )
    active = active_records[0]
    if registry["active_generation_id"] != active["generation_id"]:
        raise LifecycleError(
            "DISCOVERY_REGISTRY_ACTIVE_MISMATCH",
            "Registry active_generation_id does not match its sole active record.",
            str(_registry_path(root)),
        )
    if active["generation_id"] != active_root.name or not _same_locator(active["root"], active_root):
        raise LifecycleError(
            "DISCOVERY_REGISTRY_ROOT_MISMATCH",
            "Tool boot and active registry record resolve to different generations.",
            str(_registry_path(root)),
        )

    version_path, version_text = _read_discovery_file(active_root / "VERSION", "VERSION")
    version = version_text.strip()
    if SEMVER_PATTERN.fullmatch(version) is None or active.get("version") != version:
        raise LifecycleError("DISCOVERY_VERSION_MISMATCH", "VERSION does not match the active registry version.", str(version_path))
    try:
        classify_generation_id(active["generation_id"], expected_version=version)
    except LifecycleError as exc:
        raise LifecycleError("DISCOVERY_VERSION_MISMATCH", "Generation ID does not bind the active VERSION.", str(version_path)) from exc

    pointer_path = _pointer_path(root)
    if not pointer_path.is_file() or _is_reparse(pointer_path):
        raise LifecycleError("DISCOVERY_POINTER_MISSING", "Active generation pointer is missing or untrusted.", str(pointer_path))
    try:
        pointer = load_json(pointer_path)
    except LifecycleError as exc:
        raise LifecycleError("DISCOVERY_POINTER_INVALID", exc.message, str(pointer_path)) from exc
    expected_pointer = {
        "schema_version": 1,
        "generation_id": active["generation_id"],
        "version": active["version"],
        "root": str(active_root),
        "artifact_sha256": active["artifact_sha256"],
        "release_id": active["release_id"],
        "release_manifest_sha256": active["release_manifest_sha256"],
        "release_package_sha256": active["release_package_sha256"],
        "generation_manifest_sha256": active["generation_manifest_sha256"],
    }
    if not isinstance(pointer, dict) or canonical_json(pointer) != canonical_json(expected_pointer):
        raise LifecycleError("DISCOVERY_POINTER_MISMATCH", "Active pointer does not exactly match the active registry record.", str(pointer_path))

    # v1.1.1: the machine-global GLOBAL_BOOT.md is no longer a product surface.
    # Ordinary startup never probes a default path beside the lifecycle root;
    # the tool-local MALTS_BOOT.md plus registry/pointer/VERSION are the
    # complete discovery authority. An explicit --global-boot path remains
    # supported as an optional maintainer cross-check only.
    if global_boot is not None:
        global_path = Path(global_boot)
        if not global_path.is_absolute():
            raise LifecycleError("DISCOVERY_GLOBAL_BOOT_PATH", "Explicit GLOBAL_BOOT path must be absolute.", str(global_path))
        if global_path.exists():
            global_result = parse_global_boot(global_path)
            if global_result["state"] != "ACTIVE" or not _same_locator(global_result["malts_root"], active_root):
                raise LifecycleError(
                    "DISCOVERY_GLOBAL_BOOT_MISMATCH",
                    "GLOBAL_BOOT and tool-local discovery resolve to different lifecycle states or roots.",
                    str(global_path),
                )
            global_status = "MATCH"
        else:
            raise LifecycleError("DISCOVERY_GLOBAL_BOOT_MISSING", "Explicit GLOBAL_BOOT path is missing.", str(global_path))
    else:
        global_result = None
        global_status = "ABSENT_OPTIONAL"

    return {
        "status": "PASS",
        "mode": "READ_ONLY",
        "writes_performed": False,
        "authority": "tool-local-malts-boot",
        "tool_root": str(tool_root),
        "tool_boot": tool_boot,
        "lifecycle_root": str(root),
        "malts_root": str(active_root),
        "generation_id": active["generation_id"],
        "version": version,
        "artifact_sha256": active["artifact_sha256"],
        "cross_checks": {
            "registry": "MATCH",
            "active_pointer": "MATCH",
            "version": "MATCH",
            "global_boot": global_status,
        },
        "global_boot": global_result,
    }


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


def _assert_no_hardlink(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return
    try:
        if path.stat().st_nlink > 1:
            raise LifecycleError("TX_HARDLINK", "Hardlinks are forbidden on managed lifecycle paths.", str(path))
    except OSError as exc:
        raise LifecycleError("TX_PATH_STAT", "Cannot inspect managed lifecycle path link count.", str(path)) from exc


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
    _assert_no_hardlink(target)
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


def _absolute_preview_root(value: str | Path | None) -> Path:
    if value is None:
        raise LifecycleError(
            "TX_PREVIEW_ROOT_REQUIRED",
            "Isolated preview requires an explicit absolute preview root.",
        )
    raw = Path(str(value))
    if not raw.is_absolute():
        raise LifecycleError(
            "TX_PREVIEW_ROOT_REQUIRED",
            "Isolated preview requires an explicit absolute preview root.",
            str(raw),
        )
    root = _absolute(raw)
    if root.parent == root:
        raise LifecycleError("TX_PREVIEW_ROOT_UNSAFE", "A drive or filesystem root cannot be used as a preview root.", str(root))
    for candidate in reversed((root, *root.parents)):
        if candidate.exists() and _is_reparse(candidate):
            raise LifecycleError("TX_PREVIEW_ROOT_REPARSE", "Preview roots cannot traverse a reparse point.", str(candidate))
    return root


def preview_tool_environment(
    preview_root_value: str | Path | None,
    tool: str,
    *,
    supported: bool = True,
) -> dict[str, Any]:
    """Return a process-local, preview-contained environment for one tool."""
    preview_root = _absolute_preview_root(preview_root_value)
    if tool not in TOOLS:
        raise LifecycleError("TX_TOOL_ROOTS", "Tool root key is unsupported.", tool)
    if not supported:
        raise LifecycleError(
            "TX_PREVIEW_TOOL_ISOLATION_UNSUPPORTED",
            f"{tool} cannot be launched with a provably isolated configuration root.",
            str(preview_root),
        )
    tool_root = preview_root / "tools" / tool
    home_root = preview_root / "home" / tool
    temp_root = preview_root / "runtime" / "tool-temp" / tool
    environment = {
        "HOME": str(home_root),
        "USERPROFILE": str(home_root),
        "APPDATA": str(home_root / "AppData" / "Roaming"),
        "LOCALAPPDATA": str(home_root / "AppData" / "Local"),
        "TEMP": str(temp_root),
        "TMP": str(temp_root),
        "MALTS_PREVIEW_ROOT": str(preview_root),
        "MALTS_PREVIEW_DISCOVERY_ROOT": str(tool_root),
        "MALTS_PREVIEW_GLOBAL_BOOT": str(preview_root / GLOBAL_BOOT_FILENAME),
    }
    writable_roots = [home_root, temp_root, tool_root]
    if tool == "codex":
        environment["CODEX_HOME"] = str(tool_root)
    elif tool == "claude-code":
        environment["CLAUDE_CONFIG_DIR"] = str(tool_root)
    else:
        xdg_data = preview_root / "state" / "opencode" / "data"
        xdg_cache = preview_root / "state" / "opencode" / "cache"
        environment.update(
            {
                "XDG_CONFIG_HOME": str(tool_root.parent),
                "XDG_DATA_HOME": str(xdg_data),
                "XDG_CACHE_HOME": str(xdg_cache),
            }
        )
        writable_roots.extend((xdg_data, xdg_cache))
    if any(not _is_inside(preview_root, path) for path in writable_roots):
        raise LifecycleError("TX_PREVIEW_ROOT_ESCAPE", "A tool isolation root escapes the preview boundary.", str(preview_root))
    return {
        "schema_version": PREVIEW_CONTRACT_VERSION,
        "tool": tool,
        "preview_root": str(preview_root),
        "discovery_root": str(tool_root),
        "global_boot": str(preview_root / GLOBAL_BOOT_FILENAME),
        "environment": environment,
        "writable_roots": [str(path) for path in dict.fromkeys(writable_roots)],
    }


def capture_surface_invariants(surfaces: dict[str, str | Path]) -> dict[str, Any]:
    """Capture a deterministic read-only digest manifest for protected surfaces."""
    if not isinstance(surfaces, dict) or not surfaces:
        raise LifecycleError("TX_INVARIANT_SURFACES", "Invariant capture requires a non-empty keyed surface mapping.")
    records: list[dict[str, Any]] = []
    for name in sorted(surfaces, key=str.casefold):
        if not isinstance(name, str) or not ID_PATTERN.fullmatch(name):
            raise LifecycleError("TX_INVARIANT_SURFACES", "Invariant surface names must be canonical IDs.", str(name))
        raw = Path(str(surfaces[name]))
        if not raw.is_absolute():
            raise LifecycleError("TX_INVARIANT_SURFACES", "Invariant surface paths must be absolute.", str(raw))
        path = _absolute(raw)
        reparse = path.exists() and _is_reparse(path)
        if not path.exists():
            kind = "missing"
            digest = "MISSING"
        elif reparse:
            kind = "reparse"
            digest = "UNTRUSTED"
        elif path.is_file():
            kind = "file"
            digest = file_sha256(path)
        elif path.is_dir():
            kind = "directory"
            digest = _path_digest(path)
        else:
            kind = "other"
            digest = "UNSUPPORTED"
        records.append(
            {"name": name, "path": str(path), "kind": kind, "reparse": reparse, "sha256": digest}
        )
    return {
        "schema_version": 1,
        "algorithm": "MALTS-PROTECTED-SURFACE-INVARIANTS-v1",
        "surfaces": records,
        "manifest_sha256": sha256_bytes(canonical_json(records)),
    }


def compare_surface_invariants(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_records = {item["name"]: item for item in before.get("surfaces", [])}
    after_records = {item["name"]: item for item in after.get("surfaces", [])}
    names = sorted(set(before_records) | set(after_records), key=str.casefold)
    changed = [name for name in names if before_records.get(name) != after_records.get(name)]
    return {
        "status": "PASS" if not changed else "FAIL",
        "writes_performed": False,
        "before_manifest_sha256": before.get("manifest_sha256"),
        "after_manifest_sha256": after.get("manifest_sha256"),
        "changed": changed,
    }


def _global_boot_context(root: Path) -> dict[str, Any]:
    """Describe machine-global boot state for a lifecycle transaction.

    v1.1.1: MALTS no longer creates, refreshes, verifies, or deletes a
    machine-global GLOBAL_BOOT.md. A pre-existing user-owned file beside the
    lifecycle root is left untouched and is never a transaction target.
    """
    return {"mode": "absent", "locator": None, "sha256": "NOT_CONFIGURED"}


def _refresh_global_boot(context: dict[str, Any], active_generation_root: Path | None, operation: str) -> None:
    if context["mode"] == "absent":
        return
    if operation != "uninstall" and active_generation_root is None:
        raise LifecycleError("TX_GLOBAL_BOOT_TARGET", "Global boot refresh requires an active generation.", context["locator"])
    path = Path(context["locator"])
    payload = path.read_bytes()
    bom = payload.startswith(b"\xef\xbb\xbf")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise LifecycleError("TX_GLOBAL_BOOT_ENCODING", "Configured global boot must be valid UTF-8.", str(path)) from exc
    matches = list(GLOBAL_BOOT_POINTER_PATTERN.finditer(text))
    if len(matches) != 1:
        raise LifecycleError("TX_GLOBAL_BOOT_FORMAT", "Configured global boot must contain exactly one resolved MALTS_ROOT text block.", str(path))
    match = matches[0]
    target = GLOBAL_BOOT_UNINSTALLED if operation == "uninstall" else str(_absolute(active_generation_root))
    replacement = f"{match.group(1)}{target}{match.group(3)}"
    refreshed = text[:match.start()] + replacement + text[match.end():]
    encoded = refreshed.encode("utf-8")
    _atomic_write(path, (b"\xef\xbb\xbf" + encoded) if bom else encoded)


def _verify_global_boot(context: dict[str, Any], active_generation_root: Path | None, operation: str) -> None:
    if context["mode"] == "absent":
        return
    if operation != "uninstall" and active_generation_root is None:
        raise LifecycleError("TX_GLOBAL_BOOT_TARGET", "Global boot verification requires an active generation.", context["locator"])
    path = Path(context["locator"])
    actual = _global_boot_context(_absolute(path).parent / "lifecycle")
    if actual["mode"] != "refresh" or actual["locator"] != context["locator"]:
        raise LifecycleError("TX_GLOBAL_BOOT_VERIFY", "Configured global boot disappeared or changed type during activation.", str(path))
    text = path.read_text(encoding="utf-8-sig")
    match = GLOBAL_BOOT_POINTER_PATTERN.search(text)
    expected = GLOBAL_BOOT_UNINSTALLED if operation == "uninstall" else str(_absolute(active_generation_root))
    if match is None or match.group(2).strip() != expected:
        raise LifecycleError("TX_GLOBAL_BOOT_VERIFY", "Configured global boot does not resolve to the active generation.", str(path))


def _preview_manifest_value(context: dict[str, Any], active_generation_root: Path) -> dict[str, Any]:
    contract = context["preview_contract"]
    return {
        "schema_version": PREVIEW_CONTRACT_VERSION,
        "mode": "isolated-maintainer-preview",
        "preview_root": contract["preview_root"],
        "lifecycle_root": context["lifecycle_root"],
        "generation_id": context["target_generation_id"],
        "version": context["target_version"],
        "generation_root": str(active_generation_root),
        "global_boot": contract["global_boot"],
        "tool_isolation": contract["tool_isolation"],
        "real_tool_integration": "PENDING",
        "release_qualification": "PREVIEW_ONLY",
    }


def _write_preview_surfaces(context: dict[str, Any], active_generation_root: Path | None) -> None:
    contract = context.get("preview_contract")
    if contract is None:
        return
    if active_generation_root is None:
        raise LifecycleError("TX_PREVIEW_TARGET", "Preview activation requires an active generation root.")
    preview_root = _absolute_preview_root(contract["preview_root"])
    for tool in context["selected_tools"]:
        for raw_root in contract["tool_isolation"][tool]["writable_roots"]:
            writable_root = Path(raw_root)
            if not _is_inside(preview_root, writable_root):
                raise LifecycleError("TX_PREVIEW_ROOT_ESCAPE", "Preview writable root escapes isolation.", str(writable_root))
            _assert_no_reparse(preview_root, writable_root)
            writable_root.mkdir(parents=True, exist_ok=True)
    boot_path = Path(contract["global_boot"])
    manifest_path = Path(contract["manifest"])
    if boot_path.exists() or manifest_path.exists():
        raise LifecycleError("TX_PREVIEW_SURFACE_COLLISION", "Preview boot or manifest already exists.", str(preview_root))
    boot_text = (
        "# MALTS Isolated Maintainer Preview\n\n"
        "This boot is confined to the explicit preview root and is never a global precedence source.\n\n"
        "Resolved `MALTS_ROOT` on this machine:\n\n"
        "```text\n"
        f"{active_generation_root}\n"
        "```\n\n"
        f"Preview root: `{preview_root}`\n"
    )
    _atomic_write(boot_path, boot_text.encode("utf-8"))
    write_json(manifest_path, _preview_manifest_value(context, active_generation_root))


def _verify_preview_surfaces(context: dict[str, Any], active_generation_root: Path | None) -> None:
    contract = context.get("preview_contract")
    if contract is None:
        return
    if active_generation_root is None:
        raise LifecycleError("TX_PREVIEW_TARGET", "Preview verification requires an active generation root.")
    boot_path = Path(contract["global_boot"])
    manifest_path = Path(contract["manifest"])
    if not boot_path.is_file() or _is_reparse(boot_path):
        raise LifecycleError("TX_PREVIEW_BOOT_VERIFY", "Preview boot is missing or untrusted.", str(boot_path))
    boot_text = boot_path.read_text(encoding="utf-8-sig")
    match = GLOBAL_BOOT_POINTER_PATTERN.search(boot_text)
    if match is None or match.group(2).strip() != str(active_generation_root):
        raise LifecycleError("TX_PREVIEW_BOOT_VERIFY", "Preview boot does not bind the active preview generation.", str(boot_path))
    if not manifest_path.is_file() or _is_reparse(manifest_path):
        raise LifecycleError("TX_PREVIEW_MANIFEST_VERIFY", "Preview manifest is missing or untrusted.", str(manifest_path))
    if canonical_json(load_json(manifest_path)) != canonical_json(_preview_manifest_value(context, active_generation_root)):
        raise LifecycleError("TX_PREVIEW_MANIFEST_VERIFY", "Preview manifest content drifted.", str(manifest_path))
    preview_root = Path(contract["preview_root"])
    for tool in context["selected_tools"]:
        isolation = contract["tool_isolation"][tool]
        if Path(context["tool_roots"][tool]) != Path(isolation["discovery_root"]):
            raise LifecycleError("TX_PREVIEW_TOOL_VERIFY", f"{tool} discovery root is not preview-contained.")
        for raw_root in isolation["writable_roots"]:
            writable_root = Path(raw_root)
            if not writable_root.is_dir() or _is_reparse(writable_root) or not _is_inside(preview_root, writable_root):
                raise LifecycleError("TX_PREVIEW_TOOL_VERIFY", f"{tool} writable root is missing or untrusted.", str(writable_root))


def _remove_managed(root: Path, path: Path) -> None:
    path = _absolute(path)
    _assert_no_reparse(root, path)
    if not path.exists():
        return
    if path.is_file():
        _assert_no_hardlink(path)
        path.unlink()
        return
    for item in sorted(path.rglob("*"), key=lambda entry: len(entry.parts), reverse=True):
        _assert_no_reparse(root, item)
        if item.is_file():
            _assert_no_hardlink(item)
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


def _verify_public_repository(manifest: dict[str, Any], user_records: list[dict[str, Any]], context: str) -> None:
    repository = manifest["public_repository"]
    repository_records = repository["repository_only_files"]
    if repository_records != sorted(repository_records, key=lambda item: item["path"].casefold()):
        raise LifecycleError("TX_PUBLIC_REPOSITORY_ORDER", "Repository-only records are not canonically ordered.", context)
    user_folded = {record["path"].casefold() for record in user_records}
    repository_folded: set[str] = set()
    for record in repository_records:
        relative = _validate_relative(record["path"])
        folded = relative.casefold()
        if folded in user_folded or folded in repository_folded:
            raise LifecycleError(
                "TX_PUBLIC_REPOSITORY_OVERLAP",
                "Repository-only paths must be unique and disjoint from the installed user payload.",
                relative,
            )
        repository_folded.add(folded)
    repository_tree = sha256_bytes(canonical_json(repository_records))
    if (
        repository["profile"] != PUBLIC_REPOSITORY_PROFILE
        or repository["repository_only_file_count"] != len(repository_records)
        or repository["repository_only_tree_sha256"].upper() != repository_tree
    ):
        raise LifecycleError("TX_PUBLIC_REPOSITORY_BINDING", "Repository-only summary does not bind its exact records.", context)
    public_records = sorted([*user_records, *repository_records], key=lambda item: item["path"].casefold())
    public_tree = sha256_bytes(canonical_json(public_records))
    if repository["file_count"] != len(public_records) or repository["tree_sha256"].upper() != public_tree:
        raise LifecycleError("TX_PUBLIC_REPOSITORY_BINDING", "Public repository summary does not bind its exact inventory.", context)


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
    user_records = _user_records(root / "lifecycle_artifact" / "payload")
    _verify_user_purity(generation, user_records, str(manifest_path))
    _verify_public_repository(manifest, user_records, str(manifest_path))
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
    if not isinstance(artifact_identity, dict) or set(artifact_identity) != artifact_fields:
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_CONTRACT",
            "artifact_identity.json must use the exact installed-generation identity shape.",
            str(root / "artifact_identity.json"),
        )
    if not isinstance(release_identity, dict):
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_CONTRACT",
            "release_identity.json must be an object.",
            str(root / "release_identity.json"),
        )
    release_identity_fields = set(release_identity)
    if release_identity_fields == INSTALLED_RELEASE_IDENTITY_FIELDS:
        if release_identity.get("schema_version") != INSTALLED_RELEASE_IDENTITY_SCHEMA_VERSION:
            raise LifecycleError(
                "TX_INSTALLED_ENVELOPE_CONTRACT",
                "Installed release identity schema_version is unsupported.",
                str(root / "release_identity.json"),
            )
        source_kind = release_identity.get("source_kind")
        if source_kind not in INSTALLED_RELEASE_SOURCE_KINDS:
            raise LifecycleError(
                "TX_INSTALLED_ENVELOPE_CONTRACT",
                "Installed release identity source_kind must be release-package or repository.",
                str(root / "release_identity.json"),
            )
        release_identity_schema_version = INSTALLED_RELEASE_IDENTITY_SCHEMA_VERSION
        release_identity_provenance = "redacted-v2"
    elif release_identity_fields == LEGACY_INSTALLED_RELEASE_IDENTITY_FIELDS:
        release_root = release_identity.get("release_root")
        if not isinstance(release_root, str) or not Path(release_root).is_absolute():
            raise LifecycleError(
                "TX_INSTALLED_ENVELOPE_CONTRACT",
                "Legacy installed release identity release_root must retain an absolute provenance locator.",
                str(root / "release_identity.json"),
            )
        release_identity_schema_version = 1
        release_identity_provenance = "legacy-absolute-root"
    else:
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_CONTRACT",
            "release_identity.json must use either the legacy v1 or redacted v2 installed-generation identity shape.",
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
        "release_identity_schema_version": release_identity_schema_version,
        "release_identity_provenance": release_identity_provenance,
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


def verify_repository_root(root_value: str | Path) -> dict[str, Any]:
    """Verify a public repository as an installable MALTS source.

    Repository mode deliberately validates only the user tree plus the small
    repository identity document.  Local release controls, Git internals, and
    maintainer tooling are neither required nor accepted as install inputs.
    """
    root = _absolute(root_value)
    if not root.is_dir() or _is_reparse(root):
        raise LifecycleError("TX_REPOSITORY_ROOT", "Repository root is missing or is a reparse point.", str(root))
    identity_path = root / REPOSITORY_IDENTITY_NAME
    if not identity_path.is_file() or _is_reparse(identity_path):
        raise LifecycleError("TX_REPOSITORY_IDENTITY", "Repository identity file is missing or is a reparse point.", str(identity_path))
    identity = load_json(identity_path)
    expected_fields = {
        "schema_version",
        "release_id",
        "version",
        "release_tag",
        "source_tree_sha256",
        "user_file_count",
        "repository_only_paths",
        "created_at",
    }
    if not isinstance(identity, dict) or set(identity) != expected_fields:
        raise LifecycleError("TX_REPOSITORY_IDENTITY", "Repository identity has an invalid closed shape.", str(identity_path))
    version = identity.get("version")
    release_id = identity.get("release_id")
    release_tag = identity.get("release_tag")
    if (
        identity.get("schema_version") != REPOSITORY_IDENTITY_SCHEMA_VERSION
        or not isinstance(version, str)
        or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None
        or release_id != f"MALTS-{version}"
        or release_tag != f"v{version}"
        or not isinstance(identity.get("user_file_count"), int)
        or identity["user_file_count"] < 1
        or not isinstance(identity.get("source_tree_sha256"), str)
        or HASH_PATTERN.fullmatch(identity["source_tree_sha256"]) is None
        or identity.get("repository_only_paths") != list(REPOSITORY_IDENTITY_REPOSITORY_ONLY)
    ):
        raise LifecycleError("TX_REPOSITORY_IDENTITY", "Repository identity has invalid version, hash, or boundary fields.", str(identity_path))
    created_at = _now(identity.get("created_at"))
    version_path = root / "VERSION"
    if not version_path.is_file() or version_path.read_text(encoding="utf-8-sig").strip() != version:
        raise LifecycleError("TX_REPOSITORY_VERSION", "Repository VERSION does not match its identity document.", str(version_path))

    for relative in REPOSITORY_IDENTITY_REPOSITORY_ONLY:
        path = root / relative
        if not path.is_file() or _is_reparse(path):
            raise LifecycleError("TX_REPOSITORY_LAYOUT", "Repository source lacks a required regular repository-only file.", str(path))

    excluded = {item.casefold() for item in REPOSITORY_IDENTITY_REPOSITORY_ONLY}
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix().casefold()):
        relative = _validate_relative(path.relative_to(root).as_posix())
        if relative.split("/", 1)[0].casefold() == ".git":
            continue
        # These ignored maintainer controls may live beside a public checkout,
        # but are never part of the repository install source.
        if relative == "AGENTS.md" or relative.startswith(".release-control/"):
            continue
        if relative.casefold() in excluded:
            continue
        if _is_reparse(path):
            raise LifecycleError("TX_REPOSITORY_REPARSE", "Repository source cannot contain links or reparse points.", relative)
        if path.suffix.casefold() == ".pyc" or "__pycache__" in {part.casefold() for part in Path(relative).parts}:
            raise LifecycleError("TX_REPOSITORY_CACHE", "Repository source cannot contain Python cache files.", relative)
        if any(part.casefold() == ".malts" for part in Path(relative).parts):
            raise LifecycleError("TX_REPOSITORY_RESIDUE", "Repository source cannot contain legacy .malts state.", relative)
        folded = relative.casefold()
        if folded in seen:
            raise LifecycleError("TX_REPOSITORY_CASE_COLLISION", "Repository paths collide under Windows case folding.", relative)
        seen.add(folded)
        records.append({"path": relative, "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    tree_sha256 = sha256_bytes(canonical_json(records))
    if identity["user_file_count"] != len(records) or identity["source_tree_sha256"].upper() != tree_sha256:
        raise LifecycleError(
            "TX_REPOSITORY_IDENTITY_BINDING",
            "Repository files do not match the identity document. Refresh from an exact released source or use a verified Release package.",
            str(identity_path),
        )
    required = ("scripts/Install-MALTS.ps1", "scripts/Update-MALTS.ps1", "tools/malts_lifecycle.py")
    missing = [relative for relative in required if relative not in {record["path"] for record in records}]
    if missing:
        raise LifecycleError("TX_REPOSITORY_LAYOUT", f"Repository install source lacks required entry points: {missing}", str(root))
    return {
        "root": root,
        "identity": {**identity, "created_at": created_at, "source_tree_sha256": tree_sha256},
        "identity_sha256": file_sha256(identity_path),
        "records": records,
    }


def _repository_projection_sources(source: Path, tool: str) -> list[tuple[str, str, str]]:
    instruction = {
        "codex": "adapters/codex/AGENTS.example.md",
        "claude-code": "adapters/claude-code/CLAUDE.example.md",
        "opencode": "adapters/opencode/AGENTS.example.md",
    }[tool]
    instruction_target = "CLAUDE.md" if tool == "claude-code" else "AGENTS.md"
    items: list[tuple[str, str, str]] = [(instruction, instruction_target, "managed-block")]
    support_root = {
        "codex": source / "adapters" / "codex" / ".codex",
        "claude-code": source / "adapters" / "claude-code" / ".claude",
        "opencode": source / "adapters" / "opencode" / ".opencode",
    }[tool]
    bridge_root = source / "adapters" / "skill-bridges"
    for root in (support_root, bridge_root):
        if not root.is_dir():
            raise LifecycleError("TX_REPOSITORY_LAYOUT", "Repository install source lacks required adapter files.", str(root))
    for path in sorted((item for item in support_root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(support_root).as_posix().casefold()):
        relative = path.relative_to(support_root).as_posix()
        if tool == "codex" and relative.casefold() == "config.toml":
            continue
        items.append((path.relative_to(source).as_posix(), relative, "replace"))
    for path in sorted((item for item in bridge_root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(bridge_root).as_posix().casefold()):
        relative = path.relative_to(bridge_root).as_posix()
        items.append((path.relative_to(source).as_posix(), f"skills/{relative}", "replace"))
    return items


def _build_repository_artifact(repository: dict[str, Any], artifact_root: Path) -> dict[str, Any]:
    """Materialize a deterministic, temporary lifecycle artifact from a verified repo."""
    source = repository["root"]
    identity = repository["identity"]
    if artifact_root.exists():
        raise LifecycleError("TX_REPOSITORY_ARTIFACT", "Temporary repository artifact path already exists.", str(artifact_root))
    payload = artifact_root / "payload"
    payload.mkdir(parents=True)
    for record in repository["records"]:
        relative = record["path"]
        destination = payload / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / Path(relative), destination)
    payload_records = _user_records(payload)
    if payload_records != repository["records"]:
        raise LifecycleError("TX_REPOSITORY_COPY_BINDING", "Repository payload changed while the lifecycle artifact was prepared.", str(source))

    for tool in TOOLS:
        projection_root = artifact_root / "projections" / tool
        entries: list[dict[str, Any]] = []
        seen: set[str] = set()
        for source_relative, target_relative, mode in _repository_projection_sources(source, tool):
            target = _validate_relative(target_relative)
            if target.casefold() in seen:
                raise LifecycleError("TX_REPOSITORY_PROJECTION", "Repository projection target is duplicated.", f"{tool}:{target}")
            seen.add(target.casefold())
            stored_relative = f"files/{target}"
            stored = projection_root / Path(stored_relative)
            stored.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / Path(source_relative), stored)
            entries.append({"path": target, "source": stored_relative, "mode": mode, "sha256": file_sha256(stored)})
        boot_relative = "files/MALTS_BOOT.template.md"
        boot_path = projection_root / Path(boot_relative)
        boot_path.parent.mkdir(parents=True, exist_ok=True)
        display = {"codex": "Codex", "claude-code": "Claude Code", "opencode": "OpenCode"}[tool]
        boot_path.write_text(
            "# MALTS_BOOT\n\n"
            "SchemaVersion: 2\n"
            f"Tool: {display}\n"
            f"MALTS_ROOT: {ACTIVE_GENERATION_TOKEN}\n"
            "Source: verified immutable MALTS active generation\n",
            encoding="utf-8",
            newline="\n",
        )
        entries.append({"path": "MALTS_BOOT.md", "source": boot_relative, "mode": "boot-pointer", "sha256": file_sha256(boot_path)})
        entries.sort(key=lambda item: item["path"].casefold())
        write_json(projection_root / "projection_files.json", {"schema_version": 1, "tool": tool, "entries": entries})

    records = _inventory_records(artifact_root)
    inventory = {"schema_version": 1, "files": records}
    write_json(artifact_root / "package_inventory.json", inventory)
    inventory_sha256 = file_sha256(artifact_root / "package_inventory.json")
    package_tree_sha256 = sha256_bytes(canonical_json(records))
    version = identity["version"]
    artifact_sha256 = artifact_digest(version, inventory_sha256, package_tree_sha256)
    manifest = {
        "schema_version": 2,
        "generation_id": build_generation_id(version),
        "version": version,
        "artifact_sha256": artifact_sha256,
        "source_revision": f"local-tree-sha256:{identity['source_tree_sha256']}",
        "package_tree_sha256": package_tree_sha256,
        "package_inventory_sha256": inventory_sha256,
        "supported_platforms": ["windows"],
        "supported_tools": list(TOOLS),
        "migration_handlers": ["A", "B", "C", "D"],
        "minimum_prerequisites": [
            {"name": "Windows", "version_constraint": "10-or-later", "required": True, "applicability": "always"},
            {"name": "PowerShell", "version_constraint": ">=5.1", "required": True, "applicability": "always"},
            {"name": "Python", "version_constraint": ">=3.11", "required": True, "applicability": "always"},
            {"name": "Codex", "version_constraint": "runtime-probed", "required": True, "applicability": "selected-tool", "tool": "codex"},
            {"name": "Claude Code", "version_constraint": "runtime-probed", "required": True, "applicability": "selected-tool", "tool": "claude-code"},
            {"name": "OpenCode", "version_constraint": "runtime-probed", "required": True, "applicability": "selected-tool", "tool": "opencode"},
        ],
        "projection_classification": {
            "public_contract_paths": ["payload/*", "projections/*"],
            "generated_state_paths": [
                "registry/installation_registry.json",
                "registry/active_generation.json",
                "runtime/transactions/*",
                "state/audit/*",
                "<tool-root>/.malts-v1-projection.json",
            ],
        },
        "user_purity": {
            "policy_id": "MALTS-REPOSITORY-IDENTITY-V1",
            "policy_sha256": repository["identity_sha256"],
            "file_count": len(repository["records"]),
            "tree_sha256": identity["source_tree_sha256"],
            "identity_release_status": "REPOSITORY_VERIFIED",
        },
        "created_at": identity["created_at"],
    }
    _validate_contract("generation-manifest", manifest)
    write_json(artifact_root / "generation_manifest.json", manifest)
    return verify_artifact(artifact_root)


def _repository_release_identity(repository: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    identity_sha256 = repository["identity_sha256"]
    package_sha256 = sha256_bytes(canonical_json({
        "algorithm": REPOSITORY_ARTIFACT_PROFILE,
        "repository_identity_sha256": identity_sha256,
        "source_tree_sha256": repository["identity"]["source_tree_sha256"],
    }))
    return {
        "release_root": str(repository["root"]),
        "release_id": repository["identity"]["release_id"],
        "release_manifest_sha256": identity_sha256,
        "release_package_sha256": package_sha256,
        "artifact_sha256": artifact["artifact_sha256"],
        "generation_id": artifact["manifest"]["generation_id"],
        "generation_manifest_sha256": file_sha256(artifact["root"] / "generation_manifest.json"),
    }


@contextmanager
def _source_artifact_scope(
    *,
    release_root: str | Path | None = None,
    repository_root: str | Path | None = None,
) -> Iterable[dict[str, Any] | None]:
    if release_root is not None and repository_root is not None:
        raise LifecycleError("TX_SOURCE_INPUT", "Choose exactly one ReleaseRoot or RepositoryRoot.")
    if release_root is not None:
        yield verify_release_root(release_root)
        return
    if repository_root is None:
        yield None
        return
    repository = verify_repository_root(repository_root)
    with tempfile.TemporaryDirectory(prefix="malts-repository-artifact-") as temporary:
        artifact = _build_repository_artifact(repository, Path(temporary) / "artifact")
        yield {
            "root": repository["root"],
            "manifest": repository["identity"],
            "artifact": artifact,
            "identity": _repository_release_identity(repository, artifact),
            "verified": {
                "status": "PASS",
                "release_id": repository["identity"]["release_id"],
                "version": repository["identity"]["version"],
                "source_kind": "repository",
            },
        }


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


def _managed_block_sha256(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise LifecycleError("TX_MANAGED_MARKER", "Managed instruction projection is not valid UTF-8.") from exc
    starts = text.count(MANAGED_START)
    ends = text.count(MANAGED_END)
    if starts != 1 or ends != 1 or text.index(MANAGED_START) > text.index(MANAGED_END):
        raise LifecycleError("TX_MANAGED_MARKER", "Managed instruction markers are incomplete or duplicated.")
    start = text.index(MANAGED_START)
    end = text.index(MANAGED_END) + len(MANAGED_END)
    block = text[start:end].replace("\r\n", "\n").replace("\r", "\n")
    return sha256_bytes((block + "\n").encode("utf-8"))


def _legacy_managed_block_sha256(
    registry: dict[str, Any] | None,
    source_sha256: str,
    cache: dict[str, str | None],
) -> str | None:
    key = source_sha256.upper()
    if key in cache:
        return cache[key]
    cache[key] = None
    if registry is None:
        return None
    active = next((item for item in registry["generations"] if item["state"] == "active"), None)
    if active is None:
        return None
    generation_root = Path(active["root"])
    if not generation_root.is_dir():
        return None
    for candidate in sorted(
        (path for path in generation_root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(generation_root).as_posix().casefold(),
    ):
        if file_sha256(candidate).upper() != key:
            continue
        try:
            cache[key] = _managed_block_sha256(candidate.read_bytes())
        except LifecycleError:
            continue
        break
    return cache[key]


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
        return Path(parse_tool_boot(path)["malts_root"])
    except LifecycleError as exc:
        raise LifecycleError("MG_BOOT_POINTER_INVALID", exc.message, str(path)) from exc


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


GENERATION_BINDING_FIELDS = (
    "release_id",
    "release_manifest_sha256",
    "release_package_sha256",
    "artifact_sha256",
    "generation_id",
    "generation_manifest_sha256",
)


def _active_generation_record(registry: dict[str, Any] | None) -> dict[str, Any] | None:
    if registry is None:
        return None
    active = [item for item in registry["generations"] if item["state"] == "active"]
    return active[0] if len(active) == 1 else None


def _binding_matches(active: dict[str, Any], release_identity: dict[str, Any]) -> bool:
    return all(active.get(field) == release_identity.get(field) for field in GENERATION_BINDING_FIELDS)


def _expected_pointer(context: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generation_id": context["target_generation_id"],
        "version": context["target_version"],
        "root": context["generation_root"],
        "artifact_sha256": artifact["artifact_sha256"],
        "release_id": context["release_identity"]["release_id"],
        "release_manifest_sha256": context["release_identity"]["release_manifest_sha256"],
        "release_package_sha256": context["release_identity"]["release_package_sha256"],
        "generation_manifest_sha256": context["release_identity"]["generation_manifest_sha256"],
    }


def _same_generation_disposition(
    *,
    root: Path,
    tool_roots: dict[str, Path],
    registry: dict[str, Any] | None,
    artifact: dict[str, Any],
    release_identity: dict[str, Any],
    source_kind: str,
    operation: str,
    global_boot: dict[str, Any],
) -> str:
    """Return EXECUTE/NO_OP or fail before any lifecycle write."""
    target_id = artifact["manifest"]["generation_id"]
    target = root / "generations" / target_id
    active = _active_generation_record(registry)
    registered = [] if registry is None else [
        item for item in registry["generations"]
        if item["generation_id"] == target_id or Path(item["root"]) == target
    ]

    if active is None or active["generation_id"] != target_id:
        if target.exists() or registered:
            raise LifecycleError(
                "TX_GENERATION_COLLISION",
                "The target generation name already exists without the exact active binding; it is preserved for recovery review.",
                str(target),
            )
        return "EXECUTE"

    if Path(active["root"]) != target or not _binding_matches(active, release_identity):
        raise LifecycleError(
            "TX_GENERATION_CONTENT_CONFLICT",
            "The stable generation ID is already bound to different release or artifact content; use a new version or preview sequence.",
            str(target),
        )
    if operation == "repair":
        return "EXECUTE"
    if operation != "update":
        return "EXECUTE"

    try:
        installed = verify_installed_generation_envelope(target)
        expected_installed_identity = _installed_release_identity(release_identity, source_kind)
        if installed["release_identity"] != expected_installed_identity:
            raise LifecycleError("TX_GENERATION_REPAIR_REQUIRED", "Installed release identity differs from its active binding.", str(target))
        if installed["artifact_identity"] != {
            "artifact_sha256": artifact["artifact_sha256"],
            "package_tree_sha256": artifact["manifest"]["package_tree_sha256"],
        }:
            raise LifecycleError("TX_GENERATION_REPAIR_REQUIRED", "Installed artifact identity differs from its active binding.", str(target))
        provisional = {
            "target_generation_id": target_id,
            "target_version": artifact["manifest"]["version"],
            "generation_root": str(target),
            "release_identity": release_identity,
        }
        pointer_path = _pointer_path(root)
        if not pointer_path.is_file() or load_json(pointer_path) != _expected_pointer(provisional, artifact):
            raise LifecycleError("TX_GENERATION_REPAIR_REQUIRED", "Active-generation pointer is missing or drifted.", str(pointer_path))
        if registry["lifecycle_state"] != "stable" or len(registry["generations"]) != 1:
            raise LifecycleError("TX_GENERATION_REPAIR_REQUIRED", "Registry is not in one-generation stable state.", str(_registry_path(root)))
        _verify_projections(artifact, tool_roots, "update")
        _verify_global_boot(global_boot, target, "update")
    except LifecycleError as exc:
        if exc.code == "TX_GENERATION_CONTENT_CONFLICT":
            raise
        raise LifecycleError(
            "TX_GENERATION_REPAIR_REQUIRED",
            "The same bound generation is not byte-for-byte healthy; create an explicit repair plan instead of updating in place.",
            exc.path or str(target),
        ) from exc
    return "NO_OP"


def _operation_actions(context_hash: str, context: dict[str, Any], operation: str) -> list[dict[str, Any]]:
    targets = context["tool_roots"]
    if context.get("plan_disposition") == "NO_OP":
        return [
            {"action_id": "ACT-CONTEXT", "kind": "verify", "target": f"context-sha256:{context_hash}", "dependencies": [], "destructive": False},
        ]
    actions = [
        {"action_id": "ACT-CONTEXT", "kind": "verify", "target": f"context-sha256:{context_hash}", "dependencies": [], "destructive": False},
        {"action_id": "ACT-STAGE", "kind": "copy" if operation != "uninstall" else "verify", "target": context["staging_root"], "dependencies": ["ACT-CONTEXT"], "destructive": False},
        {"action_id": "ACT-SNAPSHOT", "kind": "copy", "target": context["snapshot_root"], "dependencies": ["ACT-STAGE"], "destructive": False},
        {"action_id": "ACT-PREVALIDATE", "kind": "verify", "target": context["lifecycle_root"], "dependencies": ["ACT-SNAPSHOT"], "destructive": False},
        {"action_id": "ACT-ACTIVATE", "kind": "activate", "target": context.get("generation_root") or context["lifecycle_root"], "dependencies": ["ACT-PREVALIDATE"], "destructive": operation in {"update", "repair", "uninstall"}},
    ]
    previous = "ACT-ACTIVATE"
    if context["global_boot"]["mode"] == "refresh":
        actions.append(
            {
                "action_id": "ACT-GLOBAL-BOOT",
                "kind": "merge",
                "target": context["global_boot"]["locator"],
                "dependencies": [previous],
                "destructive": False,
            }
        )
        previous = "ACT-GLOBAL-BOOT"
    for index, tool in enumerate(targets, start=1):
        action_id = f"ACT-PROJECT-{index}"
        actions.append({"action_id": action_id, "kind": "merge", "target": targets[tool], "dependencies": [previous], "destructive": operation == "uninstall"})
        previous = action_id
    preview_contract = context.get("preview_contract")
    if preview_contract is not None:
        actions.append(
            {
                "action_id": "ACT-PREVIEW-BOOT",
                "kind": "create",
                "target": preview_contract["global_boot"],
                "dependencies": [previous],
                "destructive": False,
            }
        )
        actions.append(
            {
                "action_id": "ACT-PREVIEW-MANIFEST",
                "kind": "create",
                "target": preview_contract["manifest"],
                "dependencies": ["ACT-PREVIEW-BOOT"],
                "destructive": False,
            }
        )
        previous = "ACT-PREVIEW-MANIFEST"
    actions.append({"action_id": "ACT-POSTVALIDATE", "kind": "verify", "target": context["lifecycle_root"], "dependencies": [previous], "destructive": False})
    for index, locator in enumerate(context["expected_cleanup"], start=1):
        actions.append({"action_id": f"ACT-CLEAN-{index}", "kind": "delete", "target": locator, "dependencies": ["ACT-POSTVALIDATE"], "destructive": True})
    dependencies = ["ACT-POSTVALIDATE", *(f"ACT-CLEAN-{index}" for index in range(1, len(context["expected_cleanup"]) + 1))]
    actions.append({"action_id": "ACT-ZERO-RESIDUE", "kind": "verify", "target": context["lifecycle_root"], "dependencies": dependencies, "destructive": False})
    return actions


def _validate_planned_write_path_bounds(
    context: dict[str, Any],
    artifact: dict[str, Any] | None,
    modifications: list[dict[str, Any]],
) -> None:
    """Fail planning before writes if a Windows target exceeds the supported bound."""
    root = Path(context["lifecycle_root"])
    transaction_root = Path(context["transaction_root"])
    staging_root = Path(context["staging_root"])
    snapshot_root = Path(context["snapshot_root"])
    direct_targets: list[tuple[str, Path]] = [
        ("transaction root", transaction_root),
        ("staging root", staging_root),
        ("snapshot root", snapshot_root),
    ]
    atomic_targets: list[tuple[str, Path]] = [
        ("installation registry", root / REGISTRY_RELATIVE),
        ("active-generation pointer", root / POINTER_RELATIVE),
        ("lifecycle lock", root / LOCK_RELATIVE),
        ("transaction plan", _plan_path(transaction_root)),
        ("transaction journal", _journal_path(transaction_root)),
        ("snapshot metadata", snapshot_root / "snapshot_meta.json"),
        ("audit plan", root / AUDIT_RELATIVE / f"{context['operation_id']}.plan.json"),
        ("audit journal", root / AUDIT_RELATIVE / f"{context['operation_id']}.journal.json"),
    ]
    if context["global_boot"]["mode"] == "refresh":
        atomic_targets.append(("global discovery boot", Path(context["global_boot"]["locator"])))
    preview_contract = context.get("preview_contract")
    if preview_contract is not None:
        atomic_targets.extend(
            (
                ("preview discovery boot", Path(preview_contract["global_boot"])),
                ("preview isolation manifest", Path(preview_contract["manifest"])),
            )
        )
        for tool in context["selected_tools"]:
            for raw_root in preview_contract["tool_isolation"][tool]["writable_roots"]:
                direct_targets.append((f"{tool} preview writable root", Path(raw_root)))

    generation_root = Path(context["generation_root"]) if context["generation_root"] else None
    if artifact is not None and generation_root is not None:
        direct_targets.append(("generation root", generation_root))
        for record in artifact["records"]:
            if not record["path"].startswith("payload/"):
                continue
            relative = Path(record["path"][len("payload/") :])
            direct_targets.append(("staged user payload", staging_root / relative))
            direct_targets.append(("installed user payload", generation_root / relative))
        for name in INSTALLED_GENERATION_METADATA:
            atomic_targets.append(("staged generation metadata", staging_root / name))
            atomic_targets.append(("installed generation metadata", generation_root / name))
        for tool in context["selected_tools"]:
            tool_root = Path(context["tool_roots"][tool])
            atomic_targets.append((f"{tool} projection manifest", tool_root / PROJECTION_MANIFEST))
            for entry in artifact["projections"][tool]["entries"]:
                atomic_targets.append((f"{tool} projection", tool_root / Path(entry["path"])))

    for modification in modifications:
        atomic_targets.append(("planned user modification", Path(modification["locator"])))

    for purpose, path in [*direct_targets, *atomic_targets]:
        absolute = _absolute(path)
        if len(str(absolute)) > WINDOWS_MAX_PATH:
            raise LifecycleError(
                "TX_PATH_TOO_LONG",
                f"Planned {purpose} exceeds the supported Windows path bound before execution ({len(str(absolute))} > {WINDOWS_MAX_PATH}). Choose shorter lifecycle and tool roots.",
                str(absolute),
            )
    for purpose, path in atomic_targets:
        temporary = _absolute(path).parent / ATOMIC_TEMP_PROBE
        if len(str(temporary)) > WINDOWS_MAX_PATH:
            raise LifecycleError(
                "TX_PATH_TOO_LONG",
                f"Planned atomic write for {purpose} exceeds the supported Windows path bound before execution ({len(str(temporary))} > {WINDOWS_MAX_PATH}). Choose shorter lifecycle and tool roots.",
                str(path),
            )


def _make_plan_resolved(
    *,
    operation: str,
    lifecycle_root: str | Path,
    tool_roots: dict[str, str | Path],
    release: dict[str, Any] | None,
    source_kind: str,
    legacy_roots: Iterable[str | Path] | None = None,
    default_legacy_root: str | Path | None = None,
    operation_id: str | None = None,
    created_at: str | None = None,
    modification_overrides: list[dict[str, Any]] | None = None,
    allow_preview: bool = False,
    preview_contract: dict[str, Any] | None = None,
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

    if operation == "uninstall" and release is not None:
        raise LifecycleError("TX_RELEASE_ROOT", "Uninstall must not consume a source root.")
    if operation != "uninstall" and release is None:
        raise LifecycleError("TX_RELEASE_ROOT", "Install, update, and repair require a verified ReleaseRoot or RepositoryRoot.")
    artifact = release["artifact"] if release is not None else None
    target_identity = None
    if artifact is not None:
        target_identity = classify_generation_id(
            artifact["manifest"]["generation_id"],
            expected_version=artifact["manifest"]["version"],
        )
        if artifact["manifest"].get("schema_version") == 2 and target_identity["kind"] not in {"stable", "preview"}:
            raise LifecycleError(
                "TX_GENERATION_ID",
                "Generation manifest schema v2 requires a canonical stable or preview generation ID.",
                artifact["manifest"]["generation_id"],
            )
        if target_identity["kind"] == "preview" and not allow_preview:
            raise LifecycleError(
                "TX_PREVIEW_REQUIRES_ISOLATION",
                "Preview artifacts require the explicit isolated-preview entry point and cannot enter the stable lifecycle plan.",
                artifact["manifest"]["generation_id"],
            )
        if allow_preview and target_identity["kind"] != "preview":
            raise LifecycleError(
                "TX_PREVIEW_ARTIFACT_REQUIRED",
                "The isolated-preview entry point accepts only a canonical preview generation artifact.",
                artifact["manifest"]["generation_id"],
            )
    if allow_preview and preview_contract is None:
        raise LifecycleError("TX_PREVIEW_CONTRACT", "An isolated preview plan requires a bound preview contract.")
    if not allow_preview and preview_contract is not None:
        raise LifecycleError("TX_PREVIEW_CONTRACT", "Stable lifecycle plans cannot carry an isolated preview contract.")
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
    global_boot = _global_boot_context(root)
    plan_disposition = "EXECUTE"
    if artifact is not None:
        plan_disposition = _same_generation_disposition(
            root=root,
            tool_roots=normalized_tools,
            registry=registry,
            artifact=artifact,
            release_identity=release_identity,
            source_kind=source_kind,
            operation=operation,
            global_boot=global_boot,
        )
    obsolete_generation_bindings = [] if registry is None else [
        {"generation_id": item["generation_id"], "root": item["root"]}
        for item in registry["generations"]
        if item["generation_id"] != target_generation_id
    ]
    generation_root = root / "generations" / target_generation_id if target_generation_id else None
    context: dict[str, Any] = {
        "schema_version": 1,
        "operation_id": operation_id,
        "operation": operation,
        "source_kind": source_kind,
        "lifecycle_root": str(root),
        "release_root": release_identity["release_root"],
        "repository_root": release_identity["release_root"] if source_kind == "repository" else None,
        "release_identity": release_identity,
        "artifact_sha256": release_identity["artifact_sha256"],
        "target_generation_id": target_generation_id,
        "target_version": target_version,
        "target_generation_kind": target_identity["kind"] if target_identity else None,
        "preview_sequence": target_identity["preview_sequence"] if target_identity else None,
        "identity_contract_version": 1 if target_identity and target_identity["kind"] in {"stable", "preview"} else 0,
        "plan_disposition": plan_disposition,
        "obsolete_generation_bindings": obsolete_generation_bindings,
        "generation_root": str(generation_root) if generation_root else None,
        "target_generation_digest": _path_digest(generation_root) if generation_root else "MISSING",
        "tool_roots": {tool: str(path) for tool, path in normalized_tools.items()},
        "selected_tools": selected_tools,
        "registry_sha256": _registry_digest(root),
        "legacy_root_specs": legacy_specs,
        "legacy_root_observations": legacy_observations,
        "transaction_root": str(transaction_root),
        "staging_root": str(transaction_root / "staging" / target_generation_id) if target_generation_id else str(transaction_root / "staging"),
        "snapshot_root": str(transaction_root / "snapshot"),
        "global_boot": global_boot,
    }
    if preview_contract is not None:
        context["preview_contract"] = copy.deepcopy(preview_contract)
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
    _validate_planned_write_path_bounds(context, artifact, modifications)
    residue_records.extend(_record_digest_reference(record, root) for record in legacy_projection_records)
    for record in residue_records:
        _validate_contract("residue-tombstone", record)
    expected_cleanup = sorted({record["locator"] for record in residue_records if record["action"] == "delete"}, key=str.casefold)
    if plan_disposition == "NO_OP" and expected_cleanup:
        raise LifecycleError(
            "TX_GENERATION_REPAIR_REQUIRED",
            "The exact active generation still has managed cleanup obligations; create an explicit repair plan.",
            expected_cleanup[0],
        )
    context["residue_records"] = residue_records
    context["expected_cleanup"] = expected_cleanup
    context["modification_observations"] = modifications
    context_hash = sha256_bytes(canonical_json(context))
    actions = _operation_actions(context_hash, context, operation)
    plan_contract = {
        "schema_version": 1,
        "operation_id": operation_id,
        "operation": operation,
        "disposition": plan_disposition,
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


def _validate_new_preview_root(
    preview_root_value: str | Path | None,
    protected_roots: Iterable[str | Path],
) -> Path:
    preview_root = _absolute_preview_root(preview_root_value)
    if preview_root.exists():
        if not preview_root.is_dir() or _is_reparse(preview_root):
            raise LifecycleError("TX_PREVIEW_ROOT_TYPE", "Preview root must be an absent or empty real directory.", str(preview_root))
        if any(preview_root.iterdir()):
            raise LifecycleError("TX_PREVIEW_ROOT_NOT_EMPTY", "Preview root must be empty before an isolated install.", str(preview_root))
    for protected_value in protected_roots:
        protected_raw = Path(str(protected_value))
        if not protected_raw.is_absolute():
            raise LifecycleError("TX_PREVIEW_PROTECTED_ROOT", "Protected roots must be absolute.", str(protected_raw))
        protected = _absolute(protected_raw)
        if _is_inside(protected, preview_root) or _is_inside(preview_root, protected):
            raise LifecycleError(
                "TX_PREVIEW_ROOT_OVERLAP",
                "Preview root must not overlap maintenance, release, real lifecycle, or real tool roots.",
                str(preview_root),
            )
    return preview_root


def _validate_preview_context(context: dict[str, Any]) -> None:
    contract = context.get("preview_contract")
    target_kind = context.get("target_generation_kind")
    if target_kind != "preview":
        if contract is not None:
            raise LifecycleError("TX_PREVIEW_CONTRACT", "Only preview generations may carry an isolated preview contract.")
        return
    required = {
        "schema_version", "mode", "preview_root", "lifecycle_root", "global_boot",
        "manifest", "tool_isolation", "protected_roots",
    }
    if not isinstance(contract, dict) or set(contract) != required:
        raise LifecycleError("TX_PREVIEW_CONTRACT", "Preview execution context has an invalid closed shape.")
    if contract["schema_version"] != PREVIEW_CONTRACT_VERSION or contract["mode"] != "isolated-maintainer-preview":
        raise LifecycleError("TX_PREVIEW_CONTRACT", "Preview execution context has an unsupported version or mode.")
    preview_root = _absolute_preview_root(contract["preview_root"])
    expected_lifecycle = preview_root / "lifecycle"
    if Path(context["lifecycle_root"]) != expected_lifecycle or contract["lifecycle_root"] != str(expected_lifecycle):
        raise LifecycleError("TX_PREVIEW_CONTRACT", "Preview lifecycle root is not the canonical contained locator.", str(expected_lifecycle))
    if contract["global_boot"] != str(preview_root / GLOBAL_BOOT_FILENAME):
        raise LifecycleError("TX_PREVIEW_CONTRACT", "Preview global boot locator escapes or drifts from the preview root.")
    if contract["manifest"] != str(preview_root / PREVIEW_MANIFEST_FILENAME):
        raise LifecycleError("TX_PREVIEW_CONTRACT", "Preview manifest locator escapes or drifts from the preview root.")
    if set(contract["tool_isolation"]) != set(context["selected_tools"]):
        raise LifecycleError("TX_PREVIEW_CONTRACT", "Preview tool isolation set differs from selected tools.")
    for tool in context["selected_tools"]:
        expected = preview_tool_environment(preview_root, tool)
        if canonical_json(contract["tool_isolation"][tool]) != canonical_json(expected):
            raise LifecycleError("TX_PREVIEW_CONTRACT", f"Preview isolation binding drifted for {tool}.")
        if context["tool_roots"][tool] != expected["discovery_root"]:
            raise LifecycleError("TX_PREVIEW_CONTRACT", f"Preview tool root drifted for {tool}.")
    for protected_value in contract["protected_roots"]:
        protected = _absolute(protected_value)
        if _is_inside(protected, preview_root) or _is_inside(preview_root, protected):
            raise LifecycleError("TX_PREVIEW_ROOT_OVERLAP", "Preview context overlaps a protected root.", str(preview_root))


def make_preview_plan(
    *,
    preview_root: str | Path | None,
    release_root: str | Path | None = None,
    repository_root: str | Path | None = None,
    protected_roots: Iterable[str | Path] | None = None,
    tools: Iterable[str] | None = None,
    tool_isolation_support: dict[str, bool] | None = None,
    operation_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create a zero-write install plan for a fully contained preview artifact."""
    if (release_root is None) == (repository_root is None):
        raise LifecycleError("TX_SOURCE_INPUT", "Preview install requires exactly one ReleaseRoot or RepositoryRoot.")
    selected = list(TOOLS if tools is None else tools)
    if not selected or len(selected) != len(set(selected)) or any(tool not in TOOLS for tool in selected):
        raise LifecycleError("TX_TOOL_ROOTS", "Preview tools must be a unique non-empty subset of supported tools.")
    selected = [tool for tool in TOOLS if tool in selected]
    source_value = repository_root if repository_root is not None else release_root
    protected = [MALTS_ROOT, _absolute(source_value), *(protected_roots or [])]
    root = _validate_new_preview_root(preview_root, protected)
    if tool_isolation_support is not None and any(tool not in TOOLS for tool in tool_isolation_support):
        raise LifecycleError("TX_TOOL_ROOTS", "Preview isolation support contains an unsupported tool key.")
    isolation: dict[str, Any] = {}
    for tool in selected:
        supported = True if tool_isolation_support is None else tool_isolation_support.get(tool, False) is True
        isolation[tool] = preview_tool_environment(root, tool, supported=supported)
    lifecycle_root = root / "lifecycle"
    normalized_protected = sorted({str(_absolute(value)) for value in protected}, key=str.casefold)
    contract = {
        "schema_version": PREVIEW_CONTRACT_VERSION,
        "mode": "isolated-maintainer-preview",
        "preview_root": str(root),
        "lifecycle_root": str(lifecycle_root),
        "global_boot": str(root / GLOBAL_BOOT_FILENAME),
        "manifest": str(root / PREVIEW_MANIFEST_FILENAME),
        "tool_isolation": isolation,
        "protected_roots": normalized_protected,
    }
    source_kind = "repository" if repository_root is not None else "release-package"
    with _source_artifact_scope(release_root=release_root, repository_root=repository_root) as release:
        return _make_plan_resolved(
            operation="install",
            lifecycle_root=lifecycle_root,
            tool_roots={tool: isolation[tool]["discovery_root"] for tool in selected},
            release=release,
            source_kind=source_kind,
            legacy_roots=(),
            default_legacy_root=None,
            operation_id=operation_id,
            created_at=created_at,
            allow_preview=True,
            preview_contract=contract,
        )


def make_plan(
    *,
    operation: str,
    lifecycle_root: str | Path,
    tool_roots: dict[str, str | Path],
    release_root: str | Path | None = None,
    repository_root: str | Path | None = None,
    legacy_roots: Iterable[str | Path] | None = None,
    default_legacy_root: str | Path | None = None,
    operation_id: str | None = None,
    created_at: str | None = None,
    modification_overrides: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if operation == "uninstall":
        if release_root is not None or repository_root is not None:
            raise LifecycleError("TX_SOURCE_INPUT", "Uninstall cannot consume ReleaseRoot or RepositoryRoot.")
        source_kind = "installed-generation"
    else:
        if (release_root is None) == (repository_root is None):
            raise LifecycleError("TX_SOURCE_INPUT", "Install, update, and repair require exactly one ReleaseRoot or RepositoryRoot.")
        source_kind = "repository" if repository_root is not None else "release-package"
    with _source_artifact_scope(release_root=release_root, repository_root=repository_root) as release:
        return _make_plan_resolved(
            operation=operation,
            lifecycle_root=lifecycle_root,
            tool_roots=tool_roots,
            release=release,
            source_kind=source_kind,
            legacy_roots=legacy_roots,
            default_legacy_root=default_legacy_root,
            operation_id=operation_id,
            created_at=created_at,
            modification_overrides=modification_overrides,
        )


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
    _validate_preview_context(context)
    return plan, context


def _modification_digest_ref(modification: dict[str, Any]) -> str:
    refs = [ref for ref in modification["evidence_refs"] if ref.startswith("detected-sha256:")]
    if len(refs) != 1:
        raise LifecycleError("TX_MODIFICATION_EVIDENCE", "Modification requires one detected hash reference.", modification["locator"])
    return refs[0].split(":", 1)[1]


def _verify_plan_inputs(
    plan: dict[str, Any],
    context: dict[str, Any],
    expected_plan_hash: str,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if plan["plan_hash"] != expected_plan_hash.upper():
        raise LifecycleError("TX_EXPECTED_PLAN_HASH", "Explicit expected plan hash does not match the plan.")
    root = _absolute(context["lifecycle_root"])
    if _registry_digest(root) != context["registry_sha256"]:
        raise LifecycleError("TX_INPUT_DRIFT", "Installation registry changed after planning.", str(_registry_path(root)))
    if _global_boot_context(root) != context["global_boot"]:
        raise LifecycleError("TX_INPUT_DRIFT", "Configured global boot changed after planning.", context["global_boot"]["locator"])
    generation_root = Path(context["generation_root"]) if context.get("generation_root") else None
    observed_generation_digest = _path_digest(generation_root) if generation_root is not None else "MISSING"
    if observed_generation_digest != context.get("target_generation_digest", observed_generation_digest):
        raise LifecycleError("TX_INPUT_DRIFT", "Target generation content or existence changed after planning.", str(generation_root))
    source_kind = context.get("source_kind", "release-package" if context.get("release_root") is not None else "installed-generation")
    if source_kind == "release-package":
        release = verify_release_root(context["release_root"])
        if canonical_json(release["identity"]) != canonical_json(context["release_identity"]):
            raise LifecycleError("TX_INPUT_DRIFT", "Closed release identity changed after planning.", context["release_root"])
        artifact = release["artifact"]
    elif source_kind == "repository":
        repository_root = context.get("repository_root")
        if not isinstance(repository_root, str) or not Path(repository_root).is_absolute():
            raise LifecycleError("TX_CONTEXT_BINDING", "Repository plan lacks an absolute RepositoryRoot.")
        if artifact is None:
            raise LifecycleError("TX_REPOSITORY_ARTIFACT", "Repository source artifact was not materialized for plan verification.", repository_root)
        repository = verify_repository_root(repository_root)
        identity = _repository_release_identity(repository, artifact)
        if canonical_json(identity) != canonical_json(context["release_identity"]):
            raise LifecycleError("TX_INPUT_DRIFT", "Repository identity or generated artifact changed after planning.", repository_root)
        if artifact["artifact_sha256"] != context["artifact_sha256"]:
            raise LifecycleError("TX_INPUT_DRIFT", "Repository artifact hash changed after planning.", repository_root)
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
    global_boot: dict[str, Any],
    preview_contract: dict[str, Any] | None,
) -> None:
    snapshot = transaction_root / "snapshot"
    snapshot.mkdir(parents=True, exist_ok=False)
    meta: dict[str, Any] = {
        "registry_exists": _registry_path(root).is_file(),
        "pointer_exists": _pointer_path(root).is_file(),
        "tools": {},
        "external_residue": [],
        "global_boot": global_boot,
        "preview_contract": preview_contract,
    }
    if meta["registry_exists"]:
        shutil.copyfile(_registry_path(root), snapshot / "registry.json")
    if meta["pointer_exists"]:
        shutil.copyfile(_pointer_path(root), snapshot / "pointer.json")
    if global_boot["mode"] == "refresh":
        shutil.copyfile(Path(global_boot["locator"]), snapshot / "global_boot.md")
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


def _installed_release_identity(release_identity: dict[str, Any], source_kind: str) -> dict[str, Any]:
    if source_kind not in INSTALLED_RELEASE_SOURCE_KINDS:
        raise LifecycleError(
            "TX_INSTALLED_ENVELOPE_CONTRACT",
            "Only release-package and repository sources can create an installed generation.",
        )
    return {
        "schema_version": INSTALLED_RELEASE_IDENTITY_SCHEMA_VERSION,
        "source_kind": source_kind,
        "release_id": release_identity["release_id"],
        "release_manifest_sha256": release_identity["release_manifest_sha256"],
        "release_package_sha256": release_identity["release_package_sha256"],
        "artifact_sha256": release_identity["artifact_sha256"],
        "generation_id": release_identity["generation_id"],
        "generation_manifest_sha256": release_identity["generation_manifest_sha256"],
    }


def _stage_artifact(
    artifact: dict[str, Any],
    release_identity: dict[str, Any],
    source_kind: str,
    staging_root: Path,
) -> None:
    _copy_tree(artifact["root"] / "payload", staging_root)
    shutil.copyfile(artifact["root"] / "generation_manifest.json", staging_root / "generation_manifest.json")
    write_json(staging_root / "artifact_identity.json", {"artifact_sha256": artifact["artifact_sha256"], "package_tree_sha256": artifact["manifest"]["package_tree_sha256"]})
    write_json(staging_root / "release_identity.json", _installed_release_identity(release_identity, source_kind))


def _verify_stage(
    artifact: dict[str, Any],
    release_identity: dict[str, Any],
    source_kind: str,
    staging_root: Path,
) -> None:
    payload_records = [record for record in artifact["records"] if record["path"].startswith("payload/")]
    actual: list[dict[str, Any]] = []
    metadata_names = {"generation_manifest.json", "artifact_identity.json", "release_identity.json"}
    for path in sorted((item for item in staging_root.rglob("*") if item.is_file() and item.name not in metadata_names), key=lambda item: item.relative_to(staging_root).as_posix().casefold()):
        actual.append({"path": f"payload/{path.relative_to(staging_root).as_posix()}", "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    if actual != payload_records:
        raise LifecycleError("TX_STAGE_VERIFY", "Staged generation differs from the verified artifact.", str(staging_root))
    if load_json(staging_root / "release_identity.json") != _installed_release_identity(release_identity, source_kind):
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
            if entry["mode"] == "managed-block":
                installed_entry["managed_block_sha256"] = _managed_block_sha256(source.read_bytes())
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
                        _assert_no_reparse(root, target)
                        _assert_no_hardlink(target)
                        target.unlink()
                    else:
                        _atomic_write(target, payload)
                elif decision == "preserve":
                    pass
                elif decision in {"replace", "drop"}:
                    _assert_no_reparse(root, target)
                    _assert_no_hardlink(target)
                    target.unlink()
                else:
                    raise LifecycleError("TX_PROJECTION_DECISION", "Stale file projection requires preserve, replace, or drop.", str(target))
        manifest_path = root / PROJECTION_MANIFEST
        _assert_no_reparse(root, manifest_path)
        _assert_no_hardlink(manifest_path)
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
        if operation != "repair":
            raise LifecycleError(
                "TX_GENERATION_COLLISION",
                "Refusing to overwrite an existing generation outside an explicit repair transaction.",
                str(target),
            )
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
    registry["generations"] = [new_record] if context.get("identity_contract_version") == 1 else [*old_records, new_record]
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


def _obsolete_generation_references(root: Path, context: dict[str, Any]) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    bindings = context.get("obsolete_generation_bindings", [])
    if not bindings:
        return references
    surfaces: list[tuple[str, Path]] = [
        ("installation-registry", _registry_path(root)),
        ("active-generation-pointer", _pointer_path(root)),
    ]
    global_boot = context.get("global_boot", {})
    if global_boot.get("mode") == "refresh":
        surfaces.append(("global-boot", Path(global_boot["locator"])))
    for tool, raw_root in context["tool_roots"].items():
        tool_root = Path(raw_root)
        surfaces.extend(
            (
                (f"{tool}-projection", tool_root / PROJECTION_MANIFEST),
                (f"{tool}-boot", tool_root / "MALTS_BOOT.md"),
            )
        )
    for surface, path in surfaces:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise LifecycleError("TX_OLD_GENERATION_REFERENCE_SCAN", "Managed reference surface is not valid UTF-8.", str(path)) from exc
        for binding in bindings:
            for token_kind in ("generation_id", "root"):
                token = binding[token_kind]
                if token and token in text:
                    references.append({"surface": surface, "path": str(path), "token_kind": token_kind, "token": token})
    return references


def _assert_obsolete_generations_unreferenced(root: Path, context: dict[str, Any]) -> None:
    if context.get("identity_contract_version") != 1:
        return
    references = _obsolete_generation_references(root, context)
    if references:
        first = references[0]
        raise LifecycleError(
            "TX_OLD_GENERATION_REFERENCED",
            f"Cleanup is blocked because {len(references)} managed reference(s) still point to an obsolete generation.",
            first["path"],
        )


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
    _assert_obsolete_generations_unreferenced(root, context)
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


def _audit_token(value: str) -> str:
    normalized = _now(value)
    parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    return parsed.strftime("%Y%m%dT%H%M%SZ")


def _audit_record_hash(value: dict[str, Any]) -> str:
    payload = copy.deepcopy(value)
    payload.pop("record_sha256", None)
    return sha256_bytes(canonical_json(payload))


def _audit_details(**overrides: Any) -> dict[str, Any]:
    value = {
        "plan_hash": None,
        "generation_id": None,
        "binding_sha256": None,
        "plan_sha256": None,
        "journal_sha256": None,
        "success_count": None,
        "failure_count": None,
        "uninstall_count": None,
        "last_operation_id": None,
    }
    value.update(overrides)
    return value


def _make_audit_record(
    *,
    record_type: str,
    record_id: str,
    created_at: str,
    operation_id: str | None,
    operation: str | None,
    outcome: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    normalized = _now(created_at)
    value = {
        "schema_version": 1,
        "record_type": record_type,
        "record_id": record_id,
        "owner": "MALTS",
        "created_at": normalized,
        "month": normalized[:7],
        "operation_id": operation_id,
        "operation": operation,
        "outcome": outcome,
        "details": details,
    }
    value["record_sha256"] = _audit_record_hash(value)
    _validate_contract("lifecycle-audit-record", value)
    return value


def _active_binding(registry: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None]:
    active = _active_generation_record(registry)
    if active is None:
        return None, None
    return active, sha256_bytes(canonical_json(active))


def _audit_forbidden_name(path: Path) -> bool:
    lowered = path.name.casefold()
    return (
        lowered.endswith((".zip", ".tar", ".tgz", ".7z"))
        or any(token in lowered for token in ("payload", "package", "generation-copy", "artifact-copy"))
    )


def _audit_issue(code: str, path: Path, message: str) -> dict[str, Any]:
    return {"code": code, "path": str(path), "message": message}


def _load_audit_record(path: Path, expected_type: str) -> dict[str, Any]:
    if not path.is_file() or _is_reparse(path):
        raise LifecycleError("AUDIT_RECORD_PATH", "Audit record must be a regular non-reparse file.", str(path))
    value = load_json(path)
    if not isinstance(value, dict):
        raise LifecycleError("AUDIT_RECORD_INVALID", "Audit record must be a JSON object.", str(path))
    _validate_contract("lifecycle-audit-record", value)
    if value["record_type"] != expected_type:
        raise LifecycleError("AUDIT_RECORD_TYPE", f"Expected {expected_type} audit record.", str(path))
    return value


def _audit_event_entry(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "sort_key": (record["created_at"], record.get("operation_id") or ""),
        "record": record,
    }


def _pre_retention_fail(code: str, message: str, path: Path) -> None:
    raise LifecycleError(code, message, str(path))


def _pre_retention_hash(value: Any, *, allow_none: bool = False) -> bool:
    return (allow_none and value is None) or (isinstance(value, str) and HASH_PATTERN.fullmatch(value) is not None)


def _pre_retention_digest(value: Any) -> bool:
    return value == "MISSING" or _pre_retention_hash(value)


def _pre_retention_absolute_path(value: Any) -> bool:
    return isinstance(value, str) and Path(value).is_absolute()


def _validate_pre_retention_audit_bundle(
    operation_id: str,
    envelope: Any,
    journal: Any,
    *,
    path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the exact v1 pre-retention audit shape without inventing newer bindings."""
    if not isinstance(envelope, dict) or set(envelope) != {"schema_version", "plan_contract", "execution_context", "context_sha256"}:
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_SCHEMA", "Pre-retention audit envelope has an invalid closed shape.", path)
    if envelope["schema_version"] != 1 or not isinstance(envelope["plan_contract"], dict) or not isinstance(envelope["execution_context"], dict):
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_SCHEMA", "Pre-retention audit envelope has invalid typed fields.", path)
    plan = envelope["plan_contract"]
    context = envelope["execution_context"]
    if set(plan) != AUDIT_PRE_RETENTION_PLAN_KEYS or set(context) != AUDIT_PRE_RETENTION_CONTEXT_KEYS:
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_SCHEMA", "Pre-retention audit plan or context does not match the exact historic field set.", path)
    if (
        plan["schema_version"] != 1
        or plan["operation_id"] != operation_id
        or not ID_PATTERN.fullmatch(operation_id)
        or plan["operation"] not in {"install", "update", "repair", "uninstall"}
        or plan["plan_hash_algorithm"] != PLAN_ALGORITHM
        or not _pre_retention_hash(plan["plan_hash"])
        or not isinstance(plan["created_at"], str)
    ):
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN", "Pre-retention audit plan identity is invalid.", path)
    _now(plan["created_at"])
    if plan["plan_hash"] != canonical_plan_hash(plan):
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN_HASH", "Pre-retention audit plan hash drifted.", path)
    if not isinstance(plan["detected_generation"], (str, type(None))):
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN", "Pre-retention detected generation is invalid.", path)
    if plan["operation"] == "uninstall":
        if plan["source_artifact_sha256"] is not None:
            _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN", "Pre-retention uninstall cannot bind a source artifact.", path)
    elif not _pre_retention_hash(plan["source_artifact_sha256"]):
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN", "Pre-retention plan source artifact hash is invalid.", path)

    tools = plan["tool_targets"]
    if (
        not isinstance(tools, list)
        or not 1 <= len(tools) <= len(TOOLS)
        or any(not isinstance(tool, str) or tool not in TOOLS for tool in tools)
        or len(set(tools)) != len(tools)
    ):
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN", "Pre-retention plan tool selection is invalid.", path)
    cleanup = plan["expected_cleanup"]
    if not isinstance(cleanup, list) or any(not _pre_retention_absolute_path(item) for item in cleanup) or len(set(cleanup)) != len(cleanup):
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN", "Pre-retention plan cleanup list is invalid.", path)

    actions = plan["actions"]
    if not isinstance(actions, list) or not actions:
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN", "Pre-retention plan has no actions.", path)
    action_ids: set[str] = set()
    dependencies: dict[str, set[str]] = {}
    for action in actions:
        if (
            not isinstance(action, dict)
            or set(action) != {"action_id", "kind", "target", "dependencies", "destructive"}
            or not isinstance(action["action_id"], str)
            or not ID_PATTERN.fullmatch(action["action_id"])
            or action["action_id"] in action_ids
            or action["kind"] not in {"verify", "copy", "activate", "merge", "delete"}
            or not isinstance(action["target"], str)
            or not action["target"]
            or not isinstance(action["dependencies"], list)
            or any(not isinstance(item, str) or not ID_PATTERN.fullmatch(item) for item in action["dependencies"])
            or len(set(action["dependencies"])) != len(action["dependencies"])
            or not isinstance(action["destructive"], bool)
        ):
            _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN", "Pre-retention plan action shape is invalid.", path)
        action_ids.add(action["action_id"])
        dependencies[action["action_id"]] = set(action["dependencies"])
        if action["kind"] == "delete" and action["target"] not in cleanup:
            _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN", "Pre-retention delete action is not listed for cleanup.", path)
    if any(not values.issubset(action_ids) or key in values for key, values in dependencies.items()):
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN", "Pre-retention action dependencies are invalid.", path)
    unresolved = {key: set(values) for key, values in dependencies.items()}
    while unresolved:
        ready = [key for key, values in unresolved.items() if not values]
        if not ready:
            _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN", "Pre-retention action dependencies contain a cycle.", path)
        for key in ready:
            unresolved.pop(key)
        for values in unresolved.values():
            values.difference_update(ready)

    acceptance = plan["acceptance_matrix"]
    if not isinstance(acceptance, list) or not acceptance:
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN", "Pre-retention acceptance matrix is invalid.", path)
    criteria: set[str] = set()
    for item in acceptance:
        if (
            not isinstance(item, dict)
            or set(item) != {"criterion_id", "hard", "verification", "expected_result"}
            or not isinstance(item["criterion_id"], str)
            or not ID_PATTERN.fullmatch(item["criterion_id"])
            or item["criterion_id"] in criteria
            or not isinstance(item["hard"], bool)
            or not isinstance(item["verification"], str)
            or not item["verification"]
            or not isinstance(item["expected_result"], str)
            or not item["expected_result"]
        ):
            _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN", "Pre-retention acceptance entry is invalid.", path)
        criteria.add(item["criterion_id"])
    modifications = plan["user_modifications"]
    if not isinstance(modifications, list):
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN", "Pre-retention modification observations are invalid.", path)
    for item in modifications:
        if (
            not isinstance(item, dict)
            or set(item) != {"locator", "classification", "decision", "evidence_refs"}
            or not _pre_retention_absolute_path(item["locator"])
            or item["classification"] not in {"U0", "U1", "U2", "U3", "U4"}
            or item["decision"] not in {"replace", "merge", "preserve", "ask", "fail-closed"}
            or not isinstance(item["evidence_refs"], list)
            or any(not isinstance(ref, str) or not ref for ref in item["evidence_refs"])
        ):
            _pre_retention_fail("TX_AUDIT_PRE_RETENTION_PLAN", "Pre-retention modification observation is invalid.", path)

    if (
        context["schema_version"] != 1
        or context["operation_id"] != operation_id
        or context["operation"] != plan["operation"]
        or not _pre_retention_digest(context["registry_sha256"])
        or not isinstance(context["target_version"], str)
        or SEMVER_PATTERN.fullmatch(context["target_version"]) is None
        or not isinstance(context["target_generation_id"], str)
        or not ID_PATTERN.fullmatch(context["target_generation_id"])
        or context["artifact_sha256"] != plan["source_artifact_sha256"]
        or sorted(context["expected_cleanup"], key=str.casefold) != sorted(cleanup, key=str.casefold)
        or not isinstance(context["tool_roots"], dict)
        or list(context["tool_roots"]) != tools
    ):
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_BINDING", "Pre-retention plan/context binding is invalid.", path)
    path_fields = ("lifecycle_root", "transaction_root", "staging_root", "snapshot_root")
    if any(not _pre_retention_absolute_path(context[field]) for field in path_fields):
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_CONTEXT", "Pre-retention context path is invalid.", path)
    for field in ("artifact_root", "generation_root"):
        if context[field] is not None and not _pre_retention_absolute_path(context[field]):
            _pre_retention_fail("TX_AUDIT_PRE_RETENTION_CONTEXT", "Pre-retention optional context path is invalid.", path)
    if any(not _pre_retention_absolute_path(value) for value in context["tool_roots"].values()):
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_CONTEXT", "Pre-retention tool root is invalid.", path)
    fixture = context["legacy_fixture"]
    fixture_hash = context["legacy_fixture_sha256"]
    if fixture is None:
        if fixture_hash is not None:
            _pre_retention_fail("TX_AUDIT_PRE_RETENTION_CONTEXT", "Absent pre-retention fixture has a hash.", path)
    elif not isinstance(fixture, dict) or not _pre_retention_hash(fixture_hash) or sha256_bytes(canonical_json(fixture)) != fixture_hash:
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_CONTEXT", "Pre-retention fixture binding is invalid.", path)
    if not isinstance(context["residue_records"], list) or not isinstance(context["modification_observations"], list):
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_CONTEXT", "Pre-retention context collections are invalid.", path)
    for record in context["residue_records"]:
        if not isinstance(record, dict):
            _pre_retention_fail("TX_AUDIT_PRE_RETENTION_CONTEXT", "Pre-retention residue record is invalid.", path)
        _validate_contract("residue-tombstone", record)
    for item in context["modification_observations"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"locator", "classification", "decision", "evidence_refs"}
            or not _pre_retention_absolute_path(item["locator"])
            or item["classification"] not in {"U0", "U1", "U2", "U3", "U4"}
            or item["decision"] not in {"replace", "merge", "preserve", "ask", "fail-closed"}
            or not isinstance(item["evidence_refs"], list)
            or any(not isinstance(ref, str) or not ref for ref in item["evidence_refs"])
        ):
            _pre_retention_fail("TX_AUDIT_PRE_RETENTION_CONTEXT", "Pre-retention modification observation is invalid.", path)
    context_hash = sha256_bytes(canonical_json(context))
    if envelope["context_sha256"] != context_hash:
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_CONTEXT_HASH", "Pre-retention context hash drifted.", path)
    if not any(action["kind"] == "verify" and action["target"] == f"context-sha256:{context_hash}" for action in actions):
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_CONTEXT_BINDING", "Pre-retention plan does not bind its context hash.", path)

    if not isinstance(journal, dict) or set(journal) != AUDIT_PRE_RETENTION_JOURNAL_KEYS:
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_JOURNAL", "Pre-retention journal has an invalid closed shape.", path)
    _validate_contract("transaction-journal", journal)
    if (
        journal["journal_id"] != f"J-{operation_id}"
        or journal["operation_id"] != operation_id
        or journal["plan_hash"] != plan["plan_hash"]
        or journal["state"] not in {"COMMIT", "FAILED"}
        or not isinstance(journal["last_completed_action"], str)
        or not isinstance(journal["recovery_actions"], list)
        or not isinstance(journal["updated_at"], str)
    ):
        _pre_retention_fail("TX_AUDIT_PRE_RETENTION_JOURNAL", "Pre-retention journal binding is invalid.", path)
    _now(journal["updated_at"])
    return plan, context


def _load_pre_retention_audit_bundle(operation_id: str, plan_path: Path, journal_path: Path) -> dict[str, Any]:
    if (
        not plan_path.is_file()
        or not journal_path.is_file()
        or _is_reparse(plan_path)
        or _is_reparse(journal_path)
    ):
        raise LifecycleError("TX_AUDIT_PRE_RETENTION_PATH", "Pre-retention audit files must be regular non-reparse files.", str(plan_path))
    envelope = load_json(plan_path)
    journal = load_json(journal_path)
    plan, context = _validate_pre_retention_audit_bundle(operation_id, envelope, journal, path=plan_path)
    return {
        "operation_id": operation_id,
        "plan": plan,
        "context": context,
        "envelope": envelope,
        "journal": journal,
        "plan_path": str(plan_path),
        "plan_sha256": file_sha256(plan_path),
        "journal_path": str(journal_path),
        "journal_sha256": file_sha256(journal_path),
        "sort_key": (journal["updated_at"], operation_id),
    }


def _scan_pre_retention_archives(audit: Path, issues: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    archive = audit / AUDIT_PRE_RETENTION_DIRECTORY
    bundles: dict[str, dict[str, Any]] = {}
    if not archive.exists():
        return bundles
    if not archive.is_dir() or _is_reparse(archive):
        issues.append(_audit_issue("AUDIT_PRE_RETENTION_ARCHIVE_INVALID", archive, "Historic archive must be a regular non-reparse directory."))
        return bundles
    for child in sorted(archive.iterdir(), key=lambda item: item.name.casefold()):
        if _is_reparse(child) or not child.is_dir() or ID_PATTERN.fullmatch(child.name) is None:
            issues.append(_audit_issue("AUDIT_PRE_RETENTION_ARCHIVE_INVALID", child, "Historic archive entry has an invalid path or name."))
            continue
        files = {item.name: item for item in child.iterdir() if item.is_file() and not _is_reparse(item)}
        if set(files) != {"plan.json", "journal.json"} or len(list(child.iterdir())) != 2:
            issues.append(_audit_issue("AUDIT_PRE_RETENTION_ARCHIVE_INVALID", child, "Historic archive entry must contain exactly plan.json and journal.json."))
            continue
        try:
            bundles[child.name] = _load_pre_retention_audit_bundle(child.name, files["plan.json"], files["journal.json"])
        except LifecycleError as exc:
            issues.append(_audit_issue("AUDIT_PRE_RETENTION_ARCHIVE_INVALID", child, exc.code))
    return bundles


def _pre_retention_matches_archive(files: dict[str, Path], archive: dict[str, Any]) -> bool:
    for kind, path in files.items():
        if file_sha256(path) != archive[f"{kind}_sha256"]:
            return False
    return True


def audit_state(root_value: str | Path, *, enforce_current_binding: bool = True) -> dict[str, Any]:
    root = _absolute(root_value)
    audit = root / AUDIT_RELATIVE
    issues: list[dict[str, Any]] = []
    success_receipts: list[dict[str, Any]] = []
    failure_bundles: list[dict[str, Any]] = []
    monthly_summaries: list[dict[str, Any]] = []
    legacy_bundles: list[dict[str, Any]] = []
    pre_retention_bundles: list[dict[str, Any]] = []
    pre_retention_archives: list[dict[str, Any]] = []
    pre_retention_migration_residue: list[dict[str, Any]] = []
    current_binding: dict[str, Any] | None = None

    if audit.exists() and (not audit.is_dir() or _is_reparse(audit)):
        issues.append(_audit_issue("AUDIT_ROOT_INVALID", audit, "Audit root must be a regular non-reparse directory."))
    elif audit.is_dir():
        allowed_directories = {"success", "failure", "monthly", AUDIT_PRE_RETENTION_DIRECTORY}
        legacy_groups: dict[str, dict[str, Path]] = {}
        for child in sorted(audit.iterdir(), key=lambda item: item.name.casefold()):
            if _is_reparse(child):
                issues.append(_audit_issue("AUDIT_REPARSE", child, "Audit content cannot be a reparse point."))
                continue
            if child.name == AUDIT_CURRENT_FILENAME:
                try:
                    record = _load_audit_record(child, "current-binding")
                    current_binding = _audit_event_entry(child, record)
                except LifecycleError as exc:
                    issues.append(_audit_issue("AUDIT_RECORD_INVALID", child, exc.code))
                continue
            if child.name in allowed_directories and child.is_dir():
                continue
            legacy_match = AUDIT_LEGACY_NAME_PATTERN.fullmatch(child.name) if child.is_file() else None
            if legacy_match is not None:
                legacy_groups.setdefault(legacy_match.group("operation_id"), {})[legacy_match.group("kind")] = child
                continue
            code = "AUDIT_FORBIDDEN_CONTENT" if _audit_forbidden_name(child) else "AUDIT_UNKNOWN_ENTRY"
            issues.append(_audit_issue(code, child, "Unknown or forbidden audit-root content is preserved and blocks pruning."))

        archived_pre_retention = _scan_pre_retention_archives(audit, issues)
        pre_retention_archives.extend(archived_pre_retention.values())

        success_root = audit / "success"
        if success_root.is_dir() and not _is_reparse(success_root):
            for path in sorted(success_root.iterdir(), key=lambda item: item.name.casefold()):
                match = AUDIT_EVENT_NAME_PATTERN.fullmatch(path.name) if path.is_file() and not _is_reparse(path) else None
                if match is None or match.group("kind") != "audit":
                    code = "AUDIT_FORBIDDEN_CONTENT" if _audit_forbidden_name(path) else "AUDIT_UNKNOWN_ENTRY"
                    issues.append(_audit_issue(code, path, "Success receipt name or type is not owned by the retention contract."))
                    continue
                try:
                    record = _load_audit_record(path, "operation-receipt")
                    if (
                        record["operation_id"] != match.group("operation_id")
                        or _audit_token(record["created_at"]) != match.group("token")
                    ):
                        raise LifecycleError("AUDIT_RECORD_NAME", "Success receipt filename does not bind its record.", str(path))
                    success_receipts.append(_audit_event_entry(path, record))
                except LifecycleError as exc:
                    issues.append(_audit_issue("AUDIT_RECORD_INVALID", path, exc.code))

        failure_root = audit / "failure"
        failure_groups: dict[tuple[str, str], dict[str, Path]] = {}
        if failure_root.is_dir() and not _is_reparse(failure_root):
            for path in sorted(failure_root.iterdir(), key=lambda item: item.name.casefold()):
                match = AUDIT_EVENT_NAME_PATTERN.fullmatch(path.name) if path.is_file() and not _is_reparse(path) else None
                if match is None:
                    code = "AUDIT_FORBIDDEN_CONTENT" if _audit_forbidden_name(path) else "AUDIT_UNKNOWN_ENTRY"
                    issues.append(_audit_issue(code, path, "Failure bundle name or type is not owned by the retention contract."))
                    continue
                key = (match.group("token"), match.group("operation_id"))
                failure_groups.setdefault(key, {})[match.group("kind")] = path
        for (token, operation_id), files in sorted(failure_groups.items()):
            if set(files) != {"audit", "plan", "journal"}:
                issues.append(_audit_issue("AUDIT_FAILURE_BUNDLE_INCOMPLETE", failure_root, f"Incomplete failure bundle for {operation_id}."))
                continue
            record_path = files["audit"]
            try:
                record = _load_audit_record(record_path, "failure-bundle")
                if record["operation_id"] != operation_id or _audit_token(record["created_at"]) != token:
                    raise LifecycleError("AUDIT_RECORD_NAME", "Failure bundle filename does not bind its record.", str(record_path))
                envelope = load_json(files["plan"])
                plan, _ = validate_plan_envelope(envelope)
                journal = load_json(files["journal"])
                _validate_contract("transaction-journal", journal)
                if (
                    plan["operation_id"] != operation_id
                    or journal["operation_id"] != operation_id
                    or journal["plan_hash"] != plan["plan_hash"]
                    or record["details"]["plan_hash"] != plan["plan_hash"]
                    or record["details"]["plan_sha256"] != file_sha256(files["plan"])
                    or record["details"]["journal_sha256"] != file_sha256(files["journal"])
                ):
                    raise LifecycleError("AUDIT_FAILURE_BINDING", "Failure bundle hashes or operation binding drifted.", str(record_path))
                entry = _audit_event_entry(record_path, record)
                entry.update(
                    {
                        "plan_path": str(files["plan"]),
                        "plan_sha256": file_sha256(files["plan"]),
                        "journal_path": str(files["journal"]),
                        "journal_sha256": file_sha256(files["journal"]),
                    }
                )
                failure_bundles.append(entry)
            except LifecycleError as exc:
                issues.append(_audit_issue("AUDIT_FAILURE_BUNDLE_INVALID", record_path, exc.code))

        monthly_root = audit / "monthly"
        if monthly_root.is_dir() and not _is_reparse(monthly_root):
            for path in sorted(monthly_root.iterdir(), key=lambda item: item.name.casefold()):
                match = AUDIT_MONTH_NAME_PATTERN.fullmatch(path.name) if path.is_file() and not _is_reparse(path) else None
                if match is None:
                    issues.append(_audit_issue("AUDIT_UNKNOWN_ENTRY", path, "Monthly summary name is not owned by the retention contract."))
                    continue
                try:
                    record = _load_audit_record(path, "monthly-summary")
                    if record["month"] != match.group("month"):
                        raise LifecycleError("AUDIT_RECORD_NAME", "Monthly summary filename does not bind its month.", str(path))
                    monthly_summaries.append(_audit_event_entry(path, record))
                except LifecycleError as exc:
                    issues.append(_audit_issue("AUDIT_RECORD_INVALID", path, exc.code))

        for operation_id, files in sorted(legacy_groups.items()):
            archived = archived_pre_retention.get(operation_id)
            if set(files) != {"plan", "journal"}:
                if archived is not None and _pre_retention_matches_archive(files, archived):
                    pre_retention_migration_residue.append(
                        {
                            "operation_id": operation_id,
                            "root_files": {kind: str(path) for kind, path in files.items()},
                            "root_sha256": {kind: file_sha256(path) for kind, path in files.items()},
                            "archive_plan_path": archived["plan_path"],
                            "archive_journal_path": archived["journal_path"],
                            "sort_key": archived["sort_key"],
                        }
                    )
                else:
                    issues.append(_audit_issue("AUDIT_LEGACY_BUNDLE_INCOMPLETE", audit, f"Incomplete legacy audit bundle for {operation_id}."))
                continue
            try:
                envelope = load_json(files["plan"])
                plan, _ = validate_plan_envelope(envelope)
                journal = load_json(files["journal"])
                _validate_contract("transaction-journal", journal)
                if (
                    plan["operation_id"] != operation_id
                    or journal["operation_id"] != operation_id
                    or journal["plan_hash"] != plan["plan_hash"]
                    or journal["state"] not in {"COMMIT", "FAILED"}
                ):
                    raise LifecycleError("AUDIT_LEGACY_BINDING", "Legacy audit bundle is not terminal or consistently bound.", str(files["plan"]))
                if archived is not None:
                    issues.append(_audit_issue("AUDIT_PRE_RETENTION_ID_COLLISION", files["plan"], "Current-format and historic archive bundles cannot share an operation_id."))
                    continue
                legacy_bundles.append(
                    {
                        "operation_id": operation_id,
                        "plan": plan,
                        "envelope": envelope,
                        "journal": journal,
                        "plan_path": str(files["plan"]),
                        "plan_sha256": file_sha256(files["plan"]),
                        "journal_path": str(files["journal"]),
                        "journal_sha256": file_sha256(files["journal"]),
                        "sort_key": (journal["updated_at"], operation_id),
                    }
                )
            except LifecycleError:
                try:
                    bundle = _load_pre_retention_audit_bundle(operation_id, files["plan"], files["journal"])
                except LifecycleError as exc:
                    issues.append(_audit_issue("AUDIT_LEGACY_BUNDLE_INVALID", files["plan"], exc.code))
                    continue
                if archived is None:
                    pre_retention_bundles.append(bundle)
                elif _pre_retention_matches_archive(files, archived):
                    pre_retention_migration_residue.append(
                        {
                            "operation_id": operation_id,
                            "root_files": {kind: str(path) for kind, path in files.items()},
                            "root_sha256": {kind: file_sha256(path) for kind, path in files.items()},
                            "archive_plan_path": archived["plan_path"],
                            "archive_journal_path": archived["journal_path"],
                            "sort_key": archived["sort_key"],
                        }
                    )
                else:
                    issues.append(_audit_issue("AUDIT_PRE_RETENTION_ARCHIVE_DRIFT", files["plan"], "Historic root and archive bundles differ."))

    registry: dict[str, Any] | None = None
    try:
        registry = _load_registry(root)
    except LifecycleError as exc:
        if enforce_current_binding:
            issues.append(_audit_issue("AUDIT_REGISTRY_INVALID", _registry_path(root), exc.code))
    if enforce_current_binding and registry is not None:
        active, binding_sha256 = _active_binding(registry)
        if registry["lifecycle_state"] == "stable" and active is not None:
            if current_binding is None:
                issues.append(_audit_issue("AUDIT_CURRENT_BINDING_MISSING", audit / AUDIT_CURRENT_FILENAME, "Stable active binding requires exactly one current receipt."))
            elif (
                current_binding["record"]["details"]["generation_id"] != active["generation_id"]
                or current_binding["record"]["details"]["binding_sha256"] != binding_sha256
            ):
                issues.append(_audit_issue("AUDIT_CURRENT_BINDING_DRIFT", Path(current_binding["path"]), "Current binding receipt does not match the active registry record."))
        elif current_binding is not None:
            issues.append(_audit_issue("AUDIT_CURRENT_BINDING_STALE", Path(current_binding["path"]), "Uninstalled or inactive registry cannot retain a current binding receipt."))

    success_receipts.sort(key=lambda item: item["sort_key"])
    failure_bundles.sort(key=lambda item: item["sort_key"])
    monthly_summaries.sort(key=lambda item: item["record"]["month"])
    legacy_bundles.sort(key=lambda item: item["sort_key"])
    pre_retention_bundles.sort(key=lambda item: item["sort_key"])
    pre_retention_archives.sort(key=lambda item: item["sort_key"])
    pre_retention_migration_residue.sort(key=lambda item: item["sort_key"])
    return {
        "status": "PASS" if not issues else "FAIL",
        "mode": "READ_ONLY",
        "writes_performed": False,
        "audit_root": str(audit),
        "current_binding": current_binding,
        "success_receipts": success_receipts,
        "failure_bundles": failure_bundles,
        "monthly_summaries": monthly_summaries,
        "legacy_bundles": legacy_bundles,
        "pre_retention_bundles": pre_retention_bundles,
        "pre_retention_archives": pre_retention_archives,
        "pre_retention_migration_residue": pre_retention_migration_residue,
        "over_limit": {
            "success": max(0, len(success_receipts) - AUDIT_SUCCESS_LIMIT),
            "failure": max(0, len(failure_bundles) - AUDIT_FAILURE_LIMIT),
            "monthly": max(0, len(monthly_summaries) - AUDIT_MONTHLY_LIMIT),
        },
        "issues": issues,
    }


def _write_exact_audit_json(path: Path, value: dict[str, Any]) -> bool:
    expected = json_bytes(value)
    if path.exists():
        if not path.is_file() or _is_reparse(path) or path.read_bytes() != expected:
            raise LifecycleError("TX_AUDIT_OWNERSHIP_DRIFT", "Existing audit target does not match the exact owned content.", str(path))
        return False
    write_json(path, value)
    if not path.is_file() or _is_reparse(path) or path.read_bytes() != expected:
        raise LifecycleError("TX_AUDIT_WRITE_VERIFY", "Atomic audit write did not produce the expected exact content.", str(path))
    return True


def _replace_current_audit_record(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        _load_audit_record(path, "current-binding")
    write_json(path, value)
    if load_json(path) != value:
        raise LifecycleError("TX_AUDIT_WRITE_VERIFY", "Current binding receipt verification failed.", str(path))


def _remove_exact_audit_file(audit: Path, path: Path, expected_sha256: str) -> None:
    if not path.exists():
        return
    if not _is_inside(audit, path) or not path.is_file() or _is_reparse(path):
        raise LifecycleError("TX_AUDIT_PRUNE_BOUNDARY", "Audit pruning target is outside the exact owned file boundary.", str(path))
    if file_sha256(path) != expected_sha256:
        raise LifecycleError("TX_AUDIT_OWNERSHIP_DRIFT", "Audit pruning target changed after review.", str(path))
    path.unlink()


def _update_monthly_summary(audit: Path, *, operation_id: str, outcome: str, created_at: str) -> None:
    month = created_at[:7]
    path = audit / "monthly" / f"{month}.audit.json"
    if path.exists():
        current = _load_audit_record(path, "monthly-summary")
        if current["details"]["last_operation_id"] == operation_id:
            return
        success_count = current["details"]["success_count"]
        failure_count = current["details"]["failure_count"]
        uninstall_count = current["details"]["uninstall_count"]
    else:
        success_count = 0
        failure_count = 0
        uninstall_count = 0
    if outcome in {"SUCCESS", "UNINSTALLED"}:
        success_count += 1
    if outcome == "RECOVERED":
        failure_count += 1
    if outcome == "UNINSTALLED":
        uninstall_count += 1
    summary = _make_audit_record(
        record_type="monthly-summary",
        record_id=f"AUDIT-MONTH-{month}",
        created_at=created_at,
        operation_id=None,
        operation=None,
        outcome="SUMMARY",
        details=_audit_details(
            success_count=success_count,
            failure_count=failure_count,
            uninstall_count=uninstall_count,
            last_operation_id=operation_id,
        ),
    )
    write_json(path, summary)
    _load_audit_record(path, "monthly-summary")


def _success_audit_record(
    plan: dict[str, Any],
    *,
    outcome: str,
    created_at: str,
    generation_id: str | None,
    binding_sha256: str | None,
) -> dict[str, Any]:
    return _make_audit_record(
        record_type="operation-receipt",
        record_id=f"AUDIT-SUCCESS-{plan['operation_id']}",
        created_at=created_at,
        operation_id=plan["operation_id"],
        operation=plan["operation"],
        outcome=outcome,
        details=_audit_details(
            plan_hash=plan["plan_hash"],
            generation_id=generation_id,
            binding_sha256=binding_sha256,
        ),
    )


def _write_success_audit_event(
    audit: Path,
    plan: dict[str, Any],
    *,
    outcome: str,
    created_at: str,
    generation_id: str | None,
    binding_sha256: str | None,
) -> Path:
    record = _success_audit_record(
        plan,
        outcome=outcome,
        created_at=created_at,
        generation_id=generation_id,
        binding_sha256=binding_sha256,
    )
    path = audit / "success" / f"{_audit_token(created_at)}--{plan['operation_id']}.audit.json"
    if not path.exists():
        _update_monthly_summary(audit, operation_id=plan["operation_id"], outcome=outcome, created_at=created_at)
    _write_exact_audit_json(path, record)
    return path


def _write_failure_audit_event(
    audit: Path,
    plan: dict[str, Any],
    envelope: dict[str, Any],
    journal: dict[str, Any],
    *,
    created_at: str,
) -> tuple[Path, Path, Path]:
    validated_plan, _ = validate_plan_envelope(envelope)
    _validate_contract("transaction-journal", journal)
    if (
        validated_plan["operation_id"] != plan["operation_id"]
        or journal["operation_id"] != plan["operation_id"]
        or journal["plan_hash"] != plan["plan_hash"]
        or journal["state"] != "FAILED"
    ):
        raise LifecycleError("TX_AUDIT_FAILURE_BINDING", "Failure audit inputs are not a complete recovered transaction bundle.")
    token = _audit_token(created_at)
    prefix = audit / "failure" / f"{token}--{plan['operation_id']}"
    record_path = Path(f"{prefix}.audit.json")
    plan_path = Path(f"{prefix}.plan.json")
    journal_path = Path(f"{prefix}.journal.json")
    record = _make_audit_record(
        record_type="failure-bundle",
        record_id=f"AUDIT-FAILURE-{plan['operation_id']}",
        created_at=created_at,
        operation_id=plan["operation_id"],
        operation=plan["operation"],
        outcome="RECOVERED",
        details=_audit_details(
            plan_hash=plan["plan_hash"],
            plan_sha256=sha256_bytes(json_bytes(envelope)),
            journal_sha256=sha256_bytes(json_bytes(journal)),
        ),
    )
    if not record_path.exists():
        _update_monthly_summary(audit, operation_id=plan["operation_id"], outcome="RECOVERED", created_at=created_at)
    _write_exact_audit_json(plan_path, envelope)
    _write_exact_audit_json(journal_path, journal)
    _write_exact_audit_json(record_path, record)
    return record_path, plan_path, journal_path


def _migrate_legacy_audit(audit: Path, state: dict[str, Any]) -> list[tuple[Path, str]]:
    retire: list[tuple[Path, str]] = []
    for bundle in state["legacy_bundles"]:
        plan = bundle["plan"]
        journal = bundle["journal"]
        created_at = _now(journal["updated_at"])
        if journal["state"] == "FAILED":
            _write_failure_audit_event(audit, plan, bundle["envelope"], journal, created_at=created_at)
        else:
            outcome = "UNINSTALLED" if plan["operation"] == "uninstall" else "SUCCESS"
            generation_id = None if outcome == "UNINSTALLED" else plan["release_identity"]["generation_id"]
            binding_sha256 = None if outcome == "UNINSTALLED" else sha256_bytes(canonical_json(plan["release_identity"]))
            _write_success_audit_event(
                audit,
                plan,
                outcome=outcome,
                created_at=created_at,
                generation_id=generation_id,
                binding_sha256=binding_sha256,
            )
        retire.extend(
            (
                (Path(bundle["plan_path"]), bundle["plan_sha256"]),
                (Path(bundle["journal_path"]), bundle["journal_sha256"]),
            )
        )
    return retire


def _archive_pre_retention_audit(
    audit: Path,
    state: dict[str, Any],
    transaction_root: Path | None,
) -> tuple[list[tuple[Path, str]], list[str]]:
    bundles = state["pre_retention_bundles"]
    residue = state["pre_retention_migration_residue"]
    if not bundles and not residue:
        return [], []
    if transaction_root is None or not transaction_root.is_dir() or _is_reparse(transaction_root):
        raise LifecycleError("TX_AUDIT_ARCHIVE_STAGE", "Historic audit migration requires one regular active transaction directory.")
    archive_root = audit / AUDIT_PRE_RETENTION_DIRECTORY
    if archive_root.exists() and (not archive_root.is_dir() or _is_reparse(archive_root)):
        raise LifecycleError("TX_AUDIT_ARCHIVE_BOUNDARY", "Historic audit archive root is not a regular directory.", str(archive_root))
    archive_root.mkdir(parents=True, exist_ok=True)
    if _is_reparse(archive_root):
        raise LifecycleError("TX_AUDIT_REPARSE", "Historic audit archive root cannot be a reparse point.", str(archive_root))
    staging_root = transaction_root / "audit-pre-retention"
    if staging_root.exists() and (not staging_root.is_dir() or _is_reparse(staging_root)):
        raise LifecycleError("TX_AUDIT_ARCHIVE_STAGE", "Historic audit migration staging root is invalid.", str(staging_root))
    staging_root.mkdir(parents=True, exist_ok=True)
    retire: list[tuple[Path, str]] = []
    archived: list[str] = []
    for bundle in bundles:
        operation_id = bundle["operation_id"]
        destination = archive_root / operation_id
        if destination.exists():
            raise LifecycleError("TX_AUDIT_ARCHIVE_COLLISION", "Historic audit archive target already exists.", str(destination))
        stage = staging_root / operation_id
        if stage.exists():
            files = {item.name: item for item in stage.iterdir() if item.is_file() and not _is_reparse(item)} if stage.is_dir() and not _is_reparse(stage) else {}
            if set(files) != {"plan.json", "journal.json"} or len(list(stage.iterdir())) != 2:
                raise LifecycleError("TX_AUDIT_ARCHIVE_STAGE", "Historic audit staging content is incomplete or untrusted.", str(stage))
            staged = _load_pre_retention_audit_bundle(operation_id, files["plan.json"], files["journal.json"])
            if staged["plan_sha256"] != bundle["plan_sha256"] or staged["journal_sha256"] != bundle["journal_sha256"]:
                raise LifecycleError("TX_AUDIT_OWNERSHIP_DRIFT", "Historic audit staging content changed after review.", str(stage))
        else:
            stage.mkdir()
            plan_stage = stage / "plan.json"
            journal_stage = stage / "journal.json"
            shutil.copyfile(Path(bundle["plan_path"]), plan_stage)
            shutil.copyfile(Path(bundle["journal_path"]), journal_stage)
            if file_sha256(plan_stage) != bundle["plan_sha256"] or file_sha256(journal_stage) != bundle["journal_sha256"]:
                raise LifecycleError("TX_AUDIT_WRITE_VERIFY", "Historic audit staging copy did not preserve exact source bytes.", str(stage))
            _load_pre_retention_audit_bundle(operation_id, plan_stage, journal_stage)
        os.replace(stage, destination)
        if not destination.is_dir() or _is_reparse(destination):
            raise LifecycleError("TX_AUDIT_WRITE_VERIFY", "Historic audit archive target is not a regular directory.", str(destination))
        files = {item.name: item for item in destination.iterdir() if item.is_file() and not _is_reparse(item)}
        if set(files) != {"plan.json", "journal.json"} or len(list(destination.iterdir())) != 2:
            raise LifecycleError("TX_AUDIT_WRITE_VERIFY", "Historic audit archive target is incomplete.", str(destination))
        archived_bundle = _load_pre_retention_audit_bundle(operation_id, files["plan.json"], files["journal.json"])
        if archived_bundle["plan_sha256"] != bundle["plan_sha256"] or archived_bundle["journal_sha256"] != bundle["journal_sha256"]:
            raise LifecycleError("TX_AUDIT_WRITE_VERIFY", "Historic audit archive did not preserve exact source bytes.", str(destination))
        retire.extend(
            (
                (Path(bundle["plan_path"]), bundle["plan_sha256"]),
                (Path(bundle["journal_path"]), bundle["journal_sha256"]),
            )
        )
        archived.append(str(destination))
    for entry in residue:
        retire.extend((Path(path), entry["root_sha256"][kind]) for kind, path in entry["root_files"].items())
    return retire, archived


def _prune_audit_state(audit: Path, state: dict[str, Any]) -> list[str]:
    deleted: list[str] = []
    success_targets = state["success_receipts"][:-AUDIT_SUCCESS_LIMIT] if len(state["success_receipts"]) > AUDIT_SUCCESS_LIMIT else []
    for entry in success_targets:
        path = Path(entry["path"])
        _remove_exact_audit_file(audit, path, entry["sha256"])
        deleted.append(str(path))
    failure_targets = state["failure_bundles"][:-AUDIT_FAILURE_LIMIT] if len(state["failure_bundles"]) > AUDIT_FAILURE_LIMIT else []
    for entry in failure_targets:
        for path_key, hash_key in (("path", "sha256"), ("plan_path", "plan_sha256"), ("journal_path", "journal_sha256")):
            path = Path(entry[path_key])
            _remove_exact_audit_file(audit, path, entry[hash_key])
            deleted.append(str(path))
    monthly_targets = state["monthly_summaries"][:-AUDIT_MONTHLY_LIMIT] if len(state["monthly_summaries"]) > AUDIT_MONTHLY_LIMIT else []
    for entry in monthly_targets:
        path = Path(entry["path"])
        _remove_exact_audit_file(audit, path, entry["sha256"])
        deleted.append(str(path))
    return deleted


def _record_audit_outcome(
    root_value: str | Path,
    *,
    plan: dict[str, Any],
    registry: dict[str, Any] | None,
    outcome: str,
    envelope: dict[str, Any] | None = None,
    journal: dict[str, Any] | None = None,
    created_at: str | None = None,
    fault_at: str | None = None,
    transaction_root: Path | None = None,
) -> dict[str, Any]:
    if outcome not in {"SUCCESS", "RECOVERED", "UNINSTALLED"}:
        raise LifecycleError("TX_AUDIT_OUTCOME", "Unsupported audit outcome.")
    operation_id = plan.get("operation_id")
    if not isinstance(operation_id, str) or not ID_PATTERN.fullmatch(operation_id):
        raise LifecycleError("TX_AUDIT_OPERATION", "Audit outcome requires a valid operation_id.")
    if plan.get("operation") not in {"install", "update", "repair", "uninstall"} or not HASH_PATTERN.fullmatch(str(plan.get("plan_hash", ""))):
        raise LifecycleError("TX_AUDIT_OPERATION", "Audit outcome requires a valid operation and plan hash.")
    root = _absolute(root_value)
    audit = root / AUDIT_RELATIVE
    before = audit_state(root, enforce_current_binding=False)
    if before["status"] != "PASS":
        raise LifecycleError("TX_AUDIT_RETENTION_BLOCKED", f"Audit retention is blocked by preserved unknown or drifted content: {before['issues']}", str(audit))
    timestamp = _now(created_at or (journal or {}).get("updated_at") or plan.get("created_at"))
    for directory in (audit, audit / "success", audit / "failure", audit / "monthly"):
        directory.mkdir(parents=True, exist_ok=True)
        if _is_reparse(directory):
            raise LifecycleError("TX_AUDIT_REPARSE", "Audit retention directory cannot be a reparse point.", str(directory))

    legacy_retire = _migrate_legacy_audit(audit, before)
    pre_retention_retire, archived_pre_retention = _archive_pre_retention_audit(audit, before, transaction_root)
    if fault_at == "AUDIT_ARCHIVE":
        raise InjectedCrash("AUDIT_ARCHIVE")
    active, active_binding_sha256 = _active_binding(registry)
    if outcome == "RECOVERED":
        if envelope is None or journal is None:
            raise LifecycleError("TX_AUDIT_FAILURE_BINDING", "Recovered audit outcome requires complete plan and journal inputs.")
        _write_failure_audit_event(audit, plan, envelope, journal, created_at=timestamp)
    else:
        receipt_outcome = "UNINSTALLED" if outcome == "UNINSTALLED" else "SUCCESS"
        if receipt_outcome == "SUCCESS" and active is None:
            raise LifecycleError("TX_AUDIT_ACTIVE_BINDING", "Successful installed operation requires one active registry binding.")
        _write_success_audit_event(
            audit,
            plan,
            outcome=receipt_outcome,
            created_at=timestamp,
            generation_id=active["generation_id"] if active is not None else None,
            binding_sha256=active_binding_sha256,
        )
    if fault_at == "AUDIT_WRITE":
        raise InjectedCrash("AUDIT_WRITE")

    current_path = audit / AUDIT_CURRENT_FILENAME
    if outcome == "UNINSTALLED":
        if current_path.exists():
            current = _load_audit_record(current_path, "current-binding")
            _remove_exact_audit_file(audit, current_path, file_sha256(current_path))
    elif outcome in {"SUCCESS", "RECOVERED"} and active is not None:
        assert active_binding_sha256 is not None
        current_operation = plan["operation"] if plan["operation"] != "uninstall" else "repair"
        current = _make_audit_record(
            record_type="current-binding",
            record_id=f"AUDIT-CURRENT-{operation_id}",
            created_at=timestamp,
            operation_id=operation_id,
            operation=current_operation,
            outcome="ACTIVE",
            details=_audit_details(
                plan_hash=plan["plan_hash"],
                generation_id=active["generation_id"],
                binding_sha256=active_binding_sha256,
            ),
        )
        _replace_current_audit_record(current_path, current)
    if fault_at == "AUDIT_PRUNE":
        raise InjectedCrash("AUDIT_PRUNE")

    staged = audit_state(root, enforce_current_binding=True)
    if staged["status"] != "PASS":
        raise LifecycleError("TX_AUDIT_RETENTION_BLOCKED", f"New audit state failed closed validation: {staged['issues']}", str(audit))
    for path, expected_sha256 in legacy_retire:
        _remove_exact_audit_file(audit, path, expected_sha256)
    for index, (path, expected_sha256) in enumerate(pre_retention_retire):
        _remove_exact_audit_file(audit, path, expected_sha256)
        if fault_at == "AUDIT_ARCHIVE_PRUNE" and index == 0:
            raise InjectedCrash("AUDIT_ARCHIVE_PRUNE")
    prunable = audit_state(root, enforce_current_binding=True)
    if prunable["status"] != "PASS":
        raise LifecycleError("TX_AUDIT_RETENTION_BLOCKED", f"Audit migration failed closed validation: {prunable['issues']}", str(audit))
    deleted = _prune_audit_state(audit, prunable)
    final = audit_state(root, enforce_current_binding=True)
    if final["status"] != "PASS" or any(final["over_limit"].values()):
        raise LifecycleError("TX_AUDIT_RETENTION_INCOMPLETE", f"Audit retention did not converge: {final}", str(audit))
    return {
        "status": "PASS",
        "writes_performed": True,
        "deleted": deleted,
        "archived_pre_retention": archived_pre_retention,
        "audit_state": final,
    }


def _commit(
    root: Path,
    context: dict[str, Any],
    journal: dict[str, Any],
    envelope: dict[str, Any],
    transaction_root: Path,
    *,
    fault_at: str | None = None,
) -> None:
    registry = _load_registry(root) or _initial_registry(root, _now(), context["selected_tools"])
    registry["lifecycle_state"] = "uninstalled" if context["operation"] == "uninstall" else "stable"
    registry["updated_at"] = _now()
    write_json(_registry_path(root), registry)
    _record_audit_outcome(
        root,
        plan=envelope["plan_contract"],
        registry=registry,
        outcome="UNINSTALLED" if context["operation"] == "uninstall" else "SUCCESS",
        created_at=journal["updated_at"],
        fault_at=fault_at,
        transaction_root=transaction_root,
    )
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
    global_boot = meta.get("global_boot")
    if isinstance(global_boot, dict) and global_boot.get("mode") == "refresh":
        source = snapshot / "global_boot.md"
        if not source.is_file():
            raise LifecycleError("TX_ROLLBACK_SNAPSHOT", "Global boot snapshot is missing.", str(source))
        _atomic_write(Path(global_boot["locator"]), source.read_bytes())
    for tool in meta["tools"]:
        tool_root = tool_roots[tool]
        current = _projection_manifest(tool_root)
        if current:
            for entry in current["entries"]:
                target = _safe_target(tool_root, entry["path"])
                if target.is_file():
                    _assert_no_reparse(tool_root, target)
                    _assert_no_hardlink(target)
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
                _assert_no_reparse(tool_root, target)
                _assert_no_hardlink(target)
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
    preview_contract = meta.get("preview_contract")
    if isinstance(preview_contract, dict):
        preview_root = Path(preview_contract["preview_root"])
        for raw_path in (preview_contract["manifest"], preview_contract["global_boot"]):
            path = Path(raw_path)
            if path.exists():
                _assert_no_reparse(preview_root, path)
                if not path.is_file():
                    raise LifecycleError("TX_ROLLBACK_DRIFT", "Preview rollback target changed type.", str(path))
                path.unlink()
        writable_roots = {
            Path(raw_root)
            for isolation in preview_contract["tool_isolation"].values()
            for raw_root in isolation["writable_roots"]
        }
        for writable_root in sorted(writable_roots, key=lambda path: len(path.parts), reverse=True):
            if writable_root.exists():
                _remove_managed(preview_root, writable_root)


def _archive_failure(root: Path, context: dict[str, Any], journal: dict[str, Any], envelope: dict[str, Any], transaction_root: Path) -> None:
    _record_audit_outcome(
        root,
        plan=envelope["plan_contract"],
        registry=_load_registry(root),
        outcome="RECOVERED",
        envelope=envelope,
        journal=journal,
        created_at=journal["updated_at"],
        transaction_root=transaction_root,
    )
    if transaction_root.exists():
        _remove_managed(root / "runtime", transaction_root)
    if _lock_path(root).exists():
        lock = load_json(_lock_path(root))
        if lock.get("operation_id") == context["operation_id"]:
            _release_lock(root, context["operation_id"])


def _rollback(root: Path, context: dict[str, Any], journal: dict[str, Any], envelope: dict[str, Any], transaction_root: Path, *, fault_at: str | None = None) -> dict[str, Any]:
    state_before_rollback = journal["state"]
    if journal["state"] not in {"DISCOVER", "LOCK"} and journal["state"] != "ROLLBACK":
        _set_state(transaction_root, journal, "ROLLBACK", evidence="lifecycle:rollback", fault_at=fault_at)
    elif journal["state"] == "ROLLBACK" and fault_at == "ROLLBACK":
        raise InjectedCrash("ROLLBACK")
    if state_before_rollback not in {"DISCOVER", "LOCK", "PLAN", "STAGE"}:
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
    transaction_active = transactions.is_dir() and any(transactions.iterdir())
    if transaction_active:
        issues.append({"code": "RS_TRANSACTION_STATE", "path": str(transactions)})
    if (root / LEGACY_RESIDUE_RELATIVE).exists():
        issues.append({"code": "RS_LEGACY_LEDGER", "path": str(root / LEGACY_RESIDUE_RELATIVE)})
    audit_report = audit_state(
        root,
        enforce_current_binding=not (transaction_active and plan_context is not None),
    )
    if audit_report["status"] != "PASS":
        issues.extend(
            {
                "code": f"RS_{item['code']}",
                "path": item["path"],
                "message": item["message"],
            }
            for item in audit_report["issues"]
        )

    ignored_audit_plan: dict[str, Any] | None = None
    context = plan_context
    if context is None:
        latest_plans = sorted((root / AUDIT_RELATIVE).glob("*.plan.json"), key=lambda path: path.stat().st_mtime) if (root / AUDIT_RELATIVE).is_dir() else []
        if latest_plans:
            try:
                latest_plan = latest_plans[-1]
                envelope = load_json(latest_plan)
                _, context = validate_plan_envelope(envelope)
                operation_id = envelope["plan_contract"]["operation_id"]
                journal_path = root / AUDIT_RELATIVE / f"{operation_id}.journal.json"
                if journal_path.is_file():
                    journal = load_json(journal_path)
                    _validate_contract("transaction-journal", journal)
                    if journal["state"] == "FAILED":
                        ignored_audit_plan = {"path": str(latest_plan), "reason": "terminal-rollback"}
                        context = None
            except LifecycleError as exc:
                ignored_audit_plan = {"path": str(latest_plans[-1]), "reason": exc.code}
                context = None

    preserved: list[dict[str, Any]] = []
    legacy_managed_hashes: dict[str, str | None] = {}
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
                    if not target.is_file():
                        issues.append({"code": "RS_PROJECTION_DRIFT", "path": str(target)})
                        continue
                    if entry.get("mode") != "managed-block":
                        if file_sha256(target) != entry["installed_sha256"]:
                            issues.append({"code": "RS_PROJECTION_DRIFT", "path": str(target)})
                        continue
                    expected_block_hash = entry.get("managed_block_sha256")
                    if expected_block_hash is None:
                        expected_block_hash = _legacy_managed_block_sha256(
                            registry,
                            entry["source_sha256"],
                            legacy_managed_hashes,
                        )
                    try:
                        observed_block_hash = _managed_block_sha256(target.read_bytes())
                    except LifecycleError:
                        observed_block_hash = None
                    if expected_block_hash is None:
                        matches = file_sha256(target) == entry["installed_sha256"]
                    else:
                        matches = observed_block_hash == expected_block_hash
                    if not matches:
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
        "audit_state": audit_report,
    }


def _execute_plan_with_artifact(
    envelope: dict[str, Any],
    expected_plan_hash: str,
    *,
    apply: bool,
    artifact: dict[str, Any] | None,
    fault_at: str | None = None,
) -> dict[str, Any]:
    plan, context = validate_plan_envelope(envelope)
    artifact = _verify_plan_inputs(plan, context, expected_plan_hash, artifact)
    if plan.get("disposition", "EXECUTE") == "NO_OP":
        return {
            "status": "NO_OP",
            "mode": "APPLY" if apply else "DRY_RUN",
            "operation_id": plan["operation_id"],
            "operation": plan["operation"],
            "plan_hash": plan["plan_hash"],
            "writes_performed": False,
        }
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
        _verify_plan_inputs(plan, context, expected_plan_hash, artifact)
        _set_state(transaction_root, journal, "PLAN", evidence="lifecycle:plan-hash", fault_at=fault_at)
        if artifact is not None:
            _stage_artifact(
                artifact,
                context["release_identity"],
                context["source_kind"],
                Path(context["staging_root"]),
            )
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
            context["global_boot"],
            context.get("preview_contract"),
        )
        _set_state(transaction_root, journal, "SNAPSHOT", evidence="lifecycle:snapshot", fault_at=fault_at)
        if artifact is not None:
            _verify_stage(
                artifact,
                context["release_identity"],
                context["source_kind"],
                Path(context["staging_root"]),
            )
        _verify_plan_inputs(plan, context, expected_plan_hash, artifact)
        _set_state(transaction_root, journal, "PREVALIDATE", evidence="lifecycle:prevalidate", fault_at=fault_at)
        _activate(root, artifact, context, plan["operation"], transaction_root)
        _set_state(transaction_root, journal, "ACTIVATE", evidence="lifecycle:activate", fault_at=fault_at)
        active_generation_root = Path(context["generation_root"]) if context["generation_root"] else None
        _refresh_global_boot(context["global_boot"], active_generation_root, plan["operation"])
        tool_paths = {tool: Path(value) for tool, value in context["tool_roots"].items()}
        _apply_projections(
            artifact,
            context["target_generation_id"],
            active_generation_root,
            tool_paths,
            plan["operation"],
            plan["user_modifications"],
        )
        _write_preview_surfaces(context, active_generation_root)
        _verify_projections(artifact, tool_paths, plan["operation"])
        _verify_global_boot(context["global_boot"], active_generation_root, plan["operation"])
        _verify_preview_surfaces(context, active_generation_root)
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
        _commit(root, context, journal, envelope, transaction_root, fault_at=fault_at)
        final_scan = scan_residue(root, context["tool_roots"], plan_context=context)
        if final_scan["status"] != "PASS":
            raise LifecycleError("TX_ZERO_RESIDUE", f"Final residue scan failed: {final_scan['issues']}")
        result = {
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
        if context.get("preview_contract") is not None:
            result.update(
                {
                    "preview_root": context["preview_contract"]["preview_root"],
                    "preview_manifest": context["preview_contract"]["manifest"],
                    "preview_generation_id": context["target_generation_id"],
                    "real_tool_integration": "PENDING",
                }
            )
        return result
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


def execute_plan(envelope: dict[str, Any], expected_plan_hash: str, *, apply: bool, fault_at: str | None = None) -> dict[str, Any]:
    _, context = validate_plan_envelope(envelope)
    source_kind = context.get("source_kind", "release-package" if context.get("release_root") is not None else "installed-generation")
    release_root = context.get("release_root") if source_kind == "release-package" else None
    repository_root = context.get("repository_root") if source_kind == "repository" else None
    with _source_artifact_scope(release_root=release_root, repository_root=repository_root) as release:
        artifact = release["artifact"] if release is not None else None
        return _execute_plan_with_artifact(
            envelope,
            expected_plan_hash,
            apply=apply,
            artifact=artifact,
            fault_at=fault_at,
        )


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
        _commit(root, context, journal, envelope, transaction_root, fault_at=fault_at)
        final = scan_residue(root, context["tool_roots"], plan_context=context)
        if final["status"] != "PASS":
            raise LifecycleError("TX_ZERO_RESIDUE", f"Recovery commit residue scan failed: {final['issues']}")
        return {"status": "RECOVERED_COMMIT", "operation_id": plan["operation_id"], "cleanup": cleanup_result, "residue_scan": final}
    if state == "FAILED":
        history = journal.get("state_history", [])
        failed_after_commit = (
            journal.get("last_completed_action") == "STATE-COMMIT"
            and len(history) >= 2
            and history[-2].get("state") == "COMMIT"
            and history[-1].get("state") == "FAILED"
            and (transaction_root / "snapshot" / "snapshot_meta.json").is_file()
        )
        if failed_after_commit:
            return _rollback(root, context, journal, envelope, transaction_root, fault_at=fault_at)
        return {"status": "FAILED", "operation_id": plan["operation_id"], "requires_manual_recovery": True}
    return _rollback(root, context, journal, envelope, transaction_root, fault_at=fault_at)


def _doctor_path_evidence(surface: str, path: Path) -> dict[str, Any]:
    path = _absolute(path)
    if not path.exists():
        return {"surface": surface, "path": str(path), "sha256": "MISSING", "status": "MISSING"}
    if _is_reparse(path):
        return {"surface": surface, "path": str(path), "sha256": "UNTRUSTED", "status": "UNTRUSTED"}
    if path.is_file():
        return {"surface": surface, "path": str(path), "sha256": file_sha256(path), "status": "PASS"}
    if path.is_dir():
        return {"surface": surface, "path": str(path), "sha256": _path_digest(path), "status": "PASS"}
    return {"surface": surface, "path": str(path), "sha256": "UNSUPPORTED", "status": "INVALID"}


def doctor(
    root_value: str | Path,
    tool_roots: dict[str, str | Path],
    *,
    checked_at: str | None = None,
) -> dict[str, Any]:
    """Inspect lifecycle trust and discovery drift without performing writes."""
    root = _absolute(root_value)
    normalized_tools = _normalize_tool_roots(tool_roots)
    selected_tools = list(normalized_tools)
    mismatches: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    tool_arguments = " ".join(
        f'--tool-root "{tool}={tool_root}"' for tool, tool_root in normalized_tools.items()
    )
    base_repair_command = f'malts lifecycle doctor-repair-plan --lifecycle-root "{root}" {tool_arguments}'

    def add_mismatch(
        code: str,
        *,
        severity: str,
        surface: str,
        expected_locator: Path | None,
        observed_locator: Path | None,
        expected: str | None,
        observed: str | None,
        trust_impact: str,
        external_required: bool = False,
    ) -> None:
        command = base_repair_command
        if external_required:
            command += ' --release-root "<verified-exact-release-root>"'
        mismatches.append(
            {
                "code": code,
                "severity": severity,
                "surface": surface,
                "expected_locator": str(_absolute(expected_locator)) if expected_locator is not None else None,
                "observed_locator": str(_absolute(observed_locator)) if observed_locator is not None else None,
                "expected": expected,
                "observed": observed,
                "trust_impact": trust_impact,
                "suggested_command": command,
            }
        )

    registry_path = _registry_path(root)
    evidence.append(_doctor_path_evidence("installation-registry", registry_path))
    registry: dict[str, Any] | None = None
    registry_invalid = False
    try:
        registry = _load_registry(root)
    except LifecycleError as exc:
        registry_invalid = True
        add_mismatch(
            "DOC_REGISTRY_MALFORMED",
            severity="CRITICAL",
            surface="installation-registry",
            expected_locator=registry_path,
            observed_locator=registry_path,
            expected="valid closed installation registry",
            observed=exc.code,
            trust_impact="CORE_INVALID",
            external_required=True,
        )
    if registry is None and not registry_invalid:
        add_mismatch(
            "DOC_REGISTRY_MISSING",
            severity="CRITICAL",
            surface="installation-registry",
            expected_locator=registry_path,
            observed_locator=None,
            expected="installed lifecycle registry",
            observed="MISSING",
            trust_impact="CORE_INVALID",
            external_required=True,
        )

    active: dict[str, Any] | None = None
    active_root: Path | None = None
    active_id: str | None = None
    if registry is not None:
        active_records = [item for item in registry["generations"] if item["state"] == "active"]
        if registry["lifecycle_state"] != "stable" or len(active_records) != 1:
            add_mismatch(
                "DOC_REGISTRY_ACTIVE_STATE",
                severity="CRITICAL",
                surface="installation-registry",
                expected_locator=registry_path,
                observed_locator=registry_path,
                expected="stable with exactly one active generation",
                observed=f"{registry['lifecycle_state']}:{len(active_records)}",
                trust_impact="CORE_INVALID",
                external_required=True,
            )
        if registry["selected_tools"] != selected_tools:
            add_mismatch(
                "DOC_REGISTRY_TOOL_SET",
                severity="ERROR",
                surface="installation-registry",
                expected_locator=registry_path,
                observed_locator=registry_path,
                expected=canonical_json(selected_tools).decode("utf-8"),
                observed=canonical_json(registry["selected_tools"]).decode("utf-8"),
                trust_impact="CORE_INVALID",
                external_required=True,
            )
        if active_records:
            active = active_records[0]
            active_id = active["generation_id"]
            active_root = Path(active["root"])
            expected_root = root / "generations" / active_id
            evidence.append(_doctor_path_evidence("active-generation", active_root))
            if registry["active_generation_id"] != active_id or active_root != expected_root:
                add_mismatch(
                    "DOC_ACTIVE_GENERATION_BINDING",
                    severity="CRITICAL",
                    surface="active-generation",
                    expected_locator=expected_root,
                    observed_locator=active_root,
                    expected=active_id,
                    observed=registry.get("active_generation_id"),
                    trust_impact="CORE_INVALID",
                    external_required=True,
                )
            try:
                installed = verify_installed_generation_envelope(active_root)
            except LifecycleError as exc:
                add_mismatch(
                    "DOC_ACTIVE_ENVELOPE_INVALID",
                    severity="CRITICAL",
                    surface="active-generation",
                    expected_locator=expected_root,
                    observed_locator=active_root if active_root.exists() else None,
                    expected="valid installed generation envelope and payload binding",
                    observed=exc.code,
                    trust_impact="CORE_INVALID",
                    external_required=True,
                )
            else:
                generation = installed["generation_manifest"]
                release_identity = installed["release_identity"]
                expected_binding = {
                    "generation_id": generation["generation_id"],
                    "version": generation["version"],
                    "artifact_sha256": generation["artifact_sha256"],
                    "release_id": release_identity["release_id"],
                    "release_manifest_sha256": release_identity["release_manifest_sha256"],
                    "release_package_sha256": release_identity["release_package_sha256"],
                    "generation_manifest_sha256": release_identity["generation_manifest_sha256"],
                    "root": str(active_root),
                }
                observed_binding = {key: active.get(key) for key in expected_binding}
                if canonical_json(expected_binding) != canonical_json(observed_binding):
                    add_mismatch(
                        "DOC_ACTIVE_REGISTRY_BINDING",
                        severity="CRITICAL",
                        surface="active-generation",
                        expected_locator=active_root,
                        observed_locator=active_root,
                        expected=canonical_json(expected_binding).decode("utf-8"),
                        observed=canonical_json(observed_binding).decode("utf-8"),
                        trust_impact="CORE_INVALID",
                        external_required=True,
                    )

    pointer_path = _pointer_path(root)
    evidence.append(_doctor_path_evidence("active-generation-pointer", pointer_path))
    if active is not None and active_root is not None:
        expected_pointer = {
            "schema_version": 1,
            "generation_id": active["generation_id"],
            "version": active["version"],
            "root": str(active_root),
            "artifact_sha256": active["artifact_sha256"],
            "release_id": active["release_id"],
            "release_manifest_sha256": active["release_manifest_sha256"],
            "release_package_sha256": active["release_package_sha256"],
            "generation_manifest_sha256": active["generation_manifest_sha256"],
        }
        if not pointer_path.exists():
            add_mismatch(
                "DOC_ACTIVE_POINTER_MISSING",
                severity="CRITICAL",
                surface="active-generation-pointer",
                expected_locator=pointer_path,
                observed_locator=None,
                expected=canonical_json(expected_pointer).decode("utf-8"),
                observed="MISSING",
                trust_impact="CORE_INVALID",
                external_required=True,
            )
        else:
            try:
                pointer = load_json(pointer_path)
            except LifecycleError as exc:
                add_mismatch(
                    "DOC_ACTIVE_POINTER_MALFORMED",
                    severity="CRITICAL",
                    surface="active-generation-pointer",
                    expected_locator=pointer_path,
                    observed_locator=pointer_path,
                    expected=canonical_json(expected_pointer).decode("utf-8"),
                    observed=exc.code,
                    trust_impact="CORE_INVALID",
                    external_required=True,
                )
            else:
                if not isinstance(pointer, dict) or canonical_json(pointer) != canonical_json(expected_pointer):
                    add_mismatch(
                        "DOC_ACTIVE_POINTER_STALE",
                        severity="CRITICAL",
                        surface="active-generation-pointer",
                        expected_locator=pointer_path,
                        observed_locator=pointer_path,
                        expected=canonical_json(expected_pointer).decode("utf-8"),
                        observed=canonical_json(pointer).decode("utf-8") if isinstance(pointer, dict) else type(pointer).__name__,
                        trust_impact="CORE_INVALID",
                        external_required=True,
                    )

    # v1.1.1: no machine-global GLOBAL_BOOT.md check. A missing or present
    # GLOBAL_BOOT.md beside the lifecycle root is intentionally not a doctor
    # input; tool boots, registry, pointer, and residue are the health surface.

    for tool, tool_root in normalized_tools.items():
        manifest_path = tool_root / PROJECTION_MANIFEST
        boot_path = tool_root / "MALTS_BOOT.md"
        evidence.append(_doctor_path_evidence(f"{tool}-projection", manifest_path))
        evidence.append(_doctor_path_evidence(f"{tool}-boot", boot_path))
        manifest: dict[str, Any] | None = None
        try:
            manifest = _projection_manifest(tool_root)
        except LifecycleError as exc:
            add_mismatch(
                "DOC_PROJECTION_MANIFEST_MALFORMED",
                severity="ERROR",
                surface=f"projection:{tool}",
                expected_locator=manifest_path,
                observed_locator=manifest_path,
                expected="valid projection manifest",
                observed=exc.code,
                trust_impact="DERIVED_ONLY",
            )
        if manifest is None:
            add_mismatch(
                "DOC_PROJECTION_MANIFEST_MISSING",
                severity="ERROR",
                surface=f"projection:{tool}",
                expected_locator=manifest_path,
                observed_locator=None,
                expected=active_id,
                observed="MISSING",
                trust_impact="DERIVED_ONLY",
            )
        elif active is not None and (
            manifest.get("generation_id") != active_id or manifest.get("artifact_sha256") != active["artifact_sha256"]
        ):
            add_mismatch(
                "DOC_PROJECTION_MANIFEST_STALE",
                severity="ERROR",
                surface=f"projection:{tool}",
                expected_locator=manifest_path,
                observed_locator=manifest_path,
                expected=f"{active_id}:{active['artifact_sha256']}",
                observed=f"{manifest.get('generation_id')}:{manifest.get('artifact_sha256')}",
                trust_impact="DERIVED_ONLY",
            )
        if manifest is not None:
            for entry in manifest.get("entries", []):
                target = _safe_target(tool_root, entry["path"])
                if not target.is_file():
                    add_mismatch(
                        "DOC_PROJECTION_FILE_MISSING",
                        severity="ERROR",
                        surface=f"projection:{tool}",
                        expected_locator=target,
                        observed_locator=None,
                        expected=entry.get("installed_sha256"),
                        observed="MISSING",
                        trust_impact="DERIVED_ONLY",
                    )
                elif file_sha256(target) != entry.get("installed_sha256"):
                    add_mismatch(
                        "DOC_PROJECTION_FILE_STALE",
                        severity="ERROR",
                        surface=f"projection:{tool}",
                        expected_locator=target,
                        observed_locator=target,
                        expected=entry.get("installed_sha256"),
                        observed=file_sha256(target),
                        trust_impact="DERIVED_ONLY",
                    )
        if active_root is not None:
            if not boot_path.exists():
                add_mismatch(
                    "DOC_TOOL_BOOT_MISSING",
                    severity="ERROR",
                    surface=f"tool-boot:{tool}",
                    expected_locator=boot_path,
                    observed_locator=None,
                    expected=str(active_root),
                    observed="MISSING",
                    trust_impact="DERIVED_ONLY",
                )
            else:
                try:
                    boot_text = boot_path.read_text(encoding="utf-8-sig")
                    boot_matches = re.findall(r"(?m)^MALTS_ROOT:\s*(.+?)\s*$", boot_text)
                except (OSError, UnicodeDecodeError):
                    boot_matches = []
                if len(boot_matches) != 1:
                    add_mismatch(
                        "DOC_TOOL_BOOT_MALFORMED",
                        severity="ERROR",
                        surface=f"tool-boot:{tool}",
                        expected_locator=boot_path,
                        observed_locator=boot_path,
                        expected=str(active_root),
                        observed="MALFORMED",
                        trust_impact="DERIVED_ONLY",
                    )
                elif _absolute(boot_matches[0]) != active_root:
                    add_mismatch(
                        "DOC_TOOL_BOOT_STALE",
                        severity="ERROR",
                        surface=f"tool-boot:{tool}",
                        expected_locator=boot_path,
                        observed_locator=boot_path,
                        expected=str(active_root),
                        observed=boot_matches[0],
                        trust_impact="DERIVED_ONLY",
                    )

    try:
        residue = scan_residue(root, normalized_tools)
    except LifecycleError as exc:
        add_mismatch(
            "DOC_RESIDUE_SCAN_INVALID",
            severity="ERROR",
            surface="lifecycle-residue",
            expected_locator=root,
            observed_locator=root,
            expected="readable residue state",
            observed=exc.code,
            trust_impact="CORE_INVALID",
            external_required=True,
        )
    else:
        if residue["status"] != "PASS":
            add_mismatch(
                "DOC_RESIDUE_DETECTED",
                severity="WARNING",
                surface="lifecycle-residue",
                expected_locator=root,
                observed_locator=root,
                expected="PASS",
                observed=canonical_json(residue["issues"]).decode("utf-8"),
                trust_impact="INFORMATIONAL",
            )

    core_invalid = any(item["trust_impact"] == "CORE_INVALID" for item in mismatches)
    derived_drift = any(item["trust_impact"] == "DERIVED_ONLY" for item in mismatches)
    if registry is None and not registry_invalid:
        status = "NOT_INSTALLED"
        core_trust = "UNAVAILABLE"
        trusted_source = "NONE"
    elif core_invalid:
        status = "UNTRUSTED"
        core_trust = "EXTERNAL_SOURCE_REQUIRED"
        trusted_source = "VERIFIED_EXTERNAL_REQUIRED"
    elif derived_drift or mismatches:
        status = "DEGRADED"
        core_trust = "LOCALLY_CONSISTENT"
        trusted_source = "ACTIVE_GENERATION"
    else:
        status = "HEALTHY"
        core_trust = "LOCALLY_CONSISTENT"
        trusted_source = "ACTIVE_GENERATION"
    commands = list(dict.fromkeys(item["suggested_command"] for item in mismatches))
    report = {
        "schema_version": 1,
        "status": status,
        "mode": "READ_ONLY",
        "writes_performed": False,
        "lifecycle_root": str(root),
        "selected_tools": selected_tools,
        "active_generation_id": active_id,
        "core_trust": core_trust,
        "trusted_repair_source": trusted_source,
        "mismatches": mismatches,
        "evidence": evidence,
        "suggested_commands": commands,
        "checked_at": _now(checked_at),
    }
    _validate_contract("lifecycle-doctor-report", report)
    return report


def make_doctor_repair_plan(
    *,
    lifecycle_root: str | Path,
    tool_roots: dict[str, str | Path],
    release_root: str | Path | None = None,
    repository_root: str | Path | None = None,
    operation_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    if release_root is not None and repository_root is not None:
        raise LifecycleError("TX_SOURCE_INPUT", "Choose exactly one verified external repair source.")
    root = _absolute(lifecycle_root)
    normalized_tools = _normalize_tool_roots(tool_roots)
    tool_arguments = " ".join(
        f'--tool-root "{tool}={tool_root}"' for tool, tool_root in normalized_tools.items()
    )
    report = doctor(root, normalized_tools, checked_at=created_at)
    registry = _load_registry(root)
    active = _active_generation_record(registry)
    if active is None:
        raise LifecycleError("TX_REPAIR_EXTERNAL_SOURCE_REQUIRED", "Repair planning requires a readable active binding and exact verified external source.", str(root))
    external_supplied = release_root is not None or repository_root is not None
    if not external_supplied:
        if report["core_trust"] != "LOCALLY_CONSISTENT":
            raise LifecycleError(
                "TX_REPAIR_EXTERNAL_SOURCE_REQUIRED",
                "Core lifecycle trust is invalid; provide a verified ReleaseRoot or RepositoryRoot matching the installed binding.",
                str(root),
            )
        targets = sorted(
            {
                item["expected_locator"]
                for item in report["mismatches"]
                if item["trust_impact"] == "DERIVED_ONLY" and item["expected_locator"] is not None
            },
            key=str.casefold,
        )
        return {
            "schema_version": 1,
            "status": "PASS",
            "mode": "REVIEW_ONLY",
            "writes_performed": False,
            "executable": False,
            "trusted_source": {
                "kind": "active-generation",
                "root": active["root"],
                "generation_id": active["generation_id"],
                "artifact_sha256": active["artifact_sha256"],
            },
            "doctor_status": report["status"],
            "targets": targets,
            "suggested_apply_command": f'malts lifecycle doctor-repair-plan --lifecycle-root "{root}" {tool_arguments} --release-root "<verified-exact-release-root>"',
        }

    with _source_artifact_scope(release_root=release_root, repository_root=repository_root) as source:
        if source is None:
            raise LifecycleError("TX_REPAIR_EXTERNAL_SOURCE_REQUIRED", "Verified external repair source is missing.")
        identity = source["identity"]
        fields = (
            "release_id", "release_manifest_sha256", "release_package_sha256", "artifact_sha256",
            "generation_id", "generation_manifest_sha256",
        )
        if any(identity[field] != active.get(field) for field in fields):
            raise LifecycleError(
                "TX_REPAIR_SOURCE_BINDING",
                "Verified external source does not match the exact installed release and artifact binding.",
                str(identity["release_root"]),
            )
    envelope = make_plan(
        operation="repair",
        lifecycle_root=root,
        tool_roots=normalized_tools,
        release_root=release_root,
        repository_root=repository_root,
        operation_id=operation_id,
        created_at=created_at,
    )
    return {
        "schema_version": 1,
        "status": "PASS",
        "mode": "REVIEW_ONLY",
        "writes_performed": False,
        "executable": True,
        "trusted_source": {
            "kind": "verified-external",
            "root": str(_absolute(release_root if release_root is not None else repository_root)),
            "generation_id": active["generation_id"],
            "artifact_sha256": active["artifact_sha256"],
        },
        "doctor_status": report["status"],
        "targets": sorted(
            {item["expected_locator"] for item in report["mismatches"] if item["expected_locator"] is not None},
            key=str.casefold,
        ),
        "plan": envelope,
    }


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
    plan.add_argument("--repository-root")
    plan.add_argument("--legacy-root", action="append", default=[])
    plan.add_argument("--default-legacy-root", default=str(Path.home() / ".malts"))
    plan.add_argument("--operation-id")
    plan.add_argument("--timestamp")
    plan.add_argument("--modification-overrides")
    plan.add_argument("--out")
    plan.add_argument("--apply", action="store_true")

    preview_plan = subparsers.add_parser("preview-plan")
    preview_plan.add_argument("--preview-root")
    preview_plan.add_argument("--release-root")
    preview_plan.add_argument("--repository-root")
    preview_plan.add_argument("--protected-root", action="append", default=[])
    preview_plan.add_argument("--tool", action="append", choices=TOOLS, default=[])
    preview_plan.add_argument("--operation-id")
    preview_plan.add_argument("--timestamp")
    preview_plan.add_argument("--out")
    preview_plan.add_argument("--apply", action="store_true")

    execute = subparsers.add_parser("execute")
    execute.add_argument("--plan", required=True)
    execute.add_argument("--expected-plan-hash", required=True)
    execute.add_argument("--fault-at", choices=(*STATES, "ROLLBACK", "AUDIT_WRITE", "AUDIT_PRUNE"))
    execute.add_argument("--apply", action="store_true")

    recover = subparsers.add_parser("recover")
    recover.add_argument("--lifecycle-root", required=True)
    recover.add_argument("--operation-id")
    recover.add_argument("--fault-at", choices=("ROLLBACK", "COMMIT", "AUDIT_WRITE", "AUDIT_PRUNE"))
    recover.add_argument("--apply", action="store_true")

    scan = subparsers.add_parser("scan")
    scan.add_argument("--lifecycle-root", required=True)
    scan.add_argument("--tool-root", action="append", default=[], required=True)

    discover = subparsers.add_parser("discover")
    discover.add_argument("--tool-root", required=True)
    discover.add_argument("--lifecycle-root")
    discover.add_argument("--global-boot")

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--lifecycle-root", required=True)
    inspect.add_argument("--tool-root", action="append", default=[], required=True)

    doctor_command = subparsers.add_parser("doctor")
    doctor_command.add_argument("--lifecycle-root", required=True)
    doctor_command.add_argument("--tool-root", action="append", default=[], required=True)
    doctor_command.add_argument("--timestamp")

    doctor_repair = subparsers.add_parser("doctor-repair-plan")
    doctor_repair.add_argument("--lifecycle-root", required=True)
    doctor_repair.add_argument("--tool-root", action="append", default=[], required=True)
    doctor_repair.add_argument("--release-root")
    doctor_repair.add_argument("--repository-root")
    doctor_repair.add_argument("--operation-id")
    doctor_repair.add_argument("--timestamp")
    doctor_repair.add_argument("--out")
    doctor_repair.add_argument("--apply", action="store_true")

    verify_release = subparsers.add_parser("verify-release")
    verify_release.add_argument("--release-root", required=True)
    verify_repository = subparsers.add_parser("verify-repository")
    verify_repository.add_argument("--repository-root", required=True)
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
                repository_root=args.repository_root,
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
        elif args.command == "preview-plan":
            envelope = make_preview_plan(
                preview_root=args.preview_root,
                release_root=args.release_root,
                repository_root=args.repository_root,
                protected_roots=args.protected_root,
                tools=args.tool or None,
                operation_id=args.operation_id,
                created_at=args.timestamp,
            )
            if args.apply:
                if not args.out:
                    raise LifecycleError("TX_PLAN_OUTPUT", "--apply requires --out for a preview plan.")
                output = _absolute(args.out)
                if output.exists():
                    raise LifecycleError("TX_PLAN_OUTPUT", "Refusing to overwrite an existing preview plan.", str(output))
                write_json(output, envelope)
            result = {
                "status": "PASS",
                "mode": "APPLY" if args.apply else "DRY_RUN",
                "writes_performed": args.apply,
                "plan_hash": envelope["plan_contract"]["plan_hash"],
                "preview_root": envelope["execution_context"]["preview_contract"]["preview_root"],
                "plan": envelope,
            }
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
        elif args.command == "discover":
            result = resolve_discovery(
                args.tool_root,
                lifecycle_root=args.lifecycle_root,
                global_boot=args.global_boot,
            )
        elif args.command == "scan":
            result = scan_residue(args.lifecycle_root, _parse_tool_roots(args.tool_root))
            result.update({"mode": "READ_ONLY", "writes_performed": False})
        elif args.command == "doctor":
            result = doctor(
                args.lifecycle_root,
                _parse_tool_roots(args.tool_root),
                checked_at=args.timestamp,
            )
        elif args.command == "doctor-repair-plan":
            result = make_doctor_repair_plan(
                lifecycle_root=args.lifecycle_root,
                tool_roots=_parse_tool_roots(args.tool_root),
                release_root=args.release_root,
                repository_root=args.repository_root,
                operation_id=args.operation_id,
                created_at=args.timestamp,
            )
            if args.apply:
                if not result["executable"]:
                    raise LifecycleError(
                        "TX_REPAIR_PLAN_NOT_EXECUTABLE",
                        "The review-only repair recommendation is not an executable transaction plan.",
                    )
                if not args.out:
                    raise LifecycleError("TX_PLAN_OUTPUT", "--apply requires --out for a doctor repair plan.")
                output = _absolute(args.out)
                if output.exists():
                    raise LifecycleError("TX_PLAN_OUTPUT", "Refusing to overwrite an existing doctor repair plan.", str(output))
                write_json(output, result["plan"])
                result = {**result, "mode": "APPLY", "writes_performed": True, "plan_output": str(output)}
        elif args.command == "verify-release":
            result = verify_release_root(args.release_root)
            result = {**result["verified"], "mode": "READ_ONLY", "writes_performed": False}
        elif args.command == "verify-repository":
            verified = verify_repository_root(args.repository_root)
            result = {
                "status": "PASS",
                "mode": "READ_ONLY",
                "writes_performed": False,
                "repository_root": str(verified["root"]),
                "release_id": verified["identity"]["release_id"],
                "version": verified["identity"]["version"],
                "user_file_count": len(verified["records"]),
                "source_tree_sha256": verified["identity"]["source_tree_sha256"],
            }
        else:
            result = semantic_state(args.lifecycle_root, _parse_tool_roots(args.tool_root))
            residue_status = result.get("residue", {}).get("status")
            result.update(
                {
                    "status": "FAIL" if residue_status == "FAIL" else "PASS",
                    "mode": "READ_ONLY",
                    "writes_performed": False,
                }
            )
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
    return 0 if result.get("status") in {"PASS", "HEALTHY", "NO_OP", "RECOVERED_COMMIT", "RECOVERED_ROLLBACK"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
