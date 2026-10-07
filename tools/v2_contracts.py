"""Closed candidate Task acceptance definitions, including explicit legacy text input."""
LEVELS={'D':1,'C':2,'B':3,'A':4}


def artifact_definition(value):
    """Validate a proposed definition only; never enroll, read payloads or grant rights.

    Store consumers must additionally resolve owners/targets, check physical
    locators and authority, and validate evidence before accepting this proposal.
    """
    import json,re
    from pathlib import Path
    from datetime import datetime
    from malts_user_contracts import validate_instance
    fields={'artifact_id','owner','role','locator','authority','retention','mode','sha256','relations','role_contract'}
    if not isinstance(value,dict) or set(value)!=fields:
        raise ValueError('Artifact definition must match its closed contract')
    encoded=json.dumps(value,ensure_ascii=False,allow_nan=False)
    if len(encoded.encode('utf-8'))>32768:raise ValueError('Artifact definition exceeds its byte budget')
    def text(item):return isinstance(item,str) and bool(item.strip()) and len(item)<=2048
    if not isinstance(value['artifact_id'],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',value['artifact_id']):
        raise ValueError('Invalid Artifact identity')
    owner=value['owner']
    if (not isinstance(owner,dict) or set(owner)!={'kind','id'} or not text(owner['kind']) or
        owner['kind'] not in {'PHASE','SESSION','SHARED','ARCHIVE','RUNTIME'} or not text(owner['id'])):
        raise ValueError('Artifact requires an explicit typed owner')
    if not text(value['role']) or value['role'] not in {'WORKING','DELIVERABLE','EVIDENCE','RECOVERY'}:
        raise ValueError('Invalid primary Artifact role')
    if not text(value['authority']) or value['authority'] not in {'WORKSPACE','SOURCE_PROJECT','EXTERNAL','GENERATED'}:
        raise ValueError('Invalid Artifact authority')
    if not isinstance(value['locator'],dict) or validate_instance(Path(__file__).resolve().parent.parent,'resource-locator',value['locator']):
        raise ValueError('Invalid typed resource locator')
    retention=value['retention']
    if not isinstance(retention,dict) or set(retention)!={'policy','expires_at'} or not text(retention['policy']):
        raise ValueError('Artifact requires an explicit retention policy')
    if retention['expires_at'] is not None:
        if not text(retention['expires_at']):raise ValueError('Invalid retention expiry')
        instant=datetime.fromisoformat(retention['expires_at'].replace('Z','+00:00'))
        if instant.tzinfo is None:raise ValueError('Retention expiry requires a timezone')
    if not text(value['mode']) or value['mode'] not in {'LIVE','FROZEN'}:
        raise ValueError('Artifact requires LIVE or FROZEN mode')
    digest=value['sha256']
    if digest is not None and (not isinstance(digest,str) or not re.fullmatch('[a-fA-F0-9]{64}',digest)):
        raise ValueError('Invalid content digest')
    if value['mode']=='FROZEN' and digest is None:raise ValueError('Frozen Artifact requires a content digest')
    relations=value['relations']
    if not isinstance(relations,list) or len(relations)>64:raise ValueError('Invalid Artifact relations')
    seen=set()
    for relation in relations:
        if (not isinstance(relation,dict) or set(relation)!={'kind','target'} or not text(relation['kind']) or
            relation['kind'] not in {'MIRROR_OF','GENERATED_FROM','SUPERSEDES','SUPERSEDED_BY','EVIDENCE_FOR','RECOVERY_FOR'} or
            not text(relation['target'])):raise ValueError('Invalid typed Artifact relation')
        pair=(relation['kind'],relation['target'])
        if pair in seen:raise ValueError('Duplicate Artifact relation')
        seen.add(pair)
    contract=value['role_contract']
    required={'EVIDENCE':{'target','evidence_id'},'RECOVERY':{'target','restore','scope','verify'}}.get(value['role'],set())
    if not isinstance(contract,dict) or set(contract)!=required or any(not text(v) for v in contract.values()):
        raise ValueError('Artifact role contract is incomplete or has unknown fields')
    if value['role']=='RECOVERY':
        placeholders={'n/a','na','none','null','-','tbd','tbc'}
        if any(item.strip().lower() in placeholders for item in [*contract.values(),retention['policy']]):
            raise ValueError('Recovery contract and retention require concrete descriptions, not placeholders')
    if required:
        targets=[r['target'] for r in relations if r['kind']==value['role']+'_FOR']
        if targets!=[contract['target']]:raise ValueError('Artifact role requires one matching typed target')
    return json.loads(encoded)


def phase_boundary(value):
    if not isinstance(value,dict) or set(value)!={'in_scope','out_of_scope'}:
        raise ValueError('Expected explicit Phase scope boundary')
    for key,values in value.items():
        if not isinstance(values,list) or (key=='in_scope' and not values) or any(not isinstance(v,str) or not v.strip() for v in values):
            raise ValueError('Phase boundary must contain text arrays')
    return {key:list(values) for key,values in value.items()}


def criteria(values):
    if not isinstance(values,list) or not values:
        raise ValueError('Acceptance requires a nonempty list')
    result=[]
    fields={'criterion_id','description','hard','verification_method','minimum_evidence_level'}
    for value in values:
        if isinstance(value,str):
            if not value.strip(): raise ValueError('Empty legacy criterion')
            value={'criterion_id':value,'description':value,'hard':True,'verification_method':'declared-review','minimum_evidence_level':'D'}
        if not isinstance(value,dict) or set(value)!=fields:
            raise ValueError('Acceptance criterion must match its closed contract')
        if any(not isinstance(value[k],str) or not value[k].strip() for k in ('criterion_id','description','verification_method')):
            raise ValueError('Criterion identity, description and method must be nonempty')
        if type(value['hard']) is not bool or value['minimum_evidence_level'] not in LEVELS:
            raise ValueError('Invalid criterion requirement or evidence level')
        result.append(dict(value))
    if len({v['criterion_id'] for v in result})!=len(result):
        raise ValueError('Duplicate criterion IDs')
    return result
