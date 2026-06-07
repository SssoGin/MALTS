#!/usr/bin/env python3
"""Lightweight checks and generators for MALTS release repositories.

This public version is intentionally small and path-neutral:
- English runtime docs are the default.
- Chinese mirrors are optional and checked only when explicitly requested.
- No local user profile, archive, session, or machine-specific paths are baked in.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


TASK_STATUS = {
    "TODO",
    "READY",
    "IN_PROGRESS",
    "REVIEW",
    "DONE",
    "BLOCKED",
    "FAILED",
    "CANCELLED",
}

ACCEPTANCE_STATUS = {"TODO", "PASS", "FAIL", "N/A"}

PROJECT_CONTROL_HEADINGS = [
    "Metadata",
    "User Original Goal",
    "Current Interpreted Goal",
    "Completion Definition",
    "Acceptance Criteria",
    "Current Stage",
    "Task Queue",
    "File Ownership",
    "Decisions",
    "Verification Records",
    "Risks And Blockers",
    "Recovery Notes",
]


@dataclass
class Finding:
    level: str
    message: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def emit(findings: list[Finding]) -> int:
    errors = [f for f in findings if f.level == "ERROR"]
    warnings = [f for f in findings if f.level == "WARN"]
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


def check_project_control(path: Path) -> int:
    findings: list[Finding] = []
    if not path.exists():
        return emit([Finding("ERROR", f"PROJECT_CONTROL not found: {path}")])

    text = read_text(path)
    for heading in PROJECT_CONTROL_HEADINGS:
        if f"## {heading}" not in text:
            findings.append(Finding("ERROR", f"Missing heading: ## {heading}"))

    for status in re.findall(r"\|\s*(TODO|READY|IN_PROGRESS|REVIEW|DONE|BLOCKED|FAILED|CANCELLED|[A-Z_]+)\s*\|", text):
        if status in {"PASS", "FAIL", "N/A"}:
            continue
        if status not in TASK_STATUS and status not in ACCEPTANCE_STATUS:
            findings.append(Finding("WARN", f"Unknown status value: {status}"))

    acceptance_section = section(text, "Acceptance Criteria")
    for line in acceptance_section.splitlines():
        if not line.startswith("|") or "---" in line or "Status" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 3 and cells[2] not in ACCEPTANCE_STATUS:
            findings.append(Finding("ERROR", f"Invalid acceptance status: {cells[2]}"))
        if len(cells) >= 4 and cells[2] == "PASS" and not cells[3]:
            findings.append(Finding("ERROR", "PASS acceptance row requires evidence."))

    return emit(findings)


def section(text: str, heading: str) -> str:
    pattern = re.compile(rf"^## {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    next_heading = re.search(r"^##\s+", text[match.end() :], re.MULTILINE)
    if next_heading:
        return text[match.end() : match.end() + next_heading.start()]
    return text[match.end() :]


def next_task_id(path: Path) -> int:
    if not path.exists():
        print("T001")
        return 0
    text = read_text(path)
    ids = [int(match) for match in re.findall(r"\bT(\d{3,})\b", text)]
    next_id = max(ids, default=0) + 1
    print(f"T{next_id:03d}")
    return 0


def check_doc_sync(output_root: Path, manifest: Path | None, require_ch: bool) -> int:
    findings: list[Finding] = []
    if not output_root.exists():
        return emit([Finding("ERROR", f"Output root not found: {output_root}")])

    pairs = load_doc_pairs(manifest)
    ch_root = output_root / "CH"
    if not require_ch:
        if not ch_root.exists():
            print("PASS: Chinese documentation is optional and disabled by default.")
            return 0

    if require_ch and not ch_root.exists() and not pairs:
        findings.append(Finding("ERROR", f"Chinese docs requested but missing: {ch_root}"))

    for pair in pairs:
        en_path = output_root / pair["en"]
        ch_path = output_root / pair["ch"]
        if not en_path.exists():
            findings.append(Finding("ERROR", f"Missing EN doc: {en_path}"))
        if require_ch and not ch_path.exists():
            findings.append(Finding("ERROR", f"Missing CH doc: {ch_path}"))
        if en_path.exists() and ch_path.exists() and require_ch:
            en_levels = heading_levels(read_text(en_path))
            ch_levels = heading_levels(read_text(ch_path))
            if en_levels != ch_levels:
                findings.append(
                    Finding(
                        "ERROR",
                        f"CH doc heading structure differs from EN doc: {pair['en']} -> {pair['ch']}",
                    )
                )

    return emit(findings)


def load_doc_pairs(manifest: Path | None) -> list[dict[str, str]]:
    if not manifest or not manifest.exists():
        return []
    data = json.loads(read_text(manifest))
    return list(data.get("pairs", []))


def heading_levels(text: str) -> list[int]:
    levels: list[int] = []
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+\S+", line)
        if match:
            levels.append(len(match.group(1)))
    return levels


PROJECT_CONTROL_TEMPLATE = """# PROJECT_CONTROL

## Metadata

- Project: {project}
- Control version: v0.1
- Current round: {round_name}
- Last updated: {timestamp}
- Maintainer: Main Controller
- Current mode: {mode}

## User Original Goal

{goal}

## Current Interpreted Goal

- Current understanding: {goal}
- Confirmed exclusions: {confirmed_exclusions}
- Open questions: {open_questions}

## Completion Definition

- [ ] The user's core goal is met.
- [ ] Required deliverables exist.
- [ ] Verification evidence is recorded.
- [ ] Known unfinished items and risks are stated.

## Acceptance Criteria

| Requirement | Verification Method | Status | Evidence |
|---|---|---|---|
{acceptance_rows}

## Current Stage

- Stage: {stage}
- Stage goal: {stage_goal}
- Exit condition: {exit_condition}

## Task Queue

| ID | Priority | Status | Owner | Task | Dependencies | Allowed Changes | Verification |
|---|---|---|---|---|---|---|---|
{task_rows}

## File Ownership

| Path | Owner | Allowed Changes | Notes |
|---|---|---|---|
| N/A | Main Controller | N/A | No file ownership assigned yet. |

## Decisions

| Decision | Reason | Alternatives | Status |
|---|---|---|---|
| N/A | N/A | N/A | N/A |

## Verification Records

| Time | Check | Result | Evidence |
|---|---|---|---|
| {timestamp} | Control file generated | PASS | Generated by `agent_system_lint.py new-project-control`. |

## Risks And Blockers

| Risk | Status | Mitigation |
|---|---|---|
| N/A | N/A | N/A |

## Recovery Notes

Future agents should read this file before continuing the project.
"""


def new_project_control(args: argparse.Namespace) -> int:
    slug = args.slug or slugify(args.project)
    out = args.out or args.output_root / "EN" / "trial-runs" / slug / f"PROJECT_CONTROL.{slug}.en.md"
    ch_out = args.ch_out or args.output_root / "CH" / "trial-runs" / slug / f"PROJECT_CONTROL.{slug}.zh.md"

    acceptance_rows = build_acceptance_rows(args.acceptance)
    task_rows = build_task_rows(args.task)
    timestamp = args.timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    text = PROJECT_CONTROL_TEMPLATE.format(
        project=args.project,
        goal=args.goal,
        mode=args.mode,
        round_name=args.round,
        timestamp=timestamp,
        confirmed_exclusions=args.confirmed_exclusions or "N/A",
        open_questions=args.open_questions or "N/A",
        stage=args.stage,
        stage_goal=args.stage_goal or "Initialize recoverable project state.",
        exit_condition=args.exit_condition or "Control file exists and passes basic validation.",
        acceptance_rows=acceptance_rows,
        task_rows=task_rows,
    )

    planned = [out]
    if args.with_ch:
        planned.append(ch_out)

    if args.dry_run:
        for path in planned:
            print(f"Would write: {path}")
        return 0

    for path in planned:
        if path.exists() and not args.overwrite:
            return emit([Finding("ERROR", f"Refusing to overwrite existing file: {path}")])

    write_text(out, text)
    if args.with_ch:
        write_text(ch_out, text)

    result = check_project_control(out)
    if result != 0:
        return result
    if args.check_doc_sync:
        return check_doc_sync(args.output_root, None, require_ch=args.with_ch)
    return 0


def build_acceptance_rows(values: list[str]) -> str:
    if not values:
        return "| Initial control file exists | Run check-project-control | TODO | |"
    rows = []
    for value in values:
        cells = value.split("|")
        while len(cells) < 4:
            cells.append("")
        rows.append("| " + " | ".join(cell.strip() for cell in cells[:4]) + " |")
    return "\n".join(rows)


def build_task_rows(values: list[str]) -> str:
    if not values:
        return "| T001 | P1 | TODO | Main Controller | Define next task | N/A | Control file only | Review task queue |"
    rows = []
    for index, value in enumerate(values, start=1):
        if "|" in value:
            cells = value.split("|")
            while len(cells) < 8:
                cells.append("")
            rows.append("| " + " | ".join(cell.strip() for cell in cells[:8]) + " |")
        else:
            rows.append(f"| T{index:03d} | P1 | TODO | Main Controller | {value} | N/A | As needed | Verify completion |")
    return "\n".join(rows)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "project"


def gitignore_matches_public_file(pattern: str, rel_paths: list[str]) -> list[str]:
    pattern = pattern.strip()
    if not pattern or pattern.startswith("#") or pattern.startswith("!"):
        return []

    root_anchored = pattern.startswith("/")
    dir_only = pattern.endswith("/")
    clean = pattern.strip("/")
    if not clean:
        return []

    hits: list[str] = []
    for rel in rel_paths:
        parts = rel.split("/")
        if "/" not in clean:
            if root_anchored:
                targets = [parts[0]]
            else:
                targets = parts[:-1] if dir_only else parts
            if any(fnmatch.fnmatchcase(part, clean) for part in targets):
                hits.append(rel)
            continue

        if dir_only:
            dirs = ["/".join(parts[:index]) for index in range(1, len(parts))]
            if root_anchored:
                matched = any(fnmatch.fnmatchcase(directory, clean) for directory in dirs)
            else:
                matched = any(
                    fnmatch.fnmatchcase(directory, clean) or directory.endswith(f"/{clean}")
                    for directory in dirs
                )
            if matched:
                hits.append(rel)
            continue

        if fnmatch.fnmatchcase(rel, clean) or (
            not root_anchored and fnmatch.fnmatchcase(rel, f"*/{clean}")
        ):
            hits.append(rel)

    return hits


def check_semantic_freshness(malts_root: Path, version: str | None) -> int:
    findings: list[Finding] = []
    release_required = [
        ".gitignore",
        "README.md",
        "README.zh-CN.md",
        "VERSION",
        "CHANGELOG.md",
        "LICENSE",
        "docs/CORE_DESIGN.md",
        "docs/BILINGUAL_DOCS.md",
        "docs/INSTALL.md",
        "docs/zh-CN/CORE_DESIGN.md",
        "docs/zh-CN/BILINGUAL_DOCS.md",
        "docs/zh-CN/INSTALL.md",
        "adapters/codex/AGENTS.example.md",
        "adapters/claude-code/CLAUDE.example.md",
        "adapters/claude-code/.claude/agents/explorer.md",
        "adapters/claude-code/.claude/agents/memory-curator.md",
        "adapters/claude-code/.claude/agents/planner.md",
        "adapters/claude-code/.claude/agents/verifier.md",
        "adapters/claude-code/.claude/agents/worker.md",
        "adapters/claude-code/.claude/commands/retrospective.md",
        "adapters/claude-code/.claude/commands/smoke-test.md",
        "adapters/claude-code/.claude/commands/start-long-task.md",
        "adapters/claude-code/.claude/commands/verify-round.md",
        "adapters/opencode/AGENTS.example.md",
        "adapters/opencode/opencode.json",
        "adapters/opencode/.opencode/agents/explorer.md",
        "adapters/opencode/.opencode/agents/memory-curator.md",
        "adapters/opencode/.opencode/agents/planner.md",
        "adapters/opencode/.opencode/agents/verifier.md",
        "adapters/opencode/.opencode/agents/worker.md",
        "skills/grill-me-preflight/SKILL.md",
        "skills/malts-project-init/SKILL.md",
        "skills/multi-agent-long-task-scheduling/SKILL.md",
        "skills/project-retrospective-growth/SKILL.md",
        "skills/session-handoff/SKILL.md",
        "skills/single-agent-lightweight-growth/SKILL.md",
        "runtime/EN/templates/PROJECT_CONTROL.template.en.md",
        "runtime/EN/templates/PROJECT_HANDOFF.template.en.md",
        "runtime/EN/templates/SUB_AGENT_REPORT.template.en.md",
        "runtime/EN/templates/TASK_CONTRACT.template.en.md",
        "runtime/EN/templates/WORK_TASK_REPORT.template.en.md",
        "runtime/EN/checklists/DELIVERY_CHECKLIST.en.md",
        "runtime/EN/checklists/QUALITY_GATE.en.md",
        "runtime/EN/checklists/MEMORY_WRITE_CHECKLIST.en.md",
        "scripts/Install-MALTS.ps1",
        "tools/agent_system_lint.py",
        "tools/doc_pairs.json",
        "tools/README.md",
    ]
    local_core_required = [
        "README.md",
        "AGENTS.md",
        "skills/grill-me-preflight/SKILL.md",
        "skills/malts-project-init/SKILL.md",
        "skills/multi-agent-long-task-scheduling/SKILL.md",
        "skills/project-retrospective-growth/SKILL.md",
        "skills/session-handoff/SKILL.md",
        "skills/single-agent-lightweight-growth/SKILL.md",
        "output/EN/templates/PROJECT_CONTROL.template.en.md",
        "output/EN/templates/PROJECT_HANDOFF.template.en.md",
        "output/EN/templates/SUB_AGENT_REPORT.template.en.md",
        "output/EN/templates/TASK_CONTRACT.template.en.md",
        "output/EN/templates/WORK_TASK_REPORT.template.en.md",
        "output/EN/checklists/DELIVERY_CHECKLIST.en.md",
        "output/EN/checklists/QUALITY_GATE.en.md",
        "output/EN/checklists/MEMORY_WRITE_CHECKLIST.en.md",
        "output/tools/agent_system_lint.py",
    ]
    required = release_required if (malts_root / "runtime" / "EN").exists() else local_core_required
    for rel in required:
        path = malts_root / rel
        if not path.exists():
            findings.append(Finding("ERROR", f"Missing release file: {rel}"))

    if version:
        version_path = malts_root / "VERSION"
        if version_path.exists() and read_text(version_path).strip() != version:
            findings.append(Finding("ERROR", f"VERSION does not match expected {version}."))

    forbidden = [
        "grill-me-preflight" + ".en.md",
        "runtime/EN/" + "skills",
        "runtime\\EN\\" + "skills",
        "output/EN/" + "skills",
        "output\\EN\\" + "skills",
        "adapters/claude-code/.claude/" + "skills",
        "adapters\\claude-code\\.claude\\" + "skills",
        "0.1.0-" + "private",
        "private release-" + "preparation",
        "private " + "preparation",
        "\u0418\u00b7\u0418\u041f\u0424\u041b\u0420\u0420",
        "\u040e\u044a",
        "\u7ead",
        "\u922b",
        "\ufffd",
    ]
    for path in malts_root.rglob("*"):
        relative_parts = path.relative_to(malts_root).parts
        if ".release-control" in relative_parts:
            continue
        if path.is_file() and (
            path.suffix.lower() in {".md", ".py", ".ps1", ".json", ".txt"}
            or path.name in {".gitignore", "VERSION", "LICENSE"}
        ):
            text = read_text(path)
            for literal in forbidden:
                if literal in text:
                    findings.append(Finding("ERROR", f"Forbidden literal `{literal}` found in {path.relative_to(malts_root)}"))

    gitignore_path = malts_root / ".gitignore"
    if gitignore_path.exists():
        rel_paths = [
            path.relative_to(malts_root).as_posix()
            for path in malts_root.rglob("*")
            if path.is_file() and path != gitignore_path
        ]
        for line in read_text(gitignore_path).splitlines():
            hits = gitignore_matches_public_file(line, rel_paths)
            if hits:
                sample = ", ".join(hits[:5])
                if len(hits) > 5:
                    sample += ", ..."
                findings.append(Finding("ERROR", f".gitignore pattern `{line.strip()}` matches public files: {sample}"))

    return emit(findings)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="MALTS release checks and generators.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    next_parser = subparsers.add_parser("next-task-id")
    next_parser.add_argument("--project-control", type=Path, required=True)

    pc_parser = subparsers.add_parser("check-project-control")
    pc_parser.add_argument("--project-control", type=Path, required=True)

    sync_parser = subparsers.add_parser("check-doc-sync")
    sync_parser.add_argument("--output-root", type=Path, required=True)
    sync_parser.add_argument("--manifest", type=Path)
    sync_parser.add_argument("--require-ch", action="store_true")

    new_parser = subparsers.add_parser("new-project-control")
    new_parser.add_argument("--project", required=True)
    new_parser.add_argument("--goal", required=True)
    new_parser.add_argument("--mode", default="Single-Agent")
    new_parser.add_argument("--round", default="R001")
    new_parser.add_argument("--slug")
    new_parser.add_argument("--out", type=Path)
    new_parser.add_argument("--output-root", type=Path, default=Path("runtime"))
    new_parser.add_argument("--ch-out", type=Path)
    new_parser.add_argument("--with-ch", action="store_true")
    new_parser.add_argument("--no-ch", action="store_true")
    new_parser.add_argument("--stage", default="Initialized")
    new_parser.add_argument("--stage-goal")
    new_parser.add_argument("--exit-condition")
    new_parser.add_argument("--confirmed-exclusions")
    new_parser.add_argument("--open-questions")
    new_parser.add_argument("--acceptance", action="append", default=[])
    new_parser.add_argument("--task", action="append", default=[])
    new_parser.add_argument("--overwrite", action="store_true")
    new_parser.add_argument("--dry-run", action="store_true")
    new_parser.add_argument("--timestamp")
    new_parser.add_argument("--check-doc-sync", action="store_true")

    freshness_parser = subparsers.add_parser("check-semantic-freshness")
    freshness_parser.add_argument("--malts-root", type=Path, required=True)
    freshness_parser.add_argument("--version")

    args = parser.parse_args(argv)
    if args.command == "next-task-id":
        return next_task_id(args.project_control)
    if args.command == "check-project-control":
        return check_project_control(args.project_control)
    if args.command == "check-doc-sync":
        return check_doc_sync(args.output_root, args.manifest, args.require_ch)
    if args.command == "new-project-control":
        return new_project_control(args)
    if args.command == "check-semantic-freshness":
        return check_semantic_freshness(args.malts_root, args.version)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
