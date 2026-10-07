"""Operation control/input separation. These helpers are internal, not read APIs."""
import hashlib,json,re
from v2_state_store import StateConflict,_json,_text
from v2_protected_inputs import ProtectedInputs,PROFILE,MAX_CIPHER_BYTES

KIND='PROTECTED_OPERATION_PARAMETERS'


def metadata_only(value,resource):
    return value=={} or (set(value)=={'tool','path'} and value['tool']=='read-file' and value['path']==resource)


def binding(store,*,operation_id,grant_id,task_id,task_revision,actor):
    owner=store.connection.execute('SELECT project_id FROM task WHERE task_id=?',(task_id,)).fetchone()[0]
    return {'owner':owner,'task_id':task_id,'task_revision':task_revision,'operation_id':operation_id,'grant_id':grant_id,'actor':actor}


def protect_parameters(store,parameters,*,resource,context,capture_authority_ref):
    if metadata_only(parameters,resource):return parameters
    if capture_authority_ref is None:raise PermissionError('Protected input capture requires controller authority')
    _text(capture_authority_ref,'capture_authority_ref')
    if len(capture_authority_ref)>256:raise ValueError('Capture authority reference is too long')
    reference=ProtectedInputs(store.path.parent/'protected-inputs').capture(_json(parameters).encode('utf-8'),context=context)
    return {'kind':KIND,'reference':reference,'capture_authority_ref':capture_authority_ref}


def protected_reference(control):
    if not isinstance(control,dict) or control.get('kind')!=KIND:return None
    if set(control)!={'kind','reference','capture_authority_ref'}:raise StateConflict('Invalid protected operation control')
    _text(control['capture_authority_ref'],'capture_authority_ref')
    return validate_reference(control['reference'])


def validate_reference(ref):
    if not isinstance(ref,dict) or set(ref)!={'format','id','profile','cipher_sha256','cipher_bytes'}:raise StateConflict('Invalid protected reference')
    if type(ref['format']) is not int or ref['format']!=1 or ref['profile']!=PROFILE or not isinstance(ref['id'],str) or not re.fullmatch('[a-f0-9]{32}',ref['id']):raise StateConflict('Invalid protected input identity')
    if type(ref['cipher_bytes']) is not int or not 0<ref['cipher_bytes']<=MAX_CIPHER_BYTES:raise StateConflict('Invalid protected input byte size')
    if not isinstance(ref['cipher_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',ref['cipher_sha256']):raise StateConflict('Invalid protected input digest')
    return ref


def operation_parameters(store,operation_id,*,actor=None):
    row=store.connection.execute('''SELECT o.request_json,o.request_hash,o.grant_id,o.task_id,o.task_revision,g.actor,g.resource,g.effect
        FROM operation o JOIN execution_grant g ON g.grant_id=o.grant_id WHERE o.operation_id=?''',(operation_id,)).fetchone()
    if row is None:raise StateConflict('Unknown operation input')
    if actor is not None and actor!=row[5]:raise PermissionError('Operation input actor differs')
    control=json.loads(row[0])
    if hashlib.sha256(_json([row[2],row[5],row[6],row[7],control]).encode()).hexdigest()!=row[1]:raise StateConflict('Operation control fingerprint changed')
    reference=protected_reference(control)
    if reference is None:
        if not isinstance(control,dict) or not metadata_only(control,row[6]):raise StateConflict('Unprotected operation payload is not supported in this schema')
        return control
    context=binding(store,operation_id=operation_id,grant_id=row[2],task_id=row[3],task_revision=row[4],actor=row[5])
    data=ProtectedInputs(store.path.parent/'protected-inputs',readonly=True).load(reference,context=context)
    value=json.loads(data)
    if not isinstance(value,dict):raise StateConflict('Protected operation parameters are not an object')
    return value


def protected_files(connection):
    result={}
    for request,resource,request_hash,grant_id,actor,effect in connection.execute('SELECT o.request_json,g.resource,o.request_hash,o.grant_id,g.actor,g.effect FROM operation o JOIN execution_grant g ON g.grant_id=o.grant_id'):
        control=json.loads(request);ref=protected_reference(control)
        if hashlib.sha256(_json([grant_id,actor,resource,effect,control]).encode()).hexdigest()!=request_hash:raise StateConflict('Backup operation control fingerprint differs')
        if ref is None and (not isinstance(control,dict) or not metadata_only(control,resource)):raise StateConflict('Unprotected operation payload cannot form a qualified backup')
        if ref:result['protected-inputs/'+ref['id']+'.bin']=ref['cipher_sha256']
    seen=set()
    for operation_id,details in connection.execute("SELECT subject_id,details_json FROM execution_audit WHERE kind='FILE_UPDATE_PREIMAGE'"):
        record=json.loads(details)
        if set(record)!={'schema','reference','request_hash'} or type(record['schema']) is not int or record['schema']!=2:raise StateConflict('Unprotected preimage record cannot form a qualified backup')
        operation=connection.execute('SELECT request_hash FROM operation WHERE operation_id=?',(operation_id,)).fetchone()
        if operation_id in seen or operation is None or operation[0]!=record['request_hash']:raise StateConflict('Preimage reference has no unique matching operation')
        seen.add(operation_id)
        ref=validate_reference(record['reference'])
        result['protected-inputs/'+ref['id']+'.bin']=ref['cipher_sha256']
    return result


def operation_binding(store,operation_id):
    row=store.connection.execute('''SELECT o.grant_id,o.task_id,o.task_revision,g.actor FROM operation o
        JOIN execution_grant g ON g.grant_id=o.grant_id WHERE o.operation_id=?''',(operation_id,)).fetchone()
    if row is None:raise StateConflict('Unknown operation binding')
    return binding(store,operation_id=operation_id,grant_id=row[0],task_id=row[1],task_revision=row[2],actor=row[3])
