# Installing MALTS

MALTS is installed as one shared system root plus thin Agent-tool adapters.

The shared root is the only canonical MALTS runtime and skill source on the machine. Tool directories should contain only the tool-specific instruction/scaffold files and a `MALTS_BOOT.md` pointer to that shared root. The installer must not create a full `malts/` copy under every tool directory by default.

## Recommended Flow

The recommended first step is dry-run:

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex
```

If Windows PowerShell blocks script execution, use a process-local execution policy override:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-MALTS.ps1 -Tool Codex
```

For double-click review on Windows, use the wrapper that keeps the console open:

```powershell
.\scripts\Install-MALTS.review.cmd -Tool Codex
```

No files are changed unless `-Apply` is provided:

```powershell
.\scripts\Install-MALTS.ps1 -Tool Codex -Apply
```

## Shared Root

By default the installer writes one shared MALTS root:

```text
%USERPROFILE%\.malts
```

When `-TargetRoot` is provided, the default shared root is:

```text
<TargetRoot>\MALTS_ROOT
```

Use `-SharedRoot <path>` to choose another reviewed location.

`MALTS_ROOT` must contain:

```text
README.md
skills/
runtime/EN/templates/
runtime/EN/checklists/
tools/
scripts/
```

## Thin Tool Adapter

Each selected tool receives only its adapter files plus `MALTS_BOOT.md`.

```text
Codex      -> AGENTS.md, config.toml, agents/*.toml, MALTS_BOOT.md
ClaudeCode -> CLAUDE.md, agents/*.md, commands/*.md, MALTS_BOOT.md
OpenCode   -> AGENTS.md, opencode.json, .opencode/agents/*.md, MALTS_BOOT.md
```

`MALTS_BOOT.md` records the shared `MALTS_ROOT`. Agents must resolve `MALTS_ROOT` from that file or another reviewed global boot file before running MALTS project initialization.

Tool targets must not receive local `skills/` copies. The shared `MALTS_ROOT\skills\` directory is the only installed skill source.

## Install Smoke Test

Maintainers can verify a real temporary install without touching the normal tool directories:

```powershell
.\scripts\Test-MALTSInstall.ps1 -Tool AllIncluded
```

The smoke test creates a guarded temporary root, installs one shared `MALTS_ROOT`, installs thin adapters for the selected tools, validates `MALTS_BOOT.md`, validates the shared runtime root, confirms tool directories do not contain local `malts/` runtime copies or `skills/` duplicates, and then removes the temporary directory unless `-KeepTemp` is provided.

The same installed layout check can be run directly:

```powershell
python tools\agent_system_lint.py check-install-layout --install-root <TOOL_TARGET> --tool Codex
```

## Supported Tools

```text
Codex
ClaudeCode
OpenCode
AllIncluded
```

## Defaults

- One shared MALTS root is installed once per install target set.
- Tool directories receive thin adapter files and `MALTS_BOOT.md`.
- `MALTS_BOOT.md` points to the shared `MALTS_ROOT`.
- Root `skills/` under `MALTS_ROOT` is the canonical skill source.
- Tool-local `skills/` duplicates are not installed.
- Per-tool `<target>\malts\` runtime copies are not installed.
- Runtime templates and checklists are under `runtime/EN` and `runtime/CH`.
- Bilingual documentation sync is disabled by default.
- Codex installs into the Codex config root; Claude Code installs into the Claude Code config root; OpenCode installs into the OpenCode config root.
- Use `-SkipInstructionTemplate` when the user wants adapter support files without changing Agent instruction files.
- Existing files are not overwritten unless the user explicitly allows it.
- The installer prints a plan before writing.

## Manual Install

1. Read `README.md`.
2. Choose one shared `MALTS_ROOT`.
3. Copy the repository runtime files into that shared root.
4. Choose the target tool adapter.
5. Review the adapter directory under `adapters/`.
6. Copy only the files needed for that tool into the tool configuration root.
7. Write `MALTS_BOOT.md` next to the tool instruction file and point it at the shared `MALTS_ROOT`.
8. Do not copy full `malts/` directories into each tool target.
9. Run the relevant smoke test or lint command.

See `docs/AGENT_INSTALL.md` for Agent-assisted installation rules.
