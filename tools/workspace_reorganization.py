"""Project-control candidate validation and byte-preserving reorganization archive helpers."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


CURRENT_ROOT_SECTIONS = (
    "metadata",
    "user-original-goal",
    "current-interpreted-goal",
    "completion-definition",
    "acceptance-criteria",
    "current-stage",
    "plan-recheck-index",
    "phase-carry-over-index",
    "artifact-contract-index",
    "task-queue",
    "file-ownership",
    "decisions",
    "verification-records",
    "risks-and-blockers",
    "recovery-notes",
)
ROOT_SECTION_DISPOSITION = {
    "metadata": "KEEP_PROJECT",
    "user-original-goal": "KEEP_PROJECT",
    "current-interpreted-goal": "KEEP_PROJECT",
    "completion-definition": "KEEP_PROJECT",
    "acceptance-criteria": "KEEP_PROJECT",
    "current-stage": "KEEP_PROJECT",
    "plan-recheck-index": "KEEP_PROJECT",
    "phase-carry-over-index": "KEEP_PROJECT",
    "artifact-contract-index": "KEEP_PROJECT",
    "task-queue": "ARCHIVE_HISTORY",
    "file-ownership": "ARCHIVE_HISTORY",
    "decisions": "KEEP_PROJECT",
    "verification-records": "ARCHIVE_HISTORY",
    "risks-and-blockers": "ARCHIVE_HISTORY",
    "recovery-notes": "KEEP_PROJECT",
}
MAX_REORGANIZED_ROOT_LINES = 220
MAX_REORGANIZED_ROOT_BYTES = 20 * 1024
SOFT_ROOT_LINES = 1500
SOFT_ROOT_BYTES = 262144
SECTION_LINE = re.compile(r"^[ \t]*<!-- MALTS:section=(?P<name>[a-z0-9-]+) -->[ \t]*\r?$", re.IGNORECASE)
PROJECT_FIELD = re.compile(r"(?m)^- (?:Project|项目)(?:\s*)[:：](?P<value>[^\r\n]*?)\s*$", re.IGNORECASE)
ACTIVE_PHASE_FIELD = re.compile(r"(?m)^- Active Phase[:：](?P<value>[^\r\n]*?)\s*$", re.IGNORECASE)
LOCKED_GOAL_FIELD = re.compile(r"(?m)^> (?:Original goal \(locked\)|用户原始目标（锁定）)[:：](?P<value>[^\r\n]*?)\s*$", re.IGNORECASE)
HISTORY_TOKEN = re.compile(r"<!-- MALTS:history:", re.IGNORECASE)
STATIC_GENERATION = re.compile(r"[\\/]lifecycle[\\/]generations[\\/]malts-", re.IGNORECASE)


class ProjectControlCandidateError(ValueError):
    pass


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def decode_markdown(payload: bytes) -> str:
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ProjectControlCandidateError("Project-control candidate is not valid UTF-8.") from exc


def root_metrics(payload: bytes) -> dict[str, int]:
    text = decode_markdown(payload)
    return {"lines": len(text.splitlines()), "bytes": len(payload)}


def _normalized_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    return value


def _section_names(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        match = SECTION_LINE.fullmatch(line)
        if match:
            names.append(match.group("name").lower())
    return names


def validate_project_control_candidate(
    payload: bytes,
    *,
    expected_sha256: str,
    project_id: str,
    active_phase_id: str | None,
) -> dict[str, Any]:
    observed_sha256 = sha256(payload)
    if observed_sha256 != expected_sha256.upper():
        raise ProjectControlCandidateError("Project-control candidate SHA-256 does not match the reviewed candidate.")
    metrics = root_metrics(payload)
    if metrics["lines"] > MAX_REORGANIZED_ROOT_LINES or metrics["bytes"] > MAX_REORGANIZED_ROOT_BYTES:
        raise ProjectControlCandidateError(
            f"Project-control candidate exceeds the reorganized-root target: "
            f"{metrics['lines']} lines/{metrics['bytes']} bytes > "
            f"{MAX_REORGANIZED_ROOT_LINES} lines/{MAX_REORGANIZED_ROOT_BYTES} bytes."
        )
    text = decode_markdown(payload)
    names = _section_names(text)
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ProjectControlCandidateError("Project-control candidate has duplicate MALTS sections: " + ", ".join(duplicates))
    missing = [name for name in CURRENT_ROOT_SECTIONS if name not in names]
    if missing:
        raise ProjectControlCandidateError("Project-control candidate lacks required CURRENT sections: " + ", ".join(missing))
    if [name for name in names if name in CURRENT_ROOT_SECTIONS] != list(CURRENT_ROOT_SECTIONS):
        raise ProjectControlCandidateError("Project-control candidate CURRENT sections are not in canonical order.")
    project_matches = list(PROJECT_FIELD.finditer(text))
    if len(project_matches) != 1 or _normalized_scalar(project_matches[0].group("value")) != project_id:
        raise ProjectControlCandidateError("Project-control candidate Project identity does not match workspace state.")
    phase_matches = list(ACTIVE_PHASE_FIELD.finditer(text))
    if len(phase_matches) != 1:
        raise ProjectControlCandidateError("Project-control candidate must contain exactly one Active Phase field.")
    phase_value = _normalized_scalar(phase_matches[0].group("value"))
    normalized_phase = None if phase_value.casefold() in {"n/a", "na", "none", "null", "无", "暂无"} else phase_value
    if normalized_phase != active_phase_id:
        raise ProjectControlCandidateError("Project-control candidate Active Phase does not match workspace state.")
    goal_matches = list(LOCKED_GOAL_FIELD.finditer(text))
    if len(goal_matches) != 1 or not _normalized_scalar(goal_matches[0].group("value")):
        raise ProjectControlCandidateError("Project-control candidate must retain one substantive locked user goal.")
    if HISTORY_TOKEN.search(text):
        raise ProjectControlCandidateError("Cold history blocks are forbidden in the reorganized hot Project control.")
    if STATIC_GENERATION.search(text):
        raise ProjectControlCandidateError("Project-control candidate contains a physical MALTS generation path.")
    if str(SOFT_ROOT_LINES) not in text or str(SOFT_ROOT_BYTES) not in text:
        raise ProjectControlCandidateError("Project-control candidate must declare the current 1500-line/262144-byte soft capacity.")
    return {
        "path": None,
        "sha256": observed_sha256,
        **metrics,
        "required_sections": list(CURRENT_ROOT_SECTIONS),
    }


def append_project_control_archive(
    existing: bytes | None,
    source: bytes,
    *,
    operation_id: str,
) -> tuple[bytes, dict[str, Any]]:
    source_sha256 = sha256(source)
    archive = existing if existing is not None else b"# PROJECT_CONTROL History\n\n"
    marker = f"MALTS:project-control-preimage operation={operation_id} sha256={source_sha256}"
    if marker.encode("ascii") in archive:
        raise ProjectControlCandidateError("Project-control history already contains this operation/source preimage.")
    if archive and not archive.endswith((b"\n", b"\r")):
        archive += b"\n"
    start = len(archive)
    header = (
        f"\n## Reorganization {operation_id}\n\n"
        f"<!-- {marker} bytes={len(source)} -->\n"
    ).encode("ascii")
    footer = f"\n<!-- MALTS:project-control-preimage-end operation={operation_id} -->\n".encode("ascii")
    payload = archive + header + source + footer
    return payload, {
        "path": "history/PROJECT_CONTROL_HISTORY.md",
        "source_sha256": source_sha256,
        "source_bytes": len(source),
        "archive_sha256": sha256(payload),
        "archive_bytes": len(payload),
        "embedded_offset": start + len(header),
        "embedded_bytes_preserved": True,
    }


def section_dispositions() -> list[dict[str, str]]:
    return [
        {"section": section, "disposition": ROOT_SECTION_DISPOSITION[section]}
        for section in CURRENT_ROOT_SECTIONS
    ]
