# Codex Workflow: Start MALTS Long Task

Codex does not use file-backed custom slash commands like Claude Code or OpenCode.
Use this workflow by asking Codex to start a MALTS long task and, when needed,
to use the configured MALTS subagents.

Required steps:

1. Read the exact tool-adjacent `MALTS_BOOT.md`, resolve `MALTS_ROOT`, and cross-check registry / active pointer / generation / `VERSION`.
2. If this is an initialized workspace, run read-only `workspace-entry` and read only its bounded current set. Do not load report/handoff/history by existence alone or rerun initialization for an ordinary task.
3. For first setup, structural recovery, explicit migration, or major lifecycle change, use the full initializer; otherwise capture only the material Project/Phase delta in its owning control.
4. Resolve material decision gaps after inspection; use Preflight only when requested or useful for connected choices. A clear task proceeds without an interview offer.
5. Discuss unattended operation only when requested or materially needed; reuse matching authorization and otherwise continue the active task normally.
6. If delegation is useful, prepare a bounded launch review. Reuse existing same-scope authorization; ask only if the launch is not yet authorized.
7. Dispatch only bounded tasks with contracts and visible Codex subagent evidence.
8. Under `resource_admission`, dispatch a writer only after its typed locator/capability Admission, exact Phase hash, lease, fencing tokens, and quarantine state pass verification. Default `single_phase` creates no coordination state.
