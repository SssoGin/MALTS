# MALTS 控制端操作参考

控制端使用已验证运行时和所选状态查询任务、执行审阅请求。当前 Core 格式 Schema69，版本 **2.0.3**。普通项目可使用已安装 Skill，下列命令说明控制端接口。演示使用另行选择的新目录，不调用模型或安装宿主。

<a id="v2-start"></a>
## 1. 第一个完整本地任务

将下面 Python 保存为 `quickstart.py`，运行 `python -B quickstart.py '<verified-runtime>/tools/malts_v2.py' '<new-demo-directory>'`。Windows 当前用户 DPAPI 是初始化前提。目录必须不存在；失败时保留现场，不在同目录盲目重跑。示例生成新库、请求、结果文件和备份，不安装、不调用模型，仅验证合成文件完整性。authority 字符串记录已有演示授权，不自行产生权限。

```python
import json, subprocess, sys
from pathlib import Path
cli, demo = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
if not cli.is_file():
    raise FileNotFoundError(cli)
demo.mkdir(exist_ok=False)
state = demo / '.malts' / 'state'
def call(*args):
    p = subprocess.run([sys.executable, '-B', str(cli), *map(str, args)],
                       capture_output=True, text=True, encoding='utf-8', timeout=60)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return json.loads(p.stdout)
def request(action, **arguments):
    path = demo / (action + '.json')
    path.write_text(json.dumps({'action': action, 'arguments': arguments}), encoding='utf-8')
    preview = call('request', '--state-dir', state, '--request-file', path)
    assert preview['decision'] == 'NOT_APPLIED'
    return call('request', '--state-dir', state, '--request-file', path, '--apply')['result']
call('workspace-init', '--workspace', demo,
     '--project-id', 'DEMO', '--goal', 'Verify an isolated file', '--apply')
criterion = {'criterion_id': 'Integrity', 'description': 'Managed bytes match',
             'hard': True, 'verification_method': 'managed-file-integrity',
             'minimum_evidence_level': 'C'}
request('task.revise', task_id='T1', project_id='DEMO', expected_revision=0,
        goal='Create hello.txt', scope=['hello.txt'], acceptance=[criterion], request_id='D-T1')
request('grant.record', grant_id='G1', task_id='T1', task_revision=1, actor='demo',
        source_ref='user:approved-isolated-file-demo', resource='hello.txt', effect='write')
p = request('operation.prepare', operation_id='OP1', grant_id='G1', actor='demo',
            resource='hello.txt', effect='write', capture_authority_ref='user:approved-synthetic-demo',
            parameters={'tool': 'create-file', 'path': 'hello.txt', 'content': 'Hello MALTS 2.0.3\n'})
request('operation.create-file', operation_id='OP1', actor='demo', expected_request_hash=p['request_hash'])
assert (demo / 'hello.txt').read_bytes() == b'Hello MALTS 2.0.3\n'
descriptor = {'owner': 'DEMO', 'target': {'task_id': 'T1', 'task_revision': 1, 'criterion': 'Integrity'},
              'content_class': 'synthetic', 'sensitivity': 'project', 'redaction_policy_version': 'demo-v1',
              'verification_scope': 'Isolated synthetic file integrity only',
              'review_ref': 'user:approved-isolated-file-demo',
              'retention': {'reuse_until': None, 'preserve_recovery_references': True},
              'access_scope': {'project_id': 'DEMO', 'purposes': ['verification', 'recovery']}}
request('verification.managed-files', evidence_id='E1', task_id='T1', task_revision=1,
        operation_id='OP1', criterion='Integrity', actor='demo', descriptor=descriptor)
request('task.accept', acceptance_id='A1', task_id='T1', task_revision=1,
        evidence_ids=['E1'], authority_ref='user:approved-demo-acceptance')
assert call('task-verify', '--state-dir', state, '--task-id', 'T1')['decision'] == 'CURRENT_EVIDENCE_VALID'
call('backup', '--state-dir', state, '--destination', demo / 'backup', '--apply')
assert call('verify-backup', '--destination', demo / 'backup')['decision'] == 'VERIFIED_BACKUP'
print('CURRENT_EVIDENCE_VALID; VERIFIED_BACKUP; synthetic file only')
```

<a id="v2-current"></a>
## 2. 当前入口与长期初始化

读取工具 Boot 并 discovery；已采用工作区运行 `workspace --workspace '<business-root>'`，原生 v2 明确传入其 state 目录。随后用 `governance-context`、`task-queue`、`context` 读取当前目标。查询不创建执行实体。

新长期工作区在显式 `workspace-init` 后还需：`project.define` 定义当前目标/验收；`phase.define` 绑定实际计划；`phase.set-active` 激活；`phase.bind-task` 绑定每个 Task revision。最后 `workspace` 必须报告 LONG_PROJECT 和 `phase_ready=true`。上方演示只是 TASK_ONLY，不能冒充长期初始化。

`phase.define` 的字段为 phase_id、project_id、project_revision、expected_revision、goal、boundary（in_scope/out_of_scope 数组）、acceptance、plan_ref、plan_sha256、authority_ref、request_id；plan_ref 是相对项目资源根的真实文件。scope 必须逐项在 in_scope 中。更改 ACTIVE Phase 前先处理 pending effects/Hosts/Runs，再 pause、define 新 revision 并重绑定受影响任务。

新长期工作区具备可执行层次，不只是数据库目录。项目定义原始/当前目标和全局条件；阶段定义有限目标、允许/排除范围、验收和实际计划；任务定义范围内输出与准确依赖，随后激活审阅阶段并绑定适用任务版本。

例如兼容阶段可允许模块/报告输出并排除部署。之后添加部署须重新核边界和任务定义，不能仅因状态库存在就发不相关写 Grant。绑定 plan_sha256 前核实际计划字节。

已有采用工作区通过 workspace/binding 和当前 context 进入，原生 v2 状态明确选择。回答状态问题不能顺带迁移或初始化，这些另有合同。

## 3. 请求和返回

`capabilities` 提供当前动作参数合同。request 文件只含 `action` 与 `arguments`；先 `request --state-dir '<state>' --request-file '<file>'`，再对已授权范围使用相同请求加 `--apply`。dry-run 返回 NOT_APPLIED/NOT_EVALUATED，既不执行也不证明就绪。

成功外层是 `decision=REQUEST_PROCESSED`，具体字段在 `result`。原始 MCP prepare 结果使用 `response.result.request_hash`；已经主动解包为 result 的客户端才直接取 request_hash。错误保留 top-level decision/error_code，无成功 result。

MCP 写接口由 Host policy 限定；只读接口不提供授权或执行。客户端不能覆盖 project/actor/authority，不能猜 Grant ID。use current context execution_inputs 的准确 ID、resource/effect 和完整 preimage_policy_templates；缺失时由控制端核既有范围。

控制端请求的顶层结构闭合：

```json
{"action":"phase.bind-task","arguments":{"task_id":"<current-task-id>","task_revision":1,"phase_id":"<reviewed-phase-id>","phase_revision":1,"authority_ref":"<existing-authorization-reference>"}}
```

这是参数格式示例，须使用实际当前 ID/版本和已有授权，不能使用占位值。先预览准确请求文件，再在审阅范围内 apply；预览不评估全部执行准入条件。

原始成功为 {decision: REQUEST_PROCESSED, action: ..., result: ...}。operation.prepare 的 result.request_hash 传给匹配适配器 expected_request_hash；只返回 result 的辅助函数已经解包。错误没有成功 result，核 error_code 和不泄露值的 reason_code，不能将传输成功当业务成功。

动作目录来自当前服务签名。未公开动作不能从状态猜名字或复制旧 API；宿主绑定 Worker 不能换控制端入口逃离指定范围。

<a id="v2-accept"></a>
## 4. 文件与验收

受管读的 prepare parameters 只含 `tool='read-file'` 和 granted relative path；read limits 放 execution。更新需要 `tool='update-file'`、path、UTF-8 content、当前 expected_sha256 和完整 preimage_policy，保存原文并核独占文件。creation 不能覆盖。

criterion 必须指定方法和最低等级。`verification.begin` 结清依赖、操作和受管 Host 后进入 VERIFYING；修复需 `verification.rework`。`verification.managed-files` 固定提供文件完整性证据，真实业务另验。`task.accept` 后用 `task-verify` 检查当前证明；历史完成查询或 exit 0 不充分。

受管更新需要已有审阅文件及当前字节哈希。取得宿主批准的完整前像策略，准备准确参数，再用返回哈希调用合格更新适配器。适配器拥有意图步骤时不手工预提交。前像变化应拒绝，而非静默覆盖。

有效验收将每项条件与实际结果连接。文件完整性演示只证明其合成字节，迁移还需要用户要求的兼容观察。不可用/失败检查保留，不能将条件改为碰巧通过的结果。

效果和宿主结清后验证并验收当前版本。验证中需修复则先 rework。失败保留原观察，新 operation ID 不是 UNKNOWN 的通用重试机制。

<a id="v2-recovery"></a>
## 5. 暂停、备份与对账

用当前 Run/checkpoint 执行 pause/resume，不建立替代 Run 重放未决效果。PAUSE_REQUESTED 同时检查 pending_operations/pending_hosts；cancel acknowledgement、PAUSED 和 expired lease 不证明写者静止。

`backup --state-dir '<state>' --destination '<new-backup>'` 先 preview，再 `--apply`；`verify-backup --destination '<backup>'` 只读核验。restore 先读 `restore --help`，绑定已核验备份 SHA-256、新目录和审阅资源。恢复建立新 epoch并保持隔离；核后续成果、外部效果和预算，不恢复旧Grant/Host/额度。备份不是恢复授权。DPAPI 跨用户恢复未认证。

`recovery-inspect`、`recovery-review` 和 update-repair-plan 检查原操作/目标；decision=REQUIRES_REVIEW 不视作已解决。保持 UNKNOWN 的同一身份；诊断和 blob清单不授删除权。

<a id="v2-collaboration"></a>
## 6. Host 与协作

先匹配已授权职责、资源范围、真实adapter、有效身份、model/effort约束与累计预算。使用已广告的 Host/controller 合同，不把 RPC ID 当 Task/Run。不静默降级硬约束；不可观察的实际模型身份保持 unknown。

Worker 不接受自己的活动 dispatch；返回产物与未决项，控制端在 Host 结清后验证/接受。关联 Job 的退出只证明所属进程树，不证明任意外部 writer 或 GUI模型取消。多 Agent、后台和无人值守需要相应范围。

<a id="v2-growth"></a>
## 7. Growth 试用

按当前合同调用 `growth.propose`、`growth.begin-trial`、`growth.record-outcome`、`growth.validate` 和 `growth.retire`。提案绑定允许用途的来源；试用绑定准确 Task/profile及现有授权。未来证据必须可比，neutral、harmful 和 unknown保留。已撤销/退役内容不得由迟到结果、重放或恢复复活。全局Skill/Prompt应用另核范围。

当前提案 JSON 的闭合正文为 action、check、boundary、applicability；后者含 task_types、tools、failure_signatures，至少一个约束。例如恢复前格式检查可限定恢复类任务和某宿主。来源须允许 Growth 用途，保留 recovery 原件本身不足以复用。

growth.propose 绑定提案/来源证据；growth.begin-trial 绑定候选/所属、已准入操作和 expected_request_hash、主体、task_type/tool、rollback_ref 与已有授权，不创建新预算。真实后续使用后，growth.record-outcome 标识试用、合格证据、结果/严重度和 independence_key。

验证使用当前评估身份和审阅证据，退役核预期状态及反证。迟到正面观察不能复活 deprecated/removed/rejected 候选。保留中性/有害结果，不能仅因项目试用已记录就发布全局规则。

<a id="v2-handoff"></a>
## 8. 交接和成果

`handoff-preview --state-dir '<state>' --task-id '<task>' --task-revision <revision>` 返回有界视图/令牌。先保全手工原文，再按 `handoff.publish` 合同核现有目标、来源令牌与前像；不存在目标先单独创建。部分页或未决 publication intent不能宣称 ready。Artifact register/promote/reconcile/Shared proof 分别核身份与关系，旧关系不是当前复用许可。

已有交接的受保护发布先 handoff.capture-file 捕获审阅前像，将该 note 纳入预览。审阅完整 markdown/source_token，再用 handoff.publish 绑定 target_relative、target_note_id、note_ids 和明确发布授权。局部预览或目标变化应拒绝；中断后先 handoff.inspect-publication，再决定后续写入。

预览 token 只覆盖所呈现所属事实，不覆盖全部原文件；其他备注是经审阅历史数据，文件保护只证明所选目标前像。外部来源的当前内容决定下一步时，须重新核该来源。

成果独立核内容、所属、关系和复用。当前动作包括 artifact.register、artifact.promote、artifact.reconcile、artifact.retire-shared，按准确合同操作。SUPERSEDED 是 disposition，不是可调用 artifact.supersede。见[交接](HANDOFF.md)和[状态合同](V2_STATE_CONTRACT.md)。

<a id="v2-migration"></a>
## 9. 历史采用与升级

旧工作区只通过已选择的 legacy adoption/forward合同迁入 v2：审阅目标、映射、当前写者、UNKNOWN、备份与source seal，再 preview/apply。采用成功之后只在 v2内前向恢复。不要删除binding/seal、直接编辑DB或恢复旧Markdown写权。版本更新见[更新](UPDATE.md)，完整机制见[状态合同](V2_STATE_CONTRACT.md)。

### 9.1 支持范围与切换边界

MALTS 提供 `legacy-adoption-apply` 及内置 `WINDOWS_GOVERNED_CONTROL_FILES` 交接器，用于 Windows 固定本地卷上经审阅的 MALTS 控制定义和历史输入。控制器从当前 discovery 核实的运行时执行，在操作期间持有生命周期互斥。Codex、Claude Code、OpenCode 和 DeepSeek Harness 共用此控制器；这不等于四端 GUI 进程均已成为受控迁移宿主。

交接器独占创建两份旧事务来源封印，以 Windows 文件句柄禁止其他调用改写或删除每份审阅输入和已知活动文件，并持有祖先目录句柄防止重命名。已有写句柄或可写映射会阻止取得保护。旧受管事务不能越过封印启动新写入；候选定义和语义评审在 SQLite 切换事务中再次核对。交接凭证记录实际持有的保护，CLI 不接受用户编写的 witness JSON。

绑定资源是审阅过的控制输入、来源协议文件和候选定义，不是业务项目目录下的所有文件。交接器不会停止 Editor、导入进程、后台任务或任意外部程序；未列入来源清单的业务文件不会因此导入或备份。预检会拒绝把外部业务根纳入该交接器。更大资源范围仍需调用方提供经验证的 Host，证明实际阻止相关写入；进程列表为空或 MALTS 记录已结清不能替代这项保证。

### 9.2 目录布局与权限

创建来源封存或状态库之前先核对布局：

```text
<control-workspace>/
  runtime/v2_binding.json
  .malts/
    management.json
    source-capsules/<adoption-id>/
    state/
    recovery/<operation-id>/
```

默认将管理数据置于所属 `.malts` 目录，capsule 与 state 仍互不包含。预检返回默认路径；持久准备前预览并应用 `management-init --workspace $SourceRoot`，再使用该布局封存和导入。也可明确选择有授权的外置路径；已有绑定不自动搬迁。完整所有权、来源排除及迁移步骤见[管理与重定位](MANAGEMENT_AND_RELOCATION.md)。采用后，state 是唯一、长期维护的任务权威，须保留备份和受保护证据，不能当作迁移缓存清理。capsule 校验只保护所选来源字节，不证明完整业务资产树已备份或可跨用户解密恢复。

读取 Boot 并通过 discovery 后，用已授权路径替换下列变量。前两条命令只读：

```powershell
$Cli = Join-Path $MaltsRoot 'tools/malts_v2.py'
& $PythonExe -B $Cli entry-status --workspace $SourceRoot --tool-root $ToolRoot --verify-package
& $PythonExe -B $Cli legacy-adoption-preflight --source-root $SourceRoot --capsule-root $CapsuleRoot --state-dir $StateDir
```

如需检查更大的拟采用范围，追加 `--resource-root '<external-business-root>'`。返回 `EXTERNAL_RESOURCE_HANDOFF_NOT_SUPPORTED` 时停止该扩展范围。布局有效或返回 `CONTROL_HANDOFF_AVAILABLE` 均不证明已取得现场保护，也不授权开始持久准备。

### 9.3 准备、定义导入与语义评审

先保全原始目标、控制、计划、成果、用户修改与恢复义务。通过 `legacy-activity` 检查旧活动；UNKNOWN 效果和未结事务沿原身份协调。审阅来源清单后，以 `legacy-stage` 预览并按准确 inventory hash 封存 capsule。通过 `legacy-import-definitions` 预览、应用经明确审阅的 Project、Phase、Task 与依赖映射，写入独立候选库，再以 `legacy-verify-import` 验证。历史 DONE 仍是历史声明。

随后，`legacy-review-semantics` 绑定经审阅的来源处置、inventory hash 和 mapping hash，仅应用批准的预览哈希。来源清单、导入数据库和语义回执是不同里程碑，均不证明已采用或获得执行权限。各命令 `--help` 给出当前闭合参数；来源或映射漂移时重新评审，不能修改保存的哈希来通过检查。

### 9.4 审阅计划与正式执行

语义评审通过后生成、保存一份 `legacy-adoption-plan`，传入已有授权引用及选定 adoption ID，将返回 JSON 原样保存为 UTF-8。`plan_sha256` 绑定来源、状态库、语义评审、定义、活动和新旧 epoch。保留此计划供重试；可能已经发生部分切换后，不另生成替代计划。

对这份已保存、审阅的计划执行：

```powershell
$Plan = Get-Content -LiteralPath $PlanPath -Raw -Encoding utf8 | ConvertFrom-Json
& $PythonExe -B $Cli legacy-adoption-apply --plan-file $PlanPath --expected-plan-sha256 $Plan.plan_sha256 --tool-root $ToolRoot
# 对同一审阅操作已有授权后，应用同一份计划：
& $PythonExe -B $Cli legacy-adoption-apply --plan-file $PlanPath --expected-plan-sha256 $Plan.plan_sha256 --tool-root $ToolRoot --apply
```

未加 `--apply` 时，不创建封印、binding、数据库变更或交接证据。正式执行取得真实保护并调用核心采用协议。`ADOPTED` 只证明相应范围的绑定切换，不激活 Phase、不恢复 Task、不启动 Host，也不签发 Grant。

### 9.5 中断与沿原身份接续

使用 `adoption-status --state-dir $StateDir --adoption-id $Plan.adoption_id` 检查原操作。Windows 控制器在失败时保留属于原计划的封印，使旧受管写入继续受阻。PREPARED、部分封印或已落盘 binding 是待恢复现场，不能删除文件或运行原生初始化绕过。保留计划、状态库和交接证据，查明并修复实际原因；评审和输入仍匹配时，应用同一计划及 ID。外来封印、binding 或定义漂移会拒绝接续，不覆盖现有内容。

ACTIVE 状态的重复调用核实当前 binding 后返回历史回执，带 `replayed=true`、`writes_performed=false` 和 `host_revalidated=false`，不声称重新隔离写入者。后续恢复备份按既有 v2 前向恢复合同执行；不支持恢复旧运行时写权。

### 9.6 正式长项目就绪查询

采用后运行 `workspace --workspace $SourceRoot`。服务核验 binding、状态库、epoch 和来源封印，返回所选 Project、当前修订、profile、活动 Phase、实际计划引用及哈希、已验证 Task/绑定/依赖数量，以及 `readiness_blockers`。`definition_body_reverified=true` 表明已复核定义正文，与有界上下文预览不同。

`LONG_PROJECT` 表示已有 Phase 层次；`phase_ready=true` 还要求完整的当前 Project 定义、合适且唯一的 ACTIVE Phase、匹配的计划字节、当前 Task 绑定，以及无未决迁移或恢复条件。查询验证依赖关系；前序任务结果尚未验收时，任务服务仍会阻止后继执行。这里的就绪是治理就绪，不是 Grant，也不是业务验收。

采用之后，通过 `phase.set-active` 明确审阅、激活应接续的 Phase；需要时修订 Task，并以 `phase.bind-task` 绑定当前修订。使用 `governance-context`、`task-queue` 和准确 Task 的 `context` 接续。不能为了把字段改成 true 就激活任意历史 Phase 或启动业务工作。

### 9.7 入口诊断与能力字段含义

`workspace` 先分类再打开状态库：旧来源返回 `MIGRATION_REQUIRED`，未绑定的导入库返回 `ADOPTION_REQUIRED`，有来源封印而未通过 binding 验证的现场返回 `RECOVERY_REQUIRED`。这些对象都不是原生工作区。无效 binding 和真实数据库故障仍返回错误，不能当作迁移成功。

能力字段描述各自层次。`migration_supported=false` 指自动数据库 schema 升级，不否定单独的、经过评审的旧工作区采用流程。`builtin_control_handoff` 描述上述 Windows 控制输入模式；`native_host_adapters_qualified=false` 和 `whole_host_occupancy_known=false` 继续保留对原生 Agent 调度和任意外部写入者的限制，内置控制交接不改变这些限制。

### 9.8 跨根工程与验证限制

采用将 Project 的 `resource_root` 绑定控制工作区。外部 Unity、Unreal、源码或资产根不会继承写入授权；产生效果前须单独审阅资源归属与适用适配器，不能通过改 binding 或数据库字段获得权限。四端安装、隔离迁移与负向/恢复检查、真实控制器操作，均与某业务工程的迁移或 Editor 行为分别验证。跨用户 DPAPI 明文恢复仍未认证。

## 原生状态库迁址与路径恢复

健康原生库与已采用库均通过正式重定位流程搬迁；原生无定位文件时明确提供原状态目录，并保留 Project 的业务资源根。统一入口为 `store-relocation-preflight`、`store-relocation-prepare`、`store-relocation-status`、`store-relocation-plan` 和 `store-relocation-apply`；正式写入使用当前安装和审阅计划哈希。恢复审查不等于执行授权，切换后 Phase 仍须明确激活。原生旧库的普通服务写入也会被拒绝。

受管长文件路径经内部扩展路径访问；不修改系统注册表，不放宽来源及链接校验。旧2.0.2未完成准备按原计划、原哈希与原操作目录接续，保留备份、失败尝试、定位前像和回执。完整前提、命令、诊断与限制见[工作区管理与状态重定位](MANAGEMENT_AND_RELOCATION.md)。
