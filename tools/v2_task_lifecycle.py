"""Task effect-recovery transitions; not native Host process control."""
import hashlib,json
from v2_state_store import StateConflict,_json,_text


def _audit(c,kind,task_id,details):
    c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',(kind,task_id,_json(details)))


def _pause_requested(c,task_id,revision):
    row=c.execute("SELECT sequence,details_json FROM execution_audit WHERE kind='TASK_PAUSE_REQUESTED' AND subject_id=? ORDER BY sequence DESC LIMIT 1",(task_id,)).fetchone()
    settled=c.execute("SELECT coalesce(max(sequence),0) FROM execution_audit WHERE kind='TASK_PAUSE_SETTLED' AND subject_id=?",(task_id,)).fetchone()[0]
    return row is not None and row[0]>settled and json.loads(row[1]).get('task_revision')==revision


def pending_hosts(c,task_id):
    return [row[0] for row in c.execute('''SELECT dispatch_id FROM host_dispatch
        WHERE task_id=? AND launch_committed=1 AND coalesce(quiesced,0)=0 ORDER BY dispatch_id''',(task_id,))]


def reconcile_effect_state(c,task_id,*,fact_ref):
    """Call in the transaction that records actual operation facts or restore.

    Never queries or stops a Host, clears an UNKNOWN, grants permission, or
    treats a cancellation as resolved effects. Fact references are identifiers.
    """
    if not c.in_transaction:raise RuntimeError('Effect state reconciliation requires a transaction')
    task=c.execute('SELECT revision,status FROM task WHERE task_id=?',(task_id,)).fetchone()
    if task is None:raise StateConflict('Unknown effect owner Task')
    revision,status=task
    marker=c.execute('SELECT task_revision,resume_status FROM task_effect_recovery WHERE task_id=?',(task_id,)).fetchone()
    if marker is not None and marker[0]!=revision:raise StateConflict('Effect recovery binds a different Task revision')
    unknown=c.execute("SELECT 1 FROM operation WHERE task_id=? AND state='UNKNOWN' LIMIT 1",(task_id,)).fetchone()
    unknown=unknown or c.execute("SELECT 1 FROM host_dispatch WHERE task_id=? AND state='UNKNOWN' LIMIT 1",(task_id,)).fetchone()
    if unknown:
        if status not in {'CANCELLED','FAILED','RECOVERY_REQUIRED'}:
            resume=status if status in {'READY','RUNNING','VERIFYING','WAITING','PAUSED'} else 'PAUSED'
            if marker is None:c.execute('INSERT INTO task_effect_recovery VALUES (?,?,?)',(task_id,revision,resume))
            c.execute("UPDATE task SET status='RECOVERY_REQUIRED' WHERE task_id=?",(task_id,))
            if status=='COMPLETED':
                c.execute("UPDATE acceptance SET valid=0,invalidation_ref='unknown-effect' WHERE task_id=? AND valid=1",(task_id,))
            _audit(c,'TASK_EFFECT_RECOVERY_REQUIRED',task_id,{'task_revision':revision,'prior_status':status,'fact_ref':fact_ref})
        return
    requested=[r[0] for r in c.execute("SELECT run_id FROM execution_run WHERE task_id=? AND state='PAUSE_REQUESTED'",(task_id,))]
    pause=_pause_requested(c,task_id,revision)
    if marker is not None:
        if status=='RECOVERY_REQUIRED':
            status='WAITING' if requested or pause else marker[1]
            c.execute('UPDATE task SET status=? WHERE task_id=?',(status,task_id))
        c.execute('DELETE FROM task_effect_recovery WHERE task_id=?',(task_id,))
        _audit(c,'TASK_EFFECT_RECOVERY_CLEARED',task_id,{'task_revision':revision,'resulting_status':status,
            'fact_ref':fact_ref,'host_quiescence_verified':False})
    if c.execute("SELECT 1 FROM operation WHERE task_id=? AND state IN ('INTENT_RECORDED','UNKNOWN') LIMIT 1",(task_id,)).fetchone():return
    if pending_hosts(c,task_id):return
    for run_id in requested:
        c.execute("UPDATE execution_run SET state='PAUSED' WHERE run_id=?",(run_id,))
        _audit(c,'RUN_PAUSED',run_id,{'settled_by_fact':fact_ref,'host_quiescence_verified':False})
    if status=='WAITING' and (requested or pause):
        c.execute("UPDATE task SET status='PAUSED' WHERE task_id=?",(task_id,))
        _audit(c,'TASK_PAUSE_SETTLED',task_id,{'task_revision':revision,'settled_by_fact':fact_ref})


def require_verification_ready(store,task_id,revision):
    """Registered controls only; does not claim all external writers are stopped."""
    store.require_execution_ready()
    from v2_governance import require_task_phase
    require_task_phase(store,task_id)
    task=store.task(task_id);c=store.connection
    if task is None or task['revision']!=revision or task['status'] not in {'RUNNING','VERIFYING'}:
        raise StateConflict('Verification requires current RUNNING or VERIFYING Task')
    if store.unresolved_dependencies(task_id,revision):raise StateConflict('Verification dependencies are not accepted')
    if c.execute("SELECT 1 FROM operation WHERE task_id=? AND state IN ('PREPARED','INTENT_RECORDED','UNKNOWN') LIMIT 1",(task_id,)).fetchone():
        raise StateConflict('Verification requires settled operations')
    if c.execute("SELECT 1 FROM host_dispatch WHERE task_id=? AND (state='PREPARED' OR (launch_committed=1 AND coalesce(quiesced,0)=0)) LIMIT 1",(task_id,)).fetchone():
        raise StateConflict('Verification requires resolved dispatches and observed managed Host quiescence')
    return task


def enter_verification(store,task_id,revision,*,review_ref):
    if not store.connection.in_transaction:raise RuntimeError('Verification transition requires a transaction')
    task=require_verification_ready(store,task_id,revision)
    if task['status']!='VERIFYING':
        store.connection.execute("UPDATE task SET status='VERIFYING' WHERE task_id=?",(task_id,))
        _audit(store.connection,'TASK_VERIFICATION_STARTED',task_id,{'task_revision':revision,'review_ref':review_ref,
            'scope':'REGISTERED_CONTROLS','external_writer_quiescence_implied':False})


class Verification:
    def __init__(self,store):self.store=store

    def begin(self,*,task_id,task_revision,request_id,review_ref):
        return self._transition(task_id,task_revision,request_id,review_ref,rework=False)

    def rework(self,*,task_id,task_revision,request_id,review_ref):
        return self._transition(task_id,task_revision,request_id,review_ref,rework=True)

    def _transition(self,task_id,revision,request_id,review_ref,*,rework):
        for name,value in (('task_id',task_id),('request_id',request_id),('review_ref',review_ref)):_text(value,name)
        if type(revision) is not int or revision<1:raise ValueError('Invalid Task revision')
        kind='TASK_VERIFICATION_REWORK' if rework else 'TASK_VERIFICATION_BEGIN'
        fingerprint=hashlib.sha256(_json([kind,task_id,revision,review_ref]).encode()).hexdigest()
        with self.store.transaction() as c:
            old=c.execute('SELECT request_hash,revision FROM request_receipt WHERE request_id=?',(request_id,)).fetchone()
            if old:
                if old!=(fingerprint,revision):raise StateConflict('Verification request identity conflict')
                return {'decision':'REPLAY','current_status':self.store.task(task_id)['status'],'task_accepted':False}
            if rework:
                task=require_verification_ready(self.store,task_id,revision)
                if task['status']!='VERIFYING':raise StateConflict('Rework requires active verification')
                # Resuming work ends the previous evidence basis; never silently reuse it.
                c.execute('''INSERT OR IGNORE INTO evidence_invalidation(evidence_id,reason,authority_ref)
                    SELECT evidence_id,'Verification returned to execution',? FROM evidence WHERE task_id=? AND task_revision=?''',
                    (review_ref,task_id,revision))
                c.execute("UPDATE task SET status='RUNNING' WHERE task_id=?",(task_id,))
            else:enter_verification(self.store,task_id,revision,review_ref=review_ref)
            c.execute('INSERT INTO request_receipt VALUES (?,?,?,?)',(request_id,fingerprint,task_id,revision))
            _audit(c,kind,task_id,{'task_revision':revision,'review_ref':review_ref,'request_id':request_id})
            return {'decision':'REWORK' if rework else 'VERIFYING','current_status':self.store.task(task_id)['status'],
                'task_accepted':False,'new_authority_granted':False}
