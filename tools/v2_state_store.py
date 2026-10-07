"""Candidate v2 Task persistence. Not wired to installed workspace authority yet."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any
from v2_contracts import criteria

SCHEMA_VERSION = 69
APPLICATION_ID = 0x4D414C54
DDL = """
BEGIN IMMEDIATE;
CREATE TABLE recovery_state(singleton INTEGER PRIMARY KEY CHECK(singleton=1), epoch TEXT NOT NULL,
    reconciliation_required INTEGER NOT NULL CHECK(reconciliation_required IN (0,1)), source_backup_hash TEXT);
CREATE TABLE migration_barrier(singleton INTEGER PRIMARY KEY CHECK(singleton=1), pending_domains_json TEXT NOT NULL);
CREATE TABLE recovery_review(review_id TEXT PRIMARY KEY NOT NULL, epoch TEXT NOT NULL UNIQUE,
    plan_sha256 TEXT NOT NULL, request_sha256 TEXT NOT NULL, report_json TEXT NOT NULL, receipt_json TEXT NOT NULL);
CREATE TABLE project(project_id TEXT PRIMARY KEY NOT NULL, original_goal TEXT NOT NULL, resource_root TEXT NOT NULL);
CREATE TABLE artifact_definition(project_id TEXT NOT NULL REFERENCES project,
    artifact_id TEXT NOT NULL, phase_id TEXT NOT NULL REFERENCES phase,
    phase_revision INTEGER NOT NULL, primary_role TEXT NOT NULL,
    protected_definition TEXT NOT NULL, request_id TEXT NOT NULL UNIQUE, request_hash TEXT NOT NULL,
    disposition TEXT NOT NULL CHECK(disposition IN ('UNRESOLVED','KEEP_OWNED','PROMOTE_SHARED','ARCHIVE')),
    local_id TEXT NOT NULL,
    PRIMARY KEY(project_id,artifact_id), UNIQUE(project_id,phase_id,local_id));
CREATE INDEX artifact_local_lookup ON artifact_definition(project_id,local_id);
CREATE TABLE artifact_shared(project_id TEXT NOT NULL REFERENCES project, shared_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL, purpose_scope_hash TEXT NOT NULL, protected_purpose_scope TEXT NOT NULL,
    task_id TEXT NOT NULL REFERENCES task, acceptance_id TEXT NOT NULL REFERENCES acceptance,
    evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id), operation_id TEXT NOT NULL REFERENCES operation,
    state TEXT NOT NULL CHECK(state IN ('CURRENT','SUPERSEDED','RETIRED')), request_id TEXT NOT NULL UNIQUE,
    request_hash TEXT NOT NULL, PRIMARY KEY(project_id,shared_id),
    FOREIGN KEY(project_id,artifact_id) REFERENCES artifact_definition(project_id,artifact_id));
CREATE UNIQUE INDEX artifact_shared_current ON artifact_shared(project_id,purpose_scope_hash) WHERE state='CURRENT';
CREATE TABLE artifact_relation_index(project_id TEXT NOT NULL, source_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL, kind TEXT NOT NULL, target_id TEXT NOT NULL, target_phase TEXT NOT NULL,
    PRIMARY KEY(project_id,source_id,ordinal),
    FOREIGN KEY(project_id,source_id) REFERENCES artifact_definition(project_id,artifact_id));
CREATE INDEX artifact_relation_incoming ON artifact_relation_index(project_id,target_id,kind,source_id);
CREATE TABLE artifact_archive(project_id TEXT NOT NULL, artifact_id TEXT NOT NULL,
    review_sequence INTEGER NOT NULL REFERENCES execution_audit(sequence), archived_at TEXT NOT NULL,
    PRIMARY KEY(project_id,artifact_id),
    FOREIGN KEY(project_id,artifact_id) REFERENCES artifact_definition(project_id,artifact_id));
CREATE TABLE definition_key(project_id TEXT PRIMARY KEY REFERENCES project, key_material TEXT NOT NULL);
CREATE TABLE handoff_note(note_id TEXT PRIMARY KEY NOT NULL,
    project_id TEXT NOT NULL REFERENCES project, task_id TEXT NOT NULL REFERENCES task,
    task_revision INTEGER NOT NULL CHECK(task_revision>=1), protected_content TEXT NOT NULL,
    request_hash TEXT NOT NULL);
CREATE INDEX handoff_note_task ON handoff_note(task_id,task_revision,note_id);
CREATE TABLE definition_preview(project_id TEXT NOT NULL REFERENCES project DEFERRABLE INITIALLY DEFERRED,
    entity_kind TEXT NOT NULL CHECK(entity_kind IN ('project-original','project','phase','task')),
    entity_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>=0),
    body_sha256 TEXT NOT NULL, protected_preview TEXT NOT NULL CHECK(length(protected_preview)<=32768),
    PRIMARY KEY(project_id,entity_kind,entity_id,revision));
CREATE TABLE migration_review(review_id TEXT PRIMARY KEY NOT NULL, project_id TEXT NOT NULL REFERENCES project,
    epoch TEXT NOT NULL, inventory_sha256 TEXT NOT NULL, mapping_sha256 TEXT NOT NULL,
    request_sha256 TEXT NOT NULL, plan_sha256 TEXT NOT NULL, report_json TEXT NOT NULL, receipt_json TEXT NOT NULL);
CREATE TABLE migration_adoption(adoption_id TEXT PRIMARY KEY NOT NULL, project_id TEXT NOT NULL REFERENCES project,
    state TEXT NOT NULL CHECK(state IN ('PREPARED','ACTIVE','ROLLBACK_PENDING','ROLLED_BACK','SUPERSEDED')), old_epoch TEXT NOT NULL,
    new_epoch TEXT NOT NULL UNIQUE, plan_sha256 TEXT NOT NULL, plan_json TEXT NOT NULL, receipt_json TEXT);
CREATE TABLE legacy_control_source(project_id TEXT NOT NULL REFERENCES project, role TEXT NOT NULL,
    source_id TEXT NOT NULL, source_path TEXT NOT NULL, source_sha256 TEXT NOT NULL,
    declared_status_json TEXT NOT NULL, evidence_state TEXT NOT NULL CHECK(evidence_state='HISTORICAL_DECLARATION_ONLY'),
    PRIMARY KEY(project_id,role,source_id));
CREATE TABLE legacy_checkpoint(project_id TEXT NOT NULL REFERENCES project, session_id TEXT NOT NULL,
    origin_phase_id TEXT, summary TEXT NOT NULL, next_action TEXT NOT NULL,
    source_path TEXT NOT NULL, source_sha256 TEXT NOT NULL, PRIMARY KEY(project_id,session_id));
CREATE TABLE legacy_artifact_source(project_id TEXT NOT NULL REFERENCES project,
    source_role TEXT NOT NULL, source_id TEXT NOT NULL, row_number INTEGER NOT NULL CHECK(row_number>0),
    artifact_ref TEXT NOT NULL, fields_json TEXT NOT NULL, identity_valid INTEGER NOT NULL CHECK(identity_valid IN (0,1)),
    source_path TEXT NOT NULL, source_sha256 TEXT NOT NULL,
    evidence_state TEXT NOT NULL CHECK(evidence_state='HISTORICAL_DECLARATION_ONLY'),
    PRIMARY KEY(project_id,source_role,source_id,row_number));
CREATE TABLE project_revision(project_id TEXT NOT NULL REFERENCES project, revision INTEGER NOT NULL CHECK(revision>0),
    goal TEXT NOT NULL, acceptance_json TEXT NOT NULL, authority_ref TEXT NOT NULL,
    PRIMARY KEY(project_id,revision));
CREATE TABLE phase(phase_id TEXT PRIMARY KEY NOT NULL, project_id TEXT NOT NULL REFERENCES project,
    revision INTEGER NOT NULL CHECK(revision>0), state TEXT NOT NULL CHECK(state IN ('PLANNED','ACTIVE','PAUSED','COMPLETED','CANCELLED')));
CREATE TABLE phase_revision(phase_id TEXT NOT NULL REFERENCES phase, revision INTEGER NOT NULL CHECK(revision>0),
    project_revision INTEGER NOT NULL, goal TEXT NOT NULL, boundary_json TEXT NOT NULL,
    acceptance_json TEXT NOT NULL, plan_ref TEXT NOT NULL, plan_sha256 TEXT NOT NULL, authority_ref TEXT NOT NULL,
    plan_scope TEXT NOT NULL CHECK(plan_scope IN ('PROJECT','STATE')),
    PRIMARY KEY(phase_id,revision));
CREATE TABLE governance_receipt(request_id TEXT PRIMARY KEY NOT NULL, request_hash TEXT NOT NULL,
    entity_id TEXT NOT NULL, revision INTEGER NOT NULL);
CREATE UNIQUE INDEX one_active_phase ON phase(project_id) WHERE state='ACTIVE';
CREATE TABLE task(task_id TEXT PRIMARY KEY NOT NULL, project_id TEXT NOT NULL REFERENCES project,
    revision INTEGER NOT NULL CHECK(revision>0), status TEXT NOT NULL CHECK(status IN
    ('READY','RUNNING','VERIFYING','WAITING','PAUSED','RECOVERY_REQUIRED','COMPLETED','FAILED','CANCELLED')));
CREATE INDEX active_tasks_by_project ON task(project_id,task_id) WHERE status NOT IN ('COMPLETED','CANCELLED');
CREATE TABLE task_revision(task_id TEXT NOT NULL REFERENCES task, revision INTEGER NOT NULL,
    goal TEXT NOT NULL, scope_json TEXT NOT NULL, acceptance_json TEXT NOT NULL,
    PRIMARY KEY(task_id,revision));
CREATE TABLE task_effect_recovery(task_id TEXT PRIMARY KEY REFERENCES task, task_revision INTEGER NOT NULL,
    resume_status TEXT NOT NULL CHECK(resume_status IN ('READY','RUNNING','VERIFYING','WAITING','PAUSED')),
    FOREIGN KEY(task_id,task_revision) REFERENCES task_revision(task_id,revision));
CREATE TABLE dispatch_budget(project_id TEXT PRIMARY KEY REFERENCES project,
    max_launch_intents INTEGER NOT NULL CHECK(max_launch_intents>0), max_delegated_agents INTEGER NOT NULL CHECK(max_delegated_agents>0),
    host_limits_json TEXT NOT NULL, max_queries INTEGER NOT NULL CHECK(max_queries>0),
    max_cancels INTEGER NOT NULL CHECK(max_cancels>0), expires_at TEXT, authority_ref TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1)), revocation_ref TEXT,
    revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), carried_launches INTEGER NOT NULL DEFAULT 0 CHECK(carried_launches>=0),
    consumption_known INTEGER NOT NULL DEFAULT 1 CHECK(consumption_known IN (0,1)),
    consumption_basis TEXT NOT NULL DEFAULT 'RETAINED_LEDGER' CHECK(consumption_basis IN ('RETAINED_LEDGER','CONTROLLER_ATTESTED','UNKNOWN_AFTER_RESTORE')));
CREATE TABLE dispatch_budget_change(request_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES dispatch_budget,
    request_hash TEXT NOT NULL, receipt_json TEXT NOT NULL);
CREATE TABLE dispatch_recovery_calls(project_id TEXT NOT NULL REFERENCES dispatch_budget, epoch TEXT NOT NULL,
    query_limit INTEGER NOT NULL CHECK(query_limit>=0), cancel_limit INTEGER NOT NULL CHECK(cancel_limit>=0),
    authority_ref TEXT NOT NULL, PRIMARY KEY(project_id,epoch));
CREATE TABLE execution_attempt(attempt_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, task_revision INTEGER NOT NULL,
    strategy_hash TEXT NOT NULL, strategy_value TEXT NOT NULL,
    FOREIGN KEY(task_id,task_revision) REFERENCES task_revision(task_id,revision));
CREATE TABLE host_dispatch(dispatch_id TEXT PRIMARY KEY, backend_key TEXT NOT NULL UNIQUE,
    attempt_id TEXT NOT NULL REFERENCES execution_attempt, task_id TEXT NOT NULL, task_revision INTEGER NOT NULL,
    project_id TEXT NOT NULL REFERENCES dispatch_budget, host_id TEXT NOT NULL, profile_revision TEXT NOT NULL, quiescence_scope TEXT NOT NULL,
    actor TEXT NOT NULL UNIQUE, epoch TEXT NOT NULL, authority_ref TEXT NOT NULL, policy_revision INTEGER NOT NULL, context_hash TEXT NOT NULL,
    request_hash TEXT NOT NULL, request_value TEXT NOT NULL, run_id TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL CHECK(state IN ('PREPARED','INTENT_COMMITTED','RUNNING','CANCEL_REQUESTED','UNKNOWN','EXITED','CANCELLED')),
    launch_committed INTEGER NOT NULL DEFAULT 0 CHECK(launch_committed IN (0,1)),
    cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0,1)),
    quiesced INTEGER CHECK(quiesced IN (0,1)), native_value TEXT, last_receipt_value TEXT,
    carried_queries INTEGER NOT NULL DEFAULT 0 CHECK(carried_queries>=0), carried_cancels INTEGER NOT NULL DEFAULT 0 CHECK(carried_cancels>=0),
    FOREIGN KEY(task_id,task_revision) REFERENCES task_revision(task_id,revision));
CREATE INDEX active_host_dispatch ON host_dispatch(project_id,host_id,task_id) WHERE launch_committed=1 AND coalesce(quiesced,0)=0;
CREATE INDEX uncertain_host_dispatch ON host_dispatch(task_id) WHERE state='UNKNOWN';
CREATE TABLE host_invocation(invocation_id TEXT PRIMARY KEY, dispatch_id TEXT NOT NULL REFERENCES host_dispatch, epoch TEXT NOT NULL,
    method TEXT NOT NULL CHECK(method IN ('LAUNCH','QUERY','CANCEL')),
    state TEXT NOT NULL CHECK(state IN ('INTENT_COMMITTED','OBSERVED','UNKNOWN')),
    response_hash TEXT, response_value TEXT, physical_requests INTEGER CHECK(physical_requests>=0));
CREATE TABLE task_budget(task_id TEXT PRIMARY KEY REFERENCES task, max_operations INTEGER NOT NULL CHECK(max_operations>=0),
    authority_ref TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0));
CREATE TABLE project_budget(project_id TEXT PRIMARY KEY REFERENCES project, max_operations INTEGER NOT NULL CHECK(max_operations>=0),
    authority_ref TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0));
CREATE TABLE phase_task(task_id TEXT NOT NULL, task_revision INTEGER NOT NULL, phase_id TEXT NOT NULL,
    phase_revision INTEGER NOT NULL, authority_ref TEXT NOT NULL, PRIMARY KEY(task_id,task_revision),
    FOREIGN KEY(task_id,task_revision) REFERENCES task_revision(task_id,revision),
    FOREIGN KEY(phase_id,phase_revision) REFERENCES phase_revision(phase_id,revision));
CREATE TABLE phase_carryover(carry_id TEXT PRIMARY KEY NOT NULL, task_id TEXT NOT NULL,
    source_task_revision INTEGER NOT NULL, source_phase_id TEXT NOT NULL, source_phase_revision INTEGER NOT NULL,
    target_task_revision INTEGER NOT NULL, target_phase_id TEXT NOT NULL, target_phase_revision INTEGER NOT NULL,
    authority_ref TEXT NOT NULL, reason TEXT NOT NULL, request_hash TEXT NOT NULL,
    UNIQUE(task_id,source_phase_id,source_phase_revision),
    FOREIGN KEY(task_id,target_task_revision) REFERENCES phase_task(task_id,task_revision));
CREATE TABLE request_receipt(request_id TEXT PRIMARY KEY NOT NULL, request_hash TEXT NOT NULL,
    task_id TEXT NOT NULL, revision INTEGER NOT NULL,
    FOREIGN KEY(task_id,revision) REFERENCES task_revision(task_id,revision));
CREATE TABLE audit(sequence INTEGER PRIMARY KEY, request_id TEXT NOT NULL UNIQUE REFERENCES request_receipt,
    kind TEXT NOT NULL, task_id TEXT NOT NULL, revision INTEGER NOT NULL,
    FOREIGN KEY(task_id,revision) REFERENCES task_revision(task_id,revision));
CREATE TABLE execution_grant(grant_id TEXT PRIMARY KEY NOT NULL, task_id TEXT NOT NULL,
    task_revision INTEGER NOT NULL, actor TEXT NOT NULL, source_ref TEXT NOT NULL,
    resource TEXT NOT NULL, effect TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1)),
    expires_at TEXT, max_operations INTEGER CHECK(max_operations IS NULL OR max_operations>=0),
    FOREIGN KEY(task_id,task_revision) REFERENCES task_revision(task_id,revision));
CREATE TABLE operation(operation_id TEXT PRIMARY KEY NOT NULL, grant_id TEXT NOT NULL REFERENCES execution_grant,
    task_id TEXT NOT NULL, task_revision INTEGER NOT NULL, request_hash TEXT NOT NULL,
    request_json TEXT NOT NULL,
    resource_json TEXT,
    execution_epoch TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('PREPARED','INTENT_RECORDED','OBSERVED','UNKNOWN','FAILED','CANCELLED','ACCEPTED')),
    FOREIGN KEY(task_id,task_revision) REFERENCES task_revision(task_id,revision));
CREATE TABLE operation_observation(observation_id TEXT PRIMARY KEY NOT NULL,
    operation_id TEXT NOT NULL REFERENCES operation, outcome TEXT NOT NULL,
    evidence_ref TEXT NOT NULL, observation_hash TEXT NOT NULL);
CREATE TABLE operation_lease(operation_id TEXT PRIMARY KEY REFERENCES operation,
    epoch TEXT NOT NULL, fence INTEGER NOT NULL CHECK(fence>0), actor TEXT NOT NULL,
    expires_at TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('HELD','QUARANTINED','RELEASED')),
    UNIQUE(epoch,fence));
CREATE INDEX current_operation_by_task ON operation(task_id,operation_id)
    WHERE state IN ('PREPARED','INTENT_RECORDED','UNKNOWN','OBSERVED');
CREATE INDEX unresolved_operation_by_task ON operation(task_id) WHERE state IN ('INTENT_RECORDED','UNKNOWN');
CREATE INDEX unknown_operation_by_task ON operation(task_id,operation_id) WHERE state='UNKNOWN';
CREATE TABLE execution_audit(sequence INTEGER PRIMARY KEY, kind TEXT NOT NULL, subject_id TEXT NOT NULL,
    details_json TEXT NOT NULL);
CREATE INDEX execution_audit_by_kind_subject ON execution_audit(kind,subject_id,sequence);
CREATE TABLE evidence(sequence INTEGER PRIMARY KEY, evidence_id TEXT NOT NULL UNIQUE,
    task_id TEXT NOT NULL, task_revision INTEGER NOT NULL, operation_id TEXT NOT NULL REFERENCES operation,
    criterion TEXT NOT NULL, result TEXT NOT NULL CHECK(result IN ('PASS','FAIL')),
    blob_hash TEXT NOT NULL, verifier_ref TEXT NOT NULL, method TEXT NOT NULL,
    evidence_level TEXT NOT NULL CHECK(evidence_level IN ('A','B','C','D')),
    FOREIGN KEY(task_id,task_revision) REFERENCES task_revision(task_id,revision));
CREATE INDEX evidence_current ON evidence(task_id,task_revision,criterion,sequence);
CREATE TABLE evidence_policy(evidence_id TEXT PRIMARY KEY REFERENCES evidence(evidence_id),
    descriptor_json TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1)),
    revocation_ref TEXT);
CREATE TABLE evidence_derivation(evidence_id TEXT PRIMARY KEY REFERENCES evidence(evidence_id),
    authority_ref TEXT NOT NULL, review_ref TEXT NOT NULL);
CREATE TABLE evidence_derivation_source(evidence_id TEXT NOT NULL REFERENCES evidence_derivation,
    source_id TEXT NOT NULL REFERENCES evidence(evidence_id), source_blob_hash TEXT NOT NULL,
    source_binding_sha256 TEXT NOT NULL, PRIMARY KEY(evidence_id,source_id), CHECK(evidence_id<>source_id));
CREATE INDEX evidence_derived_from ON evidence_derivation_source(source_id,evidence_id);
CREATE TABLE growth_candidate(candidate_id TEXT PRIMARY KEY NOT NULL, owner TEXT NOT NULL REFERENCES project,
    proposal_evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id), request_hash TEXT NOT NULL,
    authority_ref TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN
    ('CANDIDATE','PROJECT_EXPERIMENTAL','FUTURE_USE_VALIDATING','VALIDATED','CHALLENGED','SUSPENDED','DEPRECATED','REMOVED','REJECTED')));
CREATE INDEX growth_by_owner ON growth_candidate(owner,candidate_id);
CREATE TABLE growth_source(candidate_id TEXT NOT NULL REFERENCES growth_candidate,
    evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id), PRIMARY KEY(candidate_id,evidence_id));
CREATE TABLE growth_trial(trial_id TEXT PRIMARY KEY NOT NULL, candidate_id TEXT NOT NULL REFERENCES growth_candidate,
    operation_id TEXT NOT NULL UNIQUE REFERENCES operation, request_hash TEXT NOT NULL,
    actor TEXT NOT NULL, authority_ref TEXT NOT NULL, rollback_ref TEXT NOT NULL,
    context_json TEXT NOT NULL, trial_hash TEXT NOT NULL);
CREATE TABLE growth_outcome(outcome_id TEXT PRIMARY KEY NOT NULL, trial_id TEXT NOT NULL REFERENCES growth_trial,
    evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id), outcome TEXT NOT NULL
    CHECK(outcome IN ('helped','neutral','harmful','inconclusive')), severity TEXT NOT NULL,
    independence_key TEXT NOT NULL, reviewer_ref TEXT NOT NULL, request_hash TEXT NOT NULL);
CREATE TABLE growth_lifecycle(review_id TEXT PRIMARY KEY NOT NULL, candidate_id TEXT NOT NULL REFERENCES growth_candidate,
    prior_state TEXT NOT NULL, new_state TEXT NOT NULL, review_evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id),
    authority_ref TEXT NOT NULL, successor_id TEXT REFERENCES growth_candidate, request_hash TEXT NOT NULL);
CREATE UNIQUE INDEX one_growth_successor ON growth_lifecycle(candidate_id) WHERE successor_id IS NOT NULL;
CREATE TABLE acceptance(acceptance_id TEXT PRIMARY KEY NOT NULL, task_id TEXT NOT NULL,
    task_revision INTEGER NOT NULL, request_hash TEXT NOT NULL, evidence_ids_json TEXT NOT NULL,
    authority_ref TEXT NOT NULL, valid INTEGER NOT NULL DEFAULT 1 CHECK(valid IN (0,1)), invalidation_ref TEXT,
    FOREIGN KEY(task_id,task_revision) REFERENCES task_revision(task_id,revision));
CREATE UNIQUE INDEX current_acceptance ON acceptance(task_id,task_revision) WHERE valid=1;
CREATE TABLE evidence_invalidation(evidence_id TEXT PRIMARY KEY REFERENCES evidence(evidence_id),
    reason TEXT NOT NULL, authority_ref TEXT NOT NULL);
CREATE TABLE phase_completion(completion_id TEXT PRIMARY KEY NOT NULL, phase_id TEXT NOT NULL,
    phase_revision INTEGER NOT NULL, request_hash TEXT NOT NULL, criteria_json TEXT NOT NULL,
    authority_ref TEXT NOT NULL, valid INTEGER NOT NULL CHECK(valid IN (0,1)), invalidation_ref TEXT,
    FOREIGN KEY(phase_id,phase_revision) REFERENCES phase_revision(phase_id,revision));
CREATE UNIQUE INDEX valid_phase_completion ON phase_completion(phase_id,phase_revision) WHERE valid=1;
CREATE TABLE phase_completion_task(completion_id TEXT NOT NULL REFERENCES phase_completion,
    task_id TEXT NOT NULL, task_revision INTEGER NOT NULL, acceptance_id TEXT NOT NULL REFERENCES acceptance,
    PRIMARY KEY(completion_id,task_id));
CREATE TABLE project_completion(completion_id TEXT PRIMARY KEY NOT NULL, project_id TEXT NOT NULL,
    project_revision INTEGER NOT NULL, request_hash TEXT NOT NULL, criteria_json TEXT NOT NULL,
    authority_ref TEXT NOT NULL, valid INTEGER NOT NULL CHECK(valid IN (0,1)), invalidation_ref TEXT,
    FOREIGN KEY(project_id,project_revision) REFERENCES project_revision(project_id,revision));
CREATE UNIQUE INDEX valid_project_completion ON project_completion(project_id,project_revision) WHERE valid=1;
CREATE TABLE project_completion_phase(completion_id TEXT NOT NULL REFERENCES project_completion,
    phase_completion_id TEXT NOT NULL REFERENCES phase_completion, PRIMARY KEY(completion_id,phase_completion_id));
CREATE TABLE dependency(task_id TEXT NOT NULL, task_revision INTEGER NOT NULL,
    predecessor_id TEXT NOT NULL, predecessor_revision INTEGER NOT NULL,
    PRIMARY KEY(task_id,task_revision,predecessor_id), CHECK(task_id<>predecessor_id),
    FOREIGN KEY(task_id,task_revision) REFERENCES task_revision(task_id,revision),
    FOREIGN KEY(predecessor_id,predecessor_revision) REFERENCES task_revision(task_id,revision));
CREATE TABLE execution_run(run_id TEXT PRIMARY KEY NOT NULL, task_id TEXT NOT NULL,
    task_revision INTEGER NOT NULL, host TEXT NOT NULL, native_id TEXT NOT NULL, actor TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('OPEN','PAUSE_REQUESTED','PAUSED','CLOSED')), checkpoint_id TEXT,
    FOREIGN KEY(task_id,task_revision) REFERENCES task_revision(task_id,revision));
CREATE UNIQUE INDEX one_current_run ON execution_run(task_id) WHERE state IN ('OPEN','PAUSE_REQUESTED','PAUSED');
CREATE TABLE checkpoint(checkpoint_id TEXT PRIMARY KEY NOT NULL, run_id TEXT NOT NULL REFERENCES execution_run,
    task_revision INTEGER NOT NULL, summary TEXT NOT NULL, next_action TEXT NOT NULL,
    pending_operations_json TEXT NOT NULL);
COMMIT;
"""


class StateConflict(ValueError):
    """Caller must re-evaluate a stale revision or conflicting request identity."""


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be nonempty text')


class StateStore:
    def __init__(self, path: Path, *, readonly: bool = False, transaction_guard=None):
        if transaction_guard is not None and not callable(transaction_guard):raise TypeError('Trusted transaction guard must be callable')
        self.transaction_guard=transaction_guard
        self.path = Path(path)
        for part in (self.path, *self.path.parents):
            if part.is_symlink() or (part.exists() and getattr(part.lstat(), 'st_file_attributes', 0) & 0x400):
                raise ValueError('State store paths cannot traverse reparse points')
        self.readonly = readonly
        self.connection = sqlite3.connect(self.path.resolve().as_uri() + ('?mode=ro' if readonly else '?mode=rw'),
                                          uri=True, isolation_level=None, timeout=2)
        try:
            c = self.connection
            if c.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID:
                raise ValueError('Not a MALTS v2 state database')
            if c.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION:
                raise ValueError('Unsupported state schema; explicit migration required')
            if c.execute('PRAGMA journal_mode').fetchone()[0] != 'delete':
                raise ValueError('This candidate supports DELETE journal only')
            c.execute('PRAGMA foreign_keys=ON')
            c.execute('PRAGMA synchronous=FULL')
            if readonly:
                c.execute('PRAGMA query_only=ON')
        except BaseException:
            c.close()
            raise

    @classmethod
    def initialize(cls, path: Path, project_id: str, original_goal: str, *, resource_root: Path | None = None) -> StateStore:
        _text(project_id, 'project_id')
        _text(original_goal, 'original_goal')
        path = Path(path)
        for parent in path.parents:
            if parent.is_symlink() or (parent.exists() and getattr(parent.lstat(), 'st_file_attributes', 0) & 0x400):
                raise ValueError('State store parents cannot traverse reparse points')
        with path.open('xb'):
            pass
        # Initialization failures leave a non-qualified file, never overwrite or
        # delete an existing database. Opening it fails the identity/version gate.
        with closing(sqlite3.connect(path, isolation_level=None)) as c:
            c.execute('PRAGMA foreign_keys=ON')
            c.execute('PRAGMA synchronous=FULL')
            c.executescript(DDL)
            c.execute('BEGIN IMMEDIATE')
            from v2_definition_content import write_goal,initialize_key
            c.execute('INSERT INTO project VALUES (?,?,?)', (project_id, write_goal(c,original_goal,project_id,'project-original',project_id,0), str(Path(resource_root or path.parent).resolve())))
            initialize_key(c,project_id)
            c.execute('INSERT INTO recovery_state VALUES (1,?,0,NULL)', (str(uuid.uuid4()),))
            c.execute(f'PRAGMA application_id={APPLICATION_ID}')
            c.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
            c.execute('COMMIT')
        return cls(path)

    def close(self) -> None:
        self.connection.close()

    def require_execution_ready(self):
        if self.pending_migration_domains():
            raise StateConflict('Semantic migration is incomplete; execution remains disabled')
        row = self.connection.execute('SELECT reconciliation_required FROM recovery_state WHERE singleton=1').fetchone()
        if row is None or row[0]:
            raise StateConflict('Restored state requires external-effect reconciliation before execution')
        if self.connection.execute('SELECT 1 FROM legacy_control_source LIMIT 1').fetchone():
            from v2_adoption import require_active_binding
            require_active_binding(self)

    def pending_migration_domains(self):
        row=self.connection.execute('SELECT pending_domains_json FROM migration_barrier WHERE singleton=1').fetchone()
        if row is None:
            if self.connection.execute('SELECT 1 FROM legacy_control_source LIMIT 1').fetchone():
                raise StateConflict('Imported state has lost its migration barrier; review is required')
            return []
        try: domains=json.loads(row[0])
        except (ValueError,TypeError): raise StateConflict('Invalid migration barrier data') from None
        if (not isinstance(domains,list) or any(not isinstance(v,str) or v not in {'Task','Session','Growth','Artifact'} for v in domains)
                or len(set(domains))!=len(domains)):
            raise StateConflict('Invalid migration barrier domains')
        if not domains and self.connection.execute('SELECT 1 FROM legacy_control_source LIMIT 1').fetchone():
            epoch=self.connection.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()
            adopted=self.connection.execute("SELECT 1 FROM migration_adoption WHERE state='ACTIVE' AND new_epoch=?",(epoch[0],)).fetchone() if epoch else None
            if not adopted: raise StateConflict('Imported state has no current adoption receipt; an empty barrier is not sufficient')
        return domains

    @contextmanager
    def transaction(self):
        if self.readonly:
            raise PermissionError('Read-only store')
        c = self.connection
        c.execute('BEGIN IMMEDIATE')
        try:
            if self.transaction_guard is not None:self.transaction_guard(self)
            yield c
            c.execute('COMMIT')
        except BaseException:
            if c.in_transaction:
                c.execute('ROLLBACK')
            raise

    @staticmethod
    def definition_value(value,owner,kind,identity,revision,field):
        from v2_definition_content import decode
        return decode(value,owner,kind,identity,revision,field)

    def task(self, task_id: str) -> dict[str, Any] | None:
        row = self.connection.execute('''SELECT t.task_id,t.project_id,t.revision,t.status,r.goal,r.scope_json,r.acceptance_json,
            EXISTS(SELECT 1 FROM acceptance a WHERE a.task_id=t.task_id AND a.task_revision=t.revision AND a.valid=1)
            FROM task t JOIN task_revision r ON t.task_id=r.task_id AND t.revision=r.revision WHERE t.task_id=?''', (task_id,)).fetchone()
        if row is None:
            return None
        return {'task_id': row[0], 'project_id': row[1], 'revision': row[2], 'status': row[3],
                'goal': self.definition_value(row[4],row[1],'task',row[0],row[2],'goal'),
                'scope': self.definition_value(row[5],row[1],'task',row[0],row[2],'scope'),
                'acceptance': self.definition_value(row[6],row[1],'task',row[0],row[2],'acceptance'),
                'acceptance_valid': bool(row[7])}

    def task_identity(self, task_id):
        row=self.connection.execute('SELECT task_id,project_id,revision,status FROM task WHERE task_id=?',(task_id,)).fetchone()
        return None if row is None else dict(zip(('task_id','project_id','revision','status'),row))

    def current_context(self, task_id, *, limit=20, cursor=None):
        """Bounded current recovery view. This view is never execution authority."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Context limit must be between 1 and 100')
        c=self.connection
        owns_transaction=not c.in_transaction
        if owns_transaction: c.execute('BEGIN')
        try:
            task=c.execute('''SELECT t.task_id,t.project_id,t.revision,t.status,
                NULL,0,
                EXISTS(SELECT 1 FROM acceptance a WHERE a.task_id=t.task_id AND a.task_revision=t.revision AND a.valid=1)
                FROM task t JOIN task_revision r
                ON t.task_id=r.task_id AND t.revision=r.revision WHERE t.task_id=?''',(task_id,)).fetchone()
            if task is None:
                raise StateConflict('Unknown task')
            from v2_definition_content import read_preview
            preview=read_preview(c,task[1],'task',task[0],task[2])
            task=(*task[:4],preview['text'],preview['characters'],task[6])
            epoch,quarantined=c.execute('SELECT epoch,reconciliation_required FROM recovery_state WHERE singleton=1').fetchone()
            watermark=c.execute('SELECT coalesce(max(sequence),0) FROM execution_audit').fetchone()[0]
            binding={'task_id':task_id,'revision':task[2],'epoch':epoch,'watermark':watermark}
            after=''
            if cursor is not None:
                if not isinstance(cursor,dict) or set(cursor)!={'binding','after'} or cursor['binding']!=binding or not isinstance(cursor['after'],str):
                    raise StateConflict('Context cursor is stale or invalid; restart this read')
                after=cursor['after']
            rows=c.execute('''SELECT operation_id,state,task_revision,request_hash FROM operation
                WHERE task_id=? AND operation_id>? AND state IN ('PREPARED','INTENT_RECORDED','UNKNOWN','OBSERVED')
                ORDER BY operation_id LIMIT ?''',(task_id,after,limit+1)).fetchall()
            more=len(rows)>limit
            rows=rows[:limit]
            run=c.execute('''SELECT r.run_id,r.host,r.native_id,r.state,r.checkpoint_id,
                p.summary,p.next_action FROM execution_run r LEFT JOIN checkpoint p ON p.checkpoint_id=r.checkpoint_id
                WHERE r.task_id=? AND r.state IN ('OPEN','PAUSE_REQUESTED','PAUSED')''',(task_id,)).fetchone()
            if run is not None and run[4] is not None:
                from v2_checkpoint_content import checkpoint_row
                checkpoint=checkpoint_row(c,c.execute('SELECT * FROM checkpoint WHERE checkpoint_id=? AND run_id=?',(run[4],run[0])).fetchone())
                run=(*run[:5],checkpoint[3],checkpoint[4])
            phase=c.execute('''SELECT b.task_revision,b.phase_id,b.phase_revision,p.revision,p.state,r.plan_sha256,
                r.plan_scope,substr(r.plan_ref,1,2048),length(r.plan_ref)
                FROM phase_task b JOIN phase p ON p.phase_id=b.phase_id
                JOIN phase_revision r ON r.phase_id=b.phase_id AND r.revision=b.phase_revision
                WHERE b.task_id=? ORDER BY b.task_revision DESC LIMIT 1''',(task_id,)).fetchone()
            phase_context=None if phase is None else dict(zip(
                ('bound_task_revision','phase_id','bound_phase_revision','current_phase_revision','phase_state','declared_plan_sha256',
                 'plan_scope','plan_ref_preview','plan_ref_characters'),phase))
            if phase_context is not None:
                phase_context['rebind_required']=phase[0]!=task[2] or phase[2]!=phase[3]
                phase_context['plan_content_verified']=False
            result={'task':dict(zip(('task_id','project_id','revision','status','goal_preview','goal_characters'),task[:6])),
                    'operations':[dict(zip(('operation_id','state','task_revision','request_hash'),r)) for r in rows],
                    'run':None if run is None else dict(zip(('run_id','host','native_id','state','checkpoint_id','summary','next_action'),run)),
                    'binding':binding,'reconciliation_required':bool(quarantined),
                    'authorization':{'evaluation':'NOT_EVALUATED','enforced_by':'OPERATION_PREPARE_AND_DISPATCH',
                        'authority_issued_by_read':False},
                    'next_cursor':{'binding':binding,'after':rows[-1][0]} if more else None,
                    'history_included':False,'full_task_details_included':False}
            result['presentation_version']=2
            result['task']['goal_preview_status']=preview['status']
            unknown_count=c.execute("SELECT count(*) FROM operation WHERE task_id=? AND state='UNKNOWN'",(task_id,)).fetchone()[0]
            unknown_host_count=c.execute("SELECT count(*) FROM host_dispatch WHERE task_id=? AND state='UNKNOWN'",(task_id,)).fetchone()[0]
            result['task']['effect_recovery']={'required':bool(unknown_count),'unknown_operation_count':unknown_count,
                'scope':'REGISTERED_OPERATION_EFFECTS','host_quiescence_verified':False}
            result['task']['host_recovery']={'required':bool(unknown_host_count),'unknown_dispatch_count':unknown_host_count,
                'scope':'REGISTERED_HOST_DISPATCHES','host_quiescence_verified':False}
            result['definition_body_reverified']=False
            if result['run'] is not None:
                result['run']['state_scope']='REGISTERED_OPERATION_CONTROL'
                result['run']['host_process_state']='NOT_OBSERVED_BY_THIS_READ'
            result['task']['completion_evidence']={'state':'VALID_ACCEPTANCE_RECORD' if task[6] else 'NO_VALID_ACCEPTANCE_RECORD',
                'freshly_verified':False,'purpose':'COMPLETION_REPORTING_NOT_CURRENT_TASK_START_PERMISSION'}
            result['phase_binding']=phase_context
            result['pending_migration_domains']=self.pending_migration_domains()
            if owns_transaction: c.execute('COMMIT')
            return result
        except BaseException:
            if owns_transaction and c.in_transaction:
                c.execute('ROLLBACK')
            raise

    def cancel_task(self, *, task_id, expected_revision, request_id, authority_ref, reason):
        """Stop future work without claiming external effects or writers stopped."""
        for field,value in [('task_id',task_id),('request_id',request_id),('authority_ref',authority_ref),('reason',reason)]:
            _text(value,field)
        if type(expected_revision) is not int or expected_revision<1:
            raise ValueError('Invalid cancellation revision')
        fingerprint=hashlib.sha256(_json(['task.cancel',task_id,expected_revision,authority_ref,reason]).encode()).hexdigest()
        with self.transaction() as c:
            prior=c.execute('SELECT request_hash,revision FROM request_receipt WHERE request_id=?',(request_id,)).fetchone()
            if prior:
                if prior[0]!=fingerprint: raise StateConflict('Cancellation request identity conflict')
                return {'decision':'REPLAY','accepted_revision':prior[1],'host_termination_verified':False}
            task=self.task(task_id)
            if task is None or task['revision']!=expected_revision:
                raise StateConflict('Cancellation requires exact current Task revision')
            if task['status']=='COMPLETED':
                raise StateConflict('Completed work requires evidence invalidation, not cancellation')
            pending=[r[0] for r in c.execute("SELECT operation_id FROM operation WHERE task_id=? AND state IN ('INTENT_RECORDED','UNKNOWN') ORDER BY operation_id",(task_id,))]
            c.execute("UPDATE task SET status='CANCELLED' WHERE task_id=?",(task_id,))
            c.execute('UPDATE execution_grant SET revoked=1 WHERE task_id=?',(task_id,))
            c.execute("UPDATE operation SET state='CANCELLED' WHERE task_id=? AND state='PREPARED'",(task_id,))
            # Keep unresolved Host ownership visible to recovery inventory.
            # Cancellation is not proof that an external writer has terminated.
            c.execute("UPDATE execution_run SET state=? WHERE task_id=? AND state IN ('OPEN','PAUSE_REQUESTED')",('PAUSE_REQUESTED' if pending else 'PAUSED',task_id))
            c.execute('INSERT INTO request_receipt VALUES (?,?,?,?)',(request_id,fingerprint,task_id,expected_revision))
            c.execute('INSERT INTO audit(request_id,kind,task_id,revision) VALUES (?,?,?,?)',
                      (request_id,'TASK_CANCELLED',task_id,expected_revision))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                      ('TASK_CANCELLED',task_id,_json({'authority_ref':authority_ref,'reason':reason,'pending_operations':pending})))
            return {'decision':'CANCELLED','accepted_revision':expected_revision,'pending_operations':pending,
                    'host_termination_verified':False,'external_effects_undone':False}

    def _reject_dependency_cycle(self, task_id, predecessor_id):
        cycle = self.connection.execute('''WITH RECURSIVE reachable(id) AS (
            SELECT ? UNION SELECT d.predecessor_id FROM dependency d
            JOIN task t ON t.task_id=d.task_id AND t.revision=d.task_revision
            JOIN reachable r ON r.id=d.task_id)
            SELECT 1 FROM reachable WHERE id=? LIMIT 1''', (predecessor_id, task_id)).fetchone()
        if cycle:
            raise StateConflict('Dependency would create a cycle')

    def add_dependency(self, *, task_id, task_revision, predecessor_id, predecessor_revision):
        with self.transaction() as c:
            task, predecessor = self.task(task_id), self.task(predecessor_id)
            if (task is None or predecessor is None or task_id == predecessor_id or
                    task['revision'] != task_revision or predecessor['revision'] != predecessor_revision or
                    task['project_id'] != predecessor['project_id'] or task['status'] != 'READY'):
                raise StateConflict('Dependency requires distinct current same-project tasks and a READY dependent')
            if c.execute('SELECT 1 FROM operation WHERE task_id=? AND task_revision=? LIMIT 1', (task_id, task_revision)).fetchone():
                raise StateConflict('Revise the task before changing dependencies after preparation')
            prior = c.execute('SELECT predecessor_revision FROM dependency WHERE task_id=? AND task_revision=? AND predecessor_id=?', (task_id, task_revision, predecessor_id)).fetchone()
            if prior:
                if prior[0] != predecessor_revision:
                    raise StateConflict('Dependency revision is immutable')
                return 'REPLAY'
            self._reject_dependency_cycle(task_id, predecessor_id)
            c.execute('INSERT INTO dependency VALUES (?,?,?,?)', (task_id, task_revision, predecessor_id, predecessor_revision))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                      ('DEPENDENCY_ADDED', task_id, _json({'revision':task_revision,'predecessor':predecessor_id,'predecessor_revision':predecessor_revision})))
            return 'ADDED'

    def unresolved_dependencies(self, task_id, task_revision):
        from v2_local_host import verify_task_file_results
        from v2_acceptance import Acceptance
        from v2_evidence import BlobStore
        c=self.connection; owns=not c.in_transaction
        if owns: c.execute('BEGIN')
        cache={}; visiting=set(); children={}
        def current(identity,revision):
            initial=(identity,revision); stack=[(initial,False)]
            while stack:
                key,expanded=stack.pop()
                if expanded:
                    visiting.discard(key)
                    if key not in cache: cache[key]=all(cache.get(child,False) for child in children[key])
                    continue
                if key in cache: continue
                if key in visiting:
                    cache[key]=False
                    continue
                node,version=key
                row=c.execute('''SELECT t.status,t.revision,t.project_id,(SELECT a.evidence_ids_json FROM acceptance a
                    WHERE a.task_id=t.task_id AND a.task_revision=? AND a.valid=1) FROM task t WHERE t.task_id=?''',(version,node)).fetchone()
                valid=row is not None and row[:2]==('COMPLETED',version) and row[3] is not None
                if valid:
                    try:
                        selected=json.loads(row[3])
                        if (not isinstance(selected,list) or not selected or
                                any(not isinstance(v,str) or not v for v in selected) or len(set(selected))!=len(selected)):
                            raise StateConflict('Accepted dependency has no valid evidence selection')
                        service=Acceptance(self,BlobStore(self.path.parent/'blobs',readonly=True))
                        for evidence_id in selected:
                            service._read_metered_in_transaction(evidence_id=evidence_id,owner=row[2],purpose='verification',verify_artifacts=False)
                        verify_task_file_results(self,node,version)
                    except (OSError,ValueError): valid=False
                if not valid:
                    cache[key]=False
                    continue
                visiting.add(key)
                children[key]=c.execute('SELECT predecessor_id,predecessor_revision FROM dependency WHERE task_id=? AND task_revision=?',(node,version)).fetchall()
                stack.append((key,True))
                for child in reversed(children[key]): stack.append((child,False))
            return cache[initial]
        try:
            edges=c.execute('SELECT predecessor_id,predecessor_revision FROM dependency WHERE task_id=? AND task_revision=? ORDER BY predecessor_id',(task_id,task_revision)).fetchall()
            result=[dict(zip(('task_id','required_revision'),edge)) for edge in edges if not current(*edge)]
            if owns: c.execute('COMMIT')
            return result
        except BaseException:
            if owns and c.in_transaction: c.execute('ROLLBACK')
            raise

    def revise_task(self, *, task_id: str, project_id: str, expected_revision: int, goal: str,
                    scope: list[str], acceptance: list[Any], request_id: str,
                    review_ref: str | None = None,
                    dependencies: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Revise a quiescent task; a paused replan requires an operator review.

        review_ref cites the caller's scope/effect and writer-quiescence review.
        It is an attestation, not authentication or proof of Host quiescence.
        """
        if self.readonly:
            raise PermissionError('Read-only store')
        for field, value in [('task_id', task_id), ('project_id', project_id), ('goal', goal), ('request_id', request_id)]:
            _text(value, field)
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError('Invalid expected_revision')
        if review_ref is not None:
            _text(review_ref, 'review_ref')
        if dependencies is not None:
            if not isinstance(dependencies, list):
                raise ValueError('dependencies must be a list')
            seen = set()
            for dependency in dependencies:
                if not isinstance(dependency, dict) or set(dependency) != {'predecessor_id','predecessor_revision'}:
                    raise ValueError('Expected closed predecessor_id/predecessor_revision dependency')
                _text(dependency['predecessor_id'], 'predecessor_id')
                if type(dependency['predecessor_revision']) is not int or dependency['predecessor_revision'] < 1:
                    raise ValueError('Invalid predecessor_revision')
                if dependency['predecessor_id'] in seen:
                    raise ValueError('Duplicate dependency')
                seen.add(dependency['predecessor_id'])
            dependencies = sorted(dependencies, key=lambda item: item['predecessor_id'])
            if expected_revision > 0 and review_ref is None:
                raise StateConflict('Replacing dependencies requires an explicit scope review')
        acceptance = criteria(acceptance)
        for field, values in [('scope', scope)]:
            if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError(f'{field} must be a nonempty text array')
            if len(set(values)) != len(values):
                raise ValueError(f'{field} contains duplicates')
        request_content = [task_id, project_id, expected_revision, goal, scope, acceptance]
        if review_ref is not None:
            request_content.append({'review_ref': review_ref})
        if dependencies is not None:
            request_content.append({'dependencies': dependencies})
        from v2_definition_content import encode,request_fingerprint,write_goal
        request_hash = request_fingerprint(self.connection,project_id,request_content)
        c = self.connection
        c.execute('BEGIN IMMEDIATE')
        try:
            prior = c.execute('SELECT request_hash,revision FROM request_receipt WHERE request_id=?', (request_id,)).fetchone()
            if prior:
                if prior[0] != request_hash:
                    raise StateConflict('Request ID reused with different contents')
                c.execute('COMMIT')
                return {'decision': 'REPLAY', 'accepted_revision': prior[1]}
            current = self.task(task_id)
            if (current['revision'] if current else 0) != expected_revision:
                raise StateConflict('Task revision changed')
            if current and (current['project_id'] != project_id or current['status'] not in {'READY','PAUSED','COMPLETED'}):
                raise StateConflict('Task project or lifecycle does not permit this revision')
            if current and current['status'] in {'PAUSED','COMPLETED'} and review_ref is None:
                raise StateConflict('Paused replanning requires an explicit effect and writer-quiescence review')
            if current and current['status']=='COMPLETED':
                owner=c.execute('''SELECT p.state FROM phase_task b JOIN phase p ON p.phase_id=b.phase_id
                    WHERE b.task_id=? AND b.task_revision=?''',(task_id,expected_revision)).fetchone()
                if owner and owner[0]!='PAUSED':
                    raise StateConflict('Reopen or pause the owning Phase before revising completed work')
            if current:
                self.require_execution_ready()
                if c.execute("SELECT 1 FROM host_dispatch WHERE task_id=? AND launch_committed=1 AND coalesce(quiesced,0)=0 LIMIT 1",(task_id,)).fetchone():
                    raise StateConflict('Quiesce the managed Host before revising its Task')
                if c.execute("SELECT 1 FROM operation WHERE task_id=? AND state IN ('INTENT_RECORDED','UNKNOWN') LIMIT 1", (task_id,)).fetchone():
                    raise StateConflict('Reconcile pending effects before replanning')
                if c.execute("SELECT 1 FROM execution_run WHERE task_id=? AND state IN ('OPEN','PAUSE_REQUESTED') LIMIT 1", (task_id,)).fetchone():
                    raise StateConflict('Pause the current Run before replanning')
            revision = expected_revision + 1
            if current:
                c.execute("UPDATE task SET revision=?,status='READY' WHERE task_id=?", (revision, task_id))
            else:
                c.execute('INSERT INTO task VALUES (?,?,?,?)', (task_id, project_id, revision, 'READY'))
            c.execute('INSERT INTO task_revision VALUES (?,?,?,?,?)', (task_id, revision,
                write_goal(c,goal,project_id,'task',task_id,revision),
                encode(scope,project_id,'task',task_id,revision,'scope'),
                encode(acceptance,project_id,'task',task_id,revision,'acceptance')))
            c.execute("UPDATE project_completion SET valid=0,invalidation_ref='task-revised' WHERE project_id=? AND valid=1",(project_id,))
            if dependencies is not None:
                for dependency in dependencies:
                    predecessor_id = dependency['predecessor_id']
                    predecessor_revision = dependency['predecessor_revision']
                    predecessor = self.task(predecessor_id)
                    if (predecessor is None or predecessor_id == task_id or
                            predecessor['project_id'] != project_id or predecessor['revision'] != predecessor_revision):
                        raise StateConflict('Dependency requires a distinct current same-project predecessor')
                    self._reject_dependency_cycle(task_id, predecessor_id)
                    c.execute('INSERT INTO dependency VALUES (?,?,?,?)',
                              (task_id,revision,predecessor_id,predecessor_revision))
            elif current:
                c.execute('''INSERT INTO dependency(task_id,task_revision,predecessor_id,predecessor_revision)
                    SELECT task_id,?,predecessor_id,predecessor_revision FROM dependency
                    WHERE task_id=? AND task_revision=?''', (revision,task_id,expected_revision))
            if current:
                c.execute("UPDATE operation SET state='CANCELLED' WHERE task_id=? AND task_revision=? AND state='PREPARED'", (task_id,expected_revision))
                c.execute("UPDATE execution_grant SET revoked=1 WHERE task_id=? AND task_revision=?", (task_id,expected_revision))
                c.execute("UPDATE execution_run SET state='CLOSED' WHERE task_id=? AND state='PAUSED'", (task_id,))
                c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                          ('TASK_REPLANNED', task_id, _json({'previous_revision':expected_revision,
                           'revision':revision,'review_ref':review_ref,'execution_authorized':False,
                           'host_quiescence_verified':False,'dependencies_replaced':dependencies is not None})))
            c.execute('INSERT INTO request_receipt VALUES (?,?,?,?)', (request_id, request_hash, task_id, revision))
            c.execute('INSERT INTO audit(request_id,kind,task_id,revision) VALUES (?,?,?,?)',
                      (request_id, 'TASK_CREATED' if current is None else 'TASK_REVISED', task_id, revision))
            c.execute('COMMIT')
            return {'decision': 'APPLIED', 'accepted_revision': revision}
        except BaseException:
            if c.in_transaction:
                c.execute('ROLLBACK')
            raise
