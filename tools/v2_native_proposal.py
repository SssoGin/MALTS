"""Controller-mediated native Worker proposals;not a Worker permission endpoint.

Native spawning cannot inject a per-dispatch MCP configuration. The native
Worker returns a closed candidate;the trusted controller reviews one selection
and applies it with the original actor's existing Grant and file adapters.
No new Grant,successor or acceptance authority is created here.
"""
import json,re
from contextlib import nullcontext
from v2_state_store import StateConflict
from v2_native_agent_host import NativeAgentHost
from v2_operations import Operations
from v2_local_host import LocalFileHost,unambiguous_relative_file
from v2_runtime_admission import runtime_admission

FORMAT='malts.native-worker-proposal.v1'
MAX_PROPOSAL_BYTES=131072

def _closed(request):
    if not isinstance(request,dict) or set(request)!={'proposal','index','preimage_policy'}:
        raise ValueError('Reviewed proposal,selection and Host preimage policy required')
    proposal=request['proposal']
    if (not isinstance(proposal,dict) or set(proposal)!={'format','dispatch_id','task_id','task_revision','proposals'} or
        proposal['format']!=FORMAT or type(proposal['task_revision']) is not int or proposal['task_revision']<1):
        raise ValueError('Closed native Worker proposal required')
    raw=json.dumps(proposal,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
    if len(raw)>MAX_PROPOSAL_BYTES:raise ValueError('Native proposal exceeds limit')
    items=proposal['proposals'];index=request['index']
    if not isinstance(items,list) or not 1<=len(items)<=8 or type(index) is not int or not 0<=index<len(items):
        raise ValueError('Bounded explicit proposal selection required')
    for item in items:
        fields={'operation_id','grant_id','tool','path','content'}
        if not isinstance(item,dict) or item.get('tool') not in {'create-file','update-file'}:raise ValueError('Only existing file adapters are supported')
        if item['tool']=='update-file':fields.add('expected_sha256')
        if set(item)!=fields:raise ValueError('Closed file proposal required')
        for key in ('operation_id','grant_id'):
            if not isinstance(item[key],str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',item[key]) is None:raise ValueError('Bounded original effect identity required')
        unambiguous_relative_file(item['path'])
        if not isinstance(item['content'],str) or len(item['content'].encode('utf-8'))>65536:raise ValueError('Bounded UTF8 content required')
        if item['tool']=='update-file' and (not isinstance(item['expected_sha256'],str) or re.fullmatch('[A-Fa-f0-9]{64}',item['expected_sha256']) is None):
            raise ValueError('Exact reviewed preimage SHA256 required')
    return proposal,items[index]

def native_worker_proposal(service,*,dispatch_id,request,capture_authority_ref,apply=False):
    """Preview is zero-write;apply rechecks current admission and existing Grant.

    The selected proposal must equal the retained actual native result. This
    binds data provenance,not OS identity. Caller review authorizes selection;
    Worker text alone never authorizes an effect.
    """
    if not isinstance(service.adapter,NativeAgentHost) or service.adapter.role!='malts_worker':
        raise PermissionError('Native Worker dispatch required')
    if not isinstance(capture_authority_ref,str) or not capture_authority_ref:raise PermissionError('Trusted controller capture review required')
    proposal,item=_closed(request)
    tool_root=service.runtime_for_dispatch(dispatch_id,require_record=True)
    with runtime_admission(tool_root) if tool_root is not None else nullcontext():
        with service.store.transaction() if apply else nullcontext(service.store.connection) as db:
            row=service._row(dispatch_id)
            if (proposal['dispatch_id'],proposal['task_id'],proposal['task_revision'])!=(dispatch_id,row['task_id'],row['task_revision']):
                raise StateConflict('Proposal differs from original Task dispatch')
            if row['profile_revision']!=service.adapter.profile_revision:raise StateConflict('Native Worker profile changed')
            service.adapter.validate_spawn_inputs()
            if not row['launch_committed'] or row['state']!='RUNNING' or row['cancel_requested'] or row['quiesced']:
                raise StateConflict('Native Worker is no longer admitted for new effects')
            candidate=service.adapter.private_result(backend_key=row['backend_key'],purpose='verification')['candidate_message']
            if not isinstance(candidate,str) or len(candidate.encode('utf-8'))>MAX_PROPOSAL_BYTES:raise ValueError('Retained actual proposal is unavailable or exceeds bound')
            retained=json.loads(candidate)
            _closed(dict(proposal=retained,index=request['index'],preimage_policy=request['preimage_policy']))
            canonical=lambda value:json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
            if canonical(retained)!=canonical(proposal):raise StateConflict('Proposal differs from retained native output')
            ops=Operations.in_transaction(service.store) if apply else Operations(service.store)
            grant=ops._grant(db,item['grant_id'],row['actor'],item['path'],'write')
            if grant[:2]!=(row['task_id'],row['task_revision']):raise PermissionError('Grant differs from original Task revision')
            parameters={key:item[key] for key in ('tool','path','content')}
            if item['tool']=='update-file':
                policy=request['preimage_policy']
                if not isinstance(policy,dict):raise ValueError('Controller reviewed preimage policy required for update')
                parameters.update(expected_sha256=item['expected_sha256'],preimage_policy=policy)
            elif request['preimage_policy'] is not None:raise ValueError('Creation does not accept preimage policy')
            if not apply:return dict(decision='PREVIEW',dispatch_id=dispatch_id,operation_id=item['operation_id'],effect='write',tool=item['tool'],writes_performed=False)
            prepared=ops.prepare(operation_id=item['operation_id'],grant_id=item['grant_id'],actor=row['actor'],resource=item['path'],
                effect='write',parameters=parameters,capture_authority_ref=capture_authority_ref)
        host=LocalFileHost(service.store)
        result=(host.create_file if item['tool']=='create-file' else host.update_file)(operation_id=item['operation_id'],actor=row['actor'],expected_request_hash=prepared['request_hash'])
        return dict(decision='NATIVE_PROPOSAL_APPLIED',operation_id=item['operation_id'],result=result,task_accepted=False)
