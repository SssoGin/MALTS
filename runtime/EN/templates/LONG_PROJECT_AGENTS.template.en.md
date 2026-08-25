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
- `WORK_TASK_REPORT.md` is a required exact projection only for legacy workspace layout compatibility. In CURRENT contract, it and an existing `PROJECT_HANDOFF.md` are on-demand derived views whose staleness is a warning, not a competing authority.
- `runtime/workspace_control.json` owns machine-enforced schema/profile/index and transaction bindings; coordination state owns Admissions, queues, fencing, and quarantine. Other `runtime/` content is generated evidence/cache. Runtime state must never invent or overwrite canonical Markdown goals, boundaries, plans, or recovery facts.

Do not create a Session for every conversation turn or ordinary persistent write. Open one only for an explicit bounded work-session boundary.

## Daily entry and recovery order

For an initialized workspace, first run read-only `workspace-entry` with the matching task class and load only its bounded current-set read list. It writes nothing, creates no entity, and loads no full history. Escalate to full recovery only when entry blocks, recovery is explicitly requested, or a recovery-sensitive gate requires it.

Full recovery order is:

1. Read the nearest applicable instruction file.
2. Read root `PROJECT_CONTROL.md`.
3. Read the selected/primary `PHASE_CONTROL.md`, if any.
4. Read the active `SESSION_CONTROL.md` only when one exists.
5. Read report/handoff only for reporting/handoff work or when the recovery decision identifies them as relevant.
6. Verify current files and runtime safety evidence; read historical files only by explicit reference.

Summaries cannot replace the active MALTS version, current files, or required runtime probes.

Canonical recovery authority is: active Session checkpoint, otherwise active Phase recovery, otherwise an explicitly bound paused/terminal Phase, otherwise Project recovery. Never select the latest historical Session by time or list order.

## Cross-control consistency

- Fresh workspaces use the exact CURRENT workspace and Result contracts with default `single_phase`; opt-in `resource_admission` permits additional `OPEN` Phases only through runtime Admission. Supported legacy layouts remain readable internal compatibility inputs and reach CURRENT only through one-hop, dry-run/apply, exact-hash-bound reorganization.
- `phase-boundary-review` reports operation execution separately from `review_outcome`; it never persists or authorizes work. Persist only with `record-phase-boundary-review` and keep later mutation authorization separate.
- Canonical control drift, normalized Boundary/Recovery drift, invalid plan/authorization/Admission/fencing preconditions, unknown authority-affecting side effects, or an incomplete transaction blocks the affected operation. CURRENT report/handoff drift is a warning and local refresh; legacy workspace layout projection drift retains strict compatibility blocking.
- Workspace and coordination authority writes share `runtime/workspace_transaction.lock.json`, `runtime/workspace_transactions/`, `WS_TRANSACTION_*`, post-lock exact-preimage checking, and one writer. Artifact transactions retain their separate paths and `ART_TRANSACTION_*` codes.
- Resource-profile Tasks use CURRENT Result Contract execution authority and append-only typed events. Phase/Session/report/handoff/runtime summaries keep only references or rebuildable projections, never a second full Attempt ledger.
- `max_authorized_rounds` is an independent runtime STOP gate. A failed Attempt terminates only that Attempt; no automatic retry and no automatic Task/Phase terminal promotion.
- `scoped-readiness` is read-only routing advice (S0/S1/S2/ESCALATE); it never authorizes, writes, or dispatches. `refresh-project-instructions` rewrites only `MALTS-PROJECT:`-owned blocks with an exact reviewed plan; markerless customized files are never claimed automatically.

## Project-managed instruction blocks

Refresh only through the explicit command:

```text
<!-- MALTS-PROJECT:BEGIN <marker-id> -->
...
<!-- MALTS-PROJECT:END <marker-id> -->
```

`refresh-project-instructions` preserves bytes/BOM/EOL outside owned blocks, rejects reparse/hardlink targets, and is idempotent. Ordinary `init` / `validate` / `recover` never trigger it.

## Discovery and Plan Recheck

- Resolve ordinary startup only from the active tool's adjacent `MALTS_BOOT.md`; cross-check registry, active pointer, and `VERSION`. MALTS v1.1.1+ no longer uses or creates a machine-global `GLOBAL_BOOT.md`. Treat disagreement as split brain and fail closed.
- The active Phase owns the plan path, revision, raw-byte SHA-256, recheck trigger/result, and launch-review invalidation. Root control is only an index; a Session only inherits the binding.
- For S3/S4 work, run read-only `long_workspace.py plan-recheck --require-active-plan` at the applicable event before new write scope, launch review, verifier, recovery/rollback, or final delivery. `BLOCKED` stops; the command never creates authorization.

## Resource Admission

- Default `single_phase` creates no coordination state and pays no daily concurrency cost.
- Under `resource_admission`, every write verifies a typed locator/capability Admission, exact Phase hash, actor, lease expiry, and fencing epochs. Exact and parent/child paths conflict; declared aliases share one domain.
- Capabilities are `SHARED`, `EXCLUSIVE`, `QUEUED`, or `ISOLATE_REQUIRED`. Renewal is explicit; no heartbeat daemon or implicit Agent is created.
- An `UNKNOWN` external effect quarantines affected domains. Unrelated domains may continue unless workspace authority/recovery is uncertain; quarantined domains require explicit evidence-backed reconcile.

## Safety

- Separate read-only review from state-changing execution.
- Do not overwrite user files or expand scope silently.
- Do not use Git, network, providers, Agent dispatch, dependency installation, or destructive cleanup without separate authorization.
- Do not run automatic, periodic, background, or ordinary-use update checks.
