# Changelog

All notable public changes to MALTS are documented here.

## Unreleased

No unreleased user changes.

## 1.1.0

MALTS 1.1.0 adds safer runtime lifecycle handling, Plan Recheck, governed peer-task routing, stronger startup discovery, and clearer install and update behavior.

### Semantic generations and migration

- Uses stable IDs such as `malts-v1.1.0` and preview IDs such as `malts-v1.1.0-preview.1` from one shared lifecycle identity function.
- Treats an identical installed stable generation as an explicit no-op, rejects same-version content conflicts and unbound same-name directories before writes, and migrates recognized legacy generation IDs transactionally.
- Requires zero authoritative references to the old generation before cleanup and preserves rollback/recovery across process loss.

### Isolated preview verification

- Adds explicit absolute preview-root planning with overlap, reparse-point, and unsafe-root rejection.
- Keeps preview lifecycle, registry, boot, and Codex/Claude Code/OpenCode config, home, cache, and temp roots inside the preview boundary.
- Records preview verification honestly: a preview not verified with real tool integration is marked as such and cannot be treated as fully qualified.

### Doctor, repair trust, and diagnostics

- Adds a closed read-only doctor report with exact mismatch locators, severity, trust classification, and suggested commands.
- Separates diagnosis from repair: derived drift may be scoped from a locally consistent active generation, while an executable repair remains a separately reviewed, hash-bound transaction using an exact trusted source.
- Preserves nested residue and diagnostic failures instead of overwriting them with an unconditional top-level success.

### Bounded audit records

- Keeps one current binding receipt, the newest 20 successful-operation receipts, the newest 10 complete failure/recovery plan-and-journal bundles, and the newest 12 monthly summaries.
- Never prunes incomplete recoverable transactions; unknown names, hash drift, forbidden payload copies, or cleanup failures are preserved and block a stable/zero-residue result.
- Adds idempotent audit write/prune recovery and a final uninstall receipt without retaining a current binding.
- Migrates only the exact closed pre-retention v1 audit contract into a raw-byte-preserving archive; missing/extra fields, drift, reparse points, and unmatched historic content remain blocking.
- Corrects standard legacy-audit receipt compaction to use its already bound release identity, preserves post-`COMMIT` snapshot rollback, and restores a current binding when rollback returns to a stable active registry.

### Wrappers and documentation

- Exposes preview, doctor, repair-review, and preview-qualification options through the PowerShell wrappers.
- Synchronizes English and Simplified Chinese lifecycle guidance plus Codex, Claude Code, and OpenCode isolated-discovery rules.

### Plan, delegation, and discovery coherence

- Adds read-only event-triggered `plan-recheck` gates with Phase-owned plan path, revision, raw-byte SHA-256, Session inheritance, root indexing, canonical triggers/results, and fail-closed launch-review invalidation.
- Adds `peer-task` to runtime route evidence and governs Codex same-directory task windows inside the existing multi-agent Skill, including hard model/effort binding, no silent fallback, rework reuse, acceptance, and archival evidence.
- Makes tool-adjacent `MALTS_BOOT.md` the ordinary startup authority, keeps `GLOBAL_BOOT.md` as a separate machine-global/recovery schema, and adds a read-only discovery command that cross-checks registry, active pointer, active `VERSION`, and split-brain conditions.

## 1.0.1

MALTS 1.0.1 is a focused stability and maintainability update for the v1.0 contract.

### Long-workspace correctness

- Detects and blocks control-state drift when runtime metadata still marks a Phase active but its canonical Phase document is already terminal, and reports the exact `close-phase` reconciliation command.
- Corrects capacity metrics so closed or empty decision placeholders are not counted as open decisions, limits current-state metrics to the root control plus the active Phase and active Session, and scopes task/decision table statuses to their canonical sections so unrelated risk, checkpoint, acceptance, or evidence cells do not inflate the counts.
- Corrects managed-block residue inspection so user-owned content outside the managed block does not create a false drift result, while real managed-content changes still fail verification.

### Documentation validation

- Adds deterministic offline Markdown link validation for local targets, missing files, and root escapes, while ignoring external URLs, pure fragments, and fenced examples.

## 1.0.0

MALTS 1.0 is the first stable contract, lifecycle, long-workspace, and closed-package release.

### User experience

- Restored a complete English and Simplified Chinese project entry, installation guide, update guide, lifecycle guide, release-artifact guide, security guidance, and version history.
- Added a distinct `malts-long-project-workspace-init` experience: a new long-project workspace now requires an initial Phase ID and goal and creates the root controls plus first active Phase together.
- Kept Sessions explicit so normal conversations do not create permanent Session state automatically.
- Added clear selection guidance for `malts-project-init`, long-project initialization, Grill-Me Preflight, multi-agent scheduling, handoff, retrospective growth, and lightweight single-agent growth.

### Install, update, and recovery

- Established the verified public repository as the primary review-first installation and update source; the lifecycle scripts never pull Git, discover updates in the background, or download a Release archive automatically.
- Added `MALTS_RELEASE.json` as repository-only identity metadata that binds the exact public user tree while remaining outside installed generations.
- Added `Install-MALTS.review.cmd`, `Install-MALTS.ps1`, `Update-MALTS.review.cmd`, and `Update-MALTS.ps1` flows that create a persisted plan before any installation or update.
- Required the exact reviewed `plan_hash` for execution; a missing, stale, changed, or mismatched plan fails before applying changes.
- Added explicit or intentionally selected standard roots for Codex, Claude Code, OpenCode, or any one-to-three-tool selection.
- Added immutable generations, transactional active-pointer switching, rollback/recovery, inspection, and residue scanning.
- Added U0-U4 user-modification and ownership classification so modified, external, plugin-owned, and ambiguous files are not silently deleted.
- Added direct migration handling for known public layouts from `v0.1.0` through `v0.1.9`.
- Added pre-execution Windows path-bound validation for transaction staging, immutable generations, tool projections, and atomic writes; overlong custom roots now fail during planning with `TX_PATH_TOO_LONG` and no lifecycle state.
- Removed obsolete installed `.malts` runtime duplication from the v1 layout.
- Confirmed that ordinary MALTS use performs no automatic update discovery, network polling, scheduled check, or provider call.

### Long tasks and Agent routing

- Added canonical project, Phase, Session, task-contract, work-report, sub-agent-report, and handoff controls.
- Added deterministic Result contracts with bounded retries, budgets, scopes, recovery checkpoints, and terminal outcomes.
- Added dynamic `0` / `1` / `N` sub-agent routing based on real responsibility lanes, conflict-free locators, runtime capacity, and independent-verification value.
- Separated responsibility names from model difficulty; model and effort evidence records requested, recommended, configured, and effective observations independently.
- Kept the main Agent responsible for launch review, authorization, reconciliation, verification, and final delivery.
- Required explicit user confirmation of the complete launch review before real sub-agent dispatch.

### Skills and capabilities

- Added a governed Capability Catalog, advisory resolver, dependency/collision checks, and external capability sidecars without claiming ownership of third-party Skills.
- Added canonical root Skill packages and lightweight `malts-*` discovery bridges for Codex, Claude Code, and OpenCode.
- Added user-facing Skill picker metadata for clearer discovery.
- Added controlled native Skill projection that preserves canonical Skill bodies and validates source bindings.
- Kept third-party Skill installation, update, projection, and removal outside automatic MALTS behavior.

### Growth and memory

- Added deterministic project-local growth candidate recording, retrieval, validation, challenge, suspension, revision, deprecation, and removal states.
- Separated lightweight observation from durable project recording and separately authorized system-level promotion.
- Required future-use evidence before a candidate is treated as validated reusable guidance.
- Added quality, delivery, and memory-write checklists in English and Simplified Chinese.

### Release integrity and payload purity

- Added a closed ReleaseManifest that binds release notes, installed user payload, repository-only metadata, generation identity, artifact identity, and logical package identity.
- Added deterministic single-ZIP archive construction, safe extraction, and exact-source bootstrap verification for explicit offline delivery.
- Defined one optional uploaded Release asset: `MALTS-<version>.zip`; package notes and inventories remain inside that ZIP, while the GitHub Release body carries its public note.
- Separated the installed user payload from repository-only `.gitattributes`, `.github/workflows/ci.yml`, `.gitignore`, and `MALTS_RELEASE.json` while binding both surfaces in the release manifest.
- Added one self-contained public-repository integrity workflow that validates the checked-out source without entering an installed generation or optional archive; local qualification remains required for releases.
- Excluded release construction controls, local project controls, handoffs, evidence, test suites, test data, CI support material, caches, temporary files, Git internals, and private machine state from installed generations.
- Added default-deny path classification, dependency closure, byte provenance, privacy scanning, and machine-specific path rejection for the public user surface.

### Documentation and language

- Established English technical documents and equivalent Simplified Chinese user guides.
- Kept one canonical mutable project file per role by default; narrative content may use the user or project language.
- Made full translated runtime mirrors explicit rather than automatic to avoid drift and duplicate state.
- Added comprehensive system overview, core design, usage, handoff, security, lifecycle, capability, installation, update, and release-artifact documentation.

## 0.1.9

- Added shared response-quality guidance to Codex, Claude Code, and OpenCode adapter instruction examples.
- Documented response-quality guardrails in adapter guides and Simplified Chinese mirrors.
- Refreshed version metadata and semantic examples.

## 0.1.8

- Added active `VERSION` validation for project control metadata.
- Added managed instruction synchronization checks for installed Agent tool instruction files.
- Synchronized adapter rules for active version metadata and bilingual documentation parity.
- Updated initialization guidance to avoid copying stale versions from old project artifacts.

## 0.1.7

- Added lightweight native Skill discovery bridges for Codex, Claude Code, and OpenCode while keeping one shared canonical Skill source.
- Added managed-block merging for Agent instruction files with idempotent recognized migration and explicit skip/replace behavior.
- Moved tool-file conflict detection before instruction writes to prevent partial installation.
- Preserved user-modified tool configuration during safe merge operations.
- Added hash-based ownership records for stale managed-file cleanup.
- Separated target tool roots from the shared runtime root and rejected nested layouts.
- Prevented no-update runs from reinstalling unless explicitly requested.

## 0.1.6

- Enforced one canonical project control, report, and handoff file by default.
- Stopped automatically creating translated control mirrors during long-task startup.
- Added guards against legacy rules that recreated duplicate translated runtime state.
- Updated version metadata and release verification examples.

## 0.1.5

- Established `PROJECT_CONTROL.md`, `WORK_TASK_REPORT.md`, and `PROJECT_HANDOFF.md` as the default canonical runtime artifacts.
- Made translated project-control mirrors optional and explicit.
- Allowed narrative content to use the user's or project's primary language while preserving stable fields.
- Updated initialization, long-task scheduling, handoff, templates, checklists, and adapter guidance for the canonical-file policy.

## 0.1.4

- Introduced one shared MALTS runtime root with thin tool adapters.
- Stopped creating full runtime copies inside each tool directory by default.
- Added explicit shared-root installation and update control.
- Added Windows UTF-8 execution guidance to installed instruction templates.
- Rejected duplicate tool-local runtime and Skill copies.

## 0.1.3

- Added review-first update support with explicit pull/install modes for the then-current repository-based layout.
- Added isolated installation validation and installed-layout checks.
- Strengthened public package scanning for machine-specific paths and high-confidence secret values.
- Expanded Codex adapter scaffolding and Simplified Chinese documentation.

## 0.1.2

- Added UTF-8 BOM to Simplified Chinese documentation.
- Aligned the Codex adapter guide with Claude Code and OpenCode structure.
- Fixed Simplified Chinese documentation drift.
- Standardized sub-agent terminology.
- Replaced hard-coded template versions with placeholders.
- Expanded long-task, model-policy, and safety guidance in Agent templates.

## 0.1.1

- Added release hygiene checks and broader bilingual structure validation.
- Improved Claude Code smoke-workflow wording.
- Expanded hidden adapter scaffold coverage.
- Synchronized version, README, changelog, and verification examples.
- Confirmed that public releases excluded user-specific generated state.

## 0.1.0

- Initial public release.
- Added English runtime Skills, templates, and checklists.
- Added optional Codex, Claude Code, and OpenCode adapter structures.
- Added public-safe Agent instruction templates.
- Added an option to install adapter support without replacing existing Agent instruction files.
- Added project handoff rules, MIT license, installation documentation, and optional bilingual documentation.
