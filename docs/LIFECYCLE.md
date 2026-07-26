# MALTS Lifecycle

The lifecycle engine installs and manages one immutable MALTS generation at a
time. It consumes a verified outer package, keeps generation identity in its
registry, and writes projections only to the selected tool roots.

## Operations

| Operation | Purpose | Requires a verified package |
|---|---|---|
| `install` | Create the first managed generation. | Yes |
| `update` | Activate a newer verified generation. | Yes |
| `repair` | Reapply the active generation when managed files drift. | Yes |
| `uninstall` | Remove MALTS-managed material from the lifecycle root and selected tool roots. | No |

## Safety model

- `plan` is reviewable and hash-bound.
- `execute` accepts only the exact reviewed `plan_hash`.
- Paths must be absolute, separate, and free of links or reparse points.
- The engine journals changes so interrupted work can be recovered.
- Tool roots outside the selected set are not modified.

## Common commands

Use the user payload root for the engine path.

```powershell
python -B <PAYLOAD_ROOT>\tools\malts_lifecycle.py verify-release `
  --release-root <VERIFIED_OUTER_PACKAGE>
```

```powershell
python -B <PAYLOAD_ROOT>\tools\malts_lifecycle.py plan `
  --operation update `
  --lifecycle-root <LIFECYCLE_ROOT> `
  --tool-root codex=<CODEX_ROOT> `
  --release-root <VERIFIED_OUTER_PACKAGE> `
  --out <PLAN_PATH> `
  --apply
```

```powershell
python -B <PAYLOAD_ROOT>\tools\malts_lifecycle.py execute `
  --plan <PLAN_PATH> `
  --expected-plan-hash <PLAN_HASH> `
  --apply
```

For recovery after an interruption, inspect the lifecycle root first and then
run `recover` with the same lifecycle root. Do not delete transaction state by
hand.

See [Install](INSTALL.md) and [Usage](USAGE.md).
