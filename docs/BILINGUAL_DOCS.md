# Bilingual Documentation And Runtime Artifact Sync

MALTS defaults to English runtime documents for Agent execution.

Chinese public documents and runtime mirrors are not independent sources of truth, but some bilingual artifacts are normative when Chinese user-facing output or bilingual mode is in scope.

## Normative Pairs

These pairs must be created and kept substantively synchronized when the project uses Chinese user-facing state or bilingual mode:

- `PROJECT_CONTROL.md` and `项目控制.md`
- `WORK_TASK_REPORT.md` and `工作任务报告.md`
- `PROJECT_HANDOFF.md` and `项目交接.md` when a Chinese handoff mirror is requested or required by the project

Runtime template and checklist mirrors are maintained in the release package:

```text
runtime/EN/
runtime/CH/
```

## Rules

- English runtime docs are the release source of truth.
- Chinese docs and runtime mirrors are user-facing review mirrors, not independent sources.
- Agents should not load both EN and CH docs during normal execution.
- Read or update CH docs when the user explicitly asks for Chinese review, Chinese output, comparison, or bilingual synchronization.
- Do not downgrade required bilingual runtime artifacts into optional polish when the current user or project operates in Chinese.
- Critical protocol changes must be reviewed for meaning, not only translated mechanically.
- If EN and CH conflict, fix the English source first, then resynchronize the Chinese review copy.
- Chinese-facing docs, templates, and reports should be valid UTF-8. On Windows, prefer UTF-8 with BOM for Chinese-facing Markdown unless the surrounding project convention conflicts.

## Tooling

`tools/agent_system_lint.py check-doc-sync` does not require CH docs by default.
With `--require-ch`, it checks configured document pairs and requires each Chinese document to match the English heading count and heading-level sequence. When the document root is `runtime`, the built-in runtime EN/CH pairs are checked even without a manifest. It does not prove translation quality or semantic parity.

The default runtime check stays English-only:

```powershell
python tools/agent_system_lint.py check-doc-sync --output-root runtime
```

Require runtime Chinese mirrors:

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
