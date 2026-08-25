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

This is a compact reference only. `runtime/workspace_coordination.json` owns Admissions, capability queues, lease expiry, fencing epochs, and quarantine; do not copy that ledger here.

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

This optional owner-local registry exists only after explicit Artifact enrollment and the first reviewed row. Do not create an `artifacts/` directory merely because the section exists.

| Artifact ID | Role | Locator | Authority | VCS | Verification | Retention | Disposition | Relationships | Role Contract |
|---|---|---|---|---|---|---|---|---|---|

<!-- MALTS:section=phase-recovery -->
## Recovery Point

- Recovery schema: `1`
- Record ID: `phase:<PHASE_ID>:recovery`
- Summary: Phase <PHASE_ID> is active; no Session is active.
- Next action: Open a Session only for an explicit bounded work-session boundary.
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

Closure under `resource_admission` requires every Admission for this Phase to be released or explicitly reconciled; this control does not release runtime grants by itself.
