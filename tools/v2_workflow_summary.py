"""Read-only recovery guidance and current closure, never execution authority."""
import hashlib,json
from pathlib import Path
from contextlib import closing
from v2_state_store import StateStore,StateConflict,_json
from v2_evidence import _regular_path
from v2_recovery import require_project_review

def layers(*,success=True,verified=False,ready=False,operator_review=False):
    return {'operation_status':'SUCCESS' if success else 'BLOCKED','workspace_status':'VERIFIED' if verified else 'UNBOUND',
        'governance_readiness':'READY' if ready else 'NOT_READY','execution_authorization':'NOT_GRANTED',
        'external_writer_assurance':'OPERATOR_ATTESTED' if operator_review else 'UNKNOWN',
        'external_writer_isolation':'UNKNOWN','execution_authorized':False,'writes_performed':False}

def current_review(store):
    c=store.connection;epoch=c.execute('SELECT epoch FROM recovery_state').fetchone()[0]
    row=c.execute('SELECT review_id,report_json,receipt_json FROM recovery_review WHERE epoch=? ORDER BY rowid DESC LIMIT 1',(epoch,)).fetchone()
    if row is None:return None
    require_project_review(c,row[0],epoch)
    return {'review_id':row[0],'report':json.loads(row[1]),'receipt':json.loads(row[2])}

def task_recovery_view(store,task_id,revision,state):
    review=current_review(store);c=store.connection
    disposition=next((r['action'] for r in review['receipt'].get('next_tasks',[]) if r['task_id']==task_id and r['revision']==revision),None) if review else None
    restored=c.execute('SELECT source_backup_hash,reconciliation_required FROM recovery_state').fetchone()
    required=state=='PAUSED' and bool(restored[0])
    action='NONE'
    if required:action='recovery-review' if restored[1] else 'task.resume-after-recovery-or-task.revise'
    elif state=='PAUSED':action='run.resume-with-current-owned-checkpoint-or-task.revise'
    return {'resume_after_recovery_required':required,'recovery_disposition':disposition,
        'recommended_next_action':action,'current_recovery_review_id':review['review_id'] if review else None,
        'continuation_grants_execution':False}

def next_task_actions(state_dir, *, project_id,after_task_id='',limit=20):
    if type(limit) is not int or not 1<=limit<=100:raise ValueError('Bounded task page required')
    with closing(StateStore(Path(state_dir)/'state.db',readonly=True)) as store:
        c=store.connection;c.execute('BEGIN')
        if not c.execute('SELECT 1 FROM project WHERE project_id=?',(project_id,)).fetchone():raise StateConflict('Unknown Project')
        tasks=[]
        for task,revision,state in c.execute('SELECT task_id,revision,status FROM task WHERE project_id=? AND task_id>? ORDER BY task_id LIMIT ?',(project_id,after_task_id,limit+1)).fetchall():
            binding=c.execute('SELECT b.phase_id,b.phase_revision,p.revision,p.state FROM phase_task b JOIN phase p ON p.phase_id=b.phase_id WHERE b.task_id=? AND b.task_revision=?',(task,revision)).fetchone()
            blockers=[]
            if c.execute('SELECT reconciliation_required FROM recovery_state').fetchone()[0]:blockers.append('RECONCILIATION_REQUIRED')
            if binding and (binding[1]!=binding[2] or binding[3]!='ACTIVE'):blockers.append('PHASE_REVIEW_REQUIRED')
            dependencies=store.unresolved_dependencies(task,revision)
            if dependencies:blockers.append('DEPENDENCIES_NOT_ACCEPTED')
            if c.execute("SELECT 1 FROM operation WHERE task_id=? AND state IN ('INTENT_RECORDED','UNKNOWN')",(task,)).fetchone():blockers.append('UNRESOLVED_EFFECTS')
            tasks.append({'task_id':task,'revision':revision,'state':state,
                'phase':dict(zip(('phase_id','bound_revision','current_revision','state'),binding)) if binding else None,
                'unresolved_dependency_count':len(dependencies),'blockers':blockers,**task_recovery_view(store,task,revision,state)})
        result={'decision':'RECOVERY_TASK_ACTIONS','project_id':project_id,'tasks':tasks[:limit],
            'next_after_task_id':tasks[limit-1]['task_id'] if len(tasks)>limit else None,'epoch':c.execute('SELECT epoch FROM recovery_state').fetchone()[0],
            'manual_database_state_edits_supported':False,'writes_performed':False,'execution_authorized':False}
        c.execute('COMMIT');return result

def relocation_guidance(result):
    state=result['state'];steps=[];level='PREPARATION_INCOMPLETE'
    if state=='PREPARING':steps=['store-relocation-prepare-with-original-plan'];level='PREPARATION_INCOMPLETE'
    elif state=='RESTORED_QUARANTINED':steps=['recovery-review','store-relocation-plan','store-relocation-apply','phase-review-or-reactivation','workspace-final-verify'];level='RESTORED_NOT_ACTIVE'
    elif state=='RECONCILED':steps=['store-relocation-plan','store-relocation-apply','phase-review-or-reactivation','workspace-final-verify'];level='FORWARD_READY'
    elif state=='PREPARED':steps=['store-relocation-apply-with-original-forward-plan','phase-review-or-reactivation','workspace-final-verify'];level='FORWARD_CUTOVER_INCOMPLETE'
    elif state=='ACTIVE':
        from v2_entry import inspect_workspace_entry
        entry=inspect_workspace_entry(result['plan']['workspace_root'])
        result['current_workspace']=entry
        level='ACTIVE_PHASE_READY' if entry['phase_ready'] else 'ACTIVE_NOT_PHASE_READY'
        if not entry['phase_ready']:steps.append('phase-review-or-reactivation')
        steps+=['recovery-next-task-actions','workspace-final-verify']
    else:steps=['inspect-current-authority-and-original-journal'];level='AUTHORITY_REVIEW_REQUIRED'
    result.update(completion_level=level,next_required_actions=steps,
        authority_kind='ADOPTED_BINDING' if result['plan'].get('source_kind','ADOPTED')=='ADOPTED' else 'NATIVE_LOCATOR',
        business_completion_verified=False,operation_status='BLOCKED' if state=='PREPARING' else 'SUCCESS')
    return result

def _protocol_hashes(root):
    from v2_adoption import BINDING,SEALS
    from v2_backup import _hash
    return {p:_hash(root/p) for p in (BINDING,*SEALS,'.malts/native.json','.malts/management.json') if (root/p).exists()}

def final_verify(*,workspace,tool_root,operation_id=None,journal_root=None,verify_package=False):
    from v2_entry import inspect_entry,_workspace_format,workspace_readiness,_identity,_lifecycle_lock_present
    from malts_lifecycle import resolve_discovery
    from v2_relocation import status as relocation_status
    from v2_recovery import Recovery
    root=Path(workspace).absolute();_regular_path(root)
    entry=inspect_entry(workspace=root,tool_root=tool_root,verify_package=verify_package)
    result={'decision':'WORKSPACE_FINAL_VERIFICATION','runtime_discovered':entry.get('runtime_discovered',False),'entry':entry,
        'binding_verified':False,'store_active':False,'recovery_reconciled':False,'phase_ready':False,
        'execution_authorized':False,'business_tasks_started':None,'business_completion_verified':False,'writes_performed':False,
        'atomic_snapshot':False,'verification_scope':'CURRENT_DATABASE_SNAPSHOT_WITH_RECHECKED_PROTOCOL_AND_RUNTIME; not external-process isolation'}
    from v2_assurance import assurance
    result['execution_assurance']=assurance()
    if entry['status'] not in {'COMPATIBLE','OPTIONAL_REFRESH'}:
        return {**result,**layers(success=False,verified=entry.get('workspace_binding_verified',False)),
            'binding_verified':entry.get('workspace_binding_verified',False),'blockers':['ENTRY_REVIEW_REQUIRED']}
    first=resolve_discovery(tool_root)
    protocol=_protocol_hashes(root);selection=_workspace_format(root);state=Path(selection['state_dir'])
    if operation_id is not None:
        if not isinstance(operation_id,str) or __import__('re').fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',operation_id) is None:raise ValueError('Exact operation identity required')
        journal=Path(journal_root) if journal_root is not None else root/'.malts/recovery'/operation_id
        relocation=relocation_status(journal)
        if relocation['plan']['operation_id']!=operation_id or Path(relocation['plan']['state_dir'])!=state:raise StateConflict('Final verification operation or selected state differs')
        result['relocation']={'operation_id':operation_id,'state':relocation['state'],'completion_level':relocation['completion_level']}
        if relocation['state']!='ACTIVE':return {**result,**layers(success=False),'blockers':['RELOCATION_NOT_ACTIVE'],'next_required_actions':relocation['next_required_actions']}
        old=Path(relocation['plan']['old_state_dir']);result['old_store_retained']=(old/'state.db').is_file()
        if not result['old_store_retained']:raise StateConflict('Original store unavailable for final authority proof')
        with closing(StateStore(old/'state.db',readonly=True)) as previous:
            if relocation['plan'].get('source_kind','ADOPTED')=='ADOPTED':
                forward=relocation['forward']['plan']
                row=previous.connection.execute('SELECT state,new_epoch FROM migration_adoption WHERE adoption_id=?',(forward['parent_adoption_id'],)).fetchone()
                retired=row==('SUPERSEDED',relocation['plan']['old_epoch'])
                operation_receipt=relocation['forward']['receipt']
            else:
                from v2_native_authority import current
                fact=current(previous.connection)
                retired=fact is not None and fact['state']=='SUPERSEDED' and fact['operation_id']==operation_id and fact['plan_sha256']==relocation['plan']['plan_sha256']
                operation_receipt=relocation['receipt']
            if not retired:raise StateConflict('Old authority is not superseded by this transition')
        result['old_store_execution_authority_superseded']=True
        result['operation_receipt_sha256']=hashlib.sha256(_json(operation_receipt).encode('utf-8')).hexdigest()
    elif journal_root is not None:raise ValueError('Journal requires the exact operation ID')
    with closing(StateStore(state/'state.db',readonly=True)) as store:
        c=store.connection;c.execute('BEGIN');store.require_execution_ready()
        ready=workspace_readiness(store);inventory=Recovery(store)._inventory(c);review=current_review(store)
        counts=dict(c.execute('SELECT status,count(*) FROM task GROUP BY status').fetchall())
        task_views=[{'task_id':t,'revision':v,'state':s,**task_recovery_view(store,t,v,s)} for t,v,s in c.execute('SELECT task_id,revision,status FROM task ORDER BY task_id')]
        result.update(binding_verified=True,store_active=True,recovery_reconciled=not inventory['reconciliation_required'],
            project_verified=ready['project_definition_verified'],active_phase_verified=ready['active_phase'] is not None,
            task_bindings_verified=ready['profile']!='LONG_PROJECT' or ready['task_phase_bindings_verified']==ready['task_definitions_verified'],
            dependencies_verified=True,dependency_verification_scope='STRUCTURE_AND_CURRENT_DEFINITION; acceptance readiness is per Task',
            phase_ready=ready['phase_ready'],authority_kind=selection['authority_kind'],
            epoch=ready['epoch'],workspace_summary=ready,task_counts=counts,tasks=task_views,
            business_tasks_started=False,business_start_scope='THIS_READ_ONLY_VERIFICATION_STARTED_NO_TASK',
            active_registered_runs=c.execute("SELECT count(*) FROM execution_run WHERE state<>'CLOSED'").fetchone()[0],
            current_state_sha256=inventory['binding']['state_sha256'],recovery_review_sha256=hashlib.sha256(_json(review['receipt']).encode()).hexdigest() if review else None)
        from v2_governance import checked_phase_plan
        if ready['active_phase']:checked_phase_plan(store,ready['active_phase']['phase_id'],ready['active_phase']['revision'])
        second=resolve_discovery(tool_root)
        if _identity(first)!=_identity(second) or _lifecycle_lock_present(second) or protocol!=_protocol_hashes(root):raise StateConflict('Final verification inputs changed during observation')
        result['protocol_sha256']=protocol
        result.update(layers(verified=True,ready=ready['phase_ready'],operator_review=review is not None))
        result['completion_level']='CURRENT_AUTHORITY_GOVERNANCE_READY' if ready['phase_ready'] else 'CURRENT_AUTHORITY_GOVERNANCE_NOT_READY'
        result['next_required_actions']=[] if ready['phase_ready'] else ['phase-review-or-reactivation']
        if counts.get('PAUSED',0):result['next_required_actions'].append('recovery-next-task-actions')
        c.execute('COMMIT')
    result['completion_receipt_sha256']=hashlib.sha256(_json(result).encode('utf-8')).hexdigest()
    return result
