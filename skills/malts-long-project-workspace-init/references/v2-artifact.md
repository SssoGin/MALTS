# Adopted v2 Artifact and Shared-proof review

Use this reference for an explicitly selected Artifact or recovery reference. Enrollment is optional; producing a file does not create an Artifact lifecycle. The v2 store owns the exact identities and relations, not an old Markdown registry.

Read the selected Artifact's owner, definition/input digest, source Task/revision/acceptance, operation/evidence identity, locator and dependency closure. Distinguish declaration, observed bytes, accepted Task and current Shared validity. A historical CURRENT label or relation audit is not current payload validation.

Use controller read services such as `artifacts`, `artifact-audit-relations` and `artifact-verify-shared` for the exact selected objects and bounded relation budget. Check actual source/input bytes when the requested proof requires them. Changed inputs invalidate affected reuse; preserve the old Artifact identity and evidence rather than redirecting it to a newer CURRENT source.

Artifact registration, disposition, promotion, retirement, relation-index repair and recovery binding are trusted-controller actions. Their existence does not expand a Worker MCP endpoint or mint a Grant. A review-only request records no promotion, rebuild, deletion or implicit enrollment.

For recovery, select the exact current Run/Checkpoint and explicit required references. Absence of declared pins is not permission to select the latest historical object. Pending required-reference handoff blocks ordinary `run.open`; route exact successor creation and changed-pin review through the controller. Do not revive old Hosts, Grants or consumed allowances. Preserve source, dependency, recovery and audit references; expiry/revocation stops reuse rather than authorizing deletion.

## Related controller contract

Use the current action catalog for a concrete Artifact disposition. Select exact `artifact_id`/definition revision and source Task/operation/evidence identities returned by the read services; never infer them from a filename or CURRENT label. `artifact.register`, `artifact.reconcile`, `artifact.inspect-payload`, `artifact.promote`, `artifact.retire-shared`, `artifact.bind-recovery` and `artifact.recover-successor` are controller actions, not implied Worker capabilities. A needed field absent from bounded metadata is a specific controller handoff, not a reason to load unrelated workflows.

This review has no Phase activation, Growth trial, legacy migration or general-guide prerequisite. Actual payload proof and dependency/reference preservation still require the relevant input observations; a shorter reference does not relax them.
Unresolved or UNKNOWN effects and unavailable source observations remain explicit review conditions; an empty relation result cannot convert them to a valid payload proof.
