# QUALITY_GATE

> 任务进入 DONE 前，相关质量门必须满足，或明确标记为不适用。

## 需求覆盖

- [ ] 任务能对应到用户目标或已批准项目任务。
- [ ] 完成标准清楚。
- [ ] 非目标和排除项被遵守。
- [ ] 已检查用户后续变更。
- [ ] 对非琐碎任务或项目启动，已提醒 MALTS 原生 Grill-Me 启动盘问，已记录接受 / 拒绝 / N/A，并把已接受决策同步到 `PROJECT_CONTROL`。

## 范围与所有权

- [ ] 修改文件在允许范围内。
- [ ] 没有修改禁止文件。
- [ ] 遵守资源锁。
- [ ] 没有覆盖未知的用户修改。
- [ ] 如果任务属于协议、模板、检查清单、适配器或文档查漏补缺，已同时检查并同步 Codex、Claude Code、OpenCode，除非用户明确排除某个工具。
- [ ] 独立任务 / 工具产物保持本地边界，除非用户明确要求提升为系统入口、共享工具或全局索引项。
- [ ] 新增、删除、移动、重命名文件夹或改变目录用途时，已更新相关索引、手册、恢复文档，或记录 N/A 原因。
- [ ] 项目工作区根目录没有滞留误安装的全局 skills / 工具副本；如发现这类副本，已迁入正确的 Agent 全局路径、记录为有意项目产物，或验证后清理。
- [ ] 如果同时存在 `PROJECT_CONTROL.md` 和用户可读的本地化控制文件，已记录两者职责和最近同步状态。
- [ ] 需要任务或阶段报告时，`WORK_TASK_REPORT.md` 已存在；叙述正文使用用户/项目语言，完整翻译镜像只在明确要求时生成。
- [ ] 文档同步任务已记录源 / 目标文件、同步方向和模型 / 成本策略。

## Artifact Lifecycle Gate

- [ ] 除非已有精确 enrollment preview、已审阅 indexes、operation ID 和显式 `--apply` 授权，否则 workspace 保持 `NOT_ENROLLED`。
- [ ] Project control 只保留紧凑 enrollment/index pointers；详细记录属于对应 Phase、Session、Shared 或 Archive registry。
- [ ] `artifact audit`、`validate`、`maintain`、`compact`、`recover` 只沿已声明的有界引用读取，没有递归扫描未声明 payload tree。
- [ ] 每个 Artifact mutation 都先 dry-run；apply 时具有精确 operation ID、workspace lock、persisted journal、full-state preconditions 以及 atomic replacement/rollback 证据。
- [ ] Artifact mutation 没有移动/删除 payload、调用 VCS、创建 Session、静默接管 legacy directory 或重建已声明但缺失的 index。
- [ ] Promotion/supersession 保持唯一 current Shared authority，并更新所有已声明 active reference；否则 fail closed。
- [ ] 含 `UNRESOLVED` 记录的 enrolled owner 没有被关闭；stale lock/journal 只报告精确人工审阅动作且绝不自动删除。

## Workspace Cross-Control Consistency Gate

- [ ] 全新工作区使用精确 CURRENT，默认 `single_phase`；受支持的旧输入被显式分类，entry、validation、recovery、maintenance 或 installation update 不会静默重整。
- [ ] Project/Phase/Session 事实各有唯一 Markdown owner；workspace schema/profile/index 与 coordination authority 各有唯一 runtime owner。CURRENT contract report/handoff 是 derived/on-demand view；legacy workspace layout current projection binding 保持严格。
- [ ] 没有把 `phase-boundary-review` operation status 当成 review outcome、persistence、decision 或 authorization；只有 `record-phase-boundary-review` 持久化记录，后续 mutation authorization 仍然独立。
- [ ] 完整 Phase-control SHA-256 与 normalized boundary/review/recovery hash 在 canonical authority 与 machine binding 间一致；任何已刷新 view 都绑定当前精确字节且不成为 authority。
- [ ] Structural、binding、deterministic-consistency、maintenance-warning 与 advisory-semantic finding 分层报告；safety-critical drift 阻断受影响 mutation，CURRENT contract derived-view drift 保持局部 warning/reconcile。
- [ ] Recovery 顺序固定为 active Session checkpoint、active Phase recovery、显式绑定的 terminal Phase、Project recovery；不存在 latest historical Session fallback。
- [ ] Workspace/coordination mutation 使用 dry-run、精确 expected hash、唯一 operation ID、共享 `runtime/workspace_transaction.lock.json`、`runtime/workspace_transactions/` 与锁后 preimage 复核；Artifact transaction path/code 保持不变。
- [ ] Interrupted workspace transaction 只能通过精确 journal-hash `recover-workspace-transaction` review/apply 恢复；恢复失败时保留 lock/journal evidence。

## 验证证据

- [ ] 至少使用了一种直接验证方法。
- [ ] 验证结果已记录。
- [ ] 证据等级已标明。
- [ ] 失败或跳过的检查已说明。
- [ ] 如果修改了交接、状态、适配或迁移包文档，已用当前包元数据和运行时版本证据做语义新鲜度检查。
- [ ] 文档同步任务在批量翻译 / 同步前已使用脚本或结构化检查，或记录了跳过原因。
- [ ] 关键协议语义没有只凭低成本 Worker 输出就接受、合并或标记已验证。
- [ ] 如果关键语义缺少高能力 / 主控批准，结果标记为 `Draft` 或 `Unverified`，而不是完成。
- [ ] 对 GUI、视觉、覆盖层或强交互任务，已记录用户视觉确认或等价视觉证据。
- [ ] 如果发生上下文饱和、压缩或中断，外部恢复状态已更新。
- [ ] 长任务继续被表达为有边界的轮次和恢复点，而不是固定一次性运行时长承诺。
- [ ] 新窗口从有界 `workspace-entry --task-class CONTEXT_RECOVERY` 与当前 owner 文件继续；不会仅按 recency 选择 report、handoff、history 或 Session。

## 多 Agent 分派门

- [ ] 建议或启用多 Agent 前，已评估任务类型和难度。
- [ ] 只有在多 Agent 能降低风险、提高独立验证质量、支持无冲突并行工作或改善可恢复性时，才建议多 Agent。
- [ ] 如果任务是 S0/S1，或合并成本高于收益，已使用单 Agent，或记录了升级原因。
- [ ] 路由决定明确为 `0`、`1` 或 `N`；没有强加固定角色链或最低角色数量。
- [ ] 角色名只描述职责；模型与 effort 按任务难度、风险、预算和当前运行时证据选择。
- [ ] 如果用户要求使用多 Agent，分派前已展示启动审阅包。
- [ ] 启动审阅包列出总体目标、总计划、每个计划 Agent、模型名称或模型策略、任务和简要计划。
- [ ] 已询问用户是否要指定子 Agent 模型，并展示可接受的模型指定格式。
- [ ] 用户在任何真实子 Agent 分派前已明确回复 `确认运行`。
- [ ] 审阅期间对模型、范围或批次的修改已同步到任务契约。
- [ ] 分派前，Result Contract 已记录启动审阅引用和已批准批次 ID。
- [ ] `requested`、`recommended`、`configured`、`effective` 路由选择已分开记录。
- [ ] runtime effort ID、归一化推理等级和展示标签没有混为一谈。
- [ ] 仅有配置、CLI help 或接口发现时，没有标记为 `effective_verified`。
- [ ] 每个 fallback 都记录 hard/soft 约束处理、原因、binding 状态和 usage evidence。
- [ ] `N > 1` 同时受已批准 Agent 数、契约并发上限、生效运行时容量，以及只读/不冲突 scope 或具有当前 lease/fencing 的有效 typed resource Admission 限制。
- [ ] `agent_route_planner.py` 与 `result_controller.py` 仅作为建议 / 校验组件，没有冒充真实分派证据。
- [ ] 如果使用 Codex peer task，已记录为 `codex-peer-task` / `delegation_mode=peer-task`，优先使用当前任务工作区，且没有描述成原生 `spawn_agent`。
- [ ] Peer-task lifecycle 证据覆盖 PLANNED、RETURNED、Main 接受 / 返工 / 阻塞直至 ARCHIVED；除非明确允许替换，返工复用原任务。
- [ ] 已验证 peer-task 的 hard model / effort / no-fallback 约束及生效工作区 / 模型证据；没有把任务创建或配置本身当成生效证明。
- [ ] 真实 Agent/provider 验证明确标为 `G4 PASS`、`G4 FAIL` 或 `G4 NOT RUN`；component 测试没有冒充 G4。
- [ ] Agent 分派日志、任务契约、返回报告和 Agent 反馈日志在任务 ID、角色、运行时 Agent ID（如有）、模型策略和 Main Controller 决策上互相一致。

## 无人值守自动继续门

- [ ] 长任务开始时，已询问用户是否启用无人值守自动继续。
- [ ] 只有用户明确授权后，才使用无人值守继续。
- [ ] 如果用户没有明确授权，未启动、安排或暗示无人自动运行。
- [ ] `PROJECT_CONTROL` 已记录允许范围、禁止操作、多 Agent 权限、模型策略、轮次 / 时间上限、停止条件和报告要求。
- [ ] 每个无人值守轮次只持久化确有变化的 owner-local recovery/state；仅在授权包要求时刷新按需工作报告。
- [ ] 开始下一轮无人值守前已检查停止条件。
- [ ] 授权包未提前确认的新多 Agent 批次，已停下进行启动审阅并等待 `确认运行`。

## 交付完整性

- [ ] 声称的交付物真实存在。
- [ ] 交付物命名清楚。
- [ ] 面向用户的说明与实际文件或命令一致。
- [ ] 结果可用，不依赖隐藏步骤。

## 风险透明

- [ ] 剩余风险已列出。
- [ ] 未完成事项已列出。
- [ ] 假设已标记为假设。
- [ ] 猜测没有被包装成事实。

## 成长卫生

- [ ] 验证后、最终交付前已评估无写入 L1 Growth Routing Gate；`NO_OUTPUT` 保持静默，其他 route 均已面向用户可见。
- [ ] 没有把仅写入报告的 Growth 条目当作用户可见结果的替代品。
- [ ] L1 没有进行持久化写入；L2 项目维护和 L3 系统晋升仍各自保留独立授权门。
- [ ] 有意义时记录可复用经验候选。
- [ ] 一次性细节没有写入长期记忆。
- [ ] 拟写入规则具备触发条件、执行动作、检查方法和适用边界。
- [ ] 对非琐碎任务、用户纠正、恢复轮次或失败，面向用户的报告中说明了成长复盘结果。
- [ ] 如果外部长期记忆服务或全局记忆目标不可用，候选已保留在本地，并在报告中说明没有真正写入长期记忆。

## 用户报告

- [ ] 已准备清晰的用户结果；只有用户请求或确有必要时才生成 durable `WORK_TASK_REPORT.md` 视图，且不把它当作 lifecycle authority。

## Workspace v5 与兼容门禁

- [ ] 只有显式审阅一步重整后才使用 CURRENT workspace/Result contract；否则受支持的旧兼容输入保持字节不变；没有静默重整或用户可见版本链。
- [ ] 重复、无变化的 `workspace-entry` 有界、零历史读取、零写入、不创建 Phase/Session/Agent/Artifact/coordination state，且文件字节/时间戳不变。
- [ ] `single_phase` 无 coordination 开销；每个 `resource_admission` writer 都绑定当前 Phase hash、有效 Admission、未过期 lease、精确 fencing token 和已清除的受影响 quarantine domain。
- [ ] 不相交 locator 可继续；重叠/父子路径/alias、exclusive/queued/isolate-required capability、stale executor 与 `UNKNOWN` 副作用按确定性 admission/quarantine/reconcile 规则处理。
- [ ] safety-critical drift 只对受影响 authority/resource 标为 `BLOCKED`；CURRENT contract report/handoff 派生漂移为 `WARNING` 并局部刷新，legacy workspace layout 投影漂移保留严格兼容行为。
- [ ] Attempt 失败未自动重试或升级 Task/Phase 终态；`max_authorized_rounds` STOP 已生效。
- [ ] 外部副作用有 typed observations/counted units；有限硬预算下 UNKNOWN dispatch/outcome/charge 已 fail closed。
- [ ] workspace 事务恰好提交一次，含 preimage/recovery 证据；未宣称瞬时原子可见。
- [ ] `scoped-readiness` 与 `refresh-project-instructions` 仅按文档使用；无 marker 自定义文件未被动过。
- [ ] Workspace/coordination writer 共享唯一写锁，并在获锁后复核精确 preimage；没有 stale writer 提交。
