# MALTS 2.0.0 System Overview

## 1. Purpose and use cases

MALTS (Multi-Agent Long-Task Scheduling and Growth System) provides recoverable execution, controlled collaboration and experience management for AI Agent project work. Goals, task revisions, permission scopes, observed effects and acceptance evidence share one service contract, so continuation starts from current facts.

Use it for work spanning turns, migrations, investigations and documentation delivery. A small task with a clear immediate result usually needs no persistent long-project state. MALTS does not replace reasoning, editors, Git, CI, secret management or human decisions.

## 2. Changes from 1.5

2.0.0 gives the selected state store and Task services ownership of execution facts. Project defines the overall goal, Phase the stage boundary and actual plan, and Task an acceptable unit of work. Markdown controls, reports and handoffs remain sources or reading views; they have no parallel write authority in an adopted v2 workspace.

Mechanisms include versioned dependencies, Grants, cumulative budgets, intent/observation separation, current acceptance proof, protected evidence, pause/cancel/successor handling, artifact relationships and controlled Growth. CLI and MCP use the same domain services. Skills supply methods and entrypoints, not permission.

## 3. Capabilities and evidence limits

| Capability | Mechanism | Limit |
|---|---|---|
| Long-task recovery | Revisions, checkpoints, pending operations, backup and new-epoch restoration | No replay of unknown effects or revival of old allowances |
| Controlled execution | Grants, admission, intent/observe and managed file adapters | Controls managed interfaces, not arbitrary OS writers |
| Acceptance | Criteria, methods, evidence levels and current file/dependency checks | Exit status, historical COMPLETED and self-ratings are insufficient |
| Collaboration | Explicit delegation, resource scope, Host state, budgets and integration | Single Agent by default; parallelism is not a benefit guarantee |
| Artifact reuse | Ownership, versions, lineage, relationships and current Shared proof | Historical explainability is not present eligibility |
| Improvement | Sourced proposals, bounded trials, future outcomes and retirement | Observed real trials include neutral outcomes; no automatic benefit claim |

## 4. Host support

Codex, Claude Code, OpenCode and DeepSeek Harness have adapters and recorded representative native task/recovery evidence. Qualification covers the observed versions, profiles and operations. DeepSeek Harness Desktop evidence uses Windows 0.2.0-rc.2 and covers tasks, reopening a session, directory terminals and stopping/resuming an associated backend. It does not prove GUI model cancellation or universal isolation.

Installation, discovery, native behavior and business effects are separate evidence layers. A requested model label is not authenticated provider identity. Universal speedups, money or human savings, cross-user protected-evidence recovery, distributed fleets, vector memory and autonomous publication are not certified capabilities.

## 5. Reading path

Start with [Getting Started](GETTING_STARTED.md), then [Usage](USAGE.md). Executable controller examples are in [v2 Operations](V2_PREVIEW_USAGE.md); mechanisms and evidence boundaries are in [Core Design](CORE_DESIGN.md) and the [State Contract](V2_STATE_CONTRACT.md).
