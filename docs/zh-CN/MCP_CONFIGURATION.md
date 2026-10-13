# MCP 配置检查与恢复

[English](../MCP_CONFIGURATION.md) · [安装](INSTALL.md) · [生命周期](LIFECYCLE.md) · [工作区迁址](MANAGEMENT_AND_RELOCATION.md)

模型上下文协议（Model Context Protocol，MCP）让 Agent 宿主调用外部工具。MALTS 通过本机进程的标准输入输出（stdio）与 Python 服务通信，不需要开放网络监听端口。

MALTS 2.0.8 为所选宿主安装和更新必需的 `malts` MCP 服务；针对受管理和项目专用条目的配置对比与诊断入口继续有效。

## 目的与维护职责

宿主通过保存的解释器和固定入口启动受管理的 MALTS MCP 服务；服务解析当前安装，并逐次核查项目绑定。另行配置的项目专用端点保留明确的状态、项目及权限参数；这些引用可能在更新或重定位后失效，而安装核心仍然健康。

安装器在宿主文件内维护有指纹的 `malts` 条目，其余内容归宿主或用户所有。片段生成和只读检查不执行配置中的命令、不编辑文件、不改变任务，也不授予权限。配置一致、安装器的冷连接检查和业务验收分别说明不同结果。

## 自动安装与工作区使用

普通安装和更新命令自动配置 `malts` 条目，不需要为了完成安装而人工生成项目绑定。安装器仅管理这一条目和自己的解释器环境。审阅计划记录路径与指纹，不包含无关配置的值；已有设置、注释、模型账号和其他服务仍不属于其维护对象。用户修改受管理条目时会产生需要审阅的冲突。

固定入口 `runtime/mcp/mcp_launcher.py` 解析并核实所选宿主的活动代际。安装状态和工作流工具不依赖项目。项目工具明确传入当前工作区；服务每次请求核验其原生定位文件或采用绑定，再读取当前状态库，不创建全局数据库，也不保留供所有调用共享的“当前项目”。工作区重定位后，服务通过核实后的定位文件读取新库。

| 工具 | 用途 |
|---|---|
| `malts_installation` | 查询已安装版本和服务就绪状态 |
| `malts_workflow` | 读取任务、阶段、成果或恢复中的一种工作流 |
| `malts_entry_status` | 核查工作区绑定和就绪状态，按需检查安装包 |
| `malts_actions` | 读取所选项目合同和当前只读策略 |
| `malts_context` | 读取指定任务的当前状态、依赖和恢复上下文 |
| `malts_verify_task` | 复核当前验收证据，保留历史记录 |

例如，调用 `malts_context` 时传入 `{"workspace":"<当前项目的绝对工作区路径>","task_id":"<实际任务ID>"}`。服务启动目录已经等于核实后的工作区时可使用默认值，否则应传入路径。项目尚未启用 MALTS 时返回绑定错误，不创建数据库；先使用已经授权的项目初始化或采用流程。

标准端点只读。安装不创建 Grant、不启动 Agent、不激活阶段，也不绕过控制端检查。明确限定的写端点继续使用既有项目、任务、执行者策略和运行授权；下方配置片段对比章节适用于这些端点。冷连接检查证明新启动服务可用，实际宿主尚未重新加载时仍须重连或重启。卸载只移除受管理 `malts` 条目，保留其他设置及本机恢复资料。

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

生成的 Cordis JSON 即使带有独立 YAML 注释行，也无需额外解析器。安装的 MCP 环境包含解析块式 YAML 的 PyYAML；另行选用的诊断解释器也需要该解析器。安全解析拒绝标签、锚点、别名、重复键及过深嵌套。解析器缺失时为 `UNSUPPORTED`，不能算检查通过；诊断不会自行安装依赖。不使用 PyYAML 时，核心 JSON／TOML 操作仍然可用。

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
| `NOT_CONFIGURED` | 没有识别到所选条目。必需的受管理条目缺失，或所选项目专用条目尚未配置；不能把未配置当作安装成功。 |
| `UNSUPPORTED`／`CHECK_FAILED` | 格式、解析器、访问或有限检查未能确认结果。先处理该条件，再判断是否健康。 |

外部汇总报告用 `DRIFT` 表示变化、失效或旧代际条目，用 `UNVERIFIED` 表示格式不支持。安装信任结论另行报告。外部配置问题可使 `doctor` 为 `DEGRADED`，同时 `core_trust=LOCALLY_CONSISTENT`；这不能作为回滚健康载荷的依据。生命周期修复按审阅计划维护安装器拥有的 `malts` 条目，不自动覆盖未经管理的项目专用配置。

## 更新与迁址后的恢复

成功安装、更新或统一安装根后返回 `external_configuration` 提示。前向迁址 CLI 成功后也检查所选工具的已知位置，以及重复提供的 `--host-config HOST=ABSOLUTE_PATH` 文件，并使用原计划的新旧状态目录识别需要更新的引用。报告只列实际检查范围内的引用和生成参数。诊断失败保持已提交的生命周期／迁址结果，同时明确显示失败。

将建议片段与原宿主条目对照，保留用户选定的解释器、环境及权限策略。在对应授权内通过宿主支持的配置方式应用，重新加载客户端，并调用 MALTS 的只读入口核查。确认载入的运行根、Project 和状态绑定，再分别判断 Phase 是否就绪及是否获得执行授权。检查不会自动激活 Phase，也不修复不属于 MALTS 所有的文件。

## 项目 Markdown 编码

MALTS 的项目 Markdown 控制文件接受带或不带 BOM 的 UTF-8。校验器读取两种形式，BOM 是否存在不作为验收条件。不要仅为恢复被编辑器去掉的 BOM 而反复改写文档。模板可以保留自身编码，原始证据指纹仍对应具体字节。Skill 前置区、代码、脚本、JSON 和外部项目约定继续遵循各自编码要求。

## 所选项目的配置

普通只读使用默认继承安装器维护的用户级 `malts` 入口，每次项目请求明确传入工作区。固定项目、独立解释器或环境、受限写策略可能需要专用端点；这些要求仍然有效，同名条目不自动等于冗余。

运行 Doctor 时明确选择当前工作区：

```powershell
python -B "$runtime/tools/malts_lifecycle.py" doctor `
  --lifecycle-root '<已核实的生命周期根>' `
  --tool-root 'codex=<Codex工具根>' `
  --workspace '<当前工作区绝对路径>'
```

检查共享安装时传入实际登记的完整宿主集合。重复 `--workspace` 可选择多个目录，重复 `--host-config HOST=ABSOLUTE_PATH` 可选择自定义文件。普通安装和更新脚本分别接受对应的 `-Workspace`、`-HostConfig` 数组。升级计划绑定所选项目文件指纹，拒绝预览后的修改，并在安装后报告同一检查范围。这些参数用于检查，不自动编辑项目配置。

对 Codex，MALTS 读取用户文件，以及已识别 Git 项目根到所选工作区的 `.codex/config.toml`；没有 Git 根时以所选工作区为边界。最近的已检查层优先，嵌套表按字段合并。仅含 `enabled=false` 的局部表也可能禁用继承服务。报告保留逐文件合法性，另用 `effective_configuration` 说明来源、端点模式、代际、启用状态、同名覆盖、环境变量键名及写策略标记。同版本标准端点和专用端点仍有不同参数合同；不同服务器名称可以并存。

这一结论是**项目受信任时的磁盘配置层解析**。Profile 文件、命令行覆盖、受管要求和宿主实际加载的连接无法观测，报告明确保留 `NOT_VERIFIED`。其他宿主继续支持有界的显式文件检查，其项目层优先级不从 Codex 类推。不可读或不支持的层不能证明有效连接健康。优先级依据见 [Codex 官方配置说明](https://developers.openai.com/codex/config-basic/)。

## 保留专用端点

为 `mcp-config` 增加 `--stable`，并传入已经核实的 `--tool-root`，可生成稳定的固定项目配置片段。片段使用 `runtime/mcp/mcp_launcher.py --project-bound`，保留原 Project、状态库、资源根、actor、authority、Task、dispatch 及写策略参数。四种宿主配置格式均支持这一启动模式。启动器在每个新进程启动时核实活动代际；所选解释器仍须具备 MCP 依赖。项目明确选择的解释器不会被全局环境替换。

专用端点继续提供既有固定项目接口，不成为通用写服务，也不产生 Grant。状态目录变化仍须明确核对固定绑定；稳定入口解决的是代际路径维护，不是数据库迁址。已经运行的旧进程须通过宿主获得授权的停止或重连流程切换加载版本。

## 审阅项目配置变更与恢复

内置的保留式编辑目前支持明确选择的 Codex 项目 TOML 文件。其他宿主使用稳定配置片段及其正式配置方式；没有宣称已验证这些宿主的自动项目文件编辑。

```powershell
python -B "$runtime/tools/malts_lifecycle.py" mcp-project-plan `
  --lifecycle-root '<已核实的生命周期根>' `
  --tool-root '<Codex工具根>' `
  --workspace '<所选工作区>' `
  --config-path '<所选工作区>/.codex/config.toml' `
  --server-name 'malts' --strategy 'stable-project'
```

`stable-project` 只改变启动参数，保留解释器、环境、权限、无关设置、注释和编码。用户明确选择 `inherit-global` 后，才移除所选同名项目条目及其子表，以继承全局入口。该方案拒绝不同解释器、专用环境或自定义设置、禁用条目、受保护内容捕获以及写入、actor、Task 等限定策略；这些入口须保留，或另行审阅宿主变更。不删除整个文件，不以禁用条目代替继承，不重命名服务器，也不重新采用工作区。

先审阅计划，再增加 `--out '<新的本机计划.json>' --apply` 保存。计划和恢复前像可能含本机敏感内容，不能公开。通过 `mcp-project-execute --plan '<计划.json>' --expected-plan-hash '<已审阅哈希>' --apply` 应用。Windows 独占文件句柄与指纹保护预览后的内容；已检查的上级和用户配置层也必须一致。重复已完成的变更返回无变化结果。

操作中断后使用 `mcp-project-recover --lifecycle-root '<根>' --operation-id '<原操作ID>'`，审阅后应用同一操作的恢复。该命令的 `--restore` 仅在当前文件仍与记录的变更后像完全相同时恢复前像；后续用户修改保留并交由审阅，不覆盖新内容，不换ID重放不确定效果。恢复资料位于 `runtime/mcp/project-operations/<操作ID>`。

磁盘变更后重新连接所选宿主。标准入口通过 `malts_installation` 和面向既有工作区的 `malts_entry_status` 核实实际加载；保留的专用入口通过其固定项目工具核实。冷连接、宿主加载、治理就绪和业务执行权限分别报告。

## 所选引用与安装代际退役

更新计划、Doctor 和 `retire-plan` 接受同一组 `--workspace`、`--host-config`。退役计划绑定所选文件并说明覆盖范围。所选配置仍引用待退役代际时阻止规划；所选文件不可读或格式不支持时也停止。规划后的相关修改使执行失效。稳定端点引用启动器，不直接绑定待退役的版本目录。

这不证明已经发现全机所有项目或进程。未选择的项目文件和仍运行的旧进程不在证明范围，进程引用覆盖标为 `NOT_OBSERVED`。退役前应在授权范围内检查并处置有关宿主实际进程及已知项目输入。活动代际、工作区状态、证据和恢复资料保持受保护。
