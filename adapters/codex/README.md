# Codex Adapter

Use this adapter from a verified MALTS user payload. It provides the
Codex-specific instruction template, agent definitions, and workflows that
MALTS projects need at runtime.

## Install through the lifecycle

1. Verify the downloaded package before extraction.
2. Create and review a lifecycle plan for the Codex tool root.
3. Execute only the reviewed plan hash.

The lifecycle copies the Codex projection into the selected tool root and
records its exact generation identity. Do not copy these files manually.

## Included runtime material

- `AGENTS.example.md`: managed MALTS instruction block for a project.
- `.codex/agents/`: optional MALTS role definitions.
- `.codex/config.toml`: Codex adapter configuration.
- `workflows/`: start, verify, retrospective, and smoke-check guidance.

See the user [installation guide](../../docs/INSTALL.md) and
[usage guide](../../docs/USAGE.md).
