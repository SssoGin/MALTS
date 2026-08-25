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

## Growth Routing Gate

After verification and before final delivery, perform one in-context L1 routing decision. This is a no-write lifecycle check, not a user-confirmation-gated Skill invocation.

- A trivial task with no signal returns `NO_OUTPUT` and stays silent.
- A non-trivial task, user correction, verification reversal, recovery, failure, or reusable method returns `LIGHT_REPORT` with a short user-visible result.
- Repeated failure, rework, phase/long-task completion, delivery failure, or high-impact evidence returns `RETROSPECTIVE_RECOMMENDED`; recommend Standard or Major review but do not start it automatically.
- An explicitly requested retrospective or an already authorized retrospective returns `RETROSPECTIVE_AUTHORIZED`; any L2/L3 durable write remains separately authorization-gated.
- An applicable blocked Plan Recheck returns `BLOCKED`; Growth never bypasses a plan, boundary, safety, unknown-effect, or transaction gate.

The Gate creates no Growth ledger, Phase, Session, Artifact, runtime cache, background process, or durable control-file update. L1 is available without project write permission. A user-visible L1 summary is temporary visibility, not durable memory.

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
4a. If no durable control or reporting delta exists, do not rewrite `PROJECT_CONTROL.md`, `WORK_TASK_REPORT.md`, `PROJECT_HANDOFF.md`, Phase/Session controls, runtime indexes, or timestamps merely to record that nothing changed.
5. Under L1, analyze the signal in memory and report only a temporary candidate when useful.
6. Under an explicit L2 authorization, record the candidate only in the declared project surface and run the anti-pollution gate.
7. Retrieve candidates only when their task type, risk, tool, workspace key, and failure signature are relevant. Retrieval is not permission to apply the candidate.
8. Record adoption or rejection and the outcome; do not record successes only.
9. If a repeated or high-impact pattern appears, propose Standard or Major retrospective.
10. Do not propose `VALIDATED` until the original event is followed by two helped future tasks with different task IDs and independence keys. The original event does not count as future-use validation.
11. High-risk candidates also require an independent review or negative/counterexample test.
12. Harmful evidence moves the candidate to `CHALLENGED`; severe harmful evidence moves it to `SUSPENDED` and stops automatic application.
13. Any L3 proposal or write requires a separate user confirmation even when the memory checklist passes.
14. For non-trivial tasks, user corrections, recovery rounds, or failures, include the short user-facing Growth Routing result in final delivery; a report-only entry does not satisfy this visibility requirement.
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

For `LIGHT_REPORT`, `RETROSPECTIVE_RECOMMENDED`, or `RETROSPECTIVE_AUTHORIZED`:

```md
Growth review:
- Route: LIGHT_REPORT / RETROSPECTIVE_RECOMMENDED / RETROSPECTIVE_AUTHORIZED
- Reusable experience found: Yes / No
- Next-time change: ... / N/A
- Durable write decision: None / Project authorization reference / Separate L3 confirmation required
- Full retrospective: Not needed / Standard recommended / Major recommended / Authorized
```

For `NO_OUTPUT`, show no empty Growth template. For a Chinese user, render Chinese meaning plus the route code, for example `轻量成长复核（LIGHT_REPORT）`.

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

## Fast Path growth

- S0/S1 project-external or same-scope no-durable-delta work records no Phase/Session growth and never creates a Session or reverse Phase trigger.
- A durable state delta routes through `scoped-readiness` as `S2_GOVERNED`; `UNKNOWN` delta, active Session lease, enrolled Artifact, unresolved side effect, or consistency drift escalates and growth recording follows the governed path.
- In an initialized long workspace, ordinary read-only/low-risk entry uses the bounded read-only `workspace-entry` report. It loads no full history and performs no maintenance-view refresh.
- CURRENT report/handoff projections are refreshed only on demand when there is a material reporting or handoff need. Derived-view staleness is a warning; canonical, authorization, transaction, Admission/fencing, or unknown-effect drift remains fail-closed for the affected scope.
