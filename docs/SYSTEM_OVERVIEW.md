# MALTS System Overview

This document describes the purpose, function, optional capabilities, and operating boundaries of MALTS. It is intended as a public system explanation rather than an implementation reference. The detailed design invariants are recorded in `docs/CORE_DESIGN.md`.

## 1. System Purpose

MALTS is a portable workflow system for long-running coding tasks performed or assisted by AI agents. Its purpose is to make agent work recoverable, verifiable, and transferable across bounded execution rounds.

The system addresses a common operating problem: coding Agents can perform useful work, but longer tasks can lose goal context, skip evidence, mix unrelated changes, or become difficult to resume after a window change, interruption, or context compaction. MALTS converts that work from a transient conversation into a file-backed operating loop.

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

### Phase And Final Reporting

`WORK_TASK_REPORT.md` records phase or final delivery information. It should include the result, changed files, verification evidence, known risks, and next steps. It is normally user-facing and can follow the user's project language.

### Handoff And Continuation

`PROJECT_HANDOFF.md` is the default Agent-facing continuation file. It should contain enough current context for another Agent or future window to resume without relying on hidden chat state.

### Verification Checklists

The runtime checklists define delivery and quality checks. They do not prove that work is correct by themselves; they provide a repeatable structure for checking and recording evidence.

### Skills, Templates, And Checklists

Root `skills/` is the canonical implementation source for MALTS `SKILL.md` workflows such as Grill-Me Preflight, multi-agent scheduling, session handoff, retrospective growth, lightweight single-agent growth, and project initialization. The installer puts only lightweight discovery bridges in each supported tool's native skill directory; each bridge resolves `MALTS_BOOT.md` and delegates to the shared implementation.

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
| Git-based recovery | Optional | Source control can improve rollback or review safety | MALTS does not require Git |

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

## 11. Relationship To Detailed Design

This overview explains what MALTS does and how a user should evaluate it. `docs/CORE_DESIGN.md` provides the detailed design baseline, operating commitments, task sizing model, project state model, multi-agent protocol, memory pipeline, and release boundaries.
