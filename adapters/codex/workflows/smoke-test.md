# Codex Workflow: MALTS Smoke Test

Use this workflow after installing or updating MALTS for Codex.

Minimum checks:

1. Confirm `AGENTS.md` exists in the Codex target.
2. Confirm `MALTS_BOOT.md` resolves to a root containing `README.md`, `skills/`, `runtime/EN/templates`, and `runtime/EN/checklists`.
3. Confirm the Codex target does not contain a default tool-local `malts/` runtime copy or `skills/` duplicate.
4. Confirm `config.toml` and `agents/*.toml` exist when Codex subagent scaffold is installed.
5. Start a dry-run MALTS project init in a temporary workspace and verify that canonical control/report artifacts are created without translated mirrors unless explicitly requested.
