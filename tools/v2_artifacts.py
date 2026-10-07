"""Explicit candidate Artifact metadata registration; never moves payloads.

Phase-owned definitions are the first writable consumer. Other owners and
promotion require their own lifecycle contracts, not a different owner string.
Controller authority references are declarations, not independent permissions.
"""
import json
import re
import hashlib
from urllib.parse import quote,unquote
from v2_contracts import artifact_definition
from v2_state_store import StateConflict,_text,_json
from v2_definition_content import encode,decode,request_fingerprint


def artifact_ref(phase_id,local_id):
    """Canonical owner-qualified identity, independent of physical location."""
    return 'phase:'+quote(phase_id,safe='')+':'+local_id


def _relation_key(value,target):
    parts=target.split(':')
    if len(parts)==2 and parts[0] in {'artifact','archive'}:
        return artifact_ref(value['owner']['id'],parts[1])
    if len(parts)==3 and parts[0] in {'phase','archive'} and parts[1]:
        return artifact_ref(unquote(parts[1]),parts[2])
    return None


def _local_relations(value):
    result=[]
    for ordinal,relation in enumerate(value['relations']):
        parts=relation['target'].split(':');target=None;phase=''
        if len(parts)==2 and parts[0] in {'artifact','archive'}:target=parts[1]
        elif len(parts)==3 and parts[0] in {'phase','archive'} and parts[1]:phase,target=unquote(parts[1]),parts[2]
        if len(parts)==2 and parts[0]=='shared' and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',parts[1]):
            result.append((ordinal,relation['kind'],'shared:'+parts[1],''))
        elif target is not None and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',target):
            result.append((ordinal,relation['kind'],_relation_key(value,relation['target']),phase))
    return result


class Artifacts:
    def __init__(self,store,*,required_resource_root=None):
        self.store=store
        self.required_resource_root=required_resource_root

    def _resolve_id(self,project_id,identity):
        c=self.store.connection
        if identity.startswith('phase:'):
            parts=identity.split(':')
            if len(parts)!=3 or artifact_ref(unquote(parts[1]),parts[2])!=identity:
                raise ValueError('Artifact reference is not canonical')
            row=c.execute('SELECT artifact_id,phase_id,local_id FROM artifact_definition WHERE project_id=? AND artifact_id=?',(project_id,identity)).fetchone()
            if row is None:raise StateConflict('Unknown Artifact reference')
            if artifact_ref(row[1],row[2])!=row[0]:raise StateConflict('Artifact local identity projection differs')
            return row[0]
        rows=c.execute('SELECT artifact_id,phase_id,local_id FROM artifact_definition WHERE project_id=? AND local_id=? ORDER BY artifact_id LIMIT 2',
                       (project_id,identity)).fetchall()
        if len(rows)>1:raise StateConflict('Ambiguous Artifact ID; use the owner-qualified artifact_ref')
        if not rows:raise StateConflict('Unknown Artifact reference')
        if artifact_ref(rows[0][1],rows[0][2])!=rows[0][0]:raise StateConflict('Artifact local identity projection differs')
        return rows[0][0]

    def _relation_projection(self,project_id,max_artifacts):
        _text(project_id,'project_id')
        if type(max_artifacts) is not int or not 1<=max_artifacts<=10000:raise ValueError('Invalid projection rebuild budget')
        c=self.store.connection
        if not c.execute('SELECT 1 FROM project WHERE project_id=?',(project_id,)).fetchone():raise StateConflict('Unknown Project')
        rows=c.execute('SELECT artifact_id,phase_id,primary_role,protected_definition FROM artifact_definition WHERE project_id=? ORDER BY artifact_id LIMIT ?',
                       (project_id,max_artifacts+1)).fetchall()
        if len(rows)>max_artifacts:raise StateConflict('Artifact projection budget exceeded')
        expected=[]
        for identity,phase,role,protected in rows:
            value=artifact_definition(decode(protected,project_id,'artifact',identity,1,'definition'))
            if (artifact_ref(phase,value['artifact_id']),value['owner'],value['role'])!=(identity,{'kind':'PHASE','id':phase},role):
                raise StateConflict('Artifact row differs from its protected definition')
            expected.extend((project_id,identity,*edge) for edge in _local_relations(value))
        digest=hashlib.sha256(_json([project_id,rows]).encode('utf-8')).hexdigest()
        return digest,expected,len(rows)

    def relation_index_status(self,*,project_id,max_artifacts=1000):
        c=self.store.connection;own=not c.in_transaction
        if own:c.execute('BEGIN')
        try:
            digest,expected,count=self._relation_projection(project_id,max_artifacts)
            actual=c.execute('SELECT * FROM artifact_relation_index WHERE project_id=? ORDER BY source_id,ordinal LIMIT ?',(project_id,len(expected)+1)).fetchall()
            return {'project_id':project_id,'source_sha256':digest,'artifact_count':count,'expected_edges':len(expected),
                    'index_matches':actual==expected,'classification':'DERIVED_REBUILDABLE',
                    'scope':'artifact_relation_index','database_classification':'DURABLE','writes_performed':False,
                    'payload_read':False,'deletion_authorized':False}
        finally:
            if own:c.execute('ROLLBACK')

    def rebuild_relation_index(self,*,project_id,expected_source_sha256,request_id,authority_ref,max_artifacts=1000):
        for name,value in [('project_id',project_id),('expected_source_sha256',expected_source_sha256),('request_id',request_id),('authority_ref',authority_ref)]:_text(value,name)
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            fingerprint=request_fingerprint(c,project_id,[expected_source_sha256,authority_ref])
            prior=c.execute("SELECT details_json FROM execution_audit WHERE kind='ARTIFACT_INDEX_REBUILT' AND subject_id=?",(request_id,)).fetchone()
            if prior:
                record=json.loads(prior[0])
                if record['project_id']!=project_id or record['request_hash']!=fingerprint:raise StateConflict('Index rebuild request identity conflict')
                return {'decision':'REPLAY','historical_receipt':True,'payload_changed':False}
            digest,expected,count=self._relation_projection(project_id,max_artifacts)
            if digest!=expected_source_sha256:raise StateConflict('Artifact projection source changed; inspect again')
            c.execute('DELETE FROM artifact_relation_index WHERE project_id=?',(project_id,))
            c.executemany('INSERT INTO artifact_relation_index VALUES (?,?,?,?,?,?)',expected)
            protected=encode({'authority_ref':authority_ref},project_id,'artifact-index',request_id,1,'review')
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('ARTIFACT_INDEX_REBUILT',request_id,_json({'project_id':project_id,'request_hash':fingerprint,
                 'source_sha256':digest,'artifact_count':count,'edges':len(expected),'protected_review':protected})))
            return {'decision':'DERIVED_INDEX_REBUILT','edges':len(expected),'source_sha256':digest,'payload_changed':False,
                    'authoritative_definitions_changed':False,'authority_granted':False}

    def retire_shared(self,*,project_id,shared_id,request_id,review_ref,authority_ref):
        for name,value in [('project_id',project_id),('shared_id',shared_id),('request_id',request_id),
                           ('review_ref',review_ref),('authority_ref',authority_ref)]:
            _text(value,name)
            if len(value)>2048:raise ValueError('Shared retirement metadata exceeds its text budget')
        subject=_json([project_id,shared_id])
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            self._require_resource_root(project_id)
            fingerprint=request_fingerprint(c,project_id,[shared_id,review_ref,authority_ref])
            prior=c.execute("SELECT details_json FROM execution_audit WHERE kind='ARTIFACT_SHARED_RETIRE_REQUEST' AND subject_id=?",(request_id,)).fetchone()
            if prior:
                record=json.loads(prior[0])
                if record['subject']!=subject or record['request_hash']!=fingerprint:
                    raise StateConflict('Shared retirement request identity conflict')
                return {'decision':'REPLAY','historical_receipt':True,'payload_changed':False,'authority_granted':False}
            row=c.execute('SELECT state FROM artifact_shared WHERE project_id=? AND shared_id=?',(project_id,shared_id)).fetchone()
            if row!=('CURRENT',):raise StateConflict('Shared retirement requires the exact CURRENT binding')
            protected=encode({'review_ref':review_ref,'authority_ref':authority_ref},project_id,'artifact-shared-retirement',request_id,1,'review')
            c.execute("UPDATE artifact_shared SET state='RETIRED' WHERE project_id=? AND shared_id=?",(project_id,shared_id))
            event=c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('ARTIFACT_SHARED_RETIRED',subject,_json({'protected_review':protected,'request_id':request_id,'authority_assurance':'CONTROLLER_DECLARED'}))).lastrowid
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('ARTIFACT_SHARED_RETIRE_REQUEST',request_id,_json({'subject':subject,'request_hash':fingerprint,'retirement_sequence':event})))
            return {'decision':'SHARED_RETIRED','shared_id':shared_id,'retirement_sequence':event,
                    'payload_changed':False,'authority_granted':False,'verification_result':'NOT_RUN'}

    def verify_shared(self,*,project_id,shared_id,relation_audit_budget=100):
        from v2_acceptance import Acceptance
        from v2_evidence import BlobStore
        for name,value in [('project_id',project_id),('shared_id',shared_id)]:_text(value,name)
        c=self.store.connection;own=not c.in_transaction
        if own:c.execute('BEGIN')
        try:
            row=c.execute('SELECT artifact_id,task_id,acceptance_id,state FROM artifact_shared WHERE project_id=? AND shared_id=?',(project_id,shared_id)).fetchone()
            if row is None:raise StateConflict('Unknown Shared binding')
            self._require_resource_root(project_id)
            proof=Acceptance(self.store,BlobStore(self.store.path.parent/'blobs',readonly=True)).verify_task_completion(task_id=row[1])
            relations=self.audit_relations(project_id=project_id,max_artifacts=relation_audit_budget,root_artifact_id=row[0])
            current=(row[3]=='CURRENT' and proof['decision']=='CURRENT_EVIDENCE_VALID' and proof['acceptance_id']==row[2]
                     and relations['decision']=='REFERENCE_GRAPH_VALID')
            return {'project_id':project_id,'shared_id':shared_id,'artifact_id':row[0].rsplit(':',1)[-1],'artifact_ref':row[0],'declared_state':row[3],
                    'decision':'CURRENT_EVIDENCE_VALID' if current else 'NO_LONGER_PROVEN',
                    'task_proof':proof,'relation_audit':relations,'writes_performed':False,'authority_granted':False,
                    'independent_business_review_implied':False}
        finally:
            if own:c.execute('ROLLBACK')

    def _require_resource_root(self,project_id):
        if self.required_resource_root is not None:
            from pathlib import Path
            row=self.store.connection.execute('SELECT resource_root FROM project WHERE project_id=?',(project_id,)).fetchone()
            if row is None or Path(row[0]).resolve()!=Path(self.required_resource_root).resolve():
                raise PermissionError('Artifact resource root differs from Host policy')

    def promote(self,*,project_id,artifact_id,shared_id,purpose,scope,acceptance_id,evidence_id,operation_id,request_id,authority_ref,relation_audit_budget=100,supersedes_shared_id=None):
        from v2_acceptance import Acceptance
        from v2_evidence import BlobStore
        from v2_operation_inputs import operation_parameters
        for name,value in [('project_id',project_id),('artifact_id',artifact_id),('shared_id',shared_id),('purpose',purpose),
                           ('scope',scope),('acceptance_id',acceptance_id),('evidence_id',evidence_id),('operation_id',operation_id),
                           ('request_id',request_id),('authority_ref',authority_ref)]:
            _text(value,name)
            if len(value)>2048:raise ValueError('Shared metadata exceeds its text budget')
        if supersedes_shared_id is not None:
            _text(supersedes_shared_id,'supersedes_shared_id')
            if supersedes_shared_id==shared_id:raise ValueError('Replacement needs a new Shared identity')
        for identity in (shared_id,supersedes_shared_id):
            if identity is not None and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',identity):
                raise ValueError('Shared identity must be addressable by a typed reference')
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            self._require_resource_root(project_id)
            artifact_id=self._resolve_id(project_id,artifact_id)
            request_parts=[artifact_id,shared_id,purpose,scope,acceptance_id,evidence_id,operation_id,authority_ref]
            if supersedes_shared_id is not None:request_parts.append({'supersedes_shared_id':supersedes_shared_id})
            fingerprint=request_fingerprint(c,project_id,request_parts)
            old=c.execute('SELECT project_id,shared_id,request_hash FROM artifact_shared WHERE request_id=?',(request_id,)).fetchone()
            if old:
                if old!=(project_id,shared_id,fingerprint):raise StateConflict('Shared request identity conflict')
                return {'decision':'REPLAY','historical_receipt':True,'current_evidence_rechecked':False,'payload_changed':False}
            row=c.execute('SELECT phase_id,protected_definition FROM artifact_definition WHERE project_id=? AND artifact_id=?',(project_id,artifact_id)).fetchone()
            if row is None:raise StateConflict('Unknown Artifact')
            if c.execute('SELECT 1 FROM artifact_archive WHERE project_id=? AND artifact_id=?',(project_id,artifact_id)).fetchone():
                raise StateConflict('Archived Artifact cannot be promoted without explicit restoration')
            definition=artifact_definition(decode(row[1],project_id,'artifact',artifact_id,1,'definition'))
            locator=definition['locator']
            if locator['kind']!='PATH' or locator['scope']!='WORKSPACE' or definition['authority'] not in {'WORKSPACE','GENERATED'}:
                raise StateConflict('This promotion consumer requires a managed workspace file')
            owner=c.execute('SELECT project_id,revision,state FROM phase WHERE phase_id=?',(row[0],)).fetchone()
            if owner is None or owner[0]!=project_id or owner[2]!='ACTIVE':raise StateConflict('Promotion requires an active owning Phase')
            from v2_governance import checked_phase_plan
            checked_phase_plan(self.store,row[0],owner[1])
            accepted=c.execute('''SELECT a.task_id,a.task_revision,a.evidence_ids_json,a.valid FROM acceptance a
                JOIN task t ON t.task_id=a.task_id WHERE a.acceptance_id=? AND t.project_id=?''',(acceptance_id,project_id)).fetchone()
            if accepted is None or not accepted[3] or evidence_id not in json.loads(accepted[2]):
                raise StateConflict('Promotion requires selected current acceptance evidence')
            binding=c.execute('SELECT phase_id FROM phase_task WHERE task_id=? AND task_revision=?',accepted[:2]).fetchone()
            if binding!=(row[0],):raise StateConflict('Evidence Task does not belong to the Artifact owner')
            evidence=c.execute('SELECT task_id,task_revision,operation_id,result,method FROM evidence WHERE evidence_id=?',(evidence_id,)).fetchone()
            if evidence!=(*accepted[:2],operation_id,'PASS','managed-file-integrity'):
                raise StateConflict('Promotion requires fixed managed-file evidence for the exact Operation')
            operation=c.execute('SELECT o.task_id,o.task_revision,g.resource,g.effect FROM operation o JOIN execution_grant g ON g.grant_id=o.grant_id WHERE o.operation_id=?',(operation_id,)).fetchone()
            if operation!=(*accepted[:2],locator['value'],'read'):
                raise StateConflict('Promotion requires the exact Artifact read Operation')
            if operation_parameters(self.store,operation_id)!={'tool':'read-file','path':locator['value']}:
                raise StateConflict('Artifact read parameters differ')
            latest=c.execute('''SELECT o.operation_id FROM operation o JOIN execution_grant g ON g.grant_id=o.grant_id JOIN execution_audit a ON a.subject_id=o.operation_id
                WHERE o.task_id=? AND o.task_revision=? AND g.resource=? AND a.kind='INTENT_RECORDED'
                ORDER BY a.sequence DESC LIMIT 1''',(*accepted[:2],locator['value'])).fetchone()
            if latest!=(operation_id,):raise StateConflict('Artifact observation is not the current resource observation')
            observed=c.execute("SELECT details_json FROM execution_audit WHERE kind='ARTIFACT_PAYLOAD_OBSERVED' AND subject_id=? ORDER BY sequence DESC",(_json([project_id,artifact_id]),)).fetchall()
            observed=next((json.loads(item[0]) for item in observed if json.loads(item[0])['operation_id']==operation_id),None)
            if observed is None or observed['declared_digest_matches'] is False:raise StateConflict('Artifact content was not successfully observed')
            if self.audit_relations(project_id=project_id,max_artifacts=relation_audit_budget,root_artifact_id=artifact_id)['decision']!='REFERENCE_GRAPH_VALID':
                raise StateConflict('Artifact references are unresolved or audit budget is insufficient')
            proof=Acceptance(self.store,BlobStore(self.store.path.parent/'blobs',readonly=True)).verify_task_completion(task_id=accepted[0])
            if proof['decision']!='CURRENT_EVIDENCE_VALID' or proof['acceptance_id']!=acceptance_id:
                raise StateConflict('Promotion evidence is no longer current')
            # Preserve the established authority key: case-insensitive words,
            # collapsed whitespace. Keep original prose in protected metadata.
            normalized_purpose=' '.join(purpose.lower().split())
            normalized_scope=' '.join(scope.lower().split())
            identity=request_fingerprint(c,project_id,['shared-purpose-scope',normalized_purpose,normalized_scope])
            if supersedes_shared_id is not None:
                previous=c.execute('SELECT purpose_scope_hash,state FROM artifact_shared WHERE project_id=? AND shared_id=?',
                                   (project_id,supersedes_shared_id)).fetchone()
                if previous!=(identity,'CURRENT'):
                    raise StateConflict('Replacement requires the expected CURRENT binding for the same purpose/scope')
                # This update and the replacement insert are one transaction.
                # A later failure restores the original CURRENT binding.
                c.execute("UPDATE artifact_shared SET state='SUPERSEDED' WHERE project_id=? AND shared_id=? AND state='CURRENT'",
                          (project_id,supersedes_shared_id))
            if c.execute("SELECT 1 FROM artifact_shared WHERE project_id=? AND (shared_id=? OR (purpose_scope_hash=? AND state='CURRENT'))",(project_id,shared_id,identity)).fetchone():
                raise StateConflict('Shared identity or purpose/scope already has a current binding')
            protected=encode({'purpose':purpose,'scope':scope,'authority_ref':authority_ref},project_id,'artifact-shared',shared_id,1,'purpose-scope')
            c.execute('INSERT INTO artifact_shared VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (project_id,shared_id,artifact_id,identity,protected,accepted[0],acceptance_id,evidence_id,operation_id,'CURRENT',request_id,fingerprint))
            c.execute("UPDATE artifact_definition SET disposition='PROMOTE_SHARED' WHERE project_id=? AND artifact_id=?",(project_id,artifact_id))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('ARTIFACT_PROMOTED',_json([project_id,artifact_id]),_json({'shared_id':shared_id,'operation_id':operation_id,'acceptance_id':acceptance_id})))
            if supersedes_shared_id is not None:
                c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                    ('ARTIFACT_SHARED_SUPERSEDED',_json([project_id,supersedes_shared_id]),
                     _json({'replacement_shared_id':shared_id,'request_id':request_id,'artifact_id':artifact_id})))
            return {'decision':'SHARED_CURRENT_RECORDED','shared_id':shared_id,'current_evidence_rechecked':True,
                    'supersedes_shared_id':supersedes_shared_id,
                    'payload_changed':False,'authority_granted':False,'independent_business_review_implied':False}

    def inspect_payload(self,*,project_id,artifact_id,operation_id,actor,expected_request_hash,max_bytes=16777216):
        """Consume an explicitly prepared read Operation; never create a Grant."""
        for name,value in [('project_id',project_id),('artifact_id',artifact_id),('operation_id',operation_id),('actor',actor)]:_text(value,name)
        from v2_operation_inputs import operation_parameters
        from v2_local_host import LocalFileHost
        c=self.store.connection
        artifact_id=self._resolve_id(project_id,artifact_id)
        row=c.execute('SELECT protected_definition FROM artifact_definition WHERE project_id=? AND artifact_id=?',(project_id,artifact_id)).fetchone()
        if row is None:raise StateConflict('Unknown Artifact')
        value=artifact_definition(decode(row[0],project_id,'artifact',artifact_id,1,'definition'))
        locator=value['locator']
        if locator['kind']!='PATH' or locator['scope']!='WORKSPACE' or value['authority'] not in {'WORKSPACE','GENERATED'}:
            raise PermissionError('This consumer requires a workspace file; other authorities need their explicit adapters')
        operation=c.execute('''SELECT t.project_id,g.resource,g.effect,g.actor FROM operation o
            JOIN task t ON t.task_id=o.task_id JOIN execution_grant g ON g.grant_id=o.grant_id
            WHERE o.operation_id=?''',(operation_id,)).fetchone()
        if operation!=(project_id,locator['value'],'read',actor):
            raise PermissionError('Artifact inspection requires an exact same-project read Grant and actor')
        parameters=operation_parameters(self.store,operation_id,actor=actor)
        if parameters!={'tool':'read-file','path':locator['value']}:
            raise PermissionError('Read Operation does not target the Artifact locator')
        observed=LocalFileHost(self.store,required_resource_root=self.required_resource_root).read_file(
            operation_id=operation_id,actor=actor,expected_request_hash=expected_request_hash,max_bytes=max_bytes,max_characters=0)
        if observed['decision']!='READ':
            return {'decision':'NOT_REEXECUTED','operation_state':observed['operation_state'],
                    'current_content_verified':False,'payload_changed':False}
        declared=value['sha256']
        matches=None if declared is None else observed['sha256']==declared.lower()
        with self.store.transaction() as transaction:
            transaction.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('ARTIFACT_PAYLOAD_OBSERVED',_json([project_id,artifact_id]),_json({'operation_id':operation_id,
                 'sha256':observed['sha256'],'bytes':observed['bytes'],'declared_digest_matches':matches})))
        return {'decision':'PAYLOAD_DIGEST_MISMATCH' if matches is False else 'PAYLOAD_OBSERVED',
                'operation_id':operation_id,'observed_sha256':observed['sha256'],'bytes':observed['bytes'],
                'declared_digest_matches':matches,'payload_changed':False,'content_returned':False,
                'verification_scope':'BYTES_OBSERVED_BY_THIS_READ','task_accepted':False,'promotion_authorized':False}

    def audit_relations(self,*,project_id,max_artifacts=100,root_artifact_id=None,owner_phase_id=None):
        """Bounded explicit project graph audit, never payload/evidence verification."""
        _text(project_id,'project_id')
        if root_artifact_id is not None:_text(root_artifact_id,'root_artifact_id')
        if owner_phase_id is not None:
            _text(owner_phase_id,'owner_phase_id')
            if root_artifact_id is not None:raise ValueError('Select either a Phase or an Artifact root')
        if type(max_artifacts) is not int or not 1<=max_artifacts<=1000:raise ValueError('Invalid Artifact audit budget')
        c=self.store.connection;own=not c.in_transaction
        if own:c.execute('BEGIN')
        try:
            if not c.execute('SELECT 1 FROM project WHERE project_id=?',(project_id,)).fetchone():raise StateConflict('Unknown Project')
            if root_artifact_id is not None:root_artifact_id=self._resolve_id(project_id,root_artifact_id)
            base={'project_id':project_id,'payload_read':False,'writes_performed':False,'authority_granted':False,
                  'content_verified':False,'evidence_validity_verified':False,'max_artifacts':max_artifacts,
                  'scope':'PHASE_DEPENDENCY_CLOSURE' if owner_phase_id is not None else ('PROJECT' if root_artifact_id is None else 'DEPENDENCY_CLOSURE'),
                  'root_artifact_id':root_artifact_id,'owner_phase_id':owner_phase_id}
            if root_artifact_id is None and owner_phase_id is None:
                rows=c.execute('''SELECT artifact_id,phase_id,primary_role,protected_definition FROM artifact_definition
                    WHERE project_id=? ORDER BY artifact_id LIMIT ?''',(project_id,max_artifacts+1)).fetchall()
            else:
                rows=[];pending=[root_artifact_id];visited=set()
                if owner_phase_id is not None:
                    if not c.execute('SELECT 1 FROM phase WHERE project_id=? AND phase_id=?',(project_id,owner_phase_id)).fetchone():
                        raise StateConflict('Unknown Phase audit root')
                    pending=[row[0] for row in c.execute("SELECT artifact_id FROM artifact_definition WHERE project_id=? AND phase_id=? AND disposition!='ARCHIVE' ORDER BY artifact_id LIMIT ?",
                                                        (project_id,owner_phase_id,max_artifacts+1))]
                while pending:
                    identity=pending.pop()
                    if identity in visited:continue
                    if len(visited)>=max_artifacts:
                        return {**base,'decision':'AUDIT_INCOMPLETE','issues':[{'code':'ARTIFACT_BUDGET_EXCEEDED'}],'checked_artifacts':len(rows)}
                    visited.add(identity)
                    row=c.execute('''SELECT artifact_id,phase_id,primary_role,protected_definition FROM artifact_definition
                        WHERE project_id=? AND artifact_id=?''',(project_id,identity)).fetchone()
                    if row is None:
                        if identity==root_artifact_id:raise StateConflict('Unknown Artifact audit root')
                        continue
                    rows.append(row)
                    edges=c.execute('''SELECT ordinal,kind,target_id,target_phase FROM artifact_relation_index
                        WHERE project_id=? AND source_id=? ORDER BY ordinal''',(project_id,identity)).fetchall()
                    for edge in edges:
                        target=edge[2]
                        if target.startswith('shared:'):
                            binding=c.execute('SELECT artifact_id FROM artifact_shared WHERE project_id=? AND shared_id=?',
                                              (project_id,target[7:])).fetchone()
                            if binding is None:continue
                            target=binding[0]
                        if target not in visited:pending.append(target)
                    # A SUPERSEDED_BY declaration lives on the old node but its
                    # normalized edge starts at the target. Fetch these incoming
                    # declarations so directed cycles cannot disappear by scoping.
                    inverse=c.execute('''SELECT DISTINCT source_id FROM artifact_relation_index
                        WHERE project_id=? AND kind='SUPERSEDED_BY' AND (
                            (target_id=? AND target_phase IN ('',?)) OR
                            target_id IN (SELECT 'shared:' || shared_id FROM artifact_shared WHERE project_id=? AND artifact_id=?))
                        ORDER BY source_id LIMIT ?''',(project_id,identity,row[1],project_id,identity,max_artifacts+1)).fetchall()
                    if len(inverse)>max_artifacts:
                        return {**base,'decision':'AUDIT_INCOMPLETE','issues':[{'code':'ARTIFACT_BUDGET_EXCEEDED'}],'checked_artifacts':len(rows)}
                    pending.extend(item[0] for item in inverse if item[0] not in visited)
            if len(rows)>max_artifacts:
                return {**base,'decision':'AUDIT_INCOMPLETE','issues':[{'code':'ARTIFACT_BUDGET_EXCEEDED'}],'checked_artifacts':0}
            definitions={};owners={};issues=set()
            for identity,phase,role,protected in rows:
                value=artifact_definition(decode(protected,project_id,'artifact',identity,1,'definition'))
                if (artifact_ref(phase,value['artifact_id']),value['owner'],value['role'])!=(identity,{'kind':'PHASE','id':phase},role):
                    raise StateConflict('Artifact row differs from its protected definition')
                indexed=c.execute('SELECT ordinal,kind,target_id,target_phase FROM artifact_relation_index WHERE project_id=? AND source_id=? ORDER BY ordinal',(project_id,identity)).fetchall()
                if indexed!=_local_relations(value):raise StateConflict('Artifact relation index differs from its protected definition')
                definitions[identity]=value;owners[identity]=phase
            graph={identity:set() for identity in definitions}
            for identity,value in definitions.items():
                for relation in value['relations']:
                    target=relation['target'];kind=relation['kind'];parts=target.split(':')
                    other=None;resolved=False;category=None
                    if len(parts)==2 and parts[0]=='artifact':
                        category='artifact';other=_relation_key(value,target);resolved=other in definitions
                    elif len(parts)==2 and parts[0]=='shared':
                        category='artifact'
                        binding=c.execute('SELECT artifact_id FROM artifact_shared WHERE project_id=? AND shared_id=?',
                                          (project_id,parts[1])).fetchone()
                        if binding is not None:other=binding[0];resolved=other in definitions
                    elif len(parts) in {2,3} and parts[0]=='archive':
                        category='artifact';other=_relation_key(value,target)
                        resolved=other in definitions and bool(c.execute('SELECT 1 FROM artifact_archive WHERE project_id=? AND artifact_id=?',(project_id,other)).fetchone())
                    elif len(parts)==3 and parts[0]=='phase':
                        category='artifact';other=_relation_key(value,target);resolved=other in definitions and owners[other]==unquote(parts[1])
                    elif len(parts)==2 and parts[0]=='task':
                        category='task';resolved=bool(c.execute('SELECT 1 FROM task WHERE project_id=? AND task_id=?',(project_id,parts[1])).fetchone())
                    elif len(parts)==2 and parts[0]=='phase':
                        category='phase';resolved=bool(c.execute('SELECT 1 FROM phase WHERE project_id=? AND phase_id=?',(project_id,parts[1])).fetchone())
                    elif len(parts)==2 and parts[0]=='acceptance':
                        category='acceptance';resolved=bool(c.execute('''SELECT 1 FROM acceptance a JOIN task t ON t.task_id=a.task_id
                            WHERE t.project_id=? AND a.acceptance_id=?''',(project_id,parts[1])).fetchone())
                    if not resolved:
                        issues.add((identity,'TARGET_UNRESOLVED'));continue
                    if kind in {'MIRROR_OF','GENERATED_FROM','SUPERSEDES','SUPERSEDED_BY'}:
                        if category!='artifact':issues.add((identity,'TARGET_KIND_INVALID'));continue
                        if kind=='SUPERSEDED_BY':graph[other].add(identity)
                        else:graph[identity].add(other)
                if value['role']=='EVIDENCE':
                    evidence=value['role_contract']['evidence_id']
                    binding=c.execute('''SELECT e.task_id,e.task_revision FROM evidence e JOIN task t ON t.task_id=e.task_id
                        WHERE t.project_id=? AND e.evidence_id=?''',(project_id,evidence)).fetchone()
                    if binding is None:
                        issues.add((identity,'EVIDENCE_REFERENCE_UNRESOLVED'))
                    else:
                        target=value['role_contract']['target'].split(':');matches=False
                        if len(target)==2 and target[0]=='task':
                            matches=target[1]==binding[0]
                        elif len(target)==2 and target[0]=='phase':
                            matches=bool(c.execute('''SELECT 1 FROM phase_task WHERE task_id=? AND task_revision=?
                                AND phase_id=?''',(*binding,target[1])).fetchone())
                        elif len(target)==2 and target[0]=='acceptance':
                            receipt=c.execute('''SELECT evidence_ids_json FROM acceptance WHERE acceptance_id=?
                                AND task_id=? AND task_revision=?''',(target[1],*binding)).fetchone()
                            matches=receipt is not None and evidence in json.loads(receipt[0])
                        if not matches:issues.add((identity,'EVIDENCE_TARGET_BINDING_UNRESOLVED'))
            # Explicit stack avoids recursion failure on valid long chains.
            colors={}
            for root in graph:
                if colors.get(root):continue
                colors[root]=1;stack=[(root,iter(sorted(graph[root])))]
                while stack:
                    node,edges=stack[-1]
                    target=next(edges,None)
                    if target is None:colors[node]=2;stack.pop();continue
                    if colors.get(target)==1:issues.add((node,'RELATION_CYCLE'))
                    elif not colors.get(target):colors[target]=1;stack.append((target,iter(sorted(graph[target]))))
            ordered=sorted(issues)
            return {**base,'decision':'REFERENCE_GRAPH_VALID' if not issues else 'REFERENCE_GRAPH_UNRESOLVED',
                    'checked_artifacts':len(rows),'issue_count':len(ordered),
                    'issues':[{'artifact_id':definitions[identity]['artifact_id'],'artifact_ref':identity,'code':code} for identity,code in ordered[:100]],
                    'issues_truncated':len(ordered)>100}
        finally:
            if own:c.execute('ROLLBACK')

    def reconcile(self,*,project_id,artifact_id,phase_revision,expected_review_sequence,
                  disposition,request_id,review_ref,authority_ref,archive_reason=None):
        for name,value in [('project_id',project_id),('artifact_id',artifact_id),('request_id',request_id),
                           ('review_ref',review_ref),('authority_ref',authority_ref)]:_text(value,name)
        if type(phase_revision) is not int or phase_revision<1 or type(expected_review_sequence) is not int or expected_review_sequence<0:
            raise ValueError('Invalid Artifact review version')
        if not isinstance(disposition,str) or disposition not in {'KEEP_OWNED','UNRESOLVED','ARCHIVE'}:
            raise ValueError('Unsupported disposition; promotion and replacement require their dedicated consumer')
        if disposition=='ARCHIVE':
            _text(archive_reason,'archive_reason')
            if len(archive_reason)>2048:raise ValueError('Archive reason exceeds its text budget')
        elif archive_reason is not None:raise ValueError('Archive reason requires ARCHIVE disposition')
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            artifact_id=self._resolve_id(project_id,artifact_id)
            subject=_json([project_id,artifact_id])
            parts=[artifact_id,phase_revision,expected_review_sequence,disposition,review_ref,authority_ref]
            if archive_reason is not None:parts.append({'archive_reason':archive_reason})
            fingerprint=request_fingerprint(c,project_id,parts)
            prior=c.execute("SELECT sequence,details_json FROM execution_audit WHERE kind='ARTIFACT_REVIEW_REQUEST' AND subject_id=?",(request_id,)).fetchone()
            if prior:
                recorded=json.loads(prior[1])
                if recorded['request_hash']!=fingerprint or recorded['subject']!=subject:
                    raise StateConflict('Artifact review request identity conflict')
                return {'decision':'REPLAY','historical_receipt':True,'review_sequence':recorded['review_sequence'],
                        'payload_changed':False,'verification_result':'NOT_RUN'}
            row=c.execute('SELECT phase_id FROM artifact_definition WHERE project_id=? AND artifact_id=?',(project_id,artifact_id)).fetchone()
            if row is None:raise StateConflict('Unknown Artifact')
            if c.execute('SELECT 1 FROM artifact_archive WHERE project_id=? AND artifact_id=?',(project_id,artifact_id)).fetchone():
                raise StateConflict('Archived Artifact requires an explicit restoration consumer')
            if disposition=='ARCHIVE' and c.execute("SELECT 1 FROM artifact_shared WHERE project_id=? AND artifact_id=? AND state='CURRENT'",(project_id,artifact_id)).fetchone():
                raise StateConflict('Current Shared binding must be explicitly retired before archival')
            owner=c.execute('SELECT project_id,revision,state FROM phase WHERE phase_id=?',(row[0],)).fetchone()
            if owner!=(project_id,phase_revision,'ACTIVE'):raise StateConflict('Artifact review requires its current active owner')
            from v2_governance import checked_phase_plan
            checked_phase_plan(self.store,row[0],phase_revision)
            sequence=c.execute("SELECT coalesce(max(sequence),0) FROM execution_audit WHERE kind='ARTIFACT_DISPOSITION' AND subject_id=?",(subject,)).fetchone()[0]
            if sequence!=expected_review_sequence:raise StateConflict('Artifact disposition review changed')
            protected=encode({'review_ref':review_ref,'authority_ref':authority_ref,'archive_reason':archive_reason},project_id,'artifact-review',request_id,1,'review')
            event=c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('ARTIFACT_DISPOSITION',subject,_json({'disposition':disposition,'prior_sequence':sequence,
                  'phase_revision':phase_revision,'protected_review':protected,'authority_assurance':'CONTROLLER_DECLARED'}))).lastrowid
            c.execute('UPDATE artifact_definition SET disposition=? WHERE project_id=? AND artifact_id=?',(disposition,project_id,artifact_id))
            if disposition=='ARCHIVE':
                c.execute("INSERT INTO artifact_archive VALUES (?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",(project_id,artifact_id,event))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('ARTIFACT_REVIEW_REQUEST',request_id,_json({'request_hash':fingerprint,'subject':subject,'review_sequence':event})))
            return {'decision':'DISPOSITION_RECORDED','disposition':disposition,'review_sequence':event,
                    'payload_changed':False,'verification_result':'NOT_RUN','authority_granted':False}

    def _check_recovery_archive_proof(self,project_id,value,archive):
        """Bind archive bytes to current acceptance; never execute restore prose."""
        from v2_acceptance import Acceptance
        from v2_evidence import BlobStore
        from v2_operation_inputs import operation_parameters
        from v2_observation_content import read_reference
        self._require_resource_root(project_id)
        c=self.store.connection;locator=value['locator']
        if locator['kind']!='PATH' or locator['scope']!='WORKSPACE' or value['authority'] not in {'WORKSPACE','GENERATED'}:
            raise PermissionError('Recovery archive requires the workspace file adapter')
        accepted=c.execute('''SELECT a.task_id,a.task_revision,a.evidence_ids_json,a.valid FROM acceptance a
            JOIN task t ON t.task_id=a.task_id WHERE a.acceptance_id=? AND t.project_id=?''',
            (archive['acceptance_id'],project_id)).fetchone()
        if accepted is None or not accepted[3] or archive['evidence_id'] not in json.loads(accepted[2]):
            raise StateConflict('Recovery archive requires selected current acceptance evidence')
        if c.execute('SELECT phase_id FROM phase_task WHERE task_id=? AND task_revision=?',accepted[:2]).fetchone()!=(value['owner']['id'],):
            raise StateConflict('Recovery evidence Task differs from the original owner')
        evidence=c.execute('SELECT task_id,task_revision,operation_id,result,method FROM evidence WHERE evidence_id=?',
                           (archive['evidence_id'],)).fetchone()
        if evidence!=(*accepted[:2],archive['operation_id'],'PASS','managed-file-integrity'):
            raise StateConflict('Recovery archive requires fixed file evidence for the exact Operation')
        operation=c.execute('''SELECT o.task_id,o.task_revision,g.resource,g.effect FROM operation o
            JOIN execution_grant g ON g.grant_id=o.grant_id WHERE o.operation_id=?''',(archive['operation_id'],)).fetchone()
        if operation!=(*accepted[:2],locator['value'],'read') or operation_parameters(self.store,archive['operation_id'])!={'tool':'read-file','path':locator['value']}:
            raise StateConflict('Recovery archive requires the exact file read Operation')
        latest=c.execute('''SELECT o.operation_id FROM operation o JOIN execution_grant g ON g.grant_id=o.grant_id
            JOIN execution_audit a ON a.subject_id=o.operation_id WHERE o.task_id=? AND o.task_revision=?
            AND g.resource=? AND a.kind='INTENT_RECORDED' ORDER BY a.sequence DESC LIMIT 1''',
            (*accepted[:2],locator['value'])).fetchone()
        if latest!=(archive['operation_id'],):raise StateConflict('Recovery archive observation is not current')
        observations=c.execute("SELECT observation_id FROM operation_observation WHERE operation_id=? AND outcome='SUCCEEDED'",(archive['operation_id'],)).fetchall()
        matches=[re.fullmatch(r'local-read:sha256:([a-f0-9]{64}):bytes:(0|[1-9][0-9]*)',read_reference(self.store,row[0])) for row in observations]
        matches=[match for match in matches if match]
        if len(matches)!=1 or matches[0][1]!=value['sha256'].lower():
            raise StateConflict('Recovery archive definition digest differs from observed bytes')
        proof=Acceptance(self.store,BlobStore(self.store.path.parent/'blobs',readonly=True)).verify_task_completion(task_id=accepted[0])
        if proof['decision']!='CURRENT_EVIDENCE_VALID' or proof['acceptance_id']!=archive['acceptance_id']:
            raise StateConflict('Recovery archive evidence is no longer current')

    def register(self,*,project_id,phase_revision,definition,request_id,authority_ref,legacy_source=None,archive=None,run_origin=None):
        for name,value in [('project_id',project_id),('request_id',request_id),('authority_ref',authority_ref)]:_text(value,name)
        if type(phase_revision) is not int or phase_revision<1:raise ValueError('Invalid Phase revision')
        value=artifact_definition(definition)
        if run_origin is not None:
            if not isinstance(run_origin,dict) or set(run_origin)!={'run_id','checkpoint_id'}:
                raise ValueError('Artifact Run origin requires an exact Run and Checkpoint')
            for key,item in run_origin.items():
                _text(item,key)
                if len(item)>2048:raise ValueError('Artifact Run origin exceeds its text budget')
            if legacy_source is not None:
                raise ValueError('Use historical Session mapping or native Run origin, not both')
        if archive is not None:
            if not isinstance(archive,dict) or set(archive)!={'reason','acceptance_id','evidence_id','operation_id'}:
                raise ValueError('Recovery archive requires a reason and exact acceptance, evidence and Operation')
            for key,item in archive.items():
                _text(item,key)
                if len(item)>2048 or item.strip().lower() in {'n/a','na','none','null','-','tbd','tbc'}:
                    raise ValueError('Recovery archive metadata requires concrete bounded text')
            if value['role']!='RECOVERY' or value['mode']!='FROZEN':
                raise ValueError('Direct archive registration requires a FROZEN RECOVERY definition')
        if legacy_source is not None:
            if not isinstance(legacy_source,dict) or set(legacy_source)!={'source_role','source_id','row_number','source_sha256','review_ref'}:
                raise ValueError('Legacy Artifact adoption requires an exact source row, digest and review')
            for key in ('source_role','source_id','source_sha256','review_ref'):
                _text(legacy_source[key],key)
                if len(legacy_source[key])>2048:raise ValueError('Legacy adoption metadata exceeds its budget')
            if type(legacy_source['row_number']) is not int or not 1<=legacy_source['row_number']<2**63:
                raise ValueError('Invalid legacy Artifact row number')
            if not re.fullmatch('[0-9a-fA-F]{64}',legacy_source['source_sha256']):raise ValueError('Invalid legacy source digest')
        if value['owner']['kind']!='PHASE':
            raise StateConflict('This registration consumer requires a Phase owner; other owner lifecycles are not implemented')
        phase_id=value['owner']['id'];identity=artifact_ref(phase_id,value['artifact_id'])
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            request_parts=[phase_revision,value,authority_ref]
            if legacy_source is not None:request_parts.append(legacy_source)
            if archive is not None:request_parts.append({'archive':archive})
            if run_origin is not None:request_parts.append({'run_origin':run_origin})
            fingerprint=request_fingerprint(c,project_id,request_parts)
            prior=c.execute('SELECT project_id,artifact_id,request_hash FROM artifact_definition WHERE request_id=?',(request_id,)).fetchone()
            if prior:
                if prior!=(project_id,identity,fingerprint):raise StateConflict('Artifact request identity conflict')
                return {'decision':'REPLAY','artifact_id':value['artifact_id'],'artifact_ref':identity,'historical_receipt':True,'current_evidence_rechecked':False,'payload_changed':False,'authority_granted':False}
            owner=c.execute('SELECT project_id,revision,state FROM phase WHERE phase_id=?',(phase_id,)).fetchone()
            if owner!=(project_id,phase_revision,'ACTIVE'):raise StateConflict('Artifact owner must be the current active Phase of this Project')
            from v2_governance import checked_phase_plan
            checked_phase_plan(self.store,phase_id,phase_revision)
            if c.execute('SELECT 1 FROM artifact_definition WHERE project_id=? AND artifact_id=?',(project_id,identity)).fetchone():
                raise StateConflict('Artifact identity already registered')
            if archive is not None:self._check_recovery_archive_proof(project_id,value,archive)
            origin=None
            if run_origin is not None:
                run=c.execute('''SELECT r.task_id,r.task_revision,r.checkpoint_id,t.project_id,t.revision
                    FROM execution_run r JOIN task t ON t.task_id=r.task_id WHERE r.run_id=?''',(run_origin['run_id'],)).fetchone()
                if run is None or run[3]!=project_id or run[1]!=run[4] or run[2]!=run_origin['checkpoint_id']:
                    raise StateConflict('Artifact origin requires the exact Run current Checkpoint and Task revision')
                if c.execute('SELECT phase_id,phase_revision FROM phase_task WHERE task_id=? AND task_revision=?',run[:2]).fetchone()!=(phase_id,phase_revision):
                    raise StateConflict('Artifact Run origin differs from its owning Phase')
                from v2_checkpoint_content import checkpoint_row
                checkpoint=checkpoint_row(c,c.execute('SELECT * FROM checkpoint WHERE checkpoint_id=? AND run_id=?',
                    (run_origin['checkpoint_id'],run_origin['run_id'])).fetchone())
                if checkpoint[2]!=run[1]:raise StateConflict('Artifact origin Checkpoint is missing or stale')
                origin={**run_origin,'task_id':run[0],'task_revision':run[1],'phase_id':phase_id,'phase_revision':phase_revision}
            provenance=None
            if legacy_source is not None:
                from v2_migration import legacy_artifact_context
                source_key=request_fingerprint(c,project_id,['legacy-artifact',legacy_source['source_role'],legacy_source['source_id'],legacy_source['row_number']])
                if c.execute("SELECT 1 FROM execution_audit WHERE kind='LEGACY_ARTIFACT_ADOPTED' AND subject_id=?",(source_key,)).fetchone():
                    raise StateConflict('Historical Artifact row already has an explicit native mapping')
                history=legacy_artifact_context(self.store,project_id=project_id,source_role=legacy_source['source_role'],
                    source_id=legacy_source['source_id'],after_row=legacy_source['row_number']-1,limit=1,max_bytes=1048576)
                if (history['source_sha256'].lower()!=legacy_source['source_sha256'].lower() or len(history['rows'])!=1 or
                    history['rows'][0]['row_number']!=legacy_source['row_number'] or not history['rows'][0]['identity_valid']):
                    raise StateConflict('Historical Artifact source row is missing, ambiguous or changed')
                provenance=encode({'source':legacy_source,'original':history['rows'][0],
                                   'session_mapping':history['session_mapping']},project_id,'artifact-legacy',identity,1,'provenance')
            # Registration preserves a proposal and does not assert physical
            # identity, target validity, PASS, Shared CURRENT or delete rights.
            protected=encode(value,project_id,'artifact',identity,1,'definition')
            c.execute('INSERT INTO artifact_definition VALUES (?,?,?,?,?,?,?,?,?,?)',
                (project_id,identity,phase_id,phase_revision,value['role'],protected,request_id,fingerprint,'UNRESOLVED',value['artifact_id']))
            c.executemany('INSERT INTO artifact_relation_index VALUES (?,?,?,?,?,?)',
                [(project_id,identity,*edge) for edge in _local_relations(value)])
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('ARTIFACT_REGISTERED',identity,_json({'project_id':project_id,'phase_id':phase_id,'request_id':request_id,
                 'authority_assurance':'CONTROLLER_DECLARED','payload_observed':False})))
            if origin is not None:
                protected_origin=encode(origin,project_id,'artifact-run-origin',identity,1,'origin')
                c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                    ('ARTIFACT_RUN_ORIGIN',_json([project_id,identity]),_json({'protected_origin':protected_origin})))
            if provenance is not None:
                c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                    ('LEGACY_ARTIFACT_ADOPTED',source_key,_json({'project_id':project_id,'artifact_id':identity,
                     'protected_provenance':provenance,'historical_acceptance_inherited':False})))
            if archive is not None:
                if self.audit_relations(project_id=project_id,root_artifact_id=identity)['decision']!='REFERENCE_GRAPH_VALID':
                    raise StateConflict('Recovery archive references are unresolved or exceed the audit budget')
                protected_archive=encode({'archive':archive,'authority_ref':authority_ref,'original_owner':value['owner']},
                                         project_id,'artifact-archive',identity,1,'provenance')
                event=c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                    ('ARTIFACT_DISPOSITION',_json([project_id,identity]),_json({'disposition':'ARCHIVE','prior_sequence':0,
                     'phase_revision':phase_revision,'protected_provenance':protected_archive,
                     'verification_scope':'CURRENT_MANAGED_FILE_BYTES','restore_executed':False}))).lastrowid
                c.execute("UPDATE artifact_definition SET disposition='ARCHIVE' WHERE project_id=? AND artifact_id=?",(project_id,identity))
                c.execute("INSERT INTO artifact_archive VALUES (?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",(project_id,identity,event))
                return {'decision':'RECOVERY_ARCHIVE_REGISTERED','artifact_id':value['artifact_id'],'artifact_ref':identity,'disposition':'ARCHIVE',
                        'review_sequence':event,'current_evidence_rechecked':True,'verification_scope':'CURRENT_MANAGED_FILE_BYTES',
                        'restore_executed':False,'restore_readiness_proven':False,'payload_changed':False,'authority_granted':False}
            return {'decision':'REGISTERED_UNVERIFIED','artifact_id':value['artifact_id'],'artifact_ref':identity,'disposition':'UNRESOLVED',
                    'payload_changed':False,'authority_granted':False,'physical_locator_verified':False}

    def recovery_handoff(self,*,task_id,task_revision):
        _text(task_id,'task_id')
        if type(task_revision) is not int or task_revision<1:raise ValueError('Invalid handoff Task revision')
        c=self.store.connection
        task=c.execute('SELECT project_id,revision FROM task WHERE task_id=?',(task_id,)).fetchone()
        if task is None or task[1]!=task_revision:raise StateConflict('Handoff requires current Task revision')
        subject=_json([task[0],task_id,task_revision])
        row=c.execute("SELECT sequence,details_json FROM execution_audit WHERE kind='ARTIFACT_RECOVERY_HANDOFF' AND subject_id=? ORDER BY sequence DESC LIMIT 1",(subject,)).fetchone()
        if row is None:return {'decision':'NONE','handoff_sequence':0}
        consumed=c.execute("SELECT 1 FROM execution_audit WHERE kind='ARTIFACT_RECOVERY_HANDOFF_CONSUMED' AND subject_id=?",(str(row[0]),)).fetchone()
        if consumed:return {'decision':'NONE','handoff_sequence':0}
        value=decode(json.loads(row[1])['protected_handoff'],task[0],'recovery-handoff',subject,task_revision,'handoff')
        return {'decision':'SUCCESSOR_REVIEW_REQUIRED','handoff_sequence':row[0],
                'source_run_id':value['source_run_id'],'checkpoint_id':value['binding']['checkpoint_id'],
                'required_count':len(value['binding']['artifact_refs']),'epoch':value['epoch'],'execution_authorized':False}

    def stage_recovery_handoffs(self,*,task_actions,epoch):
        """Internal restore-review transaction: retain obligations before closing Runs."""
        c=self.store.connection
        if not c.in_transaction:raise RuntimeError('Handoff staging requires recovery transaction')
        for action in task_actions:
            task_id,revision=action['task_id'],action['revision']
            task=c.execute('SELECT project_id FROM task WHERE task_id=?',(task_id,)).fetchone()
            subject=_json([task[0],task_id,revision])
            current=c.execute("SELECT run_id FROM execution_run WHERE task_id=? AND task_revision=? AND state<>'CLOSED'",(task_id,revision)).fetchone()
            value=None
            if current:
                run,sequence,binding=self._recovery_binding(current[0])
                if binding is not None:
                    if binding['checkpoint_id']!=run[3]:raise StateConflict('Restored checkpoint binding differs')
                    if binding['artifact_refs']:
                        value={'source_run_id':current[0],'binding_sequence':sequence,'binding':binding,'epoch':epoch}
            if value is None:
                pending=self.recovery_handoff(task_id=task_id,task_revision=revision)
                if pending['decision']!='NONE':
                    row=c.execute('SELECT details_json FROM execution_audit WHERE sequence=?',(pending['handoff_sequence'],)).fetchone()
                    value=decode(json.loads(row[0])['protected_handoff'],task[0],'recovery-handoff',subject,revision,'handoff')
                    value={**value,'epoch':epoch,'previous_handoff_sequence':pending['handoff_sequence']}
            if value is not None:
                protected=encode(value,task[0],'recovery-handoff',subject,revision,'handoff')
                c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                          ('ARTIFACT_RECOVERY_HANDOFF',subject,_json({'protected_handoff':protected})))

    def recover_successor(self,*,task_id,task_revision,expected_handoff_sequence,run_id,checkpoint_id,
                          host,native_id,actor,request_id,review_ref,authority_ref):
        from v2_checkpoint_content import checkpoint_row
        from v2_governance import require_task_phase
        for name,value in [('task_id',task_id),('run_id',run_id),('checkpoint_id',checkpoint_id),('host',host),
                           ('native_id',native_id),('actor',actor),('request_id',request_id),('review_ref',review_ref),('authority_ref',authority_ref)]:_text(value,name)
        if type(task_revision) is not int or task_revision<1 or type(expected_handoff_sequence) is not int or expected_handoff_sequence<1:
            raise ValueError('Explicit Task and handoff revisions required')
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            task=self.store.task(task_id)
            if task is None or task['revision']!=task_revision:raise StateConflict('Successor Task revision differs')
            project=task['project_id'];subject=_json([project,task_id,task_revision])
            fingerprint=request_fingerprint(c,project,[task_id,task_revision,expected_handoff_sequence,run_id,checkpoint_id,host,native_id,actor,review_ref,authority_ref])
            prior=c.execute("SELECT details_json FROM execution_audit WHERE kind='ARTIFACT_RECOVERY_SUCCESSOR_REQUEST' AND subject_id=?",(request_id,)).fetchone()
            if prior:
                saved=json.loads(prior[0])
                if saved['request_hash']!=fingerprint:raise StateConflict('Successor request conflict')
                return {**saved['receipt'],'historical_receipt':True}
            if task['status'] not in {'READY','PAUSED'}:raise StateConflict('Successor requires reviewed READY or PAUSED Task')
            require_task_phase(self.store,task_id)
            self._require_resource_root(project)
            pending=self.recovery_handoff(task_id=task_id,task_revision=task_revision)
            epoch=c.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]
            if pending['handoff_sequence']!=expected_handoff_sequence or pending.get('epoch')!=epoch:
                raise StateConflict('Recovery handoff is stale or consumed')
            raw=c.execute('SELECT details_json FROM execution_audit WHERE sequence=?',(expected_handoff_sequence,)).fetchone()
            value=decode(json.loads(raw[0])['protected_handoff'],project,'recovery-handoff',subject,task_revision,'handoff')
            old=value['binding']
            if old['task_id']!=task_id or old['task_revision']!=task_revision:raise StateConflict('Inherited Task identity differs')
            source=c.execute('SELECT * FROM checkpoint WHERE checkpoint_id=? AND run_id=?',(old['checkpoint_id'],value['source_run_id'])).fetchone()
            source=checkpoint_row(c,source)
            c.execute("INSERT INTO execution_run VALUES (?,?,?,?,?,?,'PAUSED',?)",(run_id,task_id,task_revision,host,native_id,actor,checkpoint_id))
            c.execute('INSERT INTO checkpoint VALUES (?,?,?,?,?,?)',checkpoint_row(c,(checkpoint_id,run_id,task_revision,source[3],source[4],source[5]),protect=True))
            binding={**old,'checkpoint_id':checkpoint_id,'predecessor_run_id':value['source_run_id'],
                     'handoff_sequence':expected_handoff_sequence,'review_ref':review_ref,'authority_ref':authority_ref}
            protected=encode(binding,project,'checkpoint-artifacts',run_id,task_revision,'binding')
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('CHECKPOINT_ARTIFACT_BINDING',_json([project,run_id]),_json({'protected_binding':protected})))
            c.execute("UPDATE task SET status='PAUSED' WHERE task_id=?",(task_id,))
            receipt={'decision':'RECOVERY_SUCCESSOR_PAUSED','run_id':run_id,'checkpoint_id':checkpoint_id,
                     'required_count':len(binding['artifact_refs']),'handoff_sequence':expected_handoff_sequence,
                     'execution_authorized':False,'host_launched':False,'references_revalidated':False}
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('ARTIFACT_RECOVERY_HANDOFF_CONSUMED',str(expected_handoff_sequence),_json({'successor_run_id':run_id})))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('ARTIFACT_RECOVERY_SUCCESSOR_REQUEST',request_id,_json({'request_hash':fingerprint,'receipt':receipt})))
            return receipt

    def dispatch_recovery_source(self,*,run_id,task_id,task_revision):
        c=self.store.connection
        run,sequence,value=self._recovery_binding(run_id)
        if run[1]!=task_id or run[2]!=task_revision or run[2]!=run[5] or run[4]!='PAUSED' or run[3] is None:
            raise StateConflict('Dispatch requires the exact current paused checkpoint')
        from v2_checkpoint_content import checkpoint_row
        checkpoint=checkpoint_row(c,c.execute('SELECT * FROM checkpoint WHERE checkpoint_id=? AND run_id=?',(run[3],run_id)).fetchone())
        if json.loads(checkpoint[5]):raise StateConflict('Recovery checkpoint has unresolved effects')
        host=c.execute('SELECT task_id,task_revision,epoch,state,launch_committed,quiesced FROM host_dispatch WHERE run_id=?',(run_id,)).fetchone()
        if host is not None:
            epoch=c.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]
            if host!=(task_id,task_revision,epoch,'EXITED',1,1):
                raise StateConflict('Paused source Host must be observed quiesced in the current epoch')
        else:
            if value is None or 'handoff_sequence' not in value:
                raise StateConflict('Controller successor requires reviewed recovery provenance')
            receipt=c.execute("SELECT details_json FROM execution_audit WHERE kind='ARTIFACT_RECOVERY_HANDOFF_CONSUMED' AND subject_id=?",
                              (str(value['handoff_sequence']),)).fetchone()
            if receipt is None or json.loads(receipt[0]).get('successor_run_id')!=run_id:
                raise StateConflict('Recovery successor provenance differs')
        proof=self.verify_recovery_binding(run_id=run_id,checkpoint_id=run[3])
        if proof['decision'] not in ({'NOT_ENROLLED'} if value is None else {'BOUND_REFERENCES_CURRENT'}):
            raise StateConflict('Recovery source references need controller review')
        return run,sequence,value

    def dispatch_recovery_fingerprint(self,*,run_id,task_id,task_revision):
        run,_,_=self.dispatch_recovery_source(run_id=run_id,task_id=task_id,task_revision=task_revision)
        checkpoint=self.store.connection.execute('SELECT * FROM checkpoint WHERE checkpoint_id=? AND run_id=?',(run[3],run_id)).fetchone()
        return request_fingerprint(self.store.connection,run[0],[run_id,checkpoint])

    def transfer_recovery_to_host(self,*,source_run_id,target_run_id):
        """Called inside launch after validation; no Host I/O occurs here."""
        from v2_checkpoint_content import checkpoint_row
        c=self.store.connection
        if not c.in_transaction:raise RuntimeError('Transfer requires launch transaction')
        source,sequence,value=self._recovery_binding(source_run_id)
        target=c.execute('SELECT task_id,task_revision FROM execution_run WHERE run_id=?',(target_run_id,)).fetchone()
        if target!=(source[1],source[2]):raise StateConflict('Host recovery transfer identity differs')
        checkpoint=checkpoint_row(c,c.execute('SELECT * FROM checkpoint WHERE checkpoint_id=? AND run_id=?',(source[3],source_run_id)).fetchone())
        identity='host-recovery-'+hashlib.sha256(_json([target_run_id,source_run_id,source[3]]).encode()).hexdigest()
        c.execute('INSERT INTO checkpoint VALUES (?,?,?,?,?,?)',checkpoint_row(c,(identity,target_run_id,source[2],checkpoint[3],checkpoint[4],checkpoint[5]),protect=True))
        c.execute('UPDATE execution_run SET checkpoint_id=? WHERE run_id=?',(identity,target_run_id))
        c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
            ('HOST_CHECKPOINT_TRANSFER',target_run_id,_json({'source_run_id':source_run_id,'source_checkpoint_id':source[3],'checkpoint_id':identity})))
        if value is None:return
        value={**value,'checkpoint_id':identity,'predecessor_run_id':source_run_id,'previous_sequence':sequence}
        protected=encode(value,source[0],'checkpoint-artifacts',target_run_id,source[2],'binding')
        c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
            ('CHECKPOINT_ARTIFACT_BINDING',_json([source[0],target_run_id]),_json({'protected_binding':protected})))

    def _recovery_binding(self,run_id):
        c=self.store.connection
        run=c.execute('''SELECT t.project_id,r.task_id,r.task_revision,r.checkpoint_id,r.state,t.revision
            FROM execution_run r JOIN task t ON t.task_id=r.task_id WHERE r.run_id=?''',(run_id,)).fetchone()
        if run is None:raise StateConflict('Unknown recovery Run')
        row=c.execute("SELECT sequence,details_json FROM execution_audit WHERE kind='CHECKPOINT_ARTIFACT_BINDING' AND subject_id=? ORDER BY sequence DESC LIMIT 1",
                      (_json([run[0],run_id]),)).fetchone()
        if row is None:return run,0,None
        value=decode(json.loads(row[1])['protected_binding'],run[0],'checkpoint-artifacts',run_id,run[2],'binding')
        if value['task_id']!=run[1] or value['task_revision']!=run[2]:raise StateConflict('Recovery binding Task differs')
        return run,row[0],value

    def _recovery_snapshot(self,project,refs):
        result=[];c=self.store.connection
        for identity in refs:
            row=c.execute('SELECT protected_definition,disposition FROM artifact_definition WHERE project_id=? AND artifact_id=?',
                          (project,identity)).fetchone()
            if row is None:raise StateConflict('Required recovery Artifact is missing')
            seq=c.execute("SELECT coalesce(max(sequence),0) FROM execution_audit WHERE kind='ARTIFACT_DISPOSITION' AND subject_id=?",
                          (_json([project,identity]),)).fetchone()[0]
            result.append({'artifact_ref':identity,'definition_sha256':hashlib.sha256(row[0].encode()).hexdigest(),
                           'disposition':row[1],'review_sequence':seq})
        return result

    def bind_recovery(self,*,run_id,checkpoint_id,artifact_refs,expected_binding_sequence,request_id,review_ref,authority_ref,max_artifacts=100):
        for name,value in [('run_id',run_id),('checkpoint_id',checkpoint_id),('request_id',request_id),
                           ('review_ref',review_ref),('authority_ref',authority_ref)]:_text(value,name)
        if type(expected_binding_sequence) is not int or expected_binding_sequence<0:raise ValueError('Invalid binding revision')
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            run,sequence,previous=self._recovery_binding(run_id)
            fingerprint=request_fingerprint(c,run[0],[run_id,checkpoint_id,artifact_refs,expected_binding_sequence,review_ref,authority_ref,max_artifacts])
            prior=c.execute("SELECT details_json FROM execution_audit WHERE kind='CHECKPOINT_ARTIFACT_REQUEST' AND subject_id=?",(request_id,)).fetchone()
            if prior:
                value=json.loads(prior[0])
                if value['request_hash']!=fingerprint:raise StateConflict('Recovery binding request conflict')
                return {'decision':'REPLAY','binding_sequence':value['binding_sequence'],'historical_receipt':True,'current_references_rechecked':False}
            if run[4] not in {'PAUSED','PAUSE_REQUESTED'} or run[3]!=checkpoint_id or sequence!=expected_binding_sequence:
                raise StateConflict('Binding requires the exact paused checkpoint and current selection revision')
            report=self.recovery_context(run_id=run_id,checkpoint_id=checkpoint_id,artifact_refs=artifact_refs,max_artifacts=max_artifacts)
            if report['decision']!='SELECTED_REFERENCES_REVIEWED':raise StateConflict('Required recovery references are not reviewed')
            self._require_resource_root(run[0])
            value={'task_id':run[1],'task_revision':run[2],'checkpoint_id':checkpoint_id,'artifact_refs':artifact_refs,
                   'snapshots':self._recovery_snapshot(run[0],artifact_refs),'max_artifacts':max_artifacts,
                   'review_ref':review_ref,'authority_ref':authority_ref,'previous_sequence':sequence}
            if previous is not None:
                for key in ('handoff_sequence','predecessor_run_id'):
                    if key in previous:value[key]=previous[key]
            protected=encode(value,run[0],'checkpoint-artifacts',run_id,run[2],'binding')
            new=c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('CHECKPOINT_ARTIFACT_BINDING',_json([run[0],run_id]),_json({'protected_binding':protected}))).lastrowid
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('CHECKPOINT_ARTIFACT_REQUEST',request_id,_json({'request_hash':fingerprint,'binding_sequence':new})))
            return {'decision':'RECOVERY_REFERENCES_BOUND','binding_sequence':new,'required_count':len(artifact_refs),
                    'execution_authorized':False,'payload_verified':False}

    def verify_recovery_binding(self,*,run_id,checkpoint_id):
        c=self.store.connection;own=not c.in_transaction
        if own:c.execute('BEGIN')
        try:
            run,sequence,value=self._recovery_binding(run_id)
            if run[3]!=checkpoint_id or run[2]!=run[5] or run[4]=='CLOSED':raise StateConflict('Recovery binding is not current')
            if value is None:return {'decision':'NOT_ENROLLED','binding_sequence':0,'required_count':0,'execution_authorized':False}
            if value['checkpoint_id']!=checkpoint_id:raise StateConflict('Required references belong to a different checkpoint')
            invalid={'decision':'REVIEW_REQUIRED','binding_sequence':sequence,'required_count':len(value['artifact_refs']),
                     'execution_authorized':False,'payload_verified':False}
            try:
                if value['snapshots']!=self._recovery_snapshot(run[0],value['artifact_refs']):
                    return {**invalid,'reason':'SELECTED_ARTIFACT_CHANGED'}
                report=self.recovery_context(run_id=run_id,checkpoint_id=checkpoint_id,artifact_refs=value['artifact_refs'],max_artifacts=value['max_artifacts'])
                if report['decision']!='SELECTED_REFERENCES_REVIEWED':return {**invalid,'reason':'REFERENCE_CLOSURE_UNAVAILABLE'}
            except StateConflict:
                return {**invalid,'reason':'REFERENCE_CLOSURE_UNAVAILABLE'}
            return {'decision':'BOUND_REFERENCES_CURRENT','binding_sequence':sequence,'required_count':len(value['artifact_refs']),
                    'execution_authorized':False,'payload_verified':False,'references':report}
        finally:
            if own:c.execute('ROLLBACK')

    def carry_recovery_binding(self,*,run_id,previous_checkpoint_id,checkpoint_id):
        """Internal checkpoint transaction hook; preserves pins, including stale ones."""
        c=self.store.connection
        if not c.in_transaction:raise RuntimeError('Checkpoint carry requires one transaction')
        run,sequence,value=self._recovery_binding(run_id)
        if value is None:return
        if value['checkpoint_id']!=previous_checkpoint_id or run[3]!=checkpoint_id:
            raise StateConflict('Recovery selection carry identity differs')
        value={**value,'checkpoint_id':checkpoint_id,'previous_sequence':sequence}
        protected=encode(value,run[0],'checkpoint-artifacts',run_id,run[2],'binding')
        c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
            ('CHECKPOINT_ARTIFACT_BINDING',_json([run[0],run_id]),_json({'protected_binding':protected,'carried_from':sequence})))

    def recovery_context(self,*,run_id,checkpoint_id,artifact_refs,max_artifacts=100):
        """Inspect an explicit controller selection against the exact current checkpoint.

        This does not enroll persistent dependencies or authorize resume/payload access.
        """
        from v2_checkpoint_content import checkpoint_row
        for name,value in [('run_id',run_id),('checkpoint_id',checkpoint_id)]:_text(value,name)
        if (not isinstance(artifact_refs,list) or len(artifact_refs)>20 or
                any(not isinstance(r,str) or not r.startswith('phase:') or len(r)>8192 for r in artifact_refs) or
                len(set(artifact_refs))!=len(artifact_refs)):
            raise ValueError('Expected at most 20 distinct owner-qualified Artifact references')
        if type(max_artifacts) is not int or not 1<=max_artifacts<=1000:
            raise ValueError('Invalid recovery graph budget')
        c=self.store.connection;own=not c.in_transaction
        if own:c.execute('BEGIN')
        try:
            run=c.execute('''SELECT t.project_id,r.task_id,r.task_revision,t.revision,r.state,r.checkpoint_id
                FROM execution_run r JOIN task t ON t.task_id=r.task_id WHERE r.run_id=?''',(run_id,)).fetchone()
            if (run is None or run[2]!=run[3] or run[4]=='CLOSED' or run[5]!=checkpoint_id):
                raise StateConflict('Recovery requires the exact current Run/checkpoint')
            checkpoint_row(c,c.execute('SELECT * FROM checkpoint WHERE checkpoint_id=? AND run_id=?',
                                        (checkpoint_id,run_id)).fetchone())
            project=run[0];items=[];remaining=max_artifacts;complete=True
            for reference in artifact_refs:
                identity=self._resolve_id(project,reference)
                row=c.execute('SELECT phase_id,primary_role,disposition FROM artifact_definition WHERE project_id=? AND artifact_id=?',
                              (project,identity)).fetchone()
                if remaining:
                    audit=self.audit_relations(project_id=project,root_artifact_id=identity,max_artifacts=remaining)
                    remaining-=audit['checked_artifacts']
                    valid=audit['decision']=='REFERENCE_GRAPH_VALID'
                    if not valid:remaining=0
                else:
                    audit={'decision':'NOT_CHECKED','reason':'RECOVERY_GRAPH_BUDGET_EXHAUSTED'};valid=False
                complete=complete and valid and row[2]!='UNRESOLVED'
                items.append({'artifact_ref':identity,'owner_phase_id':row[0],'role':row[1],
                              'disposition':row[2],'relation_audit':audit})
            epoch,quarantined=c.execute('SELECT epoch,reconciliation_required FROM recovery_state WHERE singleton=1').fetchone()
            return {'decision':'SELECTED_REFERENCES_REVIEWED' if complete else 'REVIEW_REQUIRED',
                    'run_id':run_id,'checkpoint_id':checkpoint_id,'project_id':project,'task_id':run[1],
                    'task_revision':run[2],'epoch':epoch,'reconciliation_required':bool(quarantined),
                    'artifacts':items,'selection_source':'EXPLICIT_CONTROLLER_REQUEST',
                    'selection_persisted':False,'checkpoint_declared_requirements_verified':False,
                    'scope':'SELECTED_METADATA_AND_BOUNDED_DEPENDENCIES','max_artifacts':max_artifacts,
                    'unrelated_archive_scanned':False,'payload_read':False,'writes_performed':False,
                    'restore_readiness_proven':False,'execution_authorized':False}
        finally:
            if own:c.execute('ROLLBACK')

    def maintenance(self,*,project_id,as_of,after_artifact_id='',limit=20,relation_budget=0,declared_roots=None):
        """Bounded controller review hints; expiry never grants disposal authority."""
        from datetime import datetime
        _text(project_id,'project_id')
        if not isinstance(as_of,str):raise ValueError('Explicit review time required')
        instant=datetime.fromisoformat(as_of.replace('Z','+00:00'))
        if instant.tzinfo is None:raise ValueError('Review time requires a timezone')
        if (not isinstance(after_artifact_id,str) or type(limit) is not int or not 1<=limit<=100 or
                type(relation_budget) is not int or not 0<=relation_budget<=1000):
            raise ValueError('Invalid maintenance budget')
        from pathlib import Path
        from v2_local_host import unambiguous_relative_file
        from v2_evidence import _regular_path
        if declared_roots is None:declared_roots=[]
        if not isinstance(declared_roots,list) or len(declared_roots)>32:
            raise ValueError('At most 32 explicit roots may be inspected')
        relatives=[]
        for value in declared_roots:
            if not isinstance(value,str) or len(value)>2048:raise ValueError('Invalid declared root')
            relative=unambiguous_relative_file(value)
            if relative.as_posix().casefold() in {p.as_posix().casefold() for p in relatives}:
                raise ValueError('Duplicate declared root')
            relatives.append(relative)
        c=self.store.connection;own=not c.in_transaction
        if own:c.execute('BEGIN')
        try:
            project=c.execute('SELECT resource_root FROM project WHERE project_id=?',(project_id,)).fetchone()
            if not project:
                raise StateConflict('Unknown Project')
            root_candidates=[]
            if relatives:
                self._require_resource_root(project_id)
                root=Path(project[0])
                if not root.is_absolute() or str(root).startswith(('\\\\','//')):
                    raise ValueError('Explicit roots require a local absolute Project resource root')
                _regular_path(root)
                if not root.is_dir():raise StateConflict('Project resource root is unavailable')
                for relative in relatives:
                    target=root/relative
                    _regular_path(target)
                    if not target.resolve().is_relative_to(root.resolve()):
                        raise PermissionError('Declared root escapes Project resource root')
                    kind=('DIRECTORY' if target.is_dir() else 'FILE' if target.is_file()
                          else 'MISSING' if not target.exists() else 'OTHER')
                    root_candidates.append({'path':relative.as_posix(),'observed_kind':kind,
                        'registration_state':'NOT_INFERRED','owner':'NOT_ASSIGNED'})
            rows=c.execute('''SELECT artifact_id,phase_id,local_id,disposition,protected_definition
                FROM artifact_definition WHERE project_id=? AND artifact_id>?
                ORDER BY artifact_id LIMIT ?''',(project_id,after_artifact_id,limit+1)).fetchall()
            items=[]
            for identity,owner,local,disposition,protected in rows[:limit]:
                if artifact_ref(owner,local)!=identity:raise StateConflict('Artifact identity differs')
                definition=artifact_definition(decode(protected,project_id,'artifact',identity,1,'definition'))
                if definition['artifact_id']!=local or definition['owner']!={'kind':'PHASE','id':owner}:
                    raise StateConflict('Artifact protected owner differs')
                expiry=definition['retention']['expires_at']
                due=expiry is not None and datetime.fromisoformat(expiry.replace('Z','+00:00'))<=instant
                items.append({'artifact_ref':identity,'disposition':disposition,
                              'unresolved':disposition=='UNRESOLVED','retention_review_due':due,
                              'retention_time_defined':expiry is not None})
            relations=({'decision':'NOT_CHECKED','reason':'NO_RELATION_BUDGET'} if not relation_budget else
                       self.audit_relations(project_id=project_id,max_artifacts=relation_budget))
            return {'project_id':project_id,'as_of':as_of,'scope':'ENROLLED_METADATA_PAGE',
                    'artifacts':items,'counts_scope':'RETURNED_PAGE_ONLY',
                    'counts':{'returned':len(items),'unresolved':sum(i['unresolved'] for i in items),
                              'retention_review_due':sum(i['retention_review_due'] for i in items)},
                    'next_after_artifact_id':rows[limit-1][0] if len(rows)>limit else None,
                    'prior_pages_included':not bool(after_artifact_id),'later_pages_exist':len(rows)>limit,
                    'relations':relations,'declared_roots':root_candidates,
                    'root_observation_scope':'EXPLICIT_NAMES_METADATA_ONLY','directory_entries_read':0,
                    'root_observations_are_execution_proof':False,
                    'undeclared_roots':'NOT_SCANNED','payload_paths':'NOT_CHECKED',
                    'writes_performed':False,'payload_read':False,'deletion_authorized':False,
                    'authority_granted':False,'definition_content_included':False}
        finally:
            if own:c.execute('ROLLBACK')

    def context(self,*,project_id,after_artifact_id='',limit=20):
        _text(project_id,'project_id')
        if not isinstance(after_artifact_id,str) or type(limit) is not int or not 1<=limit<=100:
            raise ValueError('Invalid Artifact page')
        c=self.store.connection
        own=not c.in_transaction
        if own:c.execute('BEGIN')
        try:
            if not c.execute('SELECT 1 FROM project WHERE project_id=?',(project_id,)).fetchone():raise StateConflict('Unknown Project')
            rows=c.execute('''SELECT artifact_id,phase_id,phase_revision,primary_role,disposition,local_id FROM artifact_definition
                WHERE project_id=? AND artifact_id>? ORDER BY artifact_id LIMIT ?''',(project_id,after_artifact_id,limit+1)).fetchall()
            items=[]
            for row in rows[:limit]:
                if artifact_ref(row[1],row[5])!=row[0]:raise StateConflict('Artifact local identity projection differs')
                item=dict(zip(('artifact_id','phase_id','phase_revision','role','disposition'),row))
                item['artifact_ref']=row[0];item['artifact_id']=row[5]
                item['review_sequence']=c.execute("SELECT coalesce(max(sequence),0) FROM execution_audit WHERE kind='ARTIFACT_DISPOSITION' AND subject_id=?",(_json([project_id,row[0]]),)).fetchone()[0]
                archived=c.execute('SELECT archived_at FROM artifact_archive WHERE project_id=? AND artifact_id=?',(project_id,row[0])).fetchone()
                item['archived_at']=archived[0] if archived else None
                origin=c.execute("SELECT details_json FROM execution_audit WHERE kind='ARTIFACT_RUN_ORIGIN' AND subject_id=? ORDER BY sequence DESC LIMIT 1",
                                 (_json([project_id,row[0]]),)).fetchone()
                item['run_origin']=None if origin is None else {
                    **decode(json.loads(origin[0])['protected_origin'],project_id,'artifact-run-origin',row[0],1,'origin'),
                    'historical_binding':True,'execution_authorized':False}
                items.append(item)
            return {'project_id':project_id,'artifacts':items,
                    'next_after_artifact_id':rows[limit-1][0] if len(rows)>limit else None,
                    'definition_content_included':False,'payload_read':False,'writes_performed':False,'authority_granted':False}
        finally:
            if own:c.execute('ROLLBACK')
