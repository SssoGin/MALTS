---
name: grill-me-preflight
description: Use before non-trivial task or project starts to expose hidden assumptions, goal boundaries, key tradeoffs, and acceptance criteria.
---

# Skill: Grill-Me Preflight

## Purpose

Use this MALTS-native workflow to stress-test a plan, design, project start, or ambiguous task before implementation.

This skill is carried by MALTS itself; it does not require any external tool-provided `grill-me` skill to be installed.

The goal is to uncover hidden assumptions, goal boundaries, key tradeoffs, acceptance criteria, and failure modes before work begins.

## Trigger

Offer this workflow at the start of a non-trivial task when any of these are true:

- New project or new major workstream.
- Multi-step, multi-file, risky, recovery-sensitive, or long-running work.
- Design, architecture, planning, migration, workflow, or protocol decisions.
- Requirements, success criteria, exclusions, or tradeoffs are not fully settled.

Do not offer it for S0/S1 tasks where the goal and verification are already clear.

## User-Facing Prompt

Use this wording or an equivalent concise version:

> This task is a good fit for MALTS Grill-Me Preflight because it can expose hidden assumptions, goal boundaries, key tradeoffs, and acceptance criteria before implementation, reducing rework and requirement mismatch. Do you want to run a short preflight grilling round first?

## Workflow

1. Explore the repository, project state, and available docs first for facts that can be discovered without asking the user.
2. Ask only questions that materially change the goal, scope, design, sequencing, risk handling, or acceptance criteria.
3. Ask one question at a time.
4. For each question, include the recommended answer and why it is the default.
5. Walk the decision tree until the goal, success criteria, audience, in/out of scope, constraints, key tradeoffs, edge cases, and verification path are clear enough to implement.
6. Stop when further questions would not materially improve delivery.
7. Record accepted decisions, assumptions, and remaining open questions in `PROJECT_CONTROL.md` before implementation.

## Boundaries

- This workflow is a clarification and planning gate, not a sub-agent dispatch.
- It does not require `确认运行`.
- It must not be used to delay obvious small tasks.
- If the user declines, proceed with the best stated assumptions and record that the preflight was declined when the task is non-trivial.
- If the task later becomes ambiguous or risky, offer it again at the next checkpoint.

## Checklist

- [ ] Discoverable facts were explored before asking.
- [ ] The user was asked only decision-changing questions.
- [ ] Questions were asked one at a time.
- [ ] Each question included a recommended answer.
- [ ] Accepted decisions and assumptions were recorded in `PROJECT_CONTROL.md`.
- [ ] Remaining open questions or declined preflight status were recorded when relevant.

