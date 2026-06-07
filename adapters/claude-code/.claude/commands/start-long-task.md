Start the Agent Project Operating System long-task mode.

Use the `multi-agent-long-task-scheduling` skill.

Pre-check: If the project has no CLAUDE.md or PROJECT_CONTROL.md yet, suggest running `/init` first to set up MALTS. Do not start a long task without project control files.

Instructions:

1. Read English runtime docs only.
2. Create or update `PROJECT_CONTROL.md` (and `项目控制.md` if it does not exist).
3. Capture the user original goal.
4. Define completion and acceptance criteria.
5. Build the initial task queue.
6. Assess task type, difficulty, risk, parallelism, independent verification value, context pressure, and recovery needs before recommending sub-agents.
7. If multi-agent is only a recommendation, explain why and stop before dispatch until the user confirms.
8. Ask whether the user wants to specify sub-agent models and show the accepted format: `Role=model-id; Role=inherit; default=inherit`.
9. Show the launch review packet with the overall goal, total plan, planned agents, model names or policies, each agent's task, and each agent's short plan.
10. Wait for the user's explicit `确认运行` before invoking any sub-agent.
11. For protocol, template, checklist, adapter, or documentation gap-filling tasks, check Codex, Claude Code, and OpenCode together unless the user explicitly scopes one tool out.
12. Treat long work as bounded recoverable rounds, not as a fixed one-shot runtime promise.
13. Ask whether the user wants to enable unattended auto-continue.
14. Use unattended auto-continue only when `PROJECT_CONTROL.md` records explicit user authorization, scope, stop conditions, round caps, reports, and recovery point.
15. If the user does not explicitly authorize unattended auto-continue, do not create, schedule, or rely on automatic unattended running.
16. In a new window or another project folder, resume from project instructions, latest `PROJECT_CONTROL`, latest work task report or handoff, and current files.
17. Keep standalone task/tool artifacts local unless the user explicitly promotes them into system entries, shared tools, or global indexes.

User request:

$ARGUMENTS
