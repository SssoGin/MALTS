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

## Contents

- `AGENTS.example.md` starting template for Codex instructions
- shared MALTS skills from the repository root `skills/` directory, installed into the target tool's `skills/` directory

Install maps `AGENTS.example.md` to `AGENTS.md`.

Review existing user files before copying. Do not overwrite without explicit confirmation.

## Runtime Rule

English runtime docs are default. Chinese/bilingual docs are optional and user-facing.

## Handoff

Default Agent-facing handoff file:

```text
PROJECT_HANDOFF.md
```

Optional Chinese mirror:

```text
项目交接.md
```
