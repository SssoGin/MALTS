# MALTS Lifecycle

The lifecycle engine turns a verified MALTS source into immutable installed generations. One local registry identifies the active generation; each selected Agent tool receives only its projection and a boot pointer.

## Core Invariants

- A generation comes from one verified repository source or one explicitly verified extracted release package.
- Installed payload bytes remain immutable after activation.
- Installed-generation provenance stores only its source kind and hash-bound identities; it never stores a package, repository, or machine path.
- Exactly one generation is active after a successful install or update.
- A plan is persisted, reviewable, and bound to an exact SHA-256.
- Execution accepts only the exact reviewed plan and observed preconditions.
- Tool roots outside the selected set are not modified.
- Unknown or user-owned files are preserved or block the operation; they are not silently removed.

## Source Modes

| Source | Normal use | Validation |
|---|---|---|
| Public repository | Default install and update path | `MALTS_RELEASE.json`, `VERSION`, exact source-tree inventory, required user entry points, and safe repository topology. |
| Extracted release package | Explicit offline/fixed archive path | Closed `release_manifest.json`, release inventory, inner lifecycle artifact, and package identity. |

The optional ZIP is an archive delivery mechanism, not a third lifecycle source. Bootstrap verification extracts it into the second source mode.

## Operations

| Operation | Purpose | Source required |
|---|---|---|
| `install` | Create and activate a first generation. | Repository or extracted package |
| `update` | Stage and activate a newer verified generation. | Repository or extracted package |
| `repair` | Reconcile selected projections with the active generation. | Repository or extracted package |
| `uninstall` | Remove MALTS-owned projections and registry state under the reviewed plan. | Active installation only |
| `recover` | Resume or roll back an interrupted transaction. | Existing lifecycle state |

## Review-First Plans

The user lifecycle scripts create a plan first. A plan includes the source identity, selected roots, target generation identity, writes, removals, user-modification classification, legacy migration or residue actions, rollback, and post-validation checks.

Execution requires the same plan file and its exact `plan_hash`. Source or environment drift fails before mutation.

## Generations and Boot Pointers

The lifecycle root contains immutable generation directories, registry state, transaction journals, audit evidence, and residue records. Each selected tool receives a small projection plus `MALTS_BOOT.md`, which resolves the active generation at use time.

Do not copy a physical generation path into a project control file. Resolve the boot pointer first and read the active `VERSION` when current runtime information is needed.

For a legacy long-project workspace that contains an old physical generation
path in its generated `PROJECT_CONTROL.md`, inspect the migration first:

```powershell
python .\tools\long_workspace.py refresh-runtime-references --workspace <PROJECT_WORKSPACE>
```

Apply it only after reviewing the returned plan:

```powershell
python .\tools\long_workspace.py refresh-runtime-references --workspace <PROJECT_WORKSPACE> --apply
```

The command changes only the generated version-source metadata line. A static
generation reference makes `validate` fail with `WS_STALE_RUNTIME_REFERENCE`;
it must be refreshed or manually reviewed rather than being silently ignored
or rewritten outside that generated line.

Older installed generations can retain a legacy absolute source locator only
so a verified update can replace them. They remain readable for migration, but
the installed-generation user-purity gate fails closed until the update creates
a redacted current envelope.

## Recovery and Residue

Interrupted operations are journaled. Recovery checks the journal, registry, active pointer, generations, selected projections, and managed residue before claiming a stable state.

The engine distinguishes MALTS-owned paths from user-owned or uncertain paths. It removes only verified MALTS-owned residue under the reviewed plan; ambiguous paths are preserved or require an explicit user decision.

See [Install](INSTALL.md), [Update](UPDATE.md), and [Security](SECURITY.md).
