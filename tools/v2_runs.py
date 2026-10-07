"""Candidate explicit run/checkpoint recovery; records are not process-liveness proof."""
import json
from v2_state_store import StateStore, StateConflict, _text, _json
from v2_governance import require_task_phase
from v2_checkpoint_content import checkpoint_row
from v2_task_lifecycle import pending_hosts


class Runs:
    def __init__(self, store: StateStore):
        self.store = store

    @staticmethod
    def _pending(c, task_id):
        return [r[0] for r in c.execute("SELECT operation_id FROM operation WHERE task_id=? AND state IN ('INTENT_RECORDED','UNKNOWN') ORDER BY operation_id", (task_id,))]

    def open(self, *, run_id, task_id, task_revision, host, native_id, actor):
        for field,value in [('run_id',run_id),('task_id',task_id),('host',host),('native_id',native_id),('actor',actor)]:
            _text(value,field)
        if type(task_revision) is not int or task_revision<1:
            raise ValueError('Invalid task revision')
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            task=self.store.task(task_id)
            if task: require_task_phase(self.store,task_id)
            if not task or task['revision']!=task_revision or task['status'] not in {'READY','RUNNING'}:
                raise StateConflict('Run requires a current executable task')
            if self.store.unresolved_dependencies(task_id,task_revision):
                raise StateConflict('Dependencies are not accepted')
            from v2_artifacts import Artifacts
            if Artifacts(self.store).recovery_handoff(task_id=task_id,task_revision=task_revision)['decision']!='NONE':
                raise StateConflict('Required recovery references need an explicit paused successor handoff')
            values=(run_id,task_id,task_revision,host,native_id,actor)
            existing=c.execute('SELECT run_id,task_id,task_revision,host,native_id,actor,state FROM execution_run WHERE run_id=?',(run_id,)).fetchone()
            if existing:
                if existing[:6]!=values or existing[6]!='OPEN':
                    raise StateConflict('Run identity is immutable; use explicit resume')
                return 'REPLAY'
            c.execute("INSERT INTO execution_run VALUES (?,?,?,?,?,?,'OPEN',NULL)",values)
            c.execute("UPDATE task SET status='RUNNING' WHERE task_id=?",(task_id,))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',('RUN_OPENED',run_id,_json({'host':host,'native_id':native_id})))
            return 'OPEN'

    def pause(self, *, run_id, actor, checkpoint_id, summary, next_action):
        for field,value in [('checkpoint_id',checkpoint_id),('summary',summary),('next_action',next_action)]:
            _text(value,field)
        if len(summary)>4096 or len(next_action)>4096:
            raise ValueError('Checkpoint summary/action exceeds bounded size')
        with self.store.transaction() as c:
            run=c.execute('SELECT task_id,task_revision,actor,state,checkpoint_id FROM execution_run WHERE run_id=?',(run_id,)).fetchone()
            if run is None or run[2]!=actor or run[3]!='OPEN':
                raise StateConflict('Pause requires the owned open Run')
            task=self.store.task(run[0])
            if task['revision']!=run[1] or task['status'] not in {'RUNNING','VERIFYING','RECOVERY_REQUIRED'}:
                raise StateConflict('Task no longer matches Run')
            pending=self._pending(c,run[0])
            hosts=pending_hosts(c,run[0])
            waiting=bool(pending or hosts)
            state='PAUSE_REQUESTED' if waiting else 'PAUSED'
            c.execute('INSERT INTO checkpoint VALUES (?,?,?,?,?,?)',checkpoint_row(c,(checkpoint_id,run_id,run[1],summary,next_action,_json(pending)),protect=True))
            c.execute('UPDATE execution_run SET state=?,checkpoint_id=? WHERE run_id=?',(state,checkpoint_id,run_id))
            from v2_artifacts import Artifacts
            Artifacts(self.store).carry_recovery_binding(run_id=run_id,previous_checkpoint_id=run[4],checkpoint_id=checkpoint_id)
            c.execute('UPDATE task SET status=? WHERE task_id=?',
                ('RECOVERY_REQUIRED' if task['status']=='RECOVERY_REQUIRED' else 'WAITING' if waiting else 'PAUSED',run[0]))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                      ('RUN_PAUSE_REQUESTED' if waiting else 'RUN_PAUSED',run_id,_json({'checkpoint_id':checkpoint_id,'pending_operations':pending,'pending_hosts':hosts,
                        'resume_task_status':'VERIFYING' if task['status']=='VERIFYING' else 'RUNNING'})))
            return {'state':state,'pending_operations':pending,'pending_hosts':hosts,'registered_effects_settled':not waiting,'host_quiescence_verified':False}

    def rebuild_checkpoint(self, *, run_id, actor, expected_checkpoint_id, checkpoint_id, summary, next_action, review_ref):
        for field,value in [('checkpoint_id',checkpoint_id),('summary',summary),('next_action',next_action),('review_ref',review_ref)]:
            _text(value,field)
        if len(summary)>4096 or len(next_action)>4096:
            raise ValueError('Checkpoint summary/action exceeds bounded size')
        with self.store.transaction() as c:
            run=c.execute('SELECT task_id,task_revision,actor,state,checkpoint_id FROM execution_run WHERE run_id=?',(run_id,)).fetchone()
            if run is None or run[2]!=actor or run[3] not in {'PAUSED','PAUSE_REQUESTED'} or run[4]!=expected_checkpoint_id:
                raise StateConflict('Checkpoint replacement requires exact owned paused Run and prior checkpoint')
            task=self.store.task(run[0])
            allowed={'WAITING','RECOVERY_REQUIRED'} if run[3]=='PAUSE_REQUESTED' else {'PAUSED'}
            if task['revision']!=run[1] or task['status'] not in allowed:
                raise StateConflict('Run does not match current paused Task')
            pending=self._pending(c,run[0])
            c.execute('INSERT INTO checkpoint VALUES (?,?,?,?,?,?)',checkpoint_row(c,(checkpoint_id,run_id,run[1],summary,next_action,_json(pending)),protect=True))
            c.execute('UPDATE execution_run SET checkpoint_id=? WHERE run_id=?',(checkpoint_id,run_id))
            from v2_artifacts import Artifacts
            Artifacts(self.store).carry_recovery_binding(run_id=run_id,previous_checkpoint_id=expected_checkpoint_id,checkpoint_id=checkpoint_id)
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                      ('CHECKPOINT_REBUILT',run_id,_json({'previous':expected_checkpoint_id,'checkpoint_id':checkpoint_id,'review_ref':review_ref})))
            return {'state':run[3],'checkpoint_id':checkpoint_id,'pending_operations':pending,'execution_authorized':False}

    def resume(self, *, run_id, actor, checkpoint_id):
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            run=c.execute('SELECT task_id,task_revision,actor,state,checkpoint_id FROM execution_run WHERE run_id=?',(run_id,)).fetchone()
            if run is None or run[2]!=actor or run[3] not in {'PAUSED','PAUSE_REQUESTED'} or run[4]!=checkpoint_id:
                raise StateConflict('Resume requires the exact owned paused Run/checkpoint')
            task=self.store.task(run[0])
            withdrawing=run[3]=='PAUSE_REQUESTED'
            if task['revision']!=run[1] or task['status']!=('WAITING' if withdrawing else 'PAUSED'):
                raise StateConflict('Checkpoint no longer matches Task revision')
            managed=c.execute('''SELECT h.state,h.cancel_requested,h.quiesced,h.epoch,b.revoked,b.consumption_known,b.expires_at
                FROM host_dispatch h JOIN dispatch_budget b ON b.project_id=h.project_id WHERE h.run_id=?''',(run_id,)).fetchone()
            if withdrawing and managed is None:raise StateConflict('Pending pause requires effect reconciliation before resume')
            if managed:
                from v2_operations import Operations
                epoch=c.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]
                if (managed[0]!='RUNNING' or managed[1] or managed[2]!=0 or managed[3]!=epoch or managed[4] or not managed[5] or
                        (managed[6] is not None and Operations._instant(managed[6])<=Operations(self.store).clock())):
                    raise StateConflict('Managed Run is no longer admitted; reconcile or prepare a successor instead of reviving it')
            require_task_phase(self.store,run[0])
            if self._pending(c,run[0]) or self.store.unresolved_dependencies(run[0],run[1]):
                raise StateConflict('Reconcile pending effects/dependencies before resuming')
            checkpoint=checkpoint_row(c,c.execute('SELECT * FROM checkpoint WHERE checkpoint_id=? AND run_id=?',(checkpoint_id,run_id)).fetchone())
            from v2_artifacts import Artifacts
            recovery=Artifacts(self.store).verify_recovery_binding(run_id=run_id,checkpoint_id=checkpoint_id)
            if recovery['decision'] not in {'NOT_ENROLLED','BOUND_REFERENCES_CURRENT'}:
                raise StateConflict('Required recovery references need controller review before resume')
            c.execute("UPDATE execution_run SET state='OPEN' WHERE run_id=?",(run_id,))
            pause=c.execute("SELECT details_json FROM execution_audit WHERE kind IN ('RUN_PAUSED','RUN_PAUSE_REQUESTED') AND subject_id=? ORDER BY sequence DESC LIMIT 1",(run_id,)).fetchone()
            status='VERIFYING' if pause and json.loads(pause[0]).get('resume_task_status')=='VERIFYING' else 'RUNNING'
            c.execute('UPDATE task SET status=? WHERE task_id=?',(status,run[0]))
            if status=='VERIFYING':
                from v2_task_lifecycle import require_verification_ready
                require_verification_ready(self.store,run[0],run[1])
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',('RUN_RESUMED',run_id,_json({'checkpoint_id':checkpoint_id,'pause_request_withdrawn':withdrawing})))
            return {'state':'OPEN','summary':checkpoint[3],'next_action':checkpoint[4],
                    'checkpoint_pending_operations':json.loads(checkpoint[5]),'pause_request_withdrawn':withdrawing,'host_liveness_verified':False}
