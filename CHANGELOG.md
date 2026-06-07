# Changelog

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
- Confirmed public release excludes private handoff and release-control state

## 0.1.0

- Initial public release.
- Added English runtime skills, templates, and checklists.
- Added optional Codex, Claude Code, and OpenCode adapter structure.
- Added public-safe `AGENTS.md` / `CLAUDE.md` instruction templates for tool-specific global guidance.
- Added `-SkipInstructionTemplate` so users can install adapter support without changing existing Agent instruction files.
- Added public session-handoff rules with `PROJECT_HANDOFF.md` as the default Agent-facing file.
- Added MIT license, contribution rules, install docs, and maintainer guidance.
- Kept bilingual documentation synchronization optional and disabled by default.
