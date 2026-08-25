# PHASE_CONTROL

<!-- MALTS:section=phase-metadata -->
## Phase Metadata

- Phase ID: <PHASE_ID>
- Status: ACTIVE
- Created at: <TIMESTAMP>
- Updated at: <TIMESTAMP>

<!-- MALTS:section=phase-goal -->
## Phase Goal

<PHASE_GOAL>

<!-- MALTS:section=phase-boundary -->
## Phase Boundary Contract

- Milestone: <PHASE_MILESTONE>
- In Scope: <PHASE_IN_SCOPE>
- Explicitly Out of Scope: <PHASE_OUT_OF_SCOPE>
- Exit Criteria: <PHASE_EXIT_CRITERIA>
- Carry-over Policy: <PHASE_CARRY_OVER_POLICY>
- Boundary Review Triggers: <PHASE_BOUNDARY_REVIEW_TRIGGERS>

<!-- MALTS:section=phase-plan-recheck -->
## Active Plan And Recheck

- Active plan: `N/A`
- Plan revision: `N/A`
- Plan content SHA-256: `N/A`
- Plan updated at: `N/A`
- Supersedes: `N/A`
- Plan status: `N/A`
- Last recheck trigger: `N/A`
- Last recheck result: `N/A`
- Last rechecked at: `N/A`
- Launch review invalidated: `No`

<!-- MALTS:section=phase-queue -->
## Active Queue

| Task ID | Objective | Status | Evidence |
|---|---|---|---|

<!-- MALTS:section=phase-resource-admission-index -->
## Resource Admission References

本节只保存紧凑引用。`runtime/workspace_coordination.json` 拥有 Admission、capability queue、lease expiry、fencing epoch 与 quarantine；不得把该 ledger 复制到这里。

- Governance profile: `single_phase` / `resource_admission`
- Current Admission IDs: `N/A`
- Declared typed locator/capability scope references: `N/A`
- Latest verify/release/reconcile evidence: `N/A`

<!-- MALTS:section=phase-deliverables -->
## Deliverables And Acceptance

| Deliverable | Acceptance | Status | Evidence |
|---|---|---|---|

<!-- MALTS:section=phase-decisions -->
## Open Decisions And Risks

- Open decisions:
- Risks:

<!-- MALTS:section=phase-scope-changes -->
## Scope Change Log

| Time | Change | Reason | User Authorization | Impact |
|---|---|---|---|---|

<!-- MALTS:section=phase-carry-over -->
## Carry-over

| Source Task | Source Status | Remaining Work | Evidence | Recovery | Authorization State | Target Phase | Reason |
|---|---|---|---|---|---|---|---|

<!-- MALTS:section=phase-carried-in -->
## Carried In

| Task ID | Carried from | Source Status | Remaining Work | Evidence | Recovery | Authorization State | Current Status |
|---|---|---|---|---|---|---|---|

<!-- MALTS:section=phase-boundary-review -->
## Last Boundary Review

- Review schema: `1`
- Review ID: `N/A`
- Review status: `NOT_RUN`
- Candidate mapping: `UNCLEAR`
- Recommended review: `USER_DECISION_REQUIRED`
- Reviewed at: `N/A`
- Evidence reference: `N/A`
- Authorization reference: `N/A`

<!-- MALTS:section=phase-artifacts -->
## Artifact Registry

这个可选的 owner-local registry 只有在显式 Artifact enrollment 且首条记录经过审阅后才使用。不得仅因本节存在就创建 `artifacts/` 目录。

| Artifact ID | Role | Locator | Authority | VCS | Verification | Retention | Disposition | Relationships | Role Contract |
|---|---|---|---|---|---|---|---|---|---|

<!-- MALTS:section=phase-recovery -->
## Recovery Point

- Recovery schema: `1`
- Record ID: `phase:<PHASE_ID>:recovery`
- Summary: Phase <PHASE_ID> 已激活；当前没有 active Session。
- Next action: 仅在显式 bounded work-session 边界下创建 Session。
- Evidence references: `phase:<PHASE_ID>`
- Recorded at: `<TIMESTAMP>`

<!-- MALTS:section=phase-lifecycle -->
## Phase Lifecycle

- Pause reason: `N/A`
- Paused at: `N/A`
- Resume boundary review: `N/A`
- Resume plan review: `N/A`
- Resume authorization: `N/A`
- Resumed at: `N/A`

<!-- MALTS:section=phase-close -->
## Closure And Growth Review

- Close result: N/A
- Exit criteria status: NOT_EVALUATED
- Carry-over disposition: N/A
- Superseded by: N/A
- Closure evidence: N/A
- Closed at: N/A
- Growth candidates:

`resource_admission` 下，Phase 收口前必须释放或显式 reconcile 该 Phase 的全部 Admission；本控制文件本身不会释放 runtime grant。
