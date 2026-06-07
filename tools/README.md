# Tools

`agent_system_lint.py` provides lightweight checks and generators for MALTS release repositories.

## Commands

```powershell
python tools/agent_system_lint.py check-project-control --project-control PROJECT_CONTROL.md
python tools/agent_system_lint.py next-task-id --project-control PROJECT_CONTROL.md
python tools/agent_system_lint.py check-doc-sync --output-root runtime
python tools/agent_system_lint.py check-doc-sync --output-root . --manifest tools/doc_pairs.json --require-ch
python tools/agent_system_lint.py check-semantic-freshness --malts-root .
```

Chinese doc sync is optional. Use the repository manifest when checking public bilingual docs with `--require-ch`.

`check-doc-sync` is a structural check. With `--require-ch` and a manifest, it verifies configured document pairs and requires each Chinese document to match the English heading count and heading-level sequence. It does not validate translation quality, semantic equivalence, or whether a Chinese review copy is ready for release. Critical protocol wording still needs human or main-controller review.
