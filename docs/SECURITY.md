# Security

## Verify Before Use

For repository installation, validate `MALTS_RELEASE.json` and `VERSION` before creating a plan. The repository identity binds the expected user file count and source-tree SHA-256; an unexpected file, cache, `.malts` residue, missing required entry point, or hash mismatch fails closed.

When Git metadata is available, compare the checked-out tag with the identity file's `release_tag`. This is an additional provenance check; the repository identity remains the package-level source binding.

For an explicitly requested offline archive, use `Verify-MALTSBootstrap.ps1` before extraction. It verifies the one ZIP's deterministic structure, safe Windows paths, duplicate/case-colliding members, required package files, isolated extraction, and the immutable package verifier inside the archive.

## Installed Provenance Privacy

The installed provenance records contain only release hashes, version identity,
and the source kind (`repository` or `release-package`); they contain no local
source locator. A legacy record with an absolute source locator is accepted
only as update input and blocks use until a verified update replaces it.

## Keep Local Data Local

Do not place credentials, tokens, session data, user-profile paths, private project files, cache directories, generated runtime state, plans, transaction journals, or handoffs inside a MALTS repository or installed version.

Use environment variables or the selected tool's normal secure configuration mechanism for credentials. Do not put secret values in `PROJECT_CONTROL.md`, `WORK_TASK_REPORT.md`, handoff files, prompts, or command history.

## Review Before Mutation

Installation and update plans are hash-bound. Read the full plan before providing `-Apply` and the exact plan hash. Inspect selected roots, modified files, cleanup, rollback, and post-validation actions.

Do not approve a plan after its source, version, roots, or expected actions have changed. Create a fresh plan instead.

## Report Security Issues

Do not publish secrets in a public issue, discussion, release note, or task log. Use the repository's private security contact or another private channel agreed with the project team.
