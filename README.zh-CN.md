# MALTS

**Multi-Agent Long-Task Scheduling and Growth System**

语言：[English](README.md) | [简体中文](README.zh-CN.md)

MALTS 是面向 AI 辅助项目工作的文件化操作模型，适合需要持续性、明确决策或受控委派的场景。它把工作目标、已验证状态、职责归属、验收证据和恢复上下文保存在普通项目文件中，使工作能够跨 Session、Phase 与 Agent 安全续接。

MALTS 是对项目既有说明的补充，而不是替代。结果明确、范围有限的任务应保持轻量；当中断、范围变化、验证、交接或协同会使关键工作状态变得隐含时，才适合使用 MALTS。

## 开始使用与文档导航

请根据当前需要解决的问题，从相应文档开始阅读。

| 目标 | 建议入口 |
|---|---|
| 判断 MALTS 是否适合当前项目 | [系统概览](docs/zh-CN/SYSTEM_OVERVIEW.md) |
| 安装 MALTS 并完成第一个任务 | [快速开始](docs/zh-CN/GETTING_STARTED.md) |
| 使用已初始化工作区或选择工作流 | [使用指南](docs/zh-CN/USAGE.md) |
| 审阅工作区恢复、重整或生命周期操作 | [生命周期](docs/zh-CN/LIFECYCLE.md) |
| 了解并行、委派与安全不变量 | [核心设计](docs/zh-CN/CORE_DESIGN.md) |
| 安装或更新支持的 Agent 工具 | [安装](docs/zh-CN/INSTALL.md) 与 [更新](docs/zh-CN/UPDATE.md) |

## 它解决什么问题

长期 Agent 任务与短提示的失败方式不同：上下文可能被压缩，目标可能漂移，不完整工作可能被误判为完成，并行工作可能发生冲突，而有用经验又可能被丢失或被过度提升。

MALTS 将需要跨这些风险保存的任务状态外置。它区分规范控制与派生报告，在宣称完成前要求证据，保存可恢复的续接路径，并在真实委派开始前要求启动审阅。

## MALTS 核心工作流

MALTS 提供 7 个核心工作流。每份指南均说明其用途、适用条件、操作步骤和验证要求。

| 适用场景 | 对应 MALTS 工作流 | 启动条件 | 主要结果 |
|---|---|---|---|
| 建立普通项目控制 | [MALTS Project Init](skills/malts-project-init/SKILL.md)（`malts-project-init`） | 项目需要轻量、可持续的控制。 | 一次性建立初始 Project 级控制。 |
| 在实现前澄清非简单任务 | [MALTS Grill-Me Preflight](skills/grill-me-preflight/SKILL.md)（`malts-grill-me-preflight`） | 假设、边界、取舍或验收条件需要澄清。 | 只读的澄清结论；不修改文件，也不派发 Agent。 |
| 初始化、恢复或结构化整理长工作区 | [MALTS Long Project Workspace Init](skills/malts-long-project-workspace-init/SKILL.md)（`malts-long-project-workspace-init`） | 正在建立 Phase 化长期项目、进行结构修复或明确重整。 | 受治理的长工作区结构与恢复路径。 |
| 输出有界续接记录 | [MALTS Session Handoff](skills/session-handoff/SKILL.md)（`malts-session-handoff`） | 后续 Agent 或 Session 需要经过验证的当前上下文。 | 按需生成 `PROJECT_HANDOFF.md`；它不与规范权威竞争。 |
| 复盘已验证的项目经验 | [MALTS Project Retrospective Growth](skills/project-retrospective-growth/SKILL.md)（`malts-project-retrospective-growth`） | 已完成、失败或返工的工作包含值得审阅的证据。 | 基于证据的成长候选；写入长期规则仍需单独授权。 |
| 执行默认的任务后轻量成长检查 | [MALTS Single-Agent Lightweight Growth](skills/single-agent-lightweight-growth/SKILL.md)（`malts-single-agent-lightweight-growth`） | 已验证任务完成，适合执行无写入检查。 | 低成本建议或无操作；不会自行创建长期规则。 |
| 协调已准入的委派工作 | [MALTS Multi-Agent Long-Task Scheduling](skills/multi-agent-long-task-scheduling/SKILL.md)（`malts-multi-agent-long-task-scheduling`） | 可以明确工作通道、资源、验证职责和用户授权。 | 具有成本感知模型路由的启动审阅与受治理委派路径。 |

## 操作模型

MALTS 坚持单 Agent 优先。主 Agent 是通常的执行者；多 Agent 只是可选、经过审阅的职责分工，而不是安装后自动发生的行为。

长工作区初始化只用于首次建立、结构修复、显式重整或重大生命周期变化。已初始化且状态未变化的工作区会执行一次有界、只读的普通工作区检查（其实现路径为 `workspace-entry`）；它不创建 Phase、Session、Agent、Artifact、协调服务或报告更新，也不加载完整历史。

全新长工作区使用 CURRENT 工作区规范，默认 profile 是 `single_phase`。项目只有在能声明资源和能力时，才可以显式启用 `resource_admission`。该路径通过 typed resource locator、capability policy、可过期 lease、fencing epoch、queue 和对不确定外部副作用的域级对账来治理不相交工作。MALTS Core 不包含 Unity、Unreal、VCS、数据库、CI 或设备专项冲突规则；具体资源和能力由 adapter 声明。

Project、Phase 和显式 Session control 各自只拥有本层事实。机器强制执行的 contract、profile、index 与 coordination state 由 runtime contract 拥有。CURRENT 中，`WORK_TASK_REPORT.md` 和已存在的 `PROJECT_HANDOFF.md` 是按需派生视图，不是日常写入门禁或第二事实源。受支持的旧布局保持可读兼容，绝不静默重整。

## 核心与可选能力

| 能力 | 默认 | 用途 |
|---|---|---|
| 单 Agent 执行 | 开启 | 让小型、清晰的工作保持低开销。 |
| `PROJECT_CONTROL.md` | 非简单或恢复敏感任务使用 | 保存 Project 事实、全局验收、跨 Phase 决策和已验证恢复上下文。 |
| Phase 与显式 Session control | 长工作区中可用 | 将局部范围、队列、检查点和证据留在对应 owner。 |
| `WORK_TASK_REPORT.md` | 按需 | 提供带证据的派生报告；从不授予执行权限。 |
| `PROJECT_HANDOFF.md` | 按需 | 提供有界续接视图；不与恢复权威竞争。 |
| Grill-Me Preflight | 不清晰或非简单任务时建议 | 在实现前明确假设和验收标准。 |
| 多 Agent 调度 | 关闭 | 仅在有明确价值时增加受控委派。 |
| 资源准入 | 关闭 | 治理符合条件的并行写入、共享能力、陈旧执行者和不确定副作用。 |
| Plan Recheck | Active plan 按事件运行 | 在门禁动作前发现 plan、scope、Session 与 launch-review 漂移。 |
| 经验审阅 | 可用 | 在经验进入长期规则前进行筛选。 |
| 双语文档 | 可用 | 提供中英文参考，不复制项目状态。 |

## 控制文件与派生视图

MALTS 不会为每个短任务都创建永久控制文件。范围有限的工作保持单 Agent，并遵循原有项目说明即可。

当任务需要可恢复的长期工作模式时，在项目根目录创建或复用 `PROJECT_CONTROL.md`。只有用户要求持久报告，或确有重要交付或恢复需要时，才刷新 `WORK_TASK_REPORT.md`；只有后续 Agent 需要有界续接视图时，才创建 `PROJECT_HANDOFF.md`。叙述内容可使用项目工作语言；完整翻译镜像仅在明确需要时建立。

| 文件 | 默认角色 |
|---|---|
| `PROJECT_CONTROL.md` | Project 事实、全局验收、跨 Phase 决策和紧凑 owner 索引的规范权威。 |
| `PHASE_CONTROL.md` | Phase 目标、边界、局部队列、交付物、证据和收口的规范权威。 |
| `SESSION_CONTROL.md` | 一次明确有界工作 Session 的规范检查点。 |
| `WORK_TASK_REPORT.md` | 按需派生的直接证据报告；不授权写入，也不是生命周期权威。 |
| `PROJECT_HANDOFF.md` | 按需派生的续接视图；不与恢复权威竞争。 |

## 仓库结构

```text
skills/                 MALTS 标准 Skill 包
runtime/EN/             英文模板和检查清单
runtime/CH/             简体中文模板和检查清单
adapters/               Codex、Claude Code、OpenCode adapter 内容
scripts/                用户安装、更新、生命周期和 ZIP 验证入口
tools/                  runtime 控制器、Schema 和用户操作工具
docs/                   用户指南、设计参考和安全说明
VERSION                 当前包版本
LICENSE                 MIT 许可证
THIRD_PARTY_NOTICES.md  必需的致谢说明
```

## 文档地图

- [快速开始](docs/zh-CN/GETTING_STARTED.md)：安装与首次使用路径。
- [安装](docs/zh-CN/INSTALL.md)：安装命令与根目录选择。
- [更新](docs/zh-CN/UPDATE.md)：先审阅再替换已有安装。
- [生命周期](docs/zh-CN/LIFECYCLE.md)：运行版本、恢复、重整、doctor 诊断与清理。
- [使用指南](docs/zh-CN/USAGE.md)：普通任务、长工作区、多 Agent、经验与交接。
- [系统概览](docs/zh-CN/SYSTEM_OVERVIEW.md)：目标、能力与边界的公开说明。
- [核心设计](docs/zh-CN/CORE_DESIGN.md)：详细操作模型与不变量。
- [Agent 安装](docs/zh-CN/AGENT_INSTALL.md)：Agent 的授权和来源选择规则。
- [发布产物](docs/zh-CN/RELEASE_ARTIFACT.md)：可选单 ZIP 离线交付。
- [安全](docs/zh-CN/SECURITY.md)：来源、包验证和隐私边界。
- [双语文档](docs/zh-CN/BILINGUAL_DOCS.md)：中英文文档的覆盖范围与对应关系。
- [变更日志](CHANGELOG.md)：版本历史与发布说明。

## 致谢

MALTS 包含面向公开使用的 Agent 行为模式改写，灵感来自：

- [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills)，用于简洁的编程 Agent 行为约束。
- [mattpocock/skills](https://github.com/mattpocock/skills)，尤其是实现前追问工作流的思想。

这些项目不是 MALTS 的运行依赖，其作者也不代表认可本仓库。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 安装预览

安装先审阅。安装器先写入计划，只有你审阅计划并使用匹配的精确哈希加上 `-Apply` 后才会改变文件。

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex
.\scripts\Install-MALTS.ps1 -Tool Codex -Apply
.\scripts\Install-MALTS.ps1 -Tool AllIncluded -InstructionMode Skip
.\scripts\Install-MALTS.review.cmd -Tool AllIncluded
```

支持的工具：`Codex`、`ClaudeCode`、`OpenCode` 和 `AllIncluded`。

如果 Windows PowerShell 阻止脚本执行，请使用进程级执行策略覆盖运行同一命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool Codex
```

完整步骤见[安装](docs/zh-CN/INSTALL.md)与[Agent 安装](docs/zh-CN/AGENT_INSTALL.md)。

## 更新预览

已安装用户可以从当前仓库 checkout 更新，无需手动下载新归档。更新脚本同样先审阅：它打印计划，只有提供 `-Apply` 后才会拉取或写入文件。

```powershell
.\scripts\Update-MALTS.ps1 -Tool Codex
.\scripts\Update-MALTS.ps1 -Tool Codex -Apply
.\scripts\Update-MALTS.ps1 -Tool AllIncluded -Strategy MergeSafe
.\scripts\Update-MALTS.review.cmd -Tool Codex
```

`MergeSafe` 默认使用 `InstructionMode ManagedMerge`：更新 MALTS 管理指令块，同时保留周围用户规则。使用 `InstructionMode Skip` 可完全不修改指令文件。

## 文档语言

MALTS 提供英文与简体中文文档。各语言版本的覆盖范围与对应关系见[双语文档](docs/zh-CN/BILINGUAL_DOCS.md)。

## 版本

当前发布版本：

```text
1.5.0
```

## License

MALTS 采用 [MIT License](LICENSE) 发布。
