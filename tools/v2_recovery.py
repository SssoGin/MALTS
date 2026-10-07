"""Explicit operator-attested recovery, never automatic proof of external quiescence.

The operator/Host owns the truth and authorization of the submitted review. This
service enforces exact inventory coverage, epochs, pending-effect checks and an
atomic disposition; it cannot independently discover activity lost after backup.
No new execution Grant or valid Acceptance is created by reconciliation.
"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from typing import Any
from v2_state_store import StateStore, StateConflict, _json, _text

# Deep recovery is allowed to examine history. Daily context queries do not call
# this inventory, and raw request bodies are hashed rather than exposed by it.
# Pure definition_preview is intentionally excluded: repairing a derived view
# is not new canonical work and must not invalidate an otherwise unchanged review.
TABLES = (
    'recovery_state', 'migration_barrier', 'migration_review', 'migration_adoption', 'recovery_review', 'project', 'legacy_control_source', 'legacy_checkpoint', 'legacy_artifact_source', 'project_revision', 'phase', 'phase_revision', 'governance_receipt', 'task', 'task_revision',
    'task_budget', 'project_budget', 'phase_task', 'phase_carryover', 'phase_completion', 'phase_completion_task', 'project_completion', 'project_completion_phase', 'request_receipt', 'audit', 'execution_grant', 'operation',
    'operation_observation', 'operation_lease', 'execution_audit', 'evidence', 'acceptance',
    'evidence_policy', 'evidence_derivation', 'evidence_derivation_source', 'growth_candidate', 'growth_source', 'growth_trial', 'growth_outcome', 'growth_lifecycle', 'evidence_invalidation', 'dependency', 'execution_run', 'checkpoint', 'definition_key', 'task_effect_recovery',
    'dispatch_budget','dispatch_budget_change','dispatch_recovery_calls','execution_attempt','host_dispatch','host_invocation','handoff_note',
)
REPORT_FIELDS = {'review_id', 'authority_ref', 'basis', 'resource_reviews',
                 'writer_reviews', 'task_actions', 'unresolved_external_effects'}
TASK_ACTIONS = {'REVERIFY', 'KEEP_PAUSED', 'KEEP_HISTORY', 'CANCEL'}


def digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def closed(value: Any, fields: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f'{label} must match its closed contract')


def text(value: Any, label: str) -> None:
    _text(value, label)
    if len(value) > 4096:
        raise ValueError(f'{label} exceeds recovery text limit')


def project_root_resources(connection):
    return [{'resource_id': digest([project_id, root, '.', 'PROJECT_ROOT']),
             'project_id': project_id, 'root': root, 'locator': '.', 'coverage_scope': 'PROJECT_ROOT'}
            for project_id, root in connection.execute('SELECT project_id,resource_root FROM project ORDER BY project_id')]


def require_project_review(connection, review_id, epoch):
    """Old receipts remain history; consumers must prove current root coverage."""
    row = connection.execute('SELECT request_sha256,report_json,receipt_json FROM recovery_review WHERE review_id=? AND epoch=?',
                             (review_id, epoch)).fetchone()
    if row is None:
        raise StateConflict('Current recovery review is missing')
    report, receipt = json.loads(row[1]), json.loads(row[2])
    if digest(report) != row[0] or receipt.get('decision') != 'RECONCILED':
        raise StateConflict('Recovery review content is not a reconciled record')
    expected = {r['resource_id'] for r in project_root_resources(connection)}
    rows = report.get('resource_reviews', [])
    for resource_id in expected:
        matches = [r for r in rows if r.get('resource_id') == resource_id]
        if len(matches) != 1 or matches[0].get('coverage') != 'RECONCILED' or not matches[0].get('evidence_ref'):
            raise StateConflict('Recovery review lacks current project-root coverage; restore and review again')


class Recovery:
    def __init__(self, store: StateStore):
        self.store = store

    @contextmanager
    def _read(self):
        c = self.store.connection
        c.execute('BEGIN')
        try:
            yield c
            c.execute('COMMIT')
        except BaseException:
            if c.in_transaction:
                c.execute('ROLLBACK')
            raise

    def _inventory(self, c) -> dict[str, Any]:
        recovery = c.execute('SELECT epoch,reconciliation_required,source_backup_hash FROM recovery_state WHERE singleton=1').fetchone()
        if recovery is None:
            raise StateConflict('Recovery identity is missing')
        table_hashes = {}
        for table in TABLES:
            hasher = hashlib.sha256()
            for row in c.execute(f'SELECT * FROM {table} ORDER BY 1'):
                hasher.update((_json(list(row)) + '\n').encode('utf-8'))
            table_hashes[table] = hasher.hexdigest()
        tasks = []
        for task_id, project_id, revision, status in c.execute('SELECT task_id,project_id,revision,status FROM task ORDER BY task_id'):
            tasks.append({'task_id': task_id, 'project_id': project_id, 'revision': revision, 'status': status})
        # Historical scopes matter too: an old grant may have had an effect after
        # the backup, even when the Task's current scope has since been narrowed.
        resources = {}
        # Task scopes in a backup cannot enumerate tasks/resources first created
        # afterwards. Require a project-wide review even for an empty project;
        # this is explicit operator coverage, not automatic filesystem proof.
        for row in project_root_resources(c):
            resources[row['resource_id']] = row
        for project_id, root, scope_json, task_id, revision in c.execute('''SELECT t.project_id,p.resource_root,r.scope_json,t.task_id,r.revision
                FROM task_revision r JOIN task t ON t.task_id=r.task_id JOIN project p ON p.project_id=t.project_id'''):
            from v2_definition_content import decode
            for locator in decode(scope_json,project_id,'task',task_id,revision,'scope'):
                resource_id = digest([project_id, root, locator])
                resources[resource_id] = {'resource_id': resource_id, 'project_id': project_id, 'root': root, 'locator': locator}
        writers = [dict(zip(('run_id', 'task_id', 'host', 'native_id', 'actor', 'state'), row))
                   for row in c.execute("SELECT run_id,task_id,host,native_id,actor,state FROM execution_run WHERE state<>'CLOSED' ORDER BY run_id")]
        pending = [dict(zip(('operation_id', 'task_id', 'state', 'request_hash'), row))
                   for row in c.execute("SELECT operation_id,task_id,state,request_hash FROM operation WHERE state IN ('INTENT_RECORDED','UNKNOWN') ORDER BY operation_id")]
        return {
            'binding': {'epoch': recovery[0], 'source_backup_hash': recovery[2], 'state_sha256': digest(table_hashes)},
            'reconciliation_required': bool(recovery[1]), 'tasks': tasks,
            'resources': [resources[key] for key in sorted(resources)], 'writers': writers,
            'pending_operations': pending, 'execution_authorized': False,
            'coverage_requirement': 'Review every project root for post-backup tasks, resources, external effects and writers absent from this database, as well as every historical Task scope. Unknown coverage must remain UNKNOWN.',
            'host_facts_independently_verified': False,
        }

    def inspect(self) -> dict[str, Any]:
        with self._read() as c:
            return self._inventory(c)

    @staticmethod
    def _rows(value: Any, fields: set[str], key: str, expected: set[str], label: str) -> dict[str, dict]:
        if not isinstance(value, list):
            raise ValueError(f'{label} must be a list')
        rows = {}
        for row in value:
            closed(row, fields, label)
            text(row[key], key)
            if row[key] in rows:
                raise StateConflict(f'{label} contains duplicate identity')
            rows[row[key]] = row
        if set(rows) != expected:
            raise StateConflict(f'{label} must cover the exact current inventory')
        return rows

    def _plan(self, report: dict, inventory: dict) -> dict:
        closed(report, REPORT_FIELDS, 'Recovery review')
        text(report['review_id'], 'review_id')
        text(report['authority_ref'], 'authority_ref')
        if report['basis'] != inventory['binding']:
            raise StateConflict('Recovery review is stale or belongs to a different epoch')
        if not inventory['reconciliation_required'] or not inventory['binding']['source_backup_hash']:
            raise StateConflict('Recovery review requires a quarantined restored database')
        if not isinstance(report['unresolved_external_effects'], list):
            raise ValueError('Unresolved external effects must be an explicit list')
        for item in report['unresolved_external_effects']:
            text(item, 'external_effect')
        resource_rows = self._rows(report['resource_reviews'], {'resource_id', 'coverage', 'evidence_ref'}, 'resource_id',
                                   {r['resource_id'] for r in inventory['resources']}, 'Resource reviews')
        writer_rows = self._rows(report['writer_reviews'], {'run_id', 'state', 'evidence_ref'}, 'run_id',
                                 {r['run_id'] for r in inventory['writers']}, 'Writer reviews')
        task_rows = self._rows(report['task_actions'], {'task_id', 'revision', 'action', 'reason', 'next_action'}, 'task_id',
                               {r['task_id'] for r in inventory['tasks']}, 'Task actions')
        blockers = []
        if inventory['pending_operations']:
            blockers.append('UNRESOLVED_OPERATION')
        if self.store.connection.execute("SELECT 1 FROM host_dispatch WHERE launch_committed=1 AND coalesce(quiesced,0)=0 LIMIT 1").fetchone():
            blockers.append('HOST_DISPATCH_NOT_QUIESCED')
        if report['unresolved_external_effects']:
            blockers.append('UNRESOLVED_EXTERNAL_EFFECT')
        for row in resource_rows.values():
            text(row['evidence_ref'], 'resource evidence_ref')
            if row['coverage'] not in {'RECONCILED', 'UNKNOWN'}:
                raise ValueError('Unsupported resource coverage')
            if row['coverage'] != 'RECONCILED':
                blockers.append('RESOURCE_COVERAGE_UNKNOWN')
        for row in writer_rows.values():
            text(row['evidence_ref'], 'writer evidence_ref')
            if row['state'] not in {'QUIESCED', 'RUNNING', 'UNKNOWN'}:
                raise ValueError('Unsupported writer state')
            if row['state'] != 'QUIESCED':
                blockers.append('WRITER_NOT_QUIESCED')
        actions = []
        for task in inventory['tasks']:
            row = task_rows[task['task_id']]
            if type(row['revision']) is not int or row['revision'] != task['revision']:
                raise StateConflict('Task disposition binds a stale revision')
            if row['action'] not in TASK_ACTIONS:
                raise ValueError('Unsupported recovery task action')
            text(row['reason'], 'task reason')
            if row['action'] == 'REVERIFY':
                text(row['next_action'], 'next_action')
            elif row['next_action'] is not None:
                text(row['next_action'], 'next_action')
            if row['action'] == 'KEEP_HISTORY' and task['status'] not in {'COMPLETED', 'FAILED', 'CANCELLED'}:
                raise StateConflict('A nonterminal Task cannot be dispositioned as history')
            actions.append({**row, 'previous_status': task['status']})
        result = {
            'decision': 'BLOCKED' if blockers else 'READY_FOR_OPERATOR_ACCEPTANCE',
            'binding': inventory['binding'], 'review_id': report['review_id'], 'report_sha256': digest(report),
            'blockers': sorted(set(blockers)), 'task_actions': actions,
            'assurance': 'OPERATOR_ATTESTED', 'host_facts_independently_verified': False,
            'execution_authorized': False, 'grants_reactivated': False, 'acceptances_revalidated': False,
        }
        result['plan_sha256'] = digest(result)
        return result

    def plan(self, report: dict) -> dict:
        with self._read() as c:
            return self._plan(report, self._inventory(c))

    def apply(self, report: dict, *, expected_plan_sha256: str) -> dict:
        closed(report, REPORT_FIELDS, 'Recovery review')
        request_sha = digest(report)
        with self.store.transaction() as c:
            old = c.execute('SELECT request_sha256,plan_sha256,receipt_json,epoch FROM recovery_review WHERE review_id=?', (report['review_id'],)).fetchone()
            if old:
                current_epoch = c.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()
                if current_epoch is None or old[3] != current_epoch[0]:
                    raise StateConflict('Historical recovery receipt belongs to another restore epoch')
                if old[:2] != (request_sha, expected_plan_sha256):
                    raise StateConflict('Recovery review identity conflicts with its committed request')
                return json.loads(old[2])
            inventory = self._inventory(c)
            plan = self._plan(report, inventory)
            if plan['plan_sha256'] != expected_plan_sha256:
                raise StateConflict('Recovery apply does not match the reviewed plan hash')
            if plan['blockers']:
                raise StateConflict('Recovery remains blocked: ' + ', '.join(plan['blockers']))
            epoch = inventory['binding']['epoch']
            from v2_artifacts import Artifacts
            Artifacts(self.store).stage_recovery_handoffs(task_actions=plan['task_actions'],epoch=epoch)
            # Even grants recorded during quarantine cannot silently become live.
            c.execute('UPDATE execution_grant SET revoked=1')
            c.execute("UPDATE operation SET state='CANCELLED' WHERE state='PREPARED'")
            c.execute("UPDATE execution_run SET state='CLOSED' WHERE state<>'CLOSED'")
            status_map = {'REVERIFY': 'READY', 'KEEP_PAUSED': 'PAUSED', 'CANCEL': 'CANCELLED'}
            for action in plan['task_actions']:
                task_id, revision = action['task_id'], action['revision']
                if action['action'] != 'KEEP_HISTORY':
                    c.execute('UPDATE task SET status=? WHERE task_id=? AND revision=?', (status_map[action['action']], task_id, revision))
                c.execute('UPDATE acceptance SET valid=0,invalidation_ref=? WHERE task_id=? AND valid=1', ('recovery:' + epoch, task_id))
                c.execute('''INSERT OR IGNORE INTO evidence_invalidation(evidence_id,reason,authority_ref)
                    SELECT evidence_id,?,? FROM evidence WHERE task_id=? AND task_revision=?''',
                    ('Restored evidence requires current verification: ' + epoch, report['authority_ref'], task_id, revision))
            receipt = {
                'decision': 'RECONCILED', 'review_id': report['review_id'], 'epoch': epoch,
                'plan_sha256': expected_plan_sha256, 'assurance': 'OPERATOR_ATTESTED',
                'host_facts_independently_verified': False, 'execution_authorized': False,
                'next_tasks': plan['task_actions'],
            }
            c.execute('INSERT INTO recovery_review VALUES (?,?,?,?,?,?)',
                      (report['review_id'], epoch, expected_plan_sha256, request_sha, _json(report), _json(receipt)))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                      ('RECOVERY_REVIEW_ACCEPTED', report['review_id'], _json(receipt)))
            c.execute('UPDATE recovery_state SET reconciliation_required=0 WHERE singleton=1 AND epoch=?', (epoch,))
            return receipt
