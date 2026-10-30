"""Codex native-tool relay owned by the trusted controller.

The controller executes the returned exact tool call and supplies its actual
receipt. The relay never calls a model, accepts Worker instructions as authority,
or interprets a close acknowledgement as stopped writers. Session-stop proof is
limited to the native API's post-close shutdown/not-found observation.
"""
import hashlib,json,re,sqlite3,time,uuid
from contextlib import closing
from pathlib import Path
from v2_definition_content import encode,decode
from v2_evidence import _regular_path

APPLICATION_ID=0x4D4E4154
ROLES={'malts_explorer','malts_worker','malts_verifier','malts_planner','malts_memory_curator'}

def _connect(root,readonly=False):
    path=Path(root)/'native.db';_regular_path(path)
    c=sqlite3.connect(path.as_uri()+('?mode=ro' if readonly else '?mode=rw'),uri=True,isolation_level=None,timeout=5)
    if c.execute('PRAGMA application_id').fetchone()[0]!=APPLICATION_ID or c.execute('PRAGMA user_version').fetchone()[0]!=1:
        c.close();raise ValueError('Native journal identity differs')
    return c

def initialize(root,*,host_id):
    root=Path(root).absolute();_regular_path(root)
    if not isinstance(host_id,str) or not 1<=len(host_id)<=128:raise ValueError('Bounded Host identity required')
    root.mkdir()
    with closing(sqlite3.connect(root/'native.db',isolation_level=None)) as c:
        c.executescript('''BEGIN IMMEDIATE;
        CREATE TABLE identity(host_id TEXT NOT NULL,instance_id TEXT NOT NULL);
        CREATE TABLE native_run(backend_key TEXT PRIMARY KEY,actor TEXT NOT NULL,request_hash TEXT NOT NULL,
            request_value TEXT NOT NULL,native_value TEXT,result_value TEXT,state TEXT NOT NULL DEFAULT 'UNKNOWN',
            returned TEXT,cancel_requested INTEGER NOT NULL DEFAULT 0,close_ack INTEGER NOT NULL DEFAULT 0,
            session_closed INTEGER NOT NULL DEFAULT 0,started_at REAL NOT NULL);
        CREATE TABLE native_call(call_id TEXT PRIMARY KEY,backend_key TEXT NOT NULL,tool TEXT NOT NULL,
            arguments_value TEXT NOT NULL,receipt_value TEXT,sequence INTEGER NOT NULL UNIQUE);
        COMMIT;''')
        c.execute('INSERT INTO identity VALUES (?,?)',(host_id,uuid.uuid4().hex))
        c.execute(f'PRAGMA application_id={APPLICATION_ID}');c.execute('PRAGMA user_version=1')
    return root

class NativeAgentHost:
    quiescence_scope='NATIVE_AGENT_SESSION_CLOSED'
    def __init__(self,root,*,role='malts_verifier',profile_binding=None,inputs=None):
        if role not in ROLES:raise ValueError('An existing bounded MALTS role is required')
        self.root=Path(root).absolute();self.role=role
        with closing(_connect(self.root,True)) as c:self.host_id,self.instance_id=c.execute('SELECT host_id,instance_id FROM identity').fetchone()
        self.profile_revision='codex-native-relay-v1:'+self.instance_id+':'+role
        if (profile_binding is None)!=(inputs is None):raise ValueError('Native profile binding and input inventory are required together')
        self.inputs=None
        if inputs is not None:
            from v2_agent_qualification import _inputs,inputs_digest
            if not isinstance(profile_binding,str) or not profile_binding:raise ValueError('Reviewed native profile binding required')
            self.inputs=_inputs(inputs)
            binding=json.dumps([profile_binding,inputs_digest(self.inputs)],separators=(',',':')).encode('utf-8')
            self.profile_revision+=':'+hashlib.sha256(binding).hexdigest()

    def validate_spawn_inputs(self):
        if self.inputs is not None:
            from v2_agent_qualification import file_inputs
            if file_inputs(self.inputs)!=self.inputs:raise ValueError('Reviewed native Agent inputs changed')

    def validate_request(self,request):
        if not isinstance(request,dict) or set(request)!={'prompt','wall_seconds'}:raise ValueError('Closed native request required')
        if not isinstance(request['prompt'],str) or not 1<=len(request['prompt'].encode('utf-8'))<=131072:raise ValueError('Bounded native prompt required')
        if type(request['wall_seconds']) not in (int,float) or not 1<=request['wall_seconds']<=3600:raise ValueError('Bounded native deadline required')

    def _protect(self,key,field,value):return encode(value,self.instance_id,'native-agent',key,1,field)
    def _decode(self,key,field,value):return None if value is None else decode(value,self.instance_id,'native-agent',key,1,field)

    def _row(self,c,key):
        if not isinstance(key,str) or re.fullmatch('[a-f0-9]{32}',key) is None:raise ValueError('Original backend key required')
        cursor=c.execute('SELECT * FROM native_run WHERE backend_key=?',(key,));row=cursor.fetchone()
        if row is None:raise ValueError('Native dispatch is not registered')
        return dict(zip((v[0] for v in cursor.description),row))

    def _queue(self,c,key,tool,arguments):
        pending=c.execute('SELECT call_id FROM native_call WHERE backend_key=? AND receipt_value IS NULL',(key,)).fetchone()
        if pending:return pending[0]
        call_id=uuid.uuid4().hex
        sequence=c.execute('SELECT coalesce(max(sequence),0)+1 FROM native_call').fetchone()[0]
        c.execute('INSERT INTO native_call VALUES (?,?,?,?,NULL,?)',(call_id,key,tool,self._protect(call_id,'arguments',arguments),sequence))
        return call_id

    def start(self,*,backend_key,actor,request):
        self.validate_request(request)
        if not isinstance(actor,str) or not actor:raise ValueError('Controller-bound actor required')
        fingerprint=hashlib.sha256(json.dumps([actor,request,self.role],sort_keys=True).encode()).hexdigest()
        with closing(_connect(self.root)) as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT request_hash FROM native_run WHERE backend_key=?',(backend_key,)).fetchone()
            if old:
                if old[0]!=fingerprint:raise ValueError('Original native dispatch request differs')
            else:
                if not isinstance(backend_key,str) or re.fullmatch('[a-f0-9]{32}',backend_key) is None:raise ValueError('Generated backend key required')
                c.execute('INSERT INTO native_run(backend_key,actor,request_hash,request_value,started_at) VALUES (?,?,?,?,?)',
                    (backend_key,actor,fingerprint,self._protect(backend_key,'request',request),time.time()))
                self._queue(c,backend_key,'multi_agent_v1.spawn_agent',{'agent_type':self.role,'fork_context':False,'message':request['prompt']})
            c.execute('COMMIT')
        return self.query(backend_key=backend_key)

    def query(self,*,backend_key):
        with closing(_connect(self.root,True)) as c:row=self._row(c,backend_key)
        native=self._decode(backend_key,'native-id',row['native_value'])
        closed=bool(row['session_closed'])
        return {'backend_key':backend_key,'native_id':native,'state':'EXITED' if closed else 'RUNNING' if native else 'UNKNOWN',
            'quiesced':closed,'cancel_acknowledged':bool(row['close_ack']),
            'return_status':('NOT_STARTED' if row['returned']=='NOT_STARTED' else 'SUCCEEDED' if row['returned']=='COMPLETED' else 'FAILED' if row['returned']=='FAILED' else 'CANCELLED') if closed else None,
            'effective_identity':None,'physical_requests':None}

    def pending_call(self,*,backend_key):
        with closing(_connect(self.root,True)) as c:
            self._row(c,backend_key)
            row=c.execute('SELECT call_id,tool,arguments_value FROM native_call WHERE backend_key=? AND receipt_value IS NULL ORDER BY sequence LIMIT 1',(backend_key,)).fetchone()
        return None if row is None else {'call_id':row[0],'tool':row[1],'arguments':self._decode(row[0],'arguments',row[2])}

    def deadline_status(self,*,backend_key):
        with closing(_connect(self.root,True)) as c:row=self._row(c,backend_key)
        request=self._decode(backend_key,'request',row['request_value'])
        return {'deadline_elapsed':time.time()>=row['started_at']+request['wall_seconds'],
            'session_closed':bool(row['session_closed']),'automatic_background_enforcement':False,
            'next_action':'QUERY_OR_CANCEL_ORIGINAL' if not row['session_closed'] else 'VERIFY_RESULT'}

    def _failed_close(self,c,backend_key):
        row=c.execute("SELECT call_id,receipt_value FROM native_call WHERE backend_key=? AND tool='multi_agent_v1.close_agent' AND receipt_value IS NOT NULL ORDER BY sequence DESC LIMIT 1",(backend_key,)).fetchone()
        return row is not None and set(self._decode(row[0],'receipt',row[1]))=={'error'}

    def request_query(self,*,backend_key):
        with closing(_connect(self.root)) as c:
            c.execute('BEGIN IMMEDIATE');row=self._row(c,backend_key)
            if not row['session_closed']:
                native=self._decode(backend_key,'native-id',row['native_value'])
                if native is None:raise ValueError('Reconcile the original spawn receipt before polling')
                if row['cancel_requested'] and not row['close_ack'] and not self._failed_close(c,backend_key):
                    self._queue(c,backend_key,'multi_agent_v1.close_agent',{'target':native})
                else:self._queue(c,backend_key,'multi_agent_v1.wait_agent',{'targets':[native],'timeout_ms':10000})
            c.execute('COMMIT')

    def cancel(self,*,backend_key):
        with closing(_connect(self.root)) as c:
            c.execute('BEGIN IMMEDIATE');row=self._row(c,backend_key)
            if not row['session_closed']:
                native=self._decode(backend_key,'native-id',row['native_value'])
                c.execute('UPDATE native_run SET cancel_requested=1 WHERE backend_key=?',(backend_key,))
                if native is not None:self._queue(c,backend_key,'multi_agent_v1.close_agent',{'target':native})
            c.execute('COMMIT')
        return self.query(backend_key=backend_key)

    def discard_unadmitted_wait(self,*,backend_key,call_id):
        """Controller-only withdrawal before any executable call was exposed."""
        with closing(_connect(self.root)) as c:
            c.execute('BEGIN IMMEDIATE');self._row(c,backend_key)
            call=c.execute('SELECT tool,receipt_value FROM native_call WHERE backend_key=? AND call_id=?',(backend_key,call_id)).fetchone()
            if call is None or call[0]!='multi_agent_v1.wait_agent' or call[1] is not None:raise ValueError('Only an unadmitted pending wait can be withdrawn')
            c.execute('UPDATE native_call SET receipt_value=? WHERE call_id=?',
                (self._protect(call_id,'receipt',{'not_executed':True,'reason':'CANCELLED_BEFORE_ADMISSION'}),call_id))
            c.execute('COMMIT')

    def cancel_unadmitted_spawn(self,*,backend_key,call_id):
        """Only the controller can establish that no call was ever admitted."""
        with closing(_connect(self.root)) as c:
            c.execute('BEGIN IMMEDIATE');row=self._row(c,backend_key)
            call=c.execute('SELECT tool,receipt_value FROM native_call WHERE backend_key=? AND call_id=?',(backend_key,call_id)).fetchone()
            if call is None or call[0]!='multi_agent_v1.spawn_agent' or call[1] is not None or row['native_value'] is not None:
                raise ValueError('Only an unadmitted pending spawn can be cancelled without Host reconciliation')
            c.execute('UPDATE native_call SET receipt_value=? WHERE call_id=?',
                (self._protect(call_id,'receipt',{'not_executed':True,'reason':'CANCELLED_BEFORE_ADMISSION'}),call_id))
            c.execute("UPDATE native_run SET session_closed=1,state='EXITED',returned='NOT_STARTED',cancel_requested=1 WHERE backend_key=?",(backend_key,))
            c.execute('COMMIT')

    def record_receipt(self,*,backend_key,call_id,tool,receipt):
        """Trusted Host callback only. A Worker claim cannot authenticate this."""
        if not isinstance(receipt,dict) or len(json.dumps(receipt).encode())>262144:raise ValueError('Bounded native tool receipt required')
        with closing(_connect(self.root)) as c:
            c.execute('BEGIN IMMEDIATE');run=self._row(c,backend_key)
            call=c.execute('SELECT tool,receipt_value FROM native_call WHERE backend_key=? AND call_id=?',(backend_key,call_id)).fetchone()
            if call is None or call[0]!=tool:raise ValueError('Native receipt call identity differs')
            if call[1] is not None:
                if self._decode(call_id,'receipt',call[1])!=receipt:raise ValueError('Native receipt replay differs')
                c.execute('COMMIT');return
            native=self._decode(backend_key,'native-id',run['native_value'])
            if tool=='multi_agent_v1.spawn_agent':
                if set(receipt)!={'agent_id','nickname'} or not isinstance(receipt['agent_id'],str) or not 1<=len(receipt['agent_id'])<=256:raise ValueError('Invalid actual spawn receipt')
                c.execute('UPDATE native_run SET native_value=?,state=\'RUNNING\' WHERE backend_key=?',(self._protect(backend_key,'native-id',receipt['agent_id']),backend_key))
            elif tool=='multi_agent_v1.wait_agent':
                if set(receipt)!={'status','timed_out'} or type(receipt['timed_out']) is not bool or not isinstance(receipt['status'],dict) or set(receipt['status'])-({native} if native else set()):raise ValueError('Wait receipt is outside native dispatch')
                value=receipt['status'].get(native)
                if isinstance(value,dict):
                    if set(value)=={'completed'}:
                        if value['completed'] is not None and not isinstance(value['completed'],str):raise ValueError('Invalid native result')
                        c.execute('UPDATE native_run SET result_value=?,returned=\'COMPLETED\' WHERE backend_key=?',(self._protect(backend_key,'result',value['completed']),backend_key))
                    elif set(value)=={'errored'}:c.execute('UPDATE native_run SET returned=\'FAILED\' WHERE backend_key=?',(backend_key,))
                    else:raise ValueError('Unknown native result state')
                elif value in {'shutdown','not_found'} and (run['close_ack'] or (run['cancel_requested'] and self._failed_close(c,backend_key))):
                    c.execute('UPDATE native_run SET session_closed=1,state=\'EXITED\' WHERE backend_key=?',(backend_key,))
                elif value not in {None,'pending_init','running','interrupted','shutdown','not_found'}:raise ValueError('Unknown native wait state')
            elif tool=='multi_agent_v1.close_agent':
                if set(receipt)=={'previous_status'}:
                    c.execute('UPDATE native_run SET close_ack=1 WHERE backend_key=?',(backend_key,))
                elif (set(receipt)=={'error'} and isinstance(receipt['error'],dict) and set(receipt['error'])=={'message'} and
                      isinstance(receipt['error']['message'],str) and 1<=len(receipt['error']['message'].encode('utf-8'))<=4096 and run['cancel_requested']):
                    # Preserve an actual tool exception without inventing an
                    # acknowledgement. Only a subsequent original-session
                    # wait can establish native API absence/stoppage.
                    pass
                else:raise ValueError('Invalid actual close result')
            else:raise ValueError('Unsupported native relay tool')
            c.execute('UPDATE native_call SET receipt_value=? WHERE call_id=?',(self._protect(call_id,'receipt',receipt),call_id))
            # A cancellation requested while spawn/wait was pending survives
            # that call's receipt. Never lose it or replace the unknown call.
            current=self._row(c,backend_key)
            native=self._decode(backend_key,'native-id',current['native_value'])
            if current['cancel_requested'] and not current['close_ack'] and not current['session_closed'] and native is not None:
                if tool=='multi_agent_v1.close_agent' and set(receipt)=={'error'}:
                    self._queue(c,backend_key,'multi_agent_v1.wait_agent',{'targets':[native],'timeout_ms':10000})
                else:self._queue(c,backend_key,'multi_agent_v1.close_agent',{'target':native})
            c.execute('COMMIT')

    def private_result(self,*,backend_key,purpose):
        if purpose not in {'verification','recovery'}:raise ValueError('Private result purpose required')
        with closing(_connect(self.root,True)) as c:row=self._row(c,backend_key)
        return {'candidate_message':self._decode(backend_key,'result',row['result_value']),
            'native_thread_id':self._decode(backend_key,'native-id',row['native_value']),
            'content_class':'UNREVIEWED_AGENT_OUTPUT','allowed_purposes':['verification','recovery'],
            'physical_external_writer_isolation':False,'session_closed':bool(row['session_closed'])}
