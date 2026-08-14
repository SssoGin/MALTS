# Claude Code Adapter

Use this adapter from a verified MALTS installation. It supplies the Claude
Code instruction template, agent definitions, and command guidance needed by a
MALTS project.

## Install through the lifecycle

1. Verify the downloaded package before extraction.
2. Create and review a lifecycle plan for the Claude Code tool root.
3. Execute only the reviewed plan hash.

The lifecycle writes the Claude Code projection into the selected tool root and
records its exact generation identity. Do not copy adapter files by hand.

## Preview verification

A preview launch must use the preview-contained Claude Code discovery root as
`CLAUDE_CONFIG_DIR`, together with preview-contained `HOME`, `USERPROFILE`,
`APPDATA`, `LOCALAPPDATA`, `TEMP`, and `TMP`. Start a fresh bounded Claude Code
process and verify that it discovers the expected
`malts-v<version>-preview.<sequence>` and a representative `malts-*` Skill.
Current-process caches do not count.

If the process cannot be proven isolated, report Claude Code `BLOCKED`; never
fall back to the real Claude Code root. A preview that was not verified with
real tool integration is recorded as such and cannot be treated as fully
qualified.

## Diagnose and verify

Run lifecycle `Doctor` with the isolated or installed Claude Code root as
applicable. Doctor is read-only and reports exact boot/projection drift. It
does not repair the adapter. Any repair requires a separate trusted
`DoctorRepairPlan`, exact plan-hash review, transactional execution, and a new
fresh-process discovery check.

Normal discovery starts from Claude Code's adjacent `MALTS_BOOT.md`, then
requires the registry, the exact `<lifecycle-root>/registry/active_generation.json`
pointer, generation identity, and active `VERSION` to agree. Use
`discover.authority_paths.active_generation_pointer` as the pointer locator;
never probe a sibling `<lifecycle-root>/active_generation.json`. MALTS v1.1.1+
does not use a machine-global `GLOBAL_BOOT.md`. Missing, malformed, reparse-point,
stale, or split-brain state is `BLOCKED` and must not fall back to another root.

For a long-project Phase with an active plan, run read-only `plan-recheck` at
the defined launch, write-scope, delegated-return, verifier, recovery, rollback,
and final-delivery boundaries. The Codex-specific `codex-peer-task` route is not
a portable Claude Code API; use Claude Code's visible native dispatch and retain
equivalent route, return, acceptance, and closure evidence.

## Workspace lifecycle contract

`MALTS_WORKSPACE_LIFECYCLE_CONTRACT: 1`

`MALTS_WORKSPACE_CONSISTENCY_CONTRACT: 1`

- Phase review and transition commands: `phase-boundary-review`, `pause-phase`, `resume-phase`, `plan-phase-transition`, and `apply-phase-transition`.
- Boundary review operation success is not semantic resolution, persistence, or authorization. Use exact-hash, dry-run-first `migrate-consistency-records`, `record-phase-boundary-review`, and `reconcile-consistency-records`.
- Fresh workspaces use schema v4. Schema v1/v2/v3 remain readable and require explicit migration (`migrate-workspace-v3-to-v4`, `migrate-result-contract-v1-to-v2`); current `WORK_TASK_REPORT.md` is required and an existing handoff must bind exact Phase, boundary/review, and recovery hashes.
- Deterministic drift blocks validation, cold recovery, and ordinary lifecycle mutation. Recovery never chooses the latest historical Session; it uses active Session, active Phase, explicitly bound terminal Phase, then Project authority.
- Workspace transactions use the isolated `runtime/workspace_transaction.lock.json` / `runtime/workspace_transactions/` namespace and `WS_TRANSACTION_*` codes.
- Artifact commands: `artifact audit`, `artifact enrollment-preview`, `artifact enrollment-apply`, `artifact register`, `artifact promote`, `artifact supersede`, and `artifact reconcile`.
- The Artifact contract defaults to `NOT_ENROLLED`. Invariant: no implicit Session.
- State changes are dry-run by default and require explicit `--apply`; they do not move/delete payloads, invoke VCS, or recursively scan undeclared trees.
- Project keeps compact lifecycle pointers; detailed rows stay with the owning Phase, Session, Shared, or Archive registry.

## Included runtime material

- `CLAUDE.example.md`: managed MALTS instruction block for a project.
- `.claude/agents/`: optional MALTS role definitions.
- `.claude/commands/`: start, verify, retrospective, and smoke-check guidance.

See the user [installation guide](../../docs/INSTALL.md) and
[usage guide](../../docs/USAGE.md).
