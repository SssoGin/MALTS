---
name: malts-long-project-workspace-init
description: Initialize, structurally recover, migrate, or govern a phase-ready MALTS long-project workspace; ordinary unchanged task entry uses the bounded read-only workspace-entry path instead of rerunning initialization.
---

# Skill: MALTS Long Project Workspace Init

## Purpose

Create and govern a recoverable workspace for work that spans windows or phases without turning every conversation turn or persistent write into a Session. The same public CLI owns explicit Phase boundary transitions and an opt-in, owner-scoped Artifact lifecycle.

Selecting this dedicated Skill is an affirmative long-project intent signal. Do not silently reduce it to ordinary project initialization. Use `malts-project-init` when the user wants only lightweight root project control. Do not invoke this full initializer merely because an already initialized workspace received another ordinary task.

The fixed root skeleton is deliberately small:

- `AGENTS.md`
- `PROJECT_CONTROL.md`
- `WORK_TASK_REPORT.md`
- thin `CLAUDE.md` containing `@AGENTS.md`
- non-canonical `runtime/`

Initialization is complete only when the same reviewed operation also creates the first active `phases/<phase-id>/PHASE_CONTROL.md`. Later Phases remain explicit `open-phase` operations. Session controls remain explicit `open-session` operations and are never created merely because initialization occurred.

## Invocation boundary and daily entry

Use the full workflow for first initialization, structural repair, explicit schema/profile migration, or a major lifecycle change. For an existing workspace, classify entry before loading broad context:

| Situation | Required route |
|---|---|
| Unrelated/read-only question | Read only the user-supplied or directly relevant files; do not initialize or create MALTS entities. |
| Initialized, unchanged, same-scope ordinary task | Run read-only `workspace-entry` with the matching task class; load only its bounded current-set read list. |
| New write scope or Phase switch | Run `workspace-entry`, then the required Phase Boundary Review and Plan Recheck. |
| Context/window recovery | Run `workspace-entry --task-class CONTEXT_RECOVERY`; escalate to full `recover` only when its report blocks, the user requests a full recovery packet, or a recovery-sensitive gate requires it. |
| Real structural, binding, transaction, lease/fencing, or external-effect drift | Fail closed for the affected authority/resource and use the explicit reconcile or recovery command. |

`workspace-entry` never writes, creates Phase/Session/Agent/Artifact records, scans full history, or grants mutation authority. Repeated entry with unchanged bytes must produce the same decision and zero workspace writes. For CURRENT ordinary work without an active Session, `single_phase` is bounded to four files / 24 KiB and `resource_admission` to five files / 28 KiB; an active Session raises only the explicit current-set allowance. The host loads applicable instruction files before invoking the tool. The CURRENT ordinary read list therefore contains runtime current binding plus the selected Phase, and adds only an active Session or required coordination state. Project control, report, handoff, and history are loaded only by an explicit Project-level/review/recovery gate. A legacy v4 compatibility entry remains bounded to six files and 96 KiB.

No registered Phase is `INITIALIZATION_REQUIRED`; an initialized workspace with no active/open Phase is `PHASE_REQUIRED`. Both outcomes remain zero-write and require an explicit Phase operation rather than silently creating one.

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
| Project | Original goal, global acceptance, active phase index, cross-phase decisions, Project recovery record, compact Artifact enrollment/index pointers | Per-Artifact rows, Phase recovery, or per-turn logs |
| Phase | Phase goal, boundary contract, Boundary Review record, active plan binding, queue, deliverables, evidence, Phase recovery, optional owner-local Artifact Registry, closure and growth | Other phases' active state or report projection authority |
| Session | Inherited plan binding, bounded scope, commands, touch set, checkpoint/recovery record, optional owner-local Artifact Registry | Canonical project goal, plan authority, or implicit creation authority |
| Shared / Archive | Optional `shared/INDEX.md` current reusable authority and `archive/INDEX.md` cold/superseded history | Project goal or active queue |
| `runtime/` | Cache, generated state, lock, journal and measurements | Canonical Markdown truth or live Artifact authority |

`runtime/workspace_control.json` is an index and recovery aid. Canonical Markdown controls remain authoritative.

For ordinary discovery, the active-generation pointer is exactly `<lifecycle-root>\\registry\\active_generation.json`. Use the successful `discover` result's `authority_paths.active_generation_pointer`; never probe `<lifecycle-root>\\active_generation.json` or derive a pointer from a copied generation path.

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
python -B <MALTS_ROOT>\tools\long_workspace.py workspace-entry --workspace <workspace> --task-class LOW_RISK
python -B <MALTS_ROOT>\tools\long_workspace.py workspace-entry --workspace <workspace> --task-class NEW_WRITE_SCOPE --phase-id <phase-id> [--admission-id <id> --actor-id <id> --token <domain>=<epoch> ...]
python -B <MALTS_ROOT>\tools\long_workspace.py refresh-maintenance-views --workspace <workspace> --operation-id <id> --expected-state-sha256 <sha> --expected-phase-sha256 <sha>
python -B <MALTS_ROOT>\tools\long_workspace.py record-phase-boundary-review --workspace <workspace> --phase-id <id> --review-id <id> --candidate-mapping SAME_PHASE --recommendation KEEP --evidence-ref <ref> --authorization-ref <ref-or-N/A> --expected-phase-sha256 <sha256> --operation-id <id>
python -B <MALTS_ROOT>\tools\long_workspace.py recover-workspace-transaction --workspace <workspace> --operation-id <id> --expected-journal-sha256 <sha256>
python -B <MALTS_ROOT>\tools\long_workspace.py plan-recheck --workspace <workspace> --trigger CONTEXT_RECOVERY
python -B <MALTS_ROOT>\tools\long_workspace.py plan-recheck --workspace <workspace> --trigger BEFORE_NEW_WRITE_SCOPE --require-active-plan
python -B <MALTS_ROOT>\tools\long_workspace.py maintain --workspace <workspace>
python -B <MALTS_ROOT>\tools\long_workspace.py compact --workspace <workspace>
python -B <MALTS_ROOT>\tools\long_workspace.py recover --workspace <workspace>
python -B <MALTS_ROOT>\tools\long_workspace.py record-result-events --workspace <workspace> --contract <current-contract> --events <batch.json>
python -B <MALTS_ROOT>\tools\long_workspace.py rebuild-result-lineage --workspace <workspace> --contract <current-contract> --operation-id <id>
python -B <MALTS_ROOT>\tools\long_workspace.py plan-phase-boundary-amendment --workspace <workspace> --phase-id <id> --revision-id <rid> --review-id <review> --review-evidence-ref <ref> --authorization-ref <ref> --accepted-at <ts>
python -B <MALTS_ROOT>\tools\long_workspace.py apply-phase-boundary-amendment --workspace <workspace> --phase-id <id> --revision-id <rid> --review-id <review> --review-evidence-ref <ref> --authorization-ref <ref> --accepted-at <ts> --apply
python -B <MALTS_ROOT>\tools\long_workspace.py transfer-session-lease --workspace <workspace> --operation-id <id> --expected-session-sha256 <sha> --actor-kind MAIN_CONTROLLER --actor-id <owner> --new-owner-kind <kind> --new-owner-id <id> --new-lease-id <lease> --authorization-ref <ref> --evidence-ref <ref>
python -B <MALTS_ROOT>\tools\long_workspace.py reorganize-workspace --workspace <workspace> --operation-id <id> --expected-state-sha256 <sha> --expected-project-control-sha256 <sha> [--project-control-candidate <workspace-relative-path> --expected-candidate-sha256 <sha>] --profile single_phase|resource_admission --review-ref <ref> --authorization-ref <ref> [--expected-plan-sha256 <sha>]
python -B <MALTS_ROOT>\tools\long_workspace.py reorganize-result-contract --workspace <workspace> --contract <legacy-or-current-contract> --expected-contract-sha256 <sha> --expected-phase-control-sha256 <sha> --expected-phase-boundary-sha256 <sha> --operation-id <id> [--revision-id <rid> --task-id <tid> --lineage-id <lid> --phase-id <pid> --event-id <eid>] --revision-reason <reason> --review-ref <ref> --authorization-ref <ref> [--expected-plan-sha256 <sha>]
python -B <MALTS_ROOT>\tools\long_workspace.py scoped-readiness --workspace <workspace> [--durable-delta NONE|DURABLE|UNKNOWN]
python -B <MALTS_ROOT>\tools\long_workspace.py refresh-project-instructions --workspace <workspace> --operation-id <id> --target AGENTS.md=<sha> --block <marker>=<source>=<sha>
python -B <MALTS_ROOT>\tools\workspace_coordination.py inspect --workspace <workspace>
python -B <MALTS_ROOT>\tools\workspace_coordination.py admit --workspace <workspace> --request <request.json> --operation-id <id> --timestamp <ts>
python -B <MALTS_ROOT>\tools\workspace_coordination.py renew --workspace <workspace> --admission-id <id> --actor-id <id> --expires-at <ts> --operation-id <id> --timestamp <ts>
python -B <MALTS_ROOT>\tools\workspace_coordination.py release --workspace <workspace> --admission-id <id> --actor-id <id> --operation-id <id> --timestamp <ts> --evidence-ref <ref>
python -B <MALTS_ROOT>\tools\workspace_coordination.py reap-expired --workspace <workspace> --actor-kind SYSTEM_RECOVERY --actor-id <id> --operation-id <id> --timestamp <ts> --evidence-ref <ref>
python -B <MALTS_ROOT>\tools\workspace_coordination.py record-unknown --workspace <workspace> --admission-id <id> --actor-id <id> --affected-scope RESOURCE_DOMAINS --operation-id <id> --timestamp <ts> --evidence-ref <ref>
python -B <MALTS_ROOT>\tools\workspace_coordination.py reconcile --workspace <workspace> --quarantine-id <id> --resolution <resolution> --actor-kind MAIN_CONTROLLER --actor-id <id> --authorization-ref <ref> --operation-id <id> --timestamp <ts> --evidence-ref <ref>
python -B <MALTS_ROOT>\tools\workspace_coordination.py verify --workspace <workspace> --admission-id <id> --phase-id <id> --actor-id <id> --token <domain>=<epoch> --timestamp <ts>
python -B <MALTS_ROOT>\tools\workspace_coordination.py recover --workspace <workspace> --operation-id <id> --expected-journal-sha256 <sha>
```

If either initial Phase argument is missing, `init` fails closed with `WS_INITIAL_PHASE_REQUIRED` and writes nothing. Use `--apply` only after the corresponding write scope is authorized. `close-phase` requires no active Session. `single_phase` retains one active Phase and rejects a second open Phase; `resource_admission` keeps one scalar primary `active_phase_id` and may register additional `OPEN` Phases whose writes require resource Admission. A Session is still explicit and singular.

## Phase lifecycle contract

- `phase-boundary-review` is read-only. Run it when the candidate goal or touch set may cross the active Phase boundary; an `UNCLEAR` or outside-scope result cannot authorize a write.
- `phase-boundary-review.status` is compatibility-only operation execution status. Read `operation_status`, `review_outcome`, `candidate_mapping`, `recommendation`, and `persisted`; operation success never means that a semantic decision was resolved or recorded.
- `record-phase-boundary-review` is the only public command that persists the structured review into the Phase authority and refreshes its projections. The record is not later mutation authorization; pause/resume/transition still require their own authorization reference.
- `migrate-phase-control` upgrades a legacy active Phase without overwriting its existing goal, queue, evidence, or recovery record.
- `pause-phase` preserves ownership and recovery state but forbids new Phase work until `resume-phase` rebinds boundary review, plan review, exact plan hash, and authorization evidence.
- Cross-Phase carry-over uses `plan-phase-transition` followed by hash-bound `apply-phase-transition`. The source record is immutable, the target record is mutable, and their provenance is bidirectional.
- `SUPERSEDED` is terminal. `active_phase_id` remains the single primary Phase index. `single_phase` permits only that one open Phase; `resource_admission` may additionally keep registered `OPEN` Phases, but their writes are legal only under a valid Admission. Transition apply fails closed on stale bytes, active Sessions, incomplete disposition, or changed plan/hash preconditions.

## Cross-control consistency contract

- Fresh workspaces use the exact closed CURRENT workspace and Result contracts. The default profile is `single_phase`; `resource_admission` is opt-in. Supported legacy layouts remain readable internal compatibility inputs and are never silently rewritten by `workspace-entry`, `validate`, `recover`, maintenance, or installation switching.
- `reorganize-workspace` and `reorganize-result-contract` are the only public reorganization paths. Each reads any supported legacy layout and produces one reviewed CURRENT target in a single dry-run/apply transaction; there are no user-visible intermediate layouts, chained version hops, or downgrade path. Reuse one fixed `--timestamp` from reviewed dry run through apply. Reorganization creates no Session, Agent, Artifact, Phase, background service, or unrelated Workspace.
- `PROJECT_CONTROL.md` owns Project facts, each `PHASE_CONTROL.md` owns its Phase facts and plan/boundary/recovery records, and an explicit `SESSION_CONTROL.md` owns its bounded checkpoint. Runtime indexes are typed, non-canonical recovery aids and must never overwrite Markdown authority.
- In CURRENT contract, `WORK_TASK_REPORT.md` and an existing `PROJECT_HANDOFF.md` are on-demand, derived, non-authoritative views. Staleness is a `WARNING`; refresh only with `refresh-maintenance-views` and exact state/Phase preimages. The command rebuilds selected views from canonical current controls and does not carry older projection prose forward; it creates the report on demand, replaces a handoff only when it already exists and `--include-existing-handoff` is explicit, and is a byte-preserving no-op when current.
- Keep machine fields and stable status codes in English. Render user-facing lifecycle/status text with `malts_user_tools.py render-user-status`, selecting explicit user language first, then `NarrativeLanguage`, then English fallback. Simplified Chinese output includes the Chinese meaning and original code, for example `已返回（RETURNED）`; do not maintain a second translation table in a template or adapter.
- A legacy workspace retains its strict compatibility projection bindings until explicit CURRENT reorganization. Do not reinterpret its drift as a derived-view warning or silently reorganize it.
- Canonical control drift, boundary/recovery inconsistency, stale hashes, invalid generation/plan/Admission/fencing preconditions, unresolved transactions, and unknown authority-affecting side effects remain `BLOCKED`. Derived report/handoff drift and unrelated historical maintenance differences are warnings or local reconcile work and do not freeze unrelated resources.
- CURRENT Result Contract holds exact execution authority for resource-governed mutation. Typed events are append-only, projections are rebuildable, and an `UNKNOWN` external effect is quarantined until exact evidence selects an explicit resolution. No Phase, Session, report, handoff, or runtime summary becomes a second full Attempt ledger.
- `max_authorized_rounds` is an independent runtime STOP gate; `scoped-readiness` advises only and never authorizes, writes, or dispatches.
- `validate` reports structural, binding, deterministic-consistency, maintenance-warning, and advisory-semantic layers separately. Only stable structured fields are authoritative; never infer mapping, recommendation, or authorization from prose or timestamps.
- Workspace and coordination authority mutations share `runtime/workspace_transaction.lock.json` and `runtime/workspace_transactions/<operation-id>.json`. The writer rechecks exact preimages after acquiring the lock. Artifact transaction paths and `ART_TRANSACTION_*` codes remain separate and unchanged.
- An incomplete transaction is never auto-deleted. Use the matching recovery command with the exact reviewed journal SHA-256; dry-run before `--apply`. Recovery restores recorded original bytes or fails closed while retaining lock/journal evidence.

## Resource Admission and capability contract

This contract is active only for CURRENT contract `resource_admission`; default single-Phase workspaces do not create or load coordination state.

- A request binds an Admission ID, Phase ID, exact Phase-control SHA-256, actor, expiry, authorization, typed locators, capabilities, and evidence. Admission grants runtime write authority only; it does not decide Phase goals or replace user authorization.
- Locator kinds are `PATH`, `ARTIFACT`, `RECORD`, `SERVICE`, `DEVICE`, and `ENVIRONMENT`. Path normalization detects exact and parent/child overlap; declared aliases connect otherwise different locators to one conflict domain. Artifact and logical records conflict by typed identity, not incidental string similarity.
- Capability modes are `SHARED`, `EXCLUSIVE`, `QUEUED`, and `ISOLATE_REQUIRED`. Queued capability requests advance deterministically. Non-fenceable exclusive work must serialize; `ISOLATE_REQUIRED` work proceeds only with a distinct declared isolation key.
- Each granted conflict domain receives a monotonically increasing fencing epoch and an expiring lease. The holder must explicitly `renew`; MALTS creates no heartbeat daemon. Every write verifies the Admission, actor, Phase binding, unexpired lease, and exact fencing tokens. Expired or superseded executors are stale and cannot resume writing with an old token.
- `reap-expired` releases only expired grants. If an external side effect is `UNKNOWN`, `record-unknown` quarantines the affected resource domains; use `WORKSPACE_AUTHORITY` only when the root authority, transaction head, or recovery source is itself uncertain. Unrelated domains may continue. Reconcile requires an explicit resolution, authorization, evidence, and a fresh fenced operation.
- All workspace/coordination writers use the same unique-writer lock and post-lock compare-and-swap. This prevents a Result event, Admission release, or root-state update from validating a preimage concurrently and then overwriting newer authority.
- A raw editor, shell, database client, device tool, or third-party Agent that bypasses MALTS cannot be fenced by documentation alone. Adapters must route governed writes through Admission verification, or classify the resource as serialized/isolated and fail closed when enforcement cannot be established.

## Artifact lifecycle contract

The contract defaults to `NOT_ENROLLED`. Read-only `artifact audit`, top-level `validate`, `maintain`, `compact`, and `recover` preserve legacy compatibility behavior and never enroll a workspace, create a Session, create empty Artifact directories, or recursively scan undeclared payload trees.

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

An explicitly selected `PAUSED` Phase may run read-only `plan-recheck` for recovery review before `resume-phase`. A PASS proves only that the bound plan and indexes are current; it grants no execution authority. `pause-phase`, `resume-phase`, and `record-phase-boundary-review` require a stable boundary Review ID such as `review:phase-030:001`, not a file path. Put the evidence path in the separate evidence-reference field.

Canonical triggers are `PHASE_SWITCH`, `BEFORE_LAUNCH_REVIEW`, `BEFORE_NEW_WRITE_SCOPE`, `AFTER_WORKER_RETURN`, `BEFORE_VERIFIER`, `AFTER_VERIFIER`, `USER_CHANGE`, `CONTEXT_RECOVERY`, `FAILURE_OR_ROLLBACK`, and `FINAL_DELIVERY`. Canonical recorded results are `PASS`, `UPDATED`, `BLOCKED`, and `N/A`.

Use `--require-active-plan` for S3/S4 implementation, launch review, verifier, recovery/rollback, and final delivery gates. The requested trigger is validated against the current plan bytes, revision, scope, and evidence; the previously recorded trigger is evidence and is not required to equal the new event. A missing plan, byte drift, invalid binding, split Session/root index, or invalidated launch review returns `BLOCKED`; stop and reconcile the canonical controls. S0/S1 work without a bound Phase plan may return `N/A`. The command never writes controls or creates authorization.

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

For ordinary entry, run `workspace-entry` first and read only the returned current-set paths. Escalate to full recovery only for a blocked entry, an explicit recovery request, an incomplete/unknown transaction, real canonical drift, or a recovery-sensitive gate. Full recovery reads current sources in this order:

1. nearest `AGENTS.md` instruction;
2. root `PROJECT_CONTROL.md`;
3. active `PHASE_CONTROL.md`;
4. active `SESSION_CONTROL.md` when one exists;
5. only owner/Shared/Archive Artifact indexes explicitly referenced by those current controls;
6. current files and `runtime/workspace_control.json` evidence.

Load `WORK_TASK_REPORT.md` or `PROJECT_HANDOFF.md` only when the task is reporting/handoff work or the recovery decision explicitly identifies it as relevant. Do not load full history during ordinary entry. Treat summaries and runtime state as recovery aids only. They never replace the active MALTS version, current files, or a required runtime probe.

For CURRENT and supported legacy layouts, recovery authority is deterministic: active Session checkpoint, otherwise primary active Phase recovery, otherwise an explicitly bound terminal Phase, otherwise Project recovery. Never select the latest historical Session by time or list order. Secondary `OPEN` Phases are selected explicitly by Phase ID and never replace the primary recovery pointer by recency.

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
9. For CURRENT contract, require empty safety-critical structural/binding/deterministic issue lists, classify derived-view drift as warnings, and verify the selected governance profile. For a legacy compatibility input, require its existing strict projection bindings and the explicit legacy classification reported by `validate`.
10. For an unchanged daily entry, record the workspace-entry counters, require zero history files and zero writes, and byte-compare the workspace before and after repeated fresh-process runs. Keep deep `validate` and `recover` measurements separate from this fast path.
11. For `resource_admission`, test disjoint and overlapping locators, parent/child paths, all capability modes, expiry, stale fencing, queue order, interrupted transactions, `UNKNOWN`, local quarantine, and explicit reconcile. Also verify a generic non-engine resource example.
12. Confirm no `runtime/workspace_transaction.lock.json` or incomplete workspace/coordination journal remains; committed/rolled-back/reconciled journals are evidence and are not treated as current locks.
