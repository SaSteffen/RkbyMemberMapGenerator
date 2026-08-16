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

> **Status:** `scripts/scrape_applicants.py` (applicant scraper & data persistence) is
> implemented. The map generator, rider-pairing suggester, and birthday calendar are
> not built yet.

## Privacy first

Member data (name, address, phone number, photo, birthday) is real personal data
scraped from a members-only intranet. It is **never committed to this repository**.
It lives only in a local, git-backed directory *outside* this repository, at a path
you set via the `RKBY_DATA_DIR` environment variable — see "Running the scraper"
below. Any credentials used to scrape the intranet belong in a gitignored `.env` file
— never in source. See constitution Principle I for the full rules.

## Project structure

```
.
├── pyproject.toml           # uv-managed project config
├── scripts/
│   ├── scrape_applicants.py # applicant scraper & data persistence (implemented)
│   └── schemas/              # JSON Schema for the persisted YAML record format
├── tests/                    # pytest unit tests, obfuscated fixtures (no real data)
├── REQUIREMENTS.md          # original feature idea and technical background
└── .specify/                 # Spec Kit workflow: constitution, specs, plans, tasks
```

Each target artifact (scraper, map generator, pairing suggester, birthday calendar
builder) is its own standalone script under `scripts/`, runnable independently
(constitution Principle II — no shared multi-purpose CLI).

## Running the scraper

`scripts/scrape_applicants.py` logs into the Team Rynkeby intranet, fetches one
season's applicant list, and merges the result into a local, human-editable YAML
store — safe to re-run repeatedly without losing manual corrections. See
[specs/001-scraper-persistence/](specs/001-scraper-persistence/) for the full design.

Required environment variables (put them in a gitignored `.env`, see
[.env.example](.env.example)):

| Variable | Contains |
|---|---|
| `RKBY_INTRANET_USERNAME` | Intranet login username |
| `RKBY_INTRANET_PASSWORD` | Intranet login password |
| `RKBY_DATA_DIR` | Absolute path to a local, git-backed data repository (created by you, outside this repo) |

```bash
uv run scripts/scrape_applicants.py                # scrape the default (current) season
uv run scripts/scrape_applicants.py --season 2025-26  # or --season 2025/26
```

Persisted records live under `$RKBY_DATA_DIR/seasons/<season-label>/applicants/*.yaml`,
one file per applicant, each validated against
`scripts/schemas/applicant_record.schema.json`. Mark a record `ignore: true` by hand to
permanently exclude it from future runs and downstream scripts.

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
