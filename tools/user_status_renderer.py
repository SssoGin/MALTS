#!/usr/bin/env python3
"""Render stable MALTS status codes in the user's narrative language."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


CATALOG_RELATIVE = Path("runtime") / "status" / "user_status_labels.json"
CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")
LANGUAGE_ALIASES = {
    "en": "en",
    "en-us": "en",
    "en-gb": "en",
    "english": "en",
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh-hans": "zh-CN",
    "chinese": "zh-CN",
    "simplified chinese": "zh-CN",
    "中文": "zh-CN",
    "简体中文": "zh-CN",
}


class UserStatusError(ValueError):
    def __init__(self, code: str, message: str, detail: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


def _normalize_language(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().replace("_", "-").casefold()
    return LANGUAGE_ALIASES.get(normalized)


def select_language(explicit_language: str | None, narrative_language: str | None) -> tuple[str, str]:
    explicit = _normalize_language(explicit_language)
    if explicit is not None:
        return explicit, "EXPLICIT"
    narrative = _normalize_language(narrative_language)
    if narrative is not None:
        return narrative, "NARRATIVE_LANGUAGE"
    return "en", "FALLBACK"


def load_catalog(malts_root: Path | str) -> tuple[dict[str, Any], str]:
    root = Path(malts_root).resolve(strict=True)
    path = root / CATALOG_RELATIVE
    try:
        payload = path.read_bytes()
        catalog = json.loads(payload.decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UserStatusError("USER_STATUS_CATALOG_INVALID", "The user status catalog is unreadable.", str(path)) from exc
    if not isinstance(catalog, dict) or set(catalog) != {"contract_id", "fallback_language", "supported_languages", "labels"}:
        raise UserStatusError("USER_STATUS_CATALOG_INVALID", "The user status catalog has missing or unknown fields.")
    if catalog.get("contract_id") != "malts.user-status-labels.current" or catalog.get("fallback_language") != "en" or catalog.get("supported_languages") != ["en", "zh-CN"]:
        raise UserStatusError("USER_STATUS_CATALOG_INVALID", "The user status catalog identity or language policy is invalid.")
    labels = catalog.get("labels")
    if not isinstance(labels, list) or not labels or len(labels) > 256:
        raise UserStatusError("USER_STATUS_CATALOG_INVALID", "The user status label collection is invalid.")
    codes: list[str] = []
    for item in labels:
        if not isinstance(item, Mapping) or set(item) != {"code", "en", "zh-CN"}:
            raise UserStatusError("USER_STATUS_CATALOG_INVALID", "A user status label has missing or unknown fields.", item)
        code = item.get("code")
        if not isinstance(code, str) or CODE.fullmatch(code) is None:
            raise UserStatusError("USER_STATUS_CODE_INVALID", "A catalog status code is invalid.", code)
        if any(not isinstance(item.get(language), str) or not str(item[language]).strip() for language in ("en", "zh-CN")):
            raise UserStatusError("USER_STATUS_CATALOG_INVALID", "A user status label is empty.", code)
        codes.append(code)
    if codes != sorted(codes) or len(codes) != len(set(codes)):
        raise UserStatusError("USER_STATUS_CATALOG_ORDER", "Catalog status codes must be unique and sorted.", codes)
    return catalog, hashlib.sha256(payload).hexdigest().upper()


def render_statuses(
    malts_root: Path | str,
    codes: Sequence[str],
    *,
    explicit_language: str | None = None,
    narrative_language: str | None = None,
) -> dict[str, Any]:
    if not codes or len(codes) > 64:
        raise UserStatusError("USER_STATUS_CODES_INVALID", "One to 64 status codes are required.")
    normalized_codes: list[str] = []
    for value in codes:
        normalized = str(value).strip().upper()
        if CODE.fullmatch(normalized) is None:
            raise UserStatusError("USER_STATUS_CODE_INVALID", "A status code violates the stable machine-code contract.", value)
        normalized_codes.append(normalized)
    catalog, catalog_sha256 = load_catalog(malts_root)
    language, language_source = select_language(explicit_language, narrative_language)
    labels = {str(item["code"]): item for item in catalog["labels"]}
    items: list[dict[str, Any]] = []
    unknown_codes: list[str] = []
    for position, code in enumerate(normalized_codes, start=1):
        row = labels.get(code)
        known = row is not None
        if known:
            label = str(row[language])
        else:
            label = "未识别状态" if language == "zh-CN" else "Unknown status"
            unknown_codes.append(code)
        rendered = f"{label}（{code}）" if language == "zh-CN" else f"{label} ({code})"
        items.append({"position": position, "code": code, "label": label, "rendered": rendered, "known": known})
    return {
        "contract_id": "malts.user-status-report.current",
        "operation": "render-user-status",
        "requested_language": explicit_language,
        "narrative_language": narrative_language,
        "language": language,
        "language_source": language_source,
        "fallback_language": "en",
        "catalog": {"path": CATALOG_RELATIVE.as_posix(), "sha256": catalog_sha256},
        "items": items,
        "rendered_chain": " / ".join(item["rendered"] for item in items),
        "unknown_codes": sorted(set(unknown_codes)),
        "writes_performed": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--malts-root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--language")
    parser.add_argument("--narrative-language")
    parser.add_argument("--code", action="append", required=True)
    parser.add_argument("--output", choices=("json", "text"), default="json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        report = render_statuses(
            args.malts_root,
            args.code,
            explicit_language=args.language,
            narrative_language=args.narrative_language,
        )
        if args.output == "text":
            print(report["rendered_chain"])
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except UserStatusError as exc:
        print(json.dumps({"status": "FAIL", "code": exc.code, "message": exc.message, "detail": exc.detail}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
