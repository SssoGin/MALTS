# 安装 MALTS

用户可以选择将 MALTS 安装到所需 Agent 工具。共享核心提供项目工作、接续、验证和经验工作流，各工具使用自己的原生入口。当前版本：**2.0.0**。安装遵循先审阅计划再执行，不调用模型、不安装宿主程序，也不自动采用已有项目。

## 前置条件

- Windows、Python 3.11+ 和 PowerShell，推荐 PowerShell 7；当前 v2 受保护内容使用 Windows 当前用户 DPAPI。
- 至少已安装一端：**Codex、Claude Code、OpenCode 或 DeepSeek Harness**。
- 已审阅的公开仓库 checkout，或明确核验的离线包。
- 生命周期根位于所有所选工具配置根之外；新计划文件位于分发树之外。

生命周期根保存安装代际、注册表、计划与事务恢复；工具根保存原生投影和 `MALTS_BOOT.md`，不再复制核心实现。应选择实际宿主配置根；下方使用当前用户的通用默认位置，不含维护者个人机器路径。

## 仓库安装（主要路径）

使用已审阅的[公开仓库](https://github.com/SssoGin/MALTS) checkout，核实际 remote/ref，并确认 `MALTS_RELEASE.json` 与 `VERSION` 都为 2.0.0。`main` 上文档修订可保持相同版本，但具有独立、准确的源树身份。安装器核所选真实树；业务文件或缓存不能混入。

| 宿主 | 入口 | 范围 |
|---|---|---|
| Codex | `Install-MALTS.ps1 -Tool Codex` | 所选 Codex 根 |
| Claude Code | `Install-MALTS.ps1 -Tool ClaudeCode` | 所选 Claude Code 根 |
| OpenCode | `Install-MALTS.ps1 -Tool OpenCode` | 所选 OpenCode 根 |
| DeepSeek Harness | `Invoke-MALTSLifecycle.ps1 -ToolRootDeepSeekDesktop` | 独立 Harness 生命周期和工具根 |

前三端的计划示例：

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool Codex
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool ClaudeCode
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool OpenCode
```

这些是可选择的计划示例，只执行自己选择的计划。`-Tool Codex,ClaudeCode` 选择两端；**`AllIncluded` 仅包括 Codex、Claude Code、OpenCode，不包括 Harness。** 显式路径使用 `-LifecycleRoot`、对应 `-ToolRootCodex`、`-ToolRootClaudeCode` 或 `-ToolRootOpenCode`，以及 `-PlanPath`。

### DeepSeek Harness 安装

独立生命周期使用当前身份 `deepseek-harness`。公开参数 `ToolRootDeepSeekDesktop` 为兼容保留，指当前 Harness 配置根。使用实际 `.dsh` 根与独立 Harness 生命周期，不能用旧 Desktop 身份或路径替代。

在仓库根生成并保存审阅计划：

```powershell
$harnessRoot = Join-Path $env:USERPROFILE '.dsh'
$harnessLifecycle = Join-Path $env:USERPROFILE '.agent-system/deepseek-harness-lifecycle'
$planPath = Join-Path $env:TEMP ('malts-harness-plan-' + [guid]::NewGuid().ToString('N') + '.json')
.\scripts\Invoke-MALTSLifecycle.ps1 `
  -Command Plan -Operation install `
  -RepositoryRoot (Get-Location).Path `
  -LifecycleRoot $harnessLifecycle `
  -ToolRootDeepSeekDesktop $harnessRoot `
  -OutPath $planPath -Apply
```

这里 `Plan -Apply` **仅保存计划文件，不激活安装**；不带 `-Apply` 时输出 dry-run 计划。核输出的 `plan_hash`、来源身份、根目录、合并分类和快照，再执行：

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 `
  -Command Execute -PlanPath '<reviewed-plan-path>' `
  -ExpectedPlanHash '<reviewed-plan-sha256>' -Apply
```

Plan 通过 `-ToolRootDeepSeekDesktop` 选择 Harness；通用生命周期的 `-Tool deepseek-harness` 选择器用于 PreviewPlan。不要将 Harness 传给 Install/Update 的三端 `-Tool` 参数。此过程安装 MALTS 适配，不安装 DeepSeek Harness、本地模型、密钥或 Provider 订阅。

## 审阅并执行

普通 Install 命令创建计划并输出准确路径和哈希。审阅所选目标、来源身份、所属、个人内容合并、可恢复前像与后置检查。前三端使用实际输出值执行：

```powershell
.\scripts\Install-MALTS.ps1 -Apply -PlanPath '<reviewed-plan-path>' -ExpectedPlanHash '<reviewed-plan-sha256>'
```

来源、目标或计划变化会拒绝执行。相同版本和内容可返回 `NO_OP`；相同版本但字节不同，走保留快照的生命周期 `finalize` 审阅事务，不能覆盖当前代际或自行加版本。见[生命周期](LIFECYCLE.md)。

## 可选离线归档

Release 可选包 `MALTS-2.0.0.zip` 保留原标签内容。`main` 后续同版本文档修订不改写该不可变归档。当前指南使用仓库；明确需要固定离线输入时使用归档。

```powershell
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip -ExtractOutput '<new-extraction-root>' -Apply
```

校验器取自相应审阅来源。使用解压载荷的生命周期入口和 `-ReleaseRoot '<extracted-package-root>'`，再执行同样的计划/哈希流程。Harness 使用独立生命周期入口并传 ReleaseRoot。不能将载荷直接复制进活动代际。见[发布归档](RELEASE_ARTIFACT.md)。

## 核验已安装运行时

读取所选工具的准确 Boot，并使用其 MALTS_ROOT：

```powershell
$runtime = '<MALTS_ROOT-from-tool-boot>'
$toolRoot = '<selected-tool-config-root>'
python -B "$runtime/tools/malts_lifecycle.py" discover --tool-root $toolRoot
python -B "$runtime/tools/malts_v2.py" capabilities
```

要求 discovery PASS，registry、pointer、identity 和 VERSION 一致。Capabilities 声明接口，不证明实际模型行为。Doctor 只诊断安装信任和漂移，不自动修复。Harness 示例：

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 `
  -Command Doctor -LifecycleRoot $harnessLifecycle `
  -ToolRootDeepSeekDesktop $harnessRoot
```

共享生命周期的 Doctor 应提供其全部实际所选工具根。宿主重载后核原生 Skill/MCP 发现，不能仅检查文件存在。当前 Harness 原生证据限 Windows Desktop 0.2.0-rc.2；CLI/Web 和 GUI 模型取消另有边界。

## 核验工作区生命周期

安装只改变所选安装/工具根，不迁移或初始化项目。已有工作区用已验证运行时检查：

```powershell
python -B "$runtime/tools/malts_v2.py" workspace --workspace '<project-workspace>'
```

已采用结果须 binding 有效后才能使用当前任务服务。采用前工作区保持原经验证合同，直至明确采用；不能向已采用工作区运行旧初始化。见[状态合同](V2_STATE_CONTRACT.md)。

## 首次使用

按目标选择已安装工作流：项目设置、长期工作区、当前任务、交接、复盘或已授权协作。普通进入不创建无关实体。先读[快速开始](GETTING_STARTED.md)，再读[使用指南](USAGE.md)。Harness 加载及配置限制见[适配说明](../../adapters/deepseek-harness/README.md)。
