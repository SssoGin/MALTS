# MALTS 使用指南

语言：[English](../USAGE.md) | [简体中文](USAGE.md)

当任务需要可恢复计划、明确验证、跨窗口连续性、可选多 Agent 协调，或可复用流程复盘时使用 MALTS。

## 普通任务

小任务应保持单 Agent，降低流程开销。除非用户明确启用 MALTS，或任务扩大到需要可恢复状态，否则不要创建 MALTS 文件。

## 长任务

较大的工作启用 MALTS 后，应执行以下步骤：

1. 创建或更新 `PROJECT_CONTROL.md`。
2. 定义验收标准。
3. 建立任务队列。
4. 在可能有多个执行者时记录文件归属。
5. 标记完成前先验证。
6. 每个阶段或最终交付后写入或追加 `WORK_TASK_REPORT.md`。
7. 在 `WORK_TASK_REPORT.md` 内使用用户或项目主要语言；只有明确要求时才创建完整翻译镜像。
8. 在交接或上下文风险出现前更新 `PROJECT_HANDOFF.md`，顶部保留简短 English Agent Brief。

Single-agent first 表示启用 MALTS 后主控制 Agent 默认仍保留执行所有权。Multi-agent scheduling 只在能降低风险、改善独立验证，或让非冲突并行工作更实际时启用。

## 多 Agent 工作

多 Agent 模式是可选项，需要：

- 明确的适配评估
- launch review
- 用户确认
- 任务契约
- 分派和反馈记录
- 主控制 Agent 的最终核对

没有这些条件时，MALTS 应继续保持单 Agent。

## 成长与记忆

可复用经验通过 MALTS Memory Pipeline 处理。候选经验应先记录在 durable project state 中，例如 `PROJECT_CONTROL.md`、`WORK_TASK_REPORT.md` 或本地复盘。只有经过过滤的可复用候选，才应提升到 global skill、`GLOBAL_MEMORY.md`、`AGENTS.md`、`CLAUDE.md` 或等价工具指令入口。

## 交接

默认 Agent-facing recovery 文件是 `PROJECT_HANDOFF.md`。详细规则见 [交接说明](HANDOFF.md)。
