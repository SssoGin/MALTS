# MALTS Language Model

MALTS provides English and Simplified Chinese user documentation, templates, and checklists while keeping project state canonical and compact.

## User Documentation

Root and `docs/` English files are the stable technical reference. `README.zh-CN.md` and `docs/zh-CN/` provide Simplified Chinese user guides with equivalent topics and heading structure.

Users may read either language. Commands, paths, schema fields, IDs, status values, and Skill names remain unchanged across languages.

## Runtime Templates

- `runtime/EN/` contains English templates and checklists.
- `runtime/CH/` contains Simplified Chinese templates and checklists.

When `NarrativeLanguage` is Simplified Chinese, an Agent may use the CH templates as drafting references while preserving the stable schema markers and machine-readable values required by MALTS.

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
