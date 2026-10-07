"""Owned Windows Job process boundary for trusted controllers, not an OS sandbox.

Windows 10+ x64; Job association is supplied to CreateProcess, never a later
best-effort assignment. No breakaway flags or inherited Job handles are enabled.
Only processes associated with this Job are covered (not remote/WMI launches).
wait() enforces a wall deadline while its controller is scheduled; no claim of
a persistent watchdog or hard real-time enforcement after controller suspension.
"""
import ctypes as C
from ctypes import wintypes as W
import math,os,subprocess,time,uuid
from pathlib import Path


class JobError(OSError):pass


class _Security(C.Structure):
    _fields_=[('length',W.DWORD),('descriptor',C.c_void_p),('inherit',W.BOOL)]
class _Startup(C.Structure):
    _fields_=[('cb',W.DWORD),('reserved',W.LPWSTR),('desktop',W.LPWSTR),('title',W.LPWSTR),
        ('x',W.DWORD),('y',W.DWORD),('cx',W.DWORD),('cy',W.DWORD),('xchars',W.DWORD),('ychars',W.DWORD),
        ('fill',W.DWORD),('flags',W.DWORD),('show',W.WORD),('reserved2len',W.WORD),('reserved2',C.c_void_p),
        ('stdin',W.HANDLE),('stdout',W.HANDLE),('stderr',W.HANDLE)]
class _StartupEx(C.Structure):_fields_=[('base',_Startup),('attributes',C.c_void_p)]
class _Process(C.Structure):_fields_=[('process',W.HANDLE),('thread',W.HANDLE),('pid',W.DWORD),('tid',W.DWORD)]
class _BasicLimit(C.Structure):
    _fields_=[('process_time',C.c_longlong),('job_time',C.c_longlong),('flags',W.DWORD),
        ('min_working',C.c_size_t),('max_working',C.c_size_t),('active_limit',W.DWORD),
        ('affinity',C.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]
class _Io(C.Structure):_fields_=[(name,C.c_ulonglong) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
class _ExtendedLimit(C.Structure):
    _fields_=[('basic',_BasicLimit),('io',_Io),('process_memory',C.c_size_t),('job_memory',C.c_size_t),
        ('peak_process_memory',C.c_size_t),('peak_job_memory',C.c_size_t)]
class _Accounting(C.Structure):
    _fields_=[('user_time',C.c_longlong),('kernel_time',C.c_longlong),('period_user',C.c_longlong),('period_kernel',C.c_longlong),
        ('page_faults',W.DWORD),('total_processes',W.DWORD),('active_processes',W.DWORD),('terminated_processes',W.DWORD)]


def _api():
    if os.name!='nt' or C.sizeof(C.c_void_p)!=8:raise JobError('No qualified Windows Job profile on this platform')
    k=C.WinDLL('kernel32',use_last_error=True)
    declarations={
        'CreateJobObjectW':([C.c_void_p,W.LPCWSTR],W.HANDLE),
        'SetInformationJobObject':([W.HANDLE,C.c_int,C.c_void_p,W.DWORD],W.BOOL),
        'QueryInformationJobObject':([W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.c_void_p],W.BOOL),
        'TerminateJobObject':([W.HANDLE,W.UINT],W.BOOL),
        'CloseHandle':([W.HANDLE],W.BOOL),
        'CreateFileW':([W.LPCWSTR,W.DWORD,W.DWORD,C.POINTER(_Security),W.DWORD,W.DWORD,W.HANDLE],W.HANDLE),
        'InitializeProcThreadAttributeList':([C.c_void_p,W.DWORD,W.DWORD,C.POINTER(C.c_size_t)],W.BOOL),
        'UpdateProcThreadAttribute':([C.c_void_p,W.DWORD,C.c_size_t,C.c_void_p,C.c_size_t,C.c_void_p,C.c_void_p],W.BOOL),
        'DeleteProcThreadAttributeList':([C.c_void_p],None),
        'CreateProcessW':([W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,C.c_void_p,W.LPCWSTR,C.POINTER(_StartupEx),C.POINTER(_Process)],W.BOOL),
        'GetProcessTimes':([W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)],W.BOOL),
        'WaitForSingleObject':([W.HANDLE,W.DWORD],W.DWORD),
        'GetExitCodeProcess':([W.HANDLE,C.POINTER(W.DWORD)],W.BOOL),
        'OpenProcess':([W.DWORD,W.BOOL,W.DWORD],W.HANDLE),
        'CreatePipe':([C.POINTER(W.HANDLE),C.POINTER(W.HANDLE),C.POINTER(_Security),W.DWORD],W.BOOL),
        'SetHandleInformation':([W.HANDLE,W.DWORD,W.DWORD],W.BOOL),
    }
    for name,(args,result) in declarations.items():
        fn=getattr(k,name);fn.argtypes=args;fn.restype=result
    return k


def _check(ok,operation):
    if not ok:raise JobError(C.get_last_error(),operation+' failed')


def current_process_identity():
    k=_api();created,exited,kernel,user=(W.FILETIME() for _ in range(4))
    _check(k.GetProcessTimes(W.HANDLE(-1),C.byref(created),C.byref(exited),C.byref(kernel),C.byref(user)),'GetProcessTimes')
    return {'pid':os.getpid(),'creation_filetime':(created.dwHighDateTime<<32)|created.dwLowDateTime}


def process_identity_state(identity):
    """Read-only PID + creation-time check; never terminates a PID lookup."""
    if (not isinstance(identity,dict) or set(identity)!={'pid','creation_filetime'} or
            type(identity['pid']) is not int or identity['pid']<=0 or
            type(identity['creation_filetime']) is not int or identity['creation_filetime']<=0):raise ValueError('Invalid process identity')
    k=_api();handle=k.OpenProcess(0x101000,False,identity['pid'])
    if not handle:return 'ABSENT' if C.get_last_error()==87 else 'UNAVAILABLE'
    try:
        created,exited,kernel,user=(W.FILETIME() for _ in range(4))
        _check(k.GetProcessTimes(handle,C.byref(created),C.byref(exited),C.byref(kernel),C.byref(user)),'GetProcessTimes')
        if ((created.dwHighDateTime<<32)|created.dwLowDateTime)!=identity['creation_filetime']:return 'DIFFERENT_INSTANCE'
        result=k.WaitForSingleObject(handle,0)
        return 'EXITED' if result==0 else 'LIVE' if result==258 else 'UNAVAILABLE'
    finally:k.CloseHandle(handle)


class WindowsJob:
    def __init__(self):
        self.k=_api();self.job=None;self.process=None;self.pid=None;self.creation_time=None
        self.stdin=self.stdout=self.stderr=None
        self.name='Local\\malts-v2-'+uuid.uuid4().hex;self.stop_reason=None

    @classmethod
    def launch(cls,argv,*,cwd,capture_stdio=False):
        """Explicit trusted command only. Optional private pipes; no Agent routing."""
        if type(capture_stdio) is not bool:raise ValueError('Explicit stdio mode required')
        if not isinstance(argv,(list,tuple)) or not argv or any(not isinstance(v,str) or '\0' in v for v in argv):
            raise ValueError('Explicit argument vector required')
        executable=Path(argv[0])
        directory=Path(cwd)
        if not executable.is_absolute() or not executable.is_file() or not directory.is_absolute() or not directory.is_dir():
            raise ValueError('Existing absolute executable and working directory required')
        result=cls();k=result.k;null=None;attributes=None;initialized=False;process=_Process();pipe_handles=[];child_handles=[]
        try:
            C.set_last_error(0)
            result.job=k.CreateJobObjectW(None,result.name)
            _check(result.job,'CreateJobObject')
            if C.get_last_error()==183:
                k.CloseHandle(result.job);result.job=None
                raise JobError('Refusing an existing named Job')
            limits=_ExtendedLimit();limits.basic.flags=0x2000 # KILL_ON_JOB_CLOSE only; never allow breakaway
            _check(k.SetInformationJobObject(result.job,9,C.byref(limits),C.sizeof(limits)),'SetInformationJobObject')
            security=_Security(C.sizeof(_Security),None,True)
            null=k.CreateFileW('NUL',0xC0000000,3,C.byref(security),3,0x80,None)
            if null in (None,C.c_void_p(-1).value):raise JobError(C.get_last_error(),'Opening null stdio failed')
            std_handles=[null,null,null]
            parents=[]
            if capture_stdio:
                for index in range(3):
                    read,write=W.HANDLE(),W.HANDLE()
                    _check(k.CreatePipe(C.byref(read),C.byref(write),C.byref(security),0),'CreatePipe')
                    pipe_handles.extend((read.value,write.value))
                    child,parent=(read.value,write.value) if index==0 else (write.value,read.value)
                    _check(k.SetHandleInformation(parent,1,0),'SetHandleInformation')
                    child_handles.append(child);parents.append(parent)
                std_handles=child_handles
            size=C.c_size_t()
            k.InitializeProcThreadAttributeList(None,2,0,C.byref(size))
            if not size.value:raise JobError('Process attribute allocation size is unavailable')
            attributes=C.create_string_buffer(size.value)
            _check(k.InitializeProcThreadAttributeList(attributes,2,0,C.byref(size)),'InitializeProcThreadAttributeList');initialized=True
            jobs=(W.HANDLE*1)(result.job);handles=(W.HANDLE*len(std_handles))(*std_handles) if capture_stdio else (W.HANDLE*1)(null)
            # Verified against Windows SDK 10.0.22621.0 WinBase.h: input attribute 13 and 2.
            _check(k.UpdateProcThreadAttribute(attributes,0,0x2000D,C.cast(jobs,C.c_void_p),C.sizeof(jobs),None,None),'Job-list attribute')
            _check(k.UpdateProcThreadAttribute(attributes,0,0x20002,C.cast(handles,C.c_void_p),C.sizeof(handles),None,None),'Handle-list attribute')
            startup=_StartupEx();startup.base.cb=C.sizeof(startup);startup.base.flags=0x101 # stdio + show-window
            startup.base.show=0;startup.base.stdin,startup.base.stdout,startup.base.stderr=std_handles
            startup.attributes=C.cast(attributes,C.c_void_p)
            command=C.create_unicode_buffer(subprocess.list2cmdline(list(argv)))
            _check(k.CreateProcessW(str(executable),command,None,None,True,0x00080000|0x08000000,None,str(directory),C.byref(startup),C.byref(process)),'CreateProcess')
            result.process=process.process;result.pid=process.pid
            created,exited,kernel,user=(W.FILETIME() for _ in range(4))
            _check(k.GetProcessTimes(result.process,C.byref(created),C.byref(exited),C.byref(kernel),C.byref(user)),'GetProcessTimes')
            result.creation_time=(created.dwHighDateTime<<32)|created.dwLowDateTime
            if capture_stdio:
                import msvcrt
                for name,parent,mode in zip(('stdin','stdout','stderr'),parents,('wb','rb','rb')):
                    fd=msvcrt.open_osfhandle(parent,os.O_BINARY|(os.O_WRONLY if mode=='wb' else os.O_RDONLY))
                    pipe_handles.remove(parent)  # ownership transferred to the CRT descriptor
                    try:stream=os.fdopen(fd,mode,buffering=0)
                    except BaseException:os.close(fd);raise
                    setattr(result,name,stream)
            return result
        except BaseException:
            # Closing our new Job kills its associated children even on partial startup failure.
            if result.job:k.CloseHandle(result.job);result.job=None
            if result.process:k.CloseHandle(result.process);result.process=None
            for stream in (result.stdin,result.stdout,result.stderr):
                if stream:stream.close()
            raise
        finally:
            if process.thread:k.CloseHandle(process.thread)
            if initialized:k.DeleteProcThreadAttributeList(attributes)
            if null not in (None,C.c_void_p(-1).value):k.CloseHandle(null)
            for handle in pipe_handles:k.CloseHandle(handle)

    def members(self):
        """IDs observed in this owned Job; not a PID-based kill interface."""
        if not self.job:raise JobError('Owned Job handle is closed')
        capacity=64
        while capacity<=4096:
            class Pids(C.Structure):
                _fields_=[('assigned',W.DWORD),('count',W.DWORD),('ids',C.c_size_t*capacity)]
            value=Pids()
            if self.k.QueryInformationJobObject(self.job,3,C.byref(value),C.sizeof(value),None):
                return tuple(value.ids[:value.count])
            if C.get_last_error()!=234:raise JobError(C.get_last_error(),'Job member query failed')
            capacity*=2
        raise JobError('Job member inventory exceeds bounded query size')

    def status(self):
        if not self.job:raise JobError('Owned Job handle is closed')
        accounting=_Accounting()
        _check(self.k.QueryInformationJobObject(self.job,1,C.byref(accounting),C.sizeof(accounting),None),'QueryInformationJobObject')
        wait=self.k.WaitForSingleObject(self.process,0)
        if wait not in (0,258):raise JobError(C.get_last_error(),'Process wait status unavailable')
        code=None
        if wait==0:
            value=W.DWORD();_check(self.k.GetExitCodeProcess(self.process,C.byref(value)),'GetExitCodeProcess');code=value.value
        return {'job_name':self.name,'root_pid':self.pid,'root_creation_filetime':self.creation_time,
                'root_exited':wait==0,'root_exit_code':code,'active_processes':accounting.active_processes,
                'total_processes':accounting.total_processes,'quiesced':accounting.active_processes==0,
                'quiescence_scope':'ASSOCIATED_WINDOWS_JOB_PROCESSES','stop_reason':self.stop_reason}

    def cancel(self,*,reason='CONTROLLER_CANCEL'):
        if reason not in {'CONTROLLER_CANCEL','DEADLINE','CLOSE','IO_LIMIT','IO_ERROR'}:raise ValueError('Unsupported stop reason')
        if not self.job:raise JobError('Owned Job handle is closed')
        _check(self.k.TerminateJobObject(self.job,0xE0000001),'TerminateJobObject')
        self.stop_reason=reason

    def wait(self,timeout_seconds,*,settle_seconds=5):
        if (type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds) or not 0<=timeout_seconds<=3600 or
                type(settle_seconds) not in (int,float) or not math.isfinite(settle_seconds) or not 0<settle_seconds<=30):
            raise ValueError('Finite bounded wait required')
        deadline=time.monotonic()+timeout_seconds
        while True:
            observed=self.status()
            if observed['quiesced']:return observed
            if time.monotonic()>=deadline:break
            time.sleep(min(0.01,max(0,deadline-time.monotonic())))
        self.cancel(reason='DEADLINE')
        until=time.monotonic()+settle_seconds
        while time.monotonic()<until:
            observed=self.status()
            if observed['quiesced']:return observed
            time.sleep(0.01)
        raise JobError('Job termination requested but quiescence was not observed')

    def close(self):
        if self.job:
            try:
                if not self.status()['quiesced']:
                    self.cancel(reason='CLOSE');self.wait(5)
            finally:
                self.k.CloseHandle(self.job);self.job=None
                if self.process:self.k.CloseHandle(self.process);self.process=None
                for stream in (self.stdin,self.stdout,self.stderr):
                    if stream:stream.close()
    def __enter__(self):return self
    def __exit__(self,*ignored):self.close()
