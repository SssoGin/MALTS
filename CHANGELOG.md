# Changelog

All notable public changes to MALTS are documented here.

## 1.3.1

MALTS 1.3.1 fixes the v3-to-v4 workspace migration for workspaces with historical closed Sessions.

### Migration fix

- `migrate-workspace-v3-to-v4` archives closed historical Session registry rows in the migration plan instead of failing v4 schema validation on missing lease fields.
- No lease, owner, or authorization data is fabricated for historical Sessions; their control files remain byte-identical.
- ACTIVE Session rows still block migration (`WS_MIGRATION_NOT_QUIESCENT`).
- Added regression `M17` covering historical v3 Sessions, archive content, byte preservation, and post-migration validate/recover.

## 1.3.1（中文摘要）

MALTS 1.3.1 修复含历史已关闭 Session 的工作区 v3→v4 迁移。

- `migrate-workspace-v3-to-v4` 把已关闭的历史 Session registry 行归档进迁移计划，不再因缺少 lease 字段而 v4 schema 校验失败。
- 不为历史 Session 伪造任何 lease、owner 或授权数据；其 control 文件保持字节不变。
- ACTIVE Session 行仍然阻断迁移（`WS_MIGRATION_NOT_QUIESCENT`）。
- 新增回归 `M17`，覆盖历史 v3 Session、归档内容、字节保留与迁移后 validate/recover。

## 1.3.0

MALTS 1.3.0 upgrades the workspace schema to v4 and the Result Contract to v2, adds outcome-oriented Phase and typed Attempt semantics, enforces the authorized-rounds STOP gate, and lowers S0/S1 daily governance cost while keeping legacy workspaces readable.

### Schema and contract

- Workspace schema v4 and Result Contract v2: each governed Task owns one typed lineage authority; Phases, Sessions, reports, and handoffs keep only bindings and projections.
- Outcome-oriented Phase: invocation count, retry count, provider choice, or conversation turns no longer become automatic Phase boundaries; one failed Attempt terminates only that Attempt.
- `max_authorized_rounds` is now an independent runtime STOP gate and a release blocker.
- Append-only typed event ledger; corrections append events and projections are rebuildable.

### Migration, transactions, and side effects

- Explicit cold migration only: `migrate-workspace-v3-to-v4` and `migrate-result-contract-v1-to-v2` are dry-run first, exact-hash bound, and require a quiescent workspace; v1/v2/v3 workspaces remain readable.
- Recoverable multi-surface transactions with lock, journal, preimages, and explicit recovery; no instantaneous multi-file atomicity claim.
- External side effects use typed observations and idempotency keys; unknown dispatch state fails closed.

### Governance cost and delivery

- Read-only `scoped-readiness` Fast Path for S0/S1/S2 routing; UNKNOWN durable delta, active Session, enrolled Artifact, or drift exits the Fast Path.
- Explicit `refresh-project-instructions` rewrites only MALTS-managed blocks and preserves user-owned bytes, BOM, and line endings.
- EN/CH documentation, templates, checklists, and Codex/Claude Code/OpenCode adapters are synchronized from one machine-checkable invariant source.

## 1.3.0（中文摘要）

MALTS 1.3.0 将 workspace schema 升级到 v4、Result Contract 升级到 v2，建立成果导向 Phase 与 typed Attempt 语义，落实授权轮次 STOP 门，并降低 S0/S1 日常治理成本，同时保持旧工作区可读。

- workspace schema v4 与 Result Contract v2：每个受治理 Task 拥有唯一 typed lineage 权威；Phase、Session、report 与 handoff 只保留绑定与投影。
- 成果导向 Phase：调用次数、重试次数、provider 选择或对话轮次不再自动成为 Phase 边界；一次 Attempt 失败只终止该 Attempt。
- `max_authorized_rounds` 现在是独立的运行时 STOP 门，并作为发布阻断条件。
- 仅支持显式冷迁移：`migrate-workspace-v3-to-v4` 与 `migrate-result-contract-v1-to-v2` 均为 dry-run 先行、精确哈希绑定并要求工作区静止；v1/v2/v3 工作区保持可读。
- 带锁、journal、preimage 与显式 recovery 的可恢复多面事务；不宣称瞬时多文件原子可见。
- 只读 `scoped-readiness` Fast Path 提供 S0/S1/S2 路由；UNKNOWN 持久增量、active Session、已 enrollment Artifact 或漂移都会退出 Fast Path。
- 显式 `refresh-project-instructions` 只重写 MALTS 管理的 block，保留用户自有字节、BOM 与换行。
- EN/CH 文档、模板、checklist 与 Codex/Claude Code/OpenCode 适配器由单一机器可检查的 invariant 源同步。

## 1.2.3

MALTS 1.2.3 fixes the release test fixture copying that exceeded the Windows path limit, without changing any runtime, lifecycle, or public-surface behavior.

### Release test deep-path fix

- `SOURCE_COPY_IGNORE` in the release test suite now excludes the private `.release-control/archive` historical tree, matching the production clean-source classification that never includes it.
- Five release tests that previously failed with `WinError 206` on Windows deep paths now pass; the full nine-suite run is green.
- The repository-only CI test now classifies the isolated clean-source fixture, and the fixture filter assertion covers both `candidates` and `archive`.

### Delivery

- No runtime code, schema, Artifact, dependency, payload, VCS, update-check, or remote-publication behavior changed in this release.

## 1.2.3（中文摘要）

MALTS 1.2.3 修复 release 测试 fixture 复制超出 Windows 路径长度限制的问题，不改变任何运行时、生命周期或公开面行为。

- release 测试套件的 `SOURCE_COPY_IGNORE` 现在排除私有的 `.release-control/archive` 历史树，与生产 clean-source 分类保持一致。
- 原先因 Windows 深路径触发 `WinError 206` 的五个 release 测试现已通过，九个套件全绿。
- repository-only CI 测试改为对隔离的 clean-source fixture 分类，fixture filter 断言同时覆盖 `candidates` 与 `archive`。

## 1.2.2

MALTS 1.2.2 hardens ordinary discovery against authority-path assumptions while preserving the v1.2.1 lifecycle and workspace safety contracts.

### Discovery authority paths

- Adds deterministic `authority_paths` to a successful `discover` result, including the tool-local boot, installation registry, exact `registry/active_generation.json` pointer, active generation root, and active `VERSION` path.
- Makes the pointer locator explicit so callers do not probe or infer a sibling `<lifecycle-root>/active_generation.json` path.
- Adds regression coverage proving a wrong sibling pointer file is ignored and ordinary discovery remains read-only.

### Documentation and adapters

- Synchronizes the canonical long-project workspace Skill, its native bridge, Codex/Claude Code/OpenCode adapter guidance, and EN/zh-CN lifecycle documentation with the explicit pointer contract.

## 1.2.2（中文摘要）

MALTS 1.2.2 在保留 v1.2.1 生命周期与工作区安全合同的前提下，修复普通 discovery 对权威路径的假设风险。

- 成功的 `discover` 结果新增 deterministic `authority_paths`，明确 tool-local boot、installation registry、精确的 `registry/active_generation.json` pointer、active generation root 与 active `VERSION` 路径。
- 明确禁止探测或推导旁路的 `<lifecycle-root>/active_generation.json`，并增加错误候选路径回归测试，证明普通 discovery 仍为只读。
- 同步 canonical long-project workspace Skill、native bridge、Codex/Claude Code/OpenCode 适配器和中英文生命周期文档。

## 1.2.1

MALTS 1.2.1 hardens deterministic cross-control consistency, recovery authority, and interrupted workspace-control writes while preserving the v1.2.0 Phase and opt-in Artifact lifecycle defaults.

### Deterministic workspace consistency

- Fresh long-project workspaces use exact schema v3. Exact schema v1/v2 inputs remain readable compatibility contracts and are never silently rewritten by validation, recovery, maintenance, installation update, or active-generation switching.
- Binds the active Phase's full bytes plus normalized Boundary, recorded Boundary Review, and recovery hashes into the required current report, optional existing handoff, and typed runtime projection.
- Separates structural, binding, deterministic-consistency, and advisory-semantic findings so a successful command or semantic recommendation cannot hide stale or conflicting authority.

### Explicit migration and recovery

- Adds dry-run-first `migrate-consistency-records`, `record-phase-boundary-review`, and `reconcile-consistency-records` commands with exact expected hashes, explicit authority, and unique operation IDs.
- Makes recovery authority deterministic: active Session checkpoint, otherwise active Phase recovery, otherwise an explicitly bound terminal Phase, otherwise Project recovery. It never guesses from the newest historical Session.
- Keeps review execution, persisted review outcome, decision, and later mutation authorization as separate states.

### Transaction and Windows fixes

- Adds a persisted workspace transaction domain with original-byte rollback, exact-hash retry/recovery, retained interrupted evidence, and `WS_TRANSACTION_*` errors isolated from Artifact transactions.
- Fixes deep Windows workspace paths by using short exclusive same-directory staging names and extended-length-safe reads; recovery accepts only contained, cardinality-checked legacy or short staged files.
- Prevents public Python CLI entrypoints from writing `__pycache__` or `.pyc` files into an immutable installed generation, even when invoked with plain `python` instead of `python -B`.
- Fails closed on missing/stale current projections, full-control or normalized-section drift, unresolved review state, typed recovery-source drift, incomplete workspace transactions, ambiguous non-empty duplicate markers, and unknown schema versions.

### Synchronization and compatibility

- Synchronizes EN/zh-CN Skills, templates, checklists, public documentation, and Codex/Claude Code/OpenCode projections, including marker uniqueness and command/field parity checks.
- Keeps Artifact lifecycle `NOT_ENROLLED` by default, preserves separate `ART_TRANSACTION_*` paths and codes, never creates Sessions implicitly, and adds no automatic update check, payload scan/mutation, VCS action, or remote publication.

## 1.2.0

MALTS 1.2.0 hardens workspace initialization, Phase boundaries, command-line behavior, and cross-window recovery, and adds an opt-in Artifact lifecycle with transactional mutation.

### Workspace and Phase lifecycle

- Fixes the long-project initialization/documentation mismatch: initialization is ready only with a registered active initial Phase, while Sessions remain explicit bounded work units and are never created per turn or ordinary write.
- Adds Phase Boundary Contract and read-only boundary review, legacy Phase-control migration, `PAUSED`/resume behavior, hash-bound transition planning/apply, bidirectional carry-over provenance, and terminal `SUPERSEDED` closure.
- Fails closed on active-session conflicts, stale plan/control hashes, incomplete carry-over disposition, split active ownership, invalid transitions, and context-recovery plan drift.

### Artifact lifecycle

- Adds optional Project enrollment/index pointers plus owner-local Phase/Session registries and conditional Shared/Archive indexes. Existing schema-v1 workspaces remain readable and default to `NOT_ENROLLED`.
- Adds read-only audit and enrollment preview plus dry-run/apply register, promote, supersede, and reconcile commands under `long_workspace.py artifact`.
- Adds workspace-scoped locking, persisted hash-bound journals, full-state preconditions, staged atomic replacement, exact rollback, idempotent retry, stale-state reporting, and enrolled close gates.
- Never creates a Session implicitly, moves/deletes Artifact payloads, invokes VCS, silently adopts legacy folders, recursively scans undeclared trees, or recreates a missing declared index.

### Feedback and bug fixes

- Resolves documentation/implementation drift (`DOC-001`), tool-local boot discovery ambiguity (`BOOT-001`), and CLI error/exit consistency gaps (`CLI-001`) with positive and negative regression coverage.
- Preserves tool-local `MALTS_BOOT.md` plus registry/pointer/identity/`VERSION` cross-checks as the complete ordinary-startup authority; machine-global `GLOBAL_BOOT.md` remains retired.

### Synchronization and compatibility

- Synchronizes the canonical Skill/capability, EN/zh-CN templates, checklists, user documentation, and Codex/Claude Code/OpenCode projections.
- Registers the Artifact suite in the standard workspace/full regression gate and classifies all new user versus maintainer files in the default-deny release policy.
- Keeps update checks user-requested, all state-changing workspace commands dry-run by default, and remote publication outside local qualification.

## 1.1.1

MALTS 1.1.1 removes the machine-global discovery boot from the product contract
so fresh installations and upgraded machines behave identically, and includes
focused stability and maintainability fixes.

### Unified discovery contract

- Removes the machine-global `GLOBAL_BOOT.md` surface from ordinary startup,
  doctor, install, update, repair, and uninstall behavior. Tool-adjacent
  `MALTS_BOOT.md` cross-checked against the lifecycle registry,
  `active_generation.json`, and active `VERSION` is the complete discovery
  authority.
- A missing machine-global boot no longer degrades the doctor report; a
  pre-existing local file beside the lifecycle root is left untouched and is
  never a transaction target.
- Keeps an explicit optional `--global-boot` cross-check for maintainers who
  intentionally configure one; it is never created, refreshed, or required by
  MALTS itself.

### Stability fixes

- Detects and blocks control-state drift when runtime metadata still marks a
  Phase active but its canonical Phase document is already terminal.
- Corrects capacity metrics so closed or empty decision placeholders are not
  counted as open decisions and task/decision table statuses are scoped to
  canonical sections.
- Corrects managed-block residue inspection so user-owned content outside the
  managed block does not create a false drift result.
- Adds deterministic offline Markdown link validation for local targets,
  missing files, and root escapes.

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
