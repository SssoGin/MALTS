# MALTS Workspace Management and Store Relocation

MALTS keeps project definitions, task state, evidence and recovery information together while checking business outputs at their actual locations. Current version: **2.1.0**. This guide covers the default management layout, reviewed adoption of a legacy workspace, and relocation of a healthy native or adopted store. Installation and project-state migration are separate operations.

## 1. Default Layout and Ownership

```text
<workspace>/
  <business files and existing controls>
  runtime/v2_binding.json          # adopted workspace only
  .malts/
    management.json               # ownership of this management namespace
    native.json                   # native workspace locator, when initialized
    state/                        # database, referenced blobs and managed inputs
    source-capsules/<adoption-id>/ # selected original source bytes
    recovery/<operation-id>/       # relocation plans, backups and recovery records
```

`state` is long-lived authoritative data. A capsule preserves the selected original controls and explicitly selected payloads; it is not a backup of every business asset. Recovery records belong to the operation that created them. Keep these private directories outside public exports. A version-control exclusion for `.malts/` must be reviewed according to the project's own policy; MALTS does not silently edit SVN or Git settings.

The ownership marker identifies the workspace that owns `.malts`; it does not replace the state database or grant execution permission. An existing directory without a matching marker, unknown top-level contents, a foreign locator, a nonempty target or a linked path blocks the relevant preparation. MALTS does not claim user files by renaming or overwriting them.

New ordinary workspaces use the internal layout. Explicit external state/capsule paths remain supported. Existing external bindings are not moved by installation, entry queries or an update; use the relocation procedure below only when that change is authorized. The supported internal state location is `.malts/state`; a different internal subtree is not implicitly supported.

## 2. Initialize a Native Workspace

Resolve `$MaltsRoot`, `$PythonExe` and `$ToolRoot` through the selected tool's Boot and lifecycle discovery. Select an existing project directory as `$Workspace`. Use the verified runtime:

```powershell
$Cli = Join-Path $MaltsRoot 'tools/malts_v2.py'
& $PythonExe -B $Cli workspace-init --workspace $Workspace --project-id $ProjectId --goal $Goal
& $PythonExe -B $Cli workspace-init --workspace $Workspace --project-id $ProjectId --goal $Goal --apply
& $PythonExe -B $Cli workspace --workspace $Workspace
```

The first command checks and describes the target without creating directories or a database. Apply creates the owned namespace and native store; the final query verifies the locator, Project identity, resource root and epoch. It creates no Phase, Session or Run. Define the current Project and Phase, bind the actual plan and Tasks, and explicitly activate the intended Phase for long-project readiness. See [controller operations](V2_PREVIEW_USAGE.md).

Use `--state-dir '<explicit-external-state>'` for a deliberately external native store. The lower-level `init --state-dir` remains available to existing controllers, but does not create a workspace locator. Do not run native initialization against imported, adopted or partially migrated state.

## 3. Adopt Legacy Controls Inside the Workspace

Run `legacy-adoption-preflight --source-root $Workspace` before persistent preparation. Its default capsule is `.malts/source-capsules/adoption` and default state is `.malts/state`. To use an adoption-specific capsule, supply `--capsule-root` with `.malts/source-capsules/<adoption-id>`; supply explicit external paths for the advanced external layout.

After authorization for the exact layout, preview and apply `management-init --workspace $Workspace`. Then follow [source staging, mapping, semantic review and adoption](V2_PREVIEW_USAGE.md#v2-migration) using the returned paths. The capsule and state must remain separate from each other. Containment under the source workspace is allowed only in the owned management namespace.

Source inventory is bounded to indexed controls and explicit selections. Its hashed `source_selection` contract excludes `.malts` from migration inputs. Management writes therefore do not alter the selected source hash, and a capsule cannot collect itself. Hidden business files outside that namespace remain eligible when explicitly selected. A control or selected payload actually located under `.malts` is a conflict to resolve, not content silently omitted from a migration. Existing historical capsules without this contract remain usable for their existing external adoption; new internal preparation requires the reviewed selection contract.

`archive-only` preserves verified inactive terminal Phase/Session controls without importing their executable definitions. Only `DONE`, `CANCELLED` and `FAILED` qualify. `SUPERSEDED`, `BLOCKED`, active controls and unverified identities do not. Staging preview reports the selected identity and unsupported status before copying; it does not rewrite historical controls to make them qualify.

The Windows adoption handoff freezes the reviewed source files and protects their namespace while the candidate database commits. Management data is outside the business-operation resource surface even when physically inside the workspace. This separates logical authority without requiring sibling directories or granting arbitrary applications access to state files.

## 4. Relocate a Healthy Store

### 4.1 Scope and Preconditions

The shipped controller supports a readable, healthy native or adopted store on Windows fixed local volumes under the same user and machine. The target must be absent; source state, target state and operation journal must not contain each other. Target and journal must share a volume for atomic publication of the restored directory. The old state may be on another fixed local volume. The default target and journal are `.malts/state` and `.malts/recovery/<operation-id>`.

Resolve live Runs, unknown operation effects and unquiesced Host dispatch before planning. An empty Run list does not prove that external Editors, scripts or business writers stopped. The restored store requires an explicit current-epoch resource/effect review before switching authority. Do not mark unknown coverage as reconciled merely to complete relocation.

Network/reparse paths, unsupported internal layouts, cross-user/cross-machine transfer and non-local/cloud-synchronized storage are outside this qualified workflow. A fixed local path alone does not establish that a third-party synchronization client is absent; the operator must exclude synchronized folders. Capacity and access checks are preliminary; a subsequent disk or access failure preserves the partial scene.



Native stores do not need a fabricated legacy import. Preflight discovers an existing native locator. A store created through lower-level `init --state-dir` without a locator additionally requires `--old-state-dir $OldState`: `$Workspace` is the Project business resource root, and `$OldState` is the existing database directory. They are distinct identities. Returned `source_kind` is `NATIVE_EXPLICIT`, `NATIVE_LOCATOR` or `ADOPTED`. Do not use `workspace-init` to relocate an existing store: it creates a new store without transferring Tasks, dependencies, history or budgets.

### 4.2 Read-Only Plan and Preparation

Select a unique `$OperationId`, existing `$AuthorityRef` and new `$PlanPath`. Save the exact returned JSON as UTF-8:

```powershell
# NATIVE_EXPLICIT: $OldState is the existing database directory; $Workspace is the business root.
$SourceArguments = @('--old-state-dir', $OldState)
# NATIVE_LOCATOR or ADOPTED: resolve through the project entry instead.
# $SourceArguments = @()
& $PythonExe -B $Cli store-relocation-preflight --workspace $Workspace @SourceArguments --operation-id $OperationId --authority-ref $AuthorityRef |
    Out-File -LiteralPath $PlanPath -Encoding utf8NoBOM
$Plan = Get-Content -LiteralPath $PlanPath -Raw -Encoding utf8 | ConvertFrom-Json
& $PythonExe -B $Cli store-relocation-prepare --plan-file $PlanPath --expected-plan-sha256 $Plan.plan_sha256 --tool-root $ToolRoot
& $PythonExe -B $Cli store-relocation-prepare --plan-file $PlanPath --expected-plan-sha256 $Plan.plan_sha256 --tool-root $ToolRoot --apply
& $PythonExe -B $Cli store-relocation-status --journal-root $Plan.journal_root
```

For an explicit external target, add `--target-state-dir` at preflight; select `--journal-root` as needed. The plan binds normalized paths, user/machine identity, source protocol hashes, current state hash and the file closure. Any source-state advancement after preview rejects preparation. Preparation takes the actual SQLite exclusive lock, creates a verified backup, restores a new epoch under quarantine, and atomically publishes the restored target. It preserves the old authority at this stage.

The closure copies database-referenced blobs, STATE-scoped plans, selected legacy source, mappings and protected operation inputs through the existing backup contract. PROJECT-scoped files keep their project locations. Unreferenced historical files and absolute Host/evidence references retain their original paths and are listed as `RETAIN_EXTERNAL_HISTORY`; their old directories must remain available. This procedure neither rewrites historical strings nor authorizes deletion of the old store or separate source capsule.

### 4.3 Recovery Review

Status returns `recovery_inventory` and a `recovery_review_template`. The template deliberately contains `UNKNOWN` coverage and an unresolved-effect placeholder. Save it as a new review file; review every Project root, historical Task scope, actual writer and effect against current facts. Record the real authority/evidence references and Task dispositions. Remove unresolved effects only after resolving them. Preserve terminal history and keep continuing work paused unless its next action has been reviewed.

```powershell
& $PythonExe -B $Cli recovery-review --state-dir $Plan.state_dir --review-file $ReviewPath
# Read the returned plan_sha256, then apply that exact reviewed report:
& $PythonExe -B $Cli recovery-review --state-dir $Plan.state_dir --review-file $ReviewPath --expected-plan-sha256 $ReviewHash --apply
```

Review is operator-attested, not independent proof of arbitrary external writer isolation. It binds the exact restored epoch and inventory. A stale report, UNKNOWN coverage, unresolved effects or incomplete writer coverage blocks reconciliation.

### 4.4 Forward Switch and Verification

Save the exact journal-based forward plan for the selected source kind:

```powershell
& $PythonExe -B $Cli store-relocation-plan --journal-root $Plan.journal_root |
    Out-File -LiteralPath $ForwardPath -Encoding utf8NoBOM
$Forward = Get-Content -LiteralPath $ForwardPath -Raw -Encoding utf8 | ConvertFrom-Json
& $PythonExe -B $Cli store-relocation-apply --plan-file $ForwardPath --expected-plan-sha256 $Forward.plan_sha256 --journal-root $Plan.journal_root --tool-root $ToolRoot
& $PythonExe -B $Cli store-relocation-apply --plan-file $ForwardPath --expected-plan-sha256 $Forward.plan_sha256 --journal-root $Plan.journal_root --tool-root $ToolRoot --apply
& $PythonExe -B $Cli workspace --workspace $Workspace
& $PythonExe -B $Cli store-relocation-status --journal-root $Plan.journal_root
```

The controller holds both SQLite exclusive locks across the forward transactions, guards managed inputs and directory identities, and rechecks the backup, old state, reconciled target and lineage. Old authority is superseded before the new binding becomes active. During a partial switch both stores may refuse execution; they never gain concurrent active authority. Governed SQLite writers are blocked by real database locks. The profile is not a sandbox for arbitrary raw-file writers; external resource facts remain the reviewed operator's responsibility. SQLite lock retention follows its [exclusive locking contract](https://www.sqlite.org/pragma.html#pragma_locking_mode).

The new epoch revokes old Grants, invalidates acceptance, quarantines leases/Hosts and keeps restored budgets from being replenished. Active/completed Phases are paused by restore. Inspect current governance and explicitly activate the intended Phase after successful switch; do not resume by copying old tokens or re-running completed effects.



### 4.5 Native Authority and Long Paths

Native relocation shares backup, recovery review and actual handoff locks, then appends native lifecycle facts to the existing execution audit and atomically changes `.malts/native.json`. The target progresses through restored quarantine, prepared and active authority. Once the old store is durably superseded, services reject both its execution and ordinary writes, including new Tasks. No legacy import, adoption row or empty replacement project is created. Active authority binds the state location, epoch, workspace, original journal and receipt hash. Locator preimages and incomplete attempts support continuation under the original identity.

Windows managed-file copying, hashing, backup verification, restore and handoff file handles use an internal extended-path spelling. Public plans, references and locators retain normal normalized paths. Valid managed files exceeding 260 full-path characters can therefore be processed without changing `LongPathsEnabled`. Filesystem component limits remain applicable; link, reparse, hard-link and managed-reference checks are unchanged. Database and protocol control roots remain bounded: new preflight conservatively rejects a layout when a derived control path exceeds its 240-character budget, with `RELOCATION_CONTROL_PATH_TOO_LONG`. This differs from a long managed relative file. Copy errors report `MANAGED_FILE_IO_FAILED`, operation, character count and OS error code without private file names or a false preparation-success claim.

## 5. Interruption, Retention and Verification Limits

Keep the original operation ID, plan, journal, backup and target. `store-relocation-status` is read-only. Reapply the original preparation plan for a preparation interruption. Incomplete backup/restore attempts remain for inspection; retry publishes a completed attempt without overwriting them. After a forward interruption, use status's persisted `forward.plan` (`forward-status` remains available for adopted stores) and reapply that exact plan. Partial protocol replacements preserve preimages and resume under the original identity. An ACTIVE replay verifies binding and returns the receipt without a new cutover or Host qualification.

If the old store advanced after backup, forward planning/application rejects the stale snapshot. Resolve that divergence rather than forcing hashes or deleting new work. Unreadable old stores and disaster recovery need the existing separate recovery contracts; this healthy-store controller does not silently switch to that path.

Verification covers isolated native/internal adoption, external compatibility, actual SQLite contention, guarded inputs, drift rejection, original-ID continuation and authority switching. It does not establish migration of a particular user project, general Editor isolation, cross-user DPAPI recovery, model behavior or performance gains. Keep originals until project-specific verification and any separately authorized retention/cleanup decision are complete.

Existing v2.0.2 version-1 relocation plans and PREPARING journals remain usable. After updating the runtime, read original `store-relocation-status` and repeat `store-relocation-prepare` with the original plan file, plan hash, operation ID and journal. Preserve failed attempts; do not edit the journal or create a new ID to hide unresolved state. Complete current-epoch resource/effect review, then continue through `store-relocation-plan` / `store-relocation-apply`. Existing adopted-store `legacy-forward-*` interfaces remain compatible. Long-path validation uses owned Windows fixtures and does not prove migration of a particular user project.

## 6. Current Entry, Diagnostics and Recovery Proof

After relocation, call `entry-status` and `workspace` with the Project business root, then use the returned `state_dir`. Do not hard-code the old external store in project scripts. A superseded native endpoint reports `SUPERSEDED`, `authority_state=SUPERSEDED` and `write_allowed=false`, retaining its original operation identity and continuation hint. `COMPATIBLE` describes format compatibility, not Task, Grant, budget or external-process readiness. A located native entry is `OWNED_NATIVE_STORE`; an unlocated explicit store retains a direct-store classification.

`capabilities.schema_migration` describes automatic database upgrade; `store_relocation` describes moving an existing store; `legacy_adoption` describes reviewed legacy control adoption. Deprecated `migration_supported` means automatic schema upgrade and never determines relocation support. Native and adopted stores use the unified journal-based commands above; `legacy-forward-*` remains an adopted-store compatibility interface.

CLI stdout/stderr use strict UTF-8. PowerShell7 should save with `Out-File -Encoding utf8NoBOM`. A .NET process capture must set both stream encodings to UTF-8 and use `ArgumentList`. Recheck saved JSON against its reviewed hash; do not apply text after replacement of Chinese characters or emoji. A mismatch reports `PLAN_HASH_MISMATCH`, stage, source kind and safe expected/computed digests. Reload the original plan instead of hiding unresolved effects under a new ID. Package failures preserve a stable cause code, safe context and counts. CLI and MCP `malts_entry_status` share this implementation; MCP inspects its configured project root only.

### 6.1 Registered Effects and External Writers

Recovery review separately declares `registered_effect_coverage`, `external_writer_coverage` and `external_writer_isolation_assurance`. New templates default external coverage and isolation to UNKNOWN; existing reports still require every Project root and registered resource. Successful review may establish `registered_effects_reconciled=true` while `external_writer_isolation=UNKNOWN` remains true. Operator review of business roots is not independently verified physical isolation. Declarative INDEPENDENTLY_VERIFIED does not supply evidence. Actual unresolved effects still block; empty writer/pending lists, a successful restore and format compatibility never prove external-process quiescence.

CLI, MCP, recovery and Host observations expose `execution_assurance` or equivalent direct fields, including authentication not enforced, native adapters unqualified and external isolation UNKNOWN. Trusted-controller APIs still require the selected adapter, current Task revision/epoch/Grant/budget and identity bindings. A request requiring `require_independently_qualified_adapter=true` is rejected as `UNQUALIFIED_ADAPTER`. These service checks do not certify arbitrary Editors, raw SQL clients, cross-session/machine isolation or unattended Agent authentication.

### 6.2 Layered Backup Proof and Isolated Recovery

`verify-backup --destination $BackupRoot` verifies physical closure, database structure, managed inputs and stored evidence references without writes. `identity_layers` distinguishes the backup database file, manifest and semantic-state digests. SQLite backup bytes may differ from source bytes, and restored semantic state changes with epoch; never compare unlike layers.

```powershell
& $PythonExe -B $Cli verify-backup --destination $BackupRoot
# Read identity_layers.backup_manifest_sha256 as $BackupHash; select an absent new destination.
& $PythonExe -B $Cli verify-backup --destination $BackupRoot --mode isolated-recovery --recovery-destination $SmokeRoot --expected-backup-sha256 $BackupHash
& $PythonExe -B $Cli verify-backup --destination $BackupRoot --mode isolated-recovery --recovery-destination $SmokeRoot --expected-backup-sha256 $BackupHash --apply
```

Isolated checking restores a new-epoch store and reads current-user Project/Phase/Task definitions, actual plans, dependency structure, recovery history and stored references. Only success returns `content_recovery_verified=true`; its declared decode/reference scope does not certify all evidence plaintext or cross-user recovery. It neither replaces production state nor reconciles external writers, grants resume/execution or activates Phases. Failures are retained without automatic deletion. PROJECT plans are checked at their business root; STATE plans travel with the managed closure.

### 6.3 Preservation Stages

`workspace-audit --workspace $Workspace` provides an official read-only project-root entry. An optional `--baseline-file` uses a `malts.preservation.v1` manifest whose files each contain path, bytes and SHA-256. Every original file is checked regardless of location. Pre-adoption mode reports `LEGACY_PREPARATION_SCOPE_STALE` after legitimate v2 management additions, rather than treating additions as lost original content. Current-v2 mode validates owned management and binding files; other additions require explicit reviewed `--allow-new-path` scope. Unknown additions remain review items. Project-local preparation/preservation scripts should adopt this staged pattern; an installation does not rewrite those scripts automatically.

## 7. Entry Reports, Relocation Next Actions and Final Verification

`entry-status` separately reports runtime discovery, selected binding and package checking. Package states are PACKAGE_CHECK_NOT_PERFORMED, PACKAGE_CHECK_UNAVAILABLE, PACKAGE_CHECK_FAILED and PACKAGE_CHECK_VERIFIED. Storage unavailability differs from confirmed package drift; the valid workspace-binding result is retained. A failed check grants neither verified installation integrity nor execution. The default CLI is a read-only report command: exit0 means the report was produced. Automation uses `--strict`; noncompatible conditions or unsuccessful requested deep checking return3, while command/input errors return2.

`store-relocation-status` returns completion_level and next_required_actions on the original journal. PREPARING resumes original preparation; RESTORED_NOT_ACTIVE needs current-epoch recovery review; FORWARD_READY needs forward planning/application; FORWARD_CUTOVER_INCOMPLETE resumes the original forward plan; ACTIVE_NOT_PHASE_READY needs Phase review/activation; ACTIVE_PHASE_READY still requires Task continuation and permission checks. This changes no state or original identity and executes no suggestion automatically.

```powershell
& $PythonExe -B $Cli entry-status --workspace $Workspace --tool-root $ToolRoot --verify-package --strict
& $PythonExe -B $Cli store-relocation-status --journal-root $Plan.journal_root
& $PythonExe -B $Cli workspace-final-verify --workspace $Workspace --tool-root $ToolRoot --operation-id $OperationId --journal-root $Plan.journal_root --verify-package --strict
```

Final verification is read-only and binds runtime identity, protocol hashes, selected state/epoch, original operation receipt, old-authority supersession, current Project/Phase and actual plan, Task definitions/bindings and dependency structure into completion_receipt_sha256. It uses one database read snapshot and rechecks runtime, locks, protocol and active plan before returning. This is not an atomic snapshot across files/processes or external-writer isolation. A normal bound project can omit operation-id; a specific relocation must use its exact original ID/journal. Phase readiness, paused Tasks and business completion remain distinct. The digest fingerprints the current observation and must be reverified after relevant input changes.

### 7.1 Continue Tasks After Recovery

Restore pauses nonterminal Tasks and invalidates old Grants/acceptance. `recovery-next-task-actions --state-dir $StateDir --project-id $ProjectId` lists current revisions, Phase bindings, unresolved dependencies, recovery_disposition and recommended paths without writes; task-queue also exposes resume_after_recovery_required. KEEP_PAUSED retains an explicit decision point; REVERIFY requires new verification after review. Neither proves old business acceptance remains valid.

When goal/scope/acceptance are unchanged, the controller can preview/apply the following closed `task.resume-after-recovery` request. expected_epoch comes from the current workspace; review_id identifies its reconciled original recovery review. The service requires current revision, active Phase and actual plan, accepted dependencies and settled registered effects/writers. It changes only a matching KEEP_PAUSED Task to READY, creating no Run/Grant or replenished budget/acceptance. This is a controller operation and is not automatically exposed to MCP Workers.

```json
{"action":"task.resume-after-recovery","arguments":{"task_id":"<exact-task>","expected_revision":1,"expected_epoch":"<current-epoch>","review_id":"<current-review>","request_id":"<stable-continuation-id>","authority_ref":"<approved-review>"}}
```

```powershell
& $PythonExe -B $Cli request --state-dir $StateDir --request-file $ContinuationFile
& $PythonExe -B $Cli request --state-dir $StateDir --request-file $ContinuationFile --tool-root $ToolRoot --apply
```

A changed goal/scope/acceptance uses formal task.revise with explicit review_ref and a new revision; budgets remain cumulative, and dependencies/Phase binding follow current contracts. Ordinary pauses with a valid owned Run/checkpoint use run.resume. Closed or invalidated pre-restore Runs cannot be revived through that path. Manual database edits from PAUSED to READY are unsupported.

### 7.2 Result Layers and Authority Responsibilities

Reports distinguish operation_status, workspace_status, governance_readiness, execution_authorization and external_writer_assurance. SUCCESS/VERIFIED can coexist with NOT_GRANTED. OPERATOR_ATTESTED describes the current operator resource review; external_writer_isolation stays UNKNOWN and never becomes independently verified physical isolation.

ADOPTED_BINDING uses runtime/v2_binding.json and its adoption/forward receipt without requiring native.json. NATIVE_LOCATOR uses the owned .malts/native.json; NATIVE_EXPLICIT uses the explicitly selected native store. management.json identifies management-namespace ownership and replaces no runtime authority.

### 7.3 Project Integration and Public Regression

Project entry instructions should invoke the installed tools/malts_v2.py with the exact MALTS control workspace for workspace, workspace-final-verify and current Task queries. These provide MALTS governance state and cannot replace actual Unity Editor/process or Unity MCP observations. A project referring to a missing unity_workspace_status.py needs its maintainer to restore that project script or update the reference to the available MALTS entry while retaining separate Editor checks. MALTS installation neither invents that script nor edits an unselected project.

Public CI exercises long managed-file backup/restore, actual forward handoff, old-authority fencing, original-ID replay and recovery guidance in owned Windows temporary projects. It records actual LongPathsEnabled without registry changes. Separate local evidence covers 260+ paths with LongPathsEnabled=0, original version1 journals, retained failed attempts and native/adopted interruption recovery. Hosted runners do not qualify every user project or Windows version; each result retains its own scope.

## Refreshing Host References After A Forward Switch

MALTS 2.0.6 adds an `external_configuration` advisory to successful `store-relocation-apply` and `legacy-forward-apply` CLI results. It uses the original plan's old/new state directories to find references requiring regeneration. The selected tool's known locations are inspected; include other files explicitly with repeated `--host-config HOST=ABSOLUTE_PATH`. Custom locations and unselected Hosts are not implicitly covered.

This advisory does not change the reviewed plan, migration journal, epoch, Grants or transaction outcome, and does not edit Host configuration. Follow [MCP configuration and recovery](MCP_CONFIGURATION.md), then verify the actual connection and selected Project separately. An empty regeneration list with an unsupported or failed check is not a clean bill of health.
