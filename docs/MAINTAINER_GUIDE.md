# Maintainer Guide

This guide describes public-safe maintenance rules for MALTS. It is for humans and coding agents that need to update the public repository without depending on user-specific generated state.

## Maintenance Goals

- Keep `main` public-safe and installable.
- Preserve English runtime docs as the source of truth.
- Keep Simplified Chinese public docs synchronized when public docs change.
- Keep Codex, Claude Code, and OpenCode adapters aligned when adapter behavior changes.
- Prefer review-first changes: run dry-runs and checks before applying or releasing.

## Release Boundary

Allowed:

- public docs
- root `skills/` as the only public skill implementation source
- English runtime templates and checklists
- optional adapters
- lightweight tools
- safe install scripts

Never sync:

- release-control files
- handoff outputs
- project-specific design notes
- trial-run logs
- real user tool configuration
- sessions
- memory dumps
- caches
- secrets
- machine-specific paths
- user-specific archives
- generated migration packages
- unrelated project references
- extra public skill trees outside root `skills/`

Short rule: user-specific archives, generated migration packages, and unrelated project references do not enter the public package.

Use placeholders in public docs:

```text
<PROJECT_ROOT>
<MALTS_ROOT>
<USER_HOME>
<HANDOFF_ARCHIVE_ROOT>
```

Ignored paths may contain generated maintenance state. Those files are not part of the public release package.

## Update Policy

Agents should default to dry-run:

```text
show planned changes first
do not write files
do not commit
do not push
```

Only update files after explicit confirmation.

## Normal Update Flow

1. Make the smallest change that solves the maintenance task.
2. Update related public docs, templates, checklists, and adapters together.
3. Run the local checks listed below.
4. Commit the change with a focused message.
5. Push to GitHub and wait for CI to pass.
6. Release only after the checked commit is the intended public snapshot.

## Local Checks

Run these before pushing a public change:

```powershell
$version = (Get-Content -Raw VERSION).Trim()
python tools\agent_system_lint.py check-semantic-freshness --malts-root . --version $version
python tools\agent_system_lint.py check-doc-sync --output-root . --manifest tools\doc_pairs.json --require-ch
python tools\agent_system_lint.py check-doc-sync --output-root .\runtime --require-ch
python tools\agent_system_lint.py check-adapter-parity --malts-root .
python tools\agent_system_lint.py check-encoding --malts-root . --require-ch-bom
python tools\agent_system_lint.py check-public-safety --malts-root .
```

Run install previews for supported tools:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool Codex
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool ClaudeCode
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool OpenCode
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool AllIncluded
```

The install script defaults to dry-run mode. Do not use `-Apply` as a release check.

Run a real temporary install smoke test before publishing installer or runtime changes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Test-MALTSInstall.ps1 -Tool AllIncluded
```

The smoke test writes only to a guarded temporary directory and removes it after validating the installed layout.

## Continuous Integration

The repository uses GitHub Actions to run release hygiene checks on:

- pushes to `main`
- pull requests targeting `main`
- published releases
- manual workflow dispatches

CI runs on Windows because the install script is PowerShell-based and Windows execution-policy behavior is part of the supported install path.

## Skill Source Policy

MALTS public releases maintain one canonical skill source:

```text
<MALTS_ROOT>\skills\
```

The installer creates or updates one shared `MALTS_ROOT` and points each selected tool at that root through `MALTS_BOOT.md`. Tool config directories are thin adapter targets: they receive discovery-only skill bridges, but must not receive full `malts\` runtime copies or full skill implementation duplicates.

Keep public skills in the shared root directory, and keep adapter directories limited to tool-specific instruction templates, commands, agents, and configuration. Target tool directories are installation targets, not release-package facts.

All three public instruction examples must contain exactly one matching MALTS managed marker pair. Installer changes must prove append, in-place block update, legacy migration, idempotency, BOM/newline preservation, `Skip`, and explicit `Replace` behavior before release.

## Versioning

Use semantic versioning:

- Patch releases such as `v0.1.1`: documentation fixes, small script fixes, or compatibility fixes.
- Minor releases such as `v0.2.0`: new adapters, new skills, new public workflows, or behavior additions.
- Major releases such as `v1.0.0`: stable public contracts and intentional breaking changes after the project matures.

Before creating a new release:

1. Update `VERSION`.
2. Update `CHANGELOG.md`.
3. Run the local checks.
4. Push and confirm CI passes.
5. Create a GitHub Release from the checked commit.

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

## Agent Handoff For Maintainers

When a future Agent needs to continue MALTS maintenance, provide continuation context outside the public release package. The handoff should include:

- generated time
- repository root
- source context reviewed
- completed work
- pending work
- known risks
- verification already performed
- next recommended steps

Keep real handoff files outside release artifacts. Public examples must use placeholder content only.
