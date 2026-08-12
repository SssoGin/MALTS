# Long Project Workspace Instructions

This workspace uses MALTS long-project controls.

## Initialization readiness

- Selecting the long-project initializer means the user wants a long-project workspace, not an ordinary minimal project-control skeleton.
- A newly initialized workspace is ready only when `runtime/workspace_control.json` registers its first Phase and `active_phase_id` names that Phase.
- If root controls exist but the Phase registry is empty, report `NEEDS_INITIAL_PHASE` and propose the no-overwrite migration. Do not report initialization complete.
- Always tell the user whether an active Session exists and why no Session was created.

## Canonical ownership

- `PROJECT_CONTROL.md` owns the original goal, global acceptance criteria, active Phase index, cross-phase decisions, and Project recovery record.
- `phases/<phase-id>/PHASE_CONTROL.md` owns that Phase's goal, boundary and Boundary Review records, plan, queue, deliverables, evidence, recovery record, closure, and growth review.
- `sessions/<session-id>/SESSION_CONTROL.md` owns one explicitly bounded work session's scope, commands, touch set, checkpoint/recovery record, and next step.
- `WORK_TASK_REPORT.md` is the required current projection in schema v3. `PROJECT_HANDOFF.md` is optional, but when present its current Phase binding must also be exact.
- `runtime/` is non-canonical generated state. It must never overwrite canonical Markdown controls.

Do not create a Session for every conversation turn or ordinary persistent write. Open one only for an explicit bounded work-session boundary.

## Recovery order

1. Read the nearest applicable instruction file.
2. Read root `PROJECT_CONTROL.md`.
3. Read the active `PHASE_CONTROL.md`, if any.
4. Read the active `SESSION_CONTROL.md` only when one exists, then the current report and optional handoff.
5. Verify current files and non-canonical runtime evidence.

Summaries cannot replace the active MALTS version, current files, or required runtime probes.

For schema v3, canonical recovery authority is: active Session checkpoint, otherwise active Phase recovery, otherwise an explicitly bound terminal Phase, otherwise Project recovery. Never select the latest historical Session by time or list order.

## Cross-control consistency

- Fresh workspaces use exact workspace schema v3. Schema v1/v2 remain readable compatibility contracts; migrate only through explicit dry-run/apply commands.
- `phase-boundary-review` reports operation execution separately from `review_outcome`; it never persists or authorizes work. Persist only with `record-phase-boundary-review` and keep later mutation authorization separate.
- Missing/stale current report binding, stale optional handoff binding, full Phase-control drift, normalized Boundary/Recovery drift, unresolved review state, typed recovery-source drift, or an incomplete workspace transaction blocks validation, cold recovery, and ordinary lifecycle mutation.
- Workspace consistency writes use `runtime/workspace_transaction.lock.json`, `runtime/workspace_transactions/`, and `WS_TRANSACTION_*`. Artifact transactions retain their separate paths and `ART_TRANSACTION_*` codes.

## Discovery and Plan Recheck

- Resolve ordinary startup only from the active tool's adjacent `MALTS_BOOT.md`; cross-check registry, active pointer, and `VERSION`. MALTS v1.1.1+ no longer uses or creates a machine-global `GLOBAL_BOOT.md`. Treat disagreement as split brain and fail closed.
- The active Phase owns the plan path, revision, raw-byte SHA-256, recheck trigger/result, and launch-review invalidation. Root control is only an index; a Session only inherits the binding.
- For S3/S4 work, run read-only `long_workspace.py plan-recheck --require-active-plan` at the applicable event before new write scope, launch review, verifier, recovery/rollback, or final delivery. `BLOCKED` stops; the command never creates authorization.

## Safety

- Separate read-only review from state-changing execution.
- Do not overwrite user files or expand scope silently.
- Do not use Git, network, providers, Agent dispatch, dependency installation, or destructive cleanup without separate authorization.
- Do not run automatic, periodic, background, or ordinary-use update checks.
