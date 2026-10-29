"""Bounded private pipe transport. Raw output and hidden reasoning are never retained."""
import json,re,threading,time

MAX_JSONL_LINE_BYTES = 262144

# Only these native item envelopes carry optional, untrusted bodies. Their
# oversized bodies may be drained, never interpreted as control or evidence.
_DISCARDABLE_CODEX_ITEM = re.compile(
    rb'^[ \t\r]*\{[ \t\r]*"type"[ \t\r]*:[ \t\r]*"item\.(?:started|updated|completed)"'
    rb'[ \t\r]*,[ \t\r]*"item"[ \t\r]*:[ \t\r]*\{')


class StdioPump:
    def __init__(self,job,input_bytes,*,max_output_bytes,max_line_bytes,max_events,protocol='bounded-jsonl-v1',capture_candidate_message=False):
        if not isinstance(input_bytes,bytes) or len(input_bytes)>1048576:raise ValueError('Bounded stdin bytes required')
        for value,maximum in ((max_output_bytes,16777216),(max_line_bytes,MAX_JSONL_LINE_BYTES),(max_events,1000)):
            if type(value) is not int or not 1<=value<=maximum:raise ValueError('Invalid stream budget')
        self.job=job;self.max_output=max_output_bytes;self.max_line=max_line_bytes;self.max_events=max_events
        if protocol not in {'bounded-jsonl-v1','codex-jsonl-v1','claude-jsonl-v1','opencode-jsonl-v1','harness-jsonl-v1'}:raise ValueError('Unsupported event protocol')
        from v2_codex_events import CodexEvents
        self.codex=CodexEvents(capture_candidate_message=capture_candidate_message) if protocol=='codex-jsonl-v1' else None
        from v2_agent_events import HostEvents
        hosts={'claude-jsonl-v1':'claude-code','opencode-jsonl-v1':'opencode','harness-jsonl-v1':'deepseek-harness'}
        self.agent=self.codex if protocol not in hosts else HostEvents(hosts[protocol],capture_candidate_message=capture_candidate_message)
        self.lock=threading.Lock();self.stop=threading.Event();self.error=None
        self.counts={'stdout_bytes':0,'stderr_bytes':0,'stdin_written_bytes':0,'discarded_lines':0,'accepted_events':0,
                     'oversized_codex_items_discarded':0}
        self.events=[]
        self.invalid_event_shapes=[]
        self.threads=[threading.Thread(target=self._read,args=(job.stdout,'stdout'),daemon=True),
            threading.Thread(target=self._read,args=(job.stderr,'stderr'),daemon=True),
            threading.Thread(target=self._write,args=(input_bytes,),daemon=True)]
        for thread in self.threads:thread.start()

    def _fail(self,code):
        with self.lock:
            if self.error is None:self.error=code
            self.stop.set()

    def _write(self,data):
        try:
            view=memoryview(data);sent=0
            while sent<len(view):
                count=self.job.stdin.write(view[sent:sent+4096])
                if not count:raise OSError('Closed input')
                sent+=count
                with self.lock:self.counts['stdin_written_bytes']=sent
        except (OSError,ValueError):self._fail('STDIN_CLOSED_EARLY')
        finally:
            try:self.job.stdin.close()
            except OSError:pass

    def _line(self,line):
        if self.agent is not None and self.codex is None and not line.lstrip().startswith(b'{'):
            # Native launchers may print non-JSON diagnostic banners. Discard
            # them without retaining their contents; only a complete recognised
            # session/result protocol can establish successful completion.
            with self.lock:self.counts['discarded_lines']+=1
            return
        def pairs(items):
            value={}
            for key,item in items:
                if key in value:raise ValueError('Duplicate JSON key')
                value[key]=item
            return value
        try:
            event=json.loads(line.decode('utf-8'),object_pairs_hook=pairs)
            if not isinstance(event,dict):raise ValueError()
            if self.agent is not None:
                safe=self.agent.accept(event)
                if safe is None:
                    with self.lock:self.counts['discarded_lines']+=1
                    return
            elif set(event)=={'type','state'} and event['type']=='status' and event['state'] in {'started','completed','failed'}:
                safe=event
            elif set(event)=={'type','input_tokens','output_tokens','cached_input_tokens'} and event['type']=='usage' and all(
                    type(event[key]) is int and 0<=event[key]<=10**12 for key in ('input_tokens','output_tokens','cached_input_tokens')):
                safe=event
            else:raise ValueError()
        except (ValueError,TypeError,UnicodeError,RecursionError) as error:
            with self.lock:self.counts['discarded_lines']+=1
            if self.agent is not None and len(self.invalid_event_shapes)<4:
                event_type=event.get('type') if 'event' in locals() and isinstance(event,dict) else None
                known={'session','status','final','result','system','error','step_start','step_finish','text'}
                self.invalid_event_shapes.append({'type':event_type if event_type in known else 'UNRECOGNIZED',
                    'error_type':type(error).__name__,'line_bytes':len(line),
                    'usage_types':{k:type(v).__name__ for k,v in (event.get('usage') or {}).items()} if 'event' in locals() and isinstance(event,dict) and isinstance(event.get('usage'),dict) else {}})
            if self.agent is not None:self._fail('CODEX_EVENT_INVALID' if self.codex is not None else 'AGENT_EVENT_INVALID')
            return
        with self.lock:
            if len(self.events)>=self.max_events:
                if self.error is None:self.error='EVENT_LIMIT'
                self.stop.set();return
            self.events.append(safe);self.counts['accepted_events']+=1

    def _read(self,stream,kind):
        pending=bytearray();discarding_item=False
        try:
            while True:
                if self.stop.is_set():break
                data=stream.read(4096)
                if not data:break
                with self.lock:
                    self.counts[kind+'_bytes']+=len(data)
                    over=self.counts['stdout_bytes']+self.counts['stderr_bytes']>self.max_output
                if over:self._fail('OUTPUT_LIMIT');break
                if kind=='stderr':continue
                if self.stop.is_set():pending.clear();break
                for index,part in enumerate(data.split(b'\n')):
                    if index:
                        if discarding_item:discarding_item=False
                        else:self._line(bytes(pending))
                        pending.clear()
                    if discarding_item:continue
                    pending.extend(part)
                    if len(pending)>self.max_line:
                        if self.codex is not None and _DISCARDABLE_CODEX_ITEM.match(pending[:512]):
                            pending.clear();discarding_item=True
                            self.codex.discard_unparsed_item()
                            with self.lock:
                                self.counts['discarded_lines']+=1
                                self.counts['oversized_codex_items_discarded']+=1
                        else:
                            pending.clear();self._fail('LINE_LIMIT');break
            if kind=='stdout' and pending and not self.stop.is_set():self._line(bytes(pending))
        except (OSError,ValueError):self._fail('STREAM_READ_ERROR')

    def finish(self,timeout=2):
        deadline=time.monotonic()+timeout
        for thread in self.threads:thread.join(max(0,deadline-time.monotonic()))
        if any(thread.is_alive() for thread in self.threads):self._fail('DRAIN_INCOMPLETE')
        protocol_summary={} if self.agent is None else self.agent.summary()
        if self.agent is not None and not protocol_summary['protocol_complete']:self._fail('CODEX_PROTOCOL_INCOMPLETE' if self.codex is not None else 'AGENT_PROTOCOL_INCOMPLETE')
        with self.lock:
            return {**self.counts,'error_code':self.error,'events':list(self.events),'raw_output_retained':False,
                    'event_assurance':'REPORTED_DATA_NOT_TASK_ACCEPTANCE','input_consumption_verified':False,'protocol':protocol_summary}

    def private_values(self):
        if self.agent is None:return None
        return {**self.agent.private_values(),'invalid_event_shapes':self.invalid_event_shapes}
