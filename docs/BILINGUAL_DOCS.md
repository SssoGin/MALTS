# Bilingual Documentation And Runtime Language Policy

MALTS defaults to English source documents for public release docs and Agent execution docs.

Project runtime artifacts are single canonical files by default. `PROJECT_CONTROL.md`, `WORK_TASK_REPORT.md`, and `PROJECT_HANDOFF.md` may use the user's or project's primary language for narrative content while keeping stable headings, fields, status values, IDs, paths, commands, and evidence levels readable for Agents.

## Canonical Runtime Artifacts

Use these files by default:

- `PROJECT_CONTROL.md`
- `WORK_TASK_REPORT.md`
- `PROJECT_HANDOFF.md`

Do not create full translated mirrors by default. Optional translated mirrors such as `项目控制.md`, `工作任务报告.md`, or `项目交接.md` are created only when the user explicitly asks for a separate translated file or an external workflow requires one. If a mirror exists and conflicts with the canonical file, treat the canonical file as authoritative.

## Public Documentation Mirrors

Public docs may still have English and Simplified Chinese pairs:

```text
docs/
docs/zh-CN/
```

Runtime template and checklist references are maintained in:

```text
runtime/EN/
runtime/CH/
```

These CH files are localized references, not a requirement to generate duplicate project artifacts.

## Rules

- English public docs and runtime EN docs are the release source of truth.
- Chinese docs and runtime CH files are user-facing review/reference mirrors, not independent sources.
- Agents should not load both EN and CH docs during normal execution.
- Read or update CH docs when the user explicitly asks for Chinese review, Chinese editing, comparison, or public documentation synchronization.
- Keep runtime project artifacts single-source by default; put Chinese narrative inside the canonical file instead of generating a duplicate mirror.
- Critical protocol changes must be reviewed for meaning, not only translated mechanically.
- If EN and CH public docs conflict, fix the English source first, then resynchronize the Chinese review copy.
- Chinese-facing docs, templates, and optional mirrors should be valid UTF-8. On Windows, prefer UTF-8 with BOM for Chinese-facing Markdown unless the surrounding project convention conflicts.

## Tooling

`tools/agent_system_lint.py check-doc-sync` does not require CH docs by default.
With `--require-ch`, it checks configured public document pairs and runtime reference pairs. It does not prove translation quality or semantic parity.

Default runtime check:

```powershell
python tools/agent_system_lint.py check-doc-sync --output-root runtime
```

Check runtime localized references:

```powershell
python tools/agent_system_lint.py check-doc-sync --output-root runtime --require-ch
```

Use the repository manifest when checking public bilingual docs:

```powershell
python tools/agent_system_lint.py check-doc-sync --output-root . --manifest tools/doc_pairs.json --require-ch
```

Check encoding:

```powershell
python tools/agent_system_lint.py check-encoding --malts-root . --require-ch-bom
```
