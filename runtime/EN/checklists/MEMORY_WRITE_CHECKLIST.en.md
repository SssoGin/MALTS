# MEMORY_WRITE_CHECKLIST

> Use before writing any experience into long-term skills, `AGENTS.md`, `CLAUDE.md`, or global memory.

Passing this checklist means a long-term memory write may proceed or be proposed according to the selected destination. It is not a blanket requirement to wait for an explicit user request before every memory note. Explicit user confirmation is required when the destination changes durable global instructions or other high-risk behavior.

## Fact Check

- [ ] The experience really happened.
- [ ] The source is known: project event, error, verification, decision, or user feedback.
- [ ] Facts are separated from judgments and assumptions.
- [ ] Missing information is marked instead of invented.

## Reuse Value

- [ ] Similar situations are likely to happen again.
- [ ] The experience can reduce rework, errors, verification gaps, or communication cost.
- [ ] The benefit is higher than the process cost.
- [ ] It is not merely a one-time local detail.

## Rule Quality

- [ ] It has a clear trigger condition.
- [ ] It has a concrete action.
- [ ] It has a verification or check method.
- [ ] It has applicable boundaries.
- [ ] It includes the risk it avoids or practice it reuses.

## Deduplication

- [ ] Existing skills were checked.
- [ ] Existing `AGENTS.md` / `CLAUDE.md` rules were checked if relevant.
- [ ] The candidate does not repeat an existing rule in different wording.
- [ ] If similar rules exist, the candidate should merge or refine them instead of adding another copy.

## Destination Decision

| Destination | Use When |
|---|---|
| Current retrospective only | Useful only for this project |
| Project skill | Reusable in similar tasks inside this project |
| Global skill | Reusable across projects |
| `GLOBAL_MEMORY.md` | Cross-project stable rule, pattern, or decision |
| Tool instruction file candidate | High-frequency, stable, cross-task behavior that belongs in `AGENTS.md`, `CLAUDE.md`, or an equivalent tool instruction entry |
| Tool adapter | Specific to Claude Code, Codex, OpenCode, or another tool |
| Do not write | Too specific, unverified, duplicate, or low value |

## Safety

- [ ] No secrets, tokens, private accounts, or sensitive local details are written.
- [ ] User-specific private information is not promoted into global memory.
- [ ] The rule will not cause unsafe future automation.
- [ ] High-risk rule changes require user confirmation.

## Fallback

- [ ] If the intended long-term memory service, global skill path, or durable rule target is unavailable, the candidate is preserved in `PROJECT_CONTROL`, a work task report, or a local retrospective instead of being dropped.
- [ ] The user-facing report distinguishes between a proposed candidate, a local fallback record, and a real long-term write.

## Final Decision

- Write: Yes / No
- Destination:
- Reason:
- Fallback location if write failed or was skipped:
- Review after future use: Yes / No
