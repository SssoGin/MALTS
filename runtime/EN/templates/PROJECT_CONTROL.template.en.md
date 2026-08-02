# PROJECT_CONTROL

> Purpose: single source of truth for the current project state when MALTS is enabled.
> Language policy: keep this as the only canonical control file by default. Keep `MALTS:section` markers, status values, identifiers, paths, and commands stable; visible headings and narrative content may use the user's or project's primary language. Do not create a full translated mirror unless the user explicitly asks for one.
> Do not create MALTS control files for every trivial task by default. Create or reuse this file when the user enables MALTS, long-task scheduling is active, or a normal task grows complex enough to require recoverable state.

<!-- MALTS:section=metadata -->
## Metadata

- Project:
- Control version: <MALTS_VERSION>
- Version source: resolve `MALTS_BOOT.md` first, then read the active `MALTS_ROOT` `VERSION`; do not copy a physical generation path or current MALTS version from old control/report/handoff/template files.
- Current round:
- Last updated:
- Project owner: Main Controller
- Current mode: Single-Agent / Multi-Agent Long-Task

## Language And Structure

Use this section to make the control-file language policy explicit.

- Canonical control file: `PROJECT_CONTROL.md`
- Body language: English / Simplified Chinese / project language / mixed
- Stable fields: keep headings, table headers, status values, task IDs, evidence levels, paths, and commands machine-readable.
- Optional translated mirror: none by default; create only when explicitly requested.
- Source-of-truth policy: `PROJECT_CONTROL.md` remains authoritative if an optional translated mirror exists.

<!-- MALTS:section=user-original-goal -->
## User Original Goal

> Locked field. Paste or quote the user's original goal. Do not rewrite this field without explicit confirmation.

## Later User Changes

- Change:
- Time:
- Impact:

<!-- MALTS:section=current-interpreted-goal -->
## Current Interpreted Goal

- Current understanding:
- Confirmed exclusions:
- Open questions:

## Grill-Me Preflight

Use this for non-trivial task or project starts.

- Applies to this task: Yes / No / N/A
- Offered to user: Yes / No / N/A
- User decision: Accepted / Declined / N/A
- Benefits explained: hidden assumptions / goal boundaries / key tradeoffs / acceptance criteria / reduced rework
- Decisions resolved by preflight:
- Remaining open questions:

<!-- MALTS:section=completion-definition -->
## Completion Definition

This project is complete only when:

- [ ] The user's core goal is met.
- [ ] Required deliverables exist.
- [ ] Key changes are listed.
- [ ] Verification evidence is recorded.
- [ ] Known unfinished items are stated.
- [ ] Risks are transparent.

<!-- MALTS:section=acceptance-criteria -->
## Acceptance Criteria

| Requirement | Verification Method | Status | Evidence |
|---|---|---|---|
|  |  | TODO / PASS / FAIL / N/A |  |

<!-- MALTS:section=current-stage -->
## Current Stage

- Stage:
- Active Phase:
- Stage goal:
- Exit condition:

<!-- MALTS:section=plan-recheck-index -->
## Plan Recheck Index

- Active plan: `N/A`
- Active Phase owner: `N/A`
- Plan revision: `N/A`
- Plan content SHA-256: `N/A`
- Latest recheck trigger: `N/A`
- Latest recheck result: `N/A`
- Launch review invalidated: `No`

<!-- MALTS:section=task-queue -->
## Task Queue

Status values: TODO, READY, IN_PROGRESS, REVIEW, DONE, BLOCKED, FAILED, CANCELLED.

| ID | Priority | Status | Owner | Task | Dependencies | Allowed Changes | Verification |
|---|---|---|---|---|---|---|---|
| T001 | P0 | TODO | Main Controller |  | None |  |  |

<!-- MALTS:section=file-ownership -->
## File Ownership

| Path / Resource | Owner | Allowed Operation | Locked Until | Notes |
|---|---|---|---|---|
|  |  | Read / Write / Verify |  |  |

## Artifact And Directory Boundary

Use this when work creates, deletes, moves, renames, or changes the purpose of a folder, tool, output package, or standalone artifact.

- New or changed artifacts/directories:
- Boundary type: System entry / Shared tool / Trial-run workspace / User deliverable / Standalone task artifact / N/A
- Should global indexes or manuals be updated: Yes / No / N/A
- Index/manual/docs checked:
- Boundary decision and evidence:

## Cross-Tool Synchronization Check

Use this section for protocol, template, checklist, adapter, or documentation gap-filling tasks.

- Applies to this task: Yes / No
- Codex checked: Yes / No / N/A
- Claude Code checked: Yes / No / N/A
- OpenCode checked: Yes / No / N/A
- User explicitly scoped out any tool:
- Unsynchronized gaps and reason:

## Multi-Agent Fit Assessment

Use this before suggesting or enabling multi-agent mode.

- Task difficulty level: S0 trivial / S1 contained / S2 moderate / S3 complex / S4 high-risk or unclear
- Task type:
- Positive multi-agent signals:
- Negative multi-agent signals:
- Recommended runtime mode: Single-Agent / Suggest Multi-Agent Launch Review / Ask Clarification
- Recommended dynamic Agent count: 0 / 1 / N
- Independent verification required by acceptance contract: Yes / No
- Runtime route evidence state: effective_verified / fallback_verified / configured_unverified / static_binding / inherited / unsupported / unknown
- Reason:
- User was informed of recommendation: Yes / No / N/A
- User confirmation required before dispatch: `确认运行`

## Multi-Agent Launch Review

Use this before any real sub-agent dispatch after the user asks to use multi-agent mode.

- Overall goal:
- Total plan:
- Model-and-effort specification prompt shown: Yes / No
- Model-and-effort prompt deviation accepted: Yes / No / N/A
- How to specify routes: `responsibility=model-id@runtime-effort; responsibility=inherit@runtime-default; default=inherit@runtime-default`
- User model and effort choices:
- Launch review reference:
- Approved batch IDs:
- Route evidence reference:
- Requested / recommended / configured / effective selection:
- Runtime effort ID / normalized reasoning tier / display label:
- Constraint strength: model=hard|soft|none; effort=hard|soft|none; delegation=hard|soft|none; concurrency=hard|soft|none
- Binding status and test state:
- Effective concurrency / depth:
- Fallback reason and usage evidence, if any:
- Planned dispatch order / parallel batches:
- User confirmation phrase required: `确认运行`
- Confirmation status: Pending / Confirmed / Revised / Cancelled

| Responsibility Lane | Task ID | Model + Runtime Effort Policy | Route Evidence / Binding | Task Objective | Short Plan | Permission Level |
|---|---|---|---|---|---|---|
| Planner / Explorer / Worker / Verifier / Memory Curator / Other |  | Explicit / Inherited / Runtime default | requested / recommended / configured / effective; binding status |  |  | Level 0 / 1 / 2 / 3 / 4 |

## Agent Dispatch Log

Record every real sub-agent dispatch. If no sub-agent was dispatched, write `N/A`.

| Time | Round | Batch ID | Task ID | Responsibility | Dispatch Mechanism | Runtime Agent ID | Effective Model / Effort | Binding Status | Contract / Route Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|---|
|  |  |  |  | Planner / Explorer / Worker / Verifier / Memory Curator / Other | native spawn / `codex-peer-task` / other |  | Known value / Unknown | effective_verified / fallback_verified / other |  | PLANNED / CREATED / RUNNING / RETURNED / ACCEPTED / REWORK / BLOCKED / ARCHIVED |

## Agent Feedback Log

Record each recycled sub-agent result before merging it into project progress.

| Time | Task ID | Runtime Agent ID | Role | Feedback Reference | Main Controller Decision | Reason |
|---|---|---|---|---|---|---|
|  |  |  |  | Inline summary / Report path | Accepted / Partially Accepted / Rejected / Redispatched |  |

<!-- MALTS:section=decisions -->
## Decisions

| Time | Decision | Reason | Alternatives | Risk |
|---|---|---|---|---|
|  |  |  |  |  |

<!-- MALTS:section=verification-records -->
## Verification Records

Evidence levels:

- A: real command/test/build/run result.
- B: static check, syntax check, file existence check.
- C: code or document review.
- D: speculation; cannot prove completion.

| Time | Target | Method | Result | Evidence Level | Notes |
|---|---|---|---|---|---|
|  |  |  | PASS / FAIL / NOT RUN | A / B / C / D |  |

## Deliverables

| Deliverable | Purpose | Status | Verification Method | User Action Needed |
|---|---|---|---|---|
|  |  | Draft / Usable / Verified / Release / Accepted |  |  |

<!-- MALTS:section=risks-and-blockers -->
## Risks And Blockers

| ID | Type | Description | Impact | Mitigation | Status |
|---|---|---|---|---|---|
| R001 |  |  |  |  | Open / Mitigated / Accepted |

## Exception Handling

| Trigger | Detection Method | Response | Retry Limit | Escalation |
|---|---|---|---|---|
| Sub-agent timeout / incomplete output / scope violation / verification failure |  | Retry / Split / Serialize / Ask User / Stop |  |  |

## User Checkpoints

| Checkpoint Type | Trigger | Required User Decision | Status | Notes |
|---|---|---|---|---|
| Multi-Agent Launch Confirmation / Phase Confirmation / Blocking Decision / Abnormal Report / High-Risk Operation / Unattended Auto-Continue Authorization |  |  | Pending / Done / N/A |  |

## Runtime Duration And Round Strategy

No fixed one-shot runtime is guaranteed. Use this section to design long work as bounded, recoverable rounds.

- Unattended auto-continue prompt shown at task start: Yes / No
- User answer:
- Single chat / context limit expectation:
- Current round exit condition:
- Whole-project continuation strategy:
- Next state write checkpoint:

## Result Contract

Project terminal status has exactly four values: `DONE`, `PARTIAL`, `BLOCKED`, and `FAILED`. Internal execution status is not an additional terminal.

- Contract / result ID:
- Execution status: DRAFT / PREFLIGHT / AWAITING_AUTHORIZATION / AUTHORIZED / PLANNING / EXECUTING / VERIFYING / REPLANNING / FINALIZING / DONE / PARTIAL / BLOCKED / FAILED
- Terminal status: None / DONE / PARTIAL / BLOCKED / FAILED
- Authorization envelope reference:
- Hard acceptance criteria reconciliation:
- Current round / attempt / strategy ID:
- Budget usage / hard-limit state:
- Last status event / direct evidence:
- Remaining work:
- Recovery point:

## Unattended Auto-Continue Authorization

Use this only when the user explicitly authorizes the system to continue without waiting at every round boundary. If the user has not explicitly authorized it, unattended auto-continue is disabled and automatic unattended running is forbidden.

- Enabled: Yes / No
- Authorized by user: Yes / No
- Prompt shown at task start: Yes / No
- User authorization wording:
- Authorization time:
- Authorized objective:
- Resume from recovery point:
- Allowed files / directories:
- Allowed commands:
- Allowed action types:
- Prohibited operations:
- Multi-agent dispatch allowed while unattended: Yes / No
- Multi-agent launch already reviewed and confirmed for unattended run: Yes / No / N/A
- Sub-agent model policy:
- Maximum unattended rounds:
- Practical time cap:
- Per-round report requirement:
- Automation mechanism: Codex heartbeat / Codex cron / Claude Code verified equivalent / OpenCode verified equivalent / Manual resume / N/A
- Stop conditions:
- Current unattended status: Not Authorized / Authorized / Running / Stopped / Completed

## Planner Evaluation

| Round | Planner Used? | Accepted Suggestions | Rejected / Merged / Split Suggestions | Adjustment For Next Round |
|---|---|---|---|---|
|  | Yes / No / N/A |  |  |  |

## Round Reconciliation

- Completed this round:
- Evidence this round:
- Failed or blocked this round:
- New risks:
- Decision changes:
- Next round:

## Work Task Reports

Record user-facing task or phase reports delivered after completion.

| Time | Scope | Status | Report Location / Summary | Recovery Point |
|---|---|---|---|---|
|  | Task / Phase / Project | DONE / PARTIAL / BLOCKED / FAILED |  |  |

## Growth Candidates

L1 analysis creates no durable record. L2 project maintenance requires current project write authorization. L3 system promotion requires separate confirmation. The source observation is not a future-use validation: default `VALIDATED` requires helped outcomes in two independent future tasks; high-risk candidates also require an independent review, negative test, or counterexample test.

| Signal / Candidate | Evidence | Trigger / Action / Check / Boundary | Authority | Risk | Lifecycle Status | Future-Use Validations | Retrieval Outcome | Challenge / Suspension | Promotion Authorization |
|---|---|---|---|---|---|---|---|---|---|
|  |  |  | L1 / L2 / L3 | low / medium / high / critical | OBSERVED / CANDIDATE / PROJECT_EXPERIMENTAL / FUTURE_USE_VALIDATING / VALIDATED / CHALLENGED / SUSPENDED / SYSTEM_PROMOTION_PROPOSED / ACCEPTED / REJECTED / DEPRECATED / REMOVED | Future task IDs, independence keys, outcomes, evidence | not_evaluated / helped / neutral / harmful / inconclusive | Challenge refs, severity, replacement or review | Separate L3 authorization ref / N/A |

## Token And Complexity Control

- Latest Multi-Agent Fit Assessment result:
- Is multi-agent scheduling still worth it:
- Can the next step be done by the main controller alone:
- Are we adding process without improving delivery:

## Cost And Efficiency

- Agents dispatched this round:
- Agent IDs returned this round:
- Model policy used this round:
- Documentation sync model/cost strategy:
- Documentation sync source files, target files, and direction:
- Script or structured checks used before translation/sync:
- Low-cost candidate scope, if used:
- High-capability/main-controller approval scope:
- Draft/Unverified status required because approval is missing: Yes / No / N/A
- Documentation sync risks not reviewed:
- Outputs actually merged:
- Did parallelism reduce uncertainty or improve verification:
- Did the task queue shrink:
- Did deliverable availability improve:
- Any fake progress or repeated exploration:

<!-- MALTS:section=recovery-notes -->
## Recovery Notes

Minimum recovery unit:

- Result execution status:
- Terminal status: None / DONE / PARTIAL / BLOCKED / FAILED
- Current round / attempt:
- Active strategy ID:
- Budget usage / hard limits:
- Last status event / evidence:
- Current goal:
- Completion definition:
- Current task queue:
- Completed tasks:
- Blocking items:
- Modified files:
- Verification records:
- Next shortest path:
