"""Content-addressed candidate evidence blobs; no implicit directory creation on reads."""
from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
from pathlib import Path

DIGEST = re.compile(r'[a-f0-9]{64}')


class EvidenceCorrupt(ValueError):
    def __init__(self, message, *, bytes_read=0):
        super().__init__(message)
        self.bytes_read=bytes_read


class EvidenceReadLimit(ValueError):
    def __init__(self, minimum_bytes, bytes_read=0):
        super().__init__('Evidence exceeds the requested read budget')
        self.minimum_bytes=minimum_bytes
        self.bytes_read=bytes_read


def _regular_path(path: Path) -> None:
    # Check ancestors before descendants so a rejected parent link is never
    # traversed even for metadata inspection of a child outside the trust root.
    for part in reversed((path, *path.parents)):
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), 'st_file_attributes', 0) & 0x400):
            raise EvidenceCorrupt('Evidence paths cannot traverse links or reparse points')


class BlobStore:
    def __init__(self, root: Path, *, readonly=False):
        self.root = Path(root).absolute()
        _regular_path(self.root)
        if not self.root.is_dir():
            raise FileNotFoundError(self.root)
        self.readonly = readonly

    def path(self, digest: str) -> Path:
        if not isinstance(digest, str) or DIGEST.fullmatch(digest) is None:
            raise ValueError('Expected lowercase SHA-256')
        path = self.root / digest[:2] / digest
        _regular_path(path)
        return path

    def verify(self, digest: str) -> Path:
        path = self.path(digest)
        actual = hashlib.sha256()
        with path.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                actual.update(chunk)
        if actual.hexdigest() != digest:
            raise EvidenceCorrupt('Blob bytes do not match their content identity')
        return path

    def read(self, digest: str, *, max_bytes=None) -> bytes:
        # Validate the same bytes that are returned, not an earlier open handle.
        if max_bytes is not None and (type(max_bytes) is not int or max_bytes<0):
            raise ValueError('Read budget must be a nonnegative integer')
        with self.path(digest).open('rb') as source:
            size=os.fstat(source.fileno()).st_size
            if max_bytes is not None and size>max_bytes:
                raise EvidenceReadLimit(size)
            data=source.read() if max_bytes is None else source.read(max_bytes+1)
            if max_bytes is not None and len(data)>max_bytes:
                raise EvidenceReadLimit(len(data),len(data))
        if hashlib.sha256(data).hexdigest() != digest:
            raise EvidenceCorrupt('Blob bytes do not match their content identity',bytes_read=len(data))
        return data

    def put(self, data: bytes) -> str:
        if self.readonly:
            raise PermissionError('Read-only blob store')
        if not isinstance(data, bytes):
            raise TypeError('Evidence payload must be bytes')
        digest = hashlib.sha256(data).hexdigest()
        target = self.path(digest)
        if target.exists():
            self.verify(digest)
            return digest
        target.parent.mkdir(exist_ok=True)
        _regular_path(target.parent)
        descriptor, name = tempfile.mkstemp(prefix='.pending-', dir=target.parent)
        staged = Path(name)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Hard-link publication is atomic and fails if the hash name exists.
        # Failed publication keeps staged bytes for explicit recovery.
        try:
            os.link(staged, target)
        except FileExistsError:
            self.verify(digest)
        self.verify(digest)
        staged.unlink()  # successful publication retains the identical bytes
        return digest


def blob_references(store, *, after_sequence=0, limit=64) -> dict:
    """Page every persisted Evidence reference, including withdrawn history.

    Missing files remain visible through the database, unlike directory scans.
    Sequence is the existing indexed primary key; pages are not one snapshot.
    """
    if type(after_sequence) is not int or not 0 <= after_sequence <= 9223372036854775807:
        raise ValueError('Invalid reference sequence')
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError('Reference page limit must be between 1 and 64')
    rows = store.connection.execute(
        'SELECT sequence,blob_hash FROM evidence WHERE sequence>? ORDER BY sequence LIMIT ?',
        (after_sequence, limit + 1)).fetchall()
    if any(not isinstance(digest, str) or DIGEST.fullmatch(digest) is None for _, digest in rows):
        raise EvidenceCorrupt('Invalid content identity in reference page')
    page = rows[:limit]
    return {'mode': 'READ_ONLY', 'consistency': 'LIVE_KEYSET',
            'references': [{'sequence': seq, 'digest': digest} for seq, digest in page],
            'next_after_sequence': page[-1][0] if len(rows) > limit else None,
            'rows_read': len(rows), 'limit': limit, 'includes_withdrawn_history': True,
            'content_verified': False, 'reuse_authorized': False, 'cleanup_authorized': False}


def inventory_blobs(blobs: BlobStore, *, prefix=None, entry_budget=1000) -> dict:
    """Bounded metadata-only discovery of the two-level blob layout.

    No untrusted entry name is returned. Known identities can be passed to
    inspect_blobs; pending/unknown entries are counted, never removed.
    """
    if prefix is not None and (not isinstance(prefix, str) or re.fullmatch('[a-f0-9]{2}', prefix) is None):
        raise ValueError('Prefix must be two lowercase hexadecimal characters')
    if type(entry_budget) is not int or not 1 <= entry_budget <= 10000:
        raise ValueError('Entry budget must be between 1 and 10000')
    counts = {'pending_files': 0, 'unknown_entries': 0, 'unsafe_entries': 0, 'unreadable_scopes': 0}
    digests = []
    seen = 0
    limited = False

    def walk(directory, shard):
        nonlocal seen, limited
        try:
            _regular_path(directory)
            with os.scandir(directory) as entries:
                for entry in entries:
                    seen += 1
                    if seen > entry_budget:
                        limited = True
                        return
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                        counts['unsafe_entries'] += 1
                    elif shard is None and stat.S_ISDIR(info.st_mode) and re.fullmatch('[a-f0-9]{2}', entry.name):
                        walk(Path(entry.path), entry.name)
                        if limited:
                            return
                    elif shard is not None and stat.S_ISREG(info.st_mode):
                        if DIGEST.fullmatch(entry.name) and entry.name.startswith(shard):
                            digests.append(entry.name)
                        elif entry.name.startswith('.pending-'):
                            counts['pending_files'] += 1
                        else:
                            counts['unknown_entries'] += 1
                    else:
                        counts['unknown_entries'] += 1
        except EvidenceCorrupt:
            counts['unsafe_entries'] += 1
        except OSError:
            counts['unreadable_scopes'] += 1

    walk(blobs.root if prefix is None else blobs.root / prefix, prefix)
    return {'mode': 'READ_ONLY', 'scope': 'BLOB_ROOT' if prefix is None else 'BLOB_SHARD',
            'prefix': prefix, 'digests': sorted(digests), **counts, 'entries_observed': seen,
            'entry_budget': entry_budget, 'budget_exhausted': limited,
            'enumeration_complete': not limited and not counts['unsafe_entries'] and not counts['unreadable_scopes'],
            'filesystem_snapshot_atomic': False, 'content_verified': False,
            'references_examined': False, 'managed_files_examined': False,
            'cleanup_authorized': False}


def inspect_blobs(store, blobs: BlobStore, *, digests, reference_budget=1000,
                  max_bytes=1024 * 1024) -> dict:
    """Inspect explicit content identities against one bounded DB reference view.

    An unreferenced blob may still be between publication and registration.
    Neither this observation nor a complete reference scan authorizes removal.
    Protected managed files and unpublished staging names are different stores.
    """
    if (not isinstance(digests, list) or not 1 <= len(digests) <= 64
            or any(not isinstance(d, str) or DIGEST.fullmatch(d) is None for d in digests)
            or len(set(digests)) != len(digests)):
        raise ValueError('Supply 1 to 64 distinct lowercase content identities')
    if type(reference_budget) is not int or not 1 <= reference_budget <= 10000:
        raise ValueError('Reference budget must be between 1 and 10000')
    if type(max_bytes) is not int or not 0 <= max_bytes <= 64 * 1024 * 1024:
        raise ValueError('Byte budget must be between 0 and 67108864')
    if blobs.root != (store.path.parent / 'blobs').absolute():
        raise ValueError('Blob root must belong to the selected state store')
    c = store.connection
    own_transaction = not c.in_transaction
    if own_transaction:
        c.execute('BEGIN')
    try:
        rows = c.execute('SELECT blob_hash FROM evidence ORDER BY sequence LIMIT ?',
                         (reference_budget + 1,)).fetchall()
        complete = len(rows) <= reference_budget
        references = {row[0] for row in rows[:reference_budget]}
        if any(not isinstance(d, str) or DIGEST.fullmatch(d) is None for d in references):
            raise EvidenceCorrupt('Invalid content identity in reference snapshot')
    finally:
        if own_transaction:
            c.execute('ROLLBACK')
    # Release the read transaction before filesystem I/O. Its reference view
    # does not claim an atomic snapshot of subsequent file observations.
    used = 0
    results = []
    for digest in digests:
        reference = ('REFERENCED' if digest in references else
                     'UNREFERENCED_CANDIDATE' if complete else 'UNKNOWN_REFERENCE_COVERAGE')
        try:
            data = blobs.read(digest, max_bytes=max_bytes - used)
            used += len(data)
            integrity = 'VALID'
            del data
        except EvidenceReadLimit as error:
            used += error.bytes_read
            integrity = 'NOT_CHECKED_BYTE_BUDGET'
        except FileNotFoundError:
            integrity = 'MISSING'
        except EvidenceCorrupt as error:
            used += error.bytes_read
            integrity = 'INVALID_BYTES_OR_PATH'
        except OSError:
            integrity = 'UNREADABLE'
        results.append({'digest': digest, 'reference': reference, 'integrity': integrity})
        # read() may consume one sentinel byte if a file grows during reading.
        if used > max_bytes:
            # Preserve accounting without supplying a negative read budget.
            for pending in digests[len(results):]:
                ref = ('REFERENCED' if pending in references else
                       'UNREFERENCED_CANDIDATE' if complete else 'UNKNOWN_REFERENCE_COVERAGE')
                results.append({'digest': pending, 'reference': ref,
                                'integrity': 'NOT_CHECKED_BYTE_BUDGET'})
            break
    return {'mode': 'READ_ONLY', 'scope': 'EXPLICIT_DIGESTS_ONLY', 'results': results,
            'reference_scan_complete': complete, 'reference_rows_read': len(rows),
            'reference_budget': reference_budget, 'bytes_read': used, 'max_bytes': max_bytes,
            'filesystem_snapshot_atomic': False, 'inventory_complete': False,
            'staging_and_managed_files_examined': False, 'cleanup_authorized': False,
            'unreferenced_may_be_publication_in_progress': True}
