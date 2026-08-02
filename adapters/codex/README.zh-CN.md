# Codex 适配器

此适配器从已验证的 MALTS 安装使用，提供 Codex 在运行时需要的项目指令模板、角色定义和工作流。

## 通过生命周期安装

1. 先验证下载包，再解包。
2. 为 Codex 工具根创建并审阅生命周期计划。
3. 只执行已审阅计划的精确 hash。

生命周期会把 Codex 投影写入所选工具根，并记录精确 generation 身份。不要手工复制这些文件。

## 预览验证

preview launch 必须把 preview 内的 Codex discovery root 作为 `CODEX_HOME`，并使用
preview 内的 `HOME`、`USERPROFILE`、`APPDATA`、`LOCALAPPDATA`、`TEMP` 和
`TMP`。启动全新且有界的 Codex 进程，验证它发现预期
`malts-v<version>-preview.<sequence>` 和一个代表性 `malts-*` Skill。当前进程
cache 不能作为证据。

无法证明进程隔离时，报告 Codex `BLOCKED`；绝不回退真实 Codex root。未用真实
工具集成验证的预览会被如实记录，不能视为完整合格。

## 诊断与验证

按场景用隔离或已安装 Codex root 运行 lifecycle `Doctor`。Doctor 只读，报告精确
boot/投影漂移，不修复 adapter。任何 repair 都需要独立可信 `DoctorRepairPlan`、精确
plan hash 审阅、transaction 执行，以及新的全新进程发现检查。

正常 discovery 从 Codex 相邻的 `MALTS_BOOT.md` 开始，再要求 registry、
`active_generation.json`、generation identity 与 active `VERSION` 完全一致。已配置的机器
全局 `GLOBAL_BOOT.md` 是独立 recovery cross-check。缺失、格式错误、reparse-point、过期
或 split-brain 状态均为 `BLOCKED`，不得 fallback 到其他 root。

long-project Phase 存在 active plan 时，应在既定 launch、write-scope、delegated-return、
verifier、recovery、rollback 与 final-delivery 边界运行只读 `plan-recheck`。当 native
sub-agent routing 无法满足明确的 hard model/effort constraint 时，Codex 可以把用户可见
task/thread 作为 MALTS 治理的 `codex-peer-task`。优先使用当前任务工作区，记录 effective
route evidence，返工复用同一 task，禁止静默 fallback，并且只在 accepted 或其他 terminal
closure 后归档。

## 包含的运行时材料

- `AGENTS.example.md`：项目使用的 MALTS managed instruction block。
- `.codex/agents/`：可选的 MALTS 角色定义。
- `.codex/config.toml`：Codex 适配器配置。
- `workflows/`：启动、验证、复盘和 smoke check 指引。

参见[用户安装指南](../../docs/INSTALL.md)与[用户使用指南](../../docs/USAGE.md)。
