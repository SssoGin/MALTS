# MCP 配置检查与恢复

[English](../MCP_CONFIGURATION.md) · [安装](INSTALL.md) · [生命周期](LIFECYCLE.md) · [工作区迁址](MANAGEMENT_AND_RELOCATION.md)

MALTS 2.0.6 提供本文的配置对比与诊断入口，原有的 `mcp-config` 配置片段生成入口继续有效。

## 目的与维护职责

宿主根据保存的 Python 解释器、脚本路径、工作区状态库及 Project 参数启动 MALTS MCP 服务。安装更新可能改变活动代际，统一安装根可能改变生命周期位置，工作区迁址可能改变状态目录。因此，一份原本正确的宿主配置可能失效，而 MALTS 安装本体仍然健康。

MALTS 负责生成配置片段和检查可识别的条目；配置文件归宿主维护。检查不执行配置中的命令、不注册服务、不编辑该文件、不改变任务，也不授予权限。配置正确只是建立连接的一个前提，不是实际连接测试或业务验收。

## 对比指定条目

从所选工具的 `MALTS_BOOT.md` 及通过的 discovery 获取运行根。使用工作区经核验的状态目录及匹配的 Project ID。生成替换片段时，保留用户选择的解释器及明确的写入策略。

```powershell
$runtime = '<verified-MALTS_ROOT>'
python -B "$runtime/tools/malts_v2.py" mcp-config `
  --host deepseek-harness `
  --state-dir '<verified-state-directory>' `
  --resource-root '<workspace-root>' `
  --project-id '<project-id>' `
  --tool-root '<DeepSeek-Harness-tool-root>' `
  --check '<selected-profile>/cordis.patch.yml'
```

同一入口支持 `codex`、`claude`、`opencode`。落地条目使用其他名称时，指定 `--server-name`。对比前先验证所选状态库、资源根和 Project 的绑定；提供 `--tool-root` 时，由已核验的 discovery 确定目标活动运行根。对比保留未明确指定的解释器选择，允许宿主使用自己的 Python 环境。权限与授权设置的差异会显示，敏感授权值经过遮蔽；如何更改仍由用户明确决定。

退出码 0 表示所选条目一致且已检查引用处于当前状态；退出码 3 表示得到非当前结果，包括条目不存在；退出码 2 表示输入无效或命令失败。退出码 0 或生成成功都不授权执行。

## 诊断覆盖范围

`doctor` 在所提供的工具根下检查以下已知位置：

| 宿主 | 已知配置位置 | 支持的表示形式 |
|---|---|---|
| Codex | `config.toml` | TOML `mcp_servers` |
| Claude Code | 同级 `.claude.json`；工具根下的 `mcp.json` | JSON `mcpServers`，含可识别的项目配置段 |
| OpenCode | `opencode.json`；`opencode.jsonc` | JSON／JSONC `mcp`，支持注释和末尾逗号 |
| DeepSeek Harness | `profiles/<profile>/cordis.patch.yml` | 包含 `@deepseek-ai/dsh-mcp-client` 的 Cordis 插入补丁 |

生成的 Cordis JSON 即使带有独立 YAML 注释行，也无需额外解析器。块式 YAML 需要诊断所用 Python 环境中已有可选的 PyYAML。安全解析拒绝标签、锚点、别名、重复键及过深嵌套。解析器缺失时为 `UNSUPPORTED`，不能算检查通过；诊断不会自行安装依赖。不使用 PyYAML 时，核心 JSON／TOML 操作仍然可用。

项目级配置或自定义文件可通过精确位置纳入：

```powershell
python -B "$runtime/tools/malts_lifecycle.py" doctor `
  --lifecycle-root '<verified-lifecycle-root>' `
  --tool-root 'codex=<Codex-tool-root>' `
  --tool-root 'claude-code=<Claude-Code-tool-root>' `
  --tool-root 'opencode=<OpenCode-tool-root>' `
  --tool-root 'deepseek-harness=<DeepSeek-Harness-tool-root>' `
  --host-config 'claude=<workspace-root>/.mcp.json'
```

工具集合应与实际安装登记一致。单文件限 1 MiB，已知及显式文件合计限 64 个，profile 子项限 32 个，每个文件的条目数也有上限。链接及 reparse 路径被拒绝。不递归扫描磁盘，不宣称完整盘点任意位置的外部引用，也不宣称跨文件同时快照。报告保留已识别的 MALTS 条目、检查路径、指纹及相关差异；无关服务设置、环境变量值和凭据不进入报告。

## 理解结果

| 结果 | 含义与下一步 |
|---|---|
| `CURRENT` | 所检查条目及引用一致。实际宿主连接仍须另行验证。 |
| `VALID_OLDER_GENERATION` | 指向仍登记且存在的旧代际。应审阅更新，不等同于脚本缺失。 |
| `DIFFERENT` | 落地条目与所选绑定或权限策略有差异。逐项审阅差异。 |
| `INVALID` | 脚本、状态库或资源引用缺失，代际未登记，或项目／工作区绑定不一致。生成并审阅修正片段。 |
| `NOT_CONFIGURED` | 没有识别到所选条目。MCP 配置是可选的，不能把未配置当作检查通过。 |
| `UNSUPPORTED`／`CHECK_FAILED` | 格式、解析器、访问或有限检查未能确认结果。先处理该条件，再判断是否健康。 |

外部汇总报告用 `DRIFT` 表示变化、失效或旧代际条目，用 `UNVERIFIED` 表示格式不支持。安装信任结论另行报告。外部配置问题可使 `doctor` 为 `DEGRADED`，同时 `core_trust=LOCALLY_CONSISTENT`；这不能作为重装或回滚健康载荷的依据。`doctor-repair-plan` 的范围是安装受管理文件，不包括宿主所有的配置。

## 更新与迁址后的恢复

成功安装、更新或统一安装根后返回 `external_configuration` 提示。前向迁址 CLI 成功后也检查所选工具的已知位置，以及重复提供的 `--host-config HOST=ABSOLUTE_PATH` 文件，并使用原计划的新旧状态目录识别需要更新的引用。报告只列实际检查范围内的引用和生成参数。诊断失败保持已提交的生命周期／迁址结果，同时明确显示失败。

将建议片段与原宿主条目对照，保留用户选定的解释器、环境及权限策略。在对应授权内通过宿主支持的配置方式应用，重新加载客户端，并调用 MALTS 的只读入口核查。确认载入的运行根、Project 和状态绑定，再分别判断 Phase 是否就绪及是否获得执行授权。检查不会自动激活 Phase，也不修复不属于 MALTS 所有的文件。

## 项目 Markdown 编码

MALTS 的项目 Markdown 控制文件接受带或不带 BOM 的 UTF-8。校验器读取两种形式，BOM 是否存在不作为验收条件。不要仅为恢复被编辑器去掉的 BOM 而反复改写文档。模板可以保留自身编码，原始证据指纹仍对应具体字节。Skill 前置区、代码、脚本、JSON 和外部项目约定继续遵循各自编码要求。
