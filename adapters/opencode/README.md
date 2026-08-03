# OpenCode Adapter

Use this adapter from a verified MALTS installation. It supplies the
OpenCode instruction template, agent definitions, and settings required by a
MALTS project.

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
the registry, `active_generation.json`, generation identity, and active
`VERSION` to agree. MALTS v1.1.1+ does not use a machine-global `GLOBAL_BOOT.md`. Missing, malformed, reparse-point, stale, or split-brain
state is `BLOCKED` and must not fall back to another root.

For a long-project Phase with an active plan, run read-only `plan-recheck` at
the defined launch, write-scope, delegated-return, verifier, recovery, rollback,
and final-delivery boundaries. The Codex-specific `codex-peer-task` route is not
a portable OpenCode API; use OpenCode's visible native dispatch and retain
equivalent route, return, acceptance, and closure evidence.

## Included runtime material

- `AGENTS.example.md`: managed MALTS instruction block for a project.
- `.opencode/agents/`: optional MALTS role definitions.
- `opencode.json`: OpenCode adapter settings.

See the user [installation guide](../../docs/INSTALL.md) and
[usage guide](../../docs/USAGE.md).
