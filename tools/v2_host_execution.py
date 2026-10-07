"""Trusted-controller Host protocol. Not a public dispatch/approval endpoint.

The adapter owns true Host facts and authorization. References and hashes do
not authenticate a user. This module never accepts an Agent-supplied adapter.
An admitted Host invocation is not a provider physical-request count, a returned
Run is not Task acceptance, and owned-Run quiescence is not whole-machine safety.
"""
import json,uuid
from contextlib import contextmanager,nullcontext
from pathlib import Path
from datetime import datetime,timezone
from v2_state_store import StateConflict,_json,_text
from v2_authority import task_authority_context
from v2_definition_content import encode,decode,request_fingerprint
from v2_governance import require_task_phase
from v2_operations import Operations
from v2_task_lifecycle import reconcile_effect_state
from v2_protected_inputs import ProtectedInputError


class HostCallUncertain(StateConflict):
    """Safe outward error; never echoes a Host exception or request payload."""


def configure_budget(store,*,project_id,max_launch_intents,max_delegated_agents,host_limits,
                     max_queries,max_cancels,expires_at,authority_ref):
    """Initial reviewed Project budget; later changes require amend_budget."""
    for value in (max_launch_intents,max_delegated_agents,max_queries,max_cancels):
        if type(value) is not int or value<1:raise ValueError('Explicit positive dispatch budgets required')
    _text(authority_ref,'authority_ref')
    if not isinstance(host_limits,list) or not host_limits:raise ValueError('Host occupancy limits required')
    seen=set()
    for item in host_limits:
        if not isinstance(item,dict) or set(item)!={'host_id','max_total_occupancy','controller_occupancy'}:raise ValueError('Invalid Host budget')
        _text(item['host_id'],'host_id')
        if item['host_id'] in seen:raise ValueError('Duplicate Host policy')
        seen.add(item['host_id'])
        if (type(item['max_total_occupancy']) is not int or type(item['controller_occupancy']) is not int or
                not 0<=item['controller_occupancy']<item['max_total_occupancy']):raise ValueError('Host budget must reserve controller occupancy')
    if expires_at is not None:Operations._instant(expires_at)
    values=(project_id,max_launch_intents,max_delegated_agents,_json(sorted(host_limits,key=lambda x:x['host_id'])),
            max_queries,max_cancels,expires_at,authority_ref)
    with store.transaction() as c:
        if not c.execute('SELECT 1 FROM project WHERE project_id=?',(project_id,)).fetchone():raise StateConflict('Unknown Project')
        old=c.execute('SELECT * FROM dispatch_budget WHERE project_id=?',(project_id,)).fetchone()
        if old:
            if (*old[:7],decode(old[7],project_id,'dispatch-budget',project_id,0,'authority_ref'))!=values:raise StateConflict('Existing dispatch budget differs; use reviewed amendment without resetting usage')
            return 'REPLAY'
        values=(*values[:7],encode(authority_ref,project_id,'dispatch-budget',project_id,0,'authority_ref'))
        c.execute('INSERT INTO dispatch_budget(project_id,max_launch_intents,max_delegated_agents,host_limits_json,max_queries,max_cancels,expires_at,authority_ref) VALUES (?,?,?,?,?,?,?,?)',values)
        return 'CONFIGURED'


def revoke_budget(store,*,project_id,authority_ref):
    """Stop admissions/effect grants; the controller must still cancel/query Hosts."""
    _text(authority_ref,'authority_ref')
    with store.transaction() as c:
        row=c.execute('SELECT revoked,revocation_ref FROM dispatch_budget WHERE project_id=?',(project_id,)).fetchone()
        if row is None:raise StateConflict('Unknown dispatch budget')
        if row[0]:
            if decode(row[1],project_id,'dispatch-budget',project_id,0,'revocation_ref')!=authority_ref:raise StateConflict('Dispatch revocation is immutable')
            return 'REPLAY'
        authority_ref=encode(authority_ref,project_id,'dispatch-budget',project_id,0,'revocation_ref')
        c.execute('UPDATE dispatch_budget SET revoked=1,revocation_ref=? WHERE project_id=?',(authority_ref,project_id))
        c.execute('UPDATE execution_grant SET revoked=1 WHERE actor IN (SELECT actor FROM host_dispatch WHERE project_id=?)',(project_id,))
        c.execute("""UPDATE host_dispatch SET cancel_requested=1,state=CASE WHEN state='RUNNING' THEN 'CANCEL_REQUESTED' ELSE state END
            WHERE project_id=? AND launch_committed=1 AND coalesce(quiesced,0)=0""",(project_id,))
        c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
            ('DISPATCH_AUTHORITY_REVOKED',project_id,_json({'authority_ref':authority_ref,'host_stop_confirmed':False})))
        return 'REVOKED'


def budget_basis(store,*,project_id):
    c=store.connection
    if not c.in_transaction:
        c.execute('BEGIN')
        try:return budget_basis(store,project_id=project_id)
        finally:c.execute('ROLLBACK')
    row=c.execute('SELECT revision,carried_launches,consumption_known,revoked,consumption_basis FROM dispatch_budget WHERE project_id=?',(project_id,)).fetchone()
    if row is None:raise StateConflict('Unknown dispatch budget')
    calls=[]
    for identity,queries,cancels in c.execute('SELECT dispatch_id,carried_queries,carried_cancels FROM host_dispatch WHERE project_id=? ORDER BY dispatch_id',(project_id,)):
        counts=dict(c.execute('SELECT method,count(*) FROM host_invocation WHERE dispatch_id=? GROUP BY method',(identity,)).fetchall())
        calls.append({'dispatch_id':identity,'queries':queries+counts.get('QUERY',0),'cancels':cancels+counts.get('CANCEL',0)})
    result={'project_id':project_id,'revision':row[0],'epoch':c.execute('SELECT epoch FROM recovery_state').fetchone()[0],
        'total_launch_intents':row[1]+c.execute('SELECT coalesce(sum(launch_committed),0) FROM host_dispatch WHERE project_id=?',(project_id,)).fetchone()[0],
        'dispatch_calls':calls,'consumption_known':bool(row[2]),'revoked':bool(row[3]),'consumption_basis':row[4]}
    return {**result,'basis_hash':request_fingerprint(c,project_id,result)}


def authorize_recovery_calls(store,*,project_id,expected_epoch,query_limit,cancel_limit,authority_ref,expected_limits=None):
    """Explicit additional recovery-only allowance, not the old remaining budget."""
    _text(authority_ref,'authority_ref')
    if any(type(v) is not int or v<0 for v in (query_limit,cancel_limit)) or query_limit+cancel_limit==0:
        raise ValueError('An explicit bounded recovery call allowance is required')
    with store.transaction() as c:
        row=c.execute('SELECT consumption_known FROM dispatch_budget WHERE project_id=?',(project_id,)).fetchone()
        epoch=c.execute('SELECT epoch FROM recovery_state').fetchone()[0]
        if row!=(0,) or epoch!=expected_epoch:raise StateConflict('Recovery call allowance requires the current unknown-consumption epoch')
        values=(project_id,epoch,query_limit,cancel_limit,authority_ref)
        prior=c.execute('SELECT * FROM dispatch_recovery_calls WHERE project_id=? AND epoch=?',(project_id,epoch)).fetchone()
        if prior:
            plain=decode(prior[4],project_id,'recovery-call-budget',epoch,0,'authority_ref')
            if (*prior[:4],plain)==values:return 'REPLAY'
            if expected_limits!={'query_limit':prior[2],'cancel_limit':prior[3],'authority_ref':plain}:
                raise StateConflict('Recovery allowance review is stale or missing')
            used=dict(c.execute('''SELECT i.method,count(*) FROM host_invocation i JOIN host_dispatch d ON d.dispatch_id=i.dispatch_id
                WHERE d.project_id=? AND i.epoch=? GROUP BY i.method''',(project_id,epoch)).fetchall())
            if query_limit<used.get('QUERY',0) or cancel_limit<used.get('CANCEL',0):
                raise StateConflict('Recovery allowance cannot erase consumed calls')
            authority_ref=encode(authority_ref,project_id,'recovery-call-budget',epoch,0,'authority_ref')
            protected_prior={**expected_limits,'authority_ref':prior[4]}
            c.execute('UPDATE dispatch_recovery_calls SET query_limit=?,cancel_limit=?,authority_ref=? WHERE project_id=? AND epoch=?',
                (query_limit,cancel_limit,authority_ref,project_id,epoch))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('RECOVERY_CALL_ALLOWANCE_AMENDED',project_id,_json({'epoch':epoch,'prior':protected_prior,
                    'query_limit':query_limit,'cancel_limit':cancel_limit,'authority_ref':authority_ref})))
            return 'AMENDED_RECOVERY_CALLS'
        if expected_limits is not None:raise StateConflict('No prior recovery allowance to amend')
        values=(*values[:4],encode(authority_ref,project_id,'recovery-call-budget',epoch,0,'authority_ref'))
        c.execute('INSERT INTO dispatch_recovery_calls VALUES (?,?,?,?,?)',values)
        return 'AUTHORIZED_RECOVERY_CALLS'


def amend_budget(store,*,project_id,expected_revision,expected_epoch,expected_basis_hash,request_id,max_launch_intents,
                 max_delegated_agents,max_queries,max_cancels,expires_at,authority_ref,
                 reauthorize=False,usage_reconciliation=None):
    """Trusted-controller amendment, not a user-approval or usage verifier.

    A recovered ledger is a lower bound. Reconciliation requires the controller
    to supply independently reviewed cumulative usage, with a provenance ref.
    Neither a ref nor this API proves its truth. Previous grants stay revoked.
    """
    for field,value in (('project_id',project_id),('expected_epoch',expected_epoch),('request_id',request_id),('authority_ref',authority_ref)):
        _text(value,field)
        if len(value)>256:raise ValueError('Budget identifier/reference exceeds limit')
    if type(expected_revision) is not int or expected_revision<1 or type(reauthorize) is not bool:
        raise ValueError('Invalid budget revision or reauthorization flag')
    for value in (max_launch_intents,max_delegated_agents,max_queries,max_cancels):
        if type(value) is not int or value<1:raise ValueError('Positive budget limits are required')
    if expires_at is not None:Operations._instant(expires_at)
    if usage_reconciliation is not None:
        if (not isinstance(usage_reconciliation,dict) or set(usage_reconciliation)!={'total_launch_intents','evidence_ref','dispatch_calls'} or
                type(usage_reconciliation['total_launch_intents']) is not int or usage_reconciliation['total_launch_intents']<0):
            raise ValueError('Explicit cumulative usage and evidence reference required')
        _text(usage_reconciliation['evidence_ref'],'evidence_ref')
        if len(usage_reconciliation['evidence_ref'])>256:raise ValueError('Usage evidence reference too long')
    payload=[project_id,expected_revision,expected_epoch,expected_basis_hash,max_launch_intents,max_delegated_agents,max_queries,
             max_cancels,expires_at,authority_ref,reauthorize,usage_reconciliation]
    with store.transaction() as c:
        fingerprint=request_fingerprint(c,project_id,payload)
        old=c.execute('SELECT request_hash,receipt_json FROM dispatch_budget_change WHERE request_id=?',(request_id,)).fetchone()
        row=c.execute('SELECT revision,revoked,carried_launches,consumption_known FROM dispatch_budget WHERE project_id=?',(project_id,)).fetchone()
        if row is None:raise StateConflict('Unknown dispatch budget')
        if old:
            if old[0]!=fingerprint:raise StateConflict('Budget amendment identity differs')
            return {'decision':'REPLAY','historical_receipt':json.loads(old[1]),'current_revision':row[0],
                    'currently_revoked':bool(row[1]),'consumption_known':bool(row[3]),'authority_restored':False}
        store.require_execution_ready()
        epoch=c.execute('SELECT epoch FROM recovery_state').fetchone()[0]
        if epoch!=expected_epoch or row[0]!=expected_revision:raise StateConflict('Budget review epoch or revision is stale')
        basis=budget_basis(store,project_id=project_id)
        if basis['basis_hash']!=expected_basis_hash:raise StateConflict('Budget usage changed since review')
        if bool(row[1])!=reauthorize:raise StateConflict('Reauthorization must explicitly match current withdrawal')
        if reauthorize and c.execute("SELECT 1 FROM host_dispatch WHERE project_id=? AND launch_committed=1 AND coalesce(quiesced,0)=0 LIMIT 1",(project_id,)).fetchone():
            raise StateConflict('Quiesce previous Hosts before reauthorization')
        retained=c.execute('SELECT coalesce(sum(launch_committed),0) FROM host_dispatch WHERE project_id=?',(project_id,)).fetchone()[0]
        minimum=retained+row[2]
        if not row[3] and usage_reconciliation is None:raise StateConflict('Recovered dispatch consumption is unknown')
        total=minimum if usage_reconciliation is None else usage_reconciliation['total_launch_intents']
        if total<minimum:raise StateConflict('Cumulative launch usage cannot decrease')
        accepted_calls=basis['dispatch_calls']
        if usage_reconciliation is not None:
            accepted_calls=usage_reconciliation['dispatch_calls']
            if not isinstance(accepted_calls,list):raise ValueError('Reconciled dispatch calls must be a list')
            declared={}
            for item in accepted_calls:
                if (not isinstance(item,dict) or set(item)!={'dispatch_id','queries','cancels'} or
                        not isinstance(item['dispatch_id'],str) or item['dispatch_id'] in declared or
                        any(type(item[k]) is not int or item[k]<0 for k in ('queries','cancels'))):raise ValueError('Invalid cumulative dispatch call count')
                declared[item['dispatch_id']]=item
            if set(declared)!={v['dispatch_id'] for v in basis['dispatch_calls']}:raise StateConflict('Usage review must cover every retained dispatch')
            for previous in basis['dispatch_calls']:
                if any(declared[previous['dispatch_id']][k]<previous[k] for k in ('queries','cancels')):raise StateConflict('Dispatch call usage cannot decrease')
        active=c.execute("SELECT count(*) FROM host_dispatch WHERE project_id=? AND launch_committed=1 AND coalesce(quiesced,0)=0",(project_id,)).fetchone()[0]
        if max_launch_intents<total or max_delegated_agents<active or any(v['queries']>max_queries or v['cancels']>max_cancels for v in accepted_calls):
            raise StateConflict('Budget cannot be lowered below recorded consumption or occupancy')
        revision=expected_revision+1
        authority_ref=encode(authority_ref,project_id,'dispatch-budget',project_id,0,'authority_ref')
        for item in accepted_calls:
            counts=dict(c.execute('SELECT method,count(*) FROM host_invocation WHERE dispatch_id=? GROUP BY method',(item['dispatch_id'],)).fetchall())
            c.execute('UPDATE host_dispatch SET carried_queries=?,carried_cancels=? WHERE dispatch_id=?',
                (item['queries']-counts.get('QUERY',0),item['cancels']-counts.get('CANCEL',0),item['dispatch_id']))
        c.execute('''UPDATE dispatch_budget SET max_launch_intents=?,max_delegated_agents=?,max_queries=?,max_cancels=?,
            expires_at=?,authority_ref=?,revision=?,carried_launches=?,consumption_known=1,consumption_basis=?,
            revoked=0,revocation_ref=NULL WHERE project_id=?''',
            (max_launch_intents,max_delegated_agents,max_queries,max_cancels,expires_at,authority_ref,revision,total-retained,
             'CONTROLLER_ATTESTED' if usage_reconciliation is not None else basis['consumption_basis'],project_id))
        receipt={'decision':'AMENDED','project_id':project_id,'revision':revision,'epoch':epoch,
                 'retained_launch_intents':retained,'carried_launch_intents':total-retained,'total_launch_intents':total,
                 'reauthorized':reauthorize,'old_effect_grants_reactivated':False,'host_facts_independently_verified':False,
                 'usage_basis':'CONTROLLER_ATTESTED' if usage_reconciliation is not None else 'RETAINED_LEDGER'}
        c.execute('INSERT INTO dispatch_budget_change VALUES (?,?,?,?)',(request_id,project_id,fingerprint,_json(receipt)))
        details={'request_id':request_id,'revision':revision,'authority_ref':authority_ref,
                 'usage_reconciliation':None if usage_reconciliation is None else encode(usage_reconciliation,project_id,'dispatch-budget-amendment',request_id,revision,'usage_reconciliation'),'receipt':receipt}
        c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
            ('DISPATCH_BUDGET_AMENDED',project_id,_json(details)))
        return receipt


class HostExecutions:
    """Adapter protocol: host_id, profile_revision, validate_request, start/query/cancel.

    start receives backend_key, actor and request. query/cancel receive backend_key.
    Every observation is a closed object documented by _validate_observation.
    Calls happen outside SQLite transactions. No automatic retries or daemon.
    """
    def __init__(self,store,adapter,*,clock=None,tool_root=None):
        self.store,self.adapter=store,adapter
        profile_root=getattr(getattr(adapter,'command_factory',None),'tool_root',None)
        if tool_root is not None and profile_root is not None and Path(tool_root).resolve()!=Path(profile_root).resolve():
            raise ValueError('Controller runtime binding differs from trusted Host profile')
        self.tool_root=tool_root if tool_root is not None else profile_root
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        _text(adapter.host_id,'host_id');_text(adapter.profile_revision,'profile_revision');_text(adapter.quiescence_scope,'quiescence_scope')

    @contextmanager
    def _new_work_transaction(self):
        from v2_runtime_admission import runtime_admission
        with runtime_admission(self.tool_root) if self.tool_root is not None else nullcontext():
            with self.store.transaction() as connection:
                yield connection

    def _audit(self,c,kind,identity,value):
        c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',(kind,identity,_json(value)))

    def _row(self,dispatch_id):
        cursor=self.store.connection.execute('SELECT * FROM host_dispatch WHERE dispatch_id=?',(dispatch_id,))
        row=cursor.fetchone()
        if row is None:raise StateConflict('Unknown dispatch')
        result=dict(zip((v[0] for v in cursor.description),row))
        if result['host_id']!=self.adapter.host_id:raise PermissionError('Host adapter identity differs')
        return result

    def _policy(self,project_id):
        c=self.store.connection
        row=c.execute('SELECT max_launch_intents,max_delegated_agents,host_limits_json,max_queries,max_cancels,expires_at,revoked,revision,carried_launches,consumption_known,consumption_basis FROM dispatch_budget WHERE project_id=?',(project_id,)).fetchone()
        if row is None:raise PermissionError('No approved Project dispatch budget')
        host=next((v for v in json.loads(row[2]) if v['host_id']==self.adapter.host_id),None)
        if host is None:raise PermissionError('Host is outside approved budget scope')
        return row,host

    def _ready(self,task_id,revision,recovery_run_id=None):
        self.store.require_execution_ready()
        task=self.store.task_identity(task_id)
        if task is None or task['revision']!=revision or task['status'] not in ({'PAUSED'} if recovery_run_id is not None else {'READY','RUNNING'}):raise StateConflict('Task is not dispatch-ready')
        from v2_artifacts import Artifacts
        artifacts=Artifacts(self.store)
        if artifacts.recovery_handoff(task_id=task_id,task_revision=revision)['decision']!='NONE':
            raise StateConflict('Pending required recovery handoff blocks dispatch')
        if recovery_run_id is not None:
            artifacts.dispatch_recovery_source(run_id=recovery_run_id,task_id=task_id,task_revision=revision)
        require_task_phase(self.store,task_id)
        if self.store.unresolved_dependencies(task_id,revision):raise StateConflict('Dependencies are not accepted')
        c=self.store.connection
        if c.execute("SELECT 1 FROM operation WHERE task_id=? AND state IN ('INTENT_RECORDED','UNKNOWN') LIMIT 1",(task_id,)).fetchone():raise StateConflict('Task effects need reconciliation')
        if c.execute("SELECT 1 FROM host_dispatch WHERE task_id=? AND launch_committed=1 AND coalesce(quiesced,0)=0 LIMIT 1",(task_id,)).fetchone():raise StateConflict('Previous Host execution is not quiesced')
        runs=c.execute("SELECT run_id FROM execution_run WHERE task_id=? AND state<>'CLOSED'",(task_id,)).fetchall()
        for (run_id,) in runs:
            if run_id==recovery_run_id:continue
            if not c.execute('SELECT 1 FROM host_dispatch WHERE run_id=? AND quiesced=1',(run_id,)).fetchone():raise StateConflict('Existing Run has no qualified Host handoff')
        return task

    def prepare(self,*,dispatch_id,attempt_id,task_id,task_revision,strategy_ref,request,authority_ref,recovery_run_id=None):
        if recovery_run_id is not None:_text(recovery_run_id,'recovery_run_id')
        for name,value in (('dispatch_id',dispatch_id),('attempt_id',attempt_id),('strategy_ref',strategy_ref),('authority_ref',authority_ref)):
            _text(value,name)
            if len(value)>128:raise ValueError('Dispatch identifier/reference too long')
        if not isinstance(request,dict):raise ValueError('Host request must be structured')
        self.adapter.validate_request(request)
        with self._new_work_transaction() as c:
            task=self.store.task_identity(task_id)
            if task is None:raise StateConflict('Unknown Task')
            owner=task['project_id'];policy,_=self._policy(owner)
            if policy[6]:raise PermissionError('Dispatch scope revoked')
            fingerprint=request_fingerprint(c,owner,[dispatch_id,attempt_id,task_id,task_revision,strategy_ref,
                self.adapter.host_id,self.adapter.profile_revision,self.adapter.quiescence_scope,request,authority_ref]+([recovery_run_id] if recovery_run_id is not None else []))
            old=c.execute('SELECT request_hash,actor,run_id FROM host_dispatch WHERE dispatch_id=?',(dispatch_id,)).fetchone()
            if old:
                if old[0]!=fingerprint:raise StateConflict('Dispatch identity is immutable')
                return {'decision':'REPLAY','actor':old[1],'run_id':old[2],'host_called':False}
            task=self._ready(task_id,task_revision,recovery_run_id)
            strategy_hash=request_fingerprint(c,owner,[task_id,task_revision,strategy_ref])
            previous=c.execute('SELECT task_id,task_revision,strategy_hash FROM execution_attempt WHERE attempt_id=?',(attempt_id,)).fetchone()
            if previous and previous!=(task_id,task_revision,strategy_hash):raise StateConflict('Attempt identity is immutable')
            if previous is None:
                c.execute('INSERT INTO execution_attempt VALUES (?,?,?,?,?)',(attempt_id,task_id,task_revision,strategy_hash,
                    encode(strategy_ref,owner,'host-attempt',attempt_id,task_revision,'strategy')))
            key=uuid.uuid4().hex;actor='host-worker-'+key;run_id='host-run-'+key
            epoch=c.execute('SELECT epoch FROM recovery_state').fetchone()[0]
            context_hash=request_fingerprint(c,owner,task_authority_context(self.store,task_id))
            c.execute('''INSERT INTO host_dispatch(dispatch_id,backend_key,attempt_id,task_id,task_revision,project_id,
                host_id,profile_revision,quiescence_scope,actor,epoch,authority_ref,policy_revision,context_hash,request_hash,request_value,run_id,state)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'PREPARED')''',
                (dispatch_id,key,attempt_id,task_id,task_revision,owner,self.adapter.host_id,self.adapter.profile_revision,
                 self.adapter.quiescence_scope,actor,epoch,encode(authority_ref,owner,'host-dispatch',dispatch_id,task_revision,'authority_ref'),policy[7],context_hash,fingerprint,encode(request,owner,'host-dispatch',dispatch_id,task_revision,'request'),run_id))
            self._audit(c,'HOST_DISPATCH_PREPARED',dispatch_id,{'attempt_id':attempt_id,'task_id':task_id,'task_revision':task_revision})
            if recovery_run_id is not None:
                protected=encode(recovery_run_id,owner,'host-recovery-source',dispatch_id,task_revision,'run')
                from v2_artifacts import Artifacts
                source_hash=Artifacts(self.store).dispatch_recovery_fingerprint(run_id=recovery_run_id,task_id=task_id,task_revision=task_revision)
                self._audit(c,'HOST_DISPATCH_RECOVERY_SOURCE',dispatch_id,{'protected_source':protected,'checkpoint_source_hash':source_hash})
            return {'decision':'PREPARED','actor':actor,'run_id':run_id,'host_called':False}

    def _begin_call(self,c,row,invocation_id,method):
        _text(invocation_id,'invocation_id')
        if len(invocation_id)>128:raise ValueError('Invocation identifier too long')
        prior=c.execute('SELECT dispatch_id,method FROM host_invocation WHERE invocation_id=?',(invocation_id,)).fetchone()
        if prior:
            if prior!=(row['dispatch_id'],method):raise StateConflict('Invocation identity differs')
            return False
        policy,_=self._policy(row['project_id'])
        if method in {'QUERY','CANCEL'}:
            epoch=c.execute('SELECT epoch FROM recovery_state').fetchone()[0]
            if not policy[9]:
                allowance=c.execute('SELECT query_limit,cancel_limit FROM dispatch_recovery_calls WHERE project_id=? AND epoch=?',(row['project_id'],epoch)).fetchone()
                if allowance is None:raise PermissionError('Explicit recovery-call allowance is required; old consumption is unknown')
                limit=allowance[0 if method=='QUERY' else 1]
                used=c.execute('''SELECT count(*) FROM host_invocation i JOIN host_dispatch d ON d.dispatch_id=i.dispatch_id
                    WHERE d.project_id=? AND i.epoch=? AND i.method=?''',(row['project_id'],epoch,method)).fetchone()[0]
            else:
                limit=policy[3 if method=='QUERY' else 4]
                used=row['carried_queries' if method=='QUERY' else 'carried_cancels']+c.execute('SELECT count(*) FROM host_invocation WHERE dispatch_id=? AND method=?',(row['dispatch_id'],method)).fetchone()[0]
            if used>=limit:raise StateConflict('Host query/cancellation call budget exhausted')
        epoch=c.execute('SELECT epoch FROM recovery_state').fetchone()[0]
        c.execute("INSERT INTO host_invocation(invocation_id,dispatch_id,epoch,method,state) VALUES (?,?,?,?,'INTENT_COMMITTED')",(invocation_id,row['dispatch_id'],epoch,method))
        return True

    def launch(self,*,dispatch_id,invocation_id):
        with self._new_work_transaction() as c:
            row=self._row(dispatch_id)
            if row['state']!='PREPARED':return {'decision':'RECONCILE_ONLY','host_called':False}
            source=c.execute("SELECT details_json FROM execution_audit WHERE kind='HOST_DISPATCH_RECOVERY_SOURCE' AND subject_id=?",(dispatch_id,)).fetchone()
            recovery_run_id=None if source is None else decode(json.loads(source[0])['protected_source'],row['project_id'],'host-recovery-source',dispatch_id,row['task_revision'],'run')
            self._ready(row['task_id'],row['task_revision'],recovery_run_id)
            if recovery_run_id is not None:
                from v2_artifacts import Artifacts
                source_hash=json.loads(source[0]).get('checkpoint_source_hash')
                if source_hash is not None:
                    if source_hash!=Artifacts(self.store).dispatch_recovery_fingerprint(run_id=recovery_run_id,task_id=row['task_id'],task_revision=row['task_revision']):
                        raise StateConflict('Prepared recovery checkpoint changed')
                elif c.execute('SELECT 1 FROM host_dispatch WHERE run_id=?',(recovery_run_id,)).fetchone():
                    raise StateConflict('Paused Host continuation requires an explicitly prepared checkpoint binding')
            current_epoch=c.execute('SELECT epoch FROM recovery_state').fetchone()[0]
            if row['epoch']!=current_epoch or row['profile_revision']!=self.adapter.profile_revision or row['quiescence_scope']!=self.adapter.quiescence_scope:raise StateConflict('Dispatch Host/epoch changed')
            if row['context_hash']!=request_fingerprint(c,row['project_id'],task_authority_context(self.store,row['task_id'])):raise StateConflict('Dispatch Task context changed')
            policy,host=self._policy(row['project_id'])
            if policy[6]:raise PermissionError('Dispatch scope revoked')
            if not policy[9]:raise StateConflict('Dispatch consumption must be reconciled before launch')
            if policy[7]!=row['policy_revision']:raise StateConflict('Prepared dispatch budget revision is stale')
            if policy[5] is not None and Operations._instant(policy[5])<=self.clock():raise PermissionError('Dispatch scope expired')
            total=c.execute('SELECT coalesce(sum(launch_committed),0) FROM host_dispatch WHERE project_id=?',(row['project_id'],)).fetchone()[0]
            total+=policy[8]
            active=c.execute('''SELECT host_id FROM host_dispatch WHERE project_id=? AND launch_committed=1
                AND coalesce(quiesced,0)=0''',(row['project_id'],)).fetchall()
            if total>=policy[0] or len(active)>=policy[1] or sum(v[0]==row['host_id'] for v in active)+host['controller_occupancy']>=host['max_total_occupancy']:
                raise StateConflict('Cumulative dispatch or managed occupancy budget exhausted')
            request=decode(row['request_value'],row['project_id'],'host-dispatch',dispatch_id,row['task_revision'],'request')
            attempt=c.execute('SELECT task_id,task_revision,strategy_hash,strategy_value FROM execution_attempt WHERE attempt_id=?',(row['attempt_id'],)).fetchone()
            if attempt is None or attempt[:2]!=(row['task_id'],row['task_revision']):raise StateConflict('Attempt binding changed')
            strategy=decode(attempt[3],row['project_id'],'host-attempt',row['attempt_id'],row['task_revision'],'strategy')
            if attempt[2]!=request_fingerprint(c,row['project_id'],[row['task_id'],row['task_revision'],strategy]):raise StateConflict('Attempt strategy fingerprint changed')
            actual=request_fingerprint(c,row['project_id'],[dispatch_id,row['attempt_id'],row['task_id'],row['task_revision'],strategy,
                row['host_id'],row['profile_revision'],row['quiescence_scope'],request,decode(row['authority_ref'],row['project_id'],'host-dispatch',dispatch_id,row['task_revision'],'authority_ref')]+([recovery_run_id] if recovery_run_id is not None else []))
            if actual!=row['request_hash']:raise StateConflict('Prepared Host request fingerprint changed')
            self.adapter.validate_request(request)
            if not self._begin_call(c,row,invocation_id,'LAUNCH'):return {'decision':'HISTORICAL_INVOCATION','host_called':False}
            c.execute("UPDATE execution_run SET state='CLOSED' WHERE task_id=? AND state<>'CLOSED'",(row['task_id'],))
            c.execute("INSERT INTO execution_run VALUES (?,?,?,?,?,?,'OPEN',NULL)",
                (row['run_id'],row['task_id'],row['task_revision'],row['host_id'],'dispatch:'+row['backend_key'],row['actor']))
            if recovery_run_id is not None:
                from v2_artifacts import Artifacts
                Artifacts(self.store).transfer_recovery_to_host(source_run_id=recovery_run_id,target_run_id=row['run_id'])
            c.execute("UPDATE task SET status='RUNNING' WHERE task_id=?",(row['task_id'],))
            c.execute("UPDATE host_dispatch SET state='INTENT_COMMITTED',launch_committed=1 WHERE dispatch_id=?",(dispatch_id,))
            self._audit(c,'HOST_LAUNCH_INTENT',dispatch_id,{'invocation_id':invocation_id})
        return self._call(row,invocation_id,lambda:self.adapter.start(backend_key=row['backend_key'],actor=row['actor'],request=request))

    def poll(self,*,dispatch_id,invocation_id):
        with self.store.transaction() as c:
            row=self._row(dispatch_id)
            if not row['launch_committed']:raise StateConflict('No launch intent to query')
            if not self._begin_call(c,row,invocation_id,'QUERY'):return {'decision':'HISTORICAL_INVOCATION','host_called':False}
        return self._call(row,invocation_id,lambda:self.adapter.query(backend_key=row['backend_key']))

    def cancel(self,*,dispatch_id,invocation_id):
        with self.store.transaction() as c:
            row=self._row(dispatch_id)
            if not row['launch_committed']:
                c.execute('UPDATE execution_grant SET revoked=1 WHERE task_id=? AND actor=?',(row['task_id'],row['actor']))
                c.execute("UPDATE host_dispatch SET state='CANCELLED',cancel_requested=1,quiesced=1 WHERE dispatch_id=?",(dispatch_id,))
                return {'decision':'CANCELLED_BEFORE_LAUNCH','host_called':False}
            if row['quiesced']==1:return {'decision':'ALREADY_QUIESCED','host_called':False}
            if not self._begin_call(c,row,invocation_id,'CANCEL'):return {'decision':'HISTORICAL_INVOCATION','host_called':False}
            c.execute("UPDATE host_dispatch SET state='CANCEL_REQUESTED',cancel_requested=1 WHERE dispatch_id=?",(dispatch_id,))
            c.execute('UPDATE execution_grant SET revoked=1 WHERE task_id=? AND actor=?',(row['task_id'],row['actor']))
            self._audit(c,'HOST_CANCEL_REQUESTED',dispatch_id,{'invocation_id':invocation_id,'goal_cancelled':False})
        return self._call(row,invocation_id,lambda:self.adapter.cancel(backend_key=row['backend_key']))

    def _validate_observation(self,row,value):
        # physical_requests is this one Host-call's observed delta, never a
        # cumulative session total. None remains unknown in aggregate metrics.
        fields={'backend_key','native_id','state','quiesced','cancel_acknowledged','return_status','effective_identity','physical_requests'}
        if not isinstance(value,dict) or set(value)!=fields or value['backend_key']!=row['backend_key']:raise ValueError('Host observation shape or dispatch binding differs')
        if value['state'] not in {'RUNNING','EXITED','UNKNOWN'}:raise ValueError('Invalid Host state')
        for field in ('quiesced','cancel_acknowledged'):
            if value[field] is not None and type(value[field]) is not bool:raise ValueError('Host knowledge must be explicit')
        if value['quiesced'] is True and value['state']!='EXITED':raise ValueError('Only an exited Host execution can be quiesced')
        if value['return_status'] not in {None,'SUCCEEDED','FAILED','CANCELLED','UNKNOWN','NOT_STARTED'}:raise ValueError('Invalid Host return status')
        if value['state']=='RUNNING' and value['return_status'] is not None:raise ValueError('Running Host cannot report a return')
        if value['native_id'] is not None:_text(value['native_id'],'native_id')
        elif value['state']!='UNKNOWN' and value['return_status']!='NOT_STARTED':raise ValueError('Host identity is missing')
        if value['physical_requests'] is not None and (type(value['physical_requests']) is not int or value['physical_requests']<0):raise ValueError('Physical request count must be observed or unknown')
        if value['effective_identity'] is not None and not isinstance(value['effective_identity'],dict):raise ValueError('Invalid effective identity observation')
        _json(value)

    def _call(self,row,invocation_id,callback):
        value=None;validated=False
        try:
            value=callback()  # no database transaction spans Host work/waiting
            self._validate_observation(row,value)
            validated=True
            return self._observe(row['dispatch_id'],invocation_id,value)
        except Exception:
            with self.store.transaction() as c:
                current=self._row(row['dispatch_id'])
                c.execute("UPDATE host_invocation SET state='UNKNOWN' WHERE invocation_id=? AND state='INTENT_COMMITTED'",(invocation_id,))
                if validated:
                    try:
                        protected=encode(value,row['project_id'],'host-dispatch',row['dispatch_id'],row['task_revision'],'receipt')
                        digest=request_fingerprint(c,row['project_id'],value)
                    except ProtectedInputError:
                        protected=digest=None  # preserve uncertainty even when private capture is unavailable
                    c.execute("UPDATE host_invocation SET state='UNKNOWN',response_hash=?,response_value=?,physical_requests=? WHERE invocation_id=?",
                        (digest,protected,value['physical_requests'],invocation_id))
                if current['quiesced']!=1:
                    c.execute("UPDATE host_dispatch SET state='UNKNOWN' WHERE dispatch_id=?",(row['dispatch_id'],))
                    if self.store.task_identity(row['task_id'])['revision']==row['task_revision']:
                        reconcile_effect_state(c,row['task_id'],fact_ref='host-call:'+invocation_id)
                self._audit(c,'HOST_CALL_UNCERTAIN',row['dispatch_id'],{'invocation_id':invocation_id})
            raise HostCallUncertain('Host call outcome is uncertain; query the original dispatch') from None

    def _observe(self,dispatch_id,invocation_id,value):
        with self.store.transaction() as c:
            row=self._row(dispatch_id);owner=row['project_id'];revision=row['task_revision']
            digest=request_fingerprint(c,owner,value)
            protected=encode(value,owner,'host-dispatch',dispatch_id,revision,'receipt')
            c.execute("UPDATE host_invocation SET state='OBSERVED',response_hash=?,response_value=?,physical_requests=? WHERE invocation_id=?",
                (digest,protected,value['physical_requests'],invocation_id))
            if row['native_value'] is not None and value['native_id'] is not None:
                native=decode(row['native_value'],owner,'host-dispatch',dispatch_id,revision,'native-id')
                if native!=value['native_id']:raise StateConflict('Host returned a different native execution for the same dispatch')
            native_value=row['native_value']
            if native_value is None and value['native_id'] is not None:
                native_value=encode(value['native_id'],owner,'host-dispatch',dispatch_id,revision,'native-id')
            state=value['state']
            if state=='EXITED' and value['quiesced'] is not True:state='UNKNOWN'
            if state=='RUNNING' and row['cancel_requested']:state='CANCEL_REQUESTED'
            if row['quiesced']==1 and value['quiesced'] is not True:raise StateConflict('Terminal Host observation regressed')
            c.execute('UPDATE host_dispatch SET state=?,quiesced=?,native_value=?,last_receipt_value=? WHERE dispatch_id=?',
                (state,value['quiesced'],native_value,protected,dispatch_id))
            current=self.store.task_identity(row['task_id'])
            epoch=c.execute('SELECT epoch FROM recovery_state').fetchone()[0]
            historical=row['epoch']!=epoch or current['revision']!=revision
            if value['quiesced'] is True:
                c.execute('UPDATE execution_grant SET revoked=1 WHERE task_id=? AND actor=?',(row['task_id'],row['actor']))
                c.execute("UPDATE operation SET state='UNKNOWN' WHERE state='INTENT_RECORDED' AND grant_id IN (SELECT grant_id FROM execution_grant WHERE task_id=? AND actor=?)",
                    (row['task_id'],row['actor']))
                c.execute("""UPDATE operation_lease SET state='QUARANTINED' WHERE state='HELD' AND operation_id IN
                    (SELECT o.operation_id FROM operation o JOIN execution_grant g ON g.grant_id=o.grant_id
                     WHERE o.state='UNKNOWN' AND o.task_id=? AND g.actor=?)""",(row['task_id'],row['actor']))
                c.execute("UPDATE execution_run SET state='CLOSED' WHERE run_id=? AND state='OPEN'",(row['run_id'],))
            if current['revision']==revision:
                reconcile_effect_state(c,row['task_id'],fact_ref='host-receipt:'+invocation_id)
                # A repeated terminal observation settles only this old dispatch.
                # It must not reset a successor Host or a controller-owned Run.
                if value['quiesced'] is True and row['quiesced']!=1 and not historical:
                    c.execute("UPDATE task SET status='READY' WHERE task_id=? AND revision=? AND status='RUNNING'",(row['task_id'],revision))
            self._audit(c,'HOST_OBSERVATION_RECORDED',dispatch_id,{'invocation_id':invocation_id,'state':state,
                'quiesced':value['quiesced'],'historical_epoch_or_revision':historical,'task_accepted':False})
            return {'decision':'OBSERVED','state':state,'quiesced':value['quiesced'],'historical_epoch_or_revision':historical,
                    'task_accepted':False,'host_called':True,'quiescence_scope':row['quiescence_scope']}

    def status(self,*,project_id):
        c=self.store.connection
        if not c.in_transaction:
            c.execute('BEGIN')
            try:return self.status(project_id=project_id)
            finally:c.execute('ROLLBACK')
        policy,_=self._policy(project_id)
        active=c.execute('SELECT host_id,count(*) FROM host_dispatch WHERE project_id=? AND launch_committed=1 AND coalesce(quiesced,0)=0 GROUP BY host_id',(project_id,)).fetchall()
        counts=dict(active)
        invocation=c.execute('''SELECT count(*),count(physical_requests),coalesce(sum(physical_requests),0)
            FROM host_invocation i JOIN host_dispatch d ON d.dispatch_id=i.dispatch_id WHERE d.project_id=?''',(project_id,)).fetchone()
        return {'attempts':c.execute('SELECT count(*) FROM execution_attempt a JOIN task t ON t.task_id=a.task_id WHERE t.project_id=?',(project_id,)).fetchone()[0],
                'launch_intents':c.execute('SELECT coalesce(sum(launch_committed),0) FROM host_dispatch WHERE project_id=?',(project_id,)).fetchone()[0],
                'active_delegated':sum(counts.values()),'invocation_intents':invocation[0],
                'physical_requests':invocation[2] if invocation[0]==invocation[1] else None,
                'occupancy_scope':'PROJECT_MANAGED_ADAPTERS','unmanaged_host_occupancy':None,'dispatch_scope_revoked':bool(policy[6]),
                'budget_revision':policy[7],'carried_launch_intents':policy[8],'consumption_known':bool(policy[9]),
                'consumption_basis':policy[10],'usage_independently_verified':False,
                'launch_consumption_lower_bound':policy[8]+c.execute('SELECT coalesce(sum(launch_committed),0) FROM host_dispatch WHERE project_id=?',(project_id,)).fetchone()[0],
                'controller_occupancy_basis':'CONFIGURED_RESERVATION','counts':'REGISTERED_ATTEMPTS_AND_ADMITTED_HOST_CALL_INTENTS',
                'host_occupancy':[{'host_id':item['host_id'],'managed_children':counts.get(item['host_id'],0),
                    'controller_occupancy':item['controller_occupancy'],'managed_total':counts.get(item['host_id'],0)+item['controller_occupancy']}
                    for item in json.loads(policy[2])], 'execution_authorized':False}
