# Optional Release Archive

The repository is MALTS’s normal install/update source. The optional fixed archive supports offline or archival use; current release version is **2.0.1**.

## One Optional Release ZIP

The formal Release has one MALTS-uploaded MALTS-2.0.1.zip. GitHub-generated source archives are separate platform links. The installer never downloads a ZIP automatically.

## Verify Before Extraction

Obtain Verify-MALTSBootstrap.ps1 from the matching reviewed source and inspect before extraction:

```powershell
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.1.zip
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.1.zip -ExtractOutput '<new-extraction-root>' -Apply
```

Checks cover closed inventory, hashes, safe paths/collisions and package identity. Integrity proves these bytes, not native model or business results.

## Install from an Extracted Archive

The archive does not bypass the plan-hash requirement, ownership merges or postchecks. Use the payload lifecycle entry and ReleaseRoot for the extracted package, then review/apply its exact plan hash. For Harness, use the shared lifecycle and its actual ToolRootDeepSeekHarness along with every other registered Host. Do not copy bytes directly into an active generation. See [Install](INSTALL.md).

## Archive Contents

Read the verified manifest: the closed package contains public RELEASE_NOTES.md, manifests/inventories and the immutable lifecycle artifact. Repository-only Git/CI/identity files are outside the installed user payload.

The outer release manifest and inventory bind the complete package, including RELEASE_NOTES.md and the inner lifecycle_artifact. The inner artifact manifest/inventory bind the actual user payload and its generation identity. Verify both boundaries: matching an inner file alone cannot certify that the outer archive has no added or missing entries.

Installation treats the extracted release root as a fixed verified source and installs only its declared user payload. Git/CI and repository identity remain repository-only material. Safe extraction checks paths and collisions before final output, and a new destination avoids silently mixing the package with unrelated existing files.

If a package is unavailable or its verification fails, do not substitute a similarly named directory. Use another reviewed source through its proper verification path. A valid package proves its content identity, not the outcome of a model task or the user's complete project.

## What Is Not in the Archive

Project databases, user configuration, credentials, raw sessions, private controls, caches, tests and local acceptance bodies are excluded. A same-version hosted ZIP refresh is a new immutable package qualified against its source commit. Preserve prior packages/receipts and the original tag object as history, and publish the current digest/receipt. When a same-version alignment is explicitly authorized, the current tag and both GitHub-generated source archives must identify the same qualified commit as the MALTS ZIP. Source archives contain the repository tree; the MALTS ZIP additionally has its distribution manifests and lifecycle layout.

Exclusion is part of the distribution contract. A source checkout can contain maintainer controls and tests that are useful locally but have no place in the installed/public payload. Public projection uses exact classification, not a broad directory copy.

Likewise, update/recovery evidence generated after publication remains local to its owning workspace. It should identify the public artifact rather than be inserted into the old ZIP. This preserves the distinction between package content at release time and later observed installation/project results.
