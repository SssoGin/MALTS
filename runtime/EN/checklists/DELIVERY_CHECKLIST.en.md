# DELIVERY_CHECKLIST

> Use before final delivery or phase delivery.

## User Goal Alignment

- [ ] The original user goal was re-read from `PROJECT_CONTROL.md` or the current conversation.
- [ ] Each core requirement has a result or an explicit unfinished note.
- [ ] The delivery does not rely on an outdated interpretation of the task.

## Verification Summary

- [ ] Commands, tests, builds, or manual checks are listed.
- [ ] Results are clearly marked as passed, failed, skipped, or not available.
- [ ] The strongest available evidence level is stated.
- [ ] This delivery checklist review is recorded in `WORK_TASK_REPORT.md` or the final user-facing report.
- [ ] If context was compacted, interrupted, or near saturation, recovery state was updated before claiming completion.
- [ ] If recovery docs, adapter docs, package metadata, or runtime-version claims changed, semantic freshness was checked before delivery.

## Deliverables

- [ ] Final files or outputs are listed.
- [ ] Paths are correct.
- [ ] The user can tell which version is final.
- [ ] Usage instructions are short and accurate.
- [ ] If delivering packages, runtime packages and migration/source packages are clearly distinguished.
- [ ] If delivering archives or executables, package contents and hashes are recorded when practical.
- [ ] If standalone task or tool artifacts were created or updated, their boundary is stated and they were not promoted into system indexes unless requested.
- [ ] If folders were added, deleted, moved, renamed, or their purpose changed, related indexes, manuals, and recovery docs were updated or marked N/A with a reason.
- [ ] If accidental project-level copies of global skills/tools were discovered, the final state confirms whether they were moved to global Agent paths, documented as intentional local artifacts, or removed.
- [ ] If bilingual control files are used, the final report says which file is Agent-facing, which file is user-facing, and whether both were updated.
- [ ] If a task report is required, `WORK_TASK_REPORT.md` exists and uses the user's/project's language for narrative content; translated mirrors are generated only when explicitly requested.

## Risks And Limits

- [ ] Known risks are stated.
- [ ] Unverified parts are stated.
- [ ] Follow-up items are separated from completed work.
- [ ] No hidden failure is packaged as success.

## Cost And Process Check

- [ ] The process did not grow heavier than the task required.
- [ ] Task difficulty and multi-agent fit were assessed before choosing the execution mode.
- [ ] If multi-agent scheduling was suggested, the user was told why it fit this task.
- [ ] Multi-agent scheduling, if used, produced mergeable value.
- [ ] Ordinary documentation sync used scripts or structured checks before translation or gap filling.
- [ ] Low-cost workers produced only candidate documentation changes when available; runtime limitations were recorded when model routing was unavailable.
- [ ] High-capability or main-controller approval covered critical protocol semantics, final merge, and final risk judgment instead of full mechanical translation.
- [ ] Candidate documentation changes without required approval were delivered as `Draft` or `Unverified`, not completed work.
- [ ] For non-trivial starts, the report or `PROJECT_CONTROL` states whether MALTS-native Grill-Me Preflight was offered, accepted, declined, or N/A.
- [ ] If multi-agent scheduling was used, the user reviewed the launch packet and explicitly replied `确认运行` before dispatch.
- [ ] The work was designed as bounded recoverable rounds, not as a promised fixed one-shot runtime.
- [ ] At long-task start, the user was asked whether to enable unattended auto-continue.
- [ ] If the user did not explicitly authorize unattended auto-continue, no unattended automatic running was started or scheduled.
- [ ] If unattended auto-continue was used, the explicit authorization package, round cap, stop conditions, and report records are present in `PROJECT_CONTROL`.
- [ ] If unattended auto-continue needed a new multi-agent batch, that batch had its own launch review and `确认运行` confirmation unless already pre-confirmed in the authorization package.
- [ ] Before final validation claims, task status, acceptance criteria, termination status, and report wording were reconciled against the latest evidence.
- [ ] Gap-filling changes were checked across Codex, Claude Code, and OpenCode unless the user explicitly scoped the task to fewer tools.
- [ ] Any unnecessary pending tasks were cancelled, merged, or downgraded.

## Work Task Report

- [ ] A plain user-facing work task report is provided after task or phase completion.
- [ ] The report language policy is satisfied: `WORK_TASK_REPORT.md` is the canonical report, with stable fields and optional translated mirrors only on explicit request.
- [ ] The report records that `DELIVERY_CHECKLIST.en.md` was reviewed before delivery, or explains why it was N/A.
- [ ] The report states result, changes, verification, risks, recovery point, and next step.
- [ ] The report states the growth review result and memory-write decision when the task is non-trivial, includes user correction, or completes a recovery round.
- [ ] If long-term memory could not be written because the external service or target was unavailable, the report names the local fallback record.
- [ ] The report states how a new window or another project folder should resume from recorded files.
- [ ] The user does not need to open every underlying document to understand what happened.

## Final Trust Statement

- Verified:
- Not verified:
- Known risks:
- Recommended user confirmation:
