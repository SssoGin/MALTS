---
name: session-handoff
description: Use when the user asks for a project handoff, next-Agent summary, continuation notes, PROJECT_HANDOFF, or similar recovery context.
---

# Session Handoff

Use this skill when the user asks for a handoff, project handoff, next-Agent summary, continuation notes, `PROJECT_HANDOFF`, `交接文档`, `项目交接`, or similar recovery context.

## Output Policy

Default canonical output:

```text
<PROJECT_ROOT>/PROJECT_HANDOFF.md
```

`PROJECT_HANDOFF.md` is the single handoff source of truth by default. Include a short English `Agent Brief` at the top for machine/agent scanning, then write the remaining sections in the user's or project's primary language.

Optional full translated mirror:

```text
<PROJECT_ROOT>/项目交接.md
```

Create or update the optional mirror only when the user explicitly asks for Chinese handoff output as a separate file or a workflow requires a full translated copy. If both files exist and conflict, treat `PROJECT_HANDOFF.md` as authoritative.

## Privacy Rules

Never write secrets, tokens, cookies, passwords, credentials, authorization headers, sensitive memory dumps, or raw session logs into handoff files.

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
6. Optionally write `项目交接.md` only when explicitly requested.
7. Verify the output files exist before answering.

## Required Content

- English Agent Brief
- generated time
- workspace or project root
- source context reviewed
- current status
- completed work
- pending work
- known risks
- verification already performed
- next recommended steps
