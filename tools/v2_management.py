"""Owned workspace management namespace; not a second task-state authority."""
import json, os
from pathlib import Path
from contextlib import closing
from v2_evidence import _regular_path
from v2_state_store import StateStore, StateConflict, _json

DIRECTORY='.malts'
SELECTION={'format':'malts.v2.source-selection','version':1,
           'excluded_subtrees':['.malts'],'selection':'INDEXED_AND_EXPLICIT_FILES_ONLY'}

REASONS=frozenset({'MANAGEMENT_DIRECTORY_NOT_OWNED','MANAGEMENT_DIRECTORY_UNKNOWN_CONTENT',
    'MANAGEMENT_DIRECTORY_NOT_INITIALIZED','SOURCE_SELECTION_CONTRACT_CHANGED',
    'INTERNAL_LAYOUT_REQUIRES_REVIEWED_SOURCE_SELECTION','SOURCE_MANAGEMENT_DIRECTORY_CONFLICT',
    'MIGRATION_ROOTS_MUST_BE_SEPARATE','INTERNAL_TARGET_MUST_USE_OWNED_MANAGEMENT_LAYOUT',
    'CAPSULE_AND_STATE_MUST_BE_SEPARATE','EXISTING_WORKSPACE_REQUIRES_CURRENT_ENTRY','WORKSPACE_INITIALIZATION_TARGET_EXISTS',
    'STATE_CLOSURE_HARDLINK_NOT_SUPPORTED','STATE_TRANSACTION_OR_RECOVERY_REQUIRED','STATE_CLOSURE_ENTRY_BUDGET_EXCEEDED',
    'STATE_CLOSURE_REFERENCE_MISSING','LIVE_OR_UNRESOLVED_RUN_REQUIRES_HANDOFF','UNRESOLVED_OPERATION_REQUIRES_RECONCILIATION',
    'HOST_DISPATCH_NOT_QUIESCED','EFFECT_RECOVERY_REQUIRED','RELOCATION_STATE_AND_JOURNAL_ROOTS_MUST_BE_SEPARATE',
    'RELOCATION_TARGET_OR_JOURNAL_EXISTS_USE_ORIGINAL_STATUS','TARGET_AND_JOURNAL_REQUIRE_SAME_VOLUME',
    'INTERNAL_JOURNAL_REQUIRES_MANAGEMENT_RECOVERY_DIRECTORY','RELOCATION_TARGET_PERMISSION_OR_CAPACITY_INSUFFICIENT',
    'RELOCATION_REQUIRES_ORIGINAL_USER_AND_MACHINE','RELOCATION_ROOT_OVERLAP','ACTIVE_RUNTIME_REQUIRED',
    'OLD_STATE_CHANGED_AFTER_RELOCATION_PLAN','SOURCE_PROTOCOL_CHANGED_AFTER_RELOCATION_PLAN','RELOCATION_TARGET_EXISTS',
    'NATIVE_SOURCE_STATE_REQUIRED','ADOPTED_BINDING_MISSING_OR_DAMAGED','NATIVE_SOURCE_IDENTITY_MISMATCH',
    'SOURCE_KIND_REQUIRES_ADOPTED_WORKSPACE','RELOCATION_CONTROL_PATH_TOO_LONG'})

class ManagementConflict(StateConflict):
    def __init__(self,reason_code):
        if reason_code not in REASONS:raise ValueError('Unknown management diagnostic')
        self.reason_code=reason_code
        super().__init__(reason_code)


def root_path(value):
    from v2_adoption_host import _local_root
    return _local_root(value)


def management_root(workspace, *, require_owned=False):
    workspace=root_path(workspace); root=workspace/DIRECTORY; _regular_path(root)
    if not workspace.is_dir():raise ValueError('Existing workspace required')
    if root.exists():
        marker=root/'management.json'; _regular_path(marker)
        try:value=json.loads(marker.read_text(encoding='utf-8'))
        except (OSError,ValueError):raise ManagementConflict('MANAGEMENT_DIRECTORY_NOT_OWNED') from None
        expected={'format':'malts.v2.management','version':1,'workspace_root':str(workspace)}
        if value!=expected or type(value.get('version')) is not int:raise ManagementConflict('MANAGEMENT_DIRECTORY_NOT_OWNED')
        if any(p.name not in {'management.json','native.json','state','source-capsules','recovery'} for p in root.iterdir()):
            raise ManagementConflict('MANAGEMENT_DIRECTORY_UNKNOWN_CONTENT')
    elif require_owned:raise ManagementConflict('MANAGEMENT_DIRECTORY_NOT_INITIALIZED')
    return root


def initialize_management(workspace, *, apply=False):
    root=management_root(workspace)
    result={'decision':'MANAGEMENT_READY' if root.exists() else 'MANAGEMENT_INIT_PREVIEW',
            'management_root':str(root),'workspace_root':str(root.parent),
            'writes_performed':False,'execution_authorized':False}
    if apply and not root.exists():
        root.mkdir()  # never claim a preexisting directory
        with (root/'management.json').open('x',encoding='utf-8',newline='\n') as stream:
            stream.write(_json({'format':'malts.v2.management','version':1,'workspace_root':str(root.parent)}))
            stream.flush();os.fsync(stream.fileno())
        result.update(decision='MANAGEMENT_INITIALIZED',writes_performed=True)
    return result


def selection_conflicts(inventory):
    return [r['path'] for r in inventory['records']
            if r['path'].replace('\\','/').split('/')[0].casefold()==DIRECTORY]


def validate_selection(inventory, *, required=False):
    if 'source_selection' in inventory and inventory['source_selection']!=SELECTION:
        raise ManagementConflict('SOURCE_SELECTION_CONTRACT_CHANGED')
    if required and inventory.get('source_selection')!=SELECTION:
        raise ManagementConflict('INTERNAL_LAYOUT_REQUIRES_REVIEWED_SOURCE_SELECTION')
    if 'source_selection' in inventory and selection_conflicts(inventory):
        raise ManagementConflict('SOURCE_MANAGEMENT_DIRECTORY_CONFLICT')


def validate_layout(source, *, capsule=None, state=None, inventory=None, require_owned=False):
    source=root_path(source); roots=[root_path(p) for p in (capsule,state) if p is not None]
    internal=False
    for target in roots:
        if source.is_relative_to(target):raise ManagementConflict('MIGRATION_ROOTS_MUST_BE_SEPARATE')
        if target.is_relative_to(source):
            internal=True; managed=management_root(source,require_owned=require_owned)
            allowed=target==managed/'state' or target.is_relative_to(managed/'source-capsules')
            if not allowed or target==managed/'source-capsules':
                raise ManagementConflict('INTERNAL_TARGET_MUST_USE_OWNED_MANAGEMENT_LAYOUT')
    if len(roots)==2 and (roots[0].is_relative_to(roots[1]) or roots[1].is_relative_to(roots[0])):
        raise ManagementConflict('CAPSULE_AND_STATE_MUST_BE_SEPARATE')
    if inventory is not None:validate_selection(inventory,required=internal)
    return {'layout':'IN_WORKSPACE' if internal else 'EXTERNAL','source_selection':json.loads(json.dumps(SELECTION))}


def initialize_workspace(workspace, *, project_id, goal, state_dir=None, apply=False):
    if not isinstance(project_id,str) or not project_id.strip() or not isinstance(goal,str) or not goal.strip():
        raise ValueError('Project identity and goal must be nonempty text')
    workspace=root_path(workspace); managed=management_root(workspace)
    if (workspace/'runtime/v2_binding.json').exists() or (workspace/'runtime/workspace_control.json').exists() or (workspace/'state.db').exists():
        raise ManagementConflict('EXISTING_WORKSPACE_REQUIRES_CURRENT_ENTRY')
    state=root_path(state_dir) if state_dir else managed/'state'
    validate_layout(workspace,state=state)
    if state.exists() or (managed/'native.json').exists():raise ManagementConflict('WORKSPACE_INITIALIZATION_TARGET_EXISTS')
    result={'decision':'WORKSPACE_INIT_PREVIEW','workspace_root':str(workspace),'state_dir':str(state),
            'project_id':project_id,'writes_performed':False,'execution_authorized':False}
    if not apply:return result
    initialize_management(workspace,apply=True)
    state.mkdir()
    with closing(StateStore.initialize(state/'state.db',project_id,goal,resource_root=workspace)) as store:
        epoch=store.connection.execute('SELECT epoch FROM recovery_state').fetchone()[0]
        (state/'blobs').mkdir()
    with (managed/'native.json').open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(_json({'format':'malts.v2.native-location','version':1,'state_dir':str(state),
                            'project_id':project_id,'epoch':epoch}))
        stream.flush();os.fsync(stream.fileno())
    return {**result,'decision':'WORKSPACE_INITIALIZED','epoch':epoch,'writes_performed':True}


def native_location(workspace):
    root=management_root(workspace,require_owned=True); path=root/'native.json'; _regular_path(path)
    value=json.loads(path.read_text(encoding='utf-8'))
    if (set(value)!={'format','version','state_dir','project_id','epoch'} or
            value['format']!='malts.v2.native-location' or value['version']!=1):
        raise StateConflict('Invalid native workspace locator')
    state=root_path(value['state_dir']);validate_layout(root.parent,state=state,require_owned=True)
    with closing(StateStore(state/'state.db',readonly=True)) as store:
        projects=store.connection.execute('SELECT project_id,resource_root FROM project').fetchall()
        epoch=store.connection.execute('SELECT epoch FROM recovery_state').fetchone()[0]
        if projects!=[(value['project_id'],str(root.parent))] or epoch!=value['epoch']:
            raise StateConflict('Native workspace locator identity changed; recovery review required')
        if store.connection.execute('SELECT 1 FROM legacy_control_source LIMIT 1').fetchone() or store.connection.execute('SELECT 1 FROM migration_adoption LIMIT 1').fetchone():
            raise StateConflict('Imported state cannot use a native locator')
    return state


def protect_business_resource(store, workspace, resource):
    """Reject business-operation access to selected state and protocol files."""
    workspace=Path(workspace).resolve(); target=(workspace/resource).absolute()
    _regular_path(target); target=target.resolve()
    state=store.path.parent.resolve()
    reserved=[workspace/DIRECTORY]
    if state!=workspace:reserved.append(state)
    else:reserved.extend(state/p for p in ('state.db','blobs','legacy-source','operation-inputs','protected-inputs','plans'))
    if any(target.is_relative_to(p) for p in reserved):
        raise PermissionError('MALTS management data is not a business-operation resource')
    from v2_adoption import BINDING,SEALS
    if target in {workspace/p for p in (BINDING,*SEALS)}:
        raise PermissionError('Workspace authority protocol requires a lifecycle operation')
