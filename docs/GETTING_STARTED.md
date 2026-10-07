# Getting Started with MALTS 2.0.0

## 1. Install and verify

Follow [Installation](INSTALL.md): review a repository source, create a plan, apply its exact hash, read tool-local Boot and run discovery. Require matching version/generation/registry, then reload the Host and verify actual native Skill/MCP connections.

## 2. Start from the goal

Tell the Agent the goal, allowed edits and acceptance, for example: “Use MALTS for this module migration; inspect the current project, preserve user data, implement and verify; decide commit/publication separately.”

Existing workspaces start with applicable instructions, binding and current Task. Select `malts-long-project-workspace-init` for new long work or `malts-grill-me-preflight` for material ambiguity. Simple tasks need no persistent store. Selecting a Skill does not authorize delegation, paid calls or publication.

## 3. Inspect current state

Substitute actual discovery/binding outputs:

```powershell
$runtime = '<verified-MALTS_ROOT>'
$workspace = '<selected-workspace>'
python -B "$runtime/tools/malts_v2.py" workspace --workspace $workspace
$state = '<verified-state-dir>'
python -B "$runtime/tools/malts_v2.py" governance-context --state-dir $state --project-id '<project-id>'
python -B "$runtime/tools/malts_v2.py" task-queue --state-dir $state --project-id '<project-id>'
python -B "$runtime/tools/malts_v2.py" context --state-dir $state --task-id '<task-id>'
```

Queries are read-only, create no Session/Agent/Artifact and grant no execution. A native v2 workspace selects its state directory explicitly; an adopted workspace resolves the business root's binding.

## 4. Finish a first task

The controller defines goal/scope/criteria and existing permission/budget, executes, checks actual outputs and accepts with appropriate evidence. `task-verify` must return `CURRENT_EVIDENCE_VALID` before relying on current completion. Business acceptance still covers the user's goal.

For an executable isolated file demonstration, see [v2 Operations](V2_PREVIEW_USAGE.md#v2-start). It calls no model and proves no business benefit. A long workspace also needs a current Project definition, actual plan and ACTIVE Phase; successful `init` is not `phase_ready=true`.

## 5. Continue after interruption

Continue the same Task/Operation/Run after inspecting UNKNOWN effects, Hosts, checkpoint, revisions and budgets. Create handoffs on demand; do not reinitialize to continue. See [Usage](USAGE.md), [Handoff](HANDOFF.md) and [Lifecycle](LIFECYCLE.md).
