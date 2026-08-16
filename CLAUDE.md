# CLAUDE.md

Project-specific guidance for Claude Code in this repo. Read
[.specify/memory/constitution.md](.specify/memory/constitution.md) first — it is the
source of truth for project principles (privacy, script structure, data handling) and
overrides anything below if they conflict. [REQUIREMENTS.md](REQUIREMENTS.md) has the
original feature background.

## Commands

```bash
uv sync                              # install deps into .venv/
uv run pre-commit install --install-hooks  # one-time: enable git hooks
uv run scripts/<name>.py             # run a script
uv run ruff check .                  # lint
uv run ruff format .                 # format
uv run pytest                        # test
```

Commits go through git hooks (`.pre-commit-config.yaml`): ruff lint/format run on
every commit, and commit messages must follow
[Conventional Commits](https://www.conventionalcommits.org/) (`feat: ...`, `fix: ...`,
`chore: ...`, etc.).

## Non-negotiables

- Never read, write, print, or commit anything from `data/` or `.env` — that's real
  member personal data and intranet credentials (constitution Principle I). Both are
  gitignored; keep them that way.
- New use case → new script under `scripts/`, not a new flag/mode on an existing one
  (constitution Principle II). Don't build a shared CLI or framework.
- Scraped intranet data is a starting point; local, human-edited data always wins.
  Merges must never silently clobber manual corrections (constitution Principle III).
- `.specify/scripts/` and `.specify/templates/` are vendored Spec Kit files, not
  project code — don't lint, refactor, or "clean up" them.
