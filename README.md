# MALTS

**Multi-Agent Long-Task Scheduling and Growth System**

Languages: [English](README.md) | [简体中文](README.zh-CN.md)

A file-based workflow system that helps AI coding agents handle long-running tasks, coordinate agent collaboration, and turn reviewed experience into reusable rules.

MALTS is a Multi-Agent Long-Task Scheduling and Growth System for AI coding agents. It records goals, plans, task ownership, verification, handoffs, and retrospectives in project files so long-running work stays recoverable, verifiable, collaborative, and able to convert reviewed lessons into reusable guidance.

MALTS is relevant for migrations, multi-file changes, long bug investigations, release preparation, protocol/documentation updates, and other coding tasks where losing context or skipping verification would create avoidable risk.

MALTS is a portable workflow system made of canonical skills, templates, checklists, adapters, scripts, and public maintenance docs.

MALTS is single-agent first. That means that after MALTS is enabled, the main controller remains the default executor. Multi-agent work is a controlled division-of-work mechanism enabled only when needed, and every real sub-agent dispatch requires an explicit launch review first.

## Start Here

| Need | Read |
|---|---|
| Install MALTS and run a first task | [Getting Started](docs/GETTING_STARTED.md) |
| Understand what MALTS does and when to use it | [System Overview](docs/SYSTEM_OVERVIEW.md) |
| Review the full operating model and design boundaries | [Core Design](docs/CORE_DESIGN.md) |
| Install a specific Agent tool adapter | [Install](docs/INSTALL.md) |
| Configure Agent-assisted installation safely | [Agent Install](docs/AGENT_INSTALL.md) |

## What Problem It Solves

MALTS addresses operating risks that appear when coding-agent work becomes longer than a short, self-contained exchange. The main risks are goal drift, loss of recoverable state, weak completion evidence, unsafe multi-agent coordination, and uncontrolled growth of durable rules or memory.

MALTS responds by externalizing important state into files, defining completion criteria, recording verification evidence, requiring explicit launch review before sub-agent dispatch, and filtering reusable lessons before promotion into durable guidance.

## What It Provides

- Long-task planning and recovery through `PROJECT_CONTROL.md`
- Optional multi-agent launch review and role-based task dispatch
- Verification checklists for delivery, memory writes, and quality gates
- Agent-facing project handoffs through `PROJECT_HANDOFF.md`
- Phase and final delivery reporting through `WORK_TASK_REPORT.md`
- Growth review and durable candidate handling through the MALTS Memory Pipeline
- Canonical `SKILL.md` packages under `skills/`, installed to each supported Agent tool's local skill directory
- Optional bilingual documentation synchronization
- Optional adapters for Codex, Claude Code, and OpenCode
- Lightweight linting and project-control generation tools

## Core And Optional Capabilities

| Capability | Default | Purpose |
|---|---|---|
| Single-agent execution | On | Keep small and clear tasks low-overhead. |
| `PROJECT_CONTROL.md` | Created when MALTS is enabled or recovery is needed | Preserve goal, queue, decisions, risks, ownership, and verification state. |
| `WORK_TASK_REPORT.md` | Used after MALTS phases or final delivery | Report result, checks, risks, and next steps. |
| `PROJECT_HANDOFF.md` | Used for continuation or context-risk handoff | Provide Agent-facing recovery context. |
| Grill-Me Preflight | Offered for non-trivial or unclear starts | Expose assumptions, goal boundaries, tradeoffs, and acceptance criteria before implementation. |
| Multi-agent scheduling | Off | Add controlled delegation only when exploration, verification, parallelism, or recovery value justifies it. |
| Memory Pipeline | Available | Filter reusable lessons before promoting them into durable rules or memory. |
| Bilingual documentation sync | Off | Maintain optional Chinese review mirrors when needed. |

## Activation And Artifacts

MALTS files are not created by default for every task. For small work, stay single-agent and use the normal project instructions.

When MALTS is enabled or a task grows into recoverable long-task mode, create or reuse `PROJECT_CONTROL.md` in the project root. Each MALTS phase or final delivery should write or append `WORK_TASK_REPORT.md`. Use `PROJECT_HANDOFF.md` when a future Agent needs to continue from the recorded state.

| File | Default Role |
|---|---|
| `PROJECT_CONTROL.md` | Agent-facing project state and task queue |
| `WORK_TASK_REPORT.md` | User-facing phase/final report, usually in the user's or project's language |
| `PROJECT_HANDOFF.md` | Agent-facing continuation and recovery source |

## Repository Layout

```text
skills/                Canonical MALTS SKILL.md packages
runtime/EN/templates/    Project control, task, report, and handoff templates
runtime/EN/checklists/   Delivery, quality, and memory-write checks
adapters/                Optional Codex, Claude Code, and OpenCode adapter files
tools/                   Lightweight MALTS validation utilities
scripts/                 Safe installation helper scripts
docs/                    Design, install, usage, handoff, security, and maintenance docs
```

## Documentation Map

- [Getting Started](docs/GETTING_STARTED.md): practical installation and first-use path.
- [System Overview](docs/SYSTEM_OVERVIEW.md): public explanation of goals, features, optional capabilities, and boundaries.
- [Usage](docs/USAGE.md): concise operating guide for normal tasks, long tasks, multi-agent work, growth, and handoff.
- [Core Design](docs/CORE_DESIGN.md): detailed system model, invariants, task sizing, and protocol boundaries.
- [Install](docs/INSTALL.md): installation command reference.
- [Agent Install](docs/AGENT_INSTALL.md): rules for Agent-assisted installation.
- [Handoff](docs/HANDOFF.md): handoff file behavior and release boundary.
- [Security](docs/SECURITY.md): release hygiene and secret-handling rules.
- [Maintainer Guide](docs/MAINTAINER_GUIDE.md): public-safe maintenance, CI, versioning, and handoff boundaries.

## Acknowledgements

MALTS includes public-safe adaptations of agent behavior patterns inspired by:

- [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills), for concise coding-agent behavior guardrails.
- [mattpocock/skills](https://github.com/mattpocock/skills), especially the idea of a pre-implementation grilling workflow.

These projects are not dependencies of MALTS and do not endorse this repository. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Install Preview

Installation is intentionally review-first. The install script defaults to dry-run and does not write files unless `-Apply` is provided.

Tool instruction templates such as `AGENTS.md` and `CLAUDE.md` are optional MALTS enhancements. They help the Agent remember MALTS task mode, Grill-Me Preflight, project control, handoff, and verification rules, but they should be reviewed and merged with any existing user or project instructions instead of blindly replacing them.

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex
.\scripts\Install-MALTS.ps1 -Tool Codex -Apply
.\scripts\Install-MALTS.ps1 -Tool ClaudeCode -SkipInstructionTemplate
```

If Windows PowerShell blocks script execution, run the same command with a process-local policy override:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool Codex
```

Supported tools:

```text
Codex
ClaudeCode
OpenCode
AllIncluded
```

See [docs/INSTALL.md](docs/INSTALL.md) and [docs/AGENT_INSTALL.md](docs/AGENT_INSTALL.md).

## Documentation Language

The public repository defaults to English source documents. A Simplified Chinese public entry is available at [README.zh-CN.md](README.zh-CN.md), with translated public docs under `docs/zh-CN/`. English docs and root `skills/` remain the source of truth for Agent execution. See [docs/BILINGUAL_DOCS.md](docs/BILINGUAL_DOCS.md).

## Version

Current release version:

```text
0.1.2
```

## License

MIT License. See [LICENSE](LICENSE).

