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

这里只引用 runtime authority，不复制其 ledger。

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

这个可选的 owner-local registry 仅用于显式 enrollment 合同和明确有界的 Session Artifact；本节存在绝不创建或延长 Session。

| Artifact ID | Role | Locator | Authority | VCS | Verification | Retention | Disposition | Relationships | Role Contract |
|---|---|---|---|---|---|---|---|---|---|

<!-- MALTS:section=session-checkpoint -->
## Checkpoint

- Recovery schema: `1`
- Record ID: `session:<SESSION_ID>:checkpoint`
- Summary: Session <SESSION_ID> 在 Phase <PHASE_ID> 中处于 active 状态。
- Next action: <SESSION_GOAL>
- Evidence references: `session:<SESSION_ID>`
- Recorded at: `<TIMESTAMP>`
- Completed:
- Evidence:
- Risks or blockers:

此 Session control 不拥有、也不得重新定义 canonical project goal。
