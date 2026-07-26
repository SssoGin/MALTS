---
name: project-retrospective-growth
description: Use after project completion, phase delivery, rework, user correction, verification failure, or explicit retrospective requests to distill reusable experience without polluting long-term memory.
---

# Skill: Project Retrospective Growth

## Purpose

Use this skill to turn project facts, mistakes, successful practices, decisions, and verification methods into reusable future capability without polluting long-term memory.

The goal is not to write a beautiful summary. The goal is to make the next similar project faster, safer, and less likely to repeat the same mistakes.

## Trigger

This growth system is enabled by default, but its depth must match the task.

### Light Review

Use for normal small tasks.

Output:

- Whether there is reusable experience.
- Whether any rule candidate exists.
- Usually no file writes.

### Standard Review

Use after:

- Phase delivery.
- Minor rework.
- A useful process discovery.
- A verification issue.

Output:

- Growth candidates.
- Checklist candidates.
- Possible skill update proposal.

### Major Review

Use after:

- Major bug.
- User points out wrong direction.
- Repeated rework.
- Long-task completion.
- Delivery failure.
- Explicit user request for retrospective or skill growth.

Output:

- Fact reconstruction.
- Good experience.
- Wrong experience.
- Root-cause analysis.
- Decision review.
- Reusable rules.
- Skill or checklist updates.

## Runtime Document Loading

- Read English runtime documents by default.
- Do not read Chinese copies unless the user explicitly asks for Chinese reading, editing, comparison, or synchronization.

## Inputs

- User original goal.
- Final or current deliverables.
- `PROJECT_CONTROL.md`, if available.
- Verification records.
- Error logs or failed attempts.
- User feedback.
- Relevant existing EN skills and checklists.

## Core Principles

1. Facts first, judgment second.
2. User feedback is a signal, not the root cause.
3. Every meaningful mistake should become an avoidance mechanism.
4. Good experience needs boundaries.
5. A rule must have trigger, action, check method, and boundary.
6. A skill is a callable workflow, not a summary.
7. Long-term memory must be filtered and deduplicated.
8. Review depth must match task scale.
9. Do not write speculation as fact.
10. Do not make future agents slower without clear benefit.

## Workflow

1. Determine review depth: Light, Standard, or Major.
2. Restore confirmed facts.
3. Separate facts, assumptions, judgments, and unknowns.
4. Compare the result against the user original goal.
5. Identify good experience.
6. Identify mistakes, rework, and missed checks.
7. Ask at least two levels of why for important failures.
8. Extract reusable rules.
9. Filter rules before writing long-term memory.
10. Classify authority before deciding destination: L1 analysis, authorized L2 project maintenance, or separately confirmed L3 system promotion.
11. Record what changed or what is only proposed.
12. If the intended long-term memory target is unavailable, preserve the candidate locally in `PROJECT_CONTROL`, a work task report, or a retrospective and do not claim a real memory write.
13. Route filtered decisions and growth results through the MALTS Memory Pipeline.
14. Review the candidate lifecycle. The original event is not a future use; default validation requires two helped future tasks with different task IDs and independence keys, for three total validations including the source event. High-risk candidates need an independent review or negative/counterexample test.
15. For user corrections, recovery work, failures, and long-task phases, include the retrospective level, reusable lesson, and memory-write decision in the user-facing report.

Lifecycle states are:

`OBSERVED → CANDIDATE → PROJECT_EXPERIMENTAL → FUTURE_USE_VALIDATING → VALIDATED → SYSTEM_PROMOTION_PROPOSED → ACCEPTED / REJECTED → DEPRECATED / REMOVED`

Counterevidence may move a candidate to `CHALLENGED` or `SUSPENDED` from any applicable active state. Severe harmful evidence immediately stops automatic application. Retrieval must remain relevant to the current task and must record matched, adopted/rejected/deferred, and outcome evidence.

For system pilots, add one extra gate before closing the work: return to the main system workspace, write or update the relevant trial-run record, and record evidence, validation gaps, and growth candidates there. A target-project delivery is not the same as system validation completion.

For validation trials, run memory or growth curation after factual reports and verification evidence exist, unless the user explicitly asks for an early retrospective. Early notes may be useful during incidents, but stable growth candidates should be based on recycled evidence.

## Rule Formula

Use this format for reusable rules:

```text
When [trigger scene] appears,
the agent should [perform action],
and confirm through [check method],
to avoid [specific risk] or reuse [effective practice].
The applicable boundary is [when not to use it].
```

If this formula cannot be filled, the experience is usually not ready for long-term memory.

## Memory Destination Rules

| Experience Type | Destination |
|---|---|
| One-project fact | Current retrospective or `PROJECT_CONTROL.md` |
| Reusable workflow for this project type | Project skill |
| Cross-project stable behavior | Global skill or tool instruction file candidate such as `AGENTS.md` or `CLAUDE.md` |
| Tool-specific behavior | Tool adapter document |
| User-facing delivery detail | Project documentation |
| Unverified speculation | Do not write as memory |

## Long-Term Write Criteria

Before writing to long-term memory, the experience must pass `MEMORY_WRITE_CHECKLIST.en.md`.

Passing the checklist does not grant write authority. L1 never writes durable state. L2 writes only inside a one-time project authorization and its declared file surface. Every L3 proposal or modification to global/canonical memory, Skills, checklists, lint, adapters, installed tools, public content, `AGENTS.md`, `CLAUDE.md`, permissions, or automation policy requires a separate explicit confirmation.

The MALTS Memory Pipeline records candidates in the nearest durable MALTS surface first: `PROJECT_CONTROL.md`, a work task report, a local retrospective, `GLOBAL_MEMORY.md` or a global-rule candidate, and only then an optional external memory system when one is configured and write-capable.

If the selected memory destination is unavailable, the correct fallback is a local candidate record. Preserve enough context for a future write attempt, state the fallback location, and report that no long-term memory write actually happened.

Minimum criteria:

- Real, not invented.
- Likely to recur.
- Triggerable.
- Executable.
- Checkable.
- Bounded.
- Non-duplicate.
- Worth the cost.
- Has a challenge, suspension, deprecation, and removal path.
- Contains no secret, sensitive user detail, or unnecessary machine path.
- Will not cause unsafe future automation.

## Output Format

### Light Output

```md
## Growth Check

- Reusable experience found: Yes / No
- Candidate:
- Suggested destination:
- Reason:
- Memory write decision:
```

### Standard Output

```md
## Project Growth Notes

### Confirmed Facts
### Good Experience
### Mistakes Or Gaps
### Reusable Rule Candidates
### Suggested Skill / Checklist Updates
### User-Facing Growth Summary
```

### Major Output

```md
## Project Retrospective And Growth Result

### 1. Fact Reconstruction
### 2. Good Experience
### 3. Wrong Experience And Root Cause
### 4. Process Review
### 5. Decision Review
### 6. Reusable Rules
### 7. Skill / Checklist Updates
### 8. Next Project Checklist
### 9. Information Still Missing
### 10. User-Facing Growth Summary
### 11. Promotion To Global
### 12. Lifecycle Review
```

## Checklist

- [ ] Facts and judgments are separated.
- [ ] User goal comparison is included.
- [ ] Mistakes have root-cause analysis.
- [ ] Rules have trigger, action, check, and boundary.
- [ ] One-off details are not promoted.
- [ ] Existing rules are checked before adding new ones.
- [ ] The review depth matches task scale.
- [ ] The user-facing report states the review level and memory-write decision.
- [ ] The original event is not counted as future-use validation.
- [ ] Two helped future tasks use distinct task IDs and independence keys before `VALIDATED`.
- [ ] High-risk candidates have independent or negative/counterexample evidence.
- [ ] Harmful evidence is challenged and severe evidence is suspended.
- [ ] L1/L2/L3 authorization is recorded and no lower level is treated as higher-level authority.

