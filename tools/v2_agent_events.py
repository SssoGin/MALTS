"""Bounded native result projections. Model text is private, untrusted data.

Only documented completion signals close the protocol. Tool output, reasoning,
raw errors and arbitrary event fields never enter public telemetry.
"""
import re

def _identity(value):
    if not isinstance(value,str) or not 1<=len(value)<=512:raise ValueError('Native session identity missing')
    return value

def _model(value):
    return value if isinstance(value,str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_./:-]{0,127}',value) else None

def _usage(value,fields):
    if not isinstance(value,dict):return None
    result={}
    for output,source in fields.items():
        raw=value.get(source)
        if raw is not None:
            if type(raw) is not int or not 0<=raw<=10**12:raise ValueError('Invalid reported usage')
            result[output]=raw
    return result if {'input_tokens','output_tokens'}<=set(result) else None

class HostEvents:
    def __init__(self,host,*,capture_candidate_message=False):
        if host not in {'claude-code','opencode','deepseek-harness'}:raise ValueError('Unsupported native event profile')
        self.host=host;self.capture=capture_candidate_message;self.native=None;self.candidate=None
        self.completed=False;self.failed=False;self.started=False;self.model=None;self.usage=None
        self.pending=[];self.turn_reason=None;self.tool_observations=[];self.failure_codes=[]

    def _tool_observation(self,name,value=None):
        if len(self.tool_observations)>=80:return
        row={}
        if isinstance(name,str) and re.fullmatch('[A-Za-z0-9_./:-]{1,128}',name):row['tool']=name
        if isinstance(value,str):
            import json
            try:value=json.loads(value)
            except (ValueError,TypeError):value=None
        if isinstance(value,dict):
            for key in ('decision','error_code','reason_code'):
                v=value.get(key)
                if isinstance(v,str) and re.fullmatch('[A-Z][A-Z0-9_]{0,95}',v):row[key]=v
        if row:self.tool_observations.append(row)

    def _session(self,identity):
        identity=_identity(identity)
        if self.native is not None and self.native!=identity:raise ValueError('Native session identity changed')
        self.native=identity;self.started=True

    def accept(self,event):
        if not isinstance(event,dict):raise ValueError('Native JSON object required')
        kind=event.get('type')
        if self.host=='claude-code':
            if kind in {'assistant','user'} and isinstance(event.get('message'),dict):
                for block in event['message'].get('content',[]):
                    if not isinstance(block,dict):continue
                    if block.get('type')=='tool_use':self._tool_observation(block.get('name'))
                    if block.get('type')=='tool_result':
                        content=block.get('content')
                        if isinstance(content,list):
                            for item in content:
                                if isinstance(item,dict):self._tool_observation(None,item.get('text'))
                        else:self._tool_observation(None,content)
            if kind=='system' and event.get('subtype')=='init':
                self._session(event.get('session_id'));self.model=_model(event.get('model'))
                return {'type':'native_session_observed'}
            if kind=='result':
                if self.native is None:self._session(event.get('session_id'))
                elif event.get('session_id',self.native)!=self.native:raise ValueError('Result session differs')
                self.failed=event.get('is_error') is not False or event.get('subtype')!='success'
                self.completed=not self.failed
                if self.capture and self.completed:
                    text=event.get('result')
                    if not isinstance(text,str):raise ValueError('Final result text missing')
                    self.candidate=text
                self.usage=_usage(event.get('usage'),{'input_tokens':'input_tokens','output_tokens':'output_tokens','cached_input_tokens':'cache_read_input_tokens'})
                return {'type':'status','state':'failed' if self.failed else 'completed'}
            if kind=='error':self.failed=True;return {'type':'status','state':'failed'}
        elif self.host=='opencode':
            if 'sessionID' in event:self._session(event['sessionID'])
            if kind=='error':self.failed=True;return {'type':'status','state':'failed'}
            part=event.get('part',{})
            if isinstance(part,dict) and part.get('type')=='tool':
                self._tool_observation(part.get('tool'),part.get('state',{}).get('output') if isinstance(part.get('state'),dict) else None)
            if kind=='text' and isinstance(part,dict) and self.capture:
                text=part.get('text')
                if not isinstance(text,str):raise ValueError('Invalid native text part')
                self.pending.append(text)
            if kind=='step_start':self.completed=False;self.pending=[];return {'type':'status','state':'started'}
            if kind=='step_finish' and isinstance(part,dict):
                self.usage=_usage(part.get('tokens'),{'input_tokens':'input','output_tokens':'output'})
                if part.get('reason')=='stop':
                    self.completed=not self.failed
                    if self.capture:self.candidate='\n'.join(self.pending)
                    return {'type':'status','state':'completed'}
        else:
            if kind=='session':self._session(event.get('sessionId'));return {'type':'native_session_observed'}
            if kind=='error':self.failed=True;return {'type':'status','state':'failed'}
            if kind=='status' and event.get('phase')=='turn_end':
                reason=event.get('reason')
                self.turn_reason=reason.get('kind') if isinstance(reason,dict) else reason
                if isinstance(reason,dict) and isinstance(reason.get('error'),dict):
                    code=reason['error'].get('code')
                    if isinstance(code,str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}',code):self.failure_codes.append(code)
                if self.turn_reason!='completed':self.failed=True
                return {'type':'status','state':'failed' if self.failed else 'completed'}
            if kind=='status' and event.get('phase')=='step_end':
                usage=_usage(event.get('usage'),{'input_tokens':'inputTokens','output_tokens':'outputTokens','cached_input_tokens':'cacheReadTokens'})
                if usage is not None:
                    self.usage={k:(self.usage or {}).get(k,0)+v for k,v in usage.items()}
            if kind=='final':
                if not self.started or not isinstance(event.get('text'),str):raise ValueError('Invalid headless final event')
                self.completed=not self.failed and self.turn_reason=='completed'
                if self.capture and self.completed:self.candidate=event['text']
                return {'type':'status','state':'completed' if self.completed else 'failed'}
        return None

    def summary(self):
        return {'native_identity_observed':self.native is not None,'protocol_complete':self.native is not None and self.completed and not self.failed,
                'effective_model':self.model,'effective_effort':None,'reported_usage':self.usage,'candidate_is_verified':False}

    def private_values(self):
        return {'native_thread_id':self.native,'candidate_message':self.candidate if not self.failed else None,
                'tool_observations':self.tool_observations,'failure_codes':self.failure_codes,
                'content_class':'UNREVIEWED_AGENT_OUTPUT','allowed_purposes':['verification','recovery']}
