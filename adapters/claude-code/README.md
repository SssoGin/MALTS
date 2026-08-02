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
requires the registry, `active_generation.json`, generation identity, and
active `VERSION` to agree. A configured machine-global `GLOBAL_BOOT.md` is a
separate recovery cross-check. Missing, malformed, reparse-point, stale, or
split-brain state is `BLOCKED` and must not fall back to another root.

For a long-project Phase with an active plan, run read-only `plan-recheck` at
the defined launch, write-scope, delegated-return, verifier, recovery, rollback,
and final-delivery boundaries. The Codex-specific `codex-peer-task` route is not
a portable Claude Code API; use Claude Code's visible native dispatch and retain
equivalent route, return, acceptance, and closure evidence.

## Included runtime material

- `CLAUDE.example.md`: managed MALTS instruction block for a project.
- `.claude/agents/`: optional MALTS role definitions.
- `.claude/commands/`: start, verify, retrospective, and smoke-check guidance.

See the user [installation guide](../../docs/INSTALL.md) and
[usage guide](../../docs/USAGE.md).
