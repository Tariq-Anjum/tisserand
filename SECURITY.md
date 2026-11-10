# Security policy

## What counts as a vulnerability here

Skills are instructions that an agent may follow with your permissions. Treat them like scripts. Please report:

- a skill or script that can lead an agent to run commands, delete or overwrite files, reach the network or read secrets beyond what its stated task needs;
- install or doctor scripts that write outside their documented target, follow links unsafely, or cannot be cleanly reversed;
- toolkit (`skillkit`) bugs that let a check report a pass it did not establish, or let a provenance gap appear as complete;
- any secret, private path or personal data in the repository or its history.

Model behaviour on its own (an agent ignoring a skill) is not a vulnerability in this project, but a skill that *invites* unsafe behaviour is.

## How to report

Use GitHub private vulnerability reporting on this repository ("Report a vulnerability" under the Security tab). Do not open a public issue. Include the file, the steps to reproduce and the impact you expect.

We aim to acknowledge reports within 7 days. This is a volunteer, experimental project: there is no bug bounty and no service-level promise.

## Supported versions

Only the latest commit on the default branch is supported.

## Safe use

- Read a skill before installing it.
- Keep your agent's permissions narrow (no blanket shell or network access).
- The `activation`, `risk` and `access` fields are advice; nothing enforces them.
