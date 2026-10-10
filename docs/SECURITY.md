# Security

Security and privacy apply to the whole MALTS workflow, installation and distribution. Current version: **2.0.1**.

## Verify Before Use

Check actual repository/ref, VERSION, release identity and closed inventories. Verify ZIP before extraction; discover the installed runtime through the tool Boot and registry/pointer. Names and old receipts are not current integrity checks.

Check both provenance and current bytes. A trusted repository name does not prove that a local checkout is complete or that an extracted archive has safe paths. The lifecycle verifies declared inventories and rejects unexpected content before activation; discovery then checks the installation identity chain.

Use the actual source selected for this operation. A historical signature/hash or prior successful installation applies to its own input, not an edited guide/tree under the same version string. Preserve the mismatch for diagnosis and requalify the changed source instead of copying a trusted label onto it.

## Installed Provenance Privacy

Installed provenance binds source kind and content identity without exposing maintainer machine/source paths. Public repository/archive exclude private controls, databases, sessions, credentials and local evidence. Generic placeholder/current-user examples are not an invitation to publish real paths.

## Keep Local Data Local

Sensitive definitions/content use Windows current-user DPAPI and descriptors for owner, sensitivity, allowed purposes and retention. Encryption is not redaction or cross-user recovery proof. Derivatives require reviewed lineage and eligible purposes; withdrawal stops dependent reuse.

Evidence descriptors bind owner/target, classification, sensitivity, review, retention and allowed purposes. A body can be eligible for recovery while ineligible for derivation or Growth. Copying it into a report or changing its label does not satisfy those checks.

Current evidence derivation is a controller-reviewed operation with exact source identities and retained lineage; it is not an automatic sanitizer. Before reuse, the transitive source closure checks current bindings and access. Source withdrawal or expiry can stop a derivative even when its stored bytes are intact.

DPAPI protects content under the current Windows user profile. It does not certify that text is redacted or safe to publish, nor does it establish cross-user restore capability. Keep the original purpose checks and Host permissions in addition to encryption.

## Review Before Mutation

Grants bind actors/resources/effects and current task revisions; services check dependency, budget, epoch and admission. Preserve preimages. UNKNOWN effects are reconciled under original identities, not blindly retried. Managed fencing does not exclude arbitrary external editors. Protect secrets from shell arguments/history as well as output.

A managed adapter checks exact task/grant/resource/effect and current lease/epoch at its boundary. It can reject an old actor or changed file without proving that every other program on the machine is stopped. Inspect external editor/service writers when they affect the target.

For updates, preserve the current opened-file preimage and compare its hash before writing. If the result becomes uncertain, inspect the original operation and observed target; do not issue the same effect through a new actor/ID to evade the rejection. Recovery records must retain consumption and late observations.

The same principle applies to publication: review the exact staged paths and source identity, exclude private material, then verify the hosted result. An authorized repository push is not permission to export workspace databases or raw acceptance bodies.

## Retention And Recovery

Preserve binding/source-seals, original acceptance, uncertain effects and required backups. Age and candidate names are insufficient for cleanup. Restore within current v2 and reconcile later work/consumption; do not revive old permission.

## Report Security Issues

Send a minimal redacted reproduction through the [repository](https://github.com/SssoGin/MALTS). Never include keys, raw sessions or protected evidence bodies. See [State Contract](V2_STATE_CONTRACT.md).

## Governed adoption boundary

`legacy-adoption-preflight` checks separate source/capsule/state roots and Windows control-input support before persistent preparation; a valid layout grants no write permission. `legacy-adoption-apply` defaults to preview, binds the exact plan hash and current runtime, and uses real source seals, Windows input guards and SQLite definition rechecks. Its built-in profile covers reviewed MALTS control inputs and legacy transaction admission; it does not isolate arbitrary external applications or take over a business root.

Failure preserves the original adoption ID, plan, owned seals and private handoff evidence. Do not replay under a new ID or delete binding files to restore legacy authority. `workspace` distinguishes a legacy source, unbound imported store and sealed recovery scene. Adopted entry rechecks Project/plan/Task/dependency bodies and reports LONG_PROJECT, phase_ready and blockers. This is governance readiness, not a Grant or business acceptance. Effects on external roots need separately reviewed resources and adapters. See [adoption and upgrade](V2_PREVIEW_USAGE.md#v2-migration).
