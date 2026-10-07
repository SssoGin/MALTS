# MALTS 交接

本页属于MALTS整体系统说明，当前版本与实现为2.0.0。工作过程见[系统说明](SYSTEM_OVERVIEW.md)和[使用指南](USAGE.md)，本页只展开对应主题。

## 1. 作用与内容

交接帮助后续执行者理解当前目标、完成证据、下一步和恢复边界。它是按需派生视图，不是执行授权或第二状态库。普通成功回合不必生成交接。

包含准确 Task/revision/Phase、相关计划、已观察结果、未决效果、Host/预算/epoch、手工独有内容与有效来源。历史失败与条件性建议保持原语义，不变成待执行指令。

## 2. 保全、预览和发布

通过 handoff.preserve-note/capture-file 保全已选择原文；handoff-preview返回有界事实、部分页标识与source token。预览不证明完整性或授权限。

handoff.publish要求准确Task版本、当前来源令牌、现有已审阅输出及精确目标前像；写入前检测漂移，失败保留可恢复状态。输出不存在时，先用另一个明确限定的创建动作，不用盲目重定向。inspect-publication沿原ID核结果。

## 3. 续接检查

后续执行者重新核Boot/binding/current Task与实际相关文件。UNKNOWN沿原操作对账；旧完成、PAUSED和停止传输均不证明效果/进程已结清。原文保护、来源与保留用途见[状态合同](V2_STATE_CONTRACT.md)，控制端例见[v2操作](V2_PREVIEW_USAGE.md#v2-handoff)。
