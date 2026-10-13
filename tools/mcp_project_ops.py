"""Four native Host plans with protected payloads, byte guards and original recovery."""
import base64
import copy
import hashlib
import json
import os
from contextlib import ExitStack
from pathlib import Path
import re
from mcp_config_check import ConfigError, HOSTS, MAX_BYTES, _path, _read, _launch, _binding, _generation, _same
from mcp_host_config import document as _document
from mcp_layers import resolve_layers, subtree, cordis_targets, effective_rows
from mcp_project_edit import edit, at
from v2_protected_inputs import seal, open_sealed, validate_reference

PROFILE='malts.project-mcp-plan.v2'
MAX_PLAN_BYTES=8*1024*1024
ID=re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}')
DIGEST=re.compile(r'[0-9A-F]{64}')


def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def digest(raw):return hashlib.sha256(raw).hexdigest().upper()


def context(plan,path,field):
    return {'owner':'mcp-project','record_type':PROFILE,'record_id':plan['operation_id'],'record_revision':1,'field':field,'binding_sha256':digest(canonical({key:plan[key] for key in ('lifecycle_root','tool_root','workspace','host','profile_name','overlays','strategy','server_name')}))+':'+digest(str(path).encode())}


def protected(raw,plan,path,field):
    reference,cipher=seal(raw,context=context(plan,path,field))
    return {'reference':reference,'cipher_base64':base64.b64encode(cipher).decode('ascii')}


def payload(value,plan,path,field):
    if not isinstance(value,dict) or set(value)!={'reference','cipher_base64'}:raise ConfigError('PROJECT_PAYLOAD_SHAPE_INVALID')
    validate_reference(value['reference'])
    text=value['cipher_base64']
    if not isinstance(text,str) or len(text)>4*MAX_BYTES:raise ConfigError('PROJECT_PAYLOAD_BYTE_BUDGET')
    try: cipher=base64.b64decode(text,validate=True)
    except ValueError:raise ConfigError('PROJECT_PAYLOAD_INVALID') from None
    raw=open_sealed(cipher,value['reference'],context=context(plan,path,field))
    if len(raw)>MAX_BYTES:raise ConfigError('CONFIGURATION_BYTE_BUDGET')
    return raw


def _standard(resolved,root):
    layers=[layer for layer in resolved['layers'] if layer['scope'] in ('USER','PROFILE')]
    overrides={};entry=None
    # Resolve only the selected native global/profile layers, using the same
    # precedence rules as the complete selected context.
    for layer in layers:
        path=Path(layer['path'])
        if not path.exists():continue
        data=_document(resolved['host'],_read(path))
        if resolved['host']=='deepseek-harness':
            for _,name,value,_,disabled,_ in cordis_targets(data):
                if name=='@deepseek-ai/dsh-mcp-client' and isinstance(value,dict) and value.get('serverName')=='malts' and disabled is not True:entry=copy.deepcopy(value)
        else:
            value=subtree(data,layer['pointer']).get('malts')
            if value is not None:
                from mcp_layers import merge
                entry=copy.deepcopy(value) if resolved['host']=='claude' else merge(entry or {},value)
    if entry is None:raise ConfigError('GLOBAL_STANDARD_ENTRY_REQUIRED')
    values=_launch(resolved['host'],entry)
    if values.get('project-bound') or Path(values['script']).name!='mcp_launcher.py' or _generation(values['script'],root)[0]!='CURRENT':raise ConfigError('GLOBAL_STANDARD_ENTRY_UNVERIFIED')
    if _binding(values)[0]:raise ConfigError('GLOBAL_STANDARD_ENTRY_UNVERIFIED')
    return entry,values


def materials(plan):
    host=plan['host'];root=_path(plan['lifecycle_root']);tool=_path(plan['tool_root']);workspace=_path(plan['workspace']);path=_path(plan['config_path'])
    resolved=resolve_layers(host,tool,workspace,profile=plan['profile_name'],overlays=plan['overlays'])
    allowed=[layer for layer in resolved['layers'] if _same(layer['path'],path) and layer['scope'] not in ('USER','APPROVAL','HOME_DIRECTORY')]
    if not allowed:raise ConfigError('PROJECT_CONFIGURATION_BOUNDARY')
    standard,standard_values=_standard(resolved,root)
    name=plan['server_name'];raw=_read(path);after={};selected=resolved['entries'].get(name)
    if selected is None:return resolved,after
    targets=[]
    for layer in allowed if plan['strategy']=='stable-project' else resolved['layers']:
        if layer['scope'] in ('USER','APPROVAL','PROFILE') and plan['strategy']=='inherit-global':continue
        file=Path(layer['path'])
        if not file.exists():continue
        data=_document(host,_read(file))
        if host=='deepseek-harness':
            for identity,plugin,entry,pointer,disabled,row_pointer in cordis_targets(data):
                if (plugin=='@deepseek-ai/dsh-mcp-client' or identity==selected.get('plugin_id')) and isinstance(entry,dict) and entry.get('serverName')==name:
                    targets.append((file,tuple(pointer),tuple(row_pointer),entry,disabled))
        else:
            entry=subtree(data,layer['pointer']).get(name)
            if entry is not None:targets.append((file,(*layer['pointer'],name),None,entry,None))
    if not targets:return resolved,after
    values=_launch(host,selected['entry'])
    if _binding(values)[0]:raise ConfigError('PROJECT_BINDING_REPAIR_REQUIRED')
    if _generation(values['script'],root)[0] not in ('CURRENT','VALID_OLDER_GENERATION'):raise ConfigError('PROJECT_GENERATION_UNVERIFIED')
    if plan['strategy']=='inherit-global':
        if name!='malts':raise ConfigError('PROJECT_SPECIAL_POLICY_REQUIRES_RETENTION')
        if selected.get('disabled') or selected['entry'].get('enabled',True) is not True:raise ConfigError('PROJECT_SPECIAL_POLICY_REQUIRES_RETENTION')
        for _,_,_,entry,disabled in targets:
            allowed_keys={'command','args','startup_timeout_sec','tool_timeout_sec'} if host=='codex' else {'command','args','type','timeout','enabled'} if host in ('claude','opencode') else {'serverName','command','args'}
            if set(entry)-allowed_keys or entry.get('enabled',True) is not True or disabled not in (None,False):raise ConfigError('PROJECT_SPECIAL_POLICY_REQUIRES_RETENTION')
        if any(values.get(k) for k in ('enable-write','allow-protected-input-capture','actor','authority-ref','task-id','task-revision','dispatch-id','workflow-topic')):raise ConfigError('PROJECT_SPECIAL_POLICY_REQUIRES_RETENTION')
        if not _same(values['command'],standard_values['command']):raise ConfigError('PROJECT_INTERPRETER_DIFF_REQUIRES_RETENTION')
        # Descending pointers keep Cordis array indexes stable during removal.
        targets.sort(key=lambda row:(str(row[0]),tuple((0,v) if isinstance(v,int) else (1,v) for v in row[1])),reverse=True)
    elif 'state-dir' not in values:raise ConfigError('PROJECT_BOUND_ENTRY_REQUIRED')
    for file,pointer,remove_pointer,entry,_ in targets:
        current=after.get(str(file),_read(file))
        if plan['strategy']=='inherit-global':desired=None
        else:
            desired=copy.deepcopy(entry)
            key='command' if host=='opencode' else 'args'
            original_args=selected['entry'][key] if key not in entry else entry[key]
            args=list(original_args);index=next(i for i,v in enumerate(args) if Path(v).name in ('v2_mcp.py','mcp_launcher.py'))
            args[index]=standard_values['script']
            if '--project-bound' not in args:args.insert(index+1,'--project-bound')
            if 'tool-root' not in values:args+=['--tool-root',str(tool)]
            elif not _same(values['tool-root'],tool):raise ConfigError('PROJECT_TOOL_ROOT_CONFLICT')
            desired[key]=args
        after[str(file)]=edit(host,current,pointer,desired,remove_pointer=remove_pointer)
    after={file:raw_after for file,raw_after in after.items() if raw_after!=_read(file)}
    prospective=resolve_layers(host,tool,workspace,profile=plan['profile_name'],overlays=plan['overlays'],overrides=after)
    if plan['strategy']=='inherit-global':
        inherited=prospective['entries'].get(name)
        if inherited is None or inherited['scope'] not in ('USER','PROFILE') or inherited.get('disabled') or inherited['entry'].get('enabled',True) is not True:raise ConfigError('PROJECT_INHERITANCE_STILL_SHADOWED_OR_DISABLED')
        if _launch(host,inherited['entry'])!=standard_values:raise ConfigError('PROJECT_INHERITANCE_STILL_SHADOWED_OR_DISABLED')
    return resolved,after


def make_plan(*,lifecycle_root,tool_root,workspace,config_path,strategy,server_name='malts',operation_id=None,host='codex',profile='desktop',overlays=None):
    host=HOSTS.get(host,host)
    if host not in HOSTS.values():raise ConfigError('UNSUPPORTED_CONFIGURATION_HOST')
    if strategy not in ('inherit-global','stable-project'):raise ConfigError('PROJECT_STRATEGY_INVALID')
    operation_id=operation_id or 'MCP-PROJECT-'+os.urandom(8).hex().upper()
    if not isinstance(operation_id,str) or not ID.fullmatch(operation_id):raise ConfigError('PROJECT_OPERATION_ID_INVALID')
    if not isinstance(server_name,str) or not server_name or len(server_name)>128:raise ConfigError('PROJECT_SERVER_NAME_INVALID')
    plan={'profile':PROFILE,'operation_id':operation_id,'lifecycle_root':str(_path(lifecycle_root)),'tool_root':str(_path(tool_root)),'workspace':str(_path(workspace)),'config_path':str(_path(config_path)),'strategy':strategy,'server_name':server_name,'host':host,'profile_name':profile,'overlays':[str(_path(p)) for p in overlays or []]}
    resolved,after=materials(plan)
    plan['guards']=resolved['guards'];plan['targets']=[{'path':path,'before_sha256':resolved['guards'][path],'after_sha256':digest(raw),'after_payload':protected(raw,plan,path,'after')} for path,raw in sorted(after.items())]
    plan['changes']=['INHERIT_STANDARD_NATIVE_ENTRY' if strategy=='inherit-global' else 'USE_STABLE_PROJECT_LAUNCHER'] if after else []
    plan['host_session_connection']='NOT_VERIFIED';plan['requires_reconnect']=bool(after);plan['writes_performed']=False
    plan['expected_effective_configuration']=effective_rows(host,tool_root,workspace,lifecycle_root=lifecycle_root,profile=profile,overlays=overlays,overrides=after)
    if any(row['status']=='NOT_VERIFIED' for row in plan['expected_effective_configuration']):raise ConfigError('PROJECT_PROPOSED_CONFIGURATION_UNVERIFIED')
    plan['policy_comparison']={'interpreter_preserved':True,'fixed_binding_retained':strategy=='stable-project','write_permissions_added':False,'environment_values_disclosed':False}
    plan['plan_hash']=digest(canonical(plan))
    if len(canonical(plan))>MAX_PLAN_BYTES:raise ConfigError('PROJECT_PLAN_BYTE_BUDGET')
    return plan


def checked_plan(plan,expected_hash):
    fields={'profile','operation_id','lifecycle_root','tool_root','workspace','config_path','strategy','server_name','host','profile_name','overlays','guards','targets','changes','host_session_connection','requires_reconnect','writes_performed','expected_effective_configuration','policy_comparison','plan_hash'}
    if not isinstance(plan,dict) or set(plan)!=fields or plan['profile']!=PROFILE:raise ConfigError('PROJECT_PLAN_SHAPE_INVALID')
    if len(canonical(plan))>MAX_PLAN_BYTES:raise ConfigError('PROJECT_PLAN_BYTE_BUDGET')
    body=dict(plan);claimed=body.pop('plan_hash')
    if not isinstance(claimed,str) or not DIGEST.fullmatch(claimed) or claimed!=expected_hash or digest(canonical(body))!=claimed:raise ConfigError('PROJECT_PLAN_HASH_MISMATCH')
    if plan['host'] not in HOSTS.values() or plan['strategy'] not in ('inherit-global','stable-project') or not isinstance(plan['operation_id'],str) or not ID.fullmatch(plan['operation_id']):raise ConfigError('PROJECT_PLAN_IDENTITY_INVALID')
    if not isinstance(plan['server_name'],str) or not plan['server_name'] or len(plan['server_name'])>128:raise ConfigError('PROJECT_SERVER_NAME_INVALID')
    _path(plan['lifecycle_root'])
    if not isinstance(plan['overlays'],list) or len(plan['overlays'])>32:raise ConfigError('PROJECT_OVERLAY_BUDGET')
    from mcp_layers import locations
    layers=locations(plan['host'],plan['tool_root'],plan['workspace'],profile=plan['profile_name'],overlays=plan['overlays'])
    allowed={row['path'] for row in layers if row['scope'] not in ('USER','APPROVAL','HOME_DIRECTORY')}
    if str(_path(plan['config_path'])) not in allowed:raise ConfigError('PROJECT_CONFIGURATION_BOUNDARY')
    if not isinstance(plan['guards'],dict) or set(plan['guards'])!={row['path'] for row in layers}:raise ConfigError('PROJECT_LAYER_GUARDS_INVALID')
    if any(value!='MISSING' and (not isinstance(value,str) or not DIGEST.fullmatch(value)) for value in plan['guards'].values()):raise ConfigError('PROJECT_LAYER_GUARDS_INVALID')
    if not isinstance(plan['targets'],list) or len(plan['targets'])>32:raise ConfigError('PROJECT_TARGET_BUDGET')
    seen=set()
    for row in plan['targets']:
        if not isinstance(row,dict) or set(row)!={'path','before_sha256','after_sha256','after_payload'} or row['path'] not in allowed or row['path'] in seen:raise ConfigError('PROJECT_TARGET_INVALID')
        seen.add(row['path'])
        if row['before_sha256']!=plan['guards'][row['path']] or not isinstance(row['after_sha256'],str) or not DIGEST.fullmatch(row['after_sha256']):raise ConfigError('PROJECT_TARGET_DIGEST_INVALID')
        if digest(payload(row['after_payload'],plan,row['path'],'after'))!=row['after_sha256']:raise ConfigError('PROJECT_AFTERIMAGE_HASH_MISMATCH')
    if plan['writes_performed'] is not False or type(plan['requires_reconnect']) is not bool or plan['requires_reconnect']!=bool(plan['targets']) or plan['host_session_connection']!='NOT_VERIFIED':raise ConfigError('PROJECT_PLAN_STATUS_INVALID')
    if not isinstance(plan['changes'],list) or bool(plan['changes'])!=bool(plan['targets']):raise ConfigError('PROJECT_PLAN_STATUS_INVALID')
    expected_changes=['INHERIT_STANDARD_NATIVE_ENTRY' if plan['strategy']=='inherit-global' else 'USE_STABLE_PROJECT_LAUNCHER'] if plan['targets'] else []
    if plan['changes']!=expected_changes or plan['policy_comparison']!={'interpreter_preserved':True,'fixed_binding_retained':plan['strategy']=='stable-project','write_permissions_added':False,'environment_values_disclosed':False}:raise ConfigError('PROJECT_PLAN_STATUS_INVALID')
    if not isinstance(plan['expected_effective_configuration'],list) or len(plan['expected_effective_configuration'])>64:raise ConfigError('PROJECT_EFFECTIVE_REPORT_INVALID')
    return _path(plan['lifecycle_root'])/'runtime/mcp/project-operations'/plan['operation_id']


def control_read(path):
    with _path(path).open('rb') as stream:raw=stream.read(MAX_PLAN_BYTES+1)
    if len(raw)>MAX_PLAN_BYTES:raise ConfigError('PROJECT_CONTROL_BYTE_BUDGET')
    from mcp_config_check import _json
    return _json(raw.decode('utf-8-sig'))


def assert_idle(root,*,operation_id=None):
    directory=_path(root)/'runtime/mcp/project-operations'
    if not directory.exists():return
    children=list(directory.iterdir())
    if len(children)>4096:raise ConfigError('PROJECT_OPERATION_LEDGER_BUDGET')
    for child in children:
        _path(child)
        if not child.is_dir() or not (child/'journal.json').is_file():raise ConfigError('PROJECT_OPERATION_LEDGER_INVALID')
        journal=control_read(child/'journal.json')
        if child.name!=operation_id and journal.get('state') not in ('COMMITTED','RESTORED'):raise ConfigError('PROJECT_RECOVERY_REQUIRED')


def execute(plan,expected_hash,*,apply=False,recovery=False,restore=False,fault_at=None):
    directory=checked_plan(plan,expected_hash)
    if not apply:return {'status':'PASS','mode':'DRY_RUN','writes_performed':False,'plan_hash':expected_hash,'changes':plan['changes'],'host_session_connection':'NOT_VERIFIED'}
    if os.name!='nt':raise ConfigError('PROJECT_EDIT_WINDOWS_PROFILE_REQUIRED')
    from v2_runtime_mutex import RuntimeMutex
    from v2_file_update import exclusive_existing_file
    import malts_lifecycle as lifecycle
    from malts_lifecycle import write_json
    with RuntimeMutex(_path(plan['lifecycle_root'])):
        from lifecycle_retirement import assert_idle as lifecycle_idle
        lifecycle_idle(lifecycle,_path(plan['lifecycle_root']),project_operation_id=plan['operation_id'])
        if lifecycle._lock_path(_path(plan['lifecycle_root'])).exists():raise ConfigError('PROJECT_LIFECYCLE_RECOVERY_REQUIRED')
        assert_idle(plan['lifecycle_root'],operation_id=plan['operation_id'])
        journal_path=directory/'journal.json';journal=control_read(journal_path) if journal_path.exists() else None
        if journal and (set(journal)!={'profile','plan_hash','state','completed'} or journal['profile']!=PROFILE or journal['plan_hash']!=expected_hash or journal['state'] not in ('PREPARED','WRITING','RESTORING','COMMITTED','RESTORED') or not isinstance(journal['completed'],list) or any(p not in {r['path'] for r in plan['targets']} for p in journal['completed'])):raise ConfigError('PROJECT_OPERATION_CONFLICT')
        if journal and control_read(directory/'plan.json')!=plan:raise ConfigError('PROJECT_ORIGINAL_PLAN_CHANGED')
        if journal and not recovery and journal['state']!='COMMITTED':raise ConfigError('PROJECT_RECOVERY_REQUIRED')
        if recovery and journal is None:raise ConfigError('PROJECT_RECOVERY_NOT_FOUND')
        if restore and journal is None:raise ConfigError('PROJECT_RECOVERY_NOT_FOUND')
        if journal is None:
            resolved,after=materials(plan)
            if resolved['guards']!=plan['guards'] or {path:digest(raw) for path,raw in after.items()}!={row['path']:row['after_sha256'] for row in plan['targets']}:raise ConfigError('PROJECT_PLAN_STALE')
            if not plan['targets']:return {'status':'PASS','mode':'NO_OP','writes_performed':False,'host_session_connection':'NOT_VERIFIED'}
        with ExitStack() as stack:
            streams={row['path']:stack.enter_context(exclusive_existing_file(_path(row['path']))) for row in plan['targets']}
            desired={};current={};preimages={}
            for row in plan['targets']:
                path=row['path'];raw=streams[path].read(MAX_BYTES+1);current[path]=digest(raw)
                if len(raw)>MAX_BYTES:raise ConfigError('CONFIGURATION_BYTE_BUDGET')
                if restore:
                    before=payload(control_read(directory/(digest(path.encode())+'.before.json')),plan,path,'before')
                    if digest(before)!=row['before_sha256']:raise ConfigError('PROJECT_PREIMAGE_CHANGED')
                    desired[path]=before
                else:desired[path]=payload(row['after_payload'],plan,path,'after')
                if current[path] not in (row['before_sha256'],row['after_sha256']):raise ConfigError('PROJECT_CONFIGURATION_DRIFT')
                if journal is None and current[path]!=row['before_sha256']:raise ConfigError('PROJECT_CONFIGURATION_DRIFT')
                preimages[path]=raw
            for path,previous in plan['guards'].items():
                if path in streams:continue
                actual=digest(_read(path)) if Path(path).exists() else 'MISSING'
                if actual!=previous:raise ConfigError('PROJECT_CONFIGURATION_LAYER_DRIFT')
            if journal is None:
                directory.mkdir(parents=True,exist_ok=False)
                write_json(directory/'plan.json',plan)
                for path,raw in preimages.items():write_json(directory/(digest(path.encode())+'.before.json'),protected(raw,plan,path,'before'))
                journal={'profile':PROFILE,'plan_hash':expected_hash,'state':'PREPARED','completed':[]};write_json(journal_path,journal)
            state='RESTORED' if restore else 'COMMITTED';changed=False
            for index,row in enumerate(plan['targets']):
                path=row['path'];raw=desired[path]
                if current[path]==digest(raw):continue
                journal['state']='RESTORING' if restore else 'WRITING';write_json(journal_path,journal)
                if fault_at=='before-write':raise ConfigError('PROJECT_INJECTED_INTERRUPTION')
                stream=streams[path];stream.seek(0);stream.write(raw);stream.truncate();stream.flush();os.fsync(stream.fileno());stream.seek(0)
                if stream.read(MAX_BYTES+1)!=raw:raise ConfigError('PROJECT_WRITE_UNVERIFIED')
                changed=True;journal['completed'].append(path);write_json(journal_path,journal)
                if fault_at=='after-first-write' and index==0:raise ConfigError('PROJECT_INJECTED_INTERRUPTION')
            changed=changed or journal['state']!=state;journal['state']=state;write_json(journal_path,journal)
        return {'status':'PASS','mode':state,'writes_performed':changed,'recovery_directory':str(directory),'host_session_connection':'NOT_VERIFIED','next_step':'Reconnect the selected Host; explicitly load a selected Harness overlay before checking its session.'}


def recover(lifecycle_root,operation_id,*,apply=False,restore=False):
    if not isinstance(operation_id,str) or not ID.fullmatch(operation_id):raise ConfigError('PROJECT_OPERATION_ID_INVALID')
    directory=_path(lifecycle_root)/'runtime/mcp/project-operations'/operation_id;plan=control_read(directory/'plan.json')
    if plan.get('operation_id')!=operation_id or not _same(plan.get('lifecycle_root'),lifecycle_root):raise ConfigError('PROJECT_RECOVERY_CONTEXT_CHANGED')
    return execute(plan,plan['plan_hash'],apply=apply,recovery=True,restore=restore)
