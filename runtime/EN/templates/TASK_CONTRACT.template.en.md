# TASK_CONTRACT

> Purpose: define one dispatchable task clearly enough that a sub-agent can execute it without expanding scope.

## Task Identity

- Task ID:
- Responsibility lane: Planner / Explorer / Worker / Verifier / Memory Curator / Other
- Priority: P0 / P1 / P2 / P3
- Status: READY
- Assigned by: Main Controller

## Runtime, Model, And Effort Policy

- Runtime / adapter: Codex / Claude Code / OpenCode / Other
- Dispatch mechanism: e.g. Codex `spawn_agent`
- Model policy: Inherit current main-controller session / Explicit model / Runtime default
- Runtime effort policy: Inherit / Explicit runtime effort ID / Runtime default
- Normalized reasoning tier: none / light / standard / deep / maximum / unknown
- Display label, if exposed:
- Cross-tool sync expectation for gap-filling tasks: Codex + Claude Code + OpenCode unless user-scoped otherwise / N/A
- User-visible model name or policy:
- User model specification source: User specified / User chose inherit / Default inherit after review
- Explicit model, if any:
- Reason for explicit model, if any:
- Reason for explicit effort, if any:
- Route evidence reference:
- Requested selection:
- Recommended selection:
- Configured selection:
- Effective selection:
- Constraint strength: model=hard|soft|none; effort=hard|soft|none; delegation=hard|soft|none; concurrency=hard|soft|none
- Runtime binding status: effective_verified / fallback_verified / configured_unverified / static_binding / inherited / unsupported / unknown
- Runtime test state: behavior_verified / integration_verified / discovery_verified / provider_unconfigured / runtime_unsupported / not_run
- Effective concurrency / depth:
- Fallback reason and usage evidence, if any:
- Launch review reference and approved batch ID:
- Expected runtime agent ID source: tool-call return / runtime log / N/A
- Included in launch review packet: Yes / No / N/A
- User confirmed launch with `确认运行`: Yes / No / N/A

## Objective

- Mission objective:
- Success criteria:
- Non-goals:

## Context Packet

- User goal summary:
- Relevant current state:
- Known decisions:
- Known risks:
- Related files or resources:

## Scope

- Allowed to read:
- Allowed to modify:
- Prohibited from modifying:
- Resource locks:

## Definition Of Ready

- [ ] Goal is clear.
- [ ] Required context is available.
- [ ] Allowed reads and writes are clear.
- [ ] Prohibited changes are clear.
- [ ] Dependencies are met.
- [ ] No file or resource ownership conflict exists.
- [ ] Expected output format is clear.
- [ ] Verification method is clear.
- [ ] Runtime, model, effort, evidence quartet, constraint strength, and binding policy are clear.
- [ ] Role names describe responsibility and do not hard-code task difficulty or reasoning effort.
- [ ] If Agent count is N, effective or verified-fallback binding and effective runtime capacity are recorded.
- [ ] For protocol, template, checklist, adapter, or documentation gap-filling tasks, Codex, Claude Code, and OpenCode sync scope is clear.
- [ ] If this task is part of a user-requested multi-agent run, it was shown in the launch review packet and the user confirmed `确认运行`.

## Permission Level

- Level 0: read-only.
- Level 1: may modify specified files.
- Level 2: may add files but not delete files.
- Level 3: may restructure only with main controller approval.
- Level 4: high-risk operation; requires user confirmation.

Selected level:

## Required Output

Return a structured report using the `SUB_AGENT_REPORT` format.

Must include:

- Runtime agent ID, if provided by the runtime.
- Effective model and runtime effort, if known; otherwise state the exact configured/inherited policy and mark effective use unknown.
- Requested / recommended / configured / effective route evidence and binding status.
- What was done.
- Files changed, if any.
- Verification performed.
- Unverified items.
- Risks or blockers.
- Decisions required from the main controller.

Planner tasks must also include:

- Suggested task split.
- Dependencies and priority.
- Which tasks are READY.
- Which tasks are too large, too small, or should be merged.
- Suggested batch size and reason.

## Verification Requirement

- Required command or check:
- Minimum acceptable evidence level: A / B / C
- If verification cannot be run:

## Escalation Rules

Escalate to the main controller if:

- The task scope is unclear.
- You need to modify prohibited files.
- You discover a serious out-of-scope issue.
- Verification fails and the reason is unknown.
- Your conclusion conflicts with another agent's conclusion.
- You need to delete, overwrite, or restructure files.

## Safety Rules

- You are not the only agent in the project.
- Do not roll back or overwrite unknown changes.
- Do not expand the task scope on your own.
- Do not claim completion without verification evidence.
- Treat assumptions as assumptions, not facts.
