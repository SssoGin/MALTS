# Changelog

All notable public changes to MALTS are documented here.

## Unreleased

No unreleased user changes.

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
- Separated the installed user payload from repository-only `.gitattributes`, `.gitignore`, and `MALTS_RELEASE.json` while binding both surfaces in the release manifest.
- Excluded release construction controls, local project controls, handoffs, evidence, test suites, test data, CI configuration, caches, temporary files, Git internals, and private machine state from installed generations.
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
