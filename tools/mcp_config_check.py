"""Bounded, read-only inspection of host-owned MALTS MCP configuration.

Never execute configured commands, modify host files, or infer execution authority.
JSON/TOML use the standard library. Block YAML requires optional PyYAML; absent
support is reported, not silently accepted. Only MALTS entries enter reports.
"""
import hashlib
import json
import os
import re
import sqlite3
import tomllib
from pathlib import Path
from contextlib import closing
from v2_evidence import _regular_path

HOSTS={'codex':'codex','claude':'claude','claude-code':'claude','opencode':'opencode','deepseek-harness':'deepseek-harness'}
MAX_BYTES=1048576
MAX_FILES=64


class ConfigError(ValueError):
    pass


def _path(value):
    if not isinstance(value,(str,Path)) or not str(value) or str(value).startswith(('\\\\','//')):
        raise ConfigError('LOCAL_ABSOLUTE_PATH_REQUIRED')
    path=Path(value)
    if not path.is_absolute():raise ConfigError('LOCAL_ABSOLUTE_PATH_REQUIRED')
    _regular_path(path)
    return path


def _same(left,right):
    return os.path.normcase(os.path.normpath(str(left)))==os.path.normcase(os.path.normpath(str(right)))


def _pairs(items):
    result={}
    for key,value in items:
        if key in result:raise ConfigError('DUPLICATE_CONFIGURATION_KEY')
        result[key]=value
    return result


def _read(path):
    path=_path(path)
    with path.open('rb') as stream:raw=stream.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ConfigError('CONFIGURATION_BYTE_BUDGET')
    return raw


def _json(text):
    return json.loads(text,object_pairs_hook=_pairs,parse_constant=lambda _: (_ for _ in ()).throw(ConfigError('NONFINITE_CONFIGURATION_VALUE')))


def _document(host,raw):
    text=raw.decode('utf-8-sig')
    if host=='codex':return tomllib.loads(text)
    # A generated Cordis JSON fragment may have standalone YAML comments.
    json_text='\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#')) if host=='deepseek-harness' else text
    try:return _json(json_text)
    except json.JSONDecodeError:
        if host=='opencode':
            # Preserve quoted strings while stripping JSONC comments/trailing commas.
            strings=r'"(?:\\.|[^"\\])*"'
            cleaned=re.sub(strings+r'|//[^\r\n]*|/\*[\s\S]*?\*/',lambda m:m.group(0) if m.group(0).startswith('"') else ' ',text)
            cleaned=re.sub(strings+r'|,(?=\s*[}\]])',lambda m:m.group(0) if m.group(0).startswith('"') else '',cleaned)
            try:return _json(cleaned)
            except json.JSONDecodeError:raise ConfigError('UNSUPPORTED_CONFIGURATION_FORMAT') from None
        if host!='deepseek-harness':raise ConfigError('UNSUPPORTED_CONFIGURATION_FORMAT')
    try:import yaml
    except ImportError:raise ConfigError('YAML_PARSER_UNAVAILABLE') from None
    # Reject aliases/anchors/tags and excessive nesting before constructing data.
    depth=count=0
    for event in yaml.parse(text):
        count+=1
        if count>10000:raise ConfigError('CONFIGURATION_NODE_BUDGET')
        if isinstance(event,yaml.events.AliasEvent) or getattr(event,'anchor',None) or getattr(event,'tag',None) not in (None,'tag:yaml.org,2002:js'):
            raise ConfigError('UNSUPPORTED_YAML_REFERENCE_OR_TAG')
        if isinstance(event,(yaml.events.SequenceStartEvent,yaml.events.MappingStartEvent)):depth+=1
        if isinstance(event,(yaml.events.SequenceEndEvent,yaml.events.MappingEndEvent)):depth-=1
        if depth>32:raise ConfigError('CONFIGURATION_DEPTH_BUDGET')
    class Loader(yaml.SafeLoader):pass
    def mapping(loader,node):
        return _pairs([(loader.construct_object(k),loader.construct_object(v)) for k,v in node.value])
    Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,mapping)
    # Preserve native expressions as inert data. No expression is evaluated;
    # dynamic MALTS command/binding fields remain invalid at their consumers.
    Loader.add_constructor('tag:yaml.org,2002:js',lambda loader,node: {'__malts_opaque_native_js__':loader.construct_scalar(node)})
    return yaml.load(text,Loader=Loader)


def _entries(host,data):
    if host=='deepseek-harness':
        if not isinstance(data,list):raise ConfigError('UNSUPPORTED_CONFIGURATION_FORMAT')
        for patch in data:
            if not isinstance(patch,dict):raise ConfigError('UNSUPPORTED_CONFIGURATION_FORMAT')
            config=patch.get('config')
            if isinstance(config,dict) and _malts(config.get('serverName',patch.get('id','')),config):
                # An explicit ID patch can carry the only live generation
                # reference in this file, even without an insertion row.
                yield config.get('serverName',patch.get('id','')),config
            inserted=patch.get('insert',[])
            if not isinstance(inserted,list):raise ConfigError('INVALID_CORDIS_INSERT')
            for row in inserted:
                if isinstance(row,dict) and row.get('name')=='@deepseek-ai/dsh-mcp-client':
                    config=row.get('config',{})
                    if not isinstance(config,dict):raise ConfigError('INVALID_MCP_ENTRY')
                    yield config.get('serverName',row.get('id','')),config
    else:
        if not isinstance(data,dict):raise ConfigError('UNSUPPORTED_CONFIGURATION_FORMAT')
        key={'codex':'mcp_servers','claude':'mcpServers','opencode':'mcp'}[host]
        surfaces=[data]
        # Embedded Claude local entries require a selected workspace and native
        # precedence. They are resolved by mcp_layers, never flattened across
        # unrelated projects into this file-only comparison.
        for surface in surfaces:
            entries=surface.get(key,{})
            if not isinstance(entries,dict):raise ConfigError('INVALID_MCP_SECTION')
            yield from entries.items()


def _launch(host,entry):
    if not isinstance(entry,dict):raise ConfigError('INVALID_MCP_ENTRY')
    if host=='opencode':
        command=entry.get('command',[])
        if not isinstance(command,list) or not command:raise ConfigError('INVALID_MCP_COMMAND')
        executable,args=command[0],command[1:]
    else:executable,args=entry.get('command'),entry.get('args',[])
    if not isinstance(executable,str) or not isinstance(args,list) or any(not isinstance(v,str) for v in args):
        raise ConfigError('INVALID_MCP_COMMAND')
    if len(args)>64:raise ConfigError('MCP_ARGUMENT_BUDGET')
    indexes=[i for i,v in enumerate(args) if Path(v).name in {'v2_mcp.py','mcp_launcher.py'}]
    if len(indexes)!=1:raise ConfigError('MALTS_SCRIPT_ARGUMENT_MISSING_OR_AMBIGUOUS')
    index=indexes[0];values={'script':args[index],'command':executable}
    value_flags={'state-dir','resource-root','project-id','tool-root','actor','authority-ref','task-id','task-revision','dispatch-id','workflow-topic'}
    switches={'enable-write','allow-protected-input-capture','project-bound'}
    i=index+1
    while i<len(args):
        token=args[i]
        if not token.startswith('--'):raise ConfigError('INVALID_MALTS_ARGUMENTS')
        name=token[2:];value=None
        if '=' in name:name,value=name.split('=',1)
        if name in values or name not in value_flags|switches:raise ConfigError('INVALID_MALTS_ARGUMENTS')
        if name in switches:
            if value is not None:raise ConfigError('INVALID_MALTS_ARGUMENTS')
            values[name]=True
        else:
            if value is None:
                i+=1
                if i>=len(args) or args[i].startswith('--'):raise ConfigError('INVALID_MALTS_ARGUMENTS')
                value=args[i]
            values[name]=value
        i+=1
    if Path(values['script']).name=='mcp_launcher.py' and not values.get('project-bound'):
        if set(values)!={'script','command','tool-root'}:raise ConfigError('INSTALLED_MCP_ARGUMENT_INVALID')
    elif any(k not in values for k in ('state-dir','resource-root','project-id')):raise ConfigError('MALTS_BINDING_ARGUMENT_MISSING')
    return values


def _generation(script,lifecycle_root):
    script=_path(script)
    if script.name=='mcp_launcher.py':
        lifecycle=_path(lifecycle_root) if lifecycle_root is not None else script.parent.parent.parent
        if not _same(script,lifecycle/'runtime/mcp/mcp_launcher.py'):return 'LAUNCHER_LOCATION_INVALID',None,None
        try:
            ledger=_json(_read(lifecycle/'runtime/mcp/installation.json').decode('utf-8-sig'))
            registry=_json(_read(lifecycle/'registry/installation_registry.json').decode('utf-8-sig'))
            if ledger.get('profile')!='malts.required-mcp.v1' or hashlib.sha256(_read(script)).hexdigest().upper()!=ledger['launcher_sha256']:
                return 'LAUNCHER_UNVERIFIED',None,None
            active=[r for r in registry['generations'] if r['state']=='active']
            if len(active)!=1 or registry['lifecycle_state']!='stable':return 'GENERATION_UNVERIFIED',None,None
            return 'CURRENT',active[0]['generation_id'],script
        except (OSError,ValueError,KeyError):return 'LAUNCHER_UNVERIFIED',None,None
    root=script.parent.parent
    lifecycle=_path(lifecycle_root) if lifecycle_root is not None else root.parent.parent
    try:registry=_json(_read(lifecycle/'registry/installation_registry.json').decode('utf-8-sig'))
    except (OSError,ValueError):return ('SCRIPT_MISSING' if not script.is_file() else 'GENERATION_UNVERIFIED'),None,None
    active=registry.get('active_generation_id')
    active_rows=[r for r in registry.get('generations',[]) if r.get('generation_id')==active and r.get('state')=='active']
    current=Path(active_rows[0]['root'])/'tools/v2_mcp.py' if len(active_rows)==1 else None
    if not script.is_file():return 'SCRIPT_MISSING',None,current
    records=[r for r in registry.get('generations',[]) if _same(r.get('root',''),root)]
    if len(records)!=1 or records[0].get('state') not in {'active','retiring'}:
        return 'GENERATION_UNREGISTERED',None,current
    record=records[0];identity=record.get('generation_id')
    if identity!=root.name or not _same(root,lifecycle/'generations'/identity):return 'GENERATION_BINDING_INVALID',None,None
    version=_read(root/'VERSION').decode('utf-8-sig').strip()
    if version!=record.get('version'):return 'GENERATION_VERSION_MISMATCH',identity,None
    return ('CURRENT' if identity==active else 'VALID_OLDER_GENERATION'),identity,current


def _binding(values):
    if Path(values['script']).name=='mcp_launcher.py' and not values.get('project-bound'):
        try:
            from malts_lifecycle import resolve_discovery
            resolve_discovery(values['tool-root'])
            return [],{}
        except Exception:return ['INSTALLED_MCP_DISCOVERY_FAILED'],{}
    state=_path(values['state-dir']);resource=_path(values['resource-root'])
    issues=[];expected={}
    if Path(values['script']).name=='mcp_launcher.py':
        try:
            from malts_lifecycle import resolve_discovery
            resolve_discovery(values['tool-root'])
        except Exception:issues.append('INSTALLED_MCP_DISCOVERY_FAILED')
    if not resource.is_dir():issues.append('RESOURCE_ROOT_MISSING')
    if not state.is_dir():issues.append('STATE_DIRECTORY_MISSING')
    db=state/'state.db';_regular_path(db)
    if not db.is_file():issues.append('STATE_DATABASE_MISSING')
    else:
        try:
            with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=1)) as connection:
                rows=connection.execute('SELECT project_id,resource_root FROM project LIMIT 2').fetchall()
            if len(rows)!=1 or rows[0][0]!=values['project-id'] or not _same(rows[0][1],resource):
                issues.append('PROJECT_BINDING_MISMATCH')
        except sqlite3.Error:issues.append('STATE_DATABASE_UNVERIFIED')
    for locator in (resource/'runtime/v2_binding.json',resource/'.malts/native.json'):
        _regular_path(locator)
        if locator.is_file():
            try:
                binding=_json(_read(locator).decode('utf-8-sig'))
                target=binding.get('state_dir')
                if not isinstance(target,str):raise ConfigError('INVALID_WORKSPACE_LOCATOR')
                if not _same(target,state):
                    issues.append('WORKSPACE_STATE_BINDING_STALE');expected['state-dir']=target
            except (OSError,ValueError):issues.append('WORKSPACE_BINDING_UNVERIFIED')
    return issues,expected


def _malts(name,entry):
    if isinstance(name,str) and name.lower().startswith('malts'):return True
    if not isinstance(entry,dict):return False
    args=entry.get('args',[])
    return (isinstance(args,list) and any(isinstance(v,str) and Path(v).name in {'v2_mcp.py','mcp_launcher.py'} for v in args)) or (
        isinstance(entry.get('command'),list) and any(isinstance(v,str) and Path(v).name in {'v2_mcp.py','mcp_launcher.py'} for v in entry['command']))


def inspect_configuration(*,host,config_path,lifecycle_root=None,expected=None,server_name=None,tool_root=None,replacements=None,check_interpreter=False):
    host=HOSTS.get(host,host)
    if host not in HOSTS.values():raise ValueError('Unsupported configuration host')
    report={'host':host,'path':str(config_path),'status':'NOT_CONFIGURED','entries':[],'sha256':None}
    try:
        path=_path(config_path)
        if not path.exists():return report
        raw=_read(path);report['sha256']=hashlib.sha256(raw).hexdigest()
        entries=list(_entries(host,_document(host,raw)))
        if len(entries)>256:raise ConfigError('MCP_ENTRY_BUDGET')
        selected=[(n,e) for n,e in entries if (n==server_name if server_name is not None else _malts(n,e))]
        if len(selected)>64:raise ConfigError('MALTS_ENTRY_BUDGET')
        if server_name is not None and len(selected)>1:raise ConfigError('MALTS_ENTRY_AMBIGUOUS')
        desired=_launch(host,expected) if expected is not None else None
        for name,entry in selected:
            item={'server_name':name,'status':'CURRENT','issues':[],'differences':[]}
            report['entries'].append(item)
            try:
                values=_launch(host,entry)
                generation,identity,current=_generation(values['script'],lifecycle_root)
                issues,corrections=_binding(values)
                if Path(values['command']).is_absolute() and not _path(values['command']).is_file():issues.append('PYTHON_EXECUTABLE_MISSING')
                if generation not in {'CURRENT','VALID_OLDER_GENERATION'}:issues.append(generation)
                if generation=='VALID_OLDER_GENERATION':item['status']='VALID_OLDER_GENERATION'
                if current is not None:corrections['script']=str(current)
                for old,new in (replacements or {}).items():
                    if 'state-dir' in values and _same(values['state-dir'],old) and not _same(old,new):
                        corrections['state-dir']=str(new);issues.append('STATE_RELOCATED')
                if desired:
                    fields=('script','state-dir','resource-root','project-id','tool-root','task-id','task-revision','dispatch-id','workflow-topic','enable-write','allow-protected-input-capture','actor','authority-ref')
                    if check_interpreter:fields+=('command',)
                    for field in fields:
                        before=values.get(field);after=desired.get(field)
                        equivalent=_same(before,after) if field in {'script','state-dir','resource-root','tool-root'} and before is not None and after is not None else before==after
                        if not equivalent:item['differences'].append({'field':field,'observed':'REDACTED' if field in {'actor','authority-ref'} else before,'expected':'REDACTED' if field in {'actor','authority-ref'} else after})
                item['issues']=list(dict.fromkeys(issues))
                item['generation_id']=identity
                item['endpoint_kind']=endpoint_kind(values)
                item['enabled']=entry.get('enabled',entry.get('disabled') is not True)
                item['policy']={'write_enabled':values.get('enable-write',False),'protected_capture':values.get('allow-protected-input-capture',False),'environment_keys':sorted(entry.get('env',entry.get('environment',{}))) if isinstance(entry.get('env',entry.get('environment',{})),dict) else []}
                item['binding']={key:values[key] for key in ('script','state-dir','resource-root','project-id','tool-root') if key in values}
                item['suggested_values']=corrections
                if issues:item['status']='INVALID'
                elif item['differences']:item['status']='DIFFERENT'
                if issues or item['differences'] or generation=='VALID_OLDER_GENERATION':
                    script=current or (Path(lifecycle_root)/'generations'/ '<active-generation>'/'tools/v2_mcp.py' if lifecycle_root else None)
                    if script is not None and Path(values['script']).name!='mcp_launcher.py':
                        argv=['python','-B',str(script.with_name('malts_v2.py')),'mcp-config','--host',host,'--state-dir',corrections.get('state-dir',values['state-dir']),'--resource-root',values['resource-root'],'--project-id',values['project-id'],'--server-name',str(name)]
                        if tool_root is not None:argv+=['--tool-root',str(tool_root)]
                        item['regeneration_arguments']=argv
                        item['regeneration_note']='Review the generated fragment; preserve the selected Python interpreter and explicit Host authority policy. No registration or permission is applied.'
            except Exception as exc:
                partial=host=='codex' and path.parent.name=='.codex' and isinstance(entry,dict) and 'args' not in entry
                item.update(status='PARTIAL_PROJECT_LAYER' if partial else 'CHECK_FAILED',issues=[] if partial else [str(exc) if isinstance(exc,ConfigError) else 'ENTRY_CHECK_FAILED'])
        if _read(path)!=raw:raise ConfigError('CONFIGURATION_CHANGED_DURING_CHECK')
        statuses={row['status'] for row in report['entries']}
        report['status']=('CHECK_FAILED' if 'CHECK_FAILED' in statuses else 'INVALID' if 'INVALID' in statuses else 'DIFFERENT' if 'DIFFERENT' in statuses else 'VALID_OLDER_GENERATION' if 'VALID_OLDER_GENERATION' in statuses else 'CURRENT' if statuses else 'NOT_CONFIGURED')
    except Exception as exc:
        code=str(exc) if isinstance(exc,ConfigError) else 'CONFIGURATION_READ_OR_PARSE_FAILED'
        report.update(status='UNSUPPORTED' if code in {'UNSUPPORTED_CONFIGURATION_FORMAT','YAML_PARSER_UNAVAILABLE','UNSUPPORTED_YAML_REFERENCE_OR_TAG'} else 'CHECK_FAILED',reason=code)
    return report


def configuration_locations(tool_roots):
    locations=[]
    for tool,value in tool_roots.items():
        host=HOSTS.get(tool)
        if host is None:continue
        root=_path(value)
        if host=='codex':paths=[root/'config.toml']
        elif host=='claude':paths=[root.parent/'.claude.json',root/'mcp.json']
        elif host=='opencode':paths=[root/'opencode.json',root/'opencode.jsonc']
        else:
            profiles=root/'profiles';_regular_path(profiles)
            paths=[]
            if profiles.is_dir():
                children=sorted(profiles.iterdir())
                if len(children)>32:raise ConfigError('PROFILE_ENTRY_BUDGET')
                for child in children:
                    _regular_path(child)
                    if child.is_dir():paths.append(child/'cordis.patch.yml')
        locations.extend((host,path,root) for path in paths)
    return locations


def endpoint_kind(values):
    if Path(values['script']).name=='v2_mcp.py':return 'PROJECT_BOUND_VERSIONED'
    return 'PROJECT_BOUND_STABLE' if values.get('project-bound') else 'STANDARD_STABLE'


def _codex_project_configuration_locations(workspaces,tool_roots):
    """Inspect only the selected directories and bounded ancestor names, never recurse."""
    locations=[]
    if 'codex' not in tool_roots:return locations
    for value in workspaces or []:
        workspace=_path(value)
        if not workspace.is_dir():raise ConfigError('WORKSPACE_DIRECTORY_REQUIRED')
        # Codex scans from the project root through cwd. A missing VCS marker
        # leaves the selected workspace as our boundary; disclose other layers.
        ancestors=[workspace,*workspace.parents]
        if len(ancestors)>64:raise ConfigError('PROJECT_LAYER_DEPTH_BUDGET')
        project=next((p for p in ancestors if (p/'.git').exists()),workspace)
        selected=[]
        for path in ancestors:
            selected.append(path)
            if path==project:break
        for path in reversed(selected):locations.append(('codex',path/'.codex/config.toml',Path(tool_roots['codex'])))
    return locations


def _codex_effective_configurations(tool_roots,*,lifecycle_root=None,config_files=None,workspaces=None,document_overrides=None):
    import copy
    roots=[_path(p) for p in workspaces or []]
    roots += [Path(p).parent.parent for h,p in config_files or [] if HOSTS.get(h)=='codex' and Path(p).parent.name=='.codex' and not _same(Path(p),Path(tool_roots.get('codex',''))/'config.toml')]
    rows=[];seen=set()
    for workspace in roots:
        if str(workspace) in seen:continue
        seen.add(str(workspace))
        if 'codex' not in tool_roots:continue
        layers=[Path(tool_roots['codex'])/'config.toml']+[p for _,p,_ in _codex_project_configuration_locations([workspace],tool_roots)]
        layers=list(dict.fromkeys(layers));merged={};sources={};global_names=set();read=[]
        def merge(left,right):
            result=copy.deepcopy(left)
            for k,v in right.items():result[k]=merge(result[k],v) if k in result and isinstance(result[k],dict) and isinstance(v,dict) else copy.deepcopy(v)
            return result
        try:
            for index,path in enumerate(layers):
                if not path.exists():continue
                raw=_read(path);read.append((path,raw))
                proposed=(document_overrides or {}).get(str(path),raw)
                data=_document('codex',proposed)
                entries=data.get('mcp_servers',{})
                if not isinstance(entries,dict):raise ConfigError('INVALID_MCP_SECTION')
                if index==0:global_names=set(entries)
                for name,entry in entries.items():
                    if _malts(name,entry) or name in merged:
                        if not isinstance(entry,dict):raise ConfigError('INVALID_MCP_ENTRY')
                        merged[name]=merge(merged.get(name,{}),entry);sources[name]=path
            if any(_read(path)!=raw for path,raw in read):raise ConfigError('CONFIGURATION_CHANGED_DURING_CHECK')
            if not merged:rows.append({'host':'codex','workspace':str(workspace),'status':'NOT_CONFIGURED','host_session_connection':'NOT_VERIFIED'})
            for name,entry in merged.items():
                values=_launch('codex',entry);status,identity,_=_generation(values['script'],lifecycle_root)
                issues,_=_binding(values);enabled=entry.get('enabled',True)
                source='USER' if _same(sources[name],layers[0]) else 'PROJECT'
                rows.append({'host':'codex','workspace':str(workspace),'server_name':name,'source':source,'source_path':str(sources[name]),'checked_layers':[str(p) for p,_ in read],
                    'status':'DISABLED' if enabled is False else 'INVALID' if issues else status,'generation_id':identity,'endpoint_kind':endpoint_kind(values),'enabled':enabled,
                    'global_entry_shadowed':source=='PROJECT' and name in global_names,'issues':issues,'entry_sha256':hashlib.sha256(json.dumps(entry,sort_keys=True).encode()).hexdigest(),
                    'policy':{'write_enabled':values.get('enable-write',False),'protected_capture':values.get('allow-protected-input-capture',False),'environment_keys':sorted(entry.get('env',{})) if isinstance(entry.get('env',{}),dict) else []},
                    'host_session_connection':'NOT_VERIFIED','resolution_scope':'CHECKED_DISK_LAYERS_IF_PROJECT_TRUSTED','unchecked_layers':['Profile','CLI overrides','managed requirements','project trust/session loading'],
                    'recommendation':'REVIEW_INHERIT_GLOBAL_OR_KEEP_PROJECT_POLICY' if source=='PROJECT' else 'USE_STANDARD_WORKSPACE_REQUESTS' if endpoint_kind(values)=='STANDARD_STABLE' else 'KEEP_PROJECT_POLICY'})
        except Exception as exc:
            rows.append({'host':'codex','workspace':str(workspace),'status':'NOT_VERIFIED','reason':str(exc) if isinstance(exc,ConfigError) else 'PROJECT_CONFIGURATION_CHECK_FAILED','host_session_connection':'NOT_VERIFIED'})
    return rows


def project_configuration_locations(workspaces,tool_roots):
    from mcp_layers import locations
    rows=[]
    for host,tool in tool_roots.items():
        canonical=HOSTS.get(host)
        if canonical is None:continue
        for workspace in workspaces or []:
            profiles=['desktop']
            if canonical=='deepseek-harness' and (Path(tool)/'profiles').is_dir():
                profiles=[p.name for p in (Path(tool)/'profiles').iterdir() if p.is_dir()]
                if len(profiles)>32:raise ConfigError('PROFILE_ENTRY_BUDGET')
            for profile in profiles:
                rows.extend((canonical,Path(row['path']),Path(tool)) for row in locations(canonical,tool,workspace,profile=profile))
    return rows


def effective_configurations(tool_roots,*,lifecycle_root=None,config_files=None,workspaces=None,document_overrides=None):
    from mcp_layers import effective_rows
    # Preserve the existing Codex report contract, including explicitly selected
    # project files, while resolving the other native formats independently.
    rows=_codex_effective_configurations(tool_roots,lifecycle_root=lifecycle_root,config_files=config_files,workspaces=workspaces,document_overrides=document_overrides)
    for host,tool in tool_roots.items():
        canonical=HOSTS.get(host)
        if canonical in (None,'codex'):continue
        for workspace in workspaces or []:
            profiles=['desktop']
            if canonical=='deepseek-harness' and (Path(tool)/'profiles').is_dir():profiles=[p.name for p in (Path(tool)/'profiles').iterdir() if p.is_dir()]
            if len(profiles)>32:raise ConfigError('PROFILE_ENTRY_BUDGET')
            for profile in profiles:rows.extend(effective_rows(canonical,tool,workspace,lifecycle_root=lifecycle_root,profile=profile,overrides=document_overrides))
    return rows


def scan_configurations(tool_roots,*,lifecycle_root=None,config_files=None,replacements=None,workspaces=None):
    report={'format':'malts.mcp-configuration-check','mode':'READ_ONLY','writes_performed':False,'execution_authorized':False,'atomic_snapshot':False,'scope':'KNOWN_HOST_LOCATIONS_AND_EXPLICIT_FILES','complete_global_inventory':False,'files':[]}
    try:
        locations=configuration_locations(tool_roots)
        locations+=project_configuration_locations(workspaces,tool_roots)
        for tool,path in config_files or []:
            host=HOSTS.get(tool)
            if host is None:raise ConfigError('UNSUPPORTED_CONFIGURATION_HOST')
            locations.append((host,_path(path),tool_roots.get(tool)))
        if len(locations)>MAX_FILES:raise ConfigError('CONFIGURATION_FILE_BUDGET')
        seen=set()
        for host,path,root in locations:
            key=(host,os.path.normcase(str(path)))
            if key in seen:continue
            seen.add(key)
            report['files'].append(inspect_configuration(host=host,config_path=path,lifecycle_root=lifecycle_root,tool_root=root,replacements=replacements))
        states={r['status'] for r in report['files']}
        report['status']='CHECK_FAILED' if 'CHECK_FAILED' in states else 'DRIFT' if states&{'INVALID','DIFFERENT','VALID_OLDER_GENERATION'} else 'UNVERIFIED' if 'UNSUPPORTED' in states else 'CURRENT' if 'CURRENT' in states else 'NOT_CONFIGURED'
        report['reprojection_required']=[{'host':file['host'],'path':file['path'],'server_name':entry['server_name'],'status':entry['status'],'issues':entry['issues'],'suggested_values':entry.get('suggested_values',{}),'regeneration_arguments':entry.get('regeneration_arguments',[])} for file in report['files'] for entry in file['entries'] if entry['status'] in {'INVALID','DIFFERENT','VALID_OLDER_GENERATION'}]
        report['effective_configuration']=effective_configurations(tool_roots,lifecycle_root=lifecycle_root,config_files=config_files,workspaces=workspaces)
        if report['status']!='CHECK_FAILED' and any(r['status']=='NOT_VERIFIED' for r in report['effective_configuration']):report['status']='UNVERIFIED'
        report['effective_configuration_coverage']={'selected_workspaces':[str(p) for p in workspaces or []],'unsupported_project_hosts':[],'host_session_connection':'NOT_VERIFIED','scope':'SELECTED_NATIVE_HOST_DISK_LAYERS','complete_global_inventory':False}
    except Exception as exc:
        report.update(status='CHECK_FAILED',reason=str(exc) if isinstance(exc,ConfigError) else 'CONFIGURATION_SCAN_FAILED',reprojection_required=[])
    return report


def compare_fragment(generated,*,config_path,lifecycle_root=None,tool_root=None,runtime_root=None,check_interpreter=False):
    host=generated['host'];name=generated['server_name']
    data=tomllib.loads(generated['fragment']) if host=='codex' else generated['fragment']
    entries=[entry for server,entry in _entries(host,data) if server==name]
    if len(entries)!=1:raise ValueError('Generated configuration identity is ambiguous')
    if runtime_root is not None:
        entry=dict(entries[0]);key='command' if host=='opencode' else 'args'
        entry[key]=[str(Path(runtime_root)/'tools/v2_mcp.py') if Path(v).name=='v2_mcp.py' else v for v in entry[key]]
        entries=[entry]
    report=inspect_configuration(host=host,config_path=config_path,lifecycle_root=lifecycle_root,expected=entries[0],server_name=name,tool_root=tool_root,check_interpreter=check_interpreter)
    report.update(format='malts.mcp-configuration-comparison',mode='READ_ONLY',writes_performed=False,execution_authorized=False,host_runtime_connection_verified=False)
    return report


def parse_config_files(values):
    rows=[]
    for value in values:
        tool,separator,path=value.partition('=')
        if not separator or tool not in HOSTS:raise ValueError('Use HOST=ABSOLUTE_CONFIGURATION_PATH')
        rows.append((tool,_path(path)))
    if len(rows)>MAX_FILES:raise ValueError('Select at most 64 configuration files')
    return rows


def lifecycle_reprojection(result,tool_roots,lifecycle_root,config_files=None,workspaces=None):
    # Diagnostic failure after a committed mutation cannot change its outcome.
    output=dict(result)
    output['external_configuration']=scan_configurations(tool_roots,lifecycle_root=lifecycle_root,config_files=config_files,workspaces=workspaces)
    return output


def relocation_reprojection(result,plan,tool_root,config_files=None):
    output=dict(result)
    try:
        from malts_lifecycle import resolve_discovery
        discovery=resolve_discovery(tool_root)
        text=_read(Path(tool_root)/'MALTS_BOOT.md').decode('utf-8-sig')
        labels=re.findall(r'(?m)^Tool:\s*(.*?)\s*$',text)
        tool={'Codex':'codex','Claude Code':'claude-code','OpenCode':'opencode','DeepSeek Harness':'deepseek-harness'}.get(labels[0]) if len(labels)==1 else None
        roots={tool:str(tool_root)} if tool is not None else {}
        output['external_configuration']=scan_configurations(roots,lifecycle_root=discovery['lifecycle_root'],config_files=config_files,replacements={plan['old_state_dir']:plan['state_dir']})
    except Exception:
        output['external_configuration']={'status':'CHECK_FAILED','reason':'POST_RELOCATION_CONFIGURATION_CHECK_FAILED','writes_performed':False,'execution_authorized':False,'complete_global_inventory':False}
    return output
