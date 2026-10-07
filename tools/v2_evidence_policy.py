"""Explicit capture/propagation declarations; trusted Host authentication is external.

This contract is not a secret detector or an assertion that caller-supplied
classification proves sanitization. Protected artifacts cannot propagate to Growth.
"""
from datetime import datetime, timezone
from v2_state_store import StateConflict, _text


FIELDS = {'owner', 'target', 'content_class', 'sensitivity', 'redaction_policy_version',
          'verification_scope', 'retention', 'access_scope', 'review_ref'}
PURPOSES = {'verification', 'recovery', 'growth', 'derivation', 'export'}


def validate_descriptor(value, *, project_id, task_id, task_revision, criterion):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError('Evidence requires a closed capture descriptor')
    if value['owner'] != project_id or value['target'] != {
            'task_id': task_id, 'task_revision': task_revision, 'criterion': criterion}:
        raise StateConflict('Evidence descriptor owner or target mismatch')
    if value['content_class'] not in {'synthetic', 'reviewed-artifact', 'redacted-observation','protected-artifact'}:
        raise ValueError('Unsupported evidence content class; do not capture raw logs or prompts')
    allowed={'public','project','sensitive','unknown'} if value['content_class']=='protected-artifact' else {'public','project'}
    if value['sensitivity'] not in allowed:
        raise ValueError('Unknown or sensitive raw evidence is not capturable')
    for field in ('redaction_policy_version', 'verification_scope', 'review_ref'):
        _text(value[field], field)
        if len(value[field]) > 256:
            raise ValueError('Evidence descriptor text exceeds bounded size')
    retention = value['retention']
    if not isinstance(retention, dict) or set(retention) != {'reuse_until', 'preserve_recovery_references'} or retention['preserve_recovery_references'] is not True:
        raise ValueError('Retention must preserve recovery references')
    if retention['reuse_until'] is not None:
        expiry(retention['reuse_until'])
    access = value['access_scope']
    if (not isinstance(access, dict) or set(access) != {'project_id', 'purposes'} or
            access['project_id'] != project_id or not isinstance(access['purposes'], list) or
            not access['purposes'] or any(not isinstance(p, str) or p not in PURPOSES for p in access['purposes']) or
            len(set(access['purposes'])) != len(access['purposes'])):
        raise ValueError('Evidence access must name its owner project and supported purposes')
    if value['content_class']=='protected-artifact' and 'growth' in access['purposes']:
        raise PermissionError('Raw protected artifacts require a separately reviewed derivative for Growth')
    if 'export' in access['purposes'] and (value['content_class']!='redacted-observation' or value['sensitivity']!='public'):
        raise PermissionError('Export requires an explicitly public reviewed derivative')
    return value


def expiry(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Invalid evidence reuse expiry') from None
    if result.tzinfo is None:
        raise ValueError('Evidence expiry requires timezone')
    return result


def require_access(descriptor, *, owner, purpose, revoked, now=None):
    if (revoked or owner != descriptor['owner'] or
            purpose not in descriptor['access_scope']['purposes']):
        raise PermissionError('Evidence propagation is not allowed for this owner or purpose')
    until = descriptor['retention']['reuse_until']
    if until is not None and expiry(until) <= (now or datetime.now(timezone.utc)):
        raise PermissionError('Evidence reuse has expired; retained bytes are not permission to reuse')
