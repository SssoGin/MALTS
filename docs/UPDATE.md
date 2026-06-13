# Updating MALTS

MALTS has two update paths:

- User update: pull a newer public package and reinstall MALTS-managed files into a tool directory.
- Maintainer update: change this release repository and prepare a new public snapshot.

## User Update

Use a git clone of the public MALTS repository. The update script is review-first and defaults to dry-run:

```powershell
.\scripts\Update-MALTS.ps1 -Tool Codex
.\scripts\Update-MALTS.ps1 -Tool Codex -Apply
.\scripts\Update-MALTS.ps1 -Tool AllIncluded -Strategy MergeSafe
.\scripts\Update-MALTS.review.cmd -Tool Codex
```

Modes:

- `PullAndInstall`: check the remote branch, pull if needed, then install.
- `PullOnly`: only update the repository clone.
- `InstallOnly`: install from the already downloaded package.

Strategies:

- `MergeSafe`: update MALTS-managed runtime, skills, docs, tools, and adapter support files without replacing the user's top-level instruction file.
- `Overwrite`: update MALTS-managed files and replace tool instruction templates when the user intentionally wants that.

If the remote branch is already current, the script prints `Already up to date`. If the working tree has local changes, `-Apply` refuses to pull unless `-AllowDirty` is provided after review.

## Install Verification

Maintainers can test a real temporary install:

```powershell
.\scripts\Test-MALTSInstall.ps1 -Tool AllIncluded
```

This script installs into a guarded temporary directory, validates `MALTS_BOOT.md`, `malts/runtime`, `malts/skills`, tool scaffold files, and `malts/tools/agent_system_lint.py`, then removes the temporary directory unless `-KeepTemp` is provided.

The same installed layout check can be run directly:

```powershell
python tools\agent_system_lint.py check-install-layout --install-root <TARGET> --tool Codex
```

## Maintainer Update Flow

1. Start with dry-run.
2. Compare source MALTS runtime assets against this release repository.
3. Sync only approved release content.
4. Keep root `skills/` as the only public skill source.
5. Do not sync handoff output, release-control state, project-specific design notes, trial runs, caches, sessions, real tool configs, user-specific archives, generated migration packages, or unrelated project references.
6. When reusable Agent guidance changes, sync only stable MALTS-relevant public guidance into adapter examples. Preserve public-safe confirmation and skill-recommendation rules. Exclude personal language defaults, machine-specific paths, user-specific archive paths, package-maintenance-only rules, and environment-specific wording.
7. Keep third-party attribution current when public guidance is inspired by or adapted from upstream projects.
8. Update `VERSION` and `CHANGELOG.md`.
9. Run sensitive scans.
10. Run lint checks.
11. Review the diff before committing.
12. Use GitHub Desktop or Git CLI to commit and push.

The repository should remain safe to make public before any visibility change.
