---
name: single-agent-lightweight-growth
description: Use by default during normal single-agent work to keep growth continuous but cheap, without enabling full multi-agent scheduling.
---

# Skill: Single-Agent Lightweight Growth

## Purpose

Use this workflow during normal single-agent execution so that the agent can keep improving without enabling the full multi-agent scheduling system.

This is the default growth mode.

## Trigger

Use for all normal tasks unless multi-agent long-task scheduling is explicitly enabled.

## Principle

Growth should be continuous but cheap. Most small tasks should not produce files, long reviews, or heavy process.

## Workflow

1. Execute the user's task normally.
2. Verify before claiming completion.
3. At the end, briefly check whether the task produced reusable experience.
4. If no meaningful experience exists, do not write memory.
5. If a small lesson exists, mention it as a local note or growth candidate.
6. If a repeated or high-impact pattern appears, propose Standard or Major retrospective.
7. Write long-term memory only after the memory write checklist passes.
8. If the intended long-term memory target is unavailable, keep the candidate as a local note and report that no real long-term write happened.
9. For non-trivial tasks, user corrections, recovery rounds, or failures, include a short user-facing growth result in the final or phase report.

## Lightweight Growth Triggers

Record a growth candidate when:

- The user corrects the agent.
- Verification fails.
- A wrong assumption is discovered.
- A useful check prevented an error.
- A decision rule becomes clear.
- The same problem appears repeatedly.
- A user explicitly says to remember a working method.

## Do Not Record

Do not record:

- Temporary file paths.
- One-off user preferences.
- Speculation.
- Obvious common sense without a trigger.
- Rules that duplicate existing skills.
- Details that would slow future tasks without benefit.

## Output

If meaningful:

```md
Growth candidate:
- Trigger:
- Lesson:
- Suggested destination:
- Needs long-term write check: Yes / No
- Promotion candidate: Yes / No
```

If not meaningful, no growth output is required.

For non-trivial or recovery tasks, include this short report even when no long-term write is made:

```md
Growth review:
- Review level: Light
- Reusable experience found: Yes / No
- Next-time change:
- Memory write decision: Do not write / Local candidate / Proposed after checklist / Local fallback because target unavailable
- Promotion decision: None / Local only / Proposed for GLOBAL_MEMORY / Written to GLOBAL_MEMORY
```

## Checklist

- [ ] The task was verified before delivery.
- [ ] Any user correction was treated as a signal.
- [ ] No one-off detail was promoted.
- [ ] No long review was forced for a small task.
- [ ] Long-term writes were filtered.
- [ ] Failed or unavailable memory writes were preserved as local candidates instead of claimed as completed.
- [ ] The user-facing report includes the growth result when the task is non-trivial or recovery-related.

