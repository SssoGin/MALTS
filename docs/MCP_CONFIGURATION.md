# MCP Configuration Checks And Recovery

[中文](zh-CN/MCP_CONFIGURATION.md) · [Installation](INSTALL.md) · [Lifecycle](LIFECYCLE.md) · [Workspace relocation](MANAGEMENT_AND_RELOCATION.md)

The Model Context Protocol (MCP) lets an Agent Host call external tools. MALTS uses local standard input/output (stdio) communication with its Python service; it does not require a network listening port.

MALTS 2.0.7 installs and updates the required `malts` MCP service for the selected Hosts. The comparison and diagnostic commands remain available for managed and project-specific entries.

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
