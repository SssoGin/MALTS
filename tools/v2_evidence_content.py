"""Protected Evidence representation. Authorization belongs to Acceptance/Host.

Blob identity addresses ciphertext, never a plaintext-derived lookup key.
The immutable evidence tuple and descriptor are authenticated as DPAPI context.
"""
import base64
import hashlib
import json
from v2_state_store import StateConflict, _json
from v2_operation_inputs import binding
from v2_protected_inputs import seal, open_sealed, ProtectedInputError

KIND='PROTECTED_EVIDENCE_V1'


def context(store,values,descriptor_json,*,lineage_record=None):
    evidence_id,task_id,revision,operation_id=values[:4]
    row=store.connection.execute('''SELECT o.grant_id,g.actor FROM operation o
        JOIN execution_grant g ON g.grant_id=o.grant_id WHERE o.operation_id=?''',(operation_id,)).fetchone()
    if row is None:raise StateConflict('Evidence operation binding is unavailable')
    result=binding(store,operation_id=operation_id,grant_id=row[0],task_id=task_id,task_revision=revision,actor=row[1])
    bound=[list(values[:6])+list(values[7:]),json.loads(descriptor_json)]
    if lineage_record is not None:bound.append(lineage_record)
    result.update(record_id=evidence_id,record_binding=hashlib.sha256(_json(bound).encode()).hexdigest())
    return result


def encode(store,values,descriptor_json,data,*,lineage_record=None):
    reference,cipher=seal(data,context=context(store,values,descriptor_json,lineage_record=lineage_record))
    return _json({'kind':KIND,'reference':reference,'ciphertext':base64.b64encode(cipher).decode('ascii')}).encode()


def decode(store,values,descriptor_json,stored):
    from v2_evidence_derivation import lineage
    try:
        value=json.loads(stored)
        if not isinstance(value,dict) or set(value)!={'kind','reference','ciphertext'} or value['kind']!=KIND:
            raise ValueError()
        cipher=base64.b64decode(value['ciphertext'],validate=True)
    except (ValueError,TypeError,KeyError):
        raise ProtectedInputError('Protected evidence representation is invalid') from None
    return open_sealed(cipher,value['reference'],context=context(store,values,descriptor_json,lineage_record=lineage(store,values[0])))
