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
4. Explain that `skills/` under the shared `MALTS_ROOT` is the only skill implementation source. Tool-local `skills/` contains only lightweight discovery bridges.
5. Explain that tool instruction templates such as `AGENTS.md` and `CLAUDE.md` are optional MALTS enhancements. Default to `InstructionMode ManagedMerge`, which owns only the marked MALTS block; offer `Skip`, and require explicit confirmation before full-file `Replace`.
6. Explain that each tool needs `MALTS_BOOT.md`, but it should point to the shared `MALTS_ROOT`; the install plan should not include a full `<target>\malts\` runtime copy by default.
7. Explain that installed instruction sync can be verified with `check-managed-instruction-sync`, which compares only the MALTS managed block and ignores user-owned text outside the markers.
8. Inspect the target configuration directory.
9. Show the planned file writes, shared root location, and possible conflicts.
10. Default to dry-run.
11. Preserve user-owned instruction text outside the MALTS markers. Do not overwrite other existing files without explicit confirmation.
12. Do not read or copy secrets, sessions, memory dumps, or user-specific generated state.
13. Ask whether to enable bilingual documentation sync for public docs; default runtime project artifacts remain single canonical files, with optional translated mirrors only on explicit request.
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

When using `Install-MALTS.ps1`, the default shared root is `%USERPROFILE%\.malts`. `-TargetRoot` changes only the tool target. Use `-SharedRoot` when the user chooses another reviewed location, and reject layouts where the shared root is nested in a tool target or vice versa.

## Tool Adapter Layer

Adapter directories provide tool-specific instruction templates, commands, agents, and configuration. They do not define separate public skill sources.

Normal install layout:

```text
<tool-config-root>\MALTS_BOOT.md
<tool-config-root>\<tool adapter files>
<tool-config-root>\skills\<MALTS-skill>\SKILL.md  # lightweight bridge only
```

Invalid layouts:

```text
<tool-config-root>\malts\
<tool-config-root>\skills\<MALTS-skill>\scripts\  # runtime implementation duplicate
<tool-config-root>\skills\<MALTS-skill>\SKILL.md  # larger than the bridge contract
```

If a full runtime path or non-bridge skill package appears in the install plan, stop and correct the plan before applying.

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

If the user enables bilingual documentation sync, the Agent should follow `docs/BILINGUAL_DOCS.md`. Chinese docs are user-facing references and are not default runtime context. Project runtime artifacts are single canonical files by default: put Chinese narrative in `PROJECT_CONTROL.md`, `WORK_TASK_REPORT.md`, and `PROJECT_HANDOFF.md`, and create full translated mirrors only when explicitly requested.
