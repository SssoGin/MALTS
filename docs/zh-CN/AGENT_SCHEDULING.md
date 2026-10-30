# 真实 Agent 调度

[English](../AGENT_SCHEDULING.md) · [使用指南](USAGE.md) · [核心设计](CORE_DESIGN.md)

MALTS 通过可信控制端、所选项目状态与实际 Agent 宿主组织委派工作。本文说明如何选择执行路线、核对执行证据、分配有限预算，以及恢复原派发。

## 1. 用途与执行路线

MALTS 保存用户目标、Task 修订、依赖、权限、累计派发预算和证据，宿主实际执行 Agent。控制端连接两者，并负责整合与最终验收。选用调度 Skill 不会自动派出 Agent，也不会开启后台运行。

| 路线 | 实际执行入口 | 停止观察范围 |
|---|---|---|
| Codex CLI | `codex exec --json` | 所属 Windows Job 进程树 |
| Claude Code CLI | `claude --print --output-format stream-json` | 所属 Windows Job 进程树 |
| OpenCode CLI | `opencode run --format json` | 所属 Windows Job 进程树 |
| DeepSeek Harness CLI | `dsh --profile headless --json` | 所属 Windows Job 进程树 |
| Codex 原生子 Agent | 控制端转接真实创建、等待及关闭工具 | 关闭后观察到会话停止或不存在 |

CLI 的证据不能认证原生路线。原生会话关闭也不证明任意 Editor、shell 或远端服务工作已经停止。这些执行配置不覆盖嵌套委派、整机排他或跨机器执行。

## 2. 选择既有工作区与已审阅配置

先从所选宿主的 Boot 和生命周期 discovery 核实安装，再使用 `malts_v2.py workspace --workspace <工作区>` 解析既有工作区，以返回的状态目录和 Project 身份为准。不能通过重复初始化或采用获得委派权限。当前 Phase、Task 修订及依赖须允许执行。审查与 Worker 配置都必须使用所选工作区核实的状态目录和 Project；后续操作须匹配原派发的 Task 及修订，不能通过更换配置文件重新指向其他任务。

`tools/malts_agents.py` 是可信控制端接口，不是 Worker MCP 工具。Worker 不能借此取得后继任务、Grant 或验收权限。审阅过的配置文件包含宿主、准确可执行文件及 SHA-256、工作根、相关配置清单、执行模式、状态与任务绑定、既有授权引用及 MCP Python 解释器。模型和推理强度沿用用户当前选择；配置值不等于已独立观察到的实际身份。

配置结构示例：

```json
{
  "host": "codex",
  "executable": "<已审阅codex.exe绝对路径>",
  "executable_sha256": "<实际sha256>",
  "working_root": "<既有工作区>",
  "execution_root": "<独立的自有原生暂存目录>",
  "config_files": ["<实际宿主配置>", "<实际项目配置>"],
  "mode": "worker",
  "state_dir": "<工作区返回的状态目录>",
  "project_id": "<当前Project>",
  "task_id": "<当前Task>",
  "task_revision": 1,
  "authority_ref": "<既有用户授权引用>",
  "python_executable": "<已审阅MCP解释器>",
  "tool_root": "<所选宿主配置根>"
}
```

这些是占位值，不是可以直接执行的安装默认配置。使用已安装运行时时，审查和 Worker 配置都应传入准确 tool_root。准备与首次原生创建准入在生命周期激活互斥下复核安装身份；原派发的查询和取消仍用于对账与停止。Worker 复用控制端已验证的当前绑定，不得从暂存目录初始化新项目。Claude Code 使用 `host=claude-code`，OpenCode 使用 `opencode`。Windows 优先使用命令转接脚本背后的实际可执行文件。Harness Desktop 另须提供审阅过的启动参数前缀与归档文件指纹；选择的静态 provider/model 及推理强度应与用户配置一致，新建 headless 默认值可能指向不同的凭据来源。

Harness 使用任务自有、仅作用于子进程的 `DSH_HOME` 和每次派发的独立补丁；需要既有账号认证时显式引用原凭据存储，不复制凭据、不修改用户 Profile。动态模型表达式须另行审阅，控制端不求值任意配置代码。

## 3. 检查、资格验证与预算

控制端默认预览。`inspect`、`capabilities`、`qualification-status`、`native-call` 不调用模型；读取配置或资格不会自动生成记录。

```powershell
python -B tools/malts_agents.py inspect --profile-file '<profile.json>' --host-root '<任务自有Host日志目录>'
python -B tools/malts_agents.py qualification-status --profile-file '<profile.json>' --receipt-root '<保留的资格记录目录>' --route-id codex-cli-worker
python -B tools/malts_agents.py host-init --host-root '<新的任务自有Host日志目录>' --host-id '<已审阅Host标识>'
```

审阅后，`host-init --apply` 仅创建新的自有日志。`budget --workspace <工作区> --policy-file <policy.json>` 预览预算，应用须提供 `--expected-policy-sha256 <预览哈希> --apply`。策略沿用现有 `configure_budget` 合同，包含 Project、启动与委派数量、各 Host 占用、查询和取消额度、有效期与授权。已有预算通过当前控制端预算接口修订，不能重新初始化并清零消费。

普通准备和启动要求所选路线具有对应资格；通过 `--qualification-root` 指定记录，并按需增加 `--require-capability`。只读审查默认要求派发、结果及只读能力；Worker 默认要求派发、结果及受限写入。缺少、失效或不足的记录返回 `QUALIFICATION_REQUIRED`，不启动 Agent。

明确授权且有上限的资格试验可使用 `--qualification-run --authority-ref <已审阅授权>`。它是控制端验证入口，不是 Agent 自行认证的权限。启动前冻结场景和额度，失败或结果不明的启动同样消费适用额度并保留证据。

## 4. 准备、启动与观察原派发

首次输出原生创建调用前，MALTS 比较排队时的配置绑定并重新核对输入文件。四端 CLI 执行配置均向监督器传递所选安装绑定，在实际进程启动时检查生命周期准入。配置漂移阻止新执行，原派发的查询、取消和已准入回执保存仍可用于对账。

请求文件包含 `prompt` 和有限的 `wall_seconds`；提示词通过 stdin 传入进程。控制端提供配置、Host 日志、准确 Task/attempt/dispatch 身份、策略及授权，先预览 `prepare`，再按准确配置与请求哈希应用。随后通过现有授权服务，为返回的 Worker actor 登记所需 Grant。

`launch`、`poll`、`cancel` 使用原派发和唯一调用标识。变更先预览，再提供已审阅配置哈希应用。启动回执丢失时，不建立替代派发；先查询、对账原 Host 日志。控制端重启后可以重新打开同一日志，不自动启动替代 Agent。

Codex 原生路线须使用 Codex 配置，增加 `--native`，并用 `--role` 选择实际职责。资格同时绑定该职责和配置，Verifier 回执不能认证 Planner 或 Worker。使用相同配置和回执目录，通过 `qualification-status --native --role malts_verifier --route-id codex-native-verifier` 读取对应记录；`inspect --native --role malts_verifier` 返回该角色的 `qualification_binding`。`native-call` 首先只预览待执行调用的标识与工具名；审阅后提供 `--apply`，先保留相应预算，再输出准确可执行调用。可信控制端只执行一次，保存真实返回，再向 `native-receipt` 提交原 call ID、工具名和回执。回执保存沿用原准入，不再消费一次查询。`native-query --apply` 排队并准入有界等待，取消排队关闭。已准入的待处理调用先对账，其回执保留取消意图并继续排入关闭；从未准入的等待可以在未调用宿主的情况下撤回。返回内容仍未经过验收；关闭确认仍非终态，须随后观察到会话停止或不存在。原生路线的截止时间依靠活动控制端查询及取消，不存在隐藏计时守护进程。

### 4.1 CLI 操作顺序

在已核实的 MALTS 根目录运行以下命令，事先审阅既有配置、请求与资格记录，并用实际值替换占位符。第一次 prepare 只预览，应用须提供两个准确哈希。Worker 还须在启动前，为 prepare 返回的 actor 登记准确 Grant。Task 验收仍由控制端另行完成。

```powershell
$agentProfile = '<profile.json>'
$agentHostJournal = '<owned-host-journal>'
$agentRequest = '<request.json>'
$agentQualifications = '<retained-qualification-root>'
$agentProfileHash = (python -B tools/malts_agents.py inspect --profile-file $agentProfile --host-root $agentHostJournal | ConvertFrom-Json).profile_sha256
$agentRequestHash = (Get-FileHash -LiteralPath $agentRequest -Algorithm SHA256).Hash.ToLowerInvariant()
python -B tools/malts_agents.py prepare --profile-file $agentProfile --host-root $agentHostJournal --dispatch-id '<dispatch-id>' --attempt-id '<attempt-id>' --strategy-ref '<strategy>' --authority-ref '<existing-authorization>' --request-file $agentRequest --qualification-root $agentQualifications
python -B tools/malts_agents.py prepare --profile-file $agentProfile --host-root $agentHostJournal --dispatch-id '<dispatch-id>' --attempt-id '<attempt-id>' --strategy-ref '<strategy>' --authority-ref '<existing-authorization>' --request-file $agentRequest --qualification-root $agentQualifications --expected-profile-sha256 $agentProfileHash --expected-request-sha256 $agentRequestHash --apply
python -B tools/malts_agents.py launch --profile-file $agentProfile --host-root $agentHostJournal --dispatch-id '<dispatch-id>' --invocation-id '<unique-launch-id>' --qualification-root $agentQualifications --expected-profile-sha256 $agentProfileHash --apply
python -B tools/malts_agents.py poll --profile-file $agentProfile --host-root $agentHostJournal --dispatch-id '<dispatch-id>' --invocation-id '<unique-poll-id>' --expected-profile-sha256 $agentProfileHash --apply
python -B tools/malts_agents.py result --profile-file $agentProfile --host-root $agentHostJournal --dispatch-id '<dispatch-id>' --expected-profile-sha256 $agentProfileHash --apply
```

保留返回的 actor／Run 及每个原始标识；不同轮次的 poll 使用不同调用 ID，不通过更换 dispatch 重试不明启动。取消使用同一派发、唯一调用 ID 和已审阅配置哈希运行 `cancel`，随后观察原执行，直至确认适用的停止条件。资格试验可使用前文明确的有限测试入口，但该入口不会自动产生通过证据。


### 4.2 原生职责与 Worker 变更审阅

原生选择器支持已安装的五种职责。它们共用派发协议，分别保存资格记录：

| 职责 | 角色参数 | 路线 ID | 预期产物 |
|---|---|---|---|
| Planner（规划） | `malts_planner` | `codex-native-planner` | 任务边界、依赖与验收条件 |
| Explorer（探索） | `malts_explorer` | `codex-native-explorer` | 带具体证据的源码发现 |
| Memory Curator（经验整理） | `malts_memory_curator` | `codex-native-memory-curator` | 供控制端审阅的、有证据的经验候选 |
| Verifier（验证） | `malts_verifier` | `codex-native-verifier` | 独立检查结果与未解决问题 |
| Worker（执行） | `malts_worker` | `codex-native-worker` | 限定范围内的实现提案 |

前四种职责只读。Curator 返回内容不会写入个人记忆、修改全局指令或自动推广候选。角色名及已安装的 TOML 文件均不能证明实际执行或资格。使用 `inspect --native --role <角色>` 返回的 `route_id`；旧的 `codex-native-review` 记录仍是历史证据，不认证另一职责。每个角色可以保留自己的当前记录，不替换其他角色的记录。

原生创建接口不接受每次派发专用的 MCP 配置，因此原生 Worker 返回结构化变更提案，由可信控制端审阅。标准只读 MCP 不开启写权。控制端检查保留的实际返回，选择一项提案、预览后，再使用原派发 actor 和已有 Grant 调用现有文件适配器。该路径支持 UTF-8 文件的排他创建及带前像保护的更新，不执行任意工具，也不签发新权限。

Worker 只返回 JSON，不加 Markdown 代码围栏。闭合格式如下：

```json
{
  "format": "malts.native-worker-proposal.v1",
  "dispatch_id": "<原派发标识>",
  "task_id": "<原任务标识>",
  "task_revision": 1,
  "proposals": [{
    "operation_id": "<稳定操作标识>",
    "grant_id": "<已有授权标识>",
    "tool": "create-file",
    "path": "outputs/result.txt",
    "content": "已审阅内容\n"
  }]
}
```

更新使用 `tool=update-file`，增加 `expected_sha256`，值为当前文件准确字节的 SHA-256。每个返回包含一至八项提案，总计不超过 128 KiB，每项 UTF-8 内容不超过 64 KiB。只接受无歧义的相对文件路径。此接口不处理二进制文件或删除。

控制端写入仅包含 `proposal`、从零开始的 `index` 和 `preimage_policy` 的审阅请求。提案须与保留的原生完成内容相等，不能换成控制端另造的文本。创建时 `preimage_policy` 为 null；更新时须由控制端提供现有[文件更新合同](V2_STATE_CONTRACT.md)要求的已审阅采集策略描述，Worker 不能批准自己的恢复采集。使用已检查的原生 Worker 配置和原日志：

```powershell
python -B tools/malts_agents.py native-worker-apply --native --role malts_worker --profile-file '<profile.json>' --host-root '<owned-host-journal>' --dispatch-id '<原派发标识>' --request-file '<已审阅选择.json>'
python -B tools/malts_agents.py native-worker-apply --native --role malts_worker --profile-file '<profile.json>' --host-root '<owned-host-journal>' --dispatch-id '<原派发标识>' --request-file '<已审阅选择.json>' --expected-profile-sha256 '<预览配置哈希>' --expected-request-sha256 '<预览请求哈希>' --apply
```

预览不写文件或操作记录。应用前重新检查实际保留提案、Task 修订、原生配置、输入文件、活动派发及 Grant，再准备效果。应核对真实适配器结果和文件字节。相同标识的已完成操作重复提交时不重复执行。取消或关闭后的派发不能引入新效果；明确授权后继之前，应先对账原操作。在原 Worker 派发仍准入时应用审阅通过的变更，随后关闭并观察停止／不存在；验收仍由控制端另行决定。

原派发保留明确且受保护的运行时绑定；重开服务时即使省略可选运行时参数，新工作仍恢复原绑定，选择其他运行时会被拒绝。没有采集绑定的旧派发可继续对账，但不能获得此新增提案效果路径。所选控制端配置须匹配原 Project、Task 和修订。实际保留的 JSON 与所选提案执行相同的闭合类型检查，布尔修订不能替换为整数。

实际关闭工具抛出异常时，将准确且有界的错误文字保留为明确的失败封装：`{"error":{"message":"<实际工具错误>"}}`。通过 `native-receipt` 将其作为原已准入关闭调用的 `receipt` 保存；它不是 `previous_status` 关闭确认。日志保护失败内容，并为同一原生身份排队等待。异常本身保持执行未结算，不证明停止。后续真实等待返回 shutdown／not_found 后，才能确认原生会话不存在，此时 `cancel_acknowledged` 仍为 false。若仍在运行，则保留取消意图，将下一次关闭排队并按预算明确准入。不得将工具异常改写成成功回执、替换派发或补回消费。

此机制约束经中介执行的文件变更，不认证所有同用户调用者，也不隔离原生宿主可以使用的全部 shell、编辑器和远端动作。需要更强原生隔离时，须提供对应宿主证据，或使用满足要求的隔离 CLI 配置。资格记录应说明实际检查的边界。

## 5. 权限、结果与验收

CLI 审查配置只暴露所选宿主明确允许的工具。Worker 配置在支持处关闭原生 shell，并仅暴露绑定 Task/Run 的 MCP；每次受管变更仍核 Grant、资源、修订、actor、epoch 和派发准入。Codex Worker 须使用业务工作区之外、且不属于任何 Git 工作树的既有 execution_root。命令使用仅作用于该进程的工作区写入沙盒，原生写入限定在暂存目录，清空额外可写根并排除隐含临时目录授权。暂存目录之外的业务文件仅通过绑定 Task 的 MCP 授权变更。仅禁用 shell_tool 并不会禁用原生 apply_patch；MALTS Grant 也不能覆盖宿主只读指令。权限配置不持久写入；原生边界通过尝试修改业务夹具核实，不凭参数推断。配置语义参见[官方沙盒说明](https://learn.chatgpt.com/docs/sandboxing)与[配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)。这些措施不代表能够控制任意同用户进程或所有原生能力。

`result --apply` 是显式私有控制端读取，返回用于验证与恢复的未审阅候选文字，不接受 Task。应独立核对实际输出字节、被拒操作和未决效果。进程正常退出、最终文字可解析或 Agent 自述，均不足以证明任务完成。

公共运行摘要只保留有界状态和用量元数据。传输层不保留原始 stdout/stderr、推理、工具参数和完整工具结果。私有记录保留加密候选文字、原生身份及不含具体值的诊断码。宿主自己的会话存储仍遵守宿主策略，与 MALTS 传输层的保留范围分开。

## 6. 资格证据与失效

执行回执使用 `malts.agent-case-receipt.v2`，在采集时绑定路线、能力、已审阅输入摘要及配置绑定。不能将旧回执重新登记为新输入、其他路线或其他模式的证据。旧的无输入绑定 v1 执行回执仍是历史资料，不能认证当前执行；应补充新的有界真实案例，不改写旧回执字节。

资格按宿主、执行路线、模式和已审阅输入清单分别记录。回执列明必需与已验证能力，不使用一个全局成功开关。合成或组件检查不能证明真实宿主执行。真实 PASS 必须对应保留的执行回执字节、匹配的 SHA-256 与原生身份、已结束执行，以及对真实观察或产物文件的受支持检查；缺失、矛盾或变化的证据不能认证路线。

记录只追加，使用 Windows 当前用户 DPAPI 保护。摘要不输出个人路径、原生 ID 或原始私有正文。源码或配置变化返回 `PROFILE_CHANGED`、`STALE_INPUTS`，结果证据变化返回 `EVIDENCE_INVALID`。恢复须一起保留资格回执、原生日志和引用产物闭包；这些可选记录不会自动成为 Project 数据库备份的一部分。

可信控制端仍须提供真实宿主回执。文件哈希和 DPAPI 保护绑定与保留字节，不认证任意同用户调用者，也不证明模型普遍遵从。宿主未暴露时，实际模型、推理强度、费用及物理请求次数继续标为未知。

## 7. 有界完成

承诺产物与适用检查完成后结束本轮调度；存在阻塞时保留原身份，明确缺项。源码实现、组件检查、真实路线资格、本机安装和公开发布分别报告。只有派发与结果证据的路线，不得宣称写入、并行或恢复能力也已验证。
