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

RUNTIME_DOC_PAIRS = [
    {
        "en": "EN/templates/PROJECT_CONTROL.template.en.md",
        "ch": "CH/templates/PROJECT_CONTROL.template.zh-CN.md",
    },
    {
        "en": "EN/templates/WORK_TASK_REPORT.template.en.md",
        "ch": "CH/templates/WORK_TASK_REPORT.template.zh-CN.md",
    },
    {
        "en": "EN/templates/PROJECT_HANDOFF.template.en.md",
        "ch": "CH/templates/PROJECT_HANDOFF.template.zh-CN.md",
    },
    {
        "en": "EN/templates/TASK_CONTRACT.template.en.md",
        "ch": "CH/templates/TASK_CONTRACT.template.zh-CN.md",
    },
    {
        "en": "EN/templates/SUB_AGENT_REPORT.template.en.md",
        "ch": "CH/templates/SUB_AGENT_REPORT.template.zh-CN.md",
    },
    {
        "en": "EN/checklists/DELIVERY_CHECKLIST.en.md",
        "ch": "CH/checklists/DELIVERY_CHECKLIST.zh-CN.md",
    },
    {
        "en": "EN/checklists/QUALITY_GATE.en.md",
        "ch": "CH/checklists/QUALITY_GATE.zh-CN.md",
    },
    {
        "en": "EN/checklists/MEMORY_WRITE_CHECKLIST.en.md",
        "ch": "CH/checklists/MEMORY_WRITE_CHECKLIST.zh-CN.md",
    },
]

ADAPTER_REQUIRED = {
    "codex": [
        "adapters/codex/README.md",
        "adapters/codex/README.zh-CN.md",
        "adapters/codex/AGENTS.example.md",
        "adapters/codex/.codex/config.toml",
        "adapters/codex/.codex/agents/planner.toml",
        "adapters/codex/.codex/agents/explorer.toml",
        "adapters/codex/.codex/agents/worker.toml",
        "adapters/codex/.codex/agents/verifier.toml",
        "adapters/codex/.codex/agents/memory-curator.toml",
        "adapters/codex/workflows/start-long-task.md",
        "adapters/codex/workflows/verify-round.md",
        "adapters/codex/workflows/retrospective.md",
        "adapters/codex/workflows/smoke-test.md",
    ],
    "claude-code": [
        "adapters/claude-code/README.md",
        "adapters/claude-code/README.zh-CN.md",
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
    ],
    "opencode": [
        "adapters/opencode/README.md",
        "adapters/opencode/README.zh-CN.md",
        "adapters/opencode/AGENTS.example.md",
        "adapters/opencode/opencode.json",
        "adapters/opencode/.opencode/agents/explorer.md",
        "adapters/opencode/.opencode/agents/memory-curator.md",
        "adapters/opencode/.opencode/agents/planner.md",
        "adapters/opencode/.opencode/agents/verifier.md",
        "adapters/opencode/.opencode/agents/worker.md",
    ],
}

ADAPTER_REQUIRED_TOKENS = [
    "PROJECT_CONTROL.md",
    "WORK_TASK_REPORT.md",
    "确认运行",
    "unattended",
    "UTF-8",
    "Default write scope",
    "source project",
    "nearest applicable instruction",
]

PRIVATE_PUBLIC_LITERALS = [
    "C:\\Users\\" + "Gin",
    "D:\\" + "Agent",
    "D:\\" + "Code",
    "C:/Users/" + "Gin",
    "D:/" + "Agent",
    "D:/" + "Code",
    "Agent" + "Output",
    "Agent" + "Workspace",
    "Codex" + "Workspace",
    "Multi-Agent-System-" + "Core",
    ".agent-" + "system",
    "Baidu" + "Netdisk",
    "D:\\" + "Temp",
    "D:/" + "Temp",
]

SECRET_VALUE_PATTERNS = [
    re.compile(r"(?i)\b(openai|anthropic|github|gitlab|azure|aws|secret|token|api[_-]?key|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    re.compile(r"(?i)\bAuthorization:\s*Bearer\s+[A-Za-z0-9_./+=-]{20,}"),
]

SECRET_DOC_ALLOWLIST = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GITHUB_TOKEN",
    "api_key",
    "token",
    "secret",
    "password",
    "Authorization",
    "Bearer",
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
        return emit([Finding("ERROR", f"Document root not found: {output_root}")])

    pairs = load_doc_pairs(manifest)
    if not pairs and (output_root / "EN").exists():
        pairs = RUNTIME_DOC_PAIRS
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


def check_adapter_parity(root: Path) -> int:
    findings: list[Finding] = []
    for adapter, required_paths in ADAPTER_REQUIRED.items():
        for rel in required_paths:
            if not (root / rel).exists():
                findings.append(Finding("ERROR", f"Missing {adapter} adapter file: {rel}"))

    for adapter in ADAPTER_REQUIRED:
        text_parts: list[str] = []
        adapter_root = root / "adapters" / adapter
        if not adapter_root.exists():
            continue
        for path in adapter_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".md", ".toml", ".json"}:
                text_parts.append(read_text(path))
        adapter_text = "\n".join(text_parts)
        for token in ADAPTER_REQUIRED_TOKENS:
            if token not in adapter_text:
                findings.append(Finding("ERROR", f"{adapter} adapter missing required token: {token}"))

    forbidden_codex = [
        "adapters/codex/.codex/commands",
        "adapters/codex/.claude",
        "adapters/codex/.opencode",
    ]
    for rel in forbidden_codex:
        if (root / rel).exists():
            findings.append(Finding("ERROR", f"Codex adapter contains unsupported or cross-tool scaffold: {rel}"))

    return emit(findings)


def check_encoding(root: Path, require_ch_bom: bool) -> int:
    findings: list[Finding] = []
    text_suffixes = {".md", ".txt", ".py", ".ps1", ".json", ".toml", ".cmd", ".yml", ".yaml"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.relative_to(root).parts:
            continue
        if path.suffix.lower() not in text_suffixes and path.name not in {
            ".gitignore",
            ".gitattributes",
            ".editorconfig",
            "VERSION",
            "LICENSE",
        }:
            continue
        try:
            data = path.read_bytes()
            data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            findings.append(Finding("ERROR", f"File is not valid UTF-8: {path.relative_to(root)} ({exc})"))
            continue
        if require_ch_bom:
            rel = path.relative_to(root).as_posix()
            is_ch_surface = (
                "/zh-CN/" in f"/{rel}"
                or "/runtime/CH/" in f"/{rel}"
                or rel.endswith(".zh-CN.md")
                or any("\u4e00" <= char <= "\u9fff" for char in path.name)
            )
            if is_ch_surface and not data.startswith(b"\xef\xbb\xbf"):
                findings.append(Finding("ERROR", f"Chinese-facing file should use UTF-8 with BOM: {rel}"))
    return emit(findings)


def check_public_safety(root: Path) -> int:
    findings: list[Finding] = []
    text_suffixes = {".md", ".txt", ".py", ".ps1", ".json", ".toml", ".cmd", ".yml", ".yaml"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(root).parts
        if ".git" in relative_parts:
            continue
        if path.suffix.lower() not in text_suffixes and path.name not in {
            ".gitignore",
            ".gitattributes",
            ".editorconfig",
            "VERSION",
            "LICENSE",
        }:
            continue
        text = read_text(path)
        for literal in PRIVATE_PUBLIC_LITERALS:
            if literal in text:
                findings.append(Finding("ERROR", f"Machine-specific literal `{literal}` found in {path.relative_to(root)}"))
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern in SECRET_VALUE_PATTERNS:
                if not pattern.search(line):
                    continue
                if any(token in line for token in SECRET_DOC_ALLOWLIST) and not re.search(r"[:=]\s*['\"]?[A-Za-z0-9_./+=-]{20,}", line):
                    continue
                findings.append(
                    Finding(
                        "ERROR",
                        f"Potential secret value found in {path.relative_to(root)}:{line_number}",
                    )
                )
    return emit(findings)


def check_install_layout(install_root: Path, tool: str | None) -> int:
    findings: list[Finding] = []
    required = [
        "MALTS_BOOT.md",
        "malts/README.md",
        "malts/README.zh-CN.md",
        "malts/VERSION",
        "malts/skills/malts-project-init/SKILL.md",
        "malts/skills/multi-agent-long-task-scheduling/SKILL.md",
        "malts/runtime/EN/templates/PROJECT_CONTROL.template.en.md",
        "malts/runtime/EN/templates/WORK_TASK_REPORT.template.en.md",
        "malts/runtime/EN/checklists/QUALITY_GATE.en.md",
        "malts/runtime/EN/checklists/DELIVERY_CHECKLIST.en.md",
        "malts/runtime/CH/templates/WORK_TASK_REPORT.template.zh-CN.md",
        "malts/runtime/CH/checklists/QUALITY_GATE.zh-CN.md",
        "malts/tools/agent_system_lint.py",
        "malts/adapters/codex/AGENTS.example.md",
        "malts/adapters/claude-code/CLAUDE.example.md",
        "malts/adapters/opencode/AGENTS.example.md",
    ]

    if tool == "Codex":
        required += [
            "AGENTS.md",
            ".codex/config.toml",
            ".codex/agents/planner.toml",
            "skills/malts-project-init/SKILL.md",
        ]
    elif tool == "ClaudeCode":
        required += [
            "CLAUDE.md",
            "agents/planner.md",
            "commands/start-long-task.md",
            "skills/malts-project-init/SKILL.md",
        ]
    elif tool == "OpenCode":
        required += [
            "AGENTS.md",
            "opencode.json",
            ".opencode/agents/planner.md",
            "skills/malts-project-init/SKILL.md",
        ]

    for rel in required:
        if not (install_root / rel).exists():
            findings.append(Finding("ERROR", f"Installed layout missing: {rel}"))

    boot_path = install_root / "MALTS_BOOT.md"
    if boot_path.exists():
        boot_text = read_text(boot_path)
        expected_root = str(install_root / "malts")
        if "MALTS_ROOT:" not in boot_text:
            findings.append(Finding("ERROR", "MALTS_BOOT.md does not declare MALTS_ROOT."))
        if expected_root not in boot_text:
            findings.append(Finding("ERROR", f"MALTS_BOOT.md does not point at installed runtime root: {expected_root}"))

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
    is_local_superset = (malts_root / "AGENTS.md").exists() and (malts_root / "Handoff").exists()
    local_private_roots = {".release-control", "Handoff", ".md"}
    release_required = [
        ".editorconfig",
        ".gitattributes",
        ".gitignore",
        "README.md",
        "README.zh-CN.md",
        "VERSION",
        "CHANGELOG.md",
        "LICENSE",
        "docs/CORE_DESIGN.md",
        "docs/BILINGUAL_DOCS.md",
        "docs/INSTALL.md",
        "docs/UPDATE.md",
        "docs/zh-CN/CORE_DESIGN.md",
        "docs/zh-CN/BILINGUAL_DOCS.md",
        "docs/zh-CN/INSTALL.md",
        "docs/zh-CN/UPDATE.md",
        "adapters/codex/AGENTS.example.md",
        "adapters/codex/README.zh-CN.md",
        "adapters/codex/.codex/config.toml",
        "adapters/codex/.codex/agents/explorer.toml",
        "adapters/codex/.codex/agents/memory-curator.toml",
        "adapters/codex/.codex/agents/planner.toml",
        "adapters/codex/.codex/agents/verifier.toml",
        "adapters/codex/.codex/agents/worker.toml",
        "adapters/codex/workflows/retrospective.md",
        "adapters/codex/workflows/smoke-test.md",
        "adapters/codex/workflows/start-long-task.md",
        "adapters/codex/workflows/verify-round.md",
        "adapters/claude-code/CLAUDE.example.md",
        "adapters/claude-code/README.zh-CN.md",
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
        "adapters/opencode/README.zh-CN.md",
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
        "runtime/CH/templates/PROJECT_CONTROL.template.zh-CN.md",
        "runtime/CH/templates/PROJECT_HANDOFF.template.zh-CN.md",
        "runtime/CH/templates/SUB_AGENT_REPORT.template.zh-CN.md",
        "runtime/CH/templates/TASK_CONTRACT.template.zh-CN.md",
        "runtime/CH/templates/WORK_TASK_REPORT.template.zh-CN.md",
        "runtime/CH/checklists/DELIVERY_CHECKLIST.zh-CN.md",
        "runtime/CH/checklists/QUALITY_GATE.zh-CN.md",
        "runtime/CH/checklists/MEMORY_WRITE_CHECKLIST.zh-CN.md",
        "scripts/Install-MALTS.ps1",
        "scripts/Install-MALTS.review.cmd",
        "scripts/Test-MALTSInstall.ps1",
        "scripts/Update-MALTS.ps1",
        "scripts/Update-MALTS.review.cmd",
        "tools/agent_system_lint.py",
        "tools/doc_pairs.json",
        "tools/README.md",
    ]
    for rel in release_required:
        path = malts_root / rel
        if not path.exists():
            findings.append(Finding("ERROR", f"Missing release file: {rel}"))

    for pair in RUNTIME_DOC_PAIRS:
        en_path = malts_root / "runtime" / pair["en"]
        ch_path = malts_root / "runtime" / pair["ch"]
        if not en_path.exists():
            findings.append(Finding("ERROR", f"Missing runtime EN pair member: runtime/{pair['en']}"))
        if not ch_path.exists():
            findings.append(Finding("ERROR", f"Missing runtime CH pair member: runtime/{pair['ch']}"))

    if version:
        version_path = malts_root / "VERSION"
        if version_path.exists() and read_text(version_path).strip() != version:
            findings.append(Finding("ERROR", f"VERSION does not match expected {version}."))

    semantic_tokens = {
        "skills/malts-project-init/SKILL.md": [
            "Default write scope",
            "Source project boundary rule",
            "Simplified Chinese or bilingual form",
            "nearest applicable target-path instructions",
            "Verified read-only facts / checks",
        ],
        "adapters/codex/AGENTS.example.md": [
            "Project And Source Boundaries",
            "Default write scope",
            "source project",
            "nearest applicable instruction",
            "Simplified Chinese",
        ],
        "adapters/claude-code/CLAUDE.example.md": [
            "Project And Source Boundaries",
            "Default write scope",
            "source project",
            "nearest applicable instruction",
            "Simplified Chinese",
        ],
        "adapters/opencode/AGENTS.example.md": [
            "Project And Source Boundaries",
            "Default write scope",
            "source project",
            "nearest applicable instruction",
            "Simplified Chinese",
        ],
        "scripts/Update-MALTS.ps1": [
            "MergeSafe",
            "Overwrite",
            "Already up to date",
            "AllowDirty",
        ],
        "scripts/Test-MALTSInstall.ps1": [
            "check-install-layout",
            "MALTS-install-smoke",
        ],
    }
    for rel, tokens in semantic_tokens.items():
        path = malts_root / rel
        if path.exists():
            text = read_text(path)
            for token in tokens:
                if token not in text:
                    findings.append(Finding("ERROR", f"Missing semantic token `{token}` in {rel}"))

    forbidden = [
        "grill-me-preflight" + ".en.md",
        "runtime/EN/" + "skills",
        "runtime\\EN\\" + "skills",
        "out" + "put/EN/" + "skills",
        "out" + "put\\EN\\" + "skills",
        "out" + "put/EN/" + "templates",
        "out" + "put\\EN\\" + "templates",
        "out" + "put/EN/" + "checklists",
        "out" + "put\\EN\\" + "checklists",
        "out" + "put/" + "tools",
        "out" + "put\\" + "tools",
        "adapters/claude-code/.claude/" + "skills",
        "adapters\\claude-code\\.claude\\" + "skills",
        "0.1.0-" + "pri" + "vate",
        "pri" + "vate release-" + "preparation",
        "pri" + "vate " + "preparation",
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
        rel_paths = []
        for path in malts_root.rglob("*"):
            if not path.is_file() or path == gitignore_path:
                continue
            relative = path.relative_to(malts_root)
            if is_local_superset and relative.parts and relative.parts[0] in local_private_roots:
                continue
            rel_paths.append(relative.as_posix())
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
    sync_parser.add_argument("--output-root", type=Path, required=True, help="Document root. Use runtime for runtime EN/CH pairs, or . with a manifest for public docs.")
    sync_parser.add_argument("--manifest", type=Path)
    sync_parser.add_argument("--require-ch", action="store_true")

    adapter_parser = subparsers.add_parser("check-adapter-parity")
    adapter_parser.add_argument("--malts-root", type=Path, required=True)

    encoding_parser = subparsers.add_parser("check-encoding")
    encoding_parser.add_argument("--malts-root", type=Path, required=True)
    encoding_parser.add_argument("--require-ch-bom", action="store_true")

    safety_parser = subparsers.add_parser("check-public-safety")
    safety_parser.add_argument("--malts-root", type=Path, required=True)

    install_layout_parser = subparsers.add_parser("check-install-layout")
    install_layout_parser.add_argument("--install-root", type=Path, required=True)
    install_layout_parser.add_argument("--tool", choices=["Codex", "ClaudeCode", "OpenCode"])

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
    if args.command == "check-adapter-parity":
        return check_adapter_parity(args.malts_root)
    if args.command == "check-encoding":
        return check_encoding(args.malts_root, args.require_ch_bom)
    if args.command == "check-public-safety":
        return check_public_safety(args.malts_root)
    if args.command == "check-install-layout":
        return check_install_layout(args.install_root, args.tool)
    if args.command == "new-project-control":
        return new_project_control(args)
    if args.command == "check-semantic-freshness":
        return check_semantic_freshness(args.malts_root, args.version)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
