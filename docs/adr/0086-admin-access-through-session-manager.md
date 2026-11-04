# 0086. Admin access through Session Manager

- Status: Accepted
- Date: 2026-11-04

## Context

[ADR 0079](0079-production-behind-vercel-with-origin-secret.md) opened port 22
only to the owner's IP. The owner's public IP changes, so the rule broke
deploys. Opening port 22 to everyone is not acceptable. Raised in #466.

## Decision

- Admin access to the production machine, and `scripts/deploy.sh`, go through
  AWS Systems Manager Session Manager, with SSH tunneled inside it (the
  `AWS-StartSSHSession` document). No inbound port is open for
  administration. The only inbound rule is port 80 (TCP), open to everyone and
  protected by the origin secret.
- Access needs both the operator's AWS sign-in and the SSH key.
- `scripts/deploy.sh` is unchanged: it calls `ssh` with the alias in
  `DEPLOY_SSH_HOST`, and the alias runs inside the tunnel.
- This ADR replaces
  [ADR 0079](0079-production-behind-vercel-with-origin-secret.md) for the
  port 22 rule only. [ADR 0016](0016-production-hosting.md) still holds for the
  rest of the hosting.

## Consequences

- The operator runs `aws login` before a deploy. The session lasts up to 12
  hours and no long-term access key is stored.
- The machine needs an instance IAM role with only the managed policy
  `AmazonSSMManagedInstanceCore` and a running SSM Agent.
- The operator's machine needs the AWS CLI v2 and the Session Manager plugin.
- Rejected: port 22 limited to the owner's IP (breaks when the IP changes),
  port 22 open to everyone (exposed), EC2 Instance Connect (still needs an
  inbound port or an endpoint).
- Steps in [`deploy.md`](../deploy.md).
