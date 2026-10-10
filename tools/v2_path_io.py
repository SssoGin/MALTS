"""Internal Windows file I/O spelling; public identities remain normal paths."""
import os
from pathlib import Path


def io_path(value):
    path=Path(value)
    if os.name!='nt':return path
    raw=os.path.abspath(path)
    if raw.startswith('\\\\?\\'):return Path(raw)
    if raw.startswith('\\\\') or not Path(raw).drive:
        raise ValueError('Extended I/O requires a fixed local absolute path')
    return Path('\\\\?\\'+raw)


class ManagedPathIOError(OSError):
    """Bounded diagnostics omit file names and private absolute paths."""
    def __init__(self,operation,path,error):
        self.operation=operation
        self.path_characters=len(os.path.abspath(path))
        self.os_error=getattr(error,'winerror',None) or error.errno
        super().__init__('MANAGED_FILE_IO_FAILED')
