# Capability And Skill Governance

This guide retains the source, registry, trust, exposure, routing and lifecycle sections used since the initial MALTS product design.

## 1. Status And Purpose

Capability governance explains what a workflow can use, which sources are reviewed and how native exposure differs from execution permission. It applies to the whole product, currently **2.0.0**. It is not a third-party package manager.

## 2. One Physical Source, One Metadata View

A portable Skill has one reviewed physical source. Registry/catalog records refer to identity, revision, hash, compatibility and exposure rather than copying bodies into competing repositories. Thin native MALTS bridges resolve the shared runtime.

## 3. Current Release Boundary

The distribution supplies canonical workflows, metadata schemas, lint/router utilities, native projections and current Task services. A declared capability or configuration is not observed Host behavior or user authorization. See [Overview](SYSTEM_OVERVIEW.md).

## 4. Target Governance Layers

Separate physical source, metadata, review/trust, Host compatibility, exposure and runtime authorization. Current v2 Grants bind actors/resources/effects; Skills provide methods. A router cannot override the Host’s policy or current task contract.

## 5. Registry Data Contract

Registry descriptors identify sources and declared applicability/dependencies. Source trust, review state and execution risk remain distinct. tools/capability_registry.schema.json and capability_descriptor.schema.json define the exact data; do not infer new fields or rights from prose.

### 5.1 Capability Descriptor And External Sidecar

A native descriptor describes owned content. An external sidecar records third-party provenance/compatibility without editing that content; tools/external_capability_sidecar.schema.json defines it.

## 6. Trust, Review, And Execution Risk

Trusted provenance does not prove safe behavior. A reviewed method does not authorize an effect. Preserve current source identity and allowlisted purposes; sensitive evidence requires reviewed lineage, not relabeling as public or Growth content.

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

## 9. Third-Party Skill Placement Decision

For example, a reviewed Codex portable source can live at `~/.agents/skills/<skill-name>`; compatibility and loading still require verification. Use actual Host loading rules and explicit user intent; do not silently duplicate a portable source into all tools. MALTS lifecycle owns MALTS projections only.

### Existing Skill Consolidation

Inspect source identities, user edits, references and recovery before any relocation/removal. Catalog membership grants no cleanup authority.

## 10. Update And Lifecycle Safety

Preserve personal content outside marked MALTS blocks. Plan and apply verified source updates transactionally; reload native Hosts and verify actual discovery. Codex, Claude Code, OpenCode and DeepSeek Harness retain their loading conventions. See [Lifecycle](LIFECYCLE.md).

## 11. Public Projection And Private State

Publish eligible reusable content only. Keep credentials, user configuration, task databases, journals and raw evidence out of catalog/distribution. Exposure is not permission to copy private state.

## 12. Adoption Sequence

Inspect the actual installation/workspace; select the needed workflow; check current sources and Host facilities; prepare reviewed effects only within existing authority; verify their observed results. Do not auto-adopt a workspace, install a plugin or launch an Agent from a recommendation.

## 13. Acceptance Criteria

Check source identity and schema, dependency closure, current eligibility, intended native exposure and observed operation separately. Report missing/unavailable checks. Requested model/effort and effective execution identity are separate. Global Skill/rule changes need their own scope; neutral/harmful Growth outcomes remain valid outcomes.
