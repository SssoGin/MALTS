"""Candidate cutover protocol for a caller-configured, trusted Host adapter.

The adapter must inhibit new writers and prove quiescence/isolation while its
handoff context is held. JSON declarations are deliberately not an adapter.
Source seals block legacy governed transactions; they are not an OS sandbox.
"""
import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from v2_state_store import StateConflict, _json
from v2_evidence import _regular_path
from v2_legacy_reader import read_source_bytes, inspect_legacy_activity, verify_inventory
from v2_migration import MigrationReview, definition_state_hash, inventory_hash,verify_definition_import

BINDING='runtime/v2_binding.json'
SEALS=('runtime/workspace_transaction.lock.json','runtime/artifact_transaction.lock.json')


def _path(root,relative):
    path=Path(root)/relative
    _regular_path(path)
    if not path.resolve().is_relative_to(Path(root).resolve()): raise StateConflict('Cutover path escapes source')
    return path


def _bytes(value): return _json(value).encode('utf-8')


def _seal(plan):
    return _bytes({'format':'malts.v2.source-seal','adoption_id':plan['adoption_id'],
                   'epoch':plan['new_epoch'],'state_dir':plan['state_dir']})


def _binding(plan):
    return _bytes({'format':'malts.v2.binding','schema':1,'adoption_id':plan['adoption_id'],
                   'epoch':plan['new_epoch'],'state_dir':plan['state_dir'],'source_root':plan['source_root']})


def _write_owned(path,data):
    _regular_path(path)
    if path.exists():
        if path.read_bytes()!=data: raise StateConflict('Existing cutover file is not owned by this plan')
        return
    with path.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def _retire_owned(root,relative,data,adoption_id):
    """Restore absence while retaining exact protocol bytes for recovery."""
    path=_path(root,relative)
    saved=_path(root,relative+'.'+adoption_id+'.retired')
    if not path.exists():
        if saved.exists() and saved.read_bytes()!=data: raise StateConflict('Retired cutover file differs')
        return
    if path.read_bytes()!=data: raise StateConflict('Cutover retirement preimage changed')
    if saved.exists():
        if saved.read_bytes()!=data: raise StateConflict('Retired cutover preimage changed')
        saved=_path(root,relative+'.'+adoption_id+'.'+uuid.uuid4().hex+'.retired')
    path.rename(saved)


def require_active_binding(store):
    epoch=store.connection.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]
    rows=store.connection.execute("SELECT plan_json,receipt_json,adoption_id,project_id,plan_sha256 FROM migration_adoption WHERE state='ACTIVE' AND new_epoch=?",(epoch,)).fetchall()
    if len(rows)!=1: raise StateConflict('No unique adoption binding for current epoch')
    plan=json.loads(rows[0][0]); receipt=json.loads(rows[0][1])
    Adoption._check_plan(plan)
    if (Path(plan['state_dir']).resolve()!=store.path.parent.resolve() or receipt.get('decision')!='ADOPTED' or
            receipt.get('epoch')!=epoch or plan['new_epoch']!=epoch or receipt.get('adoption_id')!=rows[0][2] or
            (plan['adoption_id'],plan['project_id'],plan['plan_sha256'])!=rows[0][2:]):
        raise StateConflict('Adoption receipt belongs to a different store or identity')
    root=Path(plan['source_root'])
    resource=store.connection.execute('SELECT resource_root FROM project WHERE project_id=?',(plan['project_id'],)).fetchone()
    if resource is None or Path(resource[0]).resolve()!=root.resolve(): raise StateConflict('Adopted resource root changed')
    for relative,data in [(BINDING,_binding(plan)),*((name,_seal(plan)) for name in SEALS)]:
        if read_source_bytes(root,relative,max_bytes=16384)['raw_bytes']!=data:
            raise StateConflict('Source binding or legacy-writer seal changed')


class Adoption:
    def __init__(self,store): self.store=store

    def inspect(self,*,adoption_id):
        row=self.store.connection.execute('SELECT state,plan_json,receipt_json FROM migration_adoption WHERE adoption_id=?',(adoption_id,)).fetchone()
        if row is None: raise StateConflict('Adoption record not found')
        plan=json.loads(row[1]); self._check_plan(plan)
        observed=[]
        for relative,expected in [(BINDING,_binding(plan)),*((name,_seal(plan)) for name in SEALS)]:
            try:
                actual=read_source_bytes(plan['source_root'],relative,max_bytes=16384)['raw_bytes']
                status='MATCH' if actual==expected else 'DIFFERENT'
            except FileNotFoundError: status='ABSENT'
            except (OSError,ValueError): status='UNREADABLE'
            observed.append({'path':relative,'status':status})
        return {'decision':'ADOPTION_STATUS','state':row[0],'plan':plan,
                'receipt':json.loads(row[2]) if row[2] else None,'source_protocol_files':observed,
                'legacy_runtime_rollback_supported':False,
                'recovery_direction':'V2_ONLY',
                'legacy_rollback_scene':row[0] in {'ROLLBACK_PENDING','ROLLED_BACK'},
                'automatic_recovery_available':False,
                'recovery_guidance':('PRESERVE_SCENE_V2_RECOVERY_REVIEW_REQUIRED'
                    if row[0] in {'ROLLBACK_PENDING','ROLLED_BACK'} else 'INSPECT_CURRENT_V2_STATE'),
                'host_liveness_verified':False,'execution_authorized':False,'writes_performed':False}

    def plan(self,*,source_root,semantic_review_id,adoption_id,authority_ref):
        if not isinstance(adoption_id,str) or re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',adoption_id) is None:
            raise ValueError('Invalid adoption ID')
        if not isinstance(authority_ref,str) or not authority_ref.strip(): raise ValueError('Adoption authority reference required')
        source=Path(source_root).absolute(); target=self.store.path.parent.resolve()
        _regular_path(source)
        if source.resolve().is_relative_to(target) or target.is_relative_to(source.resolve()):
            raise ValueError('Source and candidate store must be separate directories')
        if _path(source,BINDING).exists(): raise StateConflict('Source already has a binding; inspect its cutover state')
        c=self.store.connection; c.execute('BEGIN')
        try:
            row=c.execute('SELECT epoch,inventory_sha256,mapping_sha256,request_sha256,report_json FROM migration_review WHERE review_id=?',
                          (semantic_review_id,)).fetchone()
            if row is None: raise StateConflict('Semantic review is missing')
            epoch=c.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]
            if row[0]!=epoch: raise StateConflict('Semantic review belongs to another epoch')
            report=json.loads(row[4])
            if inventory_hash(report)!=row[3]: raise StateConflict('Semantic review report changed')
            reviewed=MigrationReview(self.store)._plan(report,row[1],row[2])
            if reviewed['unresolved_sources']: raise StateConflict('Unresolved source dispositions prevent adoption')
            capsule=json.loads((target/'legacy-source/manifest.json').read_text(encoding='utf-8'))
            if verify_inventory(source,capsule['inventory'])['decision']!='SOURCE_MATCH': raise StateConflict('Legacy source changed since import')
            activity=inspect_legacy_activity(source)
            if activity['blockers']: raise StateConflict('Known legacy activity prevents adoption')
            result={'format':'malts.v2.adoption-plan','adoption_id':adoption_id,'project_id':reviewed['project_id'],
                'semantic_review_id':semantic_review_id,'semantic_report_sha256':row[3],
                'semantic_review_row_sha256':inventory_hash(list(row)),
                'inventory_sha256':row[1],'mapping_sha256':row[2],'source_root':str(source.resolve()),
                'state_dir':str(target),'old_epoch':epoch,'new_epoch':str(uuid.uuid4()),'authority_ref':authority_ref,
                'definition_state_sha256':definition_state_hash(c),'source_activity_sha256':activity['source_activity_sha256'],
                'host_handoff_required':True,'execution_authorized':False}
            result['plan_sha256']=inventory_hash(result)
            c.execute('COMMIT'); return result
        except BaseException:
            if c.in_transaction: c.execute('ROLLBACK')
            raise

    @staticmethod
    def _check_plan(plan):
        fields={'format','adoption_id','project_id','semantic_review_id','semantic_report_sha256','semantic_review_row_sha256',
                'inventory_sha256','mapping_sha256','source_root','state_dir','old_epoch','new_epoch','authority_ref',
                'definition_state_sha256','source_activity_sha256','host_handoff_required','execution_authorized','plan_sha256'}
        if not isinstance(plan,dict) or set(plan)!=fields or plan.get('format')!='malts.v2.adoption-plan': raise ValueError('Invalid cutover plan')
        if plan['host_handoff_required'] is not True or plan['execution_authorized'] is not False:
            raise ValueError('A cutover plan cannot authorize itself or waive Host handoff')
        if not isinstance(plan['adoption_id'],str) or re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',plan['adoption_id']) is None:
            raise ValueError('Invalid adoption identity')
        if not isinstance(plan['authority_ref'],str) or not plan['authority_ref'].strip(): raise ValueError('Authority reference required')
        if inventory_hash({k:v for k,v in plan.items() if k!='plan_sha256'})!=plan.get('plan_sha256'):
            raise StateConflict('Cutover plan fingerprint changed')

    def _check_source(self,plan):
        root=Path(plan['source_root'])
        capsule=json.loads((self.store.path.parent/'legacy-source/manifest.json').read_text(encoding='utf-8'))
        if inventory_hash(capsule['inventory'])!=plan['inventory_sha256'] or verify_inventory(root,capsule['inventory'])['decision']!='SOURCE_MATCH':
            raise StateConflict('Source inventory changed during cutover')
        activity=inspect_legacy_activity(root)
        if any(not (b['code']=='TRANSACTION_LOCK_PRESENT' and b.get('path') in SEALS) for b in activity['blockers']):
            raise StateConflict('Legacy activity became unresolved during cutover')
        for record in activity['files']:
            if record['path'] in SEALS:
                if read_source_bytes(root,record['path'],max_bytes=16384)['raw_bytes']!=_seal(plan):
                    raise StateConflict('Source seal ownership changed')
                record.update(sha256=None,bytes=0)
        digest=hashlib.sha256(json.dumps(activity['files'],sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
        if digest!=plan['source_activity_sha256']: raise StateConflict('Source activity differs from reviewed cutover input')

    def _check_review(self,plan):
        row=self.store.connection.execute('SELECT epoch,inventory_sha256,mapping_sha256,request_sha256,report_json FROM migration_review WHERE review_id=?',
                                          (plan['semantic_review_id'],)).fetchone()
        if row is None or inventory_hash(list(row))!=plan['semantic_review_row_sha256']:
            raise StateConflict('Selected semantic review changed after cutover planning')
        if (plan['old_epoch'],plan['inventory_sha256'],plan['mapping_sha256'],plan['semantic_report_sha256'])!=row[:4]:
            raise StateConflict('Cutover identity differs from the selected semantic review')
        project=self.store.connection.execute('SELECT project_id FROM migration_review WHERE review_id=?',(plan['semantic_review_id'],)).fetchone()[0]
        if plan['project_id']!=project or plan['new_epoch']==plan['old_epoch']:
            raise StateConflict('Cutover project or fresh epoch is invalid')
        try: uuid.UUID(plan['new_epoch'])
        except (ValueError,TypeError): raise StateConflict('Cutover requires a valid new epoch') from None
        verify_definition_import(self.store.path.parent,expected_inventory_sha256=row[1],expected_mapping_sha256=row[2],_with_semantic_reviews=True)
        checked=MigrationReview(self.store)._plan(json.loads(row[4]),row[1],row[2])
        if checked['unresolved_sources']: raise StateConflict('Selected semantic review is unresolved')

    @staticmethod
    def _witness(witness):
        if (not isinstance(witness,dict) or set(witness)!={'host_id','evidence_ref','coverage','state'} or
                any(not isinstance(v,str) or not v.strip() for v in witness.values()) or
                witness['coverage']!='ALL_BOUND_WRITERS_AND_RESOURCES' or witness['state'] not in {'QUIESCED','ISOLATED'}):
            raise StateConflict('Trusted Host handoff did not establish complete quiescence or isolation')

    def apply(self,plan,*,host):
        self._check_plan(plan)
        if not callable(getattr(host,'handoff',None)): raise PermissionError('An in-process trusted Host handoff adapter is required')
        if Path(plan['state_dir']).resolve()!=self.store.path.parent.resolve(): raise StateConflict('Plan targets another store')
        c=self.store.connection
        existing=c.execute('SELECT state,plan_sha256,receipt_json FROM migration_adoption WHERE adoption_id=?',(plan['adoption_id'],)).fetchone()
        if existing and existing[1]!=plan['plan_sha256']: raise StateConflict('Adoption identity conflicts')
        if existing and existing[0]=='ACTIVE':
            require_active_binding(self.store)
            return {**json.loads(existing[2]),'replayed':True,'writes_performed':False,'host_revalidated':False}
        if existing and existing[0]=='ROLLED_BACK': raise StateConflict('Rolled-back adoption requires a new review')
        if existing and existing[0]=='ROLLBACK_PENDING': raise StateConflict('Legacy rollback is incomplete; preserve the scene for v2 forward recovery')
        if existing and existing[0]=='SUPERSEDED': raise StateConflict('Superseded binding is owned by forward recovery')
        with self.store.transaction() as c:
            self._check_review(plan)
            if definition_state_hash(c)!=plan['definition_state_sha256']: raise StateConflict('Candidate definitions changed')
            if not existing:
                c.execute('INSERT INTO migration_adoption VALUES (?,?,?,?,?,?,?,NULL)',
                    (plan['adoption_id'],plan['project_id'],'PREPARED',plan['old_epoch'],plan['new_epoch'],plan['plan_sha256'],_json(plan)))
        root=Path(plan['source_root'])
        # No DB write transaction is held while the Host waits for workers.
        with host.handoff(plan) as witness:
            self._witness(witness)
            try:
                for name in SEALS: _write_owned(_path(root,name),_seal(plan))
                self._check_source(plan)
                with self.store.transaction() as c:
                    self._check_review(plan)
                    if definition_state_hash(c)!=plan['definition_state_sha256']: raise StateConflict('Candidate changed before binding switch')
                    _write_owned(_path(root,BINDING),_binding(plan))
                    c.execute('UPDATE project SET resource_root=? WHERE project_id=?',(str(root),plan['project_id']))
                    c.execute('UPDATE recovery_state SET epoch=?,reconciliation_required=0 WHERE singleton=1',(plan['new_epoch'],))
                    c.execute("UPDATE migration_barrier SET pending_domains_json='[]' WHERE singleton=1")
                    receipt={'decision':'ADOPTED','adoption_id':plan['adoption_id'],'epoch':plan['new_epoch'],
                        'host_witness':witness,'assurance':getattr(host,'assurance','CALLER_CONFIGURED_HOST_ADAPTER'),'writes_performed':True,
                        'execution_authorized':False,'legacy_source_sealed':True,'post_adoption_state_sha256':definition_state_hash(c)}
                    c.execute("UPDATE migration_adoption SET state='ACTIVE',receipt_json=? WHERE adoption_id=?",(_json(receipt),plan['adoption_id']))
                require_active_binding(self.store)
                return receipt
            except BaseException:
                # An installed binding may be observed even if the DB commit
                # failed. Keep seals and PREPARED state for exact-plan recovery.
                if not _path(root,BINDING).exists() and not getattr(host,'preserve_source_seals',False):
                    for name in SEALS:
                        path=_path(root,name)
                        if path.exists() and path.read_bytes()==_seal(plan): _retire_owned(root,name,_seal(plan),plan['adoption_id'])
                raise

    def rollback(self,*,adoption_id,host):
        """Reject legacy reactivation without touching the Host or durable state."""
        raise StateConflict('LEGACY_ROLLBACK_REMOVED: preserve binding and seals; recover forward within v2')
