"""Candidate operation lifecycle; callers supply authorized, host-verified grants.

This module records authority provenance. A source_ref string alone does not
authenticate a user or grant permission in the host. No external tools run here.
"""
import hashlib
import json
from contextlib import nullcontext
from datetime import datetime, timezone, timedelta
from v2_state_store import StateStore, StateConflict, _json, _text
from resource_locators import legacy_lease_conflict, normalize_locator, locator_conflict
from v2_definition_content import encode, decode, request_fingerprint

MAX_INLINE_PARAMETERS_BYTES = 16 * 1024 * 1024


class GrantAccessDenied(PermissionError):
    """Fixed rejection category; never disclose Grant or principal values."""
    def __init__(self,reason_code):
        if reason_code not in {'GRANT_NOT_APPLICABLE','GRANT_SCOPE_MISMATCH'}:
            raise ValueError('Unknown Grant rejection category')
        self.reason_code=reason_code
        super().__init__('Execution Grant does not authorize the requested operation')


class OperationParameterLimit(ValueError):
    def __init__(self, observed_bytes):
        super().__init__('Inline operation parameters exceed the admission byte limit')
        self.observed_bytes=observed_bytes
        self.limit_bytes=MAX_INLINE_PARAMETERS_BYTES


class Operations:
    def __init__(self, store: StateStore, *, clock=None):
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._joined_connection = None

    @classmethod
    def in_transaction(cls, store):
        if not store.connection.in_transaction: raise RuntimeError('An owning transaction is required')
        result=cls(store)
        result._joined_connection=store.connection
        return result

    @staticmethod
    def _instant(value):
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('Grant expiry requires a timezone')
        return parsed

    def _transaction(self):
        if self._joined_connection is not None:
            if self.store.connection is not self._joined_connection or not self._joined_connection.in_transaction:
                raise RuntimeError('Owning transaction has ended')
            return nullcontext(self._joined_connection)
        return self.store.transaction()

    def _physical_resource(self,c,task_id,resource,effect):
        if '://' in resource:
            return None
        root=c.execute('SELECT p.resource_root FROM project p JOIN task t ON t.project_id=p.project_id WHERE t.task_id=?',(task_id,)).fetchone()[0]
        locator=normalize_locator(root,{'schema_version':1,'locator_id':'resource','kind':'PATH','scope':'WORKSPACE',
                                       'access':'READ' if effect=='read' else 'WRITE','value':resource,'aliases':[]})
        if locator['physical_identity_status']=='UNKNOWN':
            raise StateConflict('Resource physical identity is unknown')
        return locator

    @staticmethod
    def _audit(c, kind, subject, details):
        return c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)', (kind, subject, _json(details))).lastrowid

    def record_grant(self, *, grant_id, task_id, task_revision, actor, source_ref, resource, effect, expires_at=None, max_operations=None, expected_authority_sha256=None, authority_review_sha256=None):
        if type(task_revision) is not int or task_revision < 1:
            raise ValueError('Invalid task revision')
        for key, value in locals().copy().items():
            if key not in {'self', 'task_revision', 'expires_at', 'max_operations', 'expected_authority_sha256', 'authority_review_sha256'}:
                _text(value, key)
        if max_operations is not None and (type(max_operations) is not int or max_operations < 0):
            raise ValueError('max_operations must be a nonnegative integer or null')
        if expires_at is not None:
            _text(expires_at, 'expires_at')
            if self._instant(expires_at) <= self.clock():
                raise StateConflict('Cannot record an already expired execution grant')
        if effect not in {'read', 'write', 'external'}:
            raise ValueError('Unsupported effect class')
        values = (grant_id, task_id, task_revision, actor, source_ref, resource, effect)
        with self._transaction() as c:
            if authority_review_sha256 is not None:
                _text(authority_review_sha256,'authority_review_sha256')
                if c.execute("SELECT 1 FROM execution_audit WHERE kind='AUTHORITY_REVOKED' AND subject_id=?",(authority_review_sha256,)).fetchone():
                    raise StateConflict('Reviewed authority has been withdrawn')
            if expected_authority_sha256 is not None:
                from v2_authority import task_authority_context, authority_hash
                self.store.require_execution_ready()
                if authority_hash(task_authority_context(self.store,task_id))!=expected_authority_sha256:
                    raise StateConflict('Authority binding changed before Grant commit')
            task = self.store.task(task_id)
            if not task or task['revision'] != task_revision or resource not in task['scope']:
                raise StateConflict('Grant must bind current task revision and declared resource')
            old = c.execute('SELECT * FROM execution_grant WHERE grant_id=?', (grant_id,)).fetchone()
            from v2_definition_content import encode,decode
            owner=task['project_id']
            if old:
                recorded_source=decode(old[4],owner,'grant-source',grant_id,task_revision,'source_ref')
                if (*old[:4],recorded_source,*old[5:]) != (*values, 0, expires_at, max_operations):
                    raise StateConflict('Grant ID is immutable or revoked')
                return 'REPLAY'
            protected_source=encode(source_ref,owner,'grant-source',grant_id,task_revision,'source_ref')
            stored_values=(*values[:4],protected_source,*values[5:])
            c.execute('INSERT INTO execution_grant VALUES (?,?,?,?,?,?,?,0,?,?)', (*stored_values, expires_at, max_operations))
            self._audit(c, 'GRANT_RECORDED', grant_id, {'source_ref': protected_source})
            return 'RECORDED'

    def revoke_grant(self, grant_id, source_ref):
        _text(source_ref, 'source_ref')
        with self._transaction() as c:
            row = c.execute('SELECT revoked FROM execution_grant WHERE grant_id=?', (grant_id,)).fetchone()
            if row is None:
                raise StateConflict('Unknown grant')
            if not row[0]:
                from v2_definition_content import encode
                owner,revision=c.execute('SELECT t.project_id,g.task_revision FROM execution_grant g JOIN task t ON t.task_id=g.task_id WHERE g.grant_id=?',(grant_id,)).fetchone()
                protected_source=encode(source_ref,owner,'grant-revocation',grant_id,revision,'source_ref')
                c.execute('UPDATE execution_grant SET revoked=1 WHERE grant_id=?', (grant_id,))
                self._audit(c, 'GRANT_REVOKED', grant_id, {'source_ref': protected_source})

    def _grant(self, c, grant_id, actor, resource=None, effect=None, *, for_execution=True, allow_recovery_receipt=False, allow_verification=False):
        row = c.execute('SELECT task_id,task_revision,actor,resource,effect,revoked,expires_at,max_operations FROM execution_grant WHERE grant_id=?', (grant_id,)).fetchone()
        if row is None or row[2] != actor:
            raise GrantAccessDenied('GRANT_NOT_APPLICABLE')
        if resource is not None and (row[3] != resource or row[4] != effect):
            raise GrantAccessDenied('GRANT_SCOPE_MISMATCH')
        if for_execution:
            self.store.require_execution_ready()
            host=c.execute('''SELECT h.state,h.cancel_requested,b.revoked,b.expires_at FROM host_dispatch h
                JOIN dispatch_budget b ON b.project_id=h.project_id WHERE h.actor=?''',(actor,)).fetchone()
            if host and not allow_recovery_receipt and (host[0]!='RUNNING' or host[1] or host[2] or
                    (host[3] is not None and self._instant(host[3])<=self.clock())):
                raise StateConflict('Managed Host execution is not admitted for new effects')
            from v2_governance import require_task_phase
            require_task_phase(self.store,row[0])
            task = self.store.task(row[0])
            allowed={'READY','RUNNING','RECOVERY_REQUIRED'} if allow_recovery_receipt else {'READY','RUNNING'}
            if allow_verification:allowed.add('VERIFYING')
            if row[5] or task['revision'] != row[1] or task['status'] not in allowed:
                raise StateConflict('Revoked, stale or inactive execution authority')
            if row[6] is not None and self._instant(row[6]) <= self.clock():
                raise StateConflict('Execution grant has expired')
            if self.store.unresolved_dependencies(row[0], row[1]):
                raise StateConflict('Task dependencies lack current accepted results')
        return row

    def prepare(self, *, operation_id, grant_id, actor, resource, effect, parameters=None, capture_authority_ref=None):
        _text(operation_id, 'operation_id')
        parameters = {} if parameters is None else parameters
        if not isinstance(parameters, dict):
            raise ValueError('Operation parameters must be an object')
        request_json = _json(parameters)
        parameter_bytes=len(request_json.encode('utf-8'))
        from v2_operation_inputs import binding,protect_parameters,operation_parameters
        with self._transaction() as c:
            grant = self._grant(c, grant_id, actor, resource, effect)
            old = c.execute('SELECT request_hash,state,request_json FROM operation WHERE operation_id=?', (operation_id,)).fetchone()
            if old:
                fingerprint=hashlib.sha256(_json([grant_id,actor,resource,effect,json.loads(old[2])]).encode()).hexdigest()
                if old[0] != fingerprint or _json(operation_parameters(self.store,operation_id,actor=actor))!=request_json:
                    raise StateConflict('Operation ID reused with different request')
                return {'decision': 'REPLAY', 'state': old[1], 'request_hash': fingerprint}
            if parameter_bytes>MAX_INLINE_PARAMETERS_BYTES:
                raise OperationParameterLimit(parameter_bytes)
            if c.execute("SELECT 1 FROM operation WHERE task_id=? AND state IN ('INTENT_RECORDED','UNKNOWN') LIMIT 1", (grant[0],)).fetchone():
                raise StateConflict('Reconcile pending or unknown effects before preparing another operation')
            resolved=self._physical_resource(c,grant[0],resource,effect)
            context=binding(self.store,operation_id=operation_id,grant_id=grant_id,task_id=grant[0],task_revision=grant[1],actor=actor)
            control=protect_parameters(self.store,parameters,resource=resource,context=context,capture_authority_ref=capture_authority_ref)
            request_json=_json(control)
            fingerprint=hashlib.sha256(_json([grant_id,actor,resource,effect,control]).encode()).hexdigest()
            epoch=c.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]
            c.execute('INSERT INTO operation VALUES (?,?,?,?,?,?,?,?,?)', (operation_id, grant_id, grant[0], grant[1], fingerprint, request_json, None if resolved is None else _json(resolved), epoch, 'PREPARED'))
            self._audit(c, 'OPERATION_PREPARED', operation_id, {'request_hash': fingerprint})
            return {'decision': 'PREPARED', 'state': 'PREPARED', 'request_hash': fingerprint}

    def configure_task_budget(self, *, task_id, max_operations, authority_ref):
        _text(authority_ref,'authority_ref')
        if type(max_operations) is not int or max_operations<0:
            raise ValueError('Task operation budget must be a nonnegative integer')
        with self._transaction() as c:
            task=self.store.task(task_id)
            if task is None: raise StateConflict('Unknown budget Task')
            owner=task['project_id']
            old=c.execute('SELECT max_operations,authority_ref FROM task_budget WHERE task_id=?',(task_id,)).fetchone()
            if old:
                if (old[0],decode(old[1],owner,'task-budget',task_id,0,'authority_ref'))!=(max_operations,authority_ref): raise StateConflict('Task budget policy is immutable')
                return 'REPLAY'
            used=c.execute("SELECT count(*) FROM execution_audit a JOIN operation o ON o.operation_id=a.subject_id WHERE a.kind='INTENT_RECORDED' AND o.task_id=?",(task_id,)).fetchone()[0]
            if used>max_operations: raise StateConflict('Task has already consumed more than the proposed budget')
            authority_ref=encode(authority_ref,owner,'task-budget',task_id,0,'authority_ref')
            c.execute('INSERT INTO task_budget(task_id,max_operations,authority_ref) VALUES (?,?,?)',(task_id,max_operations,authority_ref))
            self._audit(c,'TASK_BUDGET_CONFIGURED',task_id,{'max_operations':max_operations,'authority_ref':authority_ref})
            return 'CONFIGURED'

    def budget_status(self, *, project_id, task_id=None):
        c=self.store.connection
        owns_transaction=not c.in_transaction
        if owns_transaction:c.execute('BEGIN')
        try:
            if not c.execute('SELECT 1 FROM project WHERE project_id=?',(project_id,)).fetchone(): raise StateConflict('Unknown Project')
            if task_id is not None:
                task=self.store.task(task_id)
                if task is None or task['project_id']!=project_id: raise StateConflict('Task does not belong to Project')
            maximum=c.execute('SELECT max_operations,revision FROM project_budget WHERE project_id=?',(project_id,)).fetchone()
            used=c.execute("SELECT count(*) FROM execution_audit a JOIN operation o ON o.operation_id=a.subject_id JOIN task t ON t.task_id=o.task_id WHERE a.kind='INTENT_RECORDED' AND t.project_id=?",(project_id,)).fetchone()[0]
            def summary(limit,used):
                cap=None if limit is None else limit[0]
                return {'max_operations':cap,'policy_revision':None if limit is None else limit[1],'intents_consumed':used,'remaining_operations':None if cap is None else max(0,cap-used),'limit_configured':cap is not None}
            result={'project_id':project_id,'project':summary(maximum,used),'task':None,'writes_performed':False,
                    'accounting_unit':'COMMITTED_OPERATION_INTENT','provider_costs_known':False}
            if task_id is not None:
                maximum=c.execute('SELECT max_operations,revision FROM task_budget WHERE task_id=?',(task_id,)).fetchone()
                used=c.execute("SELECT count(*) FROM execution_audit a JOIN operation o ON o.operation_id=a.subject_id WHERE a.kind='INTENT_RECORDED' AND o.task_id=?",(task_id,)).fetchone()[0]
                result['task']={'task_id':task_id,**summary(maximum,used)}
            if owns_transaction:c.execute('COMMIT')
            return result
        except BaseException:
            if owns_transaction and c.in_transaction: c.execute('ROLLBACK')
            raise

    def amend_budget(self, *, scope, owner_id, expected_revision, expected_max_operations, expected_authority_ref,
                     max_operations, authority_ref, reason, request_id):
        if scope not in {'project','task'}: raise ValueError('Budget scope must be project or task')
        for key,value in [('owner_id',owner_id),('expected_authority_ref',expected_authority_ref),
                          ('authority_ref',authority_ref),('reason',reason),('request_id',request_id)]: _text(value,key)
        if any(type(v) is not int or v<0 for v in (expected_max_operations,max_operations)):
            raise ValueError('Budget limits must be nonnegative integers')
        if type(expected_revision) is not int or expected_revision<1: raise ValueError('Budget revision must be positive')
        table,column=('project_budget','project_id') if scope=='project' else ('task_budget','task_id')
        with self._transaction() as c:
            owner=owner_id
            if scope=='task':
                task=self.store.task_identity(owner_id)
                if task is None:raise StateConflict('Unknown budget Task')
                owner=task['project_id']
            fingerprint=request_fingerprint(c,owner,[scope,owner_id,expected_revision,expected_max_operations,expected_authority_ref,max_operations,authority_ref,reason])
            prior=c.execute("SELECT details_json FROM execution_audit WHERE kind='BUDGET_AMENDED' AND subject_id=?",(request_id,)).fetchone()
            if prior:
                if json.loads(prior[0])['request_hash']!=fingerprint: raise StateConflict('Budget amendment request identity conflict')
                return {'decision':'REPLAY','usage_reset':False}
            old=c.execute(f'SELECT max_operations,authority_ref,revision FROM {table} WHERE {column}=?',(owner_id,)).fetchone()
            if old is None or (old[0],decode(old[1],owner,scope+'-budget',owner_id,0,'authority_ref'),old[2])!=(expected_max_operations,expected_authority_ref,expected_revision): raise StateConflict('Budget policy changed; review current limit and revision')
            if scope=='project':
                used=c.execute("SELECT count(*) FROM execution_audit a JOIN operation o ON o.operation_id=a.subject_id JOIN task t ON t.task_id=o.task_id WHERE a.kind='INTENT_RECORDED' AND t.project_id=?",(owner_id,)).fetchone()[0]
            else:
                used=c.execute("SELECT count(*) FROM execution_audit a JOIN operation o ON o.operation_id=a.subject_id WHERE a.kind='INTENT_RECORDED' AND o.task_id=?",(owner_id,)).fetchone()[0]
            if max_operations<used: raise StateConflict('New budget cannot erase already consumed operations')
            authority_ref=encode(authority_ref,owner,scope+'-budget',owner_id,0,'authority_ref')
            reason=encode(reason,owner,'budget-amendment',request_id,expected_revision+1,'reason')
            c.execute(f'UPDATE {table} SET max_operations=?,authority_ref=?,revision=revision+1 WHERE {column}=?',(max_operations,authority_ref,owner_id))
            self._audit(c,'BUDGET_AMENDED',request_id,{'request_hash':fingerprint,'scope':scope,'owner_id':owner_id,
                        'previous_revision':expected_revision,'revision':expected_revision+1,
                        'previous_max_operations':expected_max_operations,'previous_authority_ref':old[1],
                        'max_operations':max_operations,'authority_ref':authority_ref,'reason':reason,'intents_consumed':used})
            return {'decision':'AMENDED','max_operations':max_operations,'intents_consumed':used,
                    'remaining_operations':max_operations-used,'policy_revision':expected_revision+1,'usage_reset':False}

    def configure_project_budget(self, *, project_id, max_operations, authority_ref):
        _text(authority_ref,'authority_ref')
        if type(max_operations) is not int or max_operations<0:
            raise ValueError('Project operation budget must be a nonnegative integer')
        with self._transaction() as c:
            if not c.execute('SELECT 1 FROM project WHERE project_id=?',(project_id,)).fetchone(): raise StateConflict('Unknown budget Project')
            old=c.execute('SELECT max_operations,authority_ref FROM project_budget WHERE project_id=?',(project_id,)).fetchone()
            if old:
                if (old[0],decode(old[1],project_id,'project-budget',project_id,0,'authority_ref'))!=(max_operations,authority_ref): raise StateConflict('Project budget policy is immutable')
                return 'REPLAY'
            used=c.execute("SELECT count(*) FROM execution_audit a JOIN operation o ON o.operation_id=a.subject_id JOIN task t ON t.task_id=o.task_id WHERE a.kind='INTENT_RECORDED' AND t.project_id=?",(project_id,)).fetchone()[0]
            if used>max_operations: raise StateConflict('Project already exceeds proposed operation budget')
            authority_ref=encode(authority_ref,project_id,'project-budget',project_id,0,'authority_ref')
            c.execute('INSERT INTO project_budget(project_id,max_operations,authority_ref) VALUES (?,?,?)',(project_id,max_operations,authority_ref))
            self._audit(c,'PROJECT_BUDGET_CONFIGURED',project_id,{'max_operations':max_operations,'authority_ref':authority_ref})
            return 'CONFIGURED'

    def require_operation_budget(self, c, grant_id, grant):
        used = c.execute("SELECT count(*) FROM execution_audit a JOIN operation o ON o.operation_id=a.subject_id WHERE a.kind='INTENT_RECORDED' AND o.grant_id=?", (grant_id,)).fetchone()[0]
        if grant[7] is not None and used >= grant[7]:
            raise StateConflict('Execution grant operation budget exhausted')
        task_budget=c.execute('SELECT max_operations FROM task_budget WHERE task_id=?',(grant[0],)).fetchone()
        if task_budget:
            consumed=c.execute("SELECT count(*) FROM execution_audit a JOIN operation o ON o.operation_id=a.subject_id WHERE a.kind='INTENT_RECORDED' AND o.task_id=?",(grant[0],)).fetchone()[0]
            if consumed>=task_budget[0]: raise StateConflict('Cumulative Task operation budget exhausted')
        project_id=c.execute('SELECT project_id FROM task WHERE task_id=?',(grant[0],)).fetchone()[0]
        project_budget=c.execute('SELECT max_operations FROM project_budget WHERE project_id=?',(project_id,)).fetchone()
        if project_budget:
            consumed=c.execute("SELECT count(*) FROM execution_audit a JOIN operation o ON o.operation_id=a.subject_id JOIN task t ON t.task_id=o.task_id WHERE a.kind='INTENT_RECORDED' AND t.project_id=?",(project_id,)).fetchone()[0]
            if consumed>=project_budget[0]: raise StateConflict('Cumulative Project operation budget exhausted')

    def record_intent(self, operation_id, actor, expected_request_hash=None, lease_seconds=300):
        if type(lease_seconds) is not int or not 1<=lease_seconds<=3600:
            raise ValueError('lease_seconds must be an integer between 1 and 3600')
        with self._transaction() as c:
            row = c.execute('SELECT grant_id,task_id,state,request_hash FROM operation WHERE operation_id=?', (operation_id,)).fetchone()
            if row is None:
                raise StateConflict('Unknown operation')
            if expected_request_hash is not None and expected_request_hash != row[3]:
                raise StateConflict('Prepared request hash changed or does not match')
            grant = self._grant(c, row[0], actor, allow_recovery_receipt=row[2]=='UNKNOWN')
            if row[2] != 'PREPARED':
                return {'state': row[2], 'execute_once': False}
            from v2_growth import require_trial_ready
            require_trial_ready(self.store,operation_id)
            from v2_evidence_derivation import require_export_ready
            require_export_ready(self.store,operation_id,actor)
            self.require_operation_budget(c,row[0],grant)
            if c.execute("SELECT 1 FROM operation WHERE task_id=? AND operation_id<>? AND state IN ('INTENT_RECORDED','UNKNOWN') LIMIT 1", (row[1], operation_id)).fetchone():
                raise StateConflict('Another effect is pending or unknown')
            requested={'locator':grant[3],'access':'read' if grant[4]=='read' else 'write'}
            resolved=self._physical_resource(c,row[1],grant[3],grant[4])
            recorded=c.execute('SELECT resource_json FROM operation WHERE operation_id=?',(operation_id,)).fetchone()[0]
            recorded=None if recorded is None else json.loads(recorded)
            if resolved is not None and (recorded is None or resolved['identity_sha256']!=recorded['identity_sha256']):
                raise StateConflict('Resource identity changed after preparation')
            holders=c.execute("SELECT g.resource,g.effect,o.resource_json FROM operation o JOIN execution_grant g ON g.grant_id=o.grant_id WHERE o.operation_id<>? AND o.state IN ('INTENT_RECORDED','UNKNOWN')",(operation_id,)).fetchall()
            for resource,effect,held_json in holders:
                held=None if held_json is None else json.loads(held_json)
                conflict=locator_conflict(resolved,held) if resolved is not None and held is not None else legacy_lease_conflict(requested,{'locator':resource,'access':'read' if effect=='read' else 'write'})
                if conflict:
                    raise StateConflict('Resource is held by a pending or unknown operation')
            c.execute("UPDATE operation SET state='INTENT_RECORDED' WHERE operation_id=?", (operation_id,))
            c.execute("UPDATE task SET status='RUNNING' WHERE task_id=?", (row[1],))
            fence=self._audit(c, 'INTENT_RECORDED', operation_id, {'actor': actor})
            epoch=c.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]
            expires_at=(self.clock()+timedelta(seconds=lease_seconds)).isoformat()
            c.execute("INSERT INTO operation_lease VALUES (?,?,?,?,?,'HELD')",(operation_id,epoch,fence,actor,expires_at))
            return {'state': 'INTENT_RECORDED', 'execute_once': True, 'request_hash': row[3],
                    'lease_token':{'epoch':epoch,'fence':fence},'lease_expires_at':expires_at}

    def _lease(self,c,operation_id,actor,token):
        if not isinstance(token,dict) or set(token)!={'epoch','fence'} or type(token['fence']) is not int:
            raise ValueError('Expected an exact epoch/fence lease token')
        row=c.execute('''SELECT l.epoch,l.fence,l.actor,l.expires_at,l.state,o.grant_id,o.state,o.task_id,o.resource_json
            FROM operation_lease l JOIN operation o ON o.operation_id=l.operation_id WHERE l.operation_id=?''',(operation_id,)).fetchone()
        if row is None or row[:3]!=(token['epoch'],token['fence'],actor):
            raise StateConflict('Lease token or owner does not match')
        epoch=c.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]
        if epoch!=row[0] or row[4]!='HELD' or row[6]!='INTENT_RECORDED' or self._instant(row[3])<=self.clock():
            raise StateConflict('Lease is stale, expired, quarantined or released')
        grant=self._grant(c,row[5],actor)
        from v2_growth import require_trial_ready
        require_trial_ready(self.store,operation_id)
        from v2_evidence_derivation import require_export_ready
        require_export_ready(self.store,operation_id,actor)
        current=self._physical_resource(c,row[7],grant[3],grant[4])
        previous=None if row[8] is None else json.loads(row[8])
        if current is not None and (previous is None or current['identity_sha256']!=previous['identity_sha256']):
            raise StateConflict('Leased resource identity changed')
        return row

    def verify_lease(self, *, operation_id, actor, token):
        c=self.store.connection
        owns_transaction=not c.in_transaction
        if owns_transaction:c.execute('BEGIN')
        try:
            row=self._lease(c,operation_id,actor,token)
            if owns_transaction:c.execute('COMMIT')
            return {'decision':'VALID','expires_at':row[3],'token':dict(token)}
        except BaseException:
            if owns_transaction and c.in_transaction: c.execute('ROLLBACK')
            raise

    def renew_lease(self, *, operation_id, actor, token, lease_seconds=300):
        if type(lease_seconds) is not int or not 1<=lease_seconds<=3600:
            raise ValueError('lease_seconds must be an integer between 1 and 3600')
        with self._transaction() as c:
            row=self._lease(c,operation_id,actor,token)
            expiry=max(self._instant(row[3]),self.clock()+timedelta(seconds=lease_seconds)).isoformat()
            c.execute('UPDATE operation_lease SET expires_at=? WHERE operation_id=?',(expiry,operation_id))
            self._audit(c,'LEASE_RENEWED',operation_id,{'token':token,'expires_at':expiry})
            return {'decision':'RENEWED','token':dict(token),'expires_at':expiry}

    def cancel_prepared(self, *, operation_id, actor, reason):
        """Cancel only work that has never received execution permission."""
        _text(reason,'reason')
        with self._transaction() as c:
            row=c.execute('SELECT grant_id,state FROM operation WHERE operation_id=?',(operation_id,)).fetchone()
            if row is None:
                raise StateConflict('Unknown operation')
            self._grant(c,row[0],actor,for_execution=False)
            if row[1]=='CANCELLED':
                return {'decision':'REPLAY','state':'CANCELLED'}
            if row[1]!='PREPARED':
                raise StateConflict('An issued intent or observed effect cannot be cancelled as unexecuted')
            c.execute("UPDATE operation SET state='CANCELLED' WHERE operation_id=?",(operation_id,))
            self._audit(c,'PREPARED_OPERATION_CANCELLED',operation_id,{'reason':reason,'actor':actor})
            return {'decision':'CANCELLED','state':'CANCELLED'}

    def observe(self, *, observation_id, operation_id, actor, outcome, evidence_ref):
        _text(observation_id, 'observation_id')
        _text(evidence_ref, 'evidence_ref')
        if outcome not in {'SUCCEEDED', 'FAILED', 'UNKNOWN'}:
            raise ValueError('Unsupported observation outcome')
        from v2_observation_content import encode,read_reference,fingerprint,MAX_REFERENCE_BYTES
        if len(evidence_ref.encode('utf-8'))>MAX_REFERENCE_BYTES:raise ValueError('Observation reference exceeds byte limit')
        with self._transaction() as c:
            row = c.execute('SELECT grant_id,state FROM operation WHERE operation_id=?', (operation_id,)).fetchone()
            if row is None:
                raise StateConflict('Unknown operation')
            self._grant(c, row[0], actor, for_execution=False)
            old = c.execute('SELECT operation_id,outcome FROM operation_observation WHERE observation_id=?', (observation_id,)).fetchone()
            if old:
                if old!=(operation_id,outcome) or read_reference(self.store,observation_id,actor=actor)!=evidence_ref:
                    raise StateConflict('Observation ID reused with different facts')
                return 'REPLAY'
            if row[1] not in {'INTENT_RECORDED', 'UNKNOWN'}:
                raise StateConflict('Observation requires a pending or unknown operation')
            control=encode(self.store,observation_id,operation_id,actor,outcome,evidence_ref)
            control_hash=fingerprint(observation_id,operation_id,actor,outcome,control)
            c.execute('INSERT INTO operation_observation VALUES (?,?,?,?,?)', (observation_id, operation_id, outcome, control, control_hash))
            state = {'SUCCEEDED': 'OBSERVED', 'FAILED': 'FAILED', 'UNKNOWN': 'UNKNOWN'}[outcome]
            c.execute('UPDATE operation SET state=? WHERE operation_id=?', (state, operation_id))
            c.execute('UPDATE operation_lease SET state=? WHERE operation_id=?',
                      ('QUARANTINED' if outcome=='UNKNOWN' else 'RELEASED',operation_id))
            self._audit(c, 'OUTCOME_OBSERVED', operation_id, {'observation_id': observation_id, 'outcome': outcome})
            task_id=c.execute('SELECT task_id FROM operation WHERE operation_id=?',(operation_id,)).fetchone()[0]
            from v2_task_lifecycle import reconcile_effect_state
            reconcile_effect_state(c,task_id,fact_ref='observation:'+observation_id)
            return state
