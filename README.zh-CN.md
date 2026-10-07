# MALTS 2.0.0

[English](README.md) · [快速开始](docs/zh-CN/GETTING_STARTED.md) · [使用指南](docs/zh-CN/USAGE.md) · [核心设计](docs/zh-CN/CORE_DESIGN.md)

MALTS（Multi-Agent Long-Task Scheduling and Growth System）为 AI Agent 的项目工作提供可恢复执行、受控协作和经验管理。它把目标、任务版本、授权范围、操作结果与验收证据组织为同一服务合同，帮助长期工作在中断后准确继续。

## 适用范围

适合跨多轮的代码修改、工程迁移、调查和文档交付。清楚、短小的任务可直接按项目规则完成。默认单 Agent；多 Agent、后台执行、安装和发布使用各自的明确授权。MALTS不替代模型、编辑器、Git、CI或用户决策。

## 2.0.0 的核心能力

| 能力 | 用户获得的行为 |
|---|---|
| Task 服务与版本化依赖 | 从当前目标、计划和版本继续，避免旧摘要成为第二权威 |
| 受控操作 | Grant、累计预算、资源准入和意图/结果记录约束受管执行 |
| 当前验收与恢复 | 检查实际证据；未知效果先对账，恢复不重放或补充旧额度 |
| 成果、交接与经验 | 保留来源和手工内容，核当前复用资格，限定试用并可退役 |
| 四宿主与双语入口 | Codex、Claude Code、OpenCode及DeepSeek Harness适配，中英文指南 |

v2以所选状态库和Task服务管理执行事实；已采用工作区保留Markdown来源，以及按需派生的报告和交接视图。Core当前只读写Schema69。旧项目采用必须显式审阅，不自动迁移或恢复旧写权。变化和升级影响见[版本说明](CHANGELOG.md)。

## 开始使用

从[公开仓库](https://github.com/SssoGin/MALTS)取得已审阅的v2.0.0 checkout，在Windows上使用Python3.11+和PowerShell，推荐PowerShell7。安装先生成计划：

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool Codex
```

审阅输出的目标和恢复方式，再按[安装说明](docs/zh-CN/INSTALL.md)用准确计划哈希执行。读取工具自己的MALTS_BOOT.md并discovery，重载宿主验证Skill/MCP。随后按[快速开始](docs/zh-CN/GETTING_STARTED.md)选择当前Task或建立新长期工作区。

## 验证范围与限制

已有代表性任务、恢复、权限/事务、安装及限定协作/成长证据；它们覆盖声明的版本/profile。DeepSeek Harness Desktop实证为Windows0.2.0-rc.2，GUI模型取消未认证。Growth真实试用含中性结果。MALTS不承诺普遍提速、费用/人工节省、任意OS写者互斥或跨用户受保护证据恢复。

安装通过、进程退出和历史COMPLETED不替代业务验收。完整机制及证据边界见[核心设计](docs/zh-CN/CORE_DESIGN.md)。

## 文档与目录

[系统概览](docs/zh-CN/SYSTEM_OVERVIEW.md) · [更新](docs/zh-CN/UPDATE.md) · [生命周期](docs/zh-CN/LIFECYCLE.md) · [v2操作](docs/zh-CN/V2_PREVIEW_USAGE.md) · [状态合同](docs/zh-CN/V2_STATE_CONTRACT.md) · [交接](docs/zh-CN/HANDOFF.md) · [安全](docs/zh-CN/SECURITY.md)

skills/保存标准工作流，runtime/保存合同与EN/CH模板，tools/提供服务/CLI，adapters/提供宿主适配，scripts/提供用户安装/生命周期入口，docs/提供说明。MIT许可证见[LICENSE](LICENSE)，第三方声明见[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
