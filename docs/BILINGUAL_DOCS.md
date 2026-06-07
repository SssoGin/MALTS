# Optional Bilingual Documentation Sync

MALTS defaults to English runtime documents.

Chinese documentation sync is optional and disabled by default.

## Why Optional

Benefits:

- easier review for Chinese-speaking users
- better human-readable onboarding
- useful bilingual comparison for critical process docs

Costs:

- more files to maintain
- higher review effort
- higher token usage if loaded incorrectly
- possible translation drift

## Rules

- English runtime docs are the release source of truth.
- Chinese docs are optional user-facing review mirrors, not an independent source.
- Agents should not load both EN and CH docs during normal execution.
- Read or update CH docs only when the user explicitly asks for Chinese review, Chinese output, comparison, or bilingual synchronization.
- Critical protocol changes must be reviewed for meaning, not only translated mechanically.
- If EN and CH conflict, fix the English source first, then resynchronize the Chinese review copy.

## Tooling

`tools/agent_system_lint.py check-doc-sync` does not require CH docs by default.
It checks document structure and configured pairs only; it does not prove translation quality or semantic parity.

The default runtime check stays English-only:

```powershell
python tools/agent_system_lint.py check-doc-sync --output-root runtime
```

Use the repository manifest when checking public bilingual docs:

```powershell
python tools/agent_system_lint.py check-doc-sync --output-root . --manifest tools/doc_pairs.json --require-ch
```
