# Security

## Verify before use

Use the bootstrap verifier before extracting a downloaded package. It checks the
ZIP, checksum, transport manifest, public notes, exact inventory, safe Windows
paths, and the inner lifecycle artifact.

## Keep local data local

Do not place credentials, tokens, session data, user-profile paths, private
project files, cache directories, or generated runtime state inside a MALTS
user payload or tool projection.

Use environment variables or the selected tool's normal secure configuration
mechanism for credentials. Do not put secret values in `PROJECT_CONTROL.md`,
`WORK_TASK_REPORT.md`, handoff files, prompts, or command history.

## Lifecycle safety

Review every lifecycle plan before applying it. The plan identifies the exact
roots, operations, and generation identity. Stop if a target is unexpected,
contains a link or reparse point, or no longer matches the reviewed plan.

## Report a vulnerability

Share only the minimum reproducible information needed to describe the issue.
Remove secrets and private machine details before sending a report.
