---
name: malts-project-init
description: Initialize or refresh MALTS-aware project instructions for a workspace. Use when the user asks for an /init-like workflow, project initialization, project-level AGENTS.md, PROJECT_CONTROL.md, WORK_TASK_REPORT.md, PROJECT_HANDOFF.md, optional translated mirrors on explicit request, Claude Code compatibility through CLAUDE.md, or setup of MALTS operating rules for a new or existing project. This is a shared MALTS installed skill for supported Agent adapters, not a Claude Code slash command.
---

# MALTS Project Init

Initialize a workspace with project-level Agent instructions and MALTS control files while preserving the user's execution gate: read-only discovery first, plan second, explicit authorization third, writes last.

## Non-Negotiable Gate

- Treat read-only inspection as allowed.
- Before any file write, edit, delete, move, dependency install, generated artifact, long-running service, git state change, remote write, or sub-agent dispatch, show a concrete plan and wait for explicit user authorization.
- Accept authorization only when it responds to the latest concrete plan and uses words such as "执行", "确认执行", "确认", "继续", "直接做", "都做了", `确认运行`, or an equivalent explicit approval.
- If the user only asks what init does, whether it is needed, or how it differs from Claude Code `/init`, answer without writing files.
- If additional work is discovered outside the approved plan, stop and ask for a new authorization.

## Workflow

### 1. Resolve MALTS Context

Read these files before proposing writes:

```text
MALTS_BOOT.md, when installed beside the active tool instruction file
<GLOBAL_BOOT>
<GLOBAL_MEMORY>
```

Derive `MALTS_ROOT` from `MALTS_BOOT.md` or `<GLOBAL_BOOT>` when either boot file is configured. Prefer the nearest active tool boot file for portable installs, and use an explicitly configured global boot file only when the user or project already provides one. If no boot file is configured, use the installed MALTS repository root after verifying that it contains `README.md`, `skills/`, `runtime/EN/templates`, and `runtime/EN/checklists`. Do not treat copied absolute paths elsewhere as authoritative.

For MALTS-enabled project initialization, read the shared skills, templates, and checklists required by the configured MALTS root before writing project-level instructions. At minimum this includes:

```text
<MALTS_ROOT>\README.md
<MALTS_ROOT>\skills\grill-me-preflight\SKILL.md
<MALTS_ROOT>\skills\multi-agent-long-task-scheduling\SKILL.md
<MALTS_ROOT>\skills\malts-project-init\SKILL.md
<MALTS_ROOT>\runtime\EN\templates\PROJECT_CONTROL.template.en.md
<MALTS_ROOT>\runtime\EN\checklists\QUALITY_GATE.en.md
```

If creating the first MALTS project-level `AGENTS.md`, also inspect the relevant files under `<MALTS_ROOT>\skills\`, `<MALTS_ROOT>\runtime\EN\templates\`, and `<MALTS_ROOT>\runtime\EN\checklists\` so the generated file does not omit required deliverables such as `WORK_TASK_REPORT`, Growth Review tiers, and checklist references.

When the initialization language profile selects Simplified Chinese, also read these localized drafting references before writing canonical project artifacts:

```text
<MALTS_ROOT>\runtime\CH\templates\PROJECT_CONTROL.template.zh-CN.md
<MALTS_ROOT>\runtime\CH\templates\WORK_TASK_REPORT.template.zh-CN.md
```

### 2. Inspect The Workspace

Read only. Check for:

- Existing instruction files: `AGENTS.md`, `CLAUDE.md`, `.claude\CLAUDE.md`, `CLAUDE.local.md`, `.cursorrules`, `.windsurfrules`, `.devin\rules\`, `opencode.json`.
- Existing MALTS state files: `PROJECT_CONTROL.md`, `WORK_TASK_REPORT.md`, `PROJECT_HANDOFF.md`, and any optional translated mirrors that already exist.
- Project facts: README, package manifests, build/test config, language/framework indicators, repository status, and obvious entry points.
- If the user provided a separate source project path, inspect that source project root and record that source-project writes remain out of scope unless explicitly authorized.
- If future source-project writes are likely, discover but do not summarize away the relevant layered instruction files. Record that before writing a source path the agent must re-read the source root and nearest target-path instructions such as `AGENTS.md`, `CLAUDE.md`, `.claude\CLAUDE.md`, nested `AGENTS.md` / `CLAUDE.md`, `.cursorrules`, `.windsurfrules`, `.devin\rules\`, and tool-specific config.

Do not infer project conventions that can be verified from files. Do not overwrite existing instructions; plan a surgical merge.

### 2.1 Determine The Initialization Language Profile

During read-only discovery, determine and record:

- `NarrativeLanguage`: the user's or project's primary language for visible headings, prose, plans, risks, decisions, and report content.
- `StableSchemaLanguage`: keep `MALTS:section` markers, status values, IDs, evidence levels, paths, commands, and code literals stable and English-compatible.
- `TemplateRoute`: use the matching localized runtime template as the drafting source when one exists; use the EN template as the structural fallback.

For a Simplified Chinese user or Chinese-facing workspace:

- Write project-specific `AGENTS.md` headings and explanatory prose in Simplified Chinese, while preserving code, commands, paths, variables, model names, and proper nouns.
- Draft canonical `PROJECT_CONTROL.md` from `runtime\CH\templates\PROJECT_CONTROL.template.zh-CN.md`.
- Draft canonical `WORK_TASK_REPORT.md` from `runtime\CH\templates\WORK_TASK_REPORT.template.zh-CN.md`.
- Keep the canonical filenames unchanged. Do not create `项目控制.md` or `工作任务报告.md` unless the user explicitly requests a full translated mirror.

### 3. Offer Preflight When Appropriate

For non-trivial project starts, offer MALTS-native Grill-Me Preflight from:

```text
<MALTS_ROOT>\skills\grill-me-preflight\SKILL.md
```

Explain briefly that it exposes hidden assumptions, goal boundaries, tradeoffs, and acceptance criteria. Do not auto-run it. Skip for S0/S1 work where the goal and verification path are already clear. Record `offered`, `accepted`, `declined`, or `N/A` in `PROJECT_CONTROL.md` when it is created or updated.

### 4. Present The Plan

Before writing, state:

- Which files will be created or updated.
- Whether `AGENTS.md` is new or a merge.
- Whether `CLAUDE.md` will be created, updated, or left alone.
- Whether `PROJECT_CONTROL.md` will be created or updated as the canonical control file.
- Whether `WORK_TASK_REPORT.md` will be created, updated, or left alone.
- Whether any optional translated mirror will be created, updated, or left alone because the user explicitly requested it.
- The default write scope for the init round.
- Any source project paths that are read-only context, and the exact authorization required before writing to them.
- Project assumptions discovered from files.
- The selected `NarrativeLanguage`, `StableSchemaLanguage`, and `TemplateRoute`.
- Verification checks to run after writing.

Then stop and wait for explicit authorization unless it has already been given for this exact plan.

### 5. Write Project Files After Authorization

Default outputs:

- `AGENTS.md`: primary project-level instructions for Codex and compatible agents.
- `PROJECT_CONTROL.md`: canonical project control file. Use the selected localized template for visible headings and narrative content; keep `MALTS:section` markers, status values, task IDs, evidence levels, paths, and commands stable.
- `WORK_TASK_REPORT.md`: canonical lightweight task execution report scaffold for future work logs and verification records. Use the selected localized template and the user's or project's primary language while keeping stable structure fields.
- `PROJECT_HANDOFF.md`: create only for handoff or context-risk workflows, not during default initialization. When created, include a short English Agent Brief and then use the user's or project's primary language.
- Optional translated mirrors (`项目控制.md`, `工作任务报告.md`, `项目交接.md`): create only when the user explicitly asks for full translated mirrors or an external workflow requires them.
- `CLAUDE.md`: optional compatibility shim, usually:

```md
@AGENTS.md
```

Only create `CLAUDE.md` by default when the user asks for Claude Code compatibility or the plan explicitly included it. If `CLAUDE.md` already exists, preserve Claude-specific instructions and merge carefully.

Do not create separate `DECISION_LOG.md`, `RISKS.md`, `LAUNCH_REVIEW.md`, `QUALITY_GATE.md`, `PROJECT_HANDOFF.md`, or `GROWTH_REVIEW.md` during default initialization. Add decision log and risk register sections inside the control files. Create the other files only when the project reaches that workflow stage or the user explicitly asks.

### 6. Required AGENTS.md Content

Keep `AGENTS.md` concise and project-specific. Include:

- A top-priority answer/execution separation gate if not already present. For Chinese users or Chinese-facing workspaces, write this gate in Simplified Chinese or bilingual form, including non-authorization examples, the rule that authorization must respond to the latest concrete plan, scope limits, and violation recovery.
- Default Simplified Chinese response preference, while preserving code, commands, paths, variables, and proper nouns.
- For Chinese-facing projects, Simplified Chinese visible headings and project-specific explanatory prose; do not copy the English adapter example wholesale into the project file.
- Project facts discovered from the workspace.
- Build, test, lint, and verification commands only when verified.
- Default write scope: unless the user explicitly authorizes a source project path or other external path, state-changing writes are limited to the initialized workspace and the files named in the approved plan.
- Source project boundary rule: before writing to any separate source project or any path outside the default write scope, re-read the source project root instructions and the nearest applicable target-path instructions; copied summaries in control files do not replace those layered instructions.
- MALTS discovery rule: read `<GLOBAL_BOOT>` when configured, derive `MALTS_ROOT`, then read `<GLOBAL_MEMORY>` when configured.
- When to suggest MALTS and Grill-Me Preflight.
- Requirement to create or reuse project control before substantive non-trivial implementation.
- Requirement that `PROJECT_CONTROL.md` is the single canonical control file by default.
- Requirement to maintain `WORK_TASK_REPORT.md` for non-trivial implementation tasks.
- Requirement to avoid full translated mirrors unless explicitly requested; Chinese narrative can live inside `WORK_TASK_REPORT.md`.
- Rule that no sub-agent dispatch happens until a launch review is shown and the user replies `确认运行`.
- Rule that unattended auto-continue requires explicit authorization and recording.
- Handoff and migration-package rules only if relevant to this project or inherited from the global boot rules.

Avoid:

- Speculative architecture claims.
- Generic framework advice that Codex can rediscover.
- Duplicating large MALTS docs inline.
- Reformatting unrelated existing instructions.

### 7. Required Control File Content

Create or reuse `PROJECT_CONTROL.md` as the single canonical control file. Do not create a full translated mirror by default. If an optional translated mirror already exists, preserve it and either update it only when explicitly requested or record that `PROJECT_CONTROL.md` is authoritative.

Use the selected localized template for visible headings and narrative content. Preserve stable `MALTS:section` markers so lint and future Agents do not depend on the display language.

Include:

- Project identity and workspace path.
- MALTS_ROOT resolved from `GLOBAL_BOOT.md`.
- Current status and active objective.
- Scope, non-goals, assumptions, risks, and open questions.
- Default write scope and any separate source-project paths treated as read-only context until explicitly authorized.
- Existing instruction merge log, including source-project instruction files inspected and the rule to re-read nearest instructions before source-project writes.
- Decision log and risk register sections.
- File ownership and protected files if relevant.
- Verified read-only facts / checks section for discovery results, plus verified install, test, lint, build, and dev server commands when they exist. Mark unknown commands as `unknown` instead of inventing them, and mark expected failures as facts instead of presenting them as runnable project commands.
- Existing instructions merge log describing what was preserved, merged, skipped, or left untouched.
- Last init snapshot with timestamp, workspace path, resolved `MALTS_ROOT`, and key source docs read.
- Grill-Me Preflight status.
- Launch review status and sub-agent dispatch status.
- Verification log.
- Growth Review / memory candidate section.
- Handoff location if relevant.

When Chinese text is present on Windows, prefer UTF-8 with BOM if the surrounding project convention does not conflict.

### 8. Required Work Task Report Content

Create a compact scaffold, not a verbose report. `WORK_TASK_REPORT.md` is the canonical structure and evidence source. Use the user's or project's primary language for narrative content and keep English status values, evidence levels, paths, commands, and IDs stable. Do not create a full translated mirror unless explicitly requested. Include:

- Purpose: task-level execution and verification notes for future non-trivial work.
- Current task table with task id, status, owner, scope, files touched, and last update.
- Verification log with command, result, date/time, and notes.
- Blockers and follow-ups.
- Rule that reports should be updated during and after substantive implementation, not used as a substitute for user authorization.

If `WORK_TASK_REPORT.md` or an optional translated mirror already exists, preserve history and add only missing scaffold sections inside the canonical file unless the user requested mirror maintenance.

### 9. Verify

After writing, run read-only checks:

- Re-read created or updated files.
- Confirm required files exist.
- Confirm `PROJECT_CONTROL.md` exists when the plan included MALTS state.
- Confirm `WORK_TASK_REPORT.md` exists or that the plan explicitly left it out.
- Confirm optional translated mirrors exist only when explicitly requested, or that they were intentionally not generated.
- Confirm `AGENTS.md` contains the execution gate and MALTS discovery pointer.
- Confirm `AGENTS.md` records default write scope and the source-project boundary rule when a separate source project or external path was provided.
- Confirm Chinese-facing `AGENTS.md` content includes the full authorization gate in Simplified Chinese or bilingual form, not only an English summary.
- Confirm the selected initialization language profile is recorded and the canonical control/report files use the matching localized template route.
- Confirm all required `MALTS:section` markers remain present in `PROJECT_CONTROL.md`.
- Confirm control files contain decision log, risk register, verified commands, existing instructions merge log, and last init snapshot sections.
- Confirm no sub-agent dispatch, long-running service, dependency install, or git state change occurred unless explicitly approved.
- Show a concise summary and any remaining gaps.

Use `git diff -- AGENTS.md CLAUDE.md PROJECT_CONTROL.md WORK_TASK_REPORT.md PROJECT_HANDOFF.md` when the workspace is a git repository and those files are tracked or newly created; do not stage or commit unless explicitly requested.

## Relationship To Claude Code /init

Claude Code `/init` generates or improves `CLAUDE.md` for Claude Code. This skill generates or maintains `AGENTS.md` and MALTS control files for Codex/MALTS workflows. Create a thin `CLAUDE.md` importing `AGENTS.md` only when compatibility is desired.
