# 更新 MALTS

更新所选 MALTS 安装，同时保全项目工作和个人配置。沿用的更新、所属、诊断与恢复栏目适用于整个产品。

## 更新前

分别核已安装身份、所选来源、工作区绑定、用户修改、相关写者和未决效果，保留恢复材料。更新器不会执行 Git 拉取、不自动下载 ZIP、不调用 Provider，也不隐式迁移项目。当前版本保持 **2.0.0**。

## 仓库更新审阅

选择经审阅仓库版本后创建计划：

```powershell
.\scripts\Update-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool Codex
```

可选 ClaudeCode、OpenCode、指定组合，或仅涵盖前三端的 AllIncluded。核来源、目标、所属、合并、快照与后置检查，再用实际输出值执行：

```powershell
.\scripts\Update-MALTS.ps1 -Apply -PlanPath '<reviewed-plan-path>' -ExpectedPlanHash '<reviewed-plan-sha256>'
```

### DeepSeek Harness 更新

使用已有实际生命周期与 `.dsh` 根。通用当前用户布局示例：

```powershell
$harnessRoot = Join-Path $env:USERPROFILE '.dsh'
$harnessLifecycle = Join-Path $env:USERPROFILE '.agent-system/deepseek-harness-lifecycle'
$planPath = Join-Path $env:TEMP ('malts-harness-plan-' + [guid]::NewGuid().ToString('N') + '.json')
.\scripts\Invoke-MALTSLifecycle.ps1 `
  -Command Plan -Operation update `
  -RepositoryRoot (Get-Location).Path `
  -LifecycleRoot $harnessLifecycle `
  -ToolRootDeepSeekDesktop $harnessRoot `
  -OutPath $planPath -Apply
```

Plan -Apply 仅保存计划。审阅哈希后使用[安装说明](INSTALL.md)的 Execute 命令；只有明确审阅的同版本内容修正才使用 `-Operation finalize`。Harness 不属于 Install/Update 的 AllIncluded。

## 版本迁移与冲突处理

来源与已安装内容完全相同时可返回 NO_OP；相同版本但不同字节须走当前 v2 finalize 审阅事务，保留目标快照与准确来源绑定。不能手改代际、先删安装、改 VERSION 绕过冲突或重写旧发布。main 文档修订仍不同于原 v2.0.0 标签/ZIP。

## 可选离线归档更新

核验并安全解压所选固定归档，使用 ReleaseRoot 及相同计划/哈希流程。Harness 使用独立通用生命周期入口。原归档保持原文档，仓库提供后续同版本说明。见[发布归档](RELEASE_ARTIFACT.md)。

## 用户修改与清理

| 分类 | 含义 | 处理 |
|---|---|---|
| U0 | 缺失或准确 MALTS 所属 | 仅执行计划内替换/移除 |
| U1 | 可合并的标记指令块 | 保留区块外个人内容 |
| U2 | 确定且有依据的合并 | 验证记录的合并 |
| U3 | 用户所属或不明确 | 保留并等待具体决定 |
| U4 | 敏感或不安全冲突 | 拒绝执行 |

适配变化不授权整文件替换。清理与更新分开，须核所属、引用和恢复价值；未知对象和必要快照保留。

## Repair 前先诊断

对共享生命周期全部实际根运行只读 Doctor；Harness 单独诊断。先核核心信任，再选修复来源。DoctorRepairPlan 仅准备审阅，Execute 使用审阅哈希。不能改 journal/锁或权限绕过前置失败。

## 更新 Workspace Control

安装不采用项目。v2 采用前审阅当前事实、映射、写者、未知效果和备份。已采用工作区使用当前任务服务，保留 binding/source-seal，不运行旧 Markdown 初始化或重组写入。当前 Core 仅读写 Schema69；改版本字段不构成开发库迁移。

## 恢复

沿原事务和当前恢复判断处理。项目恢复产生新 epoch，对账备份之后的工作、未知效果和预算消耗，不复活旧 Grant/Host/验收或旧运行权威。跨用户 DPAPI 恢复、任意写者排除和 GUI 模型取消仍未认证。

## 更新后 Discovery

受管指令声明准确 MALTS_BOOT_PATH；即使 Boot 与指令文件不同目录，也使用该指针。重载各所选宿主，解析准确 Boot，执行 discovery/Doctor 并核真实原生 Skill/MCP。保留 AGENTS.override.md 与区块外内容；安装不创建或删除该 override。工作区 binding 单独核。交付说明版本、准确内容身份、实际检查、恢复位置和未解决项。见[生命周期](LIFECYCLE.md)。
