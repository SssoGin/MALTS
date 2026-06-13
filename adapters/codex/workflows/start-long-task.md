# Codex Workflow: Start MALTS Long Task

Codex does not use file-backed custom slash commands like Claude Code or OpenCode.
Use this workflow by asking Codex to start a MALTS long task and, when needed,
to use the configured MALTS subagents.

Required steps:

1. Read `MALTS_BOOT.md` if installed, then resolve `MALTS_ROOT`.
2. Read `PROJECT_CONTROL.md` and `WORK_TASK_REPORT.md` / `工作任务报告.md` if they exist.
3. Capture the user original goal, completion definition, acceptance criteria, risks, and task queue.
4. Offer MALTS-native Grill-Me Preflight for non-trivial or unclear starts.
5. Ask whether unattended auto-continue is authorized and record the answer.
6. If multi-agent work is useful, show a launch review and wait for `确认运行`.
7. Dispatch only bounded tasks with contracts and visible Codex subagent evidence.

