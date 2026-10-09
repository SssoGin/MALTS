# 安装 MALTS

用户可以选择将 MALTS 安装到所需 Agent 工具。共享核心提供项目工作、接续、验证和经验工作流，各工具使用自己的原生入口。当前版本：**2.0.0**。安装遵循先审阅计划再执行，不调用模型、不安装宿主程序，也不自动采用已有项目。

## 前置条件

- Windows、Python 3.11+ 和 PowerShell，推荐 PowerShell 7；当前 v2 受保护内容使用 Windows 当前用户 DPAPI。
- 至少已安装一端：**Codex、Claude Code、OpenCode 或 DeepSeek Harness**。
- 已审阅的公开仓库 checkout，或明确核验的离线包。
- 生命周期根位于所有所选工具配置根之外；新计划文件位于分发树之外。

生命周期根保存安装代际、注册表、计划与事务恢复；工具根保存原生投影和 `MALTS_BOOT.md`，不再复制核心实现。应选择实际宿主配置根；下方使用当前用户的通用默认位置，不含维护者个人机器路径。

宿主应已能独立使用。MALTS 增加工作流和状态/恢复适配，不配置 Provider 账号或购买模型访问。受当前用户 DPAPI 保护的证据需要相应 Windows 用户身份及恢复条件；复制加密状态到另一账号不等于恢复。

使用较短、明确且无含义不明链接/保护重叠的根。生命周期规划在修改前检查支持的路径边界；仓库能打开不代表生成路径足够短。遇限应缩短目标生命周期/工具根，不能绕过检查。

## 仓库安装（主要路径）

使用已审阅的[公开仓库](https://github.com/SssoGin/MALTS) checkout，核实际 remote/ref，并确认 `MALTS_RELEASE.json` 与 `VERSION` 都为 2.0.0。`main` 上文档修订可保持相同版本，但具有独立、准确的源树身份。安装器核所选真实树；业务文件或缓存不能混入。

| 宿主 | 入口 | 范围 |
|---|---|---|
| Codex | `Install-MALTS.ps1 -Tool Codex` | 所选 Codex 根 |
| Claude Code | `Install-MALTS.ps1 -Tool ClaudeCode` | 所选 Claude Code 根 |
| OpenCode | `Install-MALTS.ps1 -Tool OpenCode` | 所选 OpenCode 根 |
| DeepSeek Harness | `Install-MALTS.ps1 -Tool DeepSeekHarness` | 所选 Harness 工具根，默认共享生命周期 |

首次安装的可选计划示例：

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool Codex
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool ClaudeCode
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool OpenCode
```

这些是可选择的首次安装计划，只执行自己选择的一项。`-Tool Codex,ClaudeCode` 选择两端；**`AllIncluded` 选择 Codex、Claude Code、OpenCode、DeepSeek Harness 四端。** 显式路径使用 `-LifecycleRoot`、对应的 `-ToolRootCodex`、`-ToolRootClaudeCode`、`-ToolRootOpenCode` 或 `-ToolRootDeepSeekHarness`，以及 `-PlanPath`。

### DeepSeek Harness 安装

Harness 与其他宿主使用同一安装入口及默认共享生命周期，只选择需要的工具。首次仅安装 Harness 的计划示例：

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool DeepSeekHarness
```

首次建立四端共享安装时使用 `-Tool AllIncluded`。`-ToolRootDeepSeekHarness` 指定实际 Harness 配置根，`ToolRootDeepSeekDesktop` 作为原调用方式的别名保留。默认工具根为 `~/.dsh`，共享安装根为 `~/.agent-system/lifecycle`。各宿主的账号、会话和模型设置仍由各自管理。

已有三端安装不能通过普通更新或手改 Boot 变为四端安装。Harness 已单独安装时，先使两套安装的完整来源身份一致，再按[生命周期合并流程](LIFECYCLE.md#合并已有安装)迁移；尚未安装时，应选择保全现有用户内容的明确新装方案。普通更新继续要求注册工具集合不变。

Install 命令保存计划并返回路径／哈希，不直接激活。核对所选根、所属、个人内容合并和前像，再执行下方“审阅并执行”步骤。此操作安装 MALTS 适配；Harness 应用、账号和模型另行管理。

每个所选宿主保留自己的 Boot 和原生入口，共用一份已核验活动代际。`AllIncluded` 选择四端，选择单端不隐式安装其余端；需要独立部署时仍可明确选择不同生命周期根。计划文件保存在源码仓库外，并核对输出中的实际工具映射。

## 审阅并执行

普通 Install 命令创建计划并输出准确路径和哈希。审阅所选目标、来源身份、所属、个人内容合并、可恢复前像与后置检查。前三端使用实际输出值执行：

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

现行 Release 附件为 `MALTS-2.0.0.zip`。同版本重新发布对应独立核验包，来源提交和 SHA-256 见 Release 说明；离线安装前核准确下载修订。GitHub 自动源码归档对应现行版本标签。现行标签、核验仓库和 MALTS 上传包应标识同一来源修订，但归档布局不同。

```powershell
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip -ExtractOutput '<new-extraction-root>' -Apply
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

## 可选的旧代际清理

安装和普通更新保留旧代际。清理不再使用的 `retiring` 代际须单独明确请求，通过[生命周期退役流程](LIFECYCLE.md#清理不再使用的安装代际)核对精确目标、当前引用和回收脚本，取得恢复证据后才移除注册记录。活动版本和项目状态保持；不能直接删除已注册目录来代替退役，也不自动清空回收站或改用永久删除。
