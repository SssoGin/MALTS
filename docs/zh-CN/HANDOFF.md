# MALTS 交接说明

语言：[English](../HANDOFF.md) | [简体中文](HANDOFF.md)

MALTS 使用 handoff 文件，让长任务能在新窗口、中断或 Agent 更换后恢复。

## 默认文件名

Agent-facing 默认文件：

```text
PROJECT_HANDOFF.md
```

可选用户-facing 中文镜像：

```text
项目交接.md
```

## 规则

- 先生成 Agent-facing handoff。
- 中文镜像是可选用户-facing 文档。
- handoff 文件中不得写入 secrets、tokens、cookies、passwords、credentials、sensitive memory dumps 或 raw session logs。
- 公开示例使用占位符。
- 真实 handoff 文件属于用户项目工作区，不属于 MALTS release repository。
- 已安装 release package 与 active-generation root 是不可变 runtime input；不得在其中保存实时 handoff 文件。

## 应包含内容

- 生成时间
- 当前 workspace
- 当前目标
- 已完成工作
- 待处理工作
- 已执行验证
- 已知风险
- 下一步建议

模板见：

```text
runtime/EN/templates/PROJECT_HANDOFF.template.en.md
```

## Plan Binding

Active S3/S4 Phase 的交接必须包含 Phase-owned active plan path、revision、raw-byte SHA-256、last trigger/result、launch-review invalidation 与继承的 Session binding。在声称 handoff-ready 前运行只读 `FINAL_DELIVERY` Plan Recheck；若结果 `BLOCKED`，保留该结果与对账动作，不得掩盖漂移。
