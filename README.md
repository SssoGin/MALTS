# MALTS v1.0

MALTS is a portable operating layer for agent work: it supplies project-control
templates, working checklists, reusable skills, and adapters for Codex, Claude
Code, and OpenCode.

This repository is a user distribution. It contains only material needed to
install, run, update, and understand MALTS in a project.

## Start here

1. Read [Install](docs/INSTALL.md) before writing into a tool root.
2. Verify the downloaded package and review a lifecycle plan.
3. Execute only the exact plan hash you reviewed.
4. Read [Usage](docs/USAGE.md) to start a MALTS-managed project.

For work that will span phases or windows, use `malts-long-project-workspace-init`.
It creates the root controls and the first active Phase as one reviewed
initialization; Sessions remain explicit and are not created automatically.

The same payload supports one selected tool, two selected tools, or all three.
It never starts network activity, provider calls, background polling, or an
automatic update by itself.

## What is included

- `runtime/`: canonical project-control templates and checklists.
- `skills/`: MALTS-native workflows for lightweight project initialization,
  phase-ready long-project initialization, preflight, long-task coordination,
  retrospective growth, and handoff.
- `adapters/`: Codex, Claude Code, and OpenCode projection inputs.
- `scripts/` and `tools/`: lifecycle planning, execution, integrity checks, and
  small project-control helpers.

## User documentation

- [Install](docs/INSTALL.md)
- [Agent-assisted install](docs/AGENT_INSTALL.md)
- [Lifecycle](docs/LIFECYCLE.md)
- [Usage](docs/USAGE.md)
- [Security](docs/SECURITY.md)

Chinese documentation is available in [README.zh-CN.md](README.zh-CN.md) and
`docs/zh-CN/`.

## Integrity

Verify the package before extraction. The bootstrap verifier checks the ZIP,
checksum, transport manifest, public notes, exact inventory, and inner
lifecycle artifact before it writes an extraction target.

See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
for attribution.
