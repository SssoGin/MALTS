# MALTS

**Multi-Agent Long-Task Scheduling and Growth System · 多 Agent 长任务调度与成长系统**

[English](README.md) · [简体中文](README.zh-CN.md) · [快速开始](docs/zh-CN/GETTING_STARTED.md) · [使用指南](docs/zh-CN/USAGE.md)

MALTS 是一套用于 AI Agent 项目工作的运行框架，将目标澄清、任务规划、执行、验证、交接和经验积累组织为连续的工作过程。它适用于无法在一次提示、一个对话窗口或一次不中断运行中完成的工作，让 Agent 在切换窗口、更换执行者或遇到失败后，仍能依据项目记录继续推进。

MALTS 默认由一个 Agent 完成工作。需要独立调查、验证或分开实施时，可以在明确分工和授权后使用多个 Agent；负责项目的主 Agent 仍承担整合、验收和最终交付责任。无论使用一个还是多个 Agent，都沿用同一套目标、阶段、验证和恢复方法。

当前版本为 **2.0.3**。本页介绍完整的 MALTS 系统；本版本的新增、改进和升级影响见[版本说明](CHANGELOG.md)。

## 它解决什么问题

AI Agent 可以完成许多局部工作，但长期项目往往需要更多连续性：用户的目标不能在长对话中被悄悄改写，已完成与待完成的部分不能混淆，失败后不能重复执行已经发生的操作，多个执行者的成果也必须能够合并并验证。

| 工作中的问题 | MALTS 的处理方式 |
|---|---|
| 对话变长后，原目标与限制逐渐模糊 | 保存目标、排除项、关键决定和验收条件，在重要变化时重新核对 |
| 换窗口或中断后，不知道应该从哪里继续 | 保存阶段进度、任务结果、检查点和必要的恢复资料 |
| 文件生成了，却没有证明用户要求已满足 | 把完成条件写清楚，检查实际结果并保留验证依据 |
| 多个 Agent 重复调查、修改冲突或无人整合 | 先分清职责、修改范围和依赖，由主 Agent 统一整合与验收 |
| 经验丢失，或一次偶然成功被写成长期规则 | 从实际结果中筛选经验，在后续工作中试用，保留无效或有害结果 |
| 不同 Agent 工具的配置和入口不一致 | 提供共同工作流与工具适配，保留各工具自身的权限和运行方式 |

## MALTS 提供的完整工作过程

### 1. 明确目标与完成条件

开始工作时，确定要交付什么、允许修改什么、哪些内容应保留，以及如何判断完成。对于重要的不确定选择，先澄清再实施；已明确授权的日常工作持续推进，不为常规细节反复确认。

### 2. 组织项目、阶段与任务

长期项目按阶段组织，每个阶段有自己的目标、范围和交付物。具体工作拆成可以执行和验收的任务，保留任务之间的依赖。这样，整体目标与当前正在做的工作能同时保持清楚，也能给一轮迭代设置明确结束条件。

### 3. 执行并保留可继续的进度

Agent 从当前任务及相关资料开始，不需要每次重新阅读全部历史。执行中记录决定、结果与必要检查点。遇到失败或中断时，先确认哪些操作已经发生、哪些结果仍不确定，再决定修复或继续，避免重复执行。

### 4. 按需要使用多个 Agent

主 Agent 可以将可分离的调查、实施或验证工作交给其他 Agent。分工应说明每位执行者的目标、输入、修改范围、返回结果和验证责任，并考虑调用预算、共享资源与整合成本。没有合适分工时，继续单 Agent 工作。

### 5. 验证、交付与交接

完成声明依据实际产物和适用检查。项目需要持久报告时，生成与证据对应的报告；需要换窗口或执行者时，生成按需派生的交接说明，保留用户手工内容、未解决事项与准确下一步。报告和交接帮助阅读，不替代当前项目事实。

### 6. 筛选和验证可复用经验

纠正、验证失败、恢复或有价值的方法可以成为复盘信号。轻量审阅先判断是否值得记录；重要或反复出现的问题可以深入复盘。经验先成为有适用范围的候选，经过后续任务试用再判断是否有用；无效、有害或已失去依据的经验可以停止使用。普通成功回合无需生成成长报告。

## 按你的需要选择工作流

工作流以 Skill 提供。Skill 是 Agent 可以发现和使用的工作方法包；你可以直接在对话中说出要使用的工作流和目标。

| 你的需求 | 工作流 | 得到的结果 |
|---|---|---|
| 给一个需要多轮完成的项目建立基本记录 | [项目初始化](skills/malts-project-init/SKILL.md) · `malts-project-init` | 项目入口、目标、验收条件和当前状态 |
| 实施前有重要目标、取舍或边界没有确定 | [目标澄清](skills/grill-me-preflight/SKILL.md) · `malts-grill-me-preflight` | 有依据的澄清结论和待决定事项 |
| 建立长期项目，或审阅真实阶段/结构变化 | [长期工作区](skills/malts-long-project-workspace-init/SKILL.md) · `malts-long-project-workspace-init` | 有明确阶段、任务与恢复入口的工作区 |
| 继续、验证或恢复当前任务 | [任务工作流](skills/v2/malts-v2-task-workflow/SKILL.md) · `malts-v2-task-workflow` | 当前任务与对应操作方法，避免依赖过期摘要 |
| 需要另一个窗口或 Agent 准确接续 | [会话交接](skills/session-handoff/SKILL.md) · `malts-session-handoff` | 保留必要事实和手工内容的续接说明 |
| 完成阶段、出现返工或需要整理重要经验 | [项目复盘](skills/project-retrospective-growth/SKILL.md) · `malts-project-retrospective-growth` | 有来源的经验建议或已授权的试用安排 |
| 普通任务后判断是否有值得记录的经验 | [轻量成长](skills/single-agent-lightweight-growth/SKILL.md) · `malts-single-agent-lightweight-growth` | 简短建议，或没有信号时不产生输出 |
| 已决定使用多个 Agent 完成复杂工作 | [多 Agent 调度](skills/multi-agent-long-task-scheduling/SKILL.md) · `malts-multi-agent-long-task-scheduling` | 明确分工、资源、预算、检查点和整合责任 |

## 核心与可选能力的默认方式

| 能力 | 默认方式 | 何时使用 |
|---|---|---|
| 单 Agent 工作 | 默认执行路径 | 普通项目工作与依赖较强的任务 |
| 项目和长期工作记录 | 按项目需要启用 | 工作跨多轮、阶段或窗口，需要保留目标与进度 |
| 多 Agent 调度 | 明确授权后启用 | 职责、资源和结果可以分离，分工确有价值 |
| 报告与交接 | 按需生成 | 用户需要持久报告，或其他窗口/执行者需要继续 |
| 轻量成长与复盘 | 有实际信号或明确请求时使用 | 纠正、验证失败、恢复或值得检验的方法 |
| 后台与无人值守工作 | 需要对应明确范围 | 任务已说明持续运行方式和停止条件 |

## 典型使用场景

**多轮代码迁移。** 保存目标和兼容性要求，按模块安排阶段与任务；每个模块完成后检查行为，遇到中断时从已验证的结果继续。

**持续排查问题。** 保存已核实事实、被排除的假设和下一步实验，避免换窗口后重复调查；以复现和验证结果判断修复是否有效。

**多人或多 Agent 分工。** 分开处理独立模块、备选方案或验证工作，保护共享修改范围；主 Agent 汇总结果、处理依赖并完成最终验收。

**长期文档与研究交付。** 保留资料来源、关键决定、章节分工和交付标准；成果完成后检查事实、链接与整份内容的一致性。

**需要恢复与交接的工程工作。** 保留准确项目状态和必要备份，说明发生了什么、当前有哪些不确定项、下一个执行者可以继续哪些工作。

## 四端共享正式安装

Codex、Claude Code、OpenCode 和 DeepSeek Harness 共用一套 MALTS 正式安装，默认运行根为 `~/.agent-system/lifecycle`。四端使用同一版本和准确内容身份，由一个安装计划统一更新、诊断和恢复。

各宿主仍保留自己的工具配置根：`~/.codex`、`~/.claude`、`~/.config/opencode` 和 `~/.dsh`。账号、模型设置、会话与原生工具由各宿主管理；共享安装不合并这些资料，也不自动改变项目状态。`AllIncluded` 选择四端，工具根另有位置时提供其实际路径。

## 开始使用

MALTS 的已验证安装路径为 Windows，要求 Python 3.11 或更高版本；推荐 PowerShell 7。支持的 Agent 工具包括 Codex、Claude Code、OpenCode 和 DeepSeek Harness，工具自身应已安装并能够正常使用。

从[公开仓库](https://github.com/SssoGin/MALTS)取得准备使用的版本，在仓库根目录先生成安装计划：

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool AllIncluded
```

安装计划会说明来源、写入位置、已有内容处理及恢复方式。审阅后，按[安装说明](docs/zh-CN/INSTALL.md)使用输出的准确计划哈希执行；四端使用同一安装入口，`AllIncluded` 选择全部四端。更新已有共享安装见[升级指南](docs/zh-CN/UPDATE.md)。

安装并确认工具已加载 MALTS 后，可以用自然语言开始：

> 使用 MALTS 管理这次模块迁移。先核对项目现状，明确修改范围和验收条件，分阶段实施并验证；遇到中断时保留可继续的进度。提交与发布另行决定。

或继续一个已有项目：

> 继续这个 MALTS 项目的当前任务。先核对现有进度、已验证结果和未解决事项，再从准确的下一步继续，不重复初始化。

需要可执行的首次任务示例、安装核查和详细步骤，阅读[快速开始](docs/zh-CN/GETTING_STARTED.md)。

## 更新已有安装

从准备使用的仓库版本生成更新计划：

```powershell
.\scripts\Update-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool AllIncluded
```

审阅计划后，使用输出的准确路径与哈希执行：

```powershell
.\scripts\Update-MALTS.ps1 -Apply -PlanPath '<reviewed-plan-path>' -ExpectedPlanHash '<reviewed-plan-sha256>'
```

更新所选工具和处理已有用户内容的完整说明见[升级指南](docs/zh-CN/UPDATE.md)；安装更新不会自动迁移项目。

## 当前版本怎样完善这套系统

2.0.0 保留 MALTS 的整体工作过程，同时改进长期工作的状态管理、执行保护与结果验证：

- **更明确的当前进度。** 项目、阶段和任务由统一的服务保存和检查，任务与计划有版本关系，阅读报告与实际状态分开。
- **更可靠的中断处理。** 区分操作准备、实际执行和已观察结果；不确定的操作先核实，恢复不重复执行或重置已经消耗的预算。
- **更严格的完成判定。** 验收同时检查任务要求、结果、依赖和证据，历史“完成”标记不能替代当前核查。
- **更清楚的分工与成果复用。** 协作使用明确的任务、资源范围和预算；成果、交接及经验保留来源和当前适用条件。
- **更完整的工具适配与说明。** 加入 DeepSeek Harness 适配，整理中英文安装、使用、设计和升级文档。

使用者可以沿用原来“明确目标—执行—验证—恢复—复盘”的方法。升级涉及的项目采用、兼容和恢复要求在[升级指南](docs/zh-CN/UPDATE.md)中说明。

## 支持范围与使用边界

MALTS 组织 Agent 的项目工作；模型推理、具体工具能力、代码仓库、编辑器和用户决策仍由各自系统提供。选择工作流不自动启用多 Agent、后台运行、付费调用或公开发布。

当前已有代码、安装与代表性原生任务/恢复验证，但不保证任意任务都成功，也不承诺普遍提速或费用节省。DeepSeek Harness 的已记录 Desktop 验证使用 Windows 0.2.0-rc.2，具体能力和限制见[适配说明](adapters/deepseek-harness/README.zh-CN.md)。跨用户恢复及外部工具控制等详细边界见[安全说明](docs/zh-CN/SECURITY.md)。

## 工作区与主要产物

| 记录或产物 | 用途 |
|---|---|
| 项目、阶段与任务记录 | 保存目标、范围、计划、依赖、当前进度和验收 |
| 业务交付物 | 用户实际需要的代码、文档、数据或工具结果 |
| 验证与恢复资料 | 支持完成判定，保留检查结果、检查点和必要备份 |
| 工作报告与交接说明 | 按需说明结果、未解决事项和下一步，保全手工内容 |
| 有来源的经验候选与试用结果 | 判断方法是否适用、是否有效以及何时停止复用 |

这些内容由对应工作流维护。当前工作区状态与阅读报告分别管理，业务文件和用户资料保留在其实际项目中；详细操作见[使用指南](docs/zh-CN/USAGE.md)。

## 文档导航

| 想了解什么 | 文档 |
|---|---|
| MALTS 的整体功能、工作方式与适用性 | [系统说明](docs/zh-CN/SYSTEM_OVERVIEW.md) |
| 安装并完成第一个任务 | [快速开始](docs/zh-CN/GETTING_STARTED.md)、[安装](docs/zh-CN/INSTALL.md) |
| 日常执行、长期项目、协作和复盘 | [使用指南](docs/zh-CN/USAGE.md) |
| 中断、交接、升级与恢复 | [交接](docs/zh-CN/HANDOFF.md)、[升级](docs/zh-CN/UPDATE.md)、[生命周期](docs/zh-CN/LIFECYCLE.md) |
| 为什么这样设计、机制与取舍 | [核心设计](docs/zh-CN/CORE_DESIGN.md) |
| Skill、工具能力与经验复用如何管理 | [能力与 Skill 治理](docs/zh-CN/CAPABILITY_AND_SKILL_GOVERNANCE.md) |
| 控制端命令和准确协议 | [操作参考](docs/zh-CN/V2_PREVIEW_USAGE.md)、[状态合同](docs/zh-CN/V2_STATE_CONTRACT.md) |
| 安全、离线包和文档语言 | [安全](docs/zh-CN/SECURITY.md)、[发布归档](docs/zh-CN/RELEASE_ARTIFACT.md)、[双语文档](docs/zh-CN/BILINGUAL_DOCS.md) |
| 让 Agent 协助安装与核查 | [Agent 安装](docs/zh-CN/AGENT_INSTALL.md) |
| 当前及历史版本的变化 | [CHANGELOG](CHANGELOG.md) |

## 仓库组成

```text
skills/       项目、长任务、协作、交接与成长工作流
runtime/      运行合同、中英文模板和检查清单
adapters/     Agent 工具适配与原生入口
tools/        状态管理、执行、验证与恢复工具
scripts/      安装、升级与安装生命周期入口
docs/         系统说明、使用指南、设计与技术参考
```

MALTS 提供经审阅的旧工作区采用和长项目就绪查询。普通新工作区默认在项目内保存管理数据，已有外置库可经审阅流程重定位；四端沿用同一套核心和任务状态。参见[工作区管理与迁移](docs/zh-CN/MANAGEMENT_AND_RELOCATION.md)。

## 版本

当前发布版本：**2.0.3**。版本说明与可选离线包见[MALTS 2.0.3 Release](https://github.com/SssoGin/MALTS/releases/tag/v2.0.3)，历史变化见[CHANGELOG](CHANGELOG.md)。

## 文档语言

提供英文与简体中文指南；项目记录和用户手工内容保持原语言，不建立两套状态。语言与文档对应关系见[双语文档](docs/zh-CN/BILINGUAL_DOCS.md)。

## 致谢

部分 Agent 工作方法参考了 [andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) 与 [mattpocock/skills](https://github.com/mattpocock/skills)；它们不是运行依赖，作者也不代表认可本项目。完整声明见[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## License

MALTS 采用 [MIT License](LICENSE)。
