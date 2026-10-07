# MALTS Capability and Skill Governance

This is part of the complete MALTS system documentation. Current implementation/version is2.0.0; workflow context is in [System Overview](SYSTEM_OVERVIEW.md) and [Usage](USAGE.md).

## 1. Method, capability and permission

Skills describe methods, capabilities describe actual Host facilities, and Grants record authorized actors/resources/effects. Skill installation, tool advertisements, configuration and model upgrades do not enlarge permission or prove actual calls.

## 2. Goal-directed routing

Verify project instructions, runtime and selected workspace. The v2 router selects task/phase/artifact/recovery instead of loading history for one question. Task execution reads bounded context and relevant references. Complexity/multiple files alone do not authorize delegation, unattended work or migration.

## 3. Instructions and Hosts

Shared core generates marked MALTS instructions; tool-local Boot identifies the actual runtime. Codex, Claude Code, OpenCode and DeepSeek Harness retain native loading/configuration rules. Preserve manual content and applicable project/current user instructions. Another tool's reference file is not automatically the active entry.

MCP exposes Host-approved actions only. Read-only endpoints mint no Grants; write endpoints still check service preconditions. Effective model/effort requires observable evidence separate from requested labels.

## 4. Growth and global changes

Experience uses sourced proposals, bounded trials, comparable future results, withdrawal and retirement. Encryption is not Growth eligibility; approved purposes and reviewed lineage remain necessary. Neutral outcomes remain neutral. DEPRECATED/REMOVED/REJECTED cannot be resurrected by late outcomes.

Global Skill/rule/plugin changes require their own authorization; project advice cannot create it. Evaluate actual behavior and benefit before changing methods instead of adding permanent prompts for every mistake. See [Core Design](CORE_DESIGN.md) and [v2 Operations](V2_PREVIEW_USAGE.md#v2-growth).

## One Physical Source, One Metadata View

A reviewed portable Skill has one physical source. Registry entries reference source/revision/hashes and compatibility rather than copying its body.

## Capability Descriptor And External Sidecar

A descriptor records native content identity. An external sidecar describes third-party material without editing its files. Both keep provenance, dependencies and exposure declarations explicit.

## Trust, Review, And Execution Risk

Source trust, review state and execution risk are separate fields. Trusted provenance does not prove safe behavior; a reviewed method does not authorize an effect.

## Exposure And Catalog Gate

Catalog exposure requires the current eligibility checks. Visibility is not execution permission. Disabled, revoked or incompatible material remains excluded instead of being made eligible by a routing score.

## Advisory Router Contract

The capability router ranks eligible candidates and reports reasons. Its advice neither accepts a Task nor executes a tool, changes permission or overrides the selected Host policy.

## Generated Catalog And Resolver

Generated metadata is a view of reviewed source identities. Resolve current content and hashes; stale catalogs require regeneration/verification, not manual eligibility edits.

## Isolated Native Projection

Native projections are tool-specific derivatives with declared ownership and input identity. Test their discovery in a selected isolated profile. A configured projection is not real-tool behavior proof.

## W3 Verification Boundary

Historical W3 evidence covers static components and isolated projections only. Later installation and native Task evidence retain their own dates/inputs; no earlier scope is retroactively enlarged.

## Third-Party Skill Placement Decision

Use the Host loading rules and one canonical source. A Codex portable Skill can use ~/.agents/skills/<skill-name>; generated tool views must not create conflicting bodies. MALTS is not a third-party package manager.

## Public Projection And Private State

Share eligible portable content only. Keep project credentials, journals, evidence bodies and user configuration out of catalogs and distribution. Exposure does not authorize copying private state.

Native tool-specific roots are ~/.codex/skills/<skill-name>, ~/.claude/skills/<skill-name> and ~/.config/opencode/skills/<skill-name>. Select the destination from actual Host loading and explicit user intent; do not duplicate a portable source silently.
