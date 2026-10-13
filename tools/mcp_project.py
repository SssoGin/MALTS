"""Preserving native project plans; retained v1 records remain recovery inputs."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import tomllib
from mcp_config_check import ConfigError,_path,_read,_launch,_binding,_generation,_same,scan_configurations,effective_configurations

def digest(raw):return hashlib.sha256(raw).hexdigest().upper()
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()

def table_spans(raw,name):
    """Parsed TOML table names with lexical string/comment shielding."""
    text=raw.decode('utf-8-sig');headers=[];i=0;line_start=True
    while i<len(text):
        char=text[i]
        if char in "\"'":
            quote=char*3 if text.startswith(char*3,i) else char;i+=len(quote)
            while i<len(text):
                if quote.startswith('"') and text[i]=='\\':i+=2;continue
                if text.startswith(quote,i):i+=len(quote);break
                i+=1
            line_start=False;continue
        if char=='#':
            end=text.find('\n',i);i=len(text) if end<0 else end;continue
        if char=='\n':line_start=True;i+=1;continue
        if line_start and char in ' \t\r':i+=1;continue
        if line_start and char=='[':
            end=text.find('\n',i);end=len(text) if end<0 else end
            header=text[i:end].split('#',1)[0].strip()
            try:
                doc=tomllib.loads(header+'\n__malts_probe=1\n');keys=[]
                while isinstance(doc,dict) and '__malts_probe' not in doc and len(doc)==1:
                    key,doc=next(iter(doc.items()));keys.append(key)
                if isinstance(doc,dict) and doc.get('__malts_probe')==1:headers.append((i,tuple(keys)))
                else:raise ValueError()
            except Exception:raise ConfigError('PROJECT_TABLE_LAYOUT_UNSUPPORTED') from None
        line_start=False;i+=1
    spans=[]
    for index,(start,keys) in enumerate(headers):
        if keys[:2]!=('mcp_servers',name):continue
        end=headers[index+1][0] if index+1<len(headers) else len(text)
        # Keep comments preceding another table in their original location.
        chunk=text[start:end];lines=chunk.splitlines(keepends=True)
        while len(lines)>1 and (not lines[-1].strip() or lines[-1].lstrip().startswith('#')):end-=len(lines.pop())
        spans.append((start,end))
    if not spans:raise ConfigError('PROJECT_TABLE_LAYOUT_UNSUPPORTED')
    return text,spans

def edit_entry(raw,name,entry):
    before=tomllib.loads(raw.decode('utf-8-sig'));text,spans=table_spans(raw,name)
    newline='\r\n' if '\r\n' in text else '\n';replacement=''
    if entry is not None:
        original=before['mcp_servers'][name]
        # Stable conversion changes argv only, preserving interpreter, policy,
        # environment, timeouts and all original lexical bytes outside args.
        if {k:v for k,v in original.items() if k!='args'}!={k:v for k,v in entry.items() if k!='args'}:raise ConfigError('PROJECT_POLICY_CHANGE_REJECTED')
        for start,end in spans:
            segment=text[start:end]
            match=re.search(r'(?m)^([ \t]*args[ \t]*=[ \t]*)\[',segment)
            if not match:continue
            offset=match.end()-1;j=offset+1;quote=None
            while j<len(segment):
                c=segment[j]
                if quote:
                    if c=='\\' and quote=='"':j+=2;continue
                    if c==quote:quote=None
                elif c in "\"'":quote=c
                elif c=='#':
                    finish=segment.find('\n',j);j=len(segment) if finish<0 else finish;continue
                elif c==']':break
                j+=1
            if j>=len(segment):raise ConfigError('PROJECT_ARGUMENT_LAYOUT_UNSUPPORTED')
            updated=text[:start+offset]+json.dumps(entry['args'],ensure_ascii=False)+text[start+j+1:]
            break
        else:raise ConfigError('PROJECT_ARGUMENT_LAYOUT_UNSUPPORTED')
    else:
        updated=text
        for start,end in reversed(spans):updated=updated[:start]+updated[end:]
    bom=b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    result=bom+updated.encode('utf-8');after=tomllib.loads(result.decode('utf-8-sig'))
    expected=copy.deepcopy(before)
    if entry is None:expected['mcp_servers'].pop(name)
    else:expected['mcp_servers'][name]=entry
    def prune(value):
        if isinstance(value,dict):return {k:prune(v) for k,v in value.items() if v!={}}
        return value
    if prune(after)!=prune(expected):raise ConfigError('UNRELATED_CONFIGURATION_CHANGED')
    return result

def _legacy_make_plan(*,lifecycle_root,tool_root,workspace,config_path,strategy,server_name='malts',operation_id=None):
    root=_path(lifecycle_root);tool=_path(tool_root);workspace=_path(workspace);path=_path(config_path)
    if path!=workspace/'.codex/config.toml':raise ConfigError('PROJECT_CONFIGURATION_BOUNDARY')
    if strategy not in {'inherit-global','stable-project'}:raise ConfigError('PROJECT_STRATEGY_INVALID')
    operation_id=operation_id or 'MCP-PROJECT-'+os.urandom(8).hex().upper()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',operation_id):raise ConfigError('PROJECT_OPERATION_ID_INVALID')
    raw=_read(path);data=tomllib.loads(raw.decode('utf-8-sig'));entry=data.get('mcp_servers',{}).get(server_name)
    global_path=tool/'config.toml';global_raw=_read(global_path);global_entry=tomllib.loads(global_raw.decode('utf-8-sig')).get('mcp_servers',{}).get('malts')
    if global_entry is None:raise ConfigError('GLOBAL_STANDARD_ENTRY_REQUIRED')
    global_values=_launch('codex',global_entry)
    if global_values.get('project-bound') or Path(global_values['script']).name!='mcp_launcher.py' or _generation(global_values['script'],root)[0]!='CURRENT':raise ConfigError('GLOBAL_STANDARD_ENTRY_UNVERIFIED')
    if entry is None:
        after=raw;changes=[]
    else:
        values=_launch('codex',entry);issues,_=_binding(values)
        if issues:raise ConfigError('PROJECT_BINDING_REPAIR_REQUIRED')
        if _generation(values['script'],root)[0] not in {'CURRENT','VALID_OLDER_GENERATION'}:raise ConfigError('PROJECT_GENERATION_UNVERIFIED')
        if strategy=='inherit-global':
            # A bound project is a meaningful contract. Inheritance is an
            # explicit strategy, never an automatic equality/name decision.
            sensitive=set(entry)-{'command','args','startup_timeout_sec','tool_timeout_sec'}
            if server_name!='malts' or sensitive or values.get('enable-write') or values.get('allow-protected-input-capture') or any(k in values for k in ('actor','authority-ref','task-id','task-revision','dispatch-id','workflow-topic')):
                raise ConfigError('PROJECT_SPECIAL_POLICY_REQUIRES_RETENTION')
            if not _same(entry['command'],global_entry['command']):raise ConfigError('PROJECT_INTERPRETER_DIFF_REQUIRES_RETENTION')
            after=edit_entry(raw,server_name,None);changes=['REMOVE_SELECTED_PROJECT_ENTRY_TO_INHERIT_GLOBAL']
        else:
            if 'state-dir' not in values:raise ConfigError('PROJECT_BOUND_ENTRY_REQUIRED')
            desired=copy.deepcopy(entry);args=list(entry['args']);index=next(i for i,v in enumerate(args) if Path(v).name in {'v2_mcp.py','mcp_launcher.py'})
            args[index]=global_values['script']
            if '--project-bound' not in args:args.insert(index+1,'--project-bound')
            if 'tool-root' not in values:args+=['--tool-root',str(tool)]
            elif not _same(values['tool-root'],tool):raise ConfigError('PROJECT_TOOL_ROOT_CONFLICT')
            desired['args']=args;after=edit_entry(raw,server_name,desired);changes=[] if after==raw else ['REPLACE_VERSIONED_SCRIPT_WITH_STABLE_PROJECT_LAUNCHER']
    # Bind every inspected layer; a later parent/user edit invalidates preview.
    scan=scan_configurations({'codex':tool},lifecycle_root=root,workspaces=[workspace])
    guards={f['path']:f['sha256'] or 'MISSING' for f in scan['files']}
    if scan['status'] in {'CHECK_FAILED','UNVERIFIED'}:raise ConfigError('PROJECT_CONFIGURATION_COVERAGE_UNVERIFIED')
    prospective=effective_configurations({'codex':tool},lifecycle_root=root,workspaces=[workspace],document_overrides={str(path):after})
    selected=[row for row in prospective if row.get('server_name')==server_name]
    if any(row['status']=='NOT_VERIFIED' for row in prospective):raise ConfigError('PROJECT_PROPOSED_CONFIGURATION_UNVERIFIED')
    if strategy=='inherit-global' and (len(selected)!=1 or selected[0].get('source')!='USER' or selected[0].get('endpoint_kind')!='STANDARD_STABLE' or not selected[0].get('enabled')):
        raise ConfigError('PROJECT_INHERITANCE_STILL_SHADOWED_OR_DISABLED')
    plan={'profile':'malts.project-mcp-plan.v1','operation_id':operation_id,'lifecycle_root':str(root),'tool_root':str(tool),'workspace':str(workspace),'config_path':str(path),'strategy':strategy,'server_name':server_name,'before_sha256':digest(raw),'after_sha256':digest(after),'after_hex':after.hex(),'guards':guards,'changes':changes,'host_session_connection':'NOT_VERIFIED','requires_reconnect':bool(changes),'writes_performed':False}
    plan['expected_effective_configuration']=prospective
    plan['policy_comparison']={'interpreter_preserved':strategy=='stable-project' or entry is None,'fixed_binding_retained':strategy=='stable-project','write_permissions_added':False,'environment_values_disclosed':False}
    plan['plan_hash']=digest(canonical(plan));return plan

def _legacy_checked_plan(plan,expected_hash):
    fields={'profile','operation_id','lifecycle_root','tool_root','workspace','config_path','strategy','server_name','before_sha256','after_sha256','after_hex','guards','changes','host_session_connection','requires_reconnect','writes_performed','expected_effective_configuration','policy_comparison','plan_hash'}
    if not isinstance(plan,dict) or set(plan)!=fields:raise ConfigError('PROJECT_PLAN_SHAPE_INVALID')
    if not isinstance(plan['after_hex'],str) or len(plan['after_hex'])>2*1048576:raise ConfigError('PROJECT_PLAN_BYTE_BUDGET')
    body=dict(plan);claimed=body.pop('plan_hash',None)
    if claimed!=expected_hash or digest(canonical(body))!=claimed or plan.get('profile')!='malts.project-mcp-plan.v1':raise ConfigError('PROJECT_PLAN_HASH_MISMATCH')
    if _path(plan['config_path'])!=_path(plan['workspace'])/'.codex/config.toml':raise ConfigError('PROJECT_CONFIGURATION_BOUNDARY')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',plan['operation_id']):raise ConfigError('PROJECT_OPERATION_ID_INVALID')
    if digest(bytes.fromhex(plan['after_hex']))!=plan['after_sha256']:raise ConfigError('PROJECT_AFTERIMAGE_HASH_MISMATCH')
    return _path(plan['lifecycle_root'])/'runtime/mcp/project-operations'/plan['operation_id']

def _legacy_execute(plan,expected_hash,*,apply=False,recovery=False,restore=False):
    directory=_legacy_checked_plan(plan,expected_hash);path=_path(plan['config_path'])
    if not apply:return {'status':'PASS','mode':'DRY_RUN','writes_performed':False,'plan_hash':expected_hash,'changes':plan['changes'],'host_session_connection':'NOT_VERIFIED'}
    if os.name!='nt':raise ConfigError('PROJECT_EDIT_WINDOWS_PROFILE_REQUIRED')
    from v2_runtime_mutex import RuntimeMutex
    from v2_file_update import exclusive_existing_file
    from malts_lifecycle import write_json
    with RuntimeMutex(_path(plan['lifecycle_root'])):
        journal_path=directory/'journal.json'
        journal=json.loads(_read(journal_path)) if journal_path.exists() else None
        if journal and journal.get('plan_hash')!=expected_hash:raise ConfigError('PROJECT_OPERATION_CONFLICT')
        if journal and not recovery and journal['state']!='COMMITTED':raise ConfigError('PROJECT_RECOVERY_REQUIRED')
        if recovery and journal is None:raise ConfigError('PROJECT_RECOVERY_NOT_FOUND')
        if journal is None:
            fresh=_legacy_make_plan(lifecycle_root=plan['lifecycle_root'],tool_root=plan['tool_root'],workspace=plan['workspace'],config_path=path,strategy=plan['strategy'],server_name=plan['server_name'],operation_id=plan['operation_id'])
            if fresh['after_sha256']!=plan['after_sha256']:raise ConfigError('PROJECT_PLAN_STALE')
            if not plan['changes']:
                return {'status':'PASS','mode':'NO_OP','writes_performed':False,'host_session_connection':'NOT_VERIFIED'}
        if restore:
            before=_read(directory/'config.before')
            if digest(before)!=plan['before_sha256']:raise ConfigError('PROJECT_PREIMAGE_CHANGED')
            expected=plan['after_sha256'];desired=before
        else:expected=plan['before_sha256'];desired=bytes.fromhex(plan['after_hex'])
        with exclusive_existing_file(path) as stream:
            raw=stream.read();current=digest(raw)
            if journal and current==digest(desired):
                state='RESTORED' if restore else 'COMMITTED';changed=journal['state']!=state
                if changed:
                    journal['state']=state;write_json(journal_path,journal)
                return {'status':'PASS','mode':'RESTORED' if restore else 'ALREADY_COMMITTED','writes_performed':changed,'host_session_connection':'NOT_VERIFIED'}
            if current!=expected:raise ConfigError('PROJECT_CONFIGURATION_DRIFT')
            if not restore:
                for guard,old in plan['guards'].items():
                    if _same(guard,path):continue
                    actual=digest(_read(guard)) if Path(guard).exists() else 'MISSING'
                    if actual.upper()!=old.upper():raise ConfigError('PROJECT_CONFIGURATION_LAYER_DRIFT')
            if journal is None:
                directory.mkdir(parents=True,exist_ok=False);(directory/'config.before').write_bytes(raw);write_json(directory/'plan.json',plan)
                journal={'plan_hash':expected_hash,'state':'PREPARED'};write_json(journal_path,journal)
            journal['state']='RESTORING' if restore else 'WRITING';write_json(journal_path,journal)
            stream.seek(0);stream.write(desired);stream.truncate();stream.flush();os.fsync(stream.fileno());stream.seek(0)
            if stream.read()!=desired:raise ConfigError('PROJECT_WRITE_UNVERIFIED')
            journal['state']='RESTORED' if restore else 'COMMITTED';write_json(journal_path,journal)
        return {'status':'PASS','mode':journal['state'],'writes_performed':bool(plan['changes']) or restore,'recovery_directory':str(directory),'host_session_connection':'NOT_VERIFIED','next_step':'Reconnect the selected Host and verify its loaded endpoint separately.'}

def _legacy_recover(lifecycle_root,operation_id,*,apply=False,restore=False):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',operation_id):raise ConfigError('PROJECT_OPERATION_ID_INVALID')
    directory=_path(lifecycle_root)/'runtime/mcp/project-operations'/operation_id
    from mcp_project_ops import control_read
    plan=control_read(directory/'plan.json')
    if plan.get('operation_id')!=operation_id or not _same(plan.get('lifecycle_root'),lifecycle_root):raise ConfigError('PROJECT_RECOVERY_CONTEXT_CHANGED')
    return _legacy_execute(plan,plan['plan_hash'],apply=apply,recovery=True,restore=restore)


def make_plan(**kwargs):
    from mcp_project_ops import make_plan as create
    return create(**kwargs)


def checked_plan(plan,expected_hash):
    if isinstance(plan,dict) and plan.get('profile')=='malts.project-mcp-plan.v1':return _legacy_checked_plan(plan,expected_hash)
    from mcp_project_ops import checked_plan as check
    return check(plan,expected_hash)


def execute(plan,expected_hash,**kwargs):
    if isinstance(plan,dict) and plan.get('profile')=='malts.project-mcp-plan.v1':
        directory=_legacy_checked_plan(plan,expected_hash)
        from mcp_project_ops import control_read
        if kwargs.get('apply') and (not (directory/'journal.json').exists() or control_read(directory/'plan.json')!=plan):raise ConfigError('PROJECT_LEGACY_PLAN_REQUIRES_ORIGINAL_RECORD')
        return _legacy_execute(plan,expected_hash,**kwargs)
    from mcp_project_ops import execute as apply_plan
    return apply_plan(plan,expected_hash,**kwargs)


def recover(lifecycle_root,operation_id,**kwargs):
    from mcp_project_ops import recover as recover_plan,control_read
    if not isinstance(operation_id,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',operation_id):raise ConfigError('PROJECT_OPERATION_ID_INVALID')
    plan=control_read(_path(lifecycle_root)/'runtime/mcp/project-operations'/operation_id/'plan.json')
    if plan.get('profile')=='malts.project-mcp-plan.v1':return _legacy_recover(lifecycle_root,operation_id,**kwargs)
    return recover_plan(lifecycle_root,operation_id,**kwargs)
