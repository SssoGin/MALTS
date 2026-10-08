# Handoff

MALTS handoffs make project work understandable across windows, interruptions and Agent changes. They preserve the goal, current progress, actual evidence and next eligible work. Current version: **2.0.0**. A handoff is an on-demand continuation view; the selected task services own execution state.

## Default File Names

The default Agent-facing filename is `PROJECT_HANDOFF.md`. An optional user-facing Chinese mirror is `项目交接.md`, created only when requested. Names are conventions, not permission or state authority. Real handoffs belong in the project workspace, never the release repository or immutable installation.

The name makes the continuation view easy to locate, but generation is selected by purpose. If several outputs exist, use the one linked to the current task/source facts; do not pick the newest filename as authority. A translated mirror should identify its source and must not create a parallel set of task states.

Keep the view in a stable project location and link larger deliverables/evidence rather than copy them into it. The runtime generation supplies templates only. This separation allows the project to continue after MALTS is updated while retaining its own original handoff material.

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

A useful continuation separates observed results from proposed next work. For a migration, specify which interface was retained, which output bytes were tested, which checks failed or remain unavailable, and whether a pending write may have occurred. “Most work is done” does not give a successor enough information to act.

The following is a format example; bracketed values identify facts to obtain from the actual task and observations:

```text
Goal: migrate the module while preserving the reviewed public interface.
Contract: Task [id/revision], Phase [id/revision], plan [path/hash].
Observed result: implementation at [output identity]; checks [observed results].
Incomplete: [unsatisfied criterion and affected dependency].
Uncertain effect: operation [original id], [observation needed before retry].
Recovery: checkpoint [identity], Host [actual state], budget [consumption].
Next: reconcile the effect, then run the named remaining compatibility check.
Manual note: [preserved source identity and relevant observation].
```

Avoid embedding credentials, broad raw logs or unexplained internal history. Include a locator and applicable evidence identity when the successor needs a larger source. Preserve failed checks instead of rewriting the example into a fully successful story.

## Plan Binding

Record the owning Phase, current plan reference and exact SHA-256, Task/Phase revisions, relevant dependency versions and the checks needed after a material change. Verify the actual plan bytes before relying on the summary. Adopted v2 work uses current Phase/task services; historical Markdown Plan Recheck does not become its write authority.

Check three relationships before relying on the view: the current task definition, its bound Phase revision, and the actual plan bytes. If a plan changed after handoff generation, the stored narrative can still explain history, but the next action must use the new reviewed definition and bindings.

For example, adding a deployment step changes the execution boundary even if most migration text stays identical. Revise the affected task/Phase instead of appending a sentence that silently grants deployment. Conversely, a spelling correction in a reading view does not itself revise the executable plan.

Record the reason for a material revision and its remaining acceptance work. This enables the successor to distinguish approved changes from proposed changes without treating every note as current permission.

## Cross-Control Binding

In adopted workspaces, verify Boot, lifecycle discovery, workspace binding and current task context before continuation. Reports and handoffs describe those facts without replacing them. Retain adoption seals, original evidence and unresolved effects. Pre-adoption documents explain their own historical contracts and must not be used to revive legacy write ownership.

## Preserve, Preview And Publish

The current services can preserve selected notes/files and preview a bounded handoff. Preview includes its sources, token and partial markers; it proves neither completeness nor permission. Guarded publication compares the exact current Task revision, source token, reviewed existing output and preimage. Inspect failures under the original identity. Creating a missing output is a separately scoped creation, not blind overwrite.

The guarded procedure has four steps. First, capture reviewed manual notes or the existing target file with its exact source hash. Second, request a preview for the current Task/revision and selected note IDs. Third, review the complete preview and its source_token. Fourth, publish to that existing target using its captured preimage and explicit publication authority.

handoff.capture-file observes the existing file under the exclusive file guard and preserves its bytes; it does not edit it. The current note/capture limit is 65,536 bytes. A successful capture applies to that moment, so publication compares the target again. handoff.preserve-note instead records controller-reviewed source bytes; its source_ref is provenance, not a path the service automatically reads.

Publication writes a derived view, not a Task execution Grant. It rejects a partial preview, changed task/source token, missing selected target preimage or changed current bytes. If publication is interrupted, handoff.inspect-publication distinguishes requested output, preimage and divergent bytes without rewriting. An intent without a usable current receipt must be inspected under the same publication ID, not replayed through a new ID.

## Continuation

Read current goals, task state and relevant actual files. Reconcile UNKNOWN under the original operation ID before dependent work. PAUSED, lease expiry, cancellation acknowledgement and transport exit do not prove all writers stopped. Retain the existing budget and later work. See [Usage](USAGE.md), [State Contract](V2_STATE_CONTRACT.md) and [Handoff Operations](V2_PREVIEW_USAGE.md#v2-handoff).

A successor first verifies runtime and workspace identity, then compares the handoff's task/plan references with current context. Inspect actual outputs and the original pending operation before executing dependent work. A preserved note can be authentic yet describe an older source state.

If current facts differ, preserve the view and explain the difference; refresh only the derived portion after reviewing source facts. Do not roll back current task state to make an old handoff match. Where manual text and generated facts conflict, retain both sources and resolve the material question rather than deleting the inconvenient note.

Read [Handoff implementation](../tools/v2_handoff.py) for the guarded capture/publication checks and [Controller Operations](V2_PREVIEW_USAGE.md#v2-handoff) for the current entry.
