"""Explicit retirement of inactive generations through an approved recycler.

The current active image is never modified. Registry removal follows verified
recycling. Durable journals fence ordinary lifecycle writes after interruption;
recovery reconciles recorded receipts and never repeats an uncertain effect.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import stat
import subprocess

LEDGER = Path('runtime/generation-retirements')


def assert_idle(lifecycle, root, *, operation_id=None):
    from lifecycle_consolidation import assert_idle as consolidation_idle
    consolidation_idle(lifecycle,root)
    ledger=Path(root)/LEDGER
    if not ledger.exists():return
    lifecycle._assert_no_reparse(Path(root),ledger)
    for directory in ledger.iterdir():
        lifecycle._assert_no_reparse(Path(root),directory)
        if not directory.is_dir():raise lifecycle.LifecycleError('RETIRE_LEDGER_INVALID','Unexpected retirement ledger entry.',str(directory))
        journal=directory/'journal.json'
        if directory.name!=operation_id and (not journal.is_file() or lifecycle.load_json(journal).get('status') not in {'COMMITTED','ABORTED'}):
            raise lifecycle.LifecycleError('RETIRE_RECOVERY_REQUIRED','Reconcile the pending generation retirement before lifecycle mutation.',str(directory))


def _snapshot(lifecycle, path):
    files=directories=size=0
    pending=[path]
    records=[]
    while pending:
        node=pending.pop()
        lifecycle._assert_no_reparse(path,node)
        if node.is_dir():
            directories+=1;pending.extend(Path(item.path) for item in os.scandir(node))
            records.append([node.relative_to(path).as_posix(),'directory'])
        elif node.is_file():
            files+=1;size+=node.stat().st_size
            records.append([node.relative_to(path).as_posix(),'file',lifecycle.file_sha256(node)])
        else:raise lifecycle.LifecycleError('RETIRE_TARGET_TYPE','Only regular generation contents are supported.',str(node))
    return {'file_count':files,'directory_count':directories,'bytes':size,'digest':lifecycle.sha256_bytes(lifecycle.canonical_json(sorted(records)))}


def _surfaces(lifecycle, root, tool_roots):
    surfaces=[('active-generation-pointer',lifecycle._pointer_path(root))]
    for tool,value in tool_roots.items():
        directory=Path(value)
        for name in ['MALTS_BOOT.md',lifecycle.PROJECTION_MANIFEST,'config.toml','.mcp.json','opencode.json','opencode.jsonc']:
            if (directory/name).is_file():surfaces.append((tool+'-'+name,directory/name))
    return surfaces


def make_plan(lifecycle, *, lifecycle_root, tool_roots, generation_ids, operation_id=None):
    root=lifecycle._absolute(lifecycle_root)
    assert_idle(lifecycle,root)
    if not root.is_dir():raise lifecycle.LifecycleError('RETIRE_ROOT','An installed lifecycle root is required.',str(root))
    registry=lifecycle._load_registry(root)
    if not registry or registry['lifecycle_state']!='stable':raise lifecycle.LifecycleError('RETIRE_NOT_STABLE','A stable installation is required.')
    tools=lifecycle._normalize_tool_roots(tool_roots)
    if set(tools)!=set(registry['selected_tools']):raise lifecycle.LifecycleError('RETIRE_TOOL_COVERAGE','Every registered tool must be supplied exactly once.')
    active=lifecycle._active_generation_record(registry)
    if not active:raise lifecycle.LifecycleError('RETIRE_ACTIVE_IDENTITY','Exactly one active generation is required.')
    if lifecycle.doctor(root,tools)['status']!='HEALTHY':raise lifecycle.LifecycleError('RETIRE_NOT_HEALTHY','Repair the current installation before retiring history.')
    ids=list(generation_ids)
    if not ids or len(ids)!=len(set(ids)):raise lifecycle.LifecycleError('RETIRE_SELECTION','Select unique exact generation IDs.')
    rows=[]
    for identity in ids:
        matches=[item for item in registry['generations'] if item['generation_id']==identity]
        if len(matches)!=1:raise lifecycle.LifecycleError('RETIRE_UNREGISTERED','The selected generation is not uniquely registered.',identity)
        item=matches[0]
        if item['state']!='retiring' or identity==registry['active_generation_id']:raise lifecycle.LifecycleError('RETIRE_ACTIVE_FORBIDDEN','Only an explicitly retiring, inactive generation may be selected.',identity)
        path=lifecycle._absolute(item['root'])
        if path!=root/'generations'/identity:raise lifecycle.LifecycleError('RETIRE_TARGET_BOUNDARY','The registered generation must be a direct canonical child.',str(path))
        lifecycle.verify_installed_generation_envelope(path)
        rows.append({'generation_id':identity,'path':str(path),'registered_record':item,**_snapshot(lifecycle,path)})
    bindings=[{'generation_id':item['generation_id'],'root':item['path']} for item in rows]
    references=lifecycle._obsolete_generation_references(root,{'obsolete_generation_bindings':bindings,'tool_roots':{tool:str(value) for tool,value in tools.items()}},reference_surfaces=_surfaces(lifecycle,root,tools))
    if references:raise lifecycle.LifecycleError('RETIRE_REFERENCED','A managed current entry still references a selected generation.',references[0]['path'])
    operation_id=operation_id or 'RETIRE-'+os.urandom(8).hex().upper()
    if not lifecycle.ID_PATTERN.fullmatch(operation_id):raise lifecycle.LifecycleError('RETIRE_OPERATION_ID','Invalid retirement operation ID.')
    guards={str(Path(active['root'])):lifecycle._path_digest(Path(active['root']))}
    guards.update({str(path):lifecycle._path_digest(path) for _,path in _surfaces(lifecycle,root,tools)})
    plan={'schema_version':1,'kind':'malts-generation-retirement','operation_id':operation_id,'lifecycle_root':str(root),'tool_roots':{tool:str(value) for tool,value in tools.items()},'active_generation_id':active['generation_id'],'registry_sha256':lifecycle._registry_digest(root),'targets':rows,'protected_digests':guards,'created_at':lifecycle._now()}
    plan['plan_hash']=lifecycle.sha256_bytes(lifecycle.canonical_json(plan))
    return plan


def _check_plan(lifecycle, plan, expected_hash):
    required={'schema_version','kind','operation_id','lifecycle_root','tool_roots','active_generation_id','registry_sha256','targets','protected_digests','created_at','plan_hash'}
    value=copy.deepcopy(plan)
    digest=value.pop('plan_hash',None)
    if set(plan)!=required or plan['schema_version']!=1 or plan['kind']!='malts-generation-retirement' or digest!=expected_hash or lifecycle.sha256_bytes(lifecycle.canonical_json(value))!=digest:
        raise lifecycle.LifecycleError('RETIRE_PLAN_HASH','The reviewed retirement plan does not match.')
    root=lifecycle._absolute(plan['lifecycle_root'])
    if not lifecycle.ID_PATTERN.fullmatch(plan['operation_id']) or not plan['targets']:raise lifecycle.LifecycleError('RETIRE_SELECTION','Invalid operation or empty target selection.')
    identities=[]
    for row in plan['targets']:
        identity=row['generation_id'];identities.append(identity)
        if identity==plan['active_generation_id'] or not lifecycle.ID_PATTERN.fullmatch(identity) or lifecycle._absolute(row['path'])!=root/'generations'/identity or row['registered_record']['generation_id']!=identity or row['registered_record']['state']!='retiring':
            raise lifecycle.LifecycleError('RETIRE_TARGET_BOUNDARY','The plan includes an active or noncanonical target.')
    if len(identities)!=len(set(identities)):raise lifecycle.LifecycleError('RETIRE_SELECTION','Duplicate target selection.')
    return root


def _check_guards(lifecycle, plan):
    for path,digest in plan['protected_digests'].items():
        if lifecycle._path_digest(Path(path))!=digest:raise lifecycle.LifecycleError('RETIRE_PROTECTED_DRIFT','A current installation input changed after planning.',path)


def _regular_executable(lifecycle, path):
    path=Path(str(path))
    if not path.is_absolute() or str(path).startswith(('\\\\','//')):
        raise lifecycle.LifecycleError('RETIRE_EXECUTOR','An exact local absolute executable/script path is required.',str(path))
    for node in [path,*path.parents]:
        if node.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:raise lifecycle.LifecycleError('RETIRE_EXECUTOR_LINK','The approved recycler must not traverse links.',str(node))
    if not path.is_file():raise lifecycle.LifecycleError('RETIRE_EXECUTOR','A regular local recycler executable/script is required.',str(path))
    return lifecycle._absolute(path)


def _invoke(lifecycle, directory, row, helper, shell, helper_hash, *, validate):
    if lifecycle.file_sha256(helper)!=helper_hash:raise lifecycle.LifecycleError('RETIRE_RECYCLER_DRIFT','The approved recycler script changed.')
    arguments=[str(shell),'-NoProfile','-File',str(helper),'-LiteralPath',row['path'],'-ExpectedType','Directory','-ExpectedFileCount',str(row['file_count']),'-ExpectedDirectoryCount',str(row['directory_count']),'-ExpectedBytes',str(row['bytes']),'-ProtectedRoot',str(Path(row['path']).parent.parent)]
    if validate:arguments.append('-ValidateOnly')
    else:arguments+=['-ExpectedMetadataFingerprint',row['metadata_fingerprint']]
    completed=subprocess.run(arguments,capture_output=True,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
    record={'exit_code':completed.returncode,'stdout':completed.stdout,'stderr':completed.stderr}
    lifecycle.write_json(directory/(row['generation_id']+('.validate.json' if validate else '.recycle.json')),record)
    try:body=json.loads(completed.stdout)
    except ValueError as exc:raise lifecycle.LifecycleError('RETIRE_RECYCLER_OUTPUT','Recycler returned no valid receipt; do not retry an uncertain effect.') from exc
    expected='VALIDATED' if validate else 'RECYCLED_VERIFIED'
    if completed.returncode or completed.stderr or body.get('Status')!=expected:
        raise lifecycle.LifecycleError('RETIRE_RECYCLE_STOP','Recycler rejected or could not verify this exact target; no fallback.',row['path'])
    evidence=body['Evidence']
    if (evidence['FileCount'],evidence['DirectoryCount'],evidence['Bytes'])!=(row['file_count'],row['directory_count'],row['bytes']):raise lifecycle.LifecycleError('RETIRE_RECYCLE_RECEIPT','Recycler receipt counts do not match.')
    if not validate and (Path(row['path']).exists() or evidence['RecycleDataMetadataFingerprint']!=row['metadata_fingerprint']):raise lifecycle.LifecycleError('RETIRE_RECYCLE_RECEIPT','Original absence and matching recovery proof are required.')
    return evidence


def _commit_verified(lifecycle, plan, journal, directory):
    registry_path=lifecycle._registry_path(Path(plan['lifecycle_root']))
    current=lifecycle.load_json(registry_path)
    removed={identity for identity,status in journal['targets'].items() if status=='RECYCLED_VERIFIED'}
    desired=copy.deepcopy(journal['registry_before'])
    desired['generations']=[row for row in desired['generations'] if row['generation_id'] not in removed]
    # updated_at is deliberately preserved: retirement does not reissue the active binding.
    previous=journal.get('registry_committed',journal['registry_before'])
    if current not in [previous,desired]:raise lifecycle.LifecycleError('RETIRE_REGISTRY_DRIFT','The registry changed outside the selected retirement.')
    if current!=desired:lifecycle.write_json(registry_path,desired)
    journal['registry_committed']=desired
    lifecycle.write_json(directory/'journal.json',journal)


def execute_plan(lifecycle, plan, expected_hash, *, helper=None, helper_sha256=None, powershell=None, apply=False, recovery=False):
    root=_check_plan(lifecycle,plan,expected_hash)
    if not apply:return {'status':'PASS','mode':'DRY_RUN','writes_performed':False,'plan_hash':expected_hash,'targets':[row['path'] for row in plan['targets']]}
    if os.name!='nt':raise lifecycle.LifecycleError('RETIRE_PLATFORM','Retirement recycling is currently qualified only on Windows.')
    from v2_runtime_mutex import RuntimeMutex
    with RuntimeMutex(root):
        assert_idle(lifecycle,root,operation_id=plan['operation_id'])
        if lifecycle._lock_path(root).exists() or ((root/lifecycle.TRANSACTIONS_RELATIVE).exists() and any((root/lifecycle.TRANSACTIONS_RELATIVE).iterdir())):
            raise lifecycle.LifecycleError('RETIRE_LIFECYCLE_BUSY','Settle the existing lifecycle transaction first.')
        _check_guards(lifecycle,plan)
        directory=root/LEDGER/plan['operation_id']
        journal_path=directory/'journal.json'
        if journal_path.exists():
            journal=lifecycle.load_json(journal_path)
            if journal['plan_hash']!=expected_hash:raise lifecycle.LifecycleError('RETIRE_OPERATION_CONFLICT','Operation ID is already bound to another plan.')
            if journal['status']=='COMMITTED':return {'status':'PASS','mode':'ALREADY_COMMITTED','writes_performed':False,'retired':list(journal['targets'])}
            if not recovery:raise lifecycle.LifecycleError('RETIRE_RECOVERY_REQUIRED','Do not replay a pending effect; use retire-recover.',str(directory))
        else:
            if recovery:raise lifecycle.LifecycleError('RETIRE_RECOVERY_NOT_FOUND','No retirement journal exists.',str(directory))
            if lifecycle._registry_digest(root)!=plan['registry_sha256']:raise lifecycle.LifecycleError('RETIRE_REGISTRY_DRIFT','The registry changed after planning.')
            fresh=make_plan(lifecycle,lifecycle_root=root,tool_roots=plan['tool_roots'],generation_ids=[row['generation_id'] for row in plan['targets']],operation_id=plan['operation_id'])
            if fresh['targets']!=plan['targets'] or fresh['protected_digests']!=plan['protected_digests']:raise lifecycle.LifecycleError('RETIRE_TARGET_DRIFT','A retirement input changed after review.')
            for row in plan['targets']:
                if _snapshot(lifecycle,Path(row['path']))['digest']!=row['digest']:raise lifecycle.LifecycleError('RETIRE_TARGET_DRIFT','A selected generation changed.',row['path'])
            helper=_regular_executable(lifecycle,helper);shell=_regular_executable(lifecycle,powershell)
            if not re.fullmatch('[0-9a-fA-F]{64}',helper_sha256 or ''):raise lifecycle.LifecycleError('RETIRE_RECYCLER_HASH','An explicitly reviewed recycler hash is required.')
            helper_sha256=helper_sha256.upper()
            if lifecycle.file_sha256(helper)!=helper_sha256:raise lifecycle.LifecycleError('RETIRE_RECYCLER_DRIFT','Recycler hash does not match review.')
            directory.mkdir(parents=True,exist_ok=False)
            lifecycle.write_json(directory/'plan.json',plan)
            (directory/'registry.before.json').write_bytes(lifecycle._registry_path(root).read_bytes())
            journal={'schema_version':1,'plan_hash':expected_hash,'status':'PREPARED','targets':{row['generation_id']:'PREPARED' for row in plan['targets']},'registry_before':lifecycle._load_registry(root),'recycler_path':str(helper),'recycler_sha256':helper_sha256,'powershell':str(shell)}
            lifecycle.write_json(journal_path,journal)
        if lifecycle.file_sha256(directory/'registry.before.json')!=plan['registry_sha256'] or lifecycle.load_json(directory/'registry.before.json')!=journal['registry_before']:
            raise lifecycle.LifecycleError('RETIRE_RECOVERY_PREIMAGE','The original registry recovery input changed.')
        if recovery:
            validated=directory/'validated-targets.json'
            fingerprints={row['generation_id']:row['metadata_fingerprint'] for row in lifecycle.load_json(validated)} if validated.is_file() else {}
            for row in plan['targets']:
                receipt=directory/(row['generation_id']+'.recycle.json')
                if journal['targets'][row['generation_id']]=='RECYCLING' and receipt.is_file():
                    record=lifecycle.load_json(receipt)
                    try:body=json.loads(record['stdout'])
                    except ValueError:body={}
                    if record['exit_code']==0 and not record['stderr'] and body.get('Status')=='RECYCLED_VERIFIED' and not Path(row['path']).exists() and fingerprints.get(row['generation_id']) and body['Evidence']['RecycleDataMetadataFingerprint']==fingerprints[row['generation_id']]:
                        journal['targets'][row['generation_id']]='RECYCLED_VERIFIED'
            _commit_verified(lifecycle,plan,journal,directory)
            complete=all(status=='RECYCLED_VERIFIED' for status in journal['targets'].values())
            no_effect=all(status=='PREPARED' for status in journal['targets'].values()) and all(Path(row['path']).exists() and _snapshot(lifecycle,Path(row['path']))['digest']==row['digest'] for row in plan['targets'])
            journal['status']='COMMITTED' if complete else 'ABORTED' if no_effect else 'RECOVERY_REQUIRED'
            lifecycle.write_json(journal_path,journal)
            return {'status':'PASS' if complete or no_effect else 'RECOVERY_REQUIRED','mode':'RECOVERY_NO_EFFECT_REPLAY','writes_performed':True,'targets':journal['targets'],'journal':str(journal_path)}
        try:
            targets=copy.deepcopy(plan['targets'])
            for row in targets:
                evidence=_invoke(lifecycle,directory,row,helper,shell,helper_sha256,validate=True)
                row['metadata_fingerprint']=evidence['MetadataFingerprint']
            lifecycle.write_json(directory/'validated-targets.json',targets)
            for row in targets:
                _check_guards(lifecycle,plan)
                if _snapshot(lifecycle,Path(row['path']))['digest']!=row['digest']:raise lifecycle.LifecycleError('RETIRE_TARGET_DRIFT','Selected content changed before recycling.',row['path'])
                journal['targets'][row['generation_id']]='RECYCLING';lifecycle.write_json(journal_path,journal)
                _invoke(lifecycle,directory,row,helper,shell,helper_sha256,validate=False)
                journal['targets'][row['generation_id']]='RECYCLED_VERIFIED';lifecycle.write_json(journal_path,journal)
                _commit_verified(lifecycle,plan,journal,directory)
            journal['status']='COMMITTED';lifecycle.write_json(journal_path,journal)
            return {'status':'PASS','mode':'RECYCLED_VERIFIED','writes_performed':True,'retired':list(journal['targets']),'active_generation_id':plan['active_generation_id'],'journal':str(journal_path),'recovery':'Approved recycler receipts and pre-retirement registry retained; restore requires reviewed lifecycle handling, not a manual active pointer change.'}
        except BaseException:
            journal['status']='RECOVERY_REQUIRED';lifecycle.write_json(journal_path,journal)
            raise


def recover(lifecycle, root, operation_id, *, apply=False):
    root=lifecycle._absolute(root)
    if not lifecycle.ID_PATTERN.fullmatch(operation_id):raise lifecycle.LifecycleError('RETIRE_OPERATION_ID','Invalid retirement operation ID.')
    directory=root/LEDGER/operation_id
    lifecycle._assert_no_reparse(root,directory)
    plan=lifecycle.load_json(directory/'plan.json')
    return execute_plan(lifecycle,plan,plan['plan_hash'],apply=apply,recovery=True)
