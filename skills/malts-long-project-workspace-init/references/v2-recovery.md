# Adopted v2 migration and forward recovery

Use this reference for an already adopted or explicitly selected v2 workspace. Verify the actual runtime, binding, selected state root, epoch, current Task/revision and exact Run/Checkpoint. Preserve the adoption receipt, source seals, backups and post-adoption work. Never restore legacy runtime write authority or delete a binding to recreate an old workspace.

Before restoring or resuming, reconcile each original UNKNOWN operation against actual effects. A missing receipt, expired lease, cancelled RPC or pause does not prove non-execution or writer quiescence. Do not use a new operation ID to replay an uncertain effect. Inspect the original registered Host and relevant external writer before migration/takeover; observation of one axis does not settle the other.

If accepted work exists after the backup, compare the backup and retained post-backup receipts and outputs. Preserve that work and its references in the reviewed v2 forward-recovery path. Do not restore a snapshot over newer accepted bytes or choose a historical Run by recency. Unreadable stores, missing deltas, unknown writers or divergent bytes remain review conditions, not a successful restore.

Restoring changes the epoch and does not revive old Grants, Hosts, Runs or acceptance. Reverify current evidence before using it. It also does not replenish consumed operation or Host launch budgets: retain recorded consumption, reconcile post-backup usage, and keep missing usage unknown. Restored Host budgets are revoked with `consumption_known=false` and `consumption_basis=UNKNOWN_AFTER_RESTORE` until the controller completes the current reconciliation/authorization contract. A new Run, checkpoint or directory is not a fresh allowance.

For review-only work, report the selected recovery path, original effect identities, protected new outputs, necessary writer/budget checks and unresolved conditions without restoring, replaying, opening a successor or changing state.

For authorized implementation, verify the full DB/blob/reference backup closure, follow current controller recovery services, keep quarantine/isolation until reviewed reconciliation, reactivate/bind explicitly and verify actual restored outputs. Required Artifact successor handoff remains enforced. Fix only affected dependencies; preserve history and unrelated accepted results.

## Related controller contract

Use the same runtime's bounded `recovery-inspect`, exact Task `context` and retained operation/Host observations before any restore. A backup used as a source needs `verify-backup` and complete DB/blob/watermark closure. `restore` uses a new destination and the reviewed backup identity; restoration is not an in-place replay or automatic activation. `recovery-review` binds the current epoch/backup/state basis plus complete project-root, resource, writer and Task dispositions, including every unresolved external effect.

Only after current reconciliation may the controller explicitly reactivate the reviewed Phase, bind the affected Task revision and resume the exact Run/checkpoint. A successor must retain selected required Artifact references and its cumulative budget. Missing fields or an unavailable recovery action require an exact controller handoff. Phase changes unrelated to the recovery, Growth and old runtime write procedures are not prerequisites for this review.
