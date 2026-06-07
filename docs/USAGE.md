# Using MALTS

Use MALTS when a task needs recoverable planning, explicit verification, cross-window continuity, optional multi-agent coordination, or reusable process review.

## Normal Task

For small tasks, stay single-agent and keep process overhead low.
Do not create MALTS files unless MALTS is explicitly enabled or the task grows enough to need recoverable state.

## Long Task

For larger work, enable MALTS and:

1. Create or update `PROJECT_CONTROL.md`.
2. Define acceptance criteria.
3. Build a task queue.
4. Record file ownership when multiple workers are possible.
5. Verify before marking work done.
6. Write or append `WORK_TASK_REPORT.md` after each phase or final delivery.
7. Update `PROJECT_HANDOFF.md` before handoff or context risk.

Single-agent first means the main controller keeps ownership by default after MALTS is enabled. Multi-agent scheduling is a controlled division-of-work mechanism enabled only when needed; use it only when it reduces risk, improves independent verification, or makes non-conflicting work practical.

## Multi-Agent Work

Multi-agent mode is optional. It requires:

- a clear fit assessment
- launch review
- user confirmation
- task contracts
- recorded dispatch and feedback
- final reconciliation by the main controller

## Growth And Memory

Use the MALTS Memory Pipeline for reusable lessons. Record candidates first in durable project state, such as `PROJECT_CONTROL.md`, `WORK_TASK_REPORT.md`, or a local retrospective. Promote only filtered, reusable candidates to a global skill, `GLOBAL_MEMORY.md`, `AGENTS.md`, `CLAUDE.md`, or an equivalent tool instruction entry.

## Handoff

Use `PROJECT_HANDOFF.md` as the default Agent-facing recovery file. See `docs/HANDOFF.md`.
