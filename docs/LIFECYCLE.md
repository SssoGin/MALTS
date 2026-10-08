# MALTS Lifecycle

The installation lifecycle verifies a source, stages a generation, preserves preimages, activates selected native integrations and checks the resulting binding. The project lifecycle maintains goals, tasks, evidence and recovery independently of installation. Current version: **2.0.0**.

## Core Invariants

Installation and project work have separate lifecycles. Installation owns immutable generations, selected projections, registry, reviewed plans and transactions. Project services own goals, stages/tasks, artifacts, evidence and recovery. Installing a generation never silently adopts or rebuilds a project.

- One verified source defines the exact installed payload.
- One registry/active pointer and each selected tool Boot identify the active version.
- Plans bind exact source/destination facts and SHA-256; execution rejects drift.
- Tool roots outside the selected set and user-owned content are preserved.
- Active generations are runtime inputs, not editable workspaces.
- Snapshots and incomplete transactions retain their recovery purpose.

Current version is **2.0.0**; same-version documentation amendments keep a distinct content identity.

A registry identity is meaningful only when it agrees with the active pointer, generation manifest and payload, and the selected tool's Boot. The installer checks the complete verified source before writing; post-validation checks the actual destination rather than inferring success from an exit message.

Separating installation from project state avoids an update becoming an unreviewed migration. A valid new runtime does not decide how an old project's goals, pending effects or backups should be mapped. Conversely, a project backup cannot repair a modified installation manifest. Each boundary has its own source, transaction and observed result.

Personal instruction files have mixed ownership. Only marked MALTS sections are managed; U1 merges preserve the surrounding personal text. Unknown files or ambiguous markers can block a plan even when the package itself is valid. An exact source hash therefore complements, rather than replaces, destination ownership checks.

## Source Modes

| Source | Use | Checks |
|---|---|---|
| Reviewed repository | Normal installation/update | VERSION, MALTS_RELEASE.json, exact inventory, source-tree identity and topology |
| Verified extracted package | Explicit fixed/offline input | Closed release/artifact manifests, inventories and hashes |

ZIP is the delivery form of the second source, not an automatic download or an alternative to source verification. A reissued 2.0.0 ZIP is qualified against its stated source commit and content identity; platform source archives follow the current version tag, which must match the qualified archive source.

Repository verification checks the declared user paths plus the repository-only identity/Git/CI files. It rejects missing, changed or unexpected public content. Installation extracts only user payload paths; repository metadata is not installed into the generation.

A fixed archive adds an outer closed inventory and inner lifecycle artifact. The verifier checks names, traversal/collision risks and hashes before final extraction. A GitHub-generated source archive is a snapshot of a Git ref and must not be assumed to have the same package layout as MALTS-2.0.0.zip.

Select the source before planning and keep it unchanged until execution. Pulling a new commit, editing a guide or adding a cache after planning can invalidate the source identity. Generate another reviewed plan rather than editing the old hash or relaxing verification.

## Semantic Version Identity And Migration

Stable identities use `malts-v<version>`; preview identities have their declared preview suffix. The builder and lifecycle use the same identity contract. Exact already-installed bytes can produce `NO_OP`. Different bytes under one version cannot be manually overwritten.

For a reviewed same-version correction, the current v2 `finalize` path preserves the target preimage and installs the qualified new identity transactionally. This is a deliberate consolidation, not an automatic cleanup or reason to invent a patch version. Historical identities and receipts remain truthful.

The version identifies a release line; the content hash identifies the exact qualified tree. These serve different purposes. Retaining 2.0.0 for a documentation correction is compatible with a new source-tree hash, but the installed identity must be updated through the formal transaction rather than pretending the old artifact contains new bytes.

For current v2 finalization, planning records the existing target and its snapshot before replacement. It does not implicitly retire every old version or scan the drive for cleanup. Review any planned writes/removals and the snapshot paths against the actual selected lifecycle. For an explicitly authorized tag correction, retain the original annotated object under a historical reference, then align the current version tag and package to the qualified source. Retained original packages/receipts keep their original identities; new tag/package observations receive a new receipt.

A preview has its own declared identity and roots. Preview success qualifies those paths and checks; activation of a normal target still requires its own exact plan/preconditions. Reusing a preview hash as a production plan is not valid.

## Operations

| Operation | Purpose |
|---|---|
| install | First activation from a verified source |
| update | Activate a selected verified update |
| repair | Reconcile selected projections using an appropriately trusted source |
| finalize | Explicit reviewed same-version consolidation with preserved preimages |
| uninstall | Remove only planned MALTS-owned integration/state |
| recover | Inspect and settle an interrupted lifecycle transaction |

`Invoke-MALTSLifecycle.ps1` exposes Plan, PreviewPlan, Execute, Recover, Inspect, Scan, Doctor and DoctorRepairPlan. Check current help before constructing a plan. No operation grants publication or project-migration permission.

## Review-First Plans

Install/Update save a plan before activation. The plan identifies source, selected roots, intended generation, writes/removals, ownership classes, snapshots and postchecks. Execute needs the exact plan path and reported hash.

For the generic entry, `Plan -Apply` saves a plan only; `Execute -Apply` performs the reviewed transaction. PreviewPlan likewise separates planning from execution. Preserve transaction journals; deleting a lock or editing a plan is not recovery.

See [Install](INSTALL.md) and [Update](UPDATE.md) for all four Host paths. Install/Update's AllIncluded selects three Hosts. Harness uses its own lifecycle/root and retained `ToolRootDeepSeekDesktop` parameter.

The transaction progresses through discovery/locking, source staging, snapshot, prevalidation, activation, postvalidation and final audit/commit. The recorded journal identifies which stages occurred. A failure can therefore be inspected at the original operation instead of inferred from which directories happen to exist.

| Review item | Check before Execute |
|---|---|
| Source binding | Exact repository/package identity and complete inventory |
| Selected roots | Actual lifecycle and tool roots, with no protected overlap |
| User modifications | Ownership class and specific merge/preserve decision |
| Target disposition | NO_OP, new activation or reviewed same-version replacement |
| Recovery | Snapshot and journal identities, with actual retained inputs |
| Postchecks | Registry/pointer/generation/Boot and projection checks |

Execution rechecks the current source and destination against that plan. A different target file with the same name or a changed personal block cannot be accepted merely because its path is still listed. Keep the real plan file and reported hash; placeholders in examples must be replaced by observed output.

Use the original operation ID when inspecting an interrupted transaction. Starting another install while an earlier transaction is unresolved can introduce competing ownership and obscure recovery. The lifecycle engine's rejection is a condition to diagnose, not an instruction to delete its lock.

## Preview Verification

A preview uses a new explicit root separate from source, active runtime, real lifecycle/tool roots and other protected objects. Review the planned paths and verify isolated Host roots before execution; do not fall back to production roots when isolation fails.

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 -Command PreviewPlan `
  -PreviewRoot '<new-absolute-preview-root>' -RepositoryRoot (Get-Location).Path `
  -ProtectedRoot '<real-lifecycle-root>' -Tool codex,claude-code,opencode `
  -OutPath '<new-preview-plan-path>' -Apply
```

Use a separate Harness preview with `-Tool deepseek-harness`. Saving a preview plan does not run it. Native tool invocation, projection checks and model behavior are separate evidence; state honestly which layer was observed.

A preview must isolate every selected Host surface as well as the lifecycle root. A separate generation directory is insufficient if the test still loads real config, home, cache or environment roots. Check the plan's generated tool mapping and the observed discovery response from each actual preview process.

The verification layers are: source/package integrity; installation/projection correctness; actual native discovery; and task behavior under a named Host/profile. State which were performed. A cold MCP check proves the loaded service interface, while a model-task run proves only its observed business interaction; neither certifies GUI cancellation or arbitrary external writers.

For unchanged runtime code and a guide-only amendment, reuse valid behavioral evidence and verify changed instructions/examples plus destination identity. A change to transaction, permissions or coordination needs the corresponding runtime checks. Select verification from the affected mechanism rather than the marketing version number.

## Doctor And Repair Trust

Doctor is a read-only trust and drift assessment. It reports expected/observed locators, severity and core trust. It does not repair, delete or call a model. Derived projection drift and tampered payload/registry identity require different trust decisions.

DoctorRepairPlan is a separate reviewed repair preparation. A recommendation is not executable authority. Repair requires the exact trusted source and normal hash-bound execution/snapshot/postchecks.

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 -Command Doctor `
  -LifecycleRoot '<existing-lifecycle-root>' -ToolRootCodex '<codex-config-root>'
```

Supply all actual roots sharing that lifecycle. Harness diagnosis uses its separate lifecycle and `-ToolRootDeepSeekDesktop`; see [Install](INSTALL.md).

A missing bridge or Boot can be a derived-projection fault if the active core is still trusted. Changed generation bytes, manifests, registry or pointer weaken that basis; repair then needs an exact independently verified source matching the intended binding. Do not trust the same altered files to prove their own correctness.

Read the report's severity, expected/observed locators and core trust together. A suggested command is a proposal; a Doctor PASS is not a repair action. Prepare DoctorRepairPlan from the appropriate source, review the executable plan and execute its hash-bound transaction. Then run Doctor/discovery again to observe the repaired state.

If repair cannot establish source trust, preserve the installation and its evidence for diagnosis. Manual copying, changing ACLs or reconstructing a registry from a folder name would bypass the very identity checks that recovery relies on.

## Versions And Boot Pointers

Each tool reads its exact adjacent or instruction-declared `MALTS_BOOT.md`. Its MALTS_ROOT points at an immutable generation. Resolve that pointer and discovery's returned authority paths; do not guess an active pointer or rely on a historical absolute runtime path.

Public entry points suppress bytecode writes; examples also use `python -B`. Do not create caches or business outputs in a generation. Reload the Host after installation and check actual Skills/MCP rather than assuming an old process loaded new bytes.

## Bounded Audit Retention

Lifecycle auditing keeps the current active binding, bounded recent successes, failure/recovery bundles and monthly summaries. Incomplete recovery transactions are preserved. Exact name/hash-bound retention rules reject unknown contents, reparse points and changed inputs.

This audit policy does not bound all project evidence or installation backups. Retained snapshots may grow until a separately reviewed cleanup has proved they are unnecessary. Do not delete historical bytes to make a newer description appear consistent.

The current engine retains one active-binding receipt, the newest 20 compact successful-operation receipts, the newest 10 failure/recovery bundles and summaries for the newest 12 calendar months. Incomplete recoverable transactions are not pruned. These limits are the lifecycle audit constants, not a disk-space guarantee for project blobs, retained generations or snapshots.

Writing a new record precedes applying the exact prune list. The engine checks names and hashes before removal so unknown objects and changed evidence are preserved rather than swept into routine retention. An interruption during audit writing or pruning remains recoverable under the original transaction.

Older recognized audit layouts are migrated by verifying their closed plan/context/journal bindings and preserving original bytes. They are not reissued with invented current version identities. If an input does not match that recognized envelope, diagnose it instead of treating it as an old file that can be deleted.

## Recovery And Residue

Inspect the original transaction and actual registry, pointer, generations, projections and snapshots. Follow the engine's observed recovery decision. Current v2 activation recovery continues within v2; it does not restore legacy runtime write authority.

UNKNOWN means the effect is uncertain; reconcile the original operation before dependent execution.

Scan inventories residue; it supplies no deletion permission. Preserve active installation, state/binding/seals, uncertain effects, original acceptance and necessary backups. Assess ownership, references and alternate recovery before deletion under the Host/user policy. Recoverable disposal failure must not become a stronger deletion.

Recovery first identifies the original operation and journal stage, then verifies source/snapshot identities and current destinations. Prevalidation, activation and postvalidation have different consequences. The current v2 engine can resume a committed tail or require forward reconciliation after activation; do not assume every failure automatically restores the previous installation.

Retain a failure bundle when automatic recovery cannot prove the result. A snapshot proves that a preimage was captured, not that it has been restored or that external processes stopped. Installation recovery also cannot decide whether a project effect occurred; use the selected task/operation observation for that separate question.

For residue, distinguish an installed active generation, a registered retained generation, a staged candidate, an unresolved transaction and ordinary temporary output. Their references and recovery value differ. A terminal label or old timestamp cannot collapse these categories into a disposable set.

## Workspace Phase And Artifact Lifecycle

### Phase Boundary And State

Phases own bounded goals, exclusions, acceptance and actual plan references; tasks bind exact Phase/revision and dependencies. A material revision updates the affected contract and binding. Review alone is neither execution permission nor business acceptance. Closing a task does not finish the Project.

### Cross-Control Consistency And Recovery Authority

An adopted workspace uses its verified v2 store. Historical Markdown retains provenance; it is not a second writable control. Query workspace, governance-context, task-queue and exact context. Preserve unknown effects and external-writer evidence; a PAUSED state alone proves no process stopped.

### Artifact Enrollment And Ownership

Artifacts record owner, revision, content identity, lineage and retention independently of path. Current sharing requires content/eligibility and dependency checks. Superseded/retired records explain history; they are not implicit redirects to new content.

### Mutation, Close, And Recovery

Use current services and reviewed revisions. Registered effects and managed Hosts must settle before acceptance; independent business checks remain necessary. Restoration uses a new epoch and reconciles later work, budgets, resources and effects without reviving old Grants or Hosts.

### Compatibility And Non-Goals

Before adoption, a workspace keeps its verified contract. Adoption is explicit and preserves original data/source seals; legacy reorganization commands do not own adopted state. No ordinary entry initializes, migrates, starts a daemon or scans all history. See [State Contract](V2_STATE_CONTRACT.md).

## Ordinary Startup Discovery

```powershell
$runtime = '<MALTS_ROOT-from-selected-tool-boot>'
python -B "$runtime/tools/malts_lifecycle.py" discover --tool-root '<selected-tool-root>'
```

Require matching registry, active pointer, generation identity and VERSION. Discovery is read-only; a machine-global GLOBAL_BOOT.md is not its current input. Then verify the selected workspace binding and task context. See [Getting Started](GETTING_STARTED.md).
