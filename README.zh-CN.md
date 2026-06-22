# MALTS

**Multi-Agent Long-Task Scheduling and Growth System**

语言：[English](README.md) | [简体中文](README.zh-CN.md)

让 AI 编程代理可靠处理长任务、协作分工并沉淀可复用经验的文件化工作流系统。

MALTS 是一套面向 AI 编程代理的多 Agent 长任务调度与成长系统：它把长任务的目标、计划、分工、验证、交接和复盘沉淀到项目文件中，让任务可恢复、可验证、可协作，并让经验在受控筛选后变成可复用规则。

MALTS 适用于 migrations、multi-file changes、long bug investigations、release preparation、protocol/documentation updates，以及其他一旦丢失上下文或跳过验证就会产生可避免风险的编码任务。

MALTS 是一个 portable workflow system，由 canonical skills、templates、checklists、adapters、scripts 和公开维护文档组成。

> 说明：英文文档是 Agent runtime 的事实源。本文和 `docs/zh-CN/` 下的文档是公开中文入口和译本，用于中文用户理解、安装和评估 MALTS。

## 从这里开始

| 需求 | 阅读 |
|---|---|
| 安装 MALTS 并运行第一个任务 | [入门指南](docs/zh-CN/GETTING_STARTED.md) |
| 理解 MALTS 做什么、什么时候使用 | [系统说明](docs/zh-CN/SYSTEM_OVERVIEW.md) |
| 审阅完整操作模型和设计边界 | [核心设计](docs/zh-CN/CORE_DESIGN.md) |
| 安装特定 Agent 工具 adapter | [安装说明](docs/zh-CN/INSTALL.md) |
| 安全配置 Agent-assisted installation | [Agent 安装协议](docs/zh-CN/AGENT_INSTALL.md) |

## 解决的问题

MALTS 针对 coding-agent work 超过短小自包含对话后出现的操作风险。主要风险包括 goal drift、可恢复状态丢失、完成证据不足、多 Agent 协调不安全，以及 durable rules 或 memory 无控制增长。

MALTS 的响应方式是：将重要状态外部化到文件，定义完成标准，记录验证证据，在子 Agent 分派前要求明确 launch review，并在可复用经验进入 durable guidance 前进行过滤。

## 提供内容

- 通过 `PROJECT_CONTROL.md` 支持长任务规划和恢复
- 可选的多 Agent 启动审阅和基于角色的任务分派
- 面向交付、记忆写入和质量门禁的验证清单
- 通过 `PROJECT_HANDOFF.md` 提供 Agent-facing 项目交接
- 通过 `WORK_TASK_REPORT.md` 提供阶段和最终交付报告；叙述正文可使用用户或项目主要语言，完整翻译镜像仅在明确要求时生成
- 通过 MALTS Memory Pipeline 处理成长复盘和持久候选
- 通过根级 `skills/` 提供唯一 `SKILL.md` 事实源，并安装到各 Agent 目标工具 skill 目录
- `runtime/EN` 与 `runtime/CH` 下的双语运行模板
- Codex、Claude Code、OpenCode 的可选 adapters
- 轻量 lint 和 project-control 生成工具

## 核心能力与可选能力

| 能力 | 默认状态 | 用途 |
|---|---|---|
| Single-agent execution | 开启 | 让小而明确的任务保持低开销。 |
| `PROJECT_CONTROL.md` | 启用 MALTS 或需要恢复时创建 | 保留目标、队列、决策、风险、文件归属和验证状态。 |
| `WORK_TASK_REPORT.md` | MALTS 阶段或最终交付后使用 | 用用户或项目主要语言报告结果、检查、风险和下一步。 |
| `PROJECT_HANDOFF.md` | 继续工作或上下文风险交接时使用 | 提供 Agent-facing recovery context。 |
| Grill-Me Preflight | 非琐碎或不清楚的开始时建议 | 在实现前暴露假设、目标边界、取舍和验收标准。 |
| Multi-agent scheduling | 关闭 | 只有当探索、验证、并行或恢复价值足够时，才加入受控分派。 |
| Memory Pipeline | 可用 | 在经验进入 durable rules 或 memory 前进行过滤。 |
| Bilingual documentation sync | 关闭 | 需要时维护可选中文审阅或公开译本。 |

## 启用与默认产物

MALTS 文件不会为每个任务默认创建。小任务应保持单 Agent，并使用普通项目指令。

当启用 MALTS，或任务扩大到需要可恢复长任务模式时，在项目根目录创建或复用 `PROJECT_CONTROL.md` 作为 canonical 控制文件。每个 MALTS 阶段或最终交付后，应写入或追加 `WORK_TASK_REPORT.md`，叙述正文使用用户或项目主要语言。需要未来 Agent 接手时，使用 `PROJECT_HANDOFF.md`，顶部保留简短 English Agent Brief。`项目控制.md`、`工作任务报告.md`、`项目交接.md` 等完整翻译镜像只在明确要求时生成。

| 文件 | 默认角色 |
|---|---|
| `PROJECT_CONTROL.md` | Canonical 项目状态和任务队列；叙述正文可用用户 / 项目语言 |
| `WORK_TASK_REPORT.md` | Canonical 阶段 / 最终报告和验证证据 |
| `PROJECT_HANDOFF.md` | Canonical 继续和恢复事实源，顶部带简短 English Agent Brief |

## 仓库结构

```text
skills/                  MALTS canonical SKILL.md packages
runtime/EN/templates/    Project control, task, report, and handoff templates
runtime/EN/checklists/   Delivery, quality, and memory-write checks
runtime/CH/templates/    简体中文运行模板镜像
runtime/CH/checklists/   简体中文检查清单镜像
adapters/                Optional Codex, Claude Code, and OpenCode adapter files
tools/                   Lightweight MALTS validation utilities
scripts/                 Safe installation helper scripts
docs/                    Design, install, usage, handoff, security, and maintenance docs
```

## 文档目录

中文公开文档：

| 中文文档 | 对应英文事实源 | 状态 |
|---|---|---|
| [入门指南](docs/zh-CN/GETTING_STARTED.md) | [Getting Started](docs/GETTING_STARTED.md) | 已提供中文公开版 |
| [系统说明](docs/zh-CN/SYSTEM_OVERVIEW.md) | [System Overview](docs/SYSTEM_OVERVIEW.md) | 已提供中文公开版 |
| [安装说明](docs/zh-CN/INSTALL.md) | [Install](docs/INSTALL.md) | 已提供中文公开版 |
| [使用指南](docs/zh-CN/USAGE.md) | [Usage](docs/USAGE.md) | 已提供中文公开版 |
| [交接说明](docs/zh-CN/HANDOFF.md) | [Handoff](docs/HANDOFF.md) | 已提供中文公开版 |
| [核心设计](docs/zh-CN/CORE_DESIGN.md) | [Core Design](docs/CORE_DESIGN.md) | 已提供中文公开版 |
| [Agent 安装协议](docs/zh-CN/AGENT_INSTALL.md) | [Agent Install](docs/AGENT_INSTALL.md) | 已提供中文公开版 |
| [双语文档规则](docs/zh-CN/BILINGUAL_DOCS.md) | [Bilingual Docs](docs/BILINGUAL_DOCS.md) | 已提供中文公开版 |
| [安全与发布卫生](docs/zh-CN/SECURITY.md) | [Security](docs/SECURITY.md) | 已提供中文公开版 |
| [更新流程](docs/zh-CN/UPDATE.md) | [Update](docs/UPDATE.md) | 已提供中文公开版 |
| [维护者指南](docs/zh-CN/MAINTAINER_GUIDE.md) | [Maintainer Guide](docs/MAINTAINER_GUIDE.md) | 已提供中文公开版 |

英文事实源文档：

| 文档 | 用途 | 中文状态 |
|---|---|---|
| [README.md](README.md) | 英文项目入口 | 本页提供中文入口 |
| [GETTING_STARTED.md](docs/GETTING_STARTED.md) | 安装和首次使用路径 | 已有中文公开版 |
| [SYSTEM_OVERVIEW.md](docs/SYSTEM_OVERVIEW.md) | 系统目的、能力、边界和使用场景 | 已有中文公开版 |
| [INSTALL.md](docs/INSTALL.md) | 安装命令参考 | 已有中文公开版 |
| [USAGE.md](docs/USAGE.md) | normal task、long task、multi-agent、growth、handoff 的简明用法 | 已有中文公开版 |
| [HANDOFF.md](docs/HANDOFF.md) | handoff 文件行为和发布边界 | 已有中文公开版 |
| [CORE_DESIGN.md](docs/CORE_DESIGN.md) | 完整系统设计、不变量和协议边界 | 已有中文公开版 |
| [AGENT_INSTALL.md](docs/AGENT_INSTALL.md) | Agent-assisted installation policy | 已有中文公开版 |
| [BILINGUAL_DOCS.md](docs/BILINGUAL_DOCS.md) | 双语文档维护规则 | 已有中文公开版 |
| [SECURITY.md](docs/SECURITY.md) | 发布卫生和 secret-handling rules | 已有中文公开版 |
| [UPDATE.md](docs/UPDATE.md) | 维护更新流程 | 已有中文公开版 |
| [MAINTAINER_GUIDE.md](docs/MAINTAINER_GUIDE.md) | 维护者发布和同步规则 | 已有中文公开版 |

## Acknowledgements

MALTS 包含公开可用的 Agent 行为模式改写，灵感来自：

- [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills)，用于简洁的 coding-agent behavior guardrails。
- [mattpocock/skills](https://github.com/mattpocock/skills)，尤其是 pre-implementation grilling workflow 的想法。

这些项目不是 MALTS 的依赖，也不代表其作者认可本仓库。见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 安装预览

安装流程是 review-first。安装脚本默认 dry-run；只有提供 `-Apply` 才会写文件。

安装器会在写入前展示一份共享 `MALTS_ROOT`、工具薄适配层文件、六个轻量发现 bridge，以及生成的 `MALTS_BOOT.md` 指针。每个 bridge 都把工具原生发现入口路由到共享 `skills/` 实现，不再把完整 MALTS 树复制到每个工具目录。

工具指令模板（例如 `AGENTS.md` 和 `CLAUDE.md`）是可选 MALTS 增强项。默认情况下，安装器只合并 `<!-- MALTS:BEGIN managed instruction -->` 与 `<!-- MALTS:END managed instruction -->` 之间的区块，区块外文本仍归用户所有；边界明确的旧版无标记 MALTS discovery section 会自动迁移。

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex
.\scripts\Install-MALTS.ps1 -Tool Codex -Apply
.\scripts\Install-MALTS.ps1 -Tool ClaudeCode -InstructionMode Skip
.\scripts\Install-MALTS.review.cmd -Tool AllIncluded
```

如果 Windows PowerShell 阻止脚本执行，可使用进程级执行策略覆盖：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool Codex
```

支持工具：

```text
Codex
ClaudeCode
OpenCode
AllIncluded
```

完整安装路径见 [docs/zh-CN/INSTALL.md](docs/zh-CN/INSTALL.md) 和 [docs/zh-CN/AGENT_INSTALL.md](docs/zh-CN/AGENT_INSTALL.md)。

## 更新预览

已安装用户可以从 git clone 更新，不需要每次手动下载新压缩包。更新脚本同样是 review-first：先检查远端分支并打印安装计划；只有提供 `-Apply` 才会拉取或写文件。

```powershell
.\scripts\Update-MALTS.ps1 -Tool Codex
.\scripts\Update-MALTS.ps1 -Tool Codex -Apply
.\scripts\Update-MALTS.ps1 -Tool AllIncluded -Strategy MergeSafe
.\scripts\Update-MALTS.review.cmd -Tool Codex
```

`MergeSafe` 默认使用 `InstructionMode ManagedMerge`：更新 MALTS 管理区块，同时保留区块外的用户规则。需要完全不改指令文件时使用 `InstructionMode Skip`；只有明确要整份替换时，才组合使用 `Strategy Overwrite` 与 `InstructionMode Replace`。

维护者可以用临时目录验证真实安装布局：

```powershell
.\scripts\Test-MALTSInstall.ps1 -Tool AllIncluded
```

## 文档语言

公开仓库默认以英文源文档作为 Agent 执行事实源。简体中文公开文档位于 `docs/zh-CN/`，本地化 runtime 参考位于 `runtime/CH/`。项目运行产物默认是单 canonical 文件；叙述正文可使用用户 / 项目语言，完整翻译镜像仅在明确要求时生成。见 [docs/zh-CN/BILINGUAL_DOCS.md](docs/zh-CN/BILINGUAL_DOCS.md)。

## 版本

当前 release version：

```text
0.1.7
```

## License

MIT License。见 [LICENSE](LICENSE)。
