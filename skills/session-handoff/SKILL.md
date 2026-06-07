---
name: session-handoff
description: Use when the user asks for a project handoff, next-Agent summary, continuation notes, PROJECT_HANDOFF, or similar recovery context.
---

# Session Handoff

Use this skill when the user asks for a handoff, project handoff, next-Agent summary, continuation notes, `PROJECT_HANDOFF`, `交接文档`, `项目交接`, or similar recovery context.

## Output Policy

Default Agent-facing output:

```text
<PROJECT_ROOT>/PROJECT_HANDOFF.md
```

Optional user-facing Chinese mirror:

```text
<PROJECT_ROOT>/项目交接.md
```

Write the Agent-facing file first. Write the Chinese mirror only when the user explicitly asks for Chinese output or bilingual handoff sync.

`PROJECT_HANDOFF.md` is the Agent-facing source of truth. `项目交接.md` is only an optional user-facing Chinese mirror. If both files exist and conflict, treat `PROJECT_HANDOFF.md` as authoritative and update the mirror.

## Privacy Rules

Never write secrets, tokens, cookies, passwords, credentials, authorization headers, private memory dumps, or raw session logs into handoff files.

For public examples, use placeholders such as:

```text
<PROJECT_ROOT>
<MALTS_ROOT>
<HANDOFF_ARCHIVE_ROOT>
```

## Workflow

1. Inspect the current project state before writing conclusions.
2. Check git status when the workspace is a git repository.
3. Read relevant project instructions, `PROJECT_CONTROL.md`, current handoff, and key files.
4. Distinguish verified current facts from historical claims.
5. Write `PROJECT_HANDOFF.md`.
6. Optionally write `项目交接.md`.
7. Verify the output files exist before answering.

## Required Content

- generated time
- workspace or project root
- source context reviewed
- current status
- completed work
- pending work
- known risks
- verification already performed
- next recommended steps

