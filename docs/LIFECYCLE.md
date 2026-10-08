# MALTS Lifecycle

The lifecycle engine installs verified MALTS content and preserves recovery boundaries. This guide keeps the established installation, diagnosis, preview and workspace sections, updated for the current **2.0.0** implementation.

## Core Invariants

Installation and project work have separate lifecycles. Installation owns immutable generations, selected projections, registry, reviewed plans and transactions. Project services own goals, stages/tasks, artifacts, evidence and recovery. Installing a generation never silently adopts or rebuilds a project.

- One verified source defines the exact installed payload.
- One registry/active pointer and each selected tool Boot identify the active version.
- Plans bind exact source/destination facts and SHA-256; execution rejects drift.
- Tool roots outside the selected set and user-owned content are preserved.
- Active generations are runtime inputs, not editable workspaces.
- Snapshots and incomplete transactions retain their recovery purpose.

Current version is **2.0.0**; same-version documentation amendments keep a distinct content identity.

## Source Modes

| Source | Use | Checks |
|---|---|---|
| Reviewed repository | Normal installation/update | VERSION, MALTS_RELEASE.json, exact inventory, source-tree identity and topology |
| Verified extracted package | Explicit fixed/offline input | Closed release/artifact manifests, inventories and hashes |

ZIP is the delivery form of the second source, not an automatic download or an alternative to source verification. A later `main` documentation revision and the original tagged ZIP can both be 2.0.0 while their exact tree identities differ.

## Semantic Version Identity And Migration

Stable identities use `malts-v<version>`; preview identities have their declared preview suffix. The builder and lifecycle use the same identity contract. Exact already-installed bytes can produce `NO_OP`. Different bytes under one version cannot be manually overwritten.

For a reviewed same-version correction, the current v2 `finalize` path preserves the target preimage and installs the qualified new identity transactionally. This is a deliberate consolidation, not an automatic cleanup or reason to invent a patch version. Historical identities and receipts remain truthful.

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

## Preview Verification

A preview uses a new explicit root separate from source, active runtime, real lifecycle/tool roots and other protected objects. Review the planned paths and verify isolated Host roots before execution; do not fall back to production roots when isolation fails.

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 -Command PreviewPlan `
  -PreviewRoot '<new-absolute-preview-root>' -RepositoryRoot (Get-Location).Path `
  -ProtectedRoot '<real-lifecycle-root>' -Tool codex,claude-code,opencode `
  -OutPath '<new-preview-plan-path>' -Apply
```

Use a separate Harness preview with `-Tool deepseek-harness`. Saving a preview plan does not run it. Native tool invocation, projection checks and model behavior are separate evidence; state honestly which layer was observed.

## Doctor And Repair Trust

Doctor is a read-only trust and drift assessment. It reports expected/observed locators, severity and core trust. It does not repair, delete or call a model. Derived projection drift and tampered payload/registry identity require different trust decisions.

DoctorRepairPlan is a separate reviewed repair preparation. A recommendation is not executable authority. Repair requires the exact trusted source and normal hash-bound execution/snapshot/postchecks.

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 -Command Doctor `
  -LifecycleRoot '<existing-lifecycle-root>' -ToolRootCodex '<codex-config-root>'
```

Supply all actual roots sharing that lifecycle. Harness diagnosis uses its separate lifecycle and `-ToolRootDeepSeekDesktop`; see [Install](INSTALL.md).

## Versions And Boot Pointers

Each tool reads its exact adjacent or instruction-declared `MALTS_BOOT.md`. Its MALTS_ROOT points at an immutable generation. Resolve that pointer and discovery's returned authority paths; do not guess an active pointer or rely on a historical absolute runtime path.

Public entry points suppress bytecode writes; examples also use `python -B`. Do not create caches or business outputs in a generation. Reload the Host after installation and check actual Skills/MCP rather than assuming an old process loaded new bytes.

## Bounded Audit Retention

Lifecycle auditing keeps the current active binding, bounded recent successes, failure/recovery bundles and monthly summaries. Incomplete recovery transactions are preserved. Exact name/hash-bound retention rules reject unknown contents, reparse points and changed inputs.

This audit policy does not bound all project evidence or installation backups. Retained snapshots may grow until a separately reviewed cleanup has proved they are unnecessary. Do not delete historical bytes to make a newer description appear consistent.

## Recovery And Residue

Inspect the original transaction and actual registry, pointer, generations, projections and snapshots. Follow the engine's observed recovery decision. Current v2 activation recovery continues within v2; it does not restore legacy runtime write authority.

UNKNOWN means the effect is uncertain; reconcile the original operation before dependent execution.

Scan inventories residue; it supplies no deletion permission. Preserve active installation, state/binding/seals, uncertain effects, original acceptance and necessary backups. Assess ownership, references and alternate recovery before deletion under the Host/user policy. Recoverable disposal failure must not become a stronger deletion.

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
