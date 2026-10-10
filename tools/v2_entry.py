"""Read-only candidate entry negotiation. Never activates, migrates or grants."""
import json,os,re,sqlite3
from pathlib import Path
from contextlib import closing
from malts_lifecycle import resolve_discovery,verify_installed_generation_envelope,classify_generation_id,LifecycleError,LOCK_RELATIVE
from v2_state_store import StateStore,StateConflict,SCHEMA_VERSION,APPLICATION_ID
from v2_evidence import _regular_path
from v2_legacy_reader import read_source_bytes
from v2_compatibility import inspect_contract,current_contract

LOADED_ROOT=Path(__file__).resolve().parent.parent


def _same(a,b):return os.path.normcase(os.path.abspath(a))==os.path.normcase(os.path.abspath(b))


def _json_file(root,relative):
    def unique(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate entry field')
            result[key]=value
        return result
    return json.loads(read_source_bytes(root,relative,max_bytes=1048576)['raw_bytes'].decode('utf-8-sig'),object_pairs_hook=unique)


def _workspace_format(workspace):
    root=Path(workspace).absolute()
    if str(root).startswith(('\\\\','//')):raise ValueError('Local workspace required')
    _regular_path(root)
    binding_path=root/'runtime/v2_binding.json';_regular_path(binding_path)
    _regular_path(root/'state.db');_regular_path(root/'runtime/workspace_control.json')
    if binding_path.exists():
        binding=_json_file(root,'runtime/v2_binding.json')
        if (not isinstance(binding,dict) or set(binding)!={'format','schema','adoption_id','epoch','state_dir','source_root'} or
                binding['format']!='malts.v2.binding' or type(binding['schema']) is not int or binding['schema']!=1 or
                not all(isinstance(binding[k],str) and binding[k] for k in ('adoption_id','epoch','state_dir','source_root')) or
                not _same(binding['source_root'],root) or not Path(binding['state_dir']).is_absolute() or
                binding['state_dir'].startswith(('\\\\','//'))):
            raise ValueError('Unsupported or mismatched workspace binding')
        state=Path(binding['state_dir']);kind='BOUND_V2_STORE'
    elif (root/'.malts/native.json').exists():
        from v2_management import native_location
        state=native_location(root);kind='OWNED_NATIVE_STORE'
    elif (root/'state.db').exists():state=root;kind='DIRECT_CANDIDATE_STORE'
    elif (root/'runtime/workspace_control.json').exists():
        value=_json_file(root,'runtime/workspace_control.json')
        if not isinstance(value,dict) or value.get('contract_id')!='malts.workspace.current':raise ValueError('Unknown legacy entry')
        return {'kind':'LEGACY_WORKSPACE','schema':None,'current_schema_opened':False}
    else:raise ValueError('No selected workspace entry')
    database=state/'state.db';_regular_path(database)
    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)) as c:
        if c.execute('PRAGMA application_id').fetchone()[0]!=APPLICATION_ID:raise ValueError('Foreign state database')
        schema=c.execute('PRAGMA user_version').fetchone()[0]
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('project','task','task_revision','recovery_state')")}
        if tables!={'project','task','task_revision','recovery_state'}:raise ValueError('Unrecognized state database')
    if schema==SCHEMA_VERSION:
        with closing(StateStore(database,readonly=True)) as store:
            if kind=='BOUND_V2_STORE':
                from v2_adoption import require_active_binding
                row=store.connection.execute('SELECT state,new_epoch,plan_json FROM migration_adoption WHERE adoption_id=?',(binding['adoption_id'],)).fetchone()
                if row is None or row[:2]!=('ACTIVE',binding['epoch']):
                    raise ValueError('Workspace adoption receipt differs')
                plan=json.loads(row[2])
                if not isinstance(plan,dict) or not isinstance(plan.get('source_root'),str) or not _same(plan['source_root'],root):
                    raise ValueError('Workspace adoption source differs')
                require_active_binding(store)
    return {'kind':kind,'schema':schema,'current_schema_opened':schema==SCHEMA_VERSION}


def _identity(discovery):
    return tuple(discovery[k] for k in ('malts_root','generation_id','version','artifact_sha256'))+(discovery['tool_boot']['sha256'],)


def workspace_readiness(store,project_id=None):
    """Verify governance bodies and plans in one read transaction; grant no effects."""
    from v2_governance import checked_phase_plan,require_carry_lineage
    from v2_definition_content import decode
    from v2_contracts import criteria,phase_boundary
    c=store.connection
    projects=c.execute('SELECT project_id,resource_root FROM project ORDER BY project_id LIMIT 2').fetchall() if project_id is None else c.execute('SELECT project_id,resource_root FROM project WHERE project_id=?',(project_id,)).fetchall()
    if len(projects)!=1:raise ValueError('Workspace requires one selected Project')
    project_id,resource_root=projects[0]
    original=c.execute('SELECT original_goal FROM project WHERE project_id=?',(project_id,)).fetchone()[0]
    if not decode(original,project_id,'project-original',project_id,0,'goal').strip():raise ValueError('Original Project goal is empty')
    current=c.execute('SELECT revision,goal,acceptance_json FROM project_revision WHERE project_id=? ORDER BY revision DESC LIMIT 1',(project_id,)).fetchone()
    project_verified=False
    if current:
        if not decode(current[1],project_id,'project',project_id,current[0],'goal').strip():raise ValueError('Project goal is empty')
        criteria(decode(current[2],project_id,'project',project_id,current[0],'acceptance'));project_verified=True
    phases=c.execute('SELECT p.phase_id,p.revision,p.state,r.goal,r.boundary_json,r.acceptance_json,r.plan_ref,r.plan_sha256,r.plan_scope FROM phase p JOIN phase_revision r ON r.phase_id=p.phase_id AND r.revision=p.revision WHERE p.project_id=? ORDER BY p.phase_id',(project_id,)).fetchall()
    active=[]
    for row in phases:
        phase_id,revision,state=row[:3]
        if not decode(row[3],project_id,'phase',phase_id,revision,'goal').strip():raise ValueError('Phase goal is empty')
        phase_boundary(decode(row[4],project_id,'phase',phase_id,revision,'boundary'))
        criteria(decode(row[5],project_id,'phase',phase_id,revision,'acceptance'))
        # Completed historical Phases may bind older Project revisions. Readiness
        # requires the current active Phase, not requalification of past work.
        if state=='ACTIVE':
            checked_phase_plan(store,phase_id,revision)
            active.append({'phase_id':phase_id,'revision':revision,'plan_ref':row[6],'plan_sha256':row[7],'plan_scope':row[8],'plan_content_verified':True})
    if len(active)>1:raise StateConflict('Ambiguous active Phases')
    blockers=[];tasks=0;dependencies=0;binding_count=0
    for task_id,revision in c.execute('SELECT task_id,revision FROM task WHERE project_id=? ORDER BY task_id',(project_id,)).fetchall():
        task=store.task(task_id);tasks+=1
        if not task['goal'].strip():raise ValueError('Task goal is empty')
        criteria(task['acceptance'])
        binding=c.execute('SELECT b.phase_id,b.phase_revision,p.revision,p.state FROM phase_task b JOIN phase p ON p.phase_id=b.phase_id WHERE b.task_id=? AND b.task_revision=?',(task_id,revision)).fetchone()
        if phases and binding is None:blockers.append('TASK_PHASE_BINDING_MISSING')
        elif binding:
            binding_count+=1;require_carry_lineage(store,task_id,revision)
            if binding[1]!=binding[2] and binding[3]=='ACTIVE':blockers.append('TASK_PHASE_REVISION_STALE')
        for dep,dep_revision,dep_project,exists in c.execute('SELECT d.predecessor_id,d.predecessor_revision,t.project_id,r.revision FROM dependency d LEFT JOIN task t ON t.task_id=d.predecessor_id LEFT JOIN task_revision r ON r.task_id=d.predecessor_id AND r.revision=d.predecessor_revision WHERE d.task_id=? AND d.task_revision=?',(task_id,revision)):
            dependencies+=1
            if exists is None or dep_project!=project_id:raise StateConflict('Task dependency definition is invalid')
    epoch,reconciliation=c.execute('SELECT epoch,reconciliation_required FROM recovery_state WHERE singleton=1').fetchone()
    domains=store.pending_migration_domains()
    if not project_verified:blockers.append('PROJECT_DEFINITION_MISSING')
    if not active:blockers.append('ACTIVE_PHASE_MISSING')
    if reconciliation:blockers.append('RECONCILIATION_REQUIRED')
    if domains:blockers.append('MIGRATION_DOMAINS_PENDING')
    if c.execute('SELECT 1 FROM task_effect_recovery LIMIT 1').fetchone():blockers.append('EFFECT_RECOVERY_REQUIRED')
    return {'project_id':project_id,'project_revision':current[0] if current else None,'resource_root':resource_root,'epoch':epoch,
        'profile':'LONG_PROJECT' if phases else 'TASK_ONLY','active_phase':active[0] if active else None,
        'phase_ready':bool(active) and not blockers,'readiness_blockers':sorted(set(blockers)),
        'reconciliation_required':bool(reconciliation),'pending_migration_domains':domains,
        'definition_body_reverified':True,'project_definition_verified':project_verified,
        'task_definitions_verified':tasks,'task_phase_bindings_verified':binding_count,'dependencies_verified':dependencies,
        'readiness_scope':'GOVERNANCE_ONLY','execution_authorized':False,'writes_performed':False}


def inspect_workspace_entry(workspace):
    """Classify before opening a database; imported state never becomes native."""
    root=Path(workspace).absolute();_regular_path(root)
    binding_path=root/'runtime/v2_binding.json';_regular_path(binding_path)
    if binding_path.exists():
        binding=_json_file(root,'runtime/v2_binding.json')
        _workspace_format(root)  # verify exact fields, receipt, source and seals
        with closing(StateStore(Path(binding['state_dir'])/'state.db',readonly=True)) as store:
            c=store.connection;c.execute('BEGIN')
            from v2_adoption import require_active_binding
            require_active_binding(store)
            row=c.execute('SELECT project_id FROM migration_adoption WHERE adoption_id=?',(binding['adoption_id'],)).fetchone()
            ready=workspace_readiness(store,row[0])
            c.execute('COMMIT')
            return {**ready,'decision':'ADOPTED_WORKSPACE','state_dir':binding['state_dir'],'binding_status':'VERIFIED','adoption_performed':False}
    if (root/'.malts/native.json').exists():
        from v2_management import native_location
        return inspect_native_workspace(native_location(root))
    _regular_path(root/'state.db')
    if (root/'state.db').exists():
        with closing(StateStore(root/'state.db',readonly=True)) as store:
            c=store.connection
            if c.execute('SELECT 1 FROM legacy_control_source LIMIT 1').fetchone() or c.execute('SELECT 1 FROM migration_adoption LIMIT 1').fetchone():
                return {'decision':'ADOPTION_REQUIRED','reason':'IMPORTED_STORE_REQUIRES_VERIFIED_SOURCE_BINDING',
                    'next_command':'adoption-status or legacy-adoption-preflight','profile':None,'phase_ready':False,
                    'execution_authorized':False,'writes_performed':False}
        return inspect_native_workspace(root)
    for name in ('runtime/workspace_transaction.lock.json','runtime/artifact_transaction.lock.json'):
        _regular_path(root/name)
        if (root/name).exists():
            try:value=_json_file(root,name)
            except ValueError:value={}
            if value.get('format')=='malts.v2.source-seal':
                return {'decision':'RECOVERY_REQUIRED','reason':'SOURCE_SEALED_WITHOUT_VERIFIED_BINDING','next_command':'adoption-status',
                    'phase_ready':False,'execution_authorized':False,'writes_performed':False}
    if (root/'runtime/workspace_control.json').exists():
        _workspace_format(root)
        return {'decision':'MIGRATION_REQUIRED','reason':'LEGACY_DEFINITIONS_REQUIRE_REVIEWED_IMPORT',
            'next_command':'legacy-adoption-preflight','phase_ready':False,'execution_authorized':False,'writes_performed':False}
    return {'decision':'WORKSPACE_NOT_FOUND','reason':'NO_SELECTED_WORKSPACE_ENTRY','phase_ready':False,'execution_authorized':False,'writes_performed':False}


def inspect_native_workspace(workspace):
    """Explicit native store entry; never synthesize adoption or initialize state."""
    root=Path(workspace).absolute()
    if str(root).startswith(('\\\\','//')):raise ValueError('Local workspace required')
    _regular_path(root);_regular_path(root/'state.db');_regular_path(root/'runtime/v2_binding.json')
    if (root/'runtime/v2_binding.json').exists():raise ValueError('Use the bound workspace entry')
    with closing(StateStore(root/'state.db',readonly=True)) as store:
        from v2_native_authority import require_authority
        require_authority(store)
        c=store.connection;c.execute('BEGIN')
        if c.execute('SELECT 1 FROM legacy_control_source LIMIT 1').fetchone() or c.execute('SELECT 1 FROM migration_adoption LIMIT 1').fetchone():
            raise ValueError('Imported or adopted state requires its verified workspace binding')
        result=workspace_readiness(store)
        c.execute('COMMIT')
        return {**result,'decision':'NATIVE_WORKSPACE','state_dir':str(root),'binding_status':'EXPLICIT_NATIVE_STORE','adoption_performed':False}


def _lifecycle_lock_present(discovery):
    # Presence is enough to require the lifecycle recovery/transaction owner.
    # Neither expiry nor a malformed/empty payload proves that work stopped.
    root=Path(discovery['lifecycle_root'])
    if not root.is_absolute():raise ValueError('Absolute lifecycle authority required')
    path=root/LOCK_RELATIVE;_regular_path(path)
    return path.exists()


def _version_order(identity,version):
    if not isinstance(version,str) or re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)',version) is None:
        raise ValueError('Unsupported semantic version')
    classification=classify_generation_id(identity,expected_version=version)
    if classification['kind'] not in {'stable','preview'}:raise ValueError('Legacy generation order needs explicit review')
    return (*map(int,version.split('.')),1 if classification['kind']=='stable' else 0,classification['preview_sequence'] or 0)


def _refresh_candidate(root,active):
    """Inspect one explicitly selected immutable generation; never search/install."""
    try:
        root=Path(root).absolute();_regular_path(root)
        manifest=verify_installed_generation_envelope(root)['generation_manifest']
        candidate={'root':str(root),'generation_id':manifest['generation_id'],'version':manifest['version'],
            'artifact_sha256':manifest['artifact_sha256'],'installation_authorized':False}
        declared=inspect_contract(root)['contract']
        if declared!=current_contract():return {**candidate,'status':'MIGRATION_OR_INTERFACE_REVIEW_REQUIRED',
            'format_contract':declared,'current_format_contract':current_contract()}
        if manifest['artifact_sha256'].lower()==active['artifact_sha256'].lower():return {**candidate,'status':'ALREADY_ACTIVE_ARTIFACT'}
        if _version_order(manifest['generation_id'],manifest['version'])<=_version_order(active['generation_id'],active['version']):
            return {**candidate,'status':'NOT_NEWER'}
        return {**candidate,'status':'OPTIONAL_REFRESH','format_contract_matches':True,'disk_package_integrity_verified':True,
            'runtime_behavior_verified':False,'selected_tool_requirements_verified':False}
    except (LifecycleError,OSError,ValueError,sqlite3.Error):
        return {'status':'BLOCKED','reason':'REFRESH_CANDIDATE_UNQUALIFIED','installation_authorized':False}


def inspect_entry(*,workspace,tool_root,verify_package=False,refresh_generation=None):
    """At most one retry if active identity changes across the read window.

    Format compatibility is not execution readiness. This does not implement
    remote update discovery, complete installation qualification or a write
    fence against a later activation; writers retain their own runtime gates.
    """
    if type(verify_package) is not bool:raise ValueError('Explicit package verification mode required')
    base={'mode':'READ_ONLY','writes_performed':False,'execution_authorized':False,
        'loaded_root':str(LOADED_ROOT),'loaded_identity_source':'EXECUTING_MODULE_PATH',
        'supported_core_schema':SCHEMA_VERSION,'active_identity_source':'TOOL_LOCAL_DISCOVERY',
        'optional_update_checked':False,'runtime_write_fence_established':False,'loaded_package_bytes_verified':False,
        'deep_package_check_requested':verify_package,'disk_package_integrity_verified':False}
    for retry in range(2):
        try:
            first=resolve_discovery(tool_root)
            if _lifecycle_lock_present(first):
                return {**base,'status':'BLOCKED','reason':'LIFECYCLE_TRANSACTION_OR_RECOVERY_PENDING',
                    'identity_retries':retry,'lock_removed':False}
            loaded_matches=_same(LOADED_ROOT,first['malts_root'])
            workspace_info=None;read_failed=False;package_verified=False;format_matches=True;refresh=None
            try:
                if loaded_matches:
                    if verify_package:
                        verified=verify_installed_generation_envelope(first['malts_root'])
                        manifest=verified['generation_manifest']
                        if (manifest['generation_id']!=first['generation_id'] or manifest['version']!=first['version'] or
                                manifest['artifact_sha256'].lower()!=first['artifact_sha256'].lower()):
                            raise ValueError('Package identity differs from active discovery')
                        package_verified=True
                        declared=inspect_contract(first['malts_root'])['contract']
                        format_matches=declared==current_contract()
                    if format_matches:
                        workspace_info=_workspace_format(workspace)
                        if refresh_generation is not None and workspace_info['schema']==SCHEMA_VERSION:
                            refresh=_refresh_candidate(refresh_generation,first)
            except (LifecycleError,OSError,ValueError,sqlite3.Error):read_failed=True
            second=resolve_discovery(tool_root)
            if _lifecycle_lock_present(second):
                return {**base,'status':'BLOCKED','reason':'LIFECYCLE_TRANSACTION_OR_RECOVERY_PENDING',
                    'identity_retries':retry,'preparation_discarded':True,'lock_removed':False}
            if _identity(first)!=_identity(second):continue
            if read_failed:return {**base,'status':'BLOCKED','reason':'ENTRY_IDENTITY_OR_FORMAT_UNAVAILABLE','identity_retries':retry}
            report={**base,'active_generation_id':second['generation_id'],'active_root':second['malts_root'],
                'active_artifact_sha256':second['artifact_sha256'],'workspace':workspace_info,
                'identity_retries':retry,'preparation_discarded':bool(retry),'disk_package_integrity_verified':package_verified,
                'optional_update_checked':refresh is not None,'refresh_candidate':refresh}
            if not loaded_matches:return {**report,'status':'STALE_PROCESS','reason':'LOADED_ROOT_IS_NOT_ACTIVE'}
            if not format_matches:return {**report,'status':'STALE_PROCESS','reason':'LOADED_FORMAT_CONTRACT_DIFFERS'}
            if workspace_info['kind']=='LEGACY_WORKSPACE':return {**report,'status':'MIGRATION_REQUIRED','reason':'LEGACY_DEFINITIONS_REQUIRE_REVIEWED_IMPORT'}
            if workspace_info['schema']!=SCHEMA_VERSION:return {**report,'status':'MIGRATION_REQUIRED','reason':'STORE_SCHEMA_NOT_SUPPORTED_BY_LOADED_READER'}
            if refresh is not None and refresh['status']=='OPTIONAL_REFRESH':
                return {**report,'status':'OPTIONAL_REFRESH','reason':'EXPLICIT_NEWER_FORMAT_COMPATIBLE_CANDIDATE','current_format_compatible':True}
            return {**report,'status':'COMPATIBLE','reason':'CURRENT_STORE_FORMAT_MATCHES','execution_readiness_evaluated':False}
        except (LifecycleError,OSError,ValueError,sqlite3.Error):
            return {**base,'status':'BLOCKED','reason':'ENTRY_IDENTITY_OR_FORMAT_UNAVAILABLE','identity_retries':retry}
    return {**base,'status':'BLOCKED','reason':'ACTIVE_IDENTITY_CHANGED_REPEATEDLY','identity_retries':1,'preparation_discarded':True}
