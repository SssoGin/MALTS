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

Install maps `CLAUDE.example.md` to `CLAUDE.md`, installs shared skills, installs a `malts/` runtime copy, and generates `MALTS_BOOT.md`.

Review existing user files before copying. Do not overwrite without explicit confirmation.

## Runtime Rule

English runtime docs are default. Chinese runtime mirrors are used when Chinese user-facing output or bilingual synchronization is in scope.

Required MALTS artifact pairs for Chinese users:

```text
PROJECT_CONTROL.md / 项目控制.md
WORK_TASK_REPORT.md / 工作任务报告.md
```

Chinese-facing Markdown should be valid UTF-8. On Windows, prefer UTF-8 with BOM unless the local project convention conflicts.

## Multi-Agent Gate

Claude Code subagents may be used only after MALTS launch review and the user's explicit `确认运行`. Record model policy, dispatch evidence, and report recycling in `PROJECT_CONTROL.md`.

## Handoff

Default Agent-facing handoff:

```text
PROJECT_HANDOFF.md
```
