# Capability And Skill Governance

This document defines the governance contract for the MALTS v1.0 Capability Registry and Workflow Router. It also fixes the safety boundary for any earlier Skill-consolidation work.

## 1. Status And Purpose

The Registry and advisory Router are implemented v1.0 components. W3 introduced deterministic Catalog generation, an advisory Resolver, collision and dependency checks, and native projection planning/apply inside an explicit isolation root. The transactional lifecycle now activates verified MALTS-owned runtime content and thin native discovery projections. It does not use those components to move, install, update, hide, or remove third-party Skills.

The W3 component evidence remains static and isolated; later lifecycle and real-tool qualification evidence is separate and dated. The Router remains advisory, and MALTS is not a third-party Skill package manager.

## 2. One Physical Source, One Metadata View

A portable Skill has one reviewed physical source. A Capability Registry may describe that source, but it must not become another directory containing a second copy of the Skill body.

The Registry may reference:

- the canonical source locator and revision
- normalized and full-tree hashes
- tool compatibility and adapter projections
- typed dependencies and conflicts
- provenance, review evidence, and rollback references
- lifecycle and per-tool exposure policy

Tool-specific overlays remain real directories owned by their respective tools or installers. Whole-root links across tool Skill directories are prohibited; a tool may use a reviewed per-Skill projection only when its runtime requires one.

## 3. Current Release Boundary

Within the current v1.0 release boundary:

- `skills/` remains the canonical source for MALTS-owned Skills.
- `adapters/skill-bridges/` remains the source for MALTS-owned native discovery bridges.
- the transactional lifecycle manages verified MALTS content and MALTS-owned thin projections only.
- third-party Skill discovery and lifecycle remain owned by the user's Agent tools and their existing installation mechanisms.
- the installed version includes the Registry Schema required for validation; generated Registries and local validation examples remain local user or project state rather than installed version content.

Documentation may describe active MALTS-owned projection only when it is bound by complete installation metadata and verified lifecycle evidence. It must not imply that generated external Catalog state or the Resolver executes a Skill, or that MALTS owns third-party Skill lifecycle.

## 4. Target Governance Layers

The v1.0 target separates five concerns:

1. Physical source: one reviewed Skill body.
2. Registry metadata: identity, provenance, compatibility, risk, exposure, and lifecycle.
3. Tool projection: native discovery entries or overlays required by a target tool.
4. Advisory Router: an explainable recommendation over registered capabilities.
5. Transactional manager: the separately gated journaled install/update/repair/uninstall layer for verified MALTS release content.

The layers were delivered in that order. W3 implemented the Registry/Resolver source components and an isolated native-projection precondition; W6/G3 later activated the verified transactional lifecycle for MALTS-owned content. The Router remains advisory, and neither layer authorizes third-party Skill lifecycle management.

## 5. Registry Data Contract

The machine-readable contract is `tools/capability_registry.schema.json`. A Registry entry must carry enough evidence to answer:

- What is this capability and who owns it?
- Where did its content come from, at which revision, and with which tree hash?
- Which tools and platforms are compatible?
- Which adapters and dependencies are required?
- What was reviewed or verified, and when?
- What may each tool expose to its catalog?
- How can the previous state be restored?

Central metadata is preferred over injecting `skill.yaml`, `VERSION`, `CHANGELOG`, or other MALTS-owned files into every third-party Skill. Upstream content should remain byte-stable unless its owner explicitly adopts the contract.

### 5.1 Capability Descriptor And External Sidecar

MALTS-owned Skills self-describe with one adjacent pair: `skills/<skill-id>/SKILL.md` remains the canonical body and `skills/<skill-id>/capability.json` supplies typed metadata. The descriptor cannot replace or duplicate the Skill body.

External-owned Skills are represented only by an operator-state sidecar that records identity, source hash, tool scope, risk, evidence, and user aliases. An external sidecar may authorize discover-and-route behavior, but it cannot authorize MALTS-managed install, update, projection, or delete.

The Capability Catalog is generated from these inputs and source hashes. It is not hand-maintained and is never a second editable source tree.

## 6. Trust, Review, And Execution Risk

These fields are independent:

- `source_trust`: confidence in origin and provenance.
- `review_status`: what static or runtime review has actually completed.
- `execution_risk`: the impact of scripts, writes, network access, credentials, destructive operations, or self-modification.

A first-party source can still carry high execution risk. A low-risk text-only Skill can still have unknown provenance. No single `trusted` Boolean may replace these dimensions.

## 7. Exposure And Catalog Gate

Physical portability does not authorize universal visibility. Every capability has a per-tool exposure decision.

Before changing a shared Skill source or projection, record the expected visible set for each affected tool and compare it with the actual post-change catalog. The change is blocked when it creates:

- an unreviewed catalog addition or removal
- a duplicate semantic capability with ambiguous precedence
- exposure of a protected, incompatible, or rejected entry
- a catalog expansion that exceeds the reviewed budget or scope
- a difference that cannot be traced to a Registry entry and winner decision

Catalog counts alone are not evidence. Verification uses names, origins, projections, and effective precedence.

## 8. Advisory Router Contract

The first Router is read-only and explainable. Its output includes:

- recommended operating mode
- candidate capabilities and why they match
- required authorization and verification gates
- evidence or uncertainty affecting the recommendation
- why a heavier workflow was not selected

The Router does not move directories, alter discovery settings, hide Skills, install packages, dispatch Agents, or bypass user confirmation. Main-controller responsibility remains unchanged.

### 8.1 Generated Catalog And Resolver

`tools/capability_router.py` validates descriptors, required files, capability dependencies, package variants, names, aliases, and projection targets before generating operator-state Catalog data. Generated output is rejected when its destination is under the MALTS package root.

Collision review covers exact/declared/alias names, target paths, nested-suite exposure, plugin-cache exposure, and recognized MALTS-owned bridge migration candidates. Unknown tool inventory remains unclassified and blocks an unqualified clean result.

Resolver selection is deterministic and advisory. It filters by tool support, exposure, installed/effective inventory, collision blocks, permissions, risk, dependencies, task intent/type, mode, and explicit user override. Its result records `execution_performed: false`; native invocation and authorization remain separate.

### 8.2 Isolated Native Projection

`tools/native_skill_projection.py` renders tool-native `SKILL.md` surfaces from the canonical body, changes only the projected front-matter name, and emits Codex-only `agents/openai.yaml` metadata. Each ProjectionManifest binds the source revision, source/descriptor hashes, package variant, target tool/version, adapter version, generated hashes, dependencies, ownership, and creator.

Apply is permitted only when the target root is contained by an explicit isolation root. A recognized MALTS bridge may be replaced only when its name, marker, capability binding, and allowed file set match. The copied bridge is retained for rollback until postvalidation succeeds, then it is removed immediately. Unknown, modified, or extra-file targets fail closed.

That direct component apply path remains isolation-only. Production tool projections are performed by the journaled lifecycle from a verified closed release and are accepted only when the active-generation, installation-registry, projection, and ownership metadata bind consistently.

### 8.3 W3 Verification Boundary

W3 evidence itself is limited to schema/static validation and isolated filesystem behavior. It closed the G2 Resolver component slice and demonstrated a G3 precondition only. Later W6/G3 evidence activated and fault-tested the lifecycle, and separately authorized G4 rows recorded dated real-tool behavior. Those later results do not turn the W3 wrapper into runtime proof; any current discovery, invocation, behavior, or effective-model claim must cite the exact dated evidence and bound installation metadata.

The v1 Registry, Descriptor, Sidecar, and ProjectionManifest contracts are frozen before the first active operator state. Because no live prior Catalog or ProjectionManifest exists, W3 does not invent a fake v1-to-v2 live migration.

## 9. Third-Party Skill Placement Decision

Placement is a lightweight pre-install decision, not a new Skill, Registry service, or installer. Before installation, the active Agent inspects the candidate `SKILL.md` and bundled files and applies this order:

1. An explicit user destination or tool scope wins.
2. A portable generic Skill defaults to `~/.agents/skills/<skill-name>`.
3. A tool-specific Skill defaults to that tool's own root: `~/.codex/skills/<skill-name>`, `~/.claude/skills/<skill-name>`, or `~/.config/opencode/skills/<skill-name>`.
4. If compatibility remains uncertain, use the active tool's own Skill root instead of assuming shared compatibility.
5. Explain the decision, wait for write authorization, and use the existing installer.

Placement does not authorize cross-tool exposure, duplication, update, removal, or unattended lifecycle management.

### Existing Skill Consolidation

An audit of already installed Skills must classify every discovered Skill before changing its location. The final ledger must have zero unclassified entries.

- Share only a generic Skill whose `SKILL.md`, bundled files, references, dependencies, and tool assumptions have been reviewed as portable.
- Keep product-managed or tool-bundled Skills in the product-owned root so future product updates do not create duplicate ownership.
- Keep tool-specific, compatibility-uncertain, broken-reference, dependency-risk, and unresolved same-name conflict cases in their existing tool roots.
- Use one physical canonical source under `~/.agents/skills/<skill-name>` for an approved shared Skill. Add only the per-Skill projection required by a tool that does not discover that root; do not link whole roots.
- Preserve displaced copies in reversible quarantine, record source hashes and rollback actions, and require post-change catalog plus representative invocation checks for Codex, Claude Code, and OpenCode.

A byte-identical duplicate is useful evidence, but it does not by itself prove cross-tool compatibility. The audit must also establish the intended exposure set.

## 10. Update And Lifecycle Safety

Third-party updates are check-only by default. An apply flow requires:

1. source and revision resolution
2. isolated staging
3. content and metadata diff
4. compatibility, dependency, and risk checks
5. an explicit apply authorization
6. a pre-change snapshot
7. post-change discovery and invocation verification
8. a tested rollback reference

Unattended third-party updates are outside the initial v1.0 scope. Quarantine is reversible; permanent deletion requires separate authorization and observation evidence.

## 11. Public Projection And Private State

Public MALTS artifacts may contain:

- this generic contract
- the Registry Schema
- placeholder examples
- generic lint and regression rules
- canonical MALTS capability descriptors and isolated projection source/tests

Public artifacts must not contain generated inventories, user paths, tool catalogs, conflict tables, source locks, environment hashes, backup locations, quarantine records, or generated Registry state. Public examples use package-relative locators and non-operational placeholder values.

## 12. Adoption Sequence

The stable sequence is:

1. finish reversible physical-source stabilization
2. observe discovery and invocation behavior
3. introduce the Schema and lint contract
4. generate a private read-only Registry projection from verified evidence
5. add source and compatibility locks
6. add an advisory Router
7. evaluate false positives, catalog drift, and operator cost
8. separately decide whether a transactional manager is justified

No second physical Registry tree is introduced at any stage.

## 13. Acceptance Criteria

The governance layer is acceptable only when:

- one capability body has one canonical physical source
- Registry entries are reconstructable from evidence and pass Schema validation
- source trust, review status, and execution risk remain separate
- each tool's effective catalog matches its reviewed exposure set
- Router output is advisory, explainable, and authorization-preserving
- update and rollback operations are staged and reversible
- public release checks reject generated operator state and machine-specific data
- English and Simplified Chinese governance documents remain structurally synchronized
