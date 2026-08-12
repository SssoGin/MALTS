#!/usr/bin/env python3
"""Recoverable workspace-scoped transactions for MALTS control mutations."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SHORT_TEMP_NAME = re.compile(r"^\.m-[a-z0-9_]{8}\.tmp$")
PENDING_STATUSES = {"IN_PROGRESS", "RECOVERY_IN_PROGRESS", "RECOVERY_REQUIRED"}


@dataclass(frozen=True)
class TransactionProfile:
    domain: str
    code_prefix: str
    lock_relative: Path
    journal_directory_relative: Path


ARTIFACT_TRANSACTION_PROFILE = TransactionProfile(
    domain="Artifact",
    code_prefix="ART_TRANSACTION",
    lock_relative=Path("runtime") / "artifact_transaction.lock.json",
    journal_directory_relative=Path("runtime") / "artifact_transactions",
)
WORKSPACE_TRANSACTION_PROFILE = TransactionProfile(
    domain="Workspace-control",
    code_prefix="WS_TRANSACTION",
    lock_relative=Path("runtime") / "workspace_transaction.lock.json",
    journal_directory_relative=Path("runtime") / "workspace_transactions",
)


def _code(profile: TransactionProfile, suffix: str) -> str:
    return f"{profile.code_prefix}_{suffix}"


class TransactionError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _inside(root: Path, path: Path, profile: TransactionProfile = ARTIFACT_TRANSACTION_PROFILE) -> Path:
    root = root.resolve(strict=True)
    try:
        resolved = path.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise TransactionError(_code(profile, "PATH_ESCAPE"), "Transaction target escapes the workspace boundary.", str(path)) from exc
    return resolved


def _io_path(path: Path) -> Path:
    """Return an explicit extended-length Windows path for filesystem I/O."""
    if os.name != "nt" or not path.is_absolute():
        return path
    value = str(path)
    if value.startswith("\\\\?\\"):
        return path
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


def _current_hash(path: Path, profile: TransactionProfile = ARTIFACT_TRANSACTION_PROFILE) -> str | None:
    io_path = _io_path(path)
    if not io_path.exists():
        return None
    if not io_path.is_file():
        raise TransactionError(_code(profile, "TARGET_TYPE"), "Transaction targets must be regular files.", str(path))
    return sha256_bytes(io_path.read_bytes())


def _write_new_file(path: Path, payload: bytes) -> None:
    with _io_path(path).open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _write_temporary_file(parent: Path, payload: bytes) -> Path:
    descriptor, raw_path = tempfile.mkstemp(prefix=".m-", suffix=".tmp", dir=str(_io_path(parent)))
    temporary = parent / Path(raw_path).name
    stream = None
    try:
        stream = os.fdopen(descriptor, "wb")
        descriptor = -1
        with stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        io_temporary = _io_path(temporary)
        if io_temporary.exists():
            io_temporary.unlink()
        raise
    return temporary


def _atomic_bytes(path: Path, payload: bytes) -> None:
    # Keep the same-directory temporary basename bounded. Target and operation
    # identity live in the journal; repeating them here can exceed MAX_PATH.
    temporary = _write_temporary_file(path.parent, payload)
    try:
        os.replace(_io_path(temporary), _io_path(path))
    finally:
        io_temporary = _io_path(temporary)
        if io_temporary.exists():
            io_temporary.unlink()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    _io_path(path.parent).mkdir(parents=True, exist_ok=True)
    _atomic_bytes(path, _json_bytes(dict(value)))


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(_io_path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransactionError(code, "Transaction control JSON is unreadable.", str(path)) from exc
    if not isinstance(value, dict):
        raise TransactionError(code, "Transaction control JSON must be an object.", str(path))
    return value


def _created_parent_directories(root: Path, targets: list[Path]) -> list[Path]:
    missing: set[Path] = set()
    for target in targets:
        current = target.parent
        while current != root and not _io_path(current).exists():
            missing.add(current)
            current = current.parent
    for directory in sorted(missing, key=lambda item: len(item.parts)):
        _io_path(directory).mkdir()
    return sorted(missing, key=lambda item: len(item.parts), reverse=True)


def _cleanup_empty_directories(directories: list[Path]) -> None:
    for directory in directories:
        try:
            _io_path(directory).rmdir()
        except OSError:
            pass


def _completed_retry(
    root: Path,
    journal: Mapping[str, Any],
    operation: str,
    changes: Mapping[Path, bytes],
    expected_input_hashes: Mapping[Path, str | None],
    profile: TransactionProfile,
) -> dict[str, Any] | None:
    if journal.get("status") != "COMMITTED":
        return None
    if journal.get("operation") != operation:
        raise TransactionError(_code(profile, "RETRY_DRIFT"), "Operation ID was already committed for a different operation.")
    recorded = journal.get("planned_outputs")
    if not isinstance(recorded, list):
        raise TransactionError(_code(profile, "JOURNAL_INVALID"), "Committed journal lacks planned outputs.")
    expected_outputs = {_relative(root, path): sha256_bytes(payload) for path, payload in changes.items()}
    recorded_outputs = {
        item.get("path"): item.get("sha256")
        for item in recorded
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    if expected_outputs != recorded_outputs:
        raise TransactionError(_code(profile, "RETRY_DRIFT"), "Operation ID was already committed with different planned bytes.")
    recorded_inputs = {
        item.get("path"): item.get("sha256")
        for item in journal.get("inputs", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    requested_inputs = {_relative(root, path): expected for path, expected in expected_input_hashes.items()}
    if recorded_inputs != requested_inputs:
        raise TransactionError(_code(profile, "RETRY_DRIFT"), "Operation ID was already committed with different input preconditions.")
    observed = {_relative(root, path): _current_hash(path, profile) for path in changes}
    if observed != expected_outputs:
        raise TransactionError(_code(profile, "RETRY_DRIFT"), "Committed transaction outputs no longer match the journal.", observed)
    target_paths = set(expected_outputs)
    for item in journal.get("inputs", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or item["path"] in target_paths:
            continue
        input_path = _inside(root, root / Path(item["path"]), profile)
        observed_input = _current_hash(input_path, profile)
        if observed_input != item.get("sha256"):
            raise TransactionError(
                _code(profile, "RETRY_DRIFT"),
                "A read-only transaction precondition changed after the committed operation.",
                {"path": item["path"], "expected": item.get("sha256"), "observed": observed_input},
            )
    return {
        "operation_id": journal.get("operation_id"),
        "journal_path": str(journal.get("journal_path", "N/A")),
        "status": "COMMITTED",
        "idempotent": True,
        "writes_performed": False,
        "replacement_count": 0,
        "lock_released": True,
    }


def _rolled_back_retry_is_safe(
    root: Path,
    journal: Mapping[str, Any],
    operation: str,
    changes: Mapping[Path, bytes],
    expected_input_hashes: Mapping[Path, str | None],
    profile: TransactionProfile,
) -> bool:
    if journal.get("status") != "ROLLED_BACK":
        return False
    if journal.get("operation") != operation:
        raise TransactionError(_code(profile, "RETRY_DRIFT"), "Operation ID was rolled back for a different operation.")
    planned_outputs = {
        item.get("path"): item.get("sha256")
        for item in journal.get("planned_outputs", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    requested_outputs = {_relative(root, path): sha256_bytes(payload) for path, payload in changes.items()}
    recorded_inputs = {
        item.get("path"): item.get("sha256")
        for item in journal.get("inputs", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    requested_inputs = {_relative(root, path): expected for path, expected in expected_input_hashes.items()}
    observed_inputs = {_relative(root, path): _current_hash(path, profile) for path in expected_input_hashes}
    if planned_outputs != requested_outputs or recorded_inputs != requested_inputs or observed_inputs != requested_inputs:
        raise TransactionError(
            _code(profile, "RETRY_DRIFT"),
            "Rolled-back operation cannot be retried because input or output bytes differ from its journal.",
            {"recorded_inputs": recorded_inputs, "requested_inputs": requested_inputs, "observed_inputs": observed_inputs},
        )
    return True


def execute_transaction(
    root: Path,
    *,
    operation_id: str,
    operation: str,
    changes: Mapping[Path, bytes],
    expected_input_hashes: Mapping[Path, str | None],
    post_validate: Callable[[], None] | None = None,
    fail_after_replacements: int | None = None,
    crash_after_replacements: int | None = None,
    profile: TransactionProfile = ARTIFACT_TRANSACTION_PROFILE,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if not OPERATION_ID.fullmatch(operation_id):
        raise TransactionError(_code(profile, "ID_INVALID"), "Operation ID contains unsupported characters.", operation_id)
    if not changes:
        return {
            "operation_id": operation_id,
            "journal_path": None,
            "status": "NO_CHANGES",
            "idempotent": True,
            "writes_performed": False,
            "replacement_count": 0,
            "lock_released": True,
        }
    normalized_changes: dict[Path, bytes] = {}
    normalized_preconditions: dict[Path, str | None] = {}
    for raw_path, expected in expected_input_hashes.items():
        path = _inside(root, Path(raw_path), profile)
        if path in normalized_preconditions:
            raise TransactionError(_code(profile, "PRECONDITION_DUPLICATE"), "Transaction precondition appears more than once.", str(path))
        normalized_preconditions[path] = expected
    for raw_path, payload in changes.items():
        path = _inside(root, Path(raw_path), profile)
        if path in normalized_changes:
            raise TransactionError(_code(profile, "TARGET_DUPLICATE"), "Transaction target appears more than once.", str(path))
        if path not in normalized_preconditions:
            raise TransactionError(_code(profile, "PRECONDITION_MISSING"), "Every target requires an expected input hash.", str(path))
        normalized_changes[path] = bytes(payload)

    lock_path = _inside(root, root / profile.lock_relative, profile)
    journal_directory = _inside(root, root / profile.journal_directory_relative, profile)
    journal_path = _inside(root, journal_directory / f"{operation_id}.json", profile)
    if _io_path(lock_path).exists():
        lock_value: dict[str, Any] | None = None
        try:
            lock_value = _read_json(lock_path, _code(profile, "LOCK_INVALID"))
        except TransactionError:
            pass
        raise TransactionError(
            _code(profile, "LOCKED"),
            f"Another or stale {profile.domain} transaction lock exists; it is not deleted automatically.",
            {"path": _relative(root, lock_path), "lock": lock_value},
        )
    prior_journal: dict[str, Any] | None = None
    if _io_path(journal_path).exists():
        journal_value = _read_json(journal_path, _code(profile, "JOURNAL_INVALID"))
        completed = _completed_retry(root, journal_value, operation, normalized_changes, normalized_preconditions, profile)
        if completed is not None:
            completed["journal_path"] = _relative(root, journal_path)
            return completed
        if _rolled_back_retry_is_safe(root, journal_value, operation, normalized_changes, normalized_preconditions, profile):
            prior_journal = journal_value
        else:
            raise TransactionError(
                _code(profile, "JOURNAL_REVIEW_REQUIRED"),
                "Operation journal already exists and is not a safe committed or rolled-back retry; manual review is required.",
                {"path": _relative(root, journal_path), "status": journal_value.get("status")},
            )

    _io_path(lock_path.parent).mkdir(parents=True, exist_ok=True)
    lock_value = {
        "contract_version": 1,
        "operation_id": operation_id,
        "operation": operation,
        "created_at": _timestamp(),
        "process_id": os.getpid(),
        "status": "ACTIVE",
        "targets": sorted(_relative(root, path) for path in normalized_changes),
        "inputs": sorted(_relative(root, path) for path in normalized_preconditions),
    }
    try:
        _write_new_file(lock_path, _json_bytes(lock_value))
    except FileExistsError as exc:
        raise TransactionError(_code(profile, "LOCKED"), f"Another {profile.domain} transaction acquired the workspace lock.", _relative(root, lock_path)) from exc

    originals: dict[Path, bytes | None] = {}
    staged: dict[Path, Path] = {}
    replaced: list[Path] = []
    created_directories: list[Path] = []
    journal: dict[str, Any] | None = None
    rollback_succeeded = False
    try:
        for path, expected in normalized_preconditions.items():
            observed = _current_hash(path, profile)
            if observed != expected:
                raise TransactionError(
                    _code(profile, "PRECONDITION_DRIFT"),
                    "Canonical input changed after planning and lock acquisition.",
                    {"path": _relative(root, path), "expected": expected, "observed": observed},
                )
            if path in normalized_changes:
                io_path = _io_path(path)
                originals[path] = io_path.read_bytes() if io_path.exists() else None

        _io_path(journal_directory).mkdir(parents=True, exist_ok=True)
        journal = {
            "contract_version": 1,
            "operation_id": operation_id,
            "operation": operation,
            "created_at": lock_value["created_at"],
            "status": "IN_PROGRESS",
            "attempt": int(prior_journal.get("attempt", 1)) + 1 if prior_journal is not None else 1,
            "attempt_history": (
                list(prior_journal.get("attempt_history", []))
                + [
                    {
                        "attempt": prior_journal.get("attempt", 1),
                        "status": prior_journal.get("status"),
                        "failed_at": prior_journal.get("failed_at"),
                        "failure": prior_journal.get("failure"),
                    }
                ]
                if prior_journal is not None
                else []
            ),
            "journal_path": _relative(root, journal_path),
            "lock_path": _relative(root, lock_path),
            "targets": sorted(_relative(root, path) for path in normalized_changes),
            "inputs": [
                {
                    "path": _relative(root, path),
                    "sha256": normalized_preconditions[path],
                    "changed": path in normalized_changes,
                    "existed": _io_path(path).exists(),
                    "original_base64": (
                        base64.b64encode(originals[path]).decode("ascii")
                        if path in originals and originals[path] is not None
                        else None
                    ),
                }
                for path in sorted(normalized_preconditions, key=lambda item: _relative(root, item))
            ],
            "planned_outputs": [
                {"path": _relative(root, path), "sha256": sha256_bytes(normalized_changes[path]), "bytes": len(normalized_changes[path])}
                for path in sorted(normalized_changes, key=lambda item: _relative(root, item))
            ],
        }
        _atomic_json(journal_path, journal)

        created_directories = _created_parent_directories(root, list(normalized_changes))
        for path, payload in normalized_changes.items():
            temporary = _write_temporary_file(path.parent, payload)
            staged[path] = temporary
        if profile is WORKSPACE_TRANSACTION_PROFILE:
            journal["staged_files"] = sorted(_relative(root, path) for path in staged.values())
            _atomic_json(journal_path, journal)
        for path in normalized_changes:
            os.replace(_io_path(staged[path]), _io_path(path))
            replaced.append(path)
            if fail_after_replacements is not None and len(replaced) == fail_after_replacements:
                raise TransactionError(
                    _code(profile, "INJECTED_FAILURE"),
                    "Injected failure after an exact replacement boundary.",
                    {"replacement_count": len(replaced)},
                )
            if crash_after_replacements is not None and len(replaced) == crash_after_replacements:
                os._exit(91)
        if post_validate is not None:
            post_validate()
        journal["status"] = "COMMITTED"
        journal["completed_at"] = _timestamp()
        journal["observed_outputs"] = [
            {"path": _relative(root, path), "sha256": _current_hash(path, profile)}
            for path in sorted(normalized_changes, key=lambda item: _relative(root, item))
        ]
        _atomic_json(journal_path, journal)
        current_lock = _read_json(lock_path, _code(profile, "LOCK_INVALID"))
        if current_lock.get("operation_id") != operation_id:
            raise TransactionError(_code(profile, "LOCK_DRIFT"), "Workspace transaction lock ownership changed unexpectedly.")
        _io_path(lock_path).unlink()
        return {
            "operation_id": operation_id,
            "journal_path": _relative(root, journal_path),
            "status": "COMMITTED",
            "idempotent": False,
            "writes_performed": True,
            "replacement_count": len(replaced),
            "lock_released": True,
        }
    except Exception as exc:
        rollback_error: Exception | None = None
        try:
            for path in reversed(replaced):
                original = originals[path]
                if original is None:
                    io_path = _io_path(path)
                    if io_path.exists():
                        io_path.unlink()
                else:
                    _atomic_bytes(path, original)
            rollback_succeeded = True
        except Exception as caught:
            rollback_error = caught
        finally:
            for temporary in staged.values():
                io_temporary = _io_path(temporary)
                if io_temporary.exists():
                    io_temporary.unlink()
            _cleanup_empty_directories(created_directories)
        if journal is not None:
            journal["status"] = "ROLLED_BACK" if rollback_succeeded else "RECOVERY_REQUIRED"
            journal["failed_at"] = _timestamp()
            journal["failure"] = {"type": type(exc).__name__, "message": str(exc)}
            if rollback_error is not None:
                journal["rollback_failure"] = {"type": type(rollback_error).__name__, "message": str(rollback_error)}
            _atomic_json(journal_path, journal)
        if rollback_succeeded and _io_path(lock_path).exists():
            current_lock = _read_json(lock_path, _code(profile, "LOCK_INVALID"))
            if current_lock.get("operation_id") == operation_id:
                _io_path(lock_path).unlink()
        if rollback_error is not None:
            raise TransactionError(
                _code(profile, "RECOVERY_REQUIRED"),
                f"{profile.domain} transaction rollback failed; persisted recovery evidence and lock were retained.",
                {
                    "operation_id": operation_id,
                    "journal_path": _relative(root, journal_path),
                    "failure": {"type": type(exc).__name__, "message": str(exc)},
                    "rollback_failure": {"type": type(rollback_error).__name__, "message": str(rollback_error)},
                },
            ) from exc
        if isinstance(exc, TransactionError):
            raise
        raise TransactionError(_code(profile, "FAILED"), f"{profile.domain} transaction failed.", {"type": type(exc).__name__, "message": str(exc)}) from exc


def recover_transaction(
    root: Path,
    *,
    operation_id: str,
    expected_journal_sha256: str,
    apply: bool = False,
    profile: TransactionProfile = ARTIFACT_TRANSACTION_PROFILE,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if not OPERATION_ID.fullmatch(operation_id):
        raise TransactionError(_code(profile, "ID_INVALID"), "Operation ID contains unsupported characters.", operation_id)
    expected_journal = expected_journal_sha256.upper()
    if re.fullmatch(r"[A-F0-9]{64}", expected_journal) is None:
        raise TransactionError(_code(profile, "JOURNAL_HASH_INVALID"), "Expected journal hash must be an exact SHA-256.")
    journal_path = _inside(root, root / profile.journal_directory_relative / f"{operation_id}.json", profile)
    lock_path = _inside(root, root / profile.lock_relative, profile)
    if not _io_path(journal_path).is_file():
        raise TransactionError(_code(profile, "JOURNAL_MISSING"), "Transaction recovery journal is missing.", _relative(root, journal_path))
    journal_payload = _io_path(journal_path).read_bytes()
    observed_journal = sha256_bytes(journal_payload)
    if observed_journal != expected_journal:
        raise TransactionError(
            _code(profile, "JOURNAL_HASH_DRIFT"),
            "Transaction journal changed after recovery review.",
            {"expected": expected_journal, "observed": observed_journal},
        )
    journal = _read_json(journal_path, _code(profile, "JOURNAL_INVALID"))
    if journal.get("operation_id") != operation_id or journal.get("status") not in PENDING_STATUSES:
        raise TransactionError(
            _code(profile, "RECOVERY_STATE_INVALID"),
            "Only a matching incomplete transaction journal can be recovered.",
            {"status": journal.get("status"), "operation_id": journal.get("operation_id")},
        )
    if not _io_path(lock_path).is_file():
        raise TransactionError(_code(profile, "LOCK_MISSING"), "Incomplete transaction recovery requires its exact lock file.", _relative(root, lock_path))
    lock = _read_json(lock_path, _code(profile, "LOCK_INVALID"))
    if lock.get("operation_id") != operation_id:
        raise TransactionError(_code(profile, "LOCK_DRIFT"), "Transaction lock belongs to another operation.", lock)
    planned_outputs = {
        item.get("path"): item.get("sha256")
        for item in journal.get("planned_outputs", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    recovery_rows: list[dict[str, Any]] = []
    originals: dict[Path, bytes | None] = {}
    for item in journal.get("inputs", []):
        if not isinstance(item, dict) or item.get("changed") is not True or not isinstance(item.get("path"), str):
            continue
        relative = item["path"]
        path = _inside(root, root / Path(relative), profile)
        original_hash = item.get("sha256")
        planned_hash = planned_outputs.get(relative)
        if planned_hash is None:
            raise TransactionError(_code(profile, "JOURNAL_INVALID"), "Changed journal input lacks a planned output.", relative)
        observed = _current_hash(path, profile)
        if observed not in {original_hash, planned_hash}:
            raise TransactionError(
                _code(profile, "RECOVERY_TARGET_DRIFT"),
                "Recovery target matches neither reviewed original nor planned output bytes.",
                {"path": relative, "original": original_hash, "planned": planned_hash, "observed": observed},
            )
        original_base64 = item.get("original_base64")
        if original_hash is None:
            if original_base64 is not None:
                raise TransactionError(_code(profile, "JOURNAL_INVALID"), "New target unexpectedly contains original bytes.", relative)
            original = None
        else:
            if not isinstance(original_base64, str):
                raise TransactionError(_code(profile, "JOURNAL_INVALID"), "Existing target lacks original bytes.", relative)
            try:
                original = base64.b64decode(original_base64, validate=True)
            except ValueError as exc:
                raise TransactionError(_code(profile, "JOURNAL_INVALID"), "Original bytes are not valid base64.", relative) from exc
            if sha256_bytes(original) != original_hash:
                raise TransactionError(_code(profile, "JOURNAL_INVALID"), "Original bytes do not match their recorded hash.", relative)
        originals[path] = original
        recovery_rows.append({"path": relative, "observed": observed, "restore_sha256": original_hash})
    if not recovery_rows:
        raise TransactionError(_code(profile, "JOURNAL_INVALID"), "Incomplete journal has no changed targets to recover.")
    result = {
        "operation_id": operation_id,
        "journal_path": _relative(root, journal_path),
        "mode": "APPLY" if apply else "DRY_RUN",
        "status": "RECOVERY_PLANNED" if not apply else "ROLLED_BACK",
        "planned_restores": recovery_rows,
        "writes_performed": False,
        "lock_released": False,
    }
    if not apply:
        return result
    journal["status"] = "RECOVERY_IN_PROGRESS"
    journal["recovery_started_at"] = _timestamp()
    _atomic_json(journal_path, journal)
    try:
        for path, original in originals.items():
            if original is None:
                io_path = _io_path(path)
                if io_path.exists():
                    io_path.unlink()
            else:
                _atomic_bytes(path, original)
        staged_values = journal.get("staged_files", [])
        if not isinstance(staged_values, list) or len(staged_values) > len(originals):
            raise TransactionError(_code(profile, "JOURNAL_INVALID"), "Staged file registry cardinality is invalid.")
        allowed_stage_parents = {path.parent for path in originals}
        observed_staged: set[Path] = set()
        for relative in staged_values:
            if not isinstance(relative, str):
                raise TransactionError(_code(profile, "JOURNAL_INVALID"), "Staged file locator is invalid.")
            staged = _inside(root, root / Path(relative), profile)
            legacy_name = f".malts-stage-{operation_id}-" in staged.name
            if staged.parent not in allowed_stage_parents or (not SHORT_TEMP_NAME.fullmatch(staged.name) and not legacy_name):
                raise TransactionError(_code(profile, "JOURNAL_INVALID"), "Staged file is outside the reviewed temporary-file contract.", relative)
            if staged in observed_staged:
                raise TransactionError(_code(profile, "JOURNAL_INVALID"), "Staged file locator is duplicated.", relative)
            observed_staged.add(staged)
            io_staged = _io_path(staged)
            if io_staged.exists():
                if not io_staged.is_file():
                    raise TransactionError(_code(profile, "RECOVERY_TARGET_DRIFT"), "Staged recovery target is not a regular file.", relative)
                io_staged.unlink()
        journal["status"] = "ROLLED_BACK"
        journal["recovered_at"] = _timestamp()
        journal["recovery_result"] = "EXACT_ORIGINALS_RESTORED"
        _atomic_json(journal_path, journal)
        current_lock = _read_json(lock_path, _code(profile, "LOCK_INVALID"))
        if current_lock.get("operation_id") != operation_id:
            raise TransactionError(_code(profile, "LOCK_DRIFT"), "Transaction lock ownership changed during recovery.")
        _io_path(lock_path).unlink()
    except Exception as exc:
        journal["status"] = "RECOVERY_REQUIRED"
        journal["recovery_failed_at"] = _timestamp()
        journal["recovery_failure"] = {"type": type(exc).__name__, "message": str(exc)}
        _atomic_json(journal_path, journal)
        if isinstance(exc, TransactionError):
            raise
        raise TransactionError(_code(profile, "RECOVERY_FAILED"), "Transaction recovery failed and evidence was preserved.", str(exc)) from exc
    result["writes_performed"] = True
    result["lock_released"] = True
    return result


def inspect_transaction_state(
    root: Path,
    profile: TransactionProfile = ARTIFACT_TRANSACTION_PROFILE,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    findings: list[dict[str, Any]] = []
    try:
        lock_path = _inside(root, root / profile.lock_relative, profile)
        journal_directory = _inside(root, root / profile.journal_directory_relative, profile)
    except TransactionError as exc:
        findings.append(
            {
                "code": _code(profile, "RUNTIME_ESCAPE"),
                "path": "runtime",
                "message": "Artifact transaction control path resolves outside the workspace and was not read.",
                "detail": {"error": exc.message},
            }
        )
        return {
            "status": "REVIEW_REQUIRED",
            "findings": findings,
            "required_actions": ["Review runtime path/reparse ownership without deleting or traversing it automatically."],
            "writes_performed": False,
            "recursive_scan_performed": False,
        }
    if _io_path(lock_path).exists():
        detail: Any
        try:
            detail = _read_json(lock_path, _code(profile, "LOCK_INVALID"))
        except TransactionError as exc:
            detail = {"error": exc.message}
        findings.append(
            {
                "code": _code(profile, "LOCK_REVIEW_REQUIRED"),
                "path": profile.lock_relative.as_posix(),
                "message": f"{profile.domain} transaction lock exists and is never auto-deleted.",
                "detail": detail,
            }
        )
    if _io_path(journal_directory).is_dir():
        with os.scandir(_io_path(journal_directory)) as entries:
            journal_names = sorted(
                (entry.name for entry in entries if entry.name.casefold().endswith(".json")),
                key=str.casefold,
            )
        for journal_name in journal_names:
            raw_journal_path = journal_directory / journal_name
            try:
                journal_path = _inside(root, raw_journal_path, profile)
            except TransactionError:
                findings.append(
                    {
                        "code": _code(profile, "JOURNAL_ESCAPE"),
                        "path": raw_journal_path.relative_to(root).as_posix(),
                        "message": "Transaction journal resolves outside the workspace and was not read.",
                        "detail": {"status": "UNREAD"},
                    }
                )
                continue
            try:
                value = _read_json(journal_path, _code(profile, "JOURNAL_INVALID"))
                status = value.get("status")
            except TransactionError as exc:
                value = {"error": exc.message}
                status = "INVALID"
            if status in PENDING_STATUSES or status == "INVALID":
                findings.append(
                    {
                        "code": _code(profile, "JOURNAL_REVIEW_REQUIRED"),
                        "path": _relative(root, journal_path),
                        "message": f"Incomplete or invalid {profile.domain} transaction journal requires exact manual review.",
                        "detail": {"status": status, "operation_id": value.get("operation_id")},
                    }
                )
    required_actions = [f"Review {item['path']} without deleting it automatically." for item in findings]
    return {
        "status": "REVIEW_REQUIRED" if findings else "PASS",
        "findings": findings,
        "required_actions": required_actions,
        "writes_performed": False,
        "recursive_scan_performed": False,
    }
