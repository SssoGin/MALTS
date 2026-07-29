# Getting Started with MALTS

This guide takes a new user from a verified public repository to the first MALTS-controlled task.

## 1. Understand the Model

MALTS is not an autonomous background service. It is a set of Skills, templates, contracts, lifecycle controls, and Agent instructions that make long work explicit and recoverable.

The main Agent remains responsible for the outcome. Sub-agents are optional and cannot be dispatched until the user confirms a complete launch review.

## 2. Choose an Installation Source

Use the public repository as the normal source. An Agent reads the repository, verifies `MALTS_RELEASE.json` and `VERSION`, and creates a review-only plan. It does not download a Release asset unless the user explicitly requests the optional offline archive.

Use the optional `MALTS-<version>.zip` only for a fixed offline copy or when a verified repository source is unavailable. The single ZIP contains the immutable release package and its package-level verification material.

## 3. Verify the Repository Source

At the repository root, confirm that `MALTS_RELEASE.json` names the same version as `VERSION`. If Git metadata is available, also confirm that the checked-out tag is the `release_tag` recorded in the identity file.

```powershell
Get-Content .\VERSION
Get-Content .\MALTS_RELEASE.json
git describe --exact-match --tags HEAD
```

An absent Git checkout does not prevent repository installation; the identity file still binds the exact user source tree.

## 4. Create an Installation Plan

```powershell
.\scripts\Install-MALTS.ps1 `
  -RepositoryRoot (Get-Location).Path `
  -UseDefaultRoots `
  -Tool Codex
```

The command writes a new plan and prints its path and exact SHA-256. It does not install MALTS yet.

For explicit roots, follow [Install](INSTALL.md). To let an Agent perform this review, follow [Agent-Assisted Installation](AGENT_INSTALL.md).

## 5. Review and Execute

Review the selected tool roots, user-modification classification, cleanup, rollback, and post-validation actions in the plan. Execute only the exact plan hash printed by the review step.

## 6. Start a Project

After installation, ask the Agent to use an installed MALTS entry point:

| Need | Entry point |
|---|---|
| Normal project controls | `malts-project-init` |
| Full long-project workspace with the first Phase | `malts-long-project-workspace-init` |
| Pre-implementation clarification | `malts-grill-me-preflight` |
| Controlled multi-agent launch review | `malts-multi-agent-long-task-scheduling` |
| Restart-safe handoff | `malts-session-handoff` |

`malts-long-project-workspace-init` is intentionally different from normal project initialization: a new long-project workspace creates its root controls and first active Phase together. A Session remains explicit and is not created by initialization alone.

## Next Reading

- [Install](INSTALL.md)
- [Update](UPDATE.md)
- [Usage](USAGE.md)
- [Lifecycle](LIFECYCLE.md)
- [Release Artifact](RELEASE_ARTIFACT.md)
