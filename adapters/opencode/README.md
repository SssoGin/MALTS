# OpenCode Adapter

Use this adapter from a verified MALTS installation. It supplies the
OpenCode instruction template, agent definitions, and settings required by a
MALTS project.

## Workspace startup contract

OpenCode must not rerun `malts-long-project-workspace-init` for every ordinary task. In an initialized workspace it runs read-only `workspace-entry`, reads only the returned bounded current set, and escalates only for new scope, Phase change, real safety drift, or explicit recovery. CURRENT reports/handoffs are on-demand derived views; they are not startup gates. Default `single_phase` creates no coordination state. Under explicit `resource_admission`, every write lane must verify its Admission, current Phase hash, lease, fencing tokens, and quarantine state before mutation.

This adapter exposes the same Core/schema contract as Codex and Claude Code. Adapter settings and prompts do not grant mutation authority, fence tools that bypass MALTS, or silently migrate legacy workspaces.

## Install through the lifecycle

1. Verify the downloaded package before extraction.
2. Create and review a lifecycle plan for the OpenCode tool root.
3. Execute only the reviewed plan hash.

The lifecycle writes the OpenCode projection into the selected tool root and
records its exact generation identity. Do not copy adapter files by hand.

## Preview verification

A preview launch must use preview-contained `XDG_CONFIG_HOME`,
`XDG_DATA_HOME`, and `XDG_CACHE_HOME`, together with preview-contained `HOME`,
`USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `TEMP`, and `TMP`. Start a fresh
bounded OpenCode process and verify that it discovers the expected
`malts-v<version>-preview.<sequence>` and a representative `malts-*` Skill.
Current-process caches do not count.

If the process cannot be proven isolated, report OpenCode `BLOCKED`; never fall
back to the real OpenCode root. A preview that was not verified with real tool
integration is recorded as such and cannot be treated as fully qualified.

## Diagnose and verify

Run lifecycle `Doctor` with the isolated or installed OpenCode root as
applicable. Doctor is read-only and reports exact boot/projection drift. It
does not repair the adapter. Any repair requires a separate trusted
`DoctorRepairPlan`, exact plan-hash review, transactional execution, and a new
fresh-process discovery check.

Normal discovery starts from OpenCode's adjacent `MALTS_BOOT.md`, then requires
the registry, the exact `<lifecycle-root>/registry/active_generation.json`
pointer, generation identity, and active `VERSION` to agree. Use
`discover.authority_paths.active_generation_pointer` as the pointer locator;
never probe a sibling `<lifecycle-root>/active_generation.json`. MALTS v1.1.1+
does not use a machine-global `GLOBAL_BOOT.md`. Missing, malformed, reparse-point,
stale, or split-brain state is `BLOCKED` and must not fall back to another root.

For a long-project Phase with an active plan, run read-only `plan-recheck` at
the defined launch, write-scope, delegated-return, verifier, recovery, rollback,
and final-delivery boundaries. The Codex-specific `codex-peer-task` route is not
a portable OpenCode API; use OpenCode's visible native dispatch and retain
equivalent route, return, acceptance, and closure evidence.

## Workspace lifecycle contract

`MALTS_WORKSPACE_LIFECYCLE_CONTRACT: 1`

`MALTS_WORKSPACE_CONSISTENCY_CONTRACT: 1`

- Phase review and transition commands: `phase-boundary-review`, `pause-phase`, `resume-phase`, `plan-phase-transition`, and `apply-phase-transition`.
- Boundary review operation success is not semantic resolution, persistence, or authorization. Use exact-hash, dry-run-first `migrate-consistency-records`, `record-phase-boundary-review`, and `reconcile-consistency-records`.
- Fresh workspaces use CURRENT with default `single_phase`; supported legacy layouts remain readable and reach CURRENT only through explicit one-hop reorganization. `resource_admission` is opt-in. CURRENT `WORK_TASK_REPORT.md`/handoff views are on demand; legacy projection bindings remain strict until reorganization.
- When the user gives no model/effort override, MALTS recommends a verified route from task complexity, uncertainty, risk, audit value, budget, latency, and runtime capability; it does not default to Main Controller inheritance. `max` requires a recorded high-risk/high-value reason or a hard user override.
- User-facing lifecycle and status text follows explicit user language, then `NarrativeLanguage`, then English fallback. Chinese output shows the Chinese meaning plus the stable English code, for example `已返回（RETURNED）`; machine fields and status codes stay English.
- Safety-critical canonical/authorization/transaction/Admission/fencing/unknown-effect drift blocks affected work. Recovery never chooses the latest historical Session; it uses active Session, primary active Phase, explicitly bound terminal Phase, then Project authority.
- Workspace/coordination authority shares `runtime/workspace_transaction.lock.json`, `runtime/workspace_transactions/`, and `WS_TRANSACTION_*` with post-lock preimage checking. Typed locators, capability modes, leases, fencing, queues, quarantine, and explicit reconcile govern resource-profile writes; Artifact transactions remain separate.
- Artifact commands: `artifact audit`, `artifact enrollment-preview`, `artifact enrollment-apply`, `artifact register`, `artifact promote`, `artifact supersede`, and `artifact reconcile`.
- The Artifact contract defaults to `NOT_ENROLLED`. Invariant: no implicit Session.
- State changes are dry-run by default and require explicit `--apply`; they do not move/delete payloads, invoke VCS, or recursively scan undeclared trees.
- Project keeps compact lifecycle pointers; detailed rows stay with the owning Phase, Session, Shared, or Archive registry.

## Included runtime material

- `AGENTS.example.md`: managed MALTS instruction block for a project.
- `.opencode/agents/`: optional MALTS role definitions.
- `opencode.json`: OpenCode adapter settings.

See the user [installation guide](../../docs/INSTALL.md) and
[usage guide](../../docs/USAGE.md).
