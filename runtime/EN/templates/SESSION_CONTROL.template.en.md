# SESSION_CONTROL

<!-- MALTS:section=session-metadata -->
## Session Metadata

- Session ID: <SESSION_ID>
- Phase ID: <PHASE_ID>
- Reason: <SESSION_REASON>
- Status: ACTIVE
- Created at: <TIMESTAMP>
- Updated at: <TIMESTAMP>

<!-- MALTS:section=session-plan-binding -->
## Plan Binding

- Active plan reference: `<ACTIVE_PLAN_REFERENCE>`
- Plan revision: `<PLAN_REVISION>`
- Plan content SHA-256: `<PLAN_SHA256>`
- Authorization/scope rechecked: `<AUTHORIZATION_SCOPE_RECHECKED>`
- Launch review reference: `<LAUNCH_REVIEW_REFERENCE>`

<!-- MALTS:section=session-scope -->
## Bounded Scope

<SESSION_GOAL>

<!-- MALTS:section=session-resource-admission-binding -->
## Resource Admission Binding

Reference runtime authority; do not copy its ledger.

- Governance profile: `single_phase` / `resource_admission`
- Admission ID: `N/A`
- Actor ID: `N/A`
- Typed locator/capability scope reference: `N/A`
- Required fencing token references: `N/A`
- Lease expiry / latest verification evidence: `N/A`
- Quarantine/reconcile state: `N/A`

<!-- MALTS:section=session-commands -->
## Commands And Touch Set

- Allowed commands:
- Allowed touch set:
- Prohibited operations:

<!-- MALTS:section=session-artifacts -->
## Artifact Registry

This optional owner-local registry is used only for an explicitly enrolled contract and explicitly bounded Session Artifacts. Its presence never creates or extends a Session.

| Artifact ID | Role | Locator | Authority | VCS | Verification | Retention | Disposition | Relationships | Role Contract |
|---|---|---|---|---|---|---|---|---|---|

<!-- MALTS:section=session-checkpoint -->
## Checkpoint

- Recovery schema: `1`
- Record ID: `session:<SESSION_ID>:checkpoint`
- Summary: Session <SESSION_ID> is active in Phase <PHASE_ID>.
- Next action: <SESSION_GOAL>
- Evidence references: `session:<SESSION_ID>`
- Recorded at: `<TIMESTAMP>`
- Completed:
- Evidence:
- Risks or blockers:

This Session control does not own or redefine the canonical project goal.
