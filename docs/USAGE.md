# Using MALTS in a Project

This guide follows a project from start to delivery. Current version is 2.0.0. See [Installation](INSTALL.md) and [Operations](V2_PREVIEW_USAGE.md) for exact setup and controller protocols. Ordinary users can select workflows in natural language.

## 1. Choose a working mode

Small, clear work can follow project rules directly. Preserve basic project records when decisions span turns; use a long workspace across stages/windows/executors. Use scheduling for approved separable investigation, implementation or verification. Scale, recovery value and actual resources determine the method.

Example: “Use MALTS for this migration, inspect current behavior, define compatibility/acceptance and implement in stages. Allow project edits/checks; do not commit or publish.”

## 2. Clarify goals, scope and acceptance

Define outputs, permitted edits, protected material and stopping conditions. Inspect discoverable facts first; use malts-grill-me-preflight for material uncertainty. Separate facts, advice and pending decisions. Analysis alone does not edit the project.

For example, replace an ambiguous repair goal with preserved interface behavior, a reproduced fault, relevant normal-behavior checks and actual outputs. The example itself grants no permission.

## 3. Establish or enter a project

Use malts-project-init for applicable entry/goals/basic records and malts-long-project-workspace-init for a first executable long-project stage. Complete setup requires phase_ready=true, not merely init or empty directories.

For existing work, verify instructions, installation, binding and current tasks without reinitialization. Read goals/plans/dependencies/accepted results/uncertain effects and relevant history only as needed. Technical Phase/task revisions use phase.bind-task; exact parameters belong to installed workflows/controllers.

## 4. Plan finite stages/tasks

Stages define goal/scope/delivery/acceptance; tasks define results, inputs, dependencies and checks. Close a stage against its actual criteria and remaining work; new goals create explicit stages instead of activating historical plans.

Split into checkable outputs, not merely activity lists. Sequence dependent work and assess independent work for parallel value. Revisit affected plans/revisions after material changes while continuing independent authorized work.

## 5. Execute, verify and preserve progress

Complete relevant edits/checks and preserve useful decisions/results/checkpoints without routine reports/timestamp rewrites. Resolve routine choices and continue necessary authorized steps.

Actual results outrank ratings/labels. Check behavior for code, facts/references for documents, real entry/content for installation. A partial check cannot accept a larger goal. Reuse valid unchanged evidence and recheck only affected claims/risks.

Current implementation separates business requirements from file integrity. Use verification.rework before repairing a task under verification. task-verify rechecks current proof; CURRENT_EVIDENCE_VALID supports its declared task scope only.

## 6. Pause and continue

Check exact tasks/progress/results, whether effects occurred and whether relevant processes stopped. UNKNOWN means uncertain effect, not failure/non-execution. Reconcile the original identity rather than retrying blindly.

Pause requests, pause states and process exit are distinct. Continue with checkpoints/current plans/remaining budgets; a new window/restoration does not replenish allowance. Preserve necessary backup and later work. See [Lifecycle](LIFECYCLE.md) and [State Contract](V2_STATE_CONTRACT.md).

## 7. Delegate when useful

Use malts-multi-agent-long-task-scheduling to inspect separation, shared resources, Host capabilities and cost. Define goals/inputs/edit scopes/budgets/outputs/acceptance for each delegation. Prepare reviewable decisions where authorization is missing while continuing unrelated work.

The main Agent retains integration responsibility. Workers return outputs/checks/uncertainties; the controller accepts after execution settlement. Worker success, file existence and model agreement do not finish the project.

Separate modules and independent integration review can help; shared files/sequential dependencies need serialization or explicit coordination. Background/unattended execution has its own scope.

## 8. Artifacts, reports and handoffs

Artifacts retain stage ownership, revisions, sources and relationships. Sharing checks current content/eligibility; invalidated artifacts remain historical. Cleanup separately assesses references/recovery.

Durable reports describe outputs/proof/remaining work/limits when needed. Use malts-session-handoff to preserve unique manual notes and create an on-demand current view for another window/executor. Handoffs create no permission and never overwrite newer facts.

## 9. Review and accumulate experience

Use malts-single-agent-lightweight-growth for meaningful correction/verification/recovery/method signals; no signal means no output. Use malts-project-retrospective-growth for material stages, repeated failure or requested review.

Record sources, applicable problems, actions, checks and exclusions. Project recording/trials use existing permission; global rule/Skill edits have separate scope. Current growth.propose/trial/outcome/validate/retire manage later assessments. Retain neutral/harmful/unknown and retirement.

A helpful check can be tried in suitable future work; one success does not justify imposing it on every project forever.

## 10. Finish a bounded round

Compare actual deliverables with original goals. Separate implementation, applicable verification, unknowns and unfinished work. Preserve recovery materials after acceptance and deliver useful results. New features/material tradeoffs do not silently expand closure.

Explain what changed, how to use it, how it was checked and remaining limits. Continue required work and stop when the goal is fulfilled; report/test counts are not quality.

## 11. Entry and diagnostics

Workflows provide current methods. Controllers can query workspace, governance-context, task-queue, context and task-verify. Read-only queries do not initialize/grant execution; request preview does not prove readiness.

| Result | Next action |
|---|---|
| NOT_APPLIED | Preview only; inspect scope/readiness before execution |
| NO_LONGER_PROVEN | Inspect changed inputs/evidence and preserve history |
| UNKNOWN / RECOVERY_REQUIRED | Reconcile the original effect and preserve the scene |
| STALE_PROCESS | Reload normally and reverify entry |
| Permission/resource mismatch | Inspect existing scope, exact targets and writers through the controller |

See [Operations](V2_PREVIEW_USAGE.md) and [System Overview](SYSTEM_OVERVIEW.md).
