# RkbyMemberMapGenerator

Local tooling for **Team Rynkeby Hamburg** — a charity cycling team whose members are
spread across a wide area around Hamburg, Germany. This project turns member data
scraped from the Team Rynkeby Intranet into things that help the team connect:

- **Member maps** — visualize where everyone lives, so people can spot neighbors and
  potential training partners.
- **Rider pairings** — suggest experienced/inexperienced rider pairs based on location
  and number of seasons ridden.
- **Birthday calendar** — an importable `.ics` file with everyone's birthdays.

See [REQUIREMENTS.md](REQUIREMENTS.md) for the full background and
[.specify/memory/constitution.md](.specify/memory/constitution.md) for the project's
governing principles (privacy, data handling, script structure).

> **Status:** early scaffolding. Project tooling (uv, pyproject.toml) is set up; the
> individual scripts described below are not implemented yet.

## Privacy first

Member data (name, address, phone number, photo, birthday) is real personal data
scraped from a members-only intranet. It is **never committed to this repository**.
It lives only in a local, gitignored `data/` directory that you create yourself, and
any credentials used to scrape the intranet belong in a gitignored `.env` file — never
in source. See constitution Principle I for the full rules.

## Project structure

```
.
├── pyproject.toml   # uv-managed project config
├── data/            # local, gitignored member data store (created locally, not in git)
├── scripts/         # one independent script per artifact (planned; see constitution
│                     # Principle II — no shared multi-purpose CLI)
├── REQUIREMENTS.md  # original feature idea and technical background
└── .specify/        # Spec Kit workflow: constitution, specs, plans, tasks
```

Each target artifact (scraper, map generator, pairing suggester, birthday calendar
builder) is its own standalone script under `scripts/`, runnable independently.

## Getting started

This project uses [uv](https://docs.astral.sh/uv/) for Python dependency and
environment management.

```bash
# Install dependencies (creates .venv/ automatically)
uv sync

# One-time: install git hooks (lint/format on commit, Conventional Commits
# on commit message) — see "Git hooks" below
uv run pre-commit install --install-hooks

# Run a script once it exists, e.g.:
uv run scripts/generate_map.py

# Lint / format
uv run ruff check .
uv run ruff format .

# Run tests
uv run pytest
```

Requires Python 3.11+ (pinned via `.python-version`; uv will fetch a matching
interpreter automatically if you don't have one).

## Git hooks

This repo uses [pre-commit](https://pre-commit.com/) to enforce code quality and commit
message style. Git doesn't run anything automatically on clone, so after `uv sync` run:

```bash
uv run pre-commit install --install-hooks
```

This wires up two hooks (config in [.pre-commit-config.yaml](.pre-commit-config.yaml)):

- **pre-commit**: runs `ruff check --fix` then `ruff format` on staged files.
  Formatting is applied automatically; if lint finds issues it can't fix, the
  commit is blocked until you fix them by hand.
- **commit-msg**: rejects commit messages that don't follow
  [Conventional Commits](https://www.conventionalcommits.org/) (e.g.
  `feat: add map export`, `fix: correct geocoding fallback`).

Run `uv run pre-commit run --all-files` to check the whole repo on demand.

## License

Public domain — see [LICENSE](LICENSE) (Unlicense).
