# Getting Started With MALTS

This guide explains how to install MALTS for a supported Agent tool and how to use it on a first task. It is written for users who want a practical setup path before reading the full system design.

## 1. What MALTS Adds

MALTS adds a file-backed operating workflow for Agent-assisted coding work. It is intended to reduce failure modes that appear in longer or higher-risk tasks:

| Problem | MALTS mechanism |
|---|---|
| The original goal becomes unclear during a long conversation. | Capture the original goal, current interpretation, completion definition, and acceptance criteria. |
| Work cannot be recovered after a new window, interruption, or context loss. | Record state in `PROJECT_CONTROL.md`, phase results in `WORK_TASK_REPORT.md`, and continuation context in `PROJECT_HANDOFF.md`. |
| An Agent claims completion without enough evidence. | Use delivery and quality checklists, then record verification evidence before delivery. |
| Multi-agent work creates coordination risk. | Require fit assessment, launch review, task contracts, explicit confirmation, dispatch records, and final reconciliation. |
| Useful lessons become uncontrolled permanent rules. | Route lessons through the MALTS Memory Pipeline and memory-write checklist before durable promotion. |

MALTS does not replace a coding Agent, IDE, source control, CI system, package manager, permission model, or human approval process. It supplies operating discipline around those systems.

## 2. Choose A Target Tool

MALTS includes optional adapters for:

| Tool | Installed instruction file | Additional adapter files |
|---|---|---|
| Codex | `AGENTS.md` | Shared skills install from root `skills/` |
| Claude Code | `CLAUDE.md` | Optional `.claude/agents` and `.claude/commands` scaffold; shared skills install from root `skills/` |
| OpenCode | `AGENTS.md` | `opencode.json`, optional `.opencode/agents` scaffold, and shared skills from root `skills/` |

Use one tool first unless there is a specific reason to install all adapters. The `AllIncluded` mode is available for users who intentionally maintain the same MALTS behavior across Codex, Claude Code, and OpenCode.

## 3. Preview The Install

The installer is review-first. A dry run prints the planned writes and does not modify files:

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex
```

Supported values:

```text
Codex
ClaudeCode
OpenCode
AllIncluded
```

For example:

```powershell
.\scripts\Install-MALTS.ps1 -Tool ClaudeCode
.\scripts\Install-MALTS.ps1 -Tool OpenCode
.\scripts\Install-MALTS.ps1 -Tool AllIncluded
```

Review the output before applying. Existing target files are reported as `exists`; new target files are reported as `new`.

## 4. Apply The Install

After reviewing the dry-run plan, apply the selected adapter:

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex -Apply
```

The installer refuses to overwrite existing files unless `-Overwrite` is supplied. Use `-Overwrite` only after reviewing the existing target file and confirming that replacement is intended.

Instruction templates are optional. To install support files without installing the tool instruction template:

```powershell
.\scripts\Install-MALTS.ps1 -Tool ClaudeCode -SkipInstructionTemplate -Apply
```

## 5. Keep Skills And Runtime Documents Available

Installed instruction templates and local skill entries depend on:

```text
skills/
runtime/EN
```

Keep the MALTS repository available to the Agent, or copy the needed shared skills, templates, and checklists into locations that the Agent can read. Root `skills/` is the canonical skill source. `runtime/EN/templates` and `runtime/EN/checklists` remain the template and checklist source. Chinese documents, when present, are user-facing public translations and are not the default Agent runtime source.

## 6. Use MALTS On A First Task

For a small task, do not create MALTS files. The expected behavior is:

1. The Agent answers or plans before state-changing execution.
2. The Agent verifies relevant facts before claiming completion.
3. The Agent stays single-agent unless the task grows.

For a non-trivial task, ask the Agent to use MALTS. A concise first request can be:

```text
Use MALTS for this task. Create or reuse PROJECT_CONTROL.md, define acceptance criteria, and verify before delivery.
```

The Agent should then:

1. Capture the original goal.
2. State assumptions and exclusions.
3. Define completion and acceptance criteria.
4. Create a task queue.
5. Record decisions, file ownership, risks, and verification evidence.
6. Write or append `WORK_TASK_REPORT.md` after a phase or final delivery.
7. Update `PROJECT_HANDOFF.md` if another Agent or window needs to continue.

## 7. Use Grill-Me Preflight When Requirements Are Unclear

For non-trivial starts, MALTS includes Grill-Me Preflight:

```text
skills/grill-me-preflight/SKILL.md
```

The preflight is a clarification gate. It asks decision-changing questions before implementation so that hidden assumptions, goal boundaries, key tradeoffs, and acceptance criteria are explicit. It is not a sub-agent dispatch and does not require the multi-agent confirmation phrase.

Use it for:

- migrations
- protocol changes
- multi-file refactors
- ambiguous product or architecture work
- tasks where success criteria are not yet measurable

Skip it for small tasks where the goal and verification path are already clear.

## 8. Use Multi-Agent Mode Only When It Adds Operational Value

Multi-agent mode is optional. It is appropriate only when delegation improves at least one of these:

- independent exploration
- independent verification
- reduced context pressure
- safe parallel work on non-conflicting files
- recovery for a multi-phase task

Before any real sub-agent dispatch, the Agent must show a launch review containing the overall goal, total plan, roles, model policy when relevant, each task, and each short plan. Dispatch must wait until the user explicitly replies:

```text
确认运行
```

Without that confirmation, MALTS remains single-agent.

## 9. Verify The Setup

Useful checks:

```powershell
python tools\agent_system_lint.py check-semantic-freshness --malts-root . --version 0.1.0
python tools\agent_system_lint.py check-doc-sync --output-root runtime
.\scripts\Install-MALTS.ps1 -Tool Codex
```

The first two commands check release metadata and documentation synchronization. The install command without `-Apply` verifies that installation planning still works without writing files.

## 10. Common Starting Points

| Situation | Recommended MALTS entry |
|---|---|
| First-time installation | `docs/INSTALL.md` and this guide |
| Understanding the system model | `docs/SYSTEM_OVERVIEW.md` |
| Detailed architecture and invariants | `docs/CORE_DESIGN.md` |
| Handoff and continuation behavior | `docs/HANDOFF.md` |
| Agent-assisted installation policy | `docs/AGENT_INSTALL.md` |
| Security and release hygiene | `docs/SECURITY.md` |


