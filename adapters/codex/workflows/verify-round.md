# Codex Workflow: Verify MALTS Round

Use this workflow after a MALTS implementation round.

Required checks:

1. Map changed files to the task contract and acceptance criteria.
2. Run the relevant tests, lint checks, installer dry-runs, or document checks.
3. Verify each fact against its owner: Project, selected Phase, explicit Session, workspace machine index, or coordination runtime. Do not use a report/handoff as mutation authority.
4. Classify canonical/authorization/transaction/Admission/fencing/unknown-effect drift as blocking for affected scope; classify CURRENT derived report/handoff drift as warning/local refresh. Preserve legacy workspace layout strict compatibility behavior.
5. Under the resource profile, verify Admission/Phase/actor/lease/fencing/quarantine evidence and release/reconcile state; under the single profile, verify no coordination overhead was introduced.
6. Verify adapter parity across Codex, Claude Code, and OpenCode when protocol, template, checklist, or adapter behavior changed.
7. Record skipped checks and residual risks. Refresh durable report/handoff views only when requested or materially useful.
