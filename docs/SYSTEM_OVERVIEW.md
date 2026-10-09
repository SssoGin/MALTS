# MALTS System Overview

MALTS preserves project goals, current progress, observed results and recovery information across AI-agent execution rounds. It combines delivery, optional collaboration and evidence-based experience use through shared project/task contracts. Current version: **2.0.0**.

## 1. System Purpose

MALTS (Multi-Agent Long-Task Scheduling and Growth System) is an operating framework for AI Agent project work. It connects delivery, long-task scheduling, recovery, verification and learning so goals/results remain continuous across execution rounds.

Long work exceeds one prompt, context window or uninterrupted run. Migrations, investigations, cross-module changes, research and documentation can require this support. MALTS organizes the necessary records/checks instead of maximizing Agent count or producing files for every conversation.

## 2. Problems Addressed

Long projects risk rewritten goals, lost progress, premature completion, shared-edit conflicts and unsupported lessons. MALTS therefore preserves intent/acceptance, separates current state from history, makes effects recoverable/checkable, assigns integration responsibility and assesses experience through future facts. Existing data/tools and user decisions remain inputs and boundaries.

A long project can fail even when each local action looks reasonable. Requirements may be summarized incompletely; a successor may repeat an already performed operation; a worker may optimize its own task while breaking an integration constraint; and a favorable lesson may be applied where its original condition no longer exists.

MALTS addresses these failures by retaining the original/current goal, binding plans and dependencies to revisions, observing effects under stable identities, verifying outputs against criteria and retaining experience applicability. These mechanisms improve inspectability and continuation; their existence does not by itself establish a statistical improvement in project success.

The user therefore reviews both the artifact and the completion claim: does the output meet the requested goal, do the checks cover that claim, and are remaining limits explicit? A large collection of reports cannot answer these questions without actual evidence.

## 3. Core Operating Model

**Delivery: goal–plan–execution–verification–delivery.** Define outputs and acceptance, organize work, inspect results and report completion/remaining work accurately.

**Scheduling and continuity: current progress–bounded work–checkpoint–recovery/handoff–next step.** Each round has scope and stopping conditions; later executors continue from preserved facts. Delegation is optional and the main Agent owns the overall outcome.

**Growth: observation–cause analysis–candidate–future trial–retain/revise/withdraw.** Experience retains provenance and applicability; one successful event or rating does not make a permanent rule.

The processes share goals and evidence. A failed check leads to repair in delivery, a truthful checkpoint in continuity and an assessment of reusable lessons in Growth.

## 4. Required Core Capabilities

### Recoverable Project Control

Preserve original/current goals, allowed scope, exclusions and acceptance. Revisit affected plans/tasks when material facts change. Agents decide routine details and reuse same-scope authorization.

### Phase-Ready Long-Project Initialization

Projects define overall goals, stages define bounded delivery, tasks define executable/acceptable outputs. Revisions/dependencies identify whether prior decisions/results still apply. A long workspace needs a first executable stage, not merely empty directories.

### State Consistency And Recovery

Check inputs, permission and tools, then preserve outcomes/checkpoints. Handle interruption/cancellation/failure separately and establish actual effects before continuing. Current implementation separates preparation, intent and observation; unknown effects retain their original identity until reconciled.

### Verification Checklists

Accept work against explicit criteria: behavior for code, facts/structure/references for documents, actual entry/content for installation. Changed requirements/dependencies/outputs can invalidate prior proof. Local tests, exits and historical labels do not prove the overall goal.

### Artifacts and reuse

Preserve stage ownership, versions, provenance and relationships. Cross-task sharing requires current content/eligibility. Superseded/retired artifacts explain history without automatic reuse. Reusability and deletability differ; recovery has separate retention needs.

### Phase And Final Reporting

A durable report explains the current result and remaining work on demand. A Phase or Task status is not a narrative report.

### Handoff And Continuation

Reports explain results/evidence; handoffs explain current state, unresolved work, recovery conditions and next steps. Create them on demand. Preserve unique manual notes and compare current facts/target before publishing to avoid stale overwrites.

### Retrospectives and Growth

Light review responds to actual signals; without one it produces no empty report. Stage delivery, repeated failure or explicit requests can justify deeper review. Candidates specify sources, applicability, actions, checks and withdrawal. Future outcomes include helpful, neutral, harmful and inconclusive. Project experience and global rule/Skill changes have separate scopes.

### Skills, Templates, And Checklists

Canonical Skills organize the workflow; templates help draft goals, task contracts, reports and handoffs; checklists inspect delivery and proposed memory writes. They support the project rather than introducing another state or permission source.

These capabilities cooperate in one delivery. For a module migration, the Project records the preserved interface and deployment exclusion; a Phase defines a bounded migration stage; tasks bind analysis, implementation and checks; operations record actual changes; evidence supports their acceptance; a handoff identifies remaining compatibility work; and a review may propose a later method trial.

The user does not need to manually create every record. The selected workflow/controller supplies the actual service operations and explains the useful result. A record is required when its recovery, execution or verification contract needs it, rather than because every turn must produce a document.

Project-level acceptance remains wider than any one task. Implementation, local verification, installed entry and native Host behavior are different evidence layers. The controller must identify which layer a result establishes and what still remains for the user's whole goal.

## 5. Optional Capabilities

Single Agent fits clear/concentrated work or strong sequential dependencies. Multiple Agents can help independent exploration, modules, verification or justified parallel work.

Define roles, inputs, edit scopes, resources, budgets, outputs and checkpoints first. The main Agent chooses work, handles shared resources, integrates and accepts the final result. Extra executors add coordination/integration costs and must serve the goal.

MALTS constrains connected consumers; external editors/processes and Host capabilities require separate observation. Cancellation, pause and actual process exit are distinct facts.

Git, external memory, translated reports and unattended execution are selected by actual need and matching authorization. No optional facility is a dependency for every project.

## 6. Supported Tool Adapters

| Tool | Integration | Recorded scope |
|---|---|---|
| Codex | Native Skills/instructions, CLI/MCP and managed execution | Representative tasks, cold recovery and selected topics/profiles |
| Claude Code | Skills/configuration and shared workflows | Fixed-profile task/independent cold successor at 2.1.207 |
| OpenCode | Skills/configuration and shared workflows | Representative task/cold recovery at 1.17.18 |
| DeepSeek Harness | Discovery, configuration, projections and Desktop adapter | Windows0.2.0-rc.2 task/reopen/terminal/associated backend |

Evidence covers observed conditions, not arbitrary models/tools. Requested model names and authenticated effective identity remain distinct. English/Chinese guides describe one system; preserve authored project content without duplicating state.

Choose any of the four installation entries in [Install](INSTALL.md). AllIncluded selects all four Hosts in one shared installation. Each Host retains its own native configuration; existing split installations require explicit consolidation.

## 7. Typical Use Cases

Code changes across modules; engineering migration with compatibility checks; investigations that span windows; finite document/research delivery; explicit independent review; continuation after interruption. In each case, preserve an actual result and stopping condition rather than maximize tasks or Agents.

| Scenario | Persistent information that matters | Suitable ending |
|---|---|---|
| Interface migration | Compatibility constraints, predecessor/output revisions and checks | Agreed interface behavior verified |
| Investigation | Reproduction inputs, observations, rejected hypotheses and next experiment | Supported cause/result or explicit unresolved question |
| Document delivery | Audience, factual sources, chapter requirements and review limits | Required explanation and references checked |
| Interrupted execution | Original operation, current bytes/results, checkpoint and Host/budget state | Uncertainty reconciled before dependent continuation |
| Independent review | Exact artifact, review criterion and integration responsibility | Observed issues resolved or explicitly retained |

Use lightweight project work when the goal is bounded and recoverable within one round. Long-workspace governance is useful when stages and dependencies need persistent authority. The same product can therefore serve different task sizes without requiring identical ceremonies.

## 8. Non-Goals And Boundaries

Recorded evidence includes domain/permission/transaction/files/recovery/installation, representative native tasks and bounded collaboration/Growth observations. Each proves its own layer. Preserve the original incomplete baseline failure and neutral real Growth trials.

Uncertified capabilities include universal success rates, cross-tool causal speedups, actual money/human savings, arbitrary writers, GUI model cancellation and cross-user protected recovery. Distributed fleets, vector memory and autonomous publication are not delivered capabilities. See [Design](CORE_DESIGN.md).

## 9. Activation Modes

Simple work follows project rules. Recovery across rounds merits basic project records; long/multistage work uses stages/tasks. Collaboration/unattended execution needs its corresponding scope. Reports, handoffs, deep checks and reviews are on demand instead of rewriting records after every successful turn.

Consider invocation, wait, preparation, verification and integration costs. Bounded relevant reads, valid-evidence reuse and useful separation can control overhead without a universal saving claim. Budgets retain cumulative consumption across recovery/new rounds.

## 10. Public Release Contents

The reusable system comprises Skills, runtime templates/checklists, deterministic services, lifecycle scripts, native adapters and product guides. User project databases, sessions, credentials and private evidence are not distribution inputs. See [Release Archive](RELEASE_ARTIFACT.md) and [Security](SECURITY.md).

## 11. Implementation Continuity

2.0.0 unifies projects, stages, tasks, operations and evidence in the selected store/services. CLI/MCP share domain contracts, Skills guide work, templates/checklists aid drafting/validation, reports/handoffs provide views. These components support one process, not separate products.

Technical entities are Project, Phase and Task; exact fields belong in the [State Contract](V2_STATE_CONTRACT.md). Historical assets support reviewed adoption without a second writable authority. Installation and project adoption are separate; recovery stays in the current system.

The v1 releases established goals, recovery files, templates and lifecycle governance. The current task service makes revisions, effects and acceptance durable without changing the product purpose. Historical release details remain in [CHANGELOG](../CHANGELOG.md), not a new current task queue.

The current runtime preserves the original operating objectives while assigning executable facts to the selected store. User-authored plans and handoffs remain valuable narrative inputs; task services make their relevant revision and effect relationships explicit. The change concerns how state is enforced, not a requirement to discard project knowledge.

Migration is an explicit ownership change. Review mappings, writers, uncertain effects and backup before adopting an older workspace. Once adopted, the current binding/source seals identify that boundary and legacy Markdown writes cannot become another current authority. See [Update](UPDATE.md) for installation versus adoption.

## 12. Relationship To Detailed Design

Use [Getting Started](GETTING_STARTED.md), then [Usage](USAGE.md). Inspect existing progress before continuation; initialize only a new long goal. See [Operations](V2_PREVIEW_USAGE.md) for controllers and [Lifecycle](LIFECYCLE.md) for upgrades/recovery.

[Core Design](CORE_DESIGN.md) preserves the detailed model, operating sections and tradeoffs. [State Contract](V2_STATE_CONTRACT.md) defines exact current protocols.
