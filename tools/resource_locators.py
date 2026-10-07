#!/usr/bin/env python3
"""Typed, product-neutral resource locator normalization and conflict tests."""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


LOCATOR_KINDS = {"PATH", "ARTIFACT", "RECORD", "SERVICE", "DEVICE", "ENVIRONMENT"}
LOCATOR_SCOPES = {"WORKSPACE", "EXTERNAL", "GLOBAL"}
LOCATOR_ACCESS = {"READ", "WRITE"}
LOCATOR_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
LOGICAL_VALUE = re.compile(r"^[^\x00-\x1f\x7f]{1,2048}$")
FILE_ID_PREFIX = "MALTS-FILE-ID:"


class LocatorError(ValueError):
    def __init__(self, code: str, message: str, detail: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


@dataclass(frozen=True)
class Conflict:
    left_locator_id: str
    right_locator_id: str
    kind: str
    relationship: str
    left_value: str
    right_value: str

    def as_dict(self) -> dict[str, str]:
        return {
            "left_locator_id": self.left_locator_id,
            "right_locator_id": self.right_locator_id,
            "kind": self.kind,
            "relationship": self.relationship,
            "left_value": self.left_value,
            "right_value": self.right_value,
        }


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _require_mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LocatorError("LOCATOR_INVALID", "A resource locator must be an object.", value)
    return value


def _normalized_absolute_path(value: Path | str) -> str:
    absolute = os.path.abspath(os.path.normpath(str(value)))
    normalized = os.path.normcase(absolute) if os.name == "nt" else absolute
    return normalized.replace("\\", "/")


def _canonical_path(workspace: Path, value: str, scope: str) -> str:
    if "\x00" in value or not value.strip():
        raise LocatorError("LOCATOR_PATH_INVALID", "A PATH locator must contain a non-empty filesystem path.", value)
    if value.startswith("~") or re.search(r"(?:^|[\\/])(?:\$\{|%)[^\\/]+", value):
        raise LocatorError("LOCATOR_PATH_DYNAMIC", "PATH locators cannot contain home or environment expansion syntax.", value)
    workspace_absolute = os.path.abspath(os.path.normpath(str(workspace)))
    candidate = Path(value)
    if scope == "WORKSPACE":
        candidate_absolute = os.path.abspath(os.path.normpath(str(candidate if candidate.is_absolute() else workspace / candidate)))
        try:
            if os.path.commonpath((workspace_absolute, candidate_absolute)) != workspace_absolute:
                raise LocatorError("LOCATOR_PATH_ESCAPE", "A WORKSPACE PATH locator escapes the workspace root.", value)
        except ValueError as exc:
            raise LocatorError("LOCATOR_PATH_ESCAPE", "A WORKSPACE PATH locator is on a different path root.", value) from exc
    elif scope == "EXTERNAL":
        if not candidate.is_absolute():
            raise LocatorError("LOCATOR_PATH_ABSOLUTE_REQUIRED", "An EXTERNAL PATH locator must be absolute.", value)
        candidate_absolute = os.path.abspath(os.path.normpath(str(candidate)))
    else:
        raise LocatorError("LOCATOR_SCOPE_INVALID", "PATH locators use WORKSPACE or EXTERNAL scope.", scope)
    return _normalized_absolute_path(candidate_absolute)


def _physical_error_code(exc: BaseException) -> str:
    if isinstance(exc, PermissionError):
        return "LOCATOR_PHYSICAL_PATH_PERMISSION_DENIED"
    if isinstance(exc, RuntimeError):
        return "LOCATOR_PHYSICAL_PATH_LOOP"
    return "LOCATOR_PHYSICAL_PATH_UNREADABLE"


def _physical_path_identity(canonical_path: str) -> dict[str, Any]:
    """Resolve one path through its nearest existing ancestor without creating it."""

    candidate = Path(canonical_path)
    cursor = candidate
    unresolved: list[str] = []
    try:
        while not os.path.lexists(str(cursor)):
            parent = cursor.parent
            if parent == cursor:
                return {
                    "status": "UNKNOWN",
                    "physical_path": None,
                    "file_id": None,
                    "error": "LOCATOR_PHYSICAL_ANCESTOR_MISSING",
                }
            unresolved.append(cursor.name)
            cursor = parent
        resolved_ancestor = cursor.resolve(strict=True)
        physical = resolved_ancestor.joinpath(*reversed(unresolved))
        physical_path = _normalized_absolute_path(physical)
        file_id = None
        if not unresolved:
            stat_result = os.stat(str(candidate), follow_symlinks=True)
            device = int(stat_result.st_dev)
            inode = int(stat_result.st_ino)
            if inode <= 0:
                return {
                    "status": "UNKNOWN",
                    "physical_path": physical_path,
                    "file_id": None,
                    "error": "LOCATOR_PHYSICAL_FILE_ID_UNAVAILABLE",
                }
            file_payload = {"device": device, "inode": inode}
            file_id = FILE_ID_PREFIX + hashlib.sha256(_canonical_json(file_payload)).hexdigest().upper()
        return {"status": "KNOWN", "physical_path": physical_path, "file_id": file_id, "error": None}
    except (OSError, RuntimeError) as exc:
        return {
            "status": "UNKNOWN",
            "physical_path": None,
            "file_id": None,
            "error": _physical_error_code(exc),
        }


def _canonical_logical(kind: str, value: str, scope: str) -> str:
    if scope not in {"WORKSPACE", "GLOBAL"}:
        raise LocatorError("LOCATOR_SCOPE_INVALID", f"{kind} locators use WORKSPACE or GLOBAL scope.", scope)
    stripped = value.strip()
    if stripped != value or LOGICAL_VALUE.fullmatch(value) is None:
        raise LocatorError("LOCATOR_VALUE_INVALID", f"{kind} locator values must be stable, non-control text.", value)
    return value.casefold()


def normalize_locator(workspace: Path | str, value: Mapping[str, Any]) -> dict[str, Any]:
    """Return one closed, deterministic locator representation."""

    raw = _require_mapping(value)
    required_keys = {"schema_version", "locator_id", "kind", "scope", "access", "value", "aliases"}
    expected_keys = {*required_keys, "backing_paths"}
    unknown = sorted(set(raw) - expected_keys)
    missing = sorted(required_keys - set(raw))
    if unknown or missing:
        raise LocatorError("LOCATOR_SHAPE_INVALID", "A locator has missing or unknown fields.", {"missing": missing, "unknown": unknown})
    if raw.get("schema_version") != 1:
        raise LocatorError("LOCATOR_VERSION_UNSUPPORTED", "Only resource Locator schema_version 1 is supported.", raw.get("schema_version"))
    locator_id = raw.get("locator_id")
    kind = raw.get("kind")
    scope = raw.get("scope")
    access = raw.get("access")
    raw_value = raw.get("value")
    aliases = raw.get("aliases")
    backing_paths = raw.get("backing_paths", [])
    if not isinstance(locator_id, str) or LOCATOR_ID.fullmatch(locator_id) is None:
        raise LocatorError("LOCATOR_ID_INVALID", "locator_id violates the stable identifier contract.", locator_id)
    if kind not in LOCATOR_KINDS:
        raise LocatorError("LOCATOR_KIND_INVALID", "Unknown resource locator kind.", kind)
    if scope not in LOCATOR_SCOPES:
        raise LocatorError("LOCATOR_SCOPE_INVALID", "Unknown resource locator scope.", scope)
    if access not in LOCATOR_ACCESS:
        raise LocatorError("LOCATOR_ACCESS_INVALID", "Unknown resource locator access mode.", access)
    if not isinstance(raw_value, str):
        raise LocatorError("LOCATOR_VALUE_INVALID", "A resource locator value must be a string.", raw_value)
    if not isinstance(aliases, list) or len(aliases) > 32 or any(not isinstance(item, str) for item in aliases):
        raise LocatorError("LOCATOR_ALIASES_INVALID", "aliases must be a bounded list of strings.", aliases)
    if len(set(aliases)) != len(aliases):
        raise LocatorError("LOCATOR_ALIASES_INVALID", "aliases must be unique before normalization.", aliases)
    if not isinstance(backing_paths, list) or len(backing_paths) > 16:
        raise LocatorError("LOCATOR_BACKING_PATHS_INVALID", "backing_paths must be a bounded array.", backing_paths)
    normalized_backing_inputs: list[dict[str, str]] = []
    for item in backing_paths:
        if not isinstance(item, Mapping) or set(item) != {"scope", "value"}:
            raise LocatorError("LOCATOR_BACKING_PATH_INVALID", "Each backing path must contain only scope and value.", item)
        backing_scope = item.get("scope")
        backing_value = item.get("value")
        if backing_scope not in {"WORKSPACE", "EXTERNAL"} or not isinstance(backing_value, str):
            raise LocatorError("LOCATOR_BACKING_PATH_INVALID", "Backing paths use WORKSPACE or EXTERNAL scope and a string value.", item)
        normalized_backing_inputs.append({"scope": str(backing_scope), "value": backing_value})
    if kind != "ARTIFACT" and normalized_backing_inputs:
        raise LocatorError("LOCATOR_BACKING_PATH_KIND_INVALID", "Only ARTIFACT locators may declare backing_paths.", kind)
    if len({(item["scope"], item["value"]) for item in normalized_backing_inputs}) != len(normalized_backing_inputs):
        raise LocatorError("LOCATOR_BACKING_PATHS_INVALID", "backing_paths must be unique before normalization.", backing_paths)

    root = Path(workspace).resolve(strict=False)
    canonicalize = (
        (lambda item: _canonical_path(root, item, str(scope)))
        if kind == "PATH"
        else (lambda item: _canonical_logical(str(kind), item, str(scope)))
    )
    canonical_value = canonicalize(raw_value)
    canonical_aliases = sorted({canonicalize(item) for item in aliases} - {canonical_value})
    canonical_backing_paths = sorted(
        [
            {"scope": item["scope"], "canonical_value": _canonical_path(root, item["value"], item["scope"])}
            for item in normalized_backing_inputs
        ],
        key=lambda item: (item["scope"], item["canonical_value"]),
    )
    path_inputs = (
        [canonical_value, *canonical_aliases]
        if kind == "PATH"
        else [item["canonical_value"] for item in canonical_backing_paths]
    )
    physical_rows = [_physical_path_identity(item) for item in path_inputs]
    physical_paths = sorted({str(item["physical_path"]) for item in physical_rows if item["physical_path"] is not None})
    physical_file_ids = sorted({str(item["file_id"]) for item in physical_rows if item["file_id"] is not None})
    physical_errors = sorted({str(item["error"]) for item in physical_rows if item["error"] is not None})
    physical_status = "NOT_APPLICABLE" if not path_inputs else ("UNKNOWN" if physical_errors else "KNOWN")
    physical_payload = {
        "canonical_backing_paths": canonical_backing_paths,
        "physical_paths": physical_paths,
        "physical_file_ids": physical_file_ids,
        "physical_identity_status": physical_status,
        "physical_identity_errors": physical_errors,
    }
    identity_payload = {
        "kind": kind,
        "scope": scope,
        "canonical_value": canonical_value,
        "canonical_aliases": canonical_aliases,
        **physical_payload,
    }
    return {
        "schema_version": 1,
        "locator_id": locator_id,
        "kind": kind,
        "scope": scope,
        "access": access,
        "value": raw_value,
        "aliases": list(aliases),
        "backing_paths": normalized_backing_inputs,
        "canonical_value": canonical_value,
        "canonical_aliases": canonical_aliases,
        **physical_payload,
        "physical_identity_sha256": hashlib.sha256(_canonical_json(physical_payload)).hexdigest().upper(),
        "identity_sha256": hashlib.sha256(_canonical_json(identity_payload)).hexdigest().upper(),
    }


def _identities(locator: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple([str(locator["canonical_value"]), *[str(item) for item in locator.get("canonical_aliases", [])]])


def _path_identities(locator: Mapping[str, Any]) -> tuple[str, ...]:
    values: set[str] = set()
    if locator.get("kind") == "PATH":
        values.update(_identities(locator))
    for item in locator.get("canonical_backing_paths", []):
        if isinstance(item, Mapping) and isinstance(item.get("canonical_value"), str):
            values.add(str(item["canonical_value"]))
    values.update(str(item) for item in locator.get("physical_paths", []))
    values.update(str(item) for item in locator.get("physical_file_ids", []))
    return tuple(sorted(values, key=lambda item: (item.startswith(FILE_ID_PREFIX), item)))


def _path_relationship(left: str, right: str) -> str | None:
    if left == right:
        return "EXACT"
    if left.startswith(FILE_ID_PREFIX) or right.startswith(FILE_ID_PREFIX):
        return None
    try:
        common = os.path.commonpath((left, right)).replace("\\", "/")
    except ValueError:
        return None
    if common == left:
        return "LEFT_PARENT"
    if common == right:
        return "RIGHT_PARENT"
    return None


def locator_conflict(left: Mapping[str, Any], right: Mapping[str, Any]) -> Conflict | None:
    """Return a conflict when identities overlap and either side can write."""

    if left.get("access") != "WRITE" and right.get("access") != "WRITE":
        return None
    left_kind = str(left["kind"])
    right_kind = str(right["kind"])
    if left_kind == right_kind and left_kind != "PATH":
        for left_value in _identities(left):
            for right_value in _identities(right):
                if left_value != right_value:
                    continue
                return Conflict(
                    left_locator_id=str(left["locator_id"]),
                    right_locator_id=str(right["locator_id"]),
                    kind=left_kind,
                    relationship="EXACT",
                    left_value=left_value,
                    right_value=right_value,
                )
    for left_value in _path_identities(left):
        for right_value in _path_identities(right):
            relationship = _path_relationship(left_value, right_value)
            if relationship is not None:
                return Conflict(
                    left_locator_id=str(left["locator_id"]),
                    right_locator_id=str(right["locator_id"]),
                    kind="PATH",
                    relationship="PHYSICAL_FILE_ID" if left_value.startswith(FILE_ID_PREFIX) else relationship,
                    left_value=left_value,
                    right_value=right_value,
                )
    return None


def legacy_lease_conflict(left: Mapping[str, str], right: Mapping[str, str]) -> Conflict | None:
    """Lexical compatibility only; callers still need physical identity/Host enforcement."""
    def normalized(lease, identifier):
        value=lease['locator'].replace('\\','/')
        kind='OPAQUE' if '://' in value else 'PATH'
        canonical=value if kind=='OPAQUE' else posixpath.normpath(value)
        if os.name=='nt' and kind=='PATH':
            canonical=canonical.casefold()
        return {'locator_id':identifier,'kind':kind,'access':lease['access'].upper(),
                'canonical_value':canonical,'canonical_aliases':[]}
    return locator_conflict(normalized(left,'requested'),normalized(right,'held'))


def find_conflicts(requested: Sequence[Mapping[str, Any]], held: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    conflicts = []
    for left in requested:
        for right in held:
            conflict = locator_conflict(left, right)
            if conflict is not None:
                conflicts.append(conflict.as_dict())
    return sorted(
        conflicts,
        key=lambda item: (
            item["left_locator_id"].casefold(),
            item["right_locator_id"].casefold(),
            item["kind"],
            item["relationship"],
        ),
    )


def normalize_locators(workspace: Path | str, values: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized = [normalize_locator(workspace, value) for value in values]
    locator_ids = [item["locator_id"] for item in normalized]
    if len(locator_ids) != len(set(locator_ids)):
        raise LocatorError("LOCATOR_ID_DUPLICATE", "locator_id values must be unique within one request.", locator_ids)
    identities = [(item["kind"], item["scope"], item["identity_sha256"], item["access"]) for item in normalized]
    if len(identities) != len(set(identities)):
        raise LocatorError("LOCATOR_IDENTITY_DUPLICATE", "Equivalent locator identities must not be repeated in one request.")
    return sorted(normalized, key=lambda item: (item["kind"], item["canonical_value"], item["locator_id"]))


def locator_domain(
    locator: Mapping[str, Any],
    canonical_value: str | None = None,
    *,
    kind: str | None = None,
    scope: str | None = None,
) -> dict[str, str]:
    value = canonical_value or str(locator["canonical_value"])
    payload = {"kind": kind or locator["kind"], "scope": scope or locator["scope"], "canonical_value": value}
    return {
        **payload,
        "domain_id": "LOC-" + hashlib.sha256(_canonical_json(payload)).hexdigest().upper()[:32],
    }


def locator_domains(locator: Mapping[str, Any]) -> list[dict[str, str]]:
    rows: dict[tuple[str, str, str], dict[str, str]] = {}
    if locator.get("kind") != "PATH":
        for value in _identities(locator):
            row = locator_domain(locator, value)
            rows[(row["kind"], row["scope"], row["canonical_value"])] = row
    path_scopes = {
        str(item.get("canonical_value")): str(item.get("scope"))
        for item in locator.get("canonical_backing_paths", [])
        if isinstance(item, Mapping)
    }
    for value in _path_identities(locator):
        row = locator_domain(
            locator,
            value,
            kind="PATH",
            scope=path_scopes.get(value, str(locator.get("scope", "WORKSPACE"))),
        )
        rows[(row["kind"], row["scope"], row["canonical_value"])] = row
    return sorted(rows.values(), key=lambda item: (item["kind"], item["scope"], item["canonical_value"]))
