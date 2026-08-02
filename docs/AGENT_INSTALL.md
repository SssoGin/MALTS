# Agent-Assisted Installation

This policy applies when an AI Agent helps a user verify, install, update, repair, recover, or uninstall MALTS.

## Source Selection

The repository is the primary source. An Agent must not automatically download the optional Release ZIP merely because it is available.

Before repository installation or update, the Agent must:

1. Read `MALTS_RELEASE.json` and `VERSION` from the selected repository root.
2. Verify that their version, release ID, source-tree hash, and file count are internally consistent.
3. If Git metadata is available, report whether the checked-out tag matches `release_tag`.
4. Stop if the repository contains unexpected files, cache, `.malts` residue, a reparse point, or an identity mismatch.

The optional single ZIP is permitted only when the user explicitly chooses an offline/fixed archive path or the verified repository source is unavailable. Verify it with the exact-source `Verify-MALTSBootstrap.ps1` before extraction.

## Required Sequence

1. Read [Install](INSTALL.md), [Lifecycle](LIFECYCLE.md), [Security](SECURITY.md), and the relevant source-specific guidance.
2. Confirm the selected source: verified repository or explicitly requested verified ZIP.
3. Ask which tools and roots are in scope; do not infer an unspoken target.
4. Create a new plan without executing it.
5. Show the plan path, exact hash, selected roots, destructive actions, user modifications, cleanup, rollback, and stop conditions.
6. Wait for explicit user authorization of that exact plan.
7. Execute using the reviewed plan path and exact hash.
8. Inspect the registry, active version, selected projections, boot pointers, and residue after execution. If an existing local `GLOBAL_BOOT.md` is configured beside the lifecycle root, the reviewed plan must bind, refresh, and verify only its active-version pointer (or write an explicit uninstalled state); this local discovery file belongs only to the local machine.

## Authorization Boundary

Reading a repository, validating identity, inspecting a ZIP, or creating a review plan is not authorization to install. Installation, update, repair, recovery, uninstall, deletion, configuration change, Git mutation, and remote publication each require the user to authorize the concrete action in scope.

Do not substitute a newer repository or Release package after the plan is shown. Source drift invalidates the plan and requires a new review.

## Privacy and Purity

Do not place local paths, credentials, tokens, user configuration, transaction journals, plans, handoffs, test data, or caches in the repository or the installed version. Keep these as local user state only.

## Discovery Verification

After apply, treat the selected tool's adjacent `MALTS_BOOT.md` as ordinary startup authority. Run `python -B <MALTS_ROOT>\tools\malts_lifecycle.py discover --tool-root <TOOL_ROOT> --lifecycle-root <LIFECYCLE_ROOT>` and require exact agreement with the registry, `active_generation.json`, active `VERSION`, and any configured `GLOBAL_BOOT.md`. `GLOBAL_BOOT.md` is a separate machine-global/recovery schema, not a substitute tool boot. Missing or conflicting evidence fails closed.
