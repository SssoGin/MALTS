"""Project candidates backed by purpose-authorized Evidence in the same store.

No automatic application, promotion, global memory, or caller authentication.
Proposal JSON is data. Host-owned review/authorization must precede this API.
"""
import hashlib
import json
from v2_state_store import StateConflict, _json, _text
from v2_contracts import LEVELS
from v2_acceptance import Acceptance
from v2_evidence import EvidenceCorrupt, EvidenceReadLimit, BlobStore

ELIGIBLE = {'CANDIDATE','PROJECT_EXPERIMENTAL','FUTURE_USE_VALIDATING','VALIDATED'}


def matches_profile(profile, query):
    if profile['tools'] and query['tools'] not in profile['tools']: return False
    if any(v is not None and profile[k] and v not in profile[k] for k,v in query.items()): return False
    return any(v is not None and v in profile[k] for k,v in query.items())


def require_trial_ready(store, operation_id):
    """Recheck immediately before managed intent and lease use; no new authority."""
    row=store.connection.execute('''SELECT t.candidate_id,g.owner,t.request_hash,o.request_hash,t.context_json
        FROM growth_trial t JOIN growth_candidate g ON g.candidate_id=t.candidate_id
        JOIN operation o ON o.operation_id=t.operation_id WHERE t.operation_id=?''',(operation_id,)).fetchone()
    if row is None: return
    if row[2]!=row[3]: raise StateConflict('Growth trial request changed')
    growth=Growth(store,BlobStore(store.path.parent/'blobs',readonly=True))
    document=growth._eligible(row[0],row[1])
    if not matches_profile(document['applicability'],json.loads(row[4])):
        raise StateConflict('Growth trial applicability no longer matches')


def proposal_document(data):
    if len(data) > 16384:
        raise ValueError('Growth proposal exceeds bounded size')
    try:
        value=json.loads(data)
    except (ValueError, UnicodeError):
        raise ValueError('Growth proposal must be UTF-8 JSON') from None
    if not isinstance(value,dict) or set(value)!={'action','check','boundary','applicability'}:
        raise ValueError('Growth proposal must match its closed contract')
    for key in ('action','check','boundary'):
        _text(value[key],key)
        if len(value[key])>2048: raise ValueError('Growth proposal text exceeds limit')
    profile=value['applicability']
    if not isinstance(profile,dict) or set(profile)!={'task_types','tools','failure_signatures'}:
        raise ValueError('Expected closed Growth applicability profile')
    for values in profile.values():
        if (not isinstance(values,list) or len(values)>20 or
                any(not isinstance(v,str) or not v.strip() or len(v)>128 for v in values) or
                len(set(values))!=len(values)):
            raise ValueError('Invalid Growth applicability values')
    if not any(profile.values()): raise ValueError('At least one applicability constraint is required')
    return value


class Growth:
    def __init__(self, store, blobs):
        self.store=store
        self.evidence=Acceptance(store,blobs)

    def _read(self, evidence_id, owner):
        return self.evidence._read_in_transaction(evidence_id=evidence_id,owner=owner,purpose='growth')

    def _eligible(self, candidate_id, owner):
        c=self.store.connection
        row=c.execute('SELECT owner,proposal_evidence_id,state FROM growth_candidate WHERE candidate_id=?',(candidate_id,)).fetchone()
        if row is None or row[0]!=owner or row[2] not in ELIGIBLE:
            raise PermissionError('Growth candidate is not eligible in this project')
        document=proposal_document(self._read(row[1],owner))
        for (source,) in c.execute('SELECT evidence_id FROM growth_source WHERE candidate_id=?',(candidate_id,)).fetchall():
            self._read(source,owner)
        if row[2]=='VALIDATED': self._read_validation(candidate_id,lambda reference:self._read(reference,owner))
        return document

    def _validation_reference(self,candidate_id):
        rows=self.store.connection.execute("SELECT review_evidence_id FROM growth_lifecycle WHERE candidate_id=? AND new_state='VALIDATED'",(candidate_id,)).fetchall()
        if len(rows)!=1: raise StateConflict('Validated candidate has no unique validation evidence')
        return rows[0][0]

    def _read_validation(self,candidate_id,reader):
        reference=self._validation_reference(candidate_id)
        binding=self.store.connection.execute('SELECT task_id,task_revision FROM evidence WHERE evidence_id=?',(reference,)).fetchone()
        if binding is None:
            raise StateConflict('Validation review evidence is missing')
        proof=self.evidence.verify_task_completion(task_id=binding[0])
        if proof['task_revision']!=binding[1] or proof['decision']!='CURRENT_EVIDENCE_VALID':
            raise StateConflict('Validated candidate review is no longer current')
        document=json.loads(reader(reference))
        if not isinstance(document,dict) or document.get('candidate_id')!=candidate_id or not isinstance(document.get('trial_reviews'),list):
            raise StateConflict('Validation support document changed')
        seen={reference}
        for item in document['trial_reviews']:
            if not isinstance(item,dict): raise StateConflict('Invalid validation support references')
            for key in ('comparison_evidence_id','cost_evidence_id'):
                evidence_id=item.get(key)
                if not isinstance(evidence_id,str) or not evidence_id: raise StateConflict('Validation support reference is missing')
                if evidence_id not in seen:
                    reader(evidence_id); seen.add(evidence_id)

    def begin_trial(self, *, trial_id, candidate_id, owner, operation_id, expected_request_hash,
                    actor, authority_ref, rollback_ref, task_type, tool, failure_signature=None):
        for key,value in [('trial_id',trial_id),('candidate_id',candidate_id),('owner',owner),('operation_id',operation_id),
                          ('expected_request_hash',expected_request_hash),('actor',actor),('authority_ref',authority_ref),
                          ('rollback_ref',rollback_ref),('task_type',task_type),('tool',tool)]:
            _text(value,key)
        if failure_signature is not None: _text(failure_signature,'failure_signature')
        context={'task_types':task_type,'tools':tool,'failure_signatures':failure_signature}
        values=(trial_id,candidate_id,operation_id,expected_request_hash,actor,authority_ref,rollback_ref,_json(context))
        fingerprint=hashlib.sha256(_json([owner,*values]).encode()).hexdigest()
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            prior=c.execute('SELECT trial_hash FROM growth_trial WHERE trial_id=?',(trial_id,)).fetchone()
            if prior:
                if prior[0]!=fingerprint: raise StateConflict('Growth trial identity is immutable')
                return {'decision':'REPLAY','execute_once':False}
            document=self._eligible(candidate_id,owner)
            if not matches_profile(document['applicability'],context): raise StateConflict('Growth trial context does not match')
            op=c.execute('''SELECT o.task_id,o.task_revision,o.state,o.request_hash,g.actor,t.project_id,t.revision
                FROM operation o JOIN execution_grant g ON g.grant_id=o.grant_id JOIN task t ON t.task_id=o.task_id
                WHERE o.operation_id=?''',(operation_id,)).fetchone()
            if (op is None or op[2]!='PREPARED' or op[3]!=expected_request_hash or
                    op[4]!=actor or op[5]!=owner or op[6]!=op[1]):
                raise StateConflict('Trial must bind an owned current prepared operation and exact request')
            source_tasks={r[0] for r in c.execute('''SELECT e.task_id FROM evidence e JOIN growth_source s ON s.evidence_id=e.evidence_id WHERE s.candidate_id=?
                UNION SELECT e.task_id FROM evidence e JOIN growth_candidate g ON g.proposal_evidence_id=e.evidence_id WHERE g.candidate_id=?''',(candidate_id,candidate_id))}
            if op[0] in source_tasks: raise StateConflict('Original source/proposal task cannot count as a future trial')
            c.execute('INSERT INTO growth_trial VALUES (?,?,?,?,?,?,?,?,?)',(*values,fingerprint))
            c.execute("UPDATE growth_candidate SET state='PROJECT_EXPERIMENTAL' WHERE candidate_id=? AND state='CANDIDATE'",(candidate_id,))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                      ('GROWTH_TRIAL_BOUND',trial_id,_json({'candidate_id':candidate_id,'operation_id':operation_id})))
            return {'decision':'TRIAL_BOUND','execute_once':False,'operation_id':operation_id}

    def propose(self, *, candidate_id, owner, proposal_evidence_id, source_evidence_ids, authority_ref):
        for key,value in [('candidate_id',candidate_id),('owner',owner),('proposal_evidence_id',proposal_evidence_id),('authority_ref',authority_ref)]:
            _text(value,key)
        if (not isinstance(source_evidence_ids,list) or not source_evidence_ids or len(source_evidence_ids)>32 or
                any(not isinstance(v,str) or not v.strip() for v in source_evidence_ids) or
                len(set(source_evidence_ids))!=len(source_evidence_ids)):
            raise ValueError('Explicit unique source evidence IDs are required')
        if proposal_evidence_id in source_evidence_ids:
            raise StateConflict('Proposal cannot be its own source evidence')
        sources=sorted(source_evidence_ids)
        fingerprint=hashlib.sha256(_json([owner,proposal_evidence_id,sources,authority_ref]).encode()).hexdigest()
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            prior=c.execute('SELECT request_hash FROM growth_candidate WHERE candidate_id=?',(candidate_id,)).fetchone()
            if prior:
                if prior[0]!=fingerprint: raise StateConflict('Growth candidate identity is immutable')
                return {'decision':'REPLAY','evidence_revalidated':False,'application_authorized':False}
            proposal_document(self._read(proposal_evidence_id,owner))
            for evidence_id in sources: self._read(evidence_id,owner)
            c.execute("INSERT INTO growth_candidate VALUES (?,?,?,?,?,'CANDIDATE')",(candidate_id,owner,proposal_evidence_id,fingerprint,authority_ref))
            c.executemany('INSERT INTO growth_source VALUES (?,?)',[(candidate_id,e) for e in sources])
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                      ('GROWTH_PROPOSED',candidate_id,_json({'owner':owner,'source_count':len(sources)})))
            return {'decision':'PROPOSED','state':'CANDIDATE','application_authorized':False}

    def record_outcome(self, *, outcome_id, trial_id, owner, evidence_id, outcome, severity,
                       independence_key, reviewer_ref):
        for key,value in [('outcome_id',outcome_id),('trial_id',trial_id),('owner',owner),('evidence_id',evidence_id),
                          ('independence_key',independence_key),('reviewer_ref',reviewer_ref)]:
            _text(value,key)
        if outcome not in {'helped','neutral','harmful','inconclusive'} or severity not in {'none','low','medium','high','critical'}:
            raise ValueError('Invalid Growth outcome or severity')
        if (outcome=='harmful') != (severity!='none'):
            raise ValueError('Only harmful outcomes carry non-none severity')
        fingerprint=hashlib.sha256(_json([trial_id,owner,evidence_id,outcome,severity,independence_key,reviewer_ref]).encode()).hexdigest()
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            old=c.execute('SELECT request_hash FROM growth_outcome WHERE outcome_id=?',(outcome_id,)).fetchone()
            if old:
                if old[0]!=fingerprint: raise StateConflict('Outcome identity is immutable')
                return {'decision':'REPLAY','verification':'HISTORICAL_RECEIPT'}
            row=c.execute('''SELECT t.candidate_id,g.owner,g.state,o.task_id,o.task_revision,o.state,o.execution_epoch
                FROM growth_trial t JOIN growth_candidate g ON g.candidate_id=t.candidate_id
                JOIN operation o ON o.operation_id=t.operation_id WHERE t.trial_id=?''',(trial_id,)).fetchone()
            if row is None or row[1]!=owner: raise PermissionError('Growth trial owner mismatch')
            epoch=c.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]
            if row[5] not in {'OBSERVED','ACCEPTED','FAILED'} or row[6]!=epoch:
                raise StateConflict('Outcome requires a known executed trial in the current epoch')
            # Outcome evidence may come from a separate verification operation on
            # this task, so failed trials can be reviewed without inventing success.
            self._read(evidence_id,owner)
            evidence=c.execute('SELECT task_id,task_revision FROM evidence WHERE evidence_id=?',(evidence_id,)).fetchone()
            if evidence!=(row[3],row[4]): raise StateConflict('Outcome evidence must bind the trial Task revision')
            c.execute('INSERT INTO growth_outcome VALUES (?,?,?,?,?,?,?,?)',
                      (outcome_id,trial_id,evidence_id,outcome,severity,independence_key,reviewer_ref,fingerprint))
            state=row[2]
            if state not in {'DEPRECATED','REMOVED','REJECTED'}:
                if outcome=='harmful':
                    state='SUSPENDED' if state=='SUSPENDED' or severity in {'high','critical'} else 'CHALLENGED'
                elif state in {'CANDIDATE','PROJECT_EXPERIMENTAL'}:
                    state='FUTURE_USE_VALIDATING'
            c.execute('UPDATE growth_candidate SET state=? WHERE candidate_id=?',(state,row[0]))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                      ('GROWTH_OUTCOME_RECORDED',outcome_id,_json({'candidate_id':row[0],'state':state})))
            return {'decision':'RECORDED','state':state,'causal_improvement_verified':False,'promotion_authorized':False}

    def assess(self, *, candidate_id, owner):
        """Read-only review of all trial evidence; never marks causal validation."""
        _text(candidate_id,'candidate_id')
        _text(owner,'owner')
        c=self.store.connection
        owns_transaction=not c.in_transaction
        if owns_transaction: c.execute('BEGIN')
        try:
            self.store.require_execution_ready()
            candidate=c.execute('SELECT owner,state,proposal_evidence_id FROM growth_candidate WHERE candidate_id=?',(candidate_id,)).fetchone()
            if candidate is None or candidate[0]!=owner: raise PermissionError('Candidate owner mismatch')
            blockers=set()
            if candidate[1] not in ELIGIBLE: blockers.add('CANDIDATE_NOT_ELIGIBLE')
            try:
                proposal_document(self._read(candidate[2],owner))
                for (source,) in c.execute('SELECT evidence_id FROM growth_source WHERE candidate_id=?',(candidate_id,)).fetchall(): self._read(source,owner)
                if candidate[1]=='VALIDATED': self._read_validation(candidate_id,lambda reference:self._read(reference,owner))
            except (PermissionError,EvidenceCorrupt,FileNotFoundError,StateConflict): blockers.add('SOURCE_UNAVAILABLE')
            epoch=c.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()[0]
            trials=c.execute('''SELECT t.trial_id,o.task_id,o.task_revision,o.state,o.execution_epoch
                FROM growth_trial t JOIN operation o ON o.operation_id=t.operation_id
                WHERE t.candidate_id=? ORDER BY t.trial_id''',(candidate_id,)).fetchall()
            outcomes=c.execute('''SELECT r.outcome_id,r.trial_id,r.evidence_id,r.outcome,r.severity,r.independence_key
                FROM growth_outcome r JOIN growth_trial t ON t.trial_id=r.trial_id
                WHERE t.candidate_id=? ORDER BY r.outcome_id''',(candidate_id,)).fetchall()
            evidence_by_trial={trial[0]:[] for trial in trials}
            for row in outcomes: evidence_by_trial[row[1]].append(row)
            helped_tasks=set()
            keys=set()
            reports=[]
            counts={key:0 for key in ('helped','neutral','harmful','inconclusive')}
            for trial_id,task_id,revision,state,execution_epoch in trials:
                reasons=set()
                records=evidence_by_trial[trial_id]
                if not records: reasons.add('MISSING_OUTCOME')
                if execution_epoch!=epoch: reasons.add('HISTORICAL_EPOCH')
                if state not in {'OBSERVED','ACCEPTED'}: reasons.add('TRIAL_NOT_SUCCESSFULLY_OBSERVED')
                task=self.store.task(task_id)
                if task['revision']!=revision or task['status']!='COMPLETED' or not task['acceptance_valid']:
                    reasons.add('TASK_NOT_CURRENTLY_ACCEPTED')
                if self.store.unresolved_dependencies(task_id,revision): reasons.add('TRIAL_DEPENDENCIES_UNAVAILABLE')
                for _,_,evidence_id,outcome,_,_ in records:
                    counts[outcome]+=1
                    if outcome=='harmful': blockers.add('HARMFUL_EVIDENCE_PRESENT')
                    if outcome!='helped': reasons.add('NON_HELPFUL_OR_CONFLICTING_OUTCOME')
                    try: self._read(evidence_id,owner)
                    except (PermissionError,EvidenceCorrupt,FileNotFoundError): reasons.add('OUTCOME_EVIDENCE_UNAVAILABLE')
                # Trial reuse follows the same current proof as task/phase/project
                # verification, including plan and carry-lineage changes.
                if task['revision']==revision:
                    proof=self.evidence.verify_task_completion(task_id=task_id)
                    if proof['decision']!='CURRENT_EVIDENCE_VALID':
                        reasons.add('ACCEPTANCE_EVIDENCE_UNAVAILABLE')
                trial_keys={r[5] for r in records}
                if len(trial_keys)!=1: reasons.add('INCONSISTENT_INDEPENDENCE_DECLARATION')
                if not reasons:
                    helped_tasks.add(task_id)
                    keys.update(trial_keys)
                reports.append({'trial_id':trial_id,'task_id':task_id,'eligible_helped':not reasons,'reasons':sorted(reasons)})
                blockers.update(reasons)
            if len(helped_tasks)<2 or len(keys)<2: blockers.add('INSUFFICIENT_DISTINCT_FUTURE_EVIDENCE')
            result={'candidate_id':candidate_id,'state':candidate[1],'trial_count':len(trials),'outcome_counts':counts,
                    'eligible_helped_task_count':len(helped_tasks),'declared_independence_key_count':len(keys),
                    'trials':reports,'blockers':sorted(blockers),
                    'decision':'READY_FOR_INDEPENDENCE_REVIEW' if not blockers else 'INSUFFICIENT_OR_BLOCKED',
                    'independence_verified':False,'causal_improvement_verified':False,
                    'promotion_authorized':False,'writes_performed':False}
            result['assessment_sha256']=hashlib.sha256(_json(result).encode()).hexdigest()
            if owns_transaction: c.execute('COMMIT')
            return result
        except BaseException:
            if owns_transaction and c.in_transaction: c.execute('ROLLBACK')
            raise

    def validate_candidate(self, *, review_id, candidate_id, owner, expected_assessment_sha256, review_evidence_id, authority_ref):
        """Accept a controller-provided comparison review; never deploy a rule."""
        for key,value in locals().copy().items():
            if key!='self': _text(value,key)
        fingerprint=hashlib.sha256(_json([candidate_id,owner,expected_assessment_sha256,review_evidence_id,authority_ref]).encode()).hexdigest()
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            prior=c.execute('SELECT request_hash,new_state FROM growth_lifecycle WHERE review_id=?',(review_id,)).fetchone()
            if prior:
                if prior[0]!=fingerprint: raise StateConflict('Validation review identity is immutable')
                return {'decision':'REPLAY','historical_state':prior[1],'evidence_revalidated':False,'application_authorized':False}
            assessment=self.assess(candidate_id=candidate_id,owner=owner)
            if assessment['assessment_sha256']!=expected_assessment_sha256: raise StateConflict('Growth assessment changed before validation')
            if assessment['decision']!='READY_FOR_INDEPENDENCE_REVIEW' or assessment['state']!='FUTURE_USE_VALIDATING':
                raise StateConflict('Candidate does not have eligible future-task evidence')
            row=c.execute('''SELECT e.task_id,e.task_revision,e.result,e.method,e.evidence_level,g.actor,t.project_id
                FROM evidence e JOIN operation o ON o.operation_id=e.operation_id JOIN execution_grant g ON g.grant_id=o.grant_id
                JOIN task t ON t.task_id=e.task_id WHERE e.evidence_id=?''',(review_evidence_id,)).fetchone()
            if row is None or row[6]!=owner or row[2]!='PASS' or row[3]!='growth-validation-review' or LEVELS[row[4]]<LEVELS['B']:
                raise StateConflict('Validation requires controller review evidence of the specified method and at least level B')
            trial_tasks={t['task_id'] for t in assessment['trials']}
            source_tasks={r[0] for r in c.execute('''SELECT e.task_id FROM evidence e JOIN growth_source s ON s.evidence_id=e.evidence_id WHERE s.candidate_id=?
                UNION SELECT e.task_id FROM evidence e JOIN growth_candidate g ON g.proposal_evidence_id=e.evidence_id WHERE g.candidate_id=?''',(candidate_id,candidate_id))}
            actors={r[0] for r in c.execute('SELECT actor FROM growth_trial WHERE candidate_id=?',(candidate_id,))}
            if row[0] in trial_tasks|source_tasks or row[5] in actors: raise StateConflict('Validation review must be separate from source and trial work')
            task=self.store.task(row[0])
            if task['revision']!=row[1] or task['status']!='COMPLETED' or not task['acceptance_valid']:
                raise StateConflict('Validation review task must have current accepted results')
            if self.store.unresolved_dependencies(row[0],row[1]): raise StateConflict('Validation review dependencies are no longer current')
            if self.evidence.verify_task_completion(task_id=row[0])['decision']!='CURRENT_EVIDENCE_VALID':
                raise StateConflict('Validation review no longer has current supporting proof')
            raw=self.evidence._read_in_transaction(evidence_id=review_evidence_id,owner=owner,purpose='verification',max_bytes=262144)
            review=json.loads(raw)
            if not isinstance(review,dict) or set(review)!={'candidate_id','assessment_sha256','trial_reviews','scope_ref'}:
                raise ValueError('Invalid growth validation review document')
            if review['candidate_id']!=candidate_id or review['assessment_sha256']!=expected_assessment_sha256:
                raise StateConflict('Validation document binds a different candidate or assessment')
            _text(review['scope_ref'],'scope_ref')
            rows=review['trial_reviews']; expected={t['trial_id'] for t in assessment['trials']}; seen=set()
            if not isinstance(rows,list): raise ValueError('Trial comparisons must be explicit')
            for item in rows:
                if not isinstance(item,dict) or set(item)!={'trial_id','independent','comparison_evidence_id','cost_evidence_id','conclusion'}:
                    raise ValueError('Invalid trial comparison')
                for key in ('trial_id','comparison_evidence_id','cost_evidence_id'): _text(item[key],key)
                if item['trial_id'] in seen or item['trial_id'] not in expected: raise StateConflict('Trial comparison coverage is inconsistent')
                seen.add(item['trial_id'])
                if item['independent'] is not True or item['conclusion']!='SUPPORTED': raise StateConflict('Review does not establish supported independent benefit')
                trial=c.execute('''SELECT o.task_id,o.task_revision FROM growth_trial t JOIN operation o ON o.operation_id=t.operation_id
                    WHERE t.trial_id=? AND t.candidate_id=?''',(item['trial_id'],candidate_id)).fetchone()
                if not c.execute('SELECT 1 FROM growth_outcome WHERE trial_id=? AND evidence_id=?',
                                 (item['trial_id'],item['comparison_evidence_id'])).fetchone():
                    raise StateConflict('Comparison must reference recorded trial outcome evidence')
                for key in ('comparison_evidence_id','cost_evidence_id'):
                    reference=item[key]
                    if reference==review_evidence_id or c.execute('SELECT task_id,task_revision FROM evidence WHERE evidence_id=?',(reference,)).fetchone()!=trial:
                        raise StateConflict('Comparison and cost evidence must belong to the trial revision, not the validation review')
                    self.evidence._read_in_transaction(evidence_id=reference,owner=owner,purpose='growth',max_bytes=262144)
            if seen!=expected: raise StateConflict('Review must account for every current trial')
            c.execute('INSERT INTO growth_lifecycle VALUES (?,?,?,?,?,?,?,?)',
                (review_id,candidate_id,assessment['state'],'VALIDATED',review_evidence_id,authority_ref,None,fingerprint))
            c.execute("UPDATE growth_candidate SET state='VALIDATED' WHERE candidate_id=?",(candidate_id,))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                ('GROWTH_VALIDATED',review_id,_json({'candidate_id':candidate_id,'assessment_sha256':expected_assessment_sha256,'review_evidence_id':review_evidence_id})))
            return {'decision':'VALIDATED','state':'VALIDATED','assurance':'CONTROLLER_REVIEWED_EVIDENCE',
                    'host_identity_independently_verified':False,'application_authorized':False,'global_rules_changed':False}

    def retire(self, *, review_id, candidate_id, owner, expected_state, action,
               review_evidence_id, authority_ref, successor_id=None):
        """Logical retirement preserves all bytes, provenance and pending effects."""
        for key,value in [('review_id',review_id),('candidate_id',candidate_id),('owner',owner),
                          ('expected_state',expected_state),('review_evidence_id',review_evidence_id),('authority_ref',authority_ref)]:
            _text(value,key)
        if action not in {'deprecate','reject','remove'}: raise ValueError('Unsupported Growth retirement action')
        if successor_id is not None:
            _text(successor_id,'successor_id')
            if action!='deprecate': raise ValueError('A successor is bound only during deprecation')
        fingerprint=hashlib.sha256(_json([candidate_id,owner,expected_state,action,review_evidence_id,authority_ref,successor_id]).encode()).hexdigest()
        with self.store.transaction() as c:
            self.store.require_execution_ready()
            prior=c.execute('SELECT request_hash,new_state FROM growth_lifecycle WHERE review_id=?',(review_id,)).fetchone()
            if prior:
                if prior[0]!=fingerprint: raise StateConflict('Lifecycle review identity is immutable')
                return {'decision':'REPLAY','historical_state':prior[1],'bytes_deleted':False}
            row=c.execute('SELECT owner,state,proposal_evidence_id FROM growth_candidate WHERE candidate_id=?',(candidate_id,)).fetchone()
            if row is None or row[0]!=owner: raise PermissionError('Candidate owner mismatch')
            if row[1]!=expected_state: raise StateConflict('Candidate state changed before lifecycle review')
            if action=='remove':
                if row[1]!='DEPRECATED': raise StateConflict('Logical removal requires prior deprecation')
                state='REMOVED'
            else:
                if row[1] in {'DEPRECATED','REMOVED','REJECTED'}: raise StateConflict('Candidate is already retired')
                state='DEPRECATED' if action=='deprecate' else 'REJECTED'
            # Old sources may already be revoked. A new authorized review can
            # still stop use without copying inaccessible old proposal contents.
            self._read(review_evidence_id,owner)
            if successor_id is not None:
                successor=c.execute('SELECT owner,state,proposal_evidence_id FROM growth_candidate WHERE candidate_id=?',(successor_id,)).fetchone()
                if successor_id==candidate_id or successor is None or successor[0]!=owner or successor[1]!='CANDIDATE':
                    raise StateConflict('Successor must be a distinct same-project untried candidate')
                if successor[2]==row[2]: raise StateConflict('Successor requires a separately reviewed proposal')
                self._eligible(successor_id,owner)
                cycle=c.execute('''WITH RECURSIVE successors(id) AS (
                    SELECT ? UNION SELECT l.successor_id FROM growth_lifecycle l JOIN successors s ON l.candidate_id=s.id
                    WHERE l.successor_id IS NOT NULL) SELECT 1 FROM successors WHERE id=?''',(successor_id,candidate_id)).fetchone()
                if cycle: raise StateConflict('Successor lineage would create a cycle')
            c.execute('INSERT INTO growth_lifecycle VALUES (?,?,?,?,?,?,?,?)',
                      (review_id,candidate_id,row[1],state,review_evidence_id,authority_ref,successor_id,fingerprint))
            c.execute('UPDATE growth_candidate SET state=? WHERE candidate_id=?',(state,candidate_id))
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                      ('GROWTH_RETIRED',review_id,_json({'candidate_id':candidate_id,'state':state,'successor_id':successor_id})))
            return {'decision':'RETIRED','state':state,'bytes_deleted':False,'successor_promoted':False}

    def retrieve(self, *, owner, task_type=None, tool=None, failure_signature=None, after_id='', limit=20, max_bytes=262144):
        _text(owner,'owner')
        if type(limit) is not int or not 1<=limit<=100 or not isinstance(after_id,str):
            raise ValueError('Invalid Growth query page')
        if type(max_bytes) is not int or not 1024<=max_bytes<=16777216:
            raise ValueError('Growth byte budget must be between 1024 and 16777216')
        query={'task_types':task_type,'tools':tool,'failure_signatures':failure_signature}
        for key,value in query.items():
            if value is not None: _text(value,key)
        if not any(query.values()): raise ValueError('Growth query requires task context')
        c=self.store.connection
        c.execute('BEGIN')
        try:
            self.store.require_execution_ready()
            rows=c.execute('''SELECT candidate_id,proposal_evidence_id,state FROM growth_candidate
                WHERE owner=? AND candidate_id>? ORDER BY candidate_id LIMIT ?''',(owner,after_id,limit+1)).fetchall()
            matches=[]
            consumed=0
            last_examined=after_id
            deferred=None
            minimum=None
            unavailable=[]
            def read_bounded(evidence_id):
                nonlocal consumed
                data,storage_bytes=self.evidence._read_metered_in_transaction(evidence_id=evidence_id,owner=owner,purpose='growth',max_bytes=max_bytes-consumed)
                consumed+=storage_bytes
                return data
            from v2_protected_inputs import ProtectedInputError
            for candidate_id,proposal_id,state in rows[:limit]:
                if state not in ELIGIBLE:
                    last_examined=candidate_id
                    continue
                start_bytes=consumed
                try:
                    document=proposal_document(read_bounded(proposal_id))
                    for (source,) in c.execute('SELECT evidence_id FROM growth_source WHERE candidate_id=?',(candidate_id,)).fetchall():
                        read_bounded(source)
                    if state=='VALIDATED': self._read_validation(candidate_id,read_bounded)
                except EvidenceReadLimit as exc:
                    minimum=consumed-start_bytes+exc.minimum_bytes
                    consumed+=exc.bytes_read
                    deferred=candidate_id
                    break
                except (PermissionError, EvidenceCorrupt, FileNotFoundError, StateConflict) as exc:
                    consumed+=getattr(exc,'bytes_read',0)
                    last_examined=candidate_id
                    continue
                except ProtectedInputError as exc:
                    consumed+=getattr(exc,'bytes_read',0)
                    unavailable.append({'candidate_id':candidate_id,'reason':'PROTECTED_INPUT_UNAVAILABLE'})
                    last_examined=candidate_id
                    continue
                last_examined=candidate_id
                profile=document['applicability']
                # Unspecified non-safety dimensions do not erase relevant matches.
                # An unknown tool cannot satisfy a declared tool restriction.
                if not matches_profile(profile,query): continue
                matches.append({'candidate_id':candidate_id,'state':state,'proposal':document,'application_authorized':False})
            result={'candidates':matches,'next_after_id':last_examined if deferred is not None or len(rows)>limit else None,
                    'pagination_consistency':'LIVE_KEYSET','writes_performed':False,
                    'bytes_read':consumed,'byte_budget':max_bytes,'budget_exhausted':deferred is not None,
                    'deferred_candidate_id':deferred,'minimum_candidate_bytes':minimum,
                    'byte_accounting':'STORED_EVIDENCE_BYTES','unavailable_candidates':unavailable}
            c.execute('COMMIT')
            return result
        except BaseException:
            if c.in_transaction: c.execute('ROLLBACK')
            raise
