# Getting Started with MALTS

This guide takes a new user from a verified repository source to the first MALTS-controlled task.

## 1. Understand the Model

MALTS is not an autonomous background service. It is a set of Skills, templates, contracts, lifecycle controls, and Agent instructions that make long work explicit and recoverable.

The main Agent remains responsible for the outcome. Sub-agents are optional and cannot be dispatched until the user confirms a complete launch review.

## 2. Choose an Installation Source

Use the repository as the normal source. An Agent reads the repository, verifies `MALTS_RELEASE.json` and `VERSION`, and creates a review-only plan. It does not download a Release asset unless the user explicitly requests the optional offline archive.

Use the optional `MALTS-<version>.zip` only for a fixed offline copy or when a verified repository source is unavailable. The single ZIP contains the immutable release package and its package-level verification material.

## 3. Verify the Repository Source

At the repository root, confirm that `MALTS_RELEASE.json` names the same version as `VERSION`. If Git metadata is available, also confirm that the checked-out tag is the `release_tag` recorded in the identity file.

```powershell
Get-Content .\VERSION
Get-Content .\MALTS_RELEASE.json
git describe --exact-match --tags HEAD
```

An absent Git checkout does not prevent repository installation; the identity file still binds the exact source tree.

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

## 7. Govern Long Work Explicitly

After initialization, keep ordinary work inside the active Phase boundary. Use read-only `phase-boundary-review` when scope may change; use explicit pause/resume or a persisted hash-bound transition instead of silently changing the Phase goal.

Artifact lifecycle remains `NOT_ENROLLED` until a real need exists. Begin with read-only `artifact audit`. Enrollment and every mutation are separate dry-run/apply operations; they do not create Sessions, move/delete payloads, invoke VCS, or scan the whole workspace.

Run `validate` and `recover` after meaningful control changes. For S3/S4 work with an active plan, run the matching read-only Plan Recheck trigger at write-scope, recovery, failure/rollback, verifier, and final-delivery boundaries.

Fresh long-project workspaces use schema v4. Existing schema v1/v2/v3 controls remain readable but are never silently rewritten. If `validate` reports migration or reconciliation required, review the exact reported command without `--apply` — `migrate-workspace-v3-to-v4`, `migrate-result-contract-v1-to-v2`, or the legacy `migrate-consistency-records` / `record-phase-boundary-review` / `reconcile-consistency-records` — bind the exact expected hashes, and apply only inside the current workspace authorization.

Current recovery authority is deterministic: active Session checkpoint, otherwise active Phase recovery, otherwise an explicitly bound terminal Phase, otherwise Project recovery. A historical Session is never selected merely because it is newest. An incomplete workspace transaction keeps its lock/journal evidence until an exact-journal-hash `recover-workspace-transaction` review/apply succeeds.

## Next Reading

- [Install](INSTALL.md)
- [Update](UPDATE.md)
- [Usage](USAGE.md)
- [Lifecycle](LIFECYCLE.md)
- [Release Artifact](RELEASE_ARTIFACT.md)
