"""Versioned Project/Phase definitions; no implicit activation or execution."""
import hashlib
import re
import json
from pathlib import Path
from v2_state_store import StateConflict, _json, _text
from v2_contracts import criteria,phase_boundary
from v2_evidence import _regular_path
from v2_definition_content import encode,decode,request_fingerprint,write_goal,read_preview


def checked_phase_plan(store,phase_id,revision):
    row=store.connection.execute('''SELECT p.resource_root,r.plan_ref,r.plan_sha256,r.project_revision,
        (SELECT max(x.revision) FROM project_revision x WHERE x.project_id=p.project_id),r.plan_scope
        FROM phase_revision r JOIN phase ph ON ph.phase_id=r.phase_id JOIN project p ON p.project_id=ph.project_id
        WHERE r.phase_id=? AND r.revision=?''',(phase_id,revision)).fetchone()
    if row is None or row[3]!=row[4]: raise StateConflict('Phase Project revision is stale')
    relative=Path(row[1])
    if relative.is_absolute() or relative.drive or '..' in relative.parts:
        raise StateConflict('Phase plan must be a project-relative regular file')
    plan=(store.path.parent if row[5]=='STATE' else Path(row[0]))/relative
    _regular_path(plan)
    digest=hashlib.sha256()
    with plan.open('rb') as stream:
        for chunk in iter(lambda:stream.read(65536),b''): digest.update(chunk)
    if digest.hexdigest()!=row[2]: raise StateConflict('Phase plan content changed')


def require_carry_lineage(store,task_id,through_revision):
    c=store.connection
    bindings=c.execute('SELECT task_revision,phase_id,phase_revision FROM phase_task WHERE task_id=? AND task_revision<=? ORDER BY task_revision',(task_id,through_revision)).fetchall()
    for previous,current in zip(bindings,bindings[1:]):
        if previous[1]==current[1]: continue
        if not c.execute('''SELECT 1 FROM phase_carryover WHERE task_id=? AND source_task_revision=?
            AND source_phase_id=? AND source_phase_revision=? AND target_task_revision=? AND target_phase_id=? AND target_phase_revision=?''',
            (task_id,*previous,*current)).fetchone():
            raise StateConflict('Cross-Phase execution requires explicit carry-over acceptance throughout lineage')


def require_task_phase(store,task_id):
    c=store.connection
    task=store.task_identity(task_id)
    row=c.execute('''SELECT b.phase_id,b.phase_revision,p.revision,p.state FROM phase_task b
        JOIN phase p ON p.phase_id=b.phase_id WHERE b.task_id=? AND b.task_revision=?''',(task_id,task['revision'])).fetchone()
    if row is None:
        if c.execute('SELECT 1 FROM phase_task WHERE task_id=?',(task_id,)).fetchone():
            raise StateConflict('Revised governed Task requires an explicit Phase binding')
        return
    if row[1]!=row[2] or row[3]!='ACTIVE': raise StateConflict('Task requires its current active Phase')
    require_carry_lineage(store,task_id,task['revision'])
    checked_phase_plan(store,row[0],row[1])


class Governance:
    def __init__(self, store): self.store=store

    def context(self, *, project_id, after_phase_id='', limit=20):
        _text(project_id,'project_id')
        if type(limit) is not int or not 1<=limit<=100 or not isinstance(after_phase_id,str):
            raise ValueError('Invalid governance page')
        c=self.store.connection
        c.execute('BEGIN')
        try:
            project=c.execute('SELECT project_id FROM project WHERE project_id=?',(project_id,)).fetchone()
            if project is None: raise StateConflict('Unknown project')
            original=read_preview(c,project_id,'project-original',project_id,0)
            project=(original['text'],original['characters'])
            current=c.execute('SELECT revision FROM project_revision WHERE project_id=? ORDER BY revision DESC LIMIT 1',(project_id,)).fetchone()
            current_preview=None
            if current:
                current_preview=read_preview(c,project_id,'project',project_id,current[0])
                current=(current[0],current_preview['text'],current_preview['characters'])
            active=c.execute("SELECT phase_id,revision FROM phase WHERE project_id=? AND state='ACTIVE'",(project_id,)).fetchone()
            phases=c.execute('''SELECT p.phase_id,p.revision,p.state,r.project_revision
                FROM phase p JOIN phase_revision r ON r.phase_id=p.phase_id AND r.revision=p.revision
                WHERE p.project_id=? AND p.phase_id>? ORDER BY p.phase_id LIMIT ?''',(project_id,after_phase_id,limit+1)).fetchall()
            phase_views=[]
            for row in phases[:limit]:
                view=read_preview(c,project_id,'phase',row[0],row[1],limit=512)
                phase_views.append({**dict(zip(('phase_id','revision','state','project_revision'),row)),
                    'goal_preview':view['text'],'goal_characters':view['characters'],'goal_preview_status':view['status']})
            work={row[0]:row[1] for row in c.execute('SELECT status,count(*) FROM task WHERE project_id=? GROUP BY status',(project_id,))}
            epoch,quarantine=c.execute('SELECT epoch,reconciliation_required FROM recovery_state').fetchone()
            receipt=c.execute('SELECT completion_id FROM project_completion WHERE project_id=? AND project_revision=? AND valid=1',
                              (project_id,current[0] if current else 0)).fetchone()
            result={'project_id':project_id,'original_goal_preview':project[0],'original_goal_characters':project[1],
                    'current_definition':None if current is None else dict(zip(('revision','goal_preview','goal_characters'),current)),
                    'active_phase':None if active is None else {'phase_id':active[0],'revision':active[1]},
                    'phases':phase_views,'original_goal_preview_status':original['status'],
                    'next_after_phase_id':phases[limit-1][0] if len(phases)>limit else None,
                    'task_counts':work,'epoch':epoch,'reconciliation_required':bool(quarantine),
                    'historical_completion_id':receipt[0] if receipt else None,
                    'current_completion_reverified':False,'execution_authorized':False,'writes_performed':False,
                    'pagination_consistency':'LIVE_KEYSET','full_definitions_included':False}
            result['pending_migration_domains']=self.store.pending_migration_domains()
            result['definition_body_reverified']=False
            if result['current_definition'] is not None:result['current_definition']['goal_preview_status']=current_preview['status']
            c.execute('COMMIT')
            return result
        except BaseException:
            if c.in_transaction: c.execute('ROLLBACK')
            raise

    def task_queue(self, *, project_id, after_task_id='', limit=20):
        """Planning readiness only. Grant/budget/resource admission is separate."""
        _text(project_id,'project_id')
        if type(limit) is not int or not 1<=limit<=100 or not isinstance(after_task_id,str):
            raise ValueError('Invalid task queue page')
        c=self.store.connection
        c.execute('BEGIN')
        try:
            if not c.execute('SELECT 1 FROM project WHERE project_id=?',(project_id,)).fetchone(): raise StateConflict('Unknown Project')
            quarantined=c.execute('SELECT reconciliation_required FROM recovery_state').fetchone()[0]
            pending_migration=self.store.pending_migration_domains()
            rows=c.execute('''WITH active_work(task_id) AS (
                SELECT task_id FROM task WHERE project_id=? AND task_id>? AND status NOT IN ('COMPLETED','CANCELLED')
                ORDER BY task_id LIMIT ?), pending_work(task_id) AS (
                SELECT DISTINCT o.task_id FROM operation o INDEXED BY unresolved_operation_by_task CROSS JOIN task t ON t.task_id=o.task_id
                WHERE t.project_id=? AND o.task_id>? AND t.status IN ('COMPLETED','CANCELLED') AND o.state IN ('INTENT_RECORDED','UNKNOWN')
                ORDER BY o.task_id LIMIT ?), work(task_id) AS (
                SELECT task_id FROM active_work UNION SELECT task_id FROM pending_work)
                SELECT t.task_id,t.revision,t.status
                FROM work w CROSS JOIN task t ON w.task_id=t.task_id
                JOIN task_revision r ON r.task_id=t.task_id AND r.revision=t.revision WHERE t.task_id>?
                ORDER BY t.task_id LIMIT ?''',(project_id,after_task_id,limit+1,project_id,after_task_id,limit+1,after_task_id,limit+1)).fetchall()
            tasks=[]
            for task_id,revision,state in rows[:limit]:
                preview=read_preview(c,project_id,'task',task_id,revision,limit=512)
                goal,characters=preview['text'],preview['characters']
                reasons=[]
                if preview['status']!='AVAILABLE':reasons.append('GOAL_PREVIEW_UNAVAILABLE')
                if quarantined: reasons.append('RECOVERY_RECONCILIATION_REQUIRED')
                if state=='RECOVERY_REQUIRED':reasons.append('EFFECT_RECOVERY_REQUIRED')
                elif state=='VERIFYING':reasons.append('VERIFICATION_IN_PROGRESS')
                elif state not in {'READY','RUNNING'}: reasons.append('TASK_REQUIRES_RESUME_OR_REPLAN')
                reconciliation_only=state in {'COMPLETED','CANCELLED'}
                if reconciliation_only: reasons=['RECONCILIATION_ONLY']+([ 'RECOVERY_RECONCILIATION_REQUIRED'] if quarantined else [])
                if pending_migration: reasons.append('SEMANTIC_MIGRATION_INCOMPLETE')
                dependencies=self.store.unresolved_dependencies(task_id,revision)
                if dependencies: reasons.append('DEPENDENCIES_NOT_ACCEPTED')
                pending=c.execute("SELECT count(*) FROM operation WHERE task_id=? AND state IN ('INTENT_RECORDED','UNKNOWN')",(task_id,)).fetchone()[0]
                if pending: reasons.append('UNRESOLVED_EFFECTS')
                try: require_task_phase(self.store,task_id)
                except (ValueError,OSError): reasons.append('PHASE_REVIEW_REQUIRED')
                tasks.append({'task_id':task_id,'revision':revision,'state':state,'goal_preview':goal,
                              'goal_preview_status':preview['status'],
                              'goal_characters':characters,'planning_ready':not reasons,'blockers':reasons,
                              'reconciliation_only':reconciliation_only,
                              'unresolved_dependency_count':len(dependencies),'pending_effect_count':pending})
            result={'project_id':project_id,'tasks':tasks,
                    'next_after_task_id':rows[limit-1][0] if len(rows)>limit else None,
                    'pagination_consistency':'LIVE_KEYSET','writes_performed':False,'execution_authorized':False,
                    'checks_not_performed':['grant','budget','resource-admission','host-liveness']}
            result['definition_body_reverified']=False
            result['pending_migration_domains']=pending_migration
            c.execute('COMMIT')
            return result
        except BaseException:
            if c.in_transaction: c.execute('ROLLBACK')
            raise

    def carry_task(self, *, carry_id, task_id, source_task_revision, target_task_revision,
                   target_phase_id, target_phase_revision, authority_ref, reason):
        for key,value in [('carry_id',carry_id),('task_id',task_id),('target_phase_id',target_phase_id),('authority_ref',authority_ref),('reason',reason)]: _text(value,key)
        if any(type(v) is not int or v<1 for v in (source_task_revision,target_task_revision,target_phase_revision)):
            raise ValueError('Carry-over revisions must be positive integers')
        fingerprint=hashlib.sha256(_json([task_id,source_task_revision,target_task_revision,target_phase_id,target_phase_revision,authority_ref,reason]).encode()).hexdigest()
        with self.store.transaction() as c:
            prior=c.execute('SELECT request_hash FROM phase_carryover WHERE carry_id=?',(carry_id,)).fetchone()
            if prior:
                if prior[0]!=fingerprint: raise StateConflict('Carry-over identity conflict')
                return 'REPLAY'
            source=c.execute('SELECT phase_id,phase_revision FROM phase_task WHERE task_id=? AND task_revision=?',(task_id,source_task_revision)).fetchone()
            target=c.execute('SELECT phase_id,phase_revision FROM phase_task WHERE task_id=? AND task_revision=?',(task_id,target_task_revision)).fetchone()
            task=self.store.task(task_id)
            previous=c.execute('SELECT task_revision FROM phase_task WHERE task_id=? AND task_revision<? ORDER BY task_revision DESC LIMIT 1',(task_id,target_task_revision)).fetchone()
            if previous!=(source_task_revision,): raise StateConflict('Carry-over must join consecutive bindings')
            require_carry_lineage(self.store,task_id,source_task_revision)
            if (source is None or target!=(target_phase_id,target_phase_revision) or source[0]==target_phase_id or
                    target_task_revision<=source_task_revision or task['revision']<target_task_revision or task['status']!='READY'):
                raise StateConflict('Carry-over requires a revised READY Task explicitly bound to a different Phase')
            suffix=c.execute('''SELECT task_revision,phase_id,phase_revision FROM phase_task
                WHERE task_id=? AND task_revision>=? ORDER BY task_revision''',(task_id,target_task_revision)).fetchall()
            if (not suffix or suffix[-1][0]!=task['revision'] or
                    any(row[1:]!=(target_phase_id,target_phase_revision) for row in suffix)):
                raise StateConflict('Late carry-over requires an unchanged destination binding through the current revision')
            phase=c.execute('SELECT revision,state FROM phase WHERE phase_id=?',(source[0],)).fetchone()
            destination=c.execute('SELECT revision,state FROM phase WHERE phase_id=?',(target_phase_id,)).fetchone()
            if phase!=(source[1],'PAUSED') or destination[0]!=target_phase_revision or destination[1] not in {'PLANNED','PAUSED'}:
                raise StateConflict('Carry-over requires paused source and non-running current destination')
            if c.execute("SELECT 1 FROM operation WHERE task_id=? AND state IN ('INTENT_RECORDED','UNKNOWN')",(task_id,)).fetchone():
                raise StateConflict('Reconcile effects before transfer')
            c.execute('INSERT INTO phase_carryover VALUES (?,?,?,?,?,?,?,?,?,?,?)',(carry_id,task_id,source_task_revision,*source,target_task_revision,target_phase_id,target_phase_revision,authority_ref,reason,fingerprint))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',('TASK_CARRIED',task_id,_json({'carry_id':carry_id,'source':source,'target':target})))
            return 'CARRIED'

    def verify_phase_completion(self, *, completion_id):
        from v2_acceptance import Acceptance
        from v2_evidence import BlobStore, EvidenceCorrupt
        _text(completion_id,'completion_id')
        c=self.store.connection
        owns_transaction=not c.in_transaction
        if owns_transaction: c.execute('BEGIN')
        try:
            receipt=c.execute('''SELECT f.phase_id,f.phase_revision,f.valid,p.project_id,p.revision,p.state
                FROM phase_completion f JOIN phase p ON p.phase_id=f.phase_id WHERE completion_id=?''',(completion_id,)).fetchone()
            if receipt is None: raise StateConflict('Unknown Phase completion receipt')
            issues=set()
            if not receipt[2]: issues.add('RECEIPT_INVALIDATED')
            if receipt[1]!=receipt[4] or receipt[5]!='COMPLETED': issues.add('PHASE_CHANGED')
            if c.execute('SELECT reconciliation_required FROM recovery_state').fetchone()[0]: issues.add('RECOVERY_QUARANTINE')
            from v2_artifacts import Artifacts
            try:
                graph=Artifacts(self.store).audit_relations(project_id=receipt[3],owner_phase_id=receipt[0],max_artifacts=1000)
                if graph['decision']!='REFERENCE_GRAPH_VALID':issues.add('ARTIFACT_REFERENCES_UNRESOLVED')
                if c.execute("SELECT 1 FROM artifact_definition WHERE phase_id=? AND disposition='UNRESOLVED' LIMIT 1",(receipt[0],)).fetchone():
                    issues.add('ARTIFACT_DISPOSITION_UNRESOLVED')
            except (ValueError,OSError):issues.add('ARTIFACT_REFERENCES_UNAVAILABLE')
            try: checked_phase_plan(self.store,receipt[0],receipt[1])
            except (OSError,ValueError): issues.add('PLAN_OR_PROJECT_CHANGED')
            service=Acceptance(self.store,BlobStore(self.store.path.parent/'blobs',readonly=True))
            tasks=c.execute('SELECT task_id,task_revision,acceptance_id FROM phase_completion_task WHERE completion_id=?',(completion_id,)).fetchall()
            for task_id,revision,acceptance_id in tasks:
                proof=service.verify_task_completion(task_id=task_id)
                if proof['task_revision']!=revision or proof['acceptance_id']!=acceptance_id:
                    issues.add('TASK_ACCEPTANCE_CHANGED')
                if 'TASK_DEPENDENCIES_CHANGED' in proof['issues']:
                    issues.add('TASK_DEPENDENCIES_CHANGED')
                if proof['decision']!='CURRENT_EVIDENCE_VALID':
                    issues.add('SUPPORTING_EVIDENCE_UNAVAILABLE')
            result={'completion_id':completion_id,'decision':'CURRENT_EVIDENCE_VALID' if not issues else 'NO_LONGER_PROVEN',
                    'issues':sorted(issues),'checked_tasks':len(tasks),'writes_performed':False,
                    'external_artifacts_reverified':False}
            if owns_transaction: c.execute('COMMIT')
            return result
        except BaseException:
            if owns_transaction and c.in_transaction: c.execute('ROLLBACK')
            raise

    def complete_project(self, *, completion_id, project_id, expected_revision, criterion_evidence, authority_ref):
        from v2_acceptance import Acceptance
        from v2_evidence import BlobStore
        from v2_contracts import LEVELS
        for key,value in [('completion_id',completion_id),('project_id',project_id),('authority_ref',authority_ref)]: _text(value,key)
        if type(expected_revision) is not int or expected_revision<1 or not isinstance(criterion_evidence,dict):
            raise ValueError('Project completion requires a current revision and evidence mapping')
        if any(not isinstance(k,str) or not isinstance(v,str) or not v.strip() for k,v in criterion_evidence.items()): raise ValueError('Invalid Project evidence mapping')
        fingerprint=hashlib.sha256(_json([project_id,expected_revision,criterion_evidence,authority_ref]).encode()).hexdigest()
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            old=c.execute('SELECT request_hash,valid FROM project_completion WHERE completion_id=?',(completion_id,)).fetchone()
            if old:
                if old[0]!=fingerprint: raise StateConflict('Project completion request conflict')
                return {'decision':'REPLAY','verification':'HISTORICAL_RECEIPT','currently_valid':bool(old[1])}
            project=c.execute('SELECT revision,acceptance_json FROM project_revision WHERE project_id=? ORDER BY revision DESC LIMIT 1',(project_id,)).fetchone()
            if project is None or project[0]!=expected_revision: raise StateConflict('Project definition changed')
            definitions={v['criterion_id']:v for v in criteria(decode(project[1],project_id,'project',project_id,project[0],'acceptance'))}
            if not {k for k,v in definitions.items() if v['hard']}.issubset(criterion_evidence) or not set(criterion_evidence).issubset(definitions):
                raise StateConflict('Global acceptance criteria are not covered')
            phases=c.execute('SELECT phase_id,revision,state FROM phase WHERE project_id=?',(project_id,)).fetchall()
            if not phases: raise StateConflict('Governed Project completion requires completed Phases')
            phase_receipts=[]
            supported=set()
            for phase_id,revision,state in phases:
                receipt=c.execute('SELECT completion_id FROM phase_completion WHERE phase_id=? AND phase_revision=? AND valid=1',(phase_id,revision)).fetchone()
                if state!='COMPLETED' or receipt is None: raise StateConflict('Project has unfinished Phase obligations')
                if self.verify_phase_completion(completion_id=receipt[0])['decision']!='CURRENT_EVIDENCE_VALID':
                    raise StateConflict('Phase supporting evidence is no longer valid')
                phase_receipts.append(receipt[0])
                for (evidence_json,) in c.execute('''SELECT a.evidence_ids_json FROM phase_completion_task p
                    JOIN acceptance a ON a.acceptance_id=p.acceptance_id WHERE p.completion_id=?''',(receipt[0],)):
                    supported.update(json.loads(evidence_json))
            service=Acceptance(self.store,BlobStore(self.store.path.parent/'blobs',readonly=True))
            for task_id,revision,status in c.execute('SELECT task_id,revision,status FROM task WHERE project_id=?',(project_id,)).fetchall():
                if status!='COMPLETED' or not self.store.task(task_id)['acceptance_valid']:
                    raise StateConflict('Project contains unresolved Task obligations')
                if self.store.unresolved_dependencies(task_id,revision): raise StateConflict('Project Task dependencies changed')
                accepted=c.execute('SELECT evidence_ids_json FROM acceptance WHERE task_id=? AND task_revision=? AND valid=1',(task_id,revision)).fetchone()
                for evidence_id in json.loads(accepted[0]):
                    service._read_in_transaction(evidence_id=evidence_id,owner=project_id,purpose='verification')
            for criterion,evidence_id in criterion_evidence.items():
                if evidence_id not in supported: raise StateConflict('Global evidence must support a completed Phase')
                service._read_in_transaction(evidence_id=evidence_id,owner=project_id,purpose='verification')
                result,method,level=c.execute('SELECT result,method,evidence_level FROM evidence WHERE evidence_id=?',(evidence_id,)).fetchone()
                definition=definitions[criterion]
                if (definition['hard'] and result!='PASS') or method!=definition['verification_method'] or LEVELS[level]<LEVELS[definition['minimum_evidence_level']]:
                    raise StateConflict('Global evidence does not meet required result, method or level')
            c.execute('INSERT INTO project_completion VALUES (?,?,?,?,?,?,1,NULL)',(completion_id,project_id,expected_revision,fingerprint,_json(criterion_evidence),authority_ref))
            c.executemany('INSERT INTO project_completion_phase VALUES (?,?)',[(completion_id,p) for p in phase_receipts])
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',('PROJECT_COMPLETED',project_id,_json({'completion_id':completion_id})))
            return {'decision':'COMPLETED','verification':'EVIDENCE_CHECKED','external_artifacts_reverified':False}

    def verify_project_completion(self, *, completion_id):
        from v2_acceptance import Acceptance
        from v2_evidence import BlobStore
        _text(completion_id,'completion_id')
        c=self.store.connection
        c.execute('BEGIN')
        try:
            receipt=c.execute('SELECT project_id,project_revision,valid FROM project_completion WHERE completion_id=?',(completion_id,)).fetchone()
            if receipt is None: raise StateConflict('Unknown Project completion receipt')
            issues=set()
            if not receipt[2]: issues.add('RECEIPT_INVALIDATED')
            revision=c.execute('SELECT max(revision) FROM project_revision WHERE project_id=?',(receipt[0],)).fetchone()[0]
            if revision!=receipt[1]: issues.add('PROJECT_REVISED')
            phase_receipts=[r[0] for r in c.execute('SELECT phase_completion_id FROM project_completion_phase WHERE completion_id=?',(completion_id,))]
            for phase_receipt in phase_receipts:
                if self.verify_phase_completion(completion_id=phase_receipt)['decision']!='CURRENT_EVIDENCE_VALID':
                    issues.add('PHASE_EVIDENCE_NO_LONGER_PROVEN')
            service=Acceptance(self.store,BlobStore(self.store.path.parent/'blobs',readonly=True))
            tasks=c.execute('SELECT task_id,revision,status FROM task WHERE project_id=?',(receipt[0],)).fetchall()
            for task_id,revision,status in tasks:
                proof=service.verify_task_completion(task_id=task_id)
                if 'TASK_NOT_CURRENTLY_ACCEPTED' in proof['issues']:
                    issues.add('TASK_OBLIGATIONS_UNRESOLVED')
                if 'TASK_DEPENDENCIES_CHANGED' in proof['issues']:
                    issues.add('TASK_DEPENDENCIES_CHANGED')
                if proof['decision']!='CURRENT_EVIDENCE_VALID':
                    issues.add('TASK_EVIDENCE_UNAVAILABLE')
            result={'completion_id':completion_id,'decision':'CURRENT_EVIDENCE_VALID' if not issues else 'NO_LONGER_PROVEN',
                    'issues':sorted(issues),'checked_phases':len(phase_receipts),'checked_tasks':len(tasks),
                    'external_artifacts_reverified':False,'writes_performed':False}
            c.execute('COMMIT')
            return result
        except BaseException:
            if c.in_transaction: c.execute('ROLLBACK')
            raise

    def complete_phase(self, *, completion_id, phase_id, expected_revision, criterion_evidence, authority_ref):
        from v2_acceptance import Acceptance
        from v2_evidence import BlobStore
        from v2_contracts import LEVELS
        for key,value in [('completion_id',completion_id),('phase_id',phase_id),('authority_ref',authority_ref)]: _text(value,key)
        if type(expected_revision) is not int or expected_revision<1 or not isinstance(criterion_evidence,dict):
            raise ValueError('Phase completion requires a revision and criterion/evidence mapping')
        if any(not isinstance(k,str) or not isinstance(v,str) or not v.strip() for k,v in criterion_evidence.items()):
            raise ValueError('Invalid Phase evidence mapping')
        fingerprint=hashlib.sha256(_json([phase_id,expected_revision,criterion_evidence,authority_ref]).encode()).hexdigest()
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            old=c.execute('SELECT request_hash,valid FROM phase_completion WHERE completion_id=?',(completion_id,)).fetchone()
            if old:
                if old[0]!=fingerprint: raise StateConflict('Phase completion identity conflict')
                return {'decision':'REPLAY','verification':'HISTORICAL_RECEIPT','currently_valid':bool(old[1])}
            phase=c.execute('''SELECT p.project_id,p.revision,p.state,r.acceptance_json FROM phase p JOIN phase_revision r
                ON r.phase_id=p.phase_id AND r.revision=p.revision WHERE p.phase_id=?''',(phase_id,)).fetchone()
            if phase is None or phase[1]!=expected_revision or phase[2]!='ACTIVE': raise StateConflict('Phase completion requires current ACTIVE Phase')
            if c.execute("SELECT 1 FROM artifact_definition WHERE phase_id=? AND disposition='UNRESOLVED' LIMIT 1",(phase_id,)).fetchone():
                raise StateConflict('Phase has unresolved Artifact dispositions')
            from v2_artifacts import Artifacts
            if Artifacts(self.store).audit_relations(project_id=phase[0],owner_phase_id=phase_id,max_artifacts=1000)['decision']!='REFERENCE_GRAPH_VALID':
                raise StateConflict('Phase Artifact references are unresolved or audit is incomplete')
            checked_phase_plan(self.store,phase_id,expected_revision)
            definitions={v['criterion_id']:v for v in criteria(decode(phase[3],phase[0],'phase',phase_id,phase[1],'acceptance'))}
            if not {k for k,v in definitions.items() if v['hard']}.issubset(criterion_evidence) or not set(criterion_evidence).issubset(definitions):
                raise StateConflict('Phase completion requires every hard criterion and no unknown criteria')
            task_ids=[r[0] for r in c.execute('SELECT DISTINCT task_id FROM phase_task WHERE phase_id=?',(phase_id,))]
            if not task_ids: raise StateConflict('An empty Phase has no delivery evidence')
            service=Acceptance(self.store,BlobStore(self.store.path.parent/'blobs',readonly=True))
            memberships=[]
            accepted_evidence=set()
            for task_id in task_ids:
                task=self.store.task(task_id)
                binding=c.execute('SELECT phase_id,phase_revision FROM phase_task WHERE task_id=? AND task_revision=?',(task_id,task['revision'])).fetchone()
                carried=c.execute('''SELECT target_task_revision,target_phase_id,target_phase_revision FROM phase_carryover
                    WHERE task_id=? AND source_phase_id=? AND source_phase_revision=?''',(task_id,phase_id,expected_revision)).fetchone()
                if carried and task['revision']>=carried[0]:
                    require_carry_lineage(self.store,task_id,task['revision'])
                    if binding is not None and binding[0]!=phase_id:
                        continue
                if binding!=(phase_id,expected_revision) or task['status']!='COMPLETED' or not task['acceptance_valid']:
                    raise StateConflict('Phase has incomplete, moved or stale Task obligations')
                if c.execute("SELECT 1 FROM operation WHERE task_id=? AND state IN ('PREPARED','INTENT_RECORDED','UNKNOWN')",(task_id,)).fetchone():
                    raise StateConflict('Phase has unresolved effects')
                accepted=c.execute('SELECT acceptance_id,evidence_ids_json FROM acceptance WHERE task_id=? AND task_revision=? AND valid=1',(task_id,task['revision'])).fetchone()
                for evidence_id in json.loads(accepted[1]):
                    service._read_in_transaction(evidence_id=evidence_id,owner=phase[0],purpose='verification')
                    accepted_evidence.add(evidence_id)
                memberships.append((completion_id,task_id,task['revision'],accepted[0]))
            for criterion,evidence_id in criterion_evidence.items():
                if evidence_id not in accepted_evidence: raise StateConflict('Phase evidence must support accepted bound Task output')
                result,method,level=c.execute('SELECT result,method,evidence_level FROM evidence WHERE evidence_id=?',(evidence_id,)).fetchone()
                definition=definitions[criterion]
                if (definition['hard'] and result!='PASS') or method!=definition['verification_method'] or LEVELS[level]<LEVELS[definition['minimum_evidence_level']]:
                    raise StateConflict('Phase criterion method, level or result is not satisfied')
            c.execute('INSERT INTO phase_completion VALUES (?,?,?,?,?,?,1,NULL)',(completion_id,phase_id,expected_revision,fingerprint,_json(criterion_evidence),authority_ref))
            c.executemany('INSERT INTO phase_completion_task VALUES (?,?,?,?)',memberships)
            c.execute("UPDATE phase SET state='COMPLETED' WHERE phase_id=?",(phase_id,))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',('PHASE_COMPLETED',phase_id,_json({'completion_id':completion_id})))
            return {'decision':'COMPLETED','verification':'EVIDENCE_CHECKED'}

    def bind_task(self, *, task_id, task_revision, phase_id, phase_revision, authority_ref):
        _text(authority_ref,'authority_ref')
        if type(task_revision) is not int or type(phase_revision) is not int:
            raise ValueError('Binding revisions must be integers')
        with self.store.transaction() as c:
            task=self.store.task(task_id)
            phase=c.execute('''SELECT p.project_id,p.revision,p.state,r.boundary_json FROM phase p
                JOIN phase_revision r ON r.phase_id=p.phase_id AND r.revision=p.revision WHERE p.phase_id=?''',(phase_id,)).fetchone()
            if (task is None or phase is None or task['revision']!=task_revision or phase[1]!=phase_revision or
                    task['project_id']!=phase[0] or task['status']!='READY' or phase[2] not in {'PLANNED','ACTIVE','PAUSED'}):
                raise StateConflict('Binding requires current same-project definitions and READY Task')
            values=(task_id,task_revision,phase_id,phase_revision,authority_ref)
            old=c.execute('SELECT * FROM phase_task WHERE task_id=? AND task_revision=?',(task_id,task_revision)).fetchone()
            if old:
                if old!=values: raise StateConflict('Task revision Phase binding is immutable')
                return 'REPLAY'
            if c.execute('SELECT 1 FROM operation WHERE task_id=? AND task_revision=?',(task_id,task_revision)).fetchone():
                raise StateConflict('Bind Phase before preparing operations')
            boundary=decode(phase[3],phase[0],'phase',phase_id,phase[1],'boundary')
            if not set(task['scope']).issubset(boundary['in_scope']) or set(task['scope']).intersection(boundary['out_of_scope']):
                raise StateConflict('Task exceeds declared Phase scope')
            c.execute('INSERT INTO phase_task VALUES (?,?,?,?,?)',values)
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',('TASK_PHASE_BOUND',task_id,_json({'binding':values})))
            return 'BOUND'

    def set_phase_active(self, *, phase_id, expected_revision, active, authority_ref):
        _text(authority_ref,'authority_ref')
        if type(expected_revision) is not int or expected_revision<1 or type(active) is not bool:
            raise ValueError('Invalid Phase activation request')
        with self.store.transaction() as c:
            row=c.execute('SELECT project_id,revision,state FROM phase WHERE phase_id=?',(phase_id,)).fetchone()
            if row is None or row[1]!=expected_revision or row[2] not in {'PLANNED','ACTIVE','PAUSED'}:
                raise StateConflict('Phase is stale or terminal')
            state='ACTIVE' if active else 'PAUSED'
            if active:
                self.store.require_execution_ready()
                checked_phase_plan(self.store,phase_id,expected_revision)
                if c.execute("SELECT 1 FROM phase WHERE project_id=? AND phase_id<>? AND state='ACTIVE'",(row[0],phase_id)).fetchone():
                    raise StateConflict('Another Phase is active in this project')
            if row[2]==state: return {'decision':'UNCHANGED','state':state}
            c.execute('UPDATE phase SET state=? WHERE phase_id=?',(state,phase_id))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                      ('PHASE_STATE_CHANGED',phase_id,_json({'state':state,'authority_ref':authority_ref})))
            return {'decision':'UPDATED','state':state,'host_termination_verified':False}

    def reopen_phase(self, *, phase_id, expected_revision, request_id, authority_ref, reason):
        for key,value in [('phase_id',phase_id),('request_id',request_id),('authority_ref',authority_ref),('reason',reason)]: _text(value,key)
        if type(expected_revision) is not int or expected_revision<1: raise ValueError('Invalid Phase revision')
        fingerprint=hashlib.sha256(_json(['phase.reopen',phase_id,expected_revision,authority_ref,reason]).encode()).hexdigest()
        with self.store.transaction() as c:
            replay=self._replay(c,request_id,fingerprint)
            if replay: return replay
            phase=c.execute('SELECT project_id,revision,state FROM phase WHERE phase_id=?',(phase_id,)).fetchone()
            if phase is None or phase[1]!=expected_revision or phase[2]!='COMPLETED':
                raise StateConflict('Explicit reopening requires the exact completed Phase revision')
            c.execute("UPDATE phase SET state='PAUSED' WHERE phase_id=?",(phase_id,))
            c.execute('UPDATE phase_completion SET valid=0,invalidation_ref=? WHERE phase_id=? AND valid=1',(request_id,phase_id))
            c.execute('UPDATE project_completion SET valid=0,invalidation_ref=? WHERE project_id=? AND valid=1',(request_id,phase[0]))
            result=self._receipt(c,request_id,fingerprint,phase_id,expected_revision,'PHASE_REOPENED')
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                      ('PHASE_REOPEN_REASON',phase_id,_json({'request_id':request_id,'authority_ref':authority_ref,'reason':reason})))
            result.update(decision='REOPENED',state='PAUSED',task_acceptances_changed=False)
            return result

    def _replay(self,c,request_id,fingerprint):
        prior=c.execute('SELECT request_hash,revision FROM governance_receipt WHERE request_id=?',(request_id,)).fetchone()
        if prior:
            if prior[0]!=fingerprint: raise StateConflict('Governance request ID reused with different content')
            return {'decision':'REPLAY','accepted_revision':prior[1],'execution_authorized':False}

    def _receipt(self,c,request_id,fingerprint,entity_id,revision,kind):
        c.execute('INSERT INTO governance_receipt VALUES (?,?,?,?)',(request_id,fingerprint,entity_id,revision))
        c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                  (kind,entity_id,_json({'revision':revision,'request_id':request_id})))
        return {'decision':'DEFINED','accepted_revision':revision,'execution_authorized':False}

    def define_project(self, *, project_id, expected_revision, goal, acceptance, authority_ref, request_id):
        for key,value in [('project_id',project_id),('goal',goal),('authority_ref',authority_ref),('request_id',request_id)]: _text(value,key)
        if type(expected_revision) is not int or expected_revision<0: raise ValueError('Invalid Project revision')
        acceptance=criteria(acceptance)
        fingerprint=request_fingerprint(self.store.connection,project_id,['project',project_id,expected_revision,goal,acceptance,authority_ref])
        with self.store.transaction() as c:
            replay=self._replay(c,request_id,fingerprint)
            if replay: return replay
            if c.execute('SELECT 1 FROM project WHERE project_id=?',(project_id,)).fetchone() is None:
                raise StateConflict('Project must be explicitly initialized first')
            if c.execute("SELECT 1 FROM host_dispatch WHERE project_id=? AND launch_committed=1 AND coalesce(quiesced,0)=0 LIMIT 1",(project_id,)).fetchone():
                raise StateConflict('Quiesce managed Hosts before revising Project definitions')
            current=c.execute('SELECT coalesce(max(revision),0) FROM project_revision WHERE project_id=?',(project_id,)).fetchone()[0]
            if current!=expected_revision: raise StateConflict('Project definition revision changed')
            if c.execute("SELECT 1 FROM phase WHERE project_id=? AND state='ACTIVE'",(project_id,)).fetchone():
                raise StateConflict('Pause and review active Phase before changing global acceptance')
            revision=current+1
            c.execute('INSERT INTO project_revision VALUES (?,?,?,?,?)',(project_id,revision,
                write_goal(c,goal,project_id,'project',project_id,revision),
                encode(acceptance,project_id,'project',project_id,revision,'acceptance'),authority_ref))
            c.execute("UPDATE project_completion SET valid=0,invalidation_ref='project-revised' WHERE project_id=? AND valid=1",(project_id,))
            return self._receipt(c,request_id,fingerprint,project_id,revision,'PROJECT_DEFINED')

    def define_phase(self, *, phase_id, project_id, project_revision, expected_revision, goal, boundary,
                     acceptance, plan_ref, plan_sha256, authority_ref, request_id, plan_scope='PROJECT'):
        for key,value in [('phase_id',phase_id),('project_id',project_id),('goal',goal),('plan_ref',plan_ref),('authority_ref',authority_ref),('request_id',request_id)]: _text(value,key)
        if (type(expected_revision) is not int or expected_revision<0 or type(project_revision) is not int or project_revision<1):
            raise ValueError('Invalid Phase or Project revision')
        if not isinstance(plan_sha256,str) or re.fullmatch('[a-fA-F0-9]{64}',plan_sha256) is None:
            raise ValueError('Phase plan requires SHA-256')
        if plan_scope not in {'PROJECT','STATE'}: raise ValueError('Phase plan scope must be PROJECT or STATE')
        boundary=phase_boundary(boundary)
        acceptance=criteria(acceptance)
        plan_sha256=plan_sha256.lower()
        fingerprint=request_fingerprint(self.store.connection,project_id,['phase',phase_id,project_id,project_revision,expected_revision,goal,boundary,acceptance,plan_ref,plan_sha256,authority_ref,plan_scope])
        with self.store.transaction() as c:
            replay=self._replay(c,request_id,fingerprint)
            if replay: return replay
            current_project=c.execute('SELECT coalesce(max(revision),0) FROM project_revision WHERE project_id=?',(project_id,)).fetchone()[0]
            if current_project!=project_revision: raise StateConflict('Phase must bind current Project definition')
            phase=c.execute('SELECT project_id,revision,state FROM phase WHERE phase_id=?',(phase_id,)).fetchone()
            if (phase[1] if phase else 0)!=expected_revision: raise StateConflict('Phase revision changed')
            if phase and (phase[0]!=project_id or phase[2] not in {'PLANNED','PAUSED'}):
                raise StateConflict('Pause Phase before revising its execution definition')
            if phase and phase[2]=='PAUSED':
                self.store.require_execution_ready()
                if c.execute('''SELECT 1 FROM host_dispatch h JOIN phase_task b ON b.task_id=h.task_id
                    WHERE b.phase_id=? AND h.launch_committed=1 AND coalesce(h.quiesced,0)=0 LIMIT 1''',(phase_id,)).fetchone():
                    raise StateConflict('Quiesce managed Hosts before revising Phase definitions')
                if c.execute('''SELECT 1 FROM phase_task b JOIN operation o ON o.task_id=b.task_id
                    WHERE b.phase_id=? AND o.state IN ('INTENT_RECORDED','UNKNOWN') LIMIT 1''',(phase_id,)).fetchone():
                    raise StateConflict('Reconcile pending Phase effects before revising its plan')
                if c.execute('''SELECT 1 FROM phase_task b JOIN execution_run r ON r.task_id=b.task_id
                    WHERE b.phase_id=? AND r.state IN ('OPEN','PAUSE_REQUESTED') LIMIT 1''',(phase_id,)).fetchone():
                    raise StateConflict('Pause owned Runs before revising Phase')
            revision=expected_revision+1
            if phase: c.execute('UPDATE phase SET revision=? WHERE phase_id=?',(revision,phase_id))
            else: c.execute("INSERT INTO phase VALUES (?,?,?,'PLANNED')",(phase_id,project_id,revision))
            c.execute('INSERT INTO phase_revision VALUES (?,?,?,?,?,?,?,?,?,?)',
                      (phase_id,revision,project_revision,
                       write_goal(c,goal,project_id,'phase',phase_id,revision),
                       encode(boundary,project_id,'phase',phase_id,revision,'boundary'),
                       encode(acceptance,project_id,'phase',phase_id,revision,'acceptance'),plan_ref,plan_sha256,authority_ref,plan_scope))
            c.execute("UPDATE project_completion SET valid=0,invalidation_ref='phase-revised' WHERE project_id=? AND valid=1",(project_id,))
            return self._receipt(c,request_id,fingerprint,phase_id,revision,'PHASE_DEFINED')
