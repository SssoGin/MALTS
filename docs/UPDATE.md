# Update MALTS

MALTS updates from a separately reviewed current public repository by default. The updater does not pull Git, discover updates in the background, or download a Release archive. It creates a review-only plan before any installation state changes.

## Before Updating

1. Finish or recover any incomplete lifecycle transaction.
2. Obtain the intended current public repository source.
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
  -RepositoryRoot <PUBLIC_REPOSITORY_ROOT> `
  -LifecycleRoot <LIFECYCLE_ROOT> `
  -Tool Codex `
  -ToolRootCodex <CODEX_ROOT> `
  -PlanPath <NEW_UPDATE_PLAN_PATH>
```

Review the plan before execution. It shows the active and target generation identities, selected projections, user-modification classifications, migration or cleanup actions, rollback actions, and post-validation checks.

```powershell
.\scripts\Update-MALTS.ps1 `
  -Apply `
  -PlanPath <REVIEWED_UPDATE_PLAN_PATH> `
  -ExpectedPlanHash <REVIEWED_UPDATE_PLAN_SHA256>
```

## Optional Offline Archive Update

When the update source must be a fixed offline archive, explicitly verify and extract the single `MALTS-<version>.zip` first. Then invoke the extracted updater with `-ReleaseRoot <EXTRACTED_RELEASE_ROOT>`. The archive is an explicit source choice; it is not a normal updater dependency.

## User Modifications and Cleanup

MALTS classifies existing projected files before changing them:

| Class | Meaning | Default result |
|---|---|---|
| U0 | Missing or exactly MALTS-owned | Replace or remove as planned. |
| U1 | Managed instruction block can be merged | Merge the managed block. |
| U2 | Deterministic evidence-backed merge | Merge only with the recorded validation. |
| U3 | User-owned or ambiguous modification | Stop for an explicit user decision. |
| U4 | Sensitive or unsafe conflict | Fail closed. |

Known legacy layouts may be migrated only when ownership evidence is sufficient. Unknown, user-owned, or ambiguous files are preserved or block the update; they are not silently deleted.

A verified update also replaces a legacy installed-generation provenance envelope that contains an absolute source locator with the current path-free envelope. Do not edit an installed generation manually.

## Recovery

If an update is interrupted, inspect or recover the lifecycle transaction before creating another plan. See [Lifecycle](LIFECYCLE.md) for registry, journal, rollback, and residue behavior.
