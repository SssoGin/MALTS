#!/usr/bin/env python3
"""Recoverable workspace-scoped transactions for MALTS Artifact mutations."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


LOCK_RELATIVE = Path("runtime") / "artifact_transaction.lock.json"
JOURNAL_DIRECTORY_RELATIVE = Path("runtime") / "artifact_transactions"
OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
PENDING_STATUSES = {"IN_PROGRESS", "RECOVERY_REQUIRED"}


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


def _inside(root: Path, path: Path) -> Path:
    root = root.resolve(strict=True)
    try:
        resolved = path.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise TransactionError("ART_TRANSACTION_PATH_ESCAPE", "Transaction target escapes the workspace boundary.", str(path)) from exc
    return resolved


def _current_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    if not path.is_file():
        raise TransactionError("ART_TRANSACTION_TARGET_TYPE", "Transaction targets must be regular files.", str(path))
    return sha256_bytes(path.read_bytes())


def _write_new_file(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _atomic_bytes(path: Path, payload: bytes) -> None:
    temporary = path.parent / f".{path.name}.malts-transaction-{uuid.uuid4().hex}.tmp"
    try:
        _write_new_file(temporary, payload)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_bytes(path, _json_bytes(dict(value)))


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransactionError(code, "Transaction control JSON is unreadable.", str(path)) from exc
    if not isinstance(value, dict):
        raise TransactionError(code, "Transaction control JSON must be an object.", str(path))
    return value


def _created_parent_directories(root: Path, targets: list[Path]) -> list[Path]:
    missing: set[Path] = set()
    for target in targets:
        current = target.parent
        while current != root and not current.exists():
            missing.add(current)
            current = current.parent
    for directory in sorted(missing, key=lambda item: len(item.parts)):
        directory.mkdir()
    return sorted(missing, key=lambda item: len(item.parts), reverse=True)


def _cleanup_empty_directories(directories: list[Path]) -> None:
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            pass


def _completed_retry(
    root: Path,
    journal: Mapping[str, Any],
    operation: str,
    changes: Mapping[Path, bytes],
    expected_input_hashes: Mapping[Path, str | None],
) -> dict[str, Any] | None:
    if journal.get("status") != "COMMITTED":
        return None
    if journal.get("operation") != operation:
        raise TransactionError("ART_TRANSACTION_RETRY_DRIFT", "Operation ID was already committed for a different operation.")
    recorded = journal.get("planned_outputs")
    if not isinstance(recorded, list):
        raise TransactionError("ART_TRANSACTION_JOURNAL_INVALID", "Committed journal lacks planned outputs.")
    expected_outputs = {_relative(root, path): sha256_bytes(payload) for path, payload in changes.items()}
    recorded_outputs = {
        item.get("path"): item.get("sha256")
        for item in recorded
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    if expected_outputs != recorded_outputs:
        raise TransactionError("ART_TRANSACTION_RETRY_DRIFT", "Operation ID was already committed with different planned bytes.")
    recorded_inputs = {
        item.get("path"): item.get("sha256")
        for item in journal.get("inputs", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    requested_inputs = {_relative(root, path): expected for path, expected in expected_input_hashes.items()}
    if recorded_inputs != requested_inputs:
        raise TransactionError("ART_TRANSACTION_RETRY_DRIFT", "Operation ID was already committed with different input preconditions.")
    observed = {_relative(root, path): _current_hash(path) for path in changes}
    if observed != expected_outputs:
        raise TransactionError("ART_TRANSACTION_RETRY_DRIFT", "Committed transaction outputs no longer match the journal.", observed)
    target_paths = set(expected_outputs)
    for item in journal.get("inputs", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or item["path"] in target_paths:
            continue
        input_path = _inside(root, root / Path(item["path"]))
        observed_input = _current_hash(input_path)
        if observed_input != item.get("sha256"):
            raise TransactionError(
                "ART_TRANSACTION_RETRY_DRIFT",
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
) -> bool:
    if journal.get("status") != "ROLLED_BACK":
        return False
    if journal.get("operation") != operation:
        raise TransactionError("ART_TRANSACTION_RETRY_DRIFT", "Operation ID was rolled back for a different operation.")
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
    observed_inputs = {_relative(root, path): _current_hash(path) for path in expected_input_hashes}
    if planned_outputs != requested_outputs or recorded_inputs != requested_inputs or observed_inputs != requested_inputs:
        raise TransactionError(
            "ART_TRANSACTION_RETRY_DRIFT",
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
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if not OPERATION_ID.fullmatch(operation_id):
        raise TransactionError("ART_TRANSACTION_ID_INVALID", "Operation ID contains unsupported characters.", operation_id)
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
        path = _inside(root, Path(raw_path))
        if path in normalized_preconditions:
            raise TransactionError("ART_TRANSACTION_PRECONDITION_DUPLICATE", "Transaction precondition appears more than once.", str(path))
        normalized_preconditions[path] = expected
    for raw_path, payload in changes.items():
        path = _inside(root, Path(raw_path))
        if path in normalized_changes:
            raise TransactionError("ART_TRANSACTION_TARGET_DUPLICATE", "Transaction target appears more than once.", str(path))
        if path not in normalized_preconditions:
            raise TransactionError("ART_TRANSACTION_PRECONDITION_MISSING", "Every target requires an expected input hash.", str(path))
        normalized_changes[path] = bytes(payload)

    lock_path = _inside(root, root / LOCK_RELATIVE)
    journal_directory = _inside(root, root / JOURNAL_DIRECTORY_RELATIVE)
    journal_path = _inside(root, journal_directory / f"{operation_id}.json")
    if lock_path.exists():
        lock_value: dict[str, Any] | None = None
        try:
            lock_value = _read_json(lock_path, "ART_TRANSACTION_LOCK_INVALID")
        except TransactionError:
            pass
        raise TransactionError(
            "ART_TRANSACTION_LOCKED",
            "Another or stale Artifact transaction lock exists; it is not deleted automatically.",
            {"path": _relative(root, lock_path), "lock": lock_value},
        )
    prior_journal: dict[str, Any] | None = None
    if journal_path.exists():
        journal_value = _read_json(journal_path, "ART_TRANSACTION_JOURNAL_INVALID")
        completed = _completed_retry(root, journal_value, operation, normalized_changes, normalized_preconditions)
        if completed is not None:
            completed["journal_path"] = _relative(root, journal_path)
            return completed
        if _rolled_back_retry_is_safe(root, journal_value, operation, normalized_changes, normalized_preconditions):
            prior_journal = journal_value
        else:
            raise TransactionError(
                "ART_TRANSACTION_JOURNAL_REVIEW_REQUIRED",
                "Operation journal already exists and is not a safe committed or rolled-back retry; manual review is required.",
                {"path": _relative(root, journal_path), "status": journal_value.get("status")},
            )

    lock_path.parent.mkdir(parents=True, exist_ok=True)
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
        raise TransactionError("ART_TRANSACTION_LOCKED", "Another Artifact transaction acquired the workspace lock.", _relative(root, lock_path)) from exc

    originals: dict[Path, bytes | None] = {}
    staged: dict[Path, Path] = {}
    replaced: list[Path] = []
    created_directories: list[Path] = []
    journal: dict[str, Any] | None = None
    rollback_succeeded = False
    try:
        for path, expected in normalized_preconditions.items():
            observed = _current_hash(path)
            if observed != expected:
                raise TransactionError(
                    "ART_TRANSACTION_PRECONDITION_DRIFT",
                    "Canonical input changed after planning and lock acquisition.",
                    {"path": _relative(root, path), "expected": expected, "observed": observed},
                )
            if path in normalized_changes:
                originals[path] = path.read_bytes() if path.exists() else None

        journal_directory.mkdir(parents=True, exist_ok=True)
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
                    "existed": path.exists(),
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
            temporary = path.parent / f".{path.name}.malts-stage-{operation_id}-{uuid.uuid4().hex}.tmp"
            _write_new_file(temporary, payload)
            staged[path] = temporary
        for path in normalized_changes:
            os.replace(staged[path], path)
            replaced.append(path)
            if fail_after_replacements is not None and len(replaced) == fail_after_replacements:
                raise TransactionError(
                    "ART_TRANSACTION_INJECTED_FAILURE",
                    "Injected failure after an exact replacement boundary.",
                    {"replacement_count": len(replaced)},
                )
        if post_validate is not None:
            post_validate()
        journal["status"] = "COMMITTED"
        journal["completed_at"] = _timestamp()
        journal["observed_outputs"] = [
            {"path": _relative(root, path), "sha256": _current_hash(path)}
            for path in sorted(normalized_changes, key=lambda item: _relative(root, item))
        ]
        _atomic_json(journal_path, journal)
        current_lock = _read_json(lock_path, "ART_TRANSACTION_LOCK_INVALID")
        if current_lock.get("operation_id") != operation_id:
            raise TransactionError("ART_TRANSACTION_LOCK_DRIFT", "Workspace transaction lock ownership changed unexpectedly.")
        lock_path.unlink()
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
                    if path.exists():
                        path.unlink()
                else:
                    _atomic_bytes(path, original)
            rollback_succeeded = True
        except Exception as caught:
            rollback_error = caught
        finally:
            for temporary in staged.values():
                if temporary.exists():
                    temporary.unlink()
            _cleanup_empty_directories(created_directories)
        if journal is not None:
            journal["status"] = "ROLLED_BACK" if rollback_succeeded else "RECOVERY_REQUIRED"
            journal["failed_at"] = _timestamp()
            journal["failure"] = {"type": type(exc).__name__, "message": str(exc)}
            if rollback_error is not None:
                journal["rollback_failure"] = {"type": type(rollback_error).__name__, "message": str(rollback_error)}
            _atomic_json(journal_path, journal)
        if rollback_succeeded and lock_path.exists():
            current_lock = _read_json(lock_path, "ART_TRANSACTION_LOCK_INVALID")
            if current_lock.get("operation_id") == operation_id:
                lock_path.unlink()
        if isinstance(exc, TransactionError):
            raise
        raise TransactionError("ART_TRANSACTION_FAILED", "Artifact transaction failed.", {"type": type(exc).__name__, "message": str(exc)}) from exc


def inspect_transaction_state(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    findings: list[dict[str, Any]] = []
    try:
        lock_path = _inside(root, root / LOCK_RELATIVE)
        journal_directory = _inside(root, root / JOURNAL_DIRECTORY_RELATIVE)
    except TransactionError as exc:
        findings.append(
            {
                "code": "ART_TRANSACTION_RUNTIME_ESCAPE",
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
    if lock_path.exists():
        detail: Any
        try:
            detail = _read_json(lock_path, "ART_TRANSACTION_LOCK_INVALID")
        except TransactionError as exc:
            detail = {"error": exc.message}
        findings.append(
            {
                "code": "ART_TRANSACTION_LOCK_REVIEW_REQUIRED",
                "path": LOCK_RELATIVE.as_posix(),
                "message": "Artifact transaction lock exists and is never auto-deleted.",
                "detail": detail,
            }
        )
    if journal_directory.is_dir():
        for raw_journal_path in sorted(journal_directory.glob("*.json"), key=lambda item: item.name.casefold()):
            try:
                journal_path = _inside(root, raw_journal_path)
            except TransactionError:
                findings.append(
                    {
                        "code": "ART_TRANSACTION_JOURNAL_ESCAPE",
                        "path": raw_journal_path.relative_to(root).as_posix(),
                        "message": "Transaction journal resolves outside the workspace and was not read.",
                        "detail": {"status": "UNREAD"},
                    }
                )
                continue
            try:
                value = _read_json(journal_path, "ART_TRANSACTION_JOURNAL_INVALID")
                status = value.get("status")
            except TransactionError as exc:
                value = {"error": exc.message}
                status = "INVALID"
            if status in PENDING_STATUSES or status == "INVALID":
                findings.append(
                    {
                        "code": "ART_TRANSACTION_JOURNAL_REVIEW_REQUIRED",
                        "path": _relative(root, journal_path),
                        "message": "Incomplete or invalid Artifact transaction journal requires exact manual review.",
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
