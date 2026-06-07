# OpenCode Adapter

This adapter contains optional OpenCode scaffold files for MALTS.

## Install

Dry-run:

```powershell
.\scripts\Install-MALTS.ps1 -Tool OpenCode
```

Apply:

```powershell
.\scripts\Install-MALTS.ps1 -Tool OpenCode -Apply
```

## Contents

- `AGENTS.example.md` (installed as `AGENTS.md`)
- `opencode.json`
- `.opencode/agents/`
- shared MALTS skills from the repository root `skills/` directory, installed into the target `skills/` directory

Review existing user files before copying. Do not overwrite without explicit confirmation.

## Runtime Rule

English runtime docs are default. Chinese/bilingual docs are optional and user-facing.

## Handoff

Default Agent-facing handoff:

```text
PROJECT_HANDOFF.md
```
