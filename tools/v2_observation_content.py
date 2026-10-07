"""Protected observation locators; internal verification reader, not propagation API."""
import base64
import hashlib
import json
from v2_state_store import StateConflict,_json
from v2_operation_inputs import binding
from v2_protected_inputs import seal,open_sealed,ProtectedInputError

MAX_REFERENCE_BYTES=16384
KIND='PROTECTED_OBSERVATION_REFERENCE_V1'


def _context(store,observation_id,operation_id,actor,outcome):
    row=store.connection.execute('SELECT grant_id,task_id,task_revision FROM operation WHERE operation_id=?',(operation_id,)).fetchone()
    if row is None:raise StateConflict('Observation operation is unavailable')
    result=binding(store,operation_id=operation_id,grant_id=row[0],task_id=row[1],task_revision=row[2],actor=actor)
    result.update(record_id=observation_id,record_binding=hashlib.sha256(_json([KIND,outcome]).encode()).hexdigest())
    return result


def fingerprint(observation_id,operation_id,actor,outcome,control):
    return hashlib.sha256(_json([observation_id,operation_id,actor,outcome,control]).encode()).hexdigest()


def encode(store,observation_id,operation_id,actor,outcome,value):
    raw=value.encode('utf-8')
    if len(raw)>MAX_REFERENCE_BYTES:raise ValueError('Observation reference exceeds byte limit')
    reference,cipher=seal(raw,context=_context(store,observation_id,operation_id,actor,outcome))
    return _json({'kind':KIND,'reference':reference,'ciphertext':base64.b64encode(cipher).decode('ascii')})


def read_reference(store,observation_id,*,actor=None):
    row=store.connection.execute('''SELECT o.operation_id,o.outcome,o.evidence_ref,o.observation_hash,g.actor
        FROM operation_observation o JOIN operation p ON p.operation_id=o.operation_id
        JOIN execution_grant g ON g.grant_id=p.grant_id WHERE o.observation_id=?''',(observation_id,)).fetchone()
    if row is None:raise StateConflict('Unknown observation')
    if actor is not None and actor!=row[4]:raise PermissionError('Observation actor differs')
    if fingerprint(observation_id,row[0],row[4],row[1],row[2])!=row[3]:raise StateConflict('Observation control fingerprint changed')
    try:
        if len(row[2])>65536:raise ValueError()
        control=json.loads(row[2])
        if not isinstance(control,dict) or set(control)!={'kind','reference','ciphertext'} or control['kind']!=KIND:
            raise ValueError()
        cipher=base64.b64decode(control['ciphertext'],validate=True)
    except (ValueError,TypeError,KeyError):raise ProtectedInputError('Invalid protected observation reference') from None
    raw=open_sealed(cipher,control['reference'],context=_context(store,observation_id,row[0],row[4],row[1]))
    if len(raw)>MAX_REFERENCE_BYTES:raise ProtectedInputError('Protected observation exceeds byte limit')
    return raw.decode('utf-8')
