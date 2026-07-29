# 更新 MALTS

MALTS 默认从经过独立审阅的当前公开仓库更新。更新器不会执行 Git 拉取、后台发现更新或下载 Release 归档。在任何安装状态变更前，它先创建只供审阅的计划。

## 更新前

1. 完成或恢复所有未完成 lifecycle transaction。
2. 取得目标版本的当前公开仓库来源。
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
  -RepositoryRoot <PUBLIC_REPOSITORY_ROOT> `
  -LifecycleRoot <LIFECYCLE_ROOT> `
  -Tool Codex `
  -ToolRootCodex <CODEX_ROOT> `
  -PlanPath <NEW_UPDATE_PLAN_PATH>
```

执行前审阅计划。它会显示活动与目标安装代身份、选定投影、用户修改分类、迁移或清理动作、回滚动作和后置验证。

```powershell
.\scripts\Update-MALTS.ps1 `
  -Apply `
  -PlanPath <REVIEWED_UPDATE_PLAN_PATH> `
  -ExpectedPlanHash <REVIEWED_UPDATE_PLAN_SHA256>
```

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

已验证更新还会把含绝对来源 locator 的 legacy 安装代来源 envelope 替换为当前无路径 envelope。不要手动编辑安装代。

## 恢复

更新中断时，先检查或恢复 lifecycle transaction，再创建新的计划。registry、journal、回滚和残留行为见[生命周期](LIFECYCLE.md)。
