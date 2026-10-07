# MALTS 2.0.0 Release Archive

## 1. Repository and optional ZIP

Normal installation/update uses the reviewed [public repository](https://github.com/SssoGin/MALTS). The formal Release provides one MALTS-uploaded asset, MALTS-2.0.0.zip; platform-generated source archives are separate links. ZIP is optional for offline/archive/repository-unavailable use and is never automatically downloaded.

## 2. Contents and verification

ZIP contains the immutable lifecycle artifact, exact inventories/manifests and public notes. Repository-only files stay outside installation payload. Closed inventories, hashes, path/collision checks and safe extraction detect added/missing/changed content.

Obtain Verify-MALTSBootstrap.ps1 from the same trusted source. Verify read-only, then extract to a new output with Apply. Installation uses ReleaseRoot and reviewed plan/hash, never direct generation overwrite. See [Installation](INSTALL.md).

## 3. Evidence boundary

Integrity proves content/identity, not native model or business results. Installation/Host/project acceptance have separate evidence. Same-version consolidation retains exact artifact identity; historical packages/receipts keep their dates/versions. See [Lifecycle](LIFECYCLE.md).

## One Optional Release ZIP

The closed package includes RELEASE_NOTES.md, release/artifact manifests and exact file inventories. See their actual named entries after verification instead of assuming a generated source archive has the same structure.

### Install from an Extracted Archive

Use the extracted payload installer with ReleaseRoot. The archive does not bypass the plan-hash requirement, user-content merge checks or actual post-installation verification.
