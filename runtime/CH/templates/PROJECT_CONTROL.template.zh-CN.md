# PROJECT_CONTROL

> 仅作为 Project 级权威：保存用户原始目标、全局验收、当前 Phase/计划索引、跨 Phase 决策、Artifact 指针和 Project 恢复入口。
> Phase、Session、Task/Result 与 runtime coordination 分别保存自身细节；报告与 handoff 仅按需生成，且不是权威来源。

<!-- MALTS:section=metadata -->
## 元信息

- 项目：
- 控制文件版本：<MALTS_VERSION>
- 版本来源：先解析 `MALTS_BOOT.md`，再读取 active `MALTS_ROOT` 的 `VERSION`；不要从旧 control/report/handoff/template 文件复制物理 generation 路径或当前 MALTS 版本。
- 当前轮次：
- 最后更新：
- 项目负责人：Main Controller
- 当前模式：Single-Agent / Multi-Agent Long-Task
- 叙述语言：English / Simplified Chinese / project language
- 权威文件：`PROJECT_CONTROL.md`
- 权威边界：只保存 Project 事实；Phase/Session/Task/Result 与 coordination 细节归各自 owner。
- 派生视图：`WORK_TASK_REPORT.md` 与 `PROJECT_HANDOFF.md` 只在明确请求时生成，不参与普通 mutation gate。
- 容量：新鲜目标不超过 150 行 / 12 KiB；日常热读取不超过 150 行 / 16 KiB；长期软上限 1500 行 / 262144 bytes。

<!-- MALTS:section=user-original-goal -->
## 用户原始目标

> 用户原始目标（锁定）：

### 后续用户变更

| 时间 | 变更 | 影响 |
|---|---|---|

<!-- MALTS:section=current-interpreted-goal -->
## 当前理解目标

- 当前理解：
- 已确认排除项：
- 待确认问题：
- Grill-Me Preflight：适用=Yes / No / N/A；已提供=Yes / No / N/A；决定=Accepted / Declined / N/A

<!-- MALTS:section=completion-definition -->
## 完成定义

- [ ] 用户核心目标和全局验收条件已满足。
- [ ] 必要的 Project 交付物与跨 Phase 决策已记录。
- [ ] 验证证据只建立索引，不复制 Phase 证据。
- [ ] 剩余工作、阻塞和恢复入口清楚明确。

<!-- MALTS:section=acceptance-criteria -->
## 验收标准

| 要求 | 验证方法 | 状态 | 证据 |
|---|---|---|---|
|  |  | TODO |  |

<!-- MALTS:section=current-stage -->
## 当前阶段

- 阶段：
- Active Phase：
- 阶段目标：
- 退出条件：

<!-- MALTS:section=plan-recheck-index -->
## 计划回看索引

- Active plan：`N/A`
- Active Phase owner：`N/A`
- Plan revision：`N/A`
- Plan content SHA-256：`N/A`
- Latest recheck trigger：`N/A`
- Latest recheck result：`N/A`
- Launch review invalidated：`No`

<!-- MALTS:section=phase-carry-over-index -->
## Phase Carry-over 索引

| Source Phase | Target Phase | Transition Plan SHA-256 | Source Record | Target Record | Status |
|---|---|---|---|---|---|

<!-- MALTS:section=artifact-contract-index -->
## Artifact 生命周期索引

- Contract version: `1`
- Enrollment: `NOT_ENROLLED`
- Shared index: `N/A`
- Archive index: `N/A`
- Latest audit: `N/A`

<!-- MALTS:section=task-queue -->
## 任务队列

这里只允许 Project 级门禁；长工作区的全部 Phase 任务归对应 `PHASE_CONTROL.md`。

| ID | 优先级 | 状态 | Owner | 任务 | 依赖 | 允许变更 | 验证 |
|---|---|---|---|---|---|---|---|

<!-- MALTS:section=file-ownership -->
## 文件所有权

这里只保存长期 Project 边界指针；runtime Admission、lease、queue 和 fencing 记录归 coordination state。

| 路径 / 资源 | Project 边界 | 权威 Owner | 说明 |
|---|---|---|---|

<!-- MALTS:section=decisions -->
## 决策记录

| 时间 | 跨 Phase / Project 决策 | 原因 | 证据 |
|---|---|---|---|

<!-- MALTS:section=verification-records -->
## 验证记录

这里只索引 Project 级验收；引用 owner 证据，不复制正文。

| 时间 | 验收要求 | 结果 | 证据引用 |
|---|---|---|---|

<!-- MALTS:section=risks-and-blockers -->
## 风险与阻塞

这里只保存全局 Project 阻塞；资源级或 Phase 级问题归对应 control/runtime record。

| ID | 范围 | 描述 | 状态 | Owner / Reconcile |
|---|---|---|---|---|

<!-- MALTS:section=recovery-notes -->
## 恢复说明

- Recovery schema: `1`
- Record ID: `project:recovery`
- Summary: 仅当没有更具体的 Phase 或 Session 恢复源时，才使用 Project recovery。
- Next action: 通过边界与授权审查后再打开或恢复 Phase。
- Evidence references: `project:recovery`
- Recorded at: `N/A`
