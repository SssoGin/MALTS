# PROJECT_CONTROL

> 用途：启用 MALTS 后，作为当前项目状态的单一事实源。  
> 语言策略：默认只维护 `PROJECT_CONTROL.md` 这一份 canonical 控制文件。`MALTS:section` marker、状态值、ID、路径和命令保持稳定；可见标题和叙述正文使用用户或项目主要语言。除非用户明确要求，不生成完整翻译镜像。
> 不要为每个琐碎任务默认创建 MALTS 控制文件。仅当用户启用 MALTS、长任务调度已激活，或普通任务变复杂并需要可恢复状态时，创建或复用本文件。

<!-- MALTS:section=metadata -->
## 元信息

- 项目：
- 控制文件版本：<MALTS_VERSION>
- 版本来源：先解析 `MALTS_BOOT.md`，再读取 active `MALTS_ROOT` 的 `VERSION`；不要从旧 control/report/handoff/template 文件复制物理 generation 路径或当前 MALTS 版本。
- 当前轮次：
- 最后更新：
- 项目负责人：Main Controller
- 当前模式：Single-Agent / Multi-Agent Long-Task

## 语言与结构

用本节明确控制文件语言策略。

- Canonical control file：`PROJECT_CONTROL.md`
- 正文语言：English / 简体中文 / 项目语言 / mixed
- 稳定字段：标题、表头、状态值、任务 ID、证据等级、路径和命令保持可机器读取。
- 可选翻译镜像：默认无；只有用户明确要求时才创建。
- 事实源策略：如果存在可选翻译镜像，仍以 `PROJECT_CONTROL.md` 为准。

<!-- MALTS:section=user-original-goal -->
## 用户原始目标

> 锁定字段。粘贴或引用用户原始目标。没有明确确认，不要改写此字段。

## 用户后续变更

- 变更：
- 时间：
- 影响：

<!-- MALTS:section=current-interpreted-goal -->
## 当前理解目标

- 当前理解：
- 已确认不做：
- 待确认问题：

## Grill-Me 启动盘问

非琐碎任务或项目启动时使用本节。

- 本任务是否适用：Yes / No / N/A
- 是否已提醒用户：Yes / No / N/A
- 用户决定：Accepted / Declined / N/A
- 已说明的收益：隐藏假设 / 目标边界 / 关键取舍 / 验收标准 / 减少返工
- 启动盘问已解决的决策：
- 剩余待确认问题：

<!-- MALTS:section=completion-definition -->
## 完成定义

本项目只有在以下条件满足时才算完成：

- [ ] 用户核心目标已满足。
- [ ] 必要交付物真实存在。
- [ ] 关键修改已列出。
- [ ] 验证证据已记录。
- [ ] 未完成事项已说明。
- [ ] 风险透明。

<!-- MALTS:section=acceptance-criteria -->
## 验收标准

| 需求 | 验证方法 | 状态 | 证据 |
|---|---|---|---|
|  |  | TODO / PASS / FAIL / N/A |  |

<!-- MALTS:section=current-stage -->
## 当前阶段

- 阶段：
- Active Phase：
- 阶段目标：
- 退出条件：

<!-- MALTS:section=plan-recheck-index -->
## Plan Recheck Index

- Active plan: `N/A`
- Active Phase owner: `N/A`
- Plan revision: `N/A`
- Plan content SHA-256: `N/A`
- Latest recheck trigger: `N/A`
- Latest recheck result: `N/A`
- Launch review invalidated: `No`

<!-- MALTS:section=task-queue -->
## 任务队列

状态值：TODO、READY、IN_PROGRESS、REVIEW、DONE、BLOCKED、FAILED、CANCELLED。

| ID | 优先级 | 状态 | 负责人 | 任务 | 依赖 | 允许修改 | 验证方式 |
|---|---|---|---|---|---|---|---|
| T001 | P0 | TODO | Main Controller |  | 无 |  |  |

<!-- MALTS:section=file-ownership -->
## 文件所有权

| 路径 / 资源 | 负责人 | 允许操作 | 锁定到 | 备注 |
|---|---|---|---|---|
|  |  | Read / Write / Verify |  |  |

## 产物与目录边界

新增、删除、移动、重命名文件夹，或改变目录、工具、输出包、独立产物用途时使用本节。

- 新增或变更的产物 / 目录：
- 边界类型：System entry / Shared tool / Trial-run workspace / User deliverable / Standalone task artifact / N/A
- 是否需要更新全局索引或手册：Yes / No / N/A
- 已检查的索引 / 手册 / 文档：
- 边界决策和证据：

## 三工具同步检查

协议、模板、检查清单、适配器或文档查漏补缺任务使用本节。

- 本任务是否适用：Yes / No
- Codex 已检查：Yes / No / N/A
- Claude Code 已检查：Yes / No / N/A
- OpenCode 已检查：Yes / No / N/A
- 用户是否明确排除某个工具：
- 未同步缺口和原因：

## 多 Agent 适配度评估

建议或启用多 Agent 模式前使用本节。

- 任务难度等级：S0 琐碎 / S1 收敛 / S2 中等 / S3 复杂 / S4 高风险或不清楚
- 任务类型：
- 适合多 Agent 的信号：
- 不适合多 Agent 的信号：
- 推荐运行模式：Single-Agent / Suggest Multi-Agent Launch Review / Ask Clarification
- 推荐动态 Agent 数量：0 / 1 / N
- 验收契约是否硬性要求独立验证：Yes / No
- 运行时路由证据状态：effective_verified / fallback_verified / configured_unverified / static_binding / inherited / unsupported / unknown
- 原因：
- 是否已告知用户建议：Yes / No / N/A
- 分派前必须等待的用户确认：`确认运行`

## 多 Agent 启动审阅

用户要求使用多 Agent 后，任何真实子 Agent 分派前都必须填写并展示本节。

- 总体目标：
- 总计划：
- 是否已询问模型与 effort 指定：Yes / No
- 模型与 effort 询问偏差是否已接受：Yes / No / N/A
- 路由指定写法：`responsibility=model-id@runtime-effort; responsibility=inherit@runtime-default; default=inherit@runtime-default`
- 用户模型与 effort 选择：
- 启动审阅引用：
- 已批准批次 ID：
- 路由证据引用：
- requested / recommended / configured / effective 选择：
- 运行时 effort ID / 归一化推理等级 / 展示标签：
- 约束强度：model=hard|soft|none; effort=hard|soft|none; delegation=hard|soft|none; concurrency=hard|soft|none
- binding status 与 test state：
- 生效并发数 / 深度：
- fallback 原因与 usage evidence（如有）：
- 分派顺序 / 并行批次：
- 必须等待的用户确认短语：`确认运行`
- 确认状态：Pending / Confirmed / Revised / Cancelled

| 职责通道 | 任务 ID | 模型 + 运行时 Effort 策略 | 路由证据 / Binding | 任务目标 | 简要计划 | 权限等级 |
|---|---|---|---|---|---|---|
| Planner / Explorer / Worker / Verifier / Memory Curator / Other |  | 显式 / 继承 / 运行时默认 | requested / recommended / configured / effective；binding status |  |  | Level 0 / 1 / 2 / 3 / 4 |

## Agent 分派日志

记录每一次真实的子 Agent 分派。如果本项目没有分派子 Agent，写 `N/A`。

| 时间 | 轮次 | 批次 ID | 任务 ID | 职责 | 分派机制 | 运行时 Agent ID | 生效模型 / Effort | Binding 状态 | 契约 / 路由证据 | 状态 |
|---|---|---|---|---|---|---|---|---|---|---|
|  |  |  |  | Planner / Explorer / Worker / Verifier / Memory Curator / Other | native spawn / `codex-peer-task` / other |  | 已知值 / Unknown | effective_verified / fallback_verified / other |  | PLANNED / CREATED / RUNNING / RETURNED / ACCEPTED / REWORK / BLOCKED / ARCHIVED |

## Agent 反馈日志

每个子 Agent 回收结果在合并为项目进度前都要记录。

| 时间 | 任务 ID | 运行时 Agent ID | 角色 | 反馈引用 | Main Controller 决策 | 原因 |
|---|---|---|---|---|---|---|
|  |  |  |  | 行内摘要 / 报告路径 | Accepted / Partially Accepted / Rejected / Redispatched |  |

<!-- MALTS:section=decisions -->
## 决策记录

| 时间 | 决策 | 原因 | 替代方案 | 风险 |
|---|---|---|---|---|
|  |  |  |  |  |

<!-- MALTS:section=verification-records -->
## 验证记录

证据等级：

- A：真实命令、测试、构建、运行结果。
- B：静态检查、语法检查、文件存在检查。
- C：代码或文档阅读判断。
- D：猜测；不能作为完成依据。

| 时间 | 目标 | 方法 | 结果 | 证据等级 | 备注 |
|---|---|---|---|---|---|
|  |  |  | PASS / FAIL / NOT RUN | A / B / C / D |  |

## 交付物

| 交付物 | 用途 | 状态 | 验证方法 | 用户需要操作 |
|---|---|---|---|---|
|  |  | Draft / Usable / Verified / Release / Accepted |  |  |

<!-- MALTS:section=risks-and-blockers -->
## 风险与阻塞

| ID | 类型 | 描述 | 影响 | 缓解方式 | 状态 |
|---|---|---|---|---|---|
| R001 |  |  |  |  | Open / Mitigated / Accepted |

## 异常处理

| 触发条件 | 检测方法 | 响应方式 | 重试上限 | 升级方式 |
|---|---|---|---|---|
| 子 Agent 超时 / 输出不完整 / 越界 / 验证失败 |  | 重试 / 拆小 / 串行 / 询问用户 / 停止 |  |  |

## 用户检查点

| 检查点类型 | 触发条件 | 需要用户决定 | 状态 | 备注 |
|---|---|---|---|---|
| 多 Agent 启动确认 / 阶段确认 / 阻塞决策 / 异常报告 / 高风险操作 / 无人值守自动继续授权 |  |  | Pending / Done / N/A |  |

## 运行时长与轮次策略

不承诺固定的一次性运行时长。用本节把长任务设计为有边界、可恢复的轮次。

- 任务开始时是否已询问无人值守自动继续：Yes / No
- 用户回答：
- 单个聊天窗口 / 上下文限制预期：
- 当前轮次退出条件：
- 整个项目继续策略：
- 下一次状态写入检查点：

## 结果合同

项目终态严格只有四种：`DONE`、`PARTIAL`、`BLOCKED`、`FAILED`。内部执行状态不是额外终态。

- 合同 / Result ID：
- 执行状态：DRAFT / PREFLIGHT / AWAITING_AUTHORIZATION / AUTHORIZED / PLANNING / EXECUTING / VERIFYING / REPLANNING / FINALIZING / DONE / PARTIAL / BLOCKED / FAILED
- 终态：None / DONE / PARTIAL / BLOCKED / FAILED
- Authorization Envelope 引用：
- hard acceptance criteria 对账：
- 当前轮次 / 尝试次数 / strategy ID：
- 预算使用量 / hard-limit 状态：
- 最后状态事件 / 直接证据：
- 剩余工作：
- 恢复点：

## 无人值守自动继续授权

仅在用户明确授权系统不在每个轮次边界等待时使用。如果用户没有明确授权，无人值守自动继续关闭，禁止擅自无人自动运行。

- 是否启用：Yes / No
- 用户是否已授权：Yes / No
- 任务开始时是否已询问：Yes / No
- 用户授权原文：
- 授权时间：
- 授权目标：
- 从哪个恢复点继续：
- 允许的文件 / 目录：
- 允许的命令：
- 允许的动作类型：
- 禁止操作：
- 无人值守期间是否允许多 Agent 分派：Yes / No
- 无人值守运行所需的多 Agent 启动是否已审阅确认：Yes / No / N/A
- 子 Agent 模型策略：
- 最大无人值守轮次：
- 实际时间上限：
- 每轮报告要求：
- 自动化机制：Codex heartbeat / Codex cron / Claude Code 已确认等价机制 / OpenCode 已确认等价机制 / 手动恢复 / N/A
- 当前无人值守状态：Not Authorized / Authorized / Running / Stopped / Completed
- 停止条件：

## Planner 评估

| 轮次 | 是否使用 Planner | 接受的建议 | 拒绝 / 合并 / 拆分的建议 | 下一轮调整 |
|---|---|---|---|---|
|  | Yes / No / N/A |  |  |  |

## 本轮对账

- 本轮完成：
- 本轮证据：
- 本轮失败或阻塞：
- 新风险：
- 决策变化：
- 下一轮：

## 工作任务报告

记录每次任务或阶段完成后已经交付给用户的工作任务报告。

| 时间 | 范围 | 状态 | 报告位置 / 摘要 | 恢复点 |
|---|---|---|---|---|
|  | Task / Phase / Project | DONE / PARTIAL / BLOCKED / FAILED |  |  |

## 成长候选

L1 分析不创建 durable record；L2 项目维护需要当前项目写入授权；L3 系统晋升需要单独确认。来源观察不计为 future-use validation：默认进入 `VALIDATED` 需要两个独立未来任务的 helped 结果；高风险候选还需要 independent review、negative test 或 counterexample test。

| Signal / Candidate | 证据 | Trigger / Action / Check / Boundary | 权限 | 风险 | 生命周期状态 | Future-Use Validations | 检索结果 | Challenge / Suspension | 晋升授权 |
|---|---|---|---|---|---|---|---|---|---|
|  |  |  | L1 / L2 / L3 | low / medium / high / critical | OBSERVED / CANDIDATE / PROJECT_EXPERIMENTAL / FUTURE_USE_VALIDATING / VALIDATED / CHALLENGED / SUSPENDED / SYSTEM_PROMOTION_PROPOSED / ACCEPTED / REJECTED / DEPRECATED / REMOVED | future task IDs、independence keys、outcomes、evidence | not_evaluated / helped / neutral / harmful / inconclusive | challenge refs、severity、replacement 或 review | 单独 L3 authorization ref / N/A |

## Token 与复杂度控制

- 最新多 Agent 适配度评估结果：
- 多 Agent 调度是否仍然值得：
- 下一步能否由 Main Controller 单独完成：
- 是否为了流程完整而增加了不必要复杂度：

## 成本与效率

- 本轮派发 Agent 数：
- 本轮返回的 Agent ID：
- 本轮使用的模型策略：
- 文档同步模型 / 成本策略：
- 文档同步源文件、目标文件和方向：
- 翻译 / 同步前使用的脚本或结构化检查：
- 低成本候选范围（如使用）：
- 高能力 / 主控批准范围：
- 因缺少批准而必须标记 Draft / Unverified：Yes / No / N/A
- 未复核的文档同步风险：
- 实际合并的输出：
- 并行是否减少不确定性或提高验证质量：
- 任务队列是否变短：
- 交付物可用性是否提高：
- 是否存在假进度或重复探索：

<!-- MALTS:section=recovery-notes -->
## 恢复说明

最低恢复单元：

- Result 执行状态：
- 终态：None / DONE / PARTIAL / BLOCKED / FAILED
- 当前轮次 / 尝试次数：
- 当前 strategy ID：
- 预算使用量 / hard limits：
- 最后状态事件 / 证据：
- 当前目标：
- 完成定义：
- 当前任务队列：
- 已完成任务：
- 阻塞项：
- 已修改文件：
- 验证记录：
- 下一步最短路径：
