# Claude Code 适配器

此适配器从已验证的 MALTS 安装使用，提供 Claude Code 项目所需的指令模板、角色定义和命令指引。

## 通过生命周期安装

1. 先验证下载包，再解包。
2. 为 Claude Code 工具根创建并审阅生命周期计划。
3. 只执行已审阅计划的精确 hash。

生命周期会把 Claude Code 投影写入所选工具根，并记录精确 generation 身份。不要手工复制适配器文件。

## 预览验证

preview launch 必须把 preview 内的 Claude Code discovery root 作为
`CLAUDE_CONFIG_DIR`，并使用 preview 内的 `HOME`、`USERPROFILE`、`APPDATA`、
`LOCALAPPDATA`、`TEMP` 和 `TMP`。启动全新且有界的 Claude Code 进程，验证它发现
预期 `malts-v<version>-preview.<sequence>` 和一个代表性 `malts-*` Skill。当前进程
cache 不能作为证据。

无法证明进程隔离时，报告 Claude Code `BLOCKED`；绝不回退真实 Claude Code root。
未用真实工具集成验证的预览会被如实记录，不能视为完整合格。

## 诊断与验证

按场景用隔离或已安装 Claude Code root 运行 lifecycle `Doctor`。Doctor 只读，报告
精确 boot/投影漂移，不修复 adapter。任何 repair 都需要独立可信
`DoctorRepairPlan`、精确 plan hash 审阅、transaction 执行，以及新的全新进程发现
检查。

正常 discovery 从 Claude Code 相邻的 `MALTS_BOOT.md` 开始，再要求 registry、
`active_generation.json`、generation identity 与 active `VERSION` 完全一致。已配置的机器
全局 `GLOBAL_BOOT.md` 是独立 recovery cross-check。缺失、格式错误、reparse-point、过期
或 split-brain 状态均为 `BLOCKED`，不得 fallback 到其他 root。

long-project Phase 存在 active plan 时，应在既定 launch、write-scope、delegated-return、
verifier、recovery、rollback 与 final-delivery 边界运行只读 `plan-recheck`。Codex 专用的
`codex-peer-task` route 不是可移植 Claude Code API；应使用 Claude Code 的可见 native
dispatch，并保留等价 route、return、acceptance 与 closure evidence。

## 包含的运行时材料

- `CLAUDE.example.md`：项目使用的 MALTS managed instruction block。
- `.claude/agents/`：可选的 MALTS 角色定义。
- `.claude/commands/`：启动、验证、复盘和 smoke check 指引。

参见[用户安装指南](../../docs/INSTALL.md)与[用户使用指南](../../docs/USAGE.md)。
