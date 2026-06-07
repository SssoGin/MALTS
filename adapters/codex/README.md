# Codex Adapter

This adapter provides Codex-facing instructions for using MALTS.

## Install

Review first:

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex
```

Apply after review:

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex -Apply
```

## Files

- `AGENTS.example.md` is a starting template for Codex instructions.
- Shared MALTS skills are installed from the repository root `skills/` directory into the target `skills/` directory.
- Do not overwrite an existing user `AGENTS.md` without reviewing it first.
- Keep repository templates and checklists under `runtime/EN` available to the installed adapter.

## Handoff

Default Agent-facing handoff file:

```text
PROJECT_HANDOFF.md
```

Optional Chinese mirror:

```text
项目交接.md
```
