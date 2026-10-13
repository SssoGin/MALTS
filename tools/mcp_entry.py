"""Installed read-only MCP entry; select an existing workspace per request."""
import json
from pathlib import Path
from contextlib import closing
import logging
from v2_entry import inspect_entry,inspect_workspace_entry
from v2_evidence import _regular_path
from v2_mcp import BoundProject,safe_error

WORKFLOWS={'task':'skills/v2/malts-v2-task-workflow/SKILL.md',
           'phase':'skills/malts-long-project-workspace-init/references/v2-phase.md',
           'artifact':'skills/malts-long-project-workspace-init/references/v2-artifact.md',
           'recovery':'skills/malts-long-project-workspace-init/references/v2-recovery.md'}

class InstalledPolicy:
    def __init__(self,tool_root,discovery):
        self.tool_root=Path(tool_root);self.discovery=discovery
        self.root=Path(discovery['malts_root'])

    def workspace(self,value=None):
        # No process-global selected project: concurrent calls cannot switch each other.
        root=Path(value) if value is not None else Path.cwd()
        if not root.is_absolute() or str(root).startswith(('\\\\','//')):
            raise ValueError('Absolute local workspace required')
        _regular_path(root)
        return root

    def bound(self,value=None):
        root=self.workspace(value)
        if not ((root/'runtime/v2_binding.json').is_file() or (root/'.malts/native.json').is_file()):
            raise ValueError('Existing opted-in workspace required; use workspace-init or reviewed adoption')
        entry=inspect_workspace_entry(root)
        if entry.get('binding_status') not in {'VERIFIED','EXPLICIT_NATIVE_STORE'}:
            raise ValueError('Workspace binding is not verified')
        return BoundProject(state_dir=entry['state_dir'],resource_root=root,
                            project_id=entry['project_id'],tool_root=self.tool_root)

    def installation(self):
        return {'decision':'MCP_READY','version':self.discovery['version'],
                'generation_id':self.discovery['generation_id'],
                'artifact_sha256':self.discovery['artifact_sha256'],
                'workspace_selection':'PER_REQUEST_VERIFIED_EXISTING_WORKSPACE',
                'write_enabled':False,'execution_authorized':False,'writes_performed':False}

    def call(self,name,arguments):
        if name=='malts_installation':return self.installation()
        if name=='malts_workflow':
            import hashlib
            topic=arguments.get('topic','task');relative=WORKFLOWS[topic]
            path=self.root/relative;_regular_path(path)
            with path.open('rb') as stream:raw=stream.read(32769)
            if len(raw)>32768:raise ValueError('Workflow byte budget')
            return {'kind':'WORKFLOW_REFERENCE','topic':topic,'sha256':hashlib.sha256(raw).hexdigest(),
                    'content':raw.decode('utf-8-sig'),'authority_issued':False,'writes_performed':False}
        if name=='malts_entry_status':
            root=self.workspace(arguments.get('workspace'))
            result=inspect_entry(workspace=root,tool_root=self.tool_root,
                                 verify_package=arguments.get('verify_package',False))
            result['mcp_ready']=True
            from mcp_config_check import scan_configurations
            import re
            label=re.findall(r'(?m)^Tool:\s*(.+?)\s*$',(self.tool_root/'MALTS_BOOT.md').read_text('utf-8-sig'))
            host={'Codex':'codex','Claude Code':'claude-code','OpenCode':'opencode','DeepSeek Harness':'deepseek-harness'}.get(label[0]) if len(label)==1 else None
            result['mcp_configuration']=scan_configurations({host:self.tool_root} if host else {},lifecycle_root=self.discovery['lifecycle_root'],workspaces=[root])
            return result
        if name=='malts_actions' and 'workspace' not in arguments:
            return {**self.installation(),'actions':{},'grant_creation_exposed':False,
                    'next_step':'Supply the current opted-in workspace to inspect its project contract.'}
        policy=self.bound(arguments.get('workspace'))
        values={k:v for k,v in arguments.items() if k!='workspace'}
        if name=='malts_actions':return policy.contracts()
        if name=='malts_context':return policy.context(values)
        if name=='malts_verify_task':return policy.verify_task(values)
        raise ValueError('Unknown tool')

def build_server(policy):
    import anyio
    import jsonschema
    import mcp.types as types
    from mcp.server.lowlevel import Server
    server=Server('MALTS',version=policy.discovery['version'])
    workspace={'type':'string','description':'Absolute current project workspace; existing MALTS binding is verified. No initialization.'}
    schemas={
        'malts_installation':{'type':'object','properties':{},'additionalProperties':False},
        'malts_workflow':{'type':'object','properties':{'topic':{'type':'string','enum':list(WORKFLOWS)}},'additionalProperties':False},
        'malts_entry_status':{'type':'object','properties':{'workspace':workspace,'verify_package':{'type':'boolean'}},'additionalProperties':False},
        'malts_actions':{'type':'object','properties':{'workspace':workspace},'additionalProperties':False},
        'malts_context':{'type':'object','properties':{'workspace':workspace,'task_id':{'type':'string'},'limit':{'type':'integer','minimum':1,'maximum':100},'cursor':{'type':['object','null']}},'required':['task_id'],'additionalProperties':False},
        'malts_verify_task':{'type':'object','properties':{'workspace':workspace,'task_id':{'type':'string'}},'required':['task_id'],'additionalProperties':False}}
    descriptions={
        'malts_installation':'Check the installed MALTS version and MCP readiness. Does not need a project or create state.',
        'malts_workflow':'Read one packaged task, phase, artifact or recovery workflow. No implicit execution authority.',
        'malts_entry_status':'Inspect the current workspace binding and readiness. Supply the Agent current workspace explicitly when startup cwd differs.',
        'malts_actions':'Inspect the existing project read-only contract; no Grants or write permission are issued.',
        'malts_context':'Read bounded Task context in the current opted-in workspace. Always supply its workspace when available; never guess a global database.',
        'malts_verify_task':'Recheck current acceptance evidence for a Task in the selected workspace; preserve history.'}
    @server.list_tools()
    async def list_tools():
        return [types.Tool(name=n,description=descriptions[n],inputSchema=s,
                  annotations=types.ToolAnnotations(readOnlyHint=True,destructiveHint=False,openWorldHint=False)) for n,s in schemas.items()]
    def call(name,arguments):
        try:
            if name not in schemas:raise ValueError('Unknown tool')
            try:jsonschema.Draft202012Validator(schemas[name]).validate(arguments)
            except jsonschema.ValidationError:raise ValueError('Tool input schema mismatch') from None
            result=policy.call(name,arguments)
            return types.CallToolResult(content=[types.TextContent(type='text',text=json.dumps(result,ensure_ascii=False))],structuredContent=result,isError=False)
        except Exception as error:
            result=safe_error(error)
            return types.CallToolResult(content=[types.TextContent(type='text',text=json.dumps(result,ensure_ascii=False))],structuredContent=result,isError=True)
    @server.call_tool(validate_input=False)
    async def call_tool(name,arguments):return await anyio.to_thread.run_sync(call,name,arguments)
    return server

def run(tool_root,discovery,*,probe=False):
    import anyio
    from mcp.server.stdio import stdio_server
    policy=InstalledPolicy(tool_root,discovery)
    if probe:
        print(json.dumps(policy.installation(),ensure_ascii=False));return 0
    logging.getLogger('mcp').setLevel(logging.CRITICAL)
    server=build_server(policy)
    async def serve():
        async with stdio_server() as (reader,writer):
            await server.run(reader,writer,server.create_initialization_options())
    anyio.run(serve);return 0
