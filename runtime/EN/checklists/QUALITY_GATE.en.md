# QUALITY_GATE

> A task cannot enter DONE until the relevant gate items are satisfied or explicitly marked as not applicable.

## Requirement Coverage

- [ ] The task maps back to a user goal or approved project task.
- [ ] The completion criteria are clear.
- [ ] Non-goals and exclusions are respected.
- [ ] Later user changes have been checked.
- [ ] For non-trivial task or project starts, MALTS-native Grill-Me Preflight was offered, accepted/declined/N/A was recorded, and accepted decisions were reflected in `PROJECT_CONTROL`.

## Scope And Ownership

- [ ] Modified files are inside the allowed scope.
- [ ] No prohibited files were modified.
- [ ] Resource locks were respected.
- [ ] Unknown user changes were not overwritten.
- [ ] For protocol, template, checklist, adapter, or documentation gap-filling tasks, Codex, Claude Code, and OpenCode were checked and synchronized unless the user explicitly scoped one out.
- [ ] Standalone task/tool artifacts were kept local unless the user explicitly requested promotion into system entries, shared tools, or global indexes.
- [ ] Folder additions, deletions, moves, renames, or purpose changes updated the related indexes/manuals/recovery docs, or the N/A reason is recorded.
- [ ] Project workspace roots do not retain accidental global-skill/tool install copies. If such copies are found, they are either promoted to the correct global Agent path, documented as intentional project artifacts, or removed after verification.
- [ ] If both `PROJECT_CONTROL.md` and a user-facing localized control file exist, their roles and latest synchronization status are recorded.
- [ ] For documentation sync work, source/target files, sync direction, and model/cost strategy were recorded.

## Verification Evidence

- [ ] At least one direct verification method was used.
- [ ] Verification result is recorded.
- [ ] Evidence level is stated.
- [ ] Failed or skipped checks are explained.
- [ ] For handoff/status/adapter/package changes, semantic freshness was checked against current package metadata and runtime version evidence.
- [ ] For documentation sync work, scripts or structured checks were used before bulk translation/sync, or the skipped-check reason is recorded.
- [ ] Critical protocol semantics were not accepted, merged, or marked verified based only on low-cost worker output.
- [ ] If high-capability/main-controller approval is missing for critical semantics, the result is marked `Draft` or `Unverified`, not done.
- [ ] For GUI, visual, overlay, or interaction-heavy work, user visual confirmation or equivalent visual evidence is recorded.
- [ ] If context saturation, compaction, or interruption occurred, the external recovery state was updated.
- [ ] Long-task continuation is expressed as bounded rounds with recovery points, not as a fixed one-shot runtime promise.
- [ ] New-window or other-project continuation can start from project instructions, latest `PROJECT_CONTROL`, latest work task report or handoff, and current files.

## Multi-Agent Dispatch Gate

- [ ] Task type and difficulty were assessed before suggesting or enabling multi-agent mode.
- [ ] Multi-agent was suggested only when it could reduce risk, improve independent verification, enable non-conflicting parallel work, or improve recoverability.
- [ ] If the task was S0/S1 or merge cost exceeded benefit, single-agent mode was used or the reason for escalation was recorded.
- [ ] If the user requested multi-agent mode, the launch review packet was shown before dispatch.
- [ ] The launch review packet listed the overall goal, total plan, each planned agent, model name or model policy, task, and short plan.
- [ ] The user was asked whether they wanted to specify sub-agent models and was shown the accepted model specification format.
- [ ] The user explicitly replied `确认运行` before any real sub-agent dispatch.
- [ ] Any model/scope/batch changes during review were reflected in task contracts before dispatch.
- [ ] Agent Dispatch Log, task contracts, returned reports, and Agent Feedback Log agree on task ID, role, runtime agent ID when available, model policy, and main-controller decision.

## Unattended Auto-Continue Gate

- [ ] At long-task start, the user was asked whether to enable unattended auto-continue.
- [ ] Unattended continuation was used only if explicitly authorized by the user.
- [ ] If not explicitly authorized, unattended automatic running was not started, scheduled, or implied.
- [ ] `PROJECT_CONTROL` records allowed scope, prohibited operations, multi-agent permission, model policy, round/time caps, stop conditions, and report requirements.
- [ ] Each unattended round updated recovery state and produced or appended a work task report.
- [ ] Stop conditions were checked before starting another unattended round.
- [ ] Any new multi-agent batch not pre-confirmed in the authorization package stopped for launch review and `确认运行`.

## Deliverable Integrity

- [ ] Claimed deliverables actually exist.
- [ ] Deliverables are named clearly.
- [ ] User-facing instructions match actual files or commands.
- [ ] The result is usable without hidden missing steps.

## Risk Transparency

- [ ] Remaining risks are listed.
- [ ] Unfinished items are listed.
- [ ] Assumptions are marked as assumptions.
- [ ] Speculation is not presented as fact.

## Growth Hygiene

- [ ] Reusable experience candidates are recorded when meaningful.
- [ ] One-off details are not written into long-term memory.
- [ ] Any proposed rule has trigger, action, check, and boundary.
- [ ] The user-facing report states the growth review result for non-trivial tasks, user corrections, recovery rounds, or failures.
- [ ] If the external long-term memory service or global memory target is unavailable, the candidate is preserved locally and the report states that no long-term memory write actually happened.

## User Report

- [ ] A clear work task report is ready for the user when the task or phase is complete.
