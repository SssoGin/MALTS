# MALTS

**Multi-Agent Long-Task Scheduling and Growth System**

语言：[English](README.md) | [简体中文](README.zh-CN.md)

MALTS 是面向 AI 编程 Agent 的文件化工作流系统。它把目标、计划、任务归属、验证、交接和经过审阅的经验写入普通项目文件，使长期工作可恢复、可检查，也更容易安全续接。

它适用于迁移、多文件修改、长期排查、发布准备、协议或文档更新，以及任何因遗漏决策或未经验证就宣称完成而会带来风险的工作。

MALTS 坚持单 Agent 优先。主 Agent 是默认执行者；多 Agent 只是可选、必须经过启动审阅的分工机制，而不是安装后自动发生的行为。

## 从这里开始

| 需求 | 阅读 |
|---|---|
| 安装 MALTS 并完成第一个任务 | [快速开始](docs/zh-CN/GETTING_STARTED.md) |
| 了解 MALTS 的作用和适用边界 | [系统概览](docs/zh-CN/SYSTEM_OVERVIEW.md) |
| 审阅完整操作模型和边界 | [核心设计](docs/zh-CN/CORE_DESIGN.md) |
| 安装或更新指定 Agent 工具 | [安装](docs/zh-CN/INSTALL.md) 与 [更新](docs/zh-CN/UPDATE.md) |
| 让 Agent 安全协助安装 | [Agent 安装](docs/zh-CN/AGENT_INSTALL.md) |
| 使用可选离线归档 | [发布产物](docs/zh-CN/RELEASE_ARTIFACT.md) |

## 它解决什么问题

长期 Agent 任务与短提示的失败方式不同：上下文可能被压缩，目标可能漂移，不完整结果可能被误判为完成，不同工作通道可能冲突，而有用经验又可能被丢失或被过度提升。

MALTS 通过外置关键任务状态、定义完成与验证标准、保留可恢复交接、在真实子 Agent 派发前要求启动审阅，并在经验进入长期规则前进行筛选，来控制这些风险。

## 它提供什么

- 通过 `PROJECT_CONTROL.md` 进行长期任务规划与恢复
- 通过 `WORK_TASK_REPORT.md` 保存 Phase 或最终交付证据
- 通过 `PROJECT_HANDOFF.md` 提供 Agent 面向的续接上下文
- 为有边界的长期项目提供显式 Phase 与 Session 控制
- 提供事件触发、只读的 Plan Recheck，以 Phase 绑定 plan revision 与 SHA-256
- 用 Grill-Me Preflight 暴露假设、边界、取舍和验收标准
- 提供可选多 Agent 启动审阅、任务合同和责任边界
- 当原生子 Agent 无法满足已批准的 hard model / effort 契约时，提供受治理的 Codex peer-task 路由
- 提供交付、质量和记忆写入检查清单
- 提供英文与简体中文 runtime 模板
- 为 Codex、Claude Code、OpenCode 提供原生 `malts-*` Skill 桥接
- 提供先审阅、再执行的安装、更新、恢复、回滚与残留处理
- 启动时与已安装运行状态交叉核对，发现不一致时关闭式失败
- 提供稳定版与预览版运行身份、只读 doctor 诊断、有界审计保留与安全旧版迁移
- 识别并迁移已知 MALTS `v0.1.0` 至 `v0.1.9` 布局

## 核心与可选能力

| 能力 | 默认 | 用途 |
|---|---|---|
| 单 Agent 执行 | 开启 | 让小型、清晰的工作保持低开销。 |
| `PROJECT_CONTROL.md` | 非简单或恢复敏感任务使用 | 保存目标、队列、决策、风险和验证状态。 |
| `WORK_TASK_REPORT.md` | MALTS Phase 或最终交付后使用 | 记录结果、证据、剩余风险和下一步。 |
| `PROJECT_HANDOFF.md` | 需要续接或上下文风险交接时使用 | 为后续 Agent 提供可恢复的当前状态。 |
| Grill-Me Preflight | 不清晰或非简单任务时建议 | 在实现前明确假设和验收标准。 |
| 多 Agent 调度 | 关闭 | 仅在有明确价值时增加受控委派。 |
| Plan Recheck | Active S3/S4 plan 按事件运行 | 在门禁动作前发现 plan、scope、Session 与 launch-review 漂移。 |
| 经验审阅 | 可用 | 在经验进入长期规则前进行筛选。 |
| 双语文档 | 可用 | 提供中英文参考，不复制项目状态。 |

## 启用与产物

MALTS 不会为每个短任务都创建永久控制文件。小型工作保持单 Agent，并遵循原有项目说明即可。

当任务需要可恢复的长期工作模式时，在项目根目录创建或复用 `PROJECT_CONTROL.md`。每个 MALTS Phase 或最终交付应写入或更新 `WORK_TASK_REPORT.md`。需要后续 Agent 续接时使用 `PROJECT_HANDOFF.md`。叙述内容可使用项目工作语言；完整翻译镜像仅在明确需要时建立。

| 文件 | 默认角色 |
|---|---|
| `PROJECT_CONTROL.md` | 标准项目状态、任务队列、决策、风险和验证状态。 |
| `WORK_TASK_REPORT.md` | 标准 Phase 或最终报告及直接证据。 |
| `PROJECT_HANDOFF.md` | 标准续接与恢复上下文。 |

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
- [生命周期](docs/zh-CN/LIFECYCLE.md)：运行版本、恢复、回滚、doctor 诊断与清理。
- [使用](docs/zh-CN/USAGE.md)：普通任务、长期任务、多 Agent、经验与交接。
- [系统概览](docs/zh-CN/SYSTEM_OVERVIEW.md)：目标、能力与边界的公开说明。
- [核心设计](docs/zh-CN/CORE_DESIGN.md)：详细操作模型与不变量。
- [Agent 安装](docs/zh-CN/AGENT_INSTALL.md)：Agent 的授权和来源选择规则。
- [发布产物](docs/zh-CN/RELEASE_ARTIFACT.md)：可选单 ZIP 离线交付。
- [安全](docs/zh-CN/SECURITY.md)：来源、包验证和隐私边界。
- [双语文档](docs/zh-CN/BILINGUAL_DOCS.md)：语言与导航策略。

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

支持的工具：

```text
Codex
ClaudeCode
OpenCode
AllIncluded
```

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

仓库默认以英文为技术参考。简体中文文档位于 `README.zh-CN.md` 与 `docs/zh-CN/`，本地化 runtime 参考位于 `runtime/CH/`。项目 runtime 产物默认保持单一标准文件。见[双语文档](docs/zh-CN/BILINGUAL_DOCS.md)。

## 版本

当前发布版本：

```text
1.1.0
```

## License

MALTS 采用 [MIT License](LICENSE) 发布。
