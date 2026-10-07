"""Translate an actual Host-reviewed scope into reusable bounded Grants.

The review hash is a consistency binding, NOT an authentication proof. Only a
trusted controller may construct ReviewedAuthority after resolving real existing
authorization. Never load an Agent-authored document as an approved authority.
This module is deliberately absent from the MCP client action registry.
"""
import hashlib
import json
from v2_state_store import StateConflict, _json, _text
from v2_operations import Operations


def task_authority_context(store, task_id):
    c=store.connection
    if not c.in_transaction:
        c.execute('BEGIN')
        try: return task_authority_context(store,task_id)
        finally: c.execute('ROLLBACK')
    task=store.task(task_id)
    if task is None: raise StateConflict('Unknown authority Task')
    task={key:value for key,value in task.items() if key not in {'status','acceptance_valid'}}
    project=c.execute('SELECT resource_root FROM project WHERE project_id=?',(task['project_id'],)).fetchone()
    epoch=c.execute('SELECT epoch FROM recovery_state WHERE singleton=1').fetchone()
    phase=c.execute('SELECT b.phase_id,b.phase_revision,p.revision FROM phase_task b JOIN phase p ON p.phase_id=b.phase_id WHERE b.task_id=? AND b.task_revision=?',
                    (task_id,task['revision'])).fetchall()
    project_revision=c.execute('SELECT max(revision) FROM project_revision WHERE project_id=?',(task['project_id'],)).fetchone()[0]
    dependencies=c.execute('SELECT predecessor_id,predecessor_revision FROM dependency WHERE task_id=? AND task_revision=? ORDER BY predecessor_id',
                           (task_id,task['revision'])).fetchall()
    return {'task':task,'resource_root':project[0],'epoch':epoch[0],
            'project_revision':project_revision,'phase_binding':phase,'dependencies':dependencies}


def authority_hash(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def review_request(store, *, task_id, actor, resources, expires_at):
    """Read-only exact proposal; it grants no authority and prompts no user."""
    _text(actor,'actor')
    context=task_authority_context(store,task_id)
    if not isinstance(resources,list) or not resources: raise ValueError('Explicit bounded resources are required')
    seen=set()
    for item in resources:
        if not isinstance(item,dict) or set(item)!={'resource','effect','max_operations'}:
            raise ValueError('Expected resource, effect and max_operations')
        if item['resource'] not in context['task']['scope'] or item['effect'] not in {'read','write','external'}:
            raise StateConflict('Approval exceeds declared Task resource/effect')
        if type(item['max_operations']) is not int or item['max_operations']<1:
            raise ValueError('Each approved resource/effect needs a positive operation limit')
        key=(item['resource'],item['effect'])
        if key in seen: raise ValueError('Duplicate resource/effect approval')
        seen.add(key)
    if expires_at is not None:
        _text(expires_at,'expires_at')
        Operations._instant(expires_at)
    result={'schema':1,'context':context,'actor':actor,'expires_at':expires_at,
            'resources':sorted(resources,key=lambda value:(value['resource'],value['effect']))}
    # Freeze caller-owned nested input. The hash includes budgets and expiry.
    return json.loads(_json(result))


class ReviewedAuthority:
    def __init__(self, review, *, approved_sha256, source_ref):
        _text(source_ref,'source_ref')
        if authority_hash(review)!=approved_sha256:
            raise StateConflict('Approved proposal hash differs from the supplied scope')
        self._review_json=_json(review)
        self._approved_sha256=approved_sha256
        self._source_ref=source_ref

    def issue(self, store, *, resource, effect):
        review=json.loads(self._review_json)
        # Revalidate the closed proposal before issuing, rather than trusting
        # the existence of a hash or a caller-created Python instance.
        if set(review)!={'schema','context','actor','expires_at','resources'} or review['schema']!=1:
            raise ValueError('Unknown authority proposal')
        current=review_request(store,task_id=review['context']['task']['task_id'],actor=review['actor'],
                               resources=review['resources'],expires_at=review['expires_at'])
        if authority_hash(current)!=self._approved_sha256:
            raise StateConflict('Task, epoch, root or scope changed after review')
        item=next((item for item in review['resources'] if (item['resource'],item['effect'])==(resource,effect)),None)
        if item is None: raise PermissionError('Resource/effect was not approved')
        grant_id='reviewed-'+authority_hash([self._approved_sha256,resource,effect])
        task=review['context']['task']
        result=Operations(store).record_grant(grant_id=grant_id,task_id=task['task_id'],task_revision=task['revision'],
            actor=review['actor'],source_ref=self._source_ref+'#review-sha256='+self._approved_sha256,
            resource=resource,effect=effect,expires_at=review['expires_at'],max_operations=item['max_operations'],
            expected_authority_sha256=authority_hash(review['context']),authority_review_sha256=self._approved_sha256)
        return {'decision':result,'grant_id':grant_id,'review_sha256':self._approved_sha256}

    def revoke(self, store, *, source_ref):
        """Durably withdraw this exact review, including not-yet-issued Grants."""
        _text(source_ref,'source_ref')
        review=json.loads(self._review_json)
        ids=['reviewed-'+authority_hash([self._approved_sha256,item['resource'],item['effect']]) for item in review['resources']]
        with store.transaction() as c:
            from v2_definition_content import encode,decode
            owner=review['context']['task']['project_id']
            old=c.execute("SELECT details_json FROM execution_audit WHERE kind='AUTHORITY_REVOKED' AND subject_id=?",
                          (self._approved_sha256,)).fetchone()
            if old:
                recorded=decode(json.loads(old[0])['source_ref'],owner,'authority-revocation',self._approved_sha256,0,'source_ref')
                if recorded!=source_ref: raise StateConflict('Authority revocation is immutable')
                return {'decision':'REPLAY','review_sha256':self._approved_sha256}
            protected_source=encode(source_ref,owner,'authority-revocation',self._approved_sha256,0,'source_ref')
            for grant_id in ids: c.execute('UPDATE execution_grant SET revoked=1 WHERE grant_id=?',(grant_id,))
            Operations._audit(c,'AUTHORITY_REVOKED',self._approved_sha256,{'source_ref':protected_source,'grant_ids':ids})
        return {'decision':'REVOKED','review_sha256':self._approved_sha256}
