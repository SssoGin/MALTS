"""Closed, path-free diagnostics shared by CLI, MCP and entry negotiation."""
from v2_state_store import StateConflict


class OperationConflict(StateConflict):
    """Public operation refusal selected at the failing guard, never from exception text."""
    messages = {
        'GRANT_BUDGET_EXHAUSTED': 'Execution grant operation budget exhausted. Review a bounded successor grant for the same authorized work.',
        'TASK_BUDGET_EXHAUSTED': 'Cumulative Task operation budget exhausted. Review the Task budget and its current revision.',
        'PROJECT_BUDGET_EXHAUSTED': 'Cumulative Project operation budget exhausted. Review the Project budget and its current revision.',
        'GRANT_REVOKED': 'The execution grant was revoked. Review current authority before requesting further work.',
        'GRANT_REVISION_STALE': 'The execution grant binds an older Task revision. Review the current Task and its grants.',
        'TASK_STATE_NOT_ADMITTED': 'The Task state does not admit this operation. Inspect the current Task context.',
        'GRANT_EXPIRED': 'The execution grant has expired. Review current authority for the intended work.',
        'DEPENDENCIES_NOT_ACCEPTED': 'Task dependencies lack current accepted results. Inspect dependency evidence.',
        'HOST_NOT_ADMITTED': 'The managed Host is no longer admitted for new effects. Inspect its original dispatch.',
        'PHASE_BINDING_REQUIRED': 'The revised Task needs an explicit Phase binding. Review the current Task and Phase.',
        'PHASE_NOT_CURRENT_ACTIVE': 'The bound Phase is inactive or its revision changed. Inspect the Phase binding.',
        'OPERATION_REQUEST_MISMATCH': 'The original operation and this request differ. Inspect the original request before proceeding.',
        'PENDING_EFFECT': 'An effect is pending or unknown. Reconcile the original operation before admitting another.',
        'RESOURCE_IDENTITY_UNAVAILABLE': 'The resource identity could not be established. Inspect the intended resource.',
        'RESOURCE_IDENTITY_CHANGED': 'The resource identity changed after preparation. Check the original resource and operation.',
        'RESOURCE_HELD': 'A pending or unknown operation holds a conflicting resource. Check the holder before continuing.',
        'LEASE_NOT_CURRENT': 'The lease is stale, expired, quarantined or released. Reconcile the original operation before further execution.',
        'INTENT_ALREADY_ISSUED': 'This operation cannot be cancelled as unexecuted. Inspect the original intent and observed effect.',
        'OBSERVATION_CONFLICT': 'The observation conflicts with the original record. Check the original operation and receipt.',
        'RUNTIME_IDENTITY_CHANGED': 'Runtime identity changed during admission. Check the active installation before proceeding.',
        'RUNTIME_NOT_ACTIVE': 'The loaded runtime is no longer active. Reconnect this Host and check the loaded version.',
        'LIFECYCLE_TRANSACTION_PENDING': 'An installation transaction needs review or recovery. Inspect the original transaction before executing.',
        'LIFECYCLE_TRANSACTION_INVALID': 'Installation transaction storage is invalid. Inspect lifecycle integrity before executing.',
        'GRANT_DEFINITION_CONFLICT': 'The grant ID already has a different or revoked definition. Preserve the original grant and review the intended authority.',
        'BUDGET_POLICY_STALE': 'The budget policy or its revision changed. Read the current policy before an amendment.',
        'BUDGET_BELOW_CONSUMPTION': 'The proposed limit is below recorded consumption. An amendment cannot erase previous use.',
    }

    def __init__(self, reason_code):
        self.reason_code = reason_code
        super().__init__(self.messages[reason_code])

    def public_error(self):
        return {'decision': 'ERROR', 'error_type': 'StateConflict', 'error_code': 'STATE_CONFLICT',
                'reason_code': self.reason_code, 'message': self.messages[self.reason_code]}


class OperationBudgetExhausted(OperationConflict):
    def __init__(self, scope, consumed, maximum):
        super().__init__({'grant': 'GRANT_BUDGET_EXHAUSTED', 'task': 'TASK_BUDGET_EXHAUSTED',
                          'project': 'PROJECT_BUDGET_EXHAUSTED'}[scope])
        self.scope, self.consumed, self.maximum = scope, consumed, maximum

    def public_error(self):
        result = super().public_error()
        result.update(budget_scope=self.scope, intents_consumed=self.consumed, max_operations=self.maximum,
                      remaining_operations=0, accounting_unit='COMMITTED_OPERATION_INTENT')
        result['message'] += f' Committed intents: {self.consumed}/{self.maximum}.'
        return result


class PlanHashMismatch(StateConflict):
    def __init__(self, *, expected,computed,stage,source_kind=None):
        super().__init__('Reviewed plan hash differs')
        self.expected,self.computed,self.stage,self.source_kind=expected,computed,stage,source_kind

def entry_error(error,stage):
    from malts_lifecycle import LifecycleError
    cause=error.code if isinstance(error,LifecycleError) else 'WORKSPACE_BINDING_OR_AUTHORITY_CONFLICT' if isinstance(error,StateConflict) else 'STORAGE_UNAVAILABLE' if isinstance(error,OSError) else 'ENTRY_FORMAT_INVALID'
    result={'status':'BLOCKED','reason':'PACKAGE_VERIFICATION_FAILED' if stage=='VERIFY_PACKAGE' else 'ENTRY_IDENTITY_OR_FORMAT_UNAVAILABLE',
        'cause_code':cause,'stage':stage,'context':'generation_manifest.json' if stage=='VERIFY_PACKAGE' else 'selected-workspace' if stage.startswith('WORKSPACE') else 'active-identity',
        'action':'REPAIR_OR_INSTALL_VERIFIED_RUNTIME' if stage=='VERIFY_PACKAGE' else 'INSPECT_CURRENT_AUTHORITY_AND_ORIGINAL_JOURNAL',
        'execution_authorized':False,'write_allowed':False}
    if isinstance(error,LifecycleError) and hasattr(error,'counts'):result.update(error.counts)
    return result

def require_plan_hash(plan,expected,stage):
    from v2_state_store import _json
    import hashlib
    computed=hashlib.sha256(_json({k:v for k,v in plan.items() if k!='plan_sha256'}).encode('utf-8')).hexdigest()
    if computed!=plan.get('plan_sha256') or expected!=plan.get('plan_sha256'):
        raise PlanHashMismatch(expected=expected,computed=computed,stage=stage,source_kind=plan.get('source_kind','ADOPTED'))
