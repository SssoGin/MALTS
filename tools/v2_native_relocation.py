"""Native store relocation through shared backup/recovery and real handoff locks."""
import hashlib,json,os
from pathlib import Path
from contextlib import closing
from v2_state_store import StateStore,StateConflict,_json
from v2_management import ManagementConflict,root_path,native_location
from v2_native_authority import current,append,lifecycle_transaction,require_authority,KIND
from v2_backup import verify_backup,_hash as file_hash,_managed_paths
from v2_forward_recovery import state_hash,replace_protocol
from v2_recovery import TABLES,require_project_review

LOCATOR='.malts/native.json'


def replace_locator(source,journal,previous,following,operation_id):
    from v2_adoption import _write_owned
    from v2_evidence import _regular_path
    path=source/LOCATOR;_regular_path(path)
    if path.read_bytes()==following:return
    if path.read_bytes()!=previous:raise StateConflict('Native locator preimage changed')
    saved_root=journal if journal.anchor.casefold()==source.anchor.casefold() else source/'.malts/recovery'/(operation_id+'-locator')
    _regular_path(saved_root);saved_root.mkdir(parents=True,exist_ok=True)
    staged=saved_root/'native-locator.next'
    _write_owned(saved_root/'native-locator.preimage',previous);_write_owned(staged,following)
    if path.read_bytes()!=previous:raise StateConflict('Native locator changed before atomic replacement')
    os.replace(staged,path)


def classify_source(workspace,explicit=None):
    from v2_adoption import BINDING,SEALS,require_active_binding
    if (workspace/BINDING).exists():
        try:
            binding=json.loads((workspace/BINDING).read_text(encoding='utf-8'))
            state=root_path(binding['state_dir'])
            if explicit is not None and root_path(explicit)!=state:raise StateConflict('Explicit source differs from adopted binding')
            with closing(StateStore(state/'state.db',readonly=True)) as store:require_active_binding(store)
            return {'source_kind':'ADOPTED','state_dir':str(state),'adoption_id':binding['adoption_id'],'protocol_paths':[BINDING,*SEALS]}
        except (KeyError,ValueError):raise ManagementConflict('ADOPTED_BINDING_MISSING_OR_DAMAGED') from None
    if any((workspace/p).exists() for p in SEALS):raise ManagementConflict('ADOPTED_BINDING_MISSING_OR_DAMAGED')
    located=(workspace/LOCATOR).exists()
    if located:state=native_location(workspace)
    elif explicit is not None:state=root_path(explicit)
    elif (workspace/'state.db').exists():state=workspace
    else:raise ManagementConflict('NATIVE_SOURCE_STATE_REQUIRED')
    if explicit is not None and state!=root_path(explicit):raise ManagementConflict('NATIVE_SOURCE_IDENTITY_MISMATCH')
    with closing(StateStore(state/'state.db',readonly=True)) as store:
        projects=store.connection.execute('SELECT project_id,resource_root FROM project').fetchall()
        if len(projects)!=1 or projects[0][1]!=str(workspace):
            raise ManagementConflict('NATIVE_SOURCE_IDENTITY_MISMATCH')
        if store.connection.execute('SELECT 1 FROM legacy_control_source LIMIT 1').fetchone() or store.connection.execute('SELECT 1 FROM migration_adoption LIMIT 1').fetchone():
            raise ManagementConflict('SOURCE_KIND_REQUIRES_ADOPTED_WORKSPACE')
        store.require_execution_ready()
        return {'source_kind':'NATIVE_LOCATOR' if located else 'NATIVE_EXPLICIT','project_id':projects[0][0],
                'state_dir':str(state),'protocol_paths':[LOCATOR] if located else [],'native_authority':current(store.connection)}


def check_source(plan,store, *, allow_locator_change=False):
    from v2_adoption import BINDING,SEALS
    root=Path(plan['workspace_root'])
    if any((root/p).exists() for p in (BINDING,*SEALS)):raise ManagementConflict('SOURCE_KIND_REQUIRES_ADOPTED_WORKSPACE')
    if store.connection.execute('SELECT project_id,resource_root FROM project').fetchall()!=[(plan['project_id'],str(root))]:
        raise ManagementConflict('NATIVE_SOURCE_IDENTITY_MISMATCH')
    if not allow_locator_change and ((root/LOCATOR).exists()!=(plan['source_kind']=='NATIVE_LOCATOR') or current(store.connection)!=plan['old_native_authority']):
        raise ManagementConflict('SOURCE_PROTOCOL_CHANGED_AFTER_RELOCATION_PLAN')


def fact(plan,store,state, *, receipt_sha256=None):
    return {'format':'malts.v2.native-authority','version':1,'operation_id':plan['operation_id'],
            'state':state,'epoch':store.connection.execute('SELECT epoch FROM recovery_state').fetchone()[0],
            'state_dir':str(store.path.parent.resolve()),'workspace_root':plan['workspace_root'],
            'journal_root':plan['journal_root'],'plan_sha256':plan['plan_sha256'],'receipt_sha256':receipt_sha256}


def quarantine_target(plan,staged):
    with closing(StateStore(staged/'state.db')) as store:
        previous=current(store.connection)
        value=fact(plan,store,'RESTORED');value['state_dir']=plan['state_dir']
        with lifecycle_transaction(store,previous) as c:append(c,value)


def native_status(result,store,journal):
    value=current(store.connection)
    if value is None:raise StateConflict('Native relocation target has no quarantine authority fact')
    if value['operation_id']!=result['plan']['operation_id']:
        result['state']='SUPERSEDED';return
    if value['state'] in {'PREPARED','ACTIVE','SUPERSEDED'}:result['state']=value['state']
    path=journal/'native-forward.json'
    if path.exists():result['forward']={'plan':json.loads(path.read_text(encoding='utf-8')),'state':result['state']}
    if result['state']=='ACTIVE':
        require_authority(store)
        receipt=json.loads((journal/'native-cutover.json').read_text(encoding='utf-8'))
        from v2_relocation import _hash
        if _hash(receipt)!=value['receipt_sha256']:raise StateConflict('Native cutover receipt changed')
        result['receipt']=receipt


def _without_current_transition(store,operation_id):
    from v2_relocation import _hash
    import hashlib
    hashes={}
    for table in TABLES:
        if table=='migration_adoption':continue
        digest=hashlib.sha256()
        if table=='execution_audit':
            rows=store.connection.execute('SELECT * FROM execution_audit WHERE NOT(kind=? AND subject_id=?) ORDER BY 1',(KIND,operation_id))
        else:rows=store.connection.execute(f'SELECT * FROM {table} ORDER BY 1')
        for row in rows:digest.update((_json(list(row))+'\n').encode('utf-8'))
        hashes[table]=digest.hexdigest()
    return _hash(hashes)


def _basis(store,old,original,target):
    from v2_relocation import _hash
    manifest=verify_backup(Path(target['backup_root']))
    with closing(StateStore(Path(target['backup_root'])/'state.db',readonly=True)) as saved:
        if state_hash(saved.connection)!=original['old_state_sha256']:raise StateConflict('Native backup differs from the original plan')
    if _without_current_transition(old,original['operation_id'])!=original['old_state_sha256']:
        raise StateConflict('Native source advanced beyond the reviewed backup')
    if _managed_paths(old.connection)!=[r['path'] for r in manifest['managed_files']]:raise StateConflict('Native managed references changed')
    for record in manifest['managed_files']:
        for root in (old.path.parent,store.path.parent):
            if file_hash(root/record['path'])!=record['sha256']:raise StateConflict('Native managed input changed')
    from v2_evidence import BlobStore
    for root in (old.path.parent,store.path.parent):
        blobs=BlobStore(root/'blobs',readonly=True)
        for digest in manifest['blobs']:blobs.verify(digest)
    recovery=store.connection.execute('SELECT epoch,reconciliation_required,source_backup_hash FROM recovery_state').fetchone()
    if recovery!=(target['epoch'],0,manifest['database_sha256']):raise StateConflict('Native target requires current-epoch effect reconciliation')
    row=store.connection.execute('SELECT review_id,receipt_json FROM recovery_review WHERE epoch=?',(target['epoch'],)).fetchone()
    if row is None or json.loads(row[1]).get('decision')!='RECONCILED':raise StateConflict('Native target recovery review is missing')
    require_project_review(store.connection,row[0],target['epoch'])
    return _hash(manifest),row[0]


def forward_plan(journal_root):
    from v2_relocation import status,_hash,_healthy
    info=status(journal_root);original=info['plan'];target=info.get('target')
    if original.get('source_kind','ADOPTED')=='ADOPTED':
        from v2_forward_recovery import ForwardRecovery
        with closing(StateStore(Path(original['state_dir'])/'state.db',readonly=True)) as store,closing(StateStore(Path(original['old_state_dir'])/'state.db',readonly=True)) as old:
            return ForwardRecovery(store,old).plan(backup_root=target['backup_root'],adoption_id=original['operation_id'],authority_ref=original['authority_ref'])
    if not target:raise StateConflict('Native relocation preparation is incomplete')
    if info['state'] in {'PREPARED','ACTIVE'}:return info['forward']['plan']
    with closing(StateStore(Path(original['state_dir'])/'state.db',readonly=True)) as store,closing(StateStore(Path(original['old_state_dir'])/'state.db',readonly=True)) as old:
        _healthy(old,native=True);check_source(original,old)
        if old.connection.execute('SELECT 1 FROM execution_audit WHERE kind=? AND subject_id=?',(KIND,original['operation_id'])).fetchone():
            raise StateConflict('Native relocation identity was already used')
        manifest_hash,review=_basis(store,old,original,target)
        locator={'format':'malts.v2.native-location','version':1,'state_dir':original['state_dir'],'project_id':original['project_id'],'epoch':target['epoch']}
        path=Path(original['workspace_root'])/LOCATOR
        value={'format':'malts.v2.native-forward-plan','version':1,'source_root':original['workspace_root'],
            'old_state_dir':original['old_state_dir'],'state_dir':original['state_dir'],'journal_root':original['journal_root'],
            'backup_root':target['backup_root'],'backup_manifest_sha256':manifest_hash,'adoption_id':original['operation_id'],
            'relocation_plan_sha256':original['plan_sha256'],'old_state_sha256':original['old_state_sha256'],
            'new_state_sha256':_without_current_transition(store,original['operation_id']),
            'old_locator':path.read_text(encoding='utf-8') if path.exists() else None,'new_locator':locator,
            'old_epoch':original['old_epoch'],'new_epoch':target['epoch'],'project_id':original['project_id'],
            'recovery_review_id':review,'authority_ref':original['authority_ref'],'profile':original['profile'],
            'execution_authorized':False,'writes_performed':False}
        value['plan_sha256']=_hash(value);return value


def validate_forward(plan):
    from v2_relocation import _hash,PROFILE
    fields={'format','version','source_root','old_state_dir','state_dir','journal_root','backup_root','backup_manifest_sha256','adoption_id',
            'relocation_plan_sha256','old_state_sha256','new_state_sha256','old_locator','new_locator','old_epoch','new_epoch','project_id',
            'recovery_review_id','authority_ref','profile','execution_authorized','writes_performed','plan_sha256'}
    if not isinstance(plan,dict) or set(plan)!=fields or plan['format']!='malts.v2.native-forward-plan' or type(plan['version']) is not int or plan['version']!=1:
        raise ValueError('Invalid native forward plan')
    if (_hash({k:v for k,v in plan.items() if k!='plan_sha256'})!=plan['plan_sha256'] or plan['execution_authorized'] is not False or
            plan['writes_performed'] is not False or plan['profile']!=PROFILE):raise StateConflict('Native forward plan changed')


def apply(plan, *, expected_plan_sha256,journal_root,tool_root=None,apply=False):
    from v2_relocation import _hash,_write,status,_active_runtime,WindowsForwardHandoff
    from v2_adoption import _write_owned
    validate_forward(plan)
    if expected_plan_sha256!=plan['plan_sha256']:raise StateConflict('Reviewed native forward plan differs')
    if tool_root is not None:_active_runtime(tool_root)
    info=status(journal_root);original=info['plan'];target=info.get('target',{})
    for key,source_key in [('source_root','workspace_root'),('old_state_dir','old_state_dir'),('state_dir','state_dir'),('journal_root','journal_root'),('adoption_id','operation_id'),('relocation_plan_sha256','plan_sha256')]:
        if plan[key]!=original[source_key]:raise StateConflict('Native forward plan differs from the original journal')
    if original.get('source_kind','ADOPTED')=='ADOPTED' or plan['backup_root']!=target.get('backup_root'):
        raise StateConflict('Native forward source or backup differs')
    locator_identity={'format':'malts.v2.native-location','version':1,'state_dir':original['state_dir'],'project_id':original['project_id'],'epoch':target['epoch']}
    if (plan['new_locator']!=locator_identity or plan['old_epoch']!=original['old_epoch'] or plan['new_epoch']!=target['epoch'] or
            plan['project_id']!=original['project_id'] or plan['old_state_sha256']!=original['old_state_sha256'] or plan['authority_ref']!=original['authority_ref']):
        raise StateConflict('Native forward identity differs from preparation')
    if original['source_kind']=='NATIVE_EXPLICIT':
        if plan['old_locator'] is not None:raise StateConflict('Unexpected native locator preimage')
    elif not isinstance(plan['old_locator'],str) or hashlib.sha256(plan['old_locator'].encode('utf-8')).hexdigest()!=next(r['sha256'] for r in original['source_protocol'] if r['path']==LOCATOR):
        raise StateConflict('Native locator preimage differs from original plan')
    if info['state']=='ACTIVE':
        if info['receipt']['native_forward_plan']!=plan:raise StateConflict('Native completed identity differs')
        return {**info['receipt'],'replayed':True,'writes_performed':False,'host_revalidated':False}
    if not apply:return {'decision':'NATIVE_RELOCATION_NOT_APPLIED','plan_sha256':plan['plan_sha256'],'execution_authorized':False,'writes_performed':False}
    journal=Path(original['journal_root'])
    with closing(StateStore(Path(plan['state_dir'])/'state.db')) as store,closing(StateStore(Path(plan['old_state_dir'])/'state.db')) as old:
        with WindowsForwardHandoff(store,old).handoff(plan) as witness:
            check_source(original,old,allow_locator_change=True)
            manifest_hash,review=_basis(store,old,original,target)
            if manifest_hash!=plan['backup_manifest_sha256'] or review!=plan['recovery_review_id']:
                raise StateConflict('Native forward recovery basis changed')
            if _without_current_transition(store,original['operation_id'])!=plan['new_state_sha256']:
                raise StateConflict('Native target changed after forward planning')
            source=Path(plan['source_root']);locator=source/LOCATOR
            previous=plan['old_locator'].encode('utf-8') if plan['old_locator'] is not None else None
            following=_json(plan['new_locator']).encode('utf-8')
            actual=locator.read_bytes() if locator.exists() else None
            if actual not in (previous,following):raise StateConflict('Native locator changed outside the reviewed cutover')
            _write(journal/'native-forward.json',plan)
            existing=current(store.connection)
            if existing['state']=='RESTORED':
                with lifecycle_transaction(store,existing) as c:append(c,fact(original,store,'PREPARED'))
            elif existing!=fact(original,store,'PREPARED'):raise StateConflict('Native target has a different transition')
            prior=current(old.connection)
            retired=fact(original,old,'SUPERSEDED')
            if prior!=retired:
                if prior!=original['old_native_authority']:raise StateConflict('Native old authority changed')
                with lifecycle_transaction(old,prior) as c:append(c,retired)
            if previous is None:_write_owned(locator,following)
            else:replace_locator(source,journal,previous,following,original['operation_id'])
            receipt={'decision':'NATIVE_RELOCATED','native_relocation':True,'native_forward_plan':plan,
                'operation_id':original['operation_id'],'epoch':plan['new_epoch'],'host_witness':witness,
                'assurance':original['profile'],'execution_authorized':False,'writes_performed':True,'old_store_retained':True}
            if (journal/'native-cutover.json').exists():
                receipt=json.loads((journal/'native-cutover.json').read_text(encoding='utf-8'))
                if receipt.get('native_forward_plan')!=plan or receipt.get('operation_id')!=original['operation_id']:
                    raise StateConflict('Native persisted cutover receipt differs')
            _write(journal/'native-cutover.json',receipt)
            with lifecycle_transaction(store,current(store.connection)) as c:
                append(c,fact(original,store,'ACTIVE',receipt_sha256=_hash(receipt)))
            require_authority(store)
            return receipt
