# Handoff

MALTS uses handoff files to make long work recoverable across windows, interruptions, and Agent changes.

In CURRENT workspace contract, a handoff is an on-demand derived continuation view, not lifecycle authority and not a mandatory daily-start input. Project, selected Phase, and explicit Session controls own the summarized facts. Run bounded `workspace-entry --task-class CONTEXT_RECOVERY` first; read or refresh the handoff only when the user requests it or the recovery decision identifies it as useful. Staleness is a warning and is repaired locally with exact state/Phase hashes; `refresh-maintenance-views --include-existing-handoff` rebuilds an existing handoff from canonical current controls, never carries older projection prose forward, never creates a missing handoff, and is a no-op when already current. A legacy workspace retains its strict binding behavior until explicit CURRENT reorganization.

A resource-profile handoff may reference Admission IDs, locator/capability domains, lease/fencing evidence, and quarantine/reconcile status. It must not copy the coordination ledger or imply that prose grants write authority. An `UNKNOWN` external effect remains quarantined regardless of a favorable summary.

## Default File Names

Canonical Agent-facing file:

```text
PROJECT_HANDOFF.md
```

Optional user-facing Chinese mirror:

```text
项目交接.md
```

## Rules

- Write the Agent-facing handoff in the user's or project's narrative language while preserving stable English field names and machine codes.
- A translated mirror is optional and is created only when explicitly requested.
- Do not write secrets, tokens, cookies, passwords, credentials, sensitive memory dumps, or raw session logs into handoff files.
- Use placeholders for public examples.
- Real handoff files belong in the user's project workspace, not in the MALTS release repository.
- Installed release packages and active-generation roots are immutable runtime inputs; never store live handoff files inside them.

## What To Include

- generated time
- current workspace
- current goal
- completed work
- pending work
- verification already performed
- known risks
- next recommended steps

Use `runtime/EN/templates/PROJECT_HANDOFF.template.en.md`.

## Plan Binding

For an active S3/S4 Phase, include the Phase-owned active plan path, revision, raw-byte SHA-256, last trigger/result, launch-review invalidation state, and inherited Session binding. Run the read-only `FINAL_DELIVERY` Plan Recheck before a handoff-ready claim; preserve a blocked result and reconciliation action rather than hiding drift.

## Cross-Control Binding

In workspace legacy workspace layout, `WORK_TASK_REPORT.md` is the required current projection. `PROJECT_HANDOFF.md` remains optional, but when it exists its `current-phase-binding` section must bind the exact active Phase control SHA-256, normalized boundary SHA-256, Boundary Review ID/SHA-256/mapping/recommendation, and normalized Phase recovery SHA-256. Re-run `validate` after writing the handoff; for recovery-sensitive delivery, run fresh-process `recover` and require the expected typed canonical recovery source.

A handoff is a projection, not permission or canonical Phase authority. It must not convert a successful review command into semantic acceptance, infer authorization from prose, select the latest historical Session, or hide an incomplete workspace transaction.
