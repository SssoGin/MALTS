# Update MALTS

An update selects verified source content and changes the chosen installation through a reviewed transaction. The updater preserves project work and user-owned configuration according to its plan; it does not select a new goal or migrate projects automatically. Current version: **2.0.2**.

## Before Updating

Inspect the installed identity, intended source, workspace binding, user edits, relevant writers and pending effects. Preserve recovery materials. The updater does not pull Git and performs no automatic repository selection, automatic ZIP download, provider call or implicit project migration. Current version remains **2.0.2**.

Compare the active source kind/hash, intended repository/package identity and actual selected tool roots. Identify whether a normal version update or same-version content consolidation is needed. Preserve required transaction snapshots and project backups for their different recovery purposes.

Check relevant writers and unsettled effects before changing shared installations. Do not use PAUSED or a missing response as process-stop evidence. A documentation-only update may reuse unchanged runtime behavior results, but the new payload identity, instructions and installed correspondence require current checks.

## Repository Update Review

Choose the reviewed repository revision, then create a plan:

```powershell
.\scripts\Update-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool AllIncluded
```

The example updates the shared formal installation registered to all four Hosts. Review source, destinations, ownership, merges, snapshots and postchecks, then execute actual output values:

```powershell
.\scripts\Update-MALTS.ps1 -Apply -PlanPath '<reviewed-plan-path>' -ExpectedPlanHash '<reviewed-plan-sha256>'
```

### DeepSeek Harness Update

Harness updates the same formal installation together with the other three Hosts. Use the `AllIncluded` plan above with all four actual configuration roots; supply `-ToolRootDeepSeekHarness` for a custom Harness path. Before planning, resolve each exact Boot and verify the common runtime/content identity.

Saving and activation remain separate. Review the source, four-Host mappings, personal-content merges and recovery preimages, then execute the actual path/hash. For changed bytes under the same version, use the reviewed `finalize` transaction described below; do not edit the active generation or change the version to bypass verification. Installation updates do not change project state, accounts, model configuration or sessions.

## Version Migration And Collision Handling

An identical installed source can return NO_OP. Different bytes under the same semantic version require the reviewed current-v2 finalize transaction, preserving target snapshots and the exact source binding. Do not patch the generation, delete it first, change VERSION to bypass a collision or rewrite the old publication. Retained original packages/tag snapshots remain historical. Current main, the version tag and Release package must identify the reviewed current source; preserve old receipts instead of rewriting them to match the new revision.

## Optional Offline Archive Update

Verify and safely extract the selected fixed archive, use its ReleaseRoot and the same plan/hash sequence. Harness and other Hosts registered to the same installation use the same entry. Choose the current archive by its stated source commit and digest; a retained older package remains historical input and must not be presented as the latest guides. See [Release Archive](RELEASE_ARTIFACT.md).

## User Modifications And Cleanup

| Class | Meaning | Treatment |
|---|---|---|
| U0 | Missing/exactly MALTS-owned | Only planned replacement/removal |
| U1 | Mergeable marked instruction block | Preserve surrounding personal content |
| U2 | Deterministic evidence-backed merge | Validate the recorded merge |
| U3 | User-owned or ambiguous | Preserve pending a specific decision |
| U4 | Sensitive/unsafe conflict | Fail closed |

Do not apply a whole-file replacement merely because an adapter changed. Cleanup is separate from update and assesses ownership, references and recovery. Preserve unknown objects and necessary snapshots.

U1 applies to recognizable mixed-ownership instruction blocks: update MALTS content while keeping personal prose outside the markers. U3 covers edited or ambiguous files that cannot be automatically classified as safe replacement; resolve the specific ownership/treatment rather than relabel them U0. U4 preserves the fail-closed boundary for unsafe or sensitive conflicts.

Snapshot availability is a recovery facility, not permission to discard unreviewed user edits. Review merge results and reload the actual Host. Do not restore an entire older configuration solely because one generated bridge needs repair; that can remove later user changes.

Retained generations, snapshots and evidence can remain after update because they serve recovery/history. Audit or Scan before a separate cleanup decision. Neither version age nor successful activation proves those originals are unnecessary.

## Diagnose Before Repair

Use read-only Doctor with all four Host roots registered to the shared lifecycle. Inspect core trust before choosing a repair source. DoctorRepairPlan prepares a review; Execute uses the reviewed hash. Do not edit journals/locks or change permissions to bypass a failed precondition.

## Update Workspace Controls

Installation does not adopt projects. Before v2 adoption, review current facts, mappings, writers, unknown effects and backups. Adopted workspaces use current task services; preserve binding/source-seals and do not run old Markdown initialization/reorganization writes. Current Core reads/writes Schema69 only; changing a version field is not a development-store migration.

Adoption must preserve the original goal, current stage/task obligations, retained outputs and unresolved effects. The mapping should identify imported historical claims separately from current verified acceptance. A legacy DONE row is not promoted into current business proof just because import parsed successfully.

Verify the adopted binding, selected state root and epoch before current services operate. Preserve both historical source seals and any post-adoption work. If a store becomes unavailable, use reviewed current forward-recovery contracts with explicit gaps; do not remove the adoption markers to restart legacy writes.

Installation restoration and project restoration need not have the same destination or journal. Recover each using its own identity and then check their correspondence. An installation transaction never silently grants fresh project budgets or acceptance.

## Recovery

Follow the original transaction and observed recovery decision. Project restoration uses a new epoch and reconciles post-backup work, unknown effects and budget consumption. It revives no old Grant/Host/acceptance or legacy runtime. Cross-user DPAPI restoration, arbitrary-writer exclusion and GUI model cancellation remain uncertified.

## Post-Update Discovery

Managed instructions identify the exact MALTS_BOOT_PATH; use that pointer even if it differs from the instruction-file directory. Reload each selected Host, resolve its exact Boot, run discovery and Doctor, and verify actual native Skills/MCP. Preserve AGENTS.override.md and outside-block content; installation does not create/remove that override. Recheck workspace binding separately. Report version, exact content identity, actual checks, recovery location and unresolved items. See [Lifecycle](LIFECYCLE.md).

## Workspace Management Data and Migration

Ordinary new workspaces use `workspace-init` to place task state, managed evidence and recovery data under an owned `.malts` directory; explicit external layouts remain supported. Installation updates do not move existing projects. Healthy adopted stores can relocate through a read-only plan, backup/restore, current-effect review and formal forward switch. The new epoch does not restore old Grants/acceptance or activate a Phase automatically. Retain old stores, external historical references and source capsules according to their actual dependencies. See [workspace management and store relocation](MANAGEMENT_AND_RELOCATION.md) for steps and limits.
