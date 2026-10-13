# 安装 MALTS

用户可以选择将 MALTS 安装到所需 Agent 工具。共享核心提供项目工作、接续、验证和经验工作流，各工具使用自己的原生入口。当前版本：**2.0.6**。安装遵循先审阅计划再执行，不调用模型、不安装宿主程序，也不自动采用已有项目。

## 前置条件

- Windows、Python 3.11+ 和 PowerShell，推荐 PowerShell 7；当前 v2 受保护内容使用 Windows 当前用户 DPAPI。
- 至少已安装一端：**Codex、Claude Code、OpenCode 或 DeepSeek Harness**。
- 已审阅的公开仓库 checkout，或明确核验的离线包。
- 生命周期根位于所有所选工具配置根之外；新计划文件位于分发树之外。

生命周期根保存安装代际、注册表、计划与事务恢复；工具根保存原生投影和 `MALTS_BOOT.md`，不再复制核心实现。应选择实际宿主配置根；下方使用当前用户的通用默认位置，不含维护者个人机器路径。

宿主应已能独立使用。MALTS 增加工作流和状态/恢复适配，不配置 Provider 账号或购买模型访问。受当前用户 DPAPI 保护的证据需要相应 Windows 用户身份及恢复条件；复制加密状态到另一账号不等于恢复。

使用较短、明确且无含义不明链接/保护重叠的根。生命周期规划在修改前检查支持的路径边界；仓库能打开不代表生成路径足够短。遇限应缩短目标生命周期/工具根，不能绕过检查。

## 仓库安装（主要路径）

使用已审阅的[公开仓库](https://github.com/SssoGin/MALTS) checkout，核实际 remote/ref，并确认 `MALTS_RELEASE.json` 与 `VERSION` 都为 2.0.6。`main` 上文档修订可保持相同版本，但具有独立、准确的源树身份。安装器核所选真实树；业务文件或缓存不能混入。

| 宿主 | 入口 | 范围 |
|---|---|---|
| Codex | `Install-MALTS.ps1 -Tool Codex` | 所选 Codex 根 |
| Claude Code | `Install-MALTS.ps1 -Tool ClaudeCode` | 所选 Claude Code 根 |
| OpenCode | `Install-MALTS.ps1 -Tool OpenCode` | 所选 OpenCode 根 |
| DeepSeek Harness | `Install-MALTS.ps1 -Tool DeepSeekHarness` | 所选 Harness 工具根，默认共享生命周期 |

四端共享正式安装的计划示例：

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool AllIncluded
```

共享正式安装使用一个计划；**`AllIncluded` 选择 Codex、Claude Code、OpenCode、DeepSeek Harness 四端。** 显式路径使用 `-LifecycleRoot`、对应的 `-ToolRootCodex`、`-ToolRootClaudeCode`、`-ToolRootOpenCode` 或 `-ToolRootDeepSeekHarness`，以及 `-PlanPath`。

### DeepSeek Harness 安装

Harness 与 Codex、Claude Code、OpenCode 共用一套正式安装，使用相同的安装入口。四端完整安装计划：

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool AllIncluded
```

默认共享生命周期根为 `~/.agent-system/lifecycle`，Harness 工具根为 `~/.dsh`。需要明确工具路径时使用 `-ToolRootDeepSeekHarness`。各端的账号、会话和模型配置仍各自保留，不复制或合并到 MALTS 安装根。

安装命令仅保存计划并返回路径和哈希。核对来源、四端实际工具根、个人指令合并和恢复前像，再执行下方步骤。已存在的正式安装使用更新流程；安装不能通过手改 Boot、注册或活动代际完成。此过程安装 MALTS 适配，Harness 应用和模型由其自身安装流程管理。

## 审阅并执行

Install 命令创建共享安装计划并输出准确路径和哈希。审阅四端目标、来源身份、所属、个人内容合并、可恢复前像与后置检查，再用实际输出值执行：

```powershell
.\scripts\Install-MALTS.ps1 -Apply -PlanPath '<reviewed-plan-path>' -ExpectedPlanHash '<reviewed-plan-sha256>'
```

来源、目标或计划变化会拒绝执行。相同版本和内容可返回 `NO_OP`；相同版本但字节不同，走保留快照的生命周期 `finalize` 审阅事务，不能覆盖当前代际或自行加版本。见[生命周期](LIFECYCLE.md)。

| 实际结果 | 含义 | 下一步 |
|---|---|---|
| 输出计划/哈希 | 已有可审阅准备 | 核准确来源、根、合并及恢复决定 |
| NO_OP | 准确目标安装已存在 | 核发现/加载，不强制重写 |
| 执行成功 | 计划事务达到已检查结果 | 回读 registry/Boot/投影与原生加载 |
| 漂移/冲突拒绝 | 审阅前置已不相符 | 保留现场，重新审阅计划或来源决定 |
| 中断事务 | 效果/激活可能未结 | 检查/恢复原操作 |

不能用手工复制或成功标签替换实际失败。安装与项目采用分开，新运行时安装后，旧项目仍可能需要明确迁移。

## 可选离线归档

现行 Release 附件为 `MALTS-2.0.6.zip`。同版本重新发布对应独立核验包，来源提交和 SHA-256 见 Release 说明；离线安装前核准确下载修订。GitHub 自动源码归档对应现行版本标签。现行标签、核验仓库和 MALTS 上传包应标识同一来源修订，但归档布局不同。

```powershell
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.6.zip
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.6.zip -ExtractOutput '<new-extraction-root>' -Apply
```

校验器取自相应审阅来源。使用解压载荷的生命周期入口和 `-ReleaseRoot '<extracted-package-root>'`，再执行同样的计划/哈希流程。Harness 使用相同生命周期入口和 ReleaseRoot，并提供该安装注册的全部工具根。不能将载荷直接复制进活动代际。见[发布归档](RELEASE_ARTIFACT.md)。

## 核验已安装运行时

读取所选工具的准确 Boot，并使用其 MALTS_ROOT：

```powershell
$runtime = '<MALTS_ROOT-from-tool-boot>'
$toolRoot = '<selected-tool-config-root>'
python -B "$runtime/tools/malts_lifecycle.py" discover --tool-root $toolRoot
python -B "$runtime/tools/malts_v2.py" capabilities
```

要求 discovery PASS，注册、活动指针、代际身份和 VERSION 一致。Doctor 核安装信任与漂移，不自动修复。四端共享安装提供全部实际工具根：

```powershell
$shared = Join-Path $env:USERPROFILE '.agent-system/lifecycle'
.\scripts\Invoke-MALTSLifecycle.ps1 `
  -Command Doctor -LifecycleRoot $shared `
  -ToolRootCodex (Join-Path $env:USERPROFILE '.codex') `
  -ToolRootClaudeCode (Join-Path $env:USERPROFILE '.claude') `
  -ToolRootOpenCode (Join-Path $env:USERPROFILE '.config/opencode') `
  -ToolRootDeepSeekHarness (Join-Path $env:USERPROFILE '.dsh')
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

## 可选的旧代际清理

安装和普通更新保留旧代际。清理不再使用的 `retiring` 代际须单独明确请求，通过[生命周期退役流程](LIFECYCLE.md#清理不再使用的安装代际)核对精确目标、当前引用和回收脚本，取得恢复证据后才移除注册记录。活动版本和项目状态保持；不能直接删除已注册目录来代替退役，也不自动清空回收站或改用永久删除。

## 工作区管理数据与迁移

普通新工作区通过 `workspace-init` 默认将任务库、受管证据和恢复资料置于所属 `.malts` 目录，显式外置布局继续受支持。安装更新不搬动已有项目。健康已采用库可经只读计划、备份恢复、当前效果审查和正式前向切换重定位；新 epoch 不恢复旧授权或验收，也不自动激活 Phase。旧库、外部历史引用和来源封存按实际依赖保留。操作与限制见[工作区管理与状态库重定位](MANAGEMENT_AND_RELOCATION.md)。

## 安装完整性与恢复核验

深度入口核验将安装用户载荷与可复现解释器缓存分开：源码、metadata和哈希链仍须精确匹配，当前解释器缓存只在能由已核实源码复现时接受。其他缓存版本、损坏缓存、额外文件和源码变化均停止检查，不自动删缓存或修改manifest。`entry-status --verify-package` 与MCP `malts_entry_status` 返回相同安全原因码。恢复结果分别说明登记效果与外部写者覆盖；格式相容、业务验收、隔离恢复与外部写者静默是不同结论。分阶段保全、UTF8计划和隔离恢复命令见[管理与恢复核验](MANAGEMENT_AND_RELOCATION.md)。

CPython的marshal序列化会因模块加载后的不可变对象共享和引用编号产生字节差异。缓存验证以有界结构摘要对照已核实源码的重新编译结果，绑定每个代码字段、常量、字节码、文件名和行号／异常表，同时检查头部、来源metadata和实际缓存文件哈希。未知格式、循环引用、可变容器及尾随数据均拒绝，不加载或执行缓存代码。返回的派生缓存清单与保持原值的用户载荷身份分开，它是当前本地核验结果，不增加新的包信任来源。结构格式覆盖CPython3.11–3.13；其他解释器缓存格式拒绝。

## 检查宿主 MCP 配置

MALTS 2.0.6 提供只读配置诊断。MALTS 安装成功，并不能证明宿主单独保存的 MCP 客户端配置仍指向存在的脚本和所选工作区状态库。升级或迁址后，参见 [MCP 配置检查与恢复](MCP_CONFIGURATION.md)。条目需要修正时，通过 `mcp-config` 重新生成片段，再人工审阅落地配置。

配置检查不启动客户端、不修改宿主文件，也不授予执行权限。应用经审阅的配置时，应保留用户选定的 Python 解释器和明确的权限设置；实际 MCP 连接须另行验证。
