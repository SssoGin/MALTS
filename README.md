# MALTS

**Multi-Agent Long-Task Scheduling and Growth System**

Languages: [English](README.md) | [简体中文](README.zh-CN.md)

MALTS is a file-based workflow system for AI coding agents. It records goals, plans, task ownership, verification, handoffs, and reviewed lessons in ordinary project files so long-running work stays recoverable, inspectable, and easier to continue safely.

MALTS is relevant for migrations, multi-file changes, long investigations, release preparation, protocol or documentation work, and other tasks where a lost decision or an unverified claim of completion would create avoidable risk.

MALTS is single-agent first. The main Agent remains the normal executor; multi-agent work is an optional, explicitly reviewed division of work rather than something that starts merely because MALTS is installed.

## Start Here

| Need | Read |
|---|---|
| Install MALTS and run a first task | [Getting Started](docs/GETTING_STARTED.md) |
| Understand what MALTS does and when to use it | [System Overview](docs/SYSTEM_OVERVIEW.md) |
| Review the full operating model and boundaries | [Core Design](docs/CORE_DESIGN.md) |
| Install or update a specific Agent tool | [Install](docs/INSTALL.md) and [Update](docs/UPDATE.md) |
| Let an Agent assist with installation safely | [Agent Install](docs/AGENT_INSTALL.md) |
| Use the optional offline archive | [Release Artifact](docs/RELEASE_ARTIFACT.md) |

## What Problem It Solves

Long Agent tasks fail differently from short prompts. Context can be compressed, goals can drift, an incomplete result can be mistaken for a completed one, several work lanes can collide, and useful lessons can be either lost or promoted too broadly.

MALTS responds by externalizing important task state, defining completion and verification criteria, keeping a recoverable handoff, requiring a launch review before real sub-agent dispatch, and filtering reusable lessons before they become durable guidance.

## What It Provides

- Long-task planning and recovery through `PROJECT_CONTROL.md`
- Phase or final evidence through `WORK_TASK_REPORT.md`
- Agent-facing continuation through `PROJECT_HANDOFF.md`
- Explicit Phase and Session controls for bounded long-project work
- Event-triggered, read-only Plan Recheck with Phase-owned plan revision and SHA-256 binding
- Grill-Me Preflight for assumptions, boundaries, tradeoffs, and acceptance criteria
- Optional multi-agent launch review, task contracts, and responsibility boundaries
- Governed Codex peer-task routing when native sub-agent dispatch cannot satisfy an approved hard model or effort contract
- Delivery, quality, and memory-write checklists
- English and Simplified Chinese runtime templates
- Native `malts-*` Skill bridges for Codex, Claude Code, and OpenCode
- Review-first install, update, recovery, rollback, and residue handling
- Startup discovery cross-checked against the installed runtime state
- Stable and preview runtime identities, read-only doctor diagnostics, bounded audit retention, and safe legacy migration
- Migration handling for known MALTS `v0.1.0` through `v0.1.9` layouts

## Core And Optional Capabilities

| Capability | Default | Purpose |
|---|---|---|
| Single-agent execution | On | Keep small and clear work low-overhead. |
| `PROJECT_CONTROL.md` | Used for non-trivial or recovery-sensitive work | Preserve goal, queue, decisions, risks, and verification state. |
| `WORK_TASK_REPORT.md` | Used after MALTS phases or final delivery | Record result, evidence, remaining risk, and next steps. |
| `PROJECT_HANDOFF.md` | Used for continuation or context-risk handoff | Give a future Agent a restart-safe current state. |
| Grill-Me Preflight | Offered for unclear or non-trivial work | Surface assumptions and acceptance criteria before implementation. |
| Multi-agent scheduling | Off | Add controlled delegation only when it has clear value. |
| Plan Recheck | Event-triggered for active S3/S4 plans | Detect plan, scope, Session, and launch-review drift before gated actions. |
| Growth review | Available | Filter reviewed lessons before durable promotion. |
| Bilingual documentation | Available | Provide English and Simplified Chinese references without duplicating project state. |

## Activation And Artifacts

MALTS does not create permanent control files for every short task. For small work, stay single-agent and use the normal project instructions.

When a task needs recoverable long-task mode, create or reuse `PROJECT_CONTROL.md` in the project root. Each MALTS phase or final delivery should write or update `WORK_TASK_REPORT.md`. Use `PROJECT_HANDOFF.md` when a future Agent needs the recorded state. Narrative content may use the project's working language; translated mirror files are optional and explicit.

| File | Default role |
|---|---|
| `PROJECT_CONTROL.md` | Canonical project state, task queue, decisions, risks, and verification status. |
| `WORK_TASK_REPORT.md` | Canonical phase or final report with direct evidence. |
| `PROJECT_HANDOFF.md` | Canonical continuation and recovery context. |

## Repository Layout

```text
skills/                 Canonical MALTS Skill packages
runtime/EN/             English templates and checklists
runtime/CH/             Simplified Chinese templates and checklists
adapters/               Codex, Claude Code, and OpenCode adapter material
scripts/                User installation, update, lifecycle, and ZIP-verification entry points
tools/                  Runtime controllers, schemas, and user operation tools
docs/                   User guides, design references, and security guidance
VERSION                 Current package version
LICENSE                 MIT license
THIRD_PARTY_NOTICES.md  Required attribution notices
```

## Documentation Map

- [Getting Started](docs/GETTING_STARTED.md): installation and first-use path.
- [Install](docs/INSTALL.md): installation commands and roots.
- [Update](docs/UPDATE.md): review-first replacement of an existing installation.
- [Lifecycle](docs/LIFECYCLE.md): runtime versions, recovery, rollback, doctor diagnostics, and cleanup.
- [Usage](docs/USAGE.md): normal tasks, long tasks, multi-agent work, growth, and handoff.
- [System Overview](docs/SYSTEM_OVERVIEW.md): public explanation of goals, features, and boundaries.
- [Core Design](docs/CORE_DESIGN.md): detailed operating model and invariants.
- [Agent Install](docs/AGENT_INSTALL.md): authorization and source-selection rules for Agents.
- [Release Artifact](docs/RELEASE_ARTIFACT.md): optional single-ZIP offline delivery.
- [Security](docs/SECURITY.md): source and package verification plus privacy boundaries.
- [Bilingual Docs](docs/BILINGUAL_DOCS.md): language and navigation policy.

## Acknowledgements

MALTS includes public-safe adaptations of coding-agent behavior patterns inspired by:

- [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills), for concise coding-agent behavior guardrails.
- [mattpocock/skills](https://github.com/mattpocock/skills), especially the idea of a pre-implementation grilling workflow.

These projects are not dependencies of MALTS and do not endorse this repository. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Install Preview

Installation is review-first. The installer writes a plan first and does not change files until you review it and supply its exact plan hash with `-Apply`.

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex
.\scripts\Install-MALTS.ps1 -Tool Codex -Apply
.\scripts\Install-MALTS.ps1 -Tool AllIncluded -InstructionMode Skip
.\scripts\Install-MALTS.review.cmd -Tool AllIncluded
```

Supported tools:

```text
Codex
ClaudeCode
OpenCode
AllIncluded
```

If Windows PowerShell blocks script execution, run the same command with a process-local policy override:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool Codex
```

See [docs/INSTALL.md](docs/INSTALL.md) and [docs/AGENT_INSTALL.md](docs/AGENT_INSTALL.md).

## Update Preview

Installed users can update from a current repository checkout without manually downloading a new archive. The update script is also review-first: it prints the plan and does not pull or write files unless `-Apply` is provided.

```powershell
.\scripts\Update-MALTS.ps1 -Tool Codex
.\scripts\Update-MALTS.ps1 -Tool Codex -Apply
.\scripts\Update-MALTS.ps1 -Tool AllIncluded -Strategy MergeSafe
.\scripts\Update-MALTS.review.cmd -Tool Codex
```

`MergeSafe` defaults to `InstructionMode ManagedMerge`: it updates the MALTS-managed instruction block while preserving surrounding user rules. Use `InstructionMode Skip` to leave the instruction file untouched.

## Documentation Language

The repository defaults to English source documents. Simplified Chinese documents live in `README.zh-CN.md` and `docs/zh-CN/`; localized runtime references live under `runtime/CH/`. Runtime project artifacts stay single and canonical by default. See [Bilingual Docs](docs/BILINGUAL_DOCS.md).

## Version

Current release version:

```text
1.1.0
```

## License

MIT License. See [LICENSE](LICENSE).
