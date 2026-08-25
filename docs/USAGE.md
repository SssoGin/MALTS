# Use MALTS in a Project

After lifecycle installation, start work from the tool's MALTS boot pointer.
It resolves the active immutable generation; do not copy runtime files into a
project manually.

## Enter an existing workspace

Do not rerun the initializer for an ordinary task. Classify the task and run one read-only entry assessment:

```powershell
python -B <MALTS_ROOT>\tools\long_workspace.py workspace-entry --workspace <WORKSPACE> --task-class LOW_RISK
```

Available classes are `READ_ONLY`, `LOW_RISK`, `WRITE_EXISTING_SCOPE`, `NEW_WRITE_SCOPE`, `HIGH_RISK`, and `CONTEXT_RECOVERY`. Read only the returned current-set paths. New scope/Phase changes trigger boundary review and Plan Recheck; real canonical/transaction/Admission drift triggers reconcile or recovery. Report/handoff/history loading and maintenance-view writes are not part of ordinary entry.

If no Phase has ever been registered, entry reports `INITIALIZATION_REQUIRED`; if an initialized workspace has only terminal Phases, it reports `PHASE_REQUIRED` and requires a new explicit Phase. Neither path creates a Phase, Session, Agent, or Artifact.

Fresh long workspaces default to CURRENT `single_phase`. To opt into resource-governed parallel Phases, review an initialization or explicit `reorganize-workspace` with `resource_admission`, then create Admission requests that bind typed locators/capabilities, exact Phase bytes, actor, expiry, authorization, and fencing tokens. All mutations are dry-run-first and require `--apply`; no daemon performs renewal.

## Start a project

For a non-trivial new project, define the goal, acceptance criteria, task queue, and
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
- After verification, normal single-agent work performs a no-write Growth Routing Gate automatically. Trivial no-signal work stays silent; non-trivial work or correction/failure/recovery receives a short visible Growth result. Repeated or high-impact evidence recommends, but does not automatically run, Standard/Major retrospective. L2/L3 writes remain separately authorized.
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

Use `phase-boundary-review` before a candidate goal or touch set may leave the active boundary. It is read-only and does not authorize implementation. Treat `status`/`operation_status` as command execution only; inspect `review_outcome`, mapping, recommendation, and `persisted` separately. Use `record-phase-boundary-review` to persist a structured result; that record still does not authorize implementation. Use `pause-phase` when ownership must be preserved but work must stop. Supply a stable Review ID such as `review:phase-030:001`, not a path, to pause/resume; evidence paths remain separate. Before resume, an explicitly selected PAUSED Phase may run read-only `plan-recheck`; PASS validates the binding but grants no execution authority. Use `resume-phase` only with current boundary/plan/authorization evidence. A cross-Phase handoff is a two-step, hash-bound `plan-phase-transition` then `apply-phase-transition` operation with explicit carry-over and disposition files.

```powershell
python -B <MALTS_ROOT>\tools\long_workspace.py phase-boundary-review --workspace <workspace> --candidate-goal <goal> --candidate-touch-set <paths> --candidate-mapping UNCLEAR --recommendation USER_DECISION_REQUIRED
python -B <MALTS_ROOT>\tools\long_workspace.py pause-phase --workspace <workspace> --reason <reason> --boundary-review-ref <review-id> --authorization-ref <ref>
python -B <MALTS_ROOT>\tools\long_workspace.py plan-recheck --workspace <workspace> --phase-id <paused-phase-id> --trigger CONTEXT_RECOVERY --require-active-plan
python -B <MALTS_ROOT>\tools\long_workspace.py resume-phase --workspace <workspace> --phase-id <id> --boundary-review-ref <review-id> --plan-review-ref <ref> --expected-plan-sha256 <sha256> --authorization-ref <ref>
```

Review the dry-run output before adding `--apply`. `SUPERSEDED` is terminal. `active_phase_id` remains the scalar primary Phase; only `resource_admission` may also register additional `OPEN` Phases, and their writes require Admission.

### Reorganize and recover consistency

Fresh workspaces use CURRENT with default `single_phase`. Supported legacy workspace and Result layouts remain readable and are not silently upgraded. Begin with `validate`; when it classifies an input for reorganization, use the exact hashes it reports and review one matching command without `--apply`. The public path always targets CURRENT directly and never asks the user to traverse intermediate versions or a downgrade chain.

```powershell
python -B <MALTS_ROOT>\tools\long_workspace.py record-phase-boundary-review --workspace <workspace> --phase-id <id> --review-id <id> --candidate-mapping SAME_PHASE --recommendation KEEP --evidence-ref <ref> --expected-phase-sha256 <sha256> --operation-id <id>
python -B <MALTS_ROOT>\tools\long_workspace.py recover-workspace-transaction --workspace <workspace> --operation-id <id> --expected-journal-sha256 <sha256>
python -B <MALTS_ROOT>\tools\long_workspace.py reorganize-workspace --workspace <workspace> --operation-id <id> --expected-state-sha256 <sha256> --expected-project-control-sha256 <sha256> [--project-control-candidate <workspace-relative-path> --expected-candidate-sha256 <sha256>] --profile <single_phase-or-resource_admission> --review-ref <ref> --authorization-ref <ref> [--expected-plan-sha256 <sha256>]
python -B <MALTS_ROOT>\tools\long_workspace.py reorganize-result-contract --workspace <workspace> --contract <legacy-or-current-contract> --expected-contract-sha256 <sha256> --expected-phase-control-sha256 <sha256> --expected-phase-boundary-sha256 <sha256> --operation-id <id> --revision-reason <reason> --review-ref <ref> --authorization-ref <ref> [--task-id <tid> --lineage-id <lid> --phase-id <pid> --event-id <eid> --expected-plan-sha256 <sha256>]
```

Applied workspace and coordination authority writes share a unique-writer lock/journal and recheck exact preimages after acquiring the lock. Do not delete an incomplete journal; run the matching exact-journal-hash recovery dry run before `--apply`. Current recovery authority is active Session checkpoint, primary active Phase recovery, explicitly bound terminal Phase, then Project recovery—never the latest historical Session.

### Coordinate resource-profile writes

`workspace_coordination.py` admits typed locators/capabilities, renews/releases leases, verifies fencing, reaps expired grants, and records/reconciles `UNKNOWN` effects. Every mutation is a dry run until `--apply`; renewal is explicit and no daemon is created. Use a request JSON conforming to `workspace_coordination.schema.json`. Non-fenceable exclusive capabilities serialize, and `ISOLATE_REQUIRED` needs a distinct isolation key.

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

## Current workspace commands

- `workspace-entry` / `refresh-maintenance-views`: bounded read-only daily entry and on-demand non-authoritative view rebuild from canonical current controls; older projection prose is not retained.
- `record-result-events` / `rebuild-result-lineage`: typed Result event append and projection rebuild (dry-run by default); resource execution uses CURRENT Result authority.
- `reorganize-workspace` / `reorganize-result-contract`: one-hop, explicit, hash-bound reorganization from any supported legacy input to CURRENT, with matching quiescence and recovery conditions.
- `workspace_coordination.py`: Admission, queue, lease, fencing, quarantine, and reconcile; no heartbeat daemon.
- `plan-phase-boundary-amendment` / `apply-phase-boundary-amendment`: immutable Phase boundary revisions.
- `transfer-session-lease`: hash-bound Session lease owner transfer.
- `scoped-readiness`: read-only S0/S1/S2/ESCALATE route advice; never authorizes or writes.
- `refresh-project-instructions`: rewrites only `MALTS-PROJECT:`-owned blocks with an exact reviewed plan.
