# Installing MALTS

MALTS is installed by choosing one or more Agent tool adapters and copying reviewed scaffold files into the matching tool configuration area. Shared MALTS skills are maintained once under the repository root `skills/` directory and are installed into each target tool's local `skills/` directory.

The recommended first step is dry-run:

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex
```

If Windows PowerShell blocks script execution, use a process-local execution policy override:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool Codex
```

No files are changed unless `-Apply` is provided:

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex -Apply
```

Instruction templates are optional. They can improve MALTS behavior by adding tool-specific reminders for task mode, Grill-Me Preflight, project control, handoff, and verification. Review and merge them with existing user or project instructions before applying.

To skip instruction templates:

```powershell
.\scripts\Install-MALTS.ps1 -Tool ClaudeCode -SkipInstructionTemplate
```

## Supported Tools

```text
Codex
ClaudeCode
OpenCode
AllIncluded
```

## Defaults

- Shared skills from `skills/` are included by default.
- Runtime templates and checklists remain under `runtime/EN`.
- Bilingual documentation sync is disabled by default.
- Codex can install `AGENTS.md`; Claude Code can install `CLAUDE.md`; OpenCode can install `AGENTS.example.md` as `AGENTS.md` plus `opencode.json`.
- Use `-SkipInstructionTemplate` when the user wants MALTS support files and shared skills without changing Agent instruction files.
- Existing files are not overwritten unless the user explicitly allows it.
- The installer prints a plan before writing.

## Skill Install Paths

The repository has one canonical skill source:

```text
skills/
```

The installer copies those skills to the target tool's discovery directory:

```text
Codex      -> <target>\skills\
ClaudeCode -> <target>\skills\
OpenCode   -> <target>\skills\
```

Adapter directories provide tool-specific instruction templates, commands, agents, and configuration. Shared MALTS skills are always installed from the repository root `skills/` directory.

## Manual Install

1. Read `README.md`.
2. Choose the target tool adapter.
3. Review the adapter directory under `adapters/`.
4. Copy only the files needed for that tool.
5. Copy root `skills/` into the tool's local `skills/` directory.
6. Keep `runtime/EN/templates` and `runtime/EN/checklists` available to the installed adapter.
7. Run the relevant smoke test or lint command.

See `docs/AGENT_INSTALL.md` for Agent-assisted installation rules.
