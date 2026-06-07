# Agent-Assisted Installation Protocol

When an Agent installs MALTS for a user, it must ask which target tool to install:

```text
Codex
Claude Code
OpenCode
AllIncluded
```

The Agent must not install all included adapters unless the user chooses `AllIncluded`.

## Required Flow

1. Read `README.md`, `docs/INSTALL.md`, and this file.
2. Ask which target tool to install.
3. Explain that shared skills from root `skills/` are support files, while tool instruction templates such as `AGENTS.md` and `CLAUDE.md` are optional MALTS enhancements. Ask whether to install or merge instruction templates into the target tool's actual instruction file.
4. Inspect the target configuration directory.
5. Show the planned file writes and possible conflicts.
6. Default to dry-run.
7. Do not overwrite existing files without explicit confirmation.
8. Do not read or copy secrets, sessions, memory dumps, or private local state.
9. Ask whether to enable bilingual documentation sync; default is disabled.
10. Run verification after installation.
11. Report exactly what changed.

## Shared Skills

MALTS has one canonical public skill source:

```text
skills/
```

Agent-assisted installation copies that directory into the selected tool's local skill directory:

```text
Codex      -> <target>\skills\
ClaudeCode -> <target>\skills\
OpenCode   -> <target>\skills\
```

Adapter directories provide tool-specific instruction templates, commands, agents, and configuration. They do not define separate public skill sources.

## Bilingual Docs

If the user enables bilingual documentation sync, the Agent should follow `docs/BILINGUAL_DOCS.md`. Chinese docs are user-facing references and are not default runtime context.
