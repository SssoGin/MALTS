# Use MALTS in a Project

After lifecycle installation, start work from the tool's MALTS boot pointer.
It resolves the active immutable generation; do not copy runtime files into a
project manually.

## Start a project

For a non-trivial task, define the goal, acceptance criteria, task queue, and
recovery point in `PROJECT_CONTROL.md`. Record execution evidence in
`WORK_TASK_REPORT.md`. Create `PROJECT_HANDOFF.md` when another Agent needs to
continue the work.

Use the matching runtime templates under `runtime/EN/` or `runtime/CH/` as
drafting references. Keep one canonical control, report, and handoff file unless
the user explicitly requests a translated mirror.

## Choose the right workflow

- Use `malts-project-init` when only lightweight root project control is needed.
- Use `malts-long-project-workspace-init` when the project will span phases,
  windows, interruptions, or recovery boundaries. Selecting it is the choice
  for a long-project workspace: initialization creates the root controls and
  first active Phase together. It does not silently stop at a minimal skeleton.
- Use Grill-Me Preflight when goals, assumptions, tradeoffs, or acceptance
  criteria need clarification.
- Keep simple work single-agent.
- For a user-approved long or multi-agent task, show the launch review before
  dispatching work.
- Use the handoff skill when continuation context must survive a session change.

The long-project initializer requires an initial Phase ID and goal. Its dry run
must list the initial `PHASE_CONTROL.md`; missing Phase input causes a zero-write
failure. After apply, check `initialization_status=READY` and the active Phase.
No Session is created by initialization. Open one only for an explicit bounded
work-session boundary.

If an older workspace has root controls but no registered Phase, validation
reports `WS_INITIAL_PHASE_MISSING`. Supply its initial Phase through the
initializer or explicitly open its first Phase; existing user files are
preserved.

## Verify project control

The user helper validates the stable project-control structure and, when a
MALTS root is supplied, its active version reference:

```powershell
python -B <MALTS_ROOT>\tools\malts_user_tools.py check-project-control `
  --project-control <PROJECT_CONTROL_PATH> `
  --malts-root <MALTS_ROOT>
```

## Safety defaults

Plan before writing. Keep tool-root changes inside the user's approved scope.
Verify before reporting completion, and do not enable unattended continuation
unless the user explicitly authorizes its objective, limits, stop conditions,
and recovery behavior.
