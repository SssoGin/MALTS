# PROJECT_CONTROL

> Project authority only: original goal, global acceptance, current Phase/plan index, cross-Phase decisions, Artifact pointers, and Project recovery.
> Phase, Session, Task/Result, and runtime coordination records own their respective details. Reports and handoffs are on-demand, non-authoritative views.

<!-- MALTS:section=metadata -->
## Metadata

- Project:
- Control version: <MALTS_VERSION>
- Version source: resolve `MALTS_BOOT.md` first, then read the active `MALTS_ROOT` `VERSION`; do not copy a physical generation path or current MALTS version from old control/report/handoff/template files.
- Current round:
- Last updated:
- Project owner: Main Controller
- Current mode: Single-Agent / Multi-Agent Long-Task
- Narrative language: English / Simplified Chinese / project language
- Canonical file: `PROJECT_CONTROL.md`
- Authority boundary: Project facts only; Phase/Session/Task/Result and coordination details remain with their owners.
- Derived views: `WORK_TASK_REPORT.md` and `PROJECT_HANDOFF.md` are generated only when requested and never gate ordinary mutation.
- Capacity: fresh target <= 150 lines / 12 KiB; daily hot read <= 150 lines / 16 KiB; soft maximum 1500 lines / 262144 bytes.

<!-- MALTS:section=user-original-goal -->
## User Original Goal

> Original goal (locked):

### Later User Changes

| Time | Change | Impact |
|---|---|---|

<!-- MALTS:section=current-interpreted-goal -->
## Current Interpreted Goal

- Current understanding:
- Confirmed exclusions:
- Open questions:
- Grill-Me Preflight: applies=Yes / No / N/A; offered=Yes / No / N/A; decision=Accepted / Declined / N/A

<!-- MALTS:section=completion-definition -->
## Completion Definition

- [ ] The user's core goal and global acceptance criteria are met.
- [ ] Required Project deliverables and cross-Phase decisions are recorded.
- [ ] Verification evidence is indexed without copying Phase evidence.
- [ ] Remaining work, blockers, and recovery are explicit.

<!-- MALTS:section=acceptance-criteria -->
## Acceptance Criteria

| Requirement | Verification Method | Status | Evidence |
|---|---|---|---|
|  |  | TODO |  |

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

<!-- MALTS:section=phase-carry-over-index -->
## Phase Carry-over Index

| Source Phase | Target Phase | Transition Plan SHA-256 | Source Record | Target Record | Status |
|---|---|---|---|---|---|

<!-- MALTS:section=artifact-contract-index -->
## Artifact Lifecycle Index

- Contract version: `1`
- Enrollment: `NOT_ENROLLED`
- Shared index: `N/A`
- Archive index: `N/A`
- Latest audit: `N/A`

<!-- MALTS:section=task-queue -->
## Task Queue

Only Project gates may appear here. A long workspace keeps every Phase task in the owning `PHASE_CONTROL.md`.

| ID | Priority | Status | Owner | Task | Dependencies | Allowed Changes | Verification |
|---|---|---|---|---|---|---|---|

<!-- MALTS:section=file-ownership -->
## File Ownership

Only durable Project boundary pointers belong here. Runtime Admission, lease, queue, and fencing records remain in coordination state.

| Path / Resource | Project Boundary | Canonical Owner | Notes |
|---|---|---|---|

<!-- MALTS:section=decisions -->
## Decisions

| Time | Cross-Phase / Project Decision | Reason | Evidence |
|---|---|---|---|

<!-- MALTS:section=verification-records -->
## Verification Records

Index Project-level acceptance only; link to owner evidence instead of copying it.

| Time | Requirement | Result | Evidence Reference |
|---|---|---|---|

<!-- MALTS:section=risks-and-blockers -->
## Risks And Blockers

Only global Project blockers belong here. Resource- or Phase-scoped issues stay with their owning control/runtime record.

| ID | Scope | Description | Status | Owner / Reconcile |
|---|---|---|---|---|

<!-- MALTS:section=recovery-notes -->
## Recovery Notes

- Recovery schema: `1`
- Record ID: `project:recovery`
- Summary: Project recovery applies only when no more specific Phase or Session recovery source exists.
- Next action: Open or resume a Phase only after boundary and authorization review.
- Evidence references: `project:recovery`
- Recorded at: `N/A`
