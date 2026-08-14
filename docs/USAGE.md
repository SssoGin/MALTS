# Use MALTS in a Project

After lifecycle installation, start work from the tool's MALTS boot pointer.
It resolves the active immutable generation; do not copy runtime files into a
project manually.

## Start a project

For a non-trivial task, define the goal, acceptance criteria, task queue, and
recovery point in `PROJECT_CONTROL.md`. Record execution evidence in
`WORK_TASK_REPORT.md`. Create `PROJECT_HANDOFF.md` when another Agent needs to
continue the work.

Use the matching runtime templates under `runtime/EN/` or `runtime/CH/` as
drafting references. Keep one canonical control, report, and handoff file unless
the user explicitly requests a translated mirror.

## Choose the right workflow

- Use `malts-project-init` when only lightweight root project control is needed.
- Use `malts-long-project-workspace-init` when the project will span phases,
  windows, interruptions, or recovery boundaries. Selecting it is the choice
  for a long-project workspace: initialization creates the root controls and
  first active Phase together. It does not silently stop at a minimal skeleton.
- Use Grill-Me Preflight when goals, assumptions, tradeoffs, or acceptance
  criteria need clarification.
- Keep simple work single-agent.
- For a user-approved long or multi-agent task, show the launch review before
  dispatching work.
- Use the handoff skill when continuation context must survive a session change.

The long-project initializer requires an initial Phase ID and goal. Its dry run
must list the initial `PHASE_CONTROL.md`; missing Phase input causes a zero-write
failure. After apply, check `initialization_status=READY` and the active Phase.
No Session is created by initialization. Open one only for an explicit bounded
work-session boundary.

If an older workspace has root controls but no registered Phase, validation
reports `WS_INITIAL_PHASE_MISSING`. Supply its initial Phase through the
initializer or explicitly open its first Phase; existing user files are
preserved.

## When MALTS Requests An Isolated Preview

For a candidate that can change runtime, boot, registry, or tool discovery,
the Agent should show the preview scope, explicit absolute root, verification,
and cleanup boundary and wait for confirmation. You do not need to guess when
the sandbox is required: release preparation reports `PREVIEW_REQUIRED` and
the Agent must surface that state before running it.

The preview uses fresh processes with process-local isolated configuration for
Codex, Claude Code, and OpenCode. If any tool cannot be isolated, it is
reported `BLOCKED`; the Agent must not fall back to the real tool root. You may
explicitly waive the preview, but the result records real-tool integration as
`NOT RUN` and is not fully release-qualified.

## Verify project control

The user helper validates the stable project-control structure and, when a
MALTS root is supplied, its active version reference:

```powershell
python -B <MALTS_ROOT>\tools\malts_user_tools.py check-project-control `
  --project-control <PROJECT_CONTROL_PATH> `
  --malts-root <MALTS_ROOT>
```

## Diagnose Without Changing State

Use `scripts\Invoke-MALTSLifecycle.ps1 -Command Doctor` with the lifecycle root
and each selected tool root to inspect an installation. Doctor reports exact
drift and trust evidence with `writes_performed=false`. It does not repair,
update, clean, or start a background check. A suggested repair must enter a
separate review-only plan and exact plan-hash authorization flow.

## Govern Phase And Artifact Lifecycle

### Review and change a Phase

Use `phase-boundary-review` before a candidate goal or touch set may leave the active boundary. It is read-only and does not authorize implementation. Treat `status`/`operation_status` as command execution only; inspect `review_outcome`, mapping, recommendation, and `persisted` separately. Use `record-phase-boundary-review` to persist a structured result; that record still does not authorize implementation. Use `pause-phase` when ownership must be preserved but work must stop; use `resume-phase` only with current boundary/plan/authorization evidence. A cross-Phase handoff is a two-step, hash-bound `plan-phase-transition` then `apply-phase-transition` operation with explicit carry-over and disposition files.

```powershell
python -B <MALTS_ROOT>\tools\long_workspace.py phase-boundary-review --workspace <workspace> --candidate-goal <goal> --candidate-touch-set <paths> --candidate-mapping UNCLEAR --recommendation USER_DECISION_REQUIRED
python -B <MALTS_ROOT>\tools\long_workspace.py pause-phase --workspace <workspace> --reason <reason> --boundary-review-ref <ref> --authorization-ref <ref>
python -B <MALTS_ROOT>\tools\long_workspace.py resume-phase --workspace <workspace> --phase-id <id> --boundary-review-ref <ref> --plan-review-ref <ref> --expected-plan-sha256 <sha256> --authorization-ref <ref>
```

Review the dry-run output before adding `--apply`. `SUPERSEDED` is terminal and at most one Phase can be `ACTIVE`.

### Migrate, record, and reconcile consistency

Fresh workspaces use schema v4. Schema v1/v2/v3 remain readable and are not silently upgraded. Begin with `validate`; if it returns a migration or reconciliation classification, use the exact hashes it reports and review the matching command without `--apply` (`migrate-workspace-v3-to-v4` and `migrate-result-contract-v1-to-v2` for v1.3.0 cold migration; legacy `migrate-consistency-records`, `record-phase-boundary-review`, and `reconcile-consistency-records` stay dry-run-first).

```powershell
python -B <MALTS_ROOT>\tools\long_workspace.py migrate-consistency-records --workspace <workspace> --authority workspace-state --expected-state-sha256 <sha256> --operation-id <id>
python -B <MALTS_ROOT>\tools\long_workspace.py record-phase-boundary-review --workspace <workspace> --phase-id <id> --review-id <id> --candidate-mapping SAME_PHASE --recommendation KEEP --evidence-ref <ref> --expected-phase-sha256 <sha256> --operation-id <id>
python -B <MALTS_ROOT>\tools\long_workspace.py reconcile-consistency-records --workspace <workspace> --authority canonical-controls --expected-state-sha256 <sha256> --expected-source-sha256 <sha256> --expected-phase-sha256 <sha256> --operation-id <id>
python -B <MALTS_ROOT>\tools\long_workspace.py recover-workspace-transaction --workspace <workspace> --operation-id <id> --expected-journal-sha256 <sha256>
```

Applied consistency writes use an isolated workspace transaction lock/journal and `WS_TRANSACTION_*` errors. Do not delete an incomplete journal; run the exact-journal-hash recovery dry run before `--apply`. Current recovery authority is active Session checkpoint, active Phase recovery, explicitly bound terminal Phase, then Project recovery—never the latest historical Session.

### Audit, enroll, and mutate Artifacts

Start with `artifact audit`; do not create index files manually. If the result is `LEGACY_UNDECLARED`, the workspace remains compatible but not enrolled. Use enrollment preview/apply only when owner, Shared, and Archive boundaries are understood.

```powershell
python -B <MALTS_ROOT>\tools\long_workspace.py artifact audit --workspace <workspace> --captured-at <timestamp>
python -B <MALTS_ROOT>\tools\long_workspace.py artifact enrollment-preview --workspace <workspace> --captured-at <timestamp>
python -B <MALTS_ROOT>\tools\long_workspace.py artifact enrollment-apply --workspace <workspace> --operation-id <id> --captured-at <timestamp> --apply
python -B <MALTS_ROOT>\tools\long_workspace.py artifact register --workspace <workspace> --owner phase:<phase-id> --role WORKING --locator <path> --authority WORKSPACE --vcs LOCAL_ONLY --verification UNVERIFIED --retention <contract> --disposition KEEP_OWNED --operation-id <id> --apply
```

Promotion requires verified source evidence. Supersession preserves old payload/history and either updates every reviewed active reference atomically or fails closed. Reconcile applies only explicit owner dispositions. All mutations are dry-run by default and never move/delete payloads, invoke VCS, recursively scan undeclared trees, or create a Session.

## Safety defaults

Plan before writing. Keep tool-root changes inside the user's approved scope.
Verify before reporting completion, and do not enable unattended continuation
unless the user explicitly authorizes its objective, limits, stop conditions,
and recovery behavior.

## Plan Recheck And Codex Peer Tasks

For an active S3/S4 long-project Phase, bind the active plan path, revision, and raw-byte SHA-256 in `PHASE_CONTROL.md`. Run read-only `long_workspace.py plan-recheck` at the applicable event before new write scope, launch review, verifier, recovery/rollback, or final delivery. The root control is only an index, and a Session only inherits the binding. `BLOCKED` stops the action; the command never edits controls or creates authorization.

Codex can use a governed peer task when native sub-agent dispatch cannot satisfy an approved hard model/effort contract and the official task/thread interface can. The task uses the current project workspace, is recorded as `codex-peer-task` / `peer-task`, has no silent fallback, reuses the same task for rework, and is archived only after Main Controller acceptance or terminal closure. This is part of the existing multi-agent Skill, not a separate Skill or hidden child Agent.

## MALTS v1.3.0 commands

- `record-result-events` / `rebuild-result-lineage`: typed Result v2 event append and projection rebuild (dry-run by default).
- `migrate-workspace-v3-to-v4` / `migrate-result-contract-v1-to-v2`: explicit hash-bound cold migrations; quiescence required.
- `plan-phase-boundary-amendment` / `apply-phase-boundary-amendment`: immutable Phase boundary revisions.
- `transfer-session-lease`: hash-bound Session lease owner transfer.
- `scoped-readiness`: read-only S0/S1/S2/ESCALATE route advice; never authorizes or writes.
- `refresh-project-instructions`: rewrites only `MALTS-PROJECT:`-owned blocks with an exact reviewed plan.
