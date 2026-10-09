# Multi-Agent Long-Task Scheduling and Growth System

MALTS (Multi-Agent Long-Task Scheduling and Growth System) organizes AI-agent project work around goals, checkable results, recoverable execution and assessed experience. The default executor is one Agent; approved collaboration uses the same project and acceptance model. The current implementation is **2.0.0**.

## Workspace authority, entry, and concurrency

MALTS preserves one operating model across ordinary work, long projects and recovery. In an adopted workspace, the selected v2 store owns executable Project, Phase and Task definitions, revisions, dependencies, permissions, operations and acceptance. Markdown controls created by earlier releases remain original sources or reading views. They are not a second writable task queue.

Entry starts from the tool's exact `MALTS_BOOT.md`, verified installation discovery and the workspace binding. Query current governance, the task queue and the selected task; do not reinitialize or choose the newest historical session. An ordinary entry creates no Project, Phase, Session, Agent or Artifact.

The Project states the overall goal; a Phase is a bounded stage with a plan and exit criteria; a Task produces a checkable result. Definitions and dependencies bind exact revisions. Material changes require updating the affected definition and binding, while unchanged relevant evidence can be reused.

Concurrency uses declared resources, current admissions, leases and fencing: a stale executor cannot reuse an old permission through managed interfaces. Different directories alone do not prove independent editor, service or device resources. Managed fencing does not exclude arbitrary external writers. UNKNOWN effects retain their original identity until reconciled. See [State Contract](V2_STATE_CONTRACT.md).

## Design Baseline

Long work can separate user intent, external effects and acceptance evidence across execution rounds. MALTS persists these facts and binds their revisions and provenance so a successor can distinguish completed work, eligible next work and uncertain effects. Scheduling, recovery and experience use depend on the same facts rather than deriving separate completion standards.

The design baseline is:

- Preserve the user's original goal, agreed boundaries and acceptance criteria across execution rounds.
- Default to one Agent; delegate only when authorized separation offers useful investigation, implementation or verification.
- Retain external state and observed evidence needed for continuation; conversation summaries alone are insufficient.
- Keep execution, verification and acceptance distinct. A task's success does not establish whole-project completion.
- Generate reports and handoffs when they help delivery or continuation, preserving unique manual content.
- Treat experience as a sourced, bounded proposal to be tested, not an automatically permanent rule.
- Reuse existing same-scope authorization and valid evidence; additional records and checks must serve a concrete purpose.
- Support projects without Git. Git can improve recovery, but is not the project-state authority.
- Keep four tool adapters around one core, with truthful limits for each actual Host/profile.

These are operating objectives, not promises of universal speed, success rates or autonomous correctness.

## Conceptual Model

MALTS connects three operating loops:

```text
Delivery: goal -> acceptance -> finite tasks -> execution -> verification -> delivery
Scheduling: current state -> next bounded round -> optional delegation -> integration -> continuation
Growth: observed facts -> cause/applicability -> reviewed proposal -> future trial -> retain or withdraw
```

| Problem | Mechanism | What the user can inspect |
|---|---|---|
| Goals drift between rounds | Original/current goals and versioned definitions | Why scope changed and what remains required |
| A window ends before work finishes | Current task state, checkpoints and recovery evidence | What happened, what is uncertain and the next eligible action |
| Delegated results conflict | Task contracts, scoped resources and controller acceptance | Each result's boundary, integration and verification |
| Lessons grow into noise | Sourced candidates, bounded trials and withdrawal | Where a method applies and whether future evidence supports it |

For example, a repository migration can use one delivery goal, compatibility checks for each stage, an explicit continuation point, and a later trial of a useful check. It does not need four separate workflow products or a mandatory group of Agents.

The transformations in these loops have different inputs and obligations. Planning consumes a goal and constraints and produces proposed executable work. Execution consumes the current task, eligible inputs and existing authorization, and produces actual effects. Verification compares those effects with criteria. Acceptance records that comparison for the specified revision. Recovery does not repeat the original plan automatically: it first determines which effects occurred and which inputs are still current.

This separation prevents two common errors. First, an executor cannot redefine an acceptance criterion after implementing an easier result without an explicit revision. Second, a successor cannot equate a missing success message with non-execution. For a failed connection after a file update, the relevant question is whether current bytes and the original operation observation establish the result; a new request may otherwise repeat the effect.

Growth uses the event as a source for a proposal, then requires later eligible observations to judge that proposal. An original correction and a future trial therefore have different evidentiary roles. The design permits learning from a failure while keeping that failure visible in delivery and recovery.

## System Definition and Scope

### Definition

MALTS (Multi-Agent Long-Task Scheduling and Growth System) is an operating framework for AI-agent-assisted project work. It helps turn a goal into checkable outputs, continue across interruption, coordinate approved division of work and assess methods for future reuse. The same workflow applies to coding, engineering migration, investigation and document delivery when their scope benefits from persistent state.

### Intended Users And Use Cases

It serves users whose work crosses turns, stages, windows or executors; maintainers who need traceable evidence and recovery; and projects where independent investigation or verification can justify delegation. Small clear tasks can still finish directly without a workspace.

### Scope Boundary

The model interprets requirements and makes business decisions; the Host provides tools, identity, permission prompts and process facilities; MALTS manages durable state and the contracts connecting execution, evidence and recovery. Editors, Git, CI, package managers and user decisions retain their own authority.

The current adopted-workspace runtime uses a local SQLite state store and CLI/MCP services. It does not require a hosted scheduler or a background daemon. The earlier file-first design explains the product's origin; it does not mean the current v2 runtime has no database.

### Normative Operating Commitments And Explicit Limits

| Commitment | Limit |
|---|---|
| Persist enough state for continuation | Unrecorded external effects cannot be reconstructed from a summary |
| Bind actions and proof to current definitions | Version numbers and historical DONE labels do not prove present acceptance |
| Review delegation and retain controller responsibility | Configuration alone cannot certify actual native dispatch |
| Retain sources and eligibility for improvement | A useful observation does not automatically authorize durable global changes |
| Protect and reconcile uncertain effects | MALTS cannot enforce exclusion on all arbitrary OS writers |

### Core Operating Loops

Delivery establishes relevance, scheduling establishes continuity, and Growth evaluates reusable methods. Verification supplies facts to all three. None adds its own permission or changes the user's completion standard.

## System Boundaries

Workflows cover clarification, project setup, long management, current tasks, handoff, review, lightweight Growth and scheduling. Skills package methods, templates aid drafting, checklists inspect outputs and tools implement deterministic state/file actions. They support one project process instead of parallel state systems.

Skills provide no permission. Tools cannot replace business judgment, model ratings cannot manufacture acceptance, and Host configuration cannot prove actual tool/process behavior.

Installation distributes an immutable runtime and native tool entries. Adapters preserve loading/permission conventions while the shared core owns common state/recovery. Installation, adoption and native behavior are separate evidence layers.

English/Chinese guides describe one state; fields remain stable and authored content retains its language. Safety includes exact permission, important preimages, provenance, protected-content purposes, stale-input rejection and external writers. Current DPAPI protection is Windows current-user Data Protection API, limiting cross-user recovery. Never manually patch immutable generations or rewrite historical evidence for prose consistency.

## Architecture

MALTS has three cooperating layers:

```text
Core: project/stage/task definitions, operations, evidence, artifacts and recovery
Workflow: canonical Skills, templates, checklists, delivery and Growth methods
Adapters: Codex | Claude Code | OpenCode | DeepSeek Harness
```

The core provides common contracts. Workflows tell an Agent how to use them for a selected goal. Adapters map that shared behavior to the actual Host's loading and tools. One immutable `MALTS_ROOT` contains canonical implementations; tool-local `malts-*` discovery bridges point there rather than carrying competing implementations.

`runtime/EN` supplies canonical Agent templates/checklists; `runtime/CH` supplies Chinese counterparts. `tools/` contains deterministic domain and lifecycle services, `scripts/` user-facing lifecycle entry points, and `docs/` product and operating guides. Runtime state and real deliverables stay in their actual project.

### Capability Governance Boundary

The Capability Registry is metadata over sources and tool overlays, not another Skill repository. Portability, Host compatibility, exposure, review and execution permission are different decisions. An advisory router cannot execute a Skill, mint permission or change discovery. See [Capability and Skill Governance](CAPABILITY_AND_SKILL_GOVERNANCE.md).

The boundaries correspond to different failure modes. A workflow can misunderstand a requirement even when a service transaction is correct; a Host can lose a process while the stored intent remains durable; an intact database can refer to changed business files. Each layer must therefore verify its own inputs instead of using another layer's success as proof.

The implementation places domain services behind a common request dispatcher (`tools/v2_service.py`). CLI and MCP expose these contracts through different permission surfaces. A controller can prepare authorized state changes, while a Host-bound worker endpoint exposes only its configured action set and binds its project/actor identity. Sharing a domain service does not make those two entry points interchangeable authorities.

One canonical Skill body reduces conflicting copies of operating rules. Native discovery bridges still differ because the four Hosts have different configuration/loading conventions. When discovery fails, inspect the bridge, target runtime and actual Host loading separately; copying another tool's files into the root does not resolve the identity chain.

## Activation Model

| Mode | When useful | Expected behavior |
|---|---|---|
| Ordinary single Agent | Small clear work | Follow project rules, finish and verify without automatic MALTS initialization |
| Recoverable MALTS project | Work spans rounds/stages | Preserve goals, current tasks, checks and recovery; reports/handoffs on demand |
| Approved collaboration | Responsibilities/resources can be separated | Review task contracts and Host capacity, integrate actual results |

Installing MALTS, initializing a project, adopting an old workspace and entering existing work are distinct. Selecting a Skill supplies a method, not permission for migration or delegation.

### Long-Project Initialization Completion

`malts-project-init` addresses lightweight project setup; `malts-long-project-workspace-init` establishes a Phase-ready long workspace. A first setup must bind the reviewed Project/plan/first active Phase and report `phase_ready=true`. Root files, an empty store or TASK_ONLY are not complete long-project setup. A Session remains an explicitly bounded operation; ordinary turns and entry create none.

## Task Sizing

Every task should receive a fit-for-process assessment before procedural overhead is added.

| Level | Shape | Default Choice |
|---|---|---|
| S0 trivial | One command, one short answer, typo, simple lookup, small formatting change | Single Agent only |
| S1 bounded | Single file or single behavior with clear verification | Single Agent plus low-overhead growth judgment when justified |
| S2 medium | Multiple files or unclear cause, but still manageable in one bounded round | Single Agent first; consider Explorer or Verifier only if it lowers risk |
| S3 complex | Multi-phase, multi-module, interruption-prone, or likely to exceed comfortable context | Use MALTS state; prepare launch review if multi-agent work has value |
| S4 high-risk or unclear | Destructive operations, permissions, dependencies, build configuration, credentials, durable rules, unclear goal, unclear verification | Resolve material uncertainty or missing authorization first; reuse approved scope and perform relevant checks |

The Agent should explain the expected operational value of multi-agent work before recommending it. If the value is unclear, the execution should remain single-agent.

Choose the level from the work's dependencies, uncertainty, reversibility and recovery value, not the number of files alone. A mechanical rename across many files may stay bounded; a single credential or database migration can require high-risk planning. The classification affects how much context, persistence and verification are useful; it does not issue permissions.

For a module migration, a useful task boundary might be “preserve this public interface while replacing its implementation, with these compatibility checks.” “Read five files” and “write a report” are activities and become standalone tasks only when their output is independently needed. Splitting too finely increases coordination and acceptance bookkeeping without improving the user's result.

If the next step needs a missing decision, stop that dependency and continue separable approved work. For example, uncertain deployment credentials can block deployment while documentation and local verification continue. The same principle prevents one unresolved external effect from being interpreted as permission to restart the entire project.

## Project State Model

Projects define overall/global acceptance, stages bounded delivery, tasks executable outputs. Each accepts proof of its own scope. Task success does not close a stage; stage closure does not finish ongoing maintenance.

Tasks bind goals, inputs, scope, dependencies, acceptance and outputs. Useful decomposition produces checkable results, not maximum task count. Sequence dependencies and assess independent work for parallelism. Distinguish new requirements from approved scope without repeated approval for necessary local repairs.

Current implementation versions definitions and binds tasks to exact stage plans/predecessors to reject stale assumptions. Users need clear goals/progress, not internal IDs. Read current queues/context and locate history by purpose.

Current executable state is persisted through the selected services, not by editing the database directly. A Project records the original/current goal; Phase and Task definitions have revisions and acceptance. Operations, grants, budgets, checkpoints and evidence retain their exact identities. Markdown is useful for narrative plans and original inputs, but cannot override the selected store.

### Long-Workspace Cross-Control Consistency

Before adoption, a workspace follows its verified legacy contract. Adoption explicitly maps original definitions and history into the selected v2 authority and preserves bindings/source seals. Once adopted, do not run legacy Markdown write commands or restore legacy authority. Missing bindings require current recovery, not silent reinitialization.

Versioning makes the meaning of a result explicit. If Task A revision 1 was accepted against interface X, and revision 2 changes the required interface, the old evidence remains historical rather than accepting the new definition. A dependent Task must bind the predecessor revision it actually relies on; choosing “the latest result” without checking that relation can change the dependency silently.

The state model distinguishes definition, execution and presentation. Definitions identify intended work and criteria; Operations record requests and observed effects; evidence records support acceptance; reports present selected facts to a reader. A handoff can summarize all four but owns none of them. This prevents an edited narrative or translation from replacing execution facts.

Plans remain readable project files, but a Phase binds their exact SHA-256. The hash detects byte changes; it does not decide whether the plan is sensible. The controller must still review changed goals, scope, inputs and acceptance, then revise the affected contract and explicitly rebind tasks. See [State Contract](V2_STATE_CONTRACT.md).

## Artifact Matrix

The established templates below remain drafting and review aids. In adopted workspaces, current service records own executable state; a template's filename does not make the resulting Markdown authoritative.

| Artifact | Default Location | Audience | Purpose |
|---|---|---|---|
| Project/Phase/Task service records | Selected workspace store | Agent/controller | Current executable goals, plans, dependencies, effects and acceptance |
| `PROJECT_CONTROL.md` | Project root | Agent-facing narrative/source | Original goal/context or pre-adoption control; not a second writable v2 queue |
| `WORK_TASK_REPORT.md` | Project root | User/Agent-facing derived view | On-demand Phase or final delivery summary; reading view, not v2 execution authority |
| `PROJECT_HANDOFF.md` | Project root | Agent-facing derived view | On-demand continuation summary; reading view, not v2 execution authority |
| `TASK_CONTRACT.template.en.md` | `runtime/EN/templates/` | Agent-facing | Contract for a real sub-agent task |
| `SUB_AGENT_REPORT.template.en.md` | `runtime/EN/templates/` | Agent-facing | Structured result returned by a sub-agent |
| `PROJECT_HANDOFF.template.en.md` | `runtime/EN/templates/` | Agent-facing | Template for fixed recovery handoff |
| `WORK_TASK_REPORT.template.en.md` | `runtime/EN/templates/` | Agent-facing structure, user-facing output | Structure for reports that may be written in the user's language |
| `WORK_TASK_REPORT.template.zh-CN.md` | `runtime/CH/templates/` | Localized reference | Reference for Chinese wording inside on-demand report views or explicit translated views |
| `DELIVERY_CHECKLIST.en.md` | `runtime/EN/checklists/` | Agent-facing | Final or phase delivery self-check |
| `MEMORY_WRITE_CHECKLIST.en.md` | `runtime/EN/checklists/` | Agent-facing | Filter before durable memory or rule writes |
| `QUALITY_GATE.en.md` | `runtime/EN/checklists/` | Agent-facing | General completion gate |

Release templates are starting points. Real project artifacts belong in the user's project workspace, not in this release repository.

The current store additionally records Project/Phase/Task definitions, operations and evidence. Business deliverables remain separate from reports and control records. Artifact ownership, revision and reuse eligibility are maintained through the selected Artifact service. Project-specific outputs never belong inside the installed generation.

A record's location and its responsibility are separate. The state store holds execution facts; a business output such as code or a report is checked at its actual path; an evidence body is retained under its owner/purpose; a template helps draft material but supplies no observed result. Avoid treating all of these as interchangeable “project files.”

Artifact metadata binds content identity, ownership and lineage. Promoting an Artifact to Shared adds a reviewed reuse purpose/scope and qualification; it does not move the payload or make its sensitive content public. A path that happens to be shared by two tasks is not sufficient evidence of a qualified Shared result.

Retirement and recovery can require retaining an output that is no longer current. Before deletion, inspect transitive references and whether another verified source can reconstruct the required bytes. Superseded content may be the only preimage for an interrupted update. The Artifact relation graph therefore informs cleanup but cannot authorize it.

## Bounded Runtime Flow

1. Read the current user goal, applicable instructions and the actual target.
2. Select the simplest useful workflow; initialize only when requested or applicable.
3. For existing MALTS work, verify discovery/binding and current task state.
4. Read the selected goal, plan, dependencies, required evidence and uncertain effects.
5. Resolve material ambiguity; reuse authorization for necessary same-scope steps.
6. Execute the next bounded result and verify the relevant behavior or content.
7. Preserve material decisions, checkpoints and observed results; derive reports/handoffs when needed.
8. Compare results with the original acceptance criteria and retain failed/skipped/unknown work.
9. Assess meaningful experience signals without automatic durable rule writes.
10. Continue required work until the goal is complete or a real stopping condition applies.

MALTS supplies recoverable rounds; it does not extend a context window or automatically watch and save every conversation. Persistence must correspond to the actual effect and checkpoint.

A bounded round has a concrete output and a stopping condition. The controller selects the next eligible task, compares relevant inputs with its contract, executes within scope and records what can be observed. It then evaluates the required check, rather than writing a success label as a substitute. An unresolved effect or decision is itself a checkpoint state, not completed progress.

The durable checkpoint needs enough facts to resume safely: exact task/plan revisions, observed outputs, pending effects, remaining dependencies, the relevant Host and consumed allowance. It need not duplicate every tool message. Persisting only “continue implementation” is insufficient when a file write or provider request may already have occurred.

Valid unchanged evidence can be reused, but its dependencies must remain unchanged. Editing user prose needs affected content/reference checks; changing transaction or permission behavior needs corresponding runtime checks. This makes verification follow risk instead of either rerunning everything or assuming every old result remains valid.

## Context And Continuity

Persist material progress before context exhaustion, compaction, interruption, executor changes or unresolved collaboration creates a risk of losing facts. A continuation must identify the current goal, exact task revision, relevant outputs, failed checks, unknown effects, writers and next eligible action.

Re-enter through current discovery/binding and selected task context. Read a handoff only when it is relevant to this continuation; do not load full history or select a historical Session by recency. If chat and current evidence disagree, investigate the actual state. A summary cannot certify non-execution or repair an incomplete effect.

The successor reconstructs a chain of facts, not the previous Agent's confidence. Start from the selected installation and workspace binding, then locate the current task and checkpoint. Check actual files or service outcomes when those facts decide whether a next action is safe. Historical documents are consulted for a named question, such as why an interface was retained; they are not blanket instructions to rerun a month of work.

Two interruptions require different responses. If a request was prepared but no effect intent was committed, the current operation contract determines whether it can proceed. If intent exists and the receipt is missing, preserve uncertainty and reconcile the original identity. Reconstructing a pleasing summary does not settle that distinction.

Unique manual observations must survive generated-view refresh. A user note about an external editor or a migration decision can be relevant even when it is not a structured field. Preserve it as source data, identify its provenance, and compare current facts before interpreting it as an action.

## Optional Multi-Agent Scheduling

Multi-agent work is a controlled division-of-work mechanism and remains outside the default runtime path.

The Main Controller is the required responsibility owner for a multi-agent round. Every other row below is an optional responsibility lane, not a required role or a mandatory sequence. Select zero, one, or N additional lanes from the work actually needed, the approved scope, non-conflicting ownership, and effective runtime capacity. A role describes responsibility, not model capability or reasoning effort.

The supported responsibility lanes are:

| Role | Participation | Default Permission | Responsibility |
|---|---|---|---|
| Main Controller | Required | Coordination, merge, final judgment | Owns user communication, state, launch review, merge, verification, delivery |
| MALTS Planner | Optional | Read-only advice | Breaks work into tasks, dependencies, priorities, and batches |
| MALTS Explorer | Optional | Read-only | Investigates project structure, logs, modules, or root cause |
| MALTS Worker | Optional | Scoped write access | Implements within a declared file or task boundary |
| MALTS Verifier | Optional | Read-only by default; may run checks | Tests, builds, scans, and validates delivery claims |
| MALTS Memory Curator | Optional | Candidate writes only | Extracts reusable lessons and prepares filtered growth candidates |

Do not create a ceremonial `Planner → Explorer → Worker → Verifier → Memory Curator` chain. A bounded task may use no sub-agent at all, one targeted lane, or multiple independent lanes only when that improves delivery and the authorization and verification contracts permit it.

Additional roles must solve an actual responsibility or verification need.

For real delegation, the controller prepares a concrete review packet and checks existing authorization. A previously approved same-scope batch is not re-approved at each step. The packet includes:

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
- the exact authorization source and unresolved decisions, if any

Honor the user's already specified models and effort without asking for the same preference again. If the runtime does not expose exact model selection or exact inherited model names, that limitation must be recorded as part of the execution evidence.

No sub-agent work may be claimed unless there is visible dispatch evidence from the runtime, such as a tool call, thread ID, agent ID, transcript, or equivalent record.

Single Agent reduces communication/synchronization/integration overhead. Independent exploration/verification and separate modules can help, depending on resources and dependencies.

Delegation declares goals, inputs, scope, outputs, budgets and verification. Editors/files/services/environments/devices can be implicit shared resources. Different directories do not prove independence. Inspect Host execution/stop capabilities before sharing, serialization, exclusion or isolation.

The main Agent checks actual integration. Agreement, success returns and reports are insufficient. Pause/cancel/successor/exit are distinct; uncertainty and consumed allowances survive new rounds.

The scheduling decision depends on both responsibility and resource independence. Independent code review can use a read-only verifier even when implementation must remain serial. Two workers changing separate modules may still share a generated manifest, editor session or database, requiring serialization or a qualified coordination profile.

Prepare a context packet containing the exact requirement, relevant inputs, ownership, allowed effects, budget, output and acceptance. Do not send complete history merely because delegation exists. At return, verify the artifact and required checks against the contract, integrate it with other changes, and only then accept the task. The controller retains responsibility for cross-module behavior.

Parallel execution is a hypothesis about useful separation, not a performance guarantee. Compare completion, verification, integration and repair costs under the actual workload before claiming benefit. A model rating or agreement between workers is not independent business verification.

## Task Contracts And Recovery

A ready task identifies its goal, inputs, allowed/prohibited scope, dependencies, resource ownership, expected output, verification method, budget and any hard Host/model constraints. The controller checks that the current revisions and actual files match that contract.

Returned reports must identify observed outputs, checks, failures and limitations. Reject off-scope or unsupported completion claims; integrate the actual artifact before accepting it. A report's favorable language is not acceptance.

Continue an exact paused Task/Run when its checkpoint, dependencies, pending effects, Host state and budget permit. An interrupted operation is reconciled under its original identity. Restoration uses a new epoch and retains consumed allowances; it revives no old Grant, Host or acceptance and does not restore legacy runtime authority.

Consider a task that updates a configuration file. Its contract identifies the file, required value, current preimage, protected content and the check after writing. An operation binds those parameters to a request hash. If the process stops after intent, the next executor checks that original operation and the observed file; it does not create a second update with a new ID just because the first return message was lost.

Rework also preserves responsibility. A rejected output should identify the unsatisfied criterion and current bytes. Reduce or clarify the task where needed, but do not call a partial result complete or erase the failure. Revisions change the executable contract, while the old request and evidence remain available to explain what happened.

Budgets constrain cumulative effects. Consumption and uncertain use survive pause, new windows and restoration. Recovering state therefore includes accounting for post-backup work and Host observations, not only replacing a database file.

## Verification And Delivery

Completion is an evidentiary claim. It must be supported by verification records rather than subjective confidence.

Before phase or final delivery, the Agent should review `DELIVERY_CHECKLIST.en.md` and record the review in `WORK_TASK_REPORT.md` or the final user-facing report.

A useful delivery statement should include:

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

Record content, ownership, revision, provenance and dependencies separately. Verify current sharing eligibility; old references cannot silently promote superseded/retired artifacts to new content.

Reports explain outputs/evidence; handoffs explain current state/unresolved work/next steps. Derive them on demand and preserve manual content. Publication compares sources/preimages instead of overwriting newer facts. Old hashes do not certify edited reading copies.

Verification must connect a claim to the input it tested. For a code change, file integrity establishes which bytes were checked, while behavior tests establish the interface or output requirement. For a document, source evidence supports factual claims and a link check supports references; neither alone proves that the explanation is sufficient for the user. Installation proof establishes content/entry, while native execution and business acceptance remain separate.

An acceptance record binds the task revision and required criterion. If a relevant dependency changes, preserve the historical record and assess current proof again. Current verification can report NO_LONGER_PROVEN without retroactively declaring the original check fabricated. This is how the system distinguishes historical validity from present applicability.

Delivery reports should state the actual result, how it is used, what was checked and material remaining limits. They should not substitute counts of tests, updates or reports for evidence. A task may be closed only for its declared scope; wider incomplete goals remain visible.

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

### Growth Routing Gate

After verification and before final delivery, every normal task evaluates a no-write L1 Growth Routing Gate. Trivial work without a signal is silent (`NO_OUTPUT`). Non-trivial work or a correction, verification reversal, recovery, failure, or reusable method produces a short visible `LIGHT_REPORT`. Repeated/high-impact evidence, phase delivery, long-task completion, and delivery failure produce `RETROSPECTIVE_RECOMMENDED`; this recommends rather than automatically executes Standard or Major review. Explicitly requested or already authorized review is `RETROSPECTIVE_AUTHORIZED`.

L1 is in-context only and cannot create a ledger, Phase, Session, Artifact, background service, or durable control update. L2 project maintenance and L3 system promotion remain independently authorized. A report-only record does not satisfy user-visible delivery. Applicable Plan/Boundary/transaction/unknown-effect gates run first and may return `BLOCKED`; Growth never bypasses them.

Review begins from actual correction, failed verification, recovery, repeated issues or useful methods. Lightweight routing decides depth; deeper review explains causes, applicability and actions. No-signal success stays quiet.

Candidates specify sources, applicability, actions, checks and withdrawal. The original event proposes a candidate but is not future-use proof. Later tasks need eligible/comparable evidence. Preserve failed/neutral/unknown outcomes; counterevidence/source withdrawal stops affected reuse.

Project recording, trials and global Skill/rule changes have separate permission scopes. Encryption does not authorize public/Growth use; reviewed derivatives and purposes remain necessary. The design supports controlled improvement without presuming benefit.

A reusable proposal needs an action with an applicable trigger and a way to detect harm. “Check schema compatibility before restore” can be a candidate if a real incident supports it; “always do more testing” is too broad to define a trial. Specify the task class, Host/profile, failure signature when relevant, intended behavior, evidence and rollback/withdrawal conditions.

The proposal event and later outcome cannot be merged into one proof. A trial binds the approved operation and its actual request hash; future evidence must represent the eligible workload and independent observations required by the assessment. Replaying one favorable result is not another sample. Neutral and harmful outcomes constrain continued use just as positive ones support a bounded claim.

Global application is a separate decision. Even a validated project candidate does not automatically rewrite a Skill, Prompt or personal rule. Preserve the source lineage and assess the maintenance cost and scope before authorizing a durable destination. The current implementation manages proposals, trials, assessment and retirement; it does not establish automatic productivity improvement.

## MALTS Memory Pipeline

MALTS Memory Pipeline is the durable growth path for reusable lessons. It is independent of any single external memory tool.

The pipeline is:

1. Observe a reusable lesson from delivery, failure, user correction, verification, or process friction.
2. Keep L1 analysis temporary; record it locally only after the matching L2 project authorization exists.
3. Filter it with `MEMORY_WRITE_CHECKLIST.en.md`.
4. Deduplicate against existing rules, skills, and instruction files.
5. Choose the narrowest durable destination: project skill, global skill, `GLOBAL_MEMORY.md`, `AGENTS.md`, `CLAUDE.md`, or an equivalent tool instruction entry.
6. Use an optional external memory system only when one is configured, write-capable, and appropriate.
7. If a durable destination is unavailable, keep the local candidate and report that no long-term write happened.

An experience should become durable memory only when it is real, repeatable, bounded, checkable, and its expected reuse value exceeds the cost of maintaining it.

A listed destination is a possible review outcome, not an automatic implemented write or permission. Current protected evidence requires eligible purposes and reviewed derivatives before reuse; trials retain neutral, harmful and unknown outcomes.

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

Costs include preparation/execution/wait/integration/verification/repair, not only response time. Account for coordination in parallel comparisons; smaller reference sets alone do not prove model token savings.

Bounded reads, valid-evidence reuse and risk-specific checks control overhead. Budgets retain consumption across recovery. Each round ends at a real deliverable, decision, checkpoint or failure condition; complete the goal without unlimited side branches.

A smaller initial reading set reduces the material requested at entry; it does not measure the model's actual reading or provider token accounting. Additional reasoning, tool observations, repetition and integration can offset an apparent reduction. Report observed costs only under their actual collection method and workload.

Use a finite completion definition to control iteration: identify the required result and evidence, resolve defects that affect that result, and defer new core capabilities through an explicit decision. Once the agreed result and relevant checks are complete, further polishing needs a concrete unresolved concern. This prevents governance work from becoming an open-ended task independent of the user's objective.

## Safety And Permissions

Authorization follows the current user request and the actual action. Read-only work does not edit the project. Existing authorization covers necessary same-scope implementation and verification; missing permission for publication, real provider calls, delegation or hard-to-recover actions must be resolved before that dependent step.

A task contract can distinguish read-only investigation, scoped edits, creation, restructuring and destructive effects. These descriptions are not runtime Grant levels. The actual Grant binds an actor, resource, effect, task revision and budget.

Check current Git state where available; preserve user changes and important preimages. Without Git, use scoped backups and recoverable patches. Keep credentials and private evidence out of public outputs. Follow the Host's exact deletion policy; an inventory, old candidate name or favorable completion label is not permission to remove data.

## Unattended Continuation

Unattended or recurring execution is a separately authorized mode. Record the goal, allowed targets/effects, prohibited actions, delegation/model constraints, time or round limits, stop conditions, reporting and recovery method, and the actual continuation mechanism.

MALTS does not automatically install a timer, watch context or grant future work because a long project exists. A scheduler or automation Host retains its own permissions and observed process behavior. A new run cannot replenish a consumed budget. Stop or request a material decision when the agreed boundary is reached.

## Adapter Strategy

| Host | Entry/loading relationship | Installation choice |
|---|---|---|
| Codex | Managed `AGENTS.md`, native Skill bridges and optional MCP | Install/Update `-Tool Codex` |
| Claude Code | Managed `CLAUDE.md`, native commands/agents/Skills | Install/Update `-Tool ClaudeCode` |
| OpenCode | Managed `AGENTS.md` and native config/Skills | Install/Update `-Tool OpenCode` |
| DeepSeek Harness | `.dsh/MALTS_BOOT.md`, native Harness workflow/profile entry | Shared default lifecycle, `-Tool DeepSeekHarness` / `-ToolRootDeepSeekHarness` |

All four use the same core contracts. `AllIncluded` in Install/Update selects all four Hosts. A shared installation has one active generation and registry; Host configuration roots and project state remain separate. See [Install](INSTALL.md) for an executable selection guide.

MALTS owns only marked managed instruction blocks; surrounding text remains user-owned. Merge idempotently, preserve personal content and stop on ambiguous ownership. Reload each Host and check actual native discovery. CLI, Web and Desktop qualification are not interchangeable. Current DeepSeek evidence is scoped to Windows Desktop 0.2.0-rc.2; GUI model cancellation remains uncertified.

## Bilingual Documentation

English and Simplified Chinese product guides describe one product and one state. Keep section purposes, command parameters, paths and limits equivalent. Agent-facing runtime templates retain stable machine fields; narrative project content keeps its authored language.

Use one relevant language during ordinary reading. Structural synchronization checks headings and paths, not semantic translation quality. Correct critical differences against the implementation and review both versions. See [Language Model](BILINGUAL_DOCS.md).

## System Distribution Boundary

MALTS is distributed as a portable operating framework for Agent work: runtime rules, templates, checklists, adapter guidance, installation helpers, and design documentation. A distribution package should contain the reusable system definition and the materials required to install or operate that system in a project environment.

Project-specific state is intentionally outside the system distribution. Actual project control files, work reports, handoff records, local retrospectives, generated packages, caches, and runtime history are execution artifacts created by individual projects. They are governed by the project that produced them, not by the MALTS system definition.

This boundary keeps the system reusable across machines, teams, and Agent runtimes. It also preserves a clear distinction between the MALTS operating model and the records produced when that model is applied to a concrete project.

## MVP Implementation Phases

The minimum delivery comprises an operating model, executable workflows, native adapters, deterministic checks and observed use. These components have dependencies: a workflow needs a defined goal/recovery model; an adapter must resolve its canonical workflow; installation must qualify the exact content; behavior observations must identify the installed implementation and profile.

| Component | Role | Verification obligation |
|---|---|---|
| Goal/state model and templates | Define intent, outputs and recoverable facts | Ownership, scope and current bindings |
| Canonical Skills | Select the method for the actual goal | Trigger, inputs, permission boundaries and references |
| Four native adapters | Connect Host loading/tools to the common core | Exact source/projection, discovery and profile |
| Lifecycle and checks | Install/recover qualified content | Plan hash, preimages, transactions and postchecks |
| Observed project work | Establish a result under real conditions | Business acceptance, interruption and applicable limitations |

Component completion and whole-product acceptance remain separate. Each observation must name its scope; neither static metadata nor a synthetic file example certifies every Host's model behavior. Current implementation/qualification relationships are described in the following acceptance and mechanism sections.

## Acceptance Standard

Acceptance asks whether the agreed result is usable within its stated scope:

- Goals, exclusions, deliverables and current plans remain traceable.
- The selected tasks and dependencies correspond to the actual work.
- Outputs pass the relevant business checks; failures and skipped checks are explicit.
- Interruption/recovery preserves current state, later work and uncertain effects.
- Approved delegation has actual Host evidence and controller integration.
- Reports/handoffs preserve manual content and explain remaining work without becoming authority.
- Experience reuse has eligible sources, applicable trials and a withdrawal path.
- Installation, workspace adoption, native Host behavior and whole-plan acceptance are reported separately.
- Four adapters have installation entries, with actual qualification limits stated.

Installation success, a version label, component tests or an old receipt cannot establish all these claims. Use current task/phase verification for the declared scope. No universal speedup or savings claim follows from acceptance.

## Plan Recheck, Peer Tasks, And Discovery Authority

A current Phase binds the actual plan and its SHA-256; tasks bind exact Phase/dependency revisions. A plan review checks changed goals, boundaries, inputs and recovery conditions. It neither supplies permission nor accepts the business result. Adopted v2 work uses Phase/task services; the old `plan-recheck` command is retained only for its verified pre-adoption contract.

Native peer tasks are Host execution facilities, not a new MALTS project hierarchy. Their actual dispatch, model/effort, settlement and results must match the reviewed contract. Native spawn, another conversation and a managed worker are not interchangeable evidence.

Discovery uses the exact tool Boot and returned registry/active-pointer paths. A machine-global `GLOBAL_BOOT.md` is not a current discovery input. Missing or conflicting identities block the affected runtime operation.

## Current Task Service Mechanisms

The following mechanisms implement those principles. They are technical reference; normal work begins from workflows.

### Responsibilities and authority

Models interpret goals and make business decisions. Hosts provide tools, permissions, process and identity capabilities. MALTS owns state, dependencies, admission, budgets, evidence and recovery contracts. A declaration at one layer cannot substitute for another layer's observed result.

The selected v2 store is the execution source of truth. CLI and MCP call the same domain services through `v2_service.py`. Project/Phase/Task definitions carry revisions, a Phase binds actual plan SHA-256, and Task dependencies bind predecessor revisions. Markdown, reports and handoffs remain interpretable sources/views, without a second writable queue.

Core Schema69 is the exact current read/write format; `runtime/v2_runtime_contract.json` declares it. Editing a version field does not upgrade a development database. An adopted workspace's binding and source seals identify its adoption boundary; removing them cannot restore legacy write authority.

### Execution, concurrency and recovery

A Grant records the authorized actor, resource and effect. Budgets track cumulative consumption; a new Run or restoration is not a new allowance. Admission, leases and fencing reject stale actors through managed interfaces. Fencing requires a current generation/lease identity, not global exclusion of tools outside those interfaces.

An operation is prepared and hash-bound, persists an intent before execution, then records an observation of the actual effect. A missing receipt retains UNKNOWN. UNKNOWN means uncertain effect, not failure, non-execution or permission to retry. Reconciliation continues under the original operation identity.

Managed `create-file` is exclusive. Windows `update-file` compares current opened-file bytes, preserves the preimage, writes and verifies. Conflicts and uncertain results retain their original identity. File adapters prove the declared file result, not unrelated network or editor effects.

Pause, cancellation and process quiescence are separate facts. PAUSED, a cancellation acknowledgement, an empty operation list and lease expiry do not prove external writers stopped. Successors inspect Host state, pending operations, checkpoint, epoch and budget. Restoration creates a new epoch and requires quarantine/reconciliation instead of reviving Grants, Hosts or acceptance.

### Acceptance and evidence

Each criterion specifies description, hard requirement, verification method and minimum evidence level. `verification.begin` enters VERIFYING after effects and Hosts settle and blocks new execution. `verification.rework` retains old evidence while invalidating its current basis. Small tasks can use `task.accept` through the same gate.

Evidence binds a current Task revision, an observed operation in the current epoch, an exact criterion and provenance. A–D evidence levels follow the contract; a lower level cannot impersonate independent or stronger verification. `task-verify` checks current proof without rewriting history. `NO_LONGER_PROVEN` means historical completion is insufficient now.

Protected content lives in blobs with owner, target, sensitivity, allowed purposes and retention descriptors. Current protection uses Windows current-user DPAPI. Encryption is not redaction or permission for Growth. Reviewed derivatives retain lineage; source withdrawal or expiry stops dependent reuse.

### Collaboration, artifacts and improvement

Single Agent is the default. For approved collaboration, the controller separates roles/resources/acceptance, binds an actual Host adapter, budgets and observable identity. Workers deliver results; the controller accepts after Host settlement. Transport IDs are not Tasks, Runs or Grants. Parallel outputs are not integration proof.

Artifact ownership, provenance revision, relationships and retention purposes are distinct from paths. Shared means governed eligibility for cross-task reuse; current content, qualification and dependency closure remain necessary. SUPERSEDED/RETIRED records explain history, without implicit redirection or resurrection.

Growth manages sourced proposals, bounded trials, future outcomes and retirement. Positive self-assessment is insufficient; neutral/harmful outcomes remain. Global Skill/rule changes need their own scope and cannot be inferred from a trial PASS.

### Installation and tradeoffs

Each tool's `MALTS_BOOT.md` identifies an immutable generation. Discovery checks registry, active pointer, identity and VERSION. Hash-bound installation plans capture source and target preimages; isolated preview precedes activation. Manual generation patches break the identity chain. The public repository is the ordinary source; ZIP is optional for offline delivery.

Exact Schema/hash binding improves auditability at the cost of explicit upgrade/adoption/recovery. Protected evidence reduces accidental propagation but limits cross-user recovery. Retained recovery originals support repair and explanation without a bounded-disk-space guarantee. Diagnostic inventories do not authorize deletion.

Skills use bounded routing and `task`, `phase`, `artifact`, `recovery` topics. A smaller reference set does not prove actual model reading behavior or token savings.

The mechanism can be followed through an actual managed-file task: task.revise defines the output and criterion; phase.bind-task identifies the applicable plan; an existing Grant and budget permit operation.prepare; a qualified file adapter commits intent and observes the effect; verification establishes the requested proof; task.accept records acceptance after effects and Hosts settle. Each step rejects a mismatch at its own boundary.

This sequence trades some explicit state management for inspectable recovery. A service cannot infer an external business result merely because a file adapter succeeded, and a model cannot bypass a failed boundary with a rewritten summary. When a step is blocked, inspect its value-free error code and the current contract instead of guessing another action name or widening the endpoint.

The maintained action contracts can be queried through capabilities. Detailed procedures and examples are in [Controller Operations](V2_PREVIEW_USAGE.md), with [State Contract](V2_STATE_CONTRACT.md) defining the current format and authority boundaries.

## Verification Scope And Limitations

Implementation is in `tools/v2_state_store.py`, `v2_governance.py`, `v2_operations.py`, `v2_local_host.py`, `v2_acceptance.py`, `v2_evidence_derivation.py`, `v2_artifacts.py`, `v2_growth.py`, `v2_handoff.py` and `malts_lifecycle.py`. Code explains mechanisms; observed checks establish behavior.

Recorded evidence covers domain/transaction/permission/recovery checks, managed files, representative native tasks and cold recovery, limited serial/parallel comparisons, future Growth trials and installation/adoption/backup restoration. Each proves its own layer. One complete fixed A/C pair observed less automatic time and reported input/output with more tool items. B1's original failed observer profile remains and is not a complete comparator. Neutral real Growth pairs demonstrate bounded trial/withdrawal behavior, not automatic benefit.

Uncertified claims include population success rates, universal/cross-Host causal speedups, actual money/human savings, provider-internal request totals, GUI model cancellation, arbitrary-OS fencing, cross-user DPAPI restoration and autonomous publication. These limits explain evidence scope without changing Task acceptance standards.

See [Usage](USAGE.md) and the [State Contract](V2_STATE_CONTRACT.md) for operations and exact state boundaries.
