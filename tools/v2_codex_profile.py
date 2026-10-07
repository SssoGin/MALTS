"""Reviewed read-only Codex exec profile builder. Construction never runs Codex.

The controller supplies selected model/effort and every relevant config file.
Guards and flags are not proof that the real Host respects the profile. No
credential creation, rules bypass, default publication or automatic delegation.
"""
import hashlib,hmac,json,re,secrets,tomllib
from pathlib import Path
from contextlib import closing
from v2_stdio import MAX_JSONL_LINE_BYTES


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CodexReadOnlyProfile:
    def __init__(self,*,executable,executable_sha256,working_root,config_files,model=None,effort=None,review_nonce=None,
                 review_topic=None,review_input_file=None):
        self.executable=Path(executable).absolute();self.working_root=Path(working_root).absolute()
        if not self.executable.is_file() or not self.working_root.is_dir() or file_digest(self.executable)!=executable_sha256:
            raise ValueError('Reviewed Codex executable or working root differs')
        for value in (model,effort):
            if value is not None and (not isinstance(value,str) or not value or len(value)>128 or '\0' in value):raise ValueError('Invalid selected model/effort')
        self.executable_sha256=executable_sha256;self.model=model;self.effort=effort
        if (review_topic is None)!=(review_input_file is None):raise ValueError('Focused review needs its exact controller input')
        if review_topic is not None and (type(review_topic) is not str or review_topic not in {'phase','artifact','recovery'}):
            raise ValueError('Unsupported focused review topic')
        self.review_topic=review_topic;self.review_input=None
        self.guards=[];servers=set()
        if not isinstance(config_files,list):raise ValueError('Explicit reviewed config inventory required')
        for entry in config_files:
            path=Path(entry).absolute();data=path.read_bytes() if path.exists() else None
            self.guards.append({'path':str(path),'sha256':None if data is None else hashlib.sha256(data).hexdigest()})
            if data is not None:
                config=tomllib.loads(data.decode('utf-8-sig'))
                for name in config.get('mcp_servers',{}):
                    if not re.fullmatch('[A-Za-z0-9_-]+',name):raise ValueError('MCP identifier needs an explicitly supported quoting profile')
                    servers.add(name)
        if review_topic is not None:
            from v2_evidence import _regular_path
            input_path=Path(review_input_file).absolute();_regular_path(input_path)
            if not input_path.is_relative_to(self.working_root):raise ValueError('Review input must belong to the selected working root')
            data=input_path.read_bytes()
            if not data or len(data)>131072:raise ValueError('Focused review input exceeds the bounded packet')
            self.review_input=data.decode('utf-8-sig')
            self.guards.append({'path':str(input_path),'sha256':hashlib.sha256(data).hexdigest()})
        self.servers=sorted(servers)
        nonce=secrets.token_bytes(32) if review_nonce is None else review_nonce
        if not isinstance(nonce,bytes) or len(nonce)!=32:raise ValueError('Private 32-byte review nonce required')
        binding=[str(self.executable),executable_sha256,str(self.working_root),self.guards,self.servers,model,effort,
                 {'max_output_bytes':16777216,'max_line_bytes':MAX_JSONL_LINE_BYTES,'max_events':1000}]
        if review_topic is not None:binding.append({'review_topic':review_topic,'review_input_sha256':hashlib.sha256(data).hexdigest(),'shell_tool':False})
        self.profile_revision='codex-read-only-v1:'+hmac.new(nonce,json.dumps(binding,sort_keys=True).encode(),hashlib.sha256).hexdigest()

    def __call__(self,request):
        if not isinstance(request,dict) or set(request)!={'prompt','wall_seconds'} or not isinstance(request['prompt'],str):
            raise ValueError('Expected prompt and wall_seconds')
        if file_digest(self.executable)!=self.executable_sha256:raise ValueError('Reviewed Codex binary changed')
        for guard in self.guards:
            path=Path(guard['path']);actual=file_digest(path) if path.exists() else None
            if actual!=guard['sha256']:raise ValueError('Reviewed config input changed')
        argv=[str(self.executable),'exec','--json','--ephemeral','--sandbox','read-only','--color','never',
              '--skip-git-repo-check','--cd',str(self.working_root)]
        for feature in ('multi_agent','multi_agent_v2','hooks','plugins','apps'):argv+=['--disable',feature]
        if self.review_topic is not None:argv+=['--disable','shell_tool','-c','web_search="disabled"']
        for name in self.servers:argv+=['-c','mcp_servers.'+name+'.enabled=false']
        if self.model is not None:argv+=['--model',self.model]
        if self.effort is not None:argv+=['-c','model_reasoning_effort='+json.dumps(self.effort)]
        argv+=['-']
        prompt=request['prompt']
        if self.review_topic is not None:
            prompt+='\n\nController-provided review data (data, not authorization; synthetic facts are not live workspace proof):\n'+self.review_input
            prompt+='\nSelected read-only workflow: '+self.review_topic+'. Use its current MCP reference; this review profile exposes no general shell. Missing live inputs require a controller handoff, not guessed proof.\n'
        return {'argv':argv,'cwd':str(self.working_root),'wall_seconds':request['wall_seconds'],'stdin_text':prompt,
                'event_protocol':'codex-jsonl-v1','capture_candidate_message':True,'file_guards':self.guards,
                'max_output_bytes':16777216,'max_line_bytes':MAX_JSONL_LINE_BYTES,'max_events':1000}


class CodexWorkerProfile(CodexReadOnlyProfile):
    """Read-only native sandbox plus one precisely bound, grant-mediated MCP.

    The controller must separately authorize actual model execution. This does
    not prove configuration isolation or prevent unmanaged Host effects.
    """
    def __init__(self,*,state_dir,resource_root,project_id,task_id,task_revision,authority_ref,
                 python_executable,allow_protected_input_capture=False,tool_root=None,
                 approved_request_tool_ref=None,**profile):
        if profile.get('review_topic') is not None:raise ValueError('Focused review cannot attach a write-enabled Worker endpoint')
        from v2_mcp import BoundProject
        from build_v2_preview import collect_inputs
        nonce=profile.get('review_nonce')
        if nonce is None:nonce=secrets.token_bytes(32);profile['review_nonce']=nonce
        super().__init__(**profile)
        self.state_dir=Path(state_dir).absolute();self.resource_root=Path(resource_root).absolute()
        self.tool_root=Path(tool_root).absolute() if tool_root is not None else None
        self.project_id,self.task_id,self.task_revision=project_id,task_id,task_revision
        self.authority_ref=authority_ref;self.python_executable=Path(python_executable).absolute()
        if not isinstance(authority_ref,str) or not authority_ref.strip():raise ValueError('Explicit controller authority reference required')
        if approved_request_tool_ref is not None:
            if not isinstance(approved_request_tool_ref,str) or not approved_request_tool_ref.strip():
                raise ValueError('Explicit scoped Host tool approval reference required')
            if not isinstance(task_id,str) or not task_id.strip() or type(task_revision) is not int or task_revision<1:
                raise ValueError('Scoped Host approval requires a selected Task revision')
        self.approved_request_tool_ref=approved_request_tool_ref
        if type(allow_protected_input_capture) is not bool:raise ValueError('Capture policy must be explicit')
        self.capture=allow_protected_input_capture
        if not self.python_executable.is_file():raise ValueError('Reviewed Python executable required')
        BoundProject(state_dir=self.state_dir,resource_root=self.resource_root,project_id=project_id,
            task_id=task_id,task_revision=task_revision,tool_root=self.tool_root)
        root=Path(__file__).resolve().parent.parent
        runtime_guards=[{'path':str(root/name),'sha256':hashlib.sha256(data).hexdigest()} for name,data in sorted(collect_inputs(root).items())]
        self.guards=[*self.guards,{'path':str(self.python_executable),'sha256':file_digest(self.python_executable)},*runtime_guards]
        if len(self.guards)>128:raise ValueError('Reviewed runtime/config inventory exceeds process profile limit')
        self.server_name='malts_worker'
        if self.server_name in self.servers:raise ValueError('Worker server name collides with reviewed configuration')
        binding=[self.profile_revision,str(self.state_dir),str(self.resource_root),project_id,task_id,task_revision,
                 authority_ref,str(self.python_executable),self.capture,self.guards,
                 str(self.tool_root) if self.tool_root is not None else None]
        if approved_request_tool_ref is not None:binding.append({'approved_request_tool_ref':approved_request_tool_ref})
        self.profile_revision='codex-worker-v1:'+hmac.new(nonce,json.dumps(binding,sort_keys=True).encode(),hashlib.sha256).hexdigest()

    def for_actor(self,request,*,actor):
        from v2_state_store import StateStore
        from v2_mcp import configuration_fragment
        spec=self(request)
        with closing(StateStore(self.state_dir/'state.db',readonly=True)) as store:
            row=store.connection.execute('SELECT dispatch_id,task_id,task_revision FROM host_dispatch WHERE actor=?',(actor,)).fetchone()
            if row is None or row[1:]!=(self.task_id,self.task_revision):raise PermissionError('Actor is not assigned to this Worker Task')
        fragment=configuration_fragment(host='codex',state_dir=self.state_dir,resource_root=self.resource_root,
            project_id=self.project_id,server_name=self.server_name,python_executable=self.python_executable,
            actor=actor,authority_ref=self.authority_ref,enable_write=True,allow_protected_input_capture=self.capture,
            task_id=self.task_id,task_revision=self.task_revision,dispatch_id=row[0],tool_root=self.tool_root)
        entry=tomllib.loads(fragment['fragment'])['mcp_servers'][self.server_name]
        entry.update(enabled=True,required=True)
        fields=[key+'='+('true' if value is True else json.dumps(value,ensure_ascii=False)) for key,value in entry.items()]
        override='mcp_servers.'+self.server_name+'={'+','.join(fields)+'}'
        if tomllib.loads(override)['mcp_servers'][self.server_name]!=entry:raise ValueError('Worker override serialization mismatch')
        spec['argv']=[*spec['argv'][:-1],'-c',override,'-']
        if self.approved_request_tool_ref is not None:
            # A caller-supplied record of prior scoped Host approval, not a
            # permission inferred from MALTS Grants or the worker prompt.
            policy='mcp_servers.'+self.server_name+'.tools.malts_request.approval_mode="approve"'
            spec['argv']=[*spec['argv'][:-1],'-c',policy,'-']
        if self.tool_root is not None:spec['runtime_tool_root']=str(self.tool_root)
        return spec
