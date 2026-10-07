# MALTS 2.0.0 Usage

## 1. Select a mode

Single Agent is the default. Keep simple work under project rules; use Project/Phase/Task for persistent recovery and delegate only with explicit scope and separable responsibilities. Adopted v2 workspaces use service state. Inspect a non-adopted workspace's existing contract without automatic migration.

| Situation | Native Skill | Result and boundary |
|---|---|---|
| Lightweight setup | `malts-project-init` | Applicable entry/goals, no implicit collaboration |
| Material goal/tradeoff ambiguity | `malts-grill-me-preflight` | Read-only clarification, no new permission |
| New long workspace/structural change | `malts-long-project-workspace-init` | Stage boundaries; v2 setup must be Phase-ready |
| Current v2 Task/topic | `malts-v2-task-workflow` | Bounded context and task/phase/artifact/recovery contracts |
| Continuation view | `malts-session-handoff` | On-demand preserved notes, preview and guarded publication |
| Retrospective | `malts-project-retrospective-growth` | Evidence-based advice or authorized trial |
| Lightweight post-verification check | `malts-single-agent-lightweight-growth` | No signal means no action; global edits need their own scope |
| Approved collaboration | `malts-multi-agent-long-task-scheduling` | Roles, budgets, resources and integration acceptance |

## 2. Entry and plans

Verify Boot/discovery and binding, then inspect the current queue and exact Task. Ordinary entry queries facts without full-history scans or implicit Run/Session/Agent/Artifact creation. For plan changes, compare goals, boundaries and actual plan bytes, then revise affected bindings only.

Task scope must be a subset of Phase in_scope and must not intersect out_of_scope. Use `phase.bind-task` for the current Task revision. Revision bindings are exact; a matching plan hash proves content, not execution permission. New native long workspaces require `init`, `project.define`, `phase.define`, `phase.set-active`, then `phase_ready=true`.

## 3. Permission and execution

Reuse applicable user authorization. MCP clients cannot mint Grants or replace Host-bound fields; controllers record existing scope. Check Grant, budget, dependencies, admission and uncertain effects before execution. A request dry run checks shape only and does not evaluate readiness; reviewed `--apply` invokes services.

Managed updates preserve old bytes and bind current SHA-256. Writes, real calls, installation, delegation and publication use their respective approved scopes. See [v2 Operations](V2_PREVIEW_USAGE.md) for requests and response fields.

## 4. Acceptance, pause and recovery

Check business outputs, then record evidence matching each criterion's method/level. `task.accept` still checks current revisions, dependencies, operations and Hosts. Use `verification.rework` before repairing a VERIFYING task. `task-verify` preserves history. One completed Task does not finish a larger user goal.

During pause, create no new effects; inspect pending operations and Hosts. Reconcile UNKNOWN under the original identity. Cancellation acknowledgements and PAUSED do not prove process exit. Recovery checks epoch, checkpoints, consumed budgets and subsequent work, without reviving legacy authority, Grants or Hosts.

## 5. Collaboration and reuse

Declare separable resources, actual Host capabilities and cumulative budgets. Workers return outputs/uncertainties; controllers verify integration. Configuration is not effective-identity/isolation proof.

Artifacts retain ownership, revisions, relationships and current Shared proof. Growth requires sourced proposals, bounded trials and future observations; retain neutral/harmful outcomes and retirement. Handoffs preserve manual notes and compare source tokens/target preimages before publication. See the [State Contract](V2_STATE_CONTRACT.md), [Skill Governance](CAPABILITY_AND_SKILL_GOVERNANCE.md) and [Handoff](HANDOFF.md).

## 6. Diagnostics

| Result | Meaning and action |
|---|---|
| `NOT_APPLIED` / `NOT_EVALUATED` | No execution/readiness proof |
| `NO_LONGER_PROVEN` | Current evidence invalid; inspect inputs and preserve history |
| `RECOVERY_REQUIRED` / `UNKNOWN` | Reconcile the original effect; do not invent a new ID |
| `STALE_PROCESS` | Loaded code differs from active declaration; reload through the Host |
| `GRANT_SCOPE_MISMATCH` | Inspect exact resource/effect scope through the controller |
| `LIFECYCLE_TRANSACTION_OR_RECOVERY_PENDING` | Settle the original transaction, never delete its lock blindly |

See [System Overview](SYSTEM_OVERVIEW.md) for support and limitations.

## Historical assets and adoption

A workspace not yet adopted into v2 is a source for explicit reviewed adoption, not a second v2 writer. Inspect its existing facts, writers, uncertain effects and backup, then use the v2 adoption contract. Do not run legacy initialization/reorganization against an adopted workspace. Current long-project setup requires phase_ready=true and the current Project/Phase/Task services.
