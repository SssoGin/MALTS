# Optional Release Archive

A GitHub Release may provide one optional offline archive for MALTS. It is convenience delivery for a fixed offline copy; it is not required for ordinary Agent-assisted installation.

## One Optional Release ZIP

Each Release uploads at most one MALTS asset:

```text
MALTS-<version>.zip
```

The ZIP is self-contained. It contains the immutable release package used for installation, its package inventories, `RELEASE_NOTES.md`, and the runtime templates, adapters, Skills, and user-facing tools needed after extraction.

No separate checksum or transport file is uploaded. The archive SHA-256 may be published in the Release body as an additional delivery-channel check, but it is not a second required download.

GitHub may also display its automatic `Source code (zip)` and `Source code (tar.gz)` links. Those are platform-generated source snapshots, not the optional offline archive described here.

## Verify Before Extraction

Obtain `scripts/Verify-MALTSBootstrap.ps1` from the same reviewed source or exact source tag as the ZIP. Then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Verify-MALTSBootstrap.ps1 `
  -ArchivePath .\MALTS-1.1.1.zip
```

To verify and extract into a new location:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Verify-MALTSBootstrap.ps1 `
  -ArchivePath .\MALTS-1.1.1.zip `
  -ExtractOutput <EXTRACTED_RELEASE_ROOT> `
  -Apply
```

The verifier accepts only the expected `MALTS-<version>.zip` name. It validates deterministic ZIP structure, safe Windows paths, duplicate or case-colliding members, required outer release files, isolated extraction, and the closed immutable package through the packaged lifecycle verifier.

## Install from an Extracted Archive

After bootstrap verification, use the extracted release root explicitly:

```powershell
<EXTRACTED_RELEASE_ROOT>\lifecycle_artifact\payload\scripts\Install-MALTS.ps1 `
  -ReleaseRoot <EXTRACTED_RELEASE_ROOT> `
  -UseDefaultRoots `
  -Tool Codex
```

This still creates a review plan first. The archive does not bypass the plan-hash or user-authorization boundary.

## Archive Contents

The ZIP contains only the content needed to install and use MALTS. Local machine state, user data, and project files are never included.

See [Install](INSTALL.md), [Security](SECURITY.md), and [Agent-Assisted Installation](AGENT_INSTALL.md).
