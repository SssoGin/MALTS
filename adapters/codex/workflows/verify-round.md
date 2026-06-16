# Codex Workflow: Verify MALTS Round

Use this workflow after a MALTS implementation round.

Required checks:

1. Map changed files to the task contract and acceptance criteria.
2. Run the relevant tests, lint checks, installer dry-runs, or document checks.
3. Check that `PROJECT_CONTROL.md` and `项目控制.md` are synchronized when both exist.
4. Check that `WORK_TASK_REPORT.md` and `工作任务报告.md` are synchronized when both exist.
5. Verify adapter parity across Codex, Claude Code, and OpenCode when protocol, template, checklist, or adapter behavior changed.
6. Record skipped checks and residual risks.
