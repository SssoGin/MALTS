# 长项目工作区说明

此工作区使用 MALTS 长项目控制。

## 初始化就绪条件

- 选择 long-project initializer 表示用户需要长期项目工作区，而不是普通的最小 project-control 骨架。
- 新工作区只有在 `runtime/workspace_control.json` 已登记首个 Phase 且 `active_phase_id` 指向该 Phase 时才算初始化就绪。
- 如果根控制文件已存在但 Phase registry 为空，必须报告 `NEEDS_INITIAL_PHASE` 并提出无覆盖迁移；不得报告初始化完成。
- 必须明确告诉用户当前是否存在 active Session，以及为什么没有创建 Session。

## Canonical ownership

- `PROJECT_CONTROL.md` 负责原始目标、全局验收条件、active Phase 索引、跨 Phase 决策和 Project recovery record。
- `phases/<phase-id>/PHASE_CONTROL.md` 负责该 Phase 的目标、boundary 与 Boundary Review record、plan、队列、交付物、证据、recovery record、收口和成长复盘。
- `sessions/<session-id>/SESSION_CONTROL.md` 负责一次显式有界工作会话的范围、命令、touch set、checkpoint/recovery record 和下一步。
- `WORK_TASK_REPORT.md` 仅在 legacy workspace layout 兼容模式下是必需的精确投影。CURRENT contract 中，它与已存在的 `PROJECT_HANDOFF.md` 都是按需派生视图；过期只产生 warning，不成为竞争权威。
- `runtime/workspace_control.json` 只拥有机器强制执行的 schema/profile/index 与 transaction binding；coordination state 拥有 Admission、queue、fencing 与 quarantine。其他 `runtime/` 内容是生成证据/缓存。Runtime 不得编造或反向覆盖 canonical Markdown 的目标、边界、计划或恢复事实。

不得因每次 conversation turn 或普通持久写入创建 Session。只有显式定义 bounded work-session 边界时才创建。

## 日常进入与 Recovery order

已初始化工作区先按任务类别运行只读 `workspace-entry`，只加载其有界 current-set read list。该命令零写入、不创建实体、不加载完整历史。只有 entry 阻塞、用户明确要求恢复，或 recovery-sensitive gate 要求时才升级到完整恢复。

完整恢复顺序：

1. 读取最近适用的 instruction 文件。
2. 读取根 `PROJECT_CONTROL.md`。
3. 如存在，读取显式选择或 primary `PHASE_CONTROL.md`。
4. 只在 active Session 存在时读取其 `SESSION_CONTROL.md`。
5. 仅在报告/交接任务或恢复决定明确需要时读取 report/handoff。
6. 核查当前文件和 runtime 安全证据；历史文件只按显式引用读取。

任何 summary 都不能替代 active MALTS version、当前文件或要求的 runtime probe。

canonical recovery authority 固定为：active Session checkpoint；否则 active Phase recovery；否则显式绑定的 paused/terminal Phase；否则 Project recovery。禁止按时间或列表顺序选择最新历史 Session。

## Cross-control consistency

- 全新工作区使用精确 CURRENT workspace/Result contract，默认 profile 为 `single_phase`；只有显式启用 `resource_admission` 并取得 runtime Admission 时，才允许额外 `OPEN` Phase。受支持的旧布局作为内部兼容输入保持可读，只能通过一步、显式 dry-run/apply、精确 hash 绑定的重整到达 CURRENT。
- `phase-boundary-review` 将 operation execution 与 `review_outcome` 分开报告；它不会持久化或授权工作。只有 `record-phase-boundary-review` 可记录 review，后续 mutation authorization 必须另行保存。
- canonical control 漂移、normalized Boundary/Recovery 漂移、无效 plan/authorization/Admission/fencing 前提、影响权威的 UNKNOWN 外部副作用或 incomplete transaction，会阻断受影响操作。CURRENT contract report/handoff 漂移是 warning 并局部刷新；legacy workspace layout 投影漂移保留严格兼容阻塞。
- Workspace 与 coordination authority 写入共享 `runtime/workspace_transaction.lock.json`、`runtime/workspace_transactions/`、`WS_TRANSACTION_*`、锁后精确 preimage 复核和唯一写者。Artifact transaction 继续使用独立路径和 `ART_TRANSACTION_*` code。
- resource profile Task 使用 CURRENT Result Contract execution authority 与 append-only typed events；Phase/Session/report/handoff/runtime summary 只保存引用或可重建投影，绝不保存第二份完整 Attempt ledger。
- `max_authorized_rounds` 是独立运行时 STOP 门。Attempt 失败只终止该 Attempt；不自动重试，也不自动升级 Task/Phase 终态。
- `scoped-readiness` 是只读路由建议（S0/S1/S2/ESCALATE），绝不授权、写入或派发。`refresh-project-instructions` 只按精确审阅计划重写 `MALTS-PROJECT:` 拥有的 block；无 marker 的自定义文件绝不自动认领。

## 项目专属 managed instruction block

只通过显式命令刷新：

```text
<!-- MALTS-PROJECT:BEGIN <marker-id> -->
...
<!-- MALTS-PROJECT:END <marker-id> -->
```

`refresh-project-instructions` 保持 block 外字节/BOM/换行原样，拒绝 reparse/hardlink 目标，且幂等。普通 `init` / `validate` / `recover` 绝不隐式触发它。

## Discovery 与 Plan Recheck

- 普通启动只从当前工具相邻的 `MALTS_BOOT.md` 解析；交叉核对 registry、active pointer 与 `VERSION`。MALTS v1.1.1 起不再使用或创建机器全局 `GLOBAL_BOOT.md`。任何不一致都按 split brain fail closed。
- Active Phase 拥有 plan path、revision、raw-byte SHA-256、recheck trigger/result 与 launch-review invalidation；root control 只保存索引，Session 只继承绑定。
- S3/S4 工作在新写入范围、launch review、verifier、recovery/rollback 或 final delivery 前，按事件运行只读 `long_workspace.py plan-recheck --require-active-plan`。`BLOCKED` 必须停止；该命令不会创建授权。

## Resource Admission

- 默认 `single_phase` 不创建 coordination state，也不承担日常并发成本。
- `resource_admission` 下，每次写入都核验 typed locator/capability Admission、精确 Phase hash、actor、lease expiry 和 fencing epoch。相同及父子路径冲突；声明 alias 的 locator 归入同一 domain。
- Capability 模式为 `SHARED`、`EXCLUSIVE`、`QUEUED`、`ISOLATE_REQUIRED`。续租必须显式执行；不会创建 heartbeat daemon 或隐式 Agent。
- 外部副作用为 `UNKNOWN` 时隔离受影响 domain。除非 workspace authority/recovery 本身不确定，无关 domain 可继续；被隔离 domain 必须显式、基于证据 reconcile。

## Safety

- 将只读审查与状态修改执行分开。
- 不覆盖用户文件，不静默扩面。
- 未经独立授权，不使用 Git、网络、provider、Agent dispatch、依赖安装或破坏性清理。
- 不运行自动、周期、后台或普通使用触发的更新检查。
