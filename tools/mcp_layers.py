"""Bounded native disk-layer resolution. It neither boots a Host nor grants trust."""
import copy
import hashlib
import json
import re
from pathlib import Path
from mcp_config_check import ConfigError, HOSTS, _path, _read, _same, _malts, _launch, _binding, _generation, endpoint_kind
from mcp_host_config import document as _document


def merge(left, right):
    result = copy.deepcopy(left)
    for key, value in right.items():
        result[key] = merge(result[key], value) if isinstance(result.get(key), dict) and isinstance(value, dict) else copy.deepcopy(value)
    return result


def project_directories(workspace):
    workspace = _path(workspace)
    if not workspace.is_dir(): raise ConfigError('WORKSPACE_DIRECTORY_REQUIRED')
    parents = [workspace, *workspace.parents]
    if len(parents) > 64: raise ConfigError('PROJECT_LAYER_DEPTH_BUDGET')
    boundary = next((p for p in parents if (p/'.git').exists()), workspace)
    return parents[:parents.index(boundary)+1]


def locations(host, tool_root, workspace, *, profile='desktop', overlays=None):
    host = HOSTS.get(host, host); tool = _path(tool_root); workspace = _path(workspace)
    directories = project_directories(workspace)
    rows = []
    def add(path, scope, pointer=()):
        rows.append({'path':str(_path(path)), 'scope':scope, 'pointer':list(pointer)})
    if host == 'codex':
        add(tool/'config.toml','USER',('mcp_servers',))
        for directory in reversed(directories): add(directory/'.codex/config.toml','PROJECT',('mcp_servers',))
    elif host == 'claude':
        add(tool.parent/'.claude.json','USER',('mcpServers',))
        add(workspace/'.mcp.json','PROJECT',('mcpServers',))
        key=str(workspace);user=tool.parent/'.claude.json'
        if user.exists():
            projects=_document(host,_read(user)).get('projects',{})
            if not isinstance(projects,dict) or len(projects)>256:raise ConfigError('CLAUDE_PROJECT_BUDGET')
            matches=[name for name in projects if _same(name,workspace)]
            if len(matches)>1:raise ConfigError('CLAUDE_PROJECT_PATH_AMBIGUOUS')
            if matches:key=matches[0]
        add(user,'LOCAL',('projects',key,'mcpServers'))
        for name in ('settings.json','settings.local.json'): add(tool/name,'APPROVAL')
        for name in ('settings.json','settings.local.json'): add(workspace/'.claude'/name,'APPROVAL')
    elif host == 'opencode':
        # Versioned native source: project files are reversed upward traversal;
        # .opencode directories retain upward traversal (closest first).
        for name in ('config.json','opencode.json','opencode.jsonc'): add(tool/name,'USER',('mcp',))
        for directory in reversed(directories):
            for name in ('opencode.json','opencode.jsonc'): add(directory/name,'PROJECT',('mcp',))
        for directory in directories:
            for name in ('opencode.json','opencode.jsonc'): add(directory/'.opencode'/name,'PROJECT',('mcp',))
        if tool.parent.name == '.config':
            for name in ('opencode.json','opencode.jsonc'): add(tool.parent.parent/'.opencode'/name,'HOME_DIRECTORY',('mcp',))
    elif host == 'deepseek-harness':
        if not isinstance(profile,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}',profile): raise ConfigError('PROFILE_ID_INVALID')
        add(tool/'profiles'/profile/'cordis.patch.yml','PROFILE')
        add(tool/'cordis.patch.yml','HOME')
        for path in overlays or []:
            path = _path(path)
            if not path.is_relative_to(workspace): raise ConfigError('PROJECT_OVERLAY_BOUNDARY')
            add(path,'OVERLAY')
    else: raise ConfigError('UNSUPPORTED_CONFIGURATION_HOST')
    if len(rows)>64: raise ConfigError('CONFIGURATION_FILE_BUDGET')
    return rows


def subtree(data, pointer):
    for key in pointer:
        if not isinstance(data,dict): raise ConfigError('INVALID_MCP_SECTION')
        data=data.get(key,{})
    if not isinstance(data,dict): raise ConfigError('INVALID_MCP_SECTION')
    return data


def cordis_targets(data):
    """Known flat MCP insertions and ID overrides; includes/groups stay unobserved."""
    if not isinstance(data,list): raise ConfigError('UNSUPPORTED_CONFIGURATION_FORMAT')
    for index, patch in enumerate(data):
        if not isinstance(patch,dict): raise ConfigError('INVALID_CORDIS_PATCH')
        if 'id' in patch and ('config' in patch or 'disabled' in patch):
            yield patch.get('id'), patch.get('name'), patch.get('config'), (index,'config') if 'config' in patch else None, patch.get('disabled'), (index,)
        inserted=patch.get('insert',[])
        if not isinstance(inserted,list): raise ConfigError('INVALID_CORDIS_INSERT')
        for number,row in enumerate(inserted):
            if not isinstance(row,dict): raise ConfigError('INVALID_CORDIS_INSERT')
            if row.get('name')=='@deepseek-ai/dsh-mcp-client':
                yield row.get('id'),row['name'],row.get('config',{}),(index,'insert',number,'config'),row.get('disabled'),(index,'insert',number)


def resolve_layers(host, tool_root, workspace, *, profile='desktop', overlays=None, overrides=None):
    host=HOSTS.get(host,host); layers=locations(host,tool_root,workspace,profile=profile,overlays=overlays)
    entries={};ids={};guards={};read={};unknown_ids=[];disabled=[];baselines={}
    for layer in layers:
        path=Path(layer['path']);raw=_read(path) if path.exists() else None
        guards[str(path)]=hashlib.sha256(raw).hexdigest().upper() if raw is not None else 'MISSING'
        if raw is None: continue
        read[str(path)]=raw;data=_document(host,(overrides or {}).get(str(path),raw))
        if host=='claude' and layer['scope']=='LOCAL':
            local=subtree(data,layer['pointer'][:-1])
            values=local.get('disabledMcpServers',[])
            if not isinstance(values,list) or any(not isinstance(v,str) for v in values):raise ConfigError('INVALID_MCP_APPROVAL_SETTING')
            disabled+=values
        if layer['scope']=='APPROVAL':
            for key in ('disabledMcpServers','disabledMcpjsonServers'):
                values=data.get(key,[])
                if not isinstance(values,list) or any(not isinstance(v,str) for v in values): raise ConfigError('INVALID_MCP_APPROVAL_SETTING')
                disabled+=values
            continue
        if host=='deepseek-harness':
            for identity,name,entry,pointer,is_disabled,row_pointer in cordis_targets(data):
                if name is None and identity not in ids:
                    unknown_ids.append(str(identity));continue
                if name is not None and name!='@deepseek-ai/dsh-mcp-client': continue
                if entry is None and identity in ids:
                    previous=copy.deepcopy(ids[identity]);previous['disabled']=is_disabled
                    previous.update(path=layer['path'],scope=layer['scope'],pointer=None,row_pointer=list(row_pointer))
                    ids[identity]=previous;server=previous['entry'].get('serverName',identity)
                    if _malts(server,previous['entry']):entries[server]=previous
                    continue
                if not isinstance(entry,dict) or dynamic(entry): raise ConfigError('DYNAMIC_OR_INVALID_MCP_ENTRY')
                if name is None:
                    previous=ids[identity];entries.pop(previous['entry'].get('serverName',identity),None)
                    if is_disabled is None:is_disabled=previous.get('disabled')
                row={**layer,'pointer':list(pointer),'row_pointer':list(row_pointer),'entry':copy.deepcopy(entry),'plugin_id':identity,'disabled':is_disabled,'requires_explicit_overlay':layer['scope']=='OVERLAY'}
                server=entry.get('serverName',identity)
                if not isinstance(server,str): raise ConfigError('DYNAMIC_MCP_SERVER_NAME')
                if identity is not None: ids[identity]=row
                if _malts(server,entry): entries[server]=row
        else:
            for name,entry in subtree(data,layer['pointer']).items():
                if not (_malts(name,entry) or name in entries): continue
                if not isinstance(entry,dict): raise ConfigError('INVALID_MCP_ENTRY')
                previous=entries.get(name,{}).get('entry',{})
                entries[name]={**layer,'pointer':[*layer['pointer'],name],'entry':copy.deepcopy(entry) if host=='claude' else merge(previous,entry)}
        if layer['scope'] in ('USER','PROFILE'):
            baselines={name:copy.deepcopy(row) for name,row in entries.items() if row['scope'] in ('USER','PROFILE')}
    for name,row in entries.items():
        if name in disabled: row['disabled']=True
    if any(_read(Path(path))!=raw for path,raw in read.items()): raise ConfigError('CONFIGURATION_CHANGED_DURING_CHECK')
    return {'host':host,'layers':layers,'guards':guards,'entries':entries,'baselines':baselines,'unknown_patch_ids':unknown_ids,'profile':profile if host=='deepseek-harness' else None}


def dynamic(value):
    if isinstance(value,dict):return '__malts_opaque_native_js__' in value or any(dynamic(v) for v in value.values())
    if isinstance(value,list):return any(dynamic(v) for v in value)
    return False


def configuration_advisory(host,tool_root,workspace,name,row,*,lifecycle_root,resolved,enabled,status,overlays=None,overrides=None):
    """Facts and a read-only edit preview; never execution authority or a plan."""
    baseline=resolved['baselines'].get(name)
    baseline_scopes={'USER','PROFILE'}
    shadowed=baseline is not None and row['scope'] not in baseline_scopes
    management='NOT_MANAGED';managed=False
    if name=='malts' and row['scope'] in baseline_scopes:
        management='UNVERIFIED';managed=None
        try:
            from mcp_host_config import fingerprint,owned_entry,owned_bytes
            if lifecycle_root is None:raise ConfigError('INSTALLATION_IDENTITY_UNAVAILABLE')
            ledger=_document('claude',_read(_path(lifecycle_root)/'runtime/mcp/installation.json'))
            if ledger.get('profile')!='malts.required-mcp.v1' or ledger.get('state')!='READY':raise ConfigError('INSTALLATION_RECORD_UNVERIFIED')
            records=ledger.get('configurations',[])
            if not isinstance(records,list) or len(records)>64:raise ConfigError('INSTALLATION_RECORD_BUDGET')
            selected=[r for r in records if isinstance(r,dict) and HOSTS.get(r.get('host'),r.get('host'))==host and _same(r.get('path',''),row['path'])]
            if len(selected)>1:raise ConfigError('INSTALLATION_RECORD_AMBIGUOUS')
            managed=False;management='NOT_MANAGED'
            if selected:
                raw=_read(row['path'])
                proposed=(overrides or {}).get(row['path'],raw)
                owned=owned_entry(host,_document(host,proposed));record=selected[0]
                managed=(hashlib.sha256(raw).hexdigest().upper()==resolved['guards'][row['path']] and owned==row['entry'] and
                         fingerprint(owned)==record.get('entry_sha256') and hashlib.sha256(owned_bytes(host,proposed)).hexdigest().upper()==record.get('managed_bytes_sha256'))
                management='VERIFIED' if managed else 'DRIFT'
        except Exception:management='UNVERIFIED';managed=None
    availability={'available':False,'reason':'NO_STANDARD_BASELINE','requires_explicit_plan':True}
    if row['scope'] in baseline_scopes:availability['reason']='ALREADY_IN_BASELINE_SCOPE'
    elif not enabled or status!='CURRENT':availability['reason']='ENTRY_NOT_CURRENT_AND_ENABLED'
    elif name!='malts':availability['reason']='PROJECT_SPECIAL_POLICY_REQUIRES_RETENTION'
    elif shadowed:
        try:
            from mcp_project_ops import materials
            # This reuses the real edit strategy's binding, enabled baseline,
            # policy, preserving editor and prospective-resolution guards.
            # No cipher/plan/journal is generated and no file is written.
            plan={'host':host,'lifecycle_root':lifecycle_root,'tool_root':tool_root,'workspace':workspace,'config_path':row['path'],
                  'strategy':'inherit-global','server_name':name,'profile_name':resolved['profile'] or 'desktop','overlays':overlays or []}
            observed,after=materials(plan,document_overrides=overrides)
            if observed['guards']!=resolved['guards']:raise ConfigError('PROJECT_CONFIGURATION_CHANGED_DURING_CHECK')
            availability.update(available=bool(after),reason='PREVIEW_ELIGIBLE' if after else 'NO_CHANGE_REQUIRED')
        except ConfigError as exc:availability['reason']=str(exc)
        except Exception:availability['reason']='INHERITANCE_NOT_VERIFIED'
    if managed and enabled and status=='CURRENT':recommendation='KEEP_INSTALLER_MANAGED_ENTRY'
    elif management=='DRIFT':recommendation='REVIEW_INSTALLER_MANAGED_ENTRY'
    elif availability['available']:recommendation='REVIEW_INHERIT_GLOBAL_OR_KEEP_PROJECT_POLICY'
    elif endpoint_kind(_launch(host,row['entry']))=='STANDARD_STABLE' and row['scope'] in baseline_scopes and enabled and status=='CURRENT':recommendation='USE_STANDARD_WORKSPACE_REQUESTS'
    else:recommendation='KEEP_PROJECT_POLICY'
    return {'global_entry_shadowed':shadowed,'baseline_source':{'scope':baseline['scope'],'path':baseline['path']} if baseline else None,
            'installation_managed':managed,'management_status':management,'inherit_global':availability,'recommendation':recommendation}


def effective_rows(host,tool_root,workspace,*,lifecycle_root=None,profile='desktop',overlays=None,overrides=None):
    host=HOSTS.get(host,host)
    try:
        resolved=resolve_layers(host,tool_root,workspace,profile=profile,overlays=overlays,overrides=overrides)
        rows=[]
        for name,row in resolved['entries'].items():
            entry=row['entry'];values=_launch(host,entry);status,identity,_=_generation(values['script'],lifecycle_root);issues,_=_binding(values)
            disabled=row.get('disabled',False)
            if disabled is None:disabled=False
            if type(disabled) is not bool: raise ConfigError('DYNAMIC_MCP_DISABLED_VALUE')
            enabled=entry.get('enabled',entry.get('disabled') is not True) and not disabled
            if type(enabled) is not bool: raise ConfigError('DYNAMIC_MCP_ENABLED_VALUE')
            unknown=['Host session/reload','CLI/environment overrides','managed policy','trust/approval']
            if host=='deepseek-harness': unknown+=['bundle patches','native groups/includes','unmatched patch IDs']; scope='CHECKED_NATIVE_PATCH_LAYERS'
            else: scope='CHECKED_DISK_LAYERS_IF_PROJECT_TRUSTED'
            policy_env=entry.get('env',entry.get('environment',{}))
            observed_status='DISABLED' if not enabled else 'INVALID' if issues else status
            advisory=configuration_advisory(host,tool_root,workspace,name,row,lifecycle_root=lifecycle_root,resolved=resolved,enabled=enabled,status=observed_status,overlays=overlays,overrides=overrides)
            rows.append({'host':host,'workspace':str(workspace),'server_name':name,'source':row['scope'],'source_path':row['path'],'checked_layers':list(resolved['guards']),
                'status':observed_status,'generation_id':identity,'endpoint_kind':endpoint_kind(values),'enabled':enabled,
                'issues':issues,'entry_sha256':hashlib.sha256(json.dumps(entry,sort_keys=True).encode()).hexdigest(),
                'policy':{'write_enabled':values.get('enable-write',False),'protected_capture':values.get('allow-protected-input-capture',False),'environment_keys':sorted(policy_env) if isinstance(policy_env,dict) else []},
                'host_session_connection':'NOT_VERIFIED','resolution_scope':scope,'unchecked_layers':unknown,**advisory})
        return rows or [{'host':host,'workspace':str(workspace),'status':'NOT_CONFIGURED','host_session_connection':'NOT_VERIFIED'}]
    except Exception as exc:
        return [{'host':host,'workspace':str(workspace),'status':'NOT_VERIFIED','reason':str(exc) if isinstance(exc,ConfigError) else 'PROJECT_CONFIGURATION_CHECK_FAILED','host_session_connection':'NOT_VERIFIED'}]
