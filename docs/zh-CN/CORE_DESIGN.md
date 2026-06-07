# MALTS 核心设计

语言：[English](../CORE_DESIGN.md) | [简体中文](CORE_DESIGN.md)

本文提供 MALTS 核心设计的中文说明。英文 [Core Design](../CORE_DESIGN.md) 仍是完整设计事实源；本文覆盖公开使用者和维护者需要优先理解的结构、不变量和发布边界。

## 设计目标

MALTS 面向 AI coding agents 的长任务工作流，目标是降低 goal drift、状态丢失、验证不足、交接困难、无控制多 Agent 协调和 durable memory 污染等风险。

系统默认 single-agent first。也就是说，即使启用 MALTS，主控制 Agent 仍是默认执行者。Multi-agent work 是受控分工机制，只在具有明确操作价值时启用，并且真实子 Agent 分派前必须有 launch review 和用户确认。

## 三层结构

```text
MALTS
|
|- Core layer
|  |- PROJECT_CONTROL.md
|  |- WORK_TASK_REPORT.md
|  |- PROJECT_HANDOFF.md
|  |- templates
|  |- checklists
|  `- durable growth candidates
|
|- Runtime layer
|  |- canonical skills
|  |- execution modes
|  |- recovery and continuity
|  |- delivery verification
|  `- memory pipeline
|
`- Adapter layer
   |- Codex
   |- Claude Code
   `- OpenCode
```

Core layer 保存通用操作模型和持久项目产物。Runtime layer 通过根级 `skills/`、execution modes、recovery、verification、templates、checklists 和 memory pipeline 把模型变成可执行 workflow。Adapter layer 把同一模型映射到各工具，不让工具差异污染核心设计。

公开包只有一个 canonical skill source：

```text
skills/
```

工具本地 skill 目录是安装目标，不是第二事实源。`runtime/EN` 保存 templates 和 checklists。

## 激活模型

| 模式 | 使用场景 | 需要文件 | 行为 |
|---|---|---|---|
| Normal single-agent work | 小、明确、低风险任务 | 默认无 | 直接完成并做相关验证 |
| MALTS single-agent mode | 需要可恢复状态或阶段报告 | `PROJECT_CONTROL.md`，通常还有 `WORK_TASK_REPORT.md` 和必要时的 `PROJECT_HANDOFF.md` | 主控制 Agent 继续执行，但状态和验证持久化 |
| MALTS multi-agent mode | 分工明确降低风险或成本 | MALTS 状态文件、任务契约和子 Agent 报告 | 需要 launch review 和明确确认 |

## 核心文件

| 文件 | 角色 |
|---|---|
| `PROJECT_CONTROL.md` | Agent-facing 项目状态、目标、队列、决策、风险和验证记录 |
| `WORK_TASK_REPORT.md` | 阶段或最终交付报告，记录结果、改动、验证、风险和后续 |
| `PROJECT_HANDOFF.md` | Agent-facing continuation 和 recovery 事实源 |

## Skills、Templates 和 Checklists

`skills/` 包含 MALTS 可安装 `SKILL.md` workflows，例如 Grill-Me Preflight、multi-agent scheduling、session handoff、retrospective growth、single-agent lightweight growth 和 `malts-project-init`。

`runtime/EN/templates` 保存 task contract、sub-agent report、project control、handoff 和 work task report 模板。

`runtime/EN/checklists` 保存 delivery、quality gate 和 memory-write 检查清单。

## Adapter 策略

| Adapter | 主指令文件 | 说明 |
|---|---|---|
| Codex | `AGENTS.md` | 提供 Codex-facing operating rules 和 MALTS reminders；共享 skills 从根级 `skills/` 安装 |
| Claude Code | `CLAUDE.md` | 提供 Claude Code 指令入口，可选 agents/commands；共享 skills 从根级 `skills/` 安装 |
| OpenCode | `AGENTS.md` | 提供 OpenCode-specific config 和可选 agent scaffold；共享 skills 从根级 `skills/` 安装 |

除非变更只适用于单一 runtime，否则 adapter docs 和 templates 应保持同步。

## 发布边界

公开发布包应包含：

- public docs
- 根级 `skills/`
- `runtime/EN/templates`
- `runtime/EN/checklists`
- adapters
- scripts
- tools

公开发布包不应包含：

- real project control files
- real handoff records
- local archives
- generated migration packages
- sessions、caches、memory dumps
- secrets 或 machine-specific absolute paths
- 根级 `skills/` 之外的额外公开 skill tree

## 验收标准

完整 MALTS release 应满足：

- 普通任务能保持低开销单 Agent 模式。
- 非琐碎开始能通过 Grill-Me Preflight 暴露假设和验收标准。
- 长任务能创建或复用 `PROJECT_CONTROL.md`。
- 状态能跨窗口或 Agent 恢复。
- 多 Agent 工作需要 launch review 和明确确认。
- 完成声明包含验证证据。
- `WORK_TASK_REPORT.md` 能向用户说明结果、验证、风险和恢复信息。
- `PROJECT_HANDOFF.md` 能指导下一个 Agent。
- 成长候选在 durable writes 前经过过滤。
- Codex、Claude Code 和 OpenCode 有同步 adapter 入口。
- 中文公开文档在启用时有结构化同步检查。
