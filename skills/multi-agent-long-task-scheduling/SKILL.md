---
name: multi-agent-long-task-scheduling
description: Assess, run, or recover an explicitly requested MALTS long-task scheduling workflow. Multiple files, potential parallelism, or architecture discussion alone do not trigger scheduling.
---

# Skill: Multi-Agent Long-Task Scheduling

## Select the current authority

First use the selected workspace's verified entry. An adopted v2 workspace or explicitly selected isolated v2 store uses the [v2 task workflow](../v2/malts-v2-task-workflow/SKILL.md) and [controller Host protocol](../../docs/V2_PREVIEW_USAGE.md#v2-collaboration). Do not initialize or migrate because parallelism looks possible. Review-only work changes no state; an authorized single-Agent continuation creates no dispatch. Multi-Agent execution needs corresponding existing or newly granted scope, a qualified actual Host adapter and available cumulative budget.

For v2 dispatch, the trusted controller prepares the exact Task revision/strategy and budget-bound contract, supplies matching effect Grants, launches once and polls the original dispatch. Worker tools remain Task/Run-bound; they cannot launch successors, mint Grants or accept their own active dispatch. Dependencies require current applicable evidence; accepted local outputs do not prove integration. A cancellation acknowledgement, root-process exit, expired lease or transport failure does not prove all writers stopped or unresolved effects vanished. Reconcile original Host/effect identities before authorized takeover, preserving consumed budget and late-result provenance. If the selected Host cannot establish the required isolation or quiescence, use the approved serialized/isolated alternative or report the specific unresolved requirement.

The fit assessment and authorization principles below remain useful. The Markdown Project/Phase/Session templates, legacy routing/dispatch records and control-file procedures below are only for a verified pre-adoption workspace; do not create a second writable authority for v2. Consult the selected runtime's actual capabilities rather than treating this Skill or an adapter declaration as native Host qualification.

## Purpose

Use this skill for a requested scheduling assessment, execution workflow, or recovery of an approved scheduling run. MALTS is single-agent first. Multi-agent work is a controlled division-of-work mechanism enabled only when needed; every real sub-agent dispatch requires an explicit launch review first.

This skill does not exist to spawn more agents. It exists to reduce loss of control.

## Trigger

Use this skill only when one of these is true:

- The user explicitly requests recoverable long-task scheduling, or the current request continues that approved workflow.
- The user requests an assessment or launch plan for multi-agent coordination; use the read-only branch below.
- A previously authorized MALTS scheduling run needs recovery or reconciliation.

Do not use this skill when:

- The task is small enough for the main controller to finish directly.
- The scheduling cost is higher than the likely benefit.

Unclear requirements, verification methods, or subtask boundaries prevent dispatch, not already authorized fact-finding or a requested assessment. Ordinary maintenance in an opted-in workspace uses its current-set entry and existing controls without invoking this scheduler.

## Select the applicable branch

- **review-only / REVIEW_ONLY:** Read the supplied goal and necessary current evidence, use Multi-Agent Fit Assessment, and return benefits, coordination costs, unresolved material decisions and a proposed scope. Do not create/update controls, run dispatch routing, prepare durable Agent logs, or dispatch. Completion is the requested assessment, not a launched workflow; stop this Skill after that result.
- **single-agent / SINGLE_AGENT_RUN:** Continue the authorized long task in the Main Controller. Reuse existing Project/Phase controls and their plan; create controls only when setup is actually requested and needed. Skip sub-agent contracts, routing, launch packets, dispatch and recycling steps. Verify the work and persist material recovery deltas under the normal workspace contract.
- **multi-agent / DISPATCH_AGENTS:** Follow the execution and dispatch sections with the approved launch scope, required permissions, resource ownership and effective route evidence. Existing same-scope authorization remains usable.

The capability descriptor's permission routes separate these branches. Resolver eligibility is advice, not a grant or proof of execution. The workflow and checklist below apply only to steps used by the selected branch; do not read every template or checklist for an assessment.

## Multi-Agent Fit Assessment

Before suggesting or enabling multi-agent scheduling, classify the task by type and difficulty. Multi-agent exists to stabilize long work, reduce loss of control, and improve independent verification; it does not exist to maximize agent count.

| Level | Task Shape | Default Action |
|---|---|---|
| S0 trivial | One command, one small answer, formatting, translation, or simple lookup | Stay single-agent. Do not suggest multi-agent. |
| S1 contained | One file or one narrow behavior with clear verification | Stay single-agent with lightweight growth. |
| S2 moderate | Several files, uncertain cause, or useful independent verification, but still manageable in one round | Prefer single-agent; suggest multi-agent only if read-only exploration or verification can reduce risk. |
| S3 complex | Multi-stage, multi-module, interruption-prone, or likely to exceed comfortable context | Prepare a bounded launch plan when delegation helps. Dispatch only within corresponding user authorization; reuse an already approved batch. |
| S4 high-risk or unclear | Material uncertainty or a real security, data, permission or external-effect boundary | Investigate discoverable facts first. Continue independent approved work; pause only the affected action for missing decision-changing information or authorization. A dependency, build-config or long-term-rule edit is not an automatic stop. |

Positive signals for suggesting multi-agent:

- Independent read-only exploration can run in parallel.
- Independent verification would materially reduce delivery risk.
- Worker tasks have non-conflicting file ownership.
- The task needs recoverable state across rounds.
- The task is likely to exceed comfortable single-session context.

Negative signals:

- Requirements or verification are unclear.
- Subtask boundaries cannot be defined.
- Merge cost is likely higher than execution benefit.
- The main controller can complete the next step faster and more safely.

When delegation would help and is not yet authorized, briefly explain its purpose, scope and cost and request that authorization. If the user already approved the same launch scope, prepare the required contracts and proceed without another confirmation.

## MALTS-Native Grill-Me Preflight

Use `skills/grill-me-preflight/SKILL.md` when the user requests an interview or inspection leaves a material unresolved decision. Complexity levels, multiple files and project starts do not automatically trigger it.

Ask a concrete decision-changing question directly. Offer a structured interview only when several connected decisions need it; reuse the current request when the user already asked for that interview.

When goals and acceptance criteria are clear, proceed without a preflight offer at any complexity level. Group independent questions when useful and sequence dependent questions. Keep real delegation authorization separate; an interview does not grant it.

## Runtime Document Loading

- Read English runtime documents by default: `EN/` directories and `.en.md` files.
- Do not load Chinese copies during normal execution.
- Read Chinese documents only when the user explicitly requests reading, reviewing, editing, comparing, or Chinese-English synchronization.

## Inputs

- User original goal.
- Current project files and constraints.
- `PROJECT_CONTROL.md`, if it exists.
- Relevant EN templates:
  - `PROJECT_CONTROL.template.en.md`
  - `TASK_CONTRACT.template.en.md`
  - `SUB_AGENT_REPORT.template.en.md`
- Relevant EN checklists:
  - `QUALITY_GATE.en.md`
  - `DELIVERY_CHECKLIST.en.md`

## Core Principles

1. The main controller owns responsibility, judgment, merging, and delivery.
2. Planner suggests; it does not own final scheduling decisions.
3. Explorer is read-only.
4. Worker modifies only assigned files or resources.
5. Verifier checks independently and does not claim delivery ownership.
6. Memory Curator records growth candidates without polluting long-term memory.
7. Completion without verification is not completion.
8. Completion not checked against user goals is not real completion.
9. Each fact has one authority: `PROJECT_CONTROL.md` owns Project facts and indexes; the selected Phase owns Phase goal/queue/evidence/plan/recovery; an explicit Session owns only its bounded checkpoint; runtime coordination owns Admissions, queues, fencing, and quarantine. Reports and handoffs are projections.
10. Process serves delivery; do not keep scheduling after the core goal is complete.
11. Do not claim multi-agent validation unless sub-agent task contracts were dispatched and sub-agent reports were recycled.
12. Do not claim a sub-agent ran unless the real runtime dispatch mechanism was used and recorded.
13. Sub-agent routing is provider-neutral and respects the user-selected model/effort and established host configuration. Use the verified configured route when it meets the task contract. Recommend a different route only for a concrete capability, cost or hard-constraint reason; record requested/configured/effective evidence without inventing runtime identity.
14. Role describes responsibility, not difficulty. Select model and effort from task complexity, risk, budget, runtime support, and evidence; do not hard-code an effort merely because a lane is called Planner, Worker, or Verifier.
15. Reuse already specified model/effort choices and same-scope delegation authorization. Explain optional route choices only when unresolved choices materially affect the result or budget; do not routinely ask the user to choose a model or repeat a launch confirmation.
16. For shared protocol, template, checklist, adapter or documentation changes, inspect the affected Codex, Claude Code, OpenCode and EN/CH surfaces. Update only affected counterparts and record a tool-specific non-applicability without requiring a new exception approval.
17. Long-task continuity is implemented through the smallest authoritative current set. If context saturation, compaction, interruption, or handoff risk appears, persist the material delta in its owning Project/Phase/Session record before expanding work; refresh a report/handoff only when requested or materially useful.
18. Report task/Phase outcomes to the user, but do not rewrite a durable work report for a round with no material reporting delta. CURRENT reports are on-demand derived views; legacy workspace compatibility bindings remain strict until explicit reorganization. Render user-facing status in the user's explicit language, then the workspace `NarrativeLanguage`, then English fallback. Chinese output includes Chinese meaning plus the stable English code in full-width parentheses.
19. Do not promise a fixed one-shot runtime such as "guaranteed 8 hours." Design long work as recoverable rounds.
20. Continuing the currently authorized task is distinct from scheduled or unattended execution. Do not ask an unattended-mode question at every start. Enable unattended operation only when the user requested or approved it and its scope, bounds and recovery mechanism are recorded.
21. If unattended continuation needs a new multi-agent batch that was not already reviewed and confirmed, stop and ask for the normal launch review confirmation.
22. Standalone task or tool artifacts must keep their boundary explicit. Do not register a one-off artifact as a system entry, shared tool, or index item unless the user asks for that scope.
23. Cross-window continuation starts with read-only `workspace-entry --task-class CONTEXT_RECOVERY` and its bounded current-set paths. Escalate to cold `recover` only when entry blocks or the gate is recovery-sensitive. Do not load a report, handoff, or full history merely because it exists, and never select the latest historical Session by time or list order.
24. Safety-critical canonical, authorization, Plan, Admission/fencing, unknown-effect, and transaction drift is `BLOCKED` for the affected authority/resource. CURRENT derived report/handoff drift is `WARNING` and locally refreshable; legacy workspace layout current projection drift retains its blocking compatibility behavior.

## Role Model

| Role | Responsibility | Default Permission |
|---|---|---|
| Main Controller | Goal, status, dispatch, merge, final judgment | Full project coordination |
| MALTS Planner | Task split and dependency suggestions | Read-only |
| MALTS Explorer | Read-only discovery | Read-only |
| MALTS Worker | Bounded implementation | Assigned write scope only |
| MALTS Verifier | Independent check | Read-only plus allowed verification commands |
| MALTS Memory Curator | Retrospective candidates | Candidate writes only |

## Workflow

1. Read the user goal, the current-set entry result and only the EN references needed by the selected branch.
2. Reuse existing canonical controls; initialize or update only what the authorized execution actually needs.
3. Lock the user original goal field.
4. Define completion criteria and acceptance criteria.
5. Build or refresh the task queue.
6. If the request actually includes unattended operation, reuse its authorization package or obtain the missing authorization for that operation. Otherwise continue the current task without an unattended-mode prompt.
7. Resolve only material remaining decisions; use Preflight if requested or useful for connected choices, otherwise continue with N/A. Record decisions only in their existing owner control.
8. Run the Multi-Agent Fit Assessment and decide whether to stay single-agent, suggest multi-agent, or ask for clarification.
9. Use the specified or configured model and effort when they satisfy the approved contract. Resolve only material gaps; routine route selection does not require a separate user interview.
10. Prepare task contracts and a user-visible launch review packet. When the selected Phase owns a plan, require a `BEFORE_LAUNCH_REVIEW` Plan Recheck against its current bytes/revision/scope; a previously recorded trigger is evidence, not an equality precondition. For legacy workspace layout, retain strict report/handoff consistency checks.
11. Verify that the launch scope is covered by the user request or an existing approval. Obtain permission only if that authorization is missing or the launch expands it.
12. Dispatch only READY tasks with clear task contracts after confirmation.
13. Record each real dispatch in the Agent Dispatch Log, including runtime agent ID and model policy when available.
14. Recycle sub-agent reports.
15. Record each returned result in the Agent Feedback Log before merging it.
16. Reject or re-dispatch reports that are unstructured, off-scope, or unverified.
17. Merge valid results.
18. Run quality gate and delivery checks.
19. Update only the authoritative control that owns a material state delta; do not mirror Phase/Session facts into `PROJECT_CONTROL.md`.
20. Update the canonical recovery record before context compaction, interruption, or handoff risk; refresh derived views only on demand.
21. Review concrete Growth signals or an explicitly requested retrospective; ordinary success alone does not require a candidate or report.
22. If a Growth review ran, report its useful result and whether it stayed local, became a candidate, or passed the applicable memory-write checks.
23. Route actual, filtered Growth results through the MALTS Memory Pipeline only within its authorization.
24. If a long-term memory target or optional external memory tool is unavailable, preserve the candidate locally in project state or the work task report and do not claim a completed long-term write.
25. For protocol, template, checklist, adapter, or documentation gap-filling tasks, verify whether the same fix must be applied to Codex, Claude Code, and OpenCode.
26. Provide or refresh `WORK_TASK_REPORT.md` only when the user requests a durable report or a material delivery/recovery need justifies it. In CURRENT contract it is a derived non-authoritative view; use the user's or project's primary language for narrative content, keep English status/evidence fields stable, and create a full translated mirror only when explicitly requested.
27. If unattended auto-continue is authorized, check round caps and stop conditions before starting another round.
28. Continue the next round or deliver with verified risks.

## Dispatch Rules

Before dispatch, every task must have:

- Task ID.
- Clear objective.
- Allowed reads.
- Allowed writes.
- Prohibited modifications.
- Expected output format.
- Verification requirement.
- Escalation rules.
- Dispatch mechanism, runtime agent ID source, model and effort policy, runtime binding status, and route evidence reference.

Use `TASK_CONTRACT.template.en.md` for dispatch.

Before any real dispatch, the main controller must present a launch review packet to the user. It must include:

- Overall goal and total plan.
- The applicable user-selected or configured model/effort and any material unresolved route choice; ask a question only when the decision is needed.
- Provider-neutral route details when needed, for example `implementation=model-id@medium; verification=model-id@max`. Omitted choices use the established configuration if it satisfies the contract.
- Planned dispatch order or parallel batches.
- Each planned responsibility lane's task objective, short plan, permission level, requested/recommended/configured/effective model-and-effort evidence, and whether the choice is user-specified, inherited, configured, or a verified fallback.
- Any runtime limitation, such as an inherited model whose exact name is not exposed.
- The authorization reference for the launch scope, including whether an existing approval already covers this batch.

For Claude Code, OpenCode, or any non-Codex runtime, record the runtime-specific visible sub-agent invocation, transcript, command output, or log reference. Do not invent a dispatch proof or model override that the installed runtime does not expose.

In Codex, native `spawn_agent` is the preferred dispatch surface when it can satisfy the approved contract. Reuse the user-selected or configured model and effort; valid inheritance is allowed when the runtime supports it and no hard constraint is violated. Record unsupported constraints and request a decision only when necessary. Configured values remain separate from observed effective values.

### Codex Peer-Task Route

When native sub-agent dispatch cannot satisfy a user-approved hard model or effort constraint, Codex may use a user-visible peer task only if the official Codex task/thread interface exposes the requested route. The Codex task/thread API is the execution surface; MALTS supplies authorization, task contracts, evidence, lifecycle, recovery, acceptance, and archival governance. This is not native `spawn_agent`, and its dispatch record must say `codex-peer-task` with `delegation_mode=peer-task`.

Follow the host's separate-task authorization contract. If it requires an explicit user request to create or fork a visible task, general delegation approval or a model constraint is not a substitute. The user-approved launch scope must cover that visible task and any later archival action.

Apply these rules:

1. Resolve the current project and follow the host's workspace default or the user's explicit choice. Use a same-directory fork only when requested and permitted; do not override a host's default isolated worktree by assumption. Never hard-code a workspace name. Record and verify the actual assigned directory and its relationship to the source project.
2. Create a user-visible task, give it a descriptive title, then send the bounded task contract through the official follow-up interface with the approved model and effort override. The task remains user-owned and visible in the Codex sidebar.
3. Record requested, recommended, configured, and effective route evidence separately. A successful task creation or configured override alone is not effective-use proof; capture returned task metadata, in-task/runtime evidence, working directory, and usage evidence.
4. A hard model, effort, delegation, or no-fallback constraint fails closed on mismatch or unavailable effective evidence. Do not silently fall back to native spawn, inherited/default routing, another model, another workspace, or a projectless task.
5. Keep default concurrency at the approved minimum. Every peer task still needs a conflict-free locator lease; a same-directory task does not gain broader read/write permission.
6. Reuse the same peer task for report clarification or rework. Do not create a new task merely to retry a response unless the existing task is unusable and the approved batch permits replacement.
7. Drive and record the lifecycle exactly: `PLANNED -> CREATED -> RUNNING -> RETURNED -> ACCEPTED | REWORK | BLOCKED -> ARCHIVED`. `REWORK` returns to `RUNNING`; archive only after Main Controller acceptance, terminal block, or explicit closure.
8. Persist task/thread ID, parent task reference, title, current workspace, contract/report/evidence paths, timestamps, route binding, lifecycle transitions, Main Controller decision, rework count, and archive result in the current Phase evidence and Agent logs.
9. Waiting, reading, follow-up, and archive operations are orchestration actions, not proof that the report is correct. Main Controller must still reconcile the report against current files and acceptance criteria.

Use a peer task only as this governed provider-specific route inside the existing multi-agent Skill. Do not create a separate peer-task Skill or represent independent task windows as hidden child Agents.

## Role Assignment Protocol

Multi-agent dispatch assigns roles by responsibility, not by count. Stacking the same role across all tasks defeats the purpose of a role model.

### Dynamic Responsibility Lanes

The Main Controller always owns authorization, merge, final judgment, and delivery. Every other role is an optional responsibility lane selected from the work actually needed. A phase may use zero, one, or N sub-agents; it does not follow a mandatory fixed chain.

- `0`: keep work in the Main Controller for S0/S1 tasks, unclear boundaries, unavailable authorization, unsupported runtime, or merge cost greater than benefit.
- `1`: assign one bounded exploration, implementation, or independent-verification lane when that materially reduces risk.
- `N`: use multiple conflict-free lanes only within the minimum of approved Agent count, contract concurrency, and effective runtime capacity.

MALTS Planner, MALTS Explorer, MALTS Worker, MALTS Verifier, and MALTS Memory Curator remain responsibility names. Their presence, order, and count are determined by dependencies and acceptance criteria, not by a fixed ceremony.

### Role Boundaries

| Role | Does | Does Not |
|---|---|---|
| MALTS Planner | Read plan, confirm edit locations, flag ambiguity | Modify files, dispatch agents, claim delivery |
| MALTS Explorer | Discover structure, find patterns, report facts | Modify files, make decisions |
| MALTS Worker | Edit assigned files within contract scope | Expand scope, modify prohibited files, delete without authorization |
| MALTS Verifier | Independently check correctness, consistency, completeness | Fix issues, modify files (unless reassigned as MALTS Worker) |
| MALTS Memory Curator | Extract, filter, and propose growth candidates | Write long-term memory without checklist, modify project files |

### Assignment Rules

1. Use the minimum number of lanes that improves the result; zero sub-agents is a valid routed outcome.
2. Under default `single_phase`, scheduling remains single-open-Phase and creates no coordination state. Under opt-in CURRENT `resource_admission`, every write lane must hold a valid Admission for its typed locators/capabilities, exact Phase hash, actor, lease expiry, and fencing epochs. Read/read sharing is allowed; overlapping writes fail closed or queue according to declared capability policy.
3. When independence is a hard acceptance requirement, the Verifier must be a different Agent instance from the work it verifies; if authorization or runtime evidence is missing, block rather than pretend independence.
4. Planner and Explorer are always read-only. Never grant them write access.
5. Memory Curator runs only when verified evidence exists and a growth review is actually warranted.
6. Do not create placeholder lanes or assign unused roles merely to reach a count.

### Resource Admission Rules

Every resource Admission and any incomplete workspace transaction remains independently governed and must be reconciled before claiming completion.

- Declare `PATH`, `ARTIFACT`, `RECORD`, `SERVICE`, `DEVICE`, or `ENVIRONMENT` locators and any `SHARED`, `EXCLUSIVE`, `QUEUED`, or `ISOLATE_REQUIRED` capability in the task contract. Do not encode tool-specific business rules in MALTS Core.
- Exact and parent/child paths conflict; declared aliases join conflict domains. Non-fenceable exclusive tools serialize, while isolate-required work needs a distinct isolation key.
- Lease renewal is explicit; MALTS starts no heartbeat daemon. A stale actor or old fencing epoch cannot continue writing. Verify Admission immediately before each governed mutation and include tokens in the returned report.
- `UNKNOWN` external effects quarantine only affected domains unless workspace authority/recovery itself is uncertain. Continue unrelated admitted work, but require explicit evidence-backed reconcile before reusing quarantined domains.
- Workspace and coordination authority mutations share one unique-writer lock with a post-lock exact-preimage check. A task contract or prompt cannot substitute for this runtime enforcement.

### Anti-Patterns

- Dispatching only Workers and calling it multi-agent.
- Claiming independent Agent verification when the same Agent performed both work and review; ordinary single-agent tests and self-review remain valid evidence within their limits.
- Treating Planner as mandatory when the Main Controller already has a verified plan.
- Running Memory Curator before Verifier has confirmed delivery.

## Batch Size Rules

- Explorers may run in parallel when they are read-only.
- Workers may run in parallel only when file ownership does not conflict.
- Compute batch size dynamically; do not use a fixed Worker-count default.
- If the task type is new or risky, run one pilot task first.
- If merge cost exceeds execution benefit, downgrade to single-agent mode.

## Runtime Route Evidence

Before relying on a model, effort, fallback, or N-agent capacity, record all four route selections: `requested`, `recommended`, `configured`, and `effective`. Keep the runtime effort ID, normalized reasoning tier, and display label separate because runtimes may expose different IDs for similar labels.

Create `agent-task-requirements` for actual delegated lanes. Reuse the user-selected or established configured route when it satisfies the approved hard constraints. Run `agent_route_planner.py` against `runtime/agent-routing/model_effort_policy.json` and verified runtime/model-profile evidence when a material route or policy decision remains. Its `ECONOMY`, `BALANCED`, `ADVANCED` and `FLAGSHIP` classes are cost/risk recommendations, not permission to override the user's model or effort. Preserve approved hard policy and budget constraints; inheritance is usable when its effective evidence and approved requirements match. Missing or conflicting hard requirements need a focused decision, not an automatic fallback.

Classify each route as one of `effective_verified`, `fallback_verified`, `configured_unverified`, `static_binding`, `inherited`, `unsupported`, or `unknown`. Configuration, CLI help, and interface discovery are not proof of effective use. Only direct behavior/return/log evidence plus usage evidence may support `effective_verified` or `fallback_verified`.

- Hard model, effort, delegation, or concurrency constraints fail closed when the effective route differs.
- A changed soft constraint may use a fallback only when the reason and effective evidence are recorded.
- `N > 1` requires effective or verified-fallback bindings and a non-null effective runtime concurrency value.
- `agent_route_planner.py` is advisory and `result_controller.py` is authorization-aware; neither component dispatches an Agent.
- Real Agent/provider behavior and the G4 runtime gate remain `NOT RUN` until a separate launch review is approved.

## User-Facing Status Language

- Keep JSON fields, lifecycle enums, error codes, model IDs, and evidence identifiers in stable English.
- Render user-facing status through `malts_user_tools.py render-user-status` or the shared status catalog semantics.
- Explicit user language wins, followed by workspace `NarrativeLanguage`, then English fallback.
- For Simplified Chinese, write the Chinese meaning first and preserve the original stable code in full-width parentheses, for example `已返回（RETURNED）`. Never send a Chinese user an unexplained English-only status chain.
- Use the installed responsibility display names `MALTS Planner`, `MALTS Explorer`, `MALTS Worker`, `MALTS Verifier`, and `MALTS Memory Curator`. When the runtime exposes a stable ID, show both, for example `MALTS Worker（malts_worker）`.
- A Chinese-facing dispatch row follows this shape: `MALTS Worker（malts_worker） / 已计划（PLANNED） / 推荐：<model-id>@<effort> / 已配置（CONFIGURED） / 有效路由未知（UNKNOWN）`. Replace each status through the shared renderer; never claim the effective model before runtime evidence exists.

## Recycling Rules

When a sub-agent returns, the main controller must check:

- Did it answer the assigned task?
- Did it stay inside scope?
- Did it modify prohibited files?
- Did it provide verification evidence?
- Did it report the runtime agent ID and model policy when available?
- Are risks and unfinished items stated?
- Does the result map to the acceptance criteria?
- Do the Agent Dispatch Log, task contract, returned report, and Agent Feedback Log agree on task ID, role, runtime agent ID, model policy, and main-controller decision?

Use `SUB_AGENT_REPORT.template.en.md` for returned results.

## Failure Handling

If a task fails:

1. Mark the task as `FAILED` or `BLOCKED` in its authoritative owner-local queue: the selected `PHASE_CONTROL.md` for Phase work, or an explicit `SESSION_CONTROL.md` only when that Session owns the bounded task. `PROJECT_CONTROL.md` receives only a Project-level decision or index delta; do not mirror the task status there.
2. Record the failure type: requirement deviation, implementation error, verification failure, environment issue, scope violation, or scheduling failure.
3. Decide whether to retry, split smaller, serialize, ask the user, or stop.
4. Do not deliver failed work as completed.
5. Add a growth candidate if the failure reveals a reusable avoidance mechanism.

## High-Risk Operations

Check the operation's actual effects against the approved scope and relevant data, credential, concurrency and recovery requirements. A backup or other safety mechanism does not grant permission. Destructive operations, permission or credential changes, global-rule edits and external effects require their corresponding authorization. Routine dependency, build or configuration edits already inside the approved task do not create a new approval gate by filename alone. Pause only the action whose scope, authorization or safe preconditions remain unresolved.

## Documentation Sync Cost Policy

- For ordinary EN/CH documentation sync, start with scripts or structured checks for file pairs, heading gaps, path/version drift, and key protocol terms.
- Use low-cost model/agent workers only to generate candidate translations, gap fills, and formatting patches when the runtime supports model choice; otherwise record the inherited/default runtime limitation.
- Low-cost workers cannot approve, merge, or mark critical protocol semantics as verified.
- Keep high-capability model/agent or main-controller review focused on critical protocol semantics: scope-based launch authorization, unattended execution, permissions, long-term memory, cross-tool sync, sub-agent dispatch/model policy, safety boundaries, final merge approval, and final risk judgment.
- Work reports must record source files, target files, sync direction, model/cost strategy, script check results, low-cost candidate scope, high-capability/main-controller approval scope, and unreviewed risks.
- If high-capability/main-controller approval is missing for critical semantics, mark the result `Draft` or `Unverified`; do not mark it done.
- Do not claim low-cost processing or high-capability review unless the runtime evidence or manual review actually occurred.

## Token Control

- Do not load both EN and CH documents.
- Do not open sub-agents for small tasks.
- Give each sub-agent only a task-specific Context Packet.
- Keep `PROJECT_CONTROL.md` compact.
- End each round with a short state compression.
- Persist state before starting a new broad read, sub-agent batch, or risky edit when context is near saturation.
- Treat compaction or interruption as recoverable from files, not as permission to restart from memory.
- Stop when the delivery value no longer improves meaningfully.

## Artifact And Directory Boundary

- When a task creates, deletes, moves, renames, or changes the purpose of a folder, record whether the folder is a project/system entry, a trial-run workspace, a user-facing deliverable, or a standalone task artifact.
- Standalone task artifacts stay in their own directory and are documented locally. They are not added to global `README`, handoff indexes, `tools/`, or adapter docs unless the user explicitly asks to promote them.
- If a directory becomes a system entry, shared tool, adapter asset, or documented workflow location, update the relevant index and usage docs before delivery.
- If a workspace contains unexpected Skill or installation copies, identify their owner, intended scope and current references. Preserve legitimate project-specific Skills. Global promotion, installation/synchronization and removal are separate actions requiring a concrete target and corresponding authorization; otherwise record the finding and preserve the content.
- At recovery time, the host first loads applicable instructions, then runs `workspace-entry` and reads its returned bounded current-set paths: runtime current binding, selected/primary Phase, active Session only when one exists, and required coordination state. Project control is loaded by an explicit Project-level, review, or recovery gate; reports/handoffs are loaded only for reporting/handoff work or an explicit recovery need. Continue only from verified current facts; do not fall back to the newest historical Session.

## Runtime Duration And Round-Based Continuity

- There is no reliable fixed maximum for a single uninterrupted run.
- Treat runtime in three layers:
  - Single chat window / context: continues only until context, runtime, tool-call, or session limits.
  - Single work round: a bounded batch that ends with verification and any material authoritative state update; a durable work report is on demand, not automatic.
  - Whole long task / project: can continue across sessions as long as external state is current.
- The practical rule is: do not try to make one window run forever; make every round recoverable, verifiable, and continuable.

## Unattended Auto-Continue

Discuss unattended auto-continue only when it is requested or materially needed beyond the current active task. Reuse an existing matching authorization package. Without that authorization, do not schedule or start unattended execution; continue the already approved active task normally.

The authorization package must include:

- Authorized objective.
- Allowed files, directories, commands, and action types.
- Prohibited operations.
- Whether multi-agent dispatch is allowed while unattended.
- Sub-agent model policy if multi-agent dispatch is allowed.
- Maximum rounds and practical time cap. This is a safety limit, not a guaranteed runtime.
- Per-round report location or summary behavior.
- Stop conditions.
- Recovery point to resume from.
- Runtime mechanism: Codex heartbeat/cron automation, verified Claude Code/OpenCode equivalent, or manual resume.

Allowed unattended work:

- Read approved project documents and files.
- Continue approved edits inside scope.
- Run approved verification commands.
- Update only the authoritative Project/Phase/Session fields and task contracts that materially changed; refresh report/handoff projections only when the authorization package requires them.

Stop and ask the user when:

- A new multi-agent launch needs review and was not already confirmed.
- A proposed model, tool, dependency, scope, permission or long-term-rule change would exceed the approved action/resource/budget boundary or violate a hard constraint. Ordinary implementation choices inside that boundary can proceed.
- A high-risk operation lacks the required authorization, verified preconditions or recovery evidence.
- Verification fails and the remaining repair choice would materially change requirements, permissions, cost or irreversible effects. Otherwise diagnose and retry safely within the approved scope.
- The goal conflicts with later user input or cannot map to acceptance criteria.
- Recovery state is missing or inconsistent.

Each unattended round must run bounded entry, read only the current authoritative set, do the next approved step, verify, persist material owner-local state, then check stop conditions before another round. It must not rewrite timestamps or derived views when nothing changed.

## Output

At delivery, report:

- Conclusion.
- Completed work.
- Modified files or deliverables.
- Verification evidence.
- Risks and unfinished items.
- How to use the result.
- Recovery point and continuation path.
- Growth candidates, if any.
- Local fallback location if memory writing failed or the target was unavailable.

## Checklist

- [ ] User original goal is captured.
- [ ] Completion definition exists.
- [ ] Task queue exists.
- [ ] File ownership is clear.
- [ ] Material decision gaps were resolved; Preflight was used only when requested or needed. A clear task proceeded without a routine interview.
- [ ] Unattended operation, if used, has explicit matching authorization; no routine mode question interrupted active approved work.
- [ ] Sub-agent tasks have contracts.
- [ ] Launch review packet was shown after the user requested multi-agent mode.
- [ ] Each real dispatch is covered by the corresponding user request or approved batch; no fixed confirmation phrase is required.
- [ ] Each real dispatch is recorded with dispatch mechanism, agent ID when available, and model policy.
- [ ] Each recycled sub-agent result is recorded before merge.
- [ ] Dispatch logs, task contracts, reports, and feedback logs agree before claiming validation.
- [ ] Any claim of multi-agent validation is backed by dispatched contracts and recycled reports.
- [ ] Verification evidence exists before DONE.
- [ ] Safety-critical structural/binding/deterministic consistency is clean and no incomplete workspace/coordination transaction remains. legacy workspace layout report/handoff bindings retain exact compatibility checks; CURRENT derived-view drift is classified as warning and refreshed only when needed.
- [ ] Every CURRENT resource-profile write lane has a valid Admission, current Phase hash, unexpired lease, exact fencing tokens, and resolved quarantine state; default single-profile work has no coordination overhead.
- [ ] Main controller performed final acceptance mapping.
- [ ] Risks are transparent.
- [ ] Growth candidates are filtered before long-term memory writes.
- [ ] Failed or unavailable memory writes are preserved as local candidates and reported honestly.
- [ ] Long-task runtime was treated as bounded rounds, not as a fixed one-shot runtime promise.
- [ ] If unattended auto-continue was used, explicit authorization, round caps, stop conditions, recovery updates, and per-round reports are recorded.
