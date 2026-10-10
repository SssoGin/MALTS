"""Forward rebind of a reconciled, current backup without discarding v2 work.

Requires the same trusted in-process Host handoff boundary as initial adoption.
This mode requires a readable old store and a backup covering its current data.
"""
import hashlib
import json
import os
import re
from contextlib import closing
from pathlib import Path
from v2_state_store import StateStore,StateConflict,_json
from v2_migration import inventory_hash,definition_state_hash
from v2_adoption import Adoption,BINDING,SEALS,_path,_write_owned,_binding,_seal,require_active_binding
from v2_backup import verify_backup,_hash
from v2_recovery import TABLES,require_project_review,closed,text
from v2_evidence import BlobStore


def state_hash(connection):
    hashes={}
    for table in TABLES:
        if table=='migration_adoption': continue
        digest=hashlib.sha256()
        for row in connection.execute(f'SELECT * FROM {table} ORDER BY 1'):
            digest.update((_json(list(row))+'\n').encode('utf-8'))
        hashes[table]=digest.hexdigest()
    return inventory_hash(hashes)


def replace_protocol(root,relative,previous,following,operation_id):
    path=_path(root,relative)
    actual=path.read_bytes()
    if actual==following: return
    if actual!=previous: raise StateConflict('Forward binding preimage is not owned by this transition')
    saved=_path(root,relative+'.'+operation_id+'.preimage')
    staged=_path(root,relative+'.'+operation_id+'.next')
    _write_owned(saved,previous)
    _write_owned(staged,following)
    if path.read_bytes()!=previous: raise StateConflict('Binding changed before atomic replacement')
    os.replace(staged,path)  # old bytes remain in the owned preimage record


def unavailable_store_inventory(root, *, max_files=10000, max_bytes=1073741824):
    """Read raw retained state without opening SQLite or following links."""
    _path(Path(root),'.')
    root=Path(root).resolve()
    if not root.is_dir(): raise StateConflict('Original state directory must be retained')
    inventory={}; total=0
    def fail(error): raise error
    for current, directories, files in os.walk(root,followlinks=False,onerror=fail):
        for name in sorted(directories+files):
            path=Path(current)/name
            relative=path.relative_to(root).as_posix()
            _path(root,relative)
            if len(inventory)>=max_files: raise StateConflict('Retained-state inventory exceeds its entry limit')
            if path.is_dir(): inventory[relative]={'kind':'directory'}; continue
            if not path.is_file(): raise StateConflict('Unsupported retained-state entry')
            size=path.stat().st_size; total+=size
            if total>max_bytes: raise StateConflict('Retained-state inventory exceeds its byte limit')
            inventory[relative]={'kind':'file','bytes':size,'sha256':_hash(path)}
    if 'state.db' not in inventory: raise StateConflict('Original database must be retained, even when unreadable')
    return inventory


class UnavailableStoreRecovery:
    """Prepare a disaster handoff from backup lineage and explicit gap review.

    Preparation is read-only. Lost facts remain operator-attested; application
    rechecks the basis inside a trusted Host handoff and preserves original data.
    """
    def __init__(self,store): self.store=store

    def plan(self,*,backup_root,old_state_dir,adoption_id,authority_ref,gap_review):
        c=self.store.connection; owned=not c.in_transaction
        if owned: c.execute('BEGIN')
        try:
            result=self._plan(backup_root=backup_root,old_state_dir=old_state_dir,adoption_id=adoption_id,
                              authority_ref=authority_ref,gap_review=gap_review)
            if owned: c.execute('COMMIT')
            return result
        except BaseException:
            if owned and c.in_transaction: c.execute('ROLLBACK')
            raise

    def _plan(self,*,backup_root,old_state_dir,adoption_id,authority_ref,gap_review,_resume_plan=None):
        text(authority_ref,'authority_ref')
        if not isinstance(adoption_id,str) or re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',adoption_id) is None:
            raise ValueError('Invalid disaster adoption ID')
        closed(gap_review,{'review_id','authority_ref','coverage','evidence_refs','unresolved_items'},'Backup gap review')
        text(gap_review['review_id'],'gap review_id'); text(gap_review['authority_ref'],'gap authority_ref')
        if gap_review['coverage'] not in {'RECONSTRUCTED','UNKNOWN'}: raise ValueError('Invalid backup gap coverage')
        for key in ('evidence_refs','unresolved_items'):
            if not isinstance(gap_review[key],list): raise ValueError('Gap references and unresolved items must be lists')
            for item in gap_review[key]: text(item,key)
        if not gap_review['evidence_refs']: raise ValueError('Independent gap review references required')
        _path(Path(backup_root),'.'); _path(Path(old_state_dir),'.')
        backup_root=Path(backup_root).resolve(); old_root=Path(old_state_dir).resolve()
        target=self.store.path.parent.resolve()
        for left,right in ((target,old_root),(target,backup_root),(old_root,backup_root)):
            if left.is_relative_to(right) or right.is_relative_to(left):
                raise StateConflict('Original, backup and restored state must be separate directories')
        manifest=verify_backup(backup_root)
        with closing(StateStore(backup_root/'state.db',readonly=True)) as saved:
            epoch=saved.connection.execute('SELECT epoch FROM recovery_state').fetchone()[0]
            rows=saved.connection.execute("SELECT adoption_id,plan_json FROM migration_adoption WHERE state='ACTIVE' AND new_epoch=?",(epoch,)).fetchall()
            if len(rows)!=1: raise StateConflict('Backup has no unique adopted v2 lineage')
            parent_id,encoded=rows[0]; old=json.loads(encoded); Adoption._check_plan(old)
        if Path(old['state_dir']).resolve()!=old_root: raise StateConflict('Retained original differs from backup lineage')
        _path(Path(old['source_root']),'.')
        source=Path(old['source_root']).resolve()
        if source.is_relative_to(target) or target.is_relative_to(source): raise StateConflict('Restored store overlaps source workspace')
        protocol_sources={}
        for relative,expected in [(BINDING,_binding(old)),*((s,_seal(old)) for s in SEALS)]:
            path=_path(source,relative)
            retired=None
            if _resume_plan is not None:
                retired=_resume_plan.get('protocol_sources',{}).get(relative)
            elif not path.exists():
                pattern=re.compile(re.escape(path.name+'.'+old['adoption_id'])+r'(?:\.[0-9a-f]{32})?\.retired')
                matches=[]
                for candidate in path.parent.iterdir():
                    if pattern.fullmatch(candidate.name):
                        name=candidate.relative_to(source).as_posix()
                        if _path(source,name).read_bytes()!=expected: raise StateConflict('Retired protocol bytes differ from backup lineage')
                        matches.append(name)
                if len(matches)!=1: raise StateConflict('Absent protocol requires one exact retained retirement preimage')
                retired=matches[0]
            if retired is not None and _path(source,retired).read_bytes()!=expected:
                raise StateConflict('Retained protocol preimage changed')
            protocol_sources[relative]=retired
            allowed=[expected]
            if _resume_plan is not None:
                new=_resume_plan['new_binding_plan']
                allowed.append(_binding(new) if relative==BINDING else _seal(new))
            if path.exists():
                if path.read_bytes() not in allowed: raise StateConflict('Source protocol no longer matches the backed-up adoption')
            elif retired is None: raise StateConflict('Source protocol is absent without retained provenance')
        c=self.store.connection
        resource=c.execute('SELECT resource_root FROM project WHERE project_id=?',(old['project_id'],)).fetchone()
        if resource is None or Path(resource[0]).resolve()!=source: raise StateConflict('Disaster resource root differs from adopted workspace')
        recovery=c.execute('SELECT epoch,reconciliation_required,source_backup_hash FROM recovery_state').fetchone()
        if recovery[1] or recovery[2]!=manifest['database_sha256']: raise StateConflict('Disaster target requires reconciled backup restoration')
        review=c.execute('SELECT review_id FROM recovery_review WHERE epoch=?',(recovery[0],)).fetchone()
        if review is None: raise StateConflict('Disaster target lacks recovery review')
        require_project_review(c,review[0],recovery[0])
        copied=c.execute('SELECT plan_json FROM migration_adoption WHERE adoption_id=?',(parent_id,)).fetchone()
        if copied is None or copied[0]!=encoded: raise StateConflict('Restored adoption lineage differs from backup')
        if c.execute("SELECT 1 FROM operation WHERE state IN ('INTENT_RECORDED','UNKNOWN') LIMIT 1").fetchone():
            raise StateConflict('Restored operations remain unresolved')
        for item in manifest['managed_files']:
            if _hash(_path(target,item['path']))!=item['sha256']: raise StateConflict('Restored managed backup files changed')
        blobs=BlobStore(target/'blobs',readonly=True)
        for digest in manifest['blobs']: blobs.verify(digest)
        retained=unavailable_store_inventory(old_root)
        new={**old,'adoption_id':adoption_id,'state_dir':str(target),'old_epoch':old['new_epoch'],
             'new_epoch':recovery[0],'authority_ref':authority_ref,'definition_state_sha256':definition_state_hash(c)}
        new['plan_sha256']=inventory_hash({k:v for k,v in new.items() if k!='plan_sha256'})
        blockers=[]
        if gap_review['coverage']!='RECONSTRUCTED' or gap_review['unresolved_items']: blockers.append('BACKUP_GAP_UNRESOLVED')
        result={'format':'malts.v2.disaster-forward-plan','adoption_id':adoption_id,'parent_adoption_id':parent_id,
                'source_root':str(source),'old_state_dir':str(old_root),'state_dir':str(target),'backup_root':str(backup_root),
                'backup_manifest_sha256':inventory_hash(manifest),'retained_inventory':retained,
                'protocol_sources':protocol_sources,
                'retained_inventory_sha256':inventory_hash(retained),'target_state_sha256':state_hash(c),
                'recovery_review_id':review[0],'gap_review':gap_review,'old_binding_plan':old,'new_binding_plan':new,
                'blockers':blockers,'decision':'BLOCKED' if blockers else 'PREPARED_FOR_HOST_REVIEW',
                'assurance':'OPERATOR_ATTESTED_GAP_RECONSTRUCTION','execution_authorized':False,
                'writes_performed':False,'host_handoff_required':True,'application_available':True}
        result['plan_sha256']=inventory_hash(result)
        return result

    def inspect(self,*,adoption_id):
        row=self.store.connection.execute('SELECT state,receipt_json FROM migration_adoption WHERE adoption_id=?',(adoption_id,)).fetchone()
        if row is None or not row[1]: raise StateConflict('Disaster transition not found')
        receipt=json.loads(row[1]); plan=receipt.get('disaster_plan')
        self._validate(plan)
        if Path(plan['state_dir']).resolve()!=self.store.path.parent.resolve(): raise StateConflict('Disaster status belongs to another target')
        return {'state':row[0],'plan':plan,'receipt':receipt,'writes_performed':False,'execution_authorized':False}

    @staticmethod
    def _validate(plan):
        if not isinstance(plan,dict) or plan.get('format')!='malts.v2.disaster-forward-plan': raise ValueError('Invalid disaster plan')
        if inventory_hash({k:v for k,v in plan.items() if k!='plan_sha256'})!=plan.get('plan_sha256'): raise StateConflict('Disaster plan hash changed')
        if plan.get('execution_authorized') is not False or plan.get('host_handoff_required') is not True:
            raise StateConflict('Disaster plan cannot authorize itself')
        Adoption._check_plan(plan['old_binding_plan']); Adoption._check_plan(plan['new_binding_plan'])

    def apply(self,plan,*,host):
        self._validate(plan)
        if plan['blockers'] or plan['decision']!='PREPARED_FOR_HOST_REVIEW': raise StateConflict('Backup gap remains unresolved')
        if Path(plan['state_dir']).resolve()!=self.store.path.parent.resolve(): raise StateConflict('Disaster target differs')
        if not callable(getattr(host,'handoff',None)): raise PermissionError('Trusted in-process Host handoff required')
        current=self.store.connection.execute('SELECT state,receipt_json FROM migration_adoption WHERE adoption_id=?',(plan['adoption_id'],)).fetchone()
        if current:
            receipt=json.loads(current[1]) if current[1] else {}
            if receipt.get('disaster_plan')!=plan: raise StateConflict('Disaster identity conflicts with persisted plan')
            if current[0]=='ACTIVE':
                require_active_binding(self.store)
                return {**receipt,'replayed':True,'writes_performed':False,'host_revalidated':False}
            if current[0]!='PREPARED': raise StateConflict('Disaster transition is not resumable')
        def recheck(resume):
            fresh=self._plan(backup_root=plan['backup_root'],old_state_dir=plan['old_state_dir'],
                adoption_id=plan['adoption_id'],authority_ref=plan['new_binding_plan']['authority_ref'],
                gap_review=plan['gap_review'],_resume_plan=plan if resume else None)
            if fresh!=plan: raise StateConflict('Disaster recovery basis changed after review')
        old,new=plan['old_binding_plan'],plan['new_binding_plan']
        with host.handoff(plan) as witness:
            Adoption._witness(witness)
            with self.store.transaction() as c:
                recheck(current is not None)
                existing=c.execute('SELECT state,receipt_json FROM migration_adoption WHERE adoption_id=?',(plan['adoption_id'],)).fetchone()
                if existing:
                    if existing[0]!='PREPARED' or json.loads(existing[1]).get('disaster_plan')!=plan:
                        raise StateConflict('Concurrent disaster transition changed')
                else:
                    receipt={'decision':'DISASTER_PREPARED','disaster_plan':plan}
                    c.execute('INSERT INTO migration_adoption VALUES (?,?,?,?,?,?,?,?)',
                        (plan['adoption_id'],new['project_id'],'PREPARED',old['new_epoch'],new['new_epoch'],new['plan_sha256'],_json(new),_json(receipt)))
                    c.execute("UPDATE migration_adoption SET state='SUPERSEDED' WHERE adoption_id=?",(plan['parent_adoption_id'],))
            # Source seals fence both prior runtimes before switching the pointer.
            # Original bytes are retained by replace_protocol; no old DB writes.
            for relative in (*SEALS,BINDING):
                previous=_binding(old) if relative==BINDING else _seal(old)
                following=_binding(new) if relative==BINDING else _seal(new)
                retired=plan.get('protocol_sources',{}).get(relative)
                path=_path(plan['source_root'],relative)
                if retired is not None and not path.exists():
                    if _path(plan['source_root'],retired).read_bytes()!=previous:
                        raise StateConflict('Retirement preimage changed before protocol recreation')
                    _write_owned(path,following)
                else:
                    replace_protocol(plan['source_root'],relative,previous,following,plan['adoption_id'])
            with self.store.transaction() as c:
                recheck(True)
                receipt={'decision':'ADOPTED','disaster_recovery':True,'disaster_plan':plan,
                    'adoption_id':plan['adoption_id'],'epoch':new['new_epoch'],'host_witness':witness,
                    'assurance':'CALLER_CONFIGURED_HOST_AND_OPERATOR_GAP_REVIEW',
                    'execution_authorized':False,'writes_performed':True,'original_store_preserved':True}
                c.execute("UPDATE migration_adoption SET state='ACTIVE',receipt_json=? WHERE adoption_id=? AND state='PREPARED'",(_json(receipt),plan['adoption_id']))
            require_active_binding(self.store)
            return receipt


class ForwardRecovery:
    def __init__(self,store,old_store=None): self.store=store; self.old_store=old_store

    def _backup(self,root):
        manifest=verify_backup(Path(root))
        with closing(StateStore(Path(root)/'state.db',readonly=True)) as saved:
            old_hash=state_hash(saved.connection)
        for item in manifest['managed_files']:
            path=_path(self.store.path.parent,item['path'])
            if _hash(path)!=item['sha256']: raise StateConflict('Restored managed files differ from the backup')
            old_path=_path(self.old_store.path.parent,item['path'])
            if _hash(old_path)!=item['sha256']: raise StateConflict('Old managed files advanced beyond the saved backup')
        blobs=BlobStore(self.store.path.parent/'blobs',readonly=True)
        for digest in manifest['blobs']: blobs.verify(digest)
        return manifest,old_hash

    def plan(self,*,backup_root,adoption_id,authority_ref):
        if self.old_store is None: raise StateConflict('Forward planning requires the readable original v2 store')
        if not isinstance(adoption_id,str) or re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',adoption_id) is None:
            raise ValueError('Invalid forward adoption ID')
        if not isinstance(authority_ref,str) or not authority_ref.strip(): raise ValueError('Forward authority reference required')
        if self.store.path.parent.resolve()==self.old_store.path.parent.resolve(): raise ValueError('Restore into a separate state directory')
        require_active_binding(self.old_store)
        old_epoch=self.old_store.connection.execute('SELECT epoch FROM recovery_state').fetchone()[0]
        parent=self.old_store.connection.execute("SELECT adoption_id,plan_json FROM migration_adoption WHERE state='ACTIVE' AND new_epoch=?",(old_epoch,)).fetchone()
        old_plan=json.loads(parent[1]); Adoption._check_plan(old_plan)
        manifest,base_hash=self._backup(backup_root)
        if state_hash(self.old_store.connection)!=base_hash: raise StateConflict('Backup does not cover current old-store work')
        recovery=self.store.connection.execute('SELECT epoch,reconciliation_required,source_backup_hash FROM recovery_state').fetchone()
        review=self.store.connection.execute('SELECT review_id,receipt_json FROM recovery_review WHERE epoch=?',(recovery[0],)).fetchone()
        if recovery[1] or recovery[2]!=manifest['database_sha256'] or review is None or json.loads(review[1]).get('decision')!='RECONCILED':
            raise StateConflict('Restored backup requires complete current-epoch external-effect reconciliation')
        require_project_review(self.store.connection,review[0],recovery[0])
        if self.store.connection.execute("SELECT 1 FROM operation WHERE state IN ('INTENT_RECORDED','UNKNOWN') LIMIT 1").fetchone():
            raise StateConflict('Restored effects remain unresolved')
        copied=self.store.connection.execute('SELECT plan_json FROM migration_adoption WHERE adoption_id=?',(parent[0],)).fetchone()
        if copied is None or copied[0]!=parent[1]: raise StateConflict('Restored adoption lineage differs from current binding')
        new_plan={**old_plan,'adoption_id':adoption_id,'state_dir':str(self.store.path.parent.resolve()),
                  'old_epoch':old_epoch,'new_epoch':recovery[0],'authority_ref':authority_ref,
                  'definition_state_sha256':definition_state_hash(self.store.connection)}
        new_plan['plan_sha256']=inventory_hash({k:v for k,v in new_plan.items() if k!='plan_sha256'})
        result={'format':'malts.v2.forward-plan','adoption_id':adoption_id,'parent_adoption_id':parent[0],
                'source_root':old_plan['source_root'],'old_state_dir':str(self.old_store.path.parent.resolve()),
                'state_dir':str(self.store.path.parent.resolve()),'backup_root':str(Path(backup_root).resolve()),
                'backup_manifest_sha256':inventory_hash(manifest),'old_state_sha256':base_hash,
                'new_state_sha256':state_hash(self.store.connection),'recovery_review_id':review[0],
                'old_binding_plan':old_plan,'new_binding_plan':new_plan,'authority_ref':authority_ref,
                'execution_authorized':False,'host_handoff_required':True}
        result['plan_sha256']=inventory_hash(result)
        return result

    @staticmethod
    def _validate(plan):
        fields={'format','adoption_id','parent_adoption_id','source_root','old_state_dir','state_dir','backup_root',
                'backup_manifest_sha256','old_state_sha256','new_state_sha256','recovery_review_id','old_binding_plan',
                'new_binding_plan','authority_ref','execution_authorized','host_handoff_required','plan_sha256'}
        if not isinstance(plan,dict) or set(plan)!=fields or plan['format']!='malts.v2.forward-plan': raise ValueError('Invalid forward plan')
        if plan['execution_authorized'] is not False or plan['host_handoff_required'] is not True: raise ValueError('Forward plan cannot authorize itself')
        if inventory_hash({k:v for k,v in plan.items() if k!='plan_sha256'})!=plan['plan_sha256']: raise StateConflict('Forward plan hash changed')
        Adoption._check_plan(plan['old_binding_plan']); Adoption._check_plan(plan['new_binding_plan'])
        if (plan['new_binding_plan']['adoption_id']!=plan['adoption_id'] or plan['old_binding_plan']['adoption_id']!=plan['parent_adoption_id'] or
                plan['source_root']!=plan['old_binding_plan']['source_root'] or plan['source_root']!=plan['new_binding_plan']['source_root'] or
                plan['state_dir']!=plan['new_binding_plan']['state_dir'] or plan['old_state_dir']!=plan['old_binding_plan']['state_dir']):
            raise StateConflict('Forward binding identity mismatch')
        old,new=plan['old_binding_plan'],plan['new_binding_plan']
        if new['project_id']!=old['project_id'] or new['old_epoch']!=old['new_epoch'] or new['new_epoch']==old['new_epoch']:
            raise StateConflict('Forward project or epoch lineage is invalid')

    def inspect(self,*,adoption_id):
        row=self.store.connection.execute('SELECT state,receipt_json FROM migration_adoption WHERE adoption_id=?',(adoption_id,)).fetchone()
        if row is None or not row[1]: raise StateConflict('Forward transition not found')
        receipt=json.loads(row[1]); plan=receipt.get('forward_plan')
        self._validate(plan)
        if Path(plan['state_dir']).resolve()!=self.store.path.parent.resolve():
            raise StateConflict('Forward status belongs to a different target store')
        return {'state':row[0],'plan':plan,'receipt':receipt,'writes_performed':False,'execution_authorized':False}

    def _files_match_either(self,plan):
        old,new=plan['old_binding_plan'],plan['new_binding_plan']
        for relative,previous,following in [(BINDING,_binding(old),_binding(new)),*((s,_seal(old),_seal(new)) for s in SEALS)]:
            if _path(plan['source_root'],relative).read_bytes() not in (previous,following):
                raise StateConflict('Source protocol changed outside the prepared forward transition')

    def apply(self,plan,*,host):
        self._validate(plan)
        if self.old_store is None: raise StateConflict('Forward application requires the readable original v2 store')
        if not callable(getattr(host,'handoff',None)): raise PermissionError('Trusted in-process Host handoff required')
        if (Path(plan['old_state_dir']).resolve()!=self.old_store.path.parent.resolve() or
                Path(plan['state_dir']).resolve()!=self.store.path.parent.resolve()): raise StateConflict('Forward plan targets different stores')
        current=self.store.connection.execute('SELECT state,receipt_json FROM migration_adoption WHERE adoption_id=?',(plan['adoption_id'],)).fetchone()
        if current:
            saved=json.loads(current[1])
            if saved.get('forward_plan')!=plan: raise StateConflict('Forward identity conflicts with persisted plan')
            if current[0]=='ACTIVE':
                require_active_binding(self.store)
                return {**saved,'replayed':True,'writes_performed':False,'host_revalidated':False}
            if current[0]!='PREPARED': raise StateConflict('Forward transition is not resumable')
        old,new=plan['old_binding_plan'],plan['new_binding_plan']
        with host.handoff(plan) as witness:
            Adoption._witness(witness)
            manifest,base_hash=self._backup(plan['backup_root'])
            if inventory_hash(manifest)!=plan['backup_manifest_sha256'] or base_hash!=plan['old_state_sha256']:
                raise StateConflict('Forward backup changed')
            recovery=self.store.connection.execute('SELECT epoch,reconciliation_required,source_backup_hash FROM recovery_state').fetchone()
            if recovery!=(new['new_epoch'],0,manifest['database_sha256']): raise StateConflict('Forward recovery basis differs from the reconciled backup')
            review=self.store.connection.execute('SELECT receipt_json FROM recovery_review WHERE review_id=? AND epoch=?',
                                                 (plan['recovery_review_id'],new['new_epoch'])).fetchone()
            if review is None or json.loads(review[0]).get('decision')!='RECONCILED': raise StateConflict('Current reconciliation receipt is missing')
            require_project_review(self.store.connection,plan['recovery_review_id'],new['new_epoch'])
            self._files_match_either(plan)
            # Lock ordering is old store then restored store; no lock spans Host waiting.
            with self.old_store.transaction() as previous:
                if state_hash(previous)!=plan['old_state_sha256']: raise StateConflict('Old store advanced beyond the saved backup')
                parent=previous.execute('SELECT state,plan_json FROM migration_adoption WHERE adoption_id=?',(plan['parent_adoption_id'],)).fetchone()
                if parent is None or parent[0] not in {'ACTIVE','SUPERSEDED'} or json.loads(parent[1])!=old: raise StateConflict('Old adoption lineage changed')
                with self.store.transaction() as restored:
                    if state_hash(restored)!=plan['new_state_sha256']: raise StateConflict('Reconciled target changed after forward planning')
                    existing=restored.execute('SELECT state,receipt_json FROM migration_adoption WHERE adoption_id=?',(plan['adoption_id'],)).fetchone()
                    if existing:
                        saved=json.loads(existing[1])
                        if saved.get('forward_plan')!=plan: raise StateConflict('Concurrent forward identity differs')
                        if existing[0]=='ACTIVE':
                            require_active_binding(self.store)
                            return {**saved,'replayed':True,'writes_performed':False,'host_revalidated':True}
                        if existing[0]!='PREPARED': raise StateConflict('Forward transition state changed')
                    else:
                        receipt={'forward_recovery':True,'forward_plan':plan,'decision':'FORWARD_PREPARED'}
                        restored.execute('INSERT INTO migration_adoption VALUES (?,?,?,?,?,?,?,?)',
                            (plan['adoption_id'],new['project_id'],'PREPARED',old['new_epoch'],new['new_epoch'],new['plan_sha256'],_json(new),_json(receipt)))
                    restored.execute("UPDATE migration_adoption SET state='SUPERSEDED' WHERE adoption_id=?",(plan['parent_adoption_id'],))
                previous.execute("UPDATE migration_adoption SET state='SUPERSEDED' WHERE adoption_id=?",(plan['parent_adoption_id'],))
            # Both runtimes now refuse execution. Keep original bytes and replace
            # seals atomically; the binding is switched last. PREPARED can resume.
            for relative in SEALS:
                replace_protocol(plan['source_root'],relative,_seal(old),_seal(new),plan['adoption_id'])
            replace_protocol(plan['source_root'],BINDING,_binding(old),_binding(new),plan['adoption_id'])
            with self.store.transaction() as restored:
                if state_hash(restored)!=plan['new_state_sha256']: raise StateConflict('Target changed before forward activation')
                receipt={'decision':'ADOPTED','forward_recovery':True,'forward_plan':plan,'adoption_id':plan['adoption_id'],
                    'epoch':new['new_epoch'],'host_witness':witness,'assurance':getattr(host,'assurance','CALLER_CONFIGURED_HOST_ADAPTER'),
                    'post_adoption_state_sha256':definition_state_hash(restored),'execution_authorized':False,
                    'writes_performed':True,'preserved_new_work':True}
                restored.execute("UPDATE migration_adoption SET state='ACTIVE',receipt_json=? WHERE adoption_id=?",(_json(receipt),plan['adoption_id']))
            require_active_binding(self.store)
            return receipt
