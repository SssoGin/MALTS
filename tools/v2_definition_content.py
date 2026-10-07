"""Protected definition values and per-Project keyed request fingerprints.

This stores application data, not Host credentials. No key is written globally
or returned by an API. Original import inputs remain separate private assets.
"""
import base64
import hashlib
import hmac
import json
import secrets
from v2_state_store import StateConflict,_json
from v2_protected_inputs import seal,open_sealed,ProtectedInputError

KIND='PROTECTED_DEFINITION_VALUE_V1'
PREVIEW_CHARACTERS=2048


def context(owner,kind,identity,revision,field):
    return {'owner':owner,'record_type':'definition:'+kind,'record_id':identity,'record_revision':revision,
            'field':field,'binding_sha256':hashlib.sha256(_json([owner,kind,identity,revision]).encode()).hexdigest()}


def encode(value,owner,kind,identity,revision,field):
    reference,cipher=seal(_json(value).encode('utf-8'),context=context(owner,kind,identity,revision,field))
    return _json({'kind':KIND,'reference':reference,'ciphertext':base64.b64encode(cipher).decode('ascii')})


def decode(value,owner,kind,identity,revision,field):
    try:
        control=json.loads(value)
        if not isinstance(control,dict) or set(control)!={'kind','reference','ciphertext'} or control['kind']!=KIND:raise ValueError()
        cipher=base64.b64decode(control['ciphertext'],validate=True)
    except (ValueError,TypeError,KeyError):raise ProtectedInputError('Invalid protected definition') from None
    raw=open_sealed(cipher,control['reference'],context=context(owner,kind,identity,revision,field))
    return json.loads(raw)


def initialize_key(connection,project_id):
    connection.execute('INSERT INTO definition_key VALUES (?,?)',
        (project_id,encode(secrets.token_hex(32),project_id,'request-key',project_id,0,'key')))


def request_fingerprint(connection,project_id,value):
    row=connection.execute('SELECT key_material FROM definition_key WHERE project_id=?',(project_id,)).fetchone()
    if row is None:
        if not connection.execute('SELECT 1 FROM project WHERE project_id=?',(project_id,)).fetchone():raise StateConflict('Project is not initialized')
        raise ProtectedInputError('Project definition fingerprint key is missing')
    key=bytes.fromhex(decode(row[0],project_id,'request-key',project_id,0,'key'))
    if len(key)!=32:raise ProtectedInputError('Invalid definition fingerprint key')
    return hmac.new(key,_json(value).encode('utf-8'),hashlib.sha256).hexdigest()


def _save_preview(connection,goal,body,owner,kind,identity,revision):
    digest=hashlib.sha256(body.encode('utf-8')).hexdigest()
    value={'text':goal[:PREVIEW_CHARACTERS],'characters':len(goal),'body_sha256':digest}
    protected=encode(value,owner,kind,identity,revision,'goal-preview')
    connection.execute('INSERT OR REPLACE INTO definition_preview VALUES (?,?,?,?,?,?)',
        (owner,kind,identity,revision,digest,protected))
    return digest


def write_goal(connection,goal,owner,kind,identity,revision):
    if not connection.in_transaction:raise RuntimeError('Goal and preview require one transaction')
    body=encode(goal,owner,kind,identity,revision,'goal')
    _save_preview(connection,goal,body,owner,kind,identity,revision)
    return body


def read_preview(connection,owner,kind,identity,revision,*,limit=2048):
    if type(limit) is not int or not 1<=limit<=PREVIEW_CHARACTERS:raise ValueError('Invalid Goal preview limit')
    row=connection.execute('''SELECT body_sha256,protected_preview FROM definition_preview
        WHERE project_id=? AND entity_kind=? AND entity_id=? AND revision=?''',(owner,kind,identity,revision)).fetchone()
    unavailable={'status':'UNAVAILABLE','text':None,'characters':None}
    if row is None:return unavailable
    try:
        # The protected preview itself is bounded; never load the full Goal as a fallback.
        if len(row[1].encode('utf-8'))>32768:raise ProtectedInputError('Oversized Goal preview')
        value=decode(row[1],owner,kind,identity,revision,'goal-preview')
        if (not isinstance(value,dict) or set(value)!={'text','characters','body_sha256'} or
                not isinstance(value['text'],str) or type(value['characters']) is not int or
                value['characters']<0 or len(value['text'])!=min(value['characters'],PREVIEW_CHARACTERS) or
                value['body_sha256']!=row[0]):raise ProtectedInputError('Invalid Goal preview binding')
        return {'status':'AVAILABLE','text':value['text'][:limit],'characters':value['characters']}
    except (ValueError,TypeError,KeyError):return unavailable


class DefinitionPreviews:
    def __init__(self,store):self.store=store

    def refresh(self,*,project_id,entity_kind,entity_id,revision):
        """Controller repair of a derived view only; canonical definitions never change."""
        if type(revision) is not int or revision<0:raise ValueError('Invalid definition revision')
        with self.store.transaction() as c:
            if entity_kind=='project-original':
                row=c.execute('SELECT original_goal FROM project WHERE project_id=? AND project_id=?',
                    (project_id,entity_id)).fetchone() if revision==0 else None
            elif entity_kind=='project':
                row=c.execute('SELECT goal FROM project_revision WHERE project_id=? AND project_id=? AND revision=?',
                    (project_id,entity_id,revision)).fetchone()
            elif entity_kind in {'task','phase'}:
                # Both identifiers are fixed by this closed branch, never caller SQL.
                row=c.execute(f'''SELECT r.goal FROM {entity_kind}_revision r JOIN {entity_kind} e
                    ON e.{entity_kind}_id=r.{entity_kind}_id WHERE e.project_id=? AND e.{entity_kind}_id=? AND r.revision=?''',
                    (project_id,entity_id,revision)).fetchone()
            else:raise ValueError('Unsupported definition kind')
            if row is None:raise StateConflict('Definition identity is unavailable')
            goal=decode(row[0],project_id,entity_kind,entity_id,revision,'goal')
            expected=hashlib.sha256(row[0].encode()).hexdigest()
            old=c.execute('''SELECT body_sha256 FROM definition_preview
                WHERE project_id=? AND entity_kind=? AND entity_id=? AND revision=?''',
                (project_id,entity_kind,entity_id,revision)).fetchone()
            view=read_preview(c,project_id,entity_kind,entity_id,revision)
            if old==(expected,) and view=={'status':'AVAILABLE','text':goal[:PREVIEW_CHARACTERS],'characters':len(goal)}:
                return {'decision':'REPLAY','canonical_changed':False,'execution_authorized':False}
            _save_preview(c,goal,row[0],project_id,entity_kind,entity_id,revision)
            return {'decision':'REFRESHED','canonical_changed':False,'execution_authorized':False}
