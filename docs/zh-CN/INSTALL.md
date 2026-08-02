# 安装 MALTS

MALTS 安装先审阅。第一条命令只写入计划；只有你审阅计划并带上精确的已审阅计划哈希和 `-Apply` 后才会改变文件。

## 前置条件

- Windows 10 或更高版本
- PowerShell 5.1 或更高版本；推荐 PowerShell 7
- Python 3.11 或更高版本
- Codex、Claude Code、OpenCode 至少之一
- 位于每个已选工具根目录之外的 lifecycle root

lifecycle root 保存已安装的 MALTS 版本、registry 状态、计划和事务状态。每个选定工具根目录只接收自己的 adapter 文件和 boot pointer。

## 仓库安装（主要路径）

1. 打开仓库根目录。
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
  -RepositoryRoot <REPOSITORY_ROOT> `
  -LifecycleRoot <LIFECYCLE_ROOT> `
  -Tool Codex `
  -ToolRootCodex <CODEX_ROOT> `
  -PlanPath <NEW_PLAN_PATH>
```

支持的 `-Tool` 值为 `Codex`、`ClaudeCode`、`OpenCode` 和 `AllIncluded`。

计划写入前，仓库会作为精确来源验证。任何意外文件、缓存、`.malts` 残留、身份文件缺失、版本不一致或源码树哈希不匹配都会在安装前停止。

安装版本 ID 使用语义格式：v1.1.0 安装为 `malts-v1.1.0`。相同版本且内容完全一致时报告 `NO_OP`；相同版本对应不同内容，或存在未绑定的同名目录时，会在创建 transaction 状态前失败。

## 审阅并执行

计划包含所选根目录、目标版本身份、拟议变更、用户修改分类、迁移或清理动作、回滚与后置验证。执行前必须审阅。

```powershell
.\scripts\Install-MALTS.ps1 `
  -Apply `
  -PlanPath <REVIEWED_PLAN_PATH> `
  -ExpectedPlanHash <REVIEWED_PLAN_SHA256>
```

来源、根目录或计划发生变化都会使哈希失效。缺少或不匹配的哈希会在安装前失败。

## 可选离线归档

Release 页面可提供一个名为 `MALTS-<version>.zip` 的可选归档。普通安装不需要它，安装器也绝不会自动下载它。

使用时，从同一已审阅来源或 tag 取得 `scripts/Verify-MALTSBootstrap.ps1`，再验证并解出 ZIP：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Verify-MALTSBootstrap.ps1 `
  -ArchivePath .\MALTS-1.1.0.zip `
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

## 验证已安装 Runtime

用 lifecycle root 和每个已选工具根运行只读 doctor：

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 `
  -Command Doctor `
  -LifecycleRoot <LIFECYCLE_ROOT> `
  -ToolRootCodex <CODEX_ROOT> `
  -ToolRootClaudeCode <CLAUDE_CODE_ROOT> `
  -ToolRootOpenCode <OPENCODE_ROOT>
```

`doctor` 会报告精确 expected/observed locator、严重度、core trust 与建议命令。它始终只读，不会执行修复。需要 repair 时，必须使用与安装绑定精确一致的可信来源，另行创建 `DoctorRepairPlan` 审阅，再只执行已审阅计划的精确哈希。

lifecycle 操作还会保留有界审计记录（一份当前绑定以及最近的成功、失败/恢复和月度摘要）。详见[生命周期](LIFECYCLE.md)。

## 首次使用

安装后，每个选定工具通过自己的 `MALTS_BOOT.md` pointer 解析活动已安装版本。不要手动把 runtime 文件复制到项目中；请使用已安装的 `malts-*` Skill 入口。

使用只读发现命令验证绑定。它解析 tool boot，并交叉核对 lifecycle registry、active pointer、`VERSION` 与可选机器全局恢复 boot；任何不一致都会阻止使用。

另见[快速开始](GETTING_STARTED.md)、[生命周期](LIFECYCLE.md)和[安全](SECURITY.md)。
