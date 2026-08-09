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

<!-- MALTS:section=session-commands -->
## Commands And Touch Set

- Allowed commands:
- Allowed touch set:
- Prohibited operations:

<!-- MALTS:section=session-checkpoint -->
<!-- MALTS:section=session-artifacts -->
## Artifact Registry

这个可选的 owner-local registry 仅用于显式 enrollment 合同和明确有界的 Session Artifact；本节存在绝不创建或延长 Session。

| Artifact ID | Role | Locator | Authority | VCS | Verification | Retention | Disposition | Relationships | Role Contract |
|---|---|---|---|---|---|---|---|---|---|

<!-- MALTS:section=session-checkpoint -->
## Checkpoint

- Completed:
- Evidence:
- Risks or blockers:
- Next action:

此 Session control 不拥有、也不得重新定义 canonical project goal。
