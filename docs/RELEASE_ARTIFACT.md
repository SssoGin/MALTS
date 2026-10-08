# Optional Release Archive

The repository is MALTS’s normal install/update source. The optional fixed archive supports offline or archival use; current release version is **2.0.0**.

## One Optional Release ZIP

The formal Release has one MALTS-uploaded MALTS-2.0.0.zip. GitHub-generated source archives are separate platform links. The installer never downloads a ZIP automatically.

## Verify Before Extraction

Obtain Verify-MALTSBootstrap.ps1 from the matching reviewed source and inspect before extraction:

```powershell
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip -ExtractOutput '<new-extraction-root>' -Apply
```

Checks cover closed inventory, hashes, safe paths/collisions and package identity. Integrity proves these bytes, not native model or business results.

## Install from an Extracted Archive

The archive does not bypass the plan-hash requirement, ownership merges or postchecks. Use the payload lifecycle entry and ReleaseRoot for the extracted package, then review/apply its exact plan hash. For Harness, choose the dedicated lifecycle and ToolRootDeepSeekDesktop. Do not copy bytes directly into an active generation. See [Install](INSTALL.md).

## Archive Contents

Read the verified manifest: the closed package contains public RELEASE_NOTES.md, manifests/inventories and the immutable lifecycle artifact. Repository-only Git/CI/identity files are outside the installed user payload.

## What Is Not in the Archive

Project databases, user configuration, credentials, raw sessions, private controls, caches, tests and local acceptance bodies are excluded. A later same-version main guide amendment does not replace the original archive/tag; its identity remains historical and explicit.
