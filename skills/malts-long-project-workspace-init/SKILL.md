---
name: malts-long-project-workspace-init
description: Initialize and govern a phase-ready MALTS long-project workspace with explicit Phase boundaries, owner-scoped Artifact lifecycle, validation, maintenance, compaction, and recovery.
---

# Skill: MALTS Long Project Workspace Init

## Purpose

Create and govern a recoverable workspace for work that spans windows or phases without turning every conversation turn or persistent write into a Session. The same public CLI owns explicit Phase boundary transitions and an opt-in, owner-scoped Artifact lifecycle.

Selecting this dedicated Skill is an affirmative long-project intent signal. Do not silently reduce it to ordinary project initialization. Use `malts-project-init` when the user wants only lightweight root project control.

The fixed root skeleton is deliberately small:

- `AGENTS.md`
- `PROJECT_CONTROL.md`
- `WORK_TASK_REPORT.md`
- thin `CLAUDE.md` containing `@AGENTS.md`
- non-canonical `runtime/`

Initialization is complete only when the same reviewed operation also creates the first active `phases/<phase-id>/PHASE_CONTROL.md`. Later Phases remain explicit `open-phase` operations. Session controls remain explicit `open-session` operations and are never created merely because initialization occurred.

## Initialization contract

Before the first write:

1. Read the nearest applicable instructions and inspect the target workspace.
2. Collect or propose the project ID, original goal, first Phase ID, first Phase goal, and narrative language.
3. Show one dry-run plan containing the root controls, `runtime/workspace_control.json`, and first `PHASE_CONTROL.md`.
4. If the first Phase information is missing, stop with zero writes and ask for it. Do not ask the user to choose between a silent minimal profile and a full profile.
5. Apply only the exact reviewed plan after authorization.

After apply, report all of the following explicitly:

- controls created and existing files preserved;
- active Phase ID;
- active Session ID, normally `None`;
- that no Session was created by design;
- the condition for opening a bounded Session;
- validation and cold-recovery results.

A legacy workspace with root controls but zero registered Phases is `NEEDS_INITIAL_PHASE`, not a completed long-project initialization. Repair it without overwriting existing user files by supplying the missing initial Phase to `init`, or by explicitly opening its first Phase.

## Authorization boundary

- `validate` and `recover` are read-only.
- Every state-changing command is a dry run unless `--apply` is present.
- Show the dry-run plan and obtain authorization before using `--apply` unless the current authorization already names that exact operation and workspace.
- Never overwrite an existing user file. If an existing file prevents a safe operation, fail closed and report its path.
- Never create a Session because of a conversation turn, ordinary file write, `validate`, `maintain`, or `compact`.
- Do not schedule automatic, periodic, background, or ordinary-use update checks. Update discovery remains user-requested only.
- Do not dispatch Agents, use Git, call a provider, or access the network as part of this Skill.

## State ownership

| Layer | Owns | Must not own |
|---|---|---|
| Project | Original goal, global acceptance, active phase index, cross-phase decisions, compact Artifact enrollment/index pointers | Per-Artifact rows or per-turn logs |
| Phase | Phase goal, boundary contract, active plan binding, queue, deliverables, evidence, optional owner-local Artifact Registry, closure and growth | Other phases' active state |
| Session | Inherited plan binding, bounded scope, commands, touch set, checkpoint, optional owner-local Artifact Registry | Canonical project goal, plan authority, or implicit creation authority |
| Shared / Archive | Optional `shared/INDEX.md` current reusable authority and `archive/INDEX.md` cold/superseded history | Project goal or active queue |
| `runtime/` | Cache, generated state, lock, journal and measurements | Canonical Markdown truth or live Artifact authority |

`runtime/workspace_control.json` is an index and recovery aid. Canonical Markdown controls remain authoritative.

## Commands

Resolve `MALTS_ROOT` from the active boot pointer, then invoke:

```powershell
python -B <MALTS_ROOT>\tools\long_workspace.py init --workspace <workspace> --project-id <id> --goal <goal> --language en --initial-phase-id <phase-id> --initial-phase-goal <phase-goal>
python -B <MALTS_ROOT>\tools\long_workspace.py init --workspace <workspace> --project-id <id> --goal <goal> --language zh-CN --initial-phase-id <phase-id> --initial-phase-goal <phase-goal> --apply
python -B <MALTS_ROOT>\tools\long_workspace.py open-phase --workspace <workspace> --phase-id <id> --goal <goal> --apply
python -B <MALTS_ROOT>\tools\long_workspace.py close-phase --workspace <workspace> --status DONE --apply
python -B <MALTS_ROOT>\tools\long_workspace.py phase-boundary-review --workspace <workspace> --candidate-goal <goal> --candidate-touch-set <paths> --candidate-mapping UNCLEAR --recommendation USER_DECISION_REQUIRED
python -B <MALTS_ROOT>\tools\long_workspace.py migrate-phase-control --workspace <workspace> --phase-id <id> --milestone <milestone> --in-scope <scope> --out-of-scope <scope> --exit-criteria <criteria> --carry-over-policy <policy> --boundary-review-triggers <triggers>
python -B <MALTS_ROOT>\tools\long_workspace.py pause-phase --workspace <workspace> --reason <reason> --boundary-review-ref <ref> --authorization-ref <ref> --apply
python -B <MALTS_ROOT>\tools\long_workspace.py resume-phase --workspace <workspace> --phase-id <id> --boundary-review-ref <ref> --plan-review-ref <ref> --expected-plan-sha256 <sha256> --authorization-ref <ref> --apply
python -B <MALTS_ROOT>\tools\long_workspace.py plan-phase-transition --workspace <workspace> --source-phase-id <id> --target-phase-id <id> --target-goal <goal> --carry-over-file <json> --disposition-file <json> --boundary-review-ref <ref> --authorization-ref <ref> --plan-out <json>
python -B <MALTS_ROOT>\tools\long_workspace.py apply-phase-transition --workspace <workspace> --plan <json> --expected-plan-sha256 <sha256> --apply
python -B <MALTS_ROOT>\tools\long_workspace.py open-session --workspace <workspace> --session-id <id> --goal <goal> --reason bounded-work-session --apply
python -B <MALTS_ROOT>\tools\long_workspace.py close-session --workspace <workspace> --status DONE --next-action <action> --apply
python -B <MALTS_ROOT>\tools\long_workspace.py validate --workspace <workspace>
python -B <MALTS_ROOT>\tools\long_workspace.py plan-recheck --workspace <workspace> --trigger CONTEXT_RECOVERY
python -B <MALTS_ROOT>\tools\long_workspace.py plan-recheck --workspace <workspace> --trigger BEFORE_NEW_WRITE_SCOPE --require-active-plan
python -B <MALTS_ROOT>\tools\long_workspace.py maintain --workspace <workspace>
python -B <MALTS_ROOT>\tools\long_workspace.py compact --workspace <workspace>
python -B <MALTS_ROOT>\tools\long_workspace.py recover --workspace <workspace>
```

If either initial Phase argument is missing, `init` fails closed with `WS_INITIAL_PHASE_REQUIRED` and writes nothing. Use `--apply` only after the corresponding write scope is authorized. `close-phase` requires no active Session. A new Phase or Session cannot be opened while one at the same layer is active.

## Phase lifecycle contract

- `phase-boundary-review` is read-only. Run it when the candidate goal or touch set may cross the active Phase boundary; an `UNCLEAR` or outside-scope result cannot authorize a write.
- `migrate-phase-control` upgrades a legacy active Phase without overwriting its existing goal, queue, evidence, or recovery record.
- `pause-phase` preserves ownership and recovery state but forbids new Phase work until `resume-phase` rebinds boundary review, plan review, exact plan hash, and authorization evidence.
- Cross-Phase carry-over uses `plan-phase-transition` followed by hash-bound `apply-phase-transition`. The source record is immutable, the target record is mutable, and their provenance is bidirectional.
- `SUPERSEDED` is terminal. At most one Phase may be `ACTIVE`; transition apply fails closed on stale bytes, active Sessions, incomplete disposition, or changed plan/hash preconditions.

## Artifact lifecycle contract

The contract defaults to `NOT_ENROLLED`. Read-only `artifact audit`, top-level `validate`, `maintain`, `compact`, and `recover` preserve legacy schema-v1 behavior and never enroll a workspace, create a Session, create empty Artifact directories, or recursively scan undeclared payload trees.

```powershell
python -B <MALTS_ROOT>\tools\long_workspace.py artifact audit --workspace <workspace> --captured-at <timestamp>
python -B <MALTS_ROOT>\tools\long_workspace.py artifact enrollment-preview --workspace <workspace> --captured-at <timestamp>
python -B <MALTS_ROOT>\tools\long_workspace.py artifact enrollment-apply --workspace <workspace> --operation-id <id> --captured-at <timestamp> --apply
python -B <MALTS_ROOT>\tools\long_workspace.py artifact register --workspace <workspace> --owner phase:<phase-id> --role WORKING --locator <path> --authority WORKSPACE --vcs LOCAL_ONLY --verification UNVERIFIED --retention <contract> --disposition KEEP_OWNED --operation-id <id> --apply
python -B <MALTS_ROOT>\tools\long_workspace.py artifact promote --workspace <workspace> --source phase:<phase-id>:<artifact-id> --purpose <purpose> --applies-to <scope> --retention <contract> --last-verified <timestamp> --operation-id <id> --apply
python -B <MALTS_ROOT>\tools\long_workspace.py artifact supersede --workspace <workspace> --old shared:<old-id> --new shared:<new-id> --operation-id <id> --apply
python -B <MALTS_ROOT>\tools\long_workspace.py artifact reconcile --workspace <workspace> --owner phase:<phase-id> --disposition <json> --operation-id <id> --apply
```

All Artifact mutations are dry-run unless `--apply` is explicit. They require an enrolled contract, stable owner-local IDs, exact locator/authority/VCS/verification/retention/disposition fields, a unique operation ID, a workspace-scoped lock, a persisted journal, and full-state hash preconditions. Mutation never moves or deletes payloads and never runs VCS. Promotion and supersession update every declared control atomically or roll back exact bytes. Closing an enrolled Phase or Session with `UNRESOLVED` rows is blocked; no Artifact command performs implicit Session creation.

## Plan Recheck contract

Plan Recheck is event-triggered and read-only; it is not a daemon, timer, background watcher, or second plan registry. The active Phase owns the active plan reference, revision, raw-byte SHA-256, timestamps, supersession, status, last trigger/result, and launch-review invalidation. Root `PROJECT_CONTROL.md` keeps only an index. An active Session inherits the Phase plan reference/revision/hash and records authorization/scope recheck plus launch-review evidence without becoming plan authority.

Canonical triggers are `PHASE_SWITCH`, `BEFORE_LAUNCH_REVIEW`, `BEFORE_NEW_WRITE_SCOPE`, `AFTER_WORKER_RETURN`, `BEFORE_VERIFIER`, `AFTER_VERIFIER`, `USER_CHANGE`, `CONTEXT_RECOVERY`, `FAILURE_OR_ROLLBACK`, and `FINAL_DELIVERY`. Canonical recorded results are `PASS`, `UPDATED`, `BLOCKED`, and `N/A`.

Use `--require-active-plan` for S3/S4 implementation, launch review, verifier, recovery/rollback, and final delivery gates. A missing plan, byte drift, stale trigger, invalid binding, split Session/root index, or invalidated launch review returns `BLOCKED`; stop and reconcile the canonical controls. S0/S1 work without a bound Phase plan may return `N/A`. The command never writes controls or creates authorization.

## Capacity and semantic compaction

`maintain` measures root, active Phase, and active Session controls separately for lines, bytes, active tasks, open decisions, evidence references, and stale-history ratio. Budgets are soft signals; exceeding one does not silently discard content.

Only blocks explicitly delimited as follows are eligible for `compact`:

```text
<!-- MALTS:history:start id=<stable-id> -->
closed historical detail
<!-- MALTS:history:end -->
```

Compaction moves those exact blocks to `history/PROJECT_CONTROL_HISTORY.md` and leaves an archive reference. Current goal, open decisions, active queue, acceptance criteria, risks, latest evidence, and recovery points must remain outside history blocks. Malformed or nested markers fail closed.

## Recovery contract

Read current sources in this order:

1. nearest `AGENTS.md` instruction;
2. root `PROJECT_CONTROL.md`;
3. active `PHASE_CONTROL.md`;
4. active/latest `SESSION_CONTROL.md`, report, or handoff;
5. only owner/Shared/Archive Artifact indexes explicitly referenced by those current controls;
6. current files and `runtime/workspace_control.json` evidence.

Treat summaries and runtime state as recovery aids only. They never replace the active MALTS version, current files, or a required runtime probe.

## Verification

Before reporting success:

1. Run `validate`.
2. Require `initialization_status=READY`, a non-empty Phase registry, and an active initial Phase for a newly initialized workspace.
3. Confirm `active_session_id` remains `None` unless the user explicitly opened a bounded Session.
4. Run `python -B <MALTS_ROOT>\tools\malts_user_tools.py check-project-control --project-control PROJECT_CONTROL.md --malts-root <MALTS_ROOT>`.
5. For recovery-sensitive delivery, run `recover` from a fresh process and record its ordered read evidence.
6. Keep full three-tool discovery/invocation/behavior verification for the G4 runtime gate; component tests alone are not G4.
7. For an active S3/S4 Phase, run the matching `plan-recheck` trigger and require `recheck_result=PASS` before the gated action or completion claim.
8. If Artifact enrollment is `ENROLLED`, require `artifact audit`, top-level `validate`, exact registry/index references, zero unresolved close blockers, and no stale transaction lock/journal before qualification.
