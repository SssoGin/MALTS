# Tools

`agent_system_lint.py` provides lightweight checks and generators for MALTS release repositories.

## Commands

```powershell
python tools/agent_system_lint.py check-project-control --project-control PROJECT_CONTROL.md
python tools/agent_system_lint.py check-project-control --project-control PROJECT_CONTROL.md --malts-root <MALTS_ROOT>
python tools/agent_system_lint.py next-task-id --project-control PROJECT_CONTROL.md
python tools/agent_system_lint.py new-project-control --project <PROJECT_NAME> --goal <GOAL>
python tools/agent_system_lint.py check-doc-sync --output-root runtime
python tools/agent_system_lint.py check-doc-sync --output-root runtime --require-ch
python tools/agent_system_lint.py check-doc-sync --output-root . --manifest tools/doc_pairs.json --require-ch
python tools/agent_system_lint.py check-adapter-parity --malts-root .
python tools/agent_system_lint.py check-encoding --malts-root . --require-ch-bom
python tools/agent_system_lint.py check-public-safety --malts-root .
python tools/agent_system_lint.py check-install-layout --install-root <TARGET> --tool Codex
python tools/agent_system_lint.py check-managed-instruction-sync --malts-root <MALTS_ROOT> --install-root <TOOL_ROOT> --tool Codex
python tools/agent_system_lint.py check-semantic-freshness --malts-root .
```

Chinese public doc sync is optional unless release scope requires it. Runtime EN/CH artifact pairs are checked with `check-doc-sync --output-root runtime --require-ch`.

`check-doc-sync` is a structural check. With `--require-ch`, it verifies configured document pairs and requires each Chinese document to match the English heading count and heading-level sequence. For `runtime`, built-in runtime EN/CH pairs are used even without a manifest. It does not validate translation quality, semantic equivalence, or whether a Chinese review copy is ready for release. Critical protocol wording still needs human or main-controller review.

`check-adapter-parity` verifies required Codex, Claude Code, and OpenCode adapter scaffold files, required protocol tokens, and exactly one valid MALTS managed instruction marker pair in every tool instruction example.

`check-project-control --malts-root <MALTS_ROOT>` verifies that current MALTS version metadata in `PROJECT_CONTROL.md` matches `<MALTS_ROOT>/VERSION`. Without `--malts-root` or `--malts-version`, it performs only structure and status-table checks.

`check-encoding` verifies text files are valid UTF-8 and, with `--require-ch-bom`, requires Chinese-facing Markdown surfaces to use UTF-8 with BOM.

`check-public-safety` verifies that release-safe text files do not contain known machine-specific path literals or high-confidence secret value patterns.

`check-install-layout` verifies an applied thin tool adapter target, including `MALTS_BOOT.md`, managed manifests, the resolved shared `MALTS_ROOT`, required shared runtime files, tool-specific scaffold files, and six lightweight skill bridges. It fails if the shared root is nested in the tool target or a bridge contains a full runtime duplicate. It is used by `scripts/Test-MALTSInstall.ps1`.

`check-managed-instruction-sync` compares only the MALTS managed block in an installed tool instruction file against the adapter source. Text outside the managed markers remains user-owned and is ignored.

`check-semantic-freshness` verifies required release surfaces and semantic tokens, and rejects stale path models, private-release wording, encoding corruption markers, and legacy rules that create translated runtime artifacts by default.
