# CLAUDE.md

Strict rules for this repository. Read `docs/workflow.md` before running
the loop: it holds the full workflow, the conventions and the recovery
cases. Read `docs/architecture.md` before any change: it holds the
decisions in force and the open ones.

## Hard rules

- Never commit, push, create branches or open pull requests by hand. Only
  `scripts/ship.sh`, through the `ship` skill.
- Never create issues by hand. Only `scripts/issue.sh`, through the
  `create-issue` skill.
- Merge a pull request only with `scripts/merge.sh`, after `publish` and
  the footer removal step. Never merge any other way: no `gh pr merge`, no
  web UI, no other API call.
- Never use GraphQL: it is blocked in cloud sessions. That rules out
  `gh issue create`, `gh issue edit`, `gh issue view`, `gh pr create` and
  `gh pr edit` as direct calls. Read with `gh api` (REST) or the built-in
  GitHub tools.
- After every `publish` and every issue `create`, remove the attribution
  footer with the built-in GitHub tools only, never `gh` or `gh api`, and
  read it back to confirm. See `docs/workflow.md`, section 7.
- A change that depends on an item under "Open decisions" in
  `docs/architecture.md` stops: the item goes in the issue as a BLOCKING
  question until the decision is recorded.
- Svelte 5 runes only in `/web`. Syntax from earlier Svelte versions is
  not used.
- Every user interface change in `/web` follows `docs/design.md`: its
  tokens, components, motion and copy. Styles use the tokens in
  `web/src/lib/styles/tokens.css` and never repeat raw values.
- The Pydantic models in `/api` are the single source of truth for every
  feed. Generated TypeScript types are never edited by hand. A change to a
  feed model regenerates them in the same change.
- Every change that adds or changes behavior adds or updates its tests in
  the same change, following `docs/testing.md`.
- An accepted ADR in `docs/adr/` is never edited, except for its status
  line when it is superseded. An ADR and its update to
  `docs/architecture.md` ship in the same change.
- No dependency is added to `/web` without a reason recorded in its pull
  request.
- Never print, log or echo the value of any environment variable.
- Never write a secret, token, email or attribution to an AI tool in code,
  content, commits, issues or pull requests.
- Never offer to watch a pull request after publishing.
- Code, comments, commits, branches, issues and pull requests: English.

## Loop

You are the orchestrator. Dispatch each stage by name with a one-line
prompt (issue number, plan path, mode). Do not read the agent definitions
and do not implement.

    create-issue / refine-issue   (skills, only when needed)
    plan-issue                    (agent, only for non-trivial issues)
    implement-issue               (agent)
    scripts/loop-path.sh          (short -> ship, full -> review)
    review-changes                (agent, full path)
    verify-findings               (agent, only on BLOCKING or IMPORTANT)
    implement-issue, fix mode     (agent, only if verify confirmed fixes)
    ship                          (skill: prepare, publish, footer removal, merge)

There is no owner approval at any stage. The only stop is a BLOCKING open
question in the issue: write it in the issue and stop the loop on it.

## Gate

The gate covers `/web` and `/api`. `implement-issue` runs it once, when
the plan is implemented, from the repository root:

    scripts/gate.sh web
    scripts/gate.sh api

`scripts/gate.sh` is the only place the gate commands are written.
`scripts/ship.sh` and CI call it and never repeat its commands.
`scripts/gate.sh api` is in force: it runs ruff check, ruff format check,
mypy strict and pytest. `scripts/gate.sh web` is in force: it requires
`web/node_modules` and runs lint, format check, svelte-check, Vitest
and the production build through the scripts in `web/package.json`.
