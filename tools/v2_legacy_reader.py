"""Read-only legacy control parsing; documents remain data, never instructions.

This is an import prerequisite, not a migration or an execution-ready receipt.
Unknown sections remain byte-addressable in source records for a later mapper.
"""
import hashlib
import json
import re
import os
from pathlib import Path
from v2_evidence import _regular_path

MARKER=re.compile(r'<!-- MALTS:section=([A-Za-z0-9_-]+) -->[ \t]*')
RESULT_FORMATS={'RESULT_EVENT':('event_version',2),'RESULT_PROJECTION':('projection_schema',2)}


def source_profiles():
    """Advertise only this reader's implemented validation, not migration approval."""
    return {'workspace_index':{'contract_id':'malts.workspace.current','validation':'INDEX_AND_REFERENCE_SHAPE',
                'full_workspace_schema_validated':False},
            'result_formats':{role:{'version_field':field,'supported_declared_version':version,
                'missing_version':'LEGACY_IDENTITY_CHAIN_ONLY','full_schema_validated':False}
                for role,(field,version) in RESULT_FORMATS.items()},
            'result_contract':{'contract_id':'malts.result.current','validation':'IDENTITY_AND_REFERENCE_CHAIN',
                'full_schema_validated':False},
            'phase_boundary':{'revision_schema':1,'validation':'IDENTITY_VERSION_AND_REFERENCE_CHAIN'},
            'growth':{'schema_version':1,'validation':'REGISTERED_CONTRACT_AND_SOURCE_BINDINGS'},
            'historical_completion_is_current_acceptance':False,'migration_authorized':False}


def control_markers(text):
    matches=[]
    issues=[]
    offset=0
    fence=None
    for raw_line in text.splitlines(keepends=True):
        line=raw_line.rstrip('\r\n')
        fenced=re.match(r' {0,3}(`{3,}|~{3,})(.*)$',line)
        if fence is not None:
            if fenced and fenced[1][0]==fence[0] and len(fenced[1])>=fence[1] and not fenced[2].strip(): fence=None
        elif fenced:
            fence=(fenced[1][0],len(fenced[1]))
        else:
            marker=MARKER.fullmatch(line)
            if marker:
                matches.append((marker[1],offset,offset+len(line)))
            elif '<!-- MALTS:section=' in line:
                issues.append('MALFORMED_SECTION_MARKER')
        offset+=len(raw_line)
    if fence is not None: issues.append('UNCLOSED_CODE_FENCE')
    return matches,sorted(set(issues))


def read_source_bytes(root, relative, *, max_bytes=1048576):
    if type(max_bytes) is not int or not 1<=max_bytes<=67108864:
        raise ValueError('Control read budget must be between 1 and 67108864 bytes')
    root=Path(root).absolute()
    if not isinstance(relative,str) or not relative:
        raise ValueError('Expected a relative control path')
    path=Path(relative)
    if path.is_absolute() or path.drive or '..' in path.parts or ':' in relative:
        raise ValueError('Control path must stay inside the workspace')
    if any(part.endswith((' ','.')) or re.search(r'[<>"|?*\x00-\x1f]',part) or
           re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?',part,re.IGNORECASE)
           for part in path.parts):
        raise ValueError('Source path must name ordinary portable file components')
    target=root/path
    _regular_path(target)
    if not target.resolve().is_relative_to(root.resolve()): raise ValueError('Control path escapes workspace')
    with target.open('rb') as stream: data=stream.read(max_bytes+1)
    if len(data)>max_bytes: raise ValueError('Control exceeds explicit parsing budget')
    return {'path':path.as_posix(),'sha256':hashlib.sha256(data).hexdigest(),
            'bytes':len(data),'raw_bytes':data}


def read_control(root, relative, *, max_bytes=1048576):
    source=read_source_bytes(root,relative,max_bytes=max_bytes)
    data=source['raw_bytes']
    text=data.decode('utf-8-sig')
    matches,parse_issues=control_markers(text)
    sections=[]
    counts={}
    for i,(name,start,body_start) in enumerate(matches):
        counts[name]=counts.get(name,0)+1
        end=matches[i+1][1] if i+1<len(matches) else len(text)
        sections.append({'name':name,'text':text[body_start:end],
                         'start_character':start,'end_character':end})
    return {**source,
            'preamble':text[:matches[0][1]] if matches else text,'sections':sections,'parse_issues':parse_issues,
            'duplicate_sections':sorted(n for n,count in counts.items() if count>1),
            'has_utf8_bom':data.startswith(b'\xef\xbb\xbf'),'raw_bytes':data}


def append_result_history(references, bindings, row, previous, role, id_key, number, budget):
    is_event=role=='RESULT_EVENT_HISTORY'
    if ((not is_event and (not isinstance(previous.get(id_key),str) or not previous[id_key])) or
            not isinstance(previous.get('path'),str) or not previous['path'] or
            not isinstance(previous.get('sha256'),str) or re.fullmatch('[a-fA-F0-9]{64}',previous['sha256']) is None):
        raise ValueError('Invalid predecessor binding')
    identity=row['task_id']+'/'+(str(number) if is_event else previous[id_key])
    if (role,identity) in bindings or len(references)>=budget:
        raise ValueError('Repeated predecessor or history budget exceeded')
    bindings[(role,identity)]=({**row,'_expected_number':number},
                              {**previous,'sequence':number} if is_event else previous,None if is_event else id_key)
    references.append((role,identity,previous['path'],{'task_id':row['task_id'],
                       'lineage_id':row['lineage_id'],'source_binding':previous}))


def inspect_workspace(root, *, max_controls=500, growth_ledgers=None, payload_files=None):
    """Bounded indexed inventory. Returns metadata, never raw document bodies."""
    if type(max_controls) is not int or not 1<=max_controls<=5000: raise ValueError('Invalid control budget')
    index=read_control(root,'runtime/workspace_control.json')
    def pairs(items):
        value={}
        for key,item in items:
            if key in value: raise ValueError('Duplicate index field')
            value[key]=item
        return value
    runtime=json.loads(index['raw_bytes'].decode('utf-8-sig'),object_pairs_hook=pairs)
    if not isinstance(runtime,dict) or runtime.get('contract_id')!='malts.workspace.current':
        raise ValueError('Unsupported legacy workspace contract')
    references=[('PROJECT',runtime.get('project_id'),runtime.get('project_control'),None)]
    active_plan=runtime.get('current_phase_binding')
    if isinstance(active_plan,dict) and active_plan.get('active_plan_path') is not None:
        references.append(('PLAN',active_plan.get('active_plan_revision'),active_plan.get('active_plan_path'),None))
    for role,collection,key in [('PHASE','phase_controls','phase_id'),('SESSION','session_controls','session_id')]:
        rows=runtime.get(collection,[])
        if not isinstance(rows,list): raise ValueError('Invalid control index collection')
        for row in rows:
            if not isinstance(row,dict): raise ValueError('Invalid control index entry')
            references.append((role,row.get(key),row.get('path'),row.get('status')))
    growth_ledgers=[] if growth_ledgers is None else growth_ledgers
    if (not isinstance(growth_ledgers,list) or any(not isinstance(path,str) or not path for path in growth_ledgers) or
            len(growth_ledgers)!=len(set(growth_ledgers)) or len(growth_ledgers)>max_controls):
        raise ValueError('Growth ledgers must be an explicit bounded unique path list')
    growth_bindings={}
    growth_values={}
    growth_issues=[]
    for path in growth_ledgers:
        from malts_user_contracts import validate_instance
        try:
            ledger_record=read_control(root,path)
            ledger=json.loads(ledger_record['raw_bytes'].decode('utf-8-sig'),object_pairs_hook=pairs)
        except (OSError,ValueError) as error:
            growth_issues.append({'code':'UNREADABLE_GROWTH_LEDGER','path':path,'error_type':type(error).__name__})
            continue
        validation=validate_instance(Path(__file__).resolve().parent.parent,'growth-ledger',ledger)
        if validation:
            growth_issues.append({'code':'GROWTH_LEDGER_SCHEMA_INVALID','path':path,
                                  'contract_issue_codes':sorted({issue.code for issue in validation})})
            continue
        if ledger['project_id']!=runtime['project_id']:
            growth_issues.append({'code':'GROWTH_LEDGER_PROJECT_MISMATCH','path':path})
            continue
        if len(references)+1+len(ledger['signal_records'])+len(ledger['candidate_records'])>max_controls:
            growth_issues.append({'code':'GROWTH_INVENTORY_BUDGET_EXCEEDED','path':path})
            continue
        ledger_id=ledger['ledger_id']
        growth_bindings[('GROWTH_LEDGER',ledger_id)]=(ledger_id,ledger_id,'ledger_id',ledger_record['sha256'])
        references.append(('GROWTH_LEDGER',ledger_id,ledger_record['path'],{'mode':ledger['mode']}))
        for collection,role,id_field in (('signal_records','GROWTH_SIGNAL','signal_id'),('candidate_records','GROWTH_CANDIDATE','candidate_id')):
            for binding in ledger[collection]:
                identity=ledger_id+'/'+binding['record_id']
                growth_bindings[(role,identity)]=(ledger_id,binding['record_id'],id_field,binding['sha256'].lower())
                references.append((role,identity,(Path(ledger_record['path']).parent/binding['relative_path']).as_posix(),None))
        if len(references)>max_controls: raise ValueError('Growth source inventory exceeds budget')
    task_heads={}
    task_rows=runtime.get('current_task_bindings',[])
    if not isinstance(task_rows,list): raise ValueError('Invalid task binding collection')
    task_ids=set()
    def append_task_row(row):
        if not isinstance(row,dict): raise ValueError('Invalid task binding')
        for key in ('task_id','phase_id','lineage_id'):
            if not isinstance(row.get(key),str) or not row[key].strip(): raise ValueError('Invalid task binding identity')
        if row['task_id'] in task_ids: raise ValueError('Duplicate task binding')
        task_ids.add(row['task_id'])
        contract=row.get('latest_contract_revision')
        event=row.get('latest_event')
        if not isinstance(contract,dict) or (event is not None and not isinstance(event,dict)):
            raise ValueError('Invalid task head binding')
        if event is not None and (type(event.get('sequence')) is not int or event['sequence']<1):
            raise ValueError('Invalid task event sequence')
        heads=[('RESULT_CONTRACT',contract,'revision_id'),
               ('RESULT_PROJECTION',{'path':row.get('projection_path'),'sha256':row.get('projection_sha256')},None)]
        if event is not None: heads.append(('RESULT_EVENT',event,'event_id'))
        if len(references)+len(heads)>max_controls: raise ValueError('Control inventory exceeds explicit budget')
        for role,head,id_key in heads:
            if (not isinstance(head.get('path'),str) or not head['path'] or
                    not isinstance(head.get('sha256'),str) or re.fullmatch('[a-fA-F0-9]{64}',head['sha256']) is None or
                    (id_key is not None and (not isinstance(head.get(id_key),str) or not head[id_key]))):
                raise ValueError('Invalid indexed task head')
            # One current head per task/role; original revision and lineage stay explicit.
            task_heads[(role,row['task_id'])]=(row,head,id_key)
            references.append((role,row['task_id'],head['path'],
                               {key:row.get(key) for key in ('task_status','lineage_id','phase_id',
                                                            'latest_contract_revision','latest_event')}))
        if len(references)>max_controls: raise ValueError('Control inventory exceeds explicit budget')
    for row in task_rows: append_task_row(row)
    if len(references)>max_controls: raise ValueError('Control inventory exceeds explicit budget')
    seen=set()
    seen_paths=set()
    records=[]
    issues=growth_issues
    result_payloads=[]
    for role,identity,relative,status in references:
        format_validation=None
        if not isinstance(identity,str) or not identity.strip():
            issues.append({'code':'MISSING_ID','role':role})
            continue
        if (role,identity) in seen:
            issues.append({'code':'DUPLICATE_ID','role':role,'id':identity})
        seen.add((role,identity))
        try:
            record=read_control(root,relative)
        except (OSError,ValueError) as error:
            issues.append({'code':'UNREADABLE_CONTROL','role':role,'id':identity,'error_type':type(error).__name__})
            continue
        path_key=os.path.normcase(str((Path(root)/record['path']).resolve()))
        if path_key in seen_paths:
            issues.append({'code':'SHARED_CONTROL_PATH','role':role,'id':identity})
        seen_paths.add(path_key)
        metadata_name={'PROJECT':'metadata','PHASE':'phase-metadata','SESSION':'session-metadata'}.get(role)
        metadata=[section['text'] for section in record['sections'] if section['name']==metadata_name]
        embedded_ids=[]
        if len(metadata)==1 and not re.search(r'^ {0,3}(?:`{3,}|~{3,})',metadata[0],re.MULTILINE):
            label={'PROJECT':r'(?:Project(?: ID)?|项目)','PHASE':r'Phase ID','SESSION':r'Session ID'}[role]
            embedded_ids=re.findall(r'^-\s*'+label+r'\s*[:：]\s*([^\r\n]+)',metadata[0],re.MULTILINE)
            embedded_ids=[value.strip().strip('`') for value in embedded_ids]
        identity_status='MATCH' if embedded_ids==[identity] else 'MISMATCH' if embedded_ids else 'NOT_VERIFIED'
        if role=='PLAN':
            expected=active_plan.get('active_plan_sha256')
            identity_status='MATCH' if isinstance(expected,str) and expected.lower()==record['sha256'] else 'MISMATCH'
        if role in {'ARTIFACT_SHARED_INDEX','ARTIFACT_ARCHIVE_INDEX'}:
            marker='shared-artifacts' if role=='ARTIFACT_SHARED_INDEX' else 'archive-artifacts'
            identity_status='MATCH' if sum(s['name']==marker for s in record['sections'])==1 else 'MISMATCH'
        if (role,identity) in growth_bindings:
            ledger_id,record_id,id_field,expected_hash=growth_bindings[(role,identity)]
            try:
                value=json.loads(record['raw_bytes'].decode('utf-8-sig'),object_pairs_hook=pairs)
                contract={'GROWTH_LEDGER':'growth-ledger','GROWTH_SIGNAL':'growth-signal','GROWTH_CANDIDATE':'growth-candidate'}[role]
                valid=(record['sha256']==expected_hash and not validate_instance(Path(__file__).resolve().parent.parent,contract,value) and value[id_field]==record_id)
                identity_status='MATCH' if valid else 'MISMATCH'
                if valid:
                    growth_values[(ledger_id,role,record_id)]=value
                    status={'ledger_id':ledger_id,'record_id':record_id,
                            **{key:value[key] for key in ('status','mode','authority_level','sensitivity','redacted') if key in value}}
            except ValueError:
                identity_status='MISMATCH'
        if (role,identity) in task_heads:
            row,head,id_key=task_heads[(role,identity)]
            base_role=role.removesuffix('_HISTORY')
            try:
                payload=json.loads(record['raw_bytes'].decode('utf-8-sig'),object_pairs_hook=pairs)
                matches=(isinstance(payload,dict) and head['sha256'].lower()==record['sha256'] and
                         all(payload.get(key)==row[key] for key in ('task_id','lineage_id')) and
                         isinstance(payload.get('phase_id'),str) and bool(payload['phase_id']))
                if matches and not role.endswith('_HISTORY'): matches=payload['phase_id']==row['phase_id']
                if matches and id_key is not None: matches=payload.get(id_key)==head[id_key]
                if matches and base_role=='RESULT_CONTRACT': matches=payload.get('contract_id')=='malts.result.current'
                if matches and base_role=='RESULT_EVENT':
                    matches=(type(payload.get('sequence')) is int and payload['sequence']==head.get('sequence') and
                             isinstance(payload.get('event_id'),str) and bool(payload['event_id']))
                if matches and role=='RESULT_PROJECTION':
                    matches=all(payload.get(key)==row.get(key) for key in ('task_status','latest_contract_revision','latest_event'))
                if isinstance(payload,dict):
                    format_validation={'status':'IDENTITY_CHAIN_ONLY','full_schema_validated':False}
                    if base_role in RESULT_FORMATS:
                        field,version=RESULT_FORMATS[base_role]
                        format_validation['version_field']=field
                        if field not in payload:format_validation['status']='UNVERSIONED_LEGACY_IDENTITY_CHAIN_ONLY'
                        elif type(payload[field]) is int and payload[field]==version:
                            format_validation.update(status='SUPPORTED_DECLARED_VERSION',declared_version=version)
                        else:
                            matches=False;format_validation['status']='UNSUPPORTED_DECLARED_VERSION'
                            issues.append({'code':'UNSUPPORTED_RESULT_VERSION','role':role,'id':identity,'field':field,'expected':version})
                identity_status='MATCH' if matches else 'MISMATCH'
                if matches and base_role in {'RESULT_CONTRACT','RESULT_EVENT'}:
                    result_payloads.append((base_role,record,payload))
                if matches and base_role in {'RESULT_CONTRACT','RESULT_EVENT'}:
                    history_role=base_role+'_HISTORY'
                    previous_key='previous_revision' if base_role=='RESULT_CONTRACT' else 'previous_event'
                    number_key='revision_number' if base_role=='RESULT_CONTRACT' else 'sequence'
                    number=payload.get(number_key)
                    if (type(number) is not int or number<1 or previous_key not in payload or
                            row.get('_expected_number',number)!=number):
                        issues.append({'code':'INVALID_RESULT_CHAIN','role':role,'id':identity})
                    else:
                        previous=payload[previous_key]
                        if number==1 and previous is not None or number>1 and not isinstance(previous,dict):
                            issues.append({'code':'INVALID_RESULT_CHAIN','role':role,'id':identity})
                        elif previous is not None:
                            # Queue predecessor reads; never recurse or scan unrelated files.
                            append_result_history(references,task_heads,row,previous,history_role,id_key,number-1,max_controls)
                    if role.endswith('_HISTORY'):
                        status={**status,'phase_id':payload['phase_id'],
                                'revision_id':payload.get('revision_id'),'event_id':payload.get('event_id')}
            except ValueError:
                identity_status='MISMATCH'
        if identity_status=='MISMATCH': issues.append({'code':'CONTROL_ID_MISMATCH','role':role,'id':identity})
        records.append({'role':role,'id':identity,'declared_status':status,'identity_verification':identity_status,
                        **({'format_validation':format_validation} if format_validation is not None else {}),
                        **{key:record[key] for key in ('path','sha256','bytes','duplicate_sections')},
                        'section_names':[s['name'] for s in record['sections']],
                        'completion_evidence':'HISTORICAL_DECLARATION_ONLY'})
        if role=='PROJECT' and identity_status=='MATCH':
            artifact_sections=[s['text'] for s in record['sections'] if s['name']=='artifact-contract-index']
            if len(artifact_sections)==1:
                section=artifact_sections[0]
                try:
                    if re.search(r'^ {0,3}(?:`{3,}|~{3,})',section,re.MULTILINE):
                        raise ValueError('Unsupported Artifact enrollment section')
                    def artifact_field(label):
                        values=re.findall(r'^-[ \t]*'+re.escape(label)+r':[ \t]*([^\r\n]+)',section,re.MULTILINE)
                        if len(values)!=1: raise ValueError('Artifact enrollment field missing or duplicated')
                        return values[0].strip().strip('`')
                    enrollment=artifact_field('Enrollment')
                    if artifact_field('Contract version')!='1' or enrollment not in {'ENROLLED','NOT_ENROLLED'}:
                        raise ValueError('Unsupported Artifact enrollment contract')
                    for label,index_role,index_id in (('Shared index','ARTIFACT_SHARED_INDEX','shared'),
                                                       ('Archive index','ARTIFACT_ARCHIVE_INDEX','archive')):
                        path=artifact_field(label)
                        if path=='N/A': continue
                        if len(references)>=max_controls: raise ValueError('Artifact index discovery budget exceeded')
                        references.append((index_role,index_id,path,{'enrollment':enrollment}))
                except ValueError as error:
                    issues.append({'code':'INVALID_ARTIFACT_SOURCE_INDEX','id':identity,'error_type':type(error).__name__})
        if role=='PHASE' and identity_status=='MATCH':
            task_sections=[s['text'] for s in record['sections'] if s['name']=='phase-task-lineage-index']
            if len(task_sections)==1:
                section=task_sections[0]
                if re.search(r'^ {0,3}(?:`{3,}|~{3,})',section,re.MULTILINE):
                    issues.append({'code':'UNSUPPORTED_PHASE_TASK_INDEX','id':identity})
                else:
                    indexed_tasks=set()
                    for line in section.splitlines():
                        if not line.strip().startswith('|'): continue
                        cells=[value.strip() for value in line.strip().strip('|').split('|')]
                        if cells==['Task ID','Lineage ID','Status','Contract revision','Latest event','Projection']: continue
                        if all(re.fullmatch(':?-+:?',value) for value in cells): continue
                        try:
                            if len(cells)!=6: raise ValueError('Unsupported task index row')
                            task_id,lineage_id,task_status,contract_ref,event_ref,projection_ref=cells
                            if task_id in indexed_tasks: raise ValueError('Duplicate Phase task')
                            indexed_tasks.add(task_id)
                            if task_id not in task_ids and len(references)+3>max_controls:
                                issues.append({'code':'PHASE_TASK_DISCOVERY_BUDGET_EXCEEDED','id':identity})
                                break
                            def indexed_ref(value):
                                path,separator,digest=value.rpartition('#')
                                if not separator or re.fullmatch('[A-Fa-f0-9]{64}',digest) is None:
                                    raise ValueError('Invalid Phase task reference')
                                return path.replace('\\','/'),digest.lower()
                            projection_path,projection_hash=indexed_ref(projection_ref)
                            projection_record=read_control(root,projection_path)
                            projection=json.loads(projection_record['raw_bytes'].decode('utf-8-sig'),object_pairs_hook=pairs)
                            if (not isinstance(projection,dict) or projection_hash!=projection_record['sha256'] or
                                    any(projection.get(key)!=value for key,value in
                                        (('task_id',task_id),('lineage_id',lineage_id),('phase_id',identity),('task_status',task_status)))):
                                raise ValueError('Phase task projection drift')
                            for reference,key in ((contract_ref,'latest_contract_revision'),(event_ref,'latest_event')):
                                binding=projection.get(key)
                                if key=='latest_event' and reference=='N/A' and binding is None: continue
                                if (not isinstance(binding,dict) or not isinstance(binding.get('path'),str) or
                                        not isinstance(binding.get('sha256'),str) or
                                        indexed_ref(reference)!=(binding['path'].replace('\\','/'),binding['sha256'].lower())):
                                    raise ValueError('Phase task head reference drift')
                            row={**projection,'projection_path':projection_path,'projection_sha256':projection_hash}
                            existing=task_heads.get(('RESULT_PROJECTION',task_id))
                            if existing is None: append_task_row(row)
                            elif (existing[1]['path'].replace('\\','/')!=projection_path or
                                  existing[1]['sha256'].lower()!=projection_hash or existing[0]['phase_id']!=identity):
                                raise ValueError('Conflicting current and Phase task bindings')
                        except (OSError,ValueError) as error:
                            issues.append({'code':'UNRESOLVED_PHASE_TASK_INDEX','id':identity,'error_type':type(error).__name__})
        if record['duplicate_sections']: issues.append({'code':'AMBIGUOUS_SECTIONS','role':role,'id':identity})
        for code in record['parse_issues']: issues.append({'code':code,'role':role,'id':identity})
    for (ledger_id,role,record_id),value in growth_values.items():
        if role!='GROWTH_CANDIDATE': continue
        signals={key[2]:signal for key,signal in growth_values.items() if key[0]==ledger_id and key[1]=='GROWTH_SIGNAL'}
        if not set(value['source_signals']).issubset(signals):
            issues.append({'code':'GROWTH_SOURCE_SIGNAL_UNRESOLVED','id':ledger_id+'/'+record_id})
        source_tasks={signals[key]['source_task_id'] for key in value['source_signals'] if key in signals}
        if any(r['validation_kind']=='future_use' and r['future_task_id'] in source_tasks for r in value['future_use_validations']):
            issues.append({'code':'GROWTH_SOURCE_TASK_REUSED','id':ledger_id+'/'+record_id})
    # Cross-links are checked after all predecessor records have been read.
    contracts={record['path']:(record,payload) for role,record,payload in result_payloads if role=='RESULT_CONTRACT'}
    boundaries={}
    for role,record,payload in result_payloads:
        if role=='RESULT_EVENT':
            binding=payload.get('contract_revision')
            target=contracts.get(binding.get('path','').replace('\\','/')) if isinstance(binding,dict) and isinstance(binding.get('path'),str) else None
            if (target is None or not isinstance(binding.get('sha256'),str) or
                    binding['sha256'].lower()!=target[0]['sha256'] or
                    binding.get('revision_id')!=target[1].get('revision_id') or
                    any(payload.get(key)!=target[1].get(key) for key in ('task_id','lineage_id','phase_id'))):
                issues.append({'code':'EVENT_CONTRACT_UNRESOLVED','path':record['path']})
        boundary=payload.get('accepted_phase_boundary' if role=='RESULT_CONTRACT' else 'phase_boundary_revision')
        if (not isinstance(boundary,dict) or not isinstance(boundary.get('revision_id'),str) or
                re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',boundary['revision_id']) is None or
                re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',payload['phase_id']) is None or
                not isinstance(boundary.get('sha256'),str) or re.fullmatch('[a-fA-F0-9]{64}',boundary['sha256']) is None):
            issues.append({'code':'INVALID_RESULT_BOUNDARY','path':record['path']})
            continue
        key=(payload['phase_id'],boundary['revision_id'])
        digest=boundary['sha256'].lower()
        if key in boundaries and boundaries[key]!=digest:
            issues.append({'code':'CONFLICTING_BOUNDARY_BINDING','path':record['path']})
        boundaries[key]=digest
    active_binding=runtime.get('current_phase_binding')
    boundary_fields=('boundary_revision_id','boundary_revision_path','boundary_revision_sha256')
    if isinstance(active_binding,dict) and any(key in active_binding for key in boundary_fields):
        phase_id=active_binding.get('active_phase_id')
        revision_id=active_binding.get('boundary_revision_id')
        digest=active_binding.get('boundary_revision_sha256')
        path=active_binding.get('boundary_revision_path')
        if (not all(isinstance(value,str) for value in (phase_id,revision_id,digest,path)) or
                re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',phase_id) is None or
                re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',revision_id) is None or
                re.fullmatch('[a-fA-F0-9]{64}',digest) is None or
                path.replace('\\','/')!=f'phases/{phase_id}/boundary-revisions/{revision_id}.json'):
            issues.append({'code':'INVALID_ACTIVE_BOUNDARY_BINDING'})
        else:
            key=(phase_id,revision_id)
            if key in boundaries and boundaries[key]!=digest.lower():
                issues.append({'code':'CONFLICTING_BOUNDARY_BINDING','path':path})
            boundaries[key]=digest.lower()
    boundary_queue=list(boundaries)
    boundary_numbers={}
    boundary_edges=[]
    for phase_id,revision_id in boundary_queue:
        digest=boundaries[(phase_id,revision_id)]
        if len(records)>=max_controls:
            issues.append({'code':'BOUNDARY_INVENTORY_BUDGET_EXCEEDED'})
            break
        relative=f'phases/{phase_id}/boundary-revisions/{revision_id}.json'
        try:
            boundary_record=read_control(root,relative)
            boundary=json.loads(boundary_record['raw_bytes'].decode('utf-8-sig'),object_pairs_hook=pairs)
            matches=(isinstance(boundary,dict) and boundary_record['sha256']==digest and
                     boundary.get('phase_id')==phase_id and boundary.get('revision_id')==revision_id and
                     type(boundary.get('revision_schema')) is int and boundary['revision_schema']==1)
            records.append({'role':'PHASE_BOUNDARY','id':phase_id+'/'+revision_id,
                'declared_status':{'phase_id':phase_id,'revision_id':revision_id},
                'identity_verification':'MATCH' if matches else 'MISMATCH',
                **{key:boundary_record[key] for key in ('path','sha256','bytes','duplicate_sections')},
                'section_names':[],'completion_evidence':'HISTORICAL_DECLARATION_ONLY'})
            if not matches: issues.append({'code':'RESULT_BOUNDARY_MISMATCH','path':relative})
            else:
                number=boundary.get('revision_number')
                previous=boundary.get('previous_revision')
                if (type(number) is not int or number<1 or 'previous_revision' not in boundary or
                        number==1 and previous is not None or number>1 and not isinstance(previous,dict)):
                    issues.append({'code':'INVALID_BOUNDARY_CHAIN','path':relative})
                    continue
                boundary_numbers[(phase_id,revision_id)]=number
                if previous is not None:
                    previous_id=previous.get('revision_id')
                    previous_hash=previous.get('sha256')
                    previous_path=previous.get('path')
                    if (not all(isinstance(value,str) for value in (previous_id,previous_hash,previous_path)) or
                            re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',previous_id) is None or
                            re.fullmatch('[a-fA-F0-9]{64}',previous_hash) is None or
                            previous_path.replace('\\','/')!=f'phases/{phase_id}/boundary-revisions/{previous_id}.json'):
                        issues.append({'code':'INVALID_BOUNDARY_CHAIN','path':relative})
                        continue
                    key=(phase_id,previous_id)
                    boundary_edges.append((key,number-1,relative))
                    if key in boundaries:
                        if boundaries[key]!=previous_hash.lower():
                            issues.append({'code':'CONFLICTING_BOUNDARY_BINDING','path':relative})
                    else:
                        boundaries[key]=previous_hash.lower()
                        boundary_queue.append(key)
        except (OSError,ValueError) as error:
            issues.append({'code':'UNREADABLE_RESULT_BOUNDARY','path':relative,'error_type':type(error).__name__})
    for key,expected_number,source_path in boundary_edges:
        if boundary_numbers.get(key)!=expected_number:
            issues.append({'code':'BOUNDARY_PREDECESSOR_UNRESOLVED','path':source_path})
    for role,field in [('PHASE','active_phase_id'),('SESSION','active_session_id')]:
        active_id=runtime.get(field)
        if active_id is not None:
            matches=[record for record in records if record['role']==role and record['id']==active_id]
            if len(matches)!=1:
                issues.append({'code':'ACTIVE_CONTROL_UNRESOLVED','role':role})
    binding=runtime.get('current_phase_binding')
    if binding is not None:
        if (not isinstance(binding,dict) or not isinstance(binding.get('phase_control_path'),str) or
                not isinstance(binding.get('phase_control_sha256'),str)):
            issues.append({'code':'INVALID_CURRENT_PHASE_BINDING'})
        else:
            matches=[record for record in records if record['role']=='PHASE' and record['id']==runtime.get('active_phase_id')]
            if (len(matches)!=1 or binding.get('active_phase_id')!=runtime.get('active_phase_id') or
                    binding.get('phase_control_path','').replace('\\','/')!=matches[0]['path'] or
                    str(binding.get('phase_control_sha256','')).lower()!=matches[0]['sha256']):
                issues.append({'code':'CURRENT_PHASE_BINDING_DRIFT'})
    payload_files=[] if payload_files is None else payload_files
    if (not isinstance(payload_files,list) or len(payload_files)>64 or
            any(not isinstance(path,str) or not path or '\\' in path or Path(path).as_posix()!=path for path in payload_files) or
            len({path.casefold() for path in payload_files})!=len(payload_files)):
        raise ValueError('Select at most 64 distinct canonical relative payload file paths')
    payload_bytes=0
    occupied={r['path'].casefold() for r in records}|{'runtime/workspace_control.json'}
    for relative in payload_files:
        if relative.casefold() in occupied:
            issues.append({'code':'PAYLOAD_CONTROL_PATH_COLLISION','path':relative})
            continue
        if len(records)>=max_controls or payload_bytes>=67108864:
            issues.append({'code':'PAYLOAD_INVENTORY_BUDGET_EXCEEDED','path':relative})
            continue
        try:
            record=read_source_bytes(root,relative,max_bytes=min(16777216,67108864-payload_bytes))
        except (OSError,ValueError) as error:
            issues.append({'code':'UNREADABLE_SELECTED_PAYLOAD','path':relative,'error_type':type(error).__name__})
            continue
        payload_bytes+=record['bytes']
        records.append({key:record[key] for key in ('path','sha256','bytes')}|
                       {'role':'SELECTED_PAYLOAD','id':relative,'identity_verification':'MATCH',
                        'declared_status':{'preservation':'EXPLICIT_SELECTION_ONLY','bytes':record['bytes']}})
    if read_control(root,'runtime/workspace_control.json')['sha256']!=index['sha256']:
        issues.append({'code':'INDEX_CHANGED_DURING_READ'})
    from v2_management import SELECTION,selection_conflicts
    conflicts=selection_conflicts({'records':records})
    if conflicts:issues.append({'code':'SOURCE_MANAGEMENT_DIRECTORY_CONFLICT','paths':conflicts})
    return {'decision':'INVENTORY_ONLY','source_contract':runtime['contract_id'],'index_sha256':index['sha256'],
            'source_selection':json.loads(json.dumps(SELECTION)),
            'growth_ledgers':growth_ledgers,**({'payload_files':payload_files} if payload_files else {}),
            'records':records,'issues':issues,'writes_performed':False,'execution_authorized':False,
            'migration_ready':False,'scope':'Indexed controls, Result/Phase boundary chains, explicitly selected Growth bundles and payload files; unselected references and semantic replay not mapped'}


def inspect_legacy_activity(root, *, max_files=2000, max_bytes=67108864):
    """Bounded source cutover diagnostics, never proof of writer quiescence."""
    from workspace_transactions import WORKSPACE_TRANSACTION_PROFILE,ARTIFACT_TRANSACTION_PROFILE
    from malts_user_contracts import validate_instance
    root=Path(root).absolute()
    if type(max_files) is not int or not 1<=max_files<=10000 or type(max_bytes) is not int or not 1<=max_bytes<=536870912:
        raise ValueError('Invalid activity inventory budget')
    profiles=(WORKSPACE_TRANSACTION_PROFILE,ARTIFACT_TRANSACTION_PROFILE)
    fixed={'runtime/workspace_control.json','runtime/workspace_coordination.json',*(p.lock_relative.as_posix() for p in profiles)}
    def paths():
        result=set(fixed)
        for profile in profiles:
            directory=root/profile.journal_directory_relative
            _regular_path(directory)
            if directory.exists():
                if not directory.is_dir(): raise ValueError('Transaction journal root is not a directory')
                for entry in directory.iterdir():
                    if entry.suffix.casefold()=='.json': result.add(entry.relative_to(root).as_posix())
                    if len(result)>max_files: raise ValueError('Activity file budget exceeded')
        if len(result)>max_files: raise ValueError('Activity file budget exceeded')
        return sorted(result)
    selected=paths(); records=[]; values={}; blockers=[]; total=0
    def unique(items):
        value={}
        for key,item in items:
            if key in value: raise ValueError('Duplicate activity JSON field')
            value[key]=item
        return value
    for relative in selected:
        path=root/relative
        _regular_path(path)
        if not path.exists():
            records.append({'path':relative,'sha256':None,'bytes':0})
            continue
        if total>=max_bytes: raise ValueError('Activity byte budget exceeded')
        source=read_source_bytes(root,relative,max_bytes=min(8388608,max_bytes-total))
        total+=source['bytes']
        records.append({k:source[k] for k in ('path','sha256','bytes')})
        try:
            value=json.loads(source['raw_bytes'].decode('utf-8-sig'),object_pairs_hook=unique)
            if not isinstance(value,dict): raise ValueError('Expected activity object')
            values[relative]=value
        except (ValueError,UnicodeError): blockers.append({'code':'INVALID_ACTIVITY_RECORD','path':relative})
    index=values.get('runtime/workspace_control.json')
    if not index or index.get('contract_id')!='malts.workspace.current':
        blockers.append({'code':'SOURCE_WORKSPACE_IDENTITY_UNVERIFIED','path':'runtime/workspace_control.json'})
    terminal=[]
    for profile in profiles:
        lock=profile.lock_relative.as_posix()
        if next(r for r in records if r['path']==lock)['sha256'] is not None:
            blockers.append({'code':'TRANSACTION_LOCK_PRESENT','path':lock})
        prefix=profile.journal_directory_relative.as_posix()+'/'
        for relative,value in values.items():
            if not relative.startswith(prefix): continue
            modern='journal_schema' in value
            state=value.get('state' if modern else 'status')
            if modern:
                valid=not validate_instance(Path(__file__).resolve().parent.parent,'workspace-transaction-journal',value)
            else:
                # This legacy format has no standalone schema. Validate known
                # identity/shape; terminal remains a declaration, not replay proof.
                required={'contract_version','operation_id','operation','created_at','status','attempt',
                          'attempt_history','journal_path','lock_path','targets','inputs','planned_outputs'}
                valid=(required.issubset(value) and type(value.get('contract_version')) is int and value['contract_version']==1 and
                       all(isinstance(value.get(k),list) for k in ('attempt_history','targets','inputs','planned_outputs')))
            valid=valid and value.get('operation_id')==Path(relative).stem and value.get('journal_path')==relative and value.get('lock_path')==lock
            if not valid or state not in {'COMMITTED','ROLLED_BACK'}:
                blockers.append({'code':'TRANSACTION_UNRESOLVED_OR_INVALID','path':relative,'declared_state':state})
            else: terminal.append({'path':relative,'declared_state':state,'validation':'SCHEMA_AND_IDENTITY' if modern else 'LEGACY_IDENTITY_AND_SHAPE_ONLY'})
    coordination=values.get('runtime/workspace_coordination.json')
    governance=(index or {}).get('phase_governance',{})
    if not isinstance(governance,dict): raise ValueError('Invalid phase governance')
    if governance.get('profile') in {'resource_admission','resource_admission_v1'} and coordination is None:
        blockers.append({'code':'REQUIRED_COORDINATION_MISSING','path':'runtime/workspace_coordination.json'})
    if coordination is not None:
        validation=validate_instance(Path(__file__).resolve().parent.parent,'workspace-coordination',coordination)
        if validation or coordination.get('workspace_id')!=(index or {}).get('project_id'):
            blockers.append({'code':'COORDINATION_INVALID_OR_WRONG_WORKSPACE','path':'runtime/workspace_coordination.json'})
        else:
            for field in ('active_admissions','queue','quarantines'):
                if coordination[field]: blockers.append({'code':'COORDINATION_NOT_QUIESCENT','field':field,'count':len(coordination[field])})
            if coordination['workspace_quarantine'] is not None: blockers.append({'code':'WORKSPACE_AUTHORITY_UNKNOWN'})
    stable=paths()==selected
    recheck_bytes=0
    for record in records:
        path=root/record['path']; _regular_path(path)
        if record['sha256'] is None:
            stable=stable and not path.exists()
        elif not path.exists(): stable=False
        else:
            if recheck_bytes>=max_bytes: raise ValueError('Activity recheck byte budget exceeded')
            observed=read_source_bytes(root,record['path'],max_bytes=min(8388608,max_bytes-recheck_bytes))
            recheck_bytes+=observed['bytes']
            if observed['sha256']!=record['sha256']: stable=False
    if not stable: blockers.append({'code':'ACTIVITY_CHANGED_DURING_READ'})
    encoded=json.dumps(records,sort_keys=True,separators=(',',':')).encode('utf-8')
    return {'decision':'KNOWN_ACTIVITY_BLOCKED' if blockers else 'NO_KNOWN_RECORD_BLOCKERS',
            'source_activity_sha256':hashlib.sha256(encoded).hexdigest(),'files':records,'bytes':total,'recheck_bytes':recheck_bytes,
            'terminal_journals':terminal,'blockers':blockers,'snapshot_stable':stable,
            'writer_quiescence_verified':False,'adoption_ready':False,'writes_performed':False,
            'uncovered':'Host processes, unregistered writers, external effects and journals outside the two canonical directories require separate evidence.'}


def annotate_archive_only(inventory, decisions):
    """Bind exact source hashes and review references into the reviewed inventory."""
    if not isinstance(decisions,list): raise ValueError('Archive decisions must be a list')
    result=json.loads(json.dumps(inventory))
    records={(r['role'],r['id']):r for r in result['records']}
    seen=set()
    for decision in decisions:
        if not isinstance(decision,dict) or set(decision)!={'role','id','sha256','review_ref'}:
            raise ValueError('Invalid archive-only decision')
        if any(not isinstance(value,str) or not value for value in decision.values()):
            raise ValueError('Archive decision fields must be nonempty text')
        key=(decision['role'],decision['id'])
        record=records.get(key)
        if key in seen or record is None or record['sha256']!=decision['sha256']:
            raise ValueError('Archive decision is duplicated or does not match its source')
        seen.add(key)
        record['archive_only']={'review_ref':decision['review_ref']}
    return result


def verify_inventory(root, inventory):
    """Compare current indexed metadata with an earlier inventory, without writes.

    This detects observed drift, not an atomic filesystem snapshot or write lock.
    Import must bind and recheck its source bytes inside its own commit protocol.
    """
    if not isinstance(inventory,dict) or inventory.get('source_contract')!='malts.workspace.current':
        raise ValueError('Unsupported inventory contract')
    from v2_management import validate_selection
    validate_selection(inventory)
    records=inventory.get('records')
    if not isinstance(records,list) or not 1<=len(records)<=5000:
        raise ValueError('Invalid inventory record count')
    expected={}
    for record in records:
        if (not isinstance(record,dict) or not isinstance(record.get('role'),str) or
                not isinstance(record.get('id'),str) or not isinstance(record.get('path'),str) or
                not isinstance(record.get('sha256'),str) or re.fullmatch('[a-f0-9]{64}',record['sha256']) is None):
            raise ValueError('Invalid inventory record')
        key=(record['role'],record['id'])
        if key in expected: raise ValueError('Ambiguous inventory IDs cannot be verified for import')
        expected[key]=(record['path'],record['sha256'])
    current=inspect_workspace(root,max_controls=5000,growth_ledgers=inventory.get('growth_ledgers',[]),
                              payload_files=inventory.get('payload_files',[]))
    observed={(record['role'],record['id']):(record['path'],record['sha256']) for record in current['records']}
    changed=[{'role':key[0],'id':key[1]} for key in sorted(set(expected)|set(observed)) if expected.get(key)!=observed.get(key)]
    payload_metadata={(r['role'],r['id']):r['bytes'] for r in current['records'] if r['role']=='SELECTED_PAYLOAD'}
    for record in records:
        key=(record['role'],record['id'])
        if record['role']=='SELECTED_PAYLOAD' and (type(record.get('bytes')) is not int or record['bytes']!=payload_metadata.get(key)):
            changed.append({'role':key[0],'id':key[1]})
    index_changed=current['index_sha256']!=inventory.get('index_sha256')
    archive_keys=set()
    actual_records={(record['role'],record['id']):record for record in current['records']}
    for record in records:
        if 'archive_only' not in record: continue
        decision=record['archive_only']
        actual=actual_records.get((record['role'],record['id']))
        if (not isinstance(decision,dict) or set(decision)!={'review_ref'} or
                not isinstance(decision['review_ref'],str) or not decision['review_ref'].strip() or
                actual is None or actual['role'] not in {'PHASE','SESSION'} or
                not isinstance(actual['declared_status'],str) or actual['declared_status'] not in {'DONE','CANCELLED','FAILED'} or
                actual['identity_verification']!='MATCH'):
            raise ValueError('Only verified terminal Phase/Session controls support archive-only disposition')
        archive_keys.add((record['role'],record['id']))
    if archive_keys:
        runtime=json.loads(read_control(root,'runtime/workspace_control.json')['raw_bytes'].decode('utf-8-sig'))
        if ('PHASE',runtime.get('active_phase_id')) in archive_keys or ('SESSION',runtime.get('active_session_id')) in archive_keys:
            raise ValueError('Active controls cannot be archive-only')
    issues=[issue for issue in current['issues'] if not
            (issue['code']=='AMBIGUOUS_SECTIONS' and (issue.get('role'),issue.get('id')) in archive_keys)]
    preserved_ambiguities=[issue for issue in current['issues'] if
            issue['code']=='AMBIGUOUS_SECTIONS' and (issue.get('role'),issue.get('id')) in archive_keys]
    return {'decision':'SOURCE_MATCH' if not changed and not index_changed and not issues else 'SOURCE_CHANGED_OR_AMBIGUOUS',
            'changed_records':changed,'index_changed':index_changed,'issues':issues,'preserved_ambiguities':preserved_ambiguities,
            'writes_performed':False,'migration_authorized':False,'atomic_snapshot':False}
