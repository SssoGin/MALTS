#!/usr/bin/env python3
"""User-facing MALTS project-control helpers.

This module provides user-facing project-control validation and task-ID
discovery.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


TASK_STATUS = {
    "TODO", "READY", "IN_PROGRESS", "REVIEW", "DONE", "BLOCKED", "FAILED", "CANCELLED",
}
ACCEPTANCE_STATUS = {"TODO", "PASS", "FAIL", "N/A"}
PROJECT_CONTROL_SECTIONS = {
    "metadata": ("Metadata", "元信息"),
    "user-original-goal": ("User Original Goal", "用户原始目标"),
    "current-interpreted-goal": ("Current Interpreted Goal", "当前理解目标"),
    "completion-definition": ("Completion Definition", "完成定义"),
    "acceptance-criteria": ("Acceptance Criteria", "验收标准"),
    "current-stage": ("Current Stage", "当前阶段"),
    "task-queue": ("Task Queue", "任务队列"),
    "file-ownership": ("File Ownership", "文件所有权"),
    "decisions": ("Decisions", "决策记录"),
    "verification-records": ("Verification Records", "验证记录"),
    "risks-and-blockers": ("Risks And Blockers", "风险与阻塞"),
    "recovery-notes": ("Recovery Notes", "恢复说明"),
}


@dataclass
class Finding:
    level: str
    message: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def emit(findings: list[Finding]) -> int:
    errors = [finding for finding in findings if finding.level == "ERROR"]
    warnings = [finding for finding in findings if finding.level == "WARN"]
    if not findings:
        print("PASS")
        return 0
    for finding in findings:
        print(f"{finding.level}: {finding.message}")
    if errors:
        return 1
    if warnings:
        print("PASS_WITH_WARNINGS")
    else:
        print("PASS")
    return 0


def project_control_section(text: str, section_id: str, headings: tuple[str, ...]) -> str | None:
    marker = re.compile(rf"^<!--\s*MALTS:section={re.escape(section_id)}\s*-->\s*$", re.MULTILINE)
    marker_match = marker.search(text)
    if marker_match:
        heading_match = re.search(r"^##\s+.+$", text[marker_match.end():], re.MULTILINE)
        if not heading_match:
            return None
        start = marker_match.end() + heading_match.end()
    else:
        heading_pattern = "|".join(re.escape(heading) for heading in headings)
        heading_match = re.search(rf"^##\s+(?:{heading_pattern})\s*$", text, re.MULTILINE)
        if not heading_match:
            return None
        start = heading_match.end()
    next_heading = re.search(r"^##\s+", text[start:], re.MULTILINE)
    return text[start:start + next_heading.start()] if next_heading else text[start:]


def markdown_tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    lines = text.splitlines()
    tables: list[tuple[list[str], list[list[str]]]] = []
    index = 0
    while index + 1 < len(lines):
        if not lines[index].lstrip().startswith("|") or not re.match(r"^\s*\|?\s*:?-{3,}", lines[index + 1]):
            index += 1
            continue
        headers = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
        rows: list[list[str]] = []
        index += 2
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            rows.append([cell.strip() for cell in lines[index].strip().strip("|").split("|")])
            index += 1
        tables.append((headers, rows))
    return tables


def validate_status_table(
    text: str,
    allowed: set[str],
    label: str,
    findings: list[Finding],
    *,
    require_evidence_for_pass: bool = False,
) -> None:
    status_headers = {"status", "状态"}
    evidence_headers = {"evidence", "证据"}
    placeholders = {"TODO / PASS / FAIL / N/A", "TODO/PASS/FAIL/N/A"}
    for headers, rows in markdown_tables(text):
        normalized = [header.casefold() for header in headers]
        status_index = next((index for index, header in enumerate(normalized) if header in status_headers), None)
        if status_index is None:
            continue
        evidence_index = next((index for index, header in enumerate(normalized) if header in evidence_headers), None)
        for row in rows:
            status = row[status_index] if status_index < len(row) else ""
            if status in placeholders:
                findings.append(Finding("WARN", f"Unresolved {label} status placeholder."))
            elif status not in allowed:
                findings.append(Finding("ERROR", f"Invalid {label} status: {status or '<empty>'}"))
            elif require_evidence_for_pass and status == "PASS":
                evidence = row[evidence_index] if evidence_index is not None and evidence_index < len(row) else ""
                if not evidence:
                    findings.append(Finding("ERROR", "PASS acceptance row requires evidence."))


def labeled_value(section: str, labels: tuple[str, ...]) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    pattern = re.compile(rf"^\s*-\s*(?:{label_pattern})\s*[:：]\s*(?P<value>.*?)\s*$", re.IGNORECASE)
    for line in section.splitlines():
        match = pattern.match(line)
        if match:
            return match.group("value").strip()
    return None


def current_state_ids(value: str) -> tuple[str | None, str | None, str | None]:
    round_match = re.search(r"(?<![A-Z0-9])R(?P<id>\d{3})(?!\d)", value, re.IGNORECASE)
    checkpoint_match = re.search(r"(?<![A-Z0-9])CKPT-(?P<id>\d{3})(?!\d)", value, re.IGNORECASE)
    activity = next((candidate for candidate in re.findall(r"\b(?:[A-Z][A-Z0-9]*-)+[A-Z0-9]+\b", value.upper()) if not candidate.startswith("CKPT-")), None)
    return (f"R{round_match.group('id')}" if round_match else None, f"CKPT-{checkpoint_match.group('id')}" if checkpoint_match else None, activity)


def validate_current_state(text: str, sections: dict[str, str], findings: list[Finding]) -> None:
    checkpoint_match = re.search(r"^\s*Checkpoint\s*[:：]\s*(?P<value>.+?)\s*$", text, re.MULTILINE | re.IGNORECASE)
    if not checkpoint_match:
        return
    header_value = checkpoint_match.group("value").strip()
    expected_round, expected_checkpoint, expected_activity = current_state_ids(header_value)
    if not expected_round or not expected_checkpoint:
        findings.append(Finding("ERROR", "Top-level Checkpoint must contain one R### round and one CKPT-### identifier."))
        return
    metadata_value = labeled_value(sections.get("metadata", ""), ("Current round", "当前轮次"))
    stage_value = labeled_value(sections.get("current-stage", ""), ("Stage", "阶段"))
    recovery_value = labeled_value(sections.get("recovery-notes", ""), ("Recovery checkpoint", "恢复检查点"))
    if not metadata_value:
        findings.append(Finding("ERROR", "Checkpointed PROJECT_CONTROL metadata is missing Current round."))
    else:
        metadata_round, _, metadata_activity = current_state_ids(metadata_value)
        if metadata_round != expected_round or (expected_activity and metadata_activity != expected_activity):
            findings.append(Finding("ERROR", "Current round does not match the top-level checkpoint."))
    if not stage_value:
        findings.append(Finding("ERROR", "Checkpointed PROJECT_CONTROL current-stage section is missing Stage."))
    else:
        stage_round, stage_checkpoint, stage_activity = current_state_ids(stage_value)
        if stage_round != expected_round or stage_checkpoint != expected_checkpoint or (expected_activity and stage_activity != expected_activity):
            findings.append(Finding("ERROR", "Current Stage does not match the top-level checkpoint."))
    if recovery_value:
        recovery_round, recovery_checkpoint, recovery_activity = current_state_ids(recovery_value)
        if recovery_round != expected_round or recovery_checkpoint != expected_checkpoint or (expected_activity and recovery_activity != expected_activity):
            findings.append(Finding("ERROR", "Recovery checkpoint does not match the top-level checkpoint."))


def normalize_semver(value: str) -> str | None:
    match = re.search(r"(?<!\d)(?:MALTS\s*)?v?(\d+\.\d+\.\d+)(?!\d)", value, re.IGNORECASE)
    return match.group(1) if match else None


def validate_version(metadata: str, expected_version: str, findings: list[Finding]) -> None:
    version_line = next((match.group("value").strip().strip("`") for line in metadata.splitlines() if (match := re.match(r"^\s*-\s*(?:Control version|MALTS runtime version|控制文件版本|MALTS\s*运行时版本)\s*[:：]\s*(?P<value>.+?)\s*$", line))), None)
    if version_line is None:
        findings.append(Finding("ERROR", "PROJECT_CONTROL metadata is missing current MALTS version metadata."))
    elif normalize_semver(version_line) != expected_version:
        findings.append(Finding("ERROR", f"PROJECT_CONTROL MALTS version `{normalize_semver(version_line) or version_line}` does not match active VERSION `{expected_version}`."))


def check_project_control(path: Path, malts_root: Path | None, malts_version: str | None) -> int:
    findings: list[Finding] = []
    if not path.is_file():
        return emit([Finding("ERROR", f"PROJECT_CONTROL not found: {path}")])
    try:
        text = read_text(path)
    except (OSError, UnicodeDecodeError) as exc:
        return emit([Finding("ERROR", f"PROJECT_CONTROL is not valid UTF-8: {exc}")])
    sections: dict[str, str] = {}
    for section_id, headings in PROJECT_CONTROL_SECTIONS.items():
        content = project_control_section(text, section_id, headings)
        if content is None:
            findings.append(Finding("ERROR", f"Missing section `{section_id}` ({' / '.join(headings)})."))
        else:
            sections[section_id] = content
    validate_status_table(sections.get("task-queue", ""), TASK_STATUS, "task", findings)
    validate_status_table(sections.get("acceptance-criteria", ""), ACCEPTANCE_STATUS, "acceptance", findings, require_evidence_for_pass=True)
    expected_version = normalize_semver(malts_version) if malts_version else None
    if malts_root and not expected_version:
        version_path = malts_root / "VERSION"
        if not version_path.is_file():
            findings.append(Finding("ERROR", f"MALTS VERSION not found: {version_path}"))
        else:
            expected_version = normalize_semver(read_text(version_path).strip())
            if not expected_version:
                findings.append(Finding("ERROR", f"MALTS VERSION is not a semantic version: {version_path}"))
    if expected_version:
        validate_version(sections.get("metadata", ""), expected_version, findings)
    validate_current_state(text, sections, findings)
    return emit(findings)


def next_task_id(path: Path) -> int:
    if not path.exists():
        print("T001")
        return 0
    ids = [int(match) for match in re.findall(r"\bT(\d{3,})\b", read_text(path))]
    print(f"T{max(ids, default=0) + 1:03d}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    control = subparsers.add_parser("check-project-control")
    control.add_argument("--project-control", required=True)
    control.add_argument("--malts-root")
    control.add_argument("--malts-version")
    next_id = subparsers.add_parser("next-task-id")
    next_id.add_argument("--project-control", required=True)
    args = parser.parse_args(argv)
    if args.command == "check-project-control":
        return check_project_control(Path(args.project_control), Path(args.malts_root) if args.malts_root else None, args.malts_version)
    return next_task_id(Path(args.project_control))


if __name__ == "__main__":
    raise SystemExit(main())
