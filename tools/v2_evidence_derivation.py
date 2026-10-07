"""Controller-reviewed derivation and transitive propagation, not a sanitizer.

Sources must explicitly permit derivation. Raw source bodies are never returned
by lineage checks. Review/authority references require trusted Host enforcement.
"""
import hashlib
import json
from v2_state_store import StateConflict, _json, _text
from v2_evidence_policy import require_access
from v2_evidence import EvidenceReadLimit,BlobStore

MAX_SOURCES=16
MAX_ANCESTORS=64


def lineage(store,evidence_id):
    row=store.connection.execute('SELECT authority_ref,review_ref FROM evidence_derivation WHERE evidence_id=?',(evidence_id,)).fetchone()
    if row is None:return None
    sources=store.connection.execute('''SELECT source_id,source_blob_hash,source_binding_sha256
        FROM evidence_derivation_source WHERE evidence_id=? ORDER BY source_id''',(evidence_id,)).fetchall()
    if not 1<=len(sources)<=MAX_SOURCES:raise StateConflict('Invalid evidence derivation source count')
    return {'authority_ref':row[0],'review_ref':row[1],
            'sources':[{'evidence_id':r[0],'blob_hash':r[1],'binding_sha256':r[2]} for r in sources]}


def source_record(store,evidence_id,owner):
    row=store.connection.execute('''SELECT e.task_id,e.task_revision,e.operation_id,e.criterion,e.result,e.blob_hash,
        e.verifier_ref,e.method,e.evidence_level,p.descriptor_json,p.revoked,
        EXISTS(SELECT 1 FROM evidence_invalidation i WHERE i.evidence_id=e.evidence_id)
        FROM evidence e JOIN evidence_policy p ON p.evidence_id=e.evidence_id WHERE e.evidence_id=?''',(evidence_id,)).fetchone()
    if row is None or row[11]:raise PermissionError('Derivation source is unavailable')
    require_access(json.loads(row[9]),owner=owner,purpose='derivation',revoked=bool(row[10]))
    # Includes randomized ciphertext identity and the direct lineage. This is
    # not a low-entropy plaintext hash. Revocation/expiry remain live checks.
    fingerprint=hashlib.sha256(_json([evidence_id,list(row[:10]),lineage(store,evidence_id)]).encode()).hexdigest()
    return {'evidence_id':evidence_id,'blob_hash':row[5],'binding_sha256':fingerprint}


def source_closure(store,evidence_id,owner):
    """Check current metadata/permissions before any derivative body read."""
    pending=[(evidence_id,frozenset({evidence_id}))]
    result={}
    while pending:
        current,ancestors=pending.pop()
        item=lineage(store,current)
        if item is None:continue
        for expected in item['sources']:
            identity=expected['evidence_id']
            if identity in ancestors:raise StateConflict('Evidence derivation cycle')
            actual=source_record(store,identity,owner)
            if actual!=expected:raise StateConflict('Evidence derivation source binding changed')
            if identity in result:continue
            result[identity]=actual['blob_hash']
            if len(result)>MAX_ANCESTORS:raise StateConflict('Evidence derivation closure exceeds bound')
            pending.append((identity,ancestors|{identity}))
    return result


def read_closure(blobs,closure,*,max_bytes=None):
    consumed=0
    try:
        for digest in closure.values():
            consumed+=len(blobs.read(digest,max_bytes=None if max_bytes is None else max_bytes-consumed))
        return consumed
    except (ValueError,OSError) as exc:
        if isinstance(exc,EvidenceReadLimit):exc.minimum_bytes+=consumed
        exc.bytes_read=consumed+getattr(exc,'bytes_read',0)
        raise


def checked_outcome_export(store,blobs,evidence_id,owner):
    from v2_acceptance import Acceptance
    raw=Acceptance(store,blobs)._read_in_transaction(evidence_id=evidence_id,owner=owner,purpose='export',max_bytes=4096)
    row=store.connection.execute('SELECT descriptor_json FROM evidence_policy WHERE evidence_id=?',(evidence_id,)).fetchone()
    descriptor=json.loads(row[0])
    if (descriptor['content_class']!='redacted-observation' or descriptor['sensitivity']!='public' or
            descriptor['redaction_policy_version']!='closed-outcome-v1' or lineage(store,evidence_id) is None):
        raise PermissionError('Outcome export requires a public, source-bound closed derivative')
    try: value=json.loads(raw)
    except (ValueError,UnicodeError): raise ValueError('Invalid closed outcome export') from None
    if (not isinstance(value,dict) or not {'policy','outcome'}<=set(value) or
            set(value)-{'policy','outcome','duration_ms','tool_calls'} or value['policy']!='closed-outcome-v1' or
            value['outcome'] not in ('SUCCEEDED','FAILED','CANCELLED','UNKNOWN')):
        raise ValueError('Export content exceeds the closed outcome contract')
    for key in ('duration_ms','tool_calls'):
        if key in value and (type(value[key]) is not int or not 0<=value[key]<=1000000000000):
            raise ValueError('Export metric is not a bounded integer')
    canonical=json.dumps(value,sort_keys=True,separators=(',',':'))
    if raw!=canonical.encode('utf-8'): raise ValueError('Export requires canonical closed outcome bytes')
    return canonical


def require_export_ready(store,operation_id,actor):
    from v2_operation_inputs import operation_parameters
    parameters=operation_parameters(store,operation_id,actor=actor)
    if 'evidence_export' not in parameters: return
    if set(parameters)!={'tool','path','content','evidence_export'} or parameters['tool']!='create-file':
        raise ValueError('Invalid evidence export operation')
    owner=store.connection.execute('SELECT t.project_id FROM operation o JOIN task t ON t.task_id=o.task_id WHERE o.operation_id=?',(operation_id,)).fetchone()[0]
    content=checked_outcome_export(store,BlobStore(store.path.parent/'blobs',readonly=True),parameters['evidence_export'],owner)
    if content!=parameters['content']: raise StateConflict('Export source differs from prepared bytes')


class Derivations:
    def __init__(self,store,blobs):
        from v2_acceptance import Acceptance
        self.store,self.blobs=store,blobs
        self.evidence=Acceptance(store,blobs)

    def prepare_outcome_export(self, *, evidence_id,operation_id,grant_id,actor,resource,authority_ref):
        from v2_operations import Operations
        operations=Operations(self.store)
        with self.store.transaction() as c:
            grant=operations._grant(c,grant_id,actor,resource,'write')
            owner=c.execute('SELECT project_id FROM task WHERE task_id=?',(grant[0],)).fetchone()[0]
            content=checked_outcome_export(self.store,self.blobs,evidence_id,owner)
        return operations.prepare(operation_id=operation_id,grant_id=grant_id,actor=actor,resource=resource,effect='write',
            parameters={'tool':'create-file','path':resource,'content':content,'evidence_export':evidence_id},
            capture_authority_ref=authority_ref)

    def record_closed_outcome(self, *, evidence_id,task_id,task_revision,operation_id,criterion,result,
                              source_evidence_id,authority_ref,review_ref,descriptor,max_source_bytes=1048576):
        """Extract fixed operational fields; no arbitrary text is propagated."""
        if not isinstance(descriptor,dict) or descriptor.get('redaction_policy_version')!='closed-outcome-v1':
            raise ValueError('Closed outcome requires its exact extraction policy')
        if type(max_source_bytes) is not int or not 1024<=max_source_bytes<=1048576:
            raise ValueError('Invalid closed outcome source budget')
        owner=descriptor.get('owner')
        c=self.store.connection; c.execute('BEGIN')
        try:
            raw,_=self.evidence._read_metered_in_transaction(evidence_id=source_evidence_id,owner=owner,
                purpose='derivation',max_bytes=max_source_bytes)
            c.execute('COMMIT')
        except BaseException:
            if c.in_transaction: c.execute('ROLLBACK')
            raise
        def unique_pairs(pairs):
            item={}
            for key,value in pairs:
                if key in item: raise ValueError('Duplicate outcome field')
                item[key]=value
            return item
        try:
            source=json.loads(raw,object_pairs_hook=unique_pairs)
        except (ValueError,UnicodeError,RecursionError):
            raise ValueError('Source is not a supported structured outcome') from None
        if not isinstance(source,dict) or source.get('outcome') not in ('SUCCEEDED','FAILED','CANCELLED','UNKNOWN'):
            raise ValueError('Source outcome must be a supported fixed value')
        selected={'policy':'closed-outcome-v1','outcome':source['outcome']}
        for key in ('duration_ms','tool_calls'):
            if key in source:
                value=source[key]
                if type(value) is not int or not 0<=value<=1000000000000:
                    raise ValueError('Outcome metric must be a bounded nonnegative integer')
                selected[key]=value
        return self.record(evidence_id=evidence_id,task_id=task_id,task_revision=task_revision,
            operation_id=operation_id,criterion=criterion,result=result,source_evidence_ids=[source_evidence_id],
            authority_ref=authority_ref,review_ref=review_ref,data=json.dumps(selected,sort_keys=True,separators=(',',':')).encode('utf-8'),
            descriptor=descriptor,max_source_bytes=max_source_bytes)

    def record(self, *, evidence_id,task_id,task_revision,operation_id,criterion,result,
               source_evidence_ids,authority_ref,review_ref,data,descriptor,max_source_bytes=16777216):
        """Capture an already reviewed independent derivative; never execute text."""
        if (not isinstance(source_evidence_ids,list) or not 1<=len(source_evidence_ids)<=MAX_SOURCES or
                any(not isinstance(v,str) or not v.strip() or len(v)>256 for v in source_evidence_ids) or
                len(set(source_evidence_ids))!=len(source_evidence_ids) or evidence_id in source_evidence_ids):
            raise ValueError('Explicit distinct derivation sources are required')
        for key,value in (('authority_ref',authority_ref),('review_ref',review_ref)):
            _text(value,key)
            if len(value)>256:raise ValueError('Derivation reference exceeds limit')
        if type(max_source_bytes) is not int or not 1024<=max_source_bytes<=67108864:
            raise ValueError('Invalid source read budget')
        if not isinstance(descriptor,dict) or descriptor.get('content_class')!='redacted-observation':
            raise ValueError('Derivative requires a reviewed redacted-observation descriptor')
        if descriptor.get('review_ref')!=review_ref:raise StateConflict('Derivative review binding differs')
        values,descriptor_json=self.evidence._validate_record(evidence_id=evidence_id,task_id=task_id,
            task_revision=task_revision,operation_id=operation_id,criterion=criterion,result=result,
            verifier_ref=review_ref,data=data,descriptor=descriptor,method='derived-review',evidence_level='D')
        owner=json.loads(descriptor_json)['owner']
        c=self.store.connection
        # Read a coherent source snapshot before publishing any candidate blob.
        c.execute('BEGIN')
        try:
            self.store.require_execution_ready()
            sources=[];consumed=0;closure=set()
            for identity in sorted(source_evidence_ids):
                raw,cost=self.evidence._read_metered_in_transaction(evidence_id=identity,owner=owner,
                    purpose='derivation',max_bytes=max_source_bytes-consumed)
                consumed+=cost
                if raw==data:raise ValueError('An unchanged source is not a redacted derivative')
                sources.append(source_record(self.store,identity,owner))
                closure.add(identity);closure.update(source_closure(self.store,identity,owner))
            if len(closure)>MAX_ANCESTORS:raise StateConflict('Evidence derivation closure exceeds bound')
            record={'authority_ref':authority_ref,'review_ref':review_ref,'sources':sources}
            prior=lineage(self.store,evidence_id)
            if prior is not None and prior!=record:raise StateConflict('Derivation identity is immutable')
            if prior is None and c.execute('SELECT 1 FROM evidence WHERE evidence_id=?',(evidence_id,)).fetchone():
                raise StateConflict('Existing evidence cannot be relabeled as a derivative')
            c.execute('COMMIT')
        except BaseException:
            if c.in_transaction:c.execute('ROLLBACK')
            raise
        values=self.evidence._publish_content(values,descriptor_json,data,lineage_record=record)
        with self.store.transaction():
            self.store.require_execution_ready()
            # Recheck live permissions and exact source bytes after publication.
            current_closure={}
            for expected in sources:
                identity=expected['evidence_id']
                if source_record(self.store,identity,owner)!=expected:raise StateConflict('Source changed during derivation')
                current_closure[identity]=expected['blob_hash']
                current_closure.update(source_closure(self.store,identity,owner))
            consumed+=read_closure(self.blobs,current_closure,max_bytes=max_source_bytes-consumed)
            prior=lineage(self.store,evidence_id)
            if prior is not None and prior!=record:raise StateConflict('Derivation identity changed')
            decision=self.evidence._persist_evidence(values,descriptor_json)
            if decision=='RECORDED':
                c.execute('INSERT INTO evidence_derivation VALUES (?,?,?)',(evidence_id,authority_ref,review_ref))
                c.executemany('INSERT INTO evidence_derivation_source VALUES (?,?,?,?)',
                    [(evidence_id,r['evidence_id'],r['blob_hash'],r['binding_sha256']) for r in sources])
                c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                    ('EVIDENCE_DERIVED',evidence_id,_json(record)))
            elif prior!=record:raise StateConflict('Derivative lineage is missing')
        return {'decision':decision,'evidence_id':evidence_id,'source_count':len(sources),
                'reviewed_method':'derived-review','evidence_level':'D','automatic_redaction_verified':False,
                'source_read_bytes':consumed,'source_byte_budget':max_source_bytes}
