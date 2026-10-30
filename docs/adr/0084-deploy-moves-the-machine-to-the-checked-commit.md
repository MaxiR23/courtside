# 0084. The deploy moves the machine to the checked commit

- Status: Accepted
- Date: 2026-10-30

## Context

Issue 440. ADR 0081 checks that `main` equals `origin/main` and then runs
`git pull --ff-only` on the machine. A merge that lands in between puts the api
on a commit other than the one that was checked and the one the web is built
from. ADR 0081 is not edited.

## Decision

- `scripts/deploy.sh` records the checked commit with `git rev-parse HEAD`.
- On the machine it runs `git fetch origin` and `git merge --ff-only <commit>`,
  never `git pull`.
- It then reads the machine's HEAD and stops before
  `sudo docker compose up -d --build` when HEAD differs from the checked commit,
  naming both hashes.
- The commit hash may be printed. No `.env.deploy` value is.

Refines ADR 0081's api update. The rest of ADR 0081 stays in force. ADR 0081 is
not edited.

## Consequences

- The api and the web of one run come from the same commit.
- A merge during a deploy needs another run.
- A machine clone that is ahead of the commit or has diverged stops the deploy
  before the rebuild and needs the operator.
