# Implementation Plan: Member Analytics Report

**Branch**: `005-member-analytics-report` | **Date**: 2026-08-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-member-analytics-report/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

A new, independent artifact — `scripts/report_member_analytics.ipynb` — reads every
season already persisted by the scraper (001) and enriched by the map generator (002),
builds one pandas DataFrame with a row per (member, season) carrying that member's
role, gender, age-at-that-season, and distance from a fixed Hamburg city-center
reference point, and renders season snapshots, season-to-season trends, and
season-over-season retention (overall and split by gender/age/distance) from it. All
the real logic — eligibility filtering, age/distance computation, cross-season
identity resolution, and aggregation — lives in a small, fully unit-tested internal
package, `scripts/rkby_report/`; the notebook itself stays a thin, easy-to-run,
easy-to-export orchestration shell over that package. The report never geocodes and
never writes to any season record — it only reads coordinates the map generator
already cached. See research.md for every technical decision and
data-model.md/contracts/ for the DataFrame schema and run/export contract.

## Technical Context

**Language/Version**: Python 3.11+ (matches `.python-version` / existing
`pyproject.toml`, same as every other script).

**Primary Dependencies**: `pandas` (**new** — the per-member-per-season DataFrame the
spec explicitly asks for); `matplotlib` (**new** — every chart; no charting
alternative is smaller or as widely used, research.md §3); `jupyterlab` + `ipykernel`
(**new** — the notebook medium itself); `nbconvert` (**new** — the export step,
FR-014/SC-005). `PyYAML`, `jsonschema` (already dependencies — reused via the existing
`scripts/rkby_records.py`, extended with one promoted function, research.md §7). No new
geocoding or distance library — great-circle distance is computed in-house
(research.md §5), mirroring 002's precedent of implementing Web Mercator math in-house
rather than adding a geo dependency. Dev-only: `pytest` (already a dependency);
`nbstripout` (**new**, dev-only — a pre-commit hook that strips notebook cell outputs
before every commit, research.md §4).

**Storage**: Local filesystem only, read-only against the same `RKBY_DATA_DIR` every
other script uses — reads `seasons/<label>/applicants/*.yaml` (never writes them; no
new geocoding, FR-007). The one thing this feature ever writes is the optional
exported report file, to a new `reports/` sibling of `seasons/`/`maps/` inside
`RKBY_DATA_DIR` (gitignored like those, research.md §4). No database (Constitution IV).

**Testing**: `pytest`, entirely offline, against synthetic multi-season YAML fixtures
under `tests/fixtures/report_seasons/` — no real member data (Constitution V). All
eligibility/age/distance/retention/aggregation logic lives in plain, pure functions in
`rkby_report/` and gets full red-green coverage; the notebook and the chart-builder
functions in `rkby_report/plots.py` stay thin and get lighter smoke-level coverage only
(research.md §2), the same proportionality 002 applied to its CLI's orchestration code.

**Target Platform**: Linux/macOS developer machine, run on demand via `uv run` — same
as every other script. Not a server, not scheduled/deployed anywhere.

**Project Type**: One notebook (Constitution II's "one artifact") plus one small
internal package, `scripts/rkby_report/`, private to it (mirrors 002's `rkby_maps/`
precedent) — still one artifact, one entrypoint. One existing shared module,
`scripts/rkby_records.py`, gains one promoted function (research.md §7); no new shared
module is created.

**Performance Goals**: No SC target needed — the whole computation is in-memory pandas
over a few hundred rows total (a handful of seasons × ~200 members), with zero network
I/O (no geocoding, FR-007). A full run completes in well under a minute on a typical
laptop.

**Constraints**: Must never trigger a new geocoding lookup (FR-007) or write to any
`seasons/*/applicants/*.yaml` record (read-only, Principle III has nothing to clobber
here). The committed notebook source MUST never carry executed cell outputs —
enforced by a new `nbstripout` pre-commit hook, not just convention (research.md §4).
The exported/shareable report MUST land outside the git repo (`$RKBY_DATA_DIR/reports/`)
and MUST show aggregates only, never a per-member roster (FR-015).

**Scale/Scope**: Same small scale as 002 — roughly 200 member records per season
across a handful of seasons on file today. Out of scope: the rider-pairing-suggestion
and birthday-calendar scripts from REQUIREMENTS.md (separate future features per
Constitution II); any new geocoding; any dashboard/web-server delivery — this is a
local, run-on-demand notebook, not a hosted report.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Member Data Privacy First | No new third-party calls at all — FR-007 forbids new geocoding, so this feature is strictly local pandas computation over coordinates the map generator already cached. The committed source, `report_member_analytics.ipynb`, never carries real numbers: a new `nbstripout` pre-commit hook strips every cell's output before it can be committed, so no chart or count derived from a real season can land in git history even by accident (research.md §4). The one artifact that does carry real numbers — an executed/exported report — is written only to `$RKBY_DATA_DIR/reports/` (outside the repo, alongside `maps/`/`interactive_map/`), never committed, and (FR-015) shows aggregated counts/rates/distributions only, never a per-member roster. Excluded/ignored members are left out of every count (FR-002), the same opt-out support every other artifact already gives. | PASS |
| II. One Script, One Artifact | New, independent artifact: `scripts/report_member_analytics.ipynb`. Its own non-trivial logic lives in a private internal package, `scripts/rkby_report/` (mirrors `rkby_maps/`'s precedent from 002) — not a second artifact, nothing outside this feature imports it. The one piece of genuinely shared logic — cross-season identity resolution — is promoted from its current private home (`rkby_interactive_map/merge.py`'s `_canonical_match_keys`) into the existing shared module `rkby_records.py`, because two independent features now need the exact same logic: the same real-duplication threshold that justified creating `rkby_records.py` in the first place (002's research.md §10). | PASS |
| III. Local Data Is the Editable Source of Truth | Read-only with respect to `seasons/*/applicants/*.yaml`: never geocodes (FR-007), never writes a record. There is nothing here for a later run to silently clobber. | PASS |
| IV. Python, Minimal Dependencies | New runtime deps: `pandas` (explicitly requested — "build a data frame first"), `matplotlib` (visualization; no smaller/more standard alternative), `jupyterlab`+`ipykernel`+`nbconvert` (the notebook medium and export path the request specifically asked for). New dev-only dep: `nbstripout`, a single-purpose pre-commit hook. Deliberately not adding a geo/distance library (rejected `geopy`, research.md §5) or a charting-convenience library (rejected `seaborn`/`plotly`, research.md §3) — great-circle distance is ~10 lines implemented in-house, matplotlib alone covers every chart this feature needs. | PASS |
| V. Test-First Development (Red-Green) | All the logic that can actually be wrong — eligibility filtering, age-at-season, distance, cross-season retention matching, aggregation — lives in `rkby_report/` as plain functions over synthetic fixtures (`tests/fixtures/report_seasons/`), fully covered by `pytest`, developed red-green, no real data. The notebook and `rkby_report/plots.py`'s chart builders stay thin and get lighter smoke-level coverage only (research.md §2) — proportional to their risk, and the same split 002 already established between its tested `rkby_maps/` package and its lightly-tested CLI orchestration. | PASS |

**Post-Phase-1 re-check**: data-model.md and contracts/ confirm the design stays
within one notebook + one internal package + one promoted shared-module function, with
no dependency introduced during Phase 1 beyond Phase 0's list. All gates above still
hold at **PASS** — no Complexity Tracking entries are needed.

## Project Structure

### Documentation (this feature)

```text
specs/005-member-analytics-report/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── member-season-frame.md   # the DataFrame's column contract
│   └── cli-and-env.md           # how to run, launch, and export the notebook
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
scripts/
├── rkby_records.py                  # existing — gains canonical_match_keys(), promoted
│                                     #   from rkby_interactive_map/merge.py (research.md §7)
├── rkby_interactive_map/
│   └── merge.py                     # existing — its private _canonical_match_keys is
│                                     #   replaced with an import of the shared
│                                     #   rkby_records.canonical_match_keys (no behavior change)
├── rkby_report/                     # NEW — internal package, private to this feature
│   │                                 #   (still one artifact, per Constitution II)
│   ├── __init__.py
│   ├── geo.py                       # HAMBURG_CENTER constant + haversine_km() (research.md §5)
│   ├── frame.py                     # build_member_season_frame(data_dir) -> pandas.DataFrame
│   │                                 #   (research.md §6, §7, §8)
│   ├── buckets.py                   # age-bracket / distance-bracket boundary constants
│   │                                 #   (research.md §9)
│   ├── aggregate.py                 # season summaries, season-to-season trend tables,
│   │                                 #   retention rate + gender/age/distance splits
│   └── plots.py                     # thin matplotlib chart builders, one per view in spec.md
└── report_member_analytics.ipynb    # NEW — the one artifact for this feature: thin
                                      #   orchestration cells only, imports rkby_report

tests/
├── unit/
│   ├── test_rkby_records_canonical_match_keys.py  # coverage for the promoted shared
│   │                                 #   function (moved/extended from merge.py's tests)
│   ├── test_rkby_report_frame.py     # eligibility filter, age-at-season, distance,
│   │                                 #   retained_next_season, alias resolution
│   ├── test_rkby_report_aggregate.py # season summaries, trend tables, retention + splits
│   └── test_rkby_report_plots.py     # smoke tests: each chart builder runs without
│                                     #   error against synthetic aggregated data
└── fixtures/
    └── report_seasons/               # synthetic multi-season applicant YAML fixtures with
                                       #   known role/sex/birthday/lat-lon/retention outcomes

data/                                 # NOT used by this feature — real data lives under
                                       # RKBY_DATA_DIR outside this repo (already gitignored)
```

**Structure Decision**: One notebook, `scripts/report_member_analytics.ipynb`, is the
deliverable (Constitution II). Its own logic is split into a small private package,
`scripts/rkby_report/`, purely so the error-prone parts (identity resolution, age/
distance math, retention aggregation) are plain, pure, fully pytest-covered functions
rather than notebook cells — it is not a second artifact, nothing outside this feature
imports it. The one piece that genuinely is shared, cross-season `match_key`/
`alias_match_keys` resolution, moves from its current private home in
`rkby_interactive_map/merge.py` into the existing shared `rkby_records.py` module,
because a second independent feature now needs the identical logic (the same
real-duplication threshold 002 already used to justify `rkby_records.py`'s
existence). That move is a refactor, not a behavior change — `merge.py`'s existing
tests must keep passing unmodified in behavior, just re-pointed at the shared
function. Tests follow the existing `tests/unit` + `tests/fixtures` convention.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — every Constitution Check row above passed without qualification, so
this table is intentionally left empty.
