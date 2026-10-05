# Development workflow

Flow for every feature, fix or non-trivial change in this repo. The loop
runs in a cloud session from end to end without owner approvals, merge
included.

## 1. Open an issue

- Title: `type: short description`, lowercase, one line, no trailing
  period. `scripts/issue.sh` builds it from the type and the description.
- Allowed types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`,
  `style`, `perf`, `ci`, `build`.
- Exactly one label, equal to the type. `scripts/ship.sh` takes the branch
  type from the label and the commit message from the title.
- Body: `## Scope`, `## Out of scope`, `## Acceptance criteria` (as
  checkboxes), and `## Open questions` only if there are any, each tagged
  BLOCKING or DEFERRABLE.
- The `create-issue` skill drafts and creates it with `scripts/issue.sh`.
  The `refine-issue` skill fills the missing sections of an existing issue.
  An issue that has the three sections is not refined.
- Scope freeze: the scope is the issue body when the loop starts. What
  comes up mid-loop is a new issue, not an addition to the running one.
- A BLOCKING open question stops the loop on that issue until the answer
  is written in the issue. Nothing plans over an assumption.
- An issue that depends on an item under "Open decisions" in
  `docs/architecture.md` carries it as a BLOCKING question until the
  decision is recorded there.

## 2. Branch

- Do not create it by hand. `scripts/ship.sh prepare` creates it, from
  `main` or from a session branch that is not `type/short-description`,
  after fetching `origin`. It creates the branch at `origin/main`,
  carries the uncommitted changes into it, and fast-forwards local `main`
  to `origin/main`. It never forces, resets or rewrites history.
- If local `main` has diverged from `origin/main`, the session branch has
  commits that are not on `origin/main`, or the uncommitted changes touch
  files that changed on `origin/main`, `prepare` stops with a `prepare:`
  message and changes nothing.
- Naming: `type/short-description`, lowercase, hyphens, built from the
  first words of the issue title.
- Never commit to `main` directly.

## 3. Implement

- The orchestrator (the session) dispatches each stage by name with a
  one-line prompt. It does not read the agent definitions and does not
  implement.
- `plan-issue` runs for issues that add or change behavior, a component,
  a page, a feed model, a source adapter, a job or the project structure.
  A typo, a docs-only tweak or a config change goes straight to
  `implement-issue`, whose scope and acceptance criteria stand in for the
  plan.
- The plan is in force as written: there is no approval step.
- `implement-issue` reads the plan, not the sources the plan cites, and
  hands back with the diff stat.
- A change to a feed model regenerates the front end's types in the same
  change. Generated types are never edited by hand.
- Every change that adds or changes behavior adds or updates its tests in
  the same change.

## 4. Verify locally

- `implement-issue` runs the gate declared in `CLAUDE.md` once, when the
  plan is implemented. The gate covers both `/web` and `/api`. If it
  fails, it fixes and reruns, at most three attempts, then stops and
  reports.
- If no gate is declared, it says so and continues.

## 5. Pick the path and review

- `scripts/loop-path.sh` prints `short` or `full` from the changed files
  (see "Short path").
- Short: goes straight to `ship`.
- Full: `review-changes` once, over the diff against `origin/main` plus
  what is uncommitted, checked against `CLAUDE.md`,
  `docs/architecture.md`, `docs/testing.md` and the issue. Then `verify-findings`, only if the review reports BLOCKING or
  IMPORTANT findings.
- `implement-issue` in fix mode fixes what `verify-findings` confirmed, in
  one cycle. There is no second review: open minors are listed in the PR
  body as a record. Nobody reviews them before the merge.

## 6. Commit and publish

- Through the `ship` skill. It names the files of the change and runs
  `scripts/ship.sh prepare <N> <paths>`, which creates the branch, refuses
  forbidden paths and identities, and commits.
- The skill writes `.claude/loop/pr-<N>.body.md` and runs
  `scripts/ship.sh publish <N>` right away, which pushes and opens or
  updates the PR, with its label and the owner as assignee.
- Commits follow Conventional Commits, in English, imperative mood. No
  body: the reasoning goes in the PR.
- These branch commits never reach `main`; only the squash does.

## 7. Remove the attribution footer

The cloud session's GitHub proxy appends an attribution footer to PR and
issue bodies, and re-adds it when the body is edited through `gh` or
`gh api`. After every `publish` and every issue `create`:

1. Read the body with the built-in GitHub tools.
2. If it ends with the footer, remove the footer and its `---` separator
   with the built-in GitHub tools only.
3. Read it back with the built-in GitHub tools and confirm it is gone.
   For a PR, report the last 3 lines of the body.
4. Change nothing else in the body.

## 8. Merge

- After `publish` and the footer removal step, the `ship` skill merges with
  `scripts/merge.sh <pr>` only. Never merge any other way.
- The script requires the PR open, based on `main`, mergeable and with no
  failing checks, and waits until every required CI check is reported and
  succeeded. The required checks are `api` and `web`, the two jobs of
  `.github/workflows/ci.yml`, listed in `REQUIRED_STATUS` in the script. It
  squash-merges through the REST API with `<PR title> (#<N>)` as the title
  (squash is the only method enabled in the repository settings), and
  prints `verified` and `reason` of the merge commit, which the session
  reports.
- The squash commit is signed by GitHub and lands on `main` as one commit
  with the PR title and the number.
- The session never offers to watch the PR.

## Recovery

- Three gate failures inside `implement-issue` in plan mode: `plan-issue`
  writes an addendum from the failing output and `implement-issue`
  implements it. If that run also fails three times, or the failure was in
  issue mode or fix mode, stop and report to the owner with the output.
- A `scripts/ship.sh prepare` failure: fix what it reports through
  `implement-issue` in fix mode if it is about the change, or follow the
  script's own message, then `prepare` again.
- A `scripts/ship.sh publish` failure before the push: follow the
  script's message and `prepare` again. A failure after the push and
  before the PR exists ("branch is pushed but has no open PR") is retried
  with `publish`, never `prepare`.
- A `scripts/merge.sh` failure: report its message and stop; never merge
  another way.
- An open decision raised by `implement-issue`: if it is a product, design
  or architecture decision, write it in the issue as a BLOCKING question
  and stop the loop on that issue.

## Short path

`scripts/loop-path.sh` prints `short` only when every changed file is a
`.md` and none is `CLAUDE.md`,
`docs/architecture.md`, `docs/workflow.md`, or under `.claude/` or
`.github/`. Anything else is `full`. There is no partial path: the script
decides, not judgment.

    implement-issue -> scripts/loop-path.sh -> ship

## Cloud session notes

- GraphQL is blocked by the session's GitHub proxy: use `gh api` (REST) or
  the built-in GitHub tools. `scripts/ship.sh`, `scripts/issue.sh` and
  `scripts/merge.sh` already do.
- Git identity comes from the cloud environment variables
  (`GIT_AUTHOR_*`, `GIT_COMMITTER_*`), and commit signing is disabled there
  (`GIT_CONFIG_*`). `scripts/ship.sh` refuses to commit as the AI identity.
- Never print, log or echo the value of any environment variable.