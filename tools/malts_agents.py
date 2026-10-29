#!/usr/bin/env python3
"""Trusted-controller real Agent orchestration. Preview by default; no daemon.

Use this controller from the verified source/installation, never from a Worker
endpoint. Existing user authorization, task revision, Grants and dispatch budgets
remain required. Native relay receipts must come from actual Host tool calls.
"""
import argparse,hashlib,json,sys
from contextlib import closing
from pathlib import Path
from v2_agent_profiles import AgentProfile,HOSTS
from v2_agent_qualification import QualificationStore,capabilities
from v2_evidence import _regular_path
from v2_entry import inspect_workspace_entry
from v2_state_store import StateStore
from v2_host_execution import HostExecutions,configure_budget
from v2_process_host import SupervisedProcessHost,initialize as initialize_process
from v2_native_agent_host import NativeAgentHost,initialize as initialize_native

def required_capabilities(mode,additional=()):
    default={'dispatch','result','readonly'} if mode=='review' else {'dispatch','result','bounded_write'}
    return default|set(additional)

def _load(path):
    path=Path(path).absolute();_regular_path(path)
    data=path.read_bytes()
    if len(data)>1048576:raise ValueError('Controller input exceeds bound')
    return json.loads(data.decode('utf-8-sig')),hashlib.sha256(data).hexdigest()

def resolve_profile(path):
    value,digest=_load(path)
    allowed={'host','executable','executable_sha256','working_root','config_files','mode','state_dir','project_id','task_id','task_revision',
        'authority_ref','python_executable','model','effort','launcher_args','launcher_files','harness_restore_auth','harness_credentials_path','execution_root','tool_root'}
    if not isinstance(value,dict) or set(value)-allowed:raise ValueError('Closed reviewed profile file required')
    entry=inspect_workspace_entry(value['working_root'])
    if entry.get('decision') not in {'ADOPTED_WORKSPACE','NATIVE_WORKSPACE'}:raise ValueError('Existing verified workspace required')
    if (Path(value['state_dir']).resolve()!=Path(entry['state_dir']).resolve() or value['project_id']!=entry['project_id']):
        raise ValueError('Profile differs from selected workspace binding')
    return AgentProfile(**value),value,digest

def route_binding(profile,*,native=False,role='malts_verifier'):
    if not native:return profile.qualification_binding
    if profile.host!='codex':raise ValueError('Codex native route requires a Codex profile')
    if role not in {'malts_explorer','malts_planner','malts_verifier','malts_worker'}:
        raise ValueError('Unsupported native responsibility')
    if (profile.mode=='worker')!=(role=='malts_worker'):
        raise ValueError('Native responsibility and reviewed write mode differ')
    return hashlib.sha256(json.dumps(['codex-native',role,profile.qualification_binding]).encode()).hexdigest()

def original_backend(store,dispatch_id,profile):
    row=store.connection.execute('SELECT backend_key,task_id,task_revision,project_id FROM host_dispatch WHERE dispatch_id=?',(dispatch_id,)).fetchone()
    if row is None:raise ValueError('Unknown original dispatch')
    if row[1:]!=(profile.task_id,profile.task_revision,profile.project_id):
        raise ValueError('Original dispatch differs from selected Task binding')
    return row[0]

def parser():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('capabilities')
    init=sub.add_parser('host-init');init.add_argument('--host-root',type=Path,required=True);init.add_argument('--host-id',required=True)
    init.add_argument('--native',action='store_true');init.add_argument('--apply',action='store_true')
    budget=sub.add_parser('budget');budget.add_argument('--workspace',type=Path,required=True);budget.add_argument('--policy-file',type=Path,required=True)
    budget.add_argument('--expected-policy-sha256');budget.add_argument('--apply',action='store_true')
    for name in ('inspect','prepare','launch','poll','cancel','result','native-call','native-query','native-receipt'):
        cmd=sub.add_parser(name);cmd.add_argument('--profile-file',type=Path,required=True);cmd.add_argument('--host-root',type=Path,required=True)
        cmd.add_argument('--native',action='store_true');cmd.add_argument('--role',default='malts_verifier')
        cmd.add_argument('--dispatch-id');cmd.add_argument('--invocation-id');cmd.add_argument('--attempt-id');cmd.add_argument('--strategy-ref')
        cmd.add_argument('--authority-ref');cmd.add_argument('--request-file',type=Path);cmd.add_argument('--receipt-file',type=Path)
        cmd.add_argument('--expected-profile-sha256');cmd.add_argument('--expected-request-sha256');cmd.add_argument('--apply',action='store_true')
        cmd.add_argument('--qualification-root',type=Path);cmd.add_argument('--require-capability',action='append',default=[])
        cmd.add_argument('--qualification-run',action='store_true',help='Explicit bounded controller qualification, not ordinary qualified execution')
    qual=sub.add_parser('qualification-status');qual.add_argument('--profile-file',type=Path,required=True);qual.add_argument('--receipt-root',type=Path,required=True);qual.add_argument('--route-id',required=True)
    qual.add_argument('--native',action='store_true');qual.add_argument('--role',default='malts_verifier')
    return p

def execute(args):
    if args.command=='capabilities':return capabilities()
    if args.command=='host-init':
        if not args.apply:return {'decision':'PREVIEW','action':'host-init','native':args.native,'writes_performed':False}
        (initialize_native if args.native else initialize_process)(args.host_root,host_id=args.host_id)
        return {'decision':'INITIALIZED','launch_performed':False}
    if args.command=='budget':
        entry=inspect_workspace_entry(args.workspace);policy,digest=_load(args.policy_file)
        if policy.get('project_id')!=entry.get('project_id'):raise ValueError('Budget project differs from workspace')
        if not args.apply:return {'decision':'PREVIEW','policy_sha256':digest,'writes_performed':False}
        if digest!=args.expected_policy_sha256:raise ValueError('Reviewed budget policy changed')
        with closing(StateStore(Path(entry['state_dir'])/'state.db')) as store:return {'decision':configure_budget(store,**policy)}
    profile,definition,digest=resolve_profile(args.profile_file)
    binding=route_binding(profile,native=args.native,role=args.role)
    if args.command=='qualification-status':return QualificationStore(args.receipt_root).status(args.route_id,profile.inputs,profile_binding=binding)
    if args.command=='inspect':
        return {'decision':'REVIEWED_PROFILE','profile_sha256':digest,'host':profile.host,'mode':profile.mode,
            'profile_revision':profile.profile_revision,'configuration_guard_count':len(profile.guards),'model_configured':profile.model,
            'qualification_binding':binding,
            'effective_model_verified':False,'writes_performed':False,'launch_performed':False}
    route_id=('codex-native' if args.native else profile.host+'-cli')+'-'+profile.mode
    if args.command in {'prepare','launch'}:
        needed=required_capabilities(profile.mode,args.require_capability)
        if args.native and profile.mode=='worker':needed.add('bounded_write')
        qualification=None if args.qualification_root is None else QualificationStore(args.qualification_root).status(route_id,profile.inputs,profile_binding=binding)
        ready=qualification is not None and needed<=set(qualification['verified_capabilities']) and qualification['status'] in {'QUALIFIED','PARTIALLY_VERIFIED'}
        if not ready and not args.qualification_run:
            return {'decision':'QUALIFICATION_REQUIRED','route_id':route_id,'required_capabilities':sorted(needed),
                'qualification':qualification,'writes_performed':False,'launch_performed':False}
        if args.qualification_run and not args.authority_ref:raise ValueError('Qualification launch requires explicit existing controller authorization')
    if not args.dispatch_id:raise ValueError('Exact original dispatch ID required')
    state=Path(definition['state_dir'])
    host=NativeAgentHost(args.host_root,role=args.role,profile_binding=binding,inputs=profile.inputs) if args.native else SupervisedProcessHost(args.host_root,profile)
    if args.command=='native-call' and not args.apply:
        if not args.native:raise ValueError('Native relay required')
        with closing(StateStore(state/'state.db',readonly=True)) as store:
            key=original_backend(store,args.dispatch_id,profile)
        pending=host.pending_call(backend_key=key)
        return {'decision':'PREVIEW','call':None if pending is None else {'call_id':pending['call_id'],'tool':pending['tool']},
            'profile_sha256':digest,'execution_authorized':False,'admission_requires_apply':True,'writes_performed':False}
    request=request_digest=None
    if args.request_file is not None:request,request_digest=_load(args.request_file)
    if not args.apply:
        if args.command=='prepare':profile._validate(request)
        return {'decision':'PREVIEW','action':args.command,'profile_sha256':digest,'request_sha256':request_digest,'writes_performed':False,'launch_performed':False}
    if args.expected_profile_sha256!=digest:raise ValueError('Reviewed controller profile changed')
    if request_digest is not None and request_digest!=args.expected_request_sha256:raise ValueError('Reviewed launch request changed')
    with closing(StateStore(state/'state.db')) as store:
        service=HostExecutions(store,host,tool_root=profile.tool_root)
        if args.command=='prepare':
            if args.authority_ref!=profile.authority_ref:raise ValueError('Dispatch authority differs from reviewed profile')
            return service.prepare(dispatch_id=args.dispatch_id,attempt_id=args.attempt_id,task_id=profile.task_id,task_revision=profile.task_revision,
                strategy_ref=args.strategy_ref,request=request,authority_ref=args.authority_ref)
        key=original_backend(store,args.dispatch_id,profile)
        if args.command=='native-query':
            if not args.native:raise ValueError('Native relay required')
            host.request_query(backend_key=key);return service.reserve_native_call(dispatch_id=args.dispatch_id)
        if args.command=='native-call':
            if not args.native:raise ValueError('Native relay required')
            return service.reserve_native_call(dispatch_id=args.dispatch_id)
        if args.command=='native-receipt':
            if not args.native:raise ValueError('Native relay required')
            receipt,_=_load(args.receipt_file)
            return service.observe_native_receipt(dispatch_id=args.dispatch_id,**receipt)
        if args.command=='result':
            return {'decision':'UNREVIEWED_PRIVATE_RESULT','result':host.private_result(backend_key=key,purpose='verification'),'task_accepted':False}
        if args.command=='launch':return service.launch(dispatch_id=args.dispatch_id,invocation_id=args.invocation_id)
        if args.command=='poll':return service.poll(dispatch_id=args.dispatch_id,invocation_id=args.invocation_id)
        if args.command=='cancel':
            if args.native:
                cancellation=service.native_cancel_request(dispatch_id=args.dispatch_id)
                if cancellation['decision']=='RECOVERY_RECONCILIATION_REQUIRED':return cancellation
                return service.reserve_native_call(dispatch_id=args.dispatch_id)
            return service.cancel(dispatch_id=args.dispatch_id,invocation_id=args.invocation_id)
    raise ValueError('Unsupported controller operation')

def main(argv=None):
    args=parser().parse_args(argv)
    try:
        value=execute(args);print(json.dumps(value,ensure_ascii=False));return 0
    except Exception as error:
        # Exact exception and private inputs belong in controller-owned recovery
        # evidence, never in a public diagnostic or a Worker-facing response.
        from v2_service import safe_error
        print(json.dumps(safe_error(error),ensure_ascii=False));return 1

if __name__=='__main__':raise SystemExit(main())
