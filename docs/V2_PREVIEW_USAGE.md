# MALTS Controller Operations

Controllers use the verified runtime and selected state to query tasks and perform reviewed requests. The current Core format is Schema69 and version **2.0.0**. Ordinary project work can use installed Skills; the commands below describe the controller interface. Demonstrations require a separately selected new directory and do not call a model or install a Host.

<a id="v2-start"></a>
## 1. First complete local task

Save the Python below as quickstart.py and run `python -B quickstart.py '<verified-runtime>/tools/malts_v2.py' '<new-demo-directory>'`. Windows current-user DPAPI is required. The directory must not exist; preserve failures instead of rerunning blindly. It creates an isolated store, requests, a file and backup, calls no model, installs nothing and verifies only synthetic file integrity. Authority strings record existing permission, never create it.

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
## 2. Entry and long-project setup

Read tool Boot and discover. Adopted workspaces pass the business root to workspace; native v2 explicitly selects state root. Inspect governance-context, task-queue and context. Queries create no execution entities.

For a new long project, init is followed by project.define, phase.define with actual plan, phase.set-active and phase.bind-task for each Task revision. Require LONG_PROJECT and phase_ready=true from workspace. The demonstration above is TASK_ONLY, not long-project setup.

phase.define fields are phase_id, project_id, project_revision, expected_revision, goal, boundary (in_scope/out_of_scope arrays), acceptance, plan_ref, plan_sha256, authority_ref and request_id. plan_ref is an actual project-relative file; Task scope entries must belong to in_scope. Before revising an ACTIVE Phase, settle effects/Hosts/Runs, pause, define a new revision and rebind affected Tasks.

A new long workspace has an executable hierarchy, not only a database directory. Project definition identifies the original/current goal and global criteria; Phase definition identifies a bounded goal, in/out scope, acceptance and actual plan; tasks identify outputs within that scope and exact dependencies. Activate the reviewed Phase and bind each applicable task revision.

For example, a compatibility stage can allow module/report outputs and exclude deployment. Adding deployment later requires revisiting the boundary and affected task definitions, not issuing an unrelated write Grant because the store exists. Verify the actual plan bytes before defining its SHA-256.

Existing adopted work enters through workspace/binding and current context. Native v2 state is selected explicitly. Do not migrate or initialize either merely to answer a status query; those actions have separate contracts.

## 3. Requests and responses

Capabilities advertise current action contracts. Request JSON contains only action/arguments. Preview with request --state-dir --request-file, then apply the same reviewed request within authorized scope. NOT_APPLIED/NOT_EVALUATED proves neither execution nor readiness.

Successful raw bodies use decision=REQUEST_PROCESSED with action fields inside result. Raw MCP preparation uses response.result.request_hash; a helper already returning result uses request_hash directly. Errors retain top-level decision/error_code without successful result.

Host policy limits MCP write interfaces; read-only endpoints grant no execution. Clients cannot override project/actor/authority or guess Grant IDs. Use exact execution_inputs and full current preimage_policy_templates; missing inputs require the controller's scope check.

A controller request has a closed top-level shape:

```json
{"action":"phase.bind-task","arguments":{"task_id":"<current-task-id>","task_revision":1,"phase_id":"<reviewed-phase-id>","phase_revision":1,"authority_ref":"<existing-authorization-reference>"}}
```

This is an argument-format example; use the actual current IDs/revisions and existing authorization, not its placeholders. Preview the exact request file, then apply within the reviewed scope. The preview does not evaluate all execution readiness checks.

Raw success is {decision: REQUEST_PROCESSED, action: ..., result: ...}. For operation.prepare, obtain result.request_hash and pass it as expected_request_hash to the matching adapter. A convenience helper returning only result has already unwrapped it. Error responses have no successful result body; inspect error_code and any value-free reason_code rather than treating transport success as business success.

The action catalog is derived from the current service signatures. If an action is not advertised, do not infer it from a status or copy an older API. A Host-bound worker must not switch to a controller endpoint to escape its assigned scope.

<a id="v2-accept"></a>
## 4. Files and acceptance

Read preparation has only tool='read-file' and granted relative path; execution carries read limits. Updates require tool='update-file', path, UTF-8 content, current expected_sha256 and full preimage_policy; preserve old bytes and check the exclusively opened file. Creation never overwrites.

Criteria specify methods/minimum levels. Verification begins after dependencies/effects/Hosts settle; rework is explicit. Managed-file verification proves file integrity, with business checks separate. After acceptance, task-verify checks current proof; historical completion and exit 0 are insufficient.

A managed update needs an existing reviewed file and its current byte hash. Obtain the Host-approved full preimage policy, prepare the exact update parameters, then call the qualified update adapter with the returned hash. Do not pre-record a manual intent for an adapter that owns that step. A changed preimage rejects execution rather than being silently overwritten.

For meaningful acceptance, connect each criterion to the actual result. A file-integrity demonstration establishes its synthetic bytes; a migration task additionally needs the compatibility observation requested by the user. Record unavailable/failed checks without changing the criterion to the result that happened to pass.

After effects and Hosts settle, verify and accept the current revision. If repairs are needed under verification, use rework first. Retain original observations on failure; a new operation ID is not a general retry mechanism for UNKNOWN.

<a id="v2-recovery"></a>
## 5. Pause, backup and reconciliation

Use current Run/checkpoint for pause/resume instead of a replacement Run replaying uncertainty. PAUSE_REQUESTED inspects both pending operations and Hosts. Acknowledgements, PAUSED and expired leases are not quiescence proof.

Preview backup --state-dir --destination, then apply; verify-backup is read-only. Read restore --help and bind verified backup SHA-256, a new destination and reviewed resources. Restoration creates a new epoch and quarantine. Reconcile subsequent work/effects/budgets without reviving Grants/Hosts/allowances. Backup is not restore permission; cross-user DPAPI recovery is uncertified.

Recovery inspection/review and update-repair-plan retain original operation/target identities. REQUIRES_REVIEW is unresolved. Blob inventories/diagnostics do not authorize deletion.

<a id="v2-collaboration"></a>
## 6. Hosts and collaboration

Match approved roles/resources, actual adapter, identity, model/effort constraints and cumulative budgets. Use advertised controller contracts, not RPC IDs as Task/Run identities. Do not silently weaken hard constraints; unobservable effective model identity remains unknown.

Workers return artifacts and uncertainties without accepting their own active dispatch. Controllers verify after Host settlement. Associated Job exit proves that owned process tree only, not arbitrary writers/GUI model cancellation. Delegation, background and unattended work need corresponding scope.

<a id="v2-growth"></a>
## 7. Growth trials

Use current growth.propose, begin-trial, record-outcome, validate and retire contracts. Proposals bind eligible sources; trials bind exact Task/profile and existing permission. Future evidence must be comparable; retain neutral/harmful/unknown. Late outcomes, replay and restoration cannot revive retired material. Global Skill/Prompt application has a separate scope.

A proposal's current closed JSON body contains action, check, boundary and applicability. applicability contains task_types, tools and failure_signatures, with at least one constraint. For example, a proposal can limit a pre-restore format check to recovery tasks and a selected Host. Its source evidence must allow Growth use; merely retaining a recovery source is insufficient.

growth.propose binds proposal/source evidence. growth.begin-trial binds candidate/owner, the admitted operation and expected_request_hash, actor, task_type/tool, rollback_ref and existing authority. It does not create a fresh operation budget. After an actual later use, growth.record-outcome identifies the trial, eligible evidence, outcome/severity and independence_key.

Validation uses current assessment identity and reviewed evidence; retirement also checks the expected state and reviewed counterevidence. A late positive observation cannot revive a deprecated/removed/rejected candidate. Keep neutral or harmful observations, and do not publish a global rule merely because a project trial was recorded.

<a id="v2-handoff"></a>
## 8. Handoffs and artifacts

Handoff-preview with exact Task revision returns a bounded view/token. Preserve manual notes, then guarded publication compares an existing reviewed target, source token and preimage. Missing output requires separate creation. Partial views/unresolved publication intents are not ready. Artifact registration/promotion/reconciliation/Shared proof separately check identities and relationships.

For a guarded existing handoff, capture its reviewed preimage using handoff.capture-file and select that note in the preview. Review the full markdown/source_token, then handoff.publish binds target_relative, target_note_id, the selected note_ids and explicit publication authority. A partial preview or changed target rejects publication. Inspect an interrupted publication with handoff.inspect-publication before any further write.

The preview token covers presented owner facts, not all source files. Other preserved notes are reviewed historical data; publication's file guard proves only its selected target preimage. Recheck any external source whose current content decides the next action.

Artifacts have independent content, ownership, relation and reuse checks. Current controller actions include artifact.register, artifact.promote, artifact.reconcile and artifact.retire-shared, with exact current contracts. SUPERSEDED is a disposition, not a callable artifact.supersede endpoint. See [Handoff](HANDOFF.md) and [State Contract](V2_STATE_CONTRACT.md).

<a id="v2-migration"></a>
## 9. Adoption and upgrade

Explicit legacy adoption/forward contracts review goals, mapping, writers, UNKNOWN, backup and seals, then preview/apply. After adoption, recovery stays in v2. Never remove binding/seals, patch DB or revive Markdown write authority. See [Update](UPDATE.md) and the [State Contract](V2_STATE_CONTRACT.md).
