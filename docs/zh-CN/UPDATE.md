# 更新 MALTS

更新选择核验来源，通过审阅事务改变所选安装，按计划保全项目工作和用户配置，不自动选择新目标或迁移项目。当前版本：**2.0.0**。

## 更新前

分别核已安装身份、所选来源、工作区绑定、用户修改、相关写者和未决效果，保留恢复材料。更新器不会执行 Git 拉取、不自动下载 ZIP、不调用 Provider，也不隐式迁移项目。当前版本保持 **2.0.0**。

比较活动来源类型/哈希、拟用仓库/包身份及实际工具根，判断是常规版本更新还是同版本内容归并。事务快照和项目备份具有不同恢复用途，均保留所需材料。

改变共享安装前核相关写者和未结效果，不能以 PAUSED 或缺回应证明进程停止。仅文档更新可复用未变代码行为结果，但新载荷身份、说明与安装对应关系须当前核验。

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

核验并安全解压所选固定归档，使用 ReleaseRoot 及相同计划/哈希流程。Harness 使用独立通用生命周期入口。按声明来源提交和校验值选择现行归档，留存旧包属于历史输入，不能当作最新指南。见[发布归档](RELEASE_ARTIFACT.md)。

## 用户修改与清理

| 分类 | 含义 | 处理 |
|---|---|---|
| U0 | 缺失或准确 MALTS 所属 | 仅执行计划内替换/移除 |
| U1 | 可合并的标记指令块 | 保留区块外个人内容 |
| U2 | 确定且有依据的合并 | 验证记录的合并 |
| U3 | 用户所属或不明确 | 保留并等待具体决定 |
| U4 | 敏感或不安全冲突 | 拒绝执行 |

适配变化不授权整文件替换。清理与更新分开，须核所属、引用和恢复价值；未知对象和必要快照保留。

U1 适用于可识别混合所属指令块，更新 MALTS 内容并保留标记外个人正文。U3 是已修改或不明确、不能自动判安全替换的文件，应解决具体所属/处理，不能重贴 U0。U4 保持不安全或敏感冲突的拒绝边界。

有快照是恢复能力，不是丢弃未审阅用户修改的权限。审阅合并结果并重载真实宿主；不能仅因一个生成桥需修复就恢复整份旧配置，否则可能删除后续个人变化。

更新后保留代际、快照和证据可能仍服务恢复/历史。独立清理决定前盘点；版本年代和激活成功都不能证明原件已无用途。

## Repair 前先诊断

对共享生命周期全部实际根运行只读 Doctor；Harness 单独诊断。先核核心信任，再选修复来源。DoctorRepairPlan 仅准备审阅，Execute 使用审阅哈希。不能改 journal/锁或权限绕过前置失败。

## 更新 Workspace Control

安装不采用项目。v2 采用前审阅当前事实、映射、写者、未知效果和备份。已采用工作区使用当前任务服务，保留 binding/source-seal，不运行旧 Markdown 初始化或重组写入。当前 Core 仅读写 Schema69；改版本字段不构成开发库迁移。

采用须保全原始目标、当前阶段/任务责任、产物和未决效果。映射将导入历史声明与当前验证验收分开；旧 DONE 行不能仅因解析成功提升为当前业务证明。

服务操作前核采用 binding、所选状态根和 epoch，保留历史来源 seal 与采用后工作。状态库不可用时，以明确缺口走经审阅当前前向恢复，不能移除采用标记重启旧写入。

安装恢复与项目恢复不必同目标或 journal，各沿自己身份恢复后核对应关系。安装事务不静默赋予新项目预算或验收。

## 恢复

沿原事务和当前恢复判断处理。项目恢复产生新 epoch，对账备份之后的工作、未知效果和预算消耗，不复活旧 Grant/Host/验收或旧运行权威。跨用户 DPAPI 恢复、任意写者排除和 GUI 模型取消仍未认证。

## 更新后 Discovery

受管指令声明准确 MALTS_BOOT_PATH；即使 Boot 与指令文件不同目录，也使用该指针。重载各所选宿主，解析准确 Boot，执行 discovery/Doctor 并核真实原生 Skill/MCP。保留 AGENTS.override.md 与区块外内容；安装不创建或删除该 override。工作区 binding 单独核。交付说明版本、准确内容身份、实际检查、恢复位置和未解决项。见[生命周期](LIFECYCLE.md)。
