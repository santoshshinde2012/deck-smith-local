# Contributing

## Setup

```bash
# uv (https://docs.astral.sh/uv/) is the supported tool; `make install` runs `uv sync --locked --all-extras`
make install && make seed
.venv/bin/pre-commit install
```

## Workflow

1. Branch from `main`, using `feat/…`, `fix/…` or `docs/…`.
2. Run `make check`. This runs ruff, strict mypy and every offline test, and CI runs the same. Run `make stack-test` as well if you changed an adapter that talks to a service.
3. Write commit messages and PR titles as [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`, `refactor:` or `test:`. Mark a breaking change with `!`. release-please uses them to choose the next SemVer version.
4. Open a pull request. Describe the change and say which E-scenarios it affects.

## Rules

- **Dependency rule.** `domain` imports nothing outside the standard library and pydantic. `application` imports only `domain`, `ports`, LangGraph and sqlglot. Adapters are imported only by `bootstrap.py`, and `tests/architecture` enforces this.
- **No numbers from the LLM.** Numbers reach slides only through facts that `data_fetch` creates. Never loosen the integrity check or the guardrail to make a test pass.
- **No SQL from the LLM.** New questions need a new template in `src/decksmith/sql/templates/`, written in Databricks SQL with typed, patterned parameters.
- **No real data, no secrets.** Use synthetic data only. Never commit `.env` or tokens; detect-private-key runs in pre-commit.
- **Tests without the network.** Use `FakeLLM`, `httpx.MockTransport` or stub clients. Mark tests that need Docker with `@pytest.mark.stack`, and make them skip cleanly when the stack is down.
- **Coverage.** CI fails below 90% branch coverage. A new adapter must join the contract suite of its port in `tests/contract/`.
- **Dependencies.** Change them in `pyproject.toml`, then run `make lock` and commit `uv.lock`. Never edit the lock by hand.
- **Errors.** Raise subclasses of `DeckSmithError` with a unique `code`, and add a row to `docs/errors.md`; a test checks it.
- **Decisions.** Record any new architectural decision as an ADR in `docs/decisions.md`, giving its context, decision and consequences.

You can also open the repo in the devcontainer (`.devcontainer/`), which runs the same setup automatically.

## Releases and repository settings

release-please opens the release PR (version bump and CHANGELOG) when `main` changes. It needs one repository setting, which only a maintainer can switch on:

- **Settings → Actions → General → Workflow permissions:** enable **"Allow GitHub Actions to create and approve pull requests"**. Nothing else needs changing: the workflow's own `permissions:` block grants the `contents` and `pull-requests` write access it needs.

Without it, the `release` workflow fails with "GitHub Actions is not permitted to create or approve pull requests".

The manual `instabox-e2e` workflow also needs the repository secret `INSTABOX_API_KEY` (see [docs/instabox.md](docs/instabox.md)).

Dependabot opens at most one grouped PR per ecosystem per month (`.github/dependabot.yml`). Python 3.14 base images are ignored for now; the reason is in that file and in the CHANGELOG.
