"""Healthy adopted-store relocation using backup, reconciliation and forward recovery.

SQLite exclusive locks fence database clients. Runtime mutexes and namespace
handles protect the governed cutover. External business writers require the
existing explicit recovery review; this is not an arbitrary-process sandbox.
"""
import hashlib,json,os,re,shutil,uuid
from pathlib import Path
from contextlib import contextmanager,ExitStack,closing
from v2_state_store import StateStore,StateConflict,_json
from v2_evidence import BlobStore,_regular_path
from v2_adoption import require_active_binding,Adoption,BINDING,SEALS
from v2_forward_recovery import ForwardRecovery,state_hash
from v2_backup import backup,verify_backup,restore_backup,_managed_paths,_referenced_blobs
from v2_recovery import Recovery
from v2_management import ManagementConflict,root_path,management_root,initialize_management,validate_layout
from v2_runtime_mutex import RuntimeMutex
from v2_path_io import io_path

PROFILE='WINDOWS_SQLITE_EXCLUSIVE_FORWARD_HANDOFF'


def _principal():
    if os.name!='nt':raise OSError('Relocation requires Windows on the same user and machine')
    import ctypes as C
    import winreg
    size=C.c_ulong(32768);name=C.create_unicode_buffer(size.value)
    function=C.WinDLL('secur32',use_last_error=True).GetUserNameExW
    function.argtypes=[C.c_int,C.c_wchar_p,C.POINTER(C.c_ulong)];function.restype=C.c_bool
    if not function(2,name,C.byref(size)):raise OSError('Windows principal identity unavailable')
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Cryptography',0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
        machine=winreg.QueryValueEx(key,'MachineGuid')[0]
    return _hash([machine,name.value.casefold()])


def _hash(value):return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def _write(path,value):
    _regular_path(path)
    data=_json(value).encode('utf-8')
    if path.exists():
        if path.read_bytes()!=data:raise StateConflict('Relocation journal identity conflicts')
        return
    with path.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())


def _file_hash(path):
    digest=hashlib.sha256()
    with io_path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1048576),b''):digest.update(chunk)
    return digest.hexdigest()


def _closure(store):
    copied=set(_managed_paths(store.connection))
    copied.update('blobs/'+h[:2]+'/'+h for h in _referenced_blobs(store))
    rows=[]
    for count,p in enumerate(io_path(store.path.parent).rglob('*'),1):
        if count>50000:raise ManagementConflict('STATE_CLOSURE_ENTRY_BUDGET_EXCEEDED')
        _regular_path(p)
        if not p.is_file():continue
        if p.stat().st_nlink!=1:raise ManagementConflict('STATE_CLOSURE_HARDLINK_NOT_SUPPORTED')
        relative=p.relative_to(io_path(store.path.parent)).as_posix()
        if relative in {'state.db-journal','state.db-wal','state.db-shm'}:
            raise ManagementConflict('STATE_TRANSACTION_OR_RECOVERY_REQUIRED')
        rows.append({'path':relative,'sha256':_file_hash(p),'bytes':p.stat().st_size,
                     'disposition':'DATABASE_BACKUP' if relative=='state.db' else 'COPY_MANAGED' if relative in copied else 'RETAIN_EXTERNAL_HISTORY'})
        if len(rows)>50000:raise ManagementConflict('STATE_CLOSURE_ENTRY_BUDGET_EXCEEDED')
    rows.sort(key=lambda r:r['path'])
    if not copied.issubset({r['path'] for r in rows}):raise ManagementConflict('STATE_CLOSURE_REFERENCE_MISSING')
    return rows


def _healthy(store, *, native=False):
    store.require_execution_ready()
    if not native:require_active_binding(store)
    c=store.connection
    if c.execute("SELECT 1 FROM execution_run WHERE state<>'CLOSED' LIMIT 1").fetchone():
        raise ManagementConflict('LIVE_OR_UNRESOLVED_RUN_REQUIRES_HANDOFF')
    if c.execute("SELECT 1 FROM operation WHERE state IN ('INTENT_RECORDED','UNKNOWN') LIMIT 1").fetchone():
        raise ManagementConflict('UNRESOLVED_OPERATION_REQUIRES_RECONCILIATION')
    if c.execute('SELECT 1 FROM host_dispatch WHERE launch_committed=1 AND coalesce(quiesced,0)=0 LIMIT 1').fetchone():
        raise ManagementConflict('HOST_DISPATCH_NOT_QUIESCED')
    if c.execute('SELECT 1 FROM task_effect_recovery LIMIT 1').fetchone():
        raise ManagementConflict('EFFECT_RECOVERY_REQUIRED')


def preflight(*,workspace,target_state_dir=None,operation_id,authority_ref,journal_root=None,old_state_dir=None):
    """Read-only exact plan; no backup, target directory or management claim."""
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',operation_id):raise ValueError('Invalid relocation identity')
    if not isinstance(authority_ref,str) or not authority_ref.strip():raise ValueError('Authority reference required')
    source=root_path(workspace); managed=management_root(source)
    from v2_native_relocation import classify_source
    identity=classify_source(source,old_state_dir)
    old=root_path(identity['state_dir']);target=root_path(target_state_dir or managed/'state')
    journal=root_path(journal_root or managed/'recovery'/operation_id)
    validate_layout(source,state=target)
    roots=(old,target,journal)
    if any(a.is_relative_to(b) or b.is_relative_to(a) for i,a in enumerate(roots) for b in roots[i+1:]):
        raise ManagementConflict('RELOCATION_STATE_AND_JOURNAL_ROOTS_MUST_BE_SEPARATE')
    if target.exists() or journal.exists():raise ManagementConflict('RELOCATION_TARGET_OR_JOURNAL_EXISTS_USE_ORIGINAL_STATUS')
    if target.anchor.casefold()!=journal.anchor.casefold():raise ManagementConflict('TARGET_AND_JOURNAL_REQUIRE_SAME_VOLUME')
    if journal.is_relative_to(source) and not journal.is_relative_to(managed/'recovery'):
        raise ManagementConflict('INTERNAL_JOURNAL_REQUIRES_MANAGEMENT_RECOVERY_DIRECTORY')
    # Database/control roots still use SQLite and ordinary protocol APIs. Long
    # managed relative files use extended I/O, without a system registry change.
    if os.name=='nt' and max(len(str(journal/'restore-'/('x'*32)/'.restoring.db')),len(str(target/'relocation-host-evidence'/(operation_id+'.'+('x'*32)+'.json'))),len(str(old/'state.db')))>240:
        raise ManagementConflict('RELOCATION_CONTROL_PATH_TOO_LONG')
    with closing(StateStore(old/'state.db',readonly=True)) as store:
        _healthy(store,native=identity['source_kind']!='ADOPTED'); rows=_closure(store)
        epoch=store.connection.execute('SELECT epoch FROM recovery_state').fetchone()[0]
        source_hash=state_hash(store.connection)
    nearest=target.parent
    while not nearest.exists():nearest=nearest.parent
    required=3*sum(r['bytes'] for r in rows)+16*1024*1024
    if not os.access(nearest,os.W_OK) or shutil.disk_usage(nearest).free<required:
        raise ManagementConflict('RELOCATION_TARGET_PERMISSION_OR_CAPACITY_INSUFFICIENT')
    result={'format':'malts.v2.relocation-plan','version':1,'operation_id':operation_id,
        'workspace_root':str(source),'old_state_dir':str(old),'state_dir':str(target),'journal_root':str(journal),
        'old_epoch':epoch,'old_adoption_id':identity.get('adoption_id'),'old_state_sha256':source_hash,
        'source_protocol':[{'path':p,'sha256':_file_hash(source/p)} for p in identity['protocol_paths']],
        'closure':rows,'authority_ref':authority_ref,'profile':PROFILE,'external_effect_review_required':True,
        'same_user_same_machine_required':True,'principal_sha256':_principal(),'execution_authorized':False,'writes_performed':False}
    if identity['source_kind']!='ADOPTED':
        result.update(version=2,source_kind=identity['source_kind'],project_id=identity['project_id'],old_native_authority=identity['native_authority'])
    result['plan_sha256']=_hash(result)
    return result


def _validate(plan):
    fields={'format','version','operation_id','workspace_root','old_state_dir','state_dir','journal_root','old_epoch',
        'old_adoption_id','old_state_sha256','source_protocol','closure','authority_ref','profile',
        'external_effect_review_required','same_user_same_machine_required','principal_sha256','execution_authorized','writes_performed','plan_sha256'}
    if isinstance(plan,dict) and plan.get('version')==2:fields|={'source_kind','project_id','old_native_authority'}
    if (not isinstance(plan,dict) or set(plan)!=fields or plan['format']!='malts.v2.relocation-plan' or
            type(plan['version']) is not int or plan['version'] not in (1,2) or plan['profile']!=PROFILE or plan['execution_authorized'] is not False or
            plan['writes_performed'] is not False or plan['external_effect_review_required'] is not True or
            plan['same_user_same_machine_required'] is not True):raise ValueError('Invalid relocation plan')
    if _hash({k:v for k,v in plan.items() if k!='plan_sha256'})!=plan['plan_sha256']:
        raise StateConflict('Relocation plan hash changed')
    if plan['principal_sha256']!=_principal():raise ManagementConflict('RELOCATION_REQUIRES_ORIGINAL_USER_AND_MACHINE')
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',plan['operation_id']):raise ValueError('Invalid relocation identity')
    roots=[root_path(plan[k]) for k in ('old_state_dir','state_dir','journal_root')]
    if any(a.is_relative_to(b) or b.is_relative_to(a) for i,a in enumerate(roots) for b in roots[i+1:]):
        raise ManagementConflict('RELOCATION_ROOT_OVERLAP')
    validate_layout(plan['workspace_root'],state=roots[1])
    if plan['version']==2 and (plan['source_kind'] not in {'NATIVE_EXPLICIT','NATIVE_LOCATOR'} or plan['old_adoption_id'] is not None):
        raise ValueError('Invalid native source classification')


@contextmanager
def exclusive(store):
    """Retain SQLite's exclusive lock across this connection's commits."""
    c=store.connection
    if c.in_transaction:raise StateConflict('Relocation requires an idle controller connection')
    c.execute('PRAGMA locking_mode=EXCLUSIVE')
    try:
        c.execute('BEGIN EXCLUSIVE');c.execute('COMMIT')
        yield
    finally:
        if c.in_transaction:c.execute('ROLLBACK')
        c.execute('PRAGMA locking_mode=NORMAL')
        c.execute('SELECT count(*) FROM recovery_state').fetchone()


def _active_runtime(tool_root):
    from malts_lifecycle import resolve_discovery
    if Path(resolve_discovery(tool_root)['malts_root']).resolve()!=Path(__file__).resolve().parent.parent:
        raise ManagementConflict('ACTIVE_RUNTIME_REQUIRED')


def prepare(plan, *, expected_plan_sha256, tool_root=None, apply=False):
    _validate(plan)
    if plan['plan_sha256']!=expected_plan_sha256:raise StateConflict('Reviewed relocation plan differs')
    if tool_root is not None:_active_runtime(tool_root)
    if not apply:return {'decision':'RELOCATION_NOT_APPLIED','plan':plan,'writes_performed':False,'execution_authorized':False}
    if os.name!='nt':raise OSError('Relocation controller requires Windows')
    source=root_path(plan['workspace_root']);old=root_path(plan['old_state_dir']);target=root_path(plan['state_dir']);journal=root_path(plan['journal_root'])
    with ExitStack() as guards:
        for root in sorted({source,old},key=lambda p:os.path.normcase(str(p))):guards.enter_context(RuntimeMutex(root))
        store=guards.enter_context(closing(StateStore(old/'state.db')));guards.enter_context(exclusive(store))
        # A journal owns only this operation's attempts. Incomplete attempts are
        # retained; a retry never deletes, reuses or overwrites their contents.
        if journal.exists():
            if json.loads((journal/'plan.json').read_text(encoding='utf-8'))!=plan:raise StateConflict('Relocation journal conflicts')
            if (journal/'target.json').exists():return status(journal)
        native=plan.get('source_kind','ADOPTED')!='ADOPTED'
        _healthy(store,native=native)
        if native:
            from v2_native_relocation import check_source
            check_source(plan,store)
        if state_hash(store.connection)!=plan['old_state_sha256'] or _closure(store)!=plan['closure']:
            raise ManagementConflict('OLD_STATE_CHANGED_AFTER_RELOCATION_PLAN')
        if any(_file_hash(source/r['path'])!=r['sha256'] for r in plan['source_protocol']):
            raise ManagementConflict('SOURCE_PROTOCOL_CHANGED_AFTER_RELOCATION_PLAN')
        if target.exists():
            # Crash after atomic rename, before publishing target.json.
            pending=json.loads((journal/'pending-target.json').read_text(encoding='utf-8')) if journal.exists() and (journal/'pending-target.json').exists() else None
            if pending and _file_hash(target/'state.db')==pending['database_sha256']:
                _write(journal/'target.json',pending);return status(journal)
            raise ManagementConflict('RELOCATION_TARGET_EXISTS')
        if not journal.exists():
            if native or journal.is_relative_to(source/'.malts') or target.is_relative_to(source/'.malts'):
                initialize_management(source,apply=True)
            journal.parent.mkdir(parents=True,exist_ok=True);journal.mkdir();_write(journal/'plan.json',plan)
        saved_record=journal/'backup.json'
        if saved_record.exists():
            record=json.loads(saved_record.read_text(encoding='utf-8'));saved=root_path(record['backup_root'])
            manifest=verify_backup(saved)
            if _hash(manifest)!=record['manifest_sha256']:raise StateConflict('Relocation backup journal changed')
        else:
            saved=journal/('backup-'+uuid.uuid4().hex)
            manifest=backup(store,BlobStore(old/'blobs',readonly=True),saved)
            _write(saved_record,{'backup_root':str(saved),'manifest_sha256':_hash(manifest)})
        # Pending completed restore can resume without creating another epoch.
        pending_path=journal/'pending-target.json'
        if pending_path.exists():
            pending=json.loads(pending_path.read_text(encoding='utf-8'));staged=root_path(pending['staged_root'])
            if _file_hash(staged/'state.db')!=pending['database_sha256']:raise StateConflict('Relocation staging changed')
        else:
            staged=journal/('restore-'+uuid.uuid4().hex)
            restore_backup(saved,staged,expected_manifest_sha256=_hash(manifest))
            if native:
                from v2_native_relocation import quarantine_target
                quarantine_target(plan,staged)
            with closing(StateStore(staged/'state.db',readonly=True)) as restored:
                epoch=restored.connection.execute('SELECT epoch FROM recovery_state').fetchone()[0]
            pending={'state_dir':str(target),'staged_root':str(staged),'backup_root':str(saved),
                     'database_sha256':_file_hash(staged/'state.db'),'epoch':epoch,'plan_sha256':plan['plan_sha256']}
            _write(pending_path,pending)
        target.parent.mkdir(parents=True,exist_ok=True)
        staged.rename(target)  # same-volume, absent target; no old-store removal
        _write(journal/'target.json',pending)
    return status(journal)


def status(journal_root):
    journal=root_path(journal_root);_regular_path(journal/'plan.json')
    plan=json.loads((journal/'plan.json').read_text(encoding='utf-8'));_validate(plan)
    if root_path(plan['journal_root'])!=journal:raise StateConflict('Relocation status journal differs')
    result={'decision':'RELOCATION_STATUS','plan':plan,'writes_performed':False,'execution_authorized':False,
            'old_store_retained':True,'state':'PREPARING','retained_historical_paths':
            [str(Path(plan['old_state_dir'])/r['path']) for r in plan['closure'] if r['disposition']=='RETAIN_EXTERNAL_HISTORY']}
    if not (journal/'target.json').exists():return result
    target=json.loads((journal/'target.json').read_text(encoding='utf-8'))
    if target['plan_sha256']!=plan['plan_sha256'] or target['state_dir']!=plan['state_dir']:
        raise StateConflict('Relocation target journal differs')
    with closing(StateStore(Path(plan['state_dir'])/'state.db',readonly=True)) as store:
        recovery=store.connection.execute('SELECT epoch,reconciliation_required FROM recovery_state').fetchone()
        if recovery[0]!=target['epoch']:raise StateConflict('Relocation target epoch changed')
        row=store.connection.execute('SELECT state FROM migration_adoption WHERE adoption_id=?',(plan['operation_id'],)).fetchone()
        result.update(state=row[0] if row else 'RESTORED_QUARANTINED' if recovery[1] else 'RECONCILED',target=target)
        if recovery[1]:
            inventory=Recovery(store).inspect();result['recovery_inventory']=inventory
            result['recovery_review_template']={'review_id':plan['operation_id']+'-review',
                'authority_ref':'TODO: reviewed authorization reference','basis':inventory['binding'],
                'resource_reviews':[{'resource_id':r['resource_id'],'coverage':'UNKNOWN','evidence_ref':'TODO: actual resource and external-writer review'} for r in inventory['resources']],
                'writer_reviews':[{'run_id':r['run_id'],'state':'UNKNOWN','evidence_ref':'TODO: actual writer handoff'} for r in inventory['writers']],
                'task_actions':[{'task_id':r['task_id'],'revision':r['revision'],
                    'action':'KEEP_HISTORY' if r['status'] in {'COMPLETED','CANCELLED','FAILED'} else 'KEEP_PAUSED',
                    'reason':'Preserve state pending operator review','next_action':None} for r in inventory['tasks']],
                'unresolved_external_effects':['TODO: review effects and writers outside the database']}
        if plan.get('source_kind','ADOPTED')!='ADOPTED':
            from v2_native_relocation import native_status
            native_status(result,store,journal)
        elif row:result['forward']=ForwardRecovery(store).inspect(adoption_id=plan['operation_id'])
    return result


class WindowsForwardHandoff:
    assurance=PROFILE
    def __init__(self,store,old_store):self.store=store;self.old_store=old_store

    @contextmanager
    def handoff(self,plan):
        from v2_adoption_host import _deny_write_handle
        if plan.get('format')=='malts.v2.native-forward-plan':
            from v2_native_relocation import validate_forward
            validate_forward(plan)
        else:ForwardRecovery._validate(plan)
        roots={root_path(plan[k]) for k in ('source_root','state_dir','old_state_dir')}
        validate_layout(plan['source_root'],state=plan['state_dir'])
        with ExitStack() as guards:
            for root in sorted(roots,key=lambda p:os.path.normcase(str(p))):guards.enter_context(RuntimeMutex(root))
            for root in sorted(roots,key=lambda p:len(p.parts)):guards.enter_context(_deny_write_handle(root,directory=True))
            for store in (self.old_store,self.store):guards.enter_context(exclusive(store))
            # Check canonical closure through database references. Historical
            # absolute evidence remains at its declared old path, not rewritten.
            for store in (self.old_store,self.store):
                for relative in _managed_paths(store.connection):guards.enter_context(_deny_write_handle(store.path.parent/relative))
                for digest in _referenced_blobs(store):guards.enter_context(_deny_write_handle(store.path.parent/'blobs'/digest[:2]/digest))
            directory=self.store.path.parent/'relocation-host-evidence';_regular_path(directory);directory.mkdir(exist_ok=True)
            path=directory/(plan['adoption_id']+'.'+uuid.uuid4().hex+'.json')
            evidence={'format':'malts.v2.forward-handoff-evidence','profile':PROFILE,'plan_sha256':plan['plan_sha256'],
                'process_id':os.getpid(),'sqlite_exclusive_locks':2,'resource_review':'CURRENT_EPOCH_OPERATOR_ATTESTED',
                'arbitrary_external_writer_isolation':False,'execution_authorized':False}
            _write(path,evidence)
            yield {'host_id':'malts-windows-forward-handoff','evidence_ref':str(path)+':sha256:'+_hash(evidence),
                   'coverage':'ALL_BOUND_WRITERS_AND_RESOURCES','state':'ISOLATED'}


def apply_forward(plan, *, expected_plan_sha256, tool_root=None, journal_root=None, apply=False):
    ForwardRecovery._validate(plan)
    if expected_plan_sha256!=plan['plan_sha256']:raise StateConflict('Reviewed forward plan differs')
    if tool_root is not None:_active_runtime(tool_root)
    if journal_root is not None:
        current=status(journal_root);original=current['plan'];target=current.get('target',{})
        if (plan['adoption_id']!=original['operation_id'] or plan['source_root']!=original['workspace_root'] or
                plan['old_state_dir']!=original['old_state_dir'] or plan['state_dir']!=original['state_dir'] or
                plan['backup_root']!=target.get('backup_root')):raise StateConflict('Forward plan differs from relocation journal')
    elif tool_root is not None:raise StateConflict('Formal relocation apply requires its original journal')
    if not apply:return {'decision':'FORWARD_NOT_APPLIED','profile':PROFILE,'plan_sha256':plan['plan_sha256'],
                         'writes_performed':False,'execution_authorized':False}
    with closing(StateStore(Path(plan['state_dir'])/'state.db')) as store,closing(StateStore(Path(plan['old_state_dir'])/'state.db')) as old:
        return ForwardRecovery(store,old).apply(plan,host=WindowsForwardHandoff(store,old))
