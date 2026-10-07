"""Pure completion policy; callers must supply trusted artifact observations.

Observations are measured by the owning runtime, never copied from the proof
packet. This module checks bindings; it does not claim that an evidence string
proves execution, and it performs no filesystem or host operations.
"""
from __future__ import annotations

import re
import json
from pathlib import Path
from collections import Counter
from typing import Any
from malts_user_contracts import validate_against_schema

EVIDENCE_STRENGTH = {'A': 4, 'B': 3, 'C': 2, 'D': 1}
HASH = re.compile(r'[A-Fa-f0-9]{64}')
PROOF_SCHEMA = json.loads(Path(__file__).with_name('completion_proof.schema.json').read_text(encoding='utf-8'))


def evaluate_completion(
    contract: dict[str, Any],
    contract_sha256: str,
    proof: dict[str, Any] | None,
    observed_artifacts: dict[str, str],
    execution_states: dict[str, str],
) -> list[str]:
    """Return stable rejection codes for a current, schema-validated contract.

Failed/cancelled earlier attempts are allowed after verified recovery. Pending
or unknown execution cannot be hidden by successful acceptance evidence.
Proof contains one current result per criterion; historical results belong in
the evidence store, where their provenance remains available.
"""
    if not isinstance(proof, dict):
        return ['RC_DONE_PROOF_REQUIRED']
    if validate_against_schema(proof, PROOF_SCHEMA):
        return ['RC_DONE_PROOF_INVALID']
    issues: list[str] = []
    if not HASH.fullmatch(contract_sha256) or proof.get('contract_sha256', '').upper() != contract_sha256.upper():
        issues.append('RC_DONE_STALE_REVISION')
    criteria = contract.get('acceptance_criteria', [])
    ids = [row.get('criterion_id') for row in criteria]
    if not ids or any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
        issues.append('RC_DONE_INVALID_CRITERIA')
    if proof.get('remaining_work') != []:
        issues.append('RC_DONE_REMAINING_WORK')
    terminal = {'SUCCEEDED', 'FAILED', 'CANCELLED', 'NOT_RUN'}
    if any(state not in terminal for state in execution_states.values()):
        issues.append('RC_DONE_UNRESOLVED_EXECUTION')

    artifacts = proof.get('artifacts', [])
    artifact_ids = [row.get('artifact_id') for row in artifacts]
    if not artifacts or len(set(artifact_ids)) != len(artifact_ids):
        issues.append('RC_DONE_STALE_ARTIFACT')
    valid_artifacts: set[str] = set()
    for row in artifacts:
        artifact_id, expected = row.get('artifact_id'), row.get('sha256')
        observed = observed_artifacts.get(artifact_id)
        if (not isinstance(artifact_id, str) or not artifact_id or
                not isinstance(expected, str) or not HASH.fullmatch(expected) or
                not isinstance(observed, str) or observed.upper() != expected.upper()):
            issues.append('RC_DONE_STALE_ARTIFACT')
        else:
            valid_artifacts.add(artifact_id)

    verification = proof.get('verification', [])
    counts = Counter(row.get('criterion_id') for row in verification)
    if any(count != 1 or key not in ids for key, count in counts.items()):
        issues.append('RC_DONE_AMBIGUOUS_VERIFICATION')
    by_id = {row.get('criterion_id'): row for row in verification}
    for criterion in criteria:
        if not criterion.get('hard'):
            continue
        row = by_id.get(criterion['criterion_id'], {})
        if row.get('result') != 'PASS':
            issues.append('RC_DONE_HARD_CRITERIA')
        refs = row.get('evidence_refs', [])
        bound = row.get('artifact_ids', [])
        if (EVIDENCE_STRENGTH.get(row.get('evidence_level'), 0) <
                EVIDENCE_STRENGTH.get(criterion.get('minimum_evidence_level'), 99) or
                not refs or any(not isinstance(ref, str) or not ref.strip() for ref in refs) or
                not bound or not set(bound).issubset(valid_artifacts)):
            issues.append('RC_DONE_EVIDENCE')
    return list(dict.fromkeys(issues))
