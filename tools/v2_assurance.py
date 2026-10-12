"""Explicit limits of registered effects and trusted-controller observations."""
def assurance(*,registered_effects_reconciled=False,operator_review=False):
    return {'registered_effects_reconciled':registered_effects_reconciled,
        'registered_effect_coverage':'DATABASE_REGISTERED_EFFECTS',
        'external_writer_coverage':'OPERATOR_REVIEWED_PROJECT_ROOTS' if operator_review else 'NOT_INDEPENDENTLY_OBSERVED',
        'external_writer_isolation':'UNKNOWN','external_writer_isolation_assurance':'UNKNOWN',
        'host_authentication':'NOT_ENFORCED','native_adapter_qualification':'UNQUALIFIED',
        'physical_external_writer_fence':False,'unmediated_host_actions_controlled':False,
        'cross_session_qualified':False,'cross_machine_supported':False,'atomic_snapshot':False,
        'scope':'Current registered service state; external processes and native model behavior require separate proof'}

class UnqualifiedAdapter(PermissionError):pass

def require_adapter_assurance(request):
    if request.get('require_independently_qualified_adapter') is True:raise UnqualifiedAdapter('Independent Host/Agent qualification unavailable')
