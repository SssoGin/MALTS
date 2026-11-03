"""Cooperative exclusion for bound CLI/MCP requests and lifecycle activation.

Host launches and direct service callers are not covered by this entry. Durable
effect/permission checks remain in services. No installation or approval here.
"""
from contextlib import closing,contextmanager
from pathlib import Path
from malts_lifecycle import resolve_discovery,LOCK_RELATIVE,TRANSACTIONS_RELATIVE
from v2_entry import LOADED_ROOT,_identity,_same
from v2_evidence import _regular_path
from v2_runtime_mutex import RuntimeMutex
from v2_state_store import StateStore
from v2_diagnostics import OperationConflict


@contextmanager
def runtime_admission(tool_root):
    """Hold activation exclusion from fresh discovery through the caller's work."""
    first=resolve_discovery(tool_root)
    root=Path(first['lifecycle_root'])
    with RuntimeMutex(root):
        current=resolve_discovery(tool_root)
        if _identity(first)!=_identity(current) or not _same(root,current['lifecycle_root']):
            raise OperationConflict('RUNTIME_IDENTITY_CHANGED')
        if not _same(LOADED_ROOT,current['malts_root']):raise OperationConflict('RUNTIME_NOT_ACTIVE')
        lock=root/LOCK_RELATIVE;_regular_path(lock)
        if lock.exists():raise OperationConflict('LIFECYCLE_TRANSACTION_PENDING')
        transactions=root/TRANSACTIONS_RELATIVE;_regular_path(transactions)
        if transactions.exists():
            if not transactions.is_dir():raise OperationConflict('LIFECYCLE_TRANSACTION_INVALID')
            with __import__('os').scandir(transactions) as entries:
                if next(entries,None) is not None:raise OperationConflict('LIFECYCLE_TRANSACTION_PENDING')
        yield


def execute_admitted_request(*,tool_root,state_dir,request,evidence_reader=None,required_resource_root=None):
    from v2_service import execute_request
    with runtime_admission(tool_root):
        with closing(StateStore(Path(state_dir)/'state.db')) as store:
            # Check on every acquisition, including abandoned=false. The
            # service still applies task-specific unresolved-effect controls.
            store.require_execution_ready()
            return execute_request(store,request,evidence_reader=evidence_reader,
                required_resource_root=required_resource_root)
