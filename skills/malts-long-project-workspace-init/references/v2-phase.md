# Adopted v2 Phase review and transition

Use this reference for a Phase boundary, plan, activation or carry-over request in a verified v2 workspace. The Task service owns executable state; the pre-adoption Markdown Plan Recheck commands do not apply.

1. Verify workspace binding, epoch and selected Project. Read `governance-context`, `task-queue` and the exact Task `context` only as needed. A synthetic case, historical DONE, goal preview or current-looking file is not a live authority check.
2. Read the current Project/Phase/Task revisions, in-scope/out-of-scope boundary, acceptance, dependency and carry-over obligations. Read actual plan bytes and verify the bound hash; a context declaration alone does not verify the body.
3. Compare the requested goal/deliverable/resource change with the current boundary. Choose current-Phase revision versus an explicit next Phase from that comparison; do not infer a transition merely from one new deliverable.
4. Check registered operations, Run/Host state, recovery isolation and relevant external writers separately. UNKNOWN must be reconciled. PAUSED or settled registered effects do not prove external-writer quiescence.

For review-only work, return the mapping, necessary facts, proposed boundary/plan changes and unresolved conditions; do not define, activate, carry, rebind or initialize anything. Reading through a managed operation may create control records and is not a zero-state-write substitute for a read-only service.

When corresponding implementation is already authorized, use the actual v2 action contracts. `phase.define` cannot revise an ACTIVE Phase directly: satisfy the current pause/effect/Run/Host preconditions first. Define the reviewed revision, bind affected Task revisions explicitly, and preserve exact carry-over lineage. Do not rebind unrelated Tasks or treat plan verification as permission. Dry-run intent is not readiness; apply the reviewed operation within the authorized scope.

## Related controller contract

The focused review above is complete without the general usage guide. For a concrete change, inspect the current action catalog before constructing arguments. `phase.define` binds `phase_id`, `project_id`, current `project_revision`, `expected_revision`, `goal`, `boundary`, `acceptance`, and actual `plan_ref`/`plan_sha256`; a STATE-scoped plan additionally declares `plan_scope=STATE`. `phase.set-active` uses the exact Phase revision. `phase.bind-task` uses both current Task and Phase revisions. None of those names grants permission or proves the input body.

For an unavailable write action, hand its exact requested contract to the controller; a Worker must not broaden its endpoint. CLI request preview is intent only, and an authorized apply still checks active-Phase, pending-effect and Run/Host conditions. Unrelated Artifact, Growth and pre-adoption procedures are not part of this Phase review.
