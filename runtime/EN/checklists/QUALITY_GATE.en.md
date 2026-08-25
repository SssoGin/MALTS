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
- [ ] `WORK_TASK_REPORT.md` exists when a task or phase report is required; narrative uses the user's/project's language, and any full translated mirror exists only when explicitly requested.
- [ ] For documentation sync work, source/target files, sync direction, and model/cost strategy were recorded.

## Artifact Lifecycle Gate

- [ ] The workspace remains `NOT_ENROLLED` unless an exact enrollment preview, reviewed indexes, operation ID, and explicit `--apply` authorization exist.
- [ ] Project control contains only compact enrollment/index pointers; detailed rows belong to the owning Phase, Session, Shared, or Archive registry.
- [ ] `artifact audit`, `validate`, `maintain`, `compact`, and `recover` used bounded declared references and did not recursively scan undeclared payload trees.
- [ ] Every Artifact mutation was dry-run first and, on apply, used an exact operation ID, workspace lock, persisted journal, full-state preconditions, and atomic replacement/rollback evidence.
- [ ] Artifact mutation did not move/delete payloads, invoke VCS, create a Session, silently adopt legacy directories, or recreate a missing declared index.
- [ ] Promotion/supersession preserved one current Shared authority and updated every declared active reference or failed closed.
- [ ] An enrolled owner with `UNRESOLVED` rows was not closed; stale lock/journal state was reported for exact manual review and never auto-deleted.

## Workspace Cross-Control Consistency Gate

- [ ] Fresh workspaces use exact CURRENT with default `single_phase`; supported legacy inputs are classified explicitly and are not silently reorganized by entry, validation, recovery, maintenance, or installation update.
- [ ] Project/Phase/Session facts have one Markdown owner; workspace schema/profile/index and coordination authority have one runtime owner. CURRENT report/handoff views are derived/on-demand; legacy workspace layout current projection bindings remain strict.
- [ ] `phase-boundary-review` operation status is not treated as review outcome, persistence, decision, or authorization; only `record-phase-boundary-review` persists the record, and later mutation authorization remains separate.
- [ ] Full Phase-control SHA-256 plus normalized boundary/review/recovery hashes agree across canonical authority and machine bindings; any refreshed view binds exact current bytes without becoming authority.
- [ ] Structural, binding, deterministic-consistency, maintenance-warning, and advisory-semantic findings are reported separately; safety-critical drift blocks affected mutations while CURRENT derived-view drift remains local warning/reconcile.
- [ ] Recovery selects active Session checkpoint, active Phase recovery, explicitly bound terminal Phase, then Project recovery; no latest-historical-Session fallback exists.
- [ ] Workspace/coordination mutations used dry-run, exact expected hashes, a unique operation ID, shared `runtime/workspace_transaction.lock.json`, `runtime/workspace_transactions/`, and post-lock preimage checks; Artifact transaction paths/codes remain unchanged.
- [ ] An interrupted workspace transaction is recovered only through exact journal-hash `recover-workspace-transaction` review/apply; failed recovery retains lock/journal evidence.

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
- [ ] New-window continuation starts from bounded `workspace-entry --task-class CONTEXT_RECOVERY` and current owner files; it does not select reports, handoffs, history, or Sessions merely by recency.

## Multi-Agent Dispatch Gate

- [ ] Task type and difficulty were assessed before suggesting or enabling multi-agent mode.
- [ ] Multi-agent was suggested only when it could reduce risk, improve independent verification, enable non-conflicting parallel work, or improve recoverability.
- [ ] If the task was S0/S1 or merge cost exceeded benefit, single-agent mode was used or the reason for escalation was recorded.
- [ ] The route decision is explicitly `0`, `1`, or `N`; no fixed role chain or minimum role count was imposed.
- [ ] Role names describe responsibility only; model and effort were selected from task difficulty, risk, budget, and current runtime evidence.
- [ ] If the user requested multi-agent mode, the launch review packet was shown before dispatch.
- [ ] The launch review packet listed the overall goal, total plan, each planned agent, model name or model policy, task, and short plan.
- [ ] The user was asked whether they wanted to specify sub-agent models and was shown the accepted model specification format.
- [ ] The user explicitly replied `确认运行` before any real sub-agent dispatch.
- [ ] Any model/scope/batch changes during review were reflected in task contracts before dispatch.
- [ ] Launch review reference and approved batch ID are recorded in the Result Contract before dispatch.
- [ ] `requested`, `recommended`, `configured`, and `effective` route selections are recorded separately.
- [ ] Runtime effort ID, normalized reasoning tier, and display label are not conflated.
- [ ] Configuration, CLI help, or interface discovery alone was not labeled `effective_verified`.
- [ ] Every fallback identifies hard/soft constraint treatment, reason, binding status, and usage evidence.
- [ ] `N > 1` is bounded by approved Agent count, contract concurrency, effective runtime capacity, and either read-only/non-conflicting scope or valid typed resource Admissions with current leases/fencing.
- [ ] `agent_route_planner.py` and `result_controller.py` were treated as advisory/validation components and not as proof of real dispatch.
- [ ] A Codex peer task, if used, is recorded as `codex-peer-task` / `delegation_mode=peer-task`, uses the current task workspace, and is not described as native `spawn_agent`.
- [ ] Peer-task lifecycle evidence covers PLANNED through RETURNED and Main acceptance/rework/block, then ARCHIVED; rework reused the existing task unless replacement was explicitly permitted.
- [ ] Hard peer-task model/effort/no-fallback constraints and effective workspace/model evidence were verified; task creation or configuration alone was not treated as effective proof.
- [ ] Real Agent/provider validation is explicitly `G4 PASS`, `G4 FAIL`, or `G4 NOT RUN`; component tests are not presented as G4.
- [ ] Agent Dispatch Log, task contracts, returned reports, and Agent Feedback Log agree on task ID, role, runtime agent ID when available, model policy, and main-controller decision.

## Unattended Auto-Continue Gate

- [ ] At long-task start, the user was asked whether to enable unattended auto-continue.
- [ ] Unattended continuation was used only if explicitly authorized by the user.
- [ ] If not explicitly authorized, unattended automatic running was not started, scheduled, or implied.
- [ ] `PROJECT_CONTROL` records allowed scope, prohibited operations, multi-agent permission, model policy, round/time caps, stop conditions, and report requirements.
- [ ] Each unattended round persisted only material owner-local recovery/state deltas; an on-demand work report was refreshed only when the authorization package required it.
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

- [ ] After verification, the no-write L1 Growth Routing Gate was evaluated before final delivery; `NO_OUTPUT` was silent and every other route was visible to the user.
- [ ] A report-only Growth entry was not used as a substitute for the user-visible Growth result.
- [ ] L1 made no durable write; L2 project maintenance and L3 system promotion retained their separate authorization gates.
- [ ] Reusable experience candidates are recorded when meaningful.
- [ ] One-off details are not written into long-term memory.
- [ ] Any proposed rule has trigger, action, check, and boundary.
- [ ] The user-facing report states the growth review result for non-trivial tasks, user corrections, recovery rounds, or failures.
- [ ] If the external long-term memory service or global memory target is unavailable, the candidate is preserved locally and the report states that no long-term memory write actually happened.

## User Report

- [ ] A clear user-facing result is ready. A durable `WORK_TASK_REPORT.md` view exists only when requested or materially required and is not treated as lifecycle authority.

## Workspace v5 and compatibility gates

- [ ] CURRENT workspace/Result contracts are used only after explicit reviewed one-hop reorganization, or the existing supported legacy compatibility input remains byte-unchanged; no silent reorganization or user-visible version chain.
- [ ] Repeated unchanged `workspace-entry` is bounded, opens no history, performs zero writes, creates no Phase/Session/Agent/Artifact/coordination state, and leaves bytes/timestamps unchanged.
- [ ] `single_phase` has no coordination overhead; every `resource_admission` writer has a current Phase hash, valid Admission, unexpired lease, exact fencing tokens, and clear affected quarantine domains.
- [ ] Disjoint locators may proceed, while overlap, parent/child paths, aliases, exclusive/queued/isolate-required capabilities, stale executors, and `UNKNOWN` effects follow deterministic admission/quarantine/reconcile rules.
- [ ] Safety-critical drift is `BLOCKED` only for its affected authority/resources; CURRENT derived report/handoff drift is `WARNING` and local refresh, while legacy workspace layout projection drift retains strict compatibility behavior.
- [ ] A failed Attempt did not auto-retry or promote Task/Phase terminal state; `max_authorized_rounds` STOP enforced.
- [ ] External side effects have typed observations/counted units; UNKNOWN dispatch/outcome/charge failed closed under finite bounds.
- [ ] Workspace transaction committed exactly once with preimages/recovery evidence; no instantaneous-atomicity claim.
- [ ] `scoped-readiness` and `refresh-project-instructions` were used only as documented; markerless custom files untouched.
- [ ] Workspace/coordination writers shared one lock and rechecked exact preimages after lock acquisition; no stale writer committed.
