# Multi-Agent Long-Task Scheduling and Growth System

MALTS is a portable operating framework for long-running coding tasks performed or assisted by AI agents. It formalizes a recoverable lifecycle for work whose duration, uncertainty, or coordination requirements may exceed a single prompt, one context window, one uninterrupted session, or one Agent's short-term memory.

MALTS is single-agent first. Multi-agent execution is a controlled division-of-work mechanism, activated only when it has demonstrable operational value, and every real sub-agent dispatch requires an explicit launch review before execution. Even when sub-agents participate, the main controller retains final responsibility for judgment, merge, verification, and delivery.

In design terms, MALTS functions as a minimal-overhead Agent Project Operating System. It connects task delivery, recoverable execution, controlled delegation, verification evidence, and retrospective learning into one closed operating loop. Its central purpose is to preserve intent, evidence, recovery state, and reusable knowledge across bounded execution rounds.

## Design Baseline

This document defines the core design principles, operating model, and system boundaries of MALTS. MALTS is designed for long-running coding tasks performed or assisted by AI agents, with emphasis on goal drift, state loss, insufficient verification evidence, cross-window recovery, and reusable learning. It specifies the relationship between single-agent execution, controlled multi-agent division of work, recovery, delivery verification, and growth.

The design-invariant baseline is:

- The system integrates long-task scheduling for delivery with project retrospective growth for future capability improvement.
- The system is one closed workflow and must not be decomposed into unrelated products.
- Normal work remains single-agent by default.
- Low-overhead growth review is always available, while file-writing and durable-memory work are tiered by value and risk.
- Multi-agent scheduling is optional and must be justified by real value such as independent exploration, independent verification, lower context pressure, or non-conflicting parallel work.
- No real sub-agent dispatch happens until the user has seen a launch review and explicitly confirmed it.
- The main controller may delegate planning, exploration, implementation, verification, or memory curation, but cannot delegate final responsibility.
- Long tasks must be recoverable from files, not only from chat memory.
- The user's original goal and acceptance criteria must stay visible and must not be silently rewritten.
- Completion claims require verification evidence.
- Growth candidates must be filtered and deduplicated before durable rule or memory writes.
- Token cost is a design constraint. Additional agents, documents, and rules are justified only when they improve recovery, verification, delivery, or reuse.
- Git is an optional recovery enhancement, not a hard dependency. MALTS must remain usable for users and projects without Git.
- High-risk actions such as deletion, dependency changes, permission changes, build configuration changes, credential changes, or durable rule changes need confirmation or explicit safety controls.
- Codex, Claude Code, and OpenCode are peer adapters around the same core system.

## Conceptual Model

MALTS treats Agent work as an auditable operating lifecycle rather than a transient conversation. The model is defined by four controlled transformations:

| Operating Problem | MALTS Control Mechanism | Resulting System Property |
|---|---|---|
| User intent can drift across long conversations. | Original goal capture, completion definition, and acceptance criteria. | Goal stability and reviewable task boundaries. |
| Long execution can exceed a single context or session. | Bounded rounds, recovery files, work reports, and handoff records. | Continuation from external evidence. |
| Parallel work can create coordination risk. | Launch review, task contracts, scoped permissions, and dispatch evidence. | Controlled delegation with reviewable accountability. |
| Experience can accumulate as noise. | Retrospective analysis, memory-write filtering, deduplication, and destination selection. | Reusable capability without uncontrolled rule growth. |

The resulting system is intentionally modest in runtime assumptions and strict in state discipline. It does not require a central service, but it requires that important goals, decisions, checks, risks, and recovery points become explicit artifacts.

## System Definition and Scope

### Definition

MALTS is a portable operating workflow for AI-agent-assisted coding projects. It defines how an Agent captures the user's goal, converts that goal into verifiable work, preserves sufficient state for continuation across interruptions, and distills reusable lessons into future capability without uncontrolled durable-memory accumulation.

The system is intentionally low-overhead. Its primary operational substrate is a file-backed set of runtime rules, templates, checklists, handoff records, work reports, and optional tool adapters. It can therefore operate inside existing coding environments without requiring a mandatory server, daemon, or database.

### Intended Users And Use Cases

MALTS is designed for:

- users who require coding-agent work to remain recoverable across windows, sessions, and interruptions
- single-agent tasks that require low-overhead growth review after corrections, failures, or consequential decisions
- long-running coding projects that need explicit state, acceptance criteria, verification, and handoff
- tasks where independent exploration or verification may justify a controlled multi-agent round
- teams or individuals who require one core operating model across Codex, Claude Code, and OpenCode

The primary operating intent is task completion with preserved goal definition, verification evidence, recovery state, and reusable lessons. Multi-agent execution is one controlled mechanism inside that broader operating model, not the defining feature of the system.

### Scope Boundary

MALTS is scoped as an Agent project operating workflow. Agent runtime behavior, source control, package management, editing, CI, secret management, and human approval remain external systems with independent authority.

The design boundary is explicit:

- orchestration is implemented as a file-backed, workflow-driven model rather than a mandatory central service
- Git improves safety as an optional recovery mechanism
- multi-agent scheduling remains an optional controlled mode
- durable memory writes are treated as filtered outcomes after review
- high-risk actions remain subject to user confirmation or explicit safety controls
- runtime state and project artifacts remain external to the reusable MALTS system definition

### Normative Operating Commitments And Explicit Limits

Within its scope, MALTS defines enforceable operating commitments and corresponding capability limits:

| Dimension | Normative Commitment | Explicit Limit |
|---|---|---|
| Recoverability | Project state is externalized into files such as `PROJECT_CONTROL.md`, `WORK_TASK_REPORT.md`, and `PROJECT_HANDOFF.md`. | Recovery cannot reconstruct work that was never recorded before interruption or handoff. |
| Runtime continuity | Long work is divided into bounded rounds with explicit stop, report, and continuation points. | Bounded rounds do not extend a runtime's context window, tool limits, or uninterrupted session lifetime. |
| Delegation control | Real sub-agent dispatch is preceded by launch review, user confirmation, task contracts, and later report recycling. | MALTS cannot certify sub-agent work when the runtime exposes no dispatch evidence. |
| Completion evidence | Completion is evaluated against acceptance criteria and recorded verification evidence. | Performed checks can be evidenced; skipped, blocked, or unavailable checks cannot be retroactively certified. |
| Knowledge growth | Reusable lessons enter durable rules or memory only after filtering, deduplication, and destination selection. | Incidental observations do not automatically become durable policy. |
| Risk governance | High-risk operations require user confirmation or an explicitly recorded safety control. | MALTS does not replace the authority of external systems such as source control, CI, permission models, or human approval. |

### Core Operating Loops

The system keeps three loops connected:

```text
Delivery loop:
goal -> completion definition -> task queue -> execution -> verification -> delivery

Scheduling loop:
state -> bounded round -> optional delegation -> report recovery -> merge -> next round

Growth loop:
fact review -> cause analysis -> reusable lesson -> filtered candidate -> future use
```

The delivery loop preserves task relevance. The scheduling loop preserves recoverability for long work. The growth loop preserves epistemic discipline by preventing unfiltered observations from becoming permanent memory.

## System Boundaries

MALTS has these core responsibilities:

- provide a recoverable state model through `PROJECT_CONTROL.md`
- keep task queues, decisions, file ownership, verification, and recovery notes outside volatile chat context
- support low-overhead single-agent growth for ordinary work
- support controlled multi-agent scheduling when it has clear value
- provide task contracts and sub-agent report templates
- provide delivery, quality, and memory-write checklists
- provide Agent-facing handoff through `PROJECT_HANDOFF.md`
- provide work reports through `WORK_TASK_REPORT.md` using the user's or project's primary language; full translated mirrors are optional and explicit
- provide optional adapters for Codex, Claude Code, and OpenCode
- provide low-overhead linting and document-structure checks

The following responsibilities remain outside the current MALTS scope:

- operating a mandatory scheduling service or database
- requiring Git, a specific IDE, or a specific agent runtime
- creating MALTS files for every small task
- default large-scale sub-agent launch
- treating every lesson as a permanent rule
- overriding user judgment on high-risk actions
- extending a runtime's uninterrupted session duration
- certifying sub-agent work without visible dispatch evidence

## Architecture

MALTS uses one core system with three layers:

```text
MALTS
|
|- Core layer
|  |- PROJECT_CONTROL.md
|  |- WORK_TASK_REPORT.md
|  |- PROJECT_HANDOFF.md
|  |- templates
|  |- checklists
|  `- durable growth candidates
|
|- Runtime layer
|  |- canonical skills
|  |- execution modes
|  |- recovery and continuity
|  |- delivery verification
|  `- memory pipeline
|
`- Adapter layer
   |- Codex
   |- Claude Code
   `- OpenCode
```

The core layer stores the common operating model and durable project artifacts. The runtime layer turns that model into executable Agent workflows through the root `skills/` directory, execution modes, recovery, verification, templates, checklists, and the memory pipeline. The adapter layer maps the same model into each supported agent tool without letting tool-specific details pollute the core design.

The public package has one canonical skill implementation and runtime source: the shared `MALTS_ROOT`, with `skills/` at that root. Target tool directories are thin adapter targets, not separate MALTS runtime or implementation sources. They may contain discovery-only bridge `SKILL.md` files required by native tool indexing. `runtime/EN` contains Agent-facing templates and checklists used by MALTS workflows. `runtime/CH` contains Simplified Chinese runtime mirrors for user-facing review and bilingual artifact generation.

## Activation Model

MALTS has three practical modes.

| Mode | When Used | Files Required | Behavior |
|---|---|---|---|
| Normal single-agent work | Small, clear, low-risk tasks | None by default | Finish directly, verify the relevant completion criteria, optionally make a low-overhead growth judgment |
| MALTS single-agent mode | Work needs recoverable state or phase reporting | `PROJECT_CONTROL.md`; usually `WORK_TASK_REPORT.md` and `PROJECT_HANDOFF.md` when appropriate | Main controller still executes by default, but state and verification are persistent |
| MALTS multi-agent mode | Delegation clearly reduces risk or cost | MALTS files plus task contracts and sub-agent reports | Requires launch review and explicit confirmation before dispatch |

Single-agent first means the main controller remains the default executor after MALTS is enabled. The principle has two explicit boundaries: it neither enables MALTS for every task nor removes state files once MALTS has been activated.

## Task Sizing

Every task should receive a fit-for-process assessment before procedural overhead is added.

| Level | Shape | Default Choice |
|---|---|---|
| S0 trivial | One command, one short answer, typo, simple lookup, small formatting change | Single Agent only |
| S1 bounded | Single file or single behavior with clear verification | Single Agent plus low-overhead growth judgment when justified |
| S2 medium | Multiple files or unclear cause, but still manageable in one bounded round | Single Agent first; consider Explorer or Verifier only if it lowers risk |
| S3 complex | Multi-phase, multi-module, interruption-prone, or likely to exceed comfortable context | Use MALTS state; prepare launch review if multi-agent work has value |
| S4 high-risk or unclear | Destructive operations, permissions, dependencies, build configuration, credentials, durable rules, unclear goal, unclear verification | Clarify or get approval first; use read-only planning or verification before writes |

The Agent should explain the expected operational value of multi-agent work before recommending it. If the value is unclear, the execution should remain single-agent.

## Project State Model

`PROJECT_CONTROL.md` is the main state file when MALTS is enabled. It exists so the next window, next Agent, or same Agent after context compaction can continue from external evidence.

Current MALTS version metadata inside `PROJECT_CONTROL.md` is not historical prose. Agents must resolve the active boot file, read `<MALTS_ROOT>/VERSION`, and write that value into current metadata. Version strings found in old control files, work reports, handoffs, templates, release notes, or chat history are historical until revalidated against the active root.

The core sections are:

```text
User Original Goal
Current Interpreted Goal
Completion Definition
Acceptance Criteria
Current Mode
Current Stage
Task Queue
File Ownership
Decisions
Verification Records
Deliverables
Risks And Blockers
Exception Handling
User Checkpoints
Termination Status
Planner Evaluation
Cost And Efficiency
Growth Candidates
Next Round Plan
Recovery Notes
```

The minimum recovery state is:

- current goal
- completion definition
- active task and next task
- completed work
- changed files
- verification evidence
- open risks or blockers
- user decisions still needed
- next shortest recovery path

For small MALTS-enabled work, the file can remain compact. The objective is recoverable state, not document volume for its own sake.

## Artifact Matrix

| Artifact | Default Location | Audience | Purpose |
|---|---|---|---|
| `PROJECT_CONTROL.md` | Project root | Agent-facing | Current goal, queue, decisions, ownership, verification, risks, recovery state |
| `WORK_TASK_REPORT.md` | Project root | Agent-facing structure and report source | Phase or final delivery report structure and evidence record |
| `PROJECT_HANDOFF.md` | Project root | Agent-facing | Continuation source for future windows, tools, or Agents |
| `TASK_CONTRACT.template.en.md` | `runtime/EN/templates/` | Agent-facing | Contract for a real sub-agent task |
| `SUB_AGENT_REPORT.template.en.md` | `runtime/EN/templates/` | Agent-facing | Structured result returned by a sub-agent |
| `PROJECT_HANDOFF.template.en.md` | `runtime/EN/templates/` | Agent-facing | Template for fixed recovery handoff |
| `WORK_TASK_REPORT.template.en.md` | `runtime/EN/templates/` | Agent-facing structure, user-facing output | Structure for reports that may be written in the user's language |
| `WORK_TASK_REPORT.template.zh-CN.md` | `runtime/CH/templates/` | Localized reference | Reference for Chinese wording inside canonical reports or explicit translated mirrors |
| `DELIVERY_CHECKLIST.en.md` | `runtime/EN/checklists/` | Agent-facing | Final or phase delivery self-check |
| `MEMORY_WRITE_CHECKLIST.en.md` | `runtime/EN/checklists/` | Agent-facing | Filter before durable memory or rule writes |
| `QUALITY_GATE.en.md` | `runtime/EN/checklists/` | Agent-facing | General completion gate |

Release templates are starting points. Real project artifacts belong in the user's project workspace, not in this release repository.

## Bounded Runtime Flow

The standard MALTS execution protocol is round-based:

1. Read the user goal and project instructions.
2. Decide whether MALTS is needed.
3. If MALTS is enabled, create or reuse `PROJECT_CONTROL.md`.
4. Capture the original goal, completion definition, acceptance criteria, task queue, file ownership, and risks.
5. Offer MALTS-native Grill-Me Preflight for non-trivial or unclear starts unless it is clearly N/A.
6. Execute the next bounded round.
7. Verify before marking tasks complete.
8. Write or append `WORK_TASK_REPORT.md` after each MALTS phase or final delivery, using the user's or project's primary language for narrative content. Create a full translated mirror only when explicitly requested.
9. When entering handoff, context-risk handling, or cross-window continuation, update `PROJECT_HANDOFF.md`.
10. Route reusable lessons through the MALTS Memory Pipeline.

Long work is modeled as a sequence of bounded rounds with explicit stop, report, and continuation points. This design makes continuity independent of any single uninterrupted chat window.

MALTS is not a background service that automatically observes context windows or writes handoff files. Recoverability depends on the Agent executing this protocol at the relevant checkpoints.

## Context And Continuity

If context becomes risky, the main controller must persist recovery state before doing more non-trivial work. Context risk includes:

- approaching context limits
- compaction or summarization
- tool/runtime interruption
- handoff to another window
- unresolved sub-agent work
- multiple active branches of work

Before continuation, a future Agent should read in this order:

1. `PROJECT_HANDOFF.md`
2. `PROJECT_CONTROL.md`
3. `WORK_TASK_REPORT.md`
4. current project files needed for the next task

If chat memory conflicts with file state, current file state wins until verified otherwise.

## Optional Multi-Agent Scheduling

Multi-agent work is a controlled division-of-work mechanism and remains outside the default runtime path.

The supported roles are:

| Role | Default Permission | Responsibility |
|---|---|---|
| Main Controller | Coordination, merge, final judgment | Owns user communication, state, launch review, merge, verification, delivery |
| Planner | Read-only advice | Breaks work into tasks, dependencies, priorities, and batches |
| Explorer | Read-only | Investigates project structure, logs, modules, or root cause |
| Worker | Scoped write access | Implements within a declared file or task boundary |
| Verifier | Read-only by default; may run checks | Tests, builds, scans, and validates delivery claims |
| Memory Curator | Candidate writes only | Extracts reusable lessons and prepares filtered growth candidates |

Advanced roles can be added later, but the MVP should avoid unbounded role proliferation.

Before any real sub-agent dispatch, the main controller must present a launch review packet with:

- overall goal and plan
- expected operational value of multi-agent work for this task
- each role to be dispatched
- each task boundary
- allowed files or directories
- prohibited areas
- model name or model policy when available
- dispatch order or parallel batches
- verification requirement
- expected output format
- statement that dispatch waits for explicit user confirmation

If the user specifies sub-agent models, the main controller should ask for model preferences and record the result before dispatch. If the runtime does not expose exact model selection or exact inherited model names, that limitation must be recorded as part of the execution evidence.

No sub-agent work may be claimed unless there is visible dispatch evidence from the runtime, such as a tool call, thread ID, agent ID, transcript, or equivalent record.

## Task Contracts And Recovery

A task is ready for dispatch only when it has:

- clear goal
- available context
- allowed read/write scope
- prohibited scope
- dependencies satisfied
- file ownership or conflict boundary
- expected output format
- verification method
- model policy when relevant

Sub-agent reports must be recycled before merge. Reports that are off-scope, unverifiable, incomplete, or inconsistent with the task contract should be rejected, retried with a smaller task, or escalated to the user.

Failures should be recorded as failures. Partial or failed sub-agent output must remain classified as incomplete work rather than completed progress.

## Verification And Delivery

Completion is an evidentiary claim. It must be supported by verification records rather than subjective confidence.

Before phase or final delivery, the Agent should review `DELIVERY_CHECKLIST.en.md` and record the review in `WORK_TASK_REPORT.md` or the final user-facing report.

The report pair should include:

- result
- changed files or artifacts
- verification performed
- skipped or failed checks
- known risks
- recovery point
- next step
- growth review and memory-write decision when applicable

Termination has three practical states:

| State | Meaning | Delivery Behavior |
|---|---|---|
| Ideal | All acceptance criteria pass and risks are closed or accepted | Deliver normally |
| Pragmatic | Core goal is met, with transparent residual risk | Deliver with risk list |
| Forced | User stops, budget is exhausted, environment blocks progress, or direction is uncertain | Save state and recovery path |

If verification is incomplete, the delivery record must state the limitation explicitly. A partially verified result is not a fully verified delivery.

## Growth System

Growth is an operational change process, not a retrospective summary alone.

| Output | Purpose |
|---|---|
| Summary | What happened |
| Retrospective | Why it happened and where process drifted |
| Distillation | What should change next time, with trigger, action, check, and boundary |
| Skill or rule | A reusable future behavior that can be invoked at the right time |

Growth runs in tiers:

| Tier | Trigger | Output |
|---|---|---|
| Light | Ordinary small task | Usually no file; short judgment only when justified |
| Standard | Phase delivery, user correction, mild rework, consequential decision | Candidate lesson, checklist item, or report note |
| Major | Significant failure, direction drift, repeated rework, long-task completion | Full retrospective and durable rule/skill candidate |

This tiering keeps ordinary work at low operational cost while preserving lessons when their expected reuse value justifies retention.

## MALTS Memory Pipeline

MALTS Memory Pipeline is the durable growth path for reusable lessons. It is independent of any single external memory tool.

The pipeline is:

1. Observe a reusable lesson from delivery, failure, user correction, verification, or process friction.
2. Record it locally first in `PROJECT_CONTROL.md`, `WORK_TASK_REPORT.md`, or a local retrospective.
3. Filter it with `MEMORY_WRITE_CHECKLIST.en.md`.
4. Deduplicate against existing rules, skills, and instruction files.
5. Choose the narrowest durable destination: project skill, global skill, `GLOBAL_MEMORY.md`, `AGENTS.md`, `CLAUDE.md`, or an equivalent tool instruction entry.
6. Use an optional external memory system only when one is configured, write-capable, and appropriate.
7. If a durable destination is unavailable, keep the local candidate and report that no long-term write happened.

An experience should become durable memory only when it is real, repeatable, bounded, checkable, and its expected reuse value exceeds the cost of maintaining it.

## Token And Cost Control

MALTS treats process cost as a first-class design constraint: coordination and documentation are justified only when their return exceeds their operational cost.

Cost controls:

- keep S0/S1 work single-agent
- read only the documents needed for the current decision
- avoid loading English and Chinese runtime docs together during normal execution
- keep long templates out of global instruction files
- use bounded rounds instead of open-ended progress
- give sub-agents only task-relevant context packets
- merge or drop low-value tasks instead of scheduling them as independent work
- keep growth review tiered
- write durable rules only after filtering
- reduce multi-agent parallelism when it creates more coordination cost than delivery value

A multi-agent round should be judged by whether uncertainty decreased, verification improved, conflicts stayed controlled, and the task queue moved toward completion.

## Safety And Permissions

Task contracts should identify permission level:

| Level | Permission |
|---|---|
| 0 | Read-only analysis |
| 1 | Modify specified files only |
| 2 | Add files, but do not delete files |
| 3 | Directory restructuring only after main-controller approval |
| 4 | High-risk operation requiring user confirmation |

High-risk operations include:

- deleting files
- modifying permissions
- changing dependency versions
- changing build configuration
- changing authentication, credentials, or authorization behavior
- overwriting existing configuration
- cleaning caches, logs, history, or archives
- modifying durable global instructions, skills, or long-term rules

If the project has Git, check current state before meaningful edits and never discard user changes without explicit approval. If the project has no Git, use lighter recovery mechanisms such as scoped backups, smaller patches, and clear recovery notes for risky edits.

## Unattended Continuation

Unattended continuation is excluded from default long-task scheduling semantics. It requires explicit user authorization and must be recorded in `PROJECT_CONTROL.md`.

An authorization record should include:

- authorized goal
- allowed files, directories, commands, and actions
- prohibited actions
- whether multi-agent dispatch is allowed
- model policy for any allowed sub-agent work
- maximum rounds or time limit
- stop conditions
- report and recovery-state requirements
- continuation mechanism, if any

Without that record, MALTS stops at normal user checkpoints.

## Adapter Strategy

MALTS keeps the core portable and puts tool-specific details in adapters.

Codex:

- use `AGENTS.md` as the instruction entry
- use Codex `config.toml` and `agents/*.toml` in the Codex config root for Codex-native custom subagent scaffolding when installed
- resolve MALTS skills and runtime files through `MALTS_BOOT.md` and the shared `MALTS_ROOT`
- do not claim Claude Code or OpenCode-style file-backed custom slash commands for Codex unless Codex documents that mechanism
- use `PROJECT_CONTROL.md` as recoverable state
- use visible tool calls or thread tools as dispatch evidence when sub-agents are actually used
- record agent IDs, roles, task IDs, model policy, and report summaries when available

Claude Code:

- use `CLAUDE.md` as the instruction entry
- place commands and agents in Claude Code's expected adapter directories
- resolve MALTS skills and runtime files through `MALTS_BOOT.md` and the shared `MALTS_ROOT`
- install only discovery bridges locally; never install tool-local skill implementation duplicates
- record the runtime-visible agent or transcript evidence available in the installed version
- record limitations when explicit model selection is unavailable or unverified

OpenCode:

- use `AGENTS.md` and OpenCode-specific config as the instruction and tool entry
- keep OpenCode-specific files in the adapter layer
- resolve MALTS skills and runtime files through `MALTS_BOOT.md` and the shared `MALTS_ROOT`
- install only discovery bridges locally; never install tool-local skill implementation duplicates
- verify how the target OpenCode version exposes sub-agent dispatch evidence before claiming transparent multi-agent execution

Adapter docs and templates should stay synchronized across Codex, Claude Code, and OpenCode unless a change is explicitly scoped to one tool. Public protocol changes should also update EN+CH counterparts together unless a release note records why a language is intentionally skipped.

Top-level tool instruction files have mixed ownership. MALTS owns only the block delimited by `<!-- MALTS:BEGIN managed instruction -->` and `<!-- MALTS:END managed instruction -->`; all surrounding text remains user-owned. The default installer and updater behavior must merge that block idempotently, migrate a recognizable legacy MALTS section, and stop on ambiguous markers. Whole-file replacement is an explicit operation, never the safe-update default. Installed tool instructions can be checked against their adapter source with `check-managed-instruction-sync`.

## Bilingual Documentation

English runtime documents are the release source of truth. Chinese documentation is an optional review mirror for user review and bilingual maintenance.

Agents should avoid loading both EN and CH documents during normal execution. The doc sync tooling checks configured structure and paths; it is not evidence of translation quality or semantic equivalence. Critical protocol wording requires human or main-controller review.

If English and Chinese docs conflict, fix the English source first, then resynchronize the Chinese review copy.

## System Distribution Boundary

MALTS is distributed as a portable operating system for Agent work: runtime rules, templates, checklists, adapter guidance, installation helpers, and design documentation. A distribution package should contain the reusable system definition and the materials required to install or operate that system in a project environment.

Project-specific state is intentionally outside the system distribution. Actual project control files, work reports, handoff records, local retrospectives, generated packages, caches, and runtime history are execution artifacts created by individual projects. They are governed by the project that produced them, not by the MALTS system definition.

This boundary keeps the system reusable across machines, teams, and Agent runtimes. It also preserves a clear distinction between the MALTS operating model and the records produced when that model is applied to a concrete project.

## MVP Implementation Phases

The MVP sequence is:

1. Design and templates: project control, task contract, sub-agent report, delivery checklist, quality gate.
2. Core skills: Grill-Me Preflight, long-task scheduling, project retrospective growth, session handoff, project initialization, and single-agent low-overhead growth under root `skills/`.
3. Tool adapters: Codex, Claude Code, OpenCode.
4. Lightweight automation: task ID generation, project-control checks, doc sync checks, semantic freshness checks, installer dry-runs.
5. Trial and retrospective: validate actual single-agent growth and actual multi-agent dispatch separately. Multi-agent validation claims require real dispatch evidence.

## Acceptance Standard

The first complete MALTS release is acceptable when:

- ordinary tasks can stay single-agent with low overhead
- non-trivial starts can expose assumptions through Grill-Me Preflight
- long tasks can create or reuse `PROJECT_CONTROL.md`
- state can recover across windows or Agents
- multi-agent work requires launch review and explicit confirmation
- sub-agent contracts include scope, output, and verification
- completion claims include evidence
- `WORK_TASK_REPORT.md` can explain results, verification, risk, and recovery to the user
- `PROJECT_HANDOFF.md` can guide the next Agent
- growth candidates pass a memory-write checklist before durable writes
- Codex, Claude Code, and OpenCode have adapter entry points
- bilingual docs are structurally synchronized when enabled
- no-Git projects still have basic recovery insurance
- token and coordination cost controls are documented and applied
