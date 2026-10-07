# MALTS Handoff

This is part of the complete MALTS system documentation. Current implementation/version is2.0.0; workflow context is in [System Overview](SYSTEM_OVERVIEW.md) and [Usage](USAGE.md).

## 1. Purpose and content

A handoff explains goals, evidence, next steps and recovery boundaries. It is an on-demand derived view, neither permission nor a second store. Ordinary successful turns need no handoff.

Include exact Task/revision/Phase, relevant plans, observed outputs, uncertain effects, Host/budget/epoch, unique manual notes and valid sources. Preserve historical failures/conditions instead of turning suggestions into commands.

## 2. Preserve, preview and publish

Preserve selected originals with handoff.preserve-note/capture-file. Preview returns bounded facts, partial markers and source token, without completeness or execution authority.

Guarded publication requires exact Task revision, current token, an existing reviewed output and exact preimage. Check drift and preserve recovery on failure. A missing output needs a separately scoped creation action, never blind redirection. Inspect publication under the original ID.

## 3. Continuation

Reverify Boot/binding/current Task and relevant actual files. Reconcile UNKNOWN under original identities. Historical completion, PAUSED and transport exit do not prove settled effects/processes. See [State Contract](V2_STATE_CONTRACT.md) and [v2 Operations](V2_PREVIEW_USAGE.md#v2-handoff).
