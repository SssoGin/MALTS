# MALTS

**Multi-Agent Long-Task Scheduling and Growth System**

Languages: [English](README.md) | [简体中文](README.zh-CN.md)

MALTS is a file-based operating model for AI-assisted project work that needs continuity, explicit decisions, or controlled delegation. It records the working objective, verified state, ownership, acceptance evidence, and recovery context in ordinary project files so work can continue safely across sessions, phases, and Agents.

MALTS complements normal project instructions; it does not replace them. A contained task with a clear outcome should remain lightweight. MALTS becomes useful when interruption, scope change, verification, handoff, or coordination would otherwise leave important work state implicit.

## Getting Started and Documentation

Use the following entry points according to the question you need to answer.

| Goal | Start with |
|---|---|
| Evaluate whether MALTS fits the project | [System Overview](docs/SYSTEM_OVERVIEW.md) |
| Install MALTS and complete a first task | [Getting Started](docs/GETTING_STARTED.md) |
| Use an initialized workspace or select a workflow | [Usage](docs/USAGE.md) |
| Review workspace recovery, reorganization, or lifecycle operations | [Lifecycle](docs/LIFECYCLE.md) |
| Review concurrency, delegation, and safety invariants | [Core Design](docs/CORE_DESIGN.md) |
| Install or update a supported Agent tool | [Install](docs/INSTALL.md) and [Update](docs/UPDATE.md) |

## What Problem It Solves

Long Agent tasks fail differently from short prompts. Context can be compressed, goals can drift, incomplete work can be mistaken for completion, parallel work can collide, and useful lessons can be either lost or promoted too broadly.

MALTS externalizes the task state that needs to survive these risks. It separates canonical control from derived reports, requires evidence before completion claims, records a recoverable continuation path, and requires a launch review before real delegated work begins.

## Core MALTS Workflows

MALTS provides seven core workflows. Each guide states its purpose, entry conditions, operating steps, and verification expectations.

| Applicable scenario | MALTS workflow | Start condition | Primary result |
|---|---|---|---|
| Establish a standard project control | [MALTS Project Init](skills/malts-project-init/SKILL.md) (`malts-project-init`) | The project needs lightweight durable control. | Establishes the initial Project-level control once. |
| Clarify a non-trivial task before implementation | [MALTS Grill-Me Preflight](skills/grill-me-preflight/SKILL.md) (`malts-grill-me-preflight`) | Assumptions, boundaries, trade-offs, or acceptance criteria need clarification. | A read-only clarification result; no files are modified and no Agent is dispatched. |
| Establish, recover, or structurally organize a long workspace | [MALTS Long Project Workspace Init](skills/malts-long-project-workspace-init/SKILL.md) (`malts-long-project-workspace-init`) | A Phase-based long project is initialized, structurally repaired, or deliberately reorganized. | A governed long-workspace structure and recovery path. |
| Produce a bounded continuation record | [MALTS Session Handoff](skills/session-handoff/SKILL.md) (`malts-session-handoff`) | A later Agent or session needs verified current context. | An on-demand `PROJECT_HANDOFF.md` view, not a competing authority. |
| Review verified project experience for possible reuse | [MALTS Project Retrospective Growth](skills/project-retrospective-growth/SKILL.md) (`malts-project-retrospective-growth`) | Completed, failed, or reworked work contains evidence worth reviewing. | Evidence-based growth candidates; durable promotion remains separately authorized. |
| Perform the default post-task growth check | [MALTS Single-Agent Lightweight Growth](skills/single-agent-lightweight-growth/SKILL.md) (`malts-single-agent-lightweight-growth`) | A verified task finished and a no-write check is appropriate. | A low-overhead recommendation or no-op; no durable guidance is created automatically. |
| Coordinate admitted delegated work | [MALTS Multi-Agent Long-Task Scheduling](skills/multi-agent-long-task-scheduling/SKILL.md) (`malts-multi-agent-long-task-scheduling`) | Work lanes, resources, verification responsibilities, and user authorization can be stated. | A governed launch-review and delegation path with cost-aware model routing. |

## Operating Model

MALTS is single-Agent first. The main Agent remains the normal executor; multi-Agent work is an optional, reviewed division of responsibility rather than an automatic consequence of installation.

Long-workspace initialization is reserved for first setup, structural repair, explicit reorganization, or a major lifecycle change. An initialized unchanged workspace uses a bounded, read-only ordinary-workspace assessment (implemented as `workspace-entry`); it creates no Phase, Session, Agent, Artifact, coordination service, or report update and loads no full history.

Fresh long workspaces use the CURRENT workspace contract with `single_phase` by default. A project may explicitly opt into `resource_admission` when it can declare resources and capabilities. That route governs disjoint work through typed resource locators, capability policies, expiring leases, fencing epochs, queues, and domain-scoped reconciliation of uncertain external effects. MALTS Core contains no Unity, Unreal, VCS, database, CI, or device-specific conflict rule; adapters declare those concrete resources and capabilities.

Project, Phase, and explicit Session controls own their respective facts. Machine-enforced contract, profile, index, and coordination state live in runtime contracts. Under CURRENT, `WORK_TASK_REPORT.md` and an existing `PROJECT_HANDOFF.md` are on-demand derived views, not daily mutation gates or alternate authorities. Supported legacy layouts remain readable compatibility inputs and are never silently reorganized.

## Core And Optional Capabilities

| Capability | Default | Purpose |
|---|---|---|
| Single-Agent execution | On | Keep small and clear work low-overhead. |
| `PROJECT_CONTROL.md` | Used for non-trivial or recovery-sensitive work | Preserve Project facts, global acceptance, cross-Phase decisions, and verified recovery context. |
| Phase and explicit Session controls | Available for long workspaces | Keep local scope, queues, checkpoints, and evidence with their owner. |
| `WORK_TASK_REPORT.md` | On demand | Provide a derived report with evidence; never grant execution authority. |
| `PROJECT_HANDOFF.md` | On demand | Provide a bounded continuation view; never compete with recovery authority. |
| Grill-Me Preflight | Offered for unclear or non-trivial work | Surface assumptions and acceptance criteria before implementation. |
| Multi-Agent scheduling | Off | Add controlled delegation only where it has clear value. |
| Resource admission | Off | Govern eligible concurrent writes, shared capabilities, stale writers, and uncertain effects. |
| Plan Recheck | Event-triggered for active plans | Detect plan, scope, Session, and launch-review drift before gated actions. |
| Growth review | Available | Filter reviewed lessons before durable promotion. |
| Bilingual documentation | Available | Provide English and Simplified Chinese references without duplicating project state. |

## Control Files And Derived Views

MALTS does not create permanent control files for every short task. For contained work, stay single-Agent and follow the existing project instructions.

When a task needs recoverable long-task mode, create or reuse `PROJECT_CONTROL.md` in the project root. Refresh `WORK_TASK_REPORT.md` only when the user requests a durable report or a material delivery or recovery need justifies one. Create `PROJECT_HANDOFF.md` only when a future Agent needs a bounded continuation view. Narrative content may use the project's working language; translated mirror files are optional and explicit.

| File | Default role |
|---|---|
| `PROJECT_CONTROL.md` | Canonical Project facts, global acceptance, cross-Phase decisions, and compact owner indexes. |
| `PHASE_CONTROL.md` | Canonical Phase objective, boundary, local queue, deliverables, evidence, and closure. |
| `SESSION_CONTROL.md` | Canonical checkpoint for one explicitly bounded work session. |
| `WORK_TASK_REPORT.md` | On-demand derived report with direct evidence; never an authorization or lifecycle authority. |
| `PROJECT_HANDOFF.md` | On-demand derived continuation view; never a competing recovery authority. |

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
- [Lifecycle](docs/LIFECYCLE.md): runtime versions, recovery, reorganization, doctor diagnostics, and cleanup.
- [Usage](docs/USAGE.md): ordinary tasks, long workspaces, multi-Agent work, growth, and handoff.
- [System Overview](docs/SYSTEM_OVERVIEW.md): public explanation of goals, features, and boundaries.
- [Core Design](docs/CORE_DESIGN.md): detailed operating model and invariants.
- [Agent Install](docs/AGENT_INSTALL.md): authorization and source-selection rules for Agents.
- [Release Artifact](docs/RELEASE_ARTIFACT.md): optional single-ZIP offline delivery.
- [Security](docs/SECURITY.md): source and package verification plus privacy boundaries.
- [Bilingual Docs](docs/BILINGUAL_DOCS.md): available English and Simplified Chinese documentation.
- [Changelog](CHANGELOG.md): version history and release notes.

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

Supported tools: `Codex`, `ClaudeCode`, `OpenCode`, and `AllIncluded`.

If Windows PowerShell blocks script execution, run the same command with a process-local policy override:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool Codex
```

See [Install](docs/INSTALL.md) and [Agent Install](docs/AGENT_INSTALL.md).

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

MALTS documentation is available in English and Simplified Chinese. See [Bilingual Docs](docs/BILINGUAL_DOCS.md) for language coverage and corresponding documents.

## Version

Current release version:

```text
1.5.0
```

## License

MIT License. See [LICENSE](LICENSE).
