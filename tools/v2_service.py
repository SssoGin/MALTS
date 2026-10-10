"""Transport-neutral candidate request dispatch; no Host permission is inferred.

Transport adapters own caller policy and input-file access. Domain services retain
all state, scope, evidence, fencing and acceptance checks. Adoption/Host handoff
is intentionally not in this generic action registry.
"""
import inspect
import json
import sqlite3
from pathlib import Path
from v2_state_store import StateStore,StateConflict
from v2_operations import Operations, OperationParameterLimit, MAX_INLINE_PARAMETERS_BYTES, GrantAccessDenied
from v2_acceptance import Acceptance
from v2_evidence import BlobStore
from v2_runs import Runs
from v2_local_host import LocalFileHost,FileReadParametersError
from v2_growth import Growth
from v2_governance import Governance
from v2_protected_inputs import ProtectedInputError
from v2_evidence_derivation import Derivations
from v2_definition_content import DefinitionPreviews
from v2_task_lifecycle import Verification
from v2_artifacts import Artifacts
from v2_handoff import HandoffNotes


class WorkerAdmissionDenied(PermissionError):
    """A bound Worker is no longer admitted; no state or identity is echoed."""
    def __init__(self):super().__init__('Worker dispatch is no longer admitted')


class HostBoundFieldError(PermissionError):
    """Expose only a whitelisted field name, never either field value."""
    def __init__(self,field):
        if field not in {'actor','owner','project_id','authority_ref','capture_authority_ref'}:
            raise ValueError('Unknown Host-bound field')
        self.field=field
        super().__init__('Client cannot replace a Host-bound field')

ACTIONS = {
    'handoff.preserve-note':HandoffNotes.preserve,
    'handoff.capture-file':HandoffNotes.capture_file,
    'handoff.publish':HandoffNotes.publish,
    'handoff.inspect-publication':HandoffNotes.inspect_publication,
    'artifact.register':Artifacts.register,
    'artifact.reconcile':Artifacts.reconcile,
    'artifact.inspect-payload':Artifacts.inspect_payload,
    'artifact.promote':Artifacts.promote,
    'artifact.retire-shared':Artifacts.retire_shared,
    'artifact.rebuild-relations':Artifacts.rebuild_relation_index,
    'artifact.bind-recovery':Artifacts.bind_recovery,
    'artifact.recover-successor':Artifacts.recover_successor,
    'verification.begin':Verification.begin,'verification.rework':Verification.rework,
    'project.define':Governance.define_project, 'phase.define':Governance.define_phase,
    'phase.set-active':Governance.set_phase_active,
    'phase.reopen':Governance.reopen_phase,
    'phase.complete':Governance.complete_phase,
    'project.complete':Governance.complete_project,
    'phase.bind-task':Governance.bind_task,
    'phase.carry-task':Governance.carry_task,
    'task.revise':StateStore.revise_task, 'task.depend':StateStore.add_dependency, 'task.cancel':StateStore.cancel_task,
    'task.configure-budget':Operations.configure_task_budget,
    'project.configure-budget':Operations.configure_project_budget,
    'budget.amend':Operations.amend_budget,
    'grant.record':Operations.record_grant, 'grant.revoke':Operations.revoke_grant,
    'operation.prepare':Operations.prepare, 'operation.intent':Operations.record_intent,
    'operation.observe':Operations.observe, 'operation.cancel-prepared':Operations.cancel_prepared,
    'operation.create-file':LocalFileHost.create_file, 'operation.renew-lease':Operations.renew_lease,
    'operation.read-file':LocalFileHost.read_file,
    'operation.update-file':LocalFileHost.update_file,
    'operation.reconcile-update':LocalFileHost.reconcile_update,
    'operation.repair-update':LocalFileHost.repair_update,
    'evidence.record':Acceptance.record, 'evidence.invalidate':Acceptance.invalidate,
    'evidence.derive':Derivations.record,
    'evidence.derive-outcome':Derivations.record_closed_outcome,
    'evidence.prepare-outcome-export':Derivations.prepare_outcome_export,
    'definition.refresh-preview':DefinitionPreviews.refresh,
    'verification.managed-files':Acceptance.verify_managed_files,
    'evidence.revoke-access':Acceptance.revoke_access, 'task.accept':Acceptance.accept,
    'growth.propose':Growth.propose, 'growth.begin-trial':Growth.begin_trial,
    'growth.record-outcome':Growth.record_outcome, 'growth.retire':Growth.retire,
    'growth.validate':Growth.validate_candidate,
    'run.open':Runs.open, 'run.pause':Runs.pause, 'run.resume':Runs.resume,
    'run.rebuild-checkpoint':Runs.rebuild_checkpoint,
}

def load_request_json(path):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('Duplicate JSON field')
            result[key]=value
        return result
    def constant(value):
        raise ValueError('Non-finite JSON number')
    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=pairs, parse_constant=constant)


def checked_arguments(request):
    if (not isinstance(request,dict) or set(request)!={'action','arguments'} or
            not isinstance(request['action'],str) or request['action'] not in ACTIONS or
            not isinstance(request['arguments'],dict)):
        raise ValueError('Expected a closed action/arguments request')
    # A transport-decoded object must have the same JSON value domain as CLI
    # input; SDK permissiveness must not admit NaN/Infinity or Python objects.
    json.dumps(request,allow_nan=False)
    arguments=dict(request['arguments'])
    if request['action'] in {'evidence.record','evidence.derive'}:
        if 'data' in arguments or not isinstance(arguments.get('data_file'),str):
            raise ValueError('Evidence requires data_file')
        arguments.pop('data_file')
        arguments['data']=None  # signature check never opens the input file
    inspect.signature(ACTIONS[request['action']]).bind(None,**arguments)
    return arguments


def action_contracts(allowed=None):
    actions={}
    for name,method in sorted(ACTIONS.items()):
        if allowed is not None and name not in allowed: continue
        parameters={}
        for key,value in inspect.signature(method).parameters.items():
            if key=='self': continue
            parameters['data_file' if name in {'evidence.record','evidence.derive'} and key=='data' else key]={
                'required':value.default is inspect.Parameter.empty or (name in {'evidence.record','evidence.derive'} and key=='descriptor')}
        actions[name]={'parameters':parameters,'apply_required':True,'nested_semantic_validation_in_service':True}
        if name=='operation.prepare':
            actions[name]['new_inline_parameters_limit']={'bytes':MAX_INLINE_PARAMETERS_BYTES,'encoding':'CANONICAL_JSON_UTF8',
                                                         'existing_identical_operation_replay_exempt':True}
            actions[name]['file_adapter_parameters']={
                'read-file':{'effect':'read','required_fields':{'tool':'read-file','path':'GRANTED_RELATIVE_RESOURCE'},
                             'additional_fields':False,
                             'execution':'operation.read-file uses operation_id and the returned request_hash as expected_request_hash; read limits belong to execution arguments.'},
                'create-file':{'effect':'write','required_fields':{'tool':'create-file','path':'GRANTED_RELATIVE_RESOURCE','content':'UTF8_TEXT'},
                               'optional_fields':['evidence_export']},
                'update-file':{'effect':'write','required_fields':{'tool':'update-file','path':'GRANTED_RELATIVE_RESOURCE',
                               'content':'UTF8_TEXT','expected_sha256':'CURRENT_BYTE_SHA256','preimage_policy':'PROTECTED_CAPTURE_POLICY'},
                               'additional_fields':False}}
    return actions


def execute_request(store,request,*,evidence_reader=None,required_resource_root=None):
    """Invoke one whitelisted service method, retaining its transaction boundary.

    Callers must supply a writable, explicitly selected store. A restricted
    transport supplies an evidence_reader rather than inheriting CLI file access.
    """
    checked_arguments(request)
    if store.readonly: raise PermissionError('Request execution requires a writable store')
    method=ACTIONS[request['action']]
    owner=method.__qualname__.split('.')[0]
    if owner=='StateStore': instance=store
    elif owner=='Operations': instance=Operations(store)
    elif owner=='Runs': instance=Runs(store)
    elif owner=='LocalFileHost': instance=LocalFileHost(store,required_resource_root=required_resource_root)
    elif owner=='Governance': instance=Governance(store)
    elif owner=='Acceptance': instance=Acceptance(store,BlobStore(store.path.parent/'blobs'))
    elif owner=='Growth': instance=Growth(store,BlobStore(store.path.parent/'blobs'))
    elif owner=='Derivations': instance=Derivations(store,BlobStore(store.path.parent/'blobs'))
    elif owner=='DefinitionPreviews': instance=DefinitionPreviews(store)
    elif owner=='Verification': instance=Verification(store)
    elif owner=='Artifacts': instance=Artifacts(store,required_resource_root=required_resource_root)
    elif owner=='HandoffNotes': instance=HandoffNotes(store)
    else: raise ValueError('Unknown registered service owner')
    arguments=dict(request['arguments'])
    if request['action'] in {'evidence.record','evidence.derive'}:
        path=arguments.pop('data_file')
        arguments['data']=Path(path).read_bytes() if evidence_reader is None else evidence_reader(path)
        if not isinstance(arguments['data'],bytes): raise ValueError('Evidence reader must return exact bytes')
    return {'decision':'REQUEST_PROCESSED','action':request['action'],'result':method(instance,**arguments)}


def safe_error(error):
    """Stable public error data; never includes raw exception messages or input."""
    from v2_adoption_host import ControlHandoffError
    if isinstance(error,ControlHandoffError):
        return {'decision':'ERROR','error_type':'ControlHandoffError','error_code':'ADOPTION_HANDOFF_BLOCKED',
                'reason_code':error.reason_code,
                'message':'Control handoff was not established. Inspect the original adoption ID/plan and retained seals; release conflicting input access or use the discovered active runtime. Do not create a replacement migration.'}
    if isinstance(error,(GrantAccessDenied,WorkerAdmissionDenied)):
        reason=error.reason_code if isinstance(error,GrantAccessDenied) else 'DISPATCH_NOT_ADMITTED'
        return {'decision':'ERROR','error_type':'PermissionError','error_code':'ACCESS_DENIED','reason_code':reason,
                'message':'No operation was admitted. Inspect the current bound dispatch and existing Grant metadata; do not invent an ID or replay an unknown effect.'}
    if isinstance(error,HostBoundFieldError):
        return {'decision':'ERROR','error_type':'PermissionError','error_code':'ACCESS_DENIED','reason_code':'HOST_BOUND_FIELD_MISMATCH',
                'host_bound_field':error.field,'message':'Omit this field from the client arguments; the configured Host supplies it. No authority was changed.'}
    if isinstance(error,FileReadParametersError):
        return {'decision':'ERROR','error_type':'ValueError','error_code':'INVALID_INPUT','reason_code':'FILE_READ_PARAMETERS_INVALID',
                'required_preparation_fields':['tool','path'],'required_tool':'read-file',
                'message':'Read preparation requires exactly tool and path. Execution limits belong to operation.read-file arguments; do not replay an existing operation with different parameters.'}
    if isinstance(error,ProtectedInputError):
        return {'decision':'ERROR','error_type':type(error).__name__,'error_code':'PROTECTED_INPUT_UNAVAILABLE',
                'message':'Protected input is unavailable; check the protection context, binding and retained ciphertext.'}
    if isinstance(error,OperationParameterLimit):
        return {'decision':'ERROR','error_type':type(error).__name__,'error_code':'OPERATION_PARAMETERS_TOO_LARGE',
                'message':'Cannot admit new inline operation parameters above the byte limit.',
                'parameter_bytes':error.observed_bytes,'limit_bytes':error.limit_bytes}
    if isinstance(error,PermissionError): code,message='ACCESS_DENIED','Access is denied for this operation or evidence purpose.'
    elif isinstance(error,StateConflict): code,message='STATE_CONFLICT','Current state conflicts with the request; inspect current task and operation state.'
    elif isinstance(error,OSError): code,message='IO_ERROR','Required storage or input is unavailable; inspect the authorized local path.'
    elif isinstance(error,sqlite3.Error): code,message='STORAGE_ERROR','Storage operation failed; preserve state and inspect database integrity or contention.'
    else: code,message='INVALID_INPUT','Input does not satisfy the command contract; check fields, types and identifiers.'
    return {'decision':'ERROR','error_type':type(error).__name__,'error_code':code,'message':message}
