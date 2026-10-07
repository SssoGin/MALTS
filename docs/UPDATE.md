# Update to MALTS 2.0.0

## 1. Before updating

Inspect the installed identity, intended source and workspace binding separately. Preserve recovery materials, settle relevant Hosts/effects and identify user edits. The updater performs no Git pull, automatic ZIP download or unspecified project migration.

2.0.0 gives the selected v2 store execution ownership. A workspace not yet adopted remains readable under its verified contract; v2 adoption requires reviewed mapping, writers, unknown effects and backup. Core reads/writes Schema69 only, without implicit development-store upgrades or legacy runtime restoration.

## 2. Review the update

From the reviewed 2.0.0 repository:

```powershell
.\scripts\Update-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool AllIncluded
```

For explicit roots, supply the existing lifecycle/tool roots. Review source identity, personal-content classification, generation changes, snapshots and postchecks, then use actual reported values:

```powershell
.\scripts\Update-MALTS.ps1 -Apply -PlanPath '<reviewed-plan-path>' -ExpectedPlanHash '<reviewed-plan-sha256>'
```

An identical same-version source may return `NO_OP`. Different content under the same version needs the lifecycle `finalize` contract with preserved preimages and exact source binding. Do not invent 2.0.1 or empty/patch the active generation. See [Lifecycle](LIFECYCLE.md).

## 3. Instructions and Host loading

Installation maintains marked MALTS blocks with the exact installed `MALTS_BOOT_PATH` and preserves personal content outside them. Follow that precise pointer when an instruction file and its Boot are in different locations. Installation does not create/remove `AGENTS.override.md`, which can change Codex's actual instruction loading. Reload the Host and check Boot/discovery, native Skills and MCP instead of assuming a process has loaded the new code.

## 4. Workspaces and recovery

Adopted workspaces continue through `workspace`, `entry-status` and Task services, without legacy initialization or dual writes. Restoration creates a new epoch; old Grants/Hosts/acceptance do not become valid automatically and consumption is not reset. Reconcile uncertain effects under their original identity.

Cross-user DPAPI recovery, arbitrary external-writer exclusion and GUI model cancellation remain uncertified. Historical evidence must match its relevant inputs. Documentation edits do not automatically invalidate unchanged code behavior, but do require command/reference checks. See the [State Contract](V2_STATE_CONTRACT.md).

## Repository Update Review

The updater does not pull Git. Review a fetched/selected checkout independently, then inspect modification classes:

| Class | Meaning | Action |
|---|---|---|
| U0 | Missing or exactly MALTS-owned | Replace/remove only as planned |
| U1 | Mergeable managed instruction block | Preserve outside content and merge the block |
| U2 | Deterministic evidence-backed merge | Use the recorded validation |
| U3 | User-owned or ambiguous edits | Preserve pending an explicit decision |
| U4 | Sensitive or unsafe conflict | Fail closed |

## Optional Offline Archive Update

Verify/extract the matching archive and use ReleaseRoot with the same update-plan/hash sequence. This does not relax drift/ownership checks.

## Historical workspace adoption

Installation updates do not adopt existing projects. Review their facts, writer quiescence, unknown effects and backups through explicit v2 adoption. Preserve historical source/seals; recovery stays in v2. Legacy reorganization commands do not own adopted-workspace state.
