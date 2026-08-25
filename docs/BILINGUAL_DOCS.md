# MALTS Language Model

MALTS provides English and Simplified Chinese user documentation, templates, and checklists while keeping project state canonical and compact.

## User Documentation

Root and `docs/` English files are the stable technical reference. `README.zh-CN.md` and `docs/zh-CN/` provide Simplified Chinese user guides with equivalent topics and heading structure.

Users may read either language. Commands, paths, schema fields, IDs, status values, and Skill names remain unchanged across languages.

## Runtime Templates

- `runtime/EN/` contains English templates and checklists.
- `runtime/CH/` contains Simplified Chinese templates and checklists.

When `NarrativeLanguage` is Simplified Chinese, an Agent may use the CH templates as drafting references while preserving the stable schema markers and machine-readable values required by MALTS.

User-facing lifecycle and status text selects language in this order: explicit user language, `NarrativeLanguage`, then English fallback. Machine-readable fields and stable status codes remain English. Simplified Chinese presentation must include the Chinese meaning plus the original code in full-width parentheses, for example `已返回（RETURNED）`; use `malts_user_tools.py render-user-status` instead of maintaining a second translation table.

Core-generated Phase/Session recovery summaries and default next actions follow the same language selection. Automatic selection reads only the stable `Narrative language` field inside `<!-- MALTS:section=metadata -->`, never a field-shaped line in free-form project text. Status labels still come from the shared status catalog; free-form user-authored goals, recovery prose, and next actions are preserved instead of being guessed or automatically translated. On-demand report and handoff projections render stored recovery prose as-is; newly generated system prose is already localized at its lifecycle write boundary, while legacy prose with no ownership provenance remains unchanged.

## Canonical Project Files

MALTS uses one canonical file for each runtime role by default:

- `PROJECT_CONTROL.md`
- `WORK_TASK_REPORT.md`
- `PROJECT_HANDOFF.md`
- one control file for each explicitly opened Phase or Session

Narrative sections can use the user's or project's primary language. A full translated mirror is created only when the user explicitly requests it or another workflow requires it.

## What Is Not Duplicated

MALTS does not require both an English and Chinese copy of every generated plan, report, handoff, task contract, registry, or transaction record. Duplicating mutable state creates drift and makes recovery ambiguous.

Generated JSON contracts keep their stable field names. User-facing explanations can be provided in the preferred language without changing those fields.

## Agent Behavior

An Agent should:

1. use the user's requested language for explanations and narrative sections
2. preserve exact code, commands, paths, IDs, and proper nouns
3. create only the canonical runtime file unless a mirror is explicitly needed
4. identify which file remains authoritative when a mirror exists
5. avoid translating machine-readable status values or contract keys

## Related Guides

- [Getting Started](GETTING_STARTED.md)
- [Usage](USAGE.md)
- [Core Design](CORE_DESIGN.md)
