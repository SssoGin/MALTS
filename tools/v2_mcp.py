#!/usr/bin/env python3
"""Optional SDK-backed stdio bridge; no install, init, Grant creation or cutover.

Tested SDK profile: mcp 1.26.0, legacy MCP through 2025-11-25. This module does
not claim the 2026-07-28 per-request-metadata protocol or OS-level authentication.
"""
import sys
sys.dont_write_bytecode=True
import argparse
import inspect
import json
import hashlib
import logging
import os
import sqlite3
import re
import tomllib
from contextlib import closing
from pathlib import Path
from v2_service import ACTIONS,action_contracts,execute_request,safe_error,HostBoundFieldError,WorkerAdmissionDenied
from v2_state_store import StateStore,StateConflict
from v2_evidence import _regular_path
from v2_legacy_reader import read_source_bytes
from v2_compatibility import MCP_APPLICATION_INTERFACE_VERSION

# Host/operator-only operations are absent, not merely hidden descriptions.
CLIENT_ACTIONS=frozenset({
    'task.revise','task.depend','task.cancel','phase.bind-task',
    'operation.prepare','operation.cancel-prepared','operation.create-file','operation.read-file',
    'operation.update-file',
    'evidence.record','verification.managed-files','verification.begin','verification.rework','task.accept','run.open','run.pause','run.resume','run.rebuild-checkpoint',
})
_DEFAULT_WORKFLOW_TOPIC=object()


def configuration_fragment(*,host,state_dir,resource_root,project_id,server_name='malts-v2',python_executable=None,
                           actor=None,authority_ref=None,enable_write=False,allow_protected_input_capture=False,
                           task_id=None,task_revision=None,dispatch_id=None,tool_root=None,workflow_topic=None):
    """Generate a validated fragment only; registration and permission are separate."""
    if host not in {'codex','claude','opencode','deepseek-harness'}: raise ValueError('Unsupported configuration host')
    if not isinstance(server_name,str) or re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,63}',server_name) is None:
        raise ValueError('Use an unambiguous server name')
    if host=='deepseek-harness' and len(server_name)>32:
        raise ValueError('DeepSeek MCP server namespace cannot exceed 32 characters')
    policy=BoundProject(state_dir=state_dir,resource_root=resource_root,project_id=project_id,
                        actor=actor,authority_ref=authority_ref,enable_write=enable_write,allow_protected_input_capture=allow_protected_input_capture,
                        task_id=task_id,task_revision=task_revision,dispatch_id=dispatch_id,tool_root=tool_root,workflow_topic=workflow_topic)
    executable=str(Path(python_executable or sys.executable).absolute())
    arguments=['-B',str(Path(__file__).absolute()),'--state-dir',str(policy.state_dir),
               '--resource-root',str(policy.resource_root),'--project-id',project_id]
    if enable_write: arguments+=['--enable-write','--actor',actor,'--authority-ref',authority_ref]
    if allow_protected_input_capture:arguments+=['--allow-protected-input-capture']
    if task_id is not None:arguments+=['--task-id',task_id,'--task-revision',str(task_revision)]
    if dispatch_id is not None:arguments+=['--dispatch-id',dispatch_id]
    if policy.tool_root is not None:arguments+=['--tool-root',str(policy.tool_root)]
    if workflow_topic is not None:arguments+=['--workflow-topic',workflow_topic]
    if host=='codex':
        fragment='[mcp_servers.'+server_name+']\ncommand = '+json.dumps(executable)+'\nargs = '+json.dumps(arguments)+'\n'
        parsed=tomllib.loads(fragment)
        if parsed['mcp_servers'][server_name]!={'command':executable,'args':arguments}: raise ValueError('Configuration serialization mismatch')
        encoding='TOML'
    elif host=='deepseek-harness':
        # dsh-v0.2.0-rc.2: a Cordis profile patch, not mcpServers/OpenCode JSON.
        # JSON is a YAML subset; merging with the existing profile is separate.
        fragment=[{'insert':[{'id':'malts-'+server_name,'name':'@deepseek-ai/dsh-mcp-client',
            'config':{'serverName':server_name,'transport':'stdio','command':executable,
                      'args':arguments,'env':{},'cwd':str(policy.resource_root),
                      'failOnStartupError':True,'reconnect':{'enabled':False}}}]}]
        encoding='CORDIS_PATCH_JSON'
    else:
        fragment=({'mcpServers':{server_name:{'command':executable,'args':arguments}}} if host=='claude'
                  else {'mcp':{server_name:{'type':'local','command':[executable,*arguments],'enabled':True}}})
        encoding='JSON'
    return {'host':host,'format':encoding,'fragment':fragment,'server_name':server_name,
            'mode':'WRITE_UNDER_EXISTING_GRANTS' if enable_write else 'READ_ONLY',
            'registration_performed':False,'existing_configuration_read_or_replaced':False,
            'writes_performed':False,'execution_authorized':False,'sdk_availability_verified':False}


class BoundProject:
    def __init__(self,*,state_dir,resource_root,project_id,actor=None,authority_ref=None,enable_write=False,allow_protected_input_capture=False,
                 task_id=None,task_revision=None,dispatch_id=None,tool_root=None,workflow_topic=None):
        self.state_dir=Path(state_dir).absolute(); self.resource_root=Path(resource_root).absolute()
        for root in (self.state_dir,self.resource_root):
            if str(root).startswith(('\\\\','//')): raise ValueError('This bridge requires local roots')
            _regular_path(root)
        if type(enable_write) is not bool: raise ValueError('Write policy must be an explicit boolean')
        for value in (project_id,*((actor,authority_ref) if enable_write else ())):
            if not isinstance(value,str) or not value.strip(): raise ValueError('Host bindings must be explicit')
        self.project_id=project_id; self.actor=actor; self.authority_ref=authority_ref
        self.enable_write=enable_write
        if workflow_topic is not None and (type(workflow_topic) is not str or workflow_topic not in {'phase','artifact','recovery'}):
            raise ValueError('Unsupported workflow reference scope')
        if workflow_topic is not None and enable_write:raise ValueError('Scoped workflow reference is read-only')
        self.workflow_topic=workflow_topic
        self.tool_root=Path(tool_root).absolute() if tool_root is not None else None
        if self.tool_root is not None:_regular_path(self.tool_root)
        if type(allow_protected_input_capture) is not bool or (allow_protected_input_capture and not enable_write):raise ValueError('Protected capture needs explicit write-enabled Host policy')
        self.allow_protected_input_capture=allow_protected_input_capture
        if (task_id is None)!=(task_revision is None):raise ValueError('Task identity and revision must be bound together')
        if task_id is not None and (not isinstance(task_id,str) or not task_id or type(task_revision) is not int or task_revision<1):
            raise ValueError('Invalid Task binding')
        if dispatch_id is not None and (task_id is None or not isinstance(dispatch_id,str) or not dispatch_id or not actor or not enable_write):
            raise ValueError('Dispatch binding requires exact Task and actor')
        self.task_id,self.task_revision,self.dispatch_id=task_id,task_revision,dispatch_id
        with closing(StateStore(self.state_dir/'state.db',readonly=True)) as store: self.check_store(store)

    def check_store(self,store):
        rows=store.connection.execute('SELECT project_id,resource_root FROM project').fetchall()
        if len(rows)!=1 or rows[0][0]!=self.project_id: raise PermissionError('Store is outside the pinned Project')
        # Compare before resolving an untrusted recorded root, avoiding implicit
        # access to a different share or filesystem endpoint.
        if os.path.normcase(os.path.abspath(rows[0][1]))!=os.path.normcase(os.path.abspath(str(self.resource_root))):
            raise PermissionError('Store resource root differs from Host launch policy')
        if self.task_id is not None:
            task=store.task_identity(self.task_id)
            if task is None or task['project_id']!=self.project_id or task['revision']!=self.task_revision:
                raise PermissionError('Task binding is missing or stale')
        if self.dispatch_id is not None:
            row=store.connection.execute('SELECT task_id,task_revision,actor FROM host_dispatch WHERE dispatch_id=?',(self.dispatch_id,)).fetchone()
            if row!=(self.task_id,self.task_revision,self.actor):raise PermissionError('Dispatch binding differs')

    def client_actions(self):
        actions=CLIENT_ACTIONS if self.task_id is None else CLIENT_ACTIONS-{'task.revise','task.depend','phase.bind-task','run.open'}
        if self.dispatch_id is not None:
            actions=actions-{'task.accept','task.cancel','verification.begin','verification.rework'}
        return actions

    def _check_worker(self,store):
        self.check_store(store)
        if self.dispatch_id is None:return
        from v2_operations import Operations
        row=store.connection.execute('''SELECT h.state,h.cancel_requested,h.quiesced,h.epoch,b.revoked,b.consumption_known,b.expires_at
            FROM host_dispatch h JOIN dispatch_budget b ON b.project_id=h.project_id WHERE h.dispatch_id=?''',(self.dispatch_id,)).fetchone()
        epoch=store.connection.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]
        if (row is None or row[0]!='RUNNING' or row[1] or row[2]!=0 or row[3]!=epoch or row[4] or not row[5] or
                (row[6] is not None and Operations._instant(row[6])<=Operations(store).clock())):
            raise WorkerAdmissionDenied()

    def _check_task_arguments(self,store,arguments):
        if self.task_id is None:return
        for key,expected in (('task_id',self.task_id),('task_revision',self.task_revision),('expected_revision',self.task_revision)):
            if key in arguments and arguments[key]!=expected:raise PermissionError('Request exceeds pinned Task revision')
        for key,table in (('grant_id','execution_grant'),('operation_id','operation'),('run_id','execution_run')):
            if key not in arguments:continue
            # prepare creates an operation ID; all other listed IDs already exist.
            row=store.connection.execute(f'SELECT task_id,task_revision FROM {table} WHERE {key}=?',(arguments[key],)).fetchone()
            if row is not None and row!=(self.task_id,self.task_revision):raise PermissionError('Referenced entity belongs to another Task')
        if self.dispatch_id is not None and 'run_id' in arguments:
            expected=store.connection.execute('SELECT run_id FROM host_dispatch WHERE dispatch_id=?',(self.dispatch_id,)).fetchone()[0]
            if arguments['run_id']!=expected:raise PermissionError('Worker may control only its own Run')

    def contracts(self):
        contracts=action_contracts(self.client_actions()) if self.enable_write else {}
        for contract in contracts.values():
            for field in ('actor','owner','project_id','authority_ref'):
                if field in contract['parameters']: contract['parameters'][field]={'required':False,'host_bound':True}
        if 'evidence.record' in contracts:
            contracts['evidence.record']['parameters']['method']={'required':False,'fixed':'declared-review'}
            contracts['evidence.record']['parameters']['evidence_level']={'required':False,'fixed':'D'}
        if 'operation.prepare' in contracts:
            contracts['operation.prepare']['parameters']['capture_authority_ref']={'required':False,'host_bound':True}
        return {'actions':contracts,'project_id':self.project_id,'actor':self.actor,'write_enabled':self.enable_write,
                'request_response_contract':{'success':{'decision':'REQUEST_PROCESSED','action':'REQUESTED_ACTION','result':'ACTION_RESULT_OBJECT'},
                    'prepare_request_hash_path':'result.request_hash','file_read_text_path':'result.text',
                    'file_read_sha256_path':'result.sha256',
                    'error':'decision=ERROR; error_code/error_type and optional reason_code are top-level. Never use an error as an action result.'},
                'task_binding':None if self.task_id is None else {'task_id':self.task_id,'task_revision':self.task_revision,'dispatch_id':self.dispatch_id},
                'completion_owner':'CONTROLLER_AFTER_HOST_QUIESCENCE' if self.dispatch_id is not None else 'CURRENT_ENDPOINT_CONTRACT',
                'protected_input_capture_enabled':self.allow_protected_input_capture,
                'evidence_capture_contract':{'content_class':'protected-artifact','sensitivity':'unknown',
                                             'allowed_purposes':['verification','recovery','derivation'],
                                             'growth_requires_controller_reviewed_derivative':True},
                'execution_input_source':'malts_context.execution_inputs for the pinned Task and actor; copy existing IDs and complete capture templates, do not construct Grant IDs',
                'grant_creation_exposed':False,'evidence_file_policy':'PROTECTED_OPERATION_RESOURCE_NO_GROWTH',
                'host_authentication_enforced':False,'presentation_version':2,
                'authorization':{'evaluation':'NOT_EVALUATED','request_access':'UNDER_EXISTING_GRANTS' if self.enable_write else 'READ_ONLY',
                                 'enforced_by':'OPERATION_PREPARE_AND_DISPATCH','authority_issued_by_read':False}}

    def workflow(self,topic=_DEFAULT_WORKFLOW_TOPIC):
        """Serve one fixed packaged workflow; never a client-selected path."""
        if topic is _DEFAULT_WORKFLOW_TOPIC:topic=self.workflow_topic or 'task'
        paths={'task':'skills/v2/malts-v2-task-workflow/SKILL.md',
               'phase':'skills/malts-long-project-workspace-init/references/v2-phase.md',
               'artifact':'skills/malts-long-project-workspace-init/references/v2-artifact.md',
               'recovery':'skills/malts-long-project-workspace-init/references/v2-recovery.md'}
        if not isinstance(topic,str) or topic not in paths:raise ValueError('Invalid workflow topic')
        if self.workflow_topic is not None and topic!=self.workflow_topic:raise PermissionError('Workflow reference is outside the selected read scope')
        path=Path(__file__).resolve().parents[1]/paths[topic]
        _regular_path(path)
        with path.open('rb') as stream: data=stream.read(32769)
        if len(data)>32768: raise ValueError('Packaged workflow exceeds reference budget')
        result={'kind':'WORKFLOW_REFERENCE','name':'malts-v2-task-workflow' if topic=='task' else 'malts-v2-'+topic+'-reference','sha256':hashlib.sha256(data).hexdigest(),
                'content':data.decode('utf-8-sig'),'authority_issued':False,'writes_performed':False,
                'scope':'Packaged MALTS reference only; this content does not authorize operations.'}
        if topic!='task':result['topic']=topic
        return result

    def context(self,arguments):
        if not isinstance(arguments,dict) or set(arguments)-{'task_id','limit','cursor'} or 'task_id' not in arguments:
            raise ValueError('Invalid context fields')
        with closing(StateStore(self.state_dir/'state.db',readonly=True)) as store:
            store.connection.execute('BEGIN')
            try:
                self.check_store(store)
                if self.task_id is not None and arguments['task_id']!=self.task_id:raise PermissionError('Context exceeds pinned Task')
                result=store.current_context(arguments['task_id'],limit=arguments.get('limit',20),cursor=arguments.get('cursor'))
                result['authorization']['request_access']='UNDER_EXISTING_GRANTS' if self.enable_write else 'READ_ONLY'
                if self.enable_write and self.task_id is not None:
                    result['execution_inputs']=self._execution_inputs(store,limit=arguments.get('limit',20))
                store.connection.execute('COMMIT')
                return result
            except BaseException:
                if store.connection.in_transaction: store.connection.execute('ROLLBACK')
                raise

    def _execution_inputs(self,store,*,limit):
        """Bounded metadata only, in the same context snapshot; never issue rights.

        Include revoked/expired records explicitly rather than imply readiness.
        Execution still rechecks admission, fencing, grants and all budgets.
        """
        rows=store.connection.execute('''SELECT grant_id,resource,effect,revoked,expires_at,max_operations
            FROM execution_grant WHERE task_id=? AND task_revision=? AND actor=?
            ORDER BY grant_id LIMIT ?''',(self.task_id,self.task_revision,self.actor,limit+1)).fetchall()
        grants=[dict(zip(('grant_id','resource','effect','revoked','expires_at','max_operations'),row)) for row in rows[:limit]]
        for grant in grants:grant['revoked']=bool(grant['revoked'])
        templates=[];template_truncated=False
        if self.allow_protected_input_capture:
            criteria=store.task(self.task_id)['acceptance']
            template_truncated=len(criteria)>limit
            for criterion in criteria[:limit]:
                templates.append({'owner':self.project_id,
                    'target':{'task_id':self.task_id,'task_revision':self.task_revision,'criterion':criterion['criterion_id']},
                    'content_class':'protected-artifact','sensitivity':'unknown',
                    'redaction_policy_version':'protected-capture-v1',
                    'verification_scope':'Preimage of the resource of the selected existing update-file Grant only',
                    'review_ref':'host:configured-protected-input-capture',
                    'retention':{'reuse_until':None,'preserve_recovery_references':True},
                    'access_scope':{'project_id':self.project_id,'purposes':['verification','recovery','derivation']}})
        return {'existing_grants':grants,'grants_truncated':len(rows)>limit,
                'preimage_policy_templates':templates,'templates_truncated':template_truncated,
                'scope':'PINNED_TASK_REVISION_AND_ACTOR','authorization_evaluated':False,
                'authority_issued_by_read':False,'writes_performed':False,
                'capture_template_is_sanitization_proof':False}

    def verify_task(self,arguments):
        if not isinstance(arguments,dict) or set(arguments)!={'task_id'} or not isinstance(arguments['task_id'],str):
            raise ValueError('Invalid Task verification fields')
        from v2_acceptance import Acceptance
        from v2_evidence import BlobStore
        with closing(StateStore(self.state_dir/'state.db',readonly=True)) as store:
            store.connection.execute('BEGIN')
            try:
                self.check_store(store)
                if self.task_id is not None and arguments['task_id']!=self.task_id:
                    raise PermissionError('Verification exceeds pinned Task')
                if store.task(arguments['task_id'])['project_id']!=self.project_id:
                    raise PermissionError('Verification exceeds pinned Project')
                result=Acceptance(store,BlobStore(self.state_dir/'blobs',readonly=True)).verify_task_completion(task_id=arguments['task_id'])
                store.connection.execute('COMMIT')
                return result
            except BaseException:
                if store.connection.in_transaction:store.connection.execute('ROLLBACK')
                raise

    def request(self,request):
        if not self.enable_write: raise PermissionError('Bridge is read-only')
        if self.tool_root is not None:
            from v2_runtime_admission import runtime_admission
            with runtime_admission(self.tool_root):
                return self._request(request)
        return self._request(request)

    def _request(self,request):
        if not self.enable_write: raise PermissionError('Bridge is read-only')
        if not isinstance(request,dict) or set(request)!={'action','arguments'} or request['action'] not in self.client_actions() or not isinstance(request['arguments'],dict):
            raise PermissionError('Action is outside the configured client surface')
        action=request['action']; arguments=dict(request['arguments'])
        if action=='operation.prepare':
            capture_ref=self.authority_ref if self.allow_protected_input_capture else None
            if arguments.get('capture_authority_ref',capture_ref)!=capture_ref:raise HostBoundFieldError('capture_authority_ref')
            arguments['capture_authority_ref']=capture_ref
        signature=inspect.signature(ACTIONS[action])
        for key,value in (('actor',self.actor),('owner',self.project_id),('project_id',self.project_id),('authority_ref',self.authority_ref)):
            if key in signature.parameters:
                if key in arguments and arguments[key]!=value: raise HostBoundFieldError(key)
                arguments[key]=value
        if action=='evidence.record':
            if not self.allow_protected_input_capture:raise PermissionError('Evidence capture requires Host capture authority')
            descriptor=arguments.get('descriptor')
            if (not isinstance(descriptor,dict) or descriptor.get('content_class')!='protected-artifact' or
                    descriptor.get('sensitivity')!='unknown' or
                    not isinstance(descriptor.get('access_scope'),dict) or
                    not isinstance(descriptor['access_scope'].get('purposes'),list) or
                    'growth' in descriptor.get('access_scope',{}).get('purposes',[])):
                raise PermissionError('Client file evidence must be protected-artifact/unknown without Growth access')
            for key,value in (('method','declared-review'),('evidence_level','D')):
                if key in arguments and arguments[key]!=value: raise PermissionError('Client review cannot impersonate a stronger verifier')
                arguments[key]=value
        def guard(store):
            if self.tool_root is not None:store.require_execution_ready()
            self._check_worker(store)
            self._check_task_arguments(store,arguments)
        with closing(StateStore(self.state_dir/'state.db',transaction_guard=guard)) as store:
            guard(store)
            def evidence_reader(value):
                path=Path(value)
                if not path.is_absolute(): path=self.resource_root/path
                path=Path(os.path.abspath(path))
                if not path.is_relative_to(Path(os.path.abspath(self.resource_root))):
                    raise PermissionError('Evidence path is outside the bound resource root')
                _regular_path(path)
                if not path.resolve().is_relative_to(self.resource_root.resolve()): raise PermissionError('Evidence path is outside the bound resource root')
                row=store.connection.execute('''SELECT g.resource,g.actor,o.state FROM operation o JOIN execution_grant g ON g.grant_id=o.grant_id
                    WHERE o.operation_id=?''',(arguments.get('operation_id'),)).fetchone()
                if row is None or row[1]!=self.actor or row[2] not in {'OBSERVED','ACCEPTED'} or (self.resource_root/row[0]).resolve()!=path.resolve():
                    raise PermissionError('Evidence file is not the granted operation resource')
                return read_source_bytes(self.resource_root,path.relative_to(self.resource_root).as_posix(),max_bytes=16777216)['raw_bytes']
            return execute_request(store,{'action':action,'arguments':arguments},evidence_reader=evidence_reader,required_resource_root=self.resource_root)


def build_server(policy):
    # Optional dependency is loaded only for this entry, never for core/CLI.
    import anyio
    import jsonschema
    import mcp.types as types
    from mcp.server.lowlevel import Server
    server=Server('malts-v2-candidate',version=f'candidate-interface-{MCP_APPLICATION_INTERFACE_VERSION}')
    empty={'type':'object','additionalProperties':False}
    schemas={
        'malts_actions':empty,
        'malts_workflow':{'type':'object','properties':{'topic':{'type':'string','enum':[policy.workflow_topic] if policy.workflow_topic is not None else ['task','phase','artifact','recovery']}},'additionalProperties':False},
        'malts_verify_task':{'type':'object','properties':{'task_id':{'type':'string'}},'required':['task_id'],'additionalProperties':False},
        'malts_context':{'type':'object','properties':{'task_id':{'type':'string'},'limit':{'type':'integer','minimum':1,'maximum':100},'cursor':{'type':['object','null']}},'required':['task_id'],'additionalProperties':False},
        'malts_request':{'type':'object','properties':{'action':{'type':'string','enum':sorted(policy.client_actions())},'arguments':{'type':'object'}},'required':['action','arguments'],'additionalProperties':False},
    }
    @server.list_tools()
    async def list_tools():
        names=['malts_actions','malts_context','malts_workflow','malts_verify_task']+(['malts_request'] if policy.enable_write else [])
        descriptions={'malts_actions':'Inspect the pinned project policy and available action arguments.',
            'malts_verify_task':'Recheck current Task acceptance evidence within the bound scope. Preserves history and grants no execution permission.',
            'malts_workflow':'Read one packaged workflow: task (default), phase, artifact or recovery. Select the topic for the requested work instead of searching the whole guide. No file paths or operation permission.',
            'malts_context':'Read bounded current Task state; no implicit initialization or authority.',
            'malts_request':'Execute one configured action under existing Grants. Keep stable business IDs; inspect unknown effects after interruption.'}
        return [types.Tool(name=name,description=descriptions[name],inputSchema=schemas[name],
                           annotations=types.ToolAnnotations(readOnlyHint=name!='malts_request',destructiveHint=name=='malts_request',openWorldHint=False)) for name in names]

    def call(name,arguments):
        try:
            if name not in schemas or (name=='malts_request' and not policy.enable_write): raise PermissionError('Tool not enabled')
            # Own error conversion avoids exposing jsonschema's echoed values.
            try: jsonschema.Draft202012Validator(schemas[name]).validate(arguments)
            except jsonschema.ValidationError as error:
                if name=='malts_request' and error.validator=='enum' and list(error.path)==['action']:
                    raise PermissionError('Action is not enabled for this client') from None
                raise ValueError('Tool input schema mismatch') from None
            result=(policy.contracts() if name=='malts_actions' else (policy.workflow(arguments['topic']) if 'topic' in arguments else policy.workflow()) if name=='malts_workflow'
                    else policy.context(arguments) if name=='malts_context' else policy.verify_task(arguments) if name=='malts_verify_task' else policy.request(arguments))
            return types.CallToolResult(content=[types.TextContent(type='text',text=json.dumps(result,ensure_ascii=False))],structuredContent=result,isError=False)
        except (OSError,ValueError,TypeError,KeyError,sqlite3.Error) as error:
            result=safe_error(error)
            return types.CallToolResult(content=[types.TextContent(type='text',text=json.dumps(result,ensure_ascii=False))],structuredContent=result,isError=True)

    @server.call_tool(validate_input=False)
    async def call_tool(name,arguments):
        return await anyio.to_thread.run_sync(call,name,arguments)
    return server


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # Startup errors can contain credentials or arbitrary Host arguments.
        # Keep the protocol stream empty and never echo argparse's raw message.
        self.exit(2, json.dumps({'decision':'ERROR','error_code':'CLI_ARGUMENTS',
                                'message':'Invalid command arguments; consult --help.'})+'\n')


def main():
    parser=SafeArgumentParser(description=__doc__)
    parser.add_argument('--state-dir',type=Path,required=True); parser.add_argument('--resource-root',type=Path,required=True)
    parser.add_argument('--project-id',required=True); parser.add_argument('--actor')
    parser.add_argument('--authority-ref'); parser.add_argument('--enable-write',action='store_true')
    parser.add_argument('--allow-protected-input-capture',action='store_true')
    parser.add_argument('--tool-root',type=Path)
    parser.add_argument('--task-id');parser.add_argument('--task-revision',type=int);parser.add_argument('--dispatch-id')
    parser.add_argument('--workflow-topic',choices=['phase','artifact','recovery'])
    args=parser.parse_args()
    try:
        policy=BoundProject(**vars(args))
        import anyio
        from mcp.server.stdio import stdio_server
        # SDK transport details are not business logs; do not echo arbitrary
        # client tool names through SDK warnings into the application transcript.
        logging.getLogger('mcp').setLevel(logging.CRITICAL)
        server=build_server(policy)
        async def run():
            async with stdio_server() as (reader,writer):
                await server.run(reader,writer,server.create_initialization_options())
        anyio.run(run)
        return 0
    except ImportError:
        print('MCP_SDK_REQUIRED: install the candidate optional requirements in an isolated environment.',file=sys.stderr); return 2
    except (OSError,ValueError,TypeError,KeyError,sqlite3.Error) as error:
        print(json.dumps(safe_error(error)),file=sys.stderr); return 2


if __name__=='__main__': raise SystemExit(main())
