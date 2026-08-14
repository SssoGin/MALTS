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
PENDING_STATUSES = {
    "PREPARED",
    "IN_PROGRESS",
    "ROLLING_BACK",
    "RECOVERY_IN_PROGRESS",
    "RECOVERY_REQUIRED",
}
WORKSPACE_JOURNAL_STATES = {
    "PREPARED",
    "IN_PROGRESS",
    "ROLLING_BACK",
    "ROLLED_BACK",
    "RECOVERY_REQUIRED",
    "COMMITTED",
}
WORKSPACE_ROLE_ORDER = {
    "IMMUTABLE_RECORD": 1,
    "RESULT_PROJECTION": 2,
    "SESSION_CONTROL": 3,
    "PHASE_CONTROL": 4,
    "REPORT": 5,
    "HANDOFF": 6,
    "PROJECT_CONTROL": 7,
    "RUNTIME_STATE": 8,
}
WORKSPACE_COMMAND_VERSION = "1.3.0"


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


def _execute_legacy_transaction(
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


def _recover_legacy_transaction(
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


def _inspect_legacy_transaction_state(
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


def _workspace_id(root: Path) -> str:
    state_path = root / "runtime" / "workspace_control.json"
    if _io_path(state_path).is_file():
        value = _read_json(state_path, "WS_TRANSACTION_WORKSPACE_ID_INVALID")
        project_id = value.get("project_id")
        if isinstance(project_id, str) and project_id:
            return project_id
    return f"WS-{sha256_bytes(str(root).casefold().encode('utf-8'))[:24]}"


def _invariant_source_sha256() -> str:
    path = Path(__file__).resolve().parent / "lifecycle_invariants.json"
    if not path.is_file():
        raise TransactionError(
            "WS_TRANSACTION_INVARIANT_SOURCE_MISSING",
            "The canonical lifecycle invariant source is missing.",
            str(path),
        )
    return sha256_bytes(path.read_bytes())


def _normalize_expected_hash(value: str | None) -> str | None:
    if value is None or value == "ABSENT":
        return None
    normalized = str(value).upper()
    if re.fullmatch(r"[A-F0-9]{64}", normalized) is None:
        raise TransactionError(
            "WS_TRANSACTION_PLAN_INVALID",
            "Expected preimages must be an exact SHA-256 or ABSENT.",
            value,
        )
    return normalized


def _infer_workspace_role(root: Path, path: Path) -> str:
    relative = _relative(root, path)
    name = path.name.upper()
    parts = {item.casefold() for item in Path(relative).parts}
    if name in {"RESULT_LINEAGE.JSON", "RESULT_LINEAGE_PROJECTION.JSON"}:
        return "RESULT_PROJECTION"
    if name == "SESSION_CONTROL.MD":
        return "SESSION_CONTROL"
    if name == "PHASE_CONTROL.MD":
        return "PHASE_CONTROL"
    if name == "WORK_TASK_REPORT.MD":
        return "REPORT"
    if name == "PROJECT_HANDOFF.MD":
        return "HANDOFF"
    if name == "PROJECT_CONTROL.MD":
        return "PROJECT_CONTROL"
    if relative.casefold().startswith("runtime/"):
        return "RUNTIME_STATE"
    if "events" in parts or "revisions" in parts or "boundary_revisions" in parts:
        return "IMMUTABLE_RECORD"
    return "IMMUTABLE_RECORD"


def _workspace_locator(root: Path, raw_path: Path | str) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise TransactionError("WS_TRANSACTION_PATH_ESCAPE", "Workspace transaction locator escapes the workspace.", str(raw_path)) from exc
    current = root
    for component in relative.parts:
        current /= component
        io_current = _io_path(current)
        if not io_current.exists() and not io_current.is_symlink():
            continue
        metadata = os.lstat(io_current)
        attributes = int(getattr(metadata, "st_file_attributes", 0))
        if io_current.is_symlink() or attributes & 0x400:
            raise TransactionError("WS_TRANSACTION_REPARSE_TARGET", "Workspace transaction locators cannot traverse a reparse target.", _relative(root, current))
        if current == candidate and io_current.is_file() and int(getattr(metadata, "st_nlink", 1)) > 1:
            raise TransactionError("WS_TRANSACTION_HARDLINK_TARGET", "Workspace transaction targets cannot be hard-linked files.", _relative(root, current))
    return _inside(root, candidate, WORKSPACE_TRANSACTION_PROFILE)


def _normalize_workspace_inputs(
    root: Path,
    changes: Mapping[Path, bytes],
    expected_input_hashes: Mapping[Path, str | None],
    target_roles: Mapping[Path | str, str] | None,
) -> tuple[dict[Path, bytes], dict[Path, str | None], dict[Path, str]]:
    normalized_changes: dict[Path, bytes] = {}
    normalized_preconditions: dict[Path, str | None] = {}
    portable_preconditions: set[str] = set()
    for raw_path, expected in expected_input_hashes.items():
        path = _workspace_locator(root, raw_path)
        portable = _relative(root, path).casefold()
        if path in normalized_preconditions or portable in portable_preconditions:
            raise TransactionError("WS_TRANSACTION_PRECONDITION_DUPLICATE", "A transaction precondition appears more than once.", str(path))
        normalized_preconditions[path] = _normalize_expected_hash(expected)
        portable_preconditions.add(portable)
    portable_targets: set[str] = set()
    for raw_path, payload in changes.items():
        path = _workspace_locator(root, raw_path)
        portable = _relative(root, path).casefold()
        if path in normalized_changes or portable in portable_targets:
            raise TransactionError("WS_TRANSACTION_TARGET_DUPLICATE", "A transaction target appears more than once.", str(path))
        if path not in normalized_preconditions:
            raise TransactionError("WS_TRANSACTION_PRECONDITION_MISSING", "Every target requires an exact preimage or ABSENT.", str(path))
        normalized_changes[path] = bytes(payload)
        portable_targets.add(portable)
    role_rows: dict[Path, str] = {}
    supplied_roles: dict[Path, str] = {}
    for raw_path, role in (target_roles or {}).items():
        path = _workspace_locator(root, raw_path)
        supplied_roles[path] = str(role)
    unknown_paths = sorted(_relative(root, path) for path in supplied_roles if path not in normalized_changes)
    if unknown_paths:
        raise TransactionError("WS_TRANSACTION_ROLE_TARGET_UNKNOWN", "A target role names an undeclared output.", unknown_paths)
    for path in normalized_changes:
        role = supplied_roles.get(path, _infer_workspace_role(root, path))
        if role not in WORKSPACE_ROLE_ORDER:
            raise TransactionError("WS_TRANSACTION_ROLE_ORDER_INVALID", "Unknown workspace replacement role.", {"path": _relative(root, path), "role": role})
        role_rows[path] = role
    return normalized_changes, normalized_preconditions, role_rows


def plan_transaction(
    root: Path,
    *,
    operation_id: str,
    operation: str,
    changes: Mapping[Path, bytes],
    expected_input_hashes: Mapping[Path, str | None],
    target_roles: Mapping[Path | str, str] | None = None,
    workspace_id: str | None = None,
    invariant_source_sha256: str | None = None,
    command_version: str = WORKSPACE_COMMAND_VERSION,
) -> dict[str, Any]:
    """Render a deterministic, zero-write workspace transaction plan."""
    root = root.resolve(strict=True)
    if not OPERATION_ID.fullmatch(operation_id):
        raise TransactionError("WS_TRANSACTION_ID_INVALID", "Operation ID contains unsupported characters.", operation_id)
    if not operation:
        raise TransactionError("WS_TRANSACTION_PLAN_INVALID", "Operation must not be empty.")
    normalized_changes, normalized_preconditions, roles = _normalize_workspace_inputs(
        root, changes, expected_input_hashes, target_roles
    )
    actual_workspace_id = _workspace_id(root)
    if workspace_id is not None and workspace_id != actual_workspace_id:
        raise TransactionError(
            "WS_TRANSACTION_PLAN_STALE",
            "Workspace identity changed after planning.",
            {"expected": workspace_id, "observed": actual_workspace_id},
        )
    actual_invariant_hash = _invariant_source_sha256()
    expected_invariant_hash = invariant_source_sha256.upper() if invariant_source_sha256 is not None else actual_invariant_hash
    if re.fullmatch(r"[A-F0-9]{64}", expected_invariant_hash) is None or expected_invariant_hash != actual_invariant_hash:
        raise TransactionError(
            "WS_TRANSACTION_PLAN_STALE",
            "Invariant-set identity changed after planning.",
            {"expected": expected_invariant_hash, "observed": actual_invariant_hash},
        )
    if command_version != WORKSPACE_COMMAND_VERSION:
        raise TransactionError(
            "WS_TRANSACTION_PLAN_STALE",
            "Command version changed after planning.",
            {"expected": command_version, "observed": WORKSPACE_COMMAND_VERSION},
        )
    ordered_targets = sorted(
        normalized_changes,
        key=lambda path: (WORKSPACE_ROLE_ORDER[roles[path]], _relative(root, path).casefold(), _relative(root, path)),
    )
    inputs = [
        {
            "path": _relative(root, path),
            "expected_preimage": normalized_preconditions[path] or "ABSENT",
            "changed": path in normalized_changes,
        }
        for path in sorted(normalized_preconditions, key=lambda item: (_relative(root, item).casefold(), _relative(root, item)))
    ]
    targets = [
        {
            "path": _relative(root, path),
            "role": roles[path],
            "order": index,
            "expected_preimage": normalized_preconditions[path] or "ABSENT",
            "planned_sha256": sha256_bytes(normalized_changes[path]),
            "planned_bytes": len(normalized_changes[path]),
            "rollback_action": "RESTORE_PREIMAGE" if normalized_preconditions[path] is not None else "REMOVE_CREATED",
        }
        for index, path in enumerate(ordered_targets, start=1)
    ]
    canonical = {
        "plan_schema": 1,
        "operation_id": operation_id,
        "operation": operation,
        "workspace_id": actual_workspace_id,
        "invariant_source_sha256": actual_invariant_hash,
        "command_version": command_version,
        "inputs": inputs,
        "targets": targets,
        "replacement_roles": [item["role"] for item in targets],
        "validation_steps": ["exact-output-hashes", "semantic-bindings"],
        "declarations": {
            "implicit_session_created": False,
            "artifact_enrollment_performed": False,
            "vcs_commands_performed": False,
            "network_calls_performed": False,
        },
    }
    return {**canonical, "plan_sha256": sha256_bytes(_json_bytes(canonical))}


def _workspace_journal_issues(value: Mapping[str, Any]) -> list[str]:
    try:
        from malts_user_contracts import validate_instance

        issues = validate_instance(Path(__file__).resolve().parent.parent, "workspace-transaction-journal", dict(value))
    except Exception as exc:
        raise TransactionError("WS_TRANSACTION_JOURNAL_SCHEMA_INVALID", "Workspace journal validation could not run.", str(exc)) from exc
    return [issue.render() for issue in issues]


def _write_workspace_journal(path: Path, journal: dict[str, Any]) -> None:
    issues = _workspace_journal_issues(journal)
    if issues:
        raise TransactionError("WS_TRANSACTION_JOURNAL_SCHEMA_INVALID", "Workspace journal violates its closed schema.", issues)
    _atomic_json(path, journal)


def _append_workspace_state(journal: dict[str, Any], state: str, evidence_refs: list[str] | None = None) -> None:
    if state not in WORKSPACE_JOURNAL_STATES:
        raise TransactionError("WS_TRANSACTION_JOURNAL_SCHEMA_INVALID", "Unknown workspace journal state.", state)
    journal["state"] = state
    journal["state_history"].append(
        {
            "state": state,
            "at": _timestamp(),
            "replacement_cursor": journal["replacement_cursor"],
            "evidence_refs": evidence_refs or [f"transaction:{journal['operation_id']}:{state.casefold()}"],
        }
    )


def _inject_workspace_fault(requested: str | None, point: str) -> None:
    if requested not in {point, f"crash:{point}", f"interrupt:{point}"}:
        return
    if requested != point:
        os._exit(91)
    raise TransactionError(
        "WS_TRANSACTION_INJECTED_FAILURE",
        "Injected failure at an exact workspace transaction boundary.",
        {"fault_point": point},
    )


def _workspace_completed_retry(
    root: Path,
    journal: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any] | None:
    if journal.get("state") != "COMMITTED":
        return None
    if journal.get("operation_id") != plan["operation_id"] or journal.get("operation") != plan["operation"] or journal.get("plan_sha256") != plan["plan_sha256"]:
        raise TransactionError("WS_TRANSACTION_REPLAY_CONFLICT", "Operation ID was already committed with a different plan.")
    observed = {
        item["path"]: _current_hash(_inside(root, root / Path(item["path"]), WORKSPACE_TRANSACTION_PROFILE), WORKSPACE_TRANSACTION_PROFILE)
        for item in plan["targets"]
    }
    expected = {item["path"]: item["planned_sha256"] for item in plan["targets"]}
    if observed != expected:
        raise TransactionError("WS_TRANSACTION_REPLAY_CONFLICT", "Committed transaction outputs no longer match their receipt.", observed)
    target_paths = set(expected)
    for item in plan["inputs"]:
        if item["path"] in target_paths:
            continue
        input_path = _workspace_locator(root, item["path"])
        expected_input = None if item["expected_preimage"] == "ABSENT" else item["expected_preimage"]
        observed_input = _current_hash(input_path, WORKSPACE_TRANSACTION_PROFILE)
        if observed_input != expected_input:
            raise TransactionError(
                "WS_TRANSACTION_REPLAY_CONFLICT",
                "A read-only precondition changed after the committed operation.",
                {"path": item["path"], "expected": expected_input, "observed": observed_input},
            )
    return {
        "operation_id": plan["operation_id"],
        "journal_path": journal.get("journal_path"),
        "plan_sha256": plan["plan_sha256"],
        "status": "COMMITTED",
        "idempotent": True,
        "writes_performed": False,
        "replacement_count": 0,
        "lock_released": True,
    }


def _workspace_target_rows(
    root: Path,
    plan: Mapping[str, Any],
    changes: Mapping[Path, bytes],
) -> tuple[list[dict[str, Any]], dict[Path, bytes | None]]:
    payload_by_relative = {_relative(root, path): payload for path, payload in changes.items()}
    rows: list[dict[str, Any]] = []
    originals: dict[Path, bytes | None] = {}
    for item in plan["targets"]:
        path = _inside(root, root / Path(item["path"]), WORKSPACE_TRANSACTION_PROFILE)
        original = _io_path(path).read_bytes() if _io_path(path).exists() else None
        originals[path] = original
        rows.append(
            {
                "path": item["path"],
                "role": item["role"],
                "order": item["order"],
                "original_existed": original is not None,
                "original_bytes": len(original) if original is not None else None,
                "original_sha256": sha256_bytes(original) if original is not None else None,
                "original_base64": base64.b64encode(original).decode("ascii") if original is not None else None,
                "planned_sha256": item["planned_sha256"],
                "planned_bytes": len(payload_by_relative[item["path"]]),
                "stage_path": None,
                "stage_sha256": None,
                "replacement_state": "PENDING",
            }
        )
    return rows, originals


def _execute_workspace_transaction(
    root: Path,
    *,
    operation_id: str,
    operation: str,
    changes: Mapping[Path, bytes],
    expected_input_hashes: Mapping[Path, str | None],
    post_validate: Callable[[], None] | None,
    target_roles: Mapping[Path | str, str] | None,
    plan_sha256: str | None,
    workspace_id: str | None,
    invariant_source_sha256: str | None,
    command_version: str,
    fault_point: str | None,
    fail_after_replacements: int | None,
    crash_after_replacements: int | None,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if not changes:
        return {
            "operation_id": operation_id, "journal_path": None, "plan_sha256": None,
            "status": "NO_CHANGES", "idempotent": True, "writes_performed": False,
            "replacement_count": 0, "lock_released": True,
        }
    normalized_changes, normalized_preconditions, roles = _normalize_workspace_inputs(root, changes, expected_input_hashes, target_roles)
    plan = plan_transaction(
        root,
        operation_id=operation_id,
        operation=operation,
        changes=normalized_changes,
        expected_input_hashes=normalized_preconditions,
        target_roles=roles,
        workspace_id=workspace_id,
        invariant_source_sha256=invariant_source_sha256,
        command_version=command_version,
    )
    if plan_sha256 is not None and plan_sha256.upper() != plan["plan_sha256"]:
        raise TransactionError(
            "WS_TRANSACTION_PLAN_STALE",
            "The supplied plan SHA-256 does not match the current deterministic plan.",
            {"expected": plan_sha256.upper(), "observed": plan["plan_sha256"]},
        )
    lock_path = _inside(root, root / WORKSPACE_TRANSACTION_PROFILE.lock_relative, WORKSPACE_TRANSACTION_PROFILE)
    journal_directory = _inside(root, root / WORKSPACE_TRANSACTION_PROFILE.journal_directory_relative, WORKSPACE_TRANSACTION_PROFILE)
    journal_path = _inside(root, journal_directory / f"{operation_id}.json", WORKSPACE_TRANSACTION_PROFILE)
    if _io_path(lock_path).exists():
        raise TransactionError("WS_TRANSACTION_INCOMPLETE", "An incomplete workspace transaction blocks governed mutation.", _relative(root, lock_path))
    prior_attempt = 0
    attempt_history: list[dict[str, Any]] = []
    if _io_path(journal_path).exists():
        prior = _read_json(journal_path, "WS_TRANSACTION_JOURNAL_SCHEMA_INVALID")
        issues = _workspace_journal_issues(prior)
        if issues:
            raise TransactionError("WS_TRANSACTION_JOURNAL_SCHEMA_INVALID", "Existing workspace journal violates its closed schema.", issues)
        completed = _workspace_completed_retry(root, prior, plan)
        if completed is not None:
            return completed
        if prior.get("state") != "ROLLED_BACK" or prior.get("plan_sha256") != plan["plan_sha256"]:
            raise TransactionError("WS_TRANSACTION_REPLAY_CONFLICT", "Operation ID already owns a different or incomplete journal.")
        prior_attempt = int(prior.get("attempt", 1))
        attempt_history = list(prior.get("attempt_history", [])) + [
            {
                "attempt": prior_attempt,
                "state": "ROLLED_BACK",
                "failed_at": prior.get("completed_at"),
                "failure": prior.get("failure"),
            }
        ]
    for path, expected in normalized_preconditions.items():
        observed = _current_hash(path, WORKSPACE_TRANSACTION_PROFILE)
        if observed != expected:
            raise TransactionError(
                "WS_TRANSACTION_PLAN_STALE",
                "A transaction input changed after planning.",
                {"path": _relative(root, path), "expected": expected or "ABSENT", "observed": observed or "ABSENT"},
            )
    ordered_paths = [
        _inside(root, root / Path(item["path"]), WORKSPACE_TRANSACTION_PROFILE)
        for item in plan["targets"]
    ]
    _io_path(lock_path.parent).mkdir(parents=True, exist_ok=True)
    lock_value = {
        "lock_schema": 1,
        "operation_id": operation_id,
        "operation": operation,
        "plan_sha256": plan["plan_sha256"],
        "workspace_id": plan["workspace_id"],
        "invariant_source_sha256": plan["invariant_source_sha256"],
        "command_version": plan["command_version"],
        "created_at": _timestamp(),
        "journal_path": _relative(root, journal_path),
        "inputs": plan["inputs"],
        "targets": plan["targets"],
    }
    try:
        _write_new_file(lock_path, _json_bytes(lock_value))
    except FileExistsError as exc:
        raise TransactionError("WS_TRANSACTION_INCOMPLETE", "Another workspace transaction acquired the lock.") from exc
    lock_sha256 = sha256_bytes(_io_path(lock_path).read_bytes())
    _inject_workspace_fault(fault_point, "after_lock_acquisition")
    target_rows, originals = _workspace_target_rows(root, plan, normalized_changes)
    journal: dict[str, Any] = {
        "journal_schema": 1,
        "operation_id": operation_id,
        "operation": operation,
        "plan_sha256": plan["plan_sha256"],
        "workspace_id": plan["workspace_id"],
        "invariant_source_sha256": plan["invariant_source_sha256"],
        "command_version": plan["command_version"],
        "created_at": lock_value["created_at"],
        "state": "PREPARED",
        "state_history": [
            {"state": "PREPARED", "at": _timestamp(), "replacement_cursor": 0, "evidence_refs": [f"plan:{plan['plan_sha256']}"]}
        ],
        "journal_path": _relative(root, journal_path),
        "lock_path": _relative(root, lock_path),
        "inputs": plan["inputs"],
        "targets": target_rows,
        "replacement_cursor": 0,
        "replacement_count": 0,
        "validation_steps": plan["validation_steps"],
        "declarations": plan["declarations"],
        "attempt": prior_attempt + 1,
        "attempt_history": attempt_history,
        "failure": None,
        "recovery": None,
        "completed_at": None,
    }
    staged: dict[Path, Path] = {}
    created_directories: list[Path] = []
    committed = False
    try:
        _inject_workspace_fault(fault_point, "before_prepared")
        _write_workspace_journal(journal_path, journal)
        _inject_workspace_fault(fault_point, "after_prepared")
        _append_workspace_state(journal, "IN_PROGRESS")
        _write_workspace_journal(journal_path, journal)
        _inject_workspace_fault(fault_point, "after_in_progress")
        created_directories = _created_parent_directories(root, ordered_paths)
        payloads = {_relative(root, path): payload for path, payload in normalized_changes.items()}
        for index, path in enumerate(ordered_paths):
            temporary = _write_temporary_file(path.parent, payloads[_relative(root, path)])
            staged[path] = temporary
            journal["targets"][index]["stage_path"] = _relative(root, temporary)
            journal["targets"][index]["stage_sha256"] = _current_hash(temporary, WORKSPACE_TRANSACTION_PROFILE)
            journal["targets"][index]["replacement_state"] = "STAGED"
        _write_workspace_journal(journal_path, journal)
        _inject_workspace_fault(fault_point, "after_all_staged")
        for index, path in enumerate(ordered_paths, start=1):
            _inject_workspace_fault(fault_point, f"before_replace:{index}")
            os.replace(_io_path(staged[path]), _io_path(path))
            _inject_workspace_fault(fault_point, f"after_replace_before_cursor:{index}")
            journal["targets"][index - 1]["stage_path"] = None
            journal["targets"][index - 1]["stage_sha256"] = None
            journal["targets"][index - 1]["replacement_state"] = "REPLACED"
            journal["replacement_cursor"] = index
            journal["replacement_count"] = index
            _write_workspace_journal(journal_path, journal)
            _inject_workspace_fault(fault_point, f"after_cursor:{index}")
            if fail_after_replacements is not None and index == fail_after_replacements:
                _inject_workspace_fault(f"after_cursor:{index}", f"after_cursor:{index}")
            if crash_after_replacements is not None and index == crash_after_replacements:
                _inject_workspace_fault(f"crash:after_cursor:{index}", f"after_cursor:{index}")
        _inject_workspace_fault(fault_point, "after_all_replacements")
        observed_outputs: dict[str, str | None] = {}
        for item, path in zip(plan["targets"], ordered_paths):
            observed_outputs[item["path"]] = _current_hash(path, WORKSPACE_TRANSACTION_PROFILE)
            if observed_outputs[item["path"]] != item["planned_sha256"]:
                raise TransactionError("WS_TRANSACTION_OUTPUT_DRIFT", "A staged output does not match its planned hash.", observed_outputs)
        if post_validate is not None:
            post_validate()
        _inject_workspace_fault(fault_point, "after_validation")
        journal["completed_at"] = _timestamp()
        _append_workspace_state(journal, "COMMITTED", [f"output:{item['path']}" for item in plan["targets"]])
        _inject_workspace_fault(fault_point, "before_committed")
        _write_workspace_journal(journal_path, journal)
        committed = True
        _inject_workspace_fault(fault_point, "after_committed")
        current_lock = _read_json(lock_path, "WS_TRANSACTION_LOCK_INVALID")
        if current_lock.get("operation_id") != operation_id or current_lock.get("plan_sha256") != plan["plan_sha256"]:
            raise TransactionError("WS_TRANSACTION_LOCK_DRIFT", "Workspace transaction lock ownership changed unexpectedly.")
        _inject_workspace_fault(fault_point, "before_lock_removal")
        _io_path(lock_path).unlink()
        return {
            "operation_id": operation_id,
            "journal_path": _relative(root, journal_path),
            "journal_sha256": sha256_bytes(_io_path(journal_path).read_bytes()),
            "lock_sha256": lock_sha256,
            "plan_sha256": plan["plan_sha256"],
            "status": "COMMITTED",
            "idempotent": False,
            "writes_performed": True,
            "replacement_count": len(ordered_paths),
            "lock_released": True,
        }
    except Exception as exc:
        if committed or journal.get("state") == "COMMITTED":
            if isinstance(exc, TransactionError):
                raise
            raise TransactionError("WS_TRANSACTION_COMMIT_FINALIZATION_REQUIRED", "COMMITTED output is awaiting exact lock finalization.", str(exc)) from exc
        rollback_errors: list[str] = []
        try:
            journal["failure"] = {
                "type": type(exc).__name__,
                "message": str(exc) or type(exc).__name__,
                "fault_point": (exc.detail or {}).get("fault_point") if isinstance(exc, TransactionError) and isinstance(exc.detail, dict) else None,
            }
            journal["recovery"] = {
                "mode": "PREIMAGE_RESTORE", "started_at": _timestamp(), "completed_at": None, "result": None,
            }
            _append_workspace_state(journal, "ROLLING_BACK")
            _write_workspace_journal(journal_path, journal)
            _inject_workspace_fault(fault_point, "after_rolling_back")
            for reverse_index, path in enumerate(reversed(ordered_paths), start=1):
                relative = _relative(root, path)
                planned = next(item["planned_sha256"] for item in plan["targets"] if item["path"] == relative)
                observed = _current_hash(path, WORKSPACE_TRANSACTION_PROFILE)
                original = originals[path]
                original_hash = sha256_bytes(original) if original is not None else None
                if observed not in {original_hash, planned}:
                    raise TransactionError(
                        "WS_TRANSACTION_RECOVERY_TARGET_DRIFT",
                        "Rollback target matches neither its exact preimage nor planned output.",
                        {"path": relative, "observed": observed, "original": original_hash, "planned": planned},
                    )
                if original is None:
                    if observed == planned and _io_path(path).exists():
                        _io_path(path).unlink()
                elif observed != original_hash:
                    _atomic_bytes(path, original)
                row = next(item for item in journal["targets"] if item["path"] == relative)
                row["stage_path"] = None
                row["stage_sha256"] = None
                row["replacement_state"] = "RESTORED"
                _write_workspace_journal(journal_path, journal)
                _inject_workspace_fault(fault_point, f"after_restore:{reverse_index}")
            journal["replacement_cursor"] = 0
            journal["replacement_count"] = 0
            journal["recovery"]["completed_at"] = _timestamp()
            journal["recovery"]["result"] = "EXACT_PREIMAGES_RESTORED"
            journal["completed_at"] = _timestamp()
            _append_workspace_state(journal, "ROLLED_BACK")
            _inject_workspace_fault(fault_point, "before_rolled_back")
            _write_workspace_journal(journal_path, journal)
            _inject_workspace_fault(fault_point, "after_rolled_back")
            current_lock = _read_json(lock_path, "WS_TRANSACTION_LOCK_INVALID")
            if current_lock.get("operation_id") != operation_id or current_lock.get("plan_sha256") != plan["plan_sha256"]:
                raise TransactionError("WS_TRANSACTION_LOCK_DRIFT", "Workspace lock changed during caught rollback.")
            _inject_workspace_fault(fault_point, "rollback_before_lock_removal")
            _io_path(lock_path).unlink()
        except Exception as rollback_exc:
            rollback_errors.append(str(rollback_exc) or type(rollback_exc).__name__)
            journal["failure"] = journal.get("failure") or {
                "type": type(exc).__name__, "message": str(exc) or type(exc).__name__, "fault_point": None,
            }
            journal["recovery"] = journal.get("recovery") or {
                "mode": "PREIMAGE_RESTORE", "started_at": _timestamp(), "completed_at": None, "result": None,
            }
            journal["recovery"]["completed_at"] = _timestamp()
            journal["recovery"]["result"] = f"FAILED: {rollback_errors[0]}"
            journal["completed_at"] = None
            _append_workspace_state(journal, "RECOVERY_REQUIRED")
            try:
                _inject_workspace_fault(fault_point, "before_recovery_required")
                _write_workspace_journal(journal_path, journal)
                _inject_workspace_fault(fault_point, "after_recovery_required")
            except Exception:
                pass
        finally:
            for temporary in staged.values():
                if _io_path(temporary).exists():
                    _io_path(temporary).unlink()
            _cleanup_empty_directories(created_directories)
        if rollback_errors:
            raise TransactionError(
                "WS_TRANSACTION_RECOVERY_REQUIRED",
                "Workspace transaction rollback could not be proven complete; lock and journal were retained.",
                {"operation_id": operation_id, "journal_path": _relative(root, journal_path), "errors": rollback_errors},
            ) from exc
        if isinstance(exc, TransactionError):
            raise
        raise TransactionError("WS_TRANSACTION_FAILED", "Workspace transaction failed and exact preimages were restored.", str(exc)) from exc


def _decode_workspace_original(item: Mapping[str, Any]) -> bytes | None:
    if item.get("original_existed") is False:
        if any(item.get(key) is not None for key in ("original_bytes", "original_sha256", "original_base64")):
            raise TransactionError("WS_TRANSACTION_JOURNAL_SCHEMA_INVALID", "ABSENT target carries an impossible preimage.", item.get("path"))
        return None
    encoded = item.get("original_base64")
    if not isinstance(encoded, str):
        raise TransactionError("WS_TRANSACTION_JOURNAL_SCHEMA_INVALID", "Existing target lacks its exact preimage.", item.get("path"))
    try:
        payload = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise TransactionError("WS_TRANSACTION_JOURNAL_SCHEMA_INVALID", "Target preimage is not valid base64.", item.get("path")) from exc
    if len(payload) != item.get("original_bytes") or sha256_bytes(payload) != item.get("original_sha256"):
        raise TransactionError("WS_TRANSACTION_JOURNAL_SCHEMA_INVALID", "Target preimage bytes do not match the journal.", item.get("path"))
    return payload


def _declared_workspace_stage(
    root: Path,
    target_path: Path,
    item: Mapping[str, Any],
) -> tuple[Path | None, dict[str, Any] | None]:
    relative = item.get("stage_path")
    expected_hash = item.get("stage_sha256")
    if relative is None:
        if expected_hash is not None:
            raise TransactionError(
                "WS_TRANSACTION_JOURNAL_SCHEMA_INVALID",
                "A missing stage locator cannot retain a stage hash.",
                item.get("path"),
            )
        return None, None
    if not isinstance(relative, str) or not isinstance(expected_hash, str):
        raise TransactionError(
            "WS_TRANSACTION_JOURNAL_SCHEMA_INVALID",
            "A declared stage file requires an exact relative locator and SHA-256.",
            item.get("path"),
        )
    stage = _workspace_locator(root, relative)
    if stage.parent != target_path.parent or SHORT_TEMP_NAME.fullmatch(stage.name) is None:
        raise TransactionError(
            "WS_TRANSACTION_JOURNAL_SCHEMA_INVALID",
            "A declared stage file is outside its exact target directory or temporary-name contract.",
            {"target": item.get("path"), "stage_path": relative},
        )
    io_stage = _io_path(stage)
    if not io_stage.exists():
        return stage, {"path": relative, "expected_sha256": expected_hash, "observed": "ABSENT"}
    if not io_stage.is_file() or io_stage.is_symlink():
        raise TransactionError(
            "WS_TRANSACTION_RECOVERY_TARGET_DRIFT",
            "A declared stage locator is not a regular non-reparse file.",
            relative,
        )
    observed_hash = _current_hash(stage, WORKSPACE_TRANSACTION_PROFILE)
    if observed_hash != expected_hash:
        raise TransactionError(
            "WS_TRANSACTION_RECOVERY_TARGET_DRIFT",
            "A declared stage file changed after interruption.",
            {"path": relative, "expected": expected_hash, "observed": observed_hash},
        )
    return stage, {"path": relative, "expected_sha256": expected_hash, "observed": observed_hash}


def _recover_workspace_lock_only(
    root: Path,
    *,
    operation_id: str,
    expected_lock_sha256: str | None,
    apply: bool,
) -> dict[str, Any]:
    lock_path = _inside(root, root / WORKSPACE_TRANSACTION_PROFILE.lock_relative, WORKSPACE_TRANSACTION_PROFILE)
    if not _io_path(lock_path).is_file():
        raise TransactionError("WS_TRANSACTION_LOCK_MISSING", "Lock-only recovery requires the exact workspace lock.")
    observed_lock_hash = sha256_bytes(_io_path(lock_path).read_bytes())
    if expected_lock_sha256 is None or expected_lock_sha256.upper() != observed_lock_hash:
        raise TransactionError(
            "WS_TRANSACTION_LOCK_HASH_DRIFT",
            "Workspace lock changed after recovery review.",
            {"expected": expected_lock_sha256, "observed": observed_lock_hash},
        )
    lock = _read_json(lock_path, "WS_TRANSACTION_LOCK_INVALID")
    if lock.get("operation_id") != operation_id:
        raise TransactionError("WS_TRANSACTION_LOCK_DRIFT", "Workspace lock belongs to another operation.")
    journal_path = _inside(root, root / Path(str(lock.get("journal_path", "N/A"))), WORKSPACE_TRANSACTION_PROFILE)
    if _io_path(journal_path).exists():
        raise TransactionError("WS_TRANSACTION_JOURNAL_HASH_REQUIRED", "A journal appeared after lock-only recovery review.")
    rows: list[dict[str, Any]] = []
    for item in lock.get("inputs", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise TransactionError("WS_TRANSACTION_LOCK_INVALID", "Lock input registry is invalid.")
        path = _inside(root, root / Path(item["path"]), WORKSPACE_TRANSACTION_PROFILE)
        expected = None if item.get("expected_preimage") == "ABSENT" else item.get("expected_preimage")
        observed = _current_hash(path, WORKSPACE_TRANSACTION_PROFILE)
        if observed != expected:
            raise TransactionError("WS_TRANSACTION_RECOVERY_TARGET_DRIFT", "A target changed before PREPARED became durable.", {"path": item["path"], "expected": expected, "observed": observed})
        rows.append({"path": item["path"], "observed": observed or "ABSENT"})
    result = {
        "operation_id": operation_id,
        "mode": "APPLY" if apply else "DRY_RUN",
        "recovery_mode": "LOCK_ONLY",
        "status": "LOCK_FINALIZED" if apply else "RECOVERY_PLANNED",
        "expected_lock_sha256": observed_lock_hash,
        "verified_inputs": rows,
        "writes_performed": False,
        "lock_released": False,
    }
    if apply:
        if sha256_bytes(_io_path(lock_path).read_bytes()) != observed_lock_hash or _io_path(journal_path).exists():
            raise TransactionError("WS_TRANSACTION_LOCK_HASH_DRIFT", "Lock-only recovery conditions changed before apply.")
        _io_path(lock_path).unlink()
        result["writes_performed"] = True
        result["lock_released"] = True
    return result


def _recover_workspace_transaction(
    root: Path,
    *,
    operation_id: str,
    expected_journal_sha256: str | None,
    expected_lock_sha256: str | None,
    apply: bool,
    fault_point: str | None,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if not OPERATION_ID.fullmatch(operation_id):
        raise TransactionError("WS_TRANSACTION_ID_INVALID", "Operation ID contains unsupported characters.", operation_id)
    journal_path = _inside(root, root / WORKSPACE_TRANSACTION_PROFILE.journal_directory_relative / f"{operation_id}.json", WORKSPACE_TRANSACTION_PROFILE)
    if not _io_path(journal_path).is_file():
        return _recover_workspace_lock_only(
            root, operation_id=operation_id, expected_lock_sha256=expected_lock_sha256, apply=apply
        )
    observed_journal_hash = sha256_bytes(_io_path(journal_path).read_bytes())
    if expected_journal_sha256 is None or expected_journal_sha256.upper() != observed_journal_hash:
        raise TransactionError(
            "WS_TRANSACTION_JOURNAL_HASH_DRIFT",
            "Workspace journal changed after recovery review.",
            {"expected": expected_journal_sha256, "observed": observed_journal_hash},
        )
    journal = _read_json(journal_path, "WS_TRANSACTION_JOURNAL_SCHEMA_INVALID")
    issues = _workspace_journal_issues(journal)
    if issues:
        raise TransactionError("WS_TRANSACTION_JOURNAL_SCHEMA_INVALID", "Workspace journal violates its closed schema.", issues)
    if journal.get("operation_id") != operation_id:
        raise TransactionError("WS_TRANSACTION_REPLAY_CONFLICT", "Journal belongs to another operation.")
    lock_path = _inside(root, root / WORKSPACE_TRANSACTION_PROFILE.lock_relative, WORKSPACE_TRANSACTION_PROFILE)
    if not _io_path(lock_path).is_file():
        raise TransactionError("WS_TRANSACTION_LOCK_MISSING", "Workspace journal recovery requires its exact lock.")
    lock_payload = _io_path(lock_path).read_bytes()
    observed_lock_hash = sha256_bytes(lock_payload)
    if expected_lock_sha256 is not None and expected_lock_sha256.upper() != observed_lock_hash:
        raise TransactionError("WS_TRANSACTION_LOCK_HASH_DRIFT", "Workspace lock changed after recovery review.", {"expected": expected_lock_sha256, "observed": observed_lock_hash})
    lock = _read_json(lock_path, "WS_TRANSACTION_LOCK_INVALID")
    if lock.get("operation_id") != operation_id or lock.get("plan_sha256") != journal.get("plan_sha256"):
        raise TransactionError("WS_TRANSACTION_LOCK_DRIFT", "Workspace lock and journal identity differ.")
    state = journal.get("state")
    if state == "COMMITTED":
        outputs: list[dict[str, Any]] = []
        for item in journal["targets"]:
            path = _inside(root, root / Path(item["path"]), WORKSPACE_TRANSACTION_PROFILE)
            observed = _current_hash(path, WORKSPACE_TRANSACTION_PROFILE)
            if observed != item["planned_sha256"]:
                raise TransactionError("WS_TRANSACTION_RECOVERY_REQUIRED", "COMMITTED output hash failed commit-finalization validation.", {"path": item["path"], "expected": item["planned_sha256"], "observed": observed})
            outputs.append({"path": item["path"], "sha256": observed})
        result = {
            "operation_id": operation_id, "journal_path": _relative(root, journal_path),
            "mode": "APPLY" if apply else "DRY_RUN", "recovery_mode": "COMMIT_FINALIZATION",
            "status": "COMMIT_FINALIZED" if apply else "RECOVERY_PLANNED",
            "validated_outputs": outputs, "writes_performed": False, "lock_released": False,
        }
        if apply:
            if sha256_bytes(_io_path(journal_path).read_bytes()) != observed_journal_hash or sha256_bytes(_io_path(lock_path).read_bytes()) != observed_lock_hash:
                raise TransactionError("WS_TRANSACTION_JOURNAL_HASH_DRIFT", "Commit-finalization inputs changed before apply.")
            _io_path(lock_path).unlink()
            result["writes_performed"] = True
            result["lock_released"] = True
        return result
    if state not in {"PREPARED", "IN_PROGRESS", "ROLLING_BACK", "RECOVERY_REQUIRED"}:
        raise TransactionError("WS_TRANSACTION_RECOVERY_STATE_INVALID", "Only an incomplete or COMMITTED-with-lock journal can be recovered.", state)
    restores: list[dict[str, Any]] = []
    decoded: dict[Path, bytes | None] = {}
    stage_cleanups: dict[Path, Path | None] = {}
    planned_stage_cleanups: list[dict[str, Any]] = []
    for item in journal["targets"]:
        path = _inside(root, root / Path(item["path"]), WORKSPACE_TRANSACTION_PROFILE)
        original = _decode_workspace_original(item)
        decoded[path] = original
        original_hash = sha256_bytes(original) if original is not None else None
        observed = _current_hash(path, WORKSPACE_TRANSACTION_PROFILE)
        if observed not in {original_hash, item["planned_sha256"]}:
            raise TransactionError("WS_TRANSACTION_RECOVERY_TARGET_DRIFT", "Recovery target matches neither exact preimage nor planned output.", {"path": item["path"], "observed": observed, "original": original_hash, "planned": item["planned_sha256"]})
        restores.append({"path": item["path"], "observed": observed or "ABSENT", "restore_sha256": original_hash or "ABSENT"})
        stage, cleanup = _declared_workspace_stage(root, path, item)
        stage_cleanups[path] = stage
        if cleanup is not None:
            planned_stage_cleanups.append(cleanup)
    result = {
        "operation_id": operation_id, "journal_path": _relative(root, journal_path),
        "mode": "APPLY" if apply else "DRY_RUN", "recovery_mode": "PREIMAGE_RESTORE",
        "status": "ROLLED_BACK" if apply else "RECOVERY_PLANNED", "planned_restores": restores,
        "planned_stage_cleanups": planned_stage_cleanups,
        "writes_performed": False, "lock_released": False,
    }
    if not apply:
        return result
    if sha256_bytes(_io_path(journal_path).read_bytes()) != observed_journal_hash or sha256_bytes(_io_path(lock_path).read_bytes()) != observed_lock_hash:
        raise TransactionError("WS_TRANSACTION_JOURNAL_HASH_DRIFT", "Recovery inputs changed before apply.")
    try:
        journal["recovery"] = {"mode": "PREIMAGE_RESTORE", "started_at": _timestamp(), "completed_at": None, "result": None}
        if journal["state"] != "ROLLING_BACK":
            _append_workspace_state(journal, "ROLLING_BACK")
        _write_workspace_journal(journal_path, journal)
        _inject_workspace_fault(fault_point, "recovery_after_rolling_back")
        for reverse_index, item in enumerate(reversed(journal["targets"]), start=1):
            path = _inside(root, root / Path(item["path"]), WORKSPACE_TRANSACTION_PROFILE)
            original = decoded[path]
            observed = _current_hash(path, WORKSPACE_TRANSACTION_PROFILE)
            if original is None:
                if observed == item["planned_sha256"] and _io_path(path).exists():
                    _io_path(path).unlink()
            elif observed != item["original_sha256"]:
                _atomic_bytes(path, original)
            stage = stage_cleanups[path]
            if stage is not None and _io_path(stage).exists():
                observed_stage = _current_hash(stage, WORKSPACE_TRANSACTION_PROFILE)
                if observed_stage != item["stage_sha256"]:
                    raise TransactionError(
                        "WS_TRANSACTION_RECOVERY_TARGET_DRIFT",
                        "A declared stage file changed before exact cleanup.",
                        {"path": item["stage_path"], "expected": item["stage_sha256"], "observed": observed_stage},
                    )
                _io_path(stage).unlink()
            item["stage_path"] = None
            item["stage_sha256"] = None
            item["replacement_state"] = "RESTORED"
            _write_workspace_journal(journal_path, journal)
            _inject_workspace_fault(fault_point, f"recovery_after_restore:{reverse_index}")
        journal["replacement_cursor"] = 0
        journal["replacement_count"] = 0
        journal["recovery"]["completed_at"] = _timestamp()
        journal["recovery"]["result"] = "EXACT_PREIMAGES_RESTORED"
        journal["completed_at"] = _timestamp()
        _append_workspace_state(journal, "ROLLED_BACK")
        _inject_workspace_fault(fault_point, "recovery_before_rolled_back")
        _write_workspace_journal(journal_path, journal)
        _inject_workspace_fault(fault_point, "recovery_after_rolled_back")
        current_lock = _read_json(lock_path, "WS_TRANSACTION_LOCK_INVALID")
        if current_lock.get("operation_id") != operation_id or current_lock.get("plan_sha256") != journal.get("plan_sha256"):
            raise TransactionError("WS_TRANSACTION_LOCK_DRIFT", "Workspace lock changed during recovery.")
        _io_path(lock_path).unlink()
    except Exception as exc:
        journal["recovery"] = journal.get("recovery") or {"mode": "PREIMAGE_RESTORE", "started_at": _timestamp(), "completed_at": None, "result": None}
        journal["recovery"]["completed_at"] = _timestamp()
        journal["recovery"]["result"] = f"FAILED: {str(exc) or type(exc).__name__}"
        journal["completed_at"] = None
        _append_workspace_state(journal, "RECOVERY_REQUIRED")
        try:
            _inject_workspace_fault(fault_point, "recovery_before_recovery_required")
            _write_workspace_journal(journal_path, journal)
            _inject_workspace_fault(fault_point, "recovery_after_recovery_required")
        except Exception:
            pass
        if isinstance(exc, TransactionError):
            raise
        raise TransactionError("WS_TRANSACTION_RECOVERY_REQUIRED", "Explicit workspace recovery failed; evidence and lock were retained.", str(exc)) from exc
    result["writes_performed"] = True
    result["lock_released"] = True
    return result


def _inspect_workspace_transaction_state(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    findings: list[dict[str, Any]] = []
    lock_path = _inside(root, root / WORKSPACE_TRANSACTION_PROFILE.lock_relative, WORKSPACE_TRANSACTION_PROFILE)
    journal_directory = _inside(root, root / WORKSPACE_TRANSACTION_PROFILE.journal_directory_relative, WORKSPACE_TRANSACTION_PROFILE)
    lock_value: dict[str, Any] | None = None
    if _io_path(lock_path).exists():
        try:
            lock_value = _read_json(lock_path, "WS_TRANSACTION_LOCK_INVALID")
        except TransactionError as exc:
            lock_value = {"error": exc.message}
        findings.append(
            {
                "code": "WS_TRANSACTION_INCOMPLETE",
                "path": WORKSPACE_TRANSACTION_PROFILE.lock_relative.as_posix(),
                "message": "A workspace transaction lock blocks every governed reader and mutation.",
                "detail": lock_value,
            }
        )
    if _io_path(journal_directory).is_dir():
        with os.scandir(_io_path(journal_directory)) as entries:
            names = sorted((entry.name for entry in entries if entry.name.casefold().endswith(".json")), key=str.casefold)
        for name in names:
            path = _inside(root, journal_directory / name, WORKSPACE_TRANSACTION_PROFILE)
            try:
                value = _read_json(path, "WS_TRANSACTION_JOURNAL_SCHEMA_INVALID")
                if "journal_schema" not in value and "contract_version" in value:
                    issues = []
                    state = value.get("status")
                else:
                    issues = _workspace_journal_issues(value)
                    state = value.get("state")
            except TransactionError as exc:
                value, issues, state = {}, [exc.message], "INVALID"
            if issues or state in {"PREPARED", "IN_PROGRESS", "RECOVERY_IN_PROGRESS", "ROLLING_BACK", "RECOVERY_REQUIRED"}:
                findings.append(
                    {
                        "code": "WS_TRANSACTION_INCOMPLETE",
                        "path": _relative(root, path),
                        "message": "An incomplete or invalid workspace journal requires exact recovery review.",
                        "detail": {"state": state, "operation_id": value.get("operation_id"), "issues": issues},
                    }
                )
    return {
        "status": "REVIEW_REQUIRED" if findings else "PASS",
        "findings": findings,
        "required_actions": [f"Review {item['path']} with exact journal/lock hash binding." for item in findings],
        "writes_performed": False,
        "recursive_scan_performed": False,
    }


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
    target_roles: Mapping[Path | str, str] | None = None,
    plan_sha256: str | None = None,
    workspace_id: str | None = None,
    invariant_source_sha256: str | None = None,
    command_version: str = WORKSPACE_COMMAND_VERSION,
    fault_point: str | None = None,
) -> dict[str, Any]:
    """Execute one transaction while preserving the legacy Artifact domain."""
    legacy_workspace_journal = False
    if profile is WORKSPACE_TRANSACTION_PROFILE and OPERATION_ID.fullmatch(operation_id):
        candidate = root.resolve(strict=True) / profile.journal_directory_relative / f"{operation_id}.json"
        if _io_path(candidate).is_file():
            value = _read_json(candidate, "WS_TRANSACTION_JOURNAL_INVALID")
            legacy_workspace_journal = "journal_schema" not in value and "contract_version" in value
    if profile is not WORKSPACE_TRANSACTION_PROFILE or legacy_workspace_journal:
        return _execute_legacy_transaction(
            root,
            operation_id=operation_id,
            operation=operation,
            changes=changes,
            expected_input_hashes=expected_input_hashes,
            post_validate=post_validate,
            fail_after_replacements=fail_after_replacements,
            crash_after_replacements=crash_after_replacements,
            profile=profile,
        )
    return _execute_workspace_transaction(
        root,
        operation_id=operation_id,
        operation=operation,
        changes=changes,
        expected_input_hashes=expected_input_hashes,
        post_validate=post_validate,
        target_roles=target_roles,
        plan_sha256=plan_sha256,
        workspace_id=workspace_id,
        invariant_source_sha256=invariant_source_sha256,
        command_version=command_version,
        fault_point=fault_point,
        fail_after_replacements=fail_after_replacements,
        crash_after_replacements=crash_after_replacements,
    )


def recover_transaction(
    root: Path,
    *,
    operation_id: str,
    expected_journal_sha256: str | None = None,
    apply: bool = False,
    profile: TransactionProfile = ARTIFACT_TRANSACTION_PROFILE,
    expected_lock_sha256: str | None = None,
    fault_point: str | None = None,
) -> dict[str, Any]:
    if profile is not WORKSPACE_TRANSACTION_PROFILE:
        if expected_journal_sha256 is None:
            raise TransactionError(_code(profile, "JOURNAL_HASH_INVALID"), "Expected journal hash must be supplied.")
        return _recover_legacy_transaction(
            root,
            operation_id=operation_id,
            expected_journal_sha256=expected_journal_sha256,
            apply=apply,
            profile=profile,
        )
    if OPERATION_ID.fullmatch(operation_id):
        candidate = root.resolve(strict=True) / profile.journal_directory_relative / f"{operation_id}.json"
        if _io_path(candidate).is_file():
            value = _read_json(candidate, "WS_TRANSACTION_JOURNAL_INVALID")
            if "journal_schema" not in value and "contract_version" in value:
                if expected_journal_sha256 is None:
                    raise TransactionError("WS_TRANSACTION_JOURNAL_HASH_INVALID", "Expected journal hash must be supplied.")
                return _recover_legacy_transaction(
                    root,
                    operation_id=operation_id,
                    expected_journal_sha256=expected_journal_sha256,
                    apply=apply,
                    profile=profile,
                )
    return _recover_workspace_transaction(
        root,
        operation_id=operation_id,
        expected_journal_sha256=expected_journal_sha256,
        expected_lock_sha256=expected_lock_sha256,
        apply=apply,
        fault_point=fault_point,
    )


def inspect_transaction_state(
    root: Path,
    profile: TransactionProfile = ARTIFACT_TRANSACTION_PROFILE,
) -> dict[str, Any]:
    if profile is WORKSPACE_TRANSACTION_PROFILE:
        return _inspect_workspace_transaction_state(root)
    return _inspect_legacy_transaction_state(root, profile)
