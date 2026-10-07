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

## Artifact Lifecycle Delivery

- [ ] Enrollment status and every live owner/Shared/Archive registry pointer are stated; runtime snapshots are labeled non-canonical.
- [ ] Artifact audit/validation evidence, unresolved rows, verification/retention/disposition state, and any stale transaction lock/journal are reported.
- [ ] Applied mutations are bound to reviewed operation IDs and final hashes; dry runs are not described as applied changes.
- [ ] No implicit Session, payload move/delete, VCS action, undeclared recursive scan, or silent legacy adoption is presented as completed work.

## Workspace Consistency Delivery

- [ ] Workspace contract class and any explicit one-hop CURRENT reorganization are reported; no compatibility input is described as silently upgraded or routed through a user-visible version chain.
- [ ] The required report and any existing handoff declare the exact current Phase full-control, boundary/review, and recovery binding hashes.
- [ ] The delivered `validate` result has no structural, binding, or deterministic-consistency failures, and fresh-process `recover` names the expected typed canonical recovery source.
- [ ] Boundary Review execution status, recorded outcome, decision, and authorization are described separately.
- [ ] Any incomplete workspace transaction and exact `recover-workspace-transaction` action are disclosed; no lock/journal evidence was silently removed.
- [ ] Recovery evidence proves there is no latest historical Session fallback.

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
- [ ] The final report states the dynamic route (`0`, `1`, or `N`), responsibility lanes, and why the selected count was justified.
- [ ] Requested, recommended, configured, and effective model/effort evidence is distinguishable in the delivery record.
- [ ] Any configured-only, inherited, unsupported, provider-unconfigured, or unknown binding is labeled honestly.
- [ ] If real Agent/provider behavior was outside scope, G4 is reported as `NOT RUN` rather than inferred from component tests.
- [ ] Ordinary documentation sync used scripts or structured checks before translation or gap filling.
- [ ] Low-cost workers produced only candidate documentation changes when available; runtime limitations were recorded when model routing was unavailable.
- [ ] High-capability or main-controller approval covered critical protocol semantics, final merge, and final risk judgment instead of full mechanical translation.
- [ ] Candidate documentation changes without required approval were delivered as `Draft` or `Unverified`, not completed work.
- [ ] Any material decisions and unresolved limits are recorded in their owning control. Preflight status alone does not require a new report, interview or approval.
- [ ] If multi-agent scheduling was used, the launch contract and corresponding user authorization were verified before dispatch.
- [ ] If a Codex peer task was used, the delivery record identifies its task/thread ID, parent task, same-directory workspace, effective model/effort evidence, lifecycle, Main decision, and archive result.
- [ ] Peer-task windows were reused for rework and archived after acceptance or terminal closure; none were left as unmanaged MALTS work.
- [ ] The work was designed as bounded recoverable rounds, not as a promised fixed one-shot runtime.
- [ ] At long-task start, the user was asked whether to enable unattended auto-continue.
- [ ] If the user did not explicitly authorize unattended auto-continue, no unattended automatic running was started or scheduled.
- [ ] If unattended auto-continue was used, the explicit authorization package, round cap, stop conditions, and report records are present in `PROJECT_CONTROL`.
- [ ] Unattended batches remained within the approved authorization package or obtained new scoped approval before dispatch.
- [ ] Before final validation claims, task status, acceptance criteria, termination status, and report wording were reconciled against the latest evidence.
- [ ] Gap-filling changes were checked across Codex, Claude Code, and OpenCode unless the user explicitly scoped the task to fewer tools.
- [ ] Any unnecessary pending tasks were cancelled, merged, or downgraded.

## Work Task Report

- [ ] A plain user-facing result is provided after completion; a durable report view is refreshed only when requested or materially useful.
- [ ] The report language policy is satisfied: CURRENT `WORK_TASK_REPORT.md` is derived/non-authoritative and on demand; legacy workspace layout strict binding remains compatible; translated mirrors require explicit request.
- [ ] The report records that `DELIVERY_CHECKLIST.en.md` was reviewed before delivery, or explains why it was N/A.
- [ ] The report states result, changes, verification, risks, recovery point, and next step.
- [ ] The report states the growth review result and memory-write decision when the task is non-trivial, includes user correction, or completes a recovery round.
- [ ] The final user response, not only a file, exposes the applicable Growth Routing result; full retrospective execution was only requested or already authorized.
- [ ] If long-term memory could not be written because the external service or target was unavailable, the report names the local fallback record.
- [ ] The report states how a new window or another project folder should resume from recorded files.
- [ ] The user does not need to open every underlying document to understand what happened.

## Final Trust Statement

- Verified:
- Not verified:
- Known risks:
- Recommended user confirmation:

## CURRENT Workspace delivery

- [ ] Current commands documented: `workspace-entry`, `refresh-maintenance-views`, one-hop `reorganize-workspace` / `reorganize-result-contract`, resource Admission/renew/release/reap/verify/UNKNOWN/reconcile/recover, plus existing lifecycle commands.
- [ ] Existing stale report/handoff projections are rebuilt from canonical current controls; old authority or active-Phase prose is absent, and repeated refresh is a byte-preserving no-op.
- [ ] Entry cost evidence records files/bytes/history/writes and fresh-process P50/P95/max; initialization, daily entry, deep validation, and cold recovery are measured separately.
- [ ] Parallel acceptance covers disjoint/overlap/parent-child locators, all capability modes, stale lease/fencing, interruption, unique writer, local quarantine, and explicit reconcile without tool-specific Core rules.
- [ ] Protected legacy workspaces were not silently reorganized; interruption restored original bytes or entered explicit evidence-backed reconcile, and no downgrade chain was used.
- [ ] Active/public/Git/GitHub writes follow their exact reviewed packet; this checklist alone is not authorization.
