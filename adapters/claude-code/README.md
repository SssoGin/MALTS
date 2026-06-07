# Claude Code Adapter

This adapter contains optional Claude Code scaffold files for MALTS.

## Install

Dry-run:

```powershell
.\scripts\Install-MALTS.ps1 -Tool ClaudeCode
```

Apply:

```powershell
.\scripts\Install-MALTS.ps1 -Tool ClaudeCode -Apply
```

## Contents

- `CLAUDE.example.md` starting template for Claude Code instructions
- `.claude/agents/`
- `.claude/commands/`
- shared MALTS skills from the repository root `skills/` directory, installed into the target tool's `skills/` directory

Install maps `CLAUDE.example.md` to `CLAUDE.md`.

Review existing user files before copying. Do not overwrite without explicit confirmation.

## Runtime Rule

English runtime docs are default. Chinese/bilingual docs are optional and user-facing.

## Handoff

Default Agent-facing handoff:

```text
PROJECT_HANDOFF.md
```
