"""Windows local update adapter. Exclusive handle, durable preimage, no blind retry."""
import ctypes
import hashlib
import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from v2_evidence import BlobStore, DIGEST, _regular_path
from v2_evidence_policy import validate_descriptor
from v2_operations import Operations
from v2_state_store import StateConflict, _json
from v2_operation_inputs import operation_parameters


@contextmanager
def exclusive_existing_file(path):
    if os.name!='nt': raise ValueError('This update adapter requires the Windows exclusive-handle profile')
    import msvcrt
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]; kernel.CloseHandle.restype=wintypes.BOOL
    kernel.GetFinalPathNameByHandleW.argtypes=[wintypes.HANDLE,wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD]
    kernel.GetFinalPathNameByHandleW.restype=wintypes.DWORD
    kernel.GetDriveTypeW.argtypes=[wintypes.LPCWSTR];kernel.GetDriveTypeW.restype=wintypes.UINT
    _regular_path(path)
    if kernel.GetDriveTypeW(Path(path).anchor)!=3: raise PermissionError('Update requires a fixed local volume')
    handle=kernel.CreateFileW(str(path),0xC0000000,0,None,3,0x00200000,None)
    if handle==ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
    try:
        buffer=ctypes.create_unicode_buffer(32768)
        length=kernel.GetFinalPathNameByHandleW(handle,buffer,len(buffer),0)
        if not length or length>=len(buffer): raise OSError('Cannot verify opened file identity')
        actual=buffer.value.removeprefix('\\\\?\\')
        if os.path.normcase(actual)!=os.path.normcase(os.path.abspath(path)):
            raise PermissionError('Opened file differs from the exact local path')
        descriptor=msvcrt.open_osfhandle(handle,os.O_RDWR|os.O_BINARY)
        handle=None
        with os.fdopen(descriptor,'r+b') as stream:
            info=os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
                raise PermissionError('Update requires an ordinary non-reparse file')
            if info.st_nlink!=1: raise PermissionError('Updating a multi-link file is not supported')
            yield stream
    finally:
        if handle is not None: kernel.CloseHandle(handle)


def _preimage_material(store,operation_id,*,purpose=None):
    from v2_operation_inputs import operation_binding,validate_reference
    from v2_protected_inputs import ProtectedInputs
    rows=store.connection.execute("SELECT details_json FROM execution_audit WHERE kind='FILE_UPDATE_PREIMAGE' AND subject_id=?",(operation_id,)).fetchall()
    if len(rows)!=1: raise StateConflict('Update lacks a unique durable preimage')
    record=json.loads(rows[0][0])
    if set(record)!={'schema','reference','request_hash'} or record['schema']!=2:raise StateConflict('Invalid protected preimage record')
    reference=validate_reference(record['reference'])
    operation=store.connection.execute('SELECT request_hash FROM operation WHERE operation_id=?',(operation_id,)).fetchone()
    parameters=operation_parameters(store,operation_id)
    if operation is None or record['request_hash']!=operation[0] or parameters.get('tool')!='update-file':raise StateConflict('Preimage operation differs')
    context=operation_binding(store,operation_id)
    if purpose is not None:
        from v2_evidence_policy import require_access
        require_access(parameters['preimage_policy'],owner=context['owner'],purpose=purpose,revoked=False)
    data=ProtectedInputs(store.path.parent/'protected-inputs',readonly=True).load(reference,context=context)
    before_hash=hashlib.sha256(data).hexdigest()
    if before_hash!=parameters.get('expected_sha256'):raise StateConflict('Protected preimage differs from reviewed bytes')
    result={'schema':2,'reference':reference,'before_sha256':before_hash,'before_bytes':len(data),
            'after_sha256':hashlib.sha256(parameters['content'].encode('utf-8')).hexdigest(),
            'policy':parameters['preimage_policy'],'request_hash':record['request_hash']}
    return result,data


def preimage_record(store,operation_id):
    return _preimage_material(store,operation_id)[0]


def read_preimage(store,operation_id):
    # Internal trusted recovery reader, not a public arbitrary payload endpoint.
    return _preimage_material(store,operation_id,purpose='recovery')[1]


def preserve_preimage(store,operation_id,data,request_hash):
    from v2_operation_inputs import operation_binding
    from v2_protected_inputs import ProtectedInputs
    if not store.connection.in_transaction:raise RuntimeError('Preimage reference requires an owning transaction')
    parameters=operation_parameters(store,operation_id)
    if parameters.get('tool')!='update-file' or hashlib.sha256(data).hexdigest()!=parameters.get('expected_sha256'):
        raise StateConflict('Preimage does not match prepared update')
    current=store.connection.execute('SELECT request_hash FROM operation WHERE operation_id=?',(operation_id,)).fetchone()[0]
    if current!=request_hash:raise StateConflict('Preimage request hash differs')
    if store.connection.execute("SELECT 1 FROM execution_audit WHERE kind='FILE_UPDATE_PREIMAGE' AND subject_id=?",(operation_id,)).fetchone():
        record,previous=_preimage_material(store,operation_id)
        if previous!=data:raise StateConflict('Pre-published preimage differs')
        return record['reference']
    ref=ProtectedInputs(store.path.parent/'protected-inputs').capture(data,context=operation_binding(store,operation_id))
    Operations._audit(store.connection,'FILE_UPDATE_PREIMAGE',operation_id,{'schema':2,'reference':ref,'request_hash':request_hash})
    return ref


def reconcile_update(host, *, operation_id, actor, expected_request_hash):
    """Controller-only observation under an exclusive handle; never repairs bytes."""
    from v2_local_host import unambiguous_relative_file
    from v2_evidence_policy import require_access
    store=host.store
    row=store.connection.execute('''SELECT o.state,o.execution_epoch,g.actor,g.resource,p.resource_root,t.project_id
        FROM operation o JOIN execution_grant g ON g.grant_id=o.grant_id JOIN task t ON t.task_id=o.task_id
        JOIN project p ON p.project_id=t.project_id WHERE o.operation_id=?''',(operation_id,)).fetchone()
    if row is None or row[2]!=actor: raise PermissionError('Reconciliation actor differs from operation')
    if row[1]!=store.connection.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]:
        raise StateConflict('Old epoch requires the full recovery protocol')
    record=preimage_record(store,operation_id)
    if record['request_hash']!=expected_request_hash: raise StateConflict('Reconciliation request differs')
    require_access(record['policy'],owner=row[5],purpose='recovery',revoked=False)
    root=Path(row[4]).absolute()
    _regular_path(root)
    if host.required_resource_root is not None and root.resolve()!=host.required_resource_root: raise PermissionError('Reconciliation root differs')
    with exclusive_existing_file(root/unambiguous_relative_file(row[3])) as stream:
        current=stream.read(16777217)
        current_hash=hashlib.sha256(current).hexdigest()
        classification=('REQUESTED_RESULT' if current_hash==record['after_sha256'] else
                        'PREIMAGE' if current_hash==record['before_sha256'] else 'DIVERGED')
        if classification=='DIVERGED':
            return {'decision':'REQUIRES_REVIEW','current_sha256':current_hash,'preimage_ref':record['reference']['id'],'bytes_rewritten':0}
        if row[0] not in {'INTENT_RECORDED','UNKNOWN'}:
            return {'decision':'HISTORICAL_OPERATION','state':row[0],'current_classification':classification,'bytes_rewritten':0}
        outcome='SUCCEEDED' if classification=='REQUESTED_RESULT' else 'FAILED'
        reference='local-update:sha256:'+record['after_sha256'] if outcome=='SUCCEEDED' else 'local-update:not-written'
        host.operations.observe(observation_id=operation_id+'-local-update',operation_id=operation_id,actor=actor,outcome=outcome,evidence_ref=reference)
        state=store.connection.execute('SELECT state FROM operation WHERE operation_id=?',(operation_id,)).fetchone()[0]
        return {'decision':'RECONCILED','state':state,'current_classification':classification,'bytes_rewritten':0}


def update_file(host, *, operation_id, actor, expected_request_hash):
    from v2_local_host import unambiguous_relative_file
    store=host.store; ops=host.operations
    row=store.connection.execute('''SELECT o.request_json,o.request_hash,g.resource,g.effect,g.actor,p.resource_root,o.task_id,o.task_revision
        FROM operation o JOIN execution_grant g ON g.grant_id=o.grant_id JOIN task t ON t.task_id=o.task_id
        JOIN project p ON p.project_id=t.project_id WHERE o.operation_id=?''',(operation_id,)).fetchone()
    if row is None or row[1]!=expected_request_hash: raise StateConflict('Update request is missing or stale')
    parameters=operation_parameters(store,operation_id,actor=actor)
    if set(parameters)!={'tool','path','content','expected_sha256','preimage_policy'} or parameters['tool']!='update-file':
        raise ValueError('Update requires closed update-file parameters')
    if row[3]!='write' or row[4]!=actor or parameters['path']!=row[2]: raise PermissionError('Update exceeds bound actor/resource/effect')
    if not isinstance(parameters['content'],str) or not isinstance(parameters['expected_sha256'],str) or DIGEST.fullmatch(parameters['expected_sha256']) is None:
        raise ValueError('Update requires UTF-8 content and the old byte digest')
    content=parameters['content'].encode('utf-8')
    if len(content)>16777216: raise ValueError('Update exceeds 16 MiB')
    task=store.task(row[6]); policy=parameters['preimage_policy']
    if not isinstance(policy,dict) or not isinstance(policy.get('target'),dict): raise ValueError('Explicit preimage capture policy required')
    validate_descriptor(policy,project_id=task['project_id'],task_id=row[6],task_revision=row[7],criterion=policy['target'].get('criterion'))
    from v2_contracts import criteria
    from v2_evidence_policy import require_access
    if policy['target']['criterion'] not in {item['criterion_id'] for item in criteria(task['acceptance'])}:
        raise StateConflict('Preimage policy must name an actual Task criterion')
    require_access(policy,owner=task['project_id'],purpose='recovery',revoked=False)
    if 'recovery' not in policy['access_scope']['purposes']: raise PermissionError('Preimage must remain available for recovery')
    root=Path(row[5]).absolute(); target=root/unambiguous_relative_file(parameters['path'])
    from v2_management import protect_business_resource
    protect_business_resource(host.store,root,parameters['path'])
    if str(root).startswith(('\\\\','//')): raise PermissionError('Update requires a local file root')
    _regular_path(root)
    if host.required_resource_root is not None and root.resolve()!=host.required_resource_root: raise PermissionError('Update root differs from Host policy')
    if os.name!='nt': raise ValueError('Windows update profile is unavailable')
    intent=ops.record_intent(operation_id,actor,expected_request_hash)
    if not intent['execute_once']: return {'decision':'NOT_REEXECUTED','operation_state':intent['state']}
    touched=False
    try:
        with exclusive_existing_file(target) as stream:
            before=stream.read(16777217)
            if len(before)>16777216 or hashlib.sha256(before).hexdigest()!=parameters['expected_sha256']:
                raise StateConflict('Current file differs from the reviewed preimage or exceeds the byte limit')
            new_hash=hashlib.sha256(content).hexdigest()
            with store.transaction() as c:
                ops._lease(c,operation_id,actor,intent['lease_token'])
                preimage_ref=preserve_preimage(store,operation_id,before,expected_request_hash)
            # Keep canonical writers fenced between the last authority check and
            # bounded file IO. The preimage above has its own durable commit, so
            # process death here cannot roll back the only copy of the old bytes.
            with store.transaction():
                ops.verify_lease(operation_id=operation_id,actor=actor,token=intent['lease_token'])
                touched=True
                stream.seek(0); stream.write(content); stream.truncate(); stream.flush(); os.fsync(stream.fileno())
                stream.seek(0)
                if stream.read(16777217)!=content: raise OSError('Updated bytes do not match the request')
        ops.observe(observation_id=operation_id+'-local-update',operation_id=operation_id,actor=actor,outcome='SUCCEEDED',evidence_ref='local-update:sha256:'+new_hash)
        return {'decision':'UPDATED','sha256':new_hash,'bytes':len(content),'preimage_ref':preimage_ref['id'],'profile':'WINDOWS_EXCLUSIVE_HANDLE'}
    except (OSError,ValueError):
        ops.observe(observation_id=operation_id+('-local-update-uncertain' if touched else '-local-update'),operation_id=operation_id,actor=actor,
                    outcome='UNKNOWN' if touched else 'FAILED',evidence_ref='local-update:uncertain' if touched else 'local-update:not-written')
        raise
