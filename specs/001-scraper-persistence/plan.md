# Implementation Plan: Applicant Scraper & Data Persistence

**Branch**: `001-scraper-persistence` | **Date**: 2026-08-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-scraper-persistence/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

A single CLI script scrapes the Team Rynkeby intranet's applicant list for one season
(paginated, session-authenticated via env-var credentials), keeps only non-"no"
applicants, and merges them into a local, git-backed, human-hand-editable data store:
one YAML file per applicant plus one photo file, under a per-season folder. The merge
is strictly additive/fill-empty-only so manual corrections and manually-flagged
"ignore" records are never touched or recreated by a later run; a status flip to "no"
marks a record excluded (with a timestamp) rather than deleting it. A whole season's
newly-fetched page data is applied atomically (all-or-nothing) so a mid-run failure
never partially updates or corrupts the persisted store. When `RKBY_DATA_DIR` is
detected to be a git repository, a successful run also auto-commits the season folder
it just changed, giving the maintainer per-run history without a manual `git commit`
step. See research.md for the resolution of every technical unknown and
data-model.md/contracts/ for the persisted shape and CLI/env-var interface.

## Technical Context

**Language/Version**: Python 3.11+ (matches `.python-version` / existing `pyproject.toml`)

**Primary Dependencies**: `requests` (HTTP + session/cookie auth), `beautifulsoup4`
(HTML parsing of the applicant table and photo-popup links, stdlib `html.parser`
backend — no `lxml`), `PyYAML` (persisted record format), `jsonschema` (schema
validation of persisted records). Dev-only: `pytest`, `responses` (HTTP mocking for
tests, no real network calls per FR-021). All resolved in research.md §1–3, §7, §12.

**Storage**: Local filesystem only — one YAML file per applicant record + one photo
file per applicant, under `<RKBY_DATA_DIR>/seasons/<season-label>/...` (typically a
separate, already-existing git repository outside this source repo). No database
(research.md §6; Constitution IV). If `RKBY_DATA_DIR` is detected as a git work tree,
a successful run auto-commits the season subtree it changed by shelling out to the
`git` CLI via `subprocess` — no new runtime dependency (research.md §14).

**Testing**: `pytest`, with `responses` intercepting all `requests` calls against
obfuscated fixtures in `tests/fixtures/` — no real network calls (research.md §12,
FR-021).

**Target Platform**: Linux/macOS developer machine, run on demand via `uv run`. Not a
server, not scheduled/deployed anywhere.

**Project Type**: Single CLI script (Constitution II: one script per artifact).

**Performance Goals**: Not performance-sensitive — a single maintainer runs this
occasionally against one season's applicant list (tens to low hundreds of people).
No specific throughput/latency target.

**Constraints**: No credential or personal member data may ever be written into this
source repository or its git history (Constitution I; FR-002, FR-007, SC-007). Must be
safe to run repeatedly with zero side effects on unchanged data (FR-008, SC-002). Must
never partially write a season's data (FR-018, SC-005).

**Scale/Scope**: One script, one persisted-record schema, one season folder layout.
Out of scope: the map/pairing/birthday-calendar scripts that will later consume this
data (separate future features per Constitution II).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Member Data Privacy First | All persisted data and photos live under `RKBY_DATA_DIR` (env var), never under the source repo; credentials are env-var-only (FR-002, FR-007); `data/` and `.env`/`*.env` are already gitignored at repo root. Test fixtures are obfuscated/synthetic, never real scraped data (FR-021). Auto-commit (research.md §14) only ever commits *within* that same already-local, never-pushed `RKBY_DATA_DIR` repo — it does not change where data lives or who can reach it. | PASS |
| II. One Script, One Artifact | This feature is exactly one script, `scripts/scrape_applicants.py`; it does not bolt onto or add a mode to any existing script (there are none yet). Auto-commit is one more responsibility of that same script's single run, not a second script. | PASS |
| III. Local Data Is the Editable Source of Truth | Persisted format is hand-editable YAML with a JSON Schema for validation/editor assistance (FR-019); merge logic is fill-empty-only and never overwrites a field or file a human (or a prior run) already set (FR-009, FR-011); format stays inspectable without special tooling (a text editor is sufficient). Auto-commit only fires after those same guarantees already hold for the run's writes, so it can only ever commit valid, non-destructive changes, and is trivially reversible via `git revert` if a maintainer disagrees with one. | PASS |
| IV. Python, Minimal Dependencies | 4 runtime deps (`requests`, `beautifulsoup4`, `PyYAML`, `jsonschema`), all well-maintained/widely-used/small-footprint, each justified in research.md; no database, no web framework, no cloud SDK. Auto-commit shells out to the `git` CLI via stdlib `subprocess` — no new dependency added. | PASS |

No violations to justify — Complexity Tracking is not needed.

**Post-Phase-1 re-check**: data-model.md and contracts/ confirm the design stays within
a single script + one schema + local filesystem storage, with no new dependency or
structural need introduced during Phase 1. Gates above still PASS unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/001-scraper-persistence/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── applicant-record.schema.json
│   └── cli-and-env.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
scripts/
├── scrape_applicants.py             # the one script for this feature (Constitution II)
└── schemas/
    └── applicant_record.schema.json # runtime copy of contracts/applicant-record.schema.json

tests/
├── unit/
│   ├── test_season.py               # default-season computation, label parsing (FR-022)
│   ├── test_config.py                # missing/invalid env vars fail before I/O (FR-023)
│   ├── test_parsing.py               # applicant-row + photo-popup HTML parsing
│   ├── test_records.py               # match-key normalization, within-scrape dedup/conflict (FR-013, FR-014)
│   ├── test_store_merge.py           # overwrite-protection, ignore handling, status-flip exclusion (FR-009, FR-011, FR-015)
│   ├── test_rollback.py              # all-or-nothing rollback on mid-pagination failure (FR-018)
│   ├── test_schema_validation.py     # schema-invalid existing record refuses to be written over (FR-017)
│   ├── test_photo_fetch.py           # per-applicant photo failure isolation/retry (FR-005)
│   └── test_auto_commit.py           # git-detected commit, skip-when-clean, non-git dir, commit-failure warning (research.md §14)
└── fixtures/
    ├── login_page.html               # obfuscated
    ├── applicants_page_1.html        # obfuscated
    ├── applicants_page_2.html        # obfuscated
    └── photo_popup.html              # obfuscated

data/                                 # NOT used by this feature — real data lives under
                                       # RKBY_DATA_DIR outside this repo (already gitignored)
```

**Structure Decision**: Single-script layout per Constitution II — the entire feature
is `scripts/scrape_applicants.py` plus a small `scripts/schemas/` data asset (not
another script). This matches the project's documented `uv run scripts/<name>.py`
convention (root CLAUDE.md) and README's "one independent script per artifact"
structure; no `src/` layer, no shared framework, no other script touched. Tests live
under the existing `tests/` convention (`uv run pytest`), split by concern per the FR
each covers, all driven off the fixtures in `tests/fixtures/` per research.md §12 —
never against the real intranet or real member data.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — the Constitution Check gates above all pass with no exceptions needed.
This section is intentionally empty.
