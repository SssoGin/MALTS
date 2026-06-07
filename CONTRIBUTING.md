# Contributing To MALTS

Contributions are welcome through issues and pull requests.

By submitting a pull request, you agree that your contribution is licensed under the MIT License used by this repository.

## Safety Requirements

Do not submit:

- API keys, tokens, cookies, credentials, passwords, or authorization headers
- user-specific configuration files
- local session logs or memory dumps
- real project handoff records
- machine-specific absolute paths
- cache files, compiled files, or generated private archives

Use placeholders in documentation:

```text
<USER_HOME>
<MALTS_ROOT>
<PROJECT_ROOT>
<HANDOFF_ARCHIVE_ROOT>
```

## Documentation Rules

- English runtime docs are the default source.
- Chinese/bilingual docs are optional and must not be loaded as default runtime context.
- Handoff examples must use fictional or placeholder content only.
- Keep adapters optional; do not assume a user wants all tools installed.

## Pull Request Checklist

- [ ] The change does not include secrets or private local data.
- [ ] Runtime behavior is documented when changed.
- [ ] Relevant templates/checklists/adapters were updated when needed.
- [ ] `tools/agent_system_lint.py` checks were run or the reason for skipping is stated.
