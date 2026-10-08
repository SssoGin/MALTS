# Capability And Skill Governance

A Skill describes a method; a capability describes what a Host or component can provide; exposure determines what is discoverable; authorization determines which effects may execute. MALTS records these decisions separately so source visibility or a routing recommendation cannot expand permission. Current version: **2.0.0**.

## 1. Status And Purpose

Capability governance explains what a workflow can use, which sources are reviewed and how native exposure differs from execution permission. It applies to the whole product, currently **2.0.0**. It is not a third-party package manager.

Without this separation, a catalog can become a second source of operating rules: a copied Skill drifts from its original, a display name is mistaken for an installed implementation, or a high-ranked method is treated as authorized. Governance retains the source identity and makes review/exposure decisions inspectable before any effect.

The registry/router utilities and the v2 execution service solve different problems. Registry metadata identifies reusable content and declared conditions. The router recommends eligible methods. Task services enforce current revisions, Grants, budgets and effect/recovery boundaries. Registering a capability neither creates a Task nor issues a Grant.

First-party schemas and implementations are in [Registry Schema](../tools/capability_registry.schema.json), [Descriptor Schema](../tools/capability_descriptor.schema.json) and [Router](../tools/capability_router.py). Their acceptance is schema/metadata behavior, separate from native-model execution.

## 2. One Physical Source, One Metadata View

A portable Skill has one reviewed physical source. Registry/catalog records refer to identity, revision, hash, compatibility and exposure rather than copying bodies into competing repositories. Thin native MALTS bridges resolve the shared runtime.

A physical source is the reviewed Skill directory and its actual files. A descriptor accompanies MALTS-owned content and declares identity, triggers, inputs/outputs, permissions, dependencies and tool metadata. A generated catalog combines those declarations with source hashes and exposure conditions. None should invent a second body of the Skill.

Thin discovery bridges are permitted derivatives because they serve a Host's indexing interface and resolve the canonical source. Their directory/front-matter names use the malts- prefix, while display metadata names the user-facing workflow. Source and bridge identities must both be checked: a valid descriptor cannot prove that a stale native bridge points at it.

For third-party content, an external sidecar avoids modifying the author's Skill. This preserves upstream ownership and updateability, at the cost of separately maintaining compatibility and review evidence. A sidecar can become stale even when the upstream content still exists.

## 3. Current Release Boundary

The distribution supplies canonical workflows, metadata schemas, lint/router utilities, native projections and current Task services. A declared capability or configuration is not observed Host behavior or user authorization. See [Overview](SYSTEM_OVERVIEW.md).

## 4. Target Governance Layers

Separate physical source, metadata, review/trust, Host compatibility, exposure and runtime authorization. Current v2 Grants bind actors/resources/effects; Skills provide methods. A router cannot override the Host’s policy or current task contract.

| Layer | Question | Relevant identity |
|---|---|---|
| Source | Which bytes implement the method? | Source revision, file/tree hashes |
| Descriptor/sidecar | What does it declare and who owns it? | capability_id, skill_id, provenance |
| Compatibility | Can the selected Host use this form? | Tool/platform/protocol constraints |
| Review and risk | What was inspected, and what effects are possible? | Review state, execution risk, evidence refs |
| Exposure | Should this entry be discoverable here? | Tool-specific exposure policy and projection |
| Execution | May this actor perform this effect now? | Current Task/Grant/budget/admission |

These decisions can legitimately differ. A portable read-only method may be catalog-eligible but not exposed to one Host. A visible update workflow may need write permission not granted for the current investigation. The runtime must use the actual current authorization rather than inherit an exposure label.

## 5. Registry Data Contract

Registry descriptors identify sources and declared applicability/dependencies. Source trust, review state and execution risk remain distinct. tools/capability_registry.schema.json and capability_descriptor.schema.json define the exact data; do not infer new fields or rights from prose.

### 5.1 Capability Descriptor And External Sidecar

A native descriptor describes owned content. An external sidecar records third-party provenance/compatibility without editing that content; tools/external_capability_sidecar.schema.json defines it.

The registry envelope contains schema_version, registry_version, design_status, registry_scope, generated_at and entries. An entry separates identity, content, interface, compatibility, review, exposure, routing and lifecycle. The schema is closed: unknown fields cannot silently add another permission or meaning.

| Field group | Function | Why it remains separate |
|---|---|---|
| id/skill_id/name/declared_name/aliases | Stable identity and lookup | A display alias is not another implementation |
| source/content/descriptor | Locator, revision and hashes | Source existence alone does not detect changed content |
| interface/dependencies | Inputs, outputs and required facilities | A matched method still needs its declared dependencies |
| compatibility/adapters/package_variants | Host/protocol/distribution scope | Portability does not prove native loading |
| source_trust/review_status/execution_risk | Provenance, inspection and possible effects | Trusted origin is not observed safe execution |
| exposure_policy/routing | Visibility and advisory matching | Ranking cannot grant execution |
| lifecycle/verification/evidence_refs/rollback | Update, observed checks and recovery | Metadata must identify its evidence and withdrawal path |

The historical design registry example uses its original design_status and placeholder hashes. It is maintainer reference, excluded from the user payload and not the current machine inventory. For an actual catalog, generate metadata from the selected package and reviewed external sidecars; use the exact source revision and generation time.

An external sidecar includes sidecar_id, capability_id, declared_name, ownership, skill_path, source_hash, capability_tags, tool_scope, risk_class, verified_at, evidence_refs, user_aliases and lifecycle_policy. Its locator belongs to local operator state; do not publish a machine-specific source path as reusable package metadata.

## 6. Trust, Review, And Execution Risk

Trusted provenance does not prove safe behavior. A reviewed method does not authorize an effect. Preserve current source identity and allowlisted purposes; sensitive evidence requires reviewed lineage, not relabeling as public or Growth content.

Review evidence should identify what was checked: parse/schema validity, source hashes, static contract, native discovery or actual task behavior. A label such as static-reviewed cannot be promoted to runtime-verified merely because installation succeeded. When content or relevant Host configuration changes, reconsider the checks dependent on that input.

Risk describes possible effects rather than publisher reputation. A first-party installer can restructure configuration and thus needs plan/preimage checks; a third-party reference may be read-only. Apply the selected route's actual required permissions and contraindications. Keep credentials and protected evidence out of prompts/catalogs unless their purpose and scope have been reviewed.

Source withdrawal, revoked review or compatibility failure excludes affected reuse. Keeping the entry for history is different from keeping it eligible; an old source or a high advisory score cannot restore a withdrawn decision.

## 7. Exposure And Catalog Gate

Expose only currently eligible compatible entries. Disabled, revoked or incompatible material stays excluded. A high ranking cannot make an entry eligible, install it or authorize execution.

## 8. Advisory Router Contract

The router ranks eligible candidates and reports reasons without calling a Skill, changing discovery, granting permission or accepting a task. Current task workflows select task/phase/artifact/recovery topics and read only relevant contracts.

### 8.1 Generated Catalog And Resolver

Generated metadata is a source-derived view; resolve exact current identity and hashes.

### 8.2 Isolated Native Projection

Projection declares ownership and input identity; check native discovery in an isolated selected profile.

### 8.3 W3 Verification Boundary

Static component/projection evidence, installation checks and actual native tasks support their own scopes. Historical W3 checks are not retroactively full Host qualification.

A routing request describes the selected tool, task_intent, task_type and mode. It can also provide authorized_permissions, required_capabilities, installed_capability_ids, exposed_capability_ids, blocked_capability_ids, max_risk and user_override. These are inputs to advisory eligibility/matching, not new authorization records.

The resolver examines compatibility, lifecycle/review conditions, risk, permissions, dependencies and contraindications. Rejected entries retain reasons such as missing-dependency or task-mismatch. It then ranks eligible candidates by task/trigger/mode matches. user_override expresses a preference within eligibility; if the requested candidate remains ineligible, the resolver does not select it anyway.

The result contains selected, no_skill_needed, candidates, authorization_preserved and execution_performed=false. A score is an ordering quantity, not a probability of success, independent review or safety rating. The consumer must resolve actual source identity and obtain appropriate execution admission before performing effects.

Catalog generation uses capability_router.py generate with --malts-root, --source-revision, --package-variant, --generated-at and --out; resolve uses --catalog and --request, with optional --out. Generated files belong outside the reusable package. A generation command writes that operator output but neither installs a Skill nor calls a provider.

## 9. Third-Party Skill Placement Decision

For example, a reviewed Codex portable source can live at `~/.agents/skills/<skill-name>`; compatibility and loading still require verification. Use actual Host loading rules and explicit user intent; do not silently duplicate a portable source into all tools. MALTS lifecycle owns MALTS projections only.

### Existing Skill Consolidation

Inspect source identities, user edits, references and recovery before any relocation/removal. Catalog membership grants no cleanup authority.

Before placement, classify the actual content: portable method, tool-native command, plugin-provided workflow or a generated bridge. Inspect how the selected Host loads it and whether an existing installation already owns that name. Identical names with different bodies require a deliberate source decision; arbitrary renaming can break native metadata or dependencies.

A consolidation must retain any local edits, authoritative source identity and references to old locations before removing duplicates. A hash match proves identical bytes at observation, not absence of future update ownership. If a plugin regenerates its own files, copying them into a second manually maintained root can create lasting divergence.

MALTS's projection/lifecycle manages its declared MALTS files. It does not take ownership of unrelated plugins or user Skills. Third-party installation and deletion follow the Host and user authorization independently of a router recommendation.

## 10. Update And Lifecycle Safety

Preserve personal content outside marked MALTS blocks. Plan and apply verified source updates transactionally; reload native Hosts and verify actual discovery. Codex, Claude Code, OpenCode and DeepSeek Harness retain their loading conventions. See [Lifecycle](LIFECYCLE.md).

## 11. Public Projection And Private State

Publish eligible reusable content only. Keep credentials, user configuration, task databases, journals and raw evidence out of catalog/distribution. Exposure is not permission to copy private state.

## 12. Adoption Sequence

Inspect the actual installation/workspace; select the needed workflow; check current sources and Host facilities; prepare reviewed effects only within existing authority; verify their observed results. Do not auto-adopt a workspace, install a plugin or launch an Agent from a recommendation.

## 13. Acceptance Criteria

Check source identity and schema, dependency closure, current eligibility, intended native exposure and observed operation separately. Report missing/unavailable checks. Requested model/effort and effective execution identity are separate. Global Skill/rule changes need their own scope; neutral/harmful Growth outcomes remain valid outcomes.

A reviewable capability result states source revision/hash, declared interface, selected tool/profile, exposure outcome, checks performed and unavailable checks. Inspect conflicts or missing dependencies before accepting an entry as usable. Parsing a schema or discovering a bridge accepts only that part of the contract.

Runtime capability evidence additionally distinguishes unsupported, provider-unconfigured, configured-unverified, inherited/static and effectively observed bindings. The classifier consumes existing evidence; it does not run a provider call or establish a multi-Agent behavior result. Its g4_status remains NOT_RUN even when preconditions are met. An effective concurrency ceiling must come from the observed profile rather than directory count or requested model names.
