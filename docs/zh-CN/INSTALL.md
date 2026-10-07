# 安装 MALTS 2.0.0

## 1. 仓库安装（主要路径）

已验证安装路径是 Windows，Python 3.11 或更高版本与 PowerShell；推荐 PowerShell 7。v2 受保护内容当前使用 Windows 当前用户 DPAPI。Codex、Claude Code、OpenCode 至少选择一个；DeepSeek Harness 的专用入口见[适配说明](../../adapters/deepseek-harness/README.zh-CN.md)。安装不调用模型，也不自动迁移项目。

通常使用[公开仓库](https://github.com/SssoGin/MALTS)的已审阅 checkout。确认 remote、commit/tag 和 `MALTS_RELEASE.json`，其中版本须与 `VERSION` 的 2.0.0 一致。安装器验证精确目录与内容身份；不要在分发目录添加缓存或业务文件。

## 2. 先审阅，再执行计划

在仓库根目录运行：

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool Codex
```

三端一起安装可用 `-Tool AllIncluded`；它只包含 Codex、Claude Code 和 OpenCode。使用自选根时传入 `-LifecycleRoot` 及相应 `-ToolRootCodex`、`-ToolRootClaudeCode`、`-ToolRootOpenCode`，并指定不存在的 `-PlanPath`。lifecycle root 必须在工具配置根之外。

第一步只生成计划，输出其路径和 SHA-256。审阅来源、目标、个人内容合并、恢复前像与风险后，把输出的真实值代入：

```powershell
$plan = '<reviewed-plan-path>'
$hash = '<reviewed-plan-sha256>'
.\scripts\Install-MALTS.ps1 -Apply -PlanPath $plan -ExpectedPlanHash $hash
```

来源、目标或计划漂移会拒绝。相同已安装内容可返回 `NO_OP`；相同版本的不同内容必须通过 lifecycle 的正式归并及恢复流程，不能覆盖代际目录。

## 3. 验证入口

读取所选工具配置根的 `MALTS_BOOT.md`，解析 `MALTS_ROOT`，再运行：

```powershell
$runtime = '<MALTS_ROOT-from-tool-boot>'
$toolRoot = '<selected-tool-config-root>'
python -B "$runtime/tools/malts_lifecycle.py" discover --tool-root $toolRoot
python -B "$runtime/tools/malts_v2.py" capabilities
```

discovery 须为 PASS，registry、active pointer 和 VERSION 须一致。`capabilities` 是接口声明；实际 Task 和宿主结果仍须验证。只读 Doctor 方法见[生命周期](LIFECYCLE.md)。重启或重载宿主后，以实际 Skill/MCP 连接核实加载，不能由文件存在推断。

## 4. 可选离线归档

需要离线来源时使用 `MALTS-2.0.0.zip`。从同一审阅来源取得 `scripts/Verify-MALTSBootstrap.ps1`，先检查归档，再显式解出：

```powershell
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip -ExtractOutput '<new-extraction-root>' -Apply
```

从解出载荷中的安装脚本传入 `-ReleaseRoot '<extracted-package-root>'`，按同一计划/哈希流程安装。不要直接复制 payload 到活动根。详见[归档说明](RELEASE_ARTIFACT.md)和[快速开始](GETTING_STARTED.md)。
