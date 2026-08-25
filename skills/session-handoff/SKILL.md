---
name: session-handoff
description: Use when the user asks for a project handoff, next-Agent summary, continuation notes, PROJECT_HANDOFF, or similar recovery context.
---

# Session Handoff

Use this skill when the user asks for a handoff, project handoff, next-Agent summary, continuation notes, `PROJECT_HANDOFF`, `交接文档`, `项目交接`, or similar recovery context.

## Output Policy

Default canonical output:

```text
<PROJECT_ROOT>/PROJECT_HANDOFF.md
```

`PROJECT_HANDOFF.md` is an on-demand continuation view, not lifecycle authority. Write the top `Agent Brief` and the remaining narrative in the user's or project's primary language while preserving stable English field names and machine status codes for machine/agent scanning. Canonical Project/Phase/Session controls remain the source of the facts summarized here.

Optional full translated mirror:

```text
<PROJECT_ROOT>/项目交接.md
```

Create or update the optional mirror only when the user explicitly asks for Chinese handoff output as a separate file or a workflow requires a full translated copy. If both files exist and conflict, treat neither copy as permission or lifecycle authority; reconcile them against the canonical Project/Phase/Session controls. The English-named file is the primary generated view.

## Privacy Rules

Never write secrets, tokens, cookies, passwords, credentials, authorization headers, sensitive memory dumps, or raw session logs into handoff files.

For public examples, use placeholders such as:

```text
<PROJECT_ROOT>
<MALTS_ROOT>
```

## Workflow

1. Inspect the current project state before writing conclusions.
2. Check git status when the workspace is a git repository.
3. Read relevant project instructions, `PROJECT_CONTROL.md`, the selected/primary Phase, the active Session if one exists, and key files. Read an existing report/handoff only when needed to refresh or compare the requested view; do not load history by default.
4. Distinguish verified current facts from historical claims.
5. Run read-only `validate` before a recovery-sensitive handoff. Safety-critical structural, canonical binding, boundary/recovery, Admission/fencing, unknown-effect, or pending-transaction failures stop the handoff-ready claim. In legacy workspace layout, stale report/handoff bindings remain blocking compatibility behavior; in CURRENT contract, derived-view drift is a warning and is repaired locally by explicit refresh.
6. If an active S3/S4 Phase binds a plan, run read-only `long_workspace.py plan-recheck --trigger FINAL_DELIVERY --require-active-plan`; a blocked result stops the handoff-ready claim until controls are reconciled.
7. Write `PROJECT_HANDOFF.md`.
8. Optionally write `项目交接.md` only when explicitly requested.
9. Re-run `validate`; for recovery-sensitive delivery, also run fresh-process `recover`. Verify the output file exists and its derived metadata binds the exact current state/Phase bytes. A CURRENT handoff refresh must not mutate canonical controls or create a missing handoff implicitly.

## Cross-Control Binding

`DERIVED_NON_AUTHORITATIVE`: CURRENT report and handoff files are derived views, not canonical lifecycle authority.

- `PROJECT_HANDOFF.md` is an optional projection, not a source for changing Phase authority. When it exists in legacy workspace layout, its `current-phase-binding` section must name the active Phase and bind the exact Phase control SHA-256, normalized boundary SHA-256, Boundary Review ID/SHA-256/mapping/recommendation, normalized Phase recovery SHA-256, and recorded time.
- `WORK_TASK_REPORT.md` is the required current projection in legacy workspace layout. Do not write a handoff that disagrees with the current report or canonical Phase/Session records.
- In CURRENT contract, report and handoff files are derived, non-authoritative, on-demand views. Their staleness is reported as `WARNING`, not a global mutation stop. Use `refresh-maintenance-views --include-existing-handoff` with exact state/Phase hashes; it rebuilds each selected view from canonical current controls rather than retaining older projection prose, never creates a missing handoff, and is a byte-preserving no-op when already current.
- Recovery authority is deterministic: active Session checkpoint, otherwise active Phase recovery, otherwise an explicitly bound terminal Phase, otherwise Project recovery. Never choose the latest historical Session merely by time or list order.
- A recorded Boundary Review is evidence, not authorization for later pause/resume/transition or implementation. Preserve separate authorization references.
- If a persisted workspace transaction is incomplete, retain its lock/journal evidence and use hash-bound `recover-workspace-transaction`; do not hide or delete it in a handoff.

## Required Content

- Agent Brief written in the user's or project's narrative language, with stable English field names and machine status codes preserved
- generated time
- workspace or project root
- source context reviewed
- current status
- completed work
- pending work
- known risks
- verification already performed
- active plan path, revision, SHA-256, latest Plan Recheck trigger/result, and launch-review invalidation state when applicable
- current Phase full-control, boundary, Boundary Review, and recovery binding hashes when legacy workspace layout is active
- typed canonical recovery source and any pending workspace transaction recovery action
- next recommended steps

## Current handoff projection

- Include the exact Result lineage head (latest event sequence/hash), active Session lease owner/scope/touch-set, current Task binding index hash, and pending migration/instruction-refresh state when present.
- Never copy a second full Attempt ledger into the handoff; Phase/Session/report/handoff/runtime keep bindings and rebuildable projections only.
- Recovery authority remains: active Session checkpoint, otherwise active Phase recovery, otherwise explicitly bound paused/terminal Phase, otherwise Project recovery.
- A resource-profile handoff may reference Admission IDs, typed locator/capability domains, fencing epochs, and quarantine/reconcile evidence, but must not copy the coordination ledger or turn those references into a second authority.
