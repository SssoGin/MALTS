# 更新 MALTS

MALTS 默认从经过独立审阅的当前仓库 checkout 更新。更新器不会执行 Git 拉取、后台发现更新或下载 Release 归档。在任何安装状态变更前，它先创建只供审阅的计划。

## 更新前

1. 完成或恢复所有未完成 lifecycle transaction。
2. 取得目标版本的当前仓库来源。
3. 验证 `MALTS_RELEASE.json`、`VERSION`，以及可用时的当前 Git tag。
4. 确认已有 lifecycle root 和每个已选工具根目录。
5. 需要时按工具自身正常流程备份用户拥有的配置。

不要从未验证文件夹更新。仓库身份不匹配、意外文件、缓存或 `.malts` 残留都会在计划阶段停止。

## 仓库更新审阅

在已审阅仓库来源中运行：

```powershell
.\scripts\Update-MALTS.ps1 `
  -RepositoryRoot (Get-Location).Path `
  -UseDefaultRoots `
  -Tool Codex
```

使用显式根目录：

```powershell
.\scripts\Update-MALTS.ps1 `
  -RepositoryRoot <REPOSITORY_ROOT> `
  -LifecycleRoot <LIFECYCLE_ROOT> `
  -Tool Codex `
  -ToolRootCodex <CODEX_ROOT> `
  -PlanPath <NEW_UPDATE_PLAN_PATH>
```

执行前审阅计划。它会显示活动与目标版本身份、选定投影、用户修改分类、迁移或清理动作、回滚动作和后置验证。

```powershell
.\scripts\Update-MALTS.ps1 `
  -Apply `
  -PlanPath <REVIEWED_UPDATE_PLAN_PATH> `
  -ExpectedPlanHash <REVIEWED_UPDATE_PLAN_SHA256>
```

## 版本迁移与冲突处理

稳定版本使用 `malts-v<version>`，隔离预览使用
`malts-v<version>-preview.<sequence>`。`malts-1.0.0-<hash>` 等已识别 legacy ID
只作为迁移输入；MALTS 不会原地改名，也不会把其物理路径当作当前 pointer。

更新会先 stage 并 prevalidate 目标，再切换 registry、active pointer、global boot 和已选工具投影。只有 post-validation 证明所有权威引用都不再指向旧版本后，才会清理旧版本。相同版本且精确一致时为 no-op；相同版本内容冲突或未绑定同名目录会在写入前失败。进程中断通过 transaction journal 继续或回滚。

## 可选离线归档更新

当更新来源必须是固定离线归档时，先明确验证并解出单一 `MALTS-<version>.zip`。随后以 `-ReleaseRoot <EXTRACTED_RELEASE_ROOT>` 调用解出内容中的更新器。该归档是明确选择的来源，不是普通更新器的依赖。

## 用户修改与清理

MALTS 会在变更前分类已有投影文件：

| 类别 | 含义 | 默认结果 |
|---|---|---|
| U0 | 缺失或与 MALTS 拥有内容完全一致 | 按计划替换或移除。 |
| U1 | 可合并的受管指令块 | 合并受管区块。 |
| U2 | 具有确定性证据的合并 | 仅在记录验证后合并。 |
| U3 | 用户拥有或归属不明确的修改 | 停止并等待明确用户决定。 |
| U4 | 敏感或不安全冲突 | 关闭式失败。 |

已知旧布局只在归属证据充分时迁移。未知、用户拥有或不明确的文件会保留或阻塞更新，不会被静默删除。

已验证更新还会把旧版来源中的绝对路径记录替换为当前无路径记录。不要手动编辑已安装版本。

## Repair 前先诊断

尝试 repair 前，用 lifecycle root 和全部已选工具根运行 `Invoke-MALTSLifecycle.ps1 -Command Doctor`。Doctor 只读，并会区分派生 boot/投影漂移与无效 core payload、manifest、registry 或 pointer 状态。

core 状态本地一致时，`DoctorRepairPlan` 可从活动版本限定派生 repair 目标，但该建议本身不是可执行变更。只有与已安装绑定精确一致的已验证来源才能生成可持久化的 executable repair plan；随后必须审阅其 hash，并作为独立授权 transaction 执行。

## 恢复

更新中断时，先检查或恢复 lifecycle transaction，再创建新的计划。registry、journal、回滚和残留行为见[生命周期](LIFECYCLE.md)。

## 更新后 Discovery

更新成功后，对每个已选 tool root 运行只读发现命令。所有 tool-local boot 必须解析到同一个新活动版本，并与 registry、active pointer、`VERSION` 及已配置的机器全局恢复 boot 一致。不得继续使用陈旧 tool boot 或猜测版本路径；repair 必须进入单独审阅的 lifecycle transaction。
