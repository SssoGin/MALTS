---
name: grill-me-preflight
description: Use before non-trivial task or project starts to expose hidden assumptions, goal boundaries, key tradeoffs, and acceptance criteria.
---

# MALTS Skill Bridge

MALTS_SKILL_BRIDGE: grill-me-preflight

This lightweight package exists only for native tool discovery. The canonical skill implementation remains under the shared `MALTS_ROOT`.

1. Resolve the tool configuration root as the parent of this bridge's `skills` directory.
2. Read `MALTS_BOOT.md` from that tool configuration root and parse its `MALTS_ROOT:` value.
3. Verify `<MALTS_ROOT>/skills/grill-me-preflight/SKILL.md` exists.
4. Read that canonical `SKILL.md` completely and follow it instead of this bridge.

If the boot pointer or canonical skill is missing, stop and report the exact missing path. Do not substitute this bridge for the canonical workflow.
