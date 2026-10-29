"""Controller-owned, input-bound observations of real Agent routes.

This is scoped qualification evidence, not Host authentication. Workers cannot
write these records through MCP. Public summaries exclude paths and native IDs.
"""
import hashlib,json,re,uuid
from datetime import datetime,timezone
from pathlib import Path
from v2_definition_content import encode,decode
from v2_evidence import _regular_path

CAPABILITIES=frozenset({'dispatch','result','readonly','bounded_write','cancel','recovery',
    'no_duplicate_launch','budget','configuration_drift','independent_review','parallel','timeout','native_close'})

def file_inputs(paths):
    result={}
    for value in paths:
        path=Path(value).absolute();_regular_path(path)
        result[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    return result

def _identifier(value):
    if not isinstance(value,str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',value) is None:
        raise ValueError('Bounded route or case identifier required')
    return value

def _inputs(value):
    if not isinstance(value,dict) or not value or len(value)>256:raise ValueError('Exact reviewed input inventory required')
    for path,digest in value.items():
        if not isinstance(path,str) or not Path(path).is_absolute():raise ValueError('Absolute private input identity required')
        if digest is not None and (not isinstance(digest,str) or re.fullmatch('[a-f0-9]{64}',digest) is None):raise ValueError('Input SHA-256 required')
    return dict(value)

def _case(value):
    fields={'case_id','capability','outcome','kind','native_id','verification','receipt_ref'}
    if not isinstance(value,dict) or set(value)!=fields:raise ValueError('Closed qualification case required')
    _identifier(value['case_id'])
    if value['capability'] not in CAPABILITIES or value['outcome'] not in {'PASS','FAIL','UNKNOWN','NOT_RUN'}:
        raise ValueError('Invalid qualification outcome or capability')
    if value['kind'] not in {'REAL_HOST','COMPONENT','SYNTHETIC'}:raise ValueError('Explicit evidence layer required')
    if value['native_id'] is not None and (not isinstance(value['native_id'],str) or not 1<=len(value['native_id'])<=512):raise ValueError('Invalid private native identity')
    if not isinstance(value['verification'],dict) or not isinstance(value['receipt_ref'],str) or not value['receipt_ref']:
        raise ValueError('Verification details and retained receipt required')
    if value['outcome']=='PASS' and value['kind']=='REAL_HOST' and (value['native_id'] is None or not value['verification']):
        raise ValueError('A real PASS needs actual identity and verification details')
    if len(json.dumps(value,ensure_ascii=False).encode('utf-8'))>65536:raise ValueError('Qualification case exceeds limit')
    return dict(value)

def inputs_digest(inputs):
    return hashlib.sha256(json.dumps(_inputs(inputs),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()

def _verify_receipt(case,*,route_id,inputs,profile_binding):
    """Verify retained bytes and concrete checks; labels alone cannot pass.

    The trusted controller still supplies real Host observations. This check
    does not turn a same-user file into independent OS/Host authentication.
    """
    if case['kind']!='REAL_HOST' or case['outcome']!='PASS':return
    verification=case['verification']
    if set(verification)!={'receipt_sha256'} or not isinstance(verification['receipt_sha256'],str):
        raise ValueError('A real PASS requires a hashed retained execution receipt')
    path=Path(case['receipt_ref'])
    if not path.is_absolute():raise ValueError('Exact retained execution receipt required')
    _regular_path(path)
    raw=path.read_bytes()
    if len(raw)>1048576 or hashlib.sha256(raw).hexdigest()!=verification['receipt_sha256']:
        raise ValueError('Retained execution receipt bytes differ')
    receipt=json.loads(raw.decode('utf-8-sig'))
    required={'format','case_id','native_id','outcome','checks','execution_observation','route_id','capability','inputs_sha256','profile_binding'}
    if not isinstance(receipt,dict) or set(receipt)!=required or receipt['format']!='malts.agent-case-receipt.v2':
        raise ValueError('Execution receipt contract differs')
    if (receipt['route_id']!=route_id or receipt['capability']!=case['capability'] or
        receipt['inputs_sha256']!=inputs_digest(inputs) or receipt['profile_binding']!=profile_binding):
        raise ValueError('Execution receipt route, capability or reviewed inputs differ')
    if receipt['case_id']!=case['case_id'] or receipt['native_id']!=case['native_id'] or receipt['outcome']!='PASS':
        raise ValueError('Execution receipt identity or outcome contradicts case')
    observation=receipt['execution_observation']
    if (not isinstance(observation,dict) or observation.get('native_id')!=case['native_id'] or
        observation.get('state')!='EXITED' or observation.get('quiesced') is not True):
        raise ValueError('Real PASS requires observed settled execution')
    checks=receipt['checks']
    if not isinstance(checks,list) or not 1<=len(checks)<=64:raise ValueError('Concrete execution checks required')
    for check in checks:
        if not isinstance(check,dict):raise ValueError('Invalid execution check')
        if check.get('type')=='file-sha256' and set(check)=={'type','path','sha256'}:
            p=Path(check['path']);_regular_path(p)
            if not p.is_absolute() or hashlib.sha256(p.read_bytes()).hexdigest()!=check['sha256']:raise ValueError('Verified output file changed')
        elif check.get('type')=='file-absent' and set(check)=={'type','path'}:
            p=Path(check['path']);_regular_path(p)
            if not p.is_absolute() or p.exists():raise ValueError('Prohibited output file exists')
        elif check.get('type')=='observation-equals' and set(check)=={'type','field','expected'}:
            if check['field'] not in {'state','quiesced','return_status','cancel_acknowledged'} or observation.get(check['field'])!=check['expected']:
                raise ValueError('Execution observation contradicts the required outcome')
        else:raise ValueError('Unsupported execution check; arbitrary passed flags are not proof')

class QualificationStore:
    """Append-only protected receipts; constructing/status never creates files."""
    def __init__(self,root):
        self.root=Path(root).absolute();_regular_path(self.root)

    def record(self,route_id,inputs,cases,*,authority_ref,required_capabilities=None,profile_binding=None):
        route_id=_identifier(route_id);inputs=_inputs(inputs)
        if not isinstance(authority_ref,str) or not authority_ref.strip():raise ValueError('Controller review authority required')
        if not isinstance(cases,list) or not 1<=len(cases)<=128:raise ValueError('Bounded actual cases required')
        cases=[_case(value) for value in cases]
        for case in cases:_verify_receipt(case,route_id=route_id,inputs=inputs,profile_binding=profile_binding)
        if len({v['case_id'] for v in cases})!=len(cases):raise ValueError('Duplicate case identity')
        required=set(required_capabilities or {'dispatch','result','readonly','bounded_write','cancel','recovery','no_duplicate_launch','budget','configuration_drift'})
        if not required or not required<=CAPABILITIES:raise ValueError('Explicit supported-capability contract required')
        if file_inputs(inputs)!=inputs:raise ValueError('Inputs changed before qualification capture')
        directory=self.root/route_id;_regular_path(directory);directory.mkdir(parents=True,exist_ok=True)
        identity=uuid.uuid4().hex
        body={'route_id':route_id,'inputs':inputs,'cases':cases,'authority_ref':authority_ref,
              'profile_binding':profile_binding,
              'required_capabilities':sorted(required),'observed_at':datetime.now(timezone.utc).isoformat(),
              'assurance':'CONTROLLER_REVIEWED_REAL_HOST_OBSERVATIONS','whole_host_isolation':False}
        protected=encode(body,'agent-route-qualification','receipt',identity,1,'body')
        path=directory/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+identity+'.json')
        with path.open('x',encoding='utf-8',newline='\n') as out:
            json.dump({'format':'malts.agent-qualification.v1','record_id':identity,'protected_body':protected},out,ensure_ascii=False)
        return self.status(route_id,inputs,profile_binding=profile_binding)

    def status(self,route_id,inputs,*,profile_binding=None):
        route_id=_identifier(route_id);inputs=_inputs(inputs)
        public={'route_id':route_id,'status':'NOT_TESTED','verified_capabilities':[],
            'required_capabilities':[],'whole_host_isolation':False,'host_authentication':False,
            'assurance':'CONTROLLER_REVIEWED_OBSERVATIONS_NOT_OS_AUTHENTICATION','writes_performed':False}
        directory=self.root/route_id;_regular_path(directory)
        if not directory.exists():return public
        files=sorted(directory.glob('*.json'))
        if not files:return public
        if len(files)>1000:raise ValueError('Qualification history exceeds bounded read')
        path=files[-1];_regular_path(path)
        raw=json.loads(path.read_text('utf-8'))
        if set(raw)!={'format','record_id','protected_body'} or raw['format']!='malts.agent-qualification.v1':raise ValueError('Invalid qualification receipt')
        body=decode(raw['protected_body'],'agent-route-qualification','receipt',raw['record_id'],1,'body')
        if body['route_id']!=route_id:raise ValueError('Qualification route binding differs')
        public.update(required_capabilities=body['required_capabilities'],observed_at=body['observed_at'],history_records=len(files))
        if body['inputs']!=inputs or body['profile_binding']!=profile_binding:return {**public,'status':'PROFILE_CHANGED'}
        if file_inputs(inputs)!=inputs:return {**public,'status':'STALE_INPUTS'}
        cases=[_case(v) for v in body['cases']]
        try:
            for case in cases:_verify_receipt(case,route_id=route_id,inputs=inputs,profile_binding=profile_binding)
        except (ValueError,OSError,KeyError,TypeError):return {**public,'status':'EVIDENCE_INVALID'}
        passed={v['capability'] for v in cases if v['kind']=='REAL_HOST' and v['outcome']=='PASS'}
        failed={v['capability'] for v in cases if v['outcome']=='FAIL'}
        verified=passed-failed
        status='FAILED' if failed else 'QUALIFIED' if set(body['required_capabilities'])<=verified else 'PARTIALLY_VERIFIED' if verified else 'NOT_VERIFIED'
        return {**public,'status':status,'verified_capabilities':sorted(verified),'failed_capabilities':sorted(failed),
                'case_counts':{outcome:sum(v['outcome']==outcome for v in cases) for outcome in ('PASS','FAIL','UNKNOWN','NOT_RUN')}}

def capabilities():
    return {'controller_cli':'tools/malts_agents.py','qualification_scope':'PER_HOST_ROUTE_PROFILE',
        'cli_hosts':['codex','claude-code','opencode','deepseek-harness'],'native_routes':['codex-native'],
        'evidence_required':True,'qualification_implied_by_installation':False,'whole_host_isolation':False,
        'default_delegation':False,'worker_can_launch_successors':False,
        'read_only_entry_creates_no_records':True,'unqualified_global_flags_are_not_route_selection':True}
