# Install MALTS v1.0

## Prerequisites

- Windows 10 or later
- PowerShell 5.1 or later
- Python 3.11 or later
- At least one selected tool: Codex, Claude Code, or OpenCode

Choose a lifecycle root outside every selected tool root. The lifecycle root
stores MALTS generations and its registry; a tool root receives only the
projection for that tool.

## 1. Verify the download

Keep these four files together in one directory: the ZIP, its checksum,
transport manifest, and public notes. Use the bootstrap verifier from the
matching user source:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Verify-MALTSBootstrap.ps1 `
  -ArchivePath <ASSET_ROOT>\MALTS-1.0.0.zip
```

To extract only after successful verification, add an empty output directory
whose final name is `MALTS-1.0.0`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Verify-MALTSBootstrap.ps1 `
  -ArchivePath <ASSET_ROOT>\MALTS-1.0.0.zip `
  -ExtractOutput <EXTRACT_PARENT>\MALTS-1.0.0 `
  -Apply
```

## 2. Create a reviewed plan

Set `$releaseRoot` to the verified extracted outer package and `$payloadRoot`
to its user payload.

```powershell
$releaseRoot = '<EXTRACT_PARENT>\MALTS-1.0.0'
$payloadRoot = Join-Path $releaseRoot 'lifecycle_artifact\payload'

powershell -NoProfile -ExecutionPolicy Bypass -File "$payloadRoot\scripts\Invoke-MALTSLifecycle.ps1" `
  -Command Plan `
  -Operation install `
  -ReleaseRoot $releaseRoot `
  -LifecycleRoot <LIFECYCLE_ROOT> `
  -ToolRootCodex <CODEX_ROOT> `
  -OutPath <PLAN_PATH> `
  -Apply
```

Select only the tool roots you intend to use. Replace `-ToolRootCodex` with,
or add, `-ToolRootClaudeCode` and `-ToolRootOpenCode` as needed. Read the
written plan and its `plan_hash` before any execution.

## 3. Execute the exact reviewed plan

```powershell
python -B "$payloadRoot\tools\malts_lifecycle.py" execute `
  --plan <PLAN_PATH> `
  --expected-plan-hash <PLAN_HASH> `
  --apply
```

The engine fails closed if the selected package, paths, or plan hash no longer
match. It never overwrites an unrelated tool root.

## Next steps

Read [Usage](USAGE.md) for project work and [Lifecycle](LIFECYCLE.md) for
update, repair, recovery, and uninstall operations.
