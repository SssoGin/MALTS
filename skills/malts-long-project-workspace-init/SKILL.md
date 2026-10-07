---
name: malts-long-project-workspace-init
description: Initialize, structurally recover, migrate, or govern a phase-ready MALTS long-project workspace; ordinary unchanged task entry uses the bounded read-only workspace-entry path instead of rerunning initialization.
---

# MALTS Long Project Workspace Init

## Purpose

Initialize a phase-ready long workspace, review its Phase boundary, or recover its structure. Selecting this dedicated Skill is affirmative long-project intent; ordinary unchanged Task entry does not rerun initialization. Use `malts-project-init` for lightweight project setup.

## Select the actual workspace contract

Discover the active runtime through the Host's exact `MALTS_BOOT.md` and verified lifecycle identity. For an adopted or explicitly selected native v2 workspace, run `tools/malts_v2.py workspace --workspace <root>` and use its verified store. A missing/conflicting binding requires v2 recovery, not legacy initialization. Ordinary entry creates no Project, Phase, Session, Run or Artifact.

For adopted v2, the selected store and services own executable state. Historical Markdown controls, `WORK_TASK_REPORT.md`, and the latest historical Session are provenance, not current acceptance or write authority. Read the exact current Task/Phase, its dependencies, actual plan bytes/hash and unresolved effects before the relevant action. A read result or declared hash does not grant execution or verify the plan body.

Read the v2 task workflow's common entry, then select only the relevant mode below. Do not load pre-adoption commands for an adopted v2 request or read all references as a checklist.

| Requested work | Focused reference |
|---|---|
| Phase definition, plan/boundary review or carry-over | [v2 Phase workflow](references/v2-phase.md) |
| Artifact identity, Shared proof or recovery-reference review | [v2 Artifact workflow](references/v2-artifact.md) |
| Adopted-workspace migration, backup or forward recovery | [v2 recovery workflow](references/v2-recovery.md) |
| Ordinary selected Task execution | [v2 Task workflow](../v2/malts-v2-task-workflow/SKILL.md) |
| Explicit new v2 long-workspace setup | The initialization section of [v2 usage](../../docs/V2_PREVIEW_USAGE.md); require complete Project/plan/first active Phase and `phase_ready=true`. TASK_ONLY or a planned/paused Phase is insufficient. |
| A verified workspace that has not adopted v2 | [Pre-adoption workspace contract](references/pre-adoption.md), using its bounded existing entry; this does not authorize migration or a v2 downgrade. |

Review-only requests remain read-only. Reuse applicable authorization for local repairs; no implicit dispatch, network/provider calls, periodic work, global configuration or deletion. Unknown effects require reconciliation; settled registered effects, a pause or an empty Task list do not prove external-writer quiescence.

The pre-adoption `single_phase` and opt-in `resource_admission` procedures remain in their reference. They do not own adopted v2 state. Preserve historical bytes, user content and accepted work; verify the affected entry, dependencies and actual outcome rather than reinitializing the workspace.
