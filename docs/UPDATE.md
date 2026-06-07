# Updating A MALTS Release Repository

Update flow:

1. Start with dry-run.
2. Compare source MALTS runtime assets against this release repository.
3. Sync only approved release content.
4. Keep root `skills/` as the only public skill source.
5. Do not sync local handoff output, private release-control state, internal design notes, trial runs, caches, sessions, real tool configs, local archives, generated migration packages, or non-public companion project references.
6. When local global Agent instructions change, sync only stable MALTS-relevant public guidance into adapter examples. Preserve public-safe confirmation and skill-recommendation rules. Exclude personal language defaults, local paths, private archive paths, private package rules, and local-only wording.
7. Keep third-party attribution current when public guidance is inspired by or adapted from upstream projects.
8. Update `VERSION` and `CHANGELOG.md`.
9. Run sensitive scans.
10. Run lint checks.
11. Review the diff before committing.
12. Use GitHub Desktop or Git CLI to commit and push.

The repository should remain safe to make public even while it is private.
