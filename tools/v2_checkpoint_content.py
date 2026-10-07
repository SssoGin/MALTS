"""Checkpoint projection protection. Original legacy sources remain private inputs."""
import base64
import hashlib
import json
from v2_state_store import StateConflict,_json
from v2_protected_inputs import seal,open_sealed,ProtectedInputError

KIND='PROTECTED_CHECKPOINT_TEXT_V1'


def _transform(value,context,protect):
    if protect:
        reference,cipher=seal(value.encode('utf-8'),context=context)
        return _json({'kind':KIND,'reference':reference,'ciphertext':base64.b64encode(cipher).decode('ascii')})
    try:
        item=json.loads(value)
        if not isinstance(item,dict) or set(item)!={'kind','reference','ciphertext'} or item['kind']!=KIND:raise ValueError()
        cipher=base64.b64decode(item['ciphertext'],validate=True)
    except (ValueError,TypeError,KeyError):raise ProtectedInputError('Invalid protected checkpoint text') from None
    return open_sealed(cipher,item['reference'],context=context).decode('utf-8')


def checkpoint_row(connection,row,*,protect=False):
    if row is None:raise StateConflict('Checkpoint is missing')
    identity,run_id,revision,summary,next_action,pending=row
    run=connection.execute('''SELECT t.project_id,r.task_id,r.task_revision,r.actor,r.host,r.native_id
        FROM execution_run r JOIN task t ON t.task_id=r.task_id WHERE r.run_id=?''',(run_id,)).fetchone()
    if run is None or run[2]!=revision:raise StateConflict('Checkpoint Run binding differs')
    context={'owner':run[0],'record_type':'checkpoint','record_id':identity,'record_revision':revision,
             'binding_sha256':hashlib.sha256(_json([run_id,list(run)]).encode()).hexdigest()}
    return (identity,run_id,revision,
            _transform(summary,{**context,'field':'summary'},protect),
            _transform(next_action,{**context,'field':'next_action'},protect),pending)


def legacy_row(row,*,protect=False):
    owner,session,phase,summary,next_action,source,digest=row
    context={'owner':owner,'record_type':'legacy-checkpoint','record_id':session,'record_revision':0,
             'binding_sha256':hashlib.sha256(_json([phase,source,digest]).encode()).hexdigest()}
    return (owner,session,phase,
            _transform(summary,{**context,'field':'summary'},protect),
            _transform(next_action,{**context,'field':'next_action'},protect),source,digest)
