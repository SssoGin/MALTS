---
name: grill-me-preflight
description: Clarify material unresolved goals, tradeoffs or acceptance criteria, or run an explicitly requested preflight interview. Task size alone does not trigger an interview.
---

# Skill: Grill-Me Preflight

## Purpose

Use this MALTS-native workflow to stress-test a plan, design, project start, or ambiguous task before implementation.

This skill is carried by MALTS itself; it does not require any external tool-provided `grill-me` skill to be installed.

The goal is to uncover hidden assumptions, goal boundaries, key tradeoffs, acceptance criteria, and failure modes before work begins.

## Trigger

Use this workflow when the user explicitly requests a preflight interview, or when inspection leaves a decision-changing gap in goals, scope, acceptance criteria, consequential tradeoffs or authorization.

Task size, multiple files, a new project, migration or an S2/S3/S4 label is not sufficient by itself. Discover facts from the current files first. Infer routine technical IDs and language from established conventions and explain assumptions briefly. When the goal and acceptance criteria are clear, proceed without an interview offer.

For one concrete missing decision, ask that question directly. Offer a longer interview only when several connected choices need structured discussion.

## User-Facing Prompt

Use this wording or an equivalent concise version:

> The remaining decision is <specific unresolved choice>; it changes <concrete outcome>. I recommend <option> because <reason>. Which outcome should this task use?

## Workflow

1. Explore the repository, project state, and available docs first for facts that can be discovered without asking the user.
2. Ask only questions that materially change the goal, scope, design, sequencing, risk handling, or acceptance criteria.
3. Group short independent questions when that reduces interruptions; ask dependent questions one at a time. Do not ask the user to repeat settled choices.
4. For each question, include the recommended answer and why it is the default.
5. Walk the decision tree until the goal, success criteria, audience, in/out of scope, constraints, key tradeoffs, edge cases, and verification path are clear enough to implement.
6. Stop when further questions would not materially improve delivery.
7. Record accepted decisions, assumptions, and remaining open questions in `PROJECT_CONTROL.md` before implementation.

## Boundaries

- This workflow resolves missing decisions; it does not reset existing approval or grant Agent dispatch permission.
- It does not require `确认运行`.
- It must not delay any task whose goal, relevant constraints and acceptance criteria are already clear, regardless of size.
- If the user declines an optional interview, proceed with reasonable reversible assumptions inside the approved scope. A missing authorization or consequential unresolved choice still pauses only its dependent action; declining an interview does not authorize it.
- Ask again only when new facts create a material decision gap; do not repeat an offer because the same task remains complex.

## Checklist

- [ ] Discoverable facts were explored before asking.
- [ ] The user was asked only decision-changing questions.
- [ ] Questions addressed unresolved choices efficiently without repeating settled decisions.
- [ ] Each question included a recommended answer.
- [ ] Accepted decisions and assumptions were recorded in `PROJECT_CONTROL.md`.
- [ ] Remaining open questions or declined preflight status were recorded when relevant.

## Runtime boundaries

- Distinguish Phase boundaries from per-Attempt envelopes: a failed Attempt terminates only that Attempt, never auto-retries, and never auto-promotes Task/Phase terminal state.
- Treat external side effects with typed observations and counted units; `UNKNOWN` dispatch/outcome/charge fails closed under finite hard bounds.
- Confirm the migration choice is cold-only and explicit (`reorganize-workspace`, `reorganize-result-contract`); hot migration, downgrade, and silent migration are out of scope.
