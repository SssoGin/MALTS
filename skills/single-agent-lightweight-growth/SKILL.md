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

Growth analysis may be continuous, but durable growth writes are permission-bound. Most small tasks should not produce files, long reviews, or heavy process.

## Authority Levels

- `L1 Analyze`: identify a real signal and form an in-memory candidate. Do not create or modify a durable project, global, canonical, Skill, checklist, lint, adapter, tool-install, or public record.
- `L2 Project Maintain`: only after a one-time project authorization that names the writable project surface. Record the triggering event, evidence, and authorization reference. The user may switch back to `analysis_only` or revoke the authorization.
- `L3 System Promote`: proposing or changing `GLOBAL_MEMORY`, global/canonical rules, Skills, checklists, lint, adapters, installed tools, or public content always requires a separate confirmation. L2 never implies L3.

## Workflow

1. Execute the user's task normally.
2. Verify before claiming completion.
3. At the end, briefly check whether the task produced a high-signal event: user correction, verification reversal, repeated failure, rework, recovery/rollback, a materially successful method, or a tool-fact/assumption conflict.
4. If no meaningful signal exists, do not create a growth file.
5. Under L1, analyze the signal in memory and report only a temporary candidate when useful.
6. Under an explicit L2 authorization, record the candidate only in the declared project surface and run the anti-pollution gate.
7. Retrieve candidates only when their task type, risk, tool, workspace key, and failure signature are relevant. Retrieval is not permission to apply the candidate.
8. Record adoption or rejection and the outcome; do not record successes only.
9. If a repeated or high-impact pattern appears, propose Standard or Major retrospective.
10. Do not propose `VALIDATED` until the original event is followed by two helped future tasks with different task IDs and independence keys. The original event does not count as future-use validation.
11. High-risk candidates also require an independent review or negative/counterexample test.
12. Harmful evidence moves the candidate to `CHALLENGED`; severe harmful evidence moves it to `SUSPENDED` and stops automatic application.
13. Any L3 proposal or write requires a separate user confirmation even when the memory checklist passes.
14. For non-trivial tasks, user corrections, recovery rounds, or failures, include a short user-facing growth result in the final or phase report.
15. When the task runs inside an active S3/S4 MALTS Phase with a bound plan, run the matching read-only Plan Recheck event before a new write scope, after a user goal change or failure/recovery, and before final delivery. Do not create a plan or authorization from this lightweight growth workflow; `BLOCKED` stops the gated action and `N/A` is valid only when the Phase does not require a plan.

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
- Authority level: L1 / L2 / L3
- Trigger:
- Action:
- Check:
- Boundary:
- Evidence:
- Lifecycle status:
- Durable write authorization: None / Project authorization reference / Separate L3 confirmation required
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
- Future-use status: Not started / Validating / Two independent future tasks passed / Challenged / Suspended
- Original event counted as future use: No
```

## Checklist

- [ ] The task was verified before delivery.
- [ ] Any user correction was treated as a signal.
- [ ] No one-off detail was promoted.
- [ ] No long review was forced for a small task.
- [ ] Long-term writes were filtered.
- [ ] L1 analysis did not create a durable file.
- [ ] Any L2 write stayed inside the declared project authorization and recorded its authorization reference.
- [ ] Any L3 proposal or write has a separate confirmation.
- [ ] The original triggering event was not counted as a future use.
- [ ] Harmful evidence opens a challenge; severe evidence suspends automatic use.
- [ ] Failed or unavailable memory writes were preserved as local candidates instead of claimed as completed.
- [ ] The user-facing report includes the growth result when the task is non-trivial or recovery-related.
