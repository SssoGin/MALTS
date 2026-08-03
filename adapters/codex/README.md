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

## Included runtime material

- `AGENTS.example.md`: managed MALTS instruction block for a project.
- `.codex/agents/`: optional MALTS role definitions.
- `.codex/config.toml`: Codex adapter configuration.
- `workflows/`: start, verify, retrospective, and smoke-check guidance.

See the user [installation guide](../../docs/INSTALL.md) and
[usage guide](../../docs/USAGE.md).
