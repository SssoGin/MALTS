# MALTS State and Service Contract

This is part of the complete MALTS system documentation. Current implementation/version is2.0.0; workflow context is in [System Overview](SYSTEM_OVERVIEW.md) and [Usage](USAGE.md).

## 1. Format, entry and authority

Core application ID is 1296125012 with exact read/write Schema69, CLI interface 1 and MCP application interface 7. `runtime-contract --root` compares the packaged declaration with static constants; `capabilities` describes loaded contracts. A declaration is not behavior proof; development stores are not upgraded implicitly.

Select native state roots explicitly. Adopted workspaces verify `runtime/v2_binding.json`, store, epoch and source seals. Invalid/missing bindings do not restore legacy authority. Context queries are read-only; controller request defaults to dry run. Current capabilities and service implementations own argument contracts.

## 2. Entities and revisions

| Entity | Responsibility |
|---|---|
| Project | Original goal, current versioned goal and global acceptance |
| Phase | Stage goal, in_scope/out_of_scope, criteria and exact plan hash |
| Task | Acceptable work, scope, revision, dependencies and state |
| Run / Host | Checkpoint and execution/dispatch identity, separate from transport |
| Grant / Budget | Existing actor/resource/effect permission and cumulative allowance |
| Operation | Request hash, lease, epoch, intent and observed/UNKNOWN effects |
| Evidence / Artifact | Acceptance proof, raw/derived lineage, ownership and relationships |
| Growth | Proposal, trial, future outcomes and retirement |

A Phase binds current Project revision and actual plan_ref/plan_sha256. Task scope is a subset of Phase in_scope; each Task revision binds an exact Phase revision. Semantic plan/acceptance changes require revision and affected dependency rebinding, never database patching.

## 3. Task and operation states

Task states include READY, RUNNING, VERIFYING, WAITING, PAUSED, RECOVERY_REQUIRED, COMPLETED and CANCELLED. Service preconditions govern transitions; labels do not grant execution. Revision requires an eligible state and reconciliation of unresolved effects.

Preparation binds Grant, actor, resource, effect, parameters, request hash, lease and epoch. After intent, effects may have occurred. Observation records known results; UNKNOWN retains uncertainty. Prepared operations are not execution proof. Replays must match identity/content; a new ID cannot justify repeating an unknown effect.

## 4. Permission, budgets and concurrency

MCP project/actor/authority Host-bound fields come from configuration and cannot be overridden. Read-only endpoints expose no write actions; write-enabled endpoints still apply service checks. An authority reference records provenance without authenticating a person or enlarging scope.

Budgets preserve cumulative consumption and restoration does not replenish them. Host dispatch checks capability, budget and admission. Leases/fencing constrain managed consumers only; external editors/processes require their own quiescence evidence.

## 5. File adapters

`operation.create-file` is exclusive. `operation.read-file` preparation needs exact `tool='read-file'` and granted relative path. Managed reads can create control records and differ from ordinary read-only context.

Windows `operation.update-file` requires tool, path, content, expected_sha256 and a complete preimage_policy. Protected old bytes and current/post-write bytes are checked. Conflicts/UNKNOWN require original-operation reconciliation or a separately approved repair plan, not a blind new ID.

## 6. Verification and current completion

Criteria have the closed fields criterion_id, description, hard, verification_method and minimum_evidence_level. Evidence binds exact Task revision/criterion, an OBSERVED current-epoch operation and a descriptor. Method/minimum level must match.

`verification.begin` requires settled dependencies/Hosts/effects and blocks new execution while VERIFYING. Rework preserves history and invalidates old proof. Acceptance uses the same boundary; task-verify is read-only current proof. Phase/Project completion needs their own criteria and current task closure.

## 7. Evidence, artifacts and Growth

DPAPI protects content and sensitive definitions. Blob descriptors declare target, classification, sensitivity, review, retention and allowed purposes. Encryption is not redaction; verification/recovery/derivation/Growth uses are separately checked. Derivatives retain lineage; withdrawal/expiry stops dependent reuse.

Artifact relationship graphs, retention dependencies, current Shared content and owners are distinct checks. Historical SUPERSEDED/RETIRED references do not silently redirect to successors. Growth uses proposal/trial states, comparable future evidence and retirement protection. Neutral remains neutral; late positive outcomes cannot revive retired methods.

## 8. Handoff and restoration

Handoff previews include source tokens, bounded facts, partial-page markers and selected manual notes. Guarded publication requires an existing reviewed output, exact preimage and current sources; missing output requires a separate creation step. A handoff is neither permission nor a second source of truth.

Backups cover DB, blobs and declared resources. Host journals and installation transactions have separate retention obligations. Restore uses a verified backup, new destination/epoch and quarantine. Reconcile subsequent work, external effects and budgets before resuming. Cross-user protected restoration is uncertified. Unavailable-store forward recovery must prove adoption lineage and gaps.

## 9. Retention and diagnostics

Blob/reference/inventory/inspection and retirement/recovery queries locate purposes without deletion permission. Terminal states, age and hashes do not replace unique recovery originals. Preserve unresolved effects, raw acceptance, seals and necessary backups; disk usage is not guaranteed bounded.

Errors use stable error_code. Successful request fields are inside result, including result.request_hash. NOT_APPLIED does not evaluate execution preconditions; REQUIRES_REVIEW and error exits are not success.

## 10. Implementation and qualification

v2_service and domain modules enforce these contracts. Domain/transaction/recovery checks, managed files, representative native tasks and installation establish distinct evidence layers. Configuration, self-ratings, synthetic examples and historical completion cannot substitute for one another. See [Overview](SYSTEM_OVERVIEW.md) and [v2 Operations](V2_PREVIEW_USAGE.md).
