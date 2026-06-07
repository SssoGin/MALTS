Run a read-only multi-agent smoke test.

Use the `multi-agent-long-task-scheduling` skill with two read-only agents.

Pre-check: PROJECT_CONTROL must exist. If not, suggest `/init` or `/start-long-task` first.

1. Assess: S0 (smoke test, read-only, no file changes). Record in PROJECT_CONTROL.
2. Show launch review packet with Explorer and Verifier roles.
3. Wait for explicit `确认运行`.
4. Dispatch Explorer: read project structure, list key files, report architecture in SUB_AGENT_REPORT format.
5. Dispatch Verifier: check Explorer's report for consistency (file existence, path correctness, structural completeness).
6. Recycle both reports. Reconcile Agent Dispatch Log.
7. If both returned structured reports and log agrees → PASS.
8. If any step failed → report which step and why → FAIL.

No Worker dispatch. No file modifications. Explorer and Verifier default to read-only.

User request:

$ARGUMENTS
