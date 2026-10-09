# MALTS 2.0.0 for DeepSeek Harness

## Entry and responsibilities

The DeepSeek Harness adapter supplies native instructions/workflow discovery. The shared v2 services own Task state, authorization scopes, evidence and recovery. The tool-local .dsh/MALTS_BOOT.md resolves the installed runtime; discovery checks registry, active pointer, identity and VERSION.

## Installation and use

Follow [Installation](../../docs/INSTALL.md) and [Usage](../../docs/USAGE.md). Reload the Host and verify actual Skills/MCP. Existing personal content outside marked MALTS blocks is retained. New long workspaces must be Phase-ready; existing adopted workspaces continue through current bindings and Task services.

Harness shares the formal installation with the other three Hosts. AllIncluded in Install-MALTS.ps1 and Update-MALTS.ps1 selects all four; each keeps its own configuration root and Boot. ToolRootDeepSeekHarness supplies the actual Harness path. See [Install](../../docs/INSTALL.md#deepseek-harness-installation), [Update](../../docs/UPDATE.md#deepseek-harness-update) and [Shared Lifecycle](../../docs/LIFECYCLE.md#shared-four-host-installation). Desktop uses profiles/desktop; CLI/Web does not substitute for Desktop qualification.

## Verified scope and limitations

Windows Desktop0.2.0-rc.2 evidence covers task/session/terminal/associated backend; GUI model cancellation and arbitrary-writer isolation remain uncertified. Configuration, installation, effective execution identity and business acceptance remain separate. Single Agent is the default. Delegation, paid calls and publication need their corresponding authorized scope. Unknown effects and cancelled/paused Hosts require reconciliation before continuation.
