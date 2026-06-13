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
4. Explain that the MALTS runtime root and boot pointer are required for a normal new-machine install. The install plan should include `<target>\malts\` and `<target>\MALTS_BOOT.md` unless the user already has another reviewed `MALTS_ROOT` discovery path.
5. Inspect the target configuration directory.
6. Show the planned file writes and possible conflicts.
7. Default to dry-run.
8. Do not overwrite existing files without explicit confirmation.
9. Do not read or copy secrets, sessions, memory dumps, or user-specific generated state.
10. Ask whether to enable bilingual documentation sync; default is disabled for public docs, but bilingual runtime artifact pairs are required when Chinese user-facing output is in scope.
11. Run verification after installation.
12. Report exactly what changed.

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

## Runtime Discovery

Project initialization must be able to find the MALTS runtime root. A normal install therefore includes:

```text
<target>\malts\
<target>\MALTS_BOOT.md
```

`MALTS_BOOT.md` records the installed `MALTS_ROOT`. The Agent must verify that this root contains:

```text
README.md
skills/
runtime/EN/templates/
runtime/EN/checklists/
```

## Bilingual Docs

If the user enables bilingual documentation sync, the Agent should follow `docs/BILINGUAL_DOCS.md`. Chinese docs are user-facing references and are not default runtime context. When the current user or project operates in Chinese, `PROJECT_CONTROL.md` / `项目控制.md` and `WORK_TASK_REPORT.md` / `工作任务报告.md` are normative artifact pairs, not optional polish.
