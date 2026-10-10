"""Candidate complete backup unit. Restoration is deliberately read-only until requalification."""
import hashlib
import json
import os
import sqlite3
import uuid
import shutil
from contextlib import closing
from pathlib import Path
from v2_state_store import StateStore, SCHEMA_VERSION, _json
from v2_evidence import BlobStore, EvidenceCorrupt, _regular_path


def _hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _managed_paths(connection):
    from v2_operation_inputs import protected_files
    rows=connection.execute('SELECT source_path FROM legacy_control_source').fetchall()
    paths={'legacy-source/manifest.json','legacy-source/controls/runtime/workspace_control.json',
           'reviewed-mapping.json','definition-import.json'} if rows else set()
    paths.update('legacy-source/controls/'+row[0] for row in rows)
    paths.update(row[0] for row in connection.execute("SELECT plan_ref FROM phase_revision WHERE plan_scope='STATE'"))
    paths.update(protected_files(connection))
    for relative in paths:
        path=Path(relative)
        if path.is_absolute() or path.drive or '..' in path.parts or ':' in relative:
            raise EvidenceCorrupt('Managed backup path escapes state directory')
    return sorted(paths)


def _copy_managed(source_root,target_root,relative,expected_hash=None):
    path=Path(relative)
    if path.is_absolute() or path.drive or '..' in path.parts or ':' in relative:
        raise EvidenceCorrupt('Invalid managed backup path')
    source,target=source_root/path,target_root/path
    _regular_path(source)
    _regular_path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    with source.open('rb') as src,target.open('xb') as dst:
        shutil.copyfileobj(src,dst,1024*1024)
        dst.flush(); os.fsync(dst.fileno())
    actual=_hash(target)
    if expected_hash is not None and actual!=expected_hash: raise EvidenceCorrupt('Managed file changed during restore')
    return {'path':relative,'sha256':actual}


def _managed_expected_hashes(connection):
    from v2_operation_inputs import protected_files
    expected={'legacy-source/controls/'+path:digest for path,digest in connection.execute('SELECT source_path,source_sha256 FROM legacy_control_source')}
    for path,digest in connection.execute("SELECT plan_ref,plan_sha256 FROM phase_revision WHERE plan_scope='STATE'"):
        if path in expected and expected[path]!=digest: raise EvidenceCorrupt('Managed plan versions require distinct preserved files')
        expected[path]=digest
    expected.update(protected_files(connection))
    return expected


def _referenced_blobs(snapshot):
    digests={r[0] for r in snapshot.connection.execute('SELECT DISTINCT blob_hash FROM evidence')}
    return sorted(digests)


def backup(store: StateStore, blobs: BlobStore, destination: Path) -> dict:
    destination = Path(destination).absolute()
    _regular_path(destination)
    state=store.path.parent.resolve()
    if state.is_relative_to(destination.resolve()) or any(destination.resolve().is_relative_to(state/p)
            for p in ('blobs','legacy-source','plans','protected-inputs')):
        raise ValueError('Backup cannot contain the state root or occupy managed input namespaces')
    destination.mkdir()  # Never overwrite an existing backup.
    database = destination/'state.db'
    with closing(sqlite3.connect(database)) as target:
        store.connection.backup(target)
    # Derive references and watermarks from the backup, not the moving source.
    with closing(StateStore(database, readonly=True)) as snapshot:
        c = snapshot.connection
        if c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or c.execute('PRAGMA foreign_key_check').fetchall():
            raise EvidenceCorrupt('Backup database is inconsistent')
        watermarks = {table: c.execute(f'SELECT coalesce(max(sequence),0) FROM {table}').fetchone()[0]
                      for table in ('audit', 'execution_audit', 'evidence')}
        managed_paths=_managed_paths(c)
        managed_hashes=_managed_expected_hashes(c)
    # Protected inputs are required to verify preimage bindings. Copy the
    # snapshot-selected immutable ciphertext before following those references.
    managed=[_copy_managed(store.path.parent,destination,relative,managed_hashes.get(relative)) for relative in managed_paths]
    with closing(StateStore(database,readonly=True)) as snapshot:
        digests=_referenced_blobs(snapshot)
    blob_root = destination/'blobs'
    blob_root.mkdir()
    target_blobs = BlobStore(blob_root)
    for digest in digests:
        copied = target_blobs.put(blobs.read(digest))
        if copied != digest:
            raise EvidenceCorrupt('Copied evidence identity mismatch')
    manifest = {'format': 2, 'state_schema': SCHEMA_VERSION, 'database_sha256': _hash(database),
                'blobs': digests, 'watermarks': watermarks, 'resume_authorized': False,'managed_files':managed}
    pending_manifest = destination/'.manifest.pending'
    with pending_manifest.open('x', encoding='utf-8') as output:
        output.write(_json(manifest))
        output.flush()
        os.fsync(output.fileno())
    # Publish only synchronized bytes; never overwrite another manifest.
    # Incomplete directories remain for review and are not reused for retries.
    os.link(pending_manifest, destination/'manifest.json')
    pending_manifest.unlink()
    return manifest


def verify_backup(root: Path) -> dict:
    """Verify stored bytes/references, not availability of a Host decryption context."""
    root = Path(root).absolute()
    _regular_path(root/'manifest.json')
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    fields = {'format','state_schema','database_sha256','blobs','watermarks','resume_authorized','managed_files'}
    if set(manifest) != fields or manifest['format'] != 2 or manifest['state_schema'] != SCHEMA_VERSION or manifest['resume_authorized'] is not False:
        raise EvidenceCorrupt('Unsupported or invalid backup manifest')
    _regular_path(root/'state.db')
    if _hash(root/'state.db') != manifest['database_sha256']:
        raise EvidenceCorrupt('Backup database hash mismatch')
    with closing(StateStore(root/'state.db', readonly=True)) as snapshot:
        c = snapshot.connection
        if c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or c.execute('PRAGMA foreign_key_check').fetchall():
            raise EvidenceCorrupt('Backup integrity failure')
        expected = _referenced_blobs(snapshot)
        observed = {table: c.execute(f'SELECT coalesce(max(sequence),0) FROM {table}').fetchone()[0]
                    for table in ('audit', 'execution_audit', 'evidence')}
        managed_paths=_managed_paths(c)
        managed_hashes=_managed_expected_hashes(c)
    if expected != manifest['blobs'] or observed != manifest['watermarks']:
        raise EvidenceCorrupt('Backup reference or watermark mismatch')
    blobs = BlobStore(root/'blobs', readonly=True)
    for digest in expected:
        blobs.verify(digest)
    records=manifest['managed_files']
    if (not isinstance(records,list) or any(not isinstance(r,dict) or set(r)!={'path','sha256'} for r in records)
            or [r['path'] for r in records]!=managed_paths):
        raise EvidenceCorrupt('Managed backup file set differs from database references')
    for record in records:
        target=root/record['path']
        _regular_path(target)
        if _hash(target)!=record['sha256']: raise EvidenceCorrupt('Managed backup file hash mismatch')
        if record['path'] in managed_hashes and record['sha256']!=managed_hashes[record['path']]: raise EvidenceCorrupt('Managed backup bytes do not match recorded provenance')
    expected_files={'manifest.json','state.db',*['blobs/'+digest[:2]+'/'+digest for digest in expected],*managed_paths}
    actual_files=set()
    for path in root.rglob('*'):
        _regular_path(path)
        if path.is_file(): actual_files.add(path.relative_to(root).as_posix())
    if actual_files!=expected_files: raise EvidenceCorrupt('Backup contains missing or unlisted files')
    return manifest


def restore_backup(source: Path, destination: Path, *, expected_manifest_sha256: str | None = None) -> dict:
    """Restore to a new directory under quarantine; never overwrite live state."""
    source, destination = Path(source).absolute(), Path(destination).absolute()
    _regular_path(source);_regular_path(destination)
    if source.resolve().is_relative_to(destination.resolve()) or destination.resolve().is_relative_to(source.resolve()):
        raise ValueError('Restore and backup directories must not overlap')
    manifest = verify_backup(source)
    manifest_sha256 = hashlib.sha256(_json(manifest).encode('utf-8')).hexdigest()
    if expected_manifest_sha256 is not None and manifest_sha256 != expected_manifest_sha256:
        raise EvidenceCorrupt('Backup manifest does not match the reviewed backup')
    _regular_path(destination)
    destination.mkdir()
    pending_database = destination/'.restoring.db'
    # The backup is an immutable, closed database image, not a live database.
    # Bind the exact copied bytes to its manifest before opening or transforming
    # them; a second SQLite backup could otherwise accept changed source state.
    _regular_path(source/'state.db')
    with (source/'state.db').open('rb') as saved, pending_database.open('xb') as output:
        shutil.copyfileobj(saved,output,1024*1024)
        output.flush()
        os.fsync(output.fileno())
    if _hash(pending_database)!=manifest['database_sha256']:
        raise EvidenceCorrupt('Backup database changed before or during restoration')
    (destination/'blobs').mkdir()
    original_blobs, restored_blobs = BlobStore(source/'blobs', readonly=True), BlobStore(destination/'blobs')
    for digest in manifest['blobs']:
        if restored_blobs.put(original_blobs.read(digest)) != digest:
            raise EvidenceCorrupt('Restored blob identity mismatch')
    for record in manifest['managed_files']:
        _copy_managed(source,destination,record['path'],record['sha256'])
    epoch = str(uuid.uuid4())
    with closing(StateStore(pending_database)) as restored:
        with restored.transaction() as c:
            c.execute('UPDATE recovery_state SET epoch=?,reconciliation_required=1,source_backup_hash=? WHERE singleton=1',
                      (epoch,manifest['database_sha256']))
            c.execute('UPDATE execution_grant SET revoked=1')
            from v2_definition_content import encode
            for (project_id,) in c.execute('SELECT project_id FROM dispatch_budget').fetchall():
                protected=encode('restore:'+epoch,project_id,'dispatch-budget',project_id,0,'revocation_ref')
                c.execute("UPDATE dispatch_budget SET revoked=1,consumption_known=0,consumption_basis='UNKNOWN_AFTER_RESTORE',revocation_ref=coalesce(revocation_ref,?) WHERE project_id=?",(protected,project_id))
            c.execute("UPDATE operation_lease SET state='QUARANTINED' WHERE state='HELD'")
            # Completion is preserved as history, not fresh validity in the new
            # epoch. An explicit later verification may establish new acceptance.
            c.execute('UPDATE acceptance SET valid=0,invalidation_ref=? WHERE valid=1',('restore:'+epoch,))
            c.execute("UPDATE operation SET state='UNKNOWN' WHERE state='INTENT_RECORDED'")
            c.execute("UPDATE host_dispatch SET state='UNKNOWN' WHERE launch_committed=1 AND coalesce(quiesced,0)=0")
            c.execute("UPDATE operation SET state='CANCELLED' WHERE state='PREPARED'")
            c.execute("""UPDATE execution_run SET state=CASE WHEN EXISTS(
                SELECT 1 FROM operation o WHERE o.task_id=execution_run.task_id AND o.state='UNKNOWN')
                THEN 'PAUSE_REQUESTED' ELSE 'PAUSED' END WHERE state='OPEN'""")
            c.execute("UPDATE task SET status='PAUSED' WHERE status IN ('READY','RUNNING','VERIFYING','WAITING','RECOVERY_REQUIRED')")
            c.execute("UPDATE task_effect_recovery SET resume_status='PAUSED'")
            from v2_task_lifecycle import reconcile_effect_state
            for (task_id,) in c.execute('SELECT task_id FROM task').fetchall():
                reconcile_effect_state(c,task_id,fact_ref='restore:'+epoch)
            c.execute("UPDATE phase SET state='PAUSED' WHERE state='ACTIVE'")
            c.execute("UPDATE phase SET state='PAUSED' WHERE state='COMPLETED'")
            c.execute("UPDATE phase_completion SET valid=0,invalidation_ref='restore' WHERE valid=1")
            c.execute("UPDATE project_completion SET valid=0,invalidation_ref='restore' WHERE valid=1")
            c.execute('INSERT INTO execution_audit(kind,subject_id,details_json) VALUES (?,?,?)',
                      ('BACKUP_RESTORED',epoch,_json({'source_hash':manifest['database_sha256'],'watermarks':manifest['watermarks'],'reconciliation_required':True})))
    pending_database.rename(destination/'state.db')
    return {'epoch':epoch,'reconciliation_required':True,'execution_authorized':False,
            'source_watermarks':manifest['watermarks']}
