"""Native lifecycle authority facts in the existing durable execution audit.

Only the trusted relocation controller writes this closed record. Native state
is not represented as a legacy import/adoption and the state schema is unchanged.
"""
import json,re
from pathlib import Path
from contextlib import contextmanager
from v2_state_store import StateConflict,_json

KIND='NATIVE_AUTHORITY'
FIELDS={'format','version','operation_id','state','epoch','state_dir','workspace_root','journal_root','plan_sha256','receipt_sha256'}


def current(connection):
    row=connection.execute('SELECT details_json FROM execution_audit WHERE kind=? ORDER BY sequence DESC LIMIT 1',(KIND,)).fetchone()
    if row is None:return None
    value=json.loads(row[0])
    if (not isinstance(value,dict) or set(value)!=FIELDS or value['format']!='malts.v2.native-authority' or type(value['version']) is not int or value['version']!=1 or
            value['state'] not in {'RESTORED','PREPARED','SUPERSEDED','ACTIVE'} or
            any(not isinstance(value[k],str) or not value[k].strip() for k in ('operation_id','epoch','state_dir','workspace_root','journal_root')) or
            not isinstance(value['plan_sha256'],str) or re.fullmatch('[a-f0-9]{64}',value['plan_sha256']) is None or
            (value['state']=='ACTIVE' and (not isinstance(value['receipt_sha256'],str) or re.fullmatch('[a-f0-9]{64}',value['receipt_sha256']) is None))):
        raise StateConflict('Native authority record is invalid')
    return value


def require_authority(store, *, write=False):
    value=current(store.connection)
    if value is None:return
    if value['state']=='RESTORED' and write:return  # reconciliation, never execution
    if value['state']!='ACTIVE':raise StateConflict('Native state authority is '+value['state']+'; use its original relocation journal')
    epoch=store.connection.execute('SELECT epoch FROM recovery_state').fetchone()[0]
    if Path(value['state_dir']).resolve()!=store.path.parent.resolve() or value['epoch']!=epoch:
        raise StateConflict('Native authority location or epoch changed')
    from v2_evidence import _regular_path
    path=Path(value['workspace_root'])/'.malts/native.json';_regular_path(path)
    locator=json.loads(path.read_text(encoding='utf-8'))
    projects=store.connection.execute('SELECT project_id,resource_root FROM project').fetchall()
    if len(projects)!=1:raise StateConflict('Native authority requires exactly one project')
    expected={'format':'malts.v2.native-location','version':1,'state_dir':value['state_dir'],'project_id':projects[0][0],'epoch':epoch}
    if len(projects)!=1 or projects[0][1]!=value['workspace_root'] or locator!=expected:
        raise StateConflict('Native authority locator no longer matches the selected store')
    receipt_path=Path(value['journal_root'])/'native-cutover.json';_regular_path(receipt_path)
    import hashlib
    receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    if hashlib.sha256(_json(receipt).encode('utf-8')).hexdigest()!=value['receipt_sha256']:
        raise StateConflict('Native authority cutover receipt changed')


def append(connection,value):
    if set(value)!=FIELDS:raise ValueError('Invalid native lifecycle fact')
    connection.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',(KIND,value['operation_id'],_json(value)))


@contextmanager
def lifecycle_transaction(store,expected):
    """Controller-only transaction: bind the exact already inspected fact."""
    c=store.connection;c.execute('BEGIN IMMEDIATE')
    try:
        if current(c)!=expected:raise StateConflict('Native lifecycle authority changed')
        yield c
        c.execute('COMMIT')
    except BaseException:
        if c.in_transaction:c.execute('ROLLBACK')
        raise
