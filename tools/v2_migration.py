"""Local legacy source preservation before semantic import; no authority switch.

Capsules contain original private control bytes and are not public export bundles.
Caller must authorize the source, local destination and data-retention scope.
"""
import hashlib
import json
import os
from pathlib import Path
from v2_evidence import _regular_path
from v2_legacy_reader import read_control,read_source_bytes,inspect_workspace,verify_inventory
from v2_state_store import _json,StateConflict,StateStore,SCHEMA_VERSION
from v2_governance import Governance
from contextlib import closing
import re
from v2_checkpoint_content import checkpoint_row,legacy_row
from v2_definition_content import decode as definition_value


def inventory_hash(inventory):
    return hashlib.sha256(_json(inventory).encode('utf-8')).hexdigest()


def definition_state_hash(connection):
    """Bind all initial state except separately versioned semantic review rows."""
    from v2_recovery import TABLES
    digests={}
    for table in TABLES:
        if table in {'migration_review','migration_adoption'}: continue
        digest=hashlib.sha256()
        for row in connection.execute(f'SELECT * FROM {table} ORDER BY 1'):
            digest.update((_json(list(row))+'\n').encode('utf-8'))
        digests[table]=digest.hexdigest()
    return inventory_hash(digests)


def legacy_control_context(store, *, project_id, role, source_id, section=None, json_field=None, max_characters=4096):
    if role not in {'PROJECT','PHASE','SESSION','PLAN','RESULT_CONTRACT','RESULT_EVENT','RESULT_PROJECTION',
                    'RESULT_CONTRACT_HISTORY','RESULT_EVENT_HISTORY','PHASE_BOUNDARY',
                    'ARTIFACT_SHARED_INDEX','ARTIFACT_ARCHIVE_INDEX','GROWTH_LEDGER','GROWTH_SIGNAL','GROWTH_CANDIDATE'}:
        raise ValueError('Unsupported legacy control role')
    if type(max_characters) is not int or not 1<=max_characters<=16384: raise ValueError('Invalid legacy text budget')
    if json_field is not None:
        if section is not None or not isinstance(json_field,str) or not json_field:
            raise ValueError('Choose exactly one named JSON field or Markdown section')
        if not (role.startswith('RESULT_') or role.startswith('GROWTH_') or role=='PHASE_BOUNDARY'):
            raise ValueError('Selected historical source is not a JSON record')
    c=store.connection
    c.execute('BEGIN')
    try:
        row=c.execute('''SELECT source_path,source_sha256,declared_status_json,evidence_state
            FROM legacy_control_source WHERE project_id=? AND role=? AND source_id=?''',(project_id,role,source_id)).fetchone()
        if row is None: raise StateConflict('No matching historical control in this project')
        record=read_control(store.path.parent/'legacy-source/controls',row[0])
        if record['sha256']!=row[1]: raise StateConflict('Historical source bytes changed')
        result={'project_id':project_id,'role':role,'source_id':source_id,'source_path':row[0],'source_sha256':row[1],
                'historical_status':json.loads(row[2]),'evidence_state':row[3],
                'sections':[r['name'] for r in record['sections']],'text_included':False,
                'execution_authorized':False,'current_recovery_authority':False,'writes_performed':False}
        if section is not None:
            matches=[r['text'] for r in record['sections'] if r['name']==section]
            if len(matches)!=1: raise StateConflict('Historical section is missing or ambiguous')
            result.update(text_included=True,section=section,text=matches[0][:max_characters],
                          text_characters=len(matches[0]),text_truncated=len(matches[0])>max_characters)
        if json_field is not None:
            def unique_fields(pairs):
                value={}
                for key,item in pairs:
                    if key in value: raise ValueError('Ambiguous historical JSON fields')
                    value[key]=item
                return value
            payload=json.loads(record['raw_bytes'].decode('utf-8-sig'),object_pairs_hook=unique_fields)
            if not isinstance(payload,dict) or json_field not in payload: raise StateConflict('Historical JSON field is missing')
            value=payload[json_field]
            encoded=_json(value)
            field_type='null' if value is None else {dict:'object',list:'array',str:'string',bool:'boolean',int:'number',float:'number'}[type(value)]
            result.update(text_included=True,json_field=json_field,field_type=field_type,text_format='JSON_VALUE_TEXT',
                          text=encoded[:max_characters],text_characters=len(encoded),text_truncated=len(encoded)>max_characters)
        c.execute('COMMIT')
        return result
    except BaseException:
        if c.in_transaction: c.execute('ROLLBACK')
        raise


def legacy_session_run_context(store, *, project_id, run_id, max_characters=4096):
    if type(max_characters) is not int or not 1<=max_characters<=16384: raise ValueError('Invalid historical context budget')
    c=store.connection
    owns_transaction=not c.in_transaction
    if owns_transaction:c.execute('BEGIN')
    try:
        run=c.execute('''SELECT r.* FROM execution_run r JOIN task t ON t.task_id=r.task_id
                         WHERE r.run_id=? AND t.project_id=?''',(run_id,project_id)).fetchone()
        audit=c.execute("SELECT details_json FROM execution_audit WHERE kind='LEGACY_SESSION_IMPORTED' AND subject_id=?",(run_id,)).fetchall()
        if run is None or len(audit)!=1: raise StateConflict('No unique historical Session Run for this project')
        details=json.loads(audit[0][0])
        if run!=(run_id,details['task_id'],1,'legacy-import',details['session_id'],'HISTORICAL_DECLARATION_ONLY','CLOSED',details['checkpoint_id']):
            raise StateConflict('Historical Run identity or closed state changed')
        source=c.execute("SELECT source_path,source_sha256 FROM legacy_control_source WHERE project_id=? AND role='SESSION' AND source_id=?",
                         (project_id,details['session_id'])).fetchone()
        if source!=(details['source_path'],details['source_sha256']): raise StateConflict('Historical Run source binding changed')
        parsed=read_control(store.path.parent/'legacy-source/controls',source[0])
        if parsed['sha256']!=source[1]: raise StateConflict('Historical Session source bytes changed')
        sections=[s for s in parsed['sections'] if s['name']=='session-checkpoint']
        if len(sections)!=1: raise StateConflict('Historical checkpoint section is ambiguous')
        summary=re.findall(r'^- Summary:[ \t]*([^\r\n]+)',sections[0]['text'],re.MULTILINE)
        action=re.findall(r'^- Next action:[ \t]*([^\r\n]+)',sections[0]['text'],re.MULTILINE)
        checkpoint=checkpoint_row(c,c.execute('SELECT * FROM checkpoint WHERE checkpoint_id=?',(run[7],)).fetchone())
        if len(summary)!=1 or len(action)!=1 or checkpoint!=(run[7],run_id,1,summary[0].strip(),action[0].strip(),'[]'):
            raise StateConflict('Historical checkpoint differs from original Session')
        result={'project_id':project_id,'run_id':run_id,'task_id':run[1],'task_revision':1,'state':'CLOSED',
                'checkpoint_id':run[7],'summary':checkpoint[3][:max_characters],'next_action':checkpoint[4][:max_characters],
                'text_truncated':len(checkpoint[3])>max_characters or len(checkpoint[4])>max_characters,
                'source':details,'evidence_state':'HISTORICAL_DECLARATION_ONLY','execution_authorized':False,
                'current_recovery_authority':False,'writes_performed':False}
        if owns_transaction:c.execute('COMMIT')
        return result
    except BaseException:
        if owns_transaction and c.in_transaction: c.execute('ROLLBACK')
        raise


def legacy_artifact_context(store, *, project_id, source_role, source_id, after_row=0, limit=20, max_bytes=16384):
    markers={'PHASE':'phase-artifacts','SESSION':'session-artifacts',
             'ARTIFACT_SHARED_INDEX':'shared-artifacts','ARTIFACT_ARCHIVE_INDEX':'archive-artifacts'}
    if source_role not in markers: raise ValueError('Unsupported Artifact source role')
    if (type(after_row) is not int or not 0<=after_row<2**63 or type(limit) is not int or not 1<=limit<=100 or
            type(max_bytes) is not int or not 256<=max_bytes<=1048576): raise ValueError('Invalid historical Artifact read budget')
    c=store.connection
    owns_transaction=not c.in_transaction
    if owns_transaction:c.execute('BEGIN')
    try:
        source=c.execute('SELECT source_path,source_sha256 FROM legacy_control_source WHERE project_id=? AND role=? AND source_id=?',
                         (project_id,source_role,source_id)).fetchone()
        if source is None: raise StateConflict('Historical Artifact source is absent from this project')
        original=read_control(store.path.parent/'legacy-source/controls',source[0])
        if original['sha256']!=source[1]: raise StateConflict('Historical Artifact source bytes changed')
        sections=[s for s in original['sections'] if s['name']==markers[source_role]]
        if len(sections)!=1: raise StateConflict('Historical Artifact registry is missing or ambiguous')
        reconstructed=historical_artifacts({'definitions':[{'role':source_role,'id':source_id,'archive_only':False,
            'source_path':source[0],'source_sha256':source[1],
            'fields':{'artifact_registry_source':{'text':sections[0]['text']}}}]})
        expected={r[2]:r for r in reconstructed['rows']}
        candidates=c.execute('''SELECT row_number,artifact_ref,fields_json,identity_valid,source_path,source_sha256,evidence_state
            FROM legacy_artifact_source WHERE project_id=? AND source_role=? AND source_id=? AND row_number>?
            ORDER BY row_number LIMIT ?''',(project_id,source_role,source_id,after_row,limit+1)).fetchall()
        if [r[0] for r in candidates]!=sorted(number for number in expected if number>after_row)[:limit+1]:
            raise StateConflict('Historical Artifact rows are absent or differ from the source page')
        rows=[]
        consumed=0
        cursor=after_row
        deferred=None
        for row in candidates[:limit]:
            if expected.get(row[0])!=(source_role,source_id,*row[:6]) or row[6]!='HISTORICAL_DECLARATION_ONLY':
                raise StateConflict('Historical Artifact row differs from original registry')
            item={'row_number':row[0],'artifact_ref':row[1],'fields':json.loads(row[2]),'identity_valid':bool(row[3])}
            size=len(_json(item).encode('utf-8'))
            if consumed+size>max_bytes:
                deferred=size
                break
            rows.append(item)
            consumed+=size
            cursor=row[0]
        has_more=deferred is not None or len(candidates)>limit
        session_mapping=None
        if source_role=='SESSION':
            run_ids=c.execute("""SELECT a.subject_id FROM execution_audit a
                JOIN task t ON t.task_id=json_extract(a.details_json,'$.task_id')
                WHERE a.kind='LEGACY_SESSION_IMPORTED' AND t.project_id=?
                AND json_extract(a.details_json,'$.session_id')=? LIMIT 2""",(project_id,source_id)).fetchall()
            if len(run_ids)>1:raise StateConflict('Historical Session mapping is ambiguous')
            if run_ids:
                mapped=legacy_session_run_context(store,project_id=project_id,run_id=run_ids[0][0],max_characters=1)
                session_mapping={key:mapped[key] for key in ('run_id','task_id','task_revision','checkpoint_id','state')}
                session_mapping['source_and_checkpoint_verified']=True
        result={'project_id':project_id,'source_role':source_role,'source_id':source_id,
                'source_path':source[0],'source_sha256':source[1],'rows':rows,'row_bytes':consumed,
                'has_more':has_more,'next_after_row':cursor if has_more else None,
                'minimum_deferred_row_bytes':deferred,'source_issue_count':len(reconstructed['issues']),
                'session_mapping':session_mapping,'native_artifact_enrollment':False,
                'source_bytes_verified':True,'returned_rows_revalidated':True,'evidence_state':'HISTORICAL_DECLARATION_ONLY',
                'execution_authorized':False,'current_recovery_authority':False,'writes_performed':False}
        if owns_transaction:c.execute('COMMIT')
        return result
    except BaseException:
        if owns_transaction and c.in_transaction: c.execute('ROLLBACK')
        raise


def stage_controls(source, destination, *, inventory, expected_inventory_sha256):
    source,destination=Path(source).absolute(),Path(destination).absolute()
    _regular_path(source)
    _regular_path(destination)
    from v2_management import validate_layout
    layout=validate_layout(source,capsule=destination,inventory=inventory,require_owned=True)
    if inventory_hash(inventory)!=expected_inventory_sha256:
        raise StateConflict('Reviewed inventory hash changed')
    if (any(r.get('identity_verification')!='MATCH' for r in inventory['records']) or
            verify_inventory(source,inventory)['decision']!='SOURCE_MATCH'):
        raise StateConflict('Source inventory is ambiguous, unverified or stale')
    if layout['layout']=='IN_WORKSPACE':destination.parent.mkdir(exist_ok=True)
    destination.mkdir()  # no overwrite, no recursive directory copying
    controls=destination/'controls'
    controls.mkdir()
    entries=[{'path':'runtime/workspace_control.json','sha256':inventory['index_sha256']},*inventory['records']]
    preserved=[]
    for entry in entries:
        record=read_source_bytes(source,entry['path'],max_bytes=16777216 if entry.get('role')=='SELECTED_PAYLOAD' else 1048576)
        if record['sha256']!=entry['sha256']: raise StateConflict('Control changed while preserving migration input')
        target=controls/record['path']
        _regular_path(target)
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:
            stream.write(record['raw_bytes'])
            stream.flush()
            os.fsync(stream.fileno())
        preserved.append({key:record[key] for key in ('path','sha256','bytes')})
    if verify_inventory(source,inventory)['decision']!='SOURCE_MATCH':
        raise StateConflict('Source drifted before capsule completion; retain partial capsule for inspection')
    manifest={'format':'malts.legacy-controls.capsule','version':1,'inventory_sha256':expected_inventory_sha256,
              'inventory':inventory,'files':preserved,'semantic_import_performed':False,'execution_authorized':False}
    with (destination/'manifest.json').open('x',encoding='utf-8') as stream:
        stream.write(_json(manifest))
        stream.flush()
        os.fsync(stream.fileno())
    verify_capsule(destination,expected_inventory_sha256=expected_inventory_sha256)
    return {'decision':'SOURCE_CONTROLS_STAGED','files':len(preserved),'semantic_import_performed':False,
            'execution_authorized':False,'source_writes_performed':False}


def verify_capsule(root, *, expected_inventory_sha256=None):
    root=Path(root).absolute()
    _regular_path(root/'manifest.json')
    def unique_fields(items):
        value={}
        for key,item in items:
            if key in value: raise ValueError('Duplicate capsule manifest field')
            value[key]=item
        return value
    manifest_record=read_control(root,'manifest.json',max_bytes=8388608)
    manifest=json.loads(manifest_record['raw_bytes'].decode('utf-8'),object_pairs_hook=unique_fields)
    fields={'format','version','inventory_sha256','inventory','files','semantic_import_performed','execution_authorized'}
    if (not isinstance(manifest,dict) or set(manifest)!=fields or manifest['format']!='malts.legacy-controls.capsule' or type(manifest['version']) is not int or manifest['version']!=1 or
            manifest['semantic_import_performed'] is not False or manifest['execution_authorized'] is not False):
        raise ValueError('Unsupported migration capsule')
    if inventory_hash(manifest['inventory'])!=manifest['inventory_sha256']: raise StateConflict('Capsule inventory hash mismatch')
    if expected_inventory_sha256 is not None and manifest['inventory_sha256']!=expected_inventory_sha256:
        raise StateConflict('Capsule does not match the independently reviewed source inventory')
    reviewed={'runtime/workspace_control.json':manifest['inventory']['index_sha256']}
    for record in manifest['inventory']['records']:
        if record['path'] in reviewed: raise ValueError('Duplicate reviewed control path')
        reviewed[record['path']]=record['sha256']
    if not isinstance(manifest['files'],list) or len(manifest['files'])!=len(reviewed):
        raise StateConflict('Capsule file set differs from reviewed inventory')
    expected={'manifest.json'}
    payload_paths=set(manifest['inventory'].get('payload_files',[]))
    for entry in manifest['files']:
        if not isinstance(entry,dict) or set(entry)!={'path','sha256','bytes'}: raise ValueError('Invalid capsule entry')
        if not isinstance(entry['path'],str) or reviewed.get(entry['path'])!=entry['sha256']:
            raise StateConflict('Capsule includes a file outside the reviewed inventory')
        record=read_source_bytes(root/'controls',entry['path'],max_bytes=16777216 if entry['path'] in payload_paths else 1048576)
        if record['sha256']!=entry['sha256'] or record['bytes']!=entry['bytes']: raise StateConflict('Capsule control bytes changed')
        key='controls/'+record['path']
        if key in expected: raise ValueError('Duplicate capsule file')
        expected.add(key)
    actual=set()
    for path in root.rglob('*'):
        _regular_path(path)
        if path.is_file(): actual.add(path.relative_to(root).as_posix())
    if actual!=expected: raise StateConflict('Capsule has missing or unexpected files')
    if verify_inventory(root/'controls',manifest['inventory'])['decision']!='SOURCE_MATCH':
        raise StateConflict('Preserved control inventory is inconsistent')
    return {'decision':'SOURCE_CAPSULE_VERIFIED','files':len(manifest['files']),
            'reviewed_source_hash_bound':expected_inventory_sha256 is not None,
            'semantic_import_performed':False,'execution_authorized':False}


def definition_sources(root, *, expected_inventory_sha256):
    """Source-linked extraction for review; never converts prose into commands.

    Returned text is private document data. Unknown sections are retained rather
    than dropped. Acceptance prose is not validated acceptance in the new store.
    """
    verify_capsule(root,expected_inventory_sha256=expected_inventory_sha256)
    manifest=json.loads((Path(root)/'manifest.json').read_text(encoding='utf-8'))
    if manifest['inventory_sha256']!=expected_inventory_sha256 or inventory_hash(manifest['inventory'])!=expected_inventory_sha256:
        raise StateConflict('Reviewed inventory changed before definition extraction')
    mappings={
        'PROJECT':{'user-original-goal':'original_goal','current-interpreted-goal':'current_goal',
                   'acceptance-criteria':'acceptance_source','completion-definition':'completion_definition',
                   'artifact-contract-index':'artifact_enrollment_source'},
        'PHASE':{'phase-goal':'goal','phase-boundary':'boundary_source','phase-plan-recheck':'plan_binding_source',
                 'phase-queue':'task_queue_source','phase-deliverables':'acceptance_source','phase-recovery':'recovery_source',
                 'phase-artifacts':'artifact_registry_source'},
        'SESSION':{'session-goal':'goal','session-recovery':'recovery_source',
                   'session-scope':'bounded_scope_source','session-checkpoint':'checkpoint_source',
                   'session-artifacts':'artifact_registry_source'},
        'ARTIFACT_SHARED_INDEX':{'shared-artifacts':'artifact_registry_source'},
        'ARTIFACT_ARCHIVE_INDEX':{'archive-artifacts':'artifact_registry_source'},
    }
    definitions=[]
    for entry in manifest['inventory']['records']:
        if entry['role']=='SELECTED_PAYLOAD':
            definitions.append({'role':entry['role'],'id':entry['id'],'source_path':entry['path'],
                                'source_sha256':entry['sha256'],'fields':{},'unmapped_sections':[],
                                'preamble':'','historical_status':{'preservation':'EXPLICIT_SELECTION_ONLY','bytes':entry['bytes']},
                                'archive_only':False,'target_acceptance_state':'NOT_VERIFIED'})
            continue
        parsed=read_control(Path(root)/'controls',entry['path'])
        archived='archive_only' in entry
        if parsed['sha256']!=entry['sha256'] or (parsed['duplicate_sections'] and not archived) or parsed['parse_issues']:
            raise StateConflict('Source changed or is ambiguous during definition extraction')
        known={} if archived else mappings.get(entry['role'],{})
        fields={}
        remaining=[]
        for section in parsed['sections']:
            value={'text':section['text'],'source_section':section['name'],
                   'start_character':section['start_character'],'end_character':section['end_character']}
            if section['name'] in known: fields[known[section['name']]]=value
            else: remaining.append(value)
        definitions.append({'role':entry['role'],'id':entry['id'],'source_path':entry['path'],
                            'source_sha256':parsed['sha256'],'fields':fields,'unmapped_sections':remaining,
                            'preamble':parsed['preamble'],'historical_status':entry.get('declared_status'),
                            'archive_only':archived,
                            'target_acceptance_state':'NOT_VERIFIED'})
    return {'decision':'DEFINITION_SOURCES_EXTRACTED','inventory_sha256':expected_inventory_sha256,
            'definitions':definitions,'writes_performed':False,'execution_authorized':False,
            'semantic_import_performed':False,'acceptance_mapping_requires_review':True}


def historical_checkpoints(sources):
    checkpoints=[]
    for source in sources['definitions']:
        if source['role']!='SESSION': continue
        section=source['fields'].get('checkpoint_source')
        if section is None or re.search(r'^ {0,3}(?:`{3,}|~{3,})',section['text'],re.MULTILINE): continue
        summary=re.findall(r'^- Summary:[ \t]*([^\r\n]+)',section['text'],re.MULTILINE)
        next_action=re.findall(r'^- Next action:[ \t]*([^\r\n]+)',section['text'],re.MULTILINE)
        if len(summary)!=1 or len(next_action)!=1: continue
        metadata=[v['text'] for v in source['unmapped_sections'] if v['source_section']=='session-metadata']
        phase=re.findall(r'^- Phase ID:[ \t]*([^\r\n]+)',metadata[0],re.MULTILINE) if len(metadata)==1 else []
        checkpoints.append((source['id'],phase[0].strip().strip('`') if len(phase)==1 else None,
                            summary[0].strip(),next_action[0].strip(),source['source_path'],source['source_sha256']))
    return checkpoints


def reviewed_session_runs(sources, mapping):
    """Map declared historical sessions without inventing a live host identity."""
    selected=mapping.get('sessions',[])
    if not isinstance(selected,list): raise ValueError('Session mapping must be a list')
    checkpoints={row[0]:row for row in historical_checkpoints(sources)}
    tasks={row['task_id']:row for row in mapping.get('tasks',[])}
    runs=[]
    records=[]
    audits=[]
    seen_sessions=set(); seen_runs=set(); seen_checkpoints=set()
    for row in selected:
        if not isinstance(row,dict) or set(row)!={'session_id','run_id','checkpoint_id','task_id','review_ref'}:
            raise ValueError('Invalid closed Session mapping')
        if any(not isinstance(v,str) or not v.strip() or len(v)>4096 for v in row.values()):
            raise ValueError('Session mapping requires bounded nonempty identities and review reference')
        session=checkpoints.get(row['session_id']); task=tasks.get(row['task_id'])
        if session is None or task is None or session[1]!=task['phase_id']:
            raise StateConflict('Session checkpoint and mapped Task must resolve to the same explicit source Phase')
        if row['session_id'] in seen_sessions or row['run_id'] in seen_runs or row['checkpoint_id'] in seen_checkpoints:
            raise StateConflict('Session mapping identities must be unique')
        if not session[2] or not session[3] or max(len(session[2]),len(session[3]))>4096:
            raise StateConflict('Historical checkpoint exceeds native checkpoint contract; preserve source for review')
        seen_sessions.add(row['session_id']); seen_runs.add(row['run_id']); seen_checkpoints.add(row['checkpoint_id'])
        runs.append((row['run_id'],row['task_id'],1,'legacy-import',row['session_id'],'HISTORICAL_DECLARATION_ONLY','CLOSED',row['checkpoint_id']))
        records.append((row['checkpoint_id'],row['run_id'],1,session[2],session[3],'[]'))
        audits.append((row['run_id'],{'session_id':row['session_id'],'task_id':row['task_id'],'task_revision':1,
            'checkpoint_id':row['checkpoint_id'],'source_path':session[4],'source_sha256':session[5],
            'review_ref':row['review_ref'],'legacy_writer_state':'NOT_VERIFIED','legacy_pending_effects':'NOT_RECONCILED'}))
    return runs,records,audits


def historical_artifacts(sources, *, max_rows=10000):
    """Parse legacy table syntax only; no locator I/O or current acceptance."""
    from workspace_artifacts import _table,OWNER_HEADERS,SHARED_HEADERS,ARCHIVE_HEADERS,ARTIFACT_REF
    if type(max_rows) is not int or not 1<=max_rows<=100000: raise ValueError('Invalid historical Artifact row budget')
    rows=[]
    issues=[]
    for source in sources['definitions']:
        section=source['fields'].get('artifact_registry_source')
        if section is None or source['archive_only']: continue
        role=source['role']
        if role in {'PHASE','SESSION'}: owner=role.lower()+':'+source['id']; headers=OWNER_HEADERS
        elif role=='ARTIFACT_SHARED_INDEX': owner='shared'; headers=SHARED_HEADERS
        elif role=='ARTIFACT_ARCHIVE_INDEX': owner='archive'; headers=ARCHIVE_HEADERS
        else: continue
        try:
            if re.search(r'^ {0,3}(?:`{3,}|~{3,})',section['text'],re.MULTILINE): raise ValueError('Fenced registry')
            parsed=_table(section['text'],headers)
        except ValueError:
            issues.append({'code':'UNPARSED_ARTIFACT_REGISTRY','role':role,'id':source['id']})
            continue
        if len(rows)+len(parsed)>max_rows: raise ValueError('Historical Artifact row budget exceeded')
        counts={}
        for row in parsed: counts[row[headers[0]]]=counts.get(row[headers[0]],0)+1
        for number,row in enumerate(parsed,1):
            local_id=row[headers[0]]
            reference=owner+':'+local_id
            valid=ARTIFACT_REF.fullmatch(reference) is not None and counts[local_id]==1
            if not valid: issues.append({'code':'AMBIGUOUS_ARTIFACT_ID','role':role,'id':source['id'],'row':number})
            rows.append((role,source['id'],number,reference,_json(row),int(valid),source['source_path'],source['source_sha256']))
    return {'rows':rows,'issues':issues,'payloads_copied':False,'current_acceptance_created':False}


def reviewed_task_source(task, source_phases, source_contracts):
    identity=task['task_id']
    phase=source_phases.get(task['phase_id'])
    if phase is None: raise StateConflict('Task Phase source is missing')
    contract=source_contracts.get(identity)
    if contract is not None:
        status=contract['historical_status']
        if not isinstance(status,dict) or status.get('phase_id')!=task['phase_id']:
            raise StateConflict('Task contract belongs to a different source Phase')
        return {'source_path':contract['source_path'],'source_sha256':contract['source_sha256'],
                'source_role':'RESULT_CONTRACT','source_revision_id':status['latest_contract_revision']['revision_id'],
                'lineage_id':status['lineage_id'],'historical_acceptance':'NOT_IMPORTED'}
    queue=phase['fields'].get('task_queue_source')
    if queue is None or re.search(r'^ {0,3}(?:`{3,}|~{3,})',queue['text'],re.MULTILINE):
        raise StateConflict('Task requires a verified Result Contract or unambiguous source queue')
    if not re.search(r'^\|\s*`?'+re.escape(identity)+r'`?\s*\|',queue['text'],re.MULTILINE):
        raise StateConflict('Task ID is absent from its source Phase queue')
    return {'source_path':phase['source_path'],'source_sha256':phase['source_sha256'],
            'source_section':queue['source_section'],'historical_acceptance':'NOT_IMPORTED'}


def import_definitions(capsule, destination, *, expected_inventory_sha256, mapping, expected_mapping_sha256, _retry_from=None):
    """Import reviewed definitions only into a new quarantined candidate store.

    Existing source/target state is never overwritten. Partial targets remain for
    inspection; state.db is published only after archive/definitions/receipt pass.
    """
    from v2_contracts import criteria,phase_boundary
    capsule,destination=Path(capsule).absolute(),Path(destination).absolute()
    _regular_path(capsule);_regular_path(destination)
    if capsule.resolve().is_relative_to(destination.resolve()) or destination.resolve().is_relative_to(capsule.resolve()):
        raise StateConflict('CAPSULE_AND_STATE_MUST_BE_SEPARATE')
    if destination.parent.name=='.malts':
        from v2_management import validate_layout
        verify_capsule(capsule,expected_inventory_sha256=expected_inventory_sha256)
        manifest=json.loads((capsule/'manifest.json').read_text(encoding='utf-8'))
        validate_layout(destination.parent.parent,capsule=capsule,state=destination,
                        inventory=manifest['inventory'],require_owned=True)
    if inventory_hash(mapping)!=expected_mapping_sha256: raise StateConflict('Reviewed definition mapping changed')
    sources=definition_sources(capsule,expected_inventory_sha256=expected_inventory_sha256)
    artifacts=historical_artifacts(sources)
    if (not isinstance(mapping,dict) or not {'project','phases','authority_ref'}.issubset(mapping) or
            not set(mapping).issubset({'project','phases','authority_ref','tasks','sessions'})):
        raise ValueError('Expected a closed reviewed definition mapping')
    project=mapping['project']
    if not isinstance(project,dict) or set(project)!={'project_id','goal','acceptance'}: raise ValueError('Invalid Project mapping')
    source_projects=[r for r in sources['definitions'] if r['role']=='PROJECT']
    if len(source_projects)!=1 or project['project_id']!=source_projects[0]['id']: raise StateConflict('Project source ID mismatch')
    original=source_projects[0]['fields'].get('original_goal')
    if original is None or not original['text'].strip(): raise StateConflict('Explicit original-goal source mapping is required')
    if not isinstance(mapping['authority_ref'],str) or not mapping['authority_ref'].strip(): raise ValueError('Mapping authority reference required')
    if not isinstance(project['goal'],str) or not project['goal'].strip(): raise ValueError('Project goal required')
    criteria(project['acceptance'])
    phases=mapping['phases']
    if not isinstance(phases,list): raise ValueError('Phase mappings must be a list')
    source_ids={r['id'] for r in sources['definitions'] if r['role']=='PHASE' and not r['archive_only']}
    seen=set()
    for phase in phases:
        if not isinstance(phase,dict) or set(phase)!={'phase_id','goal','boundary','acceptance','plan_text'}:
            raise ValueError('Invalid Phase mapping')
        identity=phase['phase_id']
        if not isinstance(identity,str) or re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',identity) is None or identity in seen:
            raise ValueError('Invalid or duplicate Phase ID')
        seen.add(identity)
        if not isinstance(phase['goal'],str) or not phase['goal'].strip(): raise ValueError('Reviewed Phase goal required')
        phase_boundary(phase['boundary'])
        if not isinstance(phase['plan_text'],str) or not phase['plan_text'].strip(): raise ValueError('Reviewed plan text is required')
        criteria(phase['acceptance'])
    if seen!=source_ids: raise StateConflict('Reviewed mapping must explicitly cover all source Phase IDs')
    tasks=mapping.get('tasks',[])
    if not isinstance(tasks,list): raise ValueError('Task mappings must be a list')
    task_ids=set()
    task_sources={}
    source_phases={r['id']:r for r in sources['definitions'] if r['role']=='PHASE' and not r['archive_only']}
    source_contracts={r['id']:r for r in sources['definitions'] if r['role']=='RESULT_CONTRACT'}
    target_phases={r['phase_id']:r for r in phases}
    for task in tasks:
        if not isinstance(task,dict) or set(task)!={'task_id','phase_id','goal','scope','acceptance','dependencies'}:
            raise ValueError('Invalid reviewed Task mapping')
        identity=task['task_id']
        if not isinstance(identity,str) or re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',identity) is None or identity in task_ids:
            raise ValueError('Invalid or duplicate Task ID')
        task_ids.add(identity)
        if not isinstance(task['phase_id'],str) or task['phase_id'] not in source_phases: raise StateConflict('Task Phase source is missing')
        task_sources[identity]=reviewed_task_source(task,source_phases,source_contracts)
        if not isinstance(task['goal'],str) or not task['goal'].strip(): raise ValueError('Task goal required')
        scope=task['scope']
        if not isinstance(scope,list) or not scope or any(not isinstance(v,str) or not v.strip() for v in scope) or len(set(scope))!=len(scope): raise ValueError('Invalid Task scope')
        boundary=target_phases[task['phase_id']]['boundary']
        if not set(scope).issubset(boundary['in_scope']) or set(scope).intersection(boundary['out_of_scope']): raise StateConflict('Imported Task exceeds reviewed Phase scope')
        criteria(task['acceptance'])
        if not isinstance(task['dependencies'],list) or any(not isinstance(v,str) for v in task['dependencies']) or len(set(task['dependencies']))!=len(task['dependencies']): raise ValueError('Invalid Task dependencies')
    for task in tasks:
        if task['task_id'] in task['dependencies'] or not set(task['dependencies']).issubset(task_ids): raise StateConflict('Imported dependencies must reference distinct mapped Tasks')
    historical_runs,run_checkpoints,run_audits=reviewed_session_runs(sources,mapping)
    _regular_path(destination)
    if destination.resolve().is_relative_to(capsule.resolve()) or capsule.resolve().is_relative_to(destination.resolve()):
        raise ValueError('Import target must be separate from source capsule')
    destination.mkdir()
    attempt={'format':'malts.definition-import-attempt','version':1,
             'inventory_sha256':expected_inventory_sha256,'mapping_sha256':expected_mapping_sha256,
             'destination':str(destination),'retry_from':_retry_from}
    with (destination/'import-attempt.json').open('x',encoding='utf-8') as stream:
        stream.write(_json(attempt)); stream.flush(); os.fsync(stream.fileno())
    archive=destination/'legacy-source'
    archive.mkdir()
    manifest=json.loads((capsule/'manifest.json').read_text(encoding='utf-8'))
    if inventory_hash(manifest['inventory'])!=expected_inventory_sha256: raise StateConflict('Capsule changed during import')
    paths=['manifest.json','controls/runtime/workspace_control.json',*['controls/'+r['source_path'] for r in sources['definitions']]]
    for relative in paths:
        source_path=capsule/relative
        _regular_path(source_path)
        target=archive/relative
        _regular_path(target)
        target.parent.mkdir(parents=True,exist_ok=True)
        with source_path.open('rb') as src,target.open('xb') as dst:
            for block in iter(lambda:src.read(65536),b''): dst.write(block)
            dst.flush()
            os.fsync(dst.fileno())
    verify_capsule(archive,expected_inventory_sha256=expected_inventory_sha256)
    with (destination/'reviewed-mapping.json').open('x',encoding='utf-8') as stream:
        stream.write(_json(mapping)); stream.flush(); os.fsync(stream.fileno())
    (destination/'blobs').mkdir()
    plans=destination/'plans'
    plans.mkdir()
    pending=destination/'state.importing.db'
    with closing(StateStore.initialize(pending,project['project_id'],original['text'],resource_root=destination)) as store:
        governance=Governance(store)
        governance.define_project(**project,expected_revision=0,authority_ref=mapping['authority_ref'],request_id='import-project')
        for phase in phases:
            # IDs are case-sensitive database identities, not safe Windows file
            # names. Hash-derived names avoid device aliases and case collisions.
            plan=plans/(hashlib.sha256(phase['phase_id'].encode('utf-8')).hexdigest()+'.md')
            with plan.open('x',encoding='utf-8',newline='') as stream:
                stream.write(phase['plan_text'])
                stream.flush()
                os.fsync(stream.fileno())
            governance.define_phase(phase_id=phase['phase_id'],project_id=project['project_id'],project_revision=1,expected_revision=0,
                goal=phase['goal'],boundary=phase['boundary'],acceptance=phase['acceptance'],plan_ref=plan.relative_to(destination).as_posix(),
                plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),authority_ref=mapping['authority_ref'],request_id='import-'+phase['phase_id'],plan_scope='STATE')
        for task in tasks:
            store.revise_task(task_id=task['task_id'],project_id=project['project_id'],expected_revision=0,
                             goal=task['goal'],scope=task['scope'],acceptance=task['acceptance'],request_id='import-task-'+task['task_id'])
            governance.bind_task(task_id=task['task_id'],task_revision=1,phase_id=task['phase_id'],phase_revision=1,authority_ref=mapping['authority_ref'])
        for task in tasks:
            for predecessor in task['dependencies']:
                store.add_dependency(task_id=task['task_id'],task_revision=1,predecessor_id=predecessor,predecessor_revision=1)
        with store.transaction() as c:
            c.executemany('INSERT INTO legacy_control_source VALUES (?,?,?,?,?,?,?)',
                [(project['project_id'],source['role'],source['id'],source['source_path'],source['source_sha256'],
                  _json(source['historical_status']),'HISTORICAL_DECLARATION_ONLY') for source in sources['definitions']])
            c.executemany('INSERT INTO legacy_checkpoint VALUES (?,?,?,?,?,?,?)',
                          [legacy_row((project['project_id'],*checkpoint),protect=True) for checkpoint in historical_checkpoints(sources)])
            c.executemany('INSERT INTO legacy_artifact_source VALUES (?,?,?,?,?,?,?,?,?,?)',
                          [(project['project_id'],*row,'HISTORICAL_DECLARATION_ONLY') for row in artifacts['rows']])
            c.executemany('INSERT INTO execution_run VALUES (?,?,?,?,?,?,?,?)',historical_runs)
            c.executemany('INSERT INTO checkpoint VALUES (?,?,?,?,?,?)',[checkpoint_row(c,row,protect=True) for row in run_checkpoints])
            c.executemany('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                          [('LEGACY_SESSION_IMPORTED',identity,_json(data)) for identity,data in run_audits])
            c.execute("UPDATE task SET status='PAUSED'")
            c.execute('UPDATE recovery_state SET reconciliation_required=1')
            c.execute('INSERT INTO migration_barrier VALUES (1,?)',(_json(['Task','Session','Growth','Artifact']),))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('DEFINITIONS_IMPORTED',project['project_id'],_json({'inventory_sha256':expected_inventory_sha256,'mapping_sha256':expected_mapping_sha256,'task_sources':task_sources})))
        if store.connection.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or store.connection.execute('PRAGMA foreign_key_check').fetchall():
            raise StateConflict('Imported definition database integrity failed')
        semantic_state_sha256=definition_state_hash(store.connection)
    receipt={'format':'malts.definition-import','schema':SCHEMA_VERSION,'inventory_sha256':expected_inventory_sha256,
             'mapping_sha256':expected_mapping_sha256,'database_sha256':hashlib.sha256(pending.read_bytes()).hexdigest(),
             'project_id':project['project_id'],'phase_count':len(phases),'imported_task_count':len(tasks),'task_sources':task_sources,'migration_complete':False,
             'historical_artifact_rows':len(artifacts['rows']),'artifact_source_issues':artifacts['issues'],
             'unmapped_domains':['Task','Session','Growth','Artifact'],'execution_authorized':False,
             'attempt':attempt,'semantic_state_sha256':semantic_state_sha256}
    with (destination/'definition-import.json').open('x',encoding='utf-8') as stream:
        stream.write(_json(receipt)); stream.flush(); os.fsync(stream.fileno())
    finalize_definition_import(destination,expected_inventory_sha256=expected_inventory_sha256,
                               expected_mapping_sha256=expected_mapping_sha256,apply=True)
    return {'decision':'DEFINITIONS_IMPORTED_QUARANTINED',**receipt}


def verify_definition_import(root, *, expected_inventory_sha256, expected_mapping_sha256, _database_name='state.db', _with_semantic_reviews=False):
    """Verify an untouched definition-import snapshot, not later execution state."""
    from v2_contracts import criteria,phase_boundary
    root=Path(root).absolute()
    if _database_name not in {'state.db','state.importing.db'}: raise ValueError('Invalid import database name')
    database=root/_database_name
    _regular_path(database)
    receipt=json.loads(read_control(root,'definition-import.json')['raw_bytes'].decode('utf-8'))
    mapping=json.loads(read_control(root,'reviewed-mapping.json',max_bytes=8388608)['raw_bytes'].decode('utf-8'))
    if (receipt.get('inventory_sha256')!=expected_inventory_sha256 or
            receipt.get('mapping_sha256')!=expected_mapping_sha256 or inventory_hash(mapping)!=expected_mapping_sha256 or
            receipt.get('schema')!=SCHEMA_VERSION or receipt.get('migration_complete') is not False):
        raise StateConflict('Imported snapshot does not match reviewed mapping and source')
    if 'attempt' in receipt:
        attempt=receipt['attempt']
        if (not isinstance(attempt,dict) or set(attempt)!={'format','version','inventory_sha256','mapping_sha256','destination','retry_from'} or
                attempt['format']!='malts.definition-import-attempt' or type(attempt['version']) is not int or attempt['version']!=1 or
                attempt['inventory_sha256']!=expected_inventory_sha256 or attempt['mapping_sha256']!=expected_mapping_sha256 or
                attempt['destination']!=str(root)):
            raise StateConflict('Import attempt provenance does not match the snapshot')
        if (root/'import-attempt.json').exists():
            recorded=json.loads(read_control(root,'import-attempt.json')['raw_bytes'].decode('utf-8'))
            if recorded!=attempt: raise StateConflict('Import attempt record differs from its completion receipt')
    if not _with_semantic_reviews and hashlib.sha256(database.read_bytes()).hexdigest()!=receipt['database_sha256']:
        raise StateConflict('Definition database changed after its import receipt')
    sources=definition_sources(root/'legacy-source',expected_inventory_sha256=expected_inventory_sha256)
    artifacts=historical_artifacts(sources)
    original=next(r for r in sources['definitions'] if r['role']=='PROJECT')['fields']['original_goal']['text']
    eligible_phases={r['id'] for r in sources['definitions'] if r['role']=='PHASE' and not r['archive_only']}
    if {r['phase_id'] for r in mapping['phases']}!=eligible_phases:
        raise StateConflict('Phase mapping does not match non-archived source controls')
    project=mapping['project']
    with closing(StateStore(database,readonly=True)) as store:
        c=store.connection
        if _with_semantic_reviews and definition_state_hash(c)!=receipt.get('semantic_state_sha256'):
            raise StateConflict('Definition state changed outside semantic review records')
        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA foreign_key_check').fetchall(): raise StateConflict('Imported database integrity failed')
        original_rows=c.execute('SELECT project_id,original_goal FROM project').fetchall()
        if [(identity,definition_value(value,identity,'project-original',identity,0,'goal')) for identity,value in original_rows]!=[(project['project_id'],original)]: raise StateConflict('Imported Project identity or original goal mismatch')
        expected_sources={(project['project_id'],source['role'],source['id'],source['source_path'],source['source_sha256'],
                           _json(source['historical_status']),'HISTORICAL_DECLARATION_ONLY') for source in sources['definitions']}
        if set(c.execute('SELECT * FROM legacy_control_source').fetchall())!=expected_sources:
            raise StateConflict('Legacy control provenance does not match source capsule')
        if {legacy_row(row) for row in c.execute('SELECT * FROM legacy_checkpoint').fetchall()}!={(project['project_id'],*checkpoint) for checkpoint in historical_checkpoints(sources)}:
            raise StateConflict('Historical checkpoint fields do not match original source')
        if (set(c.execute('SELECT * FROM legacy_artifact_source').fetchall())!=
                {(project['project_id'],*row,'HISTORICAL_DECLARATION_ONLY') for row in artifacts['rows']} or
                receipt.get('historical_artifact_rows')!=len(artifacts['rows']) or receipt.get('artifact_source_issues')!=artifacts['issues']):
            raise StateConflict('Historical Artifact rows do not match original sources')
        resource_root=c.execute('SELECT resource_root FROM project WHERE project_id=?',(project['project_id'],)).fetchone()[0]
        if Path(resource_root).resolve()!=root.resolve(): raise StateConflict('Imported resource root does not match the reviewed target')
        if c.execute('SELECT count(*) FROM project_revision').fetchone()[0]!=1: raise StateConflict('Unexpected Project revision history in definition import')
        row=c.execute('SELECT goal,acceptance_json FROM project_revision WHERE project_id=? AND revision=1',(project['project_id'],)).fetchone()
        if row is None or (definition_value(row[0],project['project_id'],'project',project['project_id'],1,'goal'),
                           definition_value(row[1],project['project_id'],'project',project['project_id'],1,'acceptance'))!=(project['goal'],criteria(project['acceptance'])): raise StateConflict('Imported Project definition mismatch')
        if {r[0] for r in c.execute('SELECT phase_id FROM phase')}!={r['phase_id'] for r in mapping['phases']}: raise StateConflict('Imported Phase set mismatch')
        if c.execute('SELECT count(*) FROM phase_revision').fetchone()[0]!=len(mapping['phases']): raise StateConflict('Unexpected Phase revisions in definition import')
        for phase in mapping['phases']:
            if c.execute('SELECT plan_scope FROM phase_revision WHERE phase_id=? AND revision=1',(phase['phase_id'],)).fetchone()!=('STATE',):
                raise StateConflict('Imported plan ownership changed')
            row=c.execute('''SELECT p.state,r.goal,r.boundary_json,r.acceptance_json,r.plan_ref,r.plan_sha256
                FROM phase p JOIN phase_revision r ON r.phase_id=p.phase_id AND r.revision=p.revision WHERE p.phase_id=?''',(phase['phase_id'],)).fetchone()
            if (row[0],*[definition_value(row[i],project['project_id'],'phase',phase['phase_id'],1,field)
                          for i,field in ((1,'goal'),(2,'boundary'),(3,'acceptance'))])!=('PLANNED',phase['goal'],phase_boundary(phase['boundary']),criteria(phase['acceptance'])): raise StateConflict('Imported Phase definition mismatch')
            if c.execute('SELECT revision,project_revision FROM phase_revision WHERE phase_id=?',(phase['phase_id'],)).fetchone()!=(1,1): raise StateConflict('Imported Phase revision binding mismatch')
            plan=read_control(root,row[4])
            if plan['raw_bytes']!=phase['plan_text'].encode('utf-8') or plan['sha256']!=row[5]: raise StateConflict('Imported plan content mismatch')
        tasks=mapping.get('tasks',[])
        source_phases={r['id']:r for r in sources['definitions'] if r['role']=='PHASE' and not r['archive_only']}
        source_contracts={r['id']:r for r in sources['definitions'] if r['role']=='RESULT_CONTRACT'}
        expected_task_sources={task['task_id']:reviewed_task_source(task,source_phases,source_contracts) for task in tasks}
        if receipt.get('task_sources')!=expected_task_sources: raise StateConflict('Imported Task source receipt mismatch')
        expected_audit={'inventory_sha256':expected_inventory_sha256,'mapping_sha256':expected_mapping_sha256,
                        'task_sources':expected_task_sources}
        if c.execute("SELECT subject_id,details_json FROM execution_audit WHERE kind='DEFINITIONS_IMPORTED'").fetchall()!=[(project['project_id'],_json(expected_audit))]:
            raise StateConflict('Imported Task source audit mismatch')
        if {r[0] for r in c.execute('SELECT task_id FROM task')}!={r['task_id'] for r in tasks}: raise StateConflict('Imported Task set mismatch')
        if c.execute('SELECT count(*) FROM task_revision').fetchone()[0]!=len(tasks): raise StateConflict('Unexpected Task revisions in definition import')
        for task in tasks:
            current=store.task(task['task_id'])
            if (current['revision']!=1 or current['status']!='PAUSED' or current['goal']!=task['goal'] or
                    current['scope']!=task['scope'] or current['acceptance']!=criteria(task['acceptance'])): raise StateConflict('Imported Task definition mismatch')
            if c.execute('SELECT phase_id,phase_revision FROM phase_task WHERE task_id=? AND task_revision=1',(task['task_id'],)).fetchone()!=(task['phase_id'],1): raise StateConflict('Imported Task Phase mismatch')
            edges=c.execute('SELECT predecessor_id,predecessor_revision FROM dependency WHERE task_id=? AND task_revision=1',(task['task_id'],)).fetchall()
            if set(edges)!={(identity,1) for identity in task['dependencies']}: raise StateConflict('Imported dependency mismatch')
        if set(store.pending_migration_domains())!={'Task','Session','Growth','Artifact'} or not c.execute('SELECT reconciliation_required FROM recovery_state').fetchone()[0]: raise StateConflict('Import barriers are missing or incomplete')
        historical_runs,run_checkpoints,run_audits=reviewed_session_runs(sources,mapping)
        if (set(c.execute('SELECT * FROM execution_run').fetchall())!=set(historical_runs) or
                {checkpoint_row(c,row) for row in c.execute('SELECT * FROM checkpoint').fetchall()}!=set(run_checkpoints) or
                set(c.execute("SELECT subject_id,details_json FROM execution_audit WHERE kind='LEGACY_SESSION_IMPORTED'").fetchall())!=
                {(identity,_json(data)) for identity,data in run_audits}):
            raise StateConflict('Historical Run/Checkpoint mapping differs from reviewed Session sources')
        for table in ('execution_grant','operation','acceptance','phase_completion','project_completion',
                      'task_budget','project_budget','growth_candidate','growth_trial','growth_outcome','growth_lifecycle'):
            if c.execute(f'SELECT count(*) FROM {table}').fetchone()[0]: raise StateConflict('Definition import contains unexpected execution state')
    return {'decision':'DEFINITION_IMPORT_VERIFIED','migration_complete':False,'execution_authorized':False,
            'project_id':project['project_id'],'phase_count':len(mapping['phases']),'task_count':len(tasks),'writes_performed':False}


class MigrationReview:
    """Source-complete semantic disposition, separate from Host cutover approval."""
    def __init__(self,store): self.store=store

    def _plan(self,report,inventory_sha256,mapping_sha256):
        from v2_recovery import Recovery
        if not isinstance(report,dict) or set(report)!={'review_id','authority_ref','dispositions'}:
            raise ValueError('Expected a closed semantic review report')
        for key in ('review_id','authority_ref'):
            if not isinstance(report[key],str) or not report[key].strip() or len(report[key])>4096:
                raise ValueError('Review identity and authority reference are required')
        root=self.store.path.parent
        verify_definition_import(root,expected_inventory_sha256=inventory_sha256,
                                 expected_mapping_sha256=mapping_sha256,_with_semantic_reviews=True)
        mapping=json.loads(read_control(root,'reviewed-mapping.json',max_bytes=8388608)['raw_bytes'].decode('utf-8'))
        receipt=json.loads(read_control(root,'definition-import.json')['raw_bytes'].decode('utf-8'))
        project_id=mapping['project']['project_id']
        source_rows=self.store.connection.execute('SELECT role,source_id,source_sha256 FROM legacy_control_source WHERE project_id=?',
                                                  (project_id,)).fetchall()
        expected={(role,identity):digest for role,identity,digest in source_rows}
        rows=report['dispositions']
        if not isinstance(rows,list) or len(rows)!=len(expected): raise StateConflict('Review must cover every imported source exactly once')
        targets={('PROJECT',project_id):[{'type':'Project','id':project_id,'revision':1}]}
        for phase in mapping['phases']: targets[('PHASE',phase['phase_id'])]=[{'type':'Phase','id':phase['phase_id'],'revision':1}]
        for task in mapping.get('tasks',[]):
            source=receipt['task_sources'][task['task_id']]
            match=self.store.connection.execute('SELECT role,source_id FROM legacy_control_source WHERE project_id=? AND source_path=?',
                                                 (project_id,source['source_path'])).fetchone()
            if match: targets.setdefault(tuple(match),[]).append({'type':'Task','id':task['task_id'],'revision':1})
        for session in mapping.get('sessions',[]):
            targets[('SESSION',session['session_id'])]=[{'type':'Run','id':session['run_id'],'state':'CLOSED'},
                                                      {'type':'Checkpoint','id':session['checkpoint_id']}]
        seen=set(); decisions=[]; unresolved=[]
        for row in rows:
            if not isinstance(row,dict) or set(row)!={'role','source_id','source_sha256','disposition','reason'}:
                raise ValueError('Invalid source disposition fields')
            if any(not isinstance(v,str) or not v.strip() or len(v)>4096 for v in row.values()):
                raise ValueError('Disposition values must be bounded nonempty text')
            key=(row['role'],row['source_id'])
            if key in seen or expected.get(key)!=row['source_sha256']: raise StateConflict('Source disposition is duplicated, unknown or stale')
            seen.add(key)
            action=row['disposition']; mapped=targets.get(key,[])
            if action not in {'ACCEPT_MAPPED','PRESERVE_HISTORY','UNRESOLVED'}: raise ValueError('Unknown source disposition')
            if action=='ACCEPT_MAPPED' and not mapped: raise StateConflict('Source has no verified native target mapping')
            if action=='PRESERVE_HISTORY' and mapped: raise StateConflict('Mapped current definitions cannot be disguised as history only')
            if action=='UNRESOLVED': unresolved.append({'role':key[0],'source_id':key[1]})
            decisions.append({**row,'verified_targets':mapped})
        binding=Recovery(self.store)._inventory(self.store.connection)['binding']
        result={'decision':'SEMANTIC_REVIEW_UNRESOLVED' if unresolved else 'SEMANTIC_REVIEW_READY_TO_RECORD',
                'review_id':report['review_id'],'project_id':project_id,'binding':binding,
                'inventory_sha256':inventory_sha256,'mapping_sha256':mapping_sha256,'report_sha256':inventory_hash(report),
                'dispositions':sorted(decisions,key=lambda row:(row['role'],row['source_id'])),'unresolved_sources':unresolved,
                'host_cutover_verified':False,'migration_complete':False,'execution_authorized':False,'writes_performed':False}
        result['plan_sha256']=inventory_hash(result)
        return result

    def plan(self,report,*,inventory_sha256,mapping_sha256):
        c=self.store.connection; c.execute('BEGIN')
        try:
            result=self._plan(report,inventory_sha256,mapping_sha256)
            c.execute('COMMIT'); return result
        except BaseException:
            if c.in_transaction: c.execute('ROLLBACK')
            raise

    def apply(self,report,*,inventory_sha256,mapping_sha256,expected_plan_sha256):
        request_sha=inventory_hash(report)
        if not isinstance(report,dict) or not isinstance(report.get('review_id'),str): raise ValueError('Review ID required')
        with self.store.transaction() as c:
            old=c.execute('SELECT epoch,inventory_sha256,mapping_sha256,request_sha256,plan_sha256,receipt_json FROM migration_review WHERE review_id=?',
                          (report['review_id'],)).fetchone()
            epoch=c.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]
            if old:
                if old[:5]!=(epoch,inventory_sha256,mapping_sha256,request_sha,expected_plan_sha256):
                    raise StateConflict('Semantic review replay conflicts or belongs to another recovery epoch')
                return {**json.loads(old[5]),'replayed':True,'writes_performed':False,'sources_revalidated':False}
            plan=self._plan(report,inventory_sha256,mapping_sha256)
            if plan['plan_sha256']!=expected_plan_sha256: raise StateConflict('Semantic review plan changed')
            receipt={**plan,'decision':'SEMANTIC_REVIEW_RECORDED','writes_performed':True,'sources_revalidated':True}
            c.execute('INSERT INTO migration_review VALUES (?,?,?,?,?,?,?,?,?)',
                (report['review_id'],plan['project_id'],epoch,inventory_sha256,mapping_sha256,request_sha,expected_plan_sha256,_json(report),_json(receipt)))
            return receipt


def retry_definition_import(capsule, failed_target, destination, *, expected_inventory_sha256, mapping,
                            expected_mapping_sha256, writer_stopped_ref, expected_failed_sha256=None, apply=False):
    """Rebuild an early failed import into a fresh target, preserving its evidence.

    The stop reference is an operator declaration, not process-liveness proof.
    Only reviewed source data are replayed; partial database state is not trusted.
    """
    if type(apply) is not bool: raise ValueError('Apply must be an explicit boolean')
    if not isinstance(writer_stopped_ref,str) or not writer_stopped_ref.strip():
        raise ValueError('Stopped writer evidence reference is required')
    capsule,failed_target,destination=map(lambda p:Path(p).absolute(),(capsule,failed_target,destination))
    for path in (capsule,failed_target,destination): _regular_path(path)
    for left,right in ((failed_target,destination),(capsule,destination),(capsule,failed_target)):
        if left.resolve().is_relative_to(right.resolve()) or right.resolve().is_relative_to(left.resolve()):
            raise ValueError('Retry source, failed target and new target must be separate directories')
    if destination.exists(): raise FileExistsError(destination)
    if (failed_target/'state.db').exists() or (failed_target/'definition-import.json').exists():
        raise StateConflict('Prepared or published import requires finalization review, not early retry')
    attempt=json.loads(read_control(failed_target,'import-attempt.json')['raw_bytes'].decode('utf-8'))
    if (not isinstance(attempt,dict) or set(attempt)!={'format','version','inventory_sha256','mapping_sha256','destination','retry_from'} or
            attempt['format']!='malts.definition-import-attempt' or type(attempt['version']) is not int or attempt['version']!=1 or
            attempt['destination']!=str(failed_target) or attempt['inventory_sha256']!=expected_inventory_sha256 or
            attempt['mapping_sha256']!=expected_mapping_sha256 or inventory_hash(mapping)!=expected_mapping_sha256):
        raise StateConflict('Failed attempt does not match reviewed source, mapping and original target')
    verify_capsule(capsule,expected_inventory_sha256=expected_inventory_sha256)
    def snapshot():
        files=[]
        directories=[]
        total=0
        for path in sorted(failed_target.rglob('*')):
            _regular_path(path)
            if len(files)+len(directories)>=10000: raise ValueError('Failed-target snapshot entry budget exceeded')
            if path.is_dir():
                directories.append(path.relative_to(failed_target).as_posix())
                continue
            if not path.is_file(): raise ValueError('Unsupported failed-target entry')
            if len(files)>=10000: raise ValueError('Failed-target snapshot file budget exceeded')
            digest=hashlib.sha256()
            size=0
            with path.open('rb') as stream:
                for block in iter(lambda:stream.read(1048576),b''):
                    size+=len(block); total+=len(block)
                    if total>536870912: raise ValueError('Failed-target snapshot byte budget exceeded')
                    digest.update(block)
            files.append({'path':path.relative_to(failed_target).as_posix(),'bytes':size,'sha256':digest.hexdigest()})
        return {'files':files,'directories':directories,'total_bytes':total}
    before=snapshot()
    fingerprint=inventory_hash(before)
    if apply and expected_failed_sha256!=fingerprint: raise StateConflict('Failed target differs from reviewed retry preview')
    result={'decision':'DEFINITION_IMPORT_RETRY_PREVIEW','failed_target_sha256':fingerprint,
            'file_count':len(before['files']),'bytes':before['total_bytes'],'writer_status':'OPERATOR_DECLARED_STOPPED',
            'writer_stopped_ref':writer_stopped_ref,'writes_performed':False,'migration_complete':False,'execution_authorized':False}
    if apply:
        imported=import_definitions(capsule,destination,expected_inventory_sha256=expected_inventory_sha256,
                                    mapping=mapping,expected_mapping_sha256=expected_mapping_sha256,
                                    _retry_from={'target':str(failed_target),'snapshot_sha256':fingerprint,
                                                 'writer_stopped_ref':writer_stopped_ref})
        if snapshot()!=before:
            raise StateConflict('Failed target changed during retry; retain both targets for review')
        result.update(decision='DEFINITION_IMPORT_REBUILT_QUARANTINED',writes_performed=True,
                      failed_target_unchanged=True,import_result=imported)
    return result


def finalize_definition_import(root, *, expected_inventory_sha256, expected_mapping_sha256, apply=False):
    """Resume the final publish boundary only, after a durable complete receipt.

    No old writer may use this private import target. A hard link publishes the
    verified SQLite inode without overwriting an existing state.db. Interruption
    before unlinking the temporary name is recoverable with both names intact.
    Earlier partial imports remain preserved for a separately reviewed rebuild.
    """
    if type(apply) is not bool: raise ValueError('Apply must be an explicit boolean')
    root=Path(root).absolute()
    pending,published=root/'state.importing.db',root/'state.db'
    for path in (pending,published):
        _regular_path(path)
        for suffix in ('-journal','-wal','-shm'):
            if Path(str(path)+suffix).exists():
                raise StateConflict('Import database has unresolved SQLite sidecars')
    if not pending.exists() and not published.exists(): raise StateConflict('No prepared import database')
    if pending.exists() and published.exists() and not os.path.samefile(pending,published):
        raise StateConflict('Published database conflicts with prepared import; neither file may be overwritten')
    arguments={'expected_inventory_sha256':expected_inventory_sha256,'expected_mapping_sha256':expected_mapping_sha256}
    selected=published if published.exists() else pending
    result=verify_definition_import(root,**arguments,_database_name=selected.name)
    # Recheck raw bytes after the read-only SQLite/source verification. This is
    # drift detection, not OS mediation against uncooperative external writers.
    receipt=json.loads(read_control(root,'definition-import.json')['raw_bytes'].decode('utf-8'))
    if hashlib.sha256(selected.read_bytes()).hexdigest()!=receipt['database_sha256']:
        raise StateConflict('Prepared import changed during verification')
    needs_publish=not published.exists()
    needs_cleanup=pending.exists()
    if apply:
        if needs_publish:
            os.link(pending,published)  # atomic create, fails if target exists; no overwrite fallback
        verify_definition_import(root,**arguments)
        if pending.exists():
            if not os.path.samefile(pending,published): raise StateConflict('Temporary import name changed')
            pending.unlink()  # same verified inode remains reachable as state.db
    return {**result,'decision':'DEFINITION_IMPORT_FINALIZED' if apply else 'DEFINITION_IMPORT_FINALIZE_PREVIEW',
            'publish_required':needs_publish,'temporary_name_cleanup_required':needs_cleanup,
            'writes_performed':bool(apply and (needs_publish or needs_cleanup))}
