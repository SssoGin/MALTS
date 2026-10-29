"""Reviewed Windows real-Agent command profiles; construction never launches.

All model prompts use stdin. Work is mediated by one Task/dispatch-bound MCP;
native shells and other MCP entries are disabled for this invocation only.
The inherited credential providers are never copied into profile documents.
"""
import hashlib,json,re,tomllib
from pathlib import Path
from contextlib import closing
from v2_codex_profile import CodexReadOnlyProfile,CodexWorkerProfile,file_digest
from v2_agent_qualification import file_inputs
from v2_evidence import _regular_path

HOSTS=('codex','claude-code','opencode','deepseek-harness')
PROTOCOLS=dict(zip(HOSTS,('codex-jsonl-v1','claude-jsonl-v1','opencode-jsonl-v1','harness-jsonl-v1')))
WORKER_TOOLS=('malts_installation','malts_entry_status','malts_actions','malts_context','malts_workflow','malts_request')

def _write_once(path,body):
    path=Path(path);_regular_path(path);data=(json.dumps(body,ensure_ascii=False,sort_keys=True)+'\n').encode('utf-8')
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=data:raise ValueError('Original private launch configuration differs')
    else:
        with path.open('xb') as stream:stream.write(data)
    return {'path':str(path),'sha256':hashlib.sha256(data).hexdigest()}

class AgentProfile:
    def __init__(self,*,host,executable,executable_sha256,working_root,config_files,mode='review',
                 state_dir=None,project_id=None,task_id=None,task_revision=None,authority_ref=None,
                 python_executable=None,model=None,effort=None,launcher_args=None,launcher_files=None,
                 harness_restore_auth=False,harness_credentials_path=None,execution_root=None,tool_root=None):
        if host not in HOSTS or mode not in {'review','worker'}:raise ValueError('Supported Host and mode required')
        self.host,self.mode=host,mode
        self.executable=Path(executable).absolute();self.root=Path(working_root).absolute()
        self.execution_root=Path(execution_root).absolute() if execution_root is not None else self.root
        if not self.executable.is_file() or not self.root.is_dir() or file_digest(self.executable)!=executable_sha256:
            raise ValueError('Reviewed executable or working root changed')
        _regular_path(self.execution_root)
        if not self.execution_root.is_dir():raise ValueError('Reviewed native execution directory must already exist')
        if host=='codex' and mode=='worker':
            actual=self.root.resolve();execution=self.execution_root.resolve()
            if execution.is_relative_to(actual) or actual.is_relative_to(execution):
                raise ValueError('Codex Worker native execution must use a separate owned staging root')
            if any((parent/'.git').exists() for parent in [execution,*execution.parents]):
                raise ValueError('Codex staging must not inherit a Git project writable root')
        if not isinstance(config_files,list):raise ValueError('Explicit configuration inventory required')
        if host=='deepseek-harness' and model is None:
            from mcp_config_check import _document
            selection={}
            for filename in config_files:
                path=Path(filename)
                if not path.exists():continue
                rows=_document('deepseek-harness',path.read_bytes())
                if not isinstance(rows,list):raise ValueError('Selected Harness profile requires an explicit static model')
                for row in rows:
                    if isinstance(row,dict) and row.get('id')=='agent-default-model':selection=row.get('config',{})
            if selection:
                if type(selection.get('provider')) is not str or type(selection.get('model')) is not str:
                    raise ValueError('Dynamic Harness model selection needs explicit controller review')
                model=selection['provider']+'/'+selection['model']
                if effort is None:effort=selection.get('reasoningEffort')
            else:raise ValueError('Select the existing Harness provider/model explicitly; do not guess a headless credential route')
        for value in (model,effort):
            if value is not None and (not isinstance(value,str) or not value or len(value)>128 or '\0' in value):raise ValueError('Explicit model/effort value is invalid')
        if host=='deepseek-harness' and effort is not None and effort not in {'low','medium','high','max'}:
            raise ValueError('Unsupported reviewed Harness reasoning effort')
        self.model,self.effort=model,effort
        if type(harness_restore_auth) is not bool:raise ValueError('Explicit existing-auth policy required')
        self.restore_auth=harness_restore_auth
        self.credentials=Path(harness_credentials_path).absolute() if harness_credentials_path is not None else None
        if self.restore_auth and (self.credentials is None or not self.credentials.is_file()):
            raise ValueError('Explicit existing Harness credential-store reference required; credentials are never copied')
        self.launcher_args=launcher_args or []
        if host=='deepseek-harness':
            if (not isinstance(self.launcher_args,list) or len(self.launcher_args)!=2 or self.launcher_args[0]!='--expose-internals' or
                not isinstance(self.launcher_args[1],str) or not self.launcher_args[1].replace('\\','/').endswith('/@deepseek-ai/dsh-desktop-host/lib/cli.js')):
                raise ValueError('Reviewed Harness desktop launcher prefix required')
            if not launcher_files:raise ValueError('Harness archive/launcher identity guards required')
        elif self.launcher_args:raise ValueError('Unexpected launcher arguments')
        self.state_dir=Path(state_dir).absolute() if state_dir is not None else None
        self.project_id,self.task_id,self.task_revision=project_id,task_id,task_revision
        self.authority_ref=authority_ref
        self.tool_root=Path(tool_root).absolute() if tool_root is not None else None
        self.python=Path(python_executable).absolute() if python_executable is not None else None
        if mode=='worker':
            from v2_mcp import BoundProject
            if self.python is None or not self.python.is_file():raise ValueError('Reviewed MCP Python required')
            if not isinstance(authority_ref,str) or not authority_ref:raise ValueError('Controller launch authority required')
            BoundProject(state_dir=self.state_dir,resource_root=self.root,project_id=project_id,task_id=task_id,task_revision=task_revision)
        paths=[self.executable,*map(Path,config_files),*map(Path,launcher_files or [])]
        if self.python is not None:paths.append(self.python)
        if self.tool_root is not None:paths.append(self.tool_root/'MALTS_BOOT.md')
        if self.credentials is not None:paths.append(self.credentials)
        paths += [Path(__file__).parent/name for name in ('v2_agent_profiles.py','v2_agent_events.py','v2_agent_qualification.py','v2_native_agent_host.py','malts_agents.py','v2_process_host.py','v2_stdio.py','v2_windows_job.py','v2_codex_profile.py','v2_codex_events.py','v2_mcp.py','agent_harness_guard.mjs')]
        from build_v2_preview import collect_inputs
        paths += [Path(__file__).parent.parent/name for name in collect_inputs(Path(__file__).parent.parent)]
        self.inputs=file_inputs(paths)
        self.guards=[{'path':p,'sha256':v} for p,v in sorted(self.inputs.items())]
        servers=set()
        for path in map(Path,config_files):
            if path.is_file() and host=='opencode':
                from mcp_config_check import _document
                value=_document('opencode',path.read_bytes())
                servers.update(value.get('mcp',{}))
        self.disabled_servers=sorted(servers)
        binding=[host,mode,str(self.root),str(self.execution_root),self.inputs,str(self.state_dir),project_id,task_id,task_revision,authority_ref,model,effort,self.launcher_args,self.restore_auth]
        self.profile_revision='real-agent-v1:'+hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest()
        # Qualification is reusable across Task IDs only for the same actual
        # Host/mode/model/configuration boundary; review never qualifies writes.
        qualification_binding=[host,mode,model,effort,str(self.root),str(self.execution_root),self.inputs,self.launcher_args,self.restore_auth]
        self.qualification_binding=hashlib.sha256(json.dumps(qualification_binding,sort_keys=True).encode()).hexdigest()
        self.codex=None
        if host=='codex':
            common=dict(executable=self.executable,executable_sha256=executable_sha256,working_root=self.execution_root,config_files=config_files,model=model,effort=effort)
            if mode=='worker':common.update(state_dir=self.state_dir,resource_root=self.root,project_id=project_id,task_id=task_id,task_revision=task_revision,
                authority_ref=authority_ref,python_executable=self.python,allow_protected_input_capture=True,approved_request_tool_ref=authority_ref,tool_root=self.tool_root)
            self.codex=(CodexWorkerProfile if mode=='worker' else CodexReadOnlyProfile)(**common)

    def _validate(self,request):
        if not isinstance(request,dict) or set(request)!={'prompt','wall_seconds'}:raise ValueError('Closed Agent request required')
        if not isinstance(request['prompt'],str) or not 1<=len(request['prompt'].encode('utf-8'))<=131072:raise ValueError('Bounded prompt required')
        if type(request['wall_seconds']) not in (int,float) or not .05<=request['wall_seconds']<=3600:raise ValueError('Bounded deadline required')
        if file_inputs(self.inputs)!=self.inputs:raise ValueError('Reviewed Agent inputs changed')

    def __call__(self,request):return self._spec(request)

    def for_actor(self,request,*,actor):
        self._validate(request)
        if self.mode=='review':
            if self.host=='deepseek-harness':
                if self.state_dir is None:raise ValueError('Harness launch needs an owned state/config directory')
                folder=self.state_dir/'agent-configs'/self.profile_revision.split(':',1)[1]/actor
                return self._spec(request,folder=folder)
            return self._spec(request)
        from v2_state_store import StateStore
        with closing(StateStore(self.state_dir/'state.db',readonly=True)) as store:
            row=store.connection.execute('SELECT dispatch_id,task_id,task_revision FROM host_dispatch WHERE actor=?',(actor,)).fetchone()
            if row is None or row[1:]!=(self.task_id,self.task_revision):raise PermissionError('Worker is outside its original Task dispatch')
        if self.codex is not None:
            spec=self.codex.for_actor(request,actor=actor)
            # Native apply_patch remains available even without shell_tool.
            # Its only writable workspace is separate disposable staging. Clear
            # extra roots and implicit temp grants: a project inside TEMP must
            # not become writable merely because the parent uses that TEMP.
            spec['argv'][spec['argv'].index('--sandbox')+1]='workspace-write'
            permission={'writable_roots':[],'network_access':False,'exclude_tmpdir_env_var':True,'exclude_slash_tmp':True}
            flags=['-c','approval_policy="never"','-c','sandbox_workspace_write='+self._toml(permission)]
            spec['argv']=[*spec['argv'][:-1],*flags,'-']
            spec['argv']=[*spec['argv'][:-1],'--disable','shell_tool','-']
            spec['file_guards']=list({v['path']:v for v in [*spec['file_guards'],*self.guards]}.values())
            if self.tool_root is not None:spec['runtime_tool_root']=str(self.tool_root)
            return spec
        from v2_mcp import configuration_fragment
        name='malts_worker'
        fragment=configuration_fragment(host={'claude-code':'claude'}.get(self.host,self.host),state_dir=self.state_dir,resource_root=self.root,
            project_id=self.project_id,server_name=name,python_executable=self.python,actor=actor,authority_ref=self.authority_ref,
            enable_write=True,allow_protected_input_capture=True,task_id=self.task_id,task_revision=self.task_revision,dispatch_id=row[0],tool_root=self.tool_root)['fragment']
        folder=self.state_dir/'agent-configs'/self.profile_revision.split(':',1)[1]/actor
        return self._spec(request,fragment=fragment,folder=folder)

    def _spec(self,request,*,fragment=None,folder=None):
        self._validate(request)
        if self.codex is not None:
            spec=self.codex(request)
            spec['argv']=[*spec['argv'][:-1],'--disable','shell_tool','-']
            spec['file_guards']=list({v['path']:v for v in [*spec['file_guards'],*self.guards]}.values())
            if self.tool_root is not None:spec['runtime_tool_root']=str(self.tool_root)
            return spec
        argv=[str(self.executable),*self.launcher_args];environment={};guards=list(self.guards)
        if self.host=='claude-code':
            argv+=['--print','--verbose','--output-format','stream-json','--no-session-persistence','--strict-mcp-config','--tools','',
                '--settings','{"disableAllHooks":true}']
            config=fragment or {'mcpServers':{}}
            argv+=['--mcp-config',json.dumps(config,ensure_ascii=False)]
            if fragment is not None:argv+=['--allowedTools',','.join('mcp__malts_worker__'+t for t in WORKER_TOOLS)]
            if self.model is not None:argv+=['--model',self.model]
            if self.effort is not None:argv+=['--effort',self.effort]
        elif self.host=='opencode':
            argv+=['run','--pure','--format','json','--dir',str(self.root)]
            if self.model is not None:argv+=['--model',self.model]
            if self.effort is not None:argv+=['--variant',self.effort]
            mcp={name:{'enabled':False} for name in self.disabled_servers}
            if fragment is not None:mcp.update(fragment['mcp'])
            permission={'*':'deny'}
            if fragment is not None:permission['malts_worker_*']='allow'
            environment={'OPENCODE_CONFIG_CONTENT':json.dumps({'mcp':mcp,'permission':permission,'autoupdate':False},ensure_ascii=False),
                         'OPENCODE_DISABLE_AUTOUPDATE':'true'}
        else:
            argv+=['--profile','headless']
            if folder is not None:
                patch=[{'id':k,'disabled':True} for k in ('session-title-llm','hmr','tool-subagent','tool-subagent-control','tool-schedule','tool-jobs','tool-plugin-manager')]
                patch += [{'id':'tools','config':{'mode':'native'}}]
                if self.restore_auth:
                    patch += [{'id':'credentials','disabled':False,'config':{'path':str(self.credentials),'watch':False}}]
                    patch += [{'id':k,'disabled':False} for k in ('authorization','deepseek-account')]
                if self.model is not None:
                    parts=self.model.split('/',1)
                    if len(parts)!=2:raise ValueError('Harness model selection requires provider/model')
                    selection={'provider':parts[0],'model':parts[1]}
                    if self.effort is not None:selection['reasoningEffort']=self.effort
                    patch.append({'id':'agent-default-model','config':selection})
                patch += fragment or []
                names=['mcp__malts_worker__'+t for t in WORKER_TOOLS] if fragment is not None else []
                patch.append({'insert':[{'id':'malts-agent-guard','name':(Path(__file__).parent/'agent_harness_guard.mjs').as_uri(),
                    'config':{'allowedNames':names}}]})
                path=folder/'harness.patch.json';guards.append(_write_once(path,patch));argv+=['--patch',str(path)]
            elif self.mode=='worker':
                # Preview only; the actual actor-bound call always supplies its patch.
                pass
            # No files are created by a preview. for_actor supplies the owned
            # per-dispatch directory before any actual process can be launched.
            if self.state_dir is None:raise ValueError('Owned Harness home required')
            argv+=['--json','-'];environment={'ELECTRON_RUN_AS_NODE':'1','DSH_TOOLS_MODE':'native',
                'DSH_HOME':str(self.state_dir/'agent-home'),'DSH_TELEMETRY_DISABLED':'1'}
        return {'argv':argv,'cwd':str(self.root),'wall_seconds':request['wall_seconds'],'stdin_text':request['prompt'],
            'event_protocol':PROTOCOLS[self.host],'capture_candidate_message':True,'max_output_bytes':16777216,
            'max_line_bytes':262144,'max_events':1000,'file_guards':guards,**({'environment':environment} if environment else {}),
            **({'runtime_tool_root':str(self.tool_root)} if self.tool_root is not None else {})}

    @staticmethod
    def _toml(value):
        if isinstance(value,dict):return '{'+','.join(json.dumps(k)+'='+AgentProfile._toml(v) for k,v in value.items())+'}'
        if isinstance(value,bool):return 'true' if value else 'false'
        return json.dumps(value,ensure_ascii=False)
