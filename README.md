# MALTS

**Multi-Agent Long-Task Scheduling and Growth System**

Languages: [English](README.md) | [简体中文](README.zh-CN.md)

MALTS is a file-based operating model for AI-assisted project work that needs continuity, explicit decisions, or controlled delegation. It records the working objective, verified state, ownership, acceptance evidence, and recovery context in ordinary project files so work can continue safely across sessions, phases, and Agents.

MALTS complements normal project instructions; it does not replace them. A contained task with a clear outcome should remain lightweight. MALTS becomes useful when interruption, scope change, verification, handoff, or coordination would otherwise leave important work state implicit.

## Task Types and Workflow Selection

Use this decision table before selecting a workflow. Workflow names are the user-facing entries; implementation commands and runtime routes belong in the linked guides rather than in the primary navigation.

| Work situation | Applicable condition | Recommended MALTS workflow | Start condition | Primary result |
|---|---|---|---|---|
| Contained project task | The work is clear, limited, and needs no durable recovery or coordination record. | Do not start MALTS. Follow the project instructions. | The project already provides sufficient execution and verification guidance. | The task stays proportionate; no unnecessary control files are created. |
| First standard MALTS project | The project needs lightweight, durable control but not a Phase-based long workspace. | [MALTS Project Init](skills/malts-project-init/SKILL.md) (`malts-project-init`) | Project purpose and initial acceptance conditions are known. | One compact Project control with explicit ownership and next steps. |
| First long-running or interruption-sensitive project | The work spans phases, is likely to resume across contexts, or needs deliberate recovery controls. | [MALTS Long Project Workspace Init](skills/malts-long-project-workspace-init/SKILL.md) (`malts-long-project-workspace-init`) | A long-workspace boundary and first Phase can be defined. | A recoverable Phase workspace; no Session, Artifact, or Agent is created implicitly. |
| Ordinary work in an initialized workspace | The workspace is unchanged and the task remains inside its current approved scope. | Use the ordinary-workspace route in [Usage](docs/USAGE.md). | Current workspace authority is available and no recovery condition is present. | A bounded read of current state; no repeated initialization or routine control-file refresh. |
| New write scope, recovery, or workspace reorganization | The task crosses an existing boundary, recorded state has genuinely drifted, or an older layout needs current controls. | Review [Lifecycle](docs/LIFECYCLE.md) and [Usage](docs/USAGE.md) before explicit execution. | The intended change and its impact are reviewed; any required plan is approved. | A deliberate, reversible or reconcilable lifecycle action instead of an implicit rewrite. |
| Concurrent work in one workspace | More than one work lane is useful and each write scope and shared capability can be declared. | Use the resource-governed path in [Core Design](docs/CORE_DESIGN.md) and [Lifecycle](docs/LIFECYCLE.md). | The project explicitly enables resource admission and declares resources or capabilities. | Non-conflicting work may proceed independently; conflicts, stale writers, and uncertain effects remain governed. |
| Multi-Agent execution | Delegation has clear value and responsibility lanes can be independent and auditable. | [MALTS Multi-Agent Long-Task Scheduling](skills/multi-agent-long-task-scheduling/SKILL.md) (`malts-multi-agent-long-task-scheduling`) | A launch review, task contracts, and explicit user confirmation are complete. | Controlled delegation with traceable responsibilities, model routing, verification, and recovery. |

## Core MALTS Workflows

These are the seven installed core workflows. Each has a narrow role; selecting one does not authorize unrelated lifecycle changes.

| Applicable scenario | MALTS workflow | Start condition | Primary result |
|---|---|---|---|
| Establish a standard project control | [MALTS Project Init](skills/malts-project-init/SKILL.md) (`malts-project-init`) | The project needs lightweight durable control. | Establishes the initial Project-level control once. |
| Clarify a non-trivial task before implementation | [MALTS Grill-Me Preflight](skills/grill-me-preflight/SKILL.md) (`malts-grill-me-preflight`) | Assumptions, boundaries, trade-offs, or acceptance criteria need clarification. | A read-only clarification result; no files are modified and no Agent is dispatched. |
| Establish, recover, or structurally organize a long workspace | [MALTS Long Project Workspace Init](skills/malts-long-project-workspace-init/SKILL.md) (`malts-long-project-workspace-init`) | A Phase-based long project is initialized, structurally repaired, or deliberately reorganized. | A governed long-workspace structure and recovery path. |
| Produce a bounded continuation record | [MALTS Session Handoff](skills/session-handoff/SKILL.md) (`malts-session-handoff`) | A later Agent or session needs verified current context. | An on-demand `PROJECT_HANDOFF.md` view, not a competing authority. |
| Review verified project experience for possible reuse | [MALTS Project Retrospective Growth](skills/project-retrospective-growth/SKILL.md) (`malts-project-retrospective-growth`) | Completed, failed, or reworked work contains evidence worth reviewing. | Evidence-based growth candidates; durable promotion remains separately authorized. |
| Perform the default post-task growth check | [MALTS Single-Agent Lightweight Growth](skills/single-agent-lightweight-growth/SKILL.md) (`malts-single-agent-lightweight-growth`) | A verified task finished and a no-write check is appropriate. | A low-overhead recommendation or no-op; no durable guidance is created automatically. |
| Coordinate admitted delegated work | [MALTS Multi-Agent Long-Task Scheduling](skills/multi-agent-long-task-scheduling/SKILL.md) (`malts-multi-agent-long-task-scheduling`) | Work lanes, resources, verification responsibilities, and user authorization can be stated. | A governed launch-review and delegation path with cost-aware model routing. |

For exact commands, permissions, and examples, see [Getting Started](docs/GETTING_STARTED.md), [Usage](docs/USAGE.md), and [Lifecycle](docs/LIFECYCLE.md).

## What Problem It Solves

Long Agent tasks fail differently from short prompts. Context can be compressed, goals can drift, incomplete work can be mistaken for completion, parallel work can collide, and useful lessons can be either lost or promoted too broadly.

MALTS externalizes the task state that needs to survive these risks. It separates canonical control from derived reports, requires evidence before completion claims, records a recoverable continuation path, and requires a launch review before real delegated work begins.

## Operating Model

MALTS is single-Agent first. The main Agent remains the normal executor; multi-Agent work is an optional, reviewed division of responsibility rather than an automatic consequence of installation.

Long-workspace initialization is reserved for first setup, structural repair, explicit reorganization, or a major lifecycle change. An initialized unchanged workspace uses a bounded, read-only ordinary-workspace assessment (implemented as `workspace-entry`); it creates no Phase, Session, Agent, Artifact, coordination service, or report update and loads no full history.

Fresh long workspaces use the CURRENT workspace contract with `single_phase` by default. A project may explicitly opt into `resource_admission` when it can declare resources and capabilities. That route governs disjoint work through typed resource locators, capability policies, expiring leases, fencing epochs, queues, and domain-scoped reconciliation of uncertain external effects. MALTS Core contains no Unity, Unreal, VCS, database, CI, or device-specific conflict rule; adapters declare those concrete resources and capabilities.

Project, Phase, and explicit Session controls own their respective facts. Machine-enforced contract, profile, index, and coordination state live in runtime contracts. Under CURRENT, `WORK_TASK_REPORT.md` and an existing `PROJECT_HANDOFF.md` are on-demand derived views, not daily mutation gates or alternate authorities. Supported legacy layouts remain readable compatibility inputs and are never silently reorganized.

## Start Here

| Need | Read |
|---|---|
| Install MALTS and complete a first task | [Getting Started](docs/GETTING_STARTED.md) |
| Understand MALTS, its limits, and intended use | [System Overview](docs/SYSTEM_OVERVIEW.md) |
| Review the operating model, concurrency, and safety invariants | [Core Design](docs/CORE_DESIGN.md) |
| Use an initialized workspace or a specific workflow | [Usage](docs/USAGE.md) |
| Recover, reorganize, or review lifecycle rules | [Lifecycle](docs/LIFECYCLE.md) |
| Install or update a specific Agent tool | [Install](docs/INSTALL.md) and [Update](docs/UPDATE.md) |
| Let an Agent assist with installation safely | [Agent Install](docs/AGENT_INSTALL.md) |
| Use the optional offline archive | [Release Artifact](docs/RELEASE_ARTIFACT.md) |

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
- [Bilingual Docs](docs/BILINGUAL_DOCS.md): language and navigation policy.
- [Changelog](CHANGELOG.md): version history; release summaries do not accumulate in this README.

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

The repository defaults to English source documents. Simplified Chinese documents live in `README.zh-CN.md` and `docs/zh-CN/`; localized runtime references live under `runtime/CH/`. Runtime project artifacts stay single and canonical by default. See [Bilingual Docs](docs/BILINGUAL_DOCS.md).

## Version

Current release version:

```text
1.5.0
```

## License

MIT License. See [LICENSE](LICENSE).
