# 安装 MALTS

MALTS 默认从已验证的公开仓库安装。安装先审阅：第一条命令只写入计划；只有用户带上精确的已审阅计划哈希并指定 `-Apply` 后才会改变文件。

## 前置条件

- Windows 10 或更高版本
- PowerShell 5.1 或更高版本；推荐 PowerShell 7
- Python 3.11 或更高版本
- Codex、Claude Code、OpenCode 至少之一
- 位于每个已选工具根目录之外的 lifecycle root

lifecycle root 保存不可变 MALTS 安装代、活动代 registry、计划和事务状态。每个选定工具根目录只接收自己的投影和 boot pointer。

## 仓库安装（主要路径）

1. 打开公开仓库根目录。
2. 读取 `MALTS_RELEASE.json`，确认它的 `version` 与 `VERSION` 相同。
3. Git 元数据存在时，确认其中的 `release_tag` 与当前检出的 tag 相同。
4. 创建计划。

```powershell
.\scripts\Install-MALTS.ps1 `
  -RepositoryRoot (Get-Location).Path `
  -UseDefaultRoots `
  -Tool Codex
```

使用显式路径：

```powershell
.\scripts\Install-MALTS.ps1 `
  -RepositoryRoot <PUBLIC_REPOSITORY_ROOT> `
  -LifecycleRoot <LIFECYCLE_ROOT> `
  -Tool Codex `
  -ToolRootCodex <CODEX_ROOT> `
  -PlanPath <NEW_PLAN_PATH>
```

支持的 `-Tool` 值为 `Codex`、`ClaudeCode`、`OpenCode` 和 `AllIncluded`。

计划写入前，仓库会作为精确用户来源验证。任何意外文件、缓存、`.malts` 残留、身份文件缺失、版本不一致或源码树哈希不匹配都会在安装前停止。

## 审阅并执行

计划包含所选根目录、目标安装代身份、拟议变更、用户修改分类、迁移或清理动作、回滚与后置验证。执行前必须审阅。

```powershell
.\scripts\Install-MALTS.ps1 `
  -Apply `
  -PlanPath <REVIEWED_PLAN_PATH> `
  -ExpectedPlanHash <REVIEWED_PLAN_SHA256>
```

来源、根目录或计划发生变化都会使哈希失效。缺少或不匹配的哈希会在安装前失败。

## 可选离线归档

Release 页面可提供一个名为 `MALTS-<version>.zip` 的可选归档。仓库安装不需要它，安装器也绝不会自动下载它。

使用时，从同一已审阅公开来源/tag 取得 `scripts/Verify-MALTSBootstrap.ps1`，再验证并解出 ZIP：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Verify-MALTSBootstrap.ps1 `
  -ArchivePath .\MALTS-1.0.0.zip `
  -ExtractOutput <EXTRACTED_RELEASE_ROOT> `
  -Apply
```

然后从解出的 package 创建标准审阅计划：

```powershell
<EXTRACTED_RELEASE_ROOT>\lifecycle_artifact\payload\scripts\Install-MALTS.ps1 `
  -ReleaseRoot <EXTRACTED_RELEASE_ROOT> `
  -UseDefaultRoots `
  -Tool Codex
```

bootstrap verifier 会验证确定性 ZIP 结构、安全路径和解出的不可变 package，随后才写入最终解出目录。

## 首次使用

安装后，每个选定工具通过自己的 `MALTS_BOOT.md` pointer 解析活动不可变安装代。不要手动把 runtime 文件复制到项目中；请使用已安装的 `malts-*` Skill 入口。

另见[快速开始](GETTING_STARTED.md)、[生命周期](LIFECYCLE.md)和[安全](SECURITY.md)。
