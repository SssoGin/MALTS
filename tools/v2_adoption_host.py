"""Windows handoff for MALTS-governed control inputs, not a general OS sandbox.

Existing legacy transaction admission is fenced with the two durable source
seals. Windows handles deny writes/deletes to every reviewed source input and
known activity file and deny ancestor renames during cutover. The SQLite commit
rechecks candidate definitions. Unbound business resources are not adopted or
authorized. No process-list or caller-supplied quiescence claim is accepted.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib,json,os,stat,uuid
from pathlib import Path
from contextlib import contextmanager,ExitStack
from v2_state_store import StateConflict,_json
from v2_evidence import _regular_path
from v2_legacy_reader import inspect_legacy_activity
from v2_adoption import Adoption,SEALS,BINDING,_path,_seal,_write_owned
from v2_runtime_mutex import RuntimeMutex

PROFILE='WINDOWS_GOVERNED_CONTROL_FILES'


class ControlHandoffError(OSError):
    """Value-free controller diagnostic; no local resource identity escapes."""
    def __init__(self,reason_code):
        if reason_code not in {'CONTROL_INPUT_IN_USE_OR_UNREADABLE','ACTIVE_RUNTIME_REQUIRED'}:raise ValueError('Unknown control handoff reason')
        self.reason_code=reason_code
        super().__init__(reason_code)


def adoption_support():
    return {'profile':PROFILE,'available':os.name=='nt','platform':'Windows fixed local volumes',
        'apply_command':'legacy-adoption-apply','preflight_command':'legacy-adoption-preflight',
        'scope':'REVIEWED_CONTROL_INPUTS_AND_LEGACY_TRANSACTION_ADMISSION',
        'external_business_resources_adopted':False,'arbitrary_external_writer_isolation':False,
        'caller_supplied_witness_accepted':False,'execution_authorized':False}


def _local_root(value):
    root=Path(value)
    if not root.is_absolute() or str(root).startswith(('\\\\','//')):raise ValueError('Absolute local root required')
    _regular_path(root)
    root=root.resolve()
    if root.parent==root:raise ValueError('A volume root is not a migration directory')
    if os.name=='nt':
        kernel=C.WinDLL('kernel32',use_last_error=True)
        kernel.GetDriveTypeW.argtypes=[W.LPCWSTR];kernel.GetDriveTypeW.restype=W.UINT
        if kernel.GetDriveTypeW(root.anchor)!=3:raise ValueError('Fixed local volume required')
    return root


def adoption_preflight(*,source_root,capsule_root=None,state_dir=None,resource_roots=()):
    """No mkdir, database creation, source seal or runtime mutation."""
    result={'decision':'ADOPTION_PREFLIGHT','support':adoption_support(),'layout_valid':False,
        'host_handoff_established':False,'preparation_authorized':False,'execution_authorized':False,'writes_performed':False}
    try:
        source=_local_root(source_root)
        capsule=_local_root(capsule_root or source/'.malts/source-capsules/adoption')
        state=_local_root(state_dir or source/'.malts/state')
        if not source.is_dir():raise ValueError('Existing source workspace required')
        from v2_management import validate_layout
        try:layout=validate_layout(source,capsule=capsule,state=state)
        except StateConflict as error:return {**result,'reason':str(error)}
        if capsule.exists() or state.exists():return {**result,'reason':'MIGRATION_TARGET_ALREADY_EXISTS'}
        if layout['layout']=='IN_WORKSPACE':
            from v2_legacy_reader import inspect_workspace
            from v2_management import selection_conflicts
            if selection_conflicts(inspect_workspace(source)):
                return {**result,'reason':'SOURCE_MANAGEMENT_DIRECTORY_CONFLICT'}
        if resource_roots and any(_local_root(r)!=source for r in resource_roots):
            return {**result,'layout_valid':True,'reason':'EXTERNAL_RESOURCE_HANDOFF_NOT_SUPPORTED',
                'next_step':'Adopt the control workspace only; obtain a separately qualified adapter before including external business resources.'}
        if (source/BINDING).exists():
            return {**result,'layout_valid':True,'reason':'SOURCE_ALREADY_BOUND_USE_WORKSPACE_QUERY','next_step':'workspace --workspace <source-root>'}
        if any((source/name).exists() for name in SEALS):
            return {**result,'layout_valid':True,'reason':'SOURCE_TRANSACTION_OR_ADOPTION_RECOVERY_REQUIRED',
                'next_step':'Inspect legacy-activity and the original adoption-status/plan; do not prepare a replacement identity.'}
        return {**result,'layout_valid':True,**layout,'source_root':str(source),'capsule_root':str(capsule),'state_dir':str(state),
            'reason':'CONTROL_HANDOFF_AVAILABLE' if os.name=='nt' else 'CONTROL_HANDOFF_PLATFORM_UNSUPPORTED',
            'preparation_prerequisites':['Explicit authorization for these three exact roots','Reviewed source inventory and semantic dispositions','No unresolved legacy activity','Successful live file-handle acquisition at apply'],
            'source_contents_copied':False,'state_is_long_lived_authority':True}
    except (OSError,ValueError):return {**result,'reason':'MIGRATION_LAYOUT_INVALID_OR_UNREADABLE'}


@contextmanager
def _deny_write_handle(path,*,directory=False):
    """Read sharing only for inputs; directory handles prevent namespace moves."""
    if os.name!='nt':raise OSError('Windows control handoff is unavailable')
    import msvcrt
    path=_local_root(path) if directory else Path(path)
    _regular_path(path)
    kernel=C.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE];kernel.CreateFileW.restype=W.HANDLE
    kernel.CloseHandle.argtypes=[W.HANDLE];kernel.CloseHandle.restype=W.BOOL
    kernel.GetFinalPathNameByHandleW.argtypes=[W.HANDLE,W.LPWSTR,W.DWORD,W.DWORD];kernel.GetFinalPathNameByHandleW.restype=W.DWORD
    # No DELETE sharing. Directory creation is inhibited by legacy admission,
    # not by pretending that a directory handle prevents arbitrary new files.
    handle=kernel.CreateFileW(str(path),0x80000000,3 if directory else 1,None,3,0x02200000 if directory else 0x00200000,None)
    if handle==C.c_void_p(-1).value:raise ControlHandoffError('CONTROL_INPUT_IN_USE_OR_UNREADABLE')
    try:
        buffer=C.create_unicode_buffer(32768)
        length=kernel.GetFinalPathNameByHandleW(handle,buffer,len(buffer),0)
        if not length or length>=len(buffer) or os.path.normcase(buffer.value.removeprefix('\\\\?\\'))!=os.path.normcase(str(path.resolve())):
            raise StateConflict('Opened handoff resource identity differs')
        if directory:yield None
        else:
            descriptor=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY);handle=None
            with os.fdopen(descriptor,'rb') as stream:
                info=os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or getattr(info,'st_file_attributes',0)&0x400:
                    raise StateConflict('Handoff input must be a single-link regular file')
                yield stream
    finally:
        if handle is not None:kernel.CloseHandle(handle)


class WindowsControlHandoff:
    """Built-in controller, with actual admission seals and OS-held input guards."""
    assurance=PROFILE
    preserve_source_seals=True

    def __init__(self,store):self.store=store

    @contextmanager
    def handoff(self,plan):
        Adoption._check_plan(plan)
        source=_local_root(plan['source_root']);target=_local_root(plan['state_dir'])
        if target!=self.store.path.parent.resolve():
            raise StateConflict('Handoff source/store scope differs')
        from v2_management import validate_layout
        inventory=json.loads((target/'legacy-source/manifest.json').read_text(encoding='utf-8'))['inventory']
        validate_layout(source,state=target,inventory=inventory,require_owned=True)
        if os.name!='nt':raise OSError('Windows control handoff is unavailable')
        with ExitStack() as guards:
            for root in sorted((source,target),key=lambda p:os.path.normcase(str(p))):guards.enter_context(RuntimeMutex(root))
            # These are exclusive creates, not declarations of writer state.
            # A preexisting foreign transaction lock blocks. Owned partial seals
            # remain bound to the original plan for crash-safe continuation.
            for relative in SEALS:_write_owned(_path(source,relative),_seal(plan))
            service=Adoption(self.store);service._check_source(plan)
            capsule=json.loads((target/'legacy-source/manifest.json').read_text(encoding='utf-8'))
            selected={'runtime/workspace_control.json',*(r['path'] for r in capsule['inventory']['records']),*SEALS}
            activity=inspect_legacy_activity(source)
            selected.update(r['path'] for r in activity['files'] if r['sha256'] is not None)
            directories={source}
            for relative in selected:
                path=_path(source,relative)
                directories.update(p for p in path.parents if p==source or p.is_relative_to(source))
            for path in sorted(directories,key=lambda p:len(p.parts)):guards.enter_context(_deny_write_handle(path,directory=True))
            frozen=[]
            for relative in sorted(selected):
                stream=guards.enter_context(_deny_write_handle(_path(source,relative)))
                digest=hashlib.sha256()
                for chunk in iter(lambda:stream.read(65536),b''):digest.update(chunk)
                frozen.append({'path':relative,'sha256':digest.hexdigest()})
            service._check_source(plan);service._check_review(plan)
            evidence={'format':'malts.v2.control-handoff-evidence','profile':PROFILE,'adoption_id':plan['adoption_id'],
                'plan_sha256':plan['plan_sha256'],'process_id':os.getpid(),'inputs':frozen,
                'directory_handles':len(directories),'legacy_admission_seals':list(SEALS),
                'external_business_resources_adopted':False,'arbitrary_external_writer_isolation':False,
                'candidate_definition_recheck':'SQLITE_CUTOVER_TRANSACTION','execution_authorized':False}
            directory=target/'adoption-host-evidence';_regular_path(directory);directory.mkdir(exist_ok=True)
            path=directory/(plan['adoption_id']+'.'+uuid.uuid4().hex+'.json')
            data=_json(evidence).encode('utf-8');_write_owned(path,data)
            yield {'host_id':'malts-windows-control-handoff','evidence_ref':str(path)+':sha256:'+hashlib.sha256(data).hexdigest(),
                'coverage':'ALL_BOUND_WRITERS_AND_RESOURCES','state':'ISOLATED'}


def apply_control_adoption(*,plan,tool_root,expected_plan_sha256,apply=False):
    """CLI controller: verified installed identity, exact plan and dry-run default."""
    from malts_lifecycle import resolve_discovery
    from v2_state_store import StateStore
    from contextlib import closing
    Adoption._check_plan(plan)
    if plan['plan_sha256']!=expected_plan_sha256:raise StateConflict('Approved adoption plan hash differs')
    discovery=resolve_discovery(tool_root)
    if Path(discovery['malts_root']).resolve()!=Path(__file__).resolve().parent.parent:
        raise ControlHandoffError('ACTIVE_RUNTIME_REQUIRED')
    parameters={'decision':'ADOPTION_NOT_APPLIED','profile':PROFILE,'adoption_id':plan['adoption_id'],
        'plan_sha256':plan['plan_sha256'],'source_root':plan['source_root'],'state_dir':plan['state_dir'],
        'execution_authorized':False,'writes_performed':False}
    from v2_runtime_admission import runtime_admission
    with runtime_admission(tool_root),closing(StateStore(Path(plan['state_dir'])/'state.db',readonly=not apply)) as store:
        service=Adoption(store)
        if not apply:
            service._check_review(plan)
            return parameters
        return service.apply(plan,host=WindowsControlHandoff(store))
