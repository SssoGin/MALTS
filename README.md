# MALTS

**Multi-Agent Long-Task Scheduling and Growth System**

Languages: [English](README.md) | [简体中文](README.zh-CN.md)

MALTS is a file-based workflow system for AI coding agents. It records goals, plans, task ownership, verification, handoffs, and reviewed lessons in ordinary project files so long-running work stays recoverable, inspectable, and easier to continue safely.

MALTS is relevant for migrations, multi-file changes, long investigations, release preparation, protocol or documentation work, and other tasks where a lost decision or an unverified claim of completion would create avoidable risk.

MALTS is single-agent first. The main Agent remains the normal executor; multi-agent work is an optional, explicitly reviewed division of work rather than something that starts merely because MALTS is installed.

## Start Here

| Need | Read |
|---|---|
| Install MALTS from this repository and run a first task | [Getting Started](docs/GETTING_STARTED.md) |
| Understand what MALTS does and when to use it | [System Overview](docs/SYSTEM_OVERVIEW.md) |
| Review the full operating model and boundaries | [Core Design](docs/CORE_DESIGN.md) |
| Install or update a specific Agent tool | [Install](docs/INSTALL.md) and [Update](docs/UPDATE.md) |
| Let an Agent assist with installation safely | [Agent Install](docs/AGENT_INSTALL.md) |
| Use the optional offline ZIP | [Release Artifact](docs/RELEASE_ARTIFACT.md) |

## What Problem It Solves

Long Agent tasks fail differently from short prompts. Context can be compressed, goals can drift, an incomplete result can be mistaken for a completed one, several work lanes can collide, and useful lessons can be either lost or promoted too broadly.

MALTS responds by externalizing important task state, defining completion and verification criteria, keeping a recoverable handoff, requiring a launch review before real sub-agent dispatch, and filtering reusable lessons before they become durable guidance.

## What It Provides

- Long-task planning and recovery through `PROJECT_CONTROL.md`
- Phase or final evidence through `WORK_TASK_REPORT.md`
- Agent-facing continuation through `PROJECT_HANDOFF.md`
- Explicit Phase and Session controls for bounded long-project work
- Grill-Me Preflight for assumptions, boundaries, tradeoffs, and acceptance criteria
- Optional multi-agent launch review, task contracts, and responsibility boundaries
- Delivery, quality, and memory-write checklists
- English and Simplified Chinese runtime templates
- Native `malts-*` Skill bridges for Codex, Claude Code, and OpenCode
- Review-first install, update, recovery, rollback, and residue handling
- Migration handling for known MALTS `v0.1.0` through `v0.1.9` layouts

## Core And Optional Capabilities

| Capability | Default | Purpose |
|---|---|---|
| Single-agent execution | On | Keep small and clear work low-overhead. |
| `PROJECT_CONTROL.md` | Used for non-trivial or recovery-sensitive work | Preserve goal, queue, decisions, risks, and verification state. |
| `WORK_TASK_REPORT.md` | Used after MALTS phases or final delivery | Record result, evidence, remaining risk, and next steps. |
| `PROJECT_HANDOFF.md` | Used for continuation or context-risk handoff | Give a future Agent a restart-safe current state. |
| Grill-Me Preflight | Offered for unclear or non-trivial work | Surface assumptions and acceptance criteria before implementation. |
| Multi-agent scheduling | Off | Add controlled delegation only when it has clear value. |
| Growth review | Available | Filter reviewed lessons before durable promotion. |
| Bilingual documentation | Available | Provide English and Simplified Chinese references without duplicating project state. |

## Activation And Artifacts

MALTS does not create permanent control files for every short task. For small work, stay single-agent and use the normal project instructions.

When a task needs recoverable long-task mode, create or reuse `PROJECT_CONTROL.md` in the project root. Each MALTS phase or final delivery should write or update `WORK_TASK_REPORT.md`. Use `PROJECT_HANDOFF.md` when a future Agent needs the recorded state. Narrative content may use the project's working language; translated mirror files are optional and explicit.

| File | Default role |
|---|---|
| `PROJECT_CONTROL.md` | Canonical project state, task queue, decisions, risks, and verification status. |
| `WORK_TASK_REPORT.md` | Canonical phase or final report with direct evidence. |
| `PROJECT_HANDOFF.md` | Canonical continuation and recovery context. |

## Repository Layout

```text
skills/                 Canonical MALTS Skill packages
runtime/EN/             English templates and checklists
runtime/CH/             Simplified Chinese templates and checklists
adapters/               Codex, Claude Code, and OpenCode adapter material
scripts/                User installation, update, lifecycle, and ZIP-verification entry points
tools/                  Runtime controllers, schemas, and user operation tools
docs/                   User guides, design references, and security guidance
MALTS_RELEASE.json      Repository identity for review-first repository installation
VERSION                 Current package version
LICENSE                 MIT license
THIRD_PARTY_NOTICES.md  Required attribution notices
```

The installed generation intentionally excludes release construction, release publication controls, tests, fixtures, candidates, local handoffs, caches, machine paths, credentials, and user-private state. `MALTS_RELEASE.json` is repository-only identity metadata: it verifies the public source tree but is not copied into an installed generation.

## Documentation Map

- [Getting Started](docs/GETTING_STARTED.md): installation and first-use path.
- [Install](docs/INSTALL.md): repository-first installation commands and roots.
- [Update](docs/UPDATE.md): review-first replacement of an existing installation.
- [Lifecycle](docs/LIFECYCLE.md): generations, plan hashes, rollback, recovery, and cleanup.
- [Usage](docs/USAGE.md): normal tasks, long tasks, multi-agent work, growth, and handoff.
- [System Overview](docs/SYSTEM_OVERVIEW.md): public explanation of goals, features, and boundaries.
- [Core Design](docs/CORE_DESIGN.md): detailed operating model and invariants.
- [Agent Install](docs/AGENT_INSTALL.md): authorization and source-selection rules for Agents.
- [Release Artifact](docs/RELEASE_ARTIFACT.md): optional single-ZIP offline delivery.
- [Security](docs/SECURITY.md): source and package verification plus privacy boundaries.
- [Bilingual Docs](docs/BILINGUAL_DOCS.md): language and navigation policy.

## Acknowledgements

MALTS includes public-safe adaptations of coding-agent behavior patterns inspired by:

- [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills), for concise coding-agent behavior guardrails.
- [mattpocock/skills](https://github.com/mattpocock/skills), especially the idea of a pre-implementation grilling workflow.

These projects are not dependencies of MALTS and do not endorse this repository. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Install Preview

The public repository is the primary installation source. An Agent normally reads the checked-out repository, validates `MALTS_RELEASE.json` and `VERSION`, creates a review-only plan, and waits for the user to approve that exact plan. It does not download a Release asset by default.

From a public repository root:

```powershell
.\scripts\Install-MALTS.ps1 `
  -RepositoryRoot (Get-Location).Path `
  -UseDefaultRoots `
  -Tool Codex
```

For explicit roots:

```powershell
.\scripts\Install-MALTS.ps1 `
  -RepositoryRoot <PUBLIC_REPOSITORY_ROOT> `
  -LifecycleRoot <LIFECYCLE_ROOT> `
  -Tool Codex `
  -ToolRootCodex <CODEX_ROOT> `
  -PlanPath <NEW_PLAN_PATH>
```

The command writes a new review plan and prints its exact SHA-256. It does not install until the user reviews the plan and supplies its matching hash with `-Apply`. See [Install](docs/INSTALL.md) for the full sequence.

### Optional Offline Archive

The optional Release delivery is one file: `MALTS-<version>.zip`. It contains the immutable release package, `RELEASE_NOTES.md`, and its own package inventories. Use it only when a fixed offline archive is needed or a verified repository source is unavailable.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Verify-MALTSBootstrap.ps1 `
  -ArchivePath .\MALTS-1.0.0.zip `
  -ExtractOutput <EXTRACTED_RELEASE_ROOT> `
  -Apply
```

The verifier checks safe deterministic ZIP structure and then verifies the extracted immutable release package before it writes the final extraction.

## Update Preview

To update, point the updater at a separately reviewed, current public repository source. The updater does not pull Git, check for updates in the background, or download a Release archive.

```powershell
.\scripts\Update-MALTS.ps1 `
  -RepositoryRoot <PUBLIC_REPOSITORY_ROOT> `
  -UseDefaultRoots `
  -Tool Codex
```

As with installation, the first command creates a review plan. Run only the exact plan hash after reviewing selected roots, user modifications, cleanup, rollback, and post-validation actions. The optional offline ZIP can also be used as an explicit update source after bootstrap verification and extraction.

## Documentation Language

The public repository defaults to English source documents. Simplified Chinese documents live in `README.zh-CN.md` and `docs/zh-CN/`; localized runtime references live under `runtime/CH/`. Runtime project artifacts stay single and canonical by default. See [Bilingual Docs](docs/BILINGUAL_DOCS.md).

## Version

Current release version:

```text
1.0.0
```

## License

MIT License. See [LICENSE](LICENSE).
