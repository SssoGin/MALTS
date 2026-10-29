# Real Agent scheduling

[简体中文](zh-CN/AGENT_SCHEDULING.md) · [Usage](USAGE.md) · [Design](CORE_DESIGN.md)

MALTS coordinates delegated work through a trusted controller, the selected project state and the actual Agent Host. This guide explains how to select a route, verify its execution evidence, allocate a finite budget and recover the original dispatch.

## 1. Purpose and execution routes

MALTS retains the user's goal, Task revision, dependencies, permissions, cumulative dispatch budget and evidence. The Host actually runs the Agent. The controller connects those two responsibilities and remains responsible for integration and acceptance. Selecting the scheduling Skill does not launch an Agent or enable background operation.

| Route | Execution surface | Stop observation |
|---|---|---|
| Codex CLI | `codex exec --json` | Owned Windows Job process tree |
| Claude Code CLI | `claude --print --output-format stream-json` | Owned Windows Job process tree |
| OpenCode CLI | `opencode run --format json` | Owned Windows Job process tree |
| DeepSeek Harness CLI | `dsh --profile headless --json` | Owned Windows Job process tree |
| Codex native | Controller relays actual spawn/wait/close tools | Post-close native session shutdown or not-found |

CLI evidence does not certify the native route. A native session closure does not prove that arbitrary Editor, shell or remote provider work has stopped. Nested delegation, machine-wide exclusion and cross-machine execution are outside these profiles.

## 2. Select an existing workspace and reviewed profile

First discover the installed runtime through the selected Host's Boot and lifecycle discovery. Resolve the existing workspace with `malts_v2.py workspace --workspace <workspace>`; use its returned state location and Project identity. Do not initialize or adopt again to obtain delegation permission. The current Phase, Task revision and dependencies must permit execution. Review and Worker profiles must both use the selected workspace's verified state directory and Project. Subsequent operations must match the original dispatch's Task and revision; choosing another profile does not retarget that dispatch.

`tools/malts_agents.py` is a trusted-controller interface, not a Worker MCP tool. A Worker cannot use it to obtain successor tasks, Grants or acceptance authority. A reviewed profile document contains Host, exact executable and SHA-256, working root, relevant configuration files, mode, state/Project/Task bindings, existing authorization reference and the MCP Python executable. Model and effort choices use the user's current selection. A configured model is not independently observed effective identity.

An example profile shape is:

```json
{
  "host": "codex",
  "executable": "<absolute-reviewed-codex.exe>",
  "executable_sha256": "<actual-sha256>",
  "working_root": "<existing-workspace>",
  "execution_root": "<separate-owned-native-staging-directory>",
  "config_files": ["<actual-host-config>", "<actual-project-config>"],
  "mode": "worker",
  "state_dir": "<workspace-returned-state-dir>",
  "project_id": "<current-project>",
  "task_id": "<current-task>",
  "task_revision": 1,
  "authority_ref": "<existing-user-authorization>",
  "python_executable": "<reviewed-mcp-python>",
  "tool_root": "<selected-host-configuration-root>"
}
```

These are placeholders, not executable installation defaults. Pass the actual tool_root for every installed profile, including review. Preparation and the first native spawn admission recheck the installed runtime under lifecycle activation exclusion; polling and cancellation remain available for original-dispatch reconciliation. A Worker reuses the controller-verified current binding and must not initialize a new project from its staging directory. Claude Code uses `host=claude-code`; OpenCode uses `opencode`. Prefer an actual executable behind Windows command shims. The Harness Desktop launcher additionally needs the reviewed launcher prefix and archive guards. Its selected static provider/model and reasoning effort must match the user's configuration; a fresh headless default may use a different credential route.

Harness uses an owned process-local `DSH_HOME`, a per-dispatch patch and an explicit reference to an existing credential store when restored account authentication is required. It does not copy credentials or modify the user's profile. Dynamic provider/model expressions need explicit review; the controller does not evaluate arbitrary configuration code.

## 3. Inspect, qualify and allocate a budget

The controller defaults to preview. `inspect`, `capabilities`, `qualification-status` and `native-call` perform no model invocation. Merely opening a profile or reading qualification does not create a record.

```powershell
python -B tools/malts_agents.py inspect --profile-file '<profile.json>' --host-root '<owned-host-journal>'
python -B tools/malts_agents.py qualification-status --profile-file '<profile.json>' --receipt-root '<retained-qualification-root>' --route-id codex-cli-worker
python -B tools/malts_agents.py host-init --host-root '<new-owned-host-journal>' --host-id '<reviewed-host-id>'
```

After review, `host-init --apply` creates only the new owned journal. `budget --workspace <workspace> --policy-file <policy.json>` previews a policy. Its approved apply requires `--expected-policy-sha256 <preview-hash> --apply`. The policy uses the existing `configure_budget` contract: Project, launch/delegated limits, per-Host occupancy, query/cancel limits, expiry and authorization. An existing policy must be amended through the current controller budget API; reinitialization never resets consumption.

Ordinary prepare/launch requires the selected route's verified capabilities. Supply `--qualification-root` and any additional `--require-capability`. Review defaults require dispatch/result/read-only; Worker defaults require dispatch/result/bounded-write. A missing, stale or insufficient record returns `QUALIFICATION_REQUIRED` without launching.

An explicitly authorized, bounded qualification run can use `--qualification-run --authority-ref <reviewed-authorization>`. This is a testing path, not permission for an Agent to self-certify. The controller freezes the cases and limits before starting; failed and uncertain starts consume the applicable allowance and remain evidence.

## 4. Prepare, launch and observe the original dispatch

Immediately before exposing the first native spawn, MALTS compares the queued profile binding and rechecks the captured input files. All four CLI profiles carry the selected installation binding into the process supervisor, which checks lifecycle admission at actual process launch. Configuration drift blocks new execution while original-dispatch queries, cancellation and already admitted receipt capture remain available for reconciliation.

Use one request file containing `prompt` and finite `wall_seconds`. Prompts enter the process through stdin. The controller previews `prepare` with the profile, Host journal, exact Task/attempt/dispatch identities, strategy and authority. Apply the exact reviewed profile and request hashes. It then records Grants for the returned Worker actor through the existing authorized controller service.

`launch`, `poll` and `cancel` use that original dispatch and unique invocation identities. Preview each mutation, then apply its reviewed profile hash. Do not replace a dispatch whose start receipt is missing. Poll/reconcile the original Host journal first. Restarting the controller can reopen the same journal; it does not launch a replacement.

For Codex native, use a Codex profile, add `--native` and select the actual responsibility with `--role`. Qualification is bound to that responsibility as well as the profile; a Verifier record cannot qualify a Planner or Worker. Read the native record using `qualification-status --native --role malts_verifier --route-id codex-native-review` with the same profile and receipt root. `inspect --native --role malts_verifier` returns the corresponding `qualification_binding`. `native-call` first previews only the pending call identity and tool name. Its reviewed `--apply` reserves the applicable budget before exposing the exact executable packet. The trusted controller invokes that Host tool once, retains the actual result, then uses `native-receipt` with its original call ID, tool name and receipt. Receipt preservation uses the prior reservation and does not spend another query. `native-query --apply` queues and admits a bounded wait; cancellation queues close. A pending admitted call must be reconciled first; its receipt preserves any cancellation request and then queues close. A never-admitted wait can be withdrawn without a Host call. A returned result is unreviewed. Close acknowledgement remains nonterminal until a post-close wait observes shutdown/not-found. Native deadlines require an active controller to query/cancel; there is no hidden timer daemon.

### 4.1 CLI sequence

Run the following from the verified MALTS root after reviewing the existing profile, request and qualification record. Replace placeholders with actual values. The first prepare is a preview; its apply requires both hashes. A Worker additionally needs its exact Grant recorded for the actor returned by prepare before launch. Task acceptance remains a separate controller operation.

```powershell
$agentProfile = '<profile.json>'
$agentHostJournal = '<owned-host-journal>'
$agentRequest = '<request.json>'
$agentQualifications = '<retained-qualification-root>'
$agentProfileHash = (python -B tools/malts_agents.py inspect --profile-file $agentProfile --host-root $agentHostJournal | ConvertFrom-Json).profile_sha256
$agentRequestHash = (Get-FileHash -LiteralPath $agentRequest -Algorithm SHA256).Hash.ToLowerInvariant()
python -B tools/malts_agents.py prepare --profile-file $agentProfile --host-root $agentHostJournal --dispatch-id '<dispatch-id>' --attempt-id '<attempt-id>' --strategy-ref '<strategy>' --authority-ref '<existing-authorization>' --request-file $agentRequest --qualification-root $agentQualifications
python -B tools/malts_agents.py prepare --profile-file $agentProfile --host-root $agentHostJournal --dispatch-id '<dispatch-id>' --attempt-id '<attempt-id>' --strategy-ref '<strategy>' --authority-ref '<existing-authorization>' --request-file $agentRequest --qualification-root $agentQualifications --expected-profile-sha256 $agentProfileHash --expected-request-sha256 $agentRequestHash --apply
python -B tools/malts_agents.py launch --profile-file $agentProfile --host-root $agentHostJournal --dispatch-id '<dispatch-id>' --invocation-id '<unique-launch-id>' --qualification-root $agentQualifications --expected-profile-sha256 $agentProfileHash --apply
python -B tools/malts_agents.py poll --profile-file $agentProfile --host-root $agentHostJournal --dispatch-id '<dispatch-id>' --invocation-id '<unique-poll-id>' --expected-profile-sha256 $agentProfileHash --apply
python -B tools/malts_agents.py result --profile-file $agentProfile --host-root $agentHostJournal --dispatch-id '<dispatch-id>' --expected-profile-sha256 $agentProfileHash --apply
```

Keep the returned actor/Run and every original identifier. Each distinct poll uses a new invocation ID; do not change the dispatch to retry a missing start. Cancellation uses `cancel` with that dispatch, a unique invocation ID and the reviewed profile hash; observe its original result until the appropriate stop condition is confirmed. A qualification test may use the explicit bounded testing flag described above; it does not create passing evidence automatically.

## 5. Permissions, results and acceptance

CLI review profiles expose no general tools except the selected Host's deliberately permitted surface. Worker profiles disable native shell access where supported and expose a Task/Run-bound MCP. Each managed mutation still checks its exact Grant, resource, revision, actor, epoch and dispatch admission. Codex Workers require a separate existing execution_root outside the business workspace and outside any Git worktree. The command uses a process-local workspace-write sandbox confined to staging, clears additional writable roots and excludes implicit temporary-directory grants. Business files outside staging therefore require the Task-bound MCP for granted changes. Disabling shell_tool alone does not disable native apply_patch. A read-only Host instruction cannot be overridden by a MALTS Grant. No permission profile is persisted. The native boundary is verified with an attempted patch to the business fixture, not inferred from flags; see the [official sandbox guide](https://learn.chatgpt.com/docs/sandboxing) and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference). These measures do not claim control over arbitrary same-user processes or all native capabilities.

`result --apply` is an explicit private controller read. It returns unreviewed candidate text for verification/recovery; it never accepts the Task. Check actual output bytes, rejected operations and pending effects independently. A normal process exit, parseable final answer or Agent statement alone is insufficient.

Public telemetry retains bounded status and usage metadata. Raw stdout/stderr, reasoning, tool arguments and full tool results are not retained by the transport. Private records hold protected candidate text, native identities and value-free diagnostic codes. Native Host session storage follows that Host's own policy and is distinct from MALTS transport retention.

## 6. Qualification evidence and invalidation

Execution receipts use `malts.agent-case-receipt.v2` and bind the route, capability, reviewed-input digest and profile binding at capture. Reusing an older receipt with new inputs, another route or another mode is rejected. Earlier unbound v1 execution receipts remain historical evidence and cannot qualify current execution; capture a new bounded real case instead of relabeling the old bytes.

Qualification is per Host, route, mode and reviewed input inventory. A receipt lists the required and verified capabilities rather than a global success flag. Synthetic/component checks cannot establish real Host execution. A real PASS requires retained execution-receipt bytes, a matching SHA-256 and native identity, settled execution and supported concrete checks of actual observations or output files. Missing, contradictory or changed evidence cannot certify a route.

Records are append-only and protected with Windows current-user DPAPI. Summaries exclude personal paths, native IDs and raw private bodies. Source/configuration changes return `PROFILE_CHANGED` or `STALE_INPUTS`; changed result evidence returns `EVIDENCE_INVALID`. Keep the receipts, native journals and referenced output closure together for recovery. These optional records do not automatically become part of a Project database backup.

The trusted controller is still responsible for supplying actual Host receipts. File hashes and DPAPI protect bindings and retained bytes; they do not authenticate an arbitrary same-user caller or prove universal model compliance. Effective model/effort, provider billing and physical request counts remain unknown when the Host does not expose them.

## 7. Finite completion

Close a scheduling round when promised outputs and applicable checks are complete, or report the exact remaining blocker with original identities intact. Keep implementation, component verification, real-route qualification, installation and publication as separate conclusions. A route with only dispatch/result evidence must not be advertised as qualified for writing, parallelism or recovery.
