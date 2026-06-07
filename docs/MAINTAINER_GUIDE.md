# Maintainer Guide

This guide describes public-safe release maintenance rules.

## Release Boundary

Allowed:

- public docs
- root `skills/` as the only public skill source
- English runtime templates and checklists
- optional adapters
- lightweight tools
- safe install scripts

Never sync:

- local release-control files
- local handoff outputs
- old private design notes
- trial-run logs
- real user tool configuration
- sessions
- memory dumps
- caches
- secrets
- machine-specific paths
- local archives
- generated migration packages
- non-public companion project references
- extra public skill trees outside root `skills/`

Short rule: local archives, generated migration packages, or non-public companion project references do not enter the public package.

## Update Policy

Agents should default to dry-run:

```text
show planned changes first
do not write files
do not commit
do not push
```

Only update files after explicit confirmation.

## Skill Source Policy

MALTS public releases maintain one canonical skill source:

```text
skills/
```

The installer distributes that directory to supported Agent tools. Keep public skills in this root directory, and keep adapter directories limited to tool-specific instruction templates, commands, agents, and configuration. Tool-local skill directories are installation targets, not release-package facts.

## Before Public Release

- Review `README.md`.
- Review `LICENSE`.
- Review `CONTRIBUTING.md`.
- Run sensitive scans.
- Add community files only when needed:
  - `CODE_OF_CONDUCT.md`
  - `.github/PULL_REQUEST_TEMPLATE.md`
  - `.github/ISSUE_TEMPLATE/`
- Confirm repository visibility change intentionally.
