# Security

MALTS is a workflow system and should not store private runtime secrets.

## Do Not Commit

Do not commit:

- API keys
- tokens
- cookies
- passwords
- credentials
- authorization headers
- local session logs
- memory dumps
- private tool configuration
- real project handoff records
- machine-specific absolute paths

## Before Publishing Scan

Before publishing or pushing, run a sensitive information scan.

Suggested patterns:

```powershell
rg -n "OPENAI_API_KEY|ANTHROPIC_API_KEY|GITHUB_TOKEN|token|secret|password|cookie|Authorization|Bearer|oauth|api_key" .
rg -n "<replace with local user or workspace path patterns before publishing>" .
```

## Allowed Public Attribution

Allowed public attribution:

```text
Copyright (c) 2026 Gin
```
