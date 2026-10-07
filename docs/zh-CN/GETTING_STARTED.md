# MALTS 2.0.0 快速开始

## 1. 安装并确认入口

按[安装说明](INSTALL.md)从已审阅仓库创建计划，再以计划哈希执行。读取所选工具根的 `MALTS_BOOT.md` 并运行 discovery。版本、活动代际与 registry 一致后重载宿主，确认原生 Skill/MCP 的实际连接。

## 2. 从用户目标开始

向 Agent 说明目标、修改范围和验收条件，例如：“使用 MALTS 管理这次模块迁移；先检查当前项目，保留用户数据；完成修改并验证，提交发布另行决定。”

已有工作区先读适用项目指令、workspace binding 和当前 Task。新长期工作可选择 `malts-long-project-workspace-init`；目标不清时使用 `malts-grill-me-preflight`。简单任务无需建立长期库。Skill 选择不构成委派、调用费用或发布授权。

## 3. 核实当前状态

将真实发现和绑定结果代入：

```powershell
$runtime = '<verified-MALTS_ROOT>'
$workspace = '<selected-workspace>'
python -B "$runtime/tools/malts_v2.py" workspace --workspace $workspace
# 以下 state 与 Task ID 来自绑定和当前队列，不猜路径。
$state = '<verified-state-dir>'
python -B "$runtime/tools/malts_v2.py" governance-context --state-dir $state --project-id '<project-id>'
python -B "$runtime/tools/malts_v2.py" task-queue --state-dir $state --project-id '<project-id>'
python -B "$runtime/tools/malts_v2.py" context --state-dir $state --task-id '<task-id>'
```

这些查询只读，不初始化、不创建 Session/Agent/Artifact、不授予执行权限。原生 v2 工作区明确选择其 state 目录；已采用工作区使用 business workspace 的 binding。

## 4. 完成第一个任务

控制端建立目标、scope、criterion、已有授权及预算，执行后核查实际产物，并用适用证据完成 `task.accept`。之后 `task-verify` 返回 `CURRENT_EVIDENCE_VALID` 才能继续援引当前完成证明；业务验收仍要覆盖用户目标。

需要可直接运行的隔离文件演示，参阅 [v2 操作说明](V2_PREVIEW_USAGE.md#v2-start)。该示例不调用模型，不证明业务收益。长期工作区还必须有当前 Project 定义、真实计划和 ACTIVE Phase；`init` 成功不等于 `phase_ready=true`。

## 5. 中断与后续

中断后继续同一 Task/Operation/Run，先对账 UNKNOWN 与 Host，核检查点、当前版本和预算。按需生成交接；不要把重新初始化当作续接。具体操作见[使用指南](USAGE.md)、[交接](HANDOFF.md)和[生命周期](LIFECYCLE.md)。
