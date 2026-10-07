# MALTS 2.0.0 v2 操作说明

文件名保留既有链接；本页说明当前正式接口，不表示仍需使用预览版。当前格式是 Core Schema69；使用精确运行根和已验证 state。以下控制端示例仅在用户授权的新演示目录运行；普通使用优先由已安装 Skill 引导。

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
state = demo / 'state'
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
call('init', '--state-dir', state, '--resource-root', demo,
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
            parameters={'tool': 'create-file', 'path': 'hello.txt', 'content': 'Hello MALTS 2.0.0\n'})
request('operation.create-file', operation_id='OP1', actor='demo', expected_request_hash=p['request_hash'])
assert (demo / 'hello.txt').read_bytes() == b'Hello MALTS 2.0.0\n'
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

新长期工作区在显式 `init` 后还需：`project.define` 定义当前目标/验收；`phase.define` 绑定实际计划；`phase.set-active` 激活；`phase.bind-task` 绑定每个 Task revision。最后 `workspace` 必须报告 LONG_PROJECT 和 `phase_ready=true`。上方演示只是 TASK_ONLY，不能冒充长期初始化。

`phase.define` 的字段为 phase_id、project_id、project_revision、expected_revision、goal、boundary（in_scope/out_of_scope 数组）、acceptance、plan_ref、plan_sha256、authority_ref、request_id；plan_ref 是相对项目资源根的真实文件。scope 必须逐项在 in_scope 中。更改 ACTIVE Phase 前先处理 pending effects/Hosts/Runs，再 pause、define 新 revision 并重绑定受影响任务。

## 3. 请求和返回

`capabilities` 提供当前动作参数合同。request 文件只含 `action` 与 `arguments`；先 `request --state-dir '<state>' --request-file '<file>'`，再对已授权范围使用相同请求加 `--apply`。dry-run 返回 NOT_APPLIED/NOT_EVALUATED，既不执行也不证明就绪。

成功外层是 `decision=REQUEST_PROCESSED`，具体字段在 `result`。原始 MCP prepare 结果使用 `response.result.request_hash`；已经主动解包为 result 的客户端才直接取 request_hash。错误保留 top-level decision/error_code，无成功 result。

MCP 写接口由 Host policy 限定；只读接口不提供授权或执行。客户端不能覆盖 project/actor/authority，不能猜 Grant ID。use current context execution_inputs 的准确 ID、resource/effect 和完整 preimage_policy_templates；缺失时由控制端核既有范围。

<a id="v2-accept"></a>
## 4. 文件与验收

受管读的 prepare parameters 只含 `tool='read-file'` 和 granted relative path；read limits 放 execution。更新需要 `tool='update-file'`、path、UTF-8 content、当前 expected_sha256 和完整 preimage_policy，保存原文并核独占文件。creation 不能覆盖。

criterion 必须指定方法和最低等级。`verification.begin` 结清依赖、操作和受管 Host 后进入 VERIFYING；修复需 `verification.rework`。`verification.managed-files` 固定提供文件完整性证据，真实业务另验。`task.accept` 后用 `task-verify` 检查当前证明；历史完成查询或 exit 0 不充分。

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

<a id="v2-handoff"></a>
## 8. 交接和成果

`handoff-preview --state-dir '<state>' --task-id '<task>' --task-revision <revision>` 返回有界视图/令牌。先保全手工原文，再按 `handoff.publish` 合同核现有目标、来源令牌与前像；不存在目标先单独创建。部分页或未决 publication intent不能宣称 ready。Artifact register/promote/reconcile/Shared proof 分别核身份与关系，旧关系不是当前复用许可。

<a id="v2-migration"></a>
## 9. 历史采用与升级

旧工作区只通过已选择的 legacy adoption/forward合同迁入 v2：审阅目标、映射、当前写者、UNKNOWN、备份与source seal，再 preview/apply。采用成功之后只在 v2内前向恢复。不要删除binding/seal、直接编辑DB或恢复旧Markdown写权。版本更新见[更新](UPDATE.md)，完整机制见[状态合同](V2_STATE_CONTRACT.md)。
