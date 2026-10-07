"""Candidate evidence acceptance. Host adapters must authenticate verifier/authority references."""
import hashlib
import json
from v2_state_store import StateStore, StateConflict, _json, _text
from v2_evidence import BlobStore
from v2_contracts import criteria, LEVELS
from v2_evidence_policy import validate_descriptor, require_access


class Acceptance:
    def __init__(self, store: StateStore, blobs: BlobStore):
        self.store, self.blobs = store, blobs

    def record(self, *, evidence_id, task_id, task_revision, operation_id, criterion, result, verifier_ref, data, descriptor=None, method='declared-review', evidence_level='D'):
        if method=='derived-review':raise PermissionError('Use the controller derivation entry to bind source lineage')
        values,descriptor_json=self._validate_record(evidence_id=evidence_id,task_id=task_id,task_revision=task_revision,
            operation_id=operation_id,criterion=criterion,result=result,verifier_ref=verifier_ref,data=data,
            descriptor=descriptor,method=method,evidence_level=evidence_level)
        values=self._publish_content(values,descriptor_json,data)
        with self.store.transaction():
            return self._persist_evidence(values,descriptor_json)

    def _validate_record(self, *, evidence_id,task_id,task_revision,operation_id,criterion,result,
                         verifier_ref,data,descriptor,method,evidence_level):
        if self.store.readonly:
            raise PermissionError('Read-only store')
        for field, value in [('evidence_id', evidence_id), ('task_id', task_id), ('operation_id', operation_id),
                             ('criterion', criterion), ('verifier_ref', verifier_ref)]:
            _text(value, field)
        if type(task_revision) is not int or task_revision < 1 or result not in {'PASS', 'FAIL'}:
            raise ValueError('Invalid evidence revision or result')
        _text(method,'method')
        if evidence_level not in LEVELS:
            raise ValueError('Invalid evidence level')
        task = self.store.task(task_id)
        if task is None or task['revision'] != task_revision or criterion not in {r['criterion_id'] for r in criteria(task['acceptance'])}:
            raise StateConflict('Evidence must bind a current acceptance criterion')
        descriptor = validate_descriptor(descriptor, project_id=task['project_id'], task_id=task_id,
                                         task_revision=task_revision, criterion=criterion)
        descriptor_json = _json(descriptor)
        if not isinstance(data,bytes):raise TypeError('Evidence payload must be bytes')
        values = (evidence_id, task_id, task_revision, operation_id, criterion, result, None, verifier_ref, method, evidence_level)
        return values,descriptor_json

    def _publish_content(self,values,descriptor_json,data,*,lineage_record=None):
        from v2_evidence_content import encode,decode
        old=self.store.connection.execute('SELECT blob_hash FROM evidence WHERE evidence_id=?',(values[0],)).fetchone()
        if old:
            values=(*values[:6],old[0],*values[7:])
            self._check_evidence_binding(values,descriptor_json)
            if decode(self.store,values,descriptor_json,self.blobs.read(old[0]))!=data:
                raise StateConflict('Evidence identity is immutable')
            return values
        self._check_evidence_binding(values,descriptor_json)
        stored=encode(self.store,values,descriptor_json,data,lineage_record=lineage_record)
        digest=self.blobs.put(stored)
        return (*values[:6],digest,*values[7:])

    def _check_evidence_binding(self, values, descriptor_json):
        (evidence_id,task_id,task_revision,operation_id,criterion,result,digest,verifier_ref,method,evidence_level)=values
        c=self.store.connection
        old = c.execute('SELECT evidence_id,task_id,task_revision,operation_id,criterion,result,blob_hash,verifier_ref,method,evidence_level FROM evidence WHERE evidence_id=?', (evidence_id,)).fetchone()
        if old:
            old_policy = c.execute('SELECT descriptor_json FROM evidence_policy WHERE evidence_id=?',(evidence_id,)).fetchone()
            if old != values or old_policy != (descriptor_json,):
                raise StateConflict('Evidence identity is immutable')
            return 'REPLAY'
        task = self.store.task(task_id)
        epoch=c.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]
        op = c.execute('SELECT task_id,task_revision,state,execution_epoch FROM operation WHERE operation_id=?', (operation_id,)).fetchone()
        if task is None or task['revision'] != task_revision or task['status'] not in {'RUNNING','VERIFYING'} or op != (task_id, task_revision, 'OBSERVED', epoch):
            raise StateConflict('Evidence requires current running task and observed operation in the current epoch')
        return 'NEW'

    def _persist_evidence(self, values, descriptor_json):
        if not self.store.connection.in_transaction:
            raise RuntimeError("Evidence persistence requires a transaction")
        if self._check_evidence_binding(values,descriptor_json)=='REPLAY':return 'REPLAY'
        (evidence_id,task_id,task_revision,operation_id,criterion,result,digest,verifier_ref,method,evidence_level)=values
        c=self.store.connection
        c.execute('INSERT INTO evidence(evidence_id,task_id,task_revision,operation_id,criterion,result,blob_hash,verifier_ref,method,evidence_level) VALUES (?,?,?,?,?,?,?,?,?,?)', values)
        c.execute('INSERT INTO evidence_policy(evidence_id,descriptor_json) VALUES (?,?)',(evidence_id,descriptor_json))
        c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)', ('EVIDENCE_RECORDED', evidence_id, _json({'blob_hash': digest})))
        return 'RECORDED'

    def verify_managed_files(self, *, evidence_id, task_id, task_revision, operation_id, criterion, actor, descriptor):
        """Run the fixed integrity verifier; no client result, bytes or grade.

        C means an actual deterministic check, not an independent business
        review. The Task must explicitly select this narrow verification method.
        """
        from v2_local_host import verify_task_file_results
        from v2_operations import Operations
        from v2_operation_inputs import operation_parameters
        for key,value in (('evidence_id',evidence_id),('task_id',task_id),('operation_id',operation_id),('criterion',criterion),('actor',actor)):
            _text(value,key)
        if type(task_revision) is not int or task_revision<1: raise ValueError('Invalid task revision')
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            task=self.store.task(task_id)
            if task is None or task['revision']!=task_revision or task['status'] not in {'RUNNING','VERIFYING'}:
                raise StateConflict('Verifier requires the current running Task')
            definition=next((v for v in criteria(task['acceptance']) if v['criterion_id']==criterion),None)
            if (definition is None or definition['verification_method']!='managed-file-integrity' or
                    LEVELS[definition['minimum_evidence_level']]>LEVELS['C']):
                raise StateConflict('Criterion does not accept this verifier and its fixed evidence level')
            validate_descriptor(descriptor,project_id=task['project_id'],task_id=task_id,
                                task_revision=task_revision,criterion=criterion)
            require_access(descriptor,owner=task['project_id'],purpose='verification',revoked=False)
            previous=c.execute('''SELECT p.revoked,EXISTS(SELECT 1 FROM evidence_invalidation i WHERE i.evidence_id=p.evidence_id)
                                  FROM evidence_policy p WHERE p.evidence_id=?''',(evidence_id,)).fetchone()
            if previous and any(previous):
                raise StateConflict('Use a new evidence identity after withdrawal or invalidation')
            rows=c.execute("SELECT operation_id,grant_id,request_json,state,execution_epoch FROM operation WHERE task_id=? AND task_revision=?",
                           (task_id,task_revision)).fetchall()
            if any(row[3] in {'PREPARED','INTENT_RECORDED','UNKNOWN'} for row in rows):
                raise StateConflict('Resolve pending effects before verification')
            parameters={row[0]:operation_parameters(self.store,row[0]) for row in rows if row[3] in {'OBSERVED','ACCEPTED'}}
            managed=[row for row in rows if row[0] in parameters and
                     parameters[row[0]].get('tool') in {'create-file','read-file','update-file'}]
            epoch=c.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]
            current=[row for row in managed if row[4]==epoch and row[3]=='OBSERVED']
            if operation_id not in {row[0] for row in current}:
                raise StateConflict('Verifier must bind a current-epoch observed managed file operation')
            operations=Operations(self.store)
            current=[row for row in current if c.execute('SELECT actor FROM execution_grant WHERE grant_id=?',(row[1],)).fetchone()==(actor,)]
            if operation_id not in {row[0] for row in current}:raise PermissionError('Verifier anchor is not owned by this actor')
            for row in current:
                operations._grant(c,row[1],actor,allow_verification=True)
            covered={parameters[row[0]]['path'] for row in current}
            if any(parameters[row[0]]['path'] not in covered for row in managed):
                raise StateConflict('Historical file results need current-epoch resource coverage')
            checked=verify_task_file_results(self.store,task_id,task_revision)
            if not checked: raise StateConflict('No managed file results were verified')
            report={'verifier':'managed-file-integrity-v1','task_id':task_id,'task_revision':task_revision,
                    'operation_count':len(managed),
                    'operation_set_sha256':hashlib.sha256(_json(sorted(row[0] for row in managed)).encode()).hexdigest(),
                    'files_checked':checked,
                    'result':'PASS','business_correctness_verified':False}
            values=(evidence_id,task_id,task_revision,operation_id,criterion,'PASS',None,
                    'malts:managed-file-integrity-v1','managed-file-integrity','C')
            values=self._publish_content(values,_json(descriptor),_json(report).encode('utf-8'))
            result=self._persist_evidence(values,_json(descriptor))
            return {'decision':result,'verification_method':'managed-file-integrity','evidence_level':'C',
                    'files_checked':checked,'business_correctness_verified':False}

    def read(self, *, evidence_id, owner, purpose):
        """Purpose-scoped propagation. Caller identity must come from trusted Host."""
        c=self.store.connection
        c.execute('BEGIN')
        try:
            data=self._read_in_transaction(evidence_id=evidence_id,owner=owner,purpose=purpose)
            c.execute('COMMIT')
            return data
        except BaseException:
            if c.in_transaction: c.execute('ROLLBACK')
            raise

    def _read_in_transaction(self, *, evidence_id, owner, purpose, max_bytes=None):
        return self._read_metered_in_transaction(evidence_id=evidence_id,owner=owner,purpose=purpose,max_bytes=max_bytes)[0]

    def _read_metered_in_transaction(self, *, evidence_id, owner, purpose, max_bytes=None, verify_artifacts=True):
        if not self.store.connection.in_transaction:
            raise RuntimeError('Evidence read requires a consistent transaction')
        if purpose != 'recovery':
            self.store.require_execution_ready()
        row=self.store.connection.execute('''SELECT e.blob_hash,p.descriptor_json,p.revoked,
            EXISTS(SELECT 1 FROM evidence_invalidation i WHERE i.evidence_id=e.evidence_id),e.task_id,e.task_revision,e.result
            FROM evidence e JOIN evidence_policy p ON p.evidence_id=e.evidence_id
            WHERE e.evidence_id=?''',(evidence_id,)).fetchone()
        if row is None or row[3]:
            raise PermissionError('Evidence is unavailable for propagation')
        require_access(json.loads(row[1]),owner=owner,purpose=purpose,revoked=bool(row[2]))
        from v2_evidence_derivation import source_closure,read_closure
        closure=source_closure(self.store,evidence_id,owner)
        if verify_artifacts and purpose=='verification' and row[6]=='PASS':
            from v2_local_host import verify_task_file_results
            verify_task_file_results(self.store,row[4],row[5])
        stored=self.blobs.read(row[0],max_bytes=max_bytes)
        from v2_evidence_content import decode
        values=self.store.connection.execute('''SELECT evidence_id,task_id,task_revision,operation_id,criterion,result,
            blob_hash,verifier_ref,method,evidence_level FROM evidence WHERE evidence_id=?''',(evidence_id,)).fetchone()
        try:
            data=decode(self.store,values,row[1],stored)
            source_cost=read_closure(self.blobs,closure,max_bytes=None if max_bytes is None else max_bytes-len(stored))
            return data,len(stored)+source_cost
        except (ValueError,OSError) as exc:
            from v2_evidence import EvidenceReadLimit
            if isinstance(exc,EvidenceReadLimit):exc.minimum_bytes+=len(stored)
            exc.bytes_read=len(stored)+getattr(exc,'bytes_read',0)
            raise

    def revoke_access(self, *, evidence_id, owner, authority_ref):
        _text(authority_ref,'authority_ref')
        with self.store.transaction() as c:
            row=c.execute('SELECT descriptor_json,revoked,revocation_ref FROM evidence_policy WHERE evidence_id=?',(evidence_id,)).fetchone()
            if row is None or json.loads(row[0])['owner'] != owner:
                raise PermissionError('Evidence owner mismatch')
            if row[1]:
                if row[2] != authority_ref: raise StateConflict('Access revocation is immutable')
                return 'REPLAY'
            c.execute('UPDATE evidence_policy SET revoked=1,revocation_ref=? WHERE evidence_id=?',(authority_ref,evidence_id))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                      ('EVIDENCE_ACCESS_REVOKED',evidence_id,_json({'authority_ref':authority_ref})))
            return 'REVOKED'

    def accept(self, *, acceptance_id, task_id, task_revision, evidence_ids, authority_ref):
        _text(acceptance_id, 'acceptance_id')
        _text(authority_ref, 'authority_ref')
        if type(task_revision) is not int or task_revision < 1:
            raise ValueError('Invalid task revision')
        if not isinstance(evidence_ids, list) or not evidence_ids or any(not isinstance(v, str) or not v for v in evidence_ids):
            raise ValueError('Explicit evidence IDs are required')
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError('Duplicate evidence selection')
        selected = sorted(evidence_ids)
        fingerprint = hashlib.sha256(_json([task_id, task_revision, selected, authority_ref]).encode()).hexdigest()
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            old = c.execute('SELECT request_hash,valid FROM acceptance WHERE acceptance_id=?', (acceptance_id,)).fetchone()
            if old:
                if old[0] != fingerprint:
                    raise StateConflict('Acceptance ID reused with different request')
                return {'decision': 'REPLAY', 'verification': 'HISTORICAL_RECEIPT', 'currently_valid': bool(old[1]),
                        'current_artifacts_reverified':False}
            task = self.store.task(task_id)
            if task is None or task['revision'] != task_revision or task['status'] not in {'RUNNING','VERIFYING'}:
                raise StateConflict('Acceptance requires the current running task')
            from v2_task_lifecycle import enter_verification
            enter_verification(self.store,task_id,task_revision,review_ref=authority_ref)
            from v2_governance import require_task_phase
            require_task_phase(self.store,task_id)
            if self.store.unresolved_dependencies(task_id,task_revision):
                raise StateConflict('Task dependencies no longer have valid accepted results')
            if c.execute("SELECT 1 FROM operation WHERE task_id=? AND state IN ('PREPARED','INTENT_RECORDED','UNKNOWN') LIMIT 1", (task_id,)).fetchone():
                raise StateConflict('Task has unresolved operations')
            latest = c.execute('''SELECT e.evidence_id,e.criterion,e.result,e.blob_hash,e.method,e.evidence_level FROM evidence e
                WHERE e.task_id=? AND e.task_revision=? AND e.sequence=(SELECT max(n.sequence) FROM evidence n
                WHERE n.task_id=e.task_id AND n.task_revision=e.task_revision AND n.criterion=e.criterion)''', (task_id, task_revision)).fetchall()
            definitions={r['criterion_id']:r for r in criteria(task['acceptance'])}
            latest=[row for row in latest if row[0] in selected]
            required={key for key,value in definitions.items() if value['hard']}
            if not required.issubset({row[1] for row in latest}) or {row[0] for row in latest} != set(selected):
                raise StateConflict('Select the latest evidence for every acceptance criterion')
            for _, criterion, result, digest, method, level in latest:
                definition=definitions[criterion]
                if definition['hard'] and result != 'PASS':
                    raise StateConflict('A current acceptance criterion failed')
                if method!=definition['verification_method'] or LEVELS[level]<LEVELS[definition['minimum_evidence_level']]:
                    raise StateConflict('Evidence method or level does not meet the acceptance contract')
            for evidence_id in selected:
                policy=c.execute('SELECT descriptor_json,revoked FROM evidence_policy WHERE evidence_id=?',(evidence_id,)).fetchone()
                if policy is None: raise PermissionError('Evidence capture policy is missing')
                require_access(json.loads(policy[0]),owner=task['project_id'],purpose='verification',revoked=bool(policy[1]))
                if c.execute('SELECT 1 FROM evidence_invalidation WHERE evidence_id=?',(evidence_id,)).fetchone():
                    raise StateConflict('Selected evidence has been invalidated')
                # Validate all payload bindings, then verify the Task's files once below.
                self._read_metered_in_transaction(evidence_id=evidence_id,owner=task['project_id'],purpose='verification',verify_artifacts=False)
            from v2_local_host import verify_task_file_results
            managed_files=verify_task_file_results(self.store,task_id,task_revision)
            c.execute('INSERT INTO acceptance(acceptance_id,task_id,task_revision,request_hash,evidence_ids_json,authority_ref) VALUES (?,?,?,?,?,?)', (acceptance_id, task_id, task_revision, fingerprint, _json(selected), authority_ref))
            c.execute("UPDATE task SET status='COMPLETED' WHERE task_id=? AND revision=?", (task_id, task_revision))
            c.execute("""UPDATE execution_run SET state='CLOSED' WHERE task_id=? AND task_revision=? AND state='OPEN'
                AND NOT EXISTS (SELECT 1 FROM host_dispatch h WHERE h.run_id=execution_run.run_id
                AND h.launch_committed=1 AND coalesce(h.quiesced,0)=0)""", (task_id,task_revision))
            c.execute("UPDATE operation SET state='ACCEPTED' WHERE task_id=? AND task_revision=? AND state='OBSERVED'", (task_id, task_revision))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)', ('TASK_ACCEPTED', task_id, _json({'acceptance_id': acceptance_id, 'revision': task_revision})))
            return {'decision': 'ACCEPTED', 'verification': 'EVIDENCE_CHECKED','managed_file_results_reverified':managed_files}

    def verify_task_completion(self, *, task_id):
        """Read current proof without rewriting the historical acceptance."""
        c=self.store.connection
        owns_transaction=not c.in_transaction
        if owns_transaction: c.execute('BEGIN')
        try:
            task=self.store.task(task_id)
            accepted=c.execute('SELECT acceptance_id,evidence_ids_json FROM acceptance '
                               'WHERE task_id=? AND task_revision=? AND valid=1',
                               (task_id,task['revision'])).fetchone()
            issues=set()
            if task['status']!='COMPLETED' or accepted is None:
                issues.add('TASK_NOT_CURRENTLY_ACCEPTED')
            if c.execute('SELECT reconciliation_required FROM recovery_state').fetchone()[0]:
                issues.add('RECOVERY_QUARANTINE')
            if self.store.unresolved_dependencies(task_id,task['revision']):
                issues.add('TASK_DEPENDENCIES_CHANGED')
            binding=c.execute('''SELECT b.phase_id,b.phase_revision,p.revision FROM phase_task b
                JOIN phase p ON p.phase_id=b.phase_id WHERE b.task_id=? AND b.task_revision=?''',
                (task_id,task['revision'])).fetchone()
            if binding is not None:
                from v2_governance import checked_phase_plan,require_carry_lineage
                if binding[1]!=binding[2]: issues.add('PHASE_REVISION_CHANGED')
                try:
                    checked_phase_plan(self.store,binding[0],binding[1])
                    require_carry_lineage(self.store,task_id,task['revision'])
                except (OSError,ValueError):
                    issues.add('PHASE_PLAN_OR_LINEAGE_CHANGED')
            evidence_ids=json.loads(accepted[1]) if accepted else []
            for evidence_id in evidence_ids:
                try:
                    self._read_metered_in_transaction(evidence_id=evidence_id,owner=task['project_id'],
                                                      purpose='verification',verify_artifacts=False)
                except (OSError,PermissionError,ValueError):
                    issues.add('SUPPORTING_EVIDENCE_UNAVAILABLE')
            if evidence_ids and 'SUPPORTING_EVIDENCE_UNAVAILABLE' not in issues:
                from v2_local_host import verify_task_file_results
                try:
                    verify_task_file_results(self.store,task_id,task['revision'])
                except (OSError,PermissionError,ValueError):
                    issues.add('SUPPORTING_EVIDENCE_UNAVAILABLE')
            result={'task_id':task_id,'task_revision':task['revision'],
                    'acceptance_id':accepted[0] if accepted else None,
                    'decision':'CURRENT_EVIDENCE_VALID' if not issues else 'NO_LONGER_PROVEN',
                    'issues':sorted(issues),'checked_evidence':len(evidence_ids),
                    'external_artifacts_reverified':False,'writes_performed':False}
            if owns_transaction: c.execute('COMMIT')
            return result
        except BaseException:
            if owns_transaction and c.in_transaction: c.execute('ROLLBACK')
            raise

    def invalidate(self, *, evidence_id, reason, authority_ref):
        _text(reason,'reason')
        _text(authority_ref,'authority_ref')
        with self.store.transaction() as c:
            evidence=c.execute('SELECT task_id,task_revision FROM evidence WHERE evidence_id=?',(evidence_id,)).fetchone()
            if evidence is None:
                raise StateConflict('Unknown evidence')
            old=c.execute('SELECT reason,authority_ref FROM evidence_invalidation WHERE evidence_id=?',(evidence_id,)).fetchone()
            if old:
                if old!=(reason,authority_ref):
                    raise StateConflict('Evidence invalidation is immutable')
                return {'decision':'REPLAY'}
            c.execute('INSERT INTO evidence_invalidation VALUES (?,?,?)',(evidence_id,reason,authority_ref))
            accepted=c.execute('SELECT evidence_ids_json FROM acceptance WHERE task_id=? AND task_revision=? AND valid=1',evidence).fetchall()
            affected=[]
            if any(evidence_id in json.loads(row[0]) for row in accepted):
                affected=c.execute('''WITH RECURSIVE affected(id,revision) AS (
                    SELECT ?,? UNION SELECT d.task_id,d.task_revision FROM dependency d
                    JOIN task t ON t.task_id=d.task_id AND t.revision=d.task_revision
                    JOIN affected a ON d.predecessor_id=a.id AND d.predecessor_revision=a.revision)
                    SELECT id,revision FROM affected''',evidence).fetchall()
            for task_id,revision in affected:
                if (task_id,revision)!=evidence:
                    downstream=c.execute('SELECT evidence_id FROM evidence WHERE task_id=? AND task_revision=?',(task_id,revision)).fetchall()
                    for (dependent_evidence,) in downstream:
                        c.execute('INSERT OR IGNORE INTO evidence_invalidation VALUES (?,?,?)',
                                  (dependent_evidence,'Dependency evidence invalidated: '+evidence_id,authority_ref))
                c.execute('UPDATE acceptance SET valid=0,invalidation_ref=? WHERE task_id=? AND task_revision=? AND valid=1',(evidence_id,task_id,revision))
                c.execute('''UPDATE project_completion SET valid=0,invalidation_ref=? WHERE project_id=
                    (SELECT project_id FROM task WHERE task_id=?) AND valid=1''',(evidence_id,task_id))
                completions=c.execute('''SELECT p.completion_id,p.phase_id FROM phase_completion p JOIN phase_completion_task t
                    ON t.completion_id=p.completion_id WHERE t.task_id=? AND t.task_revision=? AND p.valid=1''',(task_id,revision)).fetchall()
                for completion_id,phase_id in completions:
                    c.execute('UPDATE phase_completion SET valid=0,invalidation_ref=? WHERE completion_id=?',(evidence_id,completion_id))
                    c.execute('''UPDATE project_completion SET valid=0,invalidation_ref=? WHERE completion_id IN
                        (SELECT completion_id FROM project_completion_phase WHERE phase_completion_id=?)''',(evidence_id,completion_id))
                    c.execute("UPDATE phase SET state='PAUSED' WHERE phase_id=? AND state='COMPLETED'",(phase_id,))
                pending=c.execute("SELECT 1 FROM operation WHERE task_id=? AND state IN ('INTENT_RECORDED','UNKNOWN') LIMIT 1",(task_id,)).fetchone()
                if pending and c.execute('SELECT status FROM task WHERE task_id=?',(task_id,)).fetchone()[0] in {'RUNNING','VERIFYING'}:
                    c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                              ('TASK_PAUSE_REQUESTED',task_id,_json({'task_revision':revision,'reason':'EVIDENCE_INVALIDATED','evidence_id':evidence_id})))
                c.execute("UPDATE task SET status=CASE WHEN status='COMPLETED' THEN 'READY' WHEN status IN ('RUNNING','VERIFYING') THEN ? ELSE status END WHERE task_id=? AND revision=?",('WAITING' if pending else 'PAUSED',task_id,revision))
                c.execute("UPDATE execution_run SET state=? WHERE task_id=? AND task_revision=? AND state='OPEN'",('PAUSE_REQUESTED' if pending else 'PAUSED',task_id,revision))
                c.execute("UPDATE operation SET state='CANCELLED' WHERE task_id=? AND task_revision=? AND state='PREPARED'",(task_id,revision))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                      ('EVIDENCE_INVALIDATED',evidence_id,_json({'reason':reason,'authority_ref':authority_ref,'affected':affected})))
            return {'decision':'INVALIDATED','affected_tasks':[{'task_id':t,'revision':r} for t,r in affected]}
