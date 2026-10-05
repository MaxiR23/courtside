# 0005. CI and git hooks

- Status: Accepted
- Date: 2026-10-05

## Context

`scripts/merge.sh` refuses to merge without required checks, and the gate
only ran inside the loop. Developers on macOS have bash 3.2 and BSD tools.

## Decision

- One GitHub Actions workflow with one job per app, `api` and `web`, each
  calling `scripts/gate.sh <app>`.
- Every action is pinned to a full commit SHA with its version in a
  comment. Workflow permissions are `contents: read` and checkout does not
  persist credentials. A new push to a pull request cancels its run in
  progress. Each job has a timeout.
- Plain git hooks in `.githooks/`, no hook framework, enabled with
  `git config core.hooksPath .githooks`.
- `pre-commit` runs `scripts/gate.sh <app> fast` (lint and format check)
  for each app with staged changes. `pre-push` runs the full gate for each
  app changed in the pushed commits.
- The hooks and `scripts/gate.sh` run on bash 3.2 with BSD tools.

## Consequences

- The required checks are `api` and `web`, listed in `REQUIRED_STATUS`.
  Renaming a job means updating `scripts/merge.sh`.
- Updating an action means changing its SHA and its comment together.
- The hooks are opt-in per clone, and `git commit --no-verify` and
  `git push --no-verify` skip them, so CI stays the enforced check.
- The fast gate checks the working tree, not only the staged content.
- The cloud session does not enable the hooks (its setup script is out of
  scope), and `scripts/ship.sh` runs the full gate itself.
- Repository rulesets and branch protection are not decided here.
