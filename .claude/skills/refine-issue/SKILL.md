---
name: refine-issue
description: >-
  Fills the missing sections of a GitHub issue of this repo (Scope, Out of
  scope, Acceptance criteria) by verifying the issue against the real code,
  and writes the body back to GitHub. Use only when an issue lacks one of the
  three sections; an issue that has them is not refined. Trigger on "refine
  issue #N" or when plan-issue or implement-issue stop for a missing section.
---

# Refine issue

An issue enters the loop with its scope frozen: the body as it is when the
loop starts. This skill exists for the issue that arrives without a
`## Scope`, a `## Out of scope` or a `## Acceptance criteria` section. It
fills what is missing and writes the body back, so the loop starts on a
complete, frozen body.

**Mutation posture.** Writes `.claude/loop/issue-<N>.md`. Edits the issue
body once, with the built-in GitHub tools. Never comments, labels, closes
or reassigns.

## When not to run

Read the issue with the built-in GitHub tools or
`gh api repos/{owner}/{repo}/issues/<N>` (REST only). If the body has the
three sections and each has content, stop and say it needs no refinement.

## Draft

1. Read only the files the issue touches, and `docs/architecture.md`.
   This is a draft of three sections, not an audit.
2. Never invent a file, function, command, path or behavior. Everything
   stated about the code is read from the code. What cannot be verified
   goes under `## Open questions`, each tagged BLOCKING (a product, design
   or architecture decision that changes the plan) or DEFERRABLE, never
   assumed.
3. If the issue depends on an item under "Open decisions" in
   `docs/architecture.md`, that item goes under `## Open questions` as
   BLOCKING until the decision is recorded.
4. Write the missing sections, keeping every existing section verbatim:
   - `## Scope`: what changes, in one paragraph.
   - `## Out of scope`: what deliberately stays untouched.
   - `## Acceptance criteria`: checkboxes, one per line, observable.
5. Cite code by file plus symbol, never by line ranges. Every number
   comes from counting.
6. Write the complete body to `.claude/loop/issue-<N>.md`.

## Edit

Write the body from `.claude/loop/issue-<N>.md` to the issue with the
built-in GitHub tools only, never `gh` or `gh api` (through the proxy they
add an attribution footer). Read it back with the same tools and confirm
the three sections are there and no footer was added; if one was, remove
it with the same tools, as in `docs/workflow.md`, section 7.

If BLOCKING questions remain, say so and stop the loop on this issue:
plan-issue refuses to start until they are answered in the issue.

## Critical gotchas

1. Never touch the title or the labels: `scripts/ship.sh` reads them.
2. Never edit any other issue.
3. Never widen a scope the issue already states: a missing section is
   filled, an existing one is kept as written.
4. Never a secret, token, email or attribution to an AI tool in the body.
5. Never print, log or echo the value of any environment variable.
