# PROJECT_CONTROL

> Purpose: single source of truth for the current project state when MALTS is enabled.
> Language policy: keep this as the only canonical control file by default. Keep `MALTS:section` markers, status values, identifiers, paths, and commands stable; visible headings and narrative content may use the user's or project's primary language. Do not create a full translated mirror unless the user explicitly asks for one.
> Do not create MALTS control files for every trivial task by default. Create or reuse this file when the user enables MALTS, long-task scheduling is active, or a normal task grows complex enough to require recoverable state.

<!-- MALTS:section=metadata -->
## Metadata

- Project:
- Control version: <MALTS_VERSION>
- Version source: active boot file -> <MALTS_ROOT>/VERSION; do not copy current MALTS versions from old control/report/handoff/template files.
- Current round:
- Last updated:
- Maintainer: Main Controller
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
- Stage goal:
- Exit condition:

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
- Reason:
- User was informed of recommendation: Yes / No / N/A
- User confirmation required before dispatch: `确认运行`

## Multi-Agent Launch Review

Use this before any real sub-agent dispatch after the user asks to use multi-agent mode.

- Overall goal:
- Total plan:
- Model specification prompt shown: Yes / No
- Model specification prompt deviation accepted: Yes / No / N/A
- How to specify models: `Role=model-id; Role=inherit; default=inherit`
- User model choices:
- Planned dispatch order / parallel batches:
- User confirmation phrase required: `确认运行`
- Confirmation status: Pending / Confirmed / Revised / Cancelled

| Role | Task ID | Model Name / Policy | Task Objective | Short Plan | Permission Level |
|---|---|---|---|---|---|
| Planner / Explorer / Worker / Verifier / Memory Curator |  | Explicit model / Inherited model / Runtime default |  |  | Level 0 / 1 / 2 / 3 / 4 |

## Agent Dispatch Log

Record every real sub-agent dispatch. If no sub-agent was dispatched, write `N/A`.

| Time | Round | Task ID | Role | Dispatch Mechanism | Runtime Agent ID | Model Policy | Contract Reference | Status |
|---|---|---|---|---|---|---|---|---|
|  |  |  | Planner / Explorer / Worker / Verifier / Memory Curator | e.g. Codex `spawn_agent` |  | Inherited / Explicit: model name |  | Requested / Running / Returned / Failed / Cancelled |

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

## Termination Status

| Level | Current Fit | Reason | Delivery Behavior |
|---|---|---|---|
| Ideal / Pragmatic / Forced | Yes / No / Unknown |  | Normal delivery / Deliver with risks / Save recovery path |

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
|  | Task / Phase / Project | Completed / Partially Completed / Blocked / Failed |  |  |

## Growth Candidates

Only add candidates. Long-term memory writes require filtering.

| Candidate | Source | Trigger | Reusable? | Suggested Destination | Status |
|---|---|---|---|---|---|
|  | Success / Failure / Decision / Process |  | Yes / No / Unsure | Skill / Checklist / Tool instruction file / Local Only | Local / Proposed for global / Promoted / Merged / Rejected |

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

- Current goal:
- Completion definition:
- Current task queue:
- Completed tasks:
- Blocking items:
- Modified files:
- Verification records:
- Next shortest path:
