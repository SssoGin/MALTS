# MALTS 2.0.0 Core Design

## 1. Problem and objectives

Long-task risk extends beyond context length. Across windows, tools and processes, an old plan can overwrite a new decision, an external effect can occur without a receipt, and a generated file can still fail business acceptance. A prose summary alone cannot reliably distinguish current facts, history and permission.

MALTS makes those distinctions service-checkable: work binds explicit goals and revisions, effects use existing permission, uncertainty requires reconciliation, and completion requires evidence covering its scope. Models retain ordinary reasoning; not every judgment becomes a permanent rule or an extra approval.

## 2. Responsibilities and authority

Models interpret goals and make business decisions. Hosts provide tools, permissions, process and identity capabilities. MALTS owns state, dependencies, admission, budgets, evidence and recovery contracts. A declaration at one layer cannot substitute for another layer's observed result.

The selected v2 store is the execution source of truth. CLI and MCP call the same domain services through `v2_service.py`. Project/Phase/Task definitions carry revisions, a Phase binds actual plan SHA-256, and Task dependencies bind predecessor revisions. Markdown, reports and handoffs remain interpretable sources/views, without a second writable queue.

Core Schema69 is the exact current read/write format; `runtime/v2_runtime_contract.json` declares it. Editing a version field does not upgrade a development database. An adopted workspace's binding and source seals identify its adoption boundary; removing them cannot restore legacy write authority.

## 3. Execution, concurrency and recovery

A Grant records the authorized actor, resource and effect. Budgets track cumulative consumption; a new Run or restoration is not a new allowance. Admission, leases and fencing reject stale actors through managed interfaces. Fencing requires a current generation/lease identity, not global exclusion of tools outside those interfaces.

An operation is prepared and hash-bound, persists an intent before execution, then records an observation of the actual effect. A missing receipt retains UNKNOWN. UNKNOWN means uncertain effect, not failure, non-execution or permission to retry. Reconciliation continues under the original operation identity.

Managed `create-file` is exclusive. Windows `update-file` compares current opened-file bytes, preserves the preimage, writes and verifies. Conflicts and uncertain results retain their original identity. File adapters prove the declared file result, not unrelated network or editor effects.

Pause, cancellation and process quiescence are separate facts. PAUSED, a cancellation acknowledgement, an empty operation list and lease expiry do not prove external writers stopped. Successors inspect Host state, pending operations, checkpoint, epoch and budget. Restoration creates a new epoch and requires quarantine/reconciliation instead of reviving Grants, Hosts or acceptance.

## 4. Acceptance and evidence

Each criterion specifies description, hard requirement, verification method and minimum evidence level. `verification.begin` enters VERIFYING after effects and Hosts settle and blocks new execution. `verification.rework` retains old evidence while invalidating its current basis. Small tasks can use `task.accept` through the same gate.

Evidence binds a current Task revision, an observed operation in the current epoch, an exact criterion and provenance. A–D evidence levels follow the contract; a lower level cannot impersonate independent or stronger verification. `task-verify` checks current proof without rewriting history. `NO_LONGER_PROVEN` means historical completion is insufficient now.

Protected content lives in blobs with owner, target, sensitivity, allowed purposes and retention descriptors. Current protection uses Windows current-user DPAPI. Encryption is not redaction or permission for Growth. Reviewed derivatives retain lineage; source withdrawal or expiry stops dependent reuse.

## 5. Collaboration, artifacts and improvement

Single Agent is the default. For approved collaboration, the controller separates roles/resources/acceptance, binds an actual Host adapter, budgets and observable identity. Workers deliver results; the controller accepts after Host settlement. Transport IDs are not Tasks, Runs or Grants. Parallel outputs are not integration proof.

Artifact ownership, provenance revision, relationships and retention purposes are distinct from paths. Shared means governed eligibility for cross-task reuse; current content, qualification and dependency closure remain necessary. SUPERSEDED/RETIRED records explain history, without implicit redirection or resurrection.

Growth manages sourced proposals, bounded trials, future outcomes and retirement. Positive self-assessment is insufficient; neutral/harmful outcomes remain. Global Skill/rule changes need their own scope and cannot be inferred from a trial PASS.

## 6. Installation and tradeoffs

Each tool's `MALTS_BOOT.md` identifies an immutable generation. Discovery checks registry, active pointer, identity and VERSION. Hash-bound installation plans capture source and target preimages; isolated preview precedes activation. Manual generation patches break the identity chain. The public repository is the ordinary source; ZIP is optional for offline delivery.

Exact Schema/hash binding improves auditability at the cost of explicit upgrade/adoption/recovery. Protected evidence reduces accidental propagation but limits cross-user recovery. Retained recovery originals support repair and explanation without a bounded-disk-space guarantee. Diagnostic inventories do not authorize deletion.

Skills use bounded routing and `task`, `phase`, `artifact`, `recovery` topics. A smaller reference set does not prove actual model reading behavior or token savings.

## 7. Evidence and limitations

Implementation is in `tools/v2_state_store.py`, `v2_governance.py`, `v2_operations.py`, `v2_local_host.py`, `v2_acceptance.py`, `v2_evidence_derivation.py`, `v2_artifacts.py`, `v2_growth.py`, `v2_handoff.py` and `malts_lifecycle.py`. Code explains mechanisms; observed checks establish behavior.

Recorded evidence covers domain/transaction/permission/recovery checks, managed files, representative native tasks and cold recovery, limited serial/parallel comparisons, future Growth trials and installation/adoption/backup restoration. Each proves its own layer. One complete fixed A/C pair observed less automatic time and reported input/output with more tool items. B1's original failed observer profile remains and is not a complete comparator. Neutral real Growth pairs demonstrate bounded trial/withdrawal behavior, not automatic benefit.

Uncertified claims include population success rates, universal/cross-Host causal speedups, actual money/human savings, provider-internal request totals, GUI model cancellation, arbitrary-OS fencing, cross-user DPAPI restoration and autonomous publication. These limits explain evidence scope without changing Task acceptance standards.

See [Usage](USAGE.md) and the [State Contract](V2_STATE_CONTRACT.md) for operations and exact state boundaries.
