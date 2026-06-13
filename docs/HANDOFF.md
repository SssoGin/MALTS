# Handoff

MALTS uses handoff files to make long work recoverable across windows, interruptions, and Agent changes.

## Default File Names

Agent-facing English default:

```text
PROJECT_HANDOFF.md
```

Optional user-facing Chinese mirror:

```text
项目交接.md
```

## Rules

- Generate the Agent-facing handoff first.
- Chinese mirrors are optional and user-facing.
- Do not write secrets, tokens, cookies, passwords, credentials, sensitive memory dumps, or raw session logs into handoff files.
- Use placeholders for public examples.
- Real handoff files belong in the user's project workspace, not in the MALTS release repository.

## What To Include

- generated time
- current workspace
- current goal
- completed work
- pending work
- verification already performed
- known risks
- next recommended steps

Use `runtime/EN/templates/PROJECT_HANDOFF.template.en.md`.
