# MCP Configuration Checks And Recovery

[中文](zh-CN/MCP_CONFIGURATION.md) · [Installation](INSTALL.md) · [Lifecycle](LIFECYCLE.md) · [Workspace relocation](MANAGEMENT_AND_RELOCATION.md)

The Model Context Protocol (MCP) lets an Agent Host call external tools. MALTS uses local standard input/output (stdio) communication with its Python service; it does not require a network listening port.

MALTS 2.0.8 installs and updates the required `malts` MCP service for the selected Hosts. The comparison and diagnostic commands remain available for managed and project-specific entries.

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

Generated Cordis JSON with standalone YAML comments works without an additional parser. The installed MCP environment includes PyYAML for block YAML; a separately selected diagnostic interpreter also needs that parser. Safe parsing rejects tags, anchors, aliases, duplicate keys and excessive nesting. Missing parser support is `UNSUPPORTED`, not a successful check; inspection never installs a dependency. JSON/TOML core operations remain available without PyYAML.

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

For Codex, MALTS reads the user file and `.codex/config.toml` layers from the detected Git project root through the selected workspace; without a Git root its boundary is the selected workspace. The closest checked layer wins and nested table settings are merged. A partial `enabled=false` table can disable the inherited server. Reports retain individual file validity and separately give `effective_configuration`: source, endpoint kind, generation, enabled state, same-name shadowing, environment key names and write-policy flags. Same-version standard and project-bound endpoints have different parameter contracts. Different server names can coexist.

This is disk-layer analysis **conditional on the project being trusted**. Profile files, CLI overrides, managed requirements and the Host's actual loaded connection are not observed; reports explicitly say `NOT_VERIFIED`. Other Hosts retain bounded explicit-file diagnostics but their project-layer precedence is not inferred from Codex. A failed or unsupported layer cannot prove a healthy effective connection. See [Codex configuration precedence](https://developers.openai.com/codex/config-basic/).

## Retaining A Dedicated Endpoint

Generate a stable, fixed-project fragment by adding `--stable` to `mcp-config` and supplying the verified `--tool-root`. The generated fragment uses `runtime/mcp/mcp_launcher.py --project-bound` and preserves the existing Project/state/resource, actor, authority, Task/dispatch and write-policy arguments. All four Host fragment formats support this launch mode. The launcher verifies the active generation on each new process start; the selected interpreter still needs the MCP dependencies. An interpreter deliberately chosen for a project is not replaced by the global environment.

The dedicated endpoint continues to expose its existing fixed-project interface. It does not become a general-purpose write service or issue Grants. A changed state location still requires explicit review of the fixed binding; the stable launcher solves generation-path maintenance, not database relocation. A running old process must be stopped or reconnected through the Host's authorized workflow before its loaded version changes.

## Reviewed Project Entry Changes And Recovery

The built-in preserving edit profile currently supports an explicitly selected Codex project TOML file. Other Hosts use stable fragment generation and their supported configuration mechanism; MALTS does not claim an untested automatic project-file editor for them.

```powershell
python -B "$runtime/tools/malts_lifecycle.py" mcp-project-plan `
  --lifecycle-root '<verified-lifecycle-root>' `
  --tool-root '<Codex-tool-root>' `
  --workspace '<selected-workspace>' `
  --config-path '<selected-workspace>/.codex/config.toml' `
  --server-name 'malts' --strategy 'stable-project'
```

`stable-project` changes only the launch argv, preserving interpreter, environment, policy, unrelated settings, comments and encoding. `inherit-global` removes only the selected same-name project entry and its child tables after the user explicitly chooses that strategy. It refuses different interpreters, environment/custom settings, disabled entries, protected capture and bounded write/actor/Task policies. Such entries need retention or a separately reviewed Host change. No whole-file deletion, disabled replacement, server renaming or workspace adoption occurs.

Review the plan before saving it with `--out '<new-private-plan.json>' --apply`. Plans and recovery preimages are local sensitive material and must not be published. Apply the saved plan with `mcp-project-execute --plan '<plan.json>' --expected-plan-hash '<reviewed-hash>' --apply`. An exclusive Windows file handle and checked fingerprints protect against drift; inspected parent/user layers must still agree. Repeating a settled change is a no-op.

If an operation is interrupted, use `mcp-project-recover --lifecycle-root '<root>' --operation-id '<original-id>'`, then apply the reviewed recovery. The same command's `--restore` restores the saved preimage only while the current file still exactly matches the recorded afterimage. Divergent content is preserved and requires review; recovery never overwrites subsequent user edits or replays an uncertain effect under another ID. Recovery files live under `runtime/mcp/project-operations/<operation-id>`.

After the disk change, reconnect the selected Host. Verify the actual standard endpoint with `malts_installation` and `malts_entry_status` for the existing workspace; verify a retained dedicated endpoint through its fixed-project tools. Cold connection, loaded Host, governance readiness and business execution authorization remain separate results.

## Selected References And Generation Retirement

Pass the same `--workspace` and `--host-config` set to update planning, Doctor and `retire-plan`. Retirement binds the selected file surfaces and reports its coverage. A selected reference to a retiring generation blocks the plan; unreadable or unsupported selected configurations also block it. A later selected-file edit invalidates execution. A stable endpoint refers to the launcher rather than a retiring generation directory.

This does not discover every project or process on the computer. Unselected project files and active old processes remain outside the proof; process-reference coverage is `NOT_OBSERVED`. Before retiring a generation, inspect and settle the relevant actual Host processes and known project inputs within authorization. The active generation, workspace stores, evidence and recovery material remain protected.
