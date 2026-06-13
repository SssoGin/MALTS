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
- `.codex/config.toml` project-scoped Codex subagent scaffold configuration
- `.codex/agents/*.toml` Codex-native custom subagent role scaffolds
- `workflows/*.md` plain workflow prompts for Codex usage; these are not custom slash commands
- shared MALTS skills from the repository root `skills/` directory, installed into the target tool's `skills/` directory

Install maps `AGENTS.example.md` to `AGENTS.md`, copies `.codex` scaffold files, installs shared skills, installs a `malts/` runtime copy, and generates `MALTS_BOOT.md`.

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

Codex subagents may be used only after MALTS launch review and the user's explicit `确认运行`. Record model policy, dispatch evidence, and report recycling in `PROJECT_CONTROL.md`.

Codex supports project-scoped custom subagents through `.codex/config.toml` and `.codex/agents/*.toml`. Do not present `workflows/*.md` as Codex custom slash commands.

## Handoff

Default Agent-facing handoff file:

```text
PROJECT_HANDOFF.md
```

Optional Chinese mirror:

```text
项目交接.md
```
