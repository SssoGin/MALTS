# MALTS 2.0.0 Lifecycle

## 1. Two lifecycles

Installation lifecycle owns immutable generations, projections, registry, plans and transactions. Project lifecycle owns Project/Phase/Task, effects, evidence and recovery. Installation does not adopt/rebuild projects; project backup does not replace installation snapshots.

## 2. Plans and consolidation

Use review-first Install/Update scripts normally. Invoke-MALTSLifecycle.ps1 exposes Plan, PreviewPlan, Execute, Recover, Inspect, Scan, Doctor and DoctorRepairPlan for install/update/repair/finalize/uninstall. Inspect current help for exact parameters.

Finalize consolidates the same version with preserved target snapshots and exact inputs; it is not an arbitrary overwrite. Planning does not mutate installation. Execute requires reviewed PlanPath/ExpectedPlanHash. Preview in a new isolated root checks source/projections/postconditions before normal-target execution. Transactions own recovery; never patch journals or delete locks to bypass checks.

## 3. Discovery and diagnosis

Resolve runtime through tool Boot; discovery compares registry, active pointer, identity and VERSION. Doctor is read-only trust/drift diagnosis. Inspect lists installation state; Scan lists residue, not deletion permission:

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 -Command Doctor -LifecycleRoot '<existing-lifecycle-root>' -ToolRootCodex '<codex-config-root>'
```

Supply all actual roots for shared three-tool installation. Harness uses its separate lifecycle and the existing ToolRootDeepSeekDesktop parameter, which maps to current deepseek-harness identity, not a legacy identity.

## 4. v2 recovery

Resume exact Task/Run for ordinary pause. Disaster recovery verifies adopted binding/epoch, backup and writers. Verify then restore to a new root, keep quarantine and reconcile subsequent work, UNKNOWN, budgets and resources. Missing receipts do not prove non-execution. Recovery revives no old Grant/Host/consumed allowance or legacy runtime.

## 5. Retention and cleanup

Preserve active generation, registry, state, binding/seals, original acceptance, uncertain effects and required snapshots. Age, candidate names and terminal labels do not prove deletability. Inspect references, ownership, complete size and alternate recovery. Follow user/Host file policy; recoverable failure preserves the original.

Installation cleanup requires its reviewed lifecycle plan; never directly clean the active immutable generation. Recovery retention can grow disk usage without a fixed-space guarantee. See [State Contract](V2_STATE_CONTRACT.md) and [Update](UPDATE.md).
