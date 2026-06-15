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
3. Explain that MALTS uses one shared `MALTS_ROOT` plus thin tool adapters.
4. Explain that `skills/` under the shared `MALTS_ROOT` is the only installed skill source. Do not install tool-local `skills/`.
5. Explain that tool instruction templates such as `AGENTS.md` and `CLAUDE.md` are optional MALTS enhancements. Ask whether to install or merge instruction templates into the target tool's actual instruction file.
6. Explain that each tool needs `MALTS_BOOT.md`, but it should point to the shared `MALTS_ROOT`; the install plan should not include a full `<target>\malts\` runtime copy by default.
7. Inspect the target configuration directory.
8. Show the planned file writes, shared root location, and possible conflicts.
9. Default to dry-run.
10. Do not overwrite existing files without explicit confirmation.
11. Do not read or copy secrets, sessions, memory dumps, or user-specific generated state.
12. Ask whether to enable bilingual documentation sync; default is disabled for public docs, but bilingual runtime artifact pairs are required when Chinese user-facing output is in scope.
13. Run verification after installation.
14. Report exactly what changed.

## Shared Root

MALTS has one canonical public skill and runtime root per installation:

```text
MALTS_ROOT
```

The shared root must contain:

```text
README.md
skills/
runtime/EN/templates/
runtime/EN/checklists/
tools/
scripts/
```

When using `Install-MALTS.ps1`, the default shared root is `%USERPROFILE%\.malts`. When `-TargetRoot` is provided, the default shared root is `<TargetRoot>\MALTS_ROOT`. Use `-SharedRoot` when the user chooses another reviewed location.

## Tool Adapter Layer

Adapter directories provide tool-specific instruction templates, commands, agents, and configuration. They do not define separate public skill sources.

Normal install layout:

```text
<tool-config-root>\MALTS_BOOT.md
<tool-config-root>\<tool adapter files>
```

Invalid layouts:

```text
<tool-config-root>\malts\
<tool-config-root>\skills\
```

If either path appears in the install plan, stop and correct the plan before applying.

## Runtime Discovery

Project initialization must be able to find the shared MALTS runtime root. A normal install therefore includes:

```text
<tool-config-root>\MALTS_BOOT.md
```

`MALTS_BOOT.md` records the shared `MALTS_ROOT`. The Agent must verify that this root contains:

```text
README.md
skills/
runtime/EN/templates/
runtime/EN/checklists/
```

## Encoding

On Windows, do not rely on the system default encoding. Scripts, command output, and document checks should explicitly use UTF-8. Python scripts should prefer `encoding='utf-8'`; when needed, set `PYTHONUTF8=1` or explicitly reconfigure `stdout` and `stderr` to UTF-8.

## Bilingual Docs

If the user enables bilingual documentation sync, the Agent should follow `docs/BILINGUAL_DOCS.md`. Chinese docs are user-facing references and are not default runtime context. When the current user or project operates in Chinese, `PROJECT_CONTROL.md` / `项目控制.md` and `WORK_TASK_REPORT.md` / `工作任务报告.md` are normative artifact pairs, not optional polish.
