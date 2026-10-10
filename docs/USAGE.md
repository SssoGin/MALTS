# Use MALTS in a Project

Project work begins with a checkable goal and continues through planning, execution, verification and delivery. MALTS workflows preserve the facts needed for interruption, collaboration and future review. Current version: **2.0.3**; controller protocols are in [Operations](V2_PREVIEW_USAGE.md).

## Enter an existing workspace

Use malts-project-init for applicable entry/goals/basic records and malts-long-project-workspace-init for a first executable long-project stage. Complete setup requires phase_ready=true, not merely init or empty directories.

For existing work, verify instructions, installation, binding and current tasks without reinitialization. Read goals/plans/dependencies/accepted results/uncertain effects and relevant history only as needed. Technical Phase/task revisions use phase.bind-task; exact parameters belong to installed workflows/controllers.

For an adopted workspace, controllers can verify the binding with the runtime's `malts_v2.py workspace --workspace '<workspace>'`, then inspect governance-context/task-queue and the exact context. Read only relevant current facts. These queries do not grant execution. A pre-adoption workspace follows its verified contract; old long_workspace commands are not a v2 write route.

Continue from the current task and its remaining criteria. Compare the selected plan/dependencies with actual output identities, and inspect any UNKNOWN effect before retrying the associated work. Do not run an initializer just because the conversation changed.

For a read-only question, read the relevant context and files without defining a new Phase or creating managed execution records. For approved new work, identify whether it changes the current boundary and revise/create the appropriate Phase/task through services. A historical planned stage is not selected automatically because it has a similar name.

If binding is missing or inconsistent, preserve the workspace and inspect its adoption/recovery source. Do not delete the binding or initialize over the directory to make entry succeed. The required next action depends on the actual failure, not an assumed empty project.

## Start a project

Small, clear work can follow project rules directly. Preserve basic project records when decisions span turns; use a long workspace across stages/windows/executors. Use scheduling for approved separable investigation, implementation or verification. Scale, recovery value and actual resources determine the method.

Example: “Use MALTS for this migration, inspect current behavior, define compatibility/acceptance and implement in stages. Allow project edits/checks; do not commit or publish.”

Define outputs, permitted edits, protected material and stopping conditions. Inspect discoverable facts first; use malts-grill-me-preflight for material uncertainty. Separate facts, advice and pending decisions. Analysis alone does not edit the project.

For example, replace an ambiguous repair goal with preserved interface behavior, a reproduced fault, relevant normal-behavior checks and actual outputs. The example itself grants no permission.

Stages define goal/scope/delivery/acceptance; tasks define results, inputs, dependencies and checks. Close a stage against its actual criteria and remaining work; new goals create explicit stages instead of activating historical plans.

Split into checkable outputs, not merely activity lists. Sequence dependent work and assess independent work for parallel value. Revisit affected plans/revisions after material changes while continuing independent authorized work.

A practical request can specify result and exclusions together:

> Use MALTS to migrate this module. Preserve the public interface and user data, identify the compatibility checks, implement the approved change and deliver the evidence. Work in this project; deployment and publication are outside this request.

The Agent first inspects current behavior and project instructions. A useful plan separates the compatibility definition, implementation and integrated checks. It names the result each stage should produce instead of turning every file read into another milestone.

| Work | Output | Acceptance question |
|---|---|---|
| Establish current behavior | Reviewed interface/input baseline | Is the requested compatibility defined? |
| Implement the change | Actual updated module | Does it meet the scoped behavior? |
| Verify integration | Observed checks on the resulting input/output | Are required interactions still correct? |
| Deliver | Result, use and remaining limits | Does the whole request have required proof? |

This example is a decomposition pattern, not a prescribed queue for every project. Use the first active Phase only when long-workspace setup is selected; small work can complete without that overhead.

## Choose the right workflow

| Workflow | Use |
|---|---|
| malts-grill-me-preflight | Material unresolved goals, constraints or acceptance |
| malts-project-init | Explicit lightweight project setup |
| malts-long-project-workspace-init | First Phase-ready long setup or actual Phase/structure change |
| malts-v2-task-workflow | Current selected task, Phase, Artifact or recovery topic |
| malts-session-handoff | Actual continuation across executors/windows |
| malts-single-agent-lightweight-growth | No-write assessment after relevant signals |
| malts-project-retrospective-growth | Requested/authorized deeper review |
| malts-multi-agent-long-task-scheduling | Authorized division of work |

Use these methods within the current request; do not invoke every workflow as a mandatory chain.

## When MALTS Requests An Isolated Preview

Changes to installation, migration, permissions, concurrency or recovery can need an isolated preview before real effects. Ordinary content edits use affected diff/link checks and reusable unchanged behavior evidence. See [Lifecycle](LIFECYCLE.md); a preview is neither business acceptance nor permission to mutate production.

## Verify project control

Complete relevant edits/checks and preserve useful decisions/results/checkpoints without routine reports/timestamp rewrites. Resolve routine choices and continue necessary authorized steps.

Actual results outrank ratings/labels. Check behavior for code, facts/references for documents, real entry/content for installation. A partial check cannot accept a larger goal. Reuse valid unchanged evidence and recheck only affected claims/risks.

Current implementation separates business requirements from file integrity. Use verification.rework before repairing a task under verification. task-verify rechecks current proof; CURRENT_EVIDENCE_VALID supports its declared task scope only.

Compare actual deliverables with original goals. Separate implementation, applicable verification, unknowns and unfinished work. Preserve recovery materials after acceptance and deliver useful results. New features/material tradeoffs do not silently expand closure.

Explain what changed, how to use it, how it was checked and remaining limits. Continue required work and stop when the goal is fulfilled; report/test counts are not quality.

Define a check by its claim, input and expected observation. For code, include relevant normal behavior and the identified fault; for documentation, inspect completeness for its audience, sources, examples and links. Repeating a file-hash check cannot establish semantic correctness.

When a check fails, keep the failing observation, diagnose the affected cause and rework the actual result. In VERIFYING mode, use verification.rework before further execution. After acceptance, task-verify assesses the current proof and can preserve historical acceptance while reporting that changed input is no longer proven.

At delivery, distinguish implemented, verified, unavailable, failed and explicitly deferred items. State a narrower verified result if that is what the evidence supports; do not silently reduce the original goal to that subset. New requirements and major tradeoffs are separate scope decisions.

## Diagnose Without Changing State

Workflows provide current methods. Controllers can query workspace, governance-context, task-queue, context and task-verify. Read-only queries do not initialize/grant execution; request preview does not prove readiness.

| Result | Next action |
|---|---|
| NOT_APPLIED | Preview only; inspect scope/readiness before execution |
| NO_LONGER_PROVEN | Inspect changed inputs/evidence and preserve history |
| UNKNOWN / RECOVERY_REQUIRED | Reconcile the original effect and preserve the scene |
| STALE_PROCESS | Reload normally and reverify entry |
| Permission/resource mismatch | Inspect existing scope, exact targets and writers through the controller |

See [Operations](V2_PREVIEW_USAGE.md) and [System Overview](SYSTEM_OVERVIEW.md).

## Govern Phase And Artifact Lifecycle

Stages define goal/scope/delivery/acceptance; tasks define results, inputs, dependencies and checks. Close a stage against its actual criteria and remaining work; new goals create explicit stages instead of activating historical plans.

Split into checkable outputs, not merely activity lists. Sequence dependent work and assess independent work for parallel value. Revisit affected plans/revisions after material changes while continuing independent authorized work.

Artifacts retain stage ownership, revisions, sources and relationships. Sharing checks current content/eligibility; invalidated artifacts remain historical. Cleanup separately assesses references/recovery.

Durable reports describe outputs/proof/remaining work/limits when needed. Use malts-session-handoff to preserve unique manual notes and create an on-demand current view for another window/executor. Handoffs create no permission and never overwrite newer facts.

A Phase boundary describes what this stage delivers and what belongs elsewhere. Revise it when acceptance or material scope changes, then bind the affected task revisions to the reviewed plan. Pausing is a control transition; it does not itself demonstrate that a native writer stopped.

Register an Artifact with its actual owner/content/revision and dependencies. Promotion to Shared requires reviewed reuse scope and current qualification. Use current advertised services, such as artifact.register, artifact.promote and artifact.reconcile; do not infer an action name from a status such as SUPERSEDED.

Before retirement or cleanup, check whether the result remains an input, a transitive dependency or a required recovery preimage. A file can be unnecessary for the next task yet still required to settle an interrupted earlier effect. Path relocation/deletion and metadata reconciliation have different responsibilities.

## Safety defaults

Default to one Agent, least necessary scope, exact targets and meaningful verification. Reuse approved same-scope actions. Do not derive delegation, provider cost, background work, publishing or destructive effects from Skill selection. Preserve personal content, recovery sources and unknown effects.

## Plan Recheck And Codex Peer Tasks

A material plan/goal change requires the affected current Phase/Task revision and binding. Existing unchanged plans do not need ceremonial rewriting. Native peer tasks remain Host execution routes inside the approved scheduling contract, with observed identity, outputs and controller acceptance; they do not create permission.

## Pause And Continue

Check exact tasks/progress/results, whether effects occurred and whether relevant processes stopped. UNKNOWN means uncertain effect, not failure/non-execution. Reconcile the original identity rather than retrying blindly.

Pause requests, pause states and process exit are distinct. Continue with checkpoints/current plans/remaining budgets; a new window/restoration does not replenish allowance. Preserve necessary backup and later work. See [Lifecycle](LIFECYCLE.md) and [State Contract](V2_STATE_CONTRACT.md).

Preserve the current checkpoint and inspect both managed pending effects and actual Host state. A pause request can remain pending while an operation settles. A process can stop without a business result, and a business effect can occur without its receipt; evaluate those facts separately.

Resume the original eligible run when its contract permits. If successor execution is needed, use the reviewed current task/Host route and retain original consumption and uncertain effects. Do not create a replacement run solely to make pending state disappear.

For a file update interrupted after intent, compare the original request/preimage and actual current bytes through the qualified reconciliation path. For an external editor/provider effect without a qualified observation, preserve the unknown and obtain relevant evidence before repeating it. See [State Contract](V2_STATE_CONTRACT.md).

## Delegate When Useful

Use malts-multi-agent-long-task-scheduling to inspect separation, shared resources, Host capabilities and cost. Define goals/inputs/edit scopes/budgets/outputs/acceptance for each delegation. Prepare reviewable decisions where authorization is missing while continuing unrelated work.

The main Agent retains integration responsibility. Workers return outputs/checks/uncertainties; the controller accepts after execution settlement. Worker success, file existence and model agreement do not finish the project.

Separate modules and independent integration review can help; shared files/sequential dependencies need serialization or explicit coordination. Background/unattended execution has its own scope.

## Review And Accumulate Experience

Use malts-single-agent-lightweight-growth for meaningful correction/verification/recovery/method signals; no signal means no output. Use malts-project-retrospective-growth for material stages, repeated failure or requested review.

Record sources, applicable problems, actions, checks and exclusions. Project recording/trials use existing permission; global rule/Skill edits have separate scope. Current growth.propose/trial/outcome/validate/retire manage later assessments. Retain neutral/harmful/unknown and retirement.

A helpful check can be tried in suitable future work; one success does not justify imposing it on every project forever.

## Workspace Management Data and Migration

Ordinary new workspaces use `workspace-init` to place task state, managed evidence and recovery data under an owned `.malts` directory; explicit external layouts remain supported. Installation updates do not move existing projects. Healthy adopted stores can relocate through a read-only plan, backup/restore, current-effect review and formal forward switch. The new epoch does not restore old Grants/acceptance or activate a Phase automatically. Retain old stores, external historical references and source capsules according to their actual dependencies. See [workspace management and store relocation](MANAGEMENT_AND_RELOCATION.md) for steps and limits.
