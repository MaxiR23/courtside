# Architecture Decision Records

Decisions that shape the project and are expensive to reverse are recorded
here, one file per decision.

## When to write one

- An item under "Open decisions" in `docs/architecture.md` is closed.
- A decision in force is replaced by a different one.
- A choice affects more than one part of the project (`/web`, `/api`, the
  data contract, hosting or the workflow) and is not obvious from the code.

A decision that only affects one module and is clear from its code does
not need an ADR.

## Naming

`NNNN-short-title.md`: a four-digit sequence number and a lowercase,
hyphenated title. Numbers are never reused.

```text
0001-testing-tools.md
0002-hosting.md
```

## Format

Every ADR has these sections:

```markdown
# NNNN. Title

- Status: Accepted | Superseded by NNNN
- Date: YYYY-MM-DD

## Context
What needed deciding and why.

## Decision
What was decided.

## Consequences
What follows from it, including what it rules out.
```

## Rules

- An accepted ADR is not edited. When a decision changes, a new ADR is
  written and the old one's status changes to `Superseded by NNNN`. That
  status line is the only edit an accepted ADR ever gets.
- `docs/architecture.md` always reflects the decisions in force. An ADR and
  its update to `docs/architecture.md` ship in the same change.