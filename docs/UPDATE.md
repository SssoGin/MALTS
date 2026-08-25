# Update MALTS

MALTS updates from a separately reviewed current repository checkout by default. The updater does not pull Git, discover updates in the background, or download a Release archive. It creates a review-only plan before any installation state changes.

An installation update does not reorganize project workspaces or Result Contracts. After activation, an old workspace remains on its existing compatibility behavior until a separate one-hop `reorganize-workspace` or `reorganize-result-contract` dry run is reviewed and explicitly applied. Reorganization binds exact source hashes, review/authorization references, one fixed timestamp, and a recoverable journal. It never runs during ordinary `workspace-entry`, `validate`, `recover`, or generation switching.

Do not patch an active generation to obtain CURRENT workspace contract. Change and verify the maintenance source, then cross the candidate, activation, Git, tag, and public Release gates separately. Default single-profile workspaces do not need the concurrency profile and incur no coordination state.

## Before Updating

1. Finish or recover any incomplete lifecycle transaction.
2. Obtain the intended current repository source.
3. Verify `MALTS_RELEASE.json`, `VERSION`, and, when available, the checked-out Git tag.
4. Identify the existing lifecycle root and every selected tool root.
5. Back up user-owned tool configuration through the tool's normal procedure when appropriate.

Do not update from an unverified folder. A repository identity mismatch, unexpected file, cache, or `.malts` residue stops the planning operation.

## Repository Update Review

From the reviewed repository source:

```powershell
.\scripts\Update-MALTS.ps1 `
  -RepositoryRoot (Get-Location).Path `
  -UseDefaultRoots `
  -Tool Codex
```

For explicit roots:

```powershell
.\scripts\Update-MALTS.ps1 `
  -RepositoryRoot <REPOSITORY_ROOT> `
  -LifecycleRoot <LIFECYCLE_ROOT> `
  -Tool Codex `
  -ToolRootCodex <CODEX_ROOT> `
  -PlanPath <NEW_UPDATE_PLAN_PATH>
```

Review the plan before execution. It shows the active and target version identities, selected projections, user-modification classifications, migration or cleanup actions, rollback actions, and post-validation checks.

```powershell
.\scripts\Update-MALTS.ps1 `
  -Apply `
  -PlanPath <REVIEWED_UPDATE_PLAN_PATH> `
  -ExpectedPlanHash <REVIEWED_UPDATE_PLAN_SHA256>
```

## Version Migration And Collision Handling

Stable versions use `malts-v<version>`, while isolated previews use
`malts-v<version>-preview.<sequence>`. Recognized legacy IDs such as
`malts-1.0.0-<hash>` remain migration inputs; MALTS does not rename them in
place or treat their physical paths as current pointers.

An update stages and prevalidates the target before switching the registry, active pointer, and selected tool-local Boot/projection transaction unit. The installed managed instruction records the exact installed `MALTS_BOOT_PATH`; it is never resolved relative to `cwd` or a project file. The old version is cleaned only after post-validation proves that no authoritative reference still points to it. A same-version exact match is a no-op; a same-version content conflict or unbound same-name directory fails before writes. Process loss resumes or rolls back through the transaction journal.

## Optional Offline Archive Update

When the update source must be a fixed offline archive, explicitly verify and extract the single `MALTS-<version>.zip` first. Then invoke the extracted updater with `-ReleaseRoot <EXTRACTED_RELEASE_ROOT>`. The archive is an explicit source choice; it is not a normal updater dependency.

## User Modifications And Cleanup

MALTS classifies existing projected files before changing them:

| Class | Meaning | Default result |
|---|---|---|
| U0 | Missing or exactly MALTS-owned | Replace or remove as planned. |
| U1 | Managed instruction block can be merged | Merge the managed block. |
| U2 | Deterministic evidence-backed merge | Merge only with the recorded validation. |
| U3 | User-owned or ambiguous modification | Stop for an explicit user decision. |
| U4 | Sensitive or unsafe conflict | Fail closed. |

Known legacy layouts may be migrated only when ownership evidence is sufficient. Unknown, user-owned, or ambiguous files are preserved or block the update; they are not silently deleted.

A verified update also replaces any old absolute source locator in the installed provenance with the current path-free record. Do not edit an installed version manually.

## Diagnose Before Repair

Use `Invoke-MALTSLifecycle.ps1 -Command Doctor` with the lifecycle root and all selected tool roots before attempting repair. Doctor is read-only and distinguishes derived boot/projection drift from invalid core payload, manifest, registry, or pointer state.

For locally consistent core state, `DoctorRepairPlan` may scope derived repair targets from the active version, but that recommendation is not itself an executable mutation. Persist an executable repair plan only with the exact verified source that matches the installed binding; then review its hash and execute it as a separate authorized transaction.

## Update Workspace Controls

Updating MALTS installs new runtime behavior but does not rewrite project controls. Supported legacy long-project layouts remain readable, fresh workspaces use CURRENT with default `single_phase`, and Artifact lifecycle stays `NOT_ENROLLED`. The resource profile and every reorganization remain explicit workspace operations.

Run `validate` first and preserve its exact state hash/classification. If it reports a supported legacy layout, review one `reorganize-workspace` dry run that classifies every retained, moved, archived, or derived section and targets CURRENT directly. Apply only the same hash-bound plan under current workspace authorization. Legacy parser and consistency-repair details stay internal; validation and recovery never reorganize automatically.

Run `artifact audit` before considering enrollment. A legacy `shared/`-like directory is only a candidate observation; it is never silently adopted. If enrollment is wanted, run `artifact enrollment-preview`, review exact index paths and findings, then run `artifact enrollment-apply` with a unique operation ID and explicit `--apply`.

If a Boundary Review remains unresolved after reorganization, persist a structured result only through `record-phase-boundary-review` with the exact Phase SHA-256; recording is not authorization for later mutation. Ambiguous non-empty duplicate markers or legacy prose semantics fail closed rather than being inferred.

Interrupted workspace/coordination authority writes use the shared `runtime/workspace_transaction.lock.json` and `runtime/workspace_transactions/`, separate from Artifact transactions. Review `recover-workspace-transaction` with the exact journal SHA-256 before adding `--apply`; failed recovery retains the evidence.

No update path moves/deletes payloads, invokes VCS, creates a Session, selects the newest historical Session as recovery authority, or starts an automatic/background workspace scan. Roll back the installed MALTS generation through the lifecycle plan; never copy old templates over canonical workspace controls. Workspace reorganization recovers original bytes or uses explicit reconcile evidence.

## Recovery

If an update is interrupted, inspect or recover the lifecycle transaction before creating another plan. See [Lifecycle](LIFECYCLE.md) for registry, journal, rollback, and residue behavior.

## Post-Update Discovery

After a successful update, run read-only discovery for every selected tool root. Each exact installed `MALTS_BOOT_PATH` must resolve the same new active version and match registry, active pointer, and `VERSION`. MALTS does not use a machine-global Boot for ordinary discovery. Do not keep using a stale tool boot or guess a version path; repair follows a separately reviewed lifecycle transaction.
