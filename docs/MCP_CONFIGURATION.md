# MCP Configuration Checks And Recovery

[中文](zh-CN/MCP_CONFIGURATION.md) · [Installation](INSTALL.md) · [Lifecycle](LIFECYCLE.md) · [Workspace relocation](MANAGEMENT_AND_RELOCATION.md)

The Model Context Protocol (MCP) lets an Agent Host call external tools. MALTS uses local standard input/output (stdio) communication with its Python service; it does not require a network listening port.

MALTS 2.1.0 installs and updates the required `malts` MCP service for the selected Hosts. The comparison and diagnostic commands remain available for managed and project-specific entries.

## Purpose And Ownership

A Host launches the managed MALTS MCP service through its saved interpreter and fixed launcher. The service resolves the active installation and verifies project bindings per request. Separately configured project-specific endpoints retain their explicit state, Project and permission arguments; those references can become stale after an update or relocation while the installed core remains healthy.

The installer maintains its fingerprinted `malts` entry within the Host's file; the rest of that file remains Host/user-owned. Fragment generation and read-only inspection do not execute configured commands, edit files, change Tasks or grant permission. Configuration agreement is distinct from the installer's cold connection test and from business acceptance.

## Automatic Installation And Workspace Use

The ordinary installation/update command provisions the `malts` entry automatically; do not manually generate a Project binding just to finish installation. The installer manages only this entry and its own interpreter environment. A reviewed configuration plan contains paths and fingerprints, not unrelated configuration values. Existing settings, comments, model accounts and other servers remain outside its ownership. User edits to the managed entry produce a conflict requiring review.

The fixed `runtime/mcp/mcp_launcher.py` resolves and verifies the selected Host’s active generation. Basic installation and workflow tools work without a project. For project tools, supply the current workspace explicitly; the server validates its native locator or adopted binding on each request and reads the current store. It never invents a global database or retains a process-wide selected project. Workspace relocation is therefore followed through the verified locator.

| Tool | Use |
|---|---|
| `malts_installation` | Read installed version and service readiness |
| `malts_workflow` | Read one task, phase, artifact or recovery workflow |
| `malts_entry_status` | Check workspace binding and readiness; optionally verify the package |
| `malts_actions` | Read the selected project contract and current read-only policy |
| `malts_context` | Read the selected Task’s current state, dependencies and recovery context |
| `malts_verify_task` | Recheck current acceptance evidence without rewriting history |

For example, invoke `malts_context` with `{"workspace":"<absolute-current-project-workspace>","task_id":"<actual-task-id>"}`. If startup cwd already equals that verified workspace, it can supply the default; otherwise pass the path. A project that has not opted in receives a binding error rather than a new database. Use the existing approved project initialization or adoption workflow first.

The standard endpoint is read-only. Installation does not mint Grants, launch Agents, activate a Phase or bypass controller checks. Explicitly bounded write endpoints continue to use existing Project/Task/actor policy and runtime Grants; the fragment comparison section below applies to those endpoints. Cold connection checks verify a newly started server, while actual Host loading still needs reconnect/restart where necessary. Uninstall removes the owned `malts` entry while preserving unrelated settings and local recovery material.

## Compare A Selected Entry

Use the runtime found through the selected tool's `MALTS_BOOT.md` and successful discovery. Select the workspace's verified state directory and matching Project ID. Preserve the intended interpreter and explicit write policy when generating a replacement.

```powershell
$runtime = '<verified-MALTS_ROOT>'
python -B "$runtime/tools/malts_v2.py" mcp-config `
  --host deepseek-harness `
  --state-dir '<verified-state-directory>' `
  --resource-root '<workspace-root>' `
  --project-id '<project-id>' `
  --tool-root '<DeepSeek-Harness-tool-root>' `
  --check '<selected-profile>/cordis.patch.yml'
```

The same operation accepts `codex`, `claude` and `opencode`. Use `--server-name` if the deployed entry uses a different name. The expected state/resource/Project binding is validated before comparison. When `--tool-root` is supplied, verified discovery supplies the intended active runtime. Comparison ignores an unspecified interpreter choice, allowing a Host-specific Python environment to remain selected. Permission and authority differences are reported; sensitive authority values are redacted. Correcting them remains an explicit user decision.

Exit code 0 means the selected entry agrees and its checked references are current. Exit code 3 means the comparison produced a non-current result, including an absent entry; exit code 2 means invalid input or a command failure. Neither code 0 nor a generated fragment authorizes execution.

## Diagnostic Coverage

`doctor` checks these known locations under the supplied tool roots:

| Host | Known configuration locations | Supported representation |
|---|---|---|
| Codex | `config.toml` | TOML `mcp_servers` |
| Claude Code | Sibling `.claude.json`; `mcp.json` under the tool root | JSON `mcpServers`, including recognized project sections |
| OpenCode | `opencode.json`; `opencode.jsonc` | JSON/JSONC `mcp`, including comments and trailing commas |
| DeepSeek Harness | `profiles/<profile>/cordis.patch.yml` | Cordis insert patches with `@deepseek-ai/dsh-mcp-client` |

Generated Cordis JSON with standalone YAML comments works without an additional parser. The installed MCP environment includes PyYAML for block YAML; a separately selected diagnostic interpreter also needs that parser. MALTS 2.1.0 preserves native `!!js` as inert data outside MALTS, rejects dynamic MALTS fields, other tags, anchors, aliases, duplicate keys and excessive nesting. Missing parser support is `UNSUPPORTED`, not a successful check; inspection never installs a dependency. JSON/TOML core operations remain available without PyYAML.

MALTS 2.1.0 pins MCP 1.28.1, jsonschema 4.25.1, PyYAML 6.0.2, pip 26.2 and setuptools 83.0.0 in the lifecycle-owned environment. It updates that environment's pip before installing compatible binary wheels; unavailable wheels stop preparation. This addresses recorded dependency advisories while preserving stdio and the existing permissions. It does not update global Python or a dedicated project's independently chosen interpreter.

For project-local or custom files, supply an exact location:

```powershell
python -B "$runtime/tools/malts_lifecycle.py" doctor `
  --lifecycle-root '<verified-lifecycle-root>' `
  --tool-root 'codex=<Codex-tool-root>' `
  --tool-root 'claude-code=<Claude-Code-tool-root>' `
  --tool-root 'opencode=<OpenCode-tool-root>' `
  --tool-root 'deepseek-harness=<DeepSeek-Harness-tool-root>' `
  --host-config 'claude=<workspace-root>/.mcp.json'
```

Pass the actual registered tool set for the installation. Files are limited to 1 MiB, explicit/known inputs to 64, profile children to 32, and per-file entries to bounded counts. Links and reparse paths are rejected. No recursive disk scan, arbitrary external reference inventory or simultaneous cross-file snapshot is claimed. Reports contain recognized MALTS entries, checked paths, fingerprints and relevant differences; unrelated server settings, environment values and credentials are omitted.

## Interpreting Results

| Result | Meaning and next action |
|---|---|
| `CURRENT` | The checked entry and references agree. Verify the real Host connection separately. |
| `VALID_OLDER_GENERATION` | The referenced older generation is still registered and present. Review an update; it is not a missing-script error. |
| `DIFFERENT` | The deployed entry differs from the selected binding or policy. Review individual differences. |
| `INVALID` | A script/state/resource reference is missing, a generation is unregistered, or a Project/workspace binding is inconsistent. Generate and review a correction. |
| `NOT_CONFIGURED` | No recognized selected entry exists. The required managed entry is absent, or the selected project-specific entry has not been configured; this is not a successful setup. |
| `UNSUPPORTED` / `CHECK_FAILED` | The representation, parser, access or bounded check could not establish the result. Resolve that condition before declaring it healthy. |

The aggregate external report uses `DRIFT` for changed/invalid/older entries and `UNVERIFIED` for unsupported formats. Installation trust remains separately reported. An external entry can make `doctor` return `DEGRADED` with `core_trust=LOCALLY_CONSISTENT`; that does not justify rolling back a healthy payload. Lifecycle repair covers the installer-owned `malts` entry under its reviewed plan; unowned project-specific configuration is not automatically replaced.

## Update And Relocation Recovery

Successful installation/update or shared-root consolidation returns an `external_configuration` advisory. Successful forward-relocation CLI operations also inspect the selected tool's known locations and repeated `--host-config HOST=ABSOLUTE_PATH` inputs, using the original plan's old/new state directories. The report lists only inspected references and regeneration arguments. A diagnostic failure preserves the committed lifecycle/relocation outcome and remains visible.

Review the proposed fragment against the existing Host entry, retaining the chosen interpreter, environment and intended authority policy. Apply it through the Host's supported configuration mechanism within the corresponding authorization, reload that client and invoke a read-only MALTS entry check. Confirm the loaded runtime, Project and state binding, then assess Phase readiness and execution permission separately. Inspection never automatically activates a Phase or repairs an unowned file.

## Project Markdown Encoding

MALTS project Markdown controls accept UTF-8 with or without BOM. Their validators decode both forms; BOM presence is not an acceptance criterion. Do not repeatedly rewrite a document solely to restore a BOM removed by an editor. A template may retain its existing encoding, and original evidence fingerprints remain byte-specific. Skill front matter, code, scripts, JSON and external project conventions retain their separate encoding requirements.

## Selected Project Configuration

For ordinary read-only use, inherit the installer-owned user-level `malts` entry and pass the workspace in each project request. A fixed Project, a separate interpreter or environment, or a restricted write policy can require a dedicated endpoint. Those requirements remain valid; a same-name entry is not automatically redundant.

Select the current workspace when running Doctor:

```powershell
python -B "$runtime/tools/malts_lifecycle.py" doctor `
  --lifecycle-root '<verified-lifecycle-root>' `
  --tool-root 'codex=<Codex-tool-root>' `
  --workspace '<absolute-current-workspace>'
```

Supply the complete registered Host set when inspecting a shared installation. Repeated `--workspace` selects additional directories; repeated `--host-config HOST=ABSOLUTE_PATH` selects custom files. `Install-MALTS.ps1` and `Update-MALTS.ps1` accept the corresponding `-Workspace` and `-HostConfig` arrays. The reviewed update plan binds selected project-file fingerprints, rejects intervening edits, and returns the same selected scope after installation. These inputs request inspection, not automatic project-file editing.

MALTS 2.1.0 resolves each Host's own selected disk layers:

| Host | Selected layers and precedence | Scope of preserving edits |
|---|---|---|
| Codex | User TOML, then Git-root-to-workspace `.codex/config.toml`; nested tables merge | Selected project TOML entry and child tables |
| Claude Code | User `~/.claude.json`, project `.mcp.json`, then that workspace's local `projects` section; a higher entry replaces the whole lower entry | Selected project entry or exact embedded local section; other projects stay intact |
| OpenCode | Global `config.json`, `opencode.json`, `opencode.jsonc`; bounded project files; native upward `.opencode` directory order; nested fields merge | Selected JSON/JSONC entry; inheritance reviews every checked overriding entry |
| DeepSeek Harness | Selected profile patch, home patch, then explicitly selected CLI overlays; an ID patch replaces the entire plugin config | Known MCP insertion or ID config in profile/home/selected overlay |

Claude disabled/approval settings are inspected without granting trust or accepting a project server. OpenCode environment/CLI/remote/managed overrides remain unobserved unless separately selected and verified. Harness bundle patches, native groups/includes and dynamic MALTS expressions are not resolved by this disk profile. Native `!!js` values outside MALTS remain inert and unchanged; MALTS never evaluates them. An overlay is effective only when the Host actually loads it with `--patch`; MALTS does not invent an automatically loaded project file.

Disk analysis is conditional on the Host loading the selected layers. Reports retain `NOT_VERIFIED` for actual connections, trust and unobserved layers. Unsupported or unreadable input cannot prove a healthy connection. Contracts follow the [Codex configuration guide](https://developers.openai.com/codex/config-basic/), [Claude MCP scopes](https://code.claude.com/docs/en/mcp), [OpenCode configuration](https://docs.opencode.ai/docs/config/) and [Harness Loader](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/boot/app-boot/README.md).

## Retaining A Dedicated Endpoint

Generate a stable, fixed-project fragment by adding `--stable` to `mcp-config` and supplying the verified `--tool-root`. The generated fragment uses `runtime/mcp/mcp_launcher.py --project-bound` and preserves the existing Project/state/resource, actor, authority, Task/dispatch and write-policy arguments. All four Host fragment formats support this launch mode. The launcher verifies the active generation on each new process start; the selected interpreter still needs the MCP dependencies. An interpreter deliberately chosen for a project is not replaced by the global environment.

The dedicated endpoint continues to expose its existing fixed-project interface. It does not become a general-purpose write service or issue Grants. A changed state location still requires explicit review of the fixed binding; the stable launcher solves generation-path maintenance, not database relocation. A running old process must be stopped or reconnected through the Host's authorized workflow before its loaded version changes.

## Reviewed Project Entry Changes And Recovery

All four Hosts use the same plan, execute and original-operation recovery commands. Select `--host codex|claude-code|opencode|deepseek-harness` (default Codex). Claude selects `.mcp.json` or the exact embedded local project section by `--config-path`. Harness selects its profile with `--profile`; a workspace overlay also needs `--overlay`, matching the Host's actual `--patch` list. Selected files must already exist; this does not initialize configuration or business projects.

```powershell
python -B "$runtime/tools/malts_lifecycle.py" mcp-project-plan `
  --lifecycle-root '<verified-lifecycle-root>' `
  --tool-root '<Codex-tool-root>' `
  --workspace '<selected-workspace>' `
  --config-path '<selected-workspace>/.codex/config.toml' `
  --server-name 'malts' --strategy 'stable-project'
```

Use the same command with the native selection below. `$workspace`, `$tool` and `$lifecycle` are verified absolute paths; `$runtime` is MALTS 2.1.0 being tested. These are review commands, without `--apply`:

```powershell
python -B "$runtime/tools/malts_lifecycle.py" mcp-project-plan --host claude-code --lifecycle-root $lifecycle --tool-root $tool --workspace $workspace --config-path "$workspace/.mcp.json" --server-name malts --strategy stable-project
python -B "$runtime/tools/malts_lifecycle.py" mcp-project-plan --host opencode --lifecycle-root $lifecycle --tool-root $tool --workspace $workspace --config-path "$workspace/opencode.jsonc" --server-name malts --strategy stable-project
python -B "$runtime/tools/malts_lifecycle.py" mcp-project-plan --host deepseek-harness --profile desktop --overlay "$workspace/selected.patch.yml" --lifecycle-root $lifecycle --tool-root $tool --workspace $workspace --config-path "$workspace/selected.patch.yml" --server-name malts --strategy stable-project
```

For Claude local scope, select the existing user `.claude.json` instead; only the chosen workspace's `projects` entry is edited. For a Harness profile or home override, select its existing `cordis.patch.yml`; keep the actual profile and overlay order explicit. Stable conversion retains disabled settings. Global inheritance rejects them rather than enabling a service implicitly.

`stable-project` changes only the launch argv, preserving interpreter, environment, policy, unrelated settings, comments and encoding. `inherit-global` removes only the selected same-name project entry and its child tables after the user explicitly chooses that strategy. It refuses different interpreters, environment/custom settings, disabled entries, protected capture and bounded write/actor/Task policies. Such entries need retention or a separately reviewed Host change. No whole-file deletion, disabled replacement, server renaming or workspace adoption occurs.

Review the plan before saving it with `--out '<new-private-plan.json>' --apply`. New plans no longer contain whole configurations in plaintext or reversible hex. Afterimages and recovery preimages use Windows current-user DPAPI, bound to the original operation, target and Host context. Plans still contain private paths and fingerprints; do not publish them or expect another user to decrypt them. Retained legacy records recover only their original operation and are not rewritten. Apply the saved plan with `mcp-project-execute --plan '<plan.json>' --expected-plan-hash '<reviewed-hash>' --apply`. An exclusive Windows file handle and checked fingerprints protect against drift; inspected parent/user layers must still agree. Repeating a settled change is a no-op.

If an operation is interrupted, use `mcp-project-recover --lifecycle-root '<root>' --operation-id '<original-id>'`, then apply the reviewed recovery. The same command's `--restore` restores the saved preimage only while every selected file matches that operation's recorded beforeimage or afterimage, including interruption between files. Divergent content is preserved and requires review; recovery never overwrites subsequent user edits or replays an uncertain effect under another ID. Recovery files live under `runtime/mcp/project-operations/<operation-id>`. Unsettled configuration operations block new configuration writes and installation lifecycle mutations until original recovery. Writers require ordinary, non-reparse, single-link local files, verified readback and unchanged layer fingerprints.

After the disk change, reconnect the selected Host. Verify the actual standard endpoint with `malts_installation` and `malts_entry_status` for the existing workspace; verify a retained dedicated endpoint through its fixed-project tools. Cold connection, loaded Host, governance readiness and business execution authorization remain separate results.

## Selected References And Generation Retirement

Pass the same `--workspace` and `--host-config` set to update planning, Doctor and `retire-plan`. Retirement binds the selected file surfaces and reports its coverage. A selected reference to a retiring generation blocks the plan; unreadable or unsupported selected configurations also block it. A later selected-file edit invalidates execution. A stable endpoint refers to the launcher rather than a retiring generation directory.

This does not discover every project or process on the computer. Unselected project files and active old processes remain outside the proof; process-reference coverage is `NOT_OBSERVED`. Before retiring a generation, inspect and settle the relevant actual Host processes and known project inputs within authorization. The active generation, workspace stores, evidence and recovery material remain protected.

## Native source, managed locations and actionable advice

`effective_configuration.source` reports the native checked scope: `USER`, `PROJECT`, `LOCAL`, `PROFILE`, `HOME`, `HOME_DIRECTORY` or `OVERLAY`. `baseline_source` identifies a checked same-name user entry, or a Harness profile entry; it is null when none was observed. `global_entry_shadowed` is true only when a higher checked scope contributes to that same name over an observed baseline. A profile by itself is not a shadowed project entry. Different names do not establish shadowing.

`installation_managed=true` requires the eligible host scope, the installer-owned `malts` entry, and a matching READY installation record, semantic entry fingerprint and managed-byte fingerprint. `management_status` distinguishes `VERIFIED`, `NOT_MANAGED`, `DRIFT` and `UNVERIFIED`; unknown ownership is null rather than an assertion. A same-file Claude local project entry is not owned merely because its user file contains the installer's entry. These observations describe recorded local ownership, not authentication or a full Host configuration inventory.

A healthy verified managed entry recommends `KEEP_INSTALLER_MANAGED_ENTRY`. It needs no manual relocation or extra home-level copy. Suspected ownership drift recommends review rather than silently certifying the entry. `inherit_global.available` is true only after the real inheritance strategy succeeds as a read-only preserving-edit preview and actually removes an eligible override. Missing, disabled or dedicated baselines, different names/interpreters, special policy and unsupported editable scopes do not produce that recommendation. `reason` gives a value-free explanation; a reviewed saved plan is still required before application, and discovery issues no execution rights.

For Harness, `inherit-global` retains the verified profile standard entry while removing eligible home/explicit overrides. For the other Hosts it retains the verified user entry. The command name does not require creating a new USER/home layer. Installer-owned entries should be maintained through the ordinary lifecycle, which rejects managed-entry drift; moving them by hand does not make an update safer. The analysis does not evaluate dynamic expressions, load bundles/includes or verify an already running Host session.
