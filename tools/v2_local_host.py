"""Mediated create/read file operations for an explicitly trusted local caller.

Not an OS sandbox or an authentication layer. Grant provenance must be approved
by the owning host; this adapter enforces the bound operation's file parameters.
"""
import hashlib
import json
import os
import re
from pathlib import Path
from v2_operations import Operations
from v2_state_store import StateConflict, _json
from v2_evidence import _regular_path
from v2_operation_inputs import operation_parameters


class FileReadParametersError(ValueError):
    """Closed adapter contract failure, without exposing rejected values."""


def unambiguous_relative_file(value):
    """Portable normal file names; excludes Windows streams/devices/aliases."""
    if not isinstance(value,str) or not value:
        raise PermissionError('Create path requires a nonempty relative file name')
    segments=value.replace('\\','/').split('/')
    if any(not part or part in {'.','..'} or part.endswith((' ','.')) or
           any(ord(ch)<32 or ch in '<>:"|?*' for ch in part) or
           re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?',part,re.IGNORECASE)
           for part in segments):
        raise PermissionError('Create path contains a device, stream or ambiguous file name')
    relative=Path(value)
    if relative.is_absolute() or relative.drive:
        raise PermissionError('Create path must be relative')
    return relative


def verify_task_file_results(store,task_id,task_revision):
    """Verify current managed create/read versions for this Task revision.

    Other Host effect kinds need their own verifiers. Intent order, not late
    observation order, determines the current result for an exact resource path.
    This is a read-only current-result check, never a rewrite of historical facts.
    """
    rows=store.connection.execute('''SELECT o.operation_id,o.request_json,o.request_hash,o.grant_id,
        g.actor,g.resource,g.effect,p.resource_root,
        (SELECT max(a.sequence) FROM execution_audit a WHERE a.subject_id=o.operation_id AND a.kind='INTENT_RECORDED')
        FROM operation o JOIN execution_grant g ON g.grant_id=o.grant_id
        JOIN task t ON t.task_id=o.task_id JOIN project p ON p.project_id=t.project_id
        WHERE o.task_id=? AND o.task_revision=? AND o.state IN ('OBSERVED','ACCEPTED') ORDER BY 9 DESC''',
        (task_id,task_revision)).fetchall()
    latest_write={}; latest_read={}
    for operation_id,request_json,request_hash,grant_id,actor,resource,effect,root_text,intent in rows:
        parameters=operation_parameters(store,operation_id)
        if not isinstance(parameters,dict): raise StateConflict('Invalid operation parameters')
        kind=parameters.get('tool')
        if kind not in {'create-file','read-file','update-file'}: continue
        expected_fields=({'tool','path'} if kind=='read-file' else {'tool','path','content'} if kind=='create-file'
                         else {'tool','path','content','expected_sha256','preimage_policy'})
        # Export provenance is a protected create-file extension. Verification
        # checks the existing copy; source permissions gate new propagation.
        if kind=='create-file' and 'evidence_export' in parameters:
            expected_fields=expected_fields|{'evidence_export'}
            if not isinstance(parameters['evidence_export'],str) or not parameters['evidence_export']:
                raise StateConflict('Managed export source is invalid')
        if (set(parameters)!=expected_fields or effect!=('read' if kind=='read-file' else 'write') or
                parameters['path']!=resource or intent is None): raise StateConflict('Managed file result contract is incomplete')
        fingerprint=hashlib.sha256(_json([grant_id,actor,resource,effect,json.loads(request_json)]).encode()).hexdigest()
        if fingerprint!=request_hash: raise StateConflict('Managed file request changed')
        relative=unambiguous_relative_file(parameters['path'])
        root=Path(root_text).absolute(); identity=(str(root),relative.as_posix())
        if kind=='update-file':
            from v2_file_update import preimage_record
            record=preimage_record(store,operation_id)
        bucket=latest_read if kind=='read-file' else latest_write
        if identity not in bucket: bucket[identity]=(intent,operation_id,parameters)
    checked=0
    for identity in set(latest_write)|set(latest_read):
        root=Path(identity[0]); target=root/identity[1]; expectations=set()
        write=latest_write.get(identity); read=latest_read.get(identity)
        if write:
            if not isinstance(write[2]['content'],str): raise StateConflict('Invalid managed write content')
            expected=write[2]['content'].encode('utf-8')
            expectations.add((hashlib.sha256(expected).hexdigest(),len(expected)))
        if read and (write is None or read[0]>write[0]):
            from v2_observation_content import read_reference
            observations=store.connection.execute("SELECT observation_id FROM operation_observation WHERE operation_id=? AND outcome='SUCCEEDED'",(read[1],)).fetchall()
            matches=[re.fullmatch(r'local-read:sha256:([a-f0-9]{64}):bytes:(0|[1-9][0-9]*)',read_reference(store,row[0])) for row in observations]
            matches=[match for match in matches if match]
            if len(matches)!=1: raise StateConflict('Managed read lacks a unique observed content version')
            expectations.add((matches[0][1],int(matches[0][2])))
        if len(expectations)!=1: raise StateConflict('Current read and write versions disagree')
        expected_hash,expected_size=next(iter(expectations))
        try:
            _regular_path(target)
            if not target.is_file() or not target.resolve().is_relative_to(root.resolve()):
                raise StateConflict('Managed file result is missing or no longer a regular in-scope file')
            digest=hashlib.sha256(); size=0
            with target.open('rb') as stream:
                if os.fstat(stream.fileno()).st_size!=expected_size: raise StateConflict('Managed file result size changed')
                for chunk in iter(lambda:stream.read(min(65536,expected_size-size+1)),b''):
                    size+=len(chunk)
                    if size>expected_size: raise StateConflict('Managed result grew during verification')
                    digest.update(chunk)
            if size!=expected_size or digest.hexdigest()!=expected_hash: raise StateConflict('Managed file result bytes changed')
        except OSError as error: raise StateConflict('Managed file result is unavailable') from error
        checked+=1
    return checked


class LocalFileHost:
    def __init__(self,store,*,required_resource_root=None):
        self.store=store
        self.operations=Operations(store)
        self.required_resource_root=Path(required_resource_root).resolve() if required_resource_root is not None else None

    def update_file(self, *, operation_id, actor, expected_request_hash):
        from v2_file_update import update_file
        return update_file(self,operation_id=operation_id,actor=actor,expected_request_hash=expected_request_hash)

    def reconcile_update(self, *, operation_id, actor, expected_request_hash):
        from v2_file_update import reconcile_update
        return reconcile_update(self,operation_id=operation_id,actor=actor,expected_request_hash=expected_request_hash)

    def repair_update(self, *, review, approved_sha256, authority_ref):
        from v2_update_repair import repair_update
        return repair_update(self,review=review,approved_sha256=approved_sha256,authority_ref=authority_ref)

    def read_file(self, *, operation_id, actor, expected_request_hash, max_bytes=16777216, max_characters=16384):
        if type(max_bytes) is not int or not 1<=max_bytes<=67108864 or type(max_characters) is not int or not 0<=max_characters<=65536:
            raise ValueError('Invalid managed read budget')
        row=self.store.connection.execute('''SELECT o.request_json,o.request_hash,g.resource,g.effect,p.resource_root,g.actor
            FROM operation o JOIN execution_grant g ON g.grant_id=o.grant_id JOIN task t ON t.task_id=o.task_id
            JOIN project p ON p.project_id=t.project_id WHERE o.operation_id=?''',(operation_id,)).fetchone()
        if row is None or row[1]!=expected_request_hash: raise StateConflict('Read operation request is missing or stale')
        parameters=operation_parameters(self.store,operation_id,actor=actor)
        if not isinstance(parameters,dict) or set(parameters)!={'tool','path'} or parameters['tool']!='read-file':
            raise FileReadParametersError('Read adapter requires closed read-file parameters')
        if row[3]!='read' or row[5]!=actor or parameters['path']!=row[2]: raise PermissionError('Read parameters or actor differ from Grant')
        relative=unambiguous_relative_file(parameters['path']); root=Path(row[4]).absolute()
        from v2_management import protect_business_resource
        protect_business_resource(self.store,root,relative)
        if self.required_resource_root is not None and root.resolve()!=self.required_resource_root: raise PermissionError('Host resource root differs from policy')
        intent=self.operations.record_intent(operation_id,actor,expected_request_hash)
        if not intent['execute_once']: return {'decision':'NOT_REEXECUTED','operation_state':intent['state']}
        self.operations.verify_lease(operation_id=operation_id,actor=actor,token=intent['lease_token'])
        try:
            target=root/relative; _regular_path(target)
            if not target.is_file() or not target.resolve().is_relative_to(root.resolve()): raise ValueError('Read target is not a regular in-scope file')
            with target.open('rb') as stream:
                data=stream.read(max_bytes+1)
            if len(data)>max_bytes: raise ValueError('Managed read exceeds byte budget')
        except (OSError,ValueError):
            self.operations.observe(observation_id=operation_id+'-local-read',operation_id=operation_id,actor=actor,
                                    outcome='FAILED',evidence_ref='local-read:failed-or-over-budget')
            raise
        digest=hashlib.sha256(data).hexdigest()
        self.operations.observe(observation_id=operation_id+'-local-read',operation_id=operation_id,actor=actor,outcome='SUCCEEDED',
                                evidence_ref=f'local-read:sha256:{digest}:bytes:{len(data)}')
        try: decoded=data.decode('utf-8-sig')
        except UnicodeError: decoded=None
        return {'decision':'READ','path':parameters['path'],'sha256':digest,'bytes':len(data),
                'text':None if decoded is None else decoded[:max_characters],
                'text_truncated':decoded is not None and len(decoded)>max_characters,
                'binary':decoded is None,'resource_bytes_written':0}

    def create_file(self, *, operation_id, actor, expected_request_hash):
        row=self.store.connection.execute('''SELECT o.request_json,o.request_hash,g.resource,g.effect,p.resource_root
            FROM operation o JOIN execution_grant g ON g.grant_id=o.grant_id
            JOIN task t ON t.task_id=o.task_id JOIN project p ON p.project_id=t.project_id
            WHERE o.operation_id=?''',(operation_id,)).fetchone()
        if row is None or row[1]!=expected_request_hash:
            raise StateConflict('Operation request binding is missing or stale')
        parameters=operation_parameters(self.store,operation_id,actor=actor)
        if set(parameters) not in ({'tool','path','content'},{'tool','path','content','evidence_export'}) or parameters['tool']!='create-file':
            raise ValueError('This adapter supports only closed create-file parameters')
        if row[3]!='write' or parameters['path']!=row[2] or not isinstance(parameters['content'],str):
            raise PermissionError('File parameters do not match the write grant')
        relative=unambiguous_relative_file(parameters['path'])
        root=Path(row[4]).resolve()
        if self.required_resource_root is not None and root!=self.required_resource_root:
            raise PermissionError('Host resource root differs from its pinned policy')
        target=root/relative
        from v2_management import protect_business_resource
        protect_business_resource(self.store,root,relative)
        _regular_path(target)
        if not target.parent.is_dir() or not target.resolve().is_relative_to(root):
            raise PermissionError('Create target has no permitted parent')
        content=parameters['content'].encode('utf-8')
        intent=self.operations.record_intent(operation_id,actor,expected_request_hash)
        if not intent['execute_once']:
            return {'decision':'NOT_REEXECUTED','operation_state':intent['state']}
        self.operations.verify_lease(operation_id=operation_id,actor=actor,token=intent['lease_token'])
        created=False
        try:
            # Exclusive creation protects existing user files, including races
            # with another creator. No arbitrary shell or program is invoked.
            with target.open('xb') as output:
                created=True
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            observed=target.read_bytes()
            if observed!=content:
                raise OSError('Created file does not match the prepared bytes')
            digest=hashlib.sha256(observed).hexdigest()
            self.operations.observe(observation_id=operation_id+'-local-result',operation_id=operation_id,
                                    actor=actor,outcome='SUCCEEDED',evidence_ref='local-file:sha256:'+digest)
            return {'decision':'CREATED','path':parameters['path'],'sha256':digest,'bytes':len(content)}
        except OSError:
            # A partially created file is retained and remains UNKNOWN. There is
            # no destructive cleanup or retry that might erase actual effects.
            self.operations.observe(observation_id=operation_id+'-local-result',operation_id=operation_id,
                                    actor=actor,outcome='UNKNOWN' if created else 'FAILED',
                                    evidence_ref='local-file:partial-or-unverified' if created else 'local-file:not-created')
            raise
