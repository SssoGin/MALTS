# Agent-Assisted Installation

Use these rules when an Agent helps a user install MALTS.

1. Read [Install](INSTALL.md), [Lifecycle](LIFECYCLE.md), and [Security](SECURITY.md).
2. Confirm the user selected one or more tool roots and a separate lifecycle
   root.
3. Verify the downloaded package before extraction.
4. Generate a dry-run lifecycle plan and show its targets, destructive actions,
   and `plan_hash` to the user.
5. Wait for explicit authorization before executing that plan.
6. After execution, inspect the lifecycle state and the selected projections.

An Agent must not add an unselected tool, infer a tool root, reuse a stale plan
hash, or write live project files into the immutable user payload.

For ordinary project work after installation, follow the installed MALTS boot
pointer and the nearest project instructions.
