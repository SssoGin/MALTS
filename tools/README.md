# Tools

`agent_system_lint.py` provides lightweight checks and generators for MALTS release repositories.

## Commands

```powershell
python tools/agent_system_lint.py check-project-control --project-control PROJECT_CONTROL.md
python tools/agent_system_lint.py next-task-id --project-control PROJECT_CONTROL.md
python tools/agent_system_lint.py new-project-control --malts-root . --project-root .
python tools/agent_system_lint.py check-doc-sync --output-root runtime
python tools/agent_system_lint.py check-doc-sync --output-root runtime --require-ch
python tools/agent_system_lint.py check-doc-sync --output-root . --manifest tools/doc_pairs.json --require-ch
python tools/agent_system_lint.py check-adapter-parity --malts-root .
python tools/agent_system_lint.py check-encoding --malts-root . --require-ch-bom
python tools/agent_system_lint.py check-public-safety --malts-root .
python tools/agent_system_lint.py check-install-layout --install-root <TARGET> --tool Codex
python tools/agent_system_lint.py check-semantic-freshness --malts-root .
```

Chinese public doc sync is optional unless release scope requires it. Runtime EN/CH artifact pairs are checked with `check-doc-sync --output-root runtime --require-ch`.

`check-doc-sync` is a structural check. With `--require-ch`, it verifies configured document pairs and requires each Chinese document to match the English heading count and heading-level sequence. For `runtime`, built-in runtime EN/CH pairs are used even without a manifest. It does not validate translation quality, semantic equivalence, or whether a Chinese review copy is ready for release. Critical protocol wording still needs human or main-controller review.

`check-adapter-parity` verifies required Codex, Claude Code, and OpenCode adapter scaffold files and required protocol tokens.

`check-encoding` verifies text files are valid UTF-8 and, with `--require-ch-bom`, requires Chinese-facing Markdown surfaces to use UTF-8 with BOM.

`check-public-safety` verifies that release-safe text files do not contain known machine-specific path literals or high-confidence secret value patterns.

`check-install-layout` verifies an applied installation target, including `MALTS_BOOT.md`, installed `malts/runtime`, required skills, and tool-specific scaffold files. It is used by `scripts/Test-MALTSInstall.ps1`.
