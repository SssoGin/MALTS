---
name: multi-agent-long-task-scheduling
description: Use when the user explicitly enables multi-agent long-task scheduling, or when a complex long task needs recoverable state, task contracts, sub-agent dispatch, verification, and delivery control.
---

# Skill: Multi-Agent Long-Task Scheduling

## Purpose

Use this skill to make long, complex, or interruption-prone projects recoverable, verifiable, mergeable, and deliverable. MALTS is single-agent first. Multi-agent work is a controlled division-of-work mechanism enabled only when needed; every real sub-agent dispatch requires an explicit launch review first.

This skill does not exist to spawn more agents. It exists to reduce loss of control.

## Trigger

Use this skill only when one of these is true:

- The user explicitly enables MALTS, long-task mode, or multi-agent long-task scheduling.
- The task is multi-stage, multi-file, or likely to exceed a comfortable single-session context.
- Independent exploration, implementation, or verification can run in parallel without file conflicts.
- The project needs recoverable state, batch execution, growth/memory records, and acceptance-ready delivery.

Do not use this skill when:

- The task is small enough for the main controller to finish directly.
- Requirements are unclear.
- The verification method is unclear.
- Subtask boundaries cannot be defined.
- The scheduling cost is higher than the likely benefit.

## Multi-Agent Fit Assessment

Before suggesting or enabling multi-agent scheduling, classify the task by type and difficulty. Multi-agent exists to stabilize long work, reduce loss of control, and improve independent verification; it does not exist to maximize agent count.

| Level | Task Shape | Default Action |
|---|---|---|
| S0 trivial | One command, one small answer, formatting, translation, or simple lookup | Stay single-agent. Do not suggest multi-agent. |
| S1 contained | One file or one narrow behavior with clear verification | Stay single-agent with lightweight growth. |
| S2 moderate | Several files, uncertain cause, or useful independent verification, but still manageable in one round | Prefer single-agent; suggest multi-agent only if read-only exploration or verification can reduce risk. |
| S3 complex | Multi-stage, multi-module, interruption-prone, or likely to exceed comfortable context | Suggest preparing a multi-agent launch review packet. Do not dispatch before `确认运行`. |
| S4 high-risk or unclear | Ambiguous requirements, unclear verification, security/permissions/dependencies/build config/long-term rules, or destructive operations | Stop for clarification or approval first. Use Planner/Explorer/Verifier only after confirmation; Worker requires explicit scope. |

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

When the task is a good candidate, tell the user why and offer to prepare the launch review packet. Phrase the recommendation as a checkpoint, for example: "This task is a multi-agent candidate because it needs independent exploration and verification. I recommend preparing a launch review packet; no sub-agent will be dispatched unless you reply `确认运行`."

## MALTS-Native Grill-Me Preflight

Before implementation on S2/S3/S4 work, new projects, design-heavy tasks, migrations, workflow/protocol changes, or unclear requirements, offer `skills/grill-me-preflight/SKILL.md` as a MALTS-native clarification gate.

Explain that it exposes hidden assumptions, goal boundaries, key tradeoffs, and acceptance criteria before implementation, reducing rework and requirement mismatch. Do not auto-run it; ask the user first.

This preflight is not multi-agent dispatch and does not require `确认运行`. Skip it for S0/S1 tasks where the goal and verification path are already clear. If accepted, ask one decision-changing question at a time, include a recommended answer, and record accepted decisions and assumptions in `PROJECT_CONTROL.md`.

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
9. `PROJECT_CONTROL.md` is the single source of truth for current project state.
10. Process serves delivery; do not keep scheduling after the core goal is complete.
11. Do not claim multi-agent validation unless sub-agent task contracts were dispatched and sub-agent reports were recycled.
12. Do not claim a sub-agent ran unless the real runtime dispatch mechanism was used and recorded.
13. Sub-agent model policy is explicit: use the user-specified model when provided; otherwise inherit the current main-controller session model.
14. When the user asks to use multi-agent mode, ask whether they want to specify sub-agent models, explain the specification format, show the launch review packet, and wait for explicit `确认运行` before dispatching any sub-agent.
15. For any gap-filling update to protocols, templates, checklists, adapters, or docs, check and synchronize Codex, Claude Code, and OpenCode together unless the user explicitly scopes one tool out.
16. Long-task continuity is implemented through external state. If context saturation, compaction, interruption, or handoff risk appears, update `PROJECT_CONTROL.md`, task contracts, reports, and recovery notes before expanding the work.
17. After each completed MALTS task or phase, write or append a plain work task report for the user, including the growth review result and memory-write decision when the phase is non-trivial, corrective, failed, or recovery-related.
18. Do not promise a fixed one-shot runtime such as "guaranteed 8 hours." Design long work as recoverable rounds.
19. At long-task start, ask whether the user wants to enable unattended auto-continue. It requires explicit authorization recorded in `PROJECT_CONTROL.md`; without that authorization, unattended auto-running is forbidden and the system must stop at user checkpoints.
20. If unattended continuation needs a new multi-agent batch that was not already reviewed and confirmed, stop and ask for the normal launch review confirmation.
21. Standalone task or tool artifacts must keep their boundary explicit. Do not register a one-off artifact as a system entry, shared tool, or index item unless the user asks for that scope.
22. Cross-window or cross-project continuation starts from external state: project instructions, latest `PROJECT_CONTROL`, latest `WORK_TASK_REPORT` or handoff, and current files. If that state is missing or stale, update it before continuing.

## Role Model

| Role | Responsibility | Default Permission |
|---|---|---|
| Main Controller | Goal, status, dispatch, merge, final judgment | Full project coordination |
| Planner | Task split and dependency suggestions | Read-only |
| Explorer | Read-only discovery | Read-only |
| Worker | Bounded implementation | Assigned write scope only |
| Verifier | Independent check | Read-only plus allowed verification commands |
| Memory Curator | Retrospective candidates | Candidate writes only |

## Workflow

1. Read the user goal and current EN runtime documents.
2. Create or update `PROJECT_CONTROL.md`.
3. Lock the user original goal field.
4. Define completion criteria and acceptance criteria.
5. Build or refresh the task queue.
6. Ask whether the user wants to enable unattended auto-continue and record the answer in `PROJECT_CONTROL.md`.
7. Offer MALTS-native Grill-Me Preflight for non-trivial or unclear starts, unless it is clearly N/A, and record offered/accepted/declined/N/A.
8. Run the Multi-Agent Fit Assessment and decide whether to stay single-agent, suggest multi-agent, or ask for clarification.
9. Ask whether the user wants to specify sub-agent models and show the accepted format.
10. Prepare task contracts and a user-visible launch review packet.
11. Wait for the user's explicit `确认运行`.
12. Dispatch only READY tasks with clear task contracts after confirmation.
13. Record each real dispatch in the Agent Dispatch Log, including runtime agent ID and model policy when available.
14. Recycle sub-agent reports.
15. Record each returned result in the Agent Feedback Log before merging it.
16. Reject or re-dispatch reports that are unstructured, off-scope, or unverified.
17. Merge valid results.
18. Run quality gate and delivery checks.
19. Update `PROJECT_CONTROL.md`.
20. Update recovery notes before context compaction, interruption, or handoff risk.
21. Record growth candidates.
22. Make growth visible to the user: report the review level, reusable lesson if any, and whether the lesson stayed local, became a candidate, or passed the memory-write checklist.
23. Route filtered decisions and growth results through the MALTS Memory Pipeline.
24. If a long-term memory target or optional external memory tool is unavailable, preserve the candidate locally in project state or the work task report and do not claim a completed long-term write.
25. For protocol, template, checklist, adapter, or documentation gap-filling tasks, verify whether the same fix must be applied to Codex, Claude Code, and OpenCode.
26. Provide a user-facing work task report. Use `WORK_TASK_REPORT.template.en.md` as the Agent-facing structure source; the actual report should follow the user's language preference or project language.
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
- Dispatch mechanism, runtime agent ID source, and model policy.

Use `TASK_CONTRACT.template.en.md` for dispatch.

Before any real dispatch, the main controller must present a launch review packet to the user. It must include:

- Overall goal and total plan.
- A direct question asking whether the user wants to specify any sub-agent model.
- Model specification instructions, for example: `Planner=gpt-5.4-mini; Explorer=inherit; Verifier=inherit; default=inherit`.
- Planned dispatch order or parallel batches.
- Each planned agent's role, task objective, short plan, permission level, model name or model policy, and whether the model is user-specified or inherited/default.
- Any runtime limitation, such as an inherited model whose exact name is not exposed.
- A clear statement that no sub-agent will be dispatched until the user replies `确认运行`.

For Claude Code, OpenCode, or any non-Codex runtime, record the runtime-specific visible sub-agent invocation, transcript, command output, or log reference. Do not invent a dispatch proof or model override that the installed runtime does not expose.

In Codex, `spawn_agent` is the visible dispatch proof. If the user does not specify a sub-agent model, do not pass a model override and record `Model: inherited from current Codex session`. If the user specifies a model, pass it explicitly when the runtime supports that model.

## Role Assignment Protocol

Multi-agent dispatch assigns roles by responsibility, not by count. Stacking the same role across all tasks defeats the purpose of a role model.

### Standard Dispatch Chain

Planner → Worker → Verifier → Memory Curator → Main Controller

Each phase follows this chain:
1. Planner confirms scope before any edit begins.
2. Worker executes only within confirmed scope.
3. Verifier independently checks results.
4. Memory Curator extracts reusable candidates after delivery.
5. Main Controller owns merge, final judgment, and user-facing delivery.

### Role Boundaries

| Role | Does | Does Not |
|---|---|---|
| Planner | Read plan, confirm edit locations, flag ambiguity | Modify files, dispatch agents, claim delivery |
| Explorer | Discover structure, find patterns, report facts | Modify files, make decisions |
| Worker | Edit assigned files within contract scope | Expand scope, modify prohibited files, delete without authorization |
| Verifier | Independently check correctness, consistency, completeness | Fix issues, modify files (unless reassigned as Worker) |
| Memory Curator | Extract, filter, and propose growth candidates | Write long-term memory without checklist, modify project files |

### Assignment Rules

1. At least two distinct roles per phase beyond Main Controller.
2. Worker batch size: 1–3. Parallel Workers must have non-overlapping file ownership.
3. Verifier must be a different agent instance from the Worker it verifies.
4. Planner and Explorer are always read-only. Never grant them write access.
5. Memory Curator runs after verification, never before.
6. A role not needed for the current phase must be explicitly recorded as "Not assigned" with reason.

### Anti-Patterns

- Dispatching only Workers and calling it multi-agent.
- Having the same agent verify its own work.
- Skipping Planner because "the plan is already written."
- Running Memory Curator before Verifier has confirmed delivery.

## Batch Size Rules

- Explorers may run in parallel when they are read-only.
- Workers may run in parallel only when file ownership does not conflict.
- Default Worker batch size is 1 to 3.
- If the task type is new or risky, run one pilot task first.
- If merge cost exceeds execution benefit, downgrade to single-agent mode.

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

1. Mark the task as FAILED or BLOCKED in `PROJECT_CONTROL.md`.
2. Record the failure type: requirement deviation, implementation error, verification failure, environment issue, scope violation, or scheduling failure.
3. Decide whether to retry, split smaller, serialize, ask the user, or stop.
4. Do not deliver failed work as completed.
5. Add a growth candidate if the failure reveals a reusable avoidance mechanism.

## High-Risk Operations

Require confirmation or a safety mechanism before:

- Deleting files.
- Changing permissions.
- Changing dependencies.
- Changing build configuration.
- Overwriting configuration.
- Touching authentication, secrets, or security-sensitive code.
- Changing long-term rules such as `AGENTS.md`, `CLAUDE.md`, or global skills.

## Documentation Sync Cost Policy

- For ordinary EN/CH documentation sync, start with scripts or structured checks for file pairs, heading gaps, path/version drift, and key protocol terms.
- Use low-cost model/agent workers only to generate candidate translations, gap fills, and formatting patches when the runtime supports model choice; otherwise record the inherited/default runtime limitation.
- Low-cost workers cannot approve, merge, or mark critical protocol semantics as verified.
- Keep high-capability model/agent or main-controller review focused on critical protocol semantics: `确认运行`, unattended execution, permissions, long-term memory, cross-tool sync, sub-agent dispatch/model policy, safety boundaries, final merge approval, and final risk judgment.
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
- Standalone task artifacts stay in their own directory and are documented locally. They are not added to global `README`, handoff indexes, `output/tools`, or adapter docs unless the user explicitly asks to promote them.
- If a directory becomes a system entry, shared tool, adapter asset, or documented workflow location, update the relevant index and usage docs before delivery.
- If a project workspace accidentally contains global skills or tool install copies, first verify the correct Agent global paths, promote or copy missing items there if appropriate, then remove or document the project copies. Do not leave unexplained agent-style skill folders in a task workspace.
- At recovery time, a new window or another project folder should first read the project instruction entry, the latest `PROJECT_CONTROL`, the latest work task report or handoff, and the directory guide when one exists. Continue only from facts recorded there, not from memory alone.

## Runtime Duration And Round-Based Continuity

- There is no reliable fixed maximum for a single uninterrupted run.
- Treat runtime in three layers:
  - Single chat window / context: continues only until context, runtime, tool-call, or session limits.
  - Single work round: a bounded batch that ends with state update, verification, and a work task report.
  - Whole long task / project: can continue across sessions as long as external state is current.
- The practical rule is: do not try to make one window run forever; make every round recoverable, verifiable, and continuable.

## Unattended Auto-Continue

At long-task start, ask whether the user wants to enable unattended auto-continue. It is allowed only when the user explicitly authorized it and `PROJECT_CONTROL.md` contains the authorization package. Without explicit authorization, do not start, schedule, or rely on unattended automatic running.

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
- Update `PROJECT_CONTROL`, task contracts, reports, recovery notes, and work task reports.

Stop and ask the user when:

- A new multi-agent launch needs review and was not already confirmed.
- Model, tool, scope, dependency, permission, or long-term rule changes are needed.
- A high-risk operation is needed.
- Verification fails and there are multiple plausible repair paths.
- The goal conflicts with later user input or cannot map to acceptance criteria.
- Recovery state is missing or inconsistent.

Each unattended round must re-read `PROJECT_CONTROL`, do only the next approved bounded step, verify, update state and reports, then check stop conditions before another round.

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
- [ ] MALTS-native Grill-Me Preflight was offered for non-trivial or unclear starts, or N/A was recorded.
- [ ] At long-task start, the user was asked whether to enable unattended auto-continue and the answer was recorded.
- [ ] Sub-agent tasks have contracts.
- [ ] Launch review packet was shown after the user requested multi-agent mode.
- [ ] User explicitly replied `确认运行` before any real dispatch.
- [ ] Each real dispatch is recorded with dispatch mechanism, agent ID when available, and model policy.
- [ ] Each recycled sub-agent result is recorded before merge.
- [ ] Dispatch logs, task contracts, reports, and feedback logs agree before claiming validation.
- [ ] Any claim of multi-agent validation is backed by dispatched contracts and recycled reports.
- [ ] Verification evidence exists before DONE.
- [ ] Main controller performed final acceptance mapping.
- [ ] Risks are transparent.
- [ ] Growth candidates are filtered before long-term memory writes.
- [ ] Failed or unavailable memory writes are preserved as local candidates and reported honestly.
- [ ] Long-task runtime was treated as bounded rounds, not as a fixed one-shot runtime promise.
- [ ] If unattended auto-continue was used, explicit authorization, round caps, stop conditions, recovery updates, and per-round reports are recorded.

