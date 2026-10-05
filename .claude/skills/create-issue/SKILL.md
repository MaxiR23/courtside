---
name: create-issue
description: >-
  Drafts and creates a new GitHub issue for this repo with scripts/issue.sh,
  with one type label and a Conventional Commits title, so ship.sh can take
  the branch type from the label and the commit message from the title.
  Use when asked to "create an issue", "open an issue for", "file an issue",
  or when work comes up mid-loop that is outside the frozen scope.
---

# Create issue

The loop starts from an issue whose body is its frozen scope.
`scripts/ship.sh` takes the branch type from the issue's label and the
commit message from its title. This skill produces an issue that satisfies
both from the start.

**Mutation posture.** Writes `.claude/loop/issue-new-<slug>.md`. Runs
`scripts/issue.sh create` once. Edits the created issue only to remove an
attribution footer. Nothing else.

## Draft

1. Type: one of the types allowed in `docs/workflow.md`. The label is the
   type.
2. Description: lowercase, one line, no trailing period, short enough
   that `<type>: <description>` plus the ` (#N)` GitHub appends on squash
   fits in 72 characters.
3. Body, with exactly these sections and no HTML comments:
   - `## Scope`: what changes, in one paragraph.
   - `## Out of scope`: what deliberately stays untouched.
   - `## Acceptance criteria`: checkboxes (`- [ ]`), one per line,
     observable, so a person or a check can say pass or fail. "Works
     fine" is forbidden.
   - `## Open questions`, only if there are any, each tagged BLOCKING (a
     product, design or architecture decision that changes the plan) or
     DEFERRABLE. Never answer a question by assuming.
4. Read `docs/architecture.md`. If the issue depends on an item under
   "Open decisions", that item goes under `## Open questions` as
   BLOCKING until the decision is recorded.
5. When the issue touches existing code, read the files it touches and
   never invent a file, function, command or path.
6. Write the body to `.claude/loop/issue-new-<slug>.md`, where `<slug>` is
   the description in kebab-case.

## Create

Run:

    scripts/issue.sh create <type> "<description>" .claude/loop/issue-new-<slug>.md

Then follow the footer removal step in `docs/workflow.md`, section 7:
read the issue back with the built-in GitHub tools, remove a trailing
attribution footer and its `---` separator with the built-in GitHub tools
only, and read it back to confirm.

Report the number and URL. If the body has a BLOCKING open question, say
so: the loop does not start on that issue until it is answered in the
issue.

## Critical gotchas

1. Never create more than one issue per invocation.
2. Never `gh issue create` or any GraphQL call: GraphQL is blocked in
   cloud sessions. Only `scripts/issue.sh`.
3. Never two type labels, never a label that does not exist.
4. Never a secret, token, email or attribution to an AI tool in the
   title or body.
5. Never print, log or echo the value of any environment variable.
