# Changelog

## 0.1.5

Patch release for token-efficient runtime artifacts and handoff recovery.

- Made `PROJECT_CONTROL.md`, `WORK_TASK_REPORT.md`, and `PROJECT_HANDOFF.md` the default canonical runtime artifacts.
- Clarified that translated mirrors such as `项目控制.md`, `工作任务报告.md`, and `项目交接.md` are optional and created only when explicitly requested or externally required.
- Added a short English Agent Brief requirement to `PROJECT_HANDOFF.md` while allowing the main body to use the user's or project's primary language.
- Updated MALTS init, long-task scheduling, session handoff, adapter README, public docs, templates, and checklists to match the single-canonical-document policy.
- Preserved EN/CH public documentation synchronization without requiring duplicate runtime reports by default.

## 0.1.4

Patch release for shared-root installation and lighter tool adapters.

- Changed the default installer layout to one shared `MALTS_ROOT` plus thin tool adapters.
- Stopped creating full per-tool `malts/` runtime copies by default.
- Added explicit `-SharedRoot` install/update control.
- Added Windows UTF-8 execution guidance to installed tool instruction templates.
- Updated install layout validation to reject per-tool runtime copies and duplicate tool-local skills.

## 0.1.3

Patch release for public install, update, and adapter reliability.

- Added one-script update support with dry-run defaults, pull/install modes, and safe merge behavior
- Added temporary install smoke tests and installed-layout validation
- Strengthened public package safety checks for machine-specific path literals and high-confidence secret values
- Added Codex-native scaffold, runtime Chinese mirrors, and bilingual public documentation updates

## 0.1.2

Patch release for public repository audit fixes.

- Added UTF-8 BOM to all zh-CN documentation files
- Documented `new-project-control` command in tools/README
- Aligned Codex adapter README with Claude Code and OpenCode structure
- Fixed zh-CN BILINGUAL_DOCS content drift from EN version
- Unified "sub-agents" hyphenation across all files
- Replaced hardcoded version with `<MALTS_VERSION>` placeholder in template
- Added Long-Task Mode, Model Policy, Safety sections to Codex and Claude Code templates

## 0.1.1

Patch release for public repository hygiene.

- Added CI release hygiene checks
- Expanded bilingual document structure validation
- Fixed Claude Code smoke-test scaffold wording
- Covered hidden adapter scaffold files in release checks
- Synchronized VERSION, README, README.zh-CN, CHANGELOG, and release verification examples
- Confirmed public release excludes user-specific generated state

## 0.1.0

- Initial public release.
- Added English runtime skills, templates, and checklists.
- Added optional Codex, Claude Code, and OpenCode adapter structure.
- Added public-safe `AGENTS.md` / `CLAUDE.md` instruction templates for tool-specific global guidance.
- Added `-SkipInstructionTemplate` so users can install adapter support without changing existing Agent instruction files.
- Added public session-handoff rules with `PROJECT_HANDOFF.md` as the default Agent-facing file.
- Added MIT license, contribution rules, install docs, and maintainer guidance.
- Kept bilingual documentation synchronization optional and disabled by default.
