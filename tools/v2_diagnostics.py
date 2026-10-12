"""Closed, path-free diagnostics shared by CLI, MCP and entry negotiation."""
from v2_state_store import StateConflict

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
