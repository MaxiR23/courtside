# 0002. Package managers

- Status: Accepted
- Date: 2026-10-05

## Context

The project has two apps, `/web` and `/api`, in one repository. Each needs
a package manager before it can be scaffolded. Dependencies are installed
in three places: a developer's machine, the cloud sessions that run the
agent loop, and CI. All three must install exactly the same versions.

## Decision

- `/web`: pnpm.
- `/api`: pip, inside a virtual environment.
- Every dependency in both apps is pinned to an exact version. In `/api`,
  requirements files use `==` for every package, including development
  tools.

## Consequences

- Install and gate commands in both apps, CI and the cloud environment's
  setup script use these tools.
- `/web` commits its pnpm lockfile.
- pip has no native lockfile, so reproducibility in `/api` depends on the
  exact pins. A dependency added without an exact version is a review
  finding.
- No monorepo tool is used. Each app is installed and run on its own.