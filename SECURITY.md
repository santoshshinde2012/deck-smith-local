# Security policy

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Report them privately through [GitHub private vulnerability reporting](https://github.com/santoshshinde2012/deck-smith-local/security/advisories/new).

Include what you found, how to reproduce it, and the impact you expect. You should get an acknowledgement within a few working days.

## Scope and expectations

- This is a local reference implementation. The per-user views only emulate row-level security and are **not** a security boundary.
- The test tokens (`alice-token`, `bob-token`, `carol-token`) and the default passwords in `.env.example` and `docker-compose.yml` are for local use only. Never expose the stack to a network you do not control.
- Never commit real credentials. CI and pre-commit run secret checks, and GitHub secret scanning with push protection is enabled.

## Supported versions

Only the latest commit on `main` is supported.
