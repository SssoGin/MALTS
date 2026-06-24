# Updating MALTS

MALTS has two update paths:

- User update: pull a newer public package and reinstall MALTS-managed files into the shared `MALTS_ROOT` and selected thin tool adapters.
- Maintainer update: change this release repository and prepare a new public snapshot.

## User Update

Use a git clone of the public MALTS repository. The update script is review-first and defaults to dry-run:

```powershell
.\scripts\Update-MALTS.ps1 -Tool Codex
.\scripts\Update-MALTS.ps1 -Tool Codex -Apply
.\scripts\Update-MALTS.ps1 -Tool AllIncluded -Strategy MergeSafe
.\scripts\Update-MALTS.review.cmd -Tool Codex
```

Use `-SharedRoot <path>` when the installed shared root is not the default location:

```powershell
.\scripts\Update-MALTS.ps1 -Tool AllIncluded -SharedRoot <MALTS_ROOT>
```

Modes:

- `PullAndInstall`: check the remote branch, pull if needed, then install.
- `PullOnly`: only update the repository clone.
- `InstallOnly`: install from the already downloaded package.

Strategies:

- `MergeSafe`: update shared runtime, boot pointers, bridges, and unchanged MALTS-managed support files. Its default `InstructionMode ManagedMerge` creates, updates, or migrates exactly one marked MALTS instruction block while preserving surrounding user text.
- `Overwrite`: update MALTS-managed files. It defaults to `InstructionMode Replace`, which replaces the complete tool instruction file and should be used only intentionally.

Instruction modes are independent and explicit: `ManagedMerge` is the safe default, `Skip` leaves the instruction file untouched, and `Replace` requires `Overwrite`. Ambiguous or incomplete marker sets stop with an error instead of guessing. Managed manifests remove only unchanged stale MALTS files; repeated managed merges are idempotent.

After an update, use `check-managed-instruction-sync` if you need to prove that an installed `AGENTS.md` or `CLAUDE.md` managed block matches the current adapter source while preserving user-owned text outside the markers.

If the remote branch is already current, the script prints `Already up to date` and skips installation. Use `-Reinstall` to reinstall the current version intentionally. If an update is available and the working tree has local changes, `-Apply` refuses to pull unless `-AllowDirty` is provided after review.

## Layout Rules

Current updates should preserve this layout:

```text
<MALTS_ROOT>\README.md
<MALTS_ROOT>\skills\
<MALTS_ROOT>\runtime\
<MALTS_ROOT>\tools\
<MALTS_ROOT>\scripts\
<tool-config-root>\MALTS_BOOT.md
<tool-config-root>\<adapter files>
<tool-config-root>\skills\<MALTS-skill>\SKILL.md  # discovery bridge only
```

The updater must not create a full `<tool-config-root>\malts\` copy or tool-local full skill implementation. Modified stale files are preserved and reported.

## Install Verification

Maintainers can test a real temporary install:

```powershell
.\scripts\Test-MALTSInstall.ps1 -Tool AllIncluded
```

This script installs into a guarded temporary directory, validates the shared `MALTS_ROOT`, manifests, each selected tool's `MALTS_BOOT.md`, adapter scaffold, and lightweight bridges, then removes the temporary directory unless `-KeepTemp` is provided.

The same installed layout check can be run directly:

```powershell
python tools\agent_system_lint.py check-install-layout --install-root <TOOL_TARGET> --tool Codex
```

## Maintainer Update Flow

1. Start with dry-run.
2. Compare source MALTS runtime assets against this release repository.
3. Sync only approved release content.
4. Keep shared `MALTS_ROOT` as the only default runtime and skill source.
5. Do not sync handoff output, release-control state, project-specific design notes, trial runs, caches, sessions, real tool configs, user-specific archives, generated migration packages, or unrelated project references.
6. When reusable Agent guidance changes, sync only stable MALTS-relevant public guidance into adapter examples. Preserve public-safe confirmation and skill-recommendation rules. Exclude personal language defaults, machine-specific paths, user-specific archive paths, package-maintenance-only rules, and environment-specific wording.
7. Keep third-party attribution current when public guidance is inspired by or adapted from upstream projects.
8. Update `VERSION` and `CHANGELOG.md` when preparing a new public release.
9. When writing project-control metadata, resolve the active boot file and read `<MALTS_ROOT>/VERSION`; do not copy current versions from old control, report, handoff, or template files.
9. Run sensitive scans.
10. Run lint checks.
11. Review the diff before committing.
12. Use GitHub Desktop or Git CLI to commit and push.

The repository should remain safe to make public before any visibility change.
