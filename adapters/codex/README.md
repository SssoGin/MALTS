# Codex Adapter

Use this adapter from a verified MALTS installation. It provides the
Codex-specific instruction template, agent definitions, and workflows that
MALTS projects need at runtime.

## Install through the lifecycle

1. Verify the downloaded package before extraction.
2. Create and review a lifecycle plan for the Codex tool root.
3. Execute only the reviewed plan hash.

The lifecycle copies the Codex projection into the selected tool root and
records its exact generation identity. Do not copy these files manually.

## Preview verification

A preview launch must use the preview-contained Codex discovery root as
`CODEX_HOME`, together with preview-contained `HOME`, `USERPROFILE`, `APPDATA`,
`LOCALAPPDATA`, `TEMP`, and `TMP`. Start a fresh bounded Codex process and
verify that it discovers the expected `malts-v<version>-preview.<sequence>` and
a representative `malts-*` Skill. Current-process caches do not count.

If the process cannot be proven isolated, report Codex `BLOCKED`; never fall
back to the real Codex root. A preview that was not verified with real tool
integration is recorded as such and cannot be treated as fully qualified.

## Diagnose and verify

Run lifecycle `Doctor` with the isolated or installed Codex root as applicable.
Doctor is read-only and reports exact boot/projection drift. It does not repair
the adapter. Any repair requires a separate trusted `DoctorRepairPlan`, exact
plan-hash review, transactional execution, and a new fresh-process discovery
check.

Normal discovery starts from Codex's adjacent `MALTS_BOOT.md`, then requires
the registry, `active_generation.json`, generation identity, and active
`VERSION` to agree. MALTS v1.1.1+ does not use a machine-global `GLOBAL_BOOT.md`. Missing, malformed, reparse-point, stale, or split-brain
state is `BLOCKED` and must not fall back to another root.

For a long-project Phase with an active plan, run read-only `plan-recheck` at
the defined launch, write-scope, delegated-return, verifier, recovery, rollback,
and final-delivery boundaries. When native sub-agent routing cannot satisfy an
explicit hard model/effort constraint, Codex may use a user-visible task/thread
as a MALTS-governed `codex-peer-task`. Prefer the current task workspace, record
effective route evidence, reuse the same task for rework, prohibit silent
fallback, and archive only after acceptance or another terminal closure.

## Workspace lifecycle contract

`MALTS_WORKSPACE_LIFECYCLE_CONTRACT: 1`

`MALTS_WORKSPACE_CONSISTENCY_CONTRACT: 1`

- Phase review and transition commands: `phase-boundary-review`, `pause-phase`, `resume-phase`, `plan-phase-transition`, and `apply-phase-transition`.
- Boundary review operation success is not semantic resolution, persistence, or authorization. Use exact-hash, dry-run-first `migrate-consistency-records`, `record-phase-boundary-review`, and `reconcile-consistency-records`.
- Fresh workspaces use schema v3. Schema v1/v2 remain readable and require explicit migration; current `WORK_TASK_REPORT.md` is required and an existing handoff must bind exact Phase, boundary/review, and recovery hashes.
- Deterministic drift blocks validation, cold recovery, and ordinary lifecycle mutation. Recovery never chooses the latest historical Session; it uses active Session, active Phase, explicitly bound terminal Phase, then Project authority.
- Workspace transactions use the isolated `runtime/workspace_transaction.lock.json` / `runtime/workspace_transactions/` namespace and `WS_TRANSACTION_*` codes.
- Artifact commands: `artifact audit`, `artifact enrollment-preview`, `artifact enrollment-apply`, `artifact register`, `artifact promote`, `artifact supersede`, and `artifact reconcile`.
- The Artifact contract defaults to `NOT_ENROLLED`. Invariant: no implicit Session.
- State changes are dry-run by default and require explicit `--apply`; they do not move/delete payloads, invoke VCS, or recursively scan undeclared trees.
- Project keeps compact lifecycle pointers; detailed rows stay with the owning Phase, Session, Shared, or Archive registry.

## Included runtime material

- `AGENTS.example.md`: managed MALTS instruction block for a project.
- `.codex/agents/`: optional MALTS role definitions.
- `.codex/config.toml`: Codex adapter configuration.
- `workflows/`: start, verify, retrospective, and smoke-check guidance.

See the user [installation guide](../../docs/INSTALL.md) and
[usage guide](../../docs/USAGE.md).
