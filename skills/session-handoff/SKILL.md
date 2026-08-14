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

`PROJECT_HANDOFF.md` is the single handoff source of truth by default. Include a short English `Agent Brief` at the top for machine/agent scanning, then write the remaining sections in the user's or project's primary language.

Optional full translated mirror:

```text
<PROJECT_ROOT>/项目交接.md
```

Create or update the optional mirror only when the user explicitly asks for Chinese handoff output as a separate file or a workflow requires a full translated copy. If both files exist and conflict, treat `PROJECT_HANDOFF.md` as authoritative.

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
3. Read relevant project instructions, `PROJECT_CONTROL.md`, the active Phase, the active Session if one exists, the current report/handoff, and key files.
4. Distinguish verified current facts from historical claims.
5. For workspace schema v4, run read-only `validate` first. Structural, binding, deterministic-consistency, unresolved-review, typed-recovery, or pending workspace-transaction failures stop the handoff-ready claim.
6. If an active S3/S4 Phase binds a plan, run read-only `long_workspace.py plan-recheck --trigger FINAL_DELIVERY --require-active-plan`; a blocked result stops the handoff-ready claim until controls are reconciled.
7. Write `PROJECT_HANDOFF.md`.
8. Optionally write `项目交接.md` only when explicitly requested.
9. Re-run `validate`; for recovery-sensitive delivery, also run fresh-process `recover`. Verify the output files exist and their declared current Phase binding matches exact current bytes before answering.

## Cross-Control Binding

- `PROJECT_HANDOFF.md` is an optional projection, not a source for changing Phase authority. When it exists in schema v4, its `current-phase-binding` section must name the active Phase and bind the exact Phase control SHA-256, normalized boundary SHA-256, Boundary Review ID/SHA-256/mapping/recommendation, normalized Phase recovery SHA-256, and recorded time.
- `WORK_TASK_REPORT.md` is the required current projection in schema v4. Do not write a handoff that disagrees with the current report or canonical Phase/Session records.
- Recovery authority is deterministic: active Session checkpoint, otherwise active Phase recovery, otherwise an explicitly bound terminal Phase, otherwise Project recovery. Never choose the latest historical Session merely by time or list order.
- A recorded Boundary Review is evidence, not authorization for later pause/resume/transition or implementation. Preserve separate authorization references.
- If a persisted workspace transaction is incomplete, retain its lock/journal evidence and use hash-bound `recover-workspace-transaction`; do not hide or delete it in a handoff.

## Required Content

- English Agent Brief
- generated time
- workspace or project root
- source context reviewed
- current status
- completed work
- pending work
- known risks
- verification already performed
- active plan path, revision, SHA-256, latest Plan Recheck trigger/result, and launch-review invalidation state when applicable
- current Phase full-control, boundary, Boundary Review, and recovery binding hashes when schema v4 is active
- typed canonical recovery source and any pending workspace transaction recovery action
- next recommended steps

## MALTS v1.3.0 handoff projection

- Include the exact Result lineage head (latest event sequence/hash), active Session lease owner/scope/touch-set, current Task binding index hash, and pending migration/instruction-refresh state when present.
- Never copy a second full Attempt ledger into the handoff; Phase/Session/report/handoff/runtime keep bindings and rebuildable projections only.
- Recovery authority remains: active Session checkpoint, otherwise active Phase recovery, otherwise explicitly bound paused/terminal Phase, otherwise Project recovery.
