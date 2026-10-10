# MALTS Workspace Management and Store Relocation

MALTS keeps project definitions, task state, evidence and recovery information together while checking business outputs at their actual locations. Current version: **2.0.2**. This guide covers the default management layout, reviewed adoption of a legacy workspace, and relocation of a healthy adopted store. Installation and project-state migration are separate operations.

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

## 4. Relocate a Healthy Adopted Store

### 4.1 Scope and Preconditions

The shipped controller supports a readable, healthy adopted store on Windows fixed local volumes under the same user and machine. The target must be absent; source state, target state and operation journal must not contain each other. Target and journal must share a volume for atomic publication of the restored directory. The old state may be on another fixed local volume. The default target and journal are `.malts/state` and `.malts/recovery/<operation-id>`.

Resolve live Runs, unknown operation effects and unquiesced Host dispatch before planning. An empty Run list does not prove that external Editors, scripts or business writers stopped. The restored store requires an explicit current-epoch resource/effect review before switching authority. Do not mark unknown coverage as reconciled merely to complete relocation.

Network/reparse paths, unsupported internal layouts, cross-user/cross-machine transfer and non-local/cloud-synchronized storage are outside this qualified workflow. A fixed local path alone does not establish that a third-party synchronization client is absent; the operator must exclude synchronized folders. Capacity and access checks are preliminary; a subsequent disk or access failure preserves the partial scene.

### 4.2 Read-Only Plan and Preparation

Select a unique `$OperationId`, existing `$AuthorityRef` and new `$PlanPath`. Save the exact returned JSON as UTF-8:

```powershell
& $PythonExe -B $Cli store-relocation-preflight --workspace $Workspace --operation-id $OperationId --authority-ref $AuthorityRef |
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

Read the original journal's `target.backup_root` as `$BackupRoot`, then save the exact forward plan:

```powershell
& $PythonExe -B $Cli legacy-forward-plan --old-state-dir $Plan.old_state_dir --state-dir $Plan.state_dir --backup-root $BackupRoot --adoption-id $OperationId --authority-ref $AuthorityRef |
    Out-File -LiteralPath $ForwardPath -Encoding utf8NoBOM
$Forward = Get-Content -LiteralPath $ForwardPath -Raw -Encoding utf8 | ConvertFrom-Json
& $PythonExe -B $Cli legacy-forward-apply --plan-file $ForwardPath --expected-plan-sha256 $Forward.plan_sha256 --journal-root $Plan.journal_root --tool-root $ToolRoot
& $PythonExe -B $Cli legacy-forward-apply --plan-file $ForwardPath --expected-plan-sha256 $Forward.plan_sha256 --journal-root $Plan.journal_root --tool-root $ToolRoot --apply
& $PythonExe -B $Cli workspace --workspace $Workspace
& $PythonExe -B $Cli store-relocation-status --journal-root $Plan.journal_root
```

The controller holds both SQLite exclusive locks across the forward transactions, guards managed inputs and directory identities, and rechecks the backup, old state, reconciled target and lineage. Old authority is superseded before the new binding becomes active. During a partial switch both stores may refuse execution; they never gain concurrent active authority. Governed SQLite writers are blocked by real database locks. The profile is not a sandbox for arbitrary raw-file writers; external resource facts remain the reviewed operator's responsibility. SQLite lock retention follows its [exclusive locking contract](https://www.sqlite.org/pragma.html#pragma_locking_mode).

The new epoch revokes old Grants, invalidates acceptance, quarantines leases/Hosts and keeps restored budgets from being replenished. Active/completed Phases are paused by restore. Inspect current governance and explicitly activate the intended Phase after successful switch; do not resume by copying old tokens or re-running completed effects.

## 5. Interruption, Retention and Verification Limits

Keep the original operation ID, plan, journal, backup and target. `store-relocation-status` is read-only. Reapply the original preparation plan for a preparation interruption. Incomplete backup/restore attempts remain for inspection; retry publishes a completed attempt without overwriting them. After a forward interruption, use status's persisted `forward.plan` or `forward-status` and reapply that exact plan. Partial protocol replacements preserve preimages and resume under the original identity. An ACTIVE replay verifies binding and returns the receipt without a new cutover or Host qualification.

If the old store advanced after backup, forward planning/application rejects the stale snapshot. Resolve that divergence rather than forcing hashes or deleting new work. Unreadable old stores and disaster recovery need the existing separate recovery contracts; this healthy-store controller does not silently switch to that path.

Verification covers isolated native/internal adoption, external compatibility, actual SQLite contention, guarded inputs, drift rejection, original-ID continuation and authority switching. It does not establish migration of a particular user project, general Editor isolation, cross-user DPAPI recovery, model behavior or performance gains. Keep originals until project-specific verification and any separately authorized retention/cleanup decision are complete.
