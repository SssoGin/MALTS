# Handoff

MALTS handoffs make project work understandable across windows, interruptions and Agent changes. They preserve the goal, current progress, actual evidence and next eligible work. Current version: **2.0.0**. A handoff is an on-demand continuation view; the selected task services own execution state.

## Default File Names

The established Agent-facing name is `PROJECT_HANDOFF.md`. An optional user-facing Chinese mirror is `项目交接.md`, created only when requested. Names are conventions, not permission or state authority. Real handoffs belong in the project workspace, never the release repository or immutable installation.

## Rules

- Write in the user's/project's narrative language, preserving stable protocol fields and codes.
- Preserve unique manual notes and original sources before updating an existing view.
- Never copy secrets, credentials, raw session dumps or private evidence into a public handoff.
- Generate a handoff when another executor/window actually needs it; ordinary successful turns need none.
- Distinguish facts, proposals, unresolved decisions and actual authorization. A next-step suggestion authorizes nothing.
- Use current sources; a stale summary cannot overwrite newer work or certify an unknown effect.

## What To Include

| Item | Content |
|---|---|
| Identity and time | Workspace, selected Task/revision, Phase/revision, source identities and generation time |
| Goal and scope | Original/current goal, protected material and actual acceptance criteria |
| Progress | Delivered results and unfinished work, distinguished from activity |
| Evidence | Checks and applicable input versions, including failed/skipped/unverified checks |
| Recovery | Checkpoint, uncertain operation IDs, relevant Host/writer facts, epoch and consumed budget |
| Next action | Dependencies, unresolved choices and the smallest eligible continuation |
| Manual content | Unique observations/instructions that must survive regeneration |

`runtime/EN/templates/PROJECT_HANDOFF.template.en.md` is a drafting aid. Include enough information for the actual continuation; do not copy the whole database or history.

## Plan Binding

Record the owning Phase, current plan reference and exact SHA-256, Task/Phase revisions, relevant dependency versions and the checks needed after a material change. Verify the actual plan bytes before relying on the summary. Adopted v2 work uses current Phase/task services; historical Markdown Plan Recheck does not become its write authority.

## Cross-Control Binding

In adopted workspaces, verify Boot, lifecycle discovery, workspace binding and current task context before continuation. Reports and handoffs describe those facts without replacing them. Retain adoption seals, original evidence and unresolved effects. Pre-adoption documents explain their own historical contracts and must not be used to revive legacy write ownership.

## Preserve, Preview And Publish

The current services can preserve selected notes/files and preview a bounded handoff. Preview includes its sources, token and partial markers; it proves neither completeness nor permission. Guarded publication compares the exact current Task revision, source token, reviewed existing output and preimage. Inspect failures under the original identity. Creating a missing output is a separately scoped creation, not blind overwrite.

## Continuation

Read current goals, task state and relevant actual files. Reconcile UNKNOWN under the original operation ID before dependent work. PAUSED, lease expiry, cancellation acknowledgement and transport exit do not prove all writers stopped. Retain the existing budget and later work. See [Usage](USAGE.md), [State Contract](V2_STATE_CONTRACT.md) and [Handoff Operations](V2_PREVIEW_USAGE.md#v2-handoff).
