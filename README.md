# RkbyMemberMapGenerator

Local tooling for **Team Rynkeby Hamburg** — a charity cycling team whose members are
spread across a wide area around Hamburg, Germany. This project turns member data
scraped from the Team Rynkeby Intranet into things that help the team connect:

- **Member maps** — visualize where everyone lives, so people can spot neighbors and
  potential training partners.
- **Rider pairings** — suggest experienced/inexperienced rider pairs based on location
  and number of seasons ridden.
- **Birthday calendar** — an importable `.ics` file with everyone's birthdays.
- **Season stats report** — aggregate stats across all scraped seasons: median age,
  male/female split, and member turnover (who left, who's new — accounting for people
  who skip a season and return) broken down by role.

See [REQUIREMENTS.md](REQUIREMENTS.md) for the full background and
[.specify/memory/constitution.md](.specify/memory/constitution.md) for the project's
governing principles (privacy, data handling, script structure).

> **Status:** `scripts/scrape_applicants.py` (applicant scraper & data persistence) and
> `scripts/generate_member_maps.py` (member map generator) are implemented. The
> rider-pairing suggester, birthday calendar, and season stats report are not built
> yet.

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
├── pyproject.toml            # uv-managed project config
├── scripts/
│   ├── scrape_applicants.py     # applicant scraper & data persistence (implemented)
│   ├── generate_member_maps.py  # member map generator (implemented)
│   ├── rkby_records.py          # shared season/record I/O (used by both scripts above)
│   ├── rkby_maps/                # map-generator internals: basemap, rendering, geocoding, clustering
│   └── schemas/                  # JSON Schema for the persisted YAML record format
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

## Running the map generator

`scripts/generate_member_maps.py` reads every season already scraped into
`$RKBY_DATA_DIR`, geocodes each member's address (once ever, cached back into their
YAML record), and renders a role-colored pin map and a circular-photo map per season —
plus zoomed-in detail maps for any crowded cluster of markers. See
[specs/002-map-generator/](specs/002-map-generator/) for the full design.

Only `RKBY_DATA_DIR` is required (no intranet credentials):

```bash
uv run scripts/generate_member_maps.py                       # every season, defaults
uv run scripts/generate_member_maps.py --min-width-km 100     # wider minimum map width
uv run scripts/generate_member_maps.py --no-scale-bar          # suppress the scale bar
```

Generated PNGs land in `$RKBY_DATA_DIR/maps/`, split into `pins/`/`photos/` variant
subfolders (see
[specs/002-map-generator/contracts/map-output.md](specs/002-map-generator/contracts/map-output.md)
for the filename grammar); OSM tiles are cached in `$RKBY_DATA_DIR/.tile_cache/`. Both
folders are gitignored inside the data directory. Every run is idempotent — stale maps
from a since-changed member set are deleted and regenerated, not left behind.

## Getting started

This project uses [uv](https://docs.astral.sh/uv/) for Python dependency and
environment management, and — for `scripts/generate_interactive_map.py`, which
builds its frontend on every run (see
[specs/003-interactive-photo-map/](specs/003-interactive-photo-map/)) — Node.js
(via [nvm](https://github.com/nvm-sh/nvm), version pinned in
[.nvmrc](.nvmrc)) and [pnpm](https://pnpm.io/) (via Node's bundled
[Corepack](https://nodejs.org/api/corepack.html)). Every other script is
Python-only and doesn't need Node at all.

Run the setup script to install/verify both toolchains in one go:

```bash
./setup.sh
```

It installs `uv` and `nvm` if they're missing, runs `uv sync`, installs the
Node version pinned in `.nvmrc` and activates `pnpm` via Corepack, and installs
the git hooks (see "Git hooks" below). Safe to re-run any time.

Equivalent manual steps, if you'd rather not run the script (or need to debug
one piece of it):

```bash
# Python deps (creates .venv/ automatically)
uv sync

# One-time: install git hooks (lint/format on commit, Conventional Commits
# on commit message) — see "Git hooks" below
uv run pre-commit install --install-hooks

# Node, pinned to the version in .nvmrc (only needed for the interactive map)
nvm install
nvm use
corepack enable
corepack prepare pnpm@latest --activate

# Run a script, e.g.:
uv run scripts/scrape_applicants.py
uv run scripts/generate_member_maps.py

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
