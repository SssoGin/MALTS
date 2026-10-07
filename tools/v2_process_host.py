"""Persistent local supervisor adapter for trusted, reviewed process profiles.

No builtin model profile, shell, global install or daemon. Optional bounded
stdin/JSONL telemetry transport drops raw output and unknown event fields.
Each supervisor owns one bounded Job and exits after recording quiescence.
Its journal is Host-owned process evidence, not another MALTS Task authority.
"""
import argparse,hashlib,json,math,os,re,sqlite3,subprocess,sys,time,uuid
from pathlib import Path
from contextlib import closing
# Needed only when the isolated Python supervisor is invoked by absolute file.
if __name__=='__main__':sys.path.insert(0,str(Path(__file__).resolve().parent))
from v2_definition_content import encode,decode
from v2_evidence import _regular_path
from v2_windows_job import WindowsJob,current_process_identity,process_identity_state
from v2_stdio import StdioPump, MAX_JSONL_LINE_BYTES

APPLICATION_ID=0x4D485354


def inspect_journal(root,*,expected_host_id=None,backend_key=None):
    """Bounded read-only diagnosis. No private spec/body or inferred quiescence."""
    root=Path(root).absolute();database=root/'host.db';_regular_path(database)
    report={'availability':'UNKNOWN','dispatch_state':'UNKNOWN','supervisor_state':None,
        'quiescence_verified':False,'writes_performed':False,'execution_authorized':False,
        'next_action':'PRESERVE_AND_RECONCILE'}
    if not database.exists():return {**report,'availability':'JOURNAL_MISSING'}
    try:
        with closing(_connect(root,readonly=True)) as c:
            identity=c.execute('SELECT host_id FROM identity WHERE singleton=1').fetchone()
            if identity is None:raise ValueError('Missing journal identity')
            if expected_host_id is not None and identity[0]!=expected_host_id:
                return {**report,'availability':'HOST_ID_MISMATCH'}
            report['availability']='AVAILABLE'
            if backend_key is None:return {**report,'next_action':'REOPEN_VERIFIED_ADAPTER'}
            row=c.execute('SELECT state,owner_identity FROM run WHERE backend_key=?',(backend_key,)).fetchone()
            if row is None:return {**report,'dispatch_state':'NOT_FOUND'}
            report['dispatch_state']=row[0]
            if row[1]:report['supervisor_state']=process_identity_state(json.loads(row[1]))
            if report['supervisor_state']=='LIVE':report['next_action']='QUERY_OR_CANCEL_ORIGINAL'
            return report
    except sqlite3.Error:return {**report,'availability':'JOURNAL_UNREADABLE'}
    except OSError:return {**report,'availability':'JOURNAL_UNREADABLE'}
    except (ValueError,TypeError,KeyError):return {**report,'availability':'JOURNAL_INCOMPATIBLE'}


class UnavailableProcessHost:
    """Query/cancel-only fail-closed adapter for a known but unavailable journal.

    Expected identities come from retained controller dispatch records. This
    never recreates a journal, launches a replacement, or claims cancellation.
    Reopen the verified real adapter after restoring access; do not upgrade this
    object into an executor merely because a file appears later.
    """
    quiescence_scope='ASSOCIATED_WINDOWS_JOB_PROCESSES'
    def __init__(self,root,*,host_id,profile_revision):
        for value in (host_id,profile_revision):
            if not isinstance(value,str) or not value or len(value)>512:raise ValueError('Retained Host identity required')
        self.root=Path(root).absolute();self.host_id=host_id;self.profile_revision=profile_revision
        self.diagnosis=inspect_journal(self.root,expected_host_id=host_id)
        if self.diagnosis['availability']=='AVAILABLE':raise ValueError('Reopen the available journal through its verified adapter')

    def validate_request(self,request):raise PermissionError('Unavailable Host is reconciliation-only')
    def start(self,**kwargs):raise PermissionError('Unavailable Host cannot start or replace work')

    def query(self,*,backend_key):
        if not isinstance(backend_key,str) or re.fullmatch('[a-f0-9]{32}',backend_key) is None:raise ValueError('Retained backend key required')
        return {'backend_key':backend_key,'native_id':None,'state':'UNKNOWN','quiesced':None,
            'cancel_acknowledged':None,'return_status':None,'effective_identity':None,'physical_requests':0}

    def cancel(self,*,backend_key):return self.query(backend_key=backend_key)


def _hash(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as source:
        for data in iter(lambda:source.read(1048576),b''):digest.update(data)
    return digest.hexdigest()


def _connect(root,*,readonly=False):
    database=Path(root)/'host.db';_regular_path(database)
    c=sqlite3.connect(database.as_uri()+('?mode=ro' if readonly else '?mode=rw'),uri=True,isolation_level=None,timeout=5)
    if c.execute('PRAGMA application_id').fetchone()[0]!=APPLICATION_ID or c.execute('PRAGMA user_version').fetchone()[0]!=3:
        c.close();raise ValueError('Unrecognized Host journal')
    required={'backend_key','profile_revision','spec_value','state','owner_identity','job_identity','cancel_requested',
              'cancel_acknowledged','quiesced','return_status','stop_reason','io_summary','private_events_value'}
    if {r[1] for r in c.execute('PRAGMA table_info(run)')}!=required:
        c.close();raise ValueError('Host journal shape does not match its version')
    c.execute('PRAGMA synchronous=FULL');return c


def initialize(root,*,host_id):
    current_process_identity()  # refuse unsupported profiles before creating Host state
    root=Path(root).absolute();_regular_path(root)
    if not isinstance(host_id,str) or not host_id or len(host_id)>128:raise ValueError('Explicit Host identifier required')
    root.mkdir()  # explicit initialization, never overwrite another Host journal
    with closing(sqlite3.connect(root/'host.db',isolation_level=None)) as c:
        c.executescript('''BEGIN IMMEDIATE;
        CREATE TABLE identity(singleton INTEGER PRIMARY KEY CHECK(singleton=1),instance_id TEXT NOT NULL,host_id TEXT NOT NULL);
        CREATE TABLE run(backend_key TEXT PRIMARY KEY,profile_revision TEXT NOT NULL,spec_value TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('ADMITTED','STARTING','RUNNING','EXITED','UNKNOWN')),
            owner_identity TEXT,job_identity TEXT,cancel_requested INTEGER NOT NULL DEFAULT 0,
            cancel_acknowledged INTEGER NOT NULL DEFAULT 0,quiesced INTEGER,return_status TEXT,stop_reason TEXT,io_summary TEXT,private_events_value TEXT);
        COMMIT;''')
        c.execute('BEGIN IMMEDIATE')
        c.execute('INSERT INTO identity VALUES (1,?,?)',(uuid.uuid4().hex,host_id))
        c.execute(f'PRAGMA application_id={APPLICATION_ID}');c.execute('PRAGMA user_version=3');c.execute('COMMIT')
    return root


class SupervisedProcessHost:
    profile_revision='windows-supervisor-v3'
    quiescence_scope='ASSOCIATED_WINDOWS_JOB_PROCESSES'
    def __init__(self,root,command_factory):
        self.root=Path(root).absolute();self.command_factory=command_factory;self._supervisors=[]
        with closing(_connect(self.root,readonly=True)) as c:
            self.instance_id,self.host_id=c.execute('SELECT instance_id,host_id FROM identity').fetchone()
        binding=getattr(command_factory,'profile_revision',None)
        if binding is not None and (not isinstance(binding,str) or not binding or len(binding)>256):
            raise ValueError('Invalid trusted command profile revision')
        self.profile_revision='windows-supervisor-v3:'+self.instance_id+(':'+binding if binding is not None else '')

    def _spec(self,request,*,actor=None):
        # The factory is trusted application code, never imported from a request.
        bound_factory=getattr(self.command_factory,'for_actor',None)
        spec=bound_factory(request,actor=actor) if actor is not None and bound_factory is not None else self.command_factory(request)
        required={'argv','cwd','wall_seconds'};optional={'stdin_text','event_protocol','max_output_bytes','max_line_bytes','max_events','capture_candidate_message','file_guards','runtime_tool_root'}
        if not isinstance(spec,dict) or not required<=set(spec) or set(spec)-(required|optional):raise ValueError('Closed process profile required')
        if (not isinstance(spec['argv'],list) or not spec['argv'] or any(not isinstance(v,str) or '\0' in v for v in spec['argv']) or
                not Path(spec['argv'][0]).is_absolute() or not Path(spec['argv'][0]).is_file() or
                not isinstance(spec['cwd'],str) or not Path(spec['cwd']).is_absolute() or not Path(spec['cwd']).is_dir()):
            raise ValueError('Invalid explicit process command')
        if type(spec['wall_seconds']) not in (float,int) or not math.isfinite(spec['wall_seconds']) or not .05<=spec['wall_seconds']<=3600:
            raise ValueError('A finite bounded process deadline is required')
        if 'runtime_tool_root' in spec:
            value=spec['runtime_tool_root']
            if not isinstance(value,str) or not Path(value).is_absolute():raise ValueError('Explicit absolute runtime tool root required')
            _regular_path(Path(value))
        if set(spec)&(optional-{'runtime_tool_root'}):
            spec={**spec,'stdin_text':spec.get('stdin_text',''),'event_protocol':spec.get('event_protocol','bounded-jsonl-v1'),
                  'max_output_bytes':spec.get('max_output_bytes',262144),'max_line_bytes':spec.get('max_line_bytes',16384),'max_events':spec.get('max_events',100)}
            if spec['event_protocol'] not in {'bounded-jsonl-v1','codex-jsonl-v1'} or not isinstance(spec['stdin_text'],str) or len(spec['stdin_text'].encode('utf-8'))>1048576:
                raise ValueError('Unsupported event profile or oversized stdin')
            capture=spec.get('capture_candidate_message',False)
            if type(capture) is not bool or (capture and spec['event_protocol']!='codex-jsonl-v1'):
                raise ValueError('Invalid candidate capture profile')
            _check_guards(spec.get('file_guards',[]))
            for key,maximum in (('max_output_bytes',16777216),('max_line_bytes',MAX_JSONL_LINE_BYTES),('max_events',1000)):
                if type(spec[key]) is not int or not 1<=spec[key]<=maximum:raise ValueError('Invalid stream budget')
        return {**spec,'executable_sha256':_hash(spec['argv'][0])}

    def validate_request(self,request):self._spec(request)

    def start(self,*,backend_key,actor,request):
        if not isinstance(backend_key,str) or re.fullmatch('[a-f0-9]{32}',backend_key) is None:raise ValueError('Generated backend key required')
        if not isinstance(actor,str) or not actor or len(actor)>256:raise ValueError('Explicit bounded actor identity required')
        current_process_identity()
        spec={**self._spec(request,actor=actor),'actor':actor}
        with closing(_connect(self.root)) as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT profile_revision,spec_value FROM run WHERE backend_key=?',(backend_key,)).fetchone()
            if old:
                if old[0]!=self.profile_revision or decode(old[1],self.instance_id,'process-host',backend_key,1,'spec')!=spec:
                    c.execute('ROLLBACK');raise ValueError('Backend key reused with another process profile')
                c.execute('COMMIT');return self.query(backend_key=backend_key)
            c.execute("INSERT INTO run(backend_key,profile_revision,spec_value,state) VALUES (?,?,?,'ADMITTED')",
                (backend_key,self.profile_revision,encode(spec,self.instance_id,'process-host',backend_key,1,'spec')))
            c.execute('COMMIT')
        # Lost launcher receipt is not retried: ADMITTED/STARTING remains query-only.
        process=subprocess.Popen([sys.executable,'-I','-S','-B',str(Path(__file__).resolve()),'--supervise',str(self.root),'--key',backend_key],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self._supervisors.append(process)
        until=time.monotonic()+2
        while time.monotonic()<until:
            result=self.query(backend_key=backend_key)
            if result['state']!='UNKNOWN':return result
            if process.poll() is not None:break
            time.sleep(.01)
        return self.query(backend_key=backend_key)

    def query(self,*,backend_key):
        result={'backend_key':backend_key,'native_id':None,'state':'UNKNOWN','quiesced':None,'cancel_acknowledged':None,
                'return_status':None,'effective_identity':None,'physical_requests':None}
        with closing(_connect(self.root,readonly=True)) as c:
            row=c.execute('SELECT state,owner_identity,job_identity,cancel_acknowledged,quiesced,return_status FROM run WHERE backend_key=?',(backend_key,)).fetchone()
        if row is None:return result
        result['cancel_acknowledged']=bool(row[3])
        if row[2]:
            identity=json.loads(row[2]);result['native_id']=identity['job_name']+':'+str(identity['root_creation_filetime'])
        if row[0]=='EXITED' and row[4]==1:
            return {**result,'state':'EXITED','quiesced':True,'return_status':row[5]}
        if row[0]=='RUNNING' and row[1] and process_identity_state(json.loads(row[1]))=='LIVE':
            return {**result,'state':'RUNNING','quiesced':False}
        return result  # absent/stale owner is not positive quiescence evidence

    def cancel(self,*,backend_key):
        with closing(_connect(self.root)) as c:
            c.execute('UPDATE run SET cancel_requested=1 WHERE backend_key=?',(backend_key,))
        return self.query(backend_key=backend_key)

    def stream_summary(self,*,backend_key):
        with closing(_connect(self.root,readonly=True)) as c:
            row=c.execute('SELECT io_summary FROM run WHERE backend_key=?',(backend_key,)).fetchone()
        return None if row is None or row[0] is None else json.loads(row[0])

    def reap_launchers(self,timeout=5):
        """Release completed local Popen wrappers; never kills a PID lookup."""
        for process in self._supervisors:process.wait(timeout=timeout)
        self._supervisors.clear()

    def private_result(self,*,backend_key,purpose):
        """Trusted controller retrieval; not an Agent action or Growth source."""
        if purpose not in {'verification','recovery'}:raise ValueError('Unsupported private result purpose')
        with closing(_connect(self.root,readonly=True)) as c:
            row=c.execute('SELECT private_events_value FROM run WHERE backend_key=?',(backend_key,)).fetchone()
        return None if row is None or row[0] is None else decode(row[0],self.instance_id,'process-host',backend_key,1,'events')


def _check_guards(guards):
    if not isinstance(guards,list) or len(guards)>128:raise ValueError('Invalid reviewed file inventory')
    for guard in guards:
        if (not isinstance(guard,dict) or set(guard)!={'path','sha256'} or not isinstance(guard['path'],str) or
                not Path(guard['path']).is_absolute() or (guard['sha256'] is not None and
                (not isinstance(guard['sha256'],str) or re.fullmatch('[a-f0-9]{64}',guard['sha256']) is None))):
            raise ValueError('Invalid reviewed file guard')
        path=Path(guard['path']);actual=_hash(path) if path.exists() else None
        if actual!=guard['sha256']:raise ValueError('Reviewed configuration input changed')


def supervise(root,key):
    root=Path(root).absolute();job=None;pump=None;launch_attempted=False
    with closing(_connect(root)) as c:
        c.execute('BEGIN IMMEDIATE')
        instance=c.execute('SELECT instance_id FROM identity').fetchone()[0]
        row=c.execute('SELECT state,spec_value,cancel_requested FROM run WHERE backend_key=?',(key,)).fetchone()
        if row is None or row[0]!='ADMITTED':c.execute('ROLLBACK');return 0
        owner=current_process_identity()
        c.execute("UPDATE run SET state='STARTING',owner_identity=? WHERE backend_key=?",(json.dumps(owner),key));c.execute('COMMIT')
        try:
            spec=decode(row[1],instance,'process-host',key,1,'spec')
            if row[2]:
                c.execute("UPDATE run SET state='EXITED',cancel_acknowledged=1,quiesced=1,return_status='NOT_STARTED',stop_reason='CANCEL_BEFORE_START' WHERE backend_key=?",(key,));return 0
            started=time.monotonic()
            streams=spec.get('event_protocol') in {'bounded-jsonl-v1','codex-jsonl-v1'}
            from contextlib import nullcontext
            from v2_runtime_admission import runtime_admission
            # Release before serving child MCP requests, which acquire this
            # same mutex independently. This is launch exclusion, not quiescence.
            with runtime_admission(spec['runtime_tool_root']) if 'runtime_tool_root' in spec else nullcontext():
                if _hash(spec['argv'][0])!=spec['executable_sha256']:raise ValueError('Reviewed executable changed')
                _check_guards(spec.get('file_guards',[]))
                launch_attempted=True
                job=WindowsJob.launch(spec['argv'],cwd=spec['cwd'],capture_stdio=streams)
            if streams:
                pump=StdioPump(job,spec['stdin_text'].encode('utf-8'),max_output_bytes=spec['max_output_bytes'],
                    max_line_bytes=spec['max_line_bytes'],max_events=spec['max_events'],protocol=spec['event_protocol'],
                    capture_candidate_message=spec.get('capture_candidate_message',False))
            identity=job.status()
            c.execute("UPDATE run SET state='RUNNING',job_identity=? WHERE backend_key=?",(json.dumps(identity),key))
            while True:
                observed=job.status()
                if observed['quiesced']:break
                if pump is not None and pump.stop.is_set():
                    job.cancel(reason='IO_LIMIT' if pump.error in {'OUTPUT_LIMIT','LINE_LIMIT','EVENT_LIMIT'} else 'IO_ERROR')
                    observed=job.wait(5);break
                cancel=c.execute('SELECT cancel_requested FROM run WHERE backend_key=?',(key,)).fetchone()[0]
                if cancel:
                    job.cancel();c.execute('UPDATE run SET cancel_acknowledged=1 WHERE backend_key=?',(key,))
                    observed=job.wait(5);break
                remaining=spec['wall_seconds']-(time.monotonic()-started)
                if remaining<=0:observed=job.wait(0);break
                time.sleep(min(.02,remaining))
            reason=observed['stop_reason']
            if pump is not None:
                summary=pump.finish()
                private=pump.private_values()
                protected=None if private is None else encode(private,instance,'process-host',key,1,'events')
                c.execute('UPDATE run SET io_summary=?,private_events_value=? WHERE backend_key=?',(json.dumps(summary),protected,key))
                if summary['error_code'] is not None:reason=reason or 'IO_ERROR'
            returned='CANCELLED' if reason=='CONTROLLER_CANCEL' else 'FAILED' if reason in {'DEADLINE','IO_LIMIT','IO_ERROR'} or observed['root_exit_code']!=0 else 'SUCCEEDED'
            c.execute("UPDATE run SET state='EXITED',quiesced=1,return_status=?,stop_reason=? WHERE backend_key=?",(returned,reason,key))
            return 0
        except Exception:
            c.execute('UPDATE run SET state=?,quiesced=?,return_status=?,stop_reason=? WHERE backend_key=?',
                ('UNKNOWN' if launch_attempted else 'EXITED',None if launch_attempted else 1,
                 'UNKNOWN' if launch_attempted else 'NOT_STARTED','SUPERVISOR_FAILURE',key))
            return 1
        finally:
            if job:job.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--supervise',required=True);parser.add_argument('--key',required=True)
    args=parser.parse_args();raise SystemExit(supervise(args.supervise,args.key))
