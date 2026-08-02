# MALTS Lifecycle

The lifecycle engine turns a verified MALTS source into immutable installed versions. One local registry identifies the active version; each selected Agent tool receives only its projection and a boot pointer.

## Core Invariants

- A version comes from one verified repository source or one explicitly verified extracted release package.
- Installed payload bytes remain immutable after activation.
- Installed provenance stores only its source kind and hash-bound identities; it never stores a package, repository, or machine path.
- Exactly one version is active after a successful install or update.
- A plan is persisted, reviewable, and bound to an exact SHA-256.
- Execution accepts only the exact reviewed plan and observed preconditions.
- Tool roots outside the selected set are not modified.
- Unknown or user-owned files are preserved or block the operation; they are not silently removed.

## Source Modes

| Source | Normal use | Validation |
|---|---|---|
| Repository | Default install and update path | `MALTS_RELEASE.json`, `VERSION`, exact source-tree inventory, required user entry points, and safe repository topology. |
| Extracted release package | Explicit offline/fixed archive path | Closed `release_manifest.json`, release inventory, inner lifecycle artifact, and package identity. |

The optional ZIP is an archive delivery mechanism, not a third lifecycle source. Bootstrap verification extracts it into the second source mode.

## Semantic Version Identity And Migration

Stable versions use `malts-v<version>` and isolated preview versions use
`malts-v<version>-preview.<positive-sequence>`. The release builder and
lifecycle engine call the same identity function. An exact stable identity
already installed is an explicit `NO_OP`; the same ID with different content,
or an unbound directory with that name, fails before transaction or lock state
is created.

Legacy IDs such as `malts-1.0.0-<hash>` are recognized migration inputs. The
new semantic version is staged and prevalidated first. Registry, active
pointer, global boot, and selected tool projections switch transactionally;
the legacy version is removed only after post-validation proves zero
authoritative old references. A crash at any state recovers to one terminal
committed or rolled-back result.

## Operations

| Operation | Purpose | Source required |
|---|---|---|
| `install` | Create and activate a first version. | Repository or extracted package |
| `update` | Stage and activate a newer verified version. | Repository or extracted package |
| `repair` | Reconcile selected projections with the active version. | Repository or extracted package |
| `uninstall` | Remove MALTS-owned projections and registry state under the reviewed plan. | Active installation only |
| `recover` | Resume or roll back an interrupted transaction. | Existing lifecycle state |

## Review-First Plans

The user lifecycle scripts create a plan first. A plan includes the source identity, selected roots, target version identity, writes, removals, user-modification classification, legacy migration or residue actions, rollback, and post-validation checks.

Execution requires the same plan file and its exact `plan_hash`. Source or environment drift fails before mutation.

## Preview Verification

New runtime-affecting versions are verified in an explicit absolute preview
root before they can be considered for a real installation. The preview root
must not be a drive root, reparse point, source/runtime root, or an
ancestor/descendant of any protected root. Preview lifecycle, registry, global
boot, and every selected tool's config, home, cache, and temp roots stay below
that boundary.

Create a zero-write preview plan, review it, then persist and execute only its
exact hash:

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 `
  -Command PreviewPlan `
  -PreviewRoot <ABSOLUTE_PREVIEW_ROOT> `
  -ReleaseRoot <PREVIEW_RELEASE_ROOT> `
  -ProtectedRoot <REAL_LIFECYCLE_ROOT> `
  -Tool codex,claude-code,opencode `
  -OutPath <NEW_PREVIEW_PLAN_PATH> `
  -Apply
```

Fresh Codex, Claude Code, and OpenCode processes must discover the preview version through process-local isolated roots. If isolation cannot be proved, the operation is blocked; it never falls back to a real root. A preview that was not verified with real tool integration is recorded as such and cannot be treated as fully qualified.

## Doctor And Repair Trust

`Doctor` returns a closed `lifecycle-doctor-report` with exact locators, expected/observed evidence, severity, core trust, and suggested commands. It is always read-only. Derived boot or projection drift can be scoped from a locally consistent active version; tampered payload, manifest, registry, or pointer state requires an exact verified external source matching the installed binding.

`DoctorRepairPlan` is a separate review step. A local active-version recommendation is non-executable. A verified exact source may produce a normal hash-bound repair plan, but execution still requires `Execute -Apply` with the reviewed plan hash and retains normal snapshot/rollback/post-validation behavior.

## Versions And Boot Pointers

The lifecycle root contains immutable version directories, registry state, transaction journals, audit evidence, and residue records. Each selected tool receives a small projection plus `MALTS_BOOT.md`, which resolves the active version at use time.

Do not copy a physical version path into a project control file. Resolve the boot pointer first and read the active `VERSION` when current runtime information is needed.

For a legacy long-project workspace that contains an old physical version
path in its generated `PROJECT_CONTROL.md`, inspect the migration first:

```powershell
python .\tools\long_workspace.py refresh-runtime-references --workspace <PROJECT_WORKSPACE>
```

Apply it only after reviewing the returned plan:

```powershell
python .\tools\long_workspace.py refresh-runtime-references --workspace <PROJECT_WORKSPACE> --apply
```

The command changes only the generated version-source metadata line. A static
version reference makes `validate` fail with `WS_STALE_RUNTIME_REFERENCE`;
it must be refreshed or manually reviewed rather than being silently ignored
or rewritten outside that generated line.

Older installed versions can retain a legacy absolute source locator only
so a verified update can replace them. They remain readable for migration, but
installation purity checks fail closed until the update creates a redacted
current record.

## Bounded Audit Retention

Lifecycle audit state has a closed schema and fixed ownership rules. It keeps:

- one current active-binding receipt, or none after uninstall
- the newest 20 compact successful-operation receipts
- the newest 10 complete failure/recovery plan-and-journal bundles
- one compact summary for each of the newest 12 calendar months

Incomplete recoverable transactions are never pruned. A new record is written safely before an exact name/hash-bound prune list is applied. Unknown names, hash drift, reparse points, forbidden version/package/ZIP/payload copies, or cleanup failures are preserved and block a stable or zero-residue result. Audit write and prune recovery are idempotent.

For the one older audit layout written before this retention contract, migration recognizes only its exact closed v1 envelope, plan, context, and terminal journal shapes. It verifies the original plan/context hashes and operation / artifact / journal bindings, then preserves the source bytes under `state/audit/legacy-pre-retention/<operation_id>/`. It never fabricates a newer version identity. Missing or extra fields, hash drift, reparse points, unmatched archive content, and all unrecognized files remain blocking.

Recognized standard legacy plan/journal pairs compact into current receipts using the version identity already bound by their `release_identity`; a missing derived plan field is never treated as a new identity. If a normal failure occurs after `COMMIT`, the journaled snapshot rollback remains an explicit recovery path. A recovered stable active registry also receives a current binding receipt before strict audit validation can pass.

## Recovery And Residue

Interrupted operations are journaled. Recovery checks the journal, registry, active pointer, versions, selected projections, and managed residue before claiming a stable state.

The engine distinguishes MALTS-owned paths from user-owned or uncertain paths. It removes only verified MALTS-owned residue under the reviewed plan; ambiguous paths are preserved or require an explicit user decision.

## Ordinary Startup Discovery

Each tool starts from its own adjacent `MALTS_BOOT.md`, whose schema is exactly one absolute `MALTS_ROOT:` line. `GLOBAL_BOOT.md` has a separate fenced-block schema and serves only as an optional machine-global/recovery cross-check. The read-only `discover` command verifies tool boot, stable registry state, the sole active record, exact `active_generation.json`, active `VERSION`, version identity, and optional global boot. It computes no full-tree hash during ordinary startup and writes nothing. Missing, malformed, stale, or conflicting authoritative surfaces fail closed.

See [Install](INSTALL.md), [Update](UPDATE.md), and [Security](SECURITY.md).
