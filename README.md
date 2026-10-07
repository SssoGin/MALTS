# MALTS 2.0.0

[简体中文](README.zh-CN.md) · [Getting Started](docs/GETTING_STARTED.md) · [Usage](docs/USAGE.md) · [Core Design](docs/CORE_DESIGN.md)

MALTS (Multi-Agent Long-Task Scheduling and Growth System) provides recoverable execution, controlled collaboration and experience management for AI Agent project work. Goals, task revisions, permission scopes, observed effects and acceptance evidence share one service contract, enabling accurate continuation after interruption.

## Where it fits

Use MALTS for work spanning turns, migrations, investigations and documentation delivery. Small, clear tasks can follow project rules directly. Single Agent is the default; delegation, background execution, installation and publication each require appropriate scope. MALTS does not replace models, editors, Git, CI or human decisions.

## Core capabilities in 2.0.0

| Capability | User-visible behavior |
|---|---|
| Task services and versioned dependencies | Continue from current goals/plans/revisions instead of competing summaries |
| Controlled operations | Grants, cumulative budgets, admission and intent/observation constrain managed effects |
| Current acceptance and recovery | Check actual evidence; reconcile unknown effects without replay or renewed allowances |
| Artifacts, handoff and experience | Preserve lineage/manual content, verify present eligibility and bound/retire trials |
| Four Hosts and two languages | Codex, Claude Code, OpenCode and DeepSeek Harness adapters with English/Chinese guides |

v2 gives the selected store/Task services execution authority. Adopted workspaces retain Markdown sources and on-demand report/handoff views. Core reads/writes Schema69 only. Old-project adoption is explicit, without automatic migration or legacy write revival. See [Changelog](CHANGELOG.md) for upgrade implications.

## Start using it

Obtain a reviewed v2.0.0 checkout from the [public repository](https://github.com/SssoGin/MALTS). Use Windows, Python3.11+ and PowerShell; PowerShell7 is recommended. Create an installation plan:

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool Codex
```

Review targets/recovery, then apply the exact plan hash per [Installation](docs/INSTALL.md). Read tool-local Boot, discover and reload the Host to verify Skills/MCP. Follow [Getting Started](docs/GETTING_STARTED.md) to select current work or establish a long workspace.

## Evidence and limits

Recorded representative task/recovery, permission/transaction, installation and bounded collaboration/Growth evidence covers declared versions/profiles. DeepSeek Harness Desktop evidence is Windows0.2.0-rc.2; GUI model cancellation is uncertified. Real Growth trials include neutral outcomes. No universal speedup, money/human savings, arbitrary-OS exclusion or cross-user protected-restoration guarantee is made.

Installation, process exit and historical COMPLETED are not business acceptance. See [Core Design](docs/CORE_DESIGN.md) for mechanisms and evidence boundaries.

## Documentation and layout

[Overview](docs/SYSTEM_OVERVIEW.md) · [Update](docs/UPDATE.md) · [Lifecycle](docs/LIFECYCLE.md) · [v2 Operations](docs/V2_PREVIEW_USAGE.md) · [State Contract](docs/V2_STATE_CONTRACT.md) · [Handoff](docs/HANDOFF.md) · [Security](docs/SECURITY.md)

skills/ contains workflows, runtime/ contracts and EN/CH templates, tools/ services/CLI, adapters/ Host integration, scripts/ user lifecycle entrypoints, and docs/ guides. See [MIT License](LICENSE) and [Third-Party Notices](THIRD_PARTY_NOTICES.md).
