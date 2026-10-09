# TASK_CONTRACT

> Purpose: define one dispatchable task clearly enough that a sub-agent can execute it without expanding scope.

## Task Identity

- Task ID:
- Responsibility lane: MALTS Planner / MALTS Explorer / MALTS Worker / MALTS Verifier / MALTS Memory Curator / Other
- Priority: P0 / P1 / P2 / P3
- Status: READY
- Assigned by: Main Controller

## Runtime, Model, And Effort Policy

- Runtime / adapter: Codex / Claude Code / OpenCode / DeepSeek Harness / Other
- Dispatch mechanism: e.g. Codex `spawn_agent`
- Delegation mode: main / single-agent / sub-agent / nested / peer-task
- Parent task/thread reference, if peer-task:
- Current-project same-directory route and verified workspace, if peer-task:
- Peer-task lifecycle state: PLANNED / CREATED / RUNNING / RETURNED / ACCEPTED / REWORK / BLOCKED / ARCHIVED / N/A
- Rework reuse and archival rule, if peer-task:
- Model policy: Cost-aware recommended route / Exact inherit only when cost class matches / Explicit user model / Runtime default
- Runtime effort policy: Cost-aware recommended effort / Exact inherit only when cost class matches / Explicit runtime effort ID / Runtime default
- Normalized reasoning tier: none / light / standard / deep / maximum / unknown
- Display label, if exposed:
- Cross-tool sync expectation for gap-filling tasks: Codex + Claude Code + OpenCode + DeepSeek Harness unless user-scoped otherwise / N/A
- User-visible model name or policy:
- User model specification source: User specified / User chose exact inherit / Cost-aware recommendation / Runtime default after capability check
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
- User authorization covers this launch scope: Yes / No / N/A

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
- Governance profile: `single_phase` / `resource_admission` / N/A
- Admission ID / exact Phase-control SHA-256 / actor ID: `N/A`
- Typed locator requests (`PATH` / `ARTIFACT` / `RECORD` / `SERVICE` / `DEVICE` / `ENVIRONMENT`):
- Capability requests (`SHARED` / `EXCLUSIVE` / `QUEUED` / `ISOLATE_REQUIRED`):
- Lease expiry and required fencing epochs: `N/A`
- Isolation key, when required: `N/A`
- Quarantine/reconcile precondition: `CLEAR` / evidence reference / N/A

## Definition Of Ready

- [ ] Goal is clear.
- [ ] Required context is available.
- [ ] Allowed reads and writes are clear.
- [ ] Prohibited changes are clear.
- [ ] Dependencies are met.
- [ ] No file or resource ownership conflict exists.
- [ ] A resource-profile writer has a granted Admission, current Phase hash, unexpired lease, exact fencing tokens, and clear quarantine state; otherwise this is N/A.
- [ ] Expected output format is clear.
- [ ] Verification method is clear.
- [ ] Runtime, model, effort, evidence quartet, constraint strength, and binding policy are clear.
- [ ] Role names describe responsibility and do not hard-code task difficulty or reasoning effort.
- [ ] If Agent count is N, effective or verified-fallback binding and effective runtime capacity are recorded.
- [ ] For protocol, template, checklist, adapter, or documentation gap-filling tasks, Codex, Claude Code, OpenCode, and DeepSeek Harness sync scope is clear.
- [ ] This task is covered by the user request or an approved launch batch; authorization is semantic and does not require a fixed confirmation phrase.

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
- Admission verification, fencing tokens, release/reconcile result, and any `UNKNOWN` external-effect evidence when resource governance applies.
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
