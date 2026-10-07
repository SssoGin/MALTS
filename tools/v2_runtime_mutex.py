"""Windows cooperative runtime exclusion primitive, not a complete write fence."""
import ctypes as C
from ctypes import wintypes as W
import hashlib,os,threading
from pathlib import Path
from v2_evidence import _regular_path

_held=threading.local()


class RuntimeMutexBusy(ValueError):pass


def capabilities():
    return {'primitive':'WINDOWS_GLOBAL_NAMED_MUTEX','integrated_write_fence':False,
        'filesystem_state_created':False,'persistent_recovery_provided':False,
        'durable_state_check_required_on_every_acquire':True,
        'cross_session_qualified':False,'cross_machine_supported':False,'execution_authorized':False}


class RuntimeMutex:
    def __init__(self,root):
        if os.name!='nt':raise OSError('No qualified runtime mutex on this platform')
        path=Path(root)
        if not path.is_absolute():raise ValueError('Absolute runtime authority root required')
        _regular_path(path)
        path=path.resolve(strict=True)
        if not path.is_dir() or str(path).startswith(('\\\\','//')):raise ValueError('Local runtime directory required')
        key=os.path.normcase(str(path)).encode('utf-8')
        self.name='Global\\malts-runtime-v1-'+hashlib.sha256(key).hexdigest()
        self.k=C.WinDLL('kernel32',use_last_error=True)
        for name,args,result in (
            ('CreateMutexW',[C.c_void_p,W.BOOL,W.LPCWSTR],W.HANDLE),
            ('WaitForSingleObject',[W.HANDLE,W.DWORD],W.DWORD),
            ('ReleaseMutex',[W.HANDLE],W.BOOL),('CloseHandle',[W.HANDLE],W.BOOL)):
            function=getattr(self.k,name);function.argtypes=args;function.restype=result
        self.handle=self.k.CreateMutexW(None,False,self.name);self.owner=None
        if not self.handle:raise OSError(C.get_last_error(),'Runtime mutex could not be opened')

    def acquire(self,timeout_ms=0):
        if type(timeout_ms) is not int or not 0<=timeout_ms<=5000:raise ValueError('Bounded mutex wait required')
        if not self.handle:raise RuntimeError('Runtime mutex is closed')
        names=getattr(_held,'names',set())
        if self.owner is not None or self.name in names:raise RuntimeError('Nested runtime mutex acquisition is not supported')
        result=self.k.WaitForSingleObject(self.handle,timeout_ms)
        if result==258:raise RuntimeMutexBusy('Runtime authority is busy')
        if result not in (0,128):raise OSError(C.get_last_error(),'Runtime mutex wait failed')
        self.owner=threading.current_thread();_held.names=names|{self.name}
        return {'owned':True,'abandoned':result==128,'state_consistency_verified':False,'execution_authorized':False,
            'durable_state_check_required':True}

    def release(self):
        if self.owner is None:raise RuntimeError('Runtime mutex is not owned')
        if self.owner is not threading.current_thread():raise RuntimeError('Runtime mutex must be released by its owning thread')
        if not self.k.ReleaseMutex(self.handle):raise OSError(C.get_last_error(),'Runtime mutex release failed')
        self.owner=None;_held.names=getattr(_held,'names',set())-{self.name}

    def close(self):
        if self.handle:
            if self.owner is not None:self.release()
            if not self.k.CloseHandle(self.handle):raise OSError(C.get_last_error(),'Runtime mutex handle close failed')
            self.handle=None

    def __enter__(self):
        if self.owner is not None:raise RuntimeError('Runtime mutex is already owned')
        try:return self.acquire()
        except BaseException:
            self.close()
            raise
    def __exit__(self,*ignored):self.close()
