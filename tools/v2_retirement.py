"""Explicit reference-file inventory, not a retirement/deletion authorization."""
import hashlib,json,os,re
from pathlib import Path
from contextlib import closing
from malts_lifecycle import classify_generation_id,_obsolete_generation_references,_generation_reference_token_kinds
from v2_legacy_reader import read_source_bytes
from v2_evidence import _regular_path
from v2_definition_content import decode


def _host_references(root,binding):
    from v2_process_host import _connect
    root=Path(root)
    if not root.is_absolute():raise ValueError('Explicit absolute Host journal root required')
    before=read_source_bytes(root,'host.db',max_bytes=67108864)
    references=[]
    with closing(_connect(root,readonly=True)) as c:
        c.execute('BEGIN')
        instance=c.execute('SELECT instance_id FROM identity WHERE singleton=1').fetchone()[0]
        rows=c.execute('SELECT backend_key,state,length(spec_value) FROM run ORDER BY backend_key LIMIT 201').fetchall()
        if len(rows)>200 or any(r[2]>8388608 for r in rows) or sum(r[2] for r in rows)>16777216:
            raise ValueError('Host reference inspection budget exceeded')
        for key,state,_ in rows:
            stored=c.execute('SELECT spec_value FROM run WHERE backend_key=?',(key,)).fetchone()[0]
            spec=decode(stored,instance,'process-host',key,1,'spec')
            if not isinstance(spec,dict):raise ValueError('Host spec is not a structured record')
            pending=[spec];texts=[]
            while pending:
                value=pending.pop()
                if isinstance(value,str):texts.append(value)
                elif isinstance(value,dict):pending.extend(value.values())
                elif isinstance(value,list):pending.extend(value)
            kinds=_generation_reference_token_kinds(texts,binding)
            if kinds:references.append({'surface':'protected-host-spec','path':str(root/'host.db'),
                'backend_key':key,'recorded_state':state,'token_kinds':kinds})
        c.execute('COMMIT')
    after=read_source_bytes(root,'host.db',max_bytes=67108864)
    if before['sha256']!=after['sha256']:raise ValueError('Host journal changed during reference inspection')
    return {'path':str(root/'host.db'),'sha256':before['sha256'],'bytes':before['bytes'],
        'journal_version':3,'spec_records_inspected':len(rows),'private_content_returned':False},references


def _core_references(root,binding):
    from v2_state_store import StateStore,SCHEMA_VERSION
    root=Path(root)
    if not root.is_absolute():raise ValueError('Explicit absolute Core state root required')
    before=read_source_bytes(root,'state.db',max_bytes=67108864)
    references=[]
    def check(kind,identity,revision,field,values,base=None):
        texts=[]
        for value in values:
            if not isinstance(value,str):raise ValueError('Invalid Core reference field')
            texts.append(value)
            if base is not None and not Path(value).is_absolute() and ':' not in value:
                texts.append(str(Path(base)/value))
        matched=_generation_reference_token_kinds(texts,binding)
        if matched:references.append({'surface':'core-resource-reference','path':str(root/'state.db'),
            'entity_type':kind,'entity_id':identity,'revision':revision,'field':field,'token_kinds':matched})
    with closing(StateStore(root/'state.db',readonly=True)) as store:
        c=store.connection;c.execute('BEGIN')
        counts={table:c.execute('SELECT count(*) FROM '+table).fetchone()[0]
            for table in ('project','task_revision','phase_revision','execution_grant')}
        if sum(counts.values())>2000:raise ValueError('Core reference row budget exceeded')
        size=c.execute('SELECT coalesce(sum(length(scope_json)),0),coalesce(max(length(scope_json)),0) FROM task_revision').fetchone()
        if size[0]>16777216 or size[1]>8388608:raise ValueError('Core protected scope budget exceeded')
        projects=dict(c.execute('SELECT project_id,resource_root FROM project'))
        for identity,path in projects.items():check('Project',identity,None,'resource_root',[path])
        for task_id,owner,revision,stored in c.execute('''SELECT r.task_id,t.project_id,r.revision,r.scope_json
                FROM task_revision r JOIN task t ON t.task_id=r.task_id ORDER BY r.task_id,r.revision'''):
            scope=decode(stored,owner,'task',task_id,revision,'scope')
            if not isinstance(scope,list):raise ValueError('Invalid protected Task scope')
            check('Task',task_id,revision,'scope',scope,projects[owner])
        for identity,owner,revision,path,scope in c.execute('''SELECT r.phase_id,p.project_id,r.revision,r.plan_ref,r.plan_scope
                FROM phase_revision r JOIN phase p ON p.phase_id=r.phase_id ORDER BY r.phase_id,r.revision'''):
            if scope not in {'PROJECT','STATE'}:raise ValueError('Unsupported plan reference scope')
            check('Phase',identity,revision,'plan_ref',[path],root if scope=='STATE' else projects[owner])
        for grant,owner,revision,resource in c.execute('''SELECT g.grant_id,t.project_id,g.task_revision,g.resource
                FROM execution_grant g JOIN task t ON t.task_id=g.task_id ORDER BY g.grant_id'''):
            check('Grant',grant,revision,'resource',[resource],projects[owner])
        c.execute('COMMIT')
    after=read_source_bytes(root,'state.db',max_bytes=67108864)
    if before['sha256']!=after['sha256']:raise ValueError('Core state changed during reference inspection')
    return {'path':str(root/'state.db'),'sha256':before['sha256'],'bytes':before['bytes'],'core_schema':SCHEMA_VERSION,
        'row_counts':counts,'checked_fields':['project.resource_root','task_revision.scope','phase_revision.plan_ref','execution_grant.resource'],
        'compatible_replacement_reader_verified':False,'private_content_returned':False},references


def inspect_references(*,generation_root,generation_id,reference_files=None,host_journals=None,core_states=None,expected_report_sha256=None):
    if expected_report_sha256 is not None:
        if not isinstance(expected_report_sha256,str) or re.fullmatch('[a-fA-F0-9]{64}',expected_report_sha256) is None:
            raise ValueError('Expected report digest must be SHA256')
        expected_report_sha256=expected_report_sha256.lower()
    classify_generation_id(generation_id)
    target=Path(generation_root)
    if not target.is_absolute() or target.name!=generation_id:raise ValueError('Exact absolute generation root and identity required')
    _regular_path(target)
    reference_files=[] if reference_files is None else reference_files
    host_journals=[] if host_journals is None else host_journals
    core_states=[] if core_states is None else core_states
    if not isinstance(reference_files,list) or len(reference_files)>64:raise ValueError('Select at most 64 reference files')
    if not isinstance(host_journals,list) or len(host_journals)>16:raise ValueError('Select at most 16 Host journals')
    if not isinstance(core_states,list) or len(core_states)>16 or not (reference_files or host_journals or core_states):raise ValueError('Select explicit references or at most 16 Core stores')
    if len({os.path.normcase(os.path.abspath(p)) for p in host_journals})!=len(host_journals):raise ValueError('Duplicate Host journal')
    if len({os.path.normcase(os.path.abspath(p)) for p in core_states})!=len(core_states):raise ValueError('Duplicate Core store')
    files=[];seen=set();total=0
    for value in reference_files:
        path=Path(value)
        if not path.is_absolute():raise ValueError('Reference paths must be absolute')
        if path.suffix.lower() not in {'.md','.txt','.json'}:raise ValueError('Only explicit UTF8 Markdown, text and JSON references are supported')
        key=os.path.normcase(os.path.abspath(path))
        if key in seen:raise ValueError('Duplicate reference file')
        seen.add(key)
        record=read_source_bytes(path.parent,path.name,max_bytes=min(4194304,16777216-total))
        if '\0' in record['raw_bytes'].decode('utf-8-sig'):raise ValueError('Binary reference input is not supported')
        total+=record['bytes']
        if total>16777216:raise ValueError('Reference inventory exceeds byte budget')
        files.append({'path':str(path),'sha256':record['sha256'],'bytes':record['bytes']})
    context={'obsolete_generation_bindings':[{'generation_id':generation_id,'root':str(target)}],'tool_roots':{}}
    references=_obsolete_generation_references(target.parent.parent,context,
        reference_surfaces=[('explicit-workspace-or-recovery-reference',Path(row['path'])) for row in files])
    journals=[]
    for root in host_journals:
        metadata,found=_host_references(root,context['obsolete_generation_bindings'][0])
        journals.append(metadata);references.extend(found)
    stores=[]
    for root in core_states:
        metadata,found=_core_references(root,context['obsolete_generation_bindings'][0])
        stores.append(metadata);references.extend(found)
    # An early journal/store can change while a later source is inspected.
    # Recheck every selected source before publishing the combined observation;
    # this is still not a cross-file lock or an execution authorization.
    for group,limit in ((files,4194304),(journals+stores,67108864)):
        for row in group:
            path=Path(row['path'])
            current=read_source_bytes(path.parent,path.name,max_bytes=limit)
            if current['sha256']!=row['sha256'] or current['bytes']!=row['bytes']:raise ValueError('Reference changed during inspection')
    report={'format':'malts.retirement-reference-report','version':3,'generation_id':generation_id,'generation_root':str(target),
        'decision':'REFERENCED' if references else 'NO_REFERENCE_IN_SELECTED_FILES','files':files,'references':references,
        'host_journals':journals,'core_states':stores,'scope':'SELECTED_FILES_HOST_SPECS_AND_CORE_RESOURCE_FIELDS','atomic_snapshot':False,
        'reference_kind':'LITERAL_IDENTIFIER_OR_PATH','dependency_semantics_verified':False,
        'complete_global_inventory':False,'active_status_verified':False,
        'generation_payload_verified':False,'encrypted_or_binary_references_interpreted':bool(journals or stores),
        'core_database_references_interpreted':bool(stores),
        'uninspected_core_domains':['operation-input-bodies','evidence-and-growth','checkpoint-bodies','host-dispatch-bodies','definition-goals'],
        'retirement_authorized':False,'writes_performed':False}
    digest=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    report['report_sha256']=digest
    report['matches_expected_report']=None if expected_report_sha256 is None else expected_report_sha256==digest
    if expected_report_sha256 is not None and expected_report_sha256!=digest:report['decision']='REFERENCE_REVIEW_STALE'
    return report
