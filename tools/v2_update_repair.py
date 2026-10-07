"""Controller-reviewed repair of one divergent update; never implicit rollback.

Review hashes bind facts, not user identity. The trusted controller must resolve
real authorization and issue a new Grant. This API is not a client MCP tool.
"""
import hashlib,json
from pathlib import Path
from v2_state_store import StateConflict,_json,_text
from v2_operations import Operations
from v2_authority import task_authority_context,authority_hash
from v2_evidence import BlobStore,_regular_path
from v2_evidence_policy import validate_descriptor,require_access
from v2_contracts import criteria
from v2_file_update import exclusive_existing_file,preimage_record,read_preimage,preserve_preimage
from v2_local_host import unambiguous_relative_file
from v2_operation_inputs import operation_parameters


def _facts(host, original_operation_id, repair_operation_id, grant_id, actor, target, preimage_policy):
    for key,value in (('original_operation_id',original_operation_id),('repair_operation_id',repair_operation_id),('grant_id',grant_id),('actor',actor)):
        _text(value,key)
    if original_operation_id==repair_operation_id or target not in {'PREIMAGE','REQUESTED_RESULT'}:
        raise ValueError('Choose a distinct repair operation and explicit target')
    store=host.store; c=store.connection
    store.require_execution_ready()
    row=c.execute('''SELECT o.task_id,o.task_revision,o.state,o.execution_epoch,o.request_json,g.resource,g.actor,p.resource_root,t.project_id,o.grant_id
        FROM operation o JOIN execution_grant g ON g.grant_id=o.grant_id JOIN task t ON t.task_id=o.task_id
        JOIN project p ON p.project_id=t.project_id WHERE o.operation_id=?''',(original_operation_id,)).fetchone()
    if row is None or row[6]!=actor: raise PermissionError('Repair requires the bound operation actor')
    if grant_id==row[9]: raise PermissionError('Repair needs a separately authorized Grant')
    if row[2] not in {'INTENT_RECORDED','UNKNOWN'}: raise StateConflict('Repair requires an unresolved original operation')
    epoch=c.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]
    if row[3]!=epoch: raise StateConflict('Old epoch requires full recovery review')
    task=store.task(row[0])
    if task['revision']!=row[1]: raise StateConflict('Task revision changed; use full recovery review')
    record=preimage_record(store,original_operation_id)
    require_access(record['policy'],owner=row[8],purpose='recovery',revoked=False)
    data=read_preimage(store,original_operation_id)
    if target=='REQUESTED_RESULT': data=operation_parameters(store,original_operation_id,actor=actor)['content'].encode('utf-8')
    content=data.decode('utf-8')  # no implicit transcoding of a binary preimage
    if not isinstance(preimage_policy,dict) or not isinstance(preimage_policy.get('target'),dict): raise ValueError('Repair preimage policy required')
    criterion=preimage_policy['target'].get('criterion')
    validate_descriptor(preimage_policy,project_id=row[8],task_id=row[0],task_revision=row[1],criterion=criterion)
    if criterion not in {item['criterion_id'] for item in criteria(task['acceptance'])}: raise StateConflict('Unknown repair capture criterion')
    require_access(preimage_policy,owner=row[8],purpose='recovery',revoked=False)
    grant=Operations(store)._grant(c,grant_id,actor,row[5],'write')
    if grant[:2]!=(row[0],row[1]): raise PermissionError('Repair Grant must bind the original Task revision')
    Operations(store).require_operation_budget(c,grant_id,grant)
    root=Path(row[7]).absolute(); _regular_path(root)
    if host.required_resource_root is not None and root.resolve()!=host.required_resource_root: raise PermissionError('Repair root differs from Host policy')
    path=root/unambiguous_relative_file(row[5])
    base={'schema':1,'original_operation_id':original_operation_id,'repair_operation_id':repair_operation_id,
        'grant_id':grant_id,'actor':actor,'target':target,'preimage_policy':preimage_policy,
        'original_request_hash':record['request_hash'],'resource':row[5],
        'authority_context_sha256':authority_hash(task_authority_context(store,row[0])),
        'target_sha256':hashlib.sha256(data).hexdigest()}
    return base,path,content


def plan_update_repair(host, *, original_operation_id, repair_operation_id, grant_id, actor, target, preimage_policy):
    base,path,_=_facts(host,original_operation_id,repair_operation_id,grant_id,actor,target,preimage_policy)
    with exclusive_existing_file(path) as stream:
        current=stream.read(16777217)
    if len(current)>16777216: raise ValueError('Repair snapshot exceeds 16 MiB')
    base['current_sha256']=hashlib.sha256(current).hexdigest()
    return {'review':base,'review_sha256':authority_hash(base),'writes_performed':False,'execution_authorized':False}


def repair_update(host, *, review, approved_sha256, authority_ref):
    _text(authority_ref,'authority_ref')
    fields={'schema','original_operation_id','repair_operation_id','grant_id','actor','target','preimage_policy',
            'original_request_hash','resource','authority_context_sha256','target_sha256','current_sha256'}
    if not isinstance(review,dict) or set(review)!=fields or review['schema']!=1 or authority_hash(review)!=approved_sha256:
        raise StateConflict('Repair differs from the approved exact review')
    store=host.store; c=store.connection; repair_id=review['repair_operation_id']
    fingerprint=authority_hash([review,authority_ref])
    previous=c.execute("SELECT details_json FROM execution_audit WHERE kind='FILE_UPDATE_REPAIR' AND subject_id=?",(repair_id,)).fetchone()
    if previous:
        previous=json.loads(previous[0])
        if previous['request_hash']!=fingerprint: raise StateConflict('Repair identity is immutable')
        return host.update_file(operation_id=repair_id,actor=review['actor'],expected_request_hash=previous['prepared_request_hash'])
    arguments={key:review[key] for key in ('original_operation_id','repair_operation_id','grant_id','actor','target','preimage_policy')}
    base,path,content=_facts(host,**arguments)
    with exclusive_existing_file(path) as stream:
        current=stream.read(16777217)
        if len(current)>16777216 or hashlib.sha256(current).hexdigest()!=review['current_sha256']:
            raise StateConflict('Current bytes changed after repair review')
        with store.transaction() as c:
            # Recheck Task/Grant/root/epoch under the transaction which retires
            # the original uncertainty and creates the new pending operation.
            latest,latest_path,content=_facts(host,**arguments)
            latest['current_sha256']=review['current_sha256']
            if latest!=review or latest_path!=path: raise StateConflict('Repair context changed before commit')
            if c.execute('SELECT 1 FROM operation WHERE operation_id=?',(repair_id,)).fetchone(): raise StateConflict('Repair ID already exists')
            old_hash=hashlib.sha256(current).hexdigest()
            ops=Operations.in_transaction(store)
            ops.observe(observation_id=repair_id+'-original-reviewed',operation_id=review['original_operation_id'],actor=review['actor'],
                outcome='FAILED',evidence_ref='reviewed-partial-update:'+approved_sha256)
            prepared=ops.prepare(operation_id=repair_id,grant_id=review['grant_id'],actor=review['actor'],resource=review['resource'],effect='write',
                parameters={'tool':'update-file','path':review['resource'],'content':content,'expected_sha256':old_hash,'preimage_policy':review['preimage_policy']},capture_authority_ref=authority_ref)
            preserve_preimage(store,repair_id,current,prepared['request_hash'])
            ops._audit(c,'FILE_UPDATE_REPAIR',repair_id,{'request_hash':fingerprint,'approved_sha256':approved_sha256,
                'authority_ref':authority_ref,'original_operation_id':review['original_operation_id'],'prepared_request_hash':prepared['request_hash']})
    # Any intervening filesystem change is rejected by the ordinary update
    # adapter. A crash here leaves a durable PREPARED repair, never a false done.
    return host.update_file(operation_id=repair_id,actor=review['actor'],expected_request_hash=prepared['request_hash'])
