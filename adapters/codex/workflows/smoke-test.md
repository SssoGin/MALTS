# Codex Workflow: MALTS Smoke Test

Use this workflow after installing or updating MALTS for Codex.

Minimum checks:

1. Confirm `AGENTS.md` exists in the Codex target.
2. Confirm `MALTS_BOOT.md` resolves to a root containing `README.md`, `skills/`, `runtime/EN/templates`, and `runtime/EN/checklists`.
3. Confirm the Codex target does not contain a default tool-local `malts/` runtime copy or `skills/` duplicate.
4. Confirm `config.toml` and `agents/*.toml` exist when Codex subagent scaffold is installed.
5. Start a dry-run MALTS long-workspace init in a temporary workspace and verify CURRENT `single_phase`, one initial Phase, no Session, no coordination state, and no translated mirror unless explicitly requested.
6. Apply only inside that isolated temporary fixture, run repeated fresh-process `workspace-entry`, and verify bounded reads, zero history/writes/entity creation, and exact byte/timestamp stability.
7. In a separate isolated fixture, exercise `resource_admission` with disjoint and conflicting generic locators, stale fencing, `UNKNOWN`, and reconcile; do not use product-specific rules.
