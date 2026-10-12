"""Read-only project-root entry and staged preservation reference verifier."""
import json,os
from pathlib import Path
from v2_evidence import _regular_path
from v2_entry import inspect_workspace_entry
from v2_backup import _hash
from v2_path_io import io_path

def audit(workspace, *, baseline=None,mode='current-v2',allow_new_paths=()):
    root=Path(workspace).absolute();_regular_path(root)
    entry=inspect_workspace_entry(root)
    result={'decision':'VERIFIED_CURRENT_WORKSPACE','entry':entry,'writes_performed':False,'execution_authorized':False,
        'authority_source':'workspace/governance-context/task-queue/current Task service','business_acceptance_verified':False}
    if baseline is None:return result
    if not isinstance(baseline,dict) or set(baseline)!={'format','files'} or baseline['format']!='malts.preservation.v1' or not isinstance(baseline['files'],list):raise ValueError('Closed preservation manifest required')
    seen=set();changed=[]
    for row in baseline['files']:
        if not isinstance(row,dict) or set(row)!={'path','bytes','sha256'}:raise ValueError('Invalid preservation record')
        relative=Path(row['path'])
        if relative.is_absolute() or relative.drive or '..' in relative.parts or ':' in row['path'] or row['path'] in seen:raise ValueError('Unsafe or duplicate preservation path')
        seen.add(row['path']);path=root/relative;_regular_path(path)
        if not io_path(path).is_file() or io_path(path).stat().st_size!=row['bytes'] or _hash(path).casefold()!=row['sha256'].casefold():changed.append(row['path'])
    for raw in allow_new_paths:
        p=Path(raw)
        if not p.parts or p.is_absolute() or p.drive or '..' in p.parts or ':' in raw:raise ValueError('Explicit relative addition scope required')
    managed=entry['decision'] in {'NATIVE_WORKSPACE','ADOPTED_WORKSPACE'} and (root/'.malts').exists()
    if managed:
        from v2_management import management_root
        management_root(root,require_owned=True)
    extras=[];review=[]
    count=0
    for directory,children,files in os.walk(io_path(root),followlinks=False):
        for name in children+files:
            count+=1
            if count>50000:raise ValueError('Preservation entry limit exceeded')
            path=Path(directory)/name;_regular_path(path)
            if name in children:continue
            rel=path.relative_to(io_path(root)).as_posix()
            if rel in seen:continue
            extras.append(rel)
            allowed=(managed and rel.startswith('.malts/')) or (entry['decision']=='ADOPTED_WORKSPACE' and rel in {'runtime/v2_binding.json','runtime/workspace_transaction.lock.json','runtime/artifact_transaction.lock.json'})
            allowed=allowed or any(rel==p or rel.startswith(p.rstrip('/')+'/') for p in allow_new_paths)
            if not allowed:review.append(rel)
    stale=mode=='pre-adoption' and entry['decision'] in {'NATIVE_WORKSPACE','ADOPTED_WORKSPACE'} and bool(extras)
    result.update(decision='ORIGINAL_CONTENT_CHANGED' if changed else 'LEGACY_PREPARATION_SCOPE_STALE' if stale else 'ADDITIONS_REQUIRE_SCOPE_REVIEW' if review else 'ORIGINAL_CONTENT_PRESERVED',
        original_files_checked=len(seen),original_content_preserved=not changed,changed_original_paths=changed,
        additions=len(extras),new_paths_requiring_review=review,historical_preparation_scope_stale=stale,
        next_action='USE_CURRENT_V2_WORKSPACE_AUDIT_AND_REVIEW_EXPLICIT_ADDITIONS' if stale or review else 'READ_CURRENT_TASK_STATE')
    return result
