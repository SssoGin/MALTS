# MALTS

**Multi-Agent Long-Task Scheduling and Growth System**

[English](README.md) · [简体中文](README.zh-CN.md) · [Getting Started](docs/GETTING_STARTED.md) · [Usage](docs/USAGE.md)

MALTS is an operating framework for AI Agent project work. It connects goal clarification, planning, execution, verification, handoff and learning into a continuous process. Use it when work exceeds one prompt, one context window or one uninterrupted run, so an Agent can continue from project records after a new conversation, a change of executor or a failure.

One Agent is the default executor. When independent investigation, implementation or verification helps, explicitly authorized Agents can share the work. The main Agent remains responsible for integration, acceptance and delivery. The same goals, stages, verification and recovery methods apply to both modes.

The current version is **2.0.2**. This page describes MALTS as a complete system; version-specific changes and upgrade implications are in the [Changelog](CHANGELOG.md).

## Problems it addresses

Agents can complete useful local work, but long projects need continuity. Goals must remain visible, completed work must stay distinct from pending work, interrupted effects must not be repeated blindly, and separate contributions must be integrated and checked.

| Problem | MALTS response |
|---|---|
| Goals and constraints fade in a long conversation | Preserve goals, exclusions, decisions and acceptance; revisit material changes |
| A new window cannot identify where to continue | Keep stage progress, task results, checkpoints and recovery materials |
| Files exist without proving the user requirement | Define completion and check actual outputs with evidence |
| Agents duplicate work, conflict or leave integration unowned | Separate responsibilities/resources and retain one integration/acceptance owner |
| Lessons are lost or an accident becomes a permanent rule | Select sourced experience, trial it later and retain ineffective/harmful outcomes |
| Agent tools have different configuration and entrypoints | Provide shared workflows with tool-specific adapters and native permission boundaries |

## The complete MALTS workflow

### 1. Establish goals and completion

Define the output, permitted changes, protected material and acceptance. Resolve material uncertainty before implementation. Continue ordinary work already covered by user permission without repeated approval for routine details.

### 2. Organize projects, stages and tasks

A long project has stages with goals, scope and deliverables. Tasks represent executable, acceptable work and retain dependencies. This keeps the overall goal and the current work visible and gives each iteration a finite ending.

### 3. Execute with recoverable progress

Start from the current task and relevant inputs instead of rereading history. Preserve decisions, results and necessary checkpoints. After failure or interruption, establish what occurred and what is uncertain before repairing or continuing.

### 4. Use multiple Agents when appropriate

Delegate separable investigation, implementation or verification with explicit goals, inputs, edit scope, outputs and verification responsibilities. Consider invocation budgets, shared resources and integration costs. Continue with one Agent when there is no useful separation.

### 5. Verify, deliver and hand off

Completion follows actual outputs and applicable checks. Create durable reports when useful/requested and on-demand handoff views for a new window or executor. Preserve manual notes, unresolved issues and exact next steps. Reading views do not replace current project facts.

### 6. Select and validate reusable experience

Corrections, failed verification, recovery or a useful method can trigger a review. Lightweight review first decides whether anything merits recording; material/repeated issues can justify deeper retrospectives. A scoped candidate is tried in later work before promotion, and ineffective/harmful or unsupported experience can be withdrawn. Ordinary success needs no Growth report.

## Choose a workflow

Workflows are delivered as Skills: method packages an Agent can discover and use. Name the workflow and your goal in a normal conversation.

| Need | Workflow | Result |
|---|---|---|
| Establish basic records for work spanning turns | [Project Init](skills/malts-project-init/SKILL.md) · malts-project-init | Project entry, goals, acceptance and current state |
| Resolve material goals/tradeoffs before implementation | [Preflight](skills/grill-me-preflight/SKILL.md) · malts-grill-me-preflight | Evidence-based clarification and remaining decisions |
| Establish long work or review real stage/structure changes | [Long Workspace](skills/malts-long-project-workspace-init/SKILL.md) · malts-long-project-workspace-init | Stage/task structure and recovery entry |
| Continue, verify or recover current work | [Task Workflow](skills/v2/malts-v2-task-workflow/SKILL.md) · malts-v2-task-workflow | Current task and relevant operational methods |
| Continue in a new window or with another Agent | [Handoff](skills/session-handoff/SKILL.md) · malts-session-handoff | Accurate facts, preserved notes and continuation guidance |
| Review a stage, rework or important experience | [Retrospective](skills/project-retrospective-growth/SKILL.md) · malts-project-retrospective-growth | Sourced advice or an authorized trial |
| Check for a lesson after ordinary work | [Lightweight Growth](skills/single-agent-lightweight-growth/SKILL.md) · malts-single-agent-lightweight-growth | Brief advice or no output without a signal |
| Carry out approved multi-Agent work | [Scheduling](skills/multi-agent-long-task-scheduling/SKILL.md) · malts-multi-agent-long-task-scheduling | Roles, resources, budgets, checkpoints and integration responsibility |

## Core and optional capabilities: defaults

| Capability | Default | When useful |
|---|---|---|
| Single Agent | Normal execution path | Ordinary work and strongly dependent tasks |
| Project and long-work records | Selected according to need | Work spans turns/stages/windows and needs persistent goals/progress |
| Multi-Agent scheduling | Requires explicit delegation scope | Responsibilities/resources/results can be separated with useful value |
| Reports and handoffs | On demand | Durable reporting or continuation by another window/executor |
| Lightweight Growth and review | Actual signal or explicit request | Correction, failed checks, recovery or a method worth testing |
| Background/unattended execution | Requires corresponding explicit scope | Runtime behavior and stopping conditions are agreed |

## Typical scenarios

**Code migrations over several rounds.** Preserve the target and compatibility requirements, organize modules into stages/tasks, verify each result and continue from accepted work after interruption.

**Ongoing investigation.** Retain observed facts, rejected hypotheses and next experiments to avoid repeated research after changing windows; use reproduction and validation to assess a repair.

**Team or multi-Agent execution.** Separate modules, alternatives or independent verification while protecting shared edits; the main Agent integrates dependencies and accepts the final result.

**Documentation and research delivery.** Preserve sources, decisions, chapter ownership and acceptance, then check factual support, links and coherence across the complete deliverable.

**Recovery-sensitive engineering.** Keep exact project state/backups and identify what occurred, what remains uncertain and what the next executor can do.

## One formal installation for four Hosts

Codex, Claude Code, OpenCode and DeepSeek Harness share one formal MALTS installation under `~/.agent-system/lifecycle` by default. They use one version and exact content identity, with one plan for installation updates, diagnosis and recovery.

Host configuration roots remain `~/.codex`, `~/.claude`, `~/.config/opencode` and `~/.dsh`. Accounts, model settings, sessions and native tools remain owned by each Host; sharing MALTS does not merge them or automatically change project state. `AllIncluded` selects all four; provide actual paths when Host roots differ from the defaults.

## Start using MALTS

The verified installation path uses Windows and Python3.11+; PowerShell7 is recommended. Supported Agent tools are Codex, Claude Code, OpenCode and DeepSeek Harness, which should already be usable.

Obtain the selected version from the [public repository](https://github.com/SssoGin/MALTS). From its root, create an installation plan:

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool AllIncluded
```

Review source, destinations, existing content and recovery, then apply the reported plan hash per [Installation](docs/INSTALL.md). AllIncluded selects Codex, Claude Code, OpenCode and DeepSeek Harness through one installation entry. See [Update](docs/UPDATE.md) for an existing installation.

Once installation and actual Host loading are verified, start naturally:

> Use MALTS for this module migration. Inspect the project, define scope and acceptance, implement and verify in stages, and preserve recoverable progress after interruption. Decide commit/publication separately.

Or continue existing work:

> Continue this MALTS project's current task. Check progress, accepted results and unresolved issues, then proceed from the correct next step without reinitializing.

See [Getting Started](docs/GETTING_STARTED.md) for a runnable first example and exact setup/verification.

## Updating an existing installation

Create an update plan from the repository version you intend to use:

```powershell
.\scripts\Update-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool AllIncluded
```

Review it, then use the actual reported path/hash:

```powershell
.\scripts\Update-MALTS.ps1 -Apply -PlanPath '<reviewed-plan-path>' -ExpectedPlanHash '<reviewed-plan-sha256>'
```

See [Update](docs/UPDATE.md) for tool selection and treatment of user content. Installation updates do not automatically migrate projects.

## How the current version improves the system

2.0.0 retains MALTS's overall process while strengthening state, execution and verification:

- **Clear current progress.** Shared services preserve/check projects, stages and tasks, bind task/plan revisions and separate reading reports from current state.
- **Reliable interruption handling.** Separate preparation, actual execution and observed results. Investigate uncertainty instead of repeating effects or resetting consumed budgets.
- **Stronger completion.** Check requirements, outputs, dependencies and evidence instead of trusting historical completion labels.
- **Explicit collaboration and reuse.** Bind work, resources and budgets; preserve provenance and current eligibility for artifacts, handoffs and experience.
- **More complete tool integration and guidance.** Add DeepSeek Harness and organize English/Chinese installation, usage, design and upgrade documentation.

Continue using the goal–execution–verification–recovery–review process. Project adoption, compatibility and recovery implications are explained in [Update](docs/UPDATE.md).

## Support and boundaries

MALTS organizes project work; reasoning, tools, repositories, editors and user decisions remain with their respective systems. Selecting a workflow does not automatically enable delegation, background work, paid calls or publication.

Code, installation and representative native-task/recovery evidence exist, without a guarantee that every task succeeds or universal speed/money savings. Recorded DeepSeek Harness Desktop evidence uses Windows0.2.0-rc.2; see its [adapter guide](adapters/deepseek-harness/README.md). See [Security](docs/SECURITY.md) for protected restoration and external-tool boundaries.

## Workspace records and deliverables

| Record or output | Purpose |
|---|---|
| Project, stage and task records | Goals, scope, plans, dependencies, progress and acceptance |
| Business deliverables | Code, documents, data or tool results the user actually needs |
| Verification and recovery material | Checks, checkpoints and necessary backups supporting acceptance/recovery |
| Reports and handoffs | On-demand outputs, unresolved work, next steps and preserved manual notes |
| Sourced experience candidates/trials | Applicability, observed benefit and withdrawal conditions |

Corresponding workflows maintain these records. Current workspace state remains distinct from reading reports, while business files/user data stay in their actual project. See [Usage](docs/USAGE.md).

## Documentation map

| Topic | Reading |
|---|---|
| The complete system and its applicability | [System Overview](docs/SYSTEM_OVERVIEW.md) |
| Installation and first work | [Getting Started](docs/GETTING_STARTED.md), [Install](docs/INSTALL.md) |
| Daily work, long projects, collaboration and learning | [Usage](docs/USAGE.md) |
| Interruption, handoff, upgrades and recovery | [Handoff](docs/HANDOFF.md), [Update](docs/UPDATE.md), [Lifecycle](docs/LIFECYCLE.md) |
| Mechanisms and design tradeoffs | [Core Design](docs/CORE_DESIGN.md) |
| Skills, capabilities and experience reuse | [Governance](docs/CAPABILITY_AND_SKILL_GOVERNANCE.md) |
| Controller commands and exact protocols | [Operations](docs/V2_PREVIEW_USAGE.md), [State Contract](docs/V2_STATE_CONTRACT.md) |
| Safety, offline package and languages | [Security](docs/SECURITY.md), [Archive](docs/RELEASE_ARTIFACT.md), [Languages](docs/BILINGUAL_DOCS.md) |
| Agent-assisted setup and checks | [Agent Installation](docs/AGENT_INSTALL.md) |
| Current and historical version changes | [Changelog](CHANGELOG.md) |

## Repository contents

```text
skills/       Project, long-task, collaboration, handoff and Growth workflows
runtime/      Runtime contracts, English/Chinese templates and checklists
adapters/     Tool integration and native entrypoints
tools/        State, execution, verification and recovery tools
scripts/      Installation, updates and installation lifecycle
docs/         System, usage, design and technical references
```

MALTS provides reviewed legacy-workspace adoption and long-project readiness queries. Ordinary new workspaces keep management data inside the project; existing external stores can relocate through a reviewed workflow. The four tools continue to share one core and task state. See [workspace management and migration](docs/MANAGEMENT_AND_RELOCATION.md).

## Version

Current release: **2.0.2**. See the [MALTS 2.0.2 Release](https://github.com/SssoGin/MALTS/releases/tag/v2.0.2) for notes/optional offline ZIP and [Changelog](CHANGELOG.md) for history.

## Documentation languages

English and Simplified Chinese guides describe the same system. Project records/manual notes retain their language without a second state copy. See [Languages](docs/BILINGUAL_DOCS.md).

## Acknowledgements

Some Agent methods draw on [andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) and [mattpocock/skills](https://github.com/mattpocock/skills); they are not runtime dependencies and their authors do not endorse this project. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

MALTS uses the [MIT License](LICENSE).
