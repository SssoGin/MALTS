"""Owner-bound handoff snapshots and explicitly authorized local view publication."""
import copy
import base64
import hashlib
import json
import re
import os
from pathlib import Path

from v2_definition_content import request_fingerprint, encode, decode
from v2_state_store import StateConflict, _text, _json

NOTE_BYTES_LIMIT = 65536


class HandoffNotes:
    """Immutable protected owner records. Captured prose is never an instruction.

    The trusted controller supplies reviewed bytes; source_ref is provenance,
    not a path to read. Source-file identity is a separate publication check.
    """
    def __init__(self, store):
        self.store = store

    def preserve(self, *, note_id, project_id, task_id, task_revision, source_ref,
                 source_sha256, source_bytes_base64, review_ref, capture_authority_ref):
        for field, value in [('note_id',note_id), ('project_id',project_id), ('task_id',task_id),
                             ('source_ref',source_ref), ('review_ref',review_ref),
                             ('capture_authority_ref',capture_authority_ref)]:
            _text(value, field)
            if len(value) > 4096:
                raise ValueError('Handoff provenance exceeds its bound')
        if type(task_revision) is not int or task_revision < 1:
            raise ValueError('Handoff note requires an exact Task revision')
        if (not isinstance(source_bytes_base64,str) or len(source_bytes_base64) > 4*((NOTE_BYTES_LIMIT+2)//3)
                or not isinstance(source_sha256,str) or re.fullmatch('[0-9a-f]{64}',source_sha256) is None):
            raise ValueError('Invalid bounded handoff source')
        data = base64.b64decode(source_bytes_base64, validate=True)
        if len(data) > NOTE_BYTES_LIMIT or hashlib.sha256(data).hexdigest() != source_sha256:
            raise ValueError('Handoff bytes differ from the reviewed source digest')
        # Canonicalize equivalent encodings before computing an immutable receipt.
        value = {'source_ref':source_ref, 'source_sha256':source_sha256,
                 'source_bytes_base64':base64.b64encode(data).decode('ascii'),
                 'review_ref':review_ref, 'capture_authority_ref':capture_authority_ref,
                 'classification':'PRESERVED_SOURCE_DATA_NOT_INSTRUCTIONS'}
        with self.store.transaction() as c:
            fingerprint = request_fingerprint(c, project_id,
                ['handoff-note',note_id,project_id,task_id,task_revision,value])
            prior = c.execute('SELECT project_id,request_hash FROM handoff_note WHERE note_id=?',(note_id,)).fetchone()
            if prior is not None:
                if prior != (project_id,fingerprint):
                    raise StateConflict('Handoff note identity is immutable')
                return {'decision':'REPLAY','verification':'HISTORICAL_RECEIPT','execution_authorized':False}
            self.store.require_execution_ready()
            current = c.execute('SELECT project_id,revision FROM task WHERE task_id=?',(task_id,)).fetchone()
            if current != (project_id,task_revision):
                raise StateConflict('Handoff note requires the current owner Task revision')
            protected = encode(value,project_id,'handoff-note',note_id,task_revision,'source')
            c.execute('INSERT INTO handoff_note VALUES (?,?,?,?,?,?)',
                      (note_id,project_id,task_id,task_revision,protected,fingerprint))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                      ('HANDOFF_NOTE_PRESERVED',note_id,_json({'task_id':task_id,'task_revision':task_revision})))
            return {'decision':'PRESERVED','note_id':note_id,'bytes_preserved':len(data),
                    'source_file_verified':False,'execution_authorized':False,'publication_authorized':False}

    def read(self, *, project_id, note_id):
        _text(project_id,'project_id'); _text(note_id,'note_id')
        row = self.store.connection.execute('''SELECT task_id,task_revision,protected_content
            FROM handoff_note WHERE project_id=? AND note_id=?''',(project_id,note_id)).fetchone()
        if row is None:
            raise StateConflict('Handoff note is unavailable for this owner')
        value = decode(row[2],project_id,'handoff-note',note_id,row[1],'source')
        data = base64.b64decode(value['source_bytes_base64'],validate=True)
        if len(data) > NOTE_BYTES_LIMIT or hashlib.sha256(data).hexdigest() != value['source_sha256']:
            raise StateConflict('Preserved handoff source failed integrity checking')
        return {'note_id':note_id,'project_id':project_id,'task_id':row[0],'task_revision':row[1],
                'source':value,'source_file_verified':False,'execution_authorized':False,
                'current_task_authority_inherited':False}

    def capture_file(self, *, note_id, project_id, task_id, task_revision, source_relative,
                     expected_sha256, review_ref, capture_authority_ref):
        """Preserve reviewed bytes while holding the existing local file exclusively.

        No file is changed. A successful observation applies only to this capture;
        a publisher must compare the current file again under its own write guard.
        """
        from v2_local_host import unambiguous_relative_file
        from v2_file_update import exclusive_existing_file
        relative = unambiguous_relative_file(source_relative)
        if not isinstance(expected_sha256,str) or re.fullmatch('[0-9a-f]{64}',expected_sha256) is None:
            raise ValueError('Capture requires the reviewed source digest')
        if type(task_revision) is not int or task_revision < 1:
            raise ValueError('Capture requires an exact Task revision')
        self.store.require_execution_ready()
        row = self.store.connection.execute('''SELECT t.project_id,t.revision,p.resource_root
            FROM task t JOIN project p ON p.project_id=t.project_id WHERE task_id=?''',(task_id,)).fetchone()
        if row is None or row[:2] != (project_id,task_revision):
            raise StateConflict('Capture requires the current owner Task')
        # Validate explicit capture approval before any source-file read.
        for key,value in [('note_id',note_id),('review_ref',review_ref),('capture_authority_ref',capture_authority_ref)]:
            _text(value,key)
            if len(value)>4096:raise ValueError('Handoff provenance exceeds its bound')
        target = Path(row[2]).absolute()/relative
        with exclusive_existing_file(target) as stream:
            data = stream.read(NOTE_BYTES_LIMIT+1)
            if len(data)>NOTE_BYTES_LIMIT:raise ValueError('Handoff source exceeds capture limit')
            if hashlib.sha256(data).hexdigest()!=expected_sha256:
                raise StateConflict('Handoff source changed after review')
            result = self.preserve(note_id=note_id,project_id=project_id,task_id=task_id,
                task_revision=task_revision,source_ref='project-file:'+relative.as_posix(),
                source_sha256=expected_sha256,source_bytes_base64=base64.b64encode(data).decode('ascii'),
                review_ref=review_ref,capture_authority_ref=capture_authority_ref)
        return {**result,'source_file_verified_at_capture':True,'source_file_modified':False,
                'source_file_still_current':'NOT_RECHECKED_AFTER_CAPTURE','publication_authorized':False}

    def publish(self, *, publication_id, project_id, task_id, task_revision,
                target_relative, target_note_id, source_token, note_ids, publication_authority_ref,
                limit=20, language='en'):
        """Controller-authorized derived-view write, never a Task execution Grant.

        The host must authorize this exact projection replacement. The current
        target preimage has an explicit identity; other selected immutable notes
        are historical data, not claims about their source files' current bytes.
        """
        from v2_local_host import unambiguous_relative_file
        from v2_file_update import exclusive_existing_file
        for name,value in [('publication_id',publication_id),('publication_authority_ref',publication_authority_ref)]:
            _text(value,name)
            if len(value)>4096:raise ValueError('Publication reference exceeds its bound')
        relative=unambiguous_relative_file(target_relative).as_posix()
        if not isinstance(source_token,str) or re.fullmatch('[0-9a-f]{64}',source_token) is None:
            raise ValueError('Publication requires an exact reviewed source token')
        c=self.store.connection
        request=dict(project_id=project_id,task_id=task_id,task_revision=task_revision,
                     target_relative=relative,target_note_id=target_note_id,source_token=source_token,note_ids=note_ids,
                     publication_authority_ref=publication_authority_ref,limit=limit,language=language)
        fingerprint=request_fingerprint(c,project_id,['handoff-publication',publication_id,request])
        prior=c.execute("SELECT details_json FROM execution_audit WHERE kind='HANDOFF_PUBLICATION_INTENT' AND subject_id=?",(publication_id,)).fetchall()
        if prior:
            if len(prior)!=1 or json.loads(prior[0][0]).get('request_hash')!=fingerprint:
                raise StateConflict('Publication identity is immutable or belongs to another owner')
            return {'decision':'NOT_REEXECUTED','publication_id':publication_id,
                    'next_step':'INSPECT_PUBLICATION','execution_authorized':False}
        self.store.require_execution_ready()
        preview=preview_handoff(self.store,task_id=task_id,task_revision=task_revision,
            limit=limit,language=language,expected_source_token=source_token,note_ids=note_ids)
        if preview['presentation']['facts']['task']['project_id']!=project_id:
            raise StateConflict('Publication owner differs')
        if preview['decision']=='PARTIAL_PREVIEW':raise StateConflict('Cannot publish a truncated handoff')
        content=preview['markdown'].encode('utf-8')
        if len(content)>NOTE_BYTES_LIMIT:raise ValueError('Published handoff exceeds the recoverable file capture limit')
        selected=[record for record in preview['presentation']['selected_notes'] if record['note_id']==target_note_id]
        if len(selected)!=1 or selected[0]['source']['source_ref']!='project-file:'+relative:
            raise StateConflict('Publish target requires its explicitly selected preserved file preimage')
        before_hash=selected[0]['source']['source_sha256']
        root=Path(c.execute('SELECT resource_root FROM project WHERE project_id=?',(project_id,)).fetchone()[0]).absolute()
        target_hash=hashlib.sha256(content).hexdigest()
        contract={**request,'before_sha256':before_hash,'after_sha256':target_hash}
        protected=encode(contract,project_id,'handoff-publication',publication_id,task_revision,'contract')
        with exclusive_existing_file(root/relative) as stream:
            data=stream.read(NOTE_BYTES_LIMIT+1)
            if len(data)>NOTE_BYTES_LIMIT or hashlib.sha256(data).hexdigest()!=before_hash:
                raise StateConflict('Selected handoff target preimage changed')
            with self.store.transaction():
                self.store.require_execution_ready()
                preview_handoff(self.store,task_id=task_id,task_revision=task_revision,
                    limit=limit,language=language,expected_source_token=source_token,note_ids=note_ids)
                if c.execute("SELECT 1 FROM execution_audit WHERE kind='HANDOFF_PUBLICATION_INTENT' AND subject_id=?",(publication_id,)).fetchone():
                    raise StateConflict('Publication already admitted; inspect instead of retrying')
                c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                    ('HANDOFF_PUBLICATION_INTENT',publication_id,_json({'project_id':project_id,
                     'task_revision':task_revision,'request_hash':fingerprint,'contract':protected})))
            # Intent and preimage survive a crash even if this final transaction
            # rolls back. Canonical owner state is never reverted to repair a view.
            with self.store.transaction():
                self.store.require_execution_ready()
                preview_handoff(self.store,task_id=task_id,task_revision=task_revision,
                    limit=limit,language=language,expected_source_token=source_token,note_ids=note_ids)
                stream.seek(0);stream.write(content);stream.truncate();stream.flush();os.fsync(stream.fileno())
                stream.seek(0)
                if stream.read(NOTE_BYTES_LIMIT+1)!=content:raise OSError('Handoff publication readback differs')
                c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                    ('HANDOFF_PUBLICATION_WRITTEN',publication_id,_json({'sha256':target_hash})))
        return {'decision':'PUBLISHED','publication_id':publication_id,'sha256':target_hash,
                'projection_only':True,'execution_authorized':False,'canonical_task_changed':False}

    def inspect_publication(self, *, publication_id, project_id):
        """Inspect interrupted or historical publication; never rewrite the view."""
        from v2_local_host import unambiguous_relative_file
        from v2_file_update import exclusive_existing_file
        rows=self.store.connection.execute("SELECT details_json FROM execution_audit WHERE kind='HANDOFF_PUBLICATION_INTENT' AND subject_id=?",(publication_id,)).fetchall()
        if len(rows)!=1:raise StateConflict('Publication lacks a unique intent')
        record=json.loads(rows[0][0])
        if record['project_id']!=project_id:raise StateConflict('Publication belongs to another owner')
        contract=decode(record['contract'],project_id,'handoff-publication',publication_id,record['task_revision'],'contract')
        root=self.store.connection.execute('SELECT resource_root FROM project WHERE project_id=?',(project_id,)).fetchone()[0]
        target=unambiguous_relative_file(contract['target_relative']).as_posix()
        with exclusive_existing_file(Path(root).absolute()/target) as stream:
            data=stream.read(NOTE_BYTES_LIMIT+1)
        digest=hashlib.sha256(data).hexdigest()
        state='PUBLISHED_BYTES' if digest==contract['after_sha256'] else 'PREIMAGE' if digest==contract['before_sha256'] else 'DIVERGED'
        try:
            preview_handoff(self.store,task_id=contract['task_id'],task_revision=contract['task_revision'],
                limit=contract['limit'],language=contract['language'],expected_source_token=contract['source_token'],note_ids=contract['note_ids'])
            current=True
        except StateConflict:current=False
        written=self.store.connection.execute("SELECT details_json FROM execution_audit WHERE kind='HANDOFF_PUBLICATION_WRITTEN' AND subject_id=?",(publication_id,)).fetchall()
        durable_receipt=len(written)==1 and json.loads(written[0][0]).get('sha256')==contract['after_sha256']
        return {'decision':'INSPECTED','file_state':state,'source_facts_current':current,
                'view_usable':state=='PUBLISHED_BYTES' and current and durable_receipt,'bytes_rewritten':0,
                'publication_receipt':'WRITTEN' if durable_receipt else 'INTENT_UNRESOLVED',
                'target_file_rechecked':True,'other_selected_notes':'IMMUTABLE_HISTORICAL_DATA',
                'execution_authorized':False,'preserved_note_ids':contract['note_ids']}


def _recovery_facts(store, task_id, task_revision, limit):
    """Explicit current owner facts, bounded independently for each collection.

    Grant descriptions are records, never a decision that a grant is usable.
    Do not expose protected authority prose, dispatch payloads or evidence bytes.
    """
    from v2_operations import Operations
    c = store.connection
    task = store.task(task_id)
    collections = {}
    incomplete = []

    def rows(name, sql, arguments):
        cursor = c.execute(sql+' LIMIT ?', (*arguments, limit+1))
        fields = [field[0] for field in cursor.description]
        values = cursor.fetchall()
        if len(values)>limit:incomplete.append(name)
        collections[name] = [dict(zip(fields,row)) for row in values[:limit]]

    rows('grants', '''SELECT grant_id,task_revision,actor,resource,effect,revoked,expires_at,max_operations
        FROM execution_grant WHERE task_id=? AND task_revision=? ORDER BY grant_id''', (task_id,task_revision))
    rows('dependencies', '''SELECT d.predecessor_id,d.predecessor_revision,t.revision AS current_revision,t.status
        FROM dependency d JOIN task t ON t.task_id=d.predecessor_id
        WHERE d.task_id=? AND d.task_revision=? ORDER BY d.predecessor_id''', (task_id,task_revision))
    rows('leases', '''SELECT l.operation_id,l.epoch,l.fence,l.actor,l.expires_at,l.state
        FROM operation_lease l JOIN operation o ON o.operation_id=l.operation_id
        WHERE o.task_id=? AND l.state<>'RELEASED' ORDER BY l.operation_id''', (task_id,))
    rows('host_dispatches', '''SELECT dispatch_id,task_revision,host_id,profile_revision,run_id,
        state,launch_committed,cancel_requested,quiesced FROM host_dispatch
        WHERE task_id=? AND coalesce(quiesced,0)=0 ORDER BY dispatch_id''', (task_id,))
    rows('evidence_index', '''SELECT e.evidence_id,e.operation_id,e.criterion,e.result,e.method,e.evidence_level,
        coalesce(p.revoked,1) AS access_revoked,
        EXISTS(SELECT 1 FROM evidence_invalidation i WHERE i.evidence_id=e.evidence_id) AS invalidated
        FROM evidence e LEFT JOIN evidence_policy p ON p.evidence_id=e.evidence_id
        WHERE e.task_id=? AND e.task_revision=? ORDER BY e.evidence_id''', (task_id,task_revision))
    ops=Operations(store)
    for grant in collections['grants']:
        try:
            bound=ops._grant(c,grant['grant_id'],grant['actor'])
            ops.require_operation_budget(c,grant['grant_id'],bound)
            grant['current_checks']='PASSED_NOT_EXECUTION_PERMISSION'
        except (StateConflict,PermissionError):
            grant['current_checks']='NOT_USABLE_REVIEW_CURRENT_CONTRACT'
    from v2_artifacts import Artifacts
    artifacts=Artifacts(store)
    pending=artifacts.recovery_handoff(task_id=task_id,task_revision=task_revision)
    run=c.execute("SELECT run_id,checkpoint_id FROM execution_run WHERE task_id=? AND state<>'CLOSED'",(task_id,)).fetchone()
    binding={'decision':'NO_CURRENT_CHECKPOINT'}
    if run is not None and run[1] is not None:
        try:
            binding=artifacts.verify_recovery_binding(run_id=run[0],checkpoint_id=run[1])
        except StateConflict:
            binding={'decision':'REVIEW_REQUIRED','reason':'CURRENT_BINDING_UNAVAILABLE',
                     'run_id':run[0],'checkpoint_id':run[1],'execution_authorized':False}
    return {'task_definition':task,
            'resource_root':c.execute('SELECT resource_root FROM project WHERE project_id=?',(task['project_id'],)).fetchone()[0],
            'operation_budgets':ops.budget_status(project_id=task['project_id'],task_id=task_id),
            'artifact_recovery':{'current_binding':binding,'pending_successor':pending},
            **collections, 'incomplete_collections':incomplete,
            'registered_facts_only':True, 'grant_usability':'RECHECK_AT_EXECUTION',
            'external_effects_and_host_liveness':'NOT_OBSERVED',
            'evidence_and_artifact_bytes':'NOT_REVERIFIED'}


def preview_handoff(store, *, task_id, task_revision, limit=20, language='en', expected_source_token=None, note_ids=None):
    """Read one bounded snapshot. Never infer instructions from checkpoint prose.

    The keyed token detects changes in the presented owner facts, not all possible
    business dependencies. It is neither execution permission nor a file CAS.
    """
    _text(task_id, 'task_id')
    if type(task_revision) is not int or task_revision < 1:
        raise ValueError('Handoff requires an explicit Task revision')
    if language not in {'en', 'zh-CN'}:
        raise ValueError('Unsupported handoff language')
    selected = [] if note_ids is None else note_ids
    if (not isinstance(selected,list) or len(selected)>8 or
            any(not isinstance(x,str) or not x.strip() for x in selected) or len(set(selected))!=len(selected)):
        raise ValueError('Select at most eight distinct handoff note identities')
    if expected_source_token is not None and (not isinstance(expected_source_token, str) or
            re.fullmatch('[0-9a-f]{64}', expected_source_token) is None):
        raise ValueError('Invalid handoff source token')
    c = store.connection
    owns_transaction = not c.in_transaction
    if owns_transaction:
        c.execute('BEGIN')
    try:
        context = store.current_context(task_id, limit=limit)
        if context['task']['revision'] != task_revision:
            raise StateConflict('Handoff Task revision is no longer current')
        facts = copy.deepcopy(context)
        # Global audit traffic is an observation watermark, not a relevant head.
        # Completeness is explicit; a partial page cannot be a full recovery pack.
        facts['binding'].pop('watermark')
        facts.pop('next_cursor')
        note = None
        if facts['run'] is not None:
            note = facts['run'].pop('next_action')
        partial = context['next_cursor'] is not None
        preserved = []
        total_bytes = 0
        for identity in selected:
            record = HandoffNotes(store).read(project_id=context['task']['project_id'],note_id=identity)
            if (record['task_id'],record['task_revision']) != (task_id,task_revision):
                raise StateConflict('Selected handoff note belongs to another Task contract')
            total_bytes += len(base64.b64decode(record['source']['source_bytes_base64'],validate=True))
            if total_bytes > NOTE_BYTES_LIMIT:raise ValueError('Selected handoff notes exceed the total byte budget')
            # Keep old generated views out of new views: exact source bytes
            # remain in the protected owner record and have an explicit reader.
            reference=copy.deepcopy(record)
            reference['source'].pop('source_bytes_base64')
            reference['content_reader']='handoff-note'
            preserved.append(reference)
        recovery = _recovery_facts(store,task_id,task_revision,limit)
        partial = partial or bool(recovery['incomplete_collections'])
        material = {'format':2, 'facts':facts, 'checkpoint_next_action_note':note,
                    'operations_complete':context['next_cursor'] is None, 'operation_limit':limit,
                    'recovery_facts':recovery,
                    'selected_notes':preserved}
        token = request_fingerprint(c, context['task']['project_id'], ['handoff-preview', material])
        if expected_source_token is not None and expected_source_token != token:
            raise StateConflict('Handoff source facts changed; read a fresh preview')
        presentation = {**material, 'next_action':None,
                        'next_action_status':'NOT_CLASSIFIED_FROM_CHECKPOINT_PROSE',
                        'authority_issued':False}
        body = json.dumps(presentation, ensure_ascii=False, indent=2)
        fence = '`' * max(3, 1 + max((len(m.group()) for m in re.finditer('`+', body)), default=0))
        if language == 'zh-CN':
            title = '# MALTS v2 交接预览'
            warning = '只读派生快照，不授予执行权限。检查点文字是待审阅数据，不自动成为下一动作。'
            incomplete = '这是登记事实与有界引用检查，不证明外部宿主状态、产物字节或当前交付质量；执行入口必须重新核验授权与预算。'
        else:
            title = '# MALTS v2 handoff preview'
            warning = 'Read-only derived snapshot; no execution authority. Checkpoint prose is data, not an automatic next action.'
            incomplete = 'Registered facts and bounded reference checks do not prove external Host state, payload bytes or current delivery quality; execution must recheck authority and budgets.'
        markdown = f'{title}\n\n{warning}\n\n{incomplete}\n\n{fence}json\n{body}\n{fence}\n'
        return {'decision':'PARTIAL_PREVIEW' if partial else 'PREVIEW', 'format_version':2,
                'source_token':token, 'source_watermark':context['binding']['watermark'],
                'presentation':presentation, 'markdown':markdown, 'language':language,
                'writes_performed':False, 'publication_ready':False,
                'manual_content_preserved':bool(preserved), 'preservation_scope':'EXPLICIT_SELECTED_RECORDS_ONLY',
                'current_source_files_verified':False, 'execution_authorized':False}
    finally:
        if owns_transaction and c.in_transaction:
            c.execute('ROLLBACK')
