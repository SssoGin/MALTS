# MALTS State and Service Contract

The state contract binds goals, task revisions, permissions, operations, evidence and recovery to the selected workspace. CLI and MCP call the same domain services through different Host permission surfaces. Current implementation: **2.0.0**.

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

Definitions and observations have different lifetimes. A revised task changes intended work and criteria; an old operation still records what was requested/performed under its original revision. Evidence cannot be reassigned to the new task meaning merely by editing a label.

Phase membership binds a task revision to the current phase revision and plan. Dependencies bind exact predecessor revisions. When one of these changes, inspect affected bindings and remaining work before admitting new effects. This is stronger than a flat queue that always reads the latest row: it makes the version actually used by a result inspectable.

Narrative content can remain outside the machine store, such as an actual plan file, but the applicable revision binds its bytes. A hash validates identity, not business adequacy. The controller reviews the plan and criteria separately from service validation.

## 3. Task and operation states

Task states include READY, RUNNING, VERIFYING, WAITING, PAUSED, RECOVERY_REQUIRED, COMPLETED and CANCELLED. Service preconditions govern transitions; labels do not grant execution. Revision requires an eligible state and reconciliation of unresolved effects.

Preparation binds Grant, actor, resource, effect, parameters, request hash, lease and epoch. After intent, effects may have occurred. Observation records known results; UNKNOWN retains uncertainty. Prepared operations are not execution proof. Replays must match identity/content; a new ID cannot justify repeating an unknown effect.

The operation progression separates preparation from permission to perform the effect:

```text
PREPARED -> INTENT_RECORDED -> OBSERVED  (known successful observation)
                            -> FAILED   (known reported failure)
                            -> UNKNOWN  (effect remains uncertain)
```

A prepared request can be cancelled as unexecuted only while it remains PREPARED. After intent, cancellation cannot erase the possibility of an effect. Known failure still needs its actual observation; it is not a universal proof of rollback. UNKNOWN retains the original operation and quarantines its managed lease/resources until reconciliation.

An identical replay can return a historical decision without performing the effect again. Compare request identity and expected hash; do not change actor/parameters or introduce another operation ID as a retry shortcut. Managed create/read/update adapters handle their own intent and observations, so callers must not pre-commit an unrelated manual intent for them.

## 4. Permission, budgets and concurrency

MCP project/actor/authority Host-bound fields come from configuration and cannot be overridden. Read-only endpoints expose no write actions; write-enabled endpoints still apply service checks. An authority reference records provenance without authenticating a person or enlarging scope.

Budgets preserve cumulative consumption and restoration does not replenish them. Host dispatch checks capability, budget and admission. Leases/fencing constrain managed consumers only; external editors/processes require their own quiescence evidence.

The admission checks connect identity and effect: the current Task revision, actor's exact Grant, resource/effect, dependency readiness, operation budget and current resource identity. Intent records receive an epoch/fence lease; the execution adapter rechecks that token and the actual resource before use. A valid transport connection supplies none of these facts by itself.

Budgets count committed intents and retain cumulative use. A new Run, revised presentation or backup restore cannot reset that count. An amended budget is an explicit reviewed policy change, with current preconditions; it cannot erase already consumed operations.

Leases bind owner, epoch, fence and expiry. Renewal is explicit. Expiry prevents old managed execution, but does not prove an external process stopped or undo its effect. Shared editors/services/devices require their own observed writer boundary in addition to managed path/resource admission.

## 5. File adapters

`operation.create-file` is exclusive. `operation.read-file` preparation needs exact `tool='read-file'` and granted relative path. Managed reads can create control records and differ from ordinary read-only context.

Windows `operation.update-file` requires tool, path, content, expected_sha256 and a complete preimage_policy. Protected old bytes and current/post-write bytes are checked. Conflicts/UNKNOWN require original-operation reconciliation or a separately approved repair plan, not a blind new ID.

| Adapter | Target rule | Preparation/result boundary |
|---|---|---|
| create-file | New exact relative file only | Exclusive create; existing target rejects |
| read-file | Existing granted relative file | Preparation includes tool/path; result is observed bytes/hash |
| update-file | Existing exact relative file | Current SHA-256, UTF-8 replacement and protected preimage policy |

For a read, max_bytes/max_characters belong to execution limits rather than prepare parameters. A missing tool/path cannot be repaired by guessing a broad resource. For an update, inspect the full current preimage policy template provided by the configured Host; summary labels are not the complete descriptor.

The update guard compares the exclusively opened file against expected_sha256, retains the preimage, writes and checks the new bytes. If current content changed, preserve the original operation and use its current reconciliation/repair contract. A managed byte result does not prove that a build passed or an Editor/network operation occurred.

## 6. Verification and current completion

Criteria have the closed fields criterion_id, description, hard, verification_method and minimum_evidence_level. Evidence binds exact Task revision/criterion, an OBSERVED current-epoch operation and a descriptor. Method/minimum level must match.

`verification.begin` requires settled dependencies/Hosts/effects and blocks new execution while VERIFYING. Rework preserves history and invalidates old proof. Acceptance uses the same boundary; task-verify is read-only current proof. Phase/Project completion needs their own criteria and current task closure.

Hard criteria must all have evidence of the required method/level. A caller-declared review is not an independent verifier merely because its JSON says PASS. verification.managed-files supplies a fixed bounded file-integrity method/level; use separate evidence for business behavior required by the task.

Verification mode settles dependencies, operations and managed Hosts before acceptance and blocks new effects while checking the result. Rework returns to executable work and invalidates the previous current basis without erasing history. Small tasks can accept through the same gate atomically.

Phase completion checks its current plan, hard criteria, task membership/current acceptance and Artifact reference closure. Project completion aggregates its own requirements. An empty phase or one accepted file does not finish that wider scope. Current-proof queries must distinguish historical replay from CURRENT_EVIDENCE_VALID.

## 7. Evidence, artifacts and Growth

DPAPI protects content and sensitive definitions. Blob descriptors declare target, classification, sensitivity, review, retention and allowed purposes. Encryption is not redaction; verification/recovery/derivation/Growth uses are separately checked. Derivatives retain lineage; withdrawal/expiry stops dependent reuse.

Artifact relationship graphs, retention dependencies, current Shared content and owners are distinct checks. Historical SUPERSEDED/RETIRED references do not silently redirect to successors. Growth uses proposal/trial states, comparable future evidence and retirement protection. Neutral remains neutral; late positive outcomes cannot revive retired methods.

## 8. Handoff and restoration

Handoff previews include source tokens, bounded facts, partial-page markers and selected manual notes. Guarded publication requires an existing reviewed output, exact preimage and current sources; missing output requires a separate creation step. A handoff is neither permission nor a second source of truth.

Backups cover DB, blobs and declared resources. Host journals and installation transactions have separate retention obligations. Restore uses a verified backup, new destination/epoch and quarantine. Reconcile subsequent work, external effects and budgets before resuming. Cross-user protected restoration is uncertified. Unavailable-store forward recovery must prove adoption lineage and gaps.

A source_token detects the owner facts presented in the handoff snapshot. It is not a hash of every possible business dependency or a file compare-and-swap token. Selected note bodies retain their reviewed source identity, while underlying source files are not all reverified by preview. Publication therefore needs both current source-token checks and a guarded exact target preimage.

Backup verification checks the declared stored data/resources. Restoration writes a new selected destination and epoch, then requires reconciliation with work performed after the backup. Missing records cannot prove that a provider call or Host launch never occurred. Preserve original receipts, quarantine and consumption when accounting for that gap.

Host journals and installation snapshots have distinct owners and cannot be replaced merely by restoring the task store. Verify their correspondence and actual process state separately before admitting successor execution.

## 9. Retention and diagnostics

Blob/reference/inventory/inspection and retirement/recovery queries locate purposes without deletion permission. Terminal states, age and hashes do not replace unique recovery originals. Preserve unresolved effects, raw acceptance, seals and necessary backups; disk usage is not guaranteed bounded.

Errors use stable error_code. Successful request fields are inside result, including result.request_hash. NOT_APPLIED does not evaluate execution preconditions; REQUIRES_REVIEW and error exits are not success.

## 10. Implementation and qualification

v2_service and domain modules enforce these contracts. Domain/transaction/recovery checks, managed files, representative native tasks and installation establish distinct evidence layers. Configuration, self-ratings, synthetic examples and historical completion cannot substitute for one another. See [Overview](SYSTEM_OVERVIEW.md) and [v2 Operations](V2_PREVIEW_USAGE.md).
