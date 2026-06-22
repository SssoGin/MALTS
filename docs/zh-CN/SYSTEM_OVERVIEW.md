# MALTS 系统说明

语言：[English](../SYSTEM_OVERVIEW.md) | [简体中文](SYSTEM_OVERVIEW.md)

本文说明 MALTS 的目的、功能、可选能力和运行边界。它是公开系统说明，不是实现参考。详细设计不变量记录在 [核心设计](CORE_DESIGN.md)。

## 1. 系统目的

MALTS 是面向由 AI agents 执行或辅助的长期编码任务的可移植 workflow system。它的目的，是让 Agent 工作在有界执行轮次之间保持可恢复、可验证、可交接。

系统针对的操作问题是：coding Agents 可以完成有价值的工作，但较长任务容易丢失目标上下文、跳过证据、混入无关修改，或在窗口切换、中断、上下文压缩后难以恢复。MALTS 将这类工作从短暂对话转换为 file-backed operating loop。

## 2. 解决的问题

| 问题类型 | 观察到的风险 | MALTS 响应 |
|---|---|---|
| Goal drift | 长对话中任务被隐式改写。 | 保留原始目标、当前理解、排除项、完成定义和验收标准。 |
| State loss | 不能只靠 chat memory 恢复。 | 将任务状态、决策、验证和恢复记录外部化到文件。 |
| Weak verification | 没有证据就声称完成。 | 使用 checklist，并在交付前记录验证证据。 |
| Coordination risk | 多 Agent 或多工作流带来合并和责任缺口。 | 使用适配评估、launch review、scoped contracts、dispatch records 和最终核对。 |
| Uncontrolled memory growth | 每个纠正都变成永久规则。 | 通过 memory-write process 过滤可复用经验后再持久化。 |
| Tool fragmentation | 不同 Agent 工具使用不同指令格式。 | 围绕同一核心模型提供 Codex、Claude Code 和 OpenCode adapters。 |

## 3. 核心运行模型

MALTS 连接三个 loop：

```text
Delivery loop:
goal -> acceptance criteria -> task queue -> execution -> verification -> delivery

Scheduling loop:
state -> bounded round -> optional delegation -> report -> recovery -> next round

Growth loop:
observation -> cause analysis -> reusable lesson -> filtered candidate -> future use
```

delivery loop 保持工作与用户目标一致。scheduling loop 让长期任务可恢复。growth loop 保留可复用知识，同时避免偶然观察自动变成规则。

## 4. 必需核心能力

以下能力构成系统核心。

### 可恢复项目控制

启用 MALTS 时，`PROJECT_CONTROL.md` 是主要状态文件。它记录：

- original user goal
- current interpreted goal
- acceptance criteria
- task queue
- file ownership
- decisions
- risks and blockers
- verification records
- recovery notes

该文件面向下一个 Agent、新窗口，或上下文丢失后的同一 Agent。

### 阶段和最终报告

`WORK_TASK_REPORT.md` 记录阶段或最终交付信息。它应包含结果、改动文件、验证证据、已知风险和下一步。它通常面向用户，并可使用用户或项目语言。

### 交接与继续

`PROJECT_HANDOFF.md` 是默认 Agent-facing continuation file。它应包含足够当前上下文，使另一个 Agent 或未来窗口无需依赖隐藏 chat state 即可继续。

### 验证清单

runtime checklists 定义交付和质量检查。它们本身不证明工作正确；它们提供可重复的检查结构和证据记录结构。

### Skills、Templates 和 Checklists

根级 `skills/` 是 MALTS `SKILL.md` workflow 的唯一实现事实源，包含 Grill-Me Preflight、multi-agent scheduling、session handoff、retrospective growth、lightweight single-agent growth 和 project initialization。安装脚本只会在各工具的原生 skill 目录放置轻量发现 bridge；bridge 解析 `MALTS_BOOT.md` 后委托共享实现执行。

`runtime/EN/templates` 和 `runtime/EN/checklists` 定义 task contracts、reports、handoff files、project control files 和 verification gates 的预期结构。它们补充根级 skill packages，但不改变公开 skill 来源。

## 5. 可选能力

MALTS 有意保持 single-agent first。可选能力只在任务需要时启用。

| 能力 | 默认状态 | 使用场景 | 边界 |
|---|---|---|---|
| Grill-Me Preflight | 非琐碎或不清楚的开始时建议 | 需求、成功标准、范围或取舍不清楚 | 只用于澄清；不是子 Agent 分派 |
| Multi-agent scheduling | 关闭 | 独立探索、验证或并行工作能降低风险或成本 | 需要 launch review 和明确 `确认运行` |
| Bilingual documentation sync | 关闭 | 项目需要中文公开入口或审阅镜像 | 英文 release docs 仍是默认 runtime source |
| Memory Pipeline | 可用 | 经验可复用到当前任务之外 | 需要过滤和目标选择 |
| Adapter instruction templates | 可选 | 受支持 Agent 工具需要记住 MALTS 行为 | 默认受管区块合并会保留区块外用户文本 |
| Git-based recovery | 可选 | source control 可提升回滚或审阅安全性 | MALTS 不要求 Git |

## 6. 支持的工具 Adapters

MALTS 将核心 workflow 与工具特定安装细节分离。

| Adapter | 主指令文件 | 说明 |
|---|---|---|
| Codex | `AGENTS.md` | 提供 Codex-facing operating rules 和 MALTS reminders。 |
| Claude Code | `CLAUDE.md` | 添加可选 Claude Code agents 和 commands；通过共享 `MALTS_ROOT` 解析 MALTS。 |
| OpenCode | `AGENTS.md` | 添加 OpenCode-specific configuration 和可选 agent scaffold；通过共享 `MALTS_ROOT` 解析 MALTS。 |

除非变更只适用于某个 runtime，否则 adapter documents 应保持同步。工具差异属于 adapter layer，不应改变 MALTS 核心模型。

每个指令模板都显式标记 MALTS 所拥有的区块。更新时只替换该区块；不存在时追加；存在一段可明确识别的旧 discovery section 时迁移。`Skip` 保持文件完全不变；整份 `Replace` 必须显式选择。

## 7. 典型使用场景

MALTS 适合具有以下一个或多个属性的任务：

- 任务可能超过一个舒适上下文窗口
- 任务有多个阶段
- 任务修改多个文件或模块
- 后续 Agent 可能需要接手
- 验证证据很重要
- 需求不清楚，值得先做 preflight clarification
- 独立审阅或探索能降低风险
- 纠正中产生值得过滤的可复用经验

示例包括 migrations、带验收标准的 feature implementations、documentation protocol changes、multi-tool adapter updates、release preparation、long bug investigations 和 recovery-sensitive refactors。

## 8. 非目标和边界

MALTS 不做以下事情：

- 运行强制 scheduling service
- 替代 Agent runtime
- 替代 source control、CI、package managers、editors 或 permission systems
- 自动分派子 Agent
- 把每个任务都变成长任务
- 在没有验证时保证正确性
- 认证没有证据的工作
- 存储 secrets、tokens、sensitive memory dumps 或 raw session logs
- 覆盖用户对高风险操作的审批

这些边界是系统设计的一部分。它们使 MALTS 保持可移植，并减少职责意外扩张。

## 9. 启用模式

| 模式 | 使用时机 | 必需文件 | 结果 |
|---|---|---|---|
| Normal single-agent work | 小而明确、低风险任务 | 默认不需要 | 低开销、直接完成、相关验证 |
| MALTS single-agent mode | 工作需要可恢复状态或阶段报告 | `PROJECT_CONTROL.md`；通常还会使用 `WORK_TASK_REPORT.md` 和 `PROJECT_HANDOFF.md` | Main Controller 执行，但状态持久化 |
| MALTS multi-agent mode | delegation 有明确操作价值 | MALTS 状态文件、任务契约和子 Agent 报告 | 带记录责任边界的受控分派 |

默认模式是 normal single-agent work。只有当任务非琐碎、用户启用 MALTS，或工作扩大到需要可恢复状态时，才创建 MALTS 状态文件。

## 10. 公开发布内容

公开发布仓库包含：

- runtime skills
- templates
- checklists
- adapter examples
- installer script
- lightweight linting tools
- design、installation、usage、handoff、security 和 maintenance documentation
- Simplified Chinese public entry documents under `docs/zh-CN/`

发布仓库不应包含 handoff outputs、project-specific control files、user-specific archives、raw sessions、caches、credentials 或 generated migration packages。

## 11. 与详细设计的关系

本文说明 MALTS 做什么，以及用户如何评估它。[核心设计](CORE_DESIGN.md) 提供详细 design baseline、operating commitments、task sizing model、project state model、multi-agent protocol、memory pipeline 和 release boundaries。
