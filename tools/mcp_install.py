"""Required lifecycle MCP dependency, preserving registration and cold-connection steps."""
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import venv
import copy
import importlib.util
from contextlib import contextmanager
from mcp_config_check import HOSTS,ConfigError,_read,_path
from mcp_host_config import document,owned_entry,owned_bytes,patch,remove,fingerprint

PROFILE='malts.required-mcp.v1'

def digest(raw):return hashlib.sha256(raw).hexdigest().upper()
def read_json(path):return json.loads(_read(path).decode('utf-8-sig'))
def write_json(path,value):
    from malts_lifecycle import write_json as write
    _path(path);write(path,value)
def read_optional(path):
    _path(path)
    return _read(path) if path.exists() else b''
def interpreter(environment):return environment/('Scripts/python.exe' if os.name=='nt' else 'bin/python')

def locations(tool_roots):
    result=[]
    for tool,value in tool_roots.items():
        root=_path(value);host=HOSTS[tool]
        if host=='codex':paths=[root/'config.toml']
        elif host=='claude':paths=[root.parent/'.claude.json']
        elif host=='opencode':
            paths=[p for p in (root/'opencode.json',root/'opencode.jsonc') if p.exists()]
            # OpenCode loads JSON then JSONC and merges them. Keep identical
            # owned entries in both present global layers so updates/uninstall
            # retain ownership rather than orphan a lower-layer registration.
            if not paths:paths=[root/'opencode.json']
        else:
            profiles=root/'profiles';_path(profiles)
            children=sorted(profiles.iterdir()) if profiles.exists() else []
            if len(children)>32:raise ConfigError('PROFILE_ENTRY_BUDGET')
            paths=[]
            for child in children:
                _path(child)
                if child.is_dir():paths.append(child/'cordis.patch.yml')
            if not paths:paths=[profiles/'default'/'cordis.patch.yml']
        result.extend((host,_path(path),root) for path in paths)
    if len({os.path.normcase(str(path)) for _,path,_ in result})!=len(result):raise ConfigError('MCP_CONFIGURATION_PATH_COLLISION')
    return result

def entry_for(host,python,launcher,root):
    args=['-B',str(launcher),'--tool-root',str(root)]
    if host=='opencode':return {'type':'local','command':[str(python),*args],'enabled':True}
    value={'command':str(python),'args':args}
    if host=='codex':value['startup_timeout_sec']=30.0
    if host=='deepseek-harness':
        value={'serverName':'malts','transport':'stdio',**value,'env':{},'cwd':str(root),
               'failOnStartupError':True,'reconnect':{'enabled':True}}
    return value

def make_plan(lifecycle_root,tool_roots,payload_root,operation_id,*,removal=False):
    root=_path(lifecycle_root);payload=_path(payload_root)
    requirement=_read(payload/'tools/v2_mcp_requirements.txt')
    launcher=_read(payload/'tools/mcp_launcher.py')
    runtime=root/'runtime/mcp';ledger_path=runtime/'installation.json'
    ledger=read_json(ledger_path) if ledger_path.exists() else None
    if ledger is not None and ledger.get('profile')!=PROFILE:raise ConfigError('MCP_INSTALLATION_RECORD_INVALID')
    environment=runtime/('env-'+digest(requirement)[:12]);python=interpreter(environment)
    if ledger is not None and (environment/'.malts-mcp-environment.json').is_file() and python.is_file():
        _environment_yaml({'environment':str(environment),'requirements_sha256':digest(requirement)})
    installed_launcher=runtime/'mcp_launcher.py'
    old_records={row['path']:row for row in ledger['configurations']} if ledger and ledger.get('state')!='UNINSTALLED' else {}
    rows=[]
    for host,path,tool_root in locations(tool_roots):
        raw=read_optional(path);old=old_records.get(str(path));deferred=False
        try:current=owned_entry(host,document(host,raw))
        except ConfigError as error:
            if host!='deepseek-harness' or str(error)!='YAML_PARSER_UNAVAILABLE':raise
            current=None;deferred=True
        if old is not None and not deferred:
            if (current is None or fingerprint(current)!=old['entry_sha256'] or
                    digest(owned_bytes(host,raw))!=old.get('managed_bytes_sha256')):
                raise ConfigError('MANAGED_MCP_USER_EDIT_CONFLICT')
        elif current is not None:raise ConfigError('UNOWNED_MCP_ENTRY_CONFLICT')
        desired=entry_for(host,python,installed_launcher,tool_root)
        proposed=None if deferred else remove(host,raw) if removal else patch(host,raw,desired)
        rows.append({'host':host,'path':str(path),'tool_root':str(tool_root),'before_sha256':digest(raw) if path.exists() else 'MISSING',
                     'after_sha256':'DEFERRED_YAML' if deferred else digest(proposed),'entry':desired,'entry_sha256':fingerprint(desired),
                     'managed_bytes_sha256':'DEFERRED_YAML' if deferred else digest(owned_bytes(host,proposed)),
                     'yaml_preparation_deferred':deferred})
    if installed_launcher.exists() and (ledger is None or digest(_read(installed_launcher))!=ledger['launcher_sha256']):
        raise ConfigError('MANAGED_MCP_LAUNCHER_DRIFT')
    return {'profile':PROFILE,'operation_id':operation_id,'lifecycle_root':str(root),
            'tool_roots':{k:str(v) for k,v in tool_roots.items()},'runtime_root':str(runtime),
            'environment':str(environment),'python':str(python),'base_python':str(_path(Path(sys.executable).resolve(strict=True))),
            'requirements_sha256':digest(requirement),'launcher_sha256':digest(launcher),
            'previous_launcher_sha256':digest(read_optional(installed_launcher)) if installed_launcher.exists() else 'MISSING',
            'ledger_sha256':digest(_read(ledger_path)) if ledger_path.exists() else 'MISSING',
            'configurations':rows,'required':True,'write_enabled':False,'removal':removal}

def validate(plan,lifecycle_root,tool_roots,*,operation_id=None,removal=None):
    required={'profile','operation_id','lifecycle_root','tool_roots','runtime_root','environment','python','base_python',
              'requirements_sha256','launcher_sha256','previous_launcher_sha256','ledger_sha256','configurations','required','write_enabled','removal'}
    if set(plan)!=required or plan['profile']!=PROFILE or plan['required'] is not True or plan['write_enabled'] is not False or type(plan['removal']) is not bool:
        raise ConfigError('MCP_PLAN_CONTRACT_INVALID')
    if not isinstance(plan['operation_id'],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',plan['operation_id']):
        raise ConfigError('MCP_OPERATION_ID_INVALID')
    if (operation_id is not None and plan['operation_id']!=operation_id) or (removal is not None and plan['removal'] is not removal):
        raise ConfigError('MCP_OPERATION_BINDING_INVALID')
    root=_path(lifecycle_root);runtime=root/'runtime/mcp'
    if (plan['lifecycle_root']!=str(root) or plan['runtime_root']!=str(runtime) or
        plan['tool_roots']!={k:str(v) for k,v in tool_roots.items()} or
        plan['environment']!=str(runtime/('env-'+plan['requirements_sha256'][:12])) or
        plan['python']!=str(interpreter(Path(plan['environment'])))):
        raise ConfigError('MCP_PLAN_BINDING_INVALID')
    targets=locations(tool_roots)
    if len(plan['configurations'])!=len(targets):raise ConfigError('MCP_PLAN_BINDING_INVALID')
    for row,(host,path,tool_root) in zip(plan['configurations'],targets):
        if (set(row)!={'host','path','tool_root','before_sha256','after_sha256','entry','entry_sha256','managed_bytes_sha256','yaml_preparation_deferred'} or
            row['host']!=host or row['path']!=str(path) or row['tool_root']!=str(tool_root) or
            row['entry']!=entry_for(host,Path(plan['python']),runtime/'mcp_launcher.py',tool_root) or
            row['entry_sha256']!=fingerprint(row['entry'])):raise ConfigError('MCP_PLAN_BINDING_INVALID')
        if (type(row['yaml_preparation_deferred']) is not bool or (row['yaml_preparation_deferred'] and
            (host!='deepseek-harness' or row['after_sha256']!='DEFERRED_YAML' or row['managed_bytes_sha256']!='DEFERRED_YAML'))):
            raise ConfigError('MCP_PLAN_BINDING_INVALID')

def verify_inputs(plan):
    marker=Path(plan['environment'])/'.malts-mcp-environment.json'
    if marker.is_file() and Path(plan['python']).is_file():_environment_yaml(plan)
    for row in plan['configurations']:
        path=Path(row['path']);raw=read_optional(path)
        actual=digest(raw) if path.exists() else 'MISSING'
        if actual!=row['before_sha256']:raise ConfigError('MCP_CONFIGURATION_CHANGED_AFTER_PLAN')
        if row['yaml_preparation_deferred']:continue
        try:proposed=remove(row['host'],raw) if plan['removal'] else patch(row['host'],raw,row['entry'])
        except ConfigError as error:
            if row['host']=='deepseek-harness' and str(error)=='YAML_PARSER_UNAVAILABLE':continue
            raise
        if digest(proposed)!=row['after_sha256']:raise ConfigError('MCP_PLAN_CONTENT_MISMATCH')
    runtime=Path(plan['runtime_root'])
    for path,expected in ((runtime/'installation.json',plan['ledger_sha256']),
                          (runtime/'mcp_launcher.py',plan['previous_launcher_sha256'])):
        if (digest(read_optional(path)) if path.exists() else 'MISSING')!=expected:raise ConfigError('MCP_RUNTIME_CHANGED_AFTER_PLAN')

def _run(command,*,timeout=180):
    result=subprocess.run([str(x) for x in command],capture_output=True,timeout=timeout,
                          env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'})
    if result.returncode:raise ConfigError('MCP_DEPENDENCY_OR_CONNECTION_FAILURE')
    return result.stdout

def _environment_yaml(plan):
    """Load only the managed environment's parser into this installer process.

    The environment was created with the same base interpreter. This affects no
    system/package installation and does not execute .pth files or site hooks.
    """
    if importlib.util.find_spec('yaml') is not None:return
    environment=Path(plan['environment']);marker=read_json(environment/'.malts-mcp-environment.json')
    if marker.get('state')!='READY' or marker.get('requirements_sha256')!=plan['requirements_sha256']:
        raise ConfigError('MCP_YAML_ENVIRONMENT_NOT_READY')
    package=environment/'Lib/site-packages/yaml' if os.name=='nt' else environment/'lib'/('python'+str(sys.version_info.major)+'.'+str(sys.version_info.minor))/'site-packages/yaml'
    _path(package);_path(package/'__init__.py')
    spec=importlib.util.spec_from_file_location('yaml',package/'__init__.py',submodule_search_locations=[str(package)])
    module=importlib.util.module_from_spec(spec);sys.modules['yaml']=module;spec.loader.exec_module(module)

def _resolve_configurations(plan,folder):
    if not any(row['yaml_preparation_deferred'] for row in plan['configurations']):return plan
    _environment_yaml(plan)
    resolved=copy.deepcopy(plan)
    record_path=Path(plan['runtime_root'])/'installation.json'
    ledger=read_json(record_path) if record_path.exists() else None
    records={r['path']:r for r in ledger['configurations']} if ledger and ledger.get('state')!='UNINSTALLED' else {}
    for row in resolved['configurations']:
        if not row['yaml_preparation_deferred']:continue
        path=Path(row['path']);raw=read_optional(path)
        if (digest(raw) if path.exists() else 'MISSING')!=row['before_sha256']:raise ConfigError('MCP_CONFIGURATION_CHANGED_AFTER_PLAN')
        current=owned_entry(row['host'],document(row['host'],raw));old=records.get(row['path'])
        if old is not None:
            if (current is None or fingerprint(current)!=old['entry_sha256'] or digest(owned_bytes(row['host'],raw))!=old['managed_bytes_sha256']):
                raise ConfigError('MANAGED_MCP_USER_EDIT_CONFLICT')
        elif current is not None:raise ConfigError('UNOWNED_MCP_ENTRY_CONFLICT')
        proposed=remove(row['host'],raw) if plan['removal'] else patch(row['host'],raw,row['entry'])
        row['after_sha256']=digest(proposed);row['managed_bytes_sha256']=digest(owned_bytes(row['host'],proposed))
    value={'profile':PROFILE,'operation_id':plan['operation_id'],'plan_sha256':fingerprint(plan),'configurations':resolved['configurations']}
    target=folder/'resolved-configurations.json'
    if target.exists() and read_json(target)!=value:raise ConfigError('MCP_RESOLVED_CONFIGURATION_DRIFT')
    if not target.exists():write_json(target,value)
    return resolved

def _resolved_plan(plan,folder):
    if not any(row['yaml_preparation_deferred'] for row in plan['configurations']):return plan
    _environment_yaml(plan)
    value=read_json(folder/'resolved-configurations.json')
    if (set(value)!={'profile','operation_id','plan_sha256','configurations'} or value['profile']!=PROFILE or
            value['operation_id']!=plan['operation_id'] or value['plan_sha256']!=fingerprint(plan) or
            len(value['configurations'])!=len(plan['configurations'])):raise ConfigError('MCP_RESOLVED_CONFIGURATION_DRIFT')
    for original,row in zip(plan['configurations'],value['configurations']):
        if set(row)!=set(original) or any(row[k]!=v for k,v in original.items() if k not in {'after_sha256','managed_bytes_sha256'}):
            raise ConfigError('MCP_RESOLVED_CONFIGURATION_DRIFT')
        if any(not re.fullmatch('[0-9A-F]{64}',row[k]) for k in ('after_sha256','managed_bytes_sha256')):
            raise ConfigError('MCP_RESOLVED_CONFIGURATION_DRIFT')
    result=copy.deepcopy(plan);result['configurations']=value['configurations'];return result

def prepare(plan,payload_root,transaction_root):
    payload=_path(payload_root);transaction=_path(transaction_root)
    if plan['removal']:
        folder=transaction/'mcp';folder.mkdir(parents=True,exist_ok=True)
        _resolve_configurations(plan,folder)
        for index,row in enumerate(plan['configurations']):
            raw=read_optional(Path(row['path']));backup=folder/('config-'+str(index)+'.preimage')
            if (digest(raw) if Path(row['path']).exists() else 'MISSING')!=row['before_sha256']:raise ConfigError('MCP_CONFIGURATION_CHANGED_AFTER_PLAN')
            if not backup.exists():
                with backup.open('xb') as stream:stream.write(raw)
            elif _read(backup)!=raw:raise ConfigError('MCP_PREIMAGE_DRIFT')
        return {'status':'DECONFIGURATION_PREPARED','required':True}
    requirement=_read(payload/'tools/v2_mcp_requirements.txt')
    launcher=_read(payload/'tools/mcp_launcher.py')
    if digest(requirement)!=plan['requirements_sha256'] or digest(launcher)!=plan['launcher_sha256']:
        raise ConfigError('MCP_SOURCE_CHANGED')
    packages_required=[]
    for line in requirement.decode('utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        match=re.fullmatch(r'([A-Za-z0-9_-]+)==([0-9]+(?:\.[0-9]+){1,3})',line)
        if match is None:raise ConfigError('MCP_REQUIREMENTS_PROFILE_INVALID')
        packages_required.append(match.groups())
    if not packages_required or len(packages_required)>32:raise ConfigError('MCP_REQUIREMENTS_PROFILE_INVALID')
    folder=transaction/'mcp';folder.mkdir(parents=True,exist_ok=True)
    evidence=folder/'environment.json'
    environment=Path(plan['environment']);_path(environment)
    marker=environment/'.malts-mcp-environment.json'
    if environment.exists():
        if not marker.is_file():raise ConfigError('UNOWNED_MCP_ENVIRONMENT_CONFLICT')
        owner=read_json(marker)
        if owner.get('profile')!=PROFILE or owner.get('requirements_sha256')!=plan['requirements_sha256']:
            raise ConfigError('MCP_ENVIRONMENT_IDENTITY_CONFLICT')
        if owner.get('state')!='READY' and owner.get('operation_id')!=plan['operation_id']:
            raise ConfigError('MCP_ENVIRONMENT_RECOVERY_REQUIRED')
    else:
        environment.mkdir(parents=True)
        write_json(marker,{'profile':PROFILE,'operation_id':plan['operation_id'],'requirements_sha256':plan['requirements_sha256'],'state':'PREPARING'})
    owner=read_json(marker)
    if owner['state']!='READY':
        _run([plan['base_python'],'-B','-m','venv',str(environment)])
        requirements=folder/'requirements.txt'
        if requirements.exists() and _read(requirements)!=requirement:raise ConfigError('MCP_RECOVERY_REQUIREMENTS_DRIFT')
        requirements.write_bytes(requirement)
        _run([plan['python'],'-B','-m','pip','install','--disable-pip-version-check','--no-input','--no-cache-dir','-r',requirements])
        owner['state']='READY';write_json(marker,owner)
    _run([plan['python'],'-B','-c','import mcp, anyio, jsonschema, yaml; from mcp.server.lowlevel import Server'])
    packages=json.loads(_run([plan['python'],'-B','-m','pip','list','--format=json','--disable-pip-version-check']))
    versions={p['name'].lower().replace('_','-'):p['version'] for p in packages}
    if any(versions.get(name.lower().replace('_','-'))!=version for name,version in packages_required):
        raise ConfigError('MCP_ENVIRONMENT_PACKAGE_DRIFT')
    write_json(evidence,{'status':'READY','packages':packages,'requirements_sha256':plan['requirements_sha256']})
    _environment_yaml(plan)
    verify_inputs(plan)
    _resolve_configurations(plan,folder)
    for index,row in enumerate(plan['configurations']):
        backup=folder/('config-'+str(index)+'.preimage')
        raw=read_optional(Path(row['path']))
        expected=row['before_sha256']
        if (digest(raw) if Path(row['path']).exists() else 'MISSING')!=expected:
            raise ConfigError('MCP_CONFIGURATION_CHANGED_AFTER_PLAN')
        if backup.exists():
            if _read(backup)!=raw:raise ConfigError('MCP_PREIMAGE_DRIFT')
        else:
            with backup.open('xb') as stream:stream.write(raw)
    return {'status':'DEPENDENCIES_READY','required':True}

@contextmanager
def exclusive(path):
    _path(path)
    if os.name=='nt':
        import ctypes as c,msvcrt
        fn=c.WinDLL('kernel32',use_last_error=True).CreateFileW
        fn.argtypes=[c.c_wchar_p,c.c_ulong,c.c_ulong,c.c_void_p,c.c_ulong,c.c_ulong,c.c_void_p];fn.restype=c.c_void_p
        handle=fn(str(path),0xC0000000,0,None,3,0x00200000,None)
        if handle==c.c_void_p(-1).value:raise ConfigError('MCP_CONFIG_EXCLUSIVE_ACCESS_UNAVAILABLE')
        fd=msvcrt.open_osfhandle(handle,os.O_RDWR|os.O_BINARY)
        with os.fdopen(fd,'r+b') as stream:yield stream
    else:
        import fcntl
        with path.open('r+b') as stream:
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            yield stream

def apply(plan,payload_root,transaction_root,version):
    runtime=Path(plan['runtime_root']);payload=_path(payload_root);transaction=_path(transaction_root)
    folder=transaction/'mcp';journal=folder/'configuration-progress.json'
    plan=_resolved_plan(plan,folder)
    progress=read_json(journal) if journal.exists() else {'profile':PROFILE,'operation_id':plan['operation_id'],'completed':[]}
    if progress.get('profile')!=PROFILE or progress.get('operation_id')!=plan['operation_id']:
        raise ConfigError('MCP_CONFIGURATION_JOURNAL_CONFLICT')
    launcher=runtime/'mcp_launcher.py';new=read_optional(launcher) if plan['removal'] else _read(payload/'tools/mcp_launcher.py')
    if digest(new)!=plan['launcher_sha256']:raise ConfigError('MCP_SOURCE_CHANGED')
    actual=digest(read_optional(launcher)) if launcher.exists() else 'MISSING'
    if actual not in {plan['previous_launcher_sha256'],plan['launcher_sha256']}:
        raise ConfigError('MCP_LAUNCHER_CHANGED_DURING_INSTALL')
    if actual!=plan['launcher_sha256']:
        from malts_lifecycle import _atomic_write
        _atomic_write(launcher,new)
    # Check the entire review snapshot before the first Host edit. On recovery,
    # exact after-images are accepted under this original operation identity.
    for row in plan['configurations']:
        path=Path(row['path']);raw=read_optional(path)
        actual=digest(raw) if path.exists() else 'MISSING'
        if actual not in {row['before_sha256'],row['after_sha256']}:
            raise ConfigError('MCP_CONFIGURATION_RECOVERY_CONFLICT')
    for index,row in enumerate(plan['configurations']):
        path=Path(row['path']);raw=read_optional(path)
        if path.exists() and digest(raw)==row['after_sha256']:continue
        new=remove(row['host'],raw) if plan['removal'] else patch(row['host'],raw,row['entry'])
        if digest(new)!=row['after_sha256']:raise ConfigError('MCP_PLAN_CONTENT_MISMATCH')
        backup=folder/('config-'+str(index)+'.preimage')
        if not backup.is_file() or _read(backup)!=raw:raise ConfigError('MCP_PREIMAGE_MISSING')
        path.parent.mkdir(parents=True,exist_ok=True);_path(path)
        if path.exists():
            with exclusive(path) as stream:
                if digest(stream.read())!=row['before_sha256']:raise ConfigError('MCP_CONFIGURATION_CHANGED_BEFORE_WRITE')
                stream.seek(0);stream.write(new);stream.truncate();stream.flush();os.fsync(stream.fileno())
                stream.seek(0)
                if stream.read()!=new:raise ConfigError('MCP_CONFIGURATION_WRITE_UNCERTAIN')
        else:
            if row['before_sha256']!='MISSING':raise ConfigError('MCP_CONFIGURATION_DISAPPEARED')
            with path.open('xb') as stream:stream.write(new);stream.flush();os.fsync(stream.fileno())
        progress['completed'].append(index);write_json(journal,progress)
    connections=[]
    for row in plan['configurations']:
        raw=_read(Path(row['path']))
        if digest(raw)!=row['after_sha256'] or owned_entry(row['host'],document(row['host'],raw))!=(None if plan['removal'] else row['entry']):
            raise ConfigError('MCP_CONFIGURATION_VERIFY_FAILED')
        if plan['removal']:continue
        result=json.loads(_run([plan['python'],'-B',payload/'tools/mcp_connection_check.py',plan['python'],launcher,row['tool_root'],version],timeout=55))
        if result['status']!='PASS':raise ConfigError('MCP_CONNECTION_CHECK_FAILED')
        connections.append({'host':row['host'],**result})
    ledger={'profile':PROFILE,'version':version,'operation_id':plan['operation_id'],'launcher_sha256':plan['launcher_sha256'],
            'state':'UNINSTALLED' if plan['removal'] else 'READY',
            'environment':plan['environment'],'requirements_sha256':plan['requirements_sha256'],
            'configurations':[] if plan['removal'] else [{'host':r['host'],'path':r['path'],'tool_root':r['tool_root'],'entry_sha256':r['entry_sha256'],'managed_bytes_sha256':r['managed_bytes_sha256']} for r in plan['configurations']]}
    path=runtime/'installation.json';actual=digest(read_optional(path)) if path.exists() else 'MISSING'
    if actual!=plan['ledger_sha256'] and (not path.exists() or read_json(path)!=ledger):
        raise ConfigError('MCP_INSTALLATION_RECORD_CHANGED')
    write_json(path,ledger)
    result={'status':'REMOVED' if plan['removal'] else 'READY','required':True,'write_enabled':False,'connections':connections,
            'existing_host_reload':'RECONNECT_OR_RESTART_IF_HOST_DOES_NOT_RELOAD_CONFIGURATION'}
    write_json(folder/'verification.json',result)
    # Lifecycle commits retire their transaction directory. Retain the exact
    # Host preimages privately, including interrupted/replayed operation identity.
    history=runtime/'history'/plan['operation_id'];_path(history);history.mkdir(parents=True,exist_ok=True)
    for file in folder.iterdir():
        _path(file)
        if not file.is_file():raise ConfigError('MCP_RECOVERY_HISTORY_UNEXPECTED_CONTENT')
        saved=history/file.name;raw=_read(file)
        if saved.exists():
            if _read(saved)!=raw:raise ConfigError('MCP_RECOVERY_HISTORY_DRIFT')
        else:
            with saved.open('xb') as stream:stream.write(raw)
    return result

def verify_ready(plan,payload_root,version):
    """Same-generation update checks only; missing installation needs a repair plan."""
    runtime=Path(plan['runtime_root'])
    ledger=runtime/'installation.json'
    if (not ledger.is_file() or digest(read_optional(runtime/'mcp_launcher.py'))!=plan['launcher_sha256'] or
            not Path(plan['python']).is_file() or any(row['before_sha256']!=row['after_sha256'] for row in plan['configurations'])):
        raise ConfigError('MCP_REPAIR_PLAN_REQUIRED')
    connections=[]
    for row in plan['configurations']:
        result=json.loads(_run([plan['python'],'-B',Path(payload_root)/'tools/mcp_connection_check.py',plan['python'],
                              runtime/'mcp_launcher.py',row['tool_root'],version],timeout=55))
        if result['status']!='PASS':raise ConfigError('MCP_CONNECTION_CHECK_FAILED')
        connections.append({'host':row['host'],**result})
    return {'status':'READY','required':True,'write_enabled':False,'connections':connections,
            'existing_host_reload':'RECONNECT_OR_RESTART_IF_HOST_DOES_NOT_RELOAD_CONFIGURATION'}
