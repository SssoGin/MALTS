# Installing MALTS

MALTS is installed as one shared system root plus thin Agent-tool adapters.

The shared root is the only canonical MALTS runtime and skill implementation source on the machine. Tool directories contain tool-specific instruction/scaffold files, a `MALTS_BOOT.md` pointer, and six lightweight discovery bridges under `skills/`. A bridge contains only the routing `SKILL.md`; the installer must not create a full MALTS runtime or full skill implementation under every tool directory.

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

`-TargetRoot` changes only the selected tool target. It does not change the default shared root. Use `-SharedRoot` explicitly when the shared root must be placed elsewhere; the shared root and every tool target must remain separate paths.

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

Each selected tool receives its adapter files, `MALTS_BOOT.md`, and six lightweight discovery bridges.

```text
Codex      -> AGENTS.md, config.toml, agents/*.toml, MALTS_BOOT.md, skills/<name>/SKILL.md bridges
ClaudeCode -> CLAUDE.md, agents/*.md, commands/*.md, MALTS_BOOT.md, skills/<name>/SKILL.md bridges
OpenCode   -> AGENTS.md, opencode.json, .opencode/agents/*.md, MALTS_BOOT.md, skills/<name>/SKILL.md bridges
```

`MALTS_BOOT.md` records the shared `MALTS_ROOT`. Agents must resolve `MALTS_ROOT` from that file or another reviewed global boot file before running MALTS project initialization.

Tool targets must not receive full skill implementation copies. Their `skills/` entries are discovery-only bridges; the shared `MALTS_ROOT\skills\` directory remains the only implementation source.

## Install Smoke Test

Maintainers can verify a real temporary install without touching the normal tool directories:

```powershell
.\scripts\Test-MALTSInstall.ps1 -Tool AllIncluded
```

The smoke test creates a guarded temporary root, installs one shared `MALTS_ROOT`, installs thin adapters and bridges, validates `MALTS_BOOT.md`, manifests, and the shared runtime root, confirms bridge directories do not contain runtime duplicates, and then removes the temporary directory unless `-KeepTemp` is provided.

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
- Tool directories receive thin adapter files, `MALTS_BOOT.md`, and discovery bridges.
- `MALTS_BOOT.md` points to the shared `MALTS_ROOT`.
- Root `skills/` under `MALTS_ROOT` is the canonical skill source.
- Tool-local bridges contain no full skill implementations or extra runtime files.
- Per-tool `<target>\malts\` runtime copies are not installed.
- Runtime templates and checklists are under `runtime/EN` and `runtime/CH`.
- Bilingual documentation sync is disabled by default.
- Codex installs into the Codex config root; Claude Code installs into the Claude Code config root; OpenCode installs into the OpenCode config root.
- `InstructionMode ManagedMerge` is the default: create or update one marked MALTS block and preserve all surrounding user text.
- Use `-InstructionMode Skip` when the user wants adapter support files without changing Agent instruction files. `-SkipInstructionTemplate` remains a compatibility alias.
- Use `-InstructionMode Replace -Overwrite` only for an explicitly reviewed full instruction-file replacement.
- Existing support files are not overwritten unless the user explicitly allows it.
- The installer prints a plan before writing.

## Manual Install

1. Read `README.md`.
2. Choose one shared `MALTS_ROOT`.
3. Copy the repository runtime files into that shared root.
4. Choose the target tool adapter.
5. Review the adapter directory under `adapters/`.
6. Copy only the files needed for that tool into the tool configuration root.
7. Install one lightweight bridge for each MALTS skill under the tool's native `skills/` discovery directory.
8. Write `MALTS_BOOT.md` next to the tool instruction file and point it at the shared `MALTS_ROOT`.
9. Do not copy full `malts/` directories or full skill implementations into each tool target.
10. Run the relevant smoke test or lint command.

See `docs/AGENT_INSTALL.md` for Agent-assisted installation rules.
