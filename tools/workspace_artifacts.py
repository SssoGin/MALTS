#!/usr/bin/env python3
"""Bounded read-only Artifact Lifecycle inspection for MALTS workspaces."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


SECTION_LINE = re.compile(r"^<!-- MALTS:section=(?P<name>[a-z0-9-]+) -->[ \t]*\r?$", re.IGNORECASE | re.MULTILINE)
OWNER_HEADERS = (
    "Artifact ID",
    "Role",
    "Locator",
    "Authority",
    "VCS",
    "Verification",
    "Retention",
    "Disposition",
    "Relationships",
    "Role Contract",
)
SHARED_HEADERS = (
    "Shared ID",
    "Purpose",
    "Applies To",
    "Locator",
    "Authority",
    "VCS",
    "Status",
    "Source",
    "Maintainer",
    "Retention",
    "Last Verified",
    "Relationships",
)
ARCHIVE_HEADERS = (
    "Archive ID",
    "Locator",
    "Authority",
    "VCS",
    "Original Owner",
    "Archived At",
    "Reason",
    "Successor",
    "Manifest",
    "Relationships",
)
ROLES = {"WORKING", "DELIVERABLE", "EVIDENCE", "RECOVERY"}
AUTHORITIES = {"WORKSPACE", "SOURCE_PROJECT", "EXTERNAL", "GENERATED"}
VCS_STATES = {"LOCAL_ONLY", "GIT_TRACKED", "SVN_TRACKED", "UNTRACKED", "EXTERNAL", "UNKNOWN"}
VERIFICATION_STATES = {"UNVERIFIED", "PASS", "FAIL", "STALE"}
DISPOSITIONS = {"KEEP_OWNED", "PROMOTE_SHARED", "ARCHIVE", "RUNTIME_RECREATABLE", "SUPERSEDED", "UNRESOLVED"}
RELATIONS = {"MIRROR_OF", "GENERATED_FROM", "SUPERSEDES", "SUPERSEDED_BY", "EVIDENCE_FOR", "RECOVERY_FOR"}
ARTIFACT_REF = re.compile(
    r"^(?:phase:[A-Za-z0-9._-]+:ART-[0-9]{3,}|session:[A-Za-z0-9._-]+:ART-[0-9]{3,}|"
    r"shared:SHR-[0-9]{3,}|archive:ARC-[0-9]{3,})$"
)
OWNER_REF = re.compile(r"^(?:phase|session):[A-Za-z0-9._-]+$")
EXTERNAL_REF = re.compile(r"^(?:external|task|result|diagnosis|acceptance):[A-Za-z0-9._:/-]+$|^AC-[A-Za-z0-9._-]+$")
URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
PLACEHOLDERS = {"", "N/A", "NA", "NONE", "UNKNOWN", "TBD", "TODO"}
ARTIFACT_REFERENCE_IN_TEXT = re.compile(
    r"(?:phase:[A-Za-z0-9._-]+:ART-[0-9]{3,}|session:[A-Za-z0-9._-]+:ART-[0-9]{3,}|"
    r"shared:SHR-[0-9]{3,}|archive:ARC-[0-9]{3,})"
)
SHARED_INDEX_PREAMBLE = """# SHARED_ARTIFACT_INDEX

<!-- MALTS:section=shared-artifacts -->
## Shared Artifact Registry

"""
ARCHIVE_INDEX_PREAMBLE = """# ARCHIVE_ARTIFACT_INDEX

<!-- MALTS:section=archive-artifacts -->
## Archive Artifact Registry

"""


class ArtifactMutationError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Any | None = None, *, blocked: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
        self.blocked = blocked


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _read_markdown(path: Path) -> tuple[bytes, str]:
    data = path.read_bytes()
    return data, data.decode("utf-8-sig")


def _section(text: str, name: str) -> str | None:
    markers = list(SECTION_LINE.finditer(text))
    matches = [index for index, marker in enumerate(markers) if marker.group("name").lower() == name.lower()]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError(f"MALTS section must appear exactly once: {name}")
    index = matches[0]
    start = markers[index].start()
    end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
    return text[start:end]


def _field(section: str, label: str) -> str:
    pattern = re.compile(rf"(?m)^- {re.escape(label)}:[ \t]*(?P<value>[^\r\n]*?)[ \t]*\r?$")
    matches = list(pattern.finditer(section))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one '- {label}:' field.")
    value = matches[0].group("value").strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    if not value:
        raise ValueError(f"Field must not be empty: {label}")
    return value


def _cells(line: str) -> list[str]:
    return [value.strip().replace("\\|", "|") for value in line.strip().strip("|").split("|")]


def _table(section: str, expected_headers: tuple[str, ...]) -> list[dict[str, str]]:
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|") and line.strip().endswith("|")]
    if len(lines) < 2 or tuple(_cells(lines[0])) != expected_headers:
        raise ValueError("Registry table headers do not match the canonical schema.")
    delimiter = _cells(lines[1])
    if len(delimiter) != len(expected_headers) or not all(re.fullmatch(r":?-{3,}:?", item.replace(" ", "")) for item in delimiter):
        raise ValueError("Registry table delimiter does not match the canonical schema.")
    rows: list[dict[str, str]] = []
    for line in lines[2:]:
        values = _cells(line)
        if len(values) != len(expected_headers):
            raise ValueError("Registry row column count does not match the canonical schema.")
        rows.append(dict(zip(expected_headers, values)))
    return rows


def _finding(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    path: str,
    message: str,
    *,
    owner_ref: str | None = None,
    artifact_ref: str | None = None,
    required_action: str | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "path": path, "message": message}
    if owner_ref is not None:
        item["owner_ref"] = owner_ref
    if artifact_ref is not None:
        item["artifact_ref"] = artifact_ref
    if required_action is not None:
        item["required_action"] = required_action
    findings.append(item)


def _input_hash(root: Path, path: Path, kind: str) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": _relative(root, path), "bytes": len(data), "sha256": _hash(data), "kind": kind}


def _safe_workspace_path(root: Path, relative: str) -> tuple[Path | None, str | None]:
    normalized = relative.replace("\\", "/")
    candidate_relative = Path(normalized)
    if not normalized or candidate_relative.is_absolute() or ":" in normalized.split("/")[0] or ".." in candidate_relative.parts:
        return None, "Path must be a non-escaping workspace-relative locator."
    candidate = root.joinpath(*candidate_relative.parts)
    try:
        candidate.resolve(strict=False).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return None, "Path resolves outside the workspace, including through a reparse target."
    return candidate, None


def _locator_issue(root: Path, locator: str, authority: str) -> tuple[str | None, str | None]:
    if authority in {"EXTERNAL", "SOURCE_PROJECT"}:
        if URI.match(locator) or Path(locator).is_absolute():
            return None, None
        return "ART_EXTERNAL_LOCATOR_INVALID", "External authority requires an absolute path or URI and is not read by audit."
    path, error = _safe_workspace_path(root, locator)
    if error is not None:
        return "ART_LOCATOR_ESCAPE", error
    assert path is not None
    if not path.exists():
        return "ART_LOCATOR_MISSING", "Registered workspace locator does not exist."
    return None, None


def _relationships(value: str) -> tuple[list[str], str | None]:
    if value.strip().upper() in PLACEHOLDERS:
        return [], None
    relations = [item.strip() for item in value.split(";") if item.strip()]
    for relation in relations:
        if relation == "SOURCE_OF_TRUTH":
            continue
        if ":" not in relation:
            return relations, f"Relationship lacks a typed target: {relation}"
        relation_type, target = relation.split(":", 1)
        if relation_type not in RELATIONS or not target:
            return relations, f"Unknown or empty relationship: {relation}"
        if relation_type in {"SUPERSEDES", "SUPERSEDED_BY"} and not ARTIFACT_REF.fullmatch(target):
            return relations, f"Relationship requires a fully qualified Artifact target: {relation}"
        if relation_type in {"MIRROR_OF", "GENERATED_FROM"} and not (
            ARTIFACT_REF.fullmatch(target) or EXTERNAL_REF.fullmatch(target)
        ):
            return relations, f"Derivation relationship requires an Artifact or explicit external target: {relation}"
        if relation_type in {"EVIDENCE_FOR", "RECOVERY_FOR"} and not (
            ARTIFACT_REF.fullmatch(target) or OWNER_REF.fullmatch(target) or EXTERNAL_REF.fullmatch(target)
        ):
            return relations, f"Relationship target is not a stable Artifact or explicit external reference: {relation}"
    return relations, None


def _relation_target(relations: Iterable[str], relation_type: str) -> str | None:
    prefix = relation_type + ":"
    values = [item[len(prefix):] for item in relations if item.startswith(prefix)]
    return values[0] if len(values) == 1 else None


def _role_contract(value: str) -> dict[str, str]:
    if value.strip().upper() in PLACEHOLDERS:
        return {}
    result: dict[str, str] = {}
    for part in value.split(";"):
        if "=" not in part:
            return {}
        key, item_value = part.split("=", 1)
        key = key.strip()
        item_value = item_value.strip()
        if not key or not item_value or key in result:
            return {}
        result[key] = item_value
    return result


def _valid_timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _valid_sha256(value: str | None) -> bool:
    return bool(value and re.fullmatch(r"[A-Fa-f0-9]{64}", value))


def _artifact_record(
    *,
    artifact_ref: str,
    owner_ref: str,
    owner_kind: str,
    registry_path: str,
    local_id: str,
    role: str,
    locator: str,
    authority: str,
    vcs: str,
    status: str = "N/A",
    verification: str = "N/A",
    retention: str = "N/A",
    disposition: str = "N/A",
    relationships: str = "N/A",
    purpose: str = "N/A",
    applies_to: str = "N/A",
    role_contract: str = "N/A",
) -> dict[str, str]:
    return {
        "artifact_ref": artifact_ref,
        "owner_ref": owner_ref,
        "owner_kind": owner_kind,
        "registry_path": registry_path,
        "local_id": local_id,
        "role": role,
        "locator": locator,
        "authority": authority,
        "vcs": vcs,
        "status": status,
        "verification": verification,
        "retention": retention,
        "disposition": disposition,
        "relationships": relationships,
        "purpose": purpose,
        "applies_to": applies_to,
        "role_contract": role_contract,
    }


def _parse_owner_registry(
    root: Path,
    registry_path: Path,
    marker: str,
    owner_ref: str,
    owner_kind: str,
    findings: list[dict[str, Any]],
    artifacts: list[dict[str, str]],
) -> int:
    data, text = _read_markdown(registry_path)
    del data
    try:
        section = _section(text, marker)
        if section is None:
            return 0
        rows = _table(section, OWNER_HEADERS)
    except ValueError as exc:
        _finding(findings, "ISSUE", "ART_REGISTRY_SCHEMA_INVALID", _relative(root, registry_path), str(exc), owner_ref=owner_ref)
        return 0
    seen_ids: set[str] = set()
    seen_locators: set[str] = set()
    for row in rows:
        local_id = row["Artifact ID"]
        artifact_ref = f"{owner_ref}:{local_id}"
        if not re.fullmatch(r"ART-[0-9]{3,}", local_id) or local_id in seen_ids:
            _finding(findings, "ISSUE", "ART_ID_INVALID_OR_DUPLICATE", _relative(root, registry_path), "Owner-local Artifact ID is invalid or duplicated.", owner_ref=owner_ref, artifact_ref=artifact_ref)
        seen_ids.add(local_id)
        locator = row["Locator"].strip("` ")
        if locator in seen_locators:
            _finding(findings, "ISSUE", "ART_LOCATOR_DUPLICATE", _relative(root, registry_path), "Owner registry contains a duplicate locator.", owner_ref=owner_ref, artifact_ref=artifact_ref)
        seen_locators.add(locator)
        role = row["Role"]
        authority = row["Authority"]
        vcs = row["VCS"]
        if role not in ROLES:
            _finding(findings, "ISSUE", "ART_ROLE_INVALID", _relative(root, registry_path), "Artifact Role is not in the v1 enumeration.", owner_ref=owner_ref, artifact_ref=artifact_ref)
        if authority not in AUTHORITIES:
            _finding(findings, "ISSUE", "ART_AUTHORITY_INVALID", _relative(root, registry_path), "Artifact Authority is not in the v1 enumeration.", owner_ref=owner_ref, artifact_ref=artifact_ref)
        else:
            code, message = _locator_issue(root, locator, authority)
            if code is not None and message is not None:
                _finding(findings, "ISSUE", code, _relative(root, registry_path), message, owner_ref=owner_ref, artifact_ref=artifact_ref)
        if vcs not in VCS_STATES:
            _finding(findings, "ISSUE", "ART_VCS_INVALID", _relative(root, registry_path), "Artifact VCS boundary is invalid.", owner_ref=owner_ref, artifact_ref=artifact_ref)
        verification_state = row["Verification"].split(":", 1)[0]
        if verification_state not in VERIFICATION_STATES:
            _finding(findings, "ISSUE", "ART_VERIFICATION_INVALID", _relative(root, registry_path), "Verification state is invalid.", owner_ref=owner_ref, artifact_ref=artifact_ref)
        if row["Disposition"] not in DISPOSITIONS:
            _finding(findings, "ISSUE", "ART_DISPOSITION_INVALID", _relative(root, registry_path), "Disposition is invalid.", owner_ref=owner_ref, artifact_ref=artifact_ref)
        if row["Retention"].strip().upper() in PLACEHOLDERS:
            _finding(findings, "ISSUE", "ART_RETENTION_REQUIRED", _relative(root, registry_path), "Artifact requires an explicit retention boundary.", owner_ref=owner_ref, artifact_ref=artifact_ref)
        relations, relation_error = _relationships(row["Relationships"])
        if relation_error is not None:
            _finding(findings, "ISSUE", "ART_RELATIONSHIP_INVALID", _relative(root, registry_path), relation_error, owner_ref=owner_ref, artifact_ref=artifact_ref)
        contract = _role_contract(row["Role Contract"])
        if role == "EVIDENCE":
            relation_target = _relation_target(relations, "EVIDENCE_FOR")
            if not contract.get("target") or relation_target != contract.get("target"):
                _finding(findings, "ISSUE", "ART_EVIDENCE_TARGET_REQUIRED", _relative(root, registry_path), "Evidence requires one exact target in both Role Contract and EVIDENCE_FOR.", owner_ref=owner_ref, artifact_ref=artifact_ref)
            evidence_fields = {"target", "captured_at", "method", "result", "content_class", "sha256"}
            if (
                not evidence_fields.issubset(contract)
                or not _valid_timestamp(contract.get("captured_at", ""))
                or contract.get("content_class") not in {"RAW", "SUMMARY", "GENERATED_REPORT"}
                or not _valid_sha256(contract.get("sha256"))
            ):
                _finding(findings, "ISSUE", "ART_EVIDENCE_CONTRACT_REQUIRED", _relative(root, registry_path), "Evidence requires target, capture time, method, result, content class, and SHA-256.", owner_ref=owner_ref, artifact_ref=artifact_ref)
        if role == "RECOVERY":
            required = {"target", "restore", "scope", "verify", "sha256"}
            if (
                not required.issubset(contract)
                or _relation_target(relations, "RECOVERY_FOR") != contract.get("target")
                or not _valid_sha256(contract.get("sha256"))
            ):
                _finding(findings, "ISSUE", "ART_RECOVERY_CONTRACT_REQUIRED", _relative(root, registry_path), "Recovery requires target, restore procedure, scope, verification, SHA-256, and matching RECOVERY_FOR.", owner_ref=owner_ref, artifact_ref=artifact_ref)
            if row["Retention"].strip().upper() in PLACEHOLDERS:
                _finding(findings, "ISSUE", "ART_RECOVERY_RETENTION_REQUIRED", _relative(root, registry_path), "Recovery requires a non-placeholder retention boundary.", owner_ref=owner_ref, artifact_ref=artifact_ref)
        frozen_role = role in {"EVIDENCE", "RECOVERY"} or (role == "DELIVERABLE" and verification_state == "PASS")
        if frozen_role:
            expected_hash = contract.get("sha256")
            if not _valid_sha256(expected_hash):
                _finding(findings, "ISSUE", "ART_HASH_REQUIRED", _relative(root, registry_path), "Frozen Artifact role requires SHA-256 in Role Contract.", owner_ref=owner_ref, artifact_ref=artifact_ref)
            elif authority in {"WORKSPACE", "GENERATED"}:
                payload_path, payload_error = _safe_workspace_path(root, locator)
                if payload_error is None and payload_path is not None:
                    if not payload_path.is_file():
                        _finding(findings, "ISSUE", "ART_HASH_TARGET_NOT_FILE", _relative(root, registry_path), "Frozen Artifact locator must be a file or an explicit manifest file; recursive directory hashing is not performed.", owner_ref=owner_ref, artifact_ref=artifact_ref)
                    else:
                        observed_hash = _hash(payload_path.read_bytes())
                        if observed_hash != expected_hash.upper():
                            _finding(findings, "ISSUE", "ART_HASH_MISMATCH", _relative(root, registry_path), "Frozen Artifact SHA-256 does not match its current exact payload bytes.", owner_ref=owner_ref, artifact_ref=artifact_ref)
        artifacts.append(
            _artifact_record(
                artifact_ref=artifact_ref,
                owner_ref=owner_ref,
                owner_kind=owner_kind,
                registry_path=_relative(root, registry_path),
                local_id=local_id,
                role=role,
                locator=locator,
                authority=authority,
                vcs=vcs,
                verification=row["Verification"],
                retention=row["Retention"],
                disposition=row["Disposition"],
                relationships=row["Relationships"],
                role_contract=row["Role Contract"],
            )
        )
    return len(rows)


def _parse_shared_registry(
    root: Path,
    registry_path: Path,
    findings: list[dict[str, Any]],
    artifacts: list[dict[str, str]],
) -> int:
    _, text = _read_markdown(registry_path)
    try:
        section = _section(text, "shared-artifacts")
        if section is None:
            raise ValueError("Shared index lacks the shared-artifacts section.")
        rows = _table(section, SHARED_HEADERS)
    except ValueError as exc:
        _finding(findings, "ISSUE", "ART_REGISTRY_SCHEMA_INVALID", _relative(root, registry_path), str(exc), owner_ref="shared")
        return 0
    seen_ids: set[str] = set()
    current_keys: dict[tuple[str, str], str] = {}
    for row in rows:
        local_id = row["Shared ID"]
        artifact_ref = f"shared:{local_id}"
        if not re.fullmatch(r"SHR-[0-9]{3,}", local_id) or local_id in seen_ids:
            _finding(findings, "ISSUE", "ART_ID_INVALID_OR_DUPLICATE", _relative(root, registry_path), "Shared ID is invalid or duplicated.", owner_ref="shared", artifact_ref=artifact_ref)
        seen_ids.add(local_id)
        if row["Status"] not in {"CURRENT", "SUPERSEDED"}:
            _finding(findings, "ISSUE", "ART_SHARED_STATUS_INVALID", _relative(root, registry_path), "Shared Status must be CURRENT or SUPERSEDED.", owner_ref="shared", artifact_ref=artifact_ref)
        key = (" ".join(row["Purpose"].lower().split()), " ".join(row["Applies To"].lower().split()))
        if row["Status"] == "CURRENT":
            if key in current_keys:
                _finding(findings, "ISSUE", "ART_SHARED_CURRENT_CONFLICT", _relative(root, registry_path), f"Competing CURRENT Shared authorities: {current_keys[key]} and {artifact_ref}.", owner_ref="shared", artifact_ref=artifact_ref)
            current_keys[key] = artifact_ref
        authority = row["Authority"]
        vcs = row["VCS"]
        locator = row["Locator"].strip("` ")
        if authority not in AUTHORITIES:
            _finding(findings, "ISSUE", "ART_AUTHORITY_INVALID", _relative(root, registry_path), "Shared Authority is invalid.", owner_ref="shared", artifact_ref=artifact_ref)
        else:
            code, message = _locator_issue(root, locator, authority)
            if code is not None and message is not None:
                _finding(findings, "ISSUE", code, _relative(root, registry_path), message, owner_ref="shared", artifact_ref=artifact_ref)
        if vcs not in VCS_STATES:
            _finding(findings, "ISSUE", "ART_VCS_INVALID", _relative(root, registry_path), "Shared VCS boundary is invalid.", owner_ref="shared", artifact_ref=artifact_ref)
        if row["Retention"].strip().upper() in PLACEHOLDERS:
            _finding(findings, "ISSUE", "ART_RETENTION_REQUIRED", _relative(root, registry_path), "Shared entry requires an explicit retention boundary.", owner_ref="shared", artifact_ref=artifact_ref)
        if any(row[field].strip().upper() in PLACEHOLDERS for field in ("Purpose", "Applies To", "Maintainer")):
            _finding(findings, "ISSUE", "ART_SHARED_METADATA_REQUIRED", _relative(root, registry_path), "Shared entry requires purpose, applies-to scope, and maintainer.", owner_ref="shared", artifact_ref=artifact_ref)
        if not _valid_timestamp(row["Last Verified"]):
            _finding(findings, "ISSUE", "ART_SHARED_VERIFICATION_INVALID", _relative(root, registry_path), "Shared Last Verified must be a timezone-qualified ISO 8601 timestamp.", owner_ref="shared", artifact_ref=artifact_ref)
        source = row["Source"]
        if not (ARTIFACT_REF.fullmatch(source) or EXTERNAL_REF.fullmatch(source)):
            _finding(findings, "ISSUE", "ART_SHARED_SOURCE_REQUIRED", _relative(root, registry_path), "Shared Source must be a stable Artifact reference or explicit external reference.", owner_ref="shared", artifact_ref=artifact_ref)
        relations, relation_error = _relationships(row["Relationships"])
        if relation_error is not None:
            _finding(findings, "ISSUE", "ART_RELATIONSHIP_INVALID", _relative(root, registry_path), relation_error, owner_ref="shared", artifact_ref=artifact_ref)
        artifacts.append(
            _artifact_record(
                artifact_ref=artifact_ref,
                owner_ref="shared",
                owner_kind="Shared",
                registry_path=_relative(root, registry_path),
                local_id=local_id,
                role="DELIVERABLE",
                locator=locator,
                authority=authority,
                vcs=vcs,
                status=row["Status"],
                verification=f"PASS:{row['Last Verified']}",
                retention=row["Retention"],
                disposition="KEEP_OWNED" if row["Status"] == "CURRENT" else "SUPERSEDED",
                relationships=row["Relationships"],
                purpose=row["Purpose"],
                applies_to=row["Applies To"],
                role_contract=f"source={row['Source']};maintainer={row['Maintainer']}",
            )
        )
    return len(rows)


def _relation_value(relation: str, relation_type: str) -> str | None:
    prefix = relation_type + ":"
    return relation[len(prefix):] if relation.startswith(prefix) else None


def _has_cycle(graph: dict[str, set[str]]) -> bool:
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


def _validate_artifact_relationships(artifacts: list[dict[str, str]], findings: list[dict[str, Any]]) -> None:
    by_ref = {item["artifact_ref"]: item for item in artifacts}
    relation_map = {artifact_ref: _relationships(artifact["relationships"])[0] for artifact_ref, artifact in by_ref.items()}
    supersession_graph: dict[str, set[str]] = {artifact_ref: set() for artifact_ref in by_ref}
    mirror_targets: dict[str, str] = {}
    for artifact_ref, artifact in by_ref.items():
        relations = relation_map[artifact_ref]
        if artifact["owner_kind"] == "Shared":
            if artifact["status"] == "CURRENT" and "SOURCE_OF_TRUTH" not in relations:
                _finding(
                    findings,
                    "ISSUE",
                    "ART_SHARED_AUTHORITY_RELATION_REQUIRED",
                    artifact["registry_path"],
                    "A CURRENT Shared entry requires SOURCE_OF_TRUTH.",
                    owner_ref=artifact["owner_ref"],
                    artifact_ref=artifact_ref,
                )
            if artifact["status"] == "SUPERSEDED" and "SOURCE_OF_TRUTH" in relations:
                _finding(
                    findings,
                    "ISSUE",
                    "ART_SUPERSEDED_AUTHORITY_CONFLICT",
                    artifact["registry_path"],
                    "A SUPERSEDED Shared entry cannot remain SOURCE_OF_TRUTH.",
                    owner_ref=artifact["owner_ref"],
                    artifact_ref=artifact_ref,
                )
            source = _role_contract(artifact["role_contract"]).get("source")
            if source and ARTIFACT_REF.fullmatch(source) and source not in by_ref:
                _finding(
                    findings,
                    "ISSUE",
                    "ART_SHARED_SOURCE_DANGLING",
                    artifact["registry_path"],
                    f"Shared source is not resolvable in the bounded registry set: {source}",
                    owner_ref=artifact["owner_ref"],
                    artifact_ref=artifact_ref,
                )
        for relation in relations:
            if ":" not in relation:
                continue
            relation_type, target = relation.split(":", 1)
            if relation_type == "MIRROR_OF":
                mirror_targets[artifact_ref] = target
            if ARTIFACT_REF.fullmatch(target) and target not in by_ref:
                _finding(
                    findings,
                    "ISSUE",
                    "ART_RELATIONSHIP_DANGLING",
                    artifact["registry_path"],
                    f"Relationship target is not present in the current bounded registry set: {relation}",
                    owner_ref=artifact["owner_ref"],
                    artifact_ref=artifact_ref,
                )
            if relation_type == "SUPERSEDES" and target in by_ref:
                supersession_graph[artifact_ref].add(target)
                reverse = f"SUPERSEDED_BY:{artifact_ref}"
                if reverse not in relation_map[target]:
                    _finding(
                        findings,
                        "ISSUE",
                        "ART_SUPERSESSION_ONE_SIDED",
                        artifact["registry_path"],
                        f"Supersession requires reverse relation {reverse}.",
                        owner_ref=artifact["owner_ref"],
                        artifact_ref=artifact_ref,
                    )
            if relation_type == "SUPERSEDED_BY" and target in by_ref:
                reverse = f"SUPERSEDES:{artifact_ref}"
                if reverse not in relation_map[target]:
                    _finding(
                        findings,
                        "ISSUE",
                        "ART_SUPERSESSION_ONE_SIDED",
                        artifact["registry_path"],
                        f"Supersession requires reverse relation {reverse}.",
                        owner_ref=artifact["owner_ref"],
                        artifact_ref=artifact_ref,
                    )
    if _has_cycle(supersession_graph):
        _finding(findings, "ISSUE", "ART_SUPERSESSION_CYCLE", "Artifact registries", "Artifact supersession relationships contain a cycle.")
    for artifact_ref in sorted(mirror_targets):
        seen = {artifact_ref}
        target = mirror_targets[artifact_ref]
        resolved = bool(EXTERNAL_REF.fullmatch(target))
        while not resolved and target in by_ref and target not in seen:
            seen.add(target)
            if "SOURCE_OF_TRUTH" in relation_map[target]:
                resolved = True
                break
            next_target = mirror_targets.get(target)
            if next_target is None:
                break
            target = next_target
            if EXTERNAL_REF.fullmatch(target):
                resolved = True
        if not resolved:
            artifact = by_ref[artifact_ref]
            _finding(
                findings,
                "ISSUE",
                "ART_MIRROR_AUTHORITY_MISSING",
                artifact["registry_path"],
                "Mirror chain does not resolve to SOURCE_OF_TRUTH or an explicit external authority.",
                owner_ref=artifact["owner_ref"],
                artifact_ref=artifact_ref,
            )


def _parse_archive_registry(
    root: Path,
    registry_path: Path,
    findings: list[dict[str, Any]],
    artifacts: list[dict[str, str]],
) -> int:
    _, text = _read_markdown(registry_path)
    try:
        section = _section(text, "archive-artifacts")
        if section is None:
            raise ValueError("Archive index lacks the archive-artifacts section.")
        rows = _table(section, ARCHIVE_HEADERS)
    except ValueError as exc:
        _finding(findings, "ISSUE", "ART_REGISTRY_SCHEMA_INVALID", _relative(root, registry_path), str(exc), owner_ref="archive")
        return 0
    seen: set[str] = set()
    for row in rows:
        local_id = row["Archive ID"]
        artifact_ref = f"archive:{local_id}"
        if not re.fullmatch(r"ARC-[0-9]{3,}", local_id) or local_id in seen:
            _finding(findings, "ISSUE", "ART_ID_INVALID_OR_DUPLICATE", _relative(root, registry_path), "Archive ID is invalid or duplicated.", owner_ref="archive", artifact_ref=artifact_ref)
        seen.add(local_id)
        authority = row["Authority"]
        vcs = row["VCS"]
        locator = row["Locator"].strip("` ")
        if authority not in AUTHORITIES:
            _finding(findings, "ISSUE", "ART_AUTHORITY_INVALID", _relative(root, registry_path), "Archive Authority is invalid.", owner_ref="archive", artifact_ref=artifact_ref)
        else:
            code, message = _locator_issue(root, locator, authority)
            if code is not None and message is not None:
                _finding(findings, "ISSUE", code, _relative(root, registry_path), message, owner_ref="archive", artifact_ref=artifact_ref)
        if vcs not in VCS_STATES:
            _finding(findings, "ISSUE", "ART_VCS_INVALID", _relative(root, registry_path), "Archive VCS boundary is invalid.", owner_ref="archive", artifact_ref=artifact_ref)
        if not _valid_timestamp(row["Archived At"]):
            _finding(findings, "ISSUE", "ART_ARCHIVE_TIMESTAMP_INVALID", _relative(root, registry_path), "Archive timestamp must be timezone-qualified ISO 8601.", owner_ref="archive", artifact_ref=artifact_ref)
        if row["Original Owner"].strip().upper() in PLACEHOLDERS or row["Reason"].strip().upper() in PLACEHOLDERS:
            _finding(findings, "ISSUE", "ART_ARCHIVE_PROVENANCE_REQUIRED", _relative(root, registry_path), "Archive requires an original owner and reason.", owner_ref="archive", artifact_ref=artifact_ref)
        relations, relation_error = _relationships(row["Relationships"])
        del relations
        if relation_error is not None:
            _finding(findings, "ISSUE", "ART_RELATIONSHIP_INVALID", _relative(root, registry_path), relation_error, owner_ref="archive", artifact_ref=artifact_ref)
        artifacts.append(
            _artifact_record(
                artifact_ref=artifact_ref,
                owner_ref="archive",
                owner_kind="Archive",
                registry_path=_relative(root, registry_path),
                local_id=local_id,
                role="RECOVERY",
                locator=locator,
                authority=authority,
                vcs=vcs,
                status="ARCHIVED",
                verification="PASS" if row["Manifest"].upper() not in PLACEHOLDERS else "UNVERIFIED",
                retention="manual",
                disposition="ARCHIVE",
                relationships=row["Relationships"],
                role_contract=f"owner={row['Original Owner']};reason={row['Reason']};successor={row['Successor']};manifest={row['Manifest']}",
            )
        )
    return len(rows)


def _candidate_summary(root: Path, relative: str, findings: list[dict[str, Any]], *, legacy: bool) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    path, error = _safe_workspace_path(root, relative)
    if error is not None or path is None:
        _finding(findings, "ISSUE", "ART_CANDIDATE_PATH_INVALID", relative, error or "Candidate root is invalid.")
        return None, None
    normalized = _relative(root, path)
    if not path.exists():
        _finding(findings, "WARNING", "ART_CANDIDATE_ROOT_MISSING", normalized, "Explicit candidate root does not exist.")
        return {"path": normalized, "kind": "MISSING", "direct_entry_count": 0, "signature_sha256": _hash(b"missing")}, None
    entries: list[dict[str, Any]] = []
    if path.is_dir():
        try:
            direct_children = sorted(path.iterdir(), key=lambda item: item.name.casefold())
        except OSError as exc:
            _finding(findings, "ISSUE", "ART_CANDIDATE_READ_FAILED", normalized, f"Candidate root direct entries could not be read: {exc}")
            signature = _hash(_json_bytes([{"read_error": type(exc).__name__}]))
            return {
                "path": normalized,
                "kind": "DIRECTORY",
                "direct_entry_count": 0,
                "signature_sha256": signature,
            }, {"path": normalized, "bytes": 0, "sha256": signature, "kind": "CANDIDATE_ROOT_SIGNATURE"}
        for child in direct_children:
            try:
                resolved = child.resolve(strict=False)
                resolved.relative_to(root.resolve(strict=True))
                escaped = False
            except (OSError, ValueError):
                escaped = True
            if escaped:
                child_relative = f"{normalized}/{child.name}"
                _finding(findings, "ISSUE", "ART_CANDIDATE_REPARSE_ESCAPE", child_relative, "Candidate entry resolves outside the workspace and was not inspected.")
                entries.append({"name": child.name, "kind": "REPARSE_ESCAPE", "bytes": 0, "reparse_escape": True})
                continue
            try:
                child_kind = "DIRECTORY" if child.is_dir() else "FILE"
                child_bytes = child.stat().st_size if child_kind == "FILE" else 0
            except OSError as exc:
                child_relative = f"{normalized}/{child.name}"
                _finding(findings, "ISSUE", "ART_CANDIDATE_ENTRY_READ_FAILED", child_relative, f"Candidate entry metadata could not be read: {exc}")
                child_kind = "UNREADABLE"
                child_bytes = 0
            entries.append(
                {
                    "name": child.name,
                    "kind": child_kind,
                    "bytes": child_bytes,
                    "reparse_escape": False,
                }
            )
    else:
        entries.append({"name": path.name, "kind": "FILE", "bytes": path.stat().st_size, "reparse_escape": False})
    signature = _hash(_json_bytes(entries))
    summary = {
        "path": normalized,
        "kind": "DIRECTORY" if path.is_dir() else "FILE",
        "direct_entry_count": len(entries),
        "signature_sha256": signature,
    }
    if legacy:
        _finding(findings, "CANDIDATE", "ART_LEGACY_ROOT_CANDIDATE", normalized, "Legacy root is reported as an ownership candidate and is not adopted or modified.")
    input_record = {"path": normalized, "bytes": 0 if path.is_dir() else path.stat().st_size, "sha256": signature, "kind": "CANDIDATE_ROOT_SIGNATURE"}
    return summary, input_record


def audit_workspace(
    root: Path,
    state: dict[str, Any],
    *,
    captured_at: str,
    candidate_roots: list[str] | None = None,
    owners: list[str] | None = None,
    scope: str = "current",
) -> dict[str, Any]:
    del scope
    root = root.resolve(strict=True)
    findings: list[dict[str, Any]] = []
    artifacts: list[dict[str, str]] = []
    owner_records: list[dict[str, Any]] = []
    input_hashes: list[dict[str, Any]] = []
    project_path = root / "PROJECT_CONTROL.md"
    project_data, project_text = _read_markdown(project_path)
    input_hashes.append({"path": "PROJECT_CONTROL.md", "bytes": len(project_data), "sha256": _hash(project_data), "kind": "CANONICAL_ROOT"})
    state_path = root / "runtime" / "workspace_control.json"
    if state_path.is_file():
        input_hashes.append(_input_hash(root, state_path, "RUNTIME_DERIVED"))

    enrollment = {
        "contract_version": None,
        "status": "LEGACY_UNDECLARED",
        "root_index_path": "PROJECT_CONTROL.md",
        "shared_index": "N/A",
        "archive_index": "N/A",
        "latest_audit": "N/A",
    }
    try:
        contract_section = _section(project_text, "artifact-contract-index")
        if contract_section is not None:
            enrollment = {
                "contract_version": int(_field(contract_section, "Contract version")),
                "status": _field(contract_section, "Enrollment"),
                "root_index_path": "PROJECT_CONTROL.md",
                "shared_index": _field(contract_section, "Shared index"),
                "archive_index": _field(contract_section, "Archive index"),
                "latest_audit": _field(contract_section, "Latest audit"),
            }
            if enrollment["contract_version"] != 1 or enrollment["status"] not in {"NOT_ENROLLED", "ENROLLED"}:
                _finding(findings, "ISSUE", "ART_CONTRACT_INDEX_INVALID", "PROJECT_CONTROL.md", "Artifact Lifecycle root index version or enrollment state is invalid.")
        else:
            _finding(findings, "WARNING", "ART_CONTRACT_NOT_DECLARED", "PROJECT_CONTROL.md", "Legacy workspace has no Artifact Lifecycle enrollment declaration.")
    except (ValueError, TypeError) as exc:
        _finding(findings, "ISSUE", "ART_CONTRACT_INDEX_INVALID", "PROJECT_CONTROL.md", str(exc))

    selected_owners = set(owners or [])
    all_owner_candidates = [
        (f"phase:{item['phase_id']}", "Phase", item["path"], "phase-artifacts")
        for item in state["phase_controls"]
    ] + [
        (f"session:{item['session_id']}", "Session", item["path"], "session-artifacts")
        for item in state["session_controls"]
    ]
    active_owner_refs: set[str] = set()
    if state.get("active_phase_id") is not None:
        active_owner_refs.add(f"phase:{state['active_phase_id']}")
    if state.get("active_session_id") is not None:
        active_owner_refs.add(f"session:{state['active_session_id']}")
    owner_candidates = [item for item in all_owner_candidates if item[0] in active_owner_refs]
    if selected_owners:
        known = {item[0] for item in all_owner_candidates} | {"shared", "archive"}
        for owner in sorted(selected_owners - known):
            _finding(findings, "ISSUE", "ART_OWNER_UNKNOWN", "runtime/workspace_control.json", f"Requested owner is not registered: {owner}")
        owner_candidates = [item for item in all_owner_candidates if item[0] in selected_owners]

    for owner_ref, owner_kind, relative, marker in owner_candidates:
        path, path_error = _safe_workspace_path(root, relative)
        if path_error is not None or path is None:
            _finding(
                findings,
                "ISSUE",
                "ART_OWNER_CONTROL_PATH_INVALID",
                relative,
                path_error or "Owner control path is invalid.",
                owner_ref=owner_ref,
            )
            continue
        if path.is_file():
            input_hashes.append(_input_hash(root, path, "CANONICAL_OWNER_REGISTRY"))
            row_count = 0
            if enrollment["status"] == "ENROLLED":
                row_count = _parse_owner_registry(root, path, marker, owner_ref, owner_kind, findings, artifacts)
            else:
                _, text = _read_markdown(path)
                section = _section(text, marker)
                if section is not None:
                    try:
                        observed_rows = _table(section, OWNER_HEADERS)
                    except ValueError:
                        observed_rows = [{}]
                    if observed_rows:
                        _finding(findings, "WARNING", "ART_OWNER_REGISTRY_NOT_ENROLLED", relative, "Non-empty owner registry exists without explicit Artifact Lifecycle enrollment and is not adopted.", owner_ref=owner_ref)
            owner_records.append({"owner_ref": owner_ref, "owner_kind": owner_kind, "registry_path": relative, "row_count": row_count})
        elif enrollment["status"] == "ENROLLED":
            _finding(
                findings,
                "ISSUE",
                "ART_OWNER_CONTROL_MISSING",
                relative,
                "Registered Artifact owner control is missing.",
                owner_ref=owner_ref,
            )

    for label, owner_ref, marker, parser in (
        ("shared_index", "shared", "shared-artifacts", _parse_shared_registry),
        ("archive_index", "archive", "archive-artifacts", _parse_archive_registry),
    ):
        relative = str(enrollment[label])
        if selected_owners and owner_ref not in selected_owners:
            continue
        if relative == "N/A":
            continue
        path, error = _safe_workspace_path(root, relative)
        if error is not None or path is None:
            _finding(findings, "ISSUE", "ART_INDEX_PATH_INVALID", "PROJECT_CONTROL.md", error or "Artifact index path is invalid.", owner_ref=owner_ref)
            continue
        if not path.is_file():
            severity = "ISSUE" if enrollment["status"] == "ENROLLED" else "WARNING"
            _finding(
                findings,
                severity,
                "ART_ENROLLED_INDEX_MISSING" if severity == "ISSUE" else "ART_INDEX_MISSING",
                relative,
                "Declared Artifact index is missing.",
                owner_ref=owner_ref,
                required_action="Create or reconcile the exact enrolled index before relying on Artifact ownership." if severity == "ISSUE" else None,
            )
            continue
        input_hashes.append(_input_hash(root, path, "CANONICAL_SHARED_INDEX" if owner_ref == "shared" else "CANONICAL_ARCHIVE_INDEX"))
        row_count = parser(root, path, findings, artifacts)
        owner_records.append({"owner_ref": owner_ref, "owner_kind": owner_ref.title(), "registry_path": relative, "row_count": row_count})

    parsed_owner_refs = {item["owner_ref"] for item in owner_records if item["owner_kind"] in {"Phase", "Session"}}
    while True:
        referenced_owner_refs: set[str] = set()
        for artifact in artifacts:
            contract = _role_contract(artifact["role_contract"])
            source = contract.get("source")
            if source and ARTIFACT_REF.fullmatch(source) and (source.startswith("phase:") or source.startswith("session:")):
                referenced_owner_refs.add(":".join(source.split(":", 2)[:2]))
            relations, relation_error = _relationships(artifact["relationships"])
            if relation_error is not None:
                continue
            for relation in relations:
                if ":" not in relation:
                    continue
                target = relation.split(":", 1)[1]
                if ARTIFACT_REF.fullmatch(target) and (target.startswith("phase:") or target.startswith("session:")):
                    referenced_owner_refs.add(":".join(target.split(":", 2)[:2]))
        unresolved_owner_refs = sorted(referenced_owner_refs - parsed_owner_refs)
        if not unresolved_owner_refs:
            break
        progress = False
        for owner_ref in unresolved_owner_refs:
            owner_kind, owner_id = owner_ref.split(":", 1)
            collection = state["phase_controls"] if owner_kind == "phase" else state["session_controls"]
            id_field = "phase_id" if owner_kind == "phase" else "session_id"
            record = next((item for item in collection if item[id_field] == owner_id), None)
            parsed_owner_refs.add(owner_ref)
            if record is None:
                continue
            path, path_error = _safe_workspace_path(root, record["path"])
            if path_error is not None or path is None or not path.is_file():
                if path_error is not None:
                    _finding(
                        findings,
                        "ISSUE",
                        "ART_OWNER_CONTROL_PATH_INVALID",
                        record["path"],
                        path_error,
                        owner_ref=owner_ref,
                    )
                continue
            marker = "phase-artifacts" if owner_kind == "phase" else "session-artifacts"
            input_hashes.append(_input_hash(root, path, "CANONICAL_OWNER_REGISTRY"))
            row_count = _parse_owner_registry(root, path, marker, owner_ref, owner_kind.title(), findings, artifacts)
            owner_records.append(
                {
                    "owner_ref": owner_ref,
                    "owner_kind": owner_kind.title(),
                    "registry_path": record["path"],
                    "row_count": row_count,
                }
            )
            progress = True
        if not progress:
            break

    candidate_values = list(candidate_roots or [])
    declared_paths = {str(enrollment["shared_index"]), str(enrollment["archive_index"])}
    for default_root in ("shared", "archive"):
        if selected_owners and default_root not in selected_owners:
            continue
        if (root / default_root).exists() and all(not item.startswith(default_root + "/") for item in declared_paths if item != "N/A"):
            candidate_values.append(default_root)
    candidate_summaries: list[dict[str, Any]] = []
    seen_candidates: set[str] = set()
    for relative in candidate_values:
        normalized = relative.replace("\\", "/").rstrip("/")
        if normalized in seen_candidates:
            continue
        seen_candidates.add(normalized)
        summary, input_record = _candidate_summary(
            root,
            normalized,
            findings,
            legacy=enrollment["status"] != "ENROLLED",
        )
        if summary is not None:
            candidate_summaries.append(summary)
        if input_record is not None:
            input_hashes.append(input_record)

    _validate_artifact_relationships(artifacts, findings)

    runtime_snapshot_path = root / "runtime" / "artifact_audit_snapshot.json"
    if runtime_snapshot_path.is_file():
        input_hashes.append(_input_hash(root, runtime_snapshot_path, "RUNTIME_DERIVED"))
        try:
            runtime_snapshot = json.loads(runtime_snapshot_path.read_text(encoding="utf-8-sig"))
            runtime_enrollment = runtime_snapshot.get("enrollment")
            if runtime_enrollment != enrollment:
                _finding(findings, "WARNING", "ART_RUNTIME_DRIFT", _relative(root, runtime_snapshot_path), "Runtime-derived enrollment disagrees with canonical Markdown; Markdown remains authoritative.")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            _finding(findings, "WARNING", "ART_RUNTIME_SNAPSHOT_INVALID", _relative(root, runtime_snapshot_path), "Runtime-derived snapshot is unreadable and cannot affect canonical truth.")

    severity_order = {"ISSUE": 0, "WARNING": 1, "CANDIDATE": 2}
    findings.sort(key=lambda item: (severity_order[item["severity"]], item["code"], item["path"], item.get("artifact_ref", "")))
    artifacts.sort(key=lambda item: item["artifact_ref"])
    input_hashes.sort(key=lambda item: (item["kind"], item["path"]))
    owner_records.sort(key=lambda item: item["owner_ref"])
    counts = {
        "owner_registries": len(owner_records),
        "artifact_rows": len(artifacts),
        "issues": sum(item["severity"] == "ISSUE" for item in findings),
        "warnings": sum(item["severity"] == "WARNING" for item in findings),
        "candidates": sum(item["severity"] == "CANDIDATE" for item in findings),
    }
    fingerprint_payload = {
        "captured_at": captured_at,
        "enrollment": enrollment,
        "input_hashes": input_hashes,
        "artifacts": artifacts,
        "findings": findings,
    }
    return {
        "schema_version": 1,
        "contract_id": "workspace-artifact-snapshot",
        "snapshot_class": "FROZEN_CAPTURE",
        "captured_at": captured_at,
        "capture_fingerprint": _hash(_json_bytes(fingerprint_payload)),
        "canonical": False,
        "runtime_is_canonical": False,
        "workspace_schema_version": state["schema_version"],
        "enrollment": enrollment,
        "scope": {"mode": "current", "owners": sorted(selected_owners), "candidate_roots": sorted(seen_candidates)},
        "owners": owner_records,
        "artifacts": artifacts,
        "findings": findings,
        "counts": counts,
        "input_hashes": input_hashes,
        "bounded_behavior": {
            "recursive_scan_performed": False,
            "candidate_roots": candidate_summaries,
            "vcs_commands_performed": False,
            "payload_moves_performed": False,
            "payload_deletes_performed": False,
        },
        "writes_performed": False,
        "implicit_session_created": False,
    }


def enrollment_preview(
    root: Path,
    state: dict[str, Any],
    *,
    captured_at: str,
    shared_index: str,
    archive_index: str,
    candidate_roots: list[str] | None = None,
) -> dict[str, Any]:
    for label, value in (("Shared index", shared_index), ("Archive index", archive_index)):
        if value == "N/A":
            continue
        path, error = _safe_workspace_path(root, value)
        if error is not None or path is None or not value.replace("\\", "/").endswith("/INDEX.md"):
            raise ValueError(f"{label} must be N/A or a safe workspace-relative INDEX.md path.")
    snapshot = audit_workspace(root, state, captured_at=captured_at, candidate_roots=candidate_roots)
    result_label = "PASS" if snapshot["counts"]["issues"] == 0 else "BLOCKED"
    proposed = (
        "<!-- MALTS:section=artifact-contract-index -->\n"
        "## Artifact Lifecycle Index\n\n"
        "- Contract version: `1`\n"
        "- Enrollment: `ENROLLED`\n"
        f"- Shared index: `{shared_index}`\n"
        f"- Archive index: `{archive_index}`\n"
        f"- Latest audit: `{captured_at} / {result_label}`\n"
    )
    return {
        "snapshot": snapshot,
        "proposed_root_section": proposed,
        "planned_changes": ["PROJECT_CONTROL.md", "runtime/artifact_audit_snapshot.json"],
        "apply_supported": False,
        "required_actions": [
            "Review every candidate and choose explicit registrations, exclusions, or unresolved items.",
            "Create and validate every non-N/A canonical index before enrollment apply.",
            "Use the later mutation Wave for reviewed dry-run/apply; this preview never enrolls the workspace.",
        ],
    }


def _encode_markdown_like(original: bytes, text: str) -> bytes:
    payload = text.encode("utf-8")
    return b"\xef\xbb\xbf" + payload if original.startswith(b"\xef\xbb\xbf") else payload


def _cell(value: str, field: str) -> str:
    value = value.strip()
    if not value or "\n" in value or "\r" in value or "|" in value:
        raise ArtifactMutationError("ART_FIELD_INVALID", f"{field} must be one non-empty Markdown-table cell.", value)
    return value


def _row_line(headers: tuple[str, ...], row: Mapping[str, str]) -> str:
    return "| " + " | ".join(_cell(str(row[header]), header) for header in headers) + " |"


def _table_section(marker: str, title: str, headers: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    delimiter = tuple("---" for _ in headers)
    lines = [
        f"<!-- MALTS:section={marker} -->",
        f"## {title}",
        "",
        _row_line(headers, dict(zip(headers, headers))),
        _row_line(headers, dict(zip(headers, delimiter))),
    ]
    lines.extend(_row_line(headers, row) for row in rows)
    return "\n".join(lines) + "\n\n"


def _replace_or_insert_section(text: str, marker: str, rendered: str, before_marker: str | None = None) -> str:
    current = _section(text, marker)
    if current is not None:
        return text.replace(current, rendered, 1)
    if before_marker is None:
        raise ArtifactMutationError("ART_REGISTRY_SECTION_MISSING", f"Cannot insert missing registry section {marker}.")
    token = f"<!-- MALTS:section={before_marker} -->"
    if text.count(token) != 1:
        raise ArtifactMutationError("ART_REGISTRY_INSERTION_POINT", f"Expected one insertion marker: {before_marker}")
    return text.replace(token, rendered + token, 1)


def _contract_from_text(text: str) -> dict[str, Any]:
    section = _section(text, "artifact-contract-index")
    if section is None:
        return {
            "contract_version": None,
            "status": "LEGACY_UNDECLARED",
            "shared_index": "N/A",
            "archive_index": "N/A",
            "latest_audit": "N/A",
        }
    try:
        return {
            "contract_version": int(_field(section, "Contract version")),
            "status": _field(section, "Enrollment"),
            "shared_index": _field(section, "Shared index"),
            "archive_index": _field(section, "Archive index"),
            "latest_audit": _field(section, "Latest audit"),
        }
    except (ValueError, TypeError) as exc:
        raise ArtifactMutationError("ART_CONTRACT_INDEX_INVALID", str(exc)) from exc


def _read_contract(root: Path) -> tuple[Path, bytes, str, dict[str, Any]]:
    path = root / "PROJECT_CONTROL.md"
    original, text = _read_markdown(path)
    return path, original, text, _contract_from_text(text)


def _contract(root: Path) -> dict[str, Any]:
    return _read_contract(root)[3]


def _root_contract_section(*, enrollment: str, shared_index: str, archive_index: str, latest_audit: str) -> str:
    return (
        "<!-- MALTS:section=artifact-contract-index -->\n"
        "## Artifact Lifecycle Index\n\n"
        "- Contract version: `1`\n"
        f"- Enrollment: `{enrollment}`\n"
        f"- Shared index: `{shared_index}`\n"
        f"- Archive index: `{archive_index}`\n"
        f"- Latest audit: `{latest_audit}`\n\n"
    )


def _replace_root_contract(
    root: Path,
    *,
    enrollment: str,
    shared_index: str,
    archive_index: str,
    latest_audit: str,
    source_original: bytes | None = None,
    source_text: str | None = None,
) -> tuple[Path, bytes, bytes]:
    path = root / "PROJECT_CONTROL.md"
    if (source_original is None) != (source_text is None):
        raise ArtifactMutationError("ART_CONTRACT_SOURCE_INVALID", "Root contract source bytes and text must be provided together.")
    if source_original is None or source_text is None:
        original, text = _read_markdown(path)
    else:
        original, text = source_original, source_text
    rendered = _root_contract_section(
        enrollment=enrollment,
        shared_index=shared_index,
        archive_index=archive_index,
        latest_audit=latest_audit,
    )
    updated = _replace_or_insert_section(text, "artifact-contract-index", rendered, "task-queue")
    return path, original, _encode_markdown_like(original, updated)


def _owner_descriptor(root: Path, state: dict[str, Any], owner_ref: str) -> tuple[Path, str, str]:
    if owner_ref.startswith("phase:"):
        owner_id = owner_ref.split(":", 1)[1]
        record = next((item for item in state["phase_controls"] if item["phase_id"] == owner_id), None)
        marker = "phase-artifacts"
        insertion = "phase-recovery"
    elif owner_ref.startswith("session:"):
        owner_id = owner_ref.split(":", 1)[1]
        record = next((item for item in state["session_controls"] if item["session_id"] == owner_id), None)
        marker = "session-artifacts"
        insertion = "session-recovery"
    else:
        raise ArtifactMutationError("ART_OWNER_INVALID", "Owner must be a registered Phase or Session reference.", owner_ref)
    if record is None:
        raise ArtifactMutationError("ART_OWNER_UNKNOWN", "Artifact owner is not registered in workspace runtime state.", owner_ref)
    path, error = _safe_workspace_path(root, record["path"])
    if error is not None or path is None or not path.is_file():
        raise ArtifactMutationError("ART_OWNER_CONTROL_MISSING", error or "Owner control file is missing.", record["path"])
    return path, marker, insertion


def _owner_rows(root: Path, state: dict[str, Any], owner_ref: str) -> tuple[Path, bytes, str, str, str, list[dict[str, str]]]:
    path, marker, insertion = _owner_descriptor(root, state, owner_ref)
    original, text = _read_markdown(path)
    section = _section(text, marker)
    rows = _table(section, OWNER_HEADERS) if section is not None else []
    return path, original, text, marker, insertion, rows


def _validate_common_row(root: Path, row: Mapping[str, str]) -> None:
    artifact_id = row["Artifact ID"]
    if not re.fullmatch(r"ART-[0-9]{3,}", artifact_id):
        raise ArtifactMutationError("ART_ID_INVALID", "Owner-local Artifact ID must match ART-001 style.", artifact_id)
    if row["Role"] not in ROLES:
        raise ArtifactMutationError("ART_ROLE_INVALID", "Artifact Role is outside the v1 enumeration.", row["Role"])
    if row["Authority"] not in AUTHORITIES:
        raise ArtifactMutationError("ART_AUTHORITY_INVALID", "Artifact Authority is outside the v1 enumeration.", row["Authority"])
    if row["VCS"] not in VCS_STATES:
        raise ArtifactMutationError("ART_VCS_INVALID", "Artifact VCS boundary is outside the v1 enumeration.", row["VCS"])
    verification = row["Verification"].split(":", 1)[0]
    if verification not in VERIFICATION_STATES:
        raise ArtifactMutationError("ART_VERIFICATION_INVALID", "Artifact Verification state is invalid.", row["Verification"])
    if row["Retention"].upper() in PLACEHOLDERS:
        raise ArtifactMutationError("ART_RETENTION_REQUIRED", "Artifact requires an explicit retention boundary.")
    if row["Disposition"] not in DISPOSITIONS:
        raise ArtifactMutationError("ART_DISPOSITION_INVALID", "Artifact disposition is invalid.", row["Disposition"])
    relations, relation_error = _relationships(row["Relationships"])
    if relation_error is not None:
        raise ArtifactMutationError("ART_RELATIONSHIP_INVALID", relation_error)
    contract = _role_contract(row["Role Contract"])
    if row["Role"] == "EVIDENCE":
        required = {"target", "captured_at", "method", "result", "content_class", "sha256"}
        if (
            not required.issubset(contract)
            or _relation_target(relations, "EVIDENCE_FOR") != contract.get("target")
            or not _valid_timestamp(contract.get("captured_at", ""))
            or contract.get("content_class") not in {"RAW", "SUMMARY", "GENERATED_REPORT"}
            or not _valid_sha256(contract.get("sha256"))
        ):
            raise ArtifactMutationError("ART_EVIDENCE_CONTRACT_REQUIRED", "Evidence registration requires the complete Evidence contract.")
    if row["Role"] == "RECOVERY":
        required = {"target", "restore", "scope", "verify", "sha256"}
        if (
            not required.issubset(contract)
            or _relation_target(relations, "RECOVERY_FOR") != contract.get("target")
            or not _valid_sha256(contract.get("sha256"))
        ):
            raise ArtifactMutationError("ART_RECOVERY_CONTRACT_REQUIRED", "Recovery registration requires the complete Recovery contract.")
    locator = row["Locator"].strip("` ")
    code, message = _locator_issue(root, locator, row["Authority"])
    if code is not None:
        raise ArtifactMutationError(code, message or "Artifact locator is invalid.", locator)
    frozen_role = row["Role"] in {"EVIDENCE", "RECOVERY"} or (row["Role"] == "DELIVERABLE" and verification == "PASS")
    if frozen_role:
        expected_hash = contract.get("sha256")
        if not _valid_sha256(expected_hash):
            raise ArtifactMutationError("ART_HASH_REQUIRED", "Frozen Artifact role requires SHA-256 in Role Contract.")
        if row["Authority"] in {"WORKSPACE", "GENERATED"}:
            payload_path, payload_error = _safe_workspace_path(root, locator)
            if payload_error is not None or payload_path is None or not payload_path.is_file():
                raise ArtifactMutationError("ART_HASH_TARGET_NOT_FILE", payload_error or "Frozen Artifact locator must be an exact file or manifest file.", locator)
            observed_hash = _hash(payload_path.read_bytes())
            if observed_hash != expected_hash.upper():
                raise ArtifactMutationError(
                    "ART_HASH_MISMATCH",
                    "Frozen Artifact SHA-256 does not match its current exact payload bytes.",
                    {"expected": expected_hash.upper(), "observed": observed_hash},
                )


def _render_owner_rows(
    original: bytes,
    text: str,
    marker: str,
    insertion: str,
    rows: list[dict[str, str]],
) -> bytes:
    title = "Artifact Registry"
    rendered = _table_section(marker, title, OWNER_HEADERS, rows)
    return _encode_markdown_like(original, _replace_or_insert_section(text, marker, rendered, insertion))


def _index_rows(path: Path, marker: str, headers: tuple[str, ...]) -> tuple[bytes | None, str, list[dict[str, str]]]:
    if not path.exists():
        return None, "", []
    if not path.is_file():
        raise ArtifactMutationError("ART_INDEX_PATH_TYPE", "Artifact index path must be a regular file.", str(path))
    original, text = _read_markdown(path)
    section = _section(text, marker)
    if section is None:
        raise ArtifactMutationError("ART_REGISTRY_SCHEMA_INVALID", f"Artifact index lacks section {marker}.", str(path))
    return original, text, _table(section, headers)


def _render_index(
    original: bytes | None,
    text: str,
    marker: str,
    headers: tuple[str, ...],
    rows: list[dict[str, str]],
) -> bytes:
    if marker == "shared-artifacts":
        preamble = SHARED_INDEX_PREAMBLE
        title = "Shared Artifact Registry"
    else:
        preamble = ARCHIVE_INDEX_PREAMBLE
        title = "Archive Artifact Registry"
    rendered = _table_section(marker, title, headers, rows)
    if original is None:
        body = rendered
        heading = preamble.split(f"<!-- MALTS:section={marker} -->", 1)[0]
        return (heading + body).encode("utf-8")
    return _encode_markdown_like(original, _replace_or_insert_section(text, marker, rendered))


def _index_path(root: Path, value: str, default_value: str) -> tuple[Path, str]:
    relative = default_value if value == "N/A" else value
    path, error = _safe_workspace_path(root, relative)
    if error is not None or path is None or not relative.replace("\\", "/").endswith("/INDEX.md"):
        raise ArtifactMutationError("ART_INDEX_PATH_INVALID", error or "Index must be a safe workspace-relative INDEX.md path.", relative)
    return path, relative.replace("\\", "/")


def _snapshot_for_enrollment(
    snapshot: dict[str, Any],
    *,
    project_bytes: bytes,
    shared_index: str,
    archive_index: str,
    captured_at: str,
) -> dict[str, Any]:
    updated = json.loads(json.dumps(snapshot))
    updated["enrollment"] = {
        "contract_version": 1,
        "status": "ENROLLED",
        "root_index_path": "PROJECT_CONTROL.md",
        "shared_index": shared_index,
        "archive_index": archive_index,
        "latest_audit": f"{captured_at} / PASS",
    }
    updated["findings"] = [
        item
        for item in updated["findings"]
        if item["code"] not in {"ART_CONTRACT_NOT_DECLARED", "ART_OWNER_REGISTRY_NOT_ENROLLED", "ART_LEGACY_ROOT_CANDIDATE"}
    ]
    updated["counts"]["issues"] = sum(item["severity"] == "ISSUE" for item in updated["findings"])
    updated["counts"]["warnings"] = sum(item["severity"] == "WARNING" for item in updated["findings"])
    updated["counts"]["candidates"] = sum(item["severity"] == "CANDIDATE" for item in updated["findings"])
    updated["input_hashes"] = [
        item for item in updated["input_hashes"] if item["path"] != "runtime/artifact_audit_snapshot.json"
    ]
    for item in updated["input_hashes"]:
        if item["path"] == "PROJECT_CONTROL.md":
            item.update({"bytes": len(project_bytes), "sha256": _hash(project_bytes)})
    fingerprint_payload = {
        "captured_at": updated["captured_at"],
        "enrollment": updated["enrollment"],
        "input_hashes": updated["input_hashes"],
        "artifacts": updated["artifacts"],
        "findings": updated["findings"],
    }
    updated["capture_fingerprint"] = _hash(_json_bytes(fingerprint_payload))
    return updated


def _snapshot_file_preconditions(root: Path, snapshot: Mapping[str, Any]) -> dict[Path, str | None]:
    result: dict[Path, str | None] = {}
    for item in snapshot.get("input_hashes", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        if item.get("kind") == "CANDIDATE_ROOT_SIGNATURE":
            continue
        path, error = _safe_workspace_path(root, item["path"])
        if error is None and path is not None and path.is_file():
            result[path] = item.get("sha256")
    return result


def artifact_snapshot_preconditions(root: Path, snapshot: Mapping[str, Any]) -> dict[Path, str | None]:
    """Return exact file preconditions for a captured read-only Artifact snapshot."""
    return _snapshot_file_preconditions(root.resolve(strict=True), snapshot)


def plan_enrollment_apply(
    root: Path,
    state: dict[str, Any],
    *,
    captured_at: str,
    shared_index: str,
    archive_index: str,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    project_path, project_original, project_text, current = _read_contract(root)
    for label, value in (("shared", shared_index), ("archive", archive_index)):
        if value == "N/A":
            continue
        path, _ = _index_path(root, value, f"{label}/INDEX.md")
        if not path.is_file():
            raise ArtifactMutationError("ART_ENROLLMENT_INDEX_MISSING", "Enrollment requires every declared index to exist before apply.", value)
        if label == "shared":
            _index_rows(path, "shared-artifacts", SHARED_HEADERS)
        else:
            _index_rows(path, "archive-artifacts", ARCHIVE_HEADERS)
    if current["status"] == "ENROLLED":
        if current["shared_index"] == shared_index and current["archive_index"] == archive_index:
            return {"changes": {}, "precondition_hashes": {}, "idempotent": True, "enrollment": current}
        raise ArtifactMutationError("ART_ENROLLMENT_CONFLICT", "Workspace is already enrolled with different index pointers.")
    runtime_snapshot_path = root / "runtime" / "artifact_audit_snapshot.json"
    if runtime_snapshot_path.exists() and not runtime_snapshot_path.is_file():
        raise ArtifactMutationError(
            "ART_RUNTIME_SNAPSHOT_PATH_TYPE",
            "Enrollment Runtime snapshot target must be absent or a regular file.",
            _relative(root, runtime_snapshot_path),
        )
    runtime_snapshot_original = runtime_snapshot_path.read_bytes() if runtime_snapshot_path.is_file() else None
    snapshot = audit_workspace(root, state, captured_at=captured_at)
    issues = [item for item in snapshot["findings"] if item["severity"] == "ISSUE"]
    if issues:
        raise ArtifactMutationError("ART_ENROLLMENT_AUDIT_BLOCKED", "Enrollment is blocked by current Artifact audit issues.", issues, blocked=True)
    project_path, project_original, project_bytes = _replace_root_contract(
        root,
        enrollment="ENROLLED",
        shared_index=shared_index,
        archive_index=archive_index,
        latest_audit=f"{captured_at} / PASS",
        source_original=project_original,
        source_text=project_text,
    )
    runtime_snapshot = _snapshot_for_enrollment(
        snapshot,
        project_bytes=project_bytes,
        shared_index=shared_index,
        archive_index=archive_index,
        captured_at=captured_at,
    )
    preconditions = _snapshot_file_preconditions(root, snapshot)
    preconditions[project_path] = _hash(project_original)
    preconditions[runtime_snapshot_path] = _hash(runtime_snapshot_original) if runtime_snapshot_original is not None else None
    return {
        "changes": {
            project_path: project_bytes,
            runtime_snapshot_path: _json_bytes(runtime_snapshot),
        },
        "precondition_hashes": preconditions,
        "idempotent": False,
        "enrollment": runtime_snapshot["enrollment"],
    }


def plan_register(
    root: Path,
    state: dict[str, Any],
    *,
    owner_ref: str,
    artifact_id: str,
    role: str,
    locator: str,
    authority: str,
    vcs: str,
    verification: str,
    retention: str,
    disposition: str,
    relationships: str,
    role_contract: str,
    purpose: str | None = None,
    applies_to: str | None = None,
    source: str | None = None,
    maintainer: str | None = None,
    last_verified: str | None = None,
    shared_status: str = "CURRENT",
    original_owner: str | None = None,
    archived_at: str | None = None,
    archive_reason: str | None = None,
    successor: str = "N/A",
    manifest: str = "N/A",
) -> dict[str, Any]:
    project_path, project_original, _, contract_state = _read_contract(root)
    if contract_state["status"] != "ENROLLED":
        raise ArtifactMutationError("ART_ENROLLMENT_REQUIRED", "Register requires explicit Artifact Lifecycle enrollment.")
    if owner_ref == "shared":
        return _plan_register_shared(
            root,
            artifact_id=artifact_id,
            role=role,
            locator=locator,
            authority=authority,
            vcs=vcs,
            verification=verification,
            retention=retention,
            relationships=relationships,
            purpose=purpose,
            applies_to=applies_to,
            source=source,
            maintainer=maintainer,
            last_verified=last_verified,
            status=shared_status,
        )
    if owner_ref == "archive":
        return _plan_register_archive(
            root,
            artifact_id=artifact_id,
            role=role,
            locator=locator,
            authority=authority,
            vcs=vcs,
            verification=verification,
            relationships=relationships,
            original_owner=original_owner,
            archived_at=archived_at,
            reason=archive_reason,
            successor=successor,
            manifest=manifest,
        )
    path, original, text, marker, insertion, rows = _owner_rows(root, state, owner_ref)
    row = {
        "Artifact ID": artifact_id,
        "Role": role,
        "Locator": locator,
        "Authority": authority,
        "VCS": vcs,
        "Verification": verification,
        "Retention": retention,
        "Disposition": disposition,
        "Relationships": relationships,
        "Role Contract": role_contract,
    }
    for key in row:
        row[key] = _cell(row[key], key)
    _validate_common_row(root, row)
    identical = next((item for item in rows if item["Artifact ID"] == artifact_id and item == row), None)
    if identical is not None:
        return {"changes": {}, "precondition_hashes": {}, "idempotent": True, "artifact_ref": f"{owner_ref}:{artifact_id}", "external_payload_read": False}
    if any(item["Artifact ID"] == artifact_id for item in rows):
        raise ArtifactMutationError("ART_ID_COLLISION", "Owner registry already contains this Artifact ID.", artifact_id)
    if any(item["Locator"].strip("` ") == locator.strip("` ") for item in rows):
        raise ArtifactMutationError("ART_LOCATOR_COLLISION", "Owner registry already contains this locator.", locator)
    rows.append(row)
    preconditions: dict[Path, str | None] = {project_path: _hash(project_original), path: _hash(original)}
    frozen_role = role in {"EVIDENCE", "RECOVERY"} or (role == "DELIVERABLE" and verification.split(":", 1)[0] == "PASS")
    if frozen_role and authority in {"WORKSPACE", "GENERATED"}:
        payload_path, _ = _safe_workspace_path(root, locator.strip("` "))
        assert payload_path is not None
        preconditions[payload_path] = _role_contract(role_contract)["sha256"].upper()
    return {
        "changes": {path: _render_owner_rows(original, text, marker, insertion, rows)},
        "precondition_hashes": preconditions,
        "idempotent": False,
        "artifact_ref": f"{owner_ref}:{artifact_id}",
        "external_payload_read": False,
    }


def _add_relation(value: str, relation: str) -> str:
    relations, error = _relationships(value)
    if error is not None:
        raise ArtifactMutationError("ART_RELATIONSHIP_INVALID", error)
    if relation not in relations:
        relations.append(relation)
    return ";".join(relations) if relations else "N/A"


def _remove_relations(value: str, *, exact: set[str] | None = None, prefixes: tuple[str, ...] = ()) -> str:
    relations, error = _relationships(value)
    if error is not None:
        raise ArtifactMutationError("ART_RELATIONSHIP_INVALID", error)
    exact = exact or set()
    kept = [item for item in relations if item not in exact and not item.startswith(prefixes)]
    return ";".join(kept) if kept else "N/A"


def _shared_context(root: Path) -> tuple[dict[str, Any], Path, str, bytes | None, str, list[dict[str, str]], dict[Path, bytes], dict[Path, str | None]]:
    project_path, project_original, project_text, contract = _read_contract(root)
    if contract["status"] != "ENROLLED":
        raise ArtifactMutationError("ART_ENROLLMENT_REQUIRED", "Shared mutation requires explicit Artifact Lifecycle enrollment.")
    path, relative = _index_path(root, contract["shared_index"], "shared/INDEX.md")
    original, text, rows = _index_rows(path, "shared-artifacts", SHARED_HEADERS)
    if contract["shared_index"] != "N/A" and original is None:
        raise ArtifactMutationError(
            "ART_ENROLLED_INDEX_MISSING",
            "Declared enrolled Shared index is missing and cannot be recreated implicitly.",
            relative,
        )
    root_changes: dict[Path, bytes] = {}
    root_preconditions: dict[Path, str | None] = {project_path: _hash(project_original)}
    if contract["shared_index"] == "N/A":
        project_path, project_original, project_bytes = _replace_root_contract(
            root,
            enrollment="ENROLLED",
            shared_index=relative,
            archive_index=contract["archive_index"],
            latest_audit=contract["latest_audit"],
            source_original=project_original,
            source_text=project_text,
        )
        root_changes[project_path] = project_bytes
    return contract, path, relative, original, text, rows, root_changes, root_preconditions


def _archive_context(root: Path) -> tuple[dict[str, Any], Path, str, bytes | None, str, list[dict[str, str]], dict[Path, bytes], dict[Path, str | None]]:
    project_path, project_original, project_text, contract = _read_contract(root)
    if contract["status"] != "ENROLLED":
        raise ArtifactMutationError("ART_ENROLLMENT_REQUIRED", "Archive mutation requires explicit Artifact Lifecycle enrollment.")
    path, relative = _index_path(root, contract["archive_index"], "archive/INDEX.md")
    original, text, rows = _index_rows(path, "archive-artifacts", ARCHIVE_HEADERS)
    if contract["archive_index"] != "N/A" and original is None:
        raise ArtifactMutationError(
            "ART_ENROLLED_INDEX_MISSING",
            "Declared enrolled Archive index is missing and cannot be recreated implicitly.",
            relative,
        )
    root_changes: dict[Path, bytes] = {}
    root_preconditions: dict[Path, str | None] = {project_path: _hash(project_original)}
    if contract["archive_index"] == "N/A":
        project_path, project_original, project_bytes = _replace_root_contract(
            root,
            enrollment="ENROLLED",
            shared_index=contract["shared_index"],
            archive_index=relative,
            latest_audit=contract["latest_audit"],
            source_original=project_original,
            source_text=project_text,
        )
        root_changes[project_path] = project_bytes
    return contract, path, relative, original, text, rows, root_changes, root_preconditions


def _plan_register_shared(
    root: Path,
    *,
    artifact_id: str,
    role: str,
    locator: str,
    authority: str,
    vcs: str,
    verification: str,
    retention: str,
    relationships: str,
    purpose: str | None,
    applies_to: str | None,
    source: str | None,
    maintainer: str | None,
    last_verified: str | None,
    status: str,
) -> dict[str, Any]:
    if role != "DELIVERABLE":
        raise ArtifactMutationError("ART_SHARED_ROLE_INVALID", "Direct Shared registration requires Role DELIVERABLE.")
    if not re.fullmatch(r"SHR-[0-9]{3,}", artifact_id):
        raise ArtifactMutationError("ART_ID_INVALID", "Direct Shared ID must match SHR-001 style.", artifact_id)
    if authority not in AUTHORITIES or vcs not in VCS_STATES:
        raise ArtifactMutationError("ART_SHARED_BOUNDARY_INVALID", "Direct Shared authority or VCS boundary is invalid.")
    if verification.split(":", 1)[0] != "PASS":
        raise ArtifactMutationError("ART_PROMOTION_UNVERIFIED", "Direct Shared registration requires explicit PASS verification.", blocked=True)
    values = {"Purpose": purpose, "Applies To": applies_to, "Source": source, "Maintainer": maintainer, "Last Verified": last_verified}
    if any(value is None or value.strip().upper() in PLACEHOLDERS for value in values.values()):
        raise ArtifactMutationError("ART_SHARED_METADATA_REQUIRED", "Direct Shared registration requires purpose, scope, source, maintainer, and verification time.")
    assert purpose is not None and applies_to is not None and source is not None and maintainer is not None and last_verified is not None
    if not _valid_timestamp(last_verified):
        raise ArtifactMutationError("ART_SHARED_VERIFICATION_INVALID", "Shared Last Verified must be timezone-qualified ISO 8601.")
    if status not in {"CURRENT", "SUPERSEDED"}:
        raise ArtifactMutationError("ART_SHARED_STATUS_INVALID", "Shared Status must be CURRENT or SUPERSEDED.")
    if retention.strip().upper() in PLACEHOLDERS:
        raise ArtifactMutationError("ART_RETENTION_REQUIRED", "Shared registration requires explicit retention.")
    if not (ARTIFACT_REF.fullmatch(source) or EXTERNAL_REF.fullmatch(source)):
        raise ArtifactMutationError("ART_SHARED_SOURCE_REQUIRED", "Shared Source must be a stable Artifact or explicit external reference.")
    code, message = _locator_issue(root, locator.strip("` "), authority)
    if code is not None:
        raise ArtifactMutationError(code, message or "Shared locator is invalid.", locator)
    relations, relation_error = _relationships(relationships)
    if relation_error is not None:
        raise ArtifactMutationError("ART_RELATIONSHIP_INVALID", relation_error)
    if status == "CURRENT" and "SOURCE_OF_TRUTH" not in relations:
        relations.append("SOURCE_OF_TRUTH")
    rendered_relationships = ";".join(relations) if relations else "N/A"
    _, path, _, original, text, rows, root_changes, root_preconditions = _shared_context(root)
    row = {
        "Shared ID": artifact_id,
        "Purpose": purpose,
        "Applies To": applies_to,
        "Locator": locator,
        "Authority": authority,
        "VCS": vcs,
        "Status": status,
        "Source": source,
        "Maintainer": maintainer,
        "Retention": retention,
        "Last Verified": last_verified,
        "Relationships": rendered_relationships,
    }
    if any(item["Shared ID"] == artifact_id and item == row for item in rows):
        return {"changes": {}, "precondition_hashes": {}, "idempotent": True, "artifact_ref": f"shared:{artifact_id}", "external_payload_read": False}
    if any(item["Shared ID"] == artifact_id for item in rows):
        raise ArtifactMutationError("ART_ID_COLLISION", "Shared registry already contains this ID.", artifact_id)
    if any(item["Locator"].strip("` ") == locator.strip("` ") for item in rows):
        raise ArtifactMutationError("ART_LOCATOR_COLLISION", "Shared registry already contains this locator.", locator)
    key = (" ".join(purpose.lower().split()), " ".join(applies_to.lower().split()))
    if status == "CURRENT" and any(
        item["Status"] == "CURRENT"
        and (" ".join(item["Purpose"].lower().split()), " ".join(item["Applies To"].lower().split())) == key
        for item in rows
    ):
        raise ArtifactMutationError("ART_SHARED_CURRENT_CONFLICT", "Direct registration would create a competing CURRENT Shared authority.", blocked=True)
    rows.append(row)
    changes = dict(root_changes)
    changes[path] = _render_index(original, text, "shared-artifacts", SHARED_HEADERS, rows)
    preconditions = dict(root_preconditions)
    preconditions[path] = _hash(original) if original is not None else None
    return {"changes": changes, "precondition_hashes": preconditions, "idempotent": False, "artifact_ref": f"shared:{artifact_id}", "external_payload_read": False}


def _plan_register_archive(
    root: Path,
    *,
    artifact_id: str,
    role: str,
    locator: str,
    authority: str,
    vcs: str,
    verification: str,
    relationships: str,
    original_owner: str | None,
    archived_at: str | None,
    reason: str | None,
    successor: str,
    manifest: str,
) -> dict[str, Any]:
    if role != "RECOVERY":
        raise ArtifactMutationError("ART_ARCHIVE_ROLE_INVALID", "Direct Archive registration requires Role RECOVERY.")
    if not re.fullmatch(r"ARC-[0-9]{3,}", artifact_id):
        raise ArtifactMutationError("ART_ID_INVALID", "Direct Archive ID must match ARC-001 style.", artifact_id)
    if authority not in AUTHORITIES or vcs not in VCS_STATES:
        raise ArtifactMutationError("ART_ARCHIVE_BOUNDARY_INVALID", "Direct Archive authority or VCS boundary is invalid.")
    if verification.split(":", 1)[0] != "PASS":
        raise ArtifactMutationError("ART_ARCHIVE_UNVERIFIED", "Direct Archive registration requires explicit PASS verification.", blocked=True)
    if original_owner is None or original_owner.strip().upper() in PLACEHOLDERS or reason is None or reason.strip().upper() in PLACEHOLDERS:
        raise ArtifactMutationError("ART_ARCHIVE_PROVENANCE_REQUIRED", "Archive registration requires original owner and reason.")
    if archived_at is None or not _valid_timestamp(archived_at):
        raise ArtifactMutationError("ART_ARCHIVE_TIMESTAMP_INVALID", "Archive timestamp must be timezone-qualified ISO 8601.")
    if successor.upper() not in PLACEHOLDERS and not ARTIFACT_REF.fullmatch(successor):
        raise ArtifactMutationError("ART_ARCHIVE_SUCCESSOR_INVALID", "Archive successor must be N/A or a fully qualified Artifact reference.")
    code, message = _locator_issue(root, locator.strip("` "), authority)
    if code is not None:
        raise ArtifactMutationError(code, message or "Archive locator is invalid.", locator)
    _, relation_error = _relationships(relationships)
    if relation_error is not None:
        raise ArtifactMutationError("ART_RELATIONSHIP_INVALID", relation_error)
    _, path, _, original, text, rows, root_changes, root_preconditions = _archive_context(root)
    row = {
        "Archive ID": artifact_id,
        "Locator": locator,
        "Authority": authority,
        "VCS": vcs,
        "Original Owner": original_owner,
        "Archived At": archived_at,
        "Reason": reason,
        "Successor": successor,
        "Manifest": manifest,
        "Relationships": relationships,
    }
    if any(item["Archive ID"] == artifact_id and item == row for item in rows):
        return {"changes": {}, "precondition_hashes": {}, "idempotent": True, "artifact_ref": f"archive:{artifact_id}", "external_payload_read": False}
    if any(item["Archive ID"] == artifact_id for item in rows):
        raise ArtifactMutationError("ART_ID_COLLISION", "Archive registry already contains this ID.", artifact_id)
    if any(item["Locator"].strip("` ") == locator.strip("` ") for item in rows):
        raise ArtifactMutationError("ART_LOCATOR_COLLISION", "Archive registry already contains this locator.", locator)
    rows.append(row)
    changes = dict(root_changes)
    changes[path] = _render_index(original, text, "archive-artifacts", ARCHIVE_HEADERS, rows)
    preconditions = dict(root_preconditions)
    preconditions[path] = _hash(original) if original is not None else None
    return {"changes": changes, "precondition_hashes": preconditions, "idempotent": False, "artifact_ref": f"archive:{artifact_id}", "external_payload_read": False}


def plan_promote(
    root: Path,
    state: dict[str, Any],
    *,
    source_ref: str,
    shared_id: str,
    purpose: str,
    applies_to: str,
    maintainer: str,
    retention: str,
    last_verified: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"SHR-[0-9]{3,}", shared_id):
        raise ArtifactMutationError("ART_ID_INVALID", "Shared ID must match SHR-001 style.", shared_id)
    if not _valid_timestamp(last_verified):
        raise ArtifactMutationError("ART_SHARED_VERIFICATION_INVALID", "Shared Last Verified must be timezone-qualified ISO 8601.")
    for label, value in (("Purpose", purpose), ("Applies To", applies_to), ("Maintainer", maintainer), ("Retention", retention)):
        if value.strip().upper() in PLACEHOLDERS:
            raise ArtifactMutationError("ART_SHARED_METADATA_REQUIRED", f"{label} must be substantive.")
    if not (source_ref.startswith("phase:") or source_ref.startswith("session:")):
        raise ArtifactMutationError("ART_PROMOTION_SOURCE_INVALID", "Promotion source must be a Phase or Session Artifact.", source_ref)
    owner_ref, artifact_id = source_ref.rsplit(":", 1)
    source_path, source_original, source_text, marker, insertion, source_rows = _owner_rows(root, state, owner_ref)
    source_row = next((item for item in source_rows if item["Artifact ID"] == artifact_id), None)
    if source_row is None:
        raise ArtifactMutationError("ART_PROMOTION_SOURCE_MISSING", "Promotion source Artifact is not registered.", source_ref)
    if source_row["Role"] != "DELIVERABLE" or source_row["Verification"].split(":", 1)[0] != "PASS":
        raise ArtifactMutationError("ART_PROMOTION_UNVERIFIED", "Only a verified DELIVERABLE may be promoted.", source_ref, blocked=True)
    contract = _role_contract(source_row["Role Contract"])
    if not _valid_sha256(contract.get("sha256")):
        raise ArtifactMutationError("ART_PROMOTION_HASH_REQUIRED", "Promotion requires the frozen source SHA-256.", source_ref, blocked=True)
    source_payload_path: Path | None = None
    if source_row["Authority"] in {"WORKSPACE", "GENERATED"}:
        source_locator, error = _safe_workspace_path(root, source_row["Locator"].strip("` "))
        if error is not None or source_locator is None or not source_locator.is_file():
            raise ArtifactMutationError("ART_PROMOTION_SOURCE_MISSING", error or "Promotion payload is missing.", source_row["Locator"], blocked=True)
        observed = _hash(source_locator.read_bytes())
        if observed != contract["sha256"].upper():
            raise ArtifactMutationError("ART_PROMOTION_HASH_MISMATCH", "Promotion source hash does not match the frozen contract.", {"expected": contract["sha256"], "observed": observed}, blocked=True)
        source_payload_path = source_locator

    _, shared_path, _, shared_original, shared_text, shared_rows, root_changes, root_preconditions = _shared_context(root)
    normalized_key = (" ".join(purpose.lower().split()), " ".join(applies_to.lower().split()))
    shared_ref = f"shared:{shared_id}"
    expected_shared = {
        "Shared ID": shared_id,
        "Purpose": purpose,
        "Applies To": applies_to,
        "Locator": source_row["Locator"],
        "Authority": source_row["Authority"],
        "VCS": source_row["VCS"],
        "Status": "CURRENT",
        "Source": source_ref,
        "Maintainer": maintainer,
        "Retention": retention,
        "Last Verified": last_verified,
        "Relationships": f"SOURCE_OF_TRUTH;SUPERSEDES:{source_ref}",
    }
    existing = next((item for item in shared_rows if item["Shared ID"] == shared_id), None)
    source_relations, source_relation_error = _relationships(source_row["Relationships"])
    if source_relation_error is not None:
        raise ArtifactMutationError("ART_RELATIONSHIP_INVALID", source_relation_error)
    if existing is not None:
        if (
            existing == expected_shared
            and source_row["Disposition"] == "PROMOTE_SHARED"
            and f"SUPERSEDED_BY:{shared_ref}" in source_relations
        ):
            return {
                "changes": {},
                "precondition_hashes": {},
                "idempotent": True,
                "source_ref": source_ref,
                "shared_ref": shared_ref,
                "external_payload_read": False,
            }
        raise ArtifactMutationError("ART_ID_COLLISION", "Shared registry already contains this ID.", shared_id)
    conflicts = [
        f"shared:{item['Shared ID']}"
        for item in shared_rows
        if item["Status"] == "CURRENT"
        and (" ".join(item["Purpose"].lower().split()), " ".join(item["Applies To"].lower().split())) == normalized_key
    ]
    if conflicts:
        raise ArtifactMutationError(
            "ART_SHARED_CURRENT_CONFLICT",
            "Promotion would create a competing CURRENT Shared authority.",
            conflicts,
            blocked=True,
        )
    source_row["Disposition"] = "PROMOTE_SHARED"
    source_row["Relationships"] = _add_relation(source_row["Relationships"], f"SUPERSEDED_BY:{shared_ref}")
    shared_rows.append(expected_shared)
    changes = dict(root_changes)
    changes[source_path] = _render_owner_rows(source_original, source_text, marker, insertion, source_rows)
    changes[shared_path] = _render_index(shared_original, shared_text, "shared-artifacts", SHARED_HEADERS, shared_rows)
    preconditions = dict(root_preconditions)
    preconditions[source_path] = _hash(source_original)
    preconditions[shared_path] = _hash(shared_original) if shared_original is not None else None
    if source_payload_path is not None:
        preconditions[source_payload_path] = contract["sha256"].upper()
    return {"changes": changes, "precondition_hashes": preconditions, "idempotent": False, "source_ref": source_ref, "shared_ref": shared_ref, "external_payload_read": False}


def _active_control_paths(root: Path, state: dict[str, Any]) -> list[Path]:
    paths = [root / "PROJECT_CONTROL.md"]
    if state.get("active_phase_id") is not None:
        record = next(item for item in state["phase_controls"] if item["phase_id"] == state["active_phase_id"])
        path, error = _safe_workspace_path(root, record["path"])
        if error is not None or path is None:
            raise ArtifactMutationError("ART_REFERENCE_UPDATE_PATH_INVALID", error or "Active Phase control path is invalid.", record["path"])
        paths.append(path)
    if state.get("active_session_id") is not None:
        record = next(item for item in state["session_controls"] if item["session_id"] == state["active_session_id"])
        path, error = _safe_workspace_path(root, record["path"])
        if error is not None or path is None:
            raise ArtifactMutationError("ART_REFERENCE_UPDATE_PATH_INVALID", error or "Active Session control path is invalid.", record["path"])
        paths.append(path)
    return paths


def plan_supersede(
    root: Path,
    state: dict[str, Any],
    *,
    old_ref: str,
    new_ref: str,
    update_reference_paths: list[str],
    captured_at: str,
) -> dict[str, Any]:
    snapshot = audit_workspace(root, state, captured_at=captured_at)
    snapshot_preconditions = _snapshot_file_preconditions(root, snapshot)
    codes = {item["code"] for item in snapshot["findings"] if item["severity"] == "ISSUE"}
    if "ART_SUPERSESSION_CYCLE" in codes:
        raise ArtifactMutationError("ART_SUPERSESSION_CYCLE", "Existing supersession graph contains a cycle.", blocked=True)
    if not old_ref.startswith("shared:SHR-") or not new_ref.startswith("shared:SHR-") or old_ref == new_ref:
        raise ArtifactMutationError("ART_SUPERSESSION_REF_INVALID", "Supersession requires two distinct fully qualified Shared references.")
    _, shared_path, _, shared_original, shared_text, rows, root_changes, root_preconditions = _shared_context(root)
    old_id = old_ref.split(":", 1)[1]
    new_id = new_ref.split(":", 1)[1]
    old = next((item for item in rows if item["Shared ID"] == old_id), None)
    new = next((item for item in rows if item["Shared ID"] == new_id), None)
    if old is None or new is None:
        raise ArtifactMutationError("ART_SUPERSESSION_REF_MISSING", "Old and new Shared entries must already exist.")
    old_key = (" ".join(old["Purpose"].lower().split()), " ".join(old["Applies To"].lower().split()))
    new_key = (" ".join(new["Purpose"].lower().split()), " ".join(new["Applies To"].lower().split()))
    if old_key != new_key:
        raise ArtifactMutationError("ART_SUPERSESSION_SCOPE_MISMATCH", "Supersession entries must own the same normalized purpose and scope.")

    active_paths = _active_control_paths(root, state)
    stale_paths = [_relative(root, path) for path in active_paths if path.is_file() and old_ref in path.read_text(encoding="utf-8-sig")]
    requested = sorted({item.replace("\\", "/") for item in update_reference_paths})
    old_relations, old_relation_error = _relationships(old["Relationships"])
    new_relations, new_relation_error = _relationships(new["Relationships"])
    if old_relation_error is not None or new_relation_error is not None:
        raise ArtifactMutationError("ART_RELATIONSHIP_INVALID", old_relation_error or new_relation_error)
    already_applied = (
        old["Status"] == "SUPERSEDED"
        and new["Status"] == "CURRENT"
        and "SOURCE_OF_TRUTH" not in old_relations
        and f"SUPERSEDED_BY:{new_ref}" in old_relations
        and "SOURCE_OF_TRUTH" in new_relations
        and f"SUPERSEDES:{old_ref}" in new_relations
        and not any(item.startswith("SUPERSEDED_BY:") for item in new_relations)
    )
    if already_applied:
        if stale_paths:
            raise ArtifactMutationError(
                "ART_ACTIVE_REFERENCE_UPDATE_REQUIRED",
                "Active controls reintroduced references to the superseded Shared entry.",
                stale_paths,
                blocked=True,
            )
        active_relatives = {_relative(root, path) for path in active_paths}
        if any(relative not in active_relatives for relative in requested):
            raise ArtifactMutationError("ART_REFERENCE_UPDATE_SCOPE_INVALID", "Reference update paths must remain active control paths.")
        for relative in requested:
            path, error = _safe_workspace_path(root, relative)
            if error is not None or path is None or not path.is_file():
                raise ArtifactMutationError("ART_REFERENCE_UPDATE_PATH_INVALID", error or "Reference update path is missing.", relative)
            current_text = path.read_text(encoding="utf-8-sig")
            if old_ref in current_text or new_ref not in current_text:
                raise ArtifactMutationError("ART_REFERENCE_UPDATE_SCOPE_INVALID", "Previously reviewed reference path no longer reflects the successor.", relative)
        return {
            "changes": {},
            "precondition_hashes": {},
            "idempotent": True,
            "old_ref": old_ref,
            "new_ref": new_ref,
            "stale_reference_paths": [],
        }
    if old["Status"] != "CURRENT" or new["Status"] != "SUPERSEDED":
        raise ArtifactMutationError("ART_SUPERSESSION_STATE_INVALID", "Old must be CURRENT and successor must be staged as SUPERSEDED.")
    missing = sorted(set(stale_paths) - set(requested))
    if missing:
        raise ArtifactMutationError(
            "ART_ACTIVE_REFERENCE_UPDATE_REQUIRED",
            "Active controls still reference the superseded Shared entry.",
            missing,
            blocked=True,
        )
    if sorted(set(requested) - set(stale_paths)):
        raise ArtifactMutationError("ART_REFERENCE_UPDATE_SCOPE_INVALID", "Reference update paths must exactly match active stale-reference paths.")

    old["Status"] = "SUPERSEDED"
    old["Relationships"] = _remove_relations(old["Relationships"], exact={"SOURCE_OF_TRUTH"}, prefixes=("SUPERSEDED_BY:",))
    old["Relationships"] = _add_relation(old["Relationships"], f"SUPERSEDED_BY:{new_ref}")
    new["Status"] = "CURRENT"
    new["Relationships"] = _remove_relations(new["Relationships"], prefixes=("SUPERSEDED_BY:",))
    new["Relationships"] = _add_relation(new["Relationships"], "SOURCE_OF_TRUTH")
    new["Relationships"] = _add_relation(new["Relationships"], f"SUPERSEDES:{old_ref}")
    graph: dict[str, set[str]] = {}
    for row in rows:
        ref = f"shared:{row['Shared ID']}"
        relations, error = _relationships(row["Relationships"])
        if error is not None:
            raise ArtifactMutationError("ART_RELATIONSHIP_INVALID", error)
        graph[ref] = {
            target for relation in relations for target in [_relation_value(relation, "SUPERSEDES")] if target is not None
        }
    if _has_cycle(graph):
        raise ArtifactMutationError("ART_SUPERSESSION_CYCLE", "Proposed supersession graph contains a cycle.", blocked=True)
    changes = dict(root_changes)
    preconditions = dict(snapshot_preconditions)
    preconditions.update(root_preconditions)
    changes[shared_path] = _render_index(shared_original, shared_text, "shared-artifacts", SHARED_HEADERS, rows)
    preconditions[shared_path] = _hash(shared_original) if shared_original is not None else None
    for relative in requested:
        path, error = _safe_workspace_path(root, relative)
        if error is not None or path is None or not path.is_file():
            raise ArtifactMutationError("ART_REFERENCE_UPDATE_PATH_INVALID", error or "Reference update path is missing.", relative)
        original, text = _read_markdown(path)
        changes[path] = _encode_markdown_like(original, text.replace(old_ref, new_ref))
        preconditions[path] = _hash(original)
    return {
        "changes": changes,
        "precondition_hashes": preconditions,
        "idempotent": False,
        "old_ref": old_ref,
        "new_ref": new_ref,
        "stale_reference_paths": stale_paths,
    }


def plan_reconcile(
    root: Path,
    state: dict[str, Any],
    *,
    owner_ref: str,
    decisions: Mapping[str, str],
) -> dict[str, Any]:
    project_path, project_original, _, contract_state = _read_contract(root)
    if contract_state["status"] != "ENROLLED":
        return {"changes": {}, "precondition_hashes": {}, "idempotent": True, "owner_ref": owner_ref, "rows": [], "unresolved": []}
    path, original, text, marker, insertion, rows = _owner_rows(root, state, owner_ref)
    known = {item["Artifact ID"] for item in rows}
    unknown = sorted(set(decisions) - known)
    if unknown:
        raise ArtifactMutationError("ART_RECONCILE_ID_UNKNOWN", "Disposition decision references unknown Artifact IDs.", unknown)
    changed = False
    for row in rows:
        requested = decisions.get(row["Artifact ID"])
        if requested is None:
            continue
        if requested not in DISPOSITIONS:
            raise ArtifactMutationError("ART_DISPOSITION_INVALID", "Reconcile disposition is invalid.", requested)
        if row["Disposition"] != requested:
            row["Disposition"] = requested
            changed = True
    unresolved = [f"{owner_ref}:{row['Artifact ID']}" for row in rows if row["Disposition"] == "UNRESOLVED"]
    changes = {path: _render_owner_rows(original, text, marker, insertion, rows)} if changed else {}
    return {
        "changes": changes,
        "precondition_hashes": {project_path: _hash(project_original), path: _hash(original)} if changed else {},
        "idempotent": not changed,
        "owner_ref": owner_ref,
        "rows": [{"artifact_ref": f"{owner_ref}:{row['Artifact ID']}", "disposition": row["Disposition"]} for row in rows],
        "unresolved": unresolved,
    }


def artifact_close_gate(root: Path, state: dict[str, Any], owner_ref: str, *, captured_at: str) -> dict[str, Any]:
    snapshot = audit_workspace(root, state, captured_at=captured_at)
    if snapshot["enrollment"]["status"] != "ENROLLED":
        return {"status": "PASS", "reason_code": None, "unresolved": [], "snapshot": snapshot}
    issues = [item for item in snapshot["findings"] if item["severity"] == "ISSUE"]
    if issues:
        return {"status": "BLOCKED", "reason_code": "ART_CLOSE_AUDIT_ISSUES", "unresolved": [], "issues": issues, "snapshot": snapshot}
    unresolved = [item["artifact_ref"] for item in snapshot["artifacts"] if item["owner_ref"] == owner_ref and item["disposition"] == "UNRESOLVED"]
    if unresolved:
        return {"status": "BLOCKED", "reason_code": "ART_CLOSE_UNRESOLVED", "unresolved": unresolved, "issues": [], "snapshot": snapshot}
    return {"status": "PASS", "reason_code": None, "unresolved": [], "issues": [], "snapshot": snapshot}


def artifact_references_in_text(text: str) -> list[str]:
    return sorted(set(ARTIFACT_REFERENCE_IN_TEXT.findall(text)))
