# MALTS 2.0.0 for DeepSeek Harness

## Entry and responsibilities

The DeepSeek Harness adapter supplies native instructions/workflow discovery. The shared v2 services own Task state, authorization scopes, evidence and recovery. The tool-local .dsh/MALTS_BOOT.md resolves the installed runtime; discovery checks registry, active pointer, identity and VERSION.

## Installation and use

Follow [Installation](../../docs/INSTALL.md) and [Usage](../../docs/USAGE.md). Reload the Host and verify actual Skills/MCP. Existing personal content outside marked MALTS blocks is retained. New long workspaces must be Phase-ready; existing adopted workspaces continue through current bindings and Task services.

Use Invoke-MALTSLifecycle.ps1 with -Tool deepseek-harness and -ToolRootDeepSeekDesktop for its dedicated lifecycle. AllIncluded in Install/Update selects the other three Hosts only. The parameter name is retained; the current identity is deepseek-harness. The Desktop entry uses profiles/desktop; CLI/Web does not substitute for Desktop qualification.

## Verified scope and limitations

Windows Desktop0.2.0-rc.2 evidence covers task/session/terminal/associated backend; GUI model cancellation and arbitrary-writer isolation remain uncertified. Configuration, installation, effective execution identity and business acceptance remain separate. Single Agent is the default. Delegation, paid calls and publication need their corresponding authorized scope. Unknown effects and cancelled/paused Hosts require reconciliation before continuation.
