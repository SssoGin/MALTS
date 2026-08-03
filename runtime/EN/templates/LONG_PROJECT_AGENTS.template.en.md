# Long Project Workspace Instructions

This workspace uses MALTS long-project controls.

## Initialization readiness

- Selecting the long-project initializer means the user wants a long-project workspace, not an ordinary minimal project-control skeleton.
- A newly initialized workspace is ready only when `runtime/workspace_control.json` registers its first Phase and `active_phase_id` names that Phase.
- If root controls exist but the Phase registry is empty, report `NEEDS_INITIAL_PHASE` and propose the no-overwrite migration. Do not report initialization complete.
- Always tell the user whether an active Session exists and why no Session was created.

## Canonical ownership

- `PROJECT_CONTROL.md` owns the original goal, global acceptance criteria, active Phase index, and cross-phase decisions.
- `phases/<phase-id>/PHASE_CONTROL.md` owns only that Phase's goal, queue, deliverables, evidence, closure, and growth review.
- `sessions/<session-id>/SESSION_CONTROL.md` owns only one explicitly bounded work session's scope, commands, touch set, checkpoint, and next step.
- `runtime/` is non-canonical generated state. It must never overwrite canonical Markdown controls.

Do not create a Session for every conversation turn or ordinary persistent write. Open one only for an explicit bounded work-session boundary.

## Recovery order

1. Read the nearest applicable instruction file.
2. Read root `PROJECT_CONTROL.md`.
3. Read the active `PHASE_CONTROL.md`, if any.
4. Read the active/latest `SESSION_CONTROL.md`, report, or handoff, if any.
5. Verify current files and runtime evidence.

Summaries cannot replace the active MALTS version, current files, or required runtime probes.

## Discovery and Plan Recheck

- Resolve ordinary startup only from the active tool's adjacent `MALTS_BOOT.md`; cross-check registry, active pointer, and `VERSION`. MALTS v1.1.1+ no longer uses or creates a machine-global `GLOBAL_BOOT.md`. Treat disagreement as split brain and fail closed.
- The active Phase owns the plan path, revision, raw-byte SHA-256, recheck trigger/result, and launch-review invalidation. Root control is only an index; a Session only inherits the binding.
- For S3/S4 work, run read-only `long_workspace.py plan-recheck --require-active-plan` at the applicable event before new write scope, launch review, verifier, recovery/rollback, or final delivery. `BLOCKED` stops; the command never creates authorization.

## Safety

- Separate read-only review from state-changing execution.
- Do not overwrite user files or expand scope silently.
- Do not use Git, network, providers, Agent dispatch, dependency installation, or destructive cleanup without separate authorization.
- Do not run automatic, periodic, background, or ordinary-use update checks.
