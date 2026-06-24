# MALTS 入门指南

语言：[English](../GETTING_STARTED.md) | [简体中文](GETTING_STARTED.md)

本文说明如何为受支持的 Agent 工具安装 MALTS，以及如何在第一个任务中使用它。它面向需要先完成实际配置的用户，而不是系统设计读者。

## 1. MALTS 增加了什么

MALTS 为 Agent-assisted coding work 增加一套 file-backed operating workflow。它主要用于降低较长任务或较高风险任务中的常见失败模式：

| 问题 | MALTS 机制 |
|---|---|
| 长对话中原始目标变得不清楚。 | 记录原始目标、当前理解、完成定义和验收标准。 |
| 新窗口、中断或上下文丢失后难以恢复工作。 | 用 `PROJECT_CONTROL.md` 记录状态，用 `WORK_TASK_REPORT.md` 按用户/项目语言记录阶段结果；用 `PROJECT_HANDOFF.md` 记录继续上下文。 |
| Agent 缺少证据就声称完成。 | 使用交付和质量检查清单，并在交付前记录验证证据。 |
| 多 Agent 工作产生协调风险。 | 要求适配评估、launch review、任务契约、明确确认、分派记录和最终核对。 |
| 可复用经验失控地变成永久规则。 | 通过 MALTS Memory Pipeline 和 memory-write checklist 过滤后再持久化。 |

MALTS 不替代 coding Agent、IDE、source control、CI、package manager、permission model 或人工审批流程。它为这些系统外围提供操作纪律。

## 2. 选择目标工具

MALTS 包含以下可选 adapters：

| 工具 | 安装后的指令文件 | 其他 adapter 文件 |
|---|---|---|
| Codex | `AGENTS.md` | Codex-native `config.toml`、`agents/*.toml`、workflow prompts 和 `MALTS_BOOT.md` |
| Claude Code | `CLAUDE.md` | 可选 `agents/`、`commands/` scaffold 和 `MALTS_BOOT.md` |
| OpenCode | `AGENTS.md` | `opencode.json`、可选 `.opencode/agents` scaffold 和 `MALTS_BOOT.md` |

除非有明确需要，建议先安装一个工具。`AllIncluded` 适用于需要在 Codex、Claude Code 和 OpenCode 之间维护同一 MALTS 行为的用户。

## 3. 预览安装

安装脚本是 review-first。dry run 会打印计划写入内容，不修改文件：

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex
```

支持值：

```text
Codex
ClaudeCode
OpenCode
AllIncluded
```

示例：

```powershell
.\scripts\Install-MALTS.ps1 -Tool ClaudeCode
.\scripts\Install-MALTS.ps1 -Tool OpenCode
.\scripts\Install-MALTS.ps1 -Tool AllIncluded
```

应用前先审阅输出。已有目标文件会标记为 `exists`；新目标文件会标记为 `new`。

Windows 下可使用保留窗口的 dry-run wrapper：

```powershell
.\scripts\Install-MALTS.review.cmd -Tool AllIncluded
```

## 4. 应用安装

审阅 dry-run 计划后，应用所选 adapter：

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex -Apply
```

除非 `-Overwrite` 或 `-MergeSafe` 允许所选策略，安装器会保留已有支持文件。工具指令文件单独处理：默认 `ManagedMerge` 只修改带标记的 MALTS 区块，并保留区块外用户文本。

指令模板是可选项。若只安装支持文件而不安装工具指令模板：

```powershell
.\scripts\Install-MALTS.ps1 -Tool ClaudeCode -InstructionMode Skip -Apply
```

## 5. 验证 runtime 发现链路

安装后的指令模板和 adapter 文件依赖一份共享 `MALTS_ROOT`：

```text
skills/
runtime/EN
runtime/CH
MALTS_BOOT.md
```

安装器会创建一份共享 MALTS root，在每个选中的工具目录写入 `MALTS_BOOT.md`，并安装六个轻量发现 bridge。安装后，确认每个 bridge 都能路由到包含 `README.md`、`skills/`、`runtime/EN/templates` 和 `runtime/EN/checklists` 的 root。共享 `MALTS_ROOT` 下的 `skills/` 是唯一默认实现事实源。`runtime/CH` 下的中文运行镜像用于中文用户可读报告和双语同步；普通英文 Agent 执行不应加载中文镜像，除非当前任务需要。

默认安装不应包含以下重型重复内容：

```text
<tool-config-root>/malts/
<tool-config-root>/skills/<MALTS-skill>/<完整 runtime 文件>
```

预期的工具本地 skill 路径中，每个 MALTS skill 只能有一个轻量 bridge `SKILL.md`。

## 6. 在第一个任务中使用 MALTS

小任务不需要创建 MALTS 文件。预期行为是：

1. Agent 在状态修改前先回答或计划。
2. Agent 在声称完成前验证相关事实。
3. 除非任务扩大，否则保持单 Agent。

非琐碎任务可要求 Agent 使用 MALTS。一个简短请求是：

```text
Use MALTS for this task. Create or reuse PROJECT_CONTROL.md, define acceptance criteria, and verify before delivery.
```

Agent 应当：

1. 捕获原始目标。
2. 说明假设和排除项。
3. 定义完成条件和验收标准。
4. 建立任务队列。
5. 记录决策、文件归属、风险和验证证据。
6. 在阶段或最终交付后写入或追加 `WORK_TASK_REPORT.md`。
7. 在 `WORK_TASK_REPORT.md` 内使用用户或项目主要语言；只有明确要求时才创建完整翻译镜像。
8. 如果另一个 Agent 或新窗口需要继续，更新带简短 English Agent Brief 的 `PROJECT_HANDOFF.md`。

## 7. 需求不清楚时使用 Grill-Me Preflight

MALTS 包含 Grill-Me Preflight：

```text
skills/grill-me-preflight/SKILL.md
```

preflight 是澄清门禁。它在实现前提出会改变决策的问题，使隐藏假设、目标边界、关键取舍和验收标准显性化。它不是子 Agent 分派，也不需要多 Agent 确认词。

适用场景：

- migration
- protocol changes
- multi-file refactors
- ambiguous product or architecture work
- success criteria 尚不可测量的任务

小任务且目标和验证路径清楚时应跳过。

## 8. 只有有操作价值时才使用多 Agent

多 Agent 模式是可选项。只有当 delegation 改善以下至少一项时才适用：

- independent exploration
- independent verification
- reduced context pressure
- safe parallel work on non-conflicting files
- recovery for a multi-phase task

任何真实子 Agent 分派前，Agent 必须展示 launch review，其中包含总体目标、总计划、角色、相关模型策略、每个任务和每个简短计划。分派必须等待用户明确回复：

```text
确认运行
```

没有该确认时，MALTS 保持单 Agent。

## 9. 验证安装

可用检查：

```powershell
python tools\agent_system_lint.py check-semantic-freshness --malts-root . --version 0.1.8
python tools\agent_system_lint.py check-doc-sync --output-root runtime
.\scripts\Install-MALTS.ps1 -Tool Codex
```

前两个命令检查 release metadata 和 documentation synchronization。不带 `-Apply` 的 install 命令用于验证安装计划仍可运行且不会写文件。

## 10. 常见入口

| 情况 | 推荐入口 |
|---|---|
| 第一次安装 | [README.zh-CN.md](../../README.zh-CN.md) 和本文 |
| 理解系统模型 | [系统说明](SYSTEM_OVERVIEW.md) |
| 详细架构和不变量 | [核心设计](CORE_DESIGN.md) |
| handoff 与继续工作 | [交接说明](HANDOFF.md) |
| Agent-assisted installation policy | [Agent 安装协议](AGENT_INSTALL.md) |
| 安全与发布卫生 | [安全与发布卫生](SECURITY.md) |
