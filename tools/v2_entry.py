"""Read-only candidate entry negotiation. Never activates, migrates or grants."""
import json,os,re,sqlite3
from pathlib import Path
from contextlib import closing
from malts_lifecycle import resolve_discovery,verify_installed_generation_envelope,classify_generation_id,LifecycleError,LOCK_RELATIVE
from v2_state_store import StateStore,SCHEMA_VERSION,APPLICATION_ID
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


def inspect_native_workspace(workspace):
    """Explicit native store entry; never synthesize adoption or initialize state."""
    root=Path(workspace).absolute()
    if str(root).startswith(('\\\\','//')):raise ValueError('Local workspace required')
    _regular_path(root);_regular_path(root/'state.db');_regular_path(root/'runtime/v2_binding.json')
    if (root/'runtime/v2_binding.json').exists():raise ValueError('Use the bound workspace entry')
    with closing(StateStore(root/'state.db',readonly=True)) as store:
        c=store.connection;c.execute('BEGIN')
        if c.execute('SELECT 1 FROM legacy_control_source LIMIT 1').fetchone() or c.execute('SELECT 1 FROM migration_adoption LIMIT 1').fetchone():
            raise ValueError('Imported or adopted state requires its verified workspace binding')
        projects=c.execute('SELECT project_id,resource_root FROM project ORDER BY project_id LIMIT 2').fetchall()
        if len(projects)!=1:raise ValueError('Native workspace requires one unambiguous Project')
        project_id,resource_root=projects[0]
        phases=c.execute("SELECT phase_id,revision FROM phase WHERE project_id=? AND state='ACTIVE' ORDER BY phase_id LIMIT 2",(project_id,)).fetchall()
        if len(phases)>1:raise ValueError('Native workspace has ambiguous active Phases')
        has_phases=bool(c.execute('SELECT 1 FROM phase WHERE project_id=? LIMIT 1',(project_id,)).fetchone())
        phase=None
        if phases:
            from v2_governance import checked_phase_plan
            checked_phase_plan(store,phases[0][0],phases[0][1])
            phase={'phase_id':phases[0][0],'revision':phases[0][1],'plan_content_verified':True}
        epoch,reconciliation=c.execute('SELECT epoch,reconciliation_required FROM recovery_state WHERE singleton=1').fetchone()
        domains=store.pending_migration_domains()
        return {'decision':'NATIVE_WORKSPACE','state_dir':str(root),'project_id':project_id,
                'resource_root':resource_root,'epoch':epoch,'binding_status':'EXPLICIT_NATIVE_STORE',
                'profile':'LONG_PROJECT' if has_phases else 'TASK_ONLY','active_phase':phase,
                'phase_ready':phase is not None and not reconciliation and not domains,
                'reconciliation_required':bool(reconciliation),'pending_migration_domains':domains,
                'adoption_performed':False,'execution_authorized':False,'writes_performed':False}


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
