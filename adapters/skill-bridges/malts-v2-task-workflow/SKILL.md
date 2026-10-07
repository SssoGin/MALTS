---
name: malts-v2-task-workflow
description: Execute or resume a selected MALTS v2 task through its current task services, evidence and recovery state. Use for adopted v2 workspaces or explicitly selected v2 task operations, not unrelated maintenance or automatic migration.
---

# MALTS v2 task workflow bridge

This package provides native discovery only. The canonical workflow remains in the verified MALTS generation.

1. Locate the tool configuration root above this bridge's `skills` directory. Read its `MALTS_BOOT.md` and parse `MALTS_ROOT`.
2. Run that root's `tools/malts_lifecycle.py discover --tool-root <tool-configuration-root>`. Require matching registry, active pointer, generation identity and VERSION; use the returned runtime root. Reuse an unchanged discovery result from this task.
3. Select the requested workflow before loading detail. When the connected verified endpoint advertises `malts_workflow(topic=...)`, use `phase`, `artifact` or `recovery` for that request. Otherwise read the corresponding `skills/malts-long-project-workspace-init/references/v2-<topic>.md` under the verified root. For an ordinary Task query read its bounded context; for an actual Task operation use `skills/v2/malts-v2-task-workflow/SKILL.md` and only its selected execution reference. Reuse the controller's unchanged verified runtime/binding instead of repeating discovery. No Phase/Artifact/recovery review needs the general guide or the full Task execution reference.

If discovery fails or the canonical workflow is absent, report the missing v2 entry and continue independent work. Do not substitute historical paths, install or migrate a workspace, or infer authorization from this skill's presence.
