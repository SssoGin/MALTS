# MALTS System Overview

This document describes the purpose, function, optional capabilities, and operating boundaries of MALTS. It is intended as a public system explanation rather than an implementation reference. The detailed design invariants are recorded in `docs/CORE_DESIGN.md`.

## 1. System Purpose

MALTS is a portable workflow system for long-running coding tasks performed or assisted by AI agents. Its purpose is to make agent work recoverable, verifiable, and transferable across bounded execution rounds.

The system addresses a common operating problem: coding Agents can perform useful work, but longer tasks can lose goal context, skip evidence, mix unrelated changes, or become difficult to resume after a window change, interruption, or context compaction. MALTS converts that work from a transient conversation into a file-backed operating loop.

MALTS does not require that operating loop to replay initialization on every task. An unchanged initialized workspace takes a bounded read-only entry path and loads only current authority/evidence; full history, deep validation, cold recovery, report refresh, and schema migration are explicit escalations. Project, Phase, Session, machine index, coordination state, and derived reports have separate ownership so one local maintenance difference does not become a second authority or global stop.

Optional workspace concurrency is resource-based. The default remains a single open Phase with no coordination runtime. An explicitly enabled profile can admit disjoint Phase work against typed path, Artifact, logical record, service, device, and environment locators plus shared/exclusive/queued/isolation-required capabilities. Expiring leases and fencing reject stale executors; one writer and recoverable journals protect root state; uncertain external effects quarantine affected domains until explicit reconcile. This generic model applies to software repositories, documents, databases, CI/CD, build machines, editors, and devices without embedding product-specific rules in Core.

## 2. Problems Addressed

| Problem class | Observed risk | MALTS response |
|---|---|---|
| Goal drift | The task changes implicitly across a long exchange. | Preserve original goal, interpreted goal, exclusions, completion definition, and acceptance criteria. |
| State loss | Work cannot be resumed from chat memory alone. | Externalize task state, decisions, verification, and recovery notes into files. |
| Weak verification | Completion is asserted without evidence. | Require checklists and recorded verification evidence before delivery. |
| Coordination risk | Multiple agents or workstreams create merge and accountability gaps. | Use fit assessment, launch review, scoped contracts, dispatch records, and final reconciliation. |
| Uncontrolled memory growth | Every correction becomes a permanent rule. | Filter reusable lessons through a memory-write process before durable promotion. |
| Tool fragmentation | Different Agent tools use different instruction formats. | Provide adapters for Codex, Claude Code, and OpenCode around one core operating model. |

## 3. Core Operating Model

MALTS connects three loops:

```text
Delivery loop:
goal -> acceptance criteria -> task queue -> execution -> verification -> delivery

Scheduling loop:
state -> bounded round -> optional delegation -> report -> recovery -> next round

Growth loop:
observation -> cause analysis -> reusable lesson -> filtered candidate -> future use
```

The delivery loop keeps work aligned with the user goal. The scheduling loop makes long tasks recoverable. The growth loop preserves reusable knowledge without allowing every incidental observation to become a rule.

## 4. Required Core Capabilities

These capabilities form the system core.

### Recoverable Project Control

`PROJECT_CONTROL.md` is the main state file when MALTS is enabled. It records:

- original user goal
- current interpreted goal
- acceptance criteria
- task queue
- file ownership
- decisions
- risks and blockers
- verification records
- recovery notes

The file is intended for the next Agent, next window, or same Agent after context loss.

### Phase-Ready Long-Project Initialization

The lightweight `malts-project-init` workflow establishes root project control. The dedicated `malts-long-project-workspace-init` workflow additionally requires the first active Phase before initialization is complete. Its dry run includes the first `PHASE_CONTROL.md`; missing Phase input writes nothing. Later Phases and every Session remain explicit operations, and initialization never creates a Session automatically.

A root-only legacy workspace remains readable for diagnosis but validates as `NEEDS_INITIAL_PHASE` until its first Phase is registered without overwriting existing user files.

### Cross-Control Consistency And Typed Recovery

Fresh long-project workspaces use CURRENT and default to `single_phase`; supported legacy layouts remain readable internal compatibility inputs and reach CURRENT only through reviewed, explicit, one-hop, hash-bound reorganization. Project, Phase, and explicit Session controls each own their own semantic facts. The workspace runtime owns machine contract/profile/index and transaction bindings; optional coordination runtime owns Admissions/fencing/quarantine. CURRENT report/handoff files are on-demand views, while legacy inputs retain strict projection bindings until reorganization.

Validation separates structural, binding, deterministic-consistency, maintenance-warning, and advisory-semantic findings. Canonical/authorization/transaction/Admission/fencing/unknown-authority drift blocks affected work; derived-view drift warns and reconciles locally. Recovery selects active Session checkpoint, primary active Phase recovery, explicitly bound terminal Phase, then Project recovery; it never guesses from the newest historical Session. Workspace and coordination authority share one writer/transaction namespace and retain interrupted evidence until exact-hash recovery succeeds; Artifact transactions remain separate.

### Phase And Final Reporting

`WORK_TASK_REPORT.md` can present Phase or final delivery information when a durable report is requested or materially useful. Under CURRENT it is derived/non-authoritative and refreshed on demand; ordinary unchanged work does not rewrite it.

### Handoff And Continuation

`PROJECT_HANDOFF.md` is an on-demand Agent-facing continuation view. A new window begins with bounded `workspace-entry`; the handoff is read/refreshed only when relevant and never replaces canonical controls.

### Verification Checklists

The runtime checklists define delivery and quality checks. They do not prove that work is correct by themselves; they provide a repeatable structure for checking and recording evidence.

### Skills, Templates, And Checklists

Root `skills/` is the canonical implementation source for seven MALTS `SKILL.md` workflows: Grill-Me Preflight, long-project workspace initialization, multi-agent scheduling, session handoff, retrospective growth, lightweight single-agent growth, and project initialization. The installer puts only the seven corresponding `malts-*` lightweight discovery bridges in each supported tool's native skill directory; each bridge resolves `MALTS_BOOT.md` and delegates to the shared implementation. The `malts-*` machine name is part of the adapter contract so users can find every MALTS-owned native skill entry by searching `/MALTS`; `agents/openai.yaml` provides the uppercase user-facing `MALTS ...` display name and a short description that avoids repeating the title.

`runtime/EN/templates` and `runtime/EN/checklists` define the expected shape of task contracts, reports, handoff files, project control files, and verification gates. They complement the root skill packages without changing the public skill source.

## 5. Optional Capabilities

MALTS is intentionally single-agent first. Optional capabilities are enabled only when the task requires them.

| Capability | Default state | Use when | Boundary |
|---|---|---|---|
| Grill-Me Preflight | Offered for non-trivial or unclear starts | Requirements, success criteria, scope, or tradeoffs are not clear | Clarification only; not sub-agent dispatch |
| Multi-agent scheduling | Off | Independent exploration, verification, or parallel work reduces risk or cost | Requires launch review and explicit `确认运行` |
| Bilingual documentation sync | Off | A project needs user-facing Chinese review mirrors | English release docs remain the default runtime source |
| Memory Pipeline | Available | A lesson is reusable beyond the current task | Requires filtering and destination selection |
| Adapter instruction templates | Optional | A supported Agent tool should remember MALTS behavior | Default managed-block merge preserves user-owned surrounding text |
| Third-party Skill placement guidance | Available | Before a user-authorized Skill installation | Classification and destination recommendation only; no automatic lifecycle management |
| Git-based recovery | Optional | Source control can improve rollback or review safety | MALTS does not require Git |

The Capability Registry and advisory Workflow Router are implemented v1.0 components. The transactional lifecycle activates verified MALTS-owned runtime content and thin native discovery projections, while third-party Skill discovery and lifecycle remain outside MALTS ownership. The Router recommends but never invokes a Skill, dispatches an Agent, or bypasses authorization. See [Capability And Skill Governance](CAPABILITY_AND_SKILL_GOVERNANCE.md).

## 6. Supported Tool Adapters

MALTS separates the core workflow from tool-specific installation details.

| Adapter | Primary instruction file | Notes |
|---|---|---|
| Codex | `AGENTS.md` | Provides Codex-facing operating rules and MALTS reminders. |
| Claude Code | `CLAUDE.md` | Adds optional Claude Code agents and commands; resolves MALTS through shared `MALTS_ROOT`. |
| OpenCode | `AGENTS.md` | Adds OpenCode-specific configuration and optional agent scaffold; resolves MALTS through shared `MALTS_ROOT`. |

Adapter documents should stay synchronized unless a change applies to only one runtime. Tool differences are adapter-layer concerns and should not change the core MALTS model.

Each instruction template marks the MALTS-owned block explicitly. Updates replace only that block, append it when absent, or migrate one recognizable legacy discovery section. `Skip` leaves the file untouched; full-file `Replace` is opt-in.

## 7. Typical Use Cases

MALTS is designed for tasks with one or more of these properties:

- the task may exceed one comfortable context window
- the task has multiple phases
- the task modifies multiple files or modules
- a later Agent may need to continue the work
- verification evidence matters
- requirements are unclear enough to justify preflight clarification
- independent review or exploration may reduce risk
- corrections produce reusable lessons worth filtering

Examples include migrations, feature implementations with acceptance criteria, documentation protocol changes, multi-tool adapter updates, release preparation, long bug investigations, and recovery-sensitive refactors.

## 8. Non-Goals And Boundaries

MALTS does not:

- run a mandatory scheduling service
- replace the Agent runtime
- replace source control, CI, package managers, editors, or permission systems
- auto-dispatch sub-agents
- make every task a long task
- guarantee correctness without verification
- certify work for which no evidence is available
- store secrets, tokens, sensitive memory dumps, or raw session logs
- override user approval for high-risk actions

These boundaries are part of the system design. They keep MALTS portable and reduce accidental expansion into responsibilities that should remain external.

## 9. Activation Modes

| Mode | When used | Required files | Result |
|---|---|---|---|
| Normal single-agent work | Small, clear, low-risk tasks | None by default | Low overhead, direct completion, relevant verification |
| MALTS single-agent mode | Work needs recoverable state or phase reporting | `PROJECT_CONTROL.md`; often `WORK_TASK_REPORT.md` and `PROJECT_HANDOFF.md` | Persistent state with main-controller execution |
| MALTS multi-agent mode | Delegation has clear operational value | MALTS state files plus task contracts and sub-agent reports | Controlled delegation with recorded accountability |

The default mode is normal single-agent work. MALTS state files are created only when the task is non-trivial, MALTS is enabled, or the work grows enough to need recoverable state.

## 10. Public Release Contents

The public release repository contains:

- runtime skills
- templates
- checklists
- adapter examples
- installer script
- lightweight linting tools
- design, installation, usage, handoff, security, and maintenance documentation

The release repository should not contain handoff outputs, project-specific control files, user-specific archives, raw sessions, caches, credentials, or generated migration packages.

## 11. v1.1 Coherence Gates

MALTS v1.1 adds three related safeguards: event-triggered Plan Recheck binds active plan bytes to the owning Phase; governed Codex peer tasks preserve approved model/effort, current-workspace, lifecycle, and archival evidence; and tool-local discovery cross-checks registry, active pointer, and `VERSION`. All three are read/review first and fail closed on drift.

## 12. v1.2.2 Discovery Authority Gate（历史）

The v1.2.2 candidate preserves the v1.2.1 schema-v1/v2/v3 dispatch, hash-bound review/recovery, and crash-recoverable workspace transaction domain. It additionally exposes deterministic discovery `authority_paths` and fixes the active pointer contract to `<lifecycle-root>/registry/active_generation.json`; a wrong sibling pointer is never used. Operation success is not semantic resolution, persistence, or authorization. The candidate keeps Artifact, payload, VCS, Session-creation, update-check, and publication boundaries unchanged.

## 13. v1.2.3 Release Test Deep-Path Fix

The v1.2.3 candidate fixes release test fixture copying that exceeded the Windows path length limit: the test suite's `SOURCE_COPY_IGNORE` excludes the private `.release-control/archive` historical tree, matching production clean-source classification, and the repository-only CI test classifies the isolated clean-source fixture. Five `WinError 206` failures are resolved and all nine suites are green. No runtime, schema, Artifact, dependency, payload, VCS, update-check, or remote-publication behavior changed.

## 14. v1.3.0 Schema v4, Result Contract v2, And Fast Path

The v1.3.0 candidate upgrades the workspace schema to v4 and the Result Contract to v2: each governed Task owns one typed lineage authority while Phase, Session, report, handoff, and runtime keep only bindings and projections. A failed Attempt terminates only that Attempt; `max_authorized_rounds` is an independent runtime STOP gate. Migration is explicit cold migration (`migrate-workspace-v3-to-v4`, `migrate-result-contract-v1-to-v2`); legacy schemas remain readable. Multi-surface writes use recoverable transactions with lock, journal, preimages, and explicit recovery. A read-only `scoped-readiness` Fast Path and explicit marker-owned `refresh-project-instructions` lower S0/S1 governance cost without bypassing authorization or consistency gates.

## 15. v1.3.1 Migration Fix For Historical Sessions

The v1.3.1 candidate fixes the v3-to-v4 workspace migration for workspaces with historical closed Sessions: closed Session registry rows are archived into the migration plan instead of failing v4 schema validation on missing lease fields, no lease/owner authority is fabricated, historical Session files remain byte-identical, and ACTIVE Session rows still block migration.

## 16. v1.5.0 CURRENT Workspace Governance And Efficient Entry

MALTS 1.5.0 separates Phase milestone state from short-lived execution Admission. The default `single_phase` profile remains coordination-free, while the explicit `resource_admission` profile supports multiple resource-governed OPEN Phases through typed locators, capability policies, queues, leases, fencing, stale-executor rejection, and domain-scoped `UNKNOWN` reconciliation. Ordinary work enters through a bounded, read-only `workspace-entry`; full historical validation and cold recovery are reserved for real drift or recovery events. One-hop explicit reorganization maps supported legacy layouts directly to CURRENT without a user-visible migration chain or implicit lifecycle entities. User status rendering and delegated model recommendations are language-aware and cost-aware while preserving stable machine codes and fail-closed safety boundaries.

## 17. Relationship To Detailed Design

This overview explains what MALTS does and how a user should evaluate it. `docs/CORE_DESIGN.md` provides the detailed design baseline, operating commitments, task sizing model, project state model, multi-agent protocol, memory pipeline, and release boundaries.
