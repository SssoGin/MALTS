"""Selected Codex exec event mapping; content is data, never approval or acceptance."""


class CodexEvents:
    def __init__(self,*,capture_candidate_message=False):
        self.capture_message=capture_candidate_message;self.thread_id=None;self.started=False
        self.completed=0;self.failed=0;self.pending_message=None;self.candidate=None

    def accept(self,event):
        kind=event.get('type')
        if kind=='thread.started':
            if set(event)!={'type','thread_id'} or not isinstance(event['thread_id'],str) or not 1<=len(event['thread_id'])<=256:
                raise ValueError('Invalid native session observation')
            if self.thread_id is not None and self.thread_id!=event['thread_id']:raise ValueError('Native session identity changed')
            self.thread_id=event['thread_id'];return {'type':'native_session_observed'}
        if kind=='turn.started':
            if set(event)!={'type'} or self.thread_id is None or self.started:raise ValueError('Invalid turn start')
            self.started=True;self.pending_message=None
            return {'type':'status','state':'started'}
        if kind=='turn.completed':
            if set(event)!={'type','usage'} or not self.started:raise ValueError('Invalid completed turn')
            usage=event['usage'];required={'input_tokens','output_tokens','cached_input_tokens'}
            optional={'reasoning_output_tokens','cache_write_input_tokens'}
            if (not isinstance(usage,dict) or not required<=set(usage) or set(usage)-(required|optional) or
                    any(type(v) is not int or not 0<=v<=10**12 for v in usage.values())):raise ValueError('Invalid reported usage')
            self.started=False;self.completed+=1
            if self.capture_message:self.candidate=self.pending_message
            self.pending_message=None
            return {'type':'reported_turn_usage',**usage}
        if kind in {'turn.failed','error'}:
            self.failed+=1;self.started=False;self.pending_message=None
            return {'type':'status','state':'failed'}  # never retain error text
        if kind=='item.completed' and set(event)=={'type','item'}:
            item=event['item']
            if (self.capture_message and self.started and isinstance(item,dict) and set(item)=={'id','type','text'} and
                    item['type']=='agent_message' and isinstance(item['text'],str) and isinstance(item['id'],str)):
                self.pending_message=item['text']
            return None  # no item, command output, arguments or reasoning in public telemetry
        return None

    def discard_unparsed_item(self):
        # It might have been a newer final message. Do not reuse earlier text
        # as though the dropped item had been parsed or verified.
        self.pending_message=None

    def summary(self):
        return {'native_identity_observed':self.thread_id is not None,'completed_turns':self.completed,
                'failed_events':self.failed,'protocol_complete':self.thread_id is not None and self.completed>0 and not self.started and self.failed==0,
                'effective_model':None,'effective_effort':None,'candidate_is_verified':False}

    def private_values(self):
        return {'native_thread_id':self.thread_id,'candidate_message':self.candidate,
                'content_class':'UNREVIEWED_AGENT_OUTPUT','allowed_purposes':['verification','recovery']}
