# 项目交接

> 用途：canonical continuation and recovery handoff。
> 语言策略：顶部保留简短 English Agent Brief，便于 Agent 扫描；其余内容使用用户或项目主要语言。除非用户明确要求，不生成完整翻译镜像。

## Agent Brief

- Goal:
- Current status:
- Allowed scope:
- Last verification:
- Next step:

## 身份与锚点

- 生成时间：
- 项目根目录：
- 交接文件：
- 项目控制文件：
- Git 根目录 / 分支 / 远端：

## 已审阅的上下文

- 已读取文件：
- 已运行命令：
- 外部参考：

## 当前状态

- 已完成：
- 进行中：
- 待处理：

## Result Contract 恢复

- Result ID：
- 执行状态：DRAFT / PREFLIGHT / AWAITING_AUTHORIZATION / AUTHORIZED / PLANNING / EXECUTING / VERIFYING / REPLANNING / FINALIZING / DONE / PARTIAL / BLOCKED / FAILED
- 终态：None / DONE / PARTIAL / BLOCKED / FAILED
- 恢复轮次 / 尝试次数：
- 当前 strategy ID：
- 预算使用量 / hard limits：
- 最后状态事件 ID / 直接证据：
- 恢复摘要 / 下一步：

## Plan Recheck 恢复

- Active plan / revision / SHA-256：
- Last trigger / recorded result / observed gate result：
- Launch review invalidated：Yes / No / N/A
- Owning Phase / inherited Session：

## 验证

| 检查 | 结果 | 证据 |
|---|---|---|
|  | TODO / PASS / FAIL / N/A |  |

## 风险与阻塞

| 风险 | 状态 | 缓解措施 |
|---|---|---|
|  | Open / Mitigated / Accepted / N/A |  |

## 建议下一步

1. TODO

## 隐私检查

- [ ] 不包含 secrets、tokens、cookies、credentials、sensitive memory dumps 或 raw session logs。
- [ ] 公开示例使用占位符，不使用机器特定路径。
