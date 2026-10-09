"""Reviewed consolidation of identical installed MALTS generations.

Only installation registrations and MALTS-owned Host projections change.
The donor's independent state and user data are preserved in a verified backup,
not merged into project state. Physical donor cleanup is a separate action.
"""
from __future__ import annotations

import copy
from contextlib import ExitStack
import json
import os
from pathlib import Path
import stat

LEDGER=Path('runtime/consolidations')
MARKER=Path('runtime/consolidation-pending.json')
TERMINAL={'COMMITTED','ROLLED_BACK'}


def assert_idle(lc,root,*,operation_id=None):
    root=Path(root)
    marker=root/MARKER
    journals=[]
    if marker.exists():
        lc._assert_no_reparse(root,marker)
        value=lc.load_json(marker)
        if value.get('operation_id')!=operation_id:journals.append(Path(value['journal']))
    ledger=root/LEDGER
    if ledger.exists():
        lc._assert_no_reparse(root,ledger)
        for directory in ledger.iterdir():
            lc._assert_no_reparse(root,directory)
            if directory.name!=operation_id:journals.append(directory/'journal.json')
    for path in journals:
        if not path.is_file() or lc.load_json(path).get('status') not in TERMINAL:
            raise lc.LifecycleError('CONSOLIDATE_RECOVERY_REQUIRED','Reconcile the pending installation consolidation before mutation.',str(path))


def tree_digest(lc,root,*,ignore_marker=False):
    root=Path(root);pending=[root];records=[]
    while pending:
        node=pending.pop();lc._assert_no_reparse(root,node)
        relative=node.relative_to(root).as_posix()
        if ignore_marker and relative==MARKER.as_posix():continue
        if node.is_dir():
            records.append([relative,'D']);pending.extend(Path(item.path) for item in os.scandir(node))
        elif node.is_file():records.append([relative,'F',node.stat().st_size,lc.file_sha256(node)])
        else:raise lc.LifecycleError('CONSOLIDATE_PATH_TYPE','Only ordinary local content can be consolidated.',str(node))
    return lc.sha256_bytes(lc.canonical_json(sorted(records)))


def _roots(lc,primary,donor,*,require_installed=True):
    paths=[Path(str(primary)),Path(str(donor))]
    for path in paths:
        if not path.is_absolute() or str(path).startswith(('\\\\','//')) or path.parent==path:
            raise lc.LifecycleError('CONSOLIDATE_ROOT','Two distinct local installed lifecycle roots are required.',str(path))
        for parent in [path,*path.parents]:
            if parent.exists() and parent.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise lc.LifecycleError('CONSOLIDATE_LINK','Lifecycle roots must not traverse links.',str(parent))
    paths=[lc._absolute(path) for path in paths]
    if paths[0]==paths[1] or lc._is_inside(paths[0],paths[1]) or lc._is_inside(paths[1],paths[0]):
        raise lc.LifecycleError('CONSOLIDATE_OVERLAP','Lifecycle roots cannot overlap.')
    if require_installed and not all(path.is_dir() for path in paths):raise lc.LifecycleError('CONSOLIDATE_ROOT','Both installations must exist.')
    return paths


def _busy(lc,root):
    assert_idle(lc,root)
    from lifecycle_retirement import assert_idle as retirement_idle
    retirement_idle(lc,root)
    transactions=root/lc.TRANSACTIONS_RELATIVE
    if lc._lock_path(root).exists() or (transactions.exists() and any(transactions.iterdir())):
        raise lc.LifecycleError('CONSOLIDATE_BUSY','An existing lifecycle transaction must be settled first.',str(root))


def _write_record(lc,path,after):
    before=path.read_bytes() if path.is_file() else None
    return {'path':str(path),'before':None if before is None else before.hex(),'before_sha256':'MISSING' if before is None else lc.sha256_bytes(before),'after':None if after is None else after.hex(),'after_sha256':'MISSING' if after is None else lc.sha256_bytes(after)}


def _json_bytes(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')


def make_plan(lc,*,lifecycle_root,donor_lifecycle_root,tool_roots,repository_root=None,release_root=None,operation_id=None):
    primary,donor=_roots(lc,lifecycle_root,donor_lifecycle_root)
    for root in [primary,donor]:_busy(lc,root)
    registries=[lc._load_registry(root) for root in [primary,donor]]
    if any(not item or item['lifecycle_state']!='stable' for item in registries):raise lc.LifecycleError('CONSOLIDATE_NOT_STABLE','Both installations must be stable.')
    left,right=registries
    if set(left['selected_tools']) & set(right['selected_tools']):raise lc.LifecycleError('CONSOLIDATE_TOOL_OVERLAP','Selected Host sets must be disjoint.')
    tools=lc._normalize_tool_roots(tool_roots)
    if set(tools)!=set(left['selected_tools'])|set(right['selected_tools']):raise lc.LifecycleError('CONSOLIDATE_TOOL_COVERAGE','Supply every Host of both installations exactly once.')
    for path in tools.values():
        if any(lc._is_inside(root,path) or lc._is_inside(path,root) for root in [primary,donor]):raise lc.LifecycleError('CONSOLIDATE_OVERLAP','Host and installation roots cannot overlap.')
    groups=[{tool:tools[tool] for tool in registry['selected_tools']} for registry in registries]
    if any(lc.doctor(root,group)['status']!='HEALTHY' for root,group in zip([primary,donor],groups)):raise lc.LifecycleError('CONSOLIDATE_NOT_HEALTHY','Both actual installed images and Host projections must be healthy.')
    active=[lc._active_generation_record(registry) for registry in registries]
    if any(not item or not item['version'].startswith('2.') for item in active):raise lc.LifecycleError('CONSOLIDATE_VERSION','Only two verified current v2 installations are supported.')
    if any(active[0].get(field)!=active[1].get(field) for field in lc.GENERATION_BINDING_FIELDS):raise lc.LifecycleError('CONSOLIDATE_IDENTITY','The complete installed release and artifact identity must match, not just VERSION.')
    if (repository_root is None)==(release_root is None):raise lc.LifecycleError('CONSOLIDATE_SOURCE','Provide one reviewed repository or package source.')
    operation_id=operation_id or 'CONSOLIDATE-'+os.urandom(8).hex().upper()
    if not lc.ID_PATTERN.fullmatch(operation_id):raise lc.LifecycleError('CONSOLIDATE_OPERATION','Invalid consolidation operation ID.')
    writes=[];guards={}
    with lc._source_artifact_scope(repository_root=repository_root,release_root=release_root) as source:
        if any(active[0].get(field)!=source['identity'].get(field) for field in lc.GENERATION_BINDING_FIELDS):raise lc.LifecycleError('CONSOLIDATE_SOURCE_IDENTITY','The reviewed source must match both exact installed images.')
        artifact=source['artifact'];primary_generation=Path(active[0]['root'])
        modifications,residue=lc._classify_projection_modifications(artifact,groups[1],None,'update',active[0]['version'])
        if residue or any(row['decision'] not in {'replace','merge'} for row in modifications):raise lc.LifecycleError('CONSOLIDATE_USER_CONFLICT','Resolve changed or unowned donor projections before consolidation.')
        decisions=lc._modification_map(modifications)
        lc._preflight_projection_set(artifact,primary_generation,groups[1],'update',decisions)
        for tool,directory in groups[1].items():
            old=lc._projection_manifest(directory,tool);old_entries={item['path'].casefold():item for item in old['entries']};entries=[]
            for entry in artifact['projections'][tool]['entries']:
                target=lc._safe_target(directory,entry['path'])
                payload,merge,managed=lc._projection_payload(artifact,tool,directory,entry,primary_generation,decisions[os.path.normcase(str(lc._absolute(target)))],old_entries)
                writes.append(_write_record(lc,target,payload))
                item={'path':entry['path'],'mode':entry['mode'],'source_sha256':entry['sha256'],'installed_sha256':lc.sha256_bytes(payload)}
                if entry['mode']=='managed-block':item.update(rendered_managed_block_sha256=lc._managed_block_sha256(managed),boot_path=str(directory/'MALTS_BOOT.md'))
                if merge is not None:item['merge_metadata']=merge
                entries.append(item)
            manifest={'schema_version':2,'tool':tool,'generation_id':active[0]['generation_id'],'artifact_sha256':active[0]['artifact_sha256'],'boot_path':str(directory/'MALTS_BOOT.md'),'entries':entries,'created_at':lc._now()}
            writes.append(_write_record(lc,directory/lc.PROJECTION_MANIFEST,_json_bytes(manifest)))
        for tool,directory in groups[0].items():
            manifest=lc._projection_manifest(directory,tool)
            for item in manifest['entries']:guards[str(directory/item['path'])]=lc._path_digest(directory/item['path'])
            guards[str(directory/lc.PROJECTION_MANIFEST)]=lc._path_digest(directory/lc.PROJECTION_MANIFEST)
        guards[str(primary_generation)]=tree_digest(lc,primary_generation)
        guards[str(lc._pointer_path(primary))]=lc._path_digest(lc._pointer_path(primary))
        combined=[tool for tool in lc.TOOLS if tool in tools]
        target_registry=copy.deepcopy(left);target_registry['selected_tools']=combined;target_registry['updated_at']=lc._now()
        target_active=lc._active_generation_record(target_registry);target_active['projection_manifests']=[f"projection:{tool}:{target_active['generation_id']}" for tool in combined]
        retired=copy.deepcopy(right);retired.update(active_generation_id=None,lifecycle_state='uninstalled',generations=[],updated_at=lc._now())
        writes.extend([_write_record(lc,lc._registry_path(primary),_json_bytes(target_registry)),_write_record(lc,lc._registry_path(donor),_json_bytes(retired)),_write_record(lc,lc._pointer_path(donor),None)])
        audits=[_write_record(lc,root/lc.AUDIT_RELATIVE/lc.AUDIT_CURRENT_FILENAME,None) for root in [primary,donor]]
        plan={'schema_version':1,'kind':'malts-installation-consolidation','operation_id':operation_id,'lifecycle_root':str(primary),'donor_lifecycle_root':str(donor),'tool_roots':{tool:str(root) for tool,root in tools.items()},'source_kind':'repository' if repository_root else 'release-package','source_root':str(source['root']),'source_identity':{key:source['identity'][key] for key in lc.GENERATION_BINDING_FIELDS},'primary_registry_sha256':lc._registry_digest(primary),'donor_registry_sha256':lc._registry_digest(donor),'donor_tree_sha256':tree_digest(lc,donor),'guards':guards,'writes':writes,'audit_inputs':audits,'created_at':lc._now()}
    plan['plan_hash']=lc.sha256_bytes(lc.canonical_json(plan))
    return plan


def _checked_plan(lc,plan,expected):
    value=copy.deepcopy(plan);digest=value.pop('plan_hash',None)
    if digest!=expected or lc.sha256_bytes(lc.canonical_json(value))!=digest or plan.get('kind')!='malts-installation-consolidation':raise lc.LifecycleError('CONSOLIDATE_PLAN_HASH','Reviewed consolidation plan hash mismatch.')
    primary,donor=_roots(lc,plan['lifecycle_root'],plan['donor_lifecycle_root'],require_installed=False)
    if not lc.ID_PATTERN.fullmatch(plan['operation_id']):raise lc.LifecycleError('CONSOLIDATE_OPERATION','Invalid operation ID.')
    tools=lc._normalize_tool_roots(plan['tool_roots']);allowed={str(lc._registry_path(root)) for root in [primary,donor]}|{str(lc._pointer_path(donor))}
    for tool,directory in tools.items():
        manifest=lc._projection_manifest(directory,tool)
        if manifest:allowed|={str(directory/item['path']) for item in manifest['entries']}|{str(directory/lc.PROJECTION_MANIFEST)}
    seen=set()
    expected_audits={str(root/lc.AUDIT_RELATIVE/lc.AUDIT_CURRENT_FILENAME) for root in [primary,donor]}
    if {row['path'] for row in plan['audit_inputs']}!=expected_audits:raise lc.LifecycleError('CONSOLIDATE_WRITE_BOUNDARY','Audit inputs must be the two exact current-binding receipts.')
    allowed|=expected_audits
    for row in plan['writes']+plan['audit_inputs']:
        if row['path'] not in allowed or row['path'] in seen:raise lc.LifecycleError('CONSOLIDATE_WRITE_BOUNDARY','Unowned or duplicate write target.',row['path'])
        seen.add(row['path'])
        for name in ['before','after']:
            if (row[name] is None and row[name+'_sha256']!='MISSING') or (row[name] is not None and lc.sha256_bytes(bytes.fromhex(row[name]))!=row[name+'_sha256']):raise lc.LifecycleError('CONSOLIDATE_WRITE_HASH','Planned file bytes do not match their digest.')
    return primary,donor


def _audit_writes(lc,plan):
    primary=Path(plan['lifecycle_root'])
    target=next(row for row in plan['writes'] if row['path']==str(lc._registry_path(primary)))
    registry=json.loads(bytes.fromhex(target['after']));active,binding=lc._active_binding(registry)
    audit=lc._make_audit_record(record_type='current-binding',record_id='AUDIT-CURRENT-'+plan['operation_id'],created_at=plan['created_at'],operation_id=plan['operation_id'],operation='consolidate',outcome='ACTIVE',details=lc._audit_details(plan_hash=plan['plan_hash'],generation_id=active['generation_id'],binding_sha256=binding))
    rows=copy.deepcopy(plan['audit_inputs']);payload=_json_bytes(audit)
    primary_row=next(row for row in rows if row['path']==str(primary/lc.AUDIT_RELATIVE/lc.AUDIT_CURRENT_FILENAME))
    primary_row.update(after=payload.hex(),after_sha256=lc.sha256_bytes(payload))
    return rows


def _guard(lc,plan):
    for path,digest in plan['guards'].items():
        p=Path(path);actual=tree_digest(lc,p) if p.is_dir() else lc._path_digest(p)
        if actual!=digest:raise lc.LifecycleError('CONSOLIDATE_GUARD_DRIFT','A protected active installation or original Host changed.',path)


def _apply_row(lc,row,*,restore=False):
    path=Path(row['path']);lc._assert_no_reparse(path.parent,path);lc._assert_no_hardlink(path)
    if lc._path_digest(path) not in {row['before_sha256'],row['after_sha256']}:raise lc.LifecycleError('CONSOLIDATE_FILE_DRIFT','A planned Host or registry file has unreviewed bytes.',str(path))
    value=row['before' if restore else 'after']
    if value is None:
        if path.exists():path.unlink()
    else:lc._atomic_write(path,bytes.fromhex(value))


def execute(lc,plan,expected,*,apply=False,recovery=False,fault_at=None):
    primary,donor=_checked_plan(lc,plan,expected)
    writes=plan['writes']+_audit_writes(lc,plan)
    if not apply:return {'status':'PASS','mode':'DRY_RUN','writes_performed':False,'plan_hash':expected,'hosts':list(plan['tool_roots']),'primary':str(primary),'donor':str(donor)}
    if not donor.exists():
        journal_path=primary/LEDGER/plan['operation_id']/'journal.json'
        if journal_path.is_file():
            receipt=lc.load_json(journal_path)
            if receipt.get('plan_hash')==expected and receipt.get('status')=='COMMITTED':
                _guard(lc,plan)
                return {'status':'PASS','mode':'ALREADY_COMMITTED','writes_performed':False,'lifecycle_root':str(primary),'hosts':list(plan['tool_roots']),'donor_physically_absent':True}
        raise lc.LifecycleError('CONSOLIDATE_DONOR_MISSING','No committed consolidation receipt proves this donor removal.')
    from v2_runtime_mutex import RuntimeMutex
    with ExitStack() as stack:
        for root in sorted([primary,donor],key=lambda p:os.path.normcase(str(p))):stack.enter_context(RuntimeMutex(root))
        for root in [primary,donor]:assert_idle(lc,root,operation_id=plan['operation_id'])
        _guard(lc,plan)
        directory=primary/LEDGER/plan['operation_id'];journal_path=directory/'journal.json'
        if journal_path.exists():
            journal=lc.load_json(journal_path)
            if journal.get('plan_hash')!=expected:raise lc.LifecycleError('CONSOLIDATE_OPERATION_CONFLICT','Operation ID has another plan.')
            if journal['status']=='COMMITTED':return {'status':'PASS','mode':'ALREADY_COMMITTED','writes_performed':False,'lifecycle_root':str(primary),'hosts':list(plan['tool_roots'])}
            if not recovery:raise lc.LifecycleError('CONSOLIDATE_RECOVERY_REQUIRED','Resume the original consolidation instead of replaying a pending operation.',str(directory))
        else:
            if recovery:raise lc.LifecycleError('CONSOLIDATE_RECOVERY_REQUIRED','Journal preparation was incomplete; preserve the directory for inspected recovery.',str(directory))
            for root in [primary,donor]:_busy(lc,root)
            if lc._registry_digest(primary)!=plan['primary_registry_sha256'] or lc._registry_digest(donor)!=plan['donor_registry_sha256'] or tree_digest(lc,donor)!=plan['donor_tree_sha256']:raise lc.LifecycleError('CONSOLIDATE_INPUT_DRIFT','Installed registration or donor content changed after review.')
            for row in writes:
                if lc._path_digest(Path(row['path']))!=row['before_sha256']:raise lc.LifecycleError('CONSOLIDATE_INPUT_DRIFT','Host bytes changed after review.',row['path'])
            directory.mkdir(parents=True,exist_ok=False);lc.write_json(directory/'plan.json',plan)
            journal={'schema_version':1,'plan_hash':expected,'status':'PREPARING','completed_writes':0,'backup_complete':False};lc.write_json(journal_path,journal)
            lc.write_json(donor/MARKER,{'operation_id':plan['operation_id'],'journal':str(journal_path)})
        backup=directory/'donor-backup'
        try:
            if not journal['backup_complete']:
                if backup.exists():raise lc.LifecycleError('CONSOLIDATE_BACKUP_INCOMPLETE','Incomplete backup is preserved; inspect before resuming.',str(backup))
                lc._copy_tree(donor,backup)
                marker=backup/MARKER
                if marker.exists():marker.unlink()
                if tree_digest(lc,backup)!=plan['donor_tree_sha256']:raise lc.LifecycleError('CONSOLIDATE_BACKUP_HASH','Donor backup does not match the reviewed original.')
                journal.update(backup_complete=True,status='PREPARED');lc.write_json(journal_path,journal)
            if tree_digest(lc,backup)!=plan['donor_tree_sha256']:raise lc.LifecycleError('CONSOLIDATE_BACKUP_HASH','Verified donor recovery input changed.')
            journal['status']='APPLYING';lc.write_json(journal_path,journal)
            for number,row in enumerate(writes,1):
                _guard(lc,plan);_apply_row(lc,row)
                journal['completed_writes']=number;lc.write_json(journal_path,journal)
                if fault_at=='AFTER_FIRST_WRITE' and number==1:raise lc.InjectedCrash('AFTER_FIRST_WRITE')
                if fault_at=='AFTER_PRIMARY_REGISTRY' and row['path']==str(lc._registry_path(primary)):raise lc.InjectedCrash('AFTER_PRIMARY_REGISTRY')
            doctor=lc.doctor(primary,plan['tool_roots'])
            if doctor['status']!='HEALTHY':raise lc.LifecycleError('CONSOLIDATE_POSTVALIDATE','Unified installation is not healthy.')
            donor_registry=lc._load_registry(donor)
            if donor_registry['lifecycle_state']!='uninstalled' or donor_registry['generations'] or lc._pointer_path(donor).exists():raise lc.LifecycleError('CONSOLIDATE_POSTVALIDATE','Donor registration did not retire.')
            _guard(lc,plan)
            journal['status']='COMMITTED';lc.write_json(journal_path,journal)
            if (donor/MARKER).exists():(donor/MARKER).unlink()
            return {'status':'PASS','mode':'CONSOLIDATED','writes_performed':True,'lifecycle_root':str(primary),'hosts':list(plan['tool_roots']),'donor_retired':str(donor),'donor_backup':str(backup),'donor_backup_sha256':plan['donor_tree_sha256'],'journal':str(journal_path),'physical_donor_cleanup_performed':False,'project_state_migrated':False}
        except lc.InjectedCrash:
            journal['status']='RECOVERY_REQUIRED';lc.write_json(journal_path,journal);raise
        except Exception:
            journal['status']='RECOVERY_REQUIRED';lc.write_json(journal_path,journal)
            # Only original or planned output bytes can be restored. A new
            # external edit is never overwritten during automatic rollback.
            try:
                _guard(lc,plan)
                for row in reversed(writes):_apply_row(lc,row,restore=True)
                journal['status']='ROLLED_BACK';lc.write_json(journal_path,journal)
                if (donor/MARKER).exists():(donor/MARKER).unlink()
            except Exception as rollback_error:
                journal['rollback_error']=type(rollback_error).__name__+': '+str(rollback_error)
                lc.write_json(journal_path,journal)
            raise


def recover(lc,root,operation_id,*,apply=False):
    root=lc._absolute(root)
    if not lc.ID_PATTERN.fullmatch(operation_id):raise lc.LifecycleError('CONSOLIDATE_OPERATION','Invalid operation ID.')
    directory=root/LEDGER/operation_id;lc._assert_no_reparse(root,directory)
    plan=lc.load_json(directory/'plan.json')
    return execute(lc,plan,plan['plan_hash'],apply=apply,recovery=True)
