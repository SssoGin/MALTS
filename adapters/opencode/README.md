# OpenCode Adapter

Use this adapter from a verified MALTS user payload. It supplies the
OpenCode instruction template, agent definitions, and settings required by a
MALTS project.

## Install through the lifecycle

1. Verify the downloaded package before extraction.
2. Create and review a lifecycle plan for the OpenCode tool root.
3. Execute only the reviewed plan hash.

The lifecycle writes the OpenCode projection into the selected tool root and
records its exact generation identity. Do not copy adapter files by hand.

## Included runtime material

- `AGENTS.example.md`: managed MALTS instruction block for a project.
- `.opencode/agents/`: optional MALTS role definitions.
- `opencode.json`: OpenCode adapter settings.

See the user [installation guide](../../docs/INSTALL.md) and
[usage guide](../../docs/USAGE.md).
