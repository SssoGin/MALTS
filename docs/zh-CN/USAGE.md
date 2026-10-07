# MALTS 2.0.0 使用指南

## 1. 选择工作模式

日常任务默认单 Agent。简单目标沿用项目规则；需要长期恢复时建立 Project/Phase/Task；只有明确授权且职责可分离时才委派。已采用 v2 的工作区以服务状态为准，未采用工作区先确认其现有合同，不自动迁移。

| 场景 | 原生 Skill | 输出与边界 |
|---|---|---|
| 轻量项目设置 | `malts-project-init` | 建立适用项目入口与目标；不隐式创建协作 |
| 重要目标/取舍未定 | `malts-grill-me-preflight` | 只读澄清；方法不增加审批权限 |
| 新长工作区或真实结构变化 | `malts-long-project-workspace-init` | 建立阶段边界；v2 初始化必须 Phase-ready |
| 当前 v2 Task/专题 | `malts-v2-task-workflow` | 有界上下文和对应 task/phase/artifact/recovery 合同 |
| 需要续接视图 | `malts-session-handoff` | 按需保全原文、生成并受控发布交接 |
| 任务后经验审阅 | `malts-project-retrospective-growth` | 基于证据的建议/已授权试用 |
| 已验证任务轻量检查 | `malts-single-agent-lightweight-growth` | 无信号时无操作；全局规则修改另受授权 |
| 已授权协作 | `malts-multi-agent-long-task-scheduling` | 明确职责、预算、资源与集成验收 |

## 2. 普通进入和计划

先核 Boot/discovery 与 workspace binding，再读当前队列和准确 Task。普通进入只查询当前事实，不扫描全历史或自动创建 Run/Session/Agent/Artifact。Phase 计划修改时对比目标、边界与实际计划字节；更新 revision 与受影响绑定，不更改无关任务。

Task scope 必须是所属 Phase 的 in_scope 子集，out_of_scope 不得相交。通过 `phase.bind-task` 绑定准确 Task revision 与 Phase revision；计划哈希一致只证明内容身份，不授执行权限。原生新长工作区需 `init`、`project.define`、`phase.define`、`phase.set-active` 后检查 `phase_ready=true`。

## 3. 授权与执行

复用同范围用户授权。MCP 客户端不能自行 mint Grant 或覆盖 Host-bound 字段；控制端按当前合同登记已有授权。执行前检查 Grant、budget、依赖、准入和未决效果。`request` 默认 dry-run，只检查请求形状，不评估实际可执行性；使用已审阅请求的 `--apply` 才调用服务。

受管文件更新保存原字节并绑定当前 SHA-256，避免陈旧内容覆盖。写入、真实调用、安装、委派与公开发布分别遵守它们的已授权范围。具体请求与返回字段见 [v2 操作说明](V2_PREVIEW_USAGE.md)。

## 4. 验收、暂停与恢复

先验证业务结果，再登记符合 criterion 方法与等级的证据。`task.accept` 仍检查当前版本、依赖、操作和 Host。VERIFYING 状态下需要修复时先用 `verification.rework`。查询 `task-verify` 不重写历史。一个 Task 完成不自动完成整个用户目标。

暂停期间不新建效果；检查原 pending_operations 和 pending_hosts。UNKNOWN 沿原操作对账，不能重放。取消确认和 PAUSED 不证明进程已退出。恢复核 epoch、检查点、已消费预算及后续新增成果；不恢复旧写权、Grant 或 Host。

## 5. 协作、成果、成长与交接

协作前声明可分离资源、实际宿主能力和累计预算，Worker 提供产物与不确定项；控制端验证整合。只观测配置不能证明真实执行身份或隔离。

成果以 Artifact owner、版本、关系和当前 Shared 证明复用。Growth 候选需来源、限定试用与未来观察，中性/有害结果保留并可退役；不要把局部成功直接写入永久 Prompt。交接保全用户手工内容，预览只是一份有界视图；发布前核来源令牌和目标前像。见[成果与状态合同](V2_STATE_CONTRACT.md)、[经验与 Skill](CAPABILITY_AND_SKILL_GOVERNANCE.md)及[交接](HANDOFF.md)。

## 6. 常见诊断

| 结果 | 含义与处理 |
|---|---|
| `NOT_APPLIED` / `NOT_EVALUATED` | 尚未执行，不是验证通过 |
| `NO_LONGER_PROVEN` | 当前证明失效；检查变化输入，不改历史 |
| `RECOVERY_REQUIRED` / `UNKNOWN` | 原效果待对账，不创建替代 ID |
| `STALE_PROCESS` | 加载代码与活动声明不一致；通过宿主正常重载再核入口 |
| `GRANT_SCOPE_MISMATCH` | 资源/效果不符；用控制端和既有授权检查精确范围 |
| `LIFECYCLE_TRANSACTION_OR_RECOVERY_PENDING` | 生命周期未结清；处理原事务，不自行删除锁 |

当前支持与未认证能力见[系统概览](SYSTEM_OVERVIEW.md)。

## 历史资产与采用

尚未采用 v2 的工作区是显式审阅采用的来源，不是另一套 v2 写者。核原有事实、writer、未知效果与备份后通过 v2 采用合同迁入。不得对已采用工作区运行旧初始化/重整。当前长期设置要求 phase_ready=true 及 Project/Phase/Task 服务。
