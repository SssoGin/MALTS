# MALTS

**Multi-Agent Long-Task Scheduling and Growth System**

Languages: [English](README.md) | [简体中文](README.zh-CN.md)

MALTS is a portable, file-based operating framework for long-running project work performed or assisted by AI agents. Its operational substrate is a file-based workflow of canonical rules, templates, checklists, recovery records, and optional tool adapters. It formalizes a recoverable lifecycle for tasks whose duration, uncertainty, or coordination requirements may exceed a single prompt, one context window, one uninterrupted session, or one Agent's short-term memory.

MALTS operates as a minimal-overhead Agent project operating system, connecting task delivery, recoverable execution, controlled delegation, verification evidence, and retrospective learning into one closed loop, with the central purpose of preserving intent, evidence, recovery state, and reusable knowledge across bounded execution rounds. It is single-agent by default; multi-agent execution is a controlled division-of-work mechanism, activated only when it has demonstrable operational value, and requires an explicit launch review before dispatch, with the main controller retaining final responsibility for judgment, merge, verification, and delivery. Long-running tasks persist in project files rather than only in chat memory, so they can continue across windows, sessions, or agents.

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

## Scope

MALTS is scoped to project work performed or assisted by AI agents. It applies to long-running, multi-file, or recovery-sensitive work -- migrations, multi-file changes, long investigations, release preparation, protocol or documentation work -- where losing a decision or claiming completion without verification would be costly. For a small task with a clear result, the normal project workflow is sufficient. Agent runtime behavior, source control, package management, editing, CI, secret management, and human approval remain external systems with independent authority.

## Core MALTS Workflows

MALTS provides seven core workflows. Choose the entry point that matches what you want to do; each one states when to use it, how it runs, and what you get afterward.

| Applicable scenario | MALTS workflow | When to use | Result |
|---|---|---|---|
| Give a normal project durable goals and state | [MALTS Project Init](skills/malts-project-init/SKILL.md) (`malts-project-init`) | The result is clear, but the work has several steps or spans multiple rounds. | Creates project control once, preserving the goal, acceptance criteria, and current state. |
| Confirm goals and boundaries before implementation | [MALTS Grill-Me Preflight](skills/grill-me-preflight/SKILL.md) (`malts-grill-me-preflight`) | The goal, boundary, trade-offs, or acceptance criteria are still unclear. | Returns a read-only clarification; no file changes and no Agent dispatch. |
| Build a long workspace that can recover across windows | [MALTS Long Project Workspace Init](skills/malts-long-project-workspace-init/SKILL.md) (`malts-long-project-workspace-init`) | The project lasts multiple days or phases and needs interruption-safe continuation. | Creates a Phase-based recoverable structure, phase boundaries, and a recovery entry. |
| Produce continuation notes for a completed segment | [MALTS Session Handoff](skills/session-handoff/SKILL.md) (`malts-session-handoff`) | Current work has ended and the next step must know exactly where it stopped. | Creates `PROJECT_HANDOFF.md` on demand as an evidence-backed continuation view. |
| Review experience from a task and decide whether to reuse it | [MALTS Project Retrospective Growth](skills/project-retrospective-growth/SKILL.md) (`malts-project-retrospective-growth`) | A success, failure, or rework contains lessons worth reviewing. | Provides evidence-based improvement candidates; durable promotion remains separately authorized. |
| Run a lightweight experience check after an ordinary task | [MALTS Single-Agent Lightweight Growth](skills/single-agent-lightweight-growth/SKILL.md) (`malts-single-agent-lightweight-growth`) | The task is done and verified, and you only want to know whether the experience is worth recording. | Returns a recommendation or no-op; it never creates durable guidance automatically. |
| Have multiple Agents complete complex work by division | [MALTS Multi-Agent Long-Task Scheduling](skills/multi-agent-long-task-scheduling/SKILL.md) (`malts-multi-agent-long-task-scheduling`) | Complex work needs multiple Agents, with clear responsibilities, resources, and verification ownership. | Provides a reviewed multi-Agent delegation plan with cost-aware model routing after user confirmation. |

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
