# 长项目工作区说明

此工作区使用 MALTS 长项目控制。

## 初始化就绪条件

- 选择 long-project initializer 表示用户需要长期项目工作区，而不是普通的最小 project-control 骨架。
- 新工作区只有在 `runtime/workspace_control.json` 已登记首个 Phase 且 `active_phase_id` 指向该 Phase 时才算初始化就绪。
- 如果根控制文件已存在但 Phase registry 为空，必须报告 `NEEDS_INITIAL_PHASE` 并提出无覆盖迁移；不得报告初始化完成。
- 必须明确告诉用户当前是否存在 active Session，以及为什么没有创建 Session。

## Canonical ownership

- `PROJECT_CONTROL.md` 仅负责原始目标、全局验收条件、active Phase 索引和跨 Phase 决策。
- `phases/<phase-id>/PHASE_CONTROL.md` 仅负责该 Phase 的目标、队列、交付物、证据、收口和成长复盘。
- `sessions/<session-id>/SESSION_CONTROL.md` 仅负责一次显式有界工作会话的范围、命令、touch set、检查点和下一步。
- `runtime/` 是 non-canonical 生成态，禁止反向覆盖 canonical Markdown 控制文件。

不得因每次 conversation turn 或普通持久写入创建 Session。只有显式定义 bounded work-session 边界时才创建。

## Recovery order

1. 读取最近适用的 instruction 文件。
2. 读取根 `PROJECT_CONTROL.md`。
3. 如存在，读取 active `PHASE_CONTROL.md`。
4. 如存在，读取 active/latest `SESSION_CONTROL.md`、report 或 handoff。
5. 核查当前文件与 runtime evidence。

任何 summary 都不能替代 active MALTS version、当前文件或要求的 runtime probe。

## Discovery 与 Plan Recheck

- 普通启动只从当前工具相邻的 `MALTS_BOOT.md` 解析；交叉核对 registry、active pointer、`VERSION` 与可选的机器全局 / 恢复 `GLOBAL_BOOT.md`。任何不一致都按 split brain fail closed。
- Active Phase 拥有 plan path、revision、raw-byte SHA-256、recheck trigger/result 与 launch-review invalidation；root control 只保存索引，Session 只继承绑定。
- S3/S4 工作在新写入范围、launch review、verifier、recovery/rollback 或 final delivery 前，按事件运行只读 `long_workspace.py plan-recheck --require-active-plan`。`BLOCKED` 必须停止；该命令不会创建授权。

## Safety

- 将只读审查与状态修改执行分开。
- 不覆盖用户文件，不静默扩面。
- 未经独立授权，不使用 Git、网络、provider、Agent dispatch、依赖安装或破坏性清理。
- 不运行自动、周期、后台或普通使用触发的更新检查。
