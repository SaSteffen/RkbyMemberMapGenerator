# Implementation Plan: Rider Pairing Suggester

**Branch**: `006-rider-pairing-suggester` | **Date**: 2026-08-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-rider-pairing-suggester/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

A new, independent artifact — `scripts/generate_rider_pairings.py` — reads the latest
season already persisted by the scraper (001) and geocoded by the map generator (002),
and produces one Markdown report under `$RKBY_DATA_DIR/reports/`: a ranked list of
experienced mentor-candidate contacts for every new rider (proximity primary, age-gap
secondary, same-sex tertiary tie-break), plus training clusters of three or more
current-season riders who live close enough together to plausibly train together. All
the real logic — eligibility filtering, cross-season "has ridden before" resolution,
ranking, and geographic clustering — lives in a small, fully unit-tested internal
package, `scripts/rkby_pairing/`, mirroring the `rkby_maps/`/`rkby_report/` precedent
from features 002/005. The script never scrapes and never geocodes (FR-011) — it only
reads `latitude`/`longitude` a prior `generate_member_maps.py` run already cached. The
report embeds full contact info and a photo link per person (FR-009/FR-013, no
privacy-minimization — this is an internal-team artifact) and is auto-committed on
every write (FR-014) so a later regeneration can never silently destroy a hand-edit; a
separate, computation-independent `--pdf-only` mode renders whatever Markdown content
currently exists (hand-edited or not) to PDF (FR-012). See research.md for every
technical decision and data-model.md/contracts/ for the report schema and run contract.

## Technical Context

**Language/Version**: Python 3.11+ (matches `.python-version` / existing
`pyproject.toml`, same as every other script).

**Primary Dependencies**: `markdown` (**new** — pure-Python Markdown-to-HTML
conversion, the first step of FR-012's PDF export, research.md §9); `xhtml2pdf`
(**new** — pure-Python HTML-to-PDF rendering with no system-level libraries, the second
step, research.md §9). `PyYAML`, `jsonschema` (already dependencies, reused via
`scripts/rkby_records.py`, unchanged). No new geocoding library and no new distance
library — great-circle distance is reused as-is from `scripts.rkby_report.geo.
haversine_km` (research.md §2), the same direct-cross-package-import precedent already
established by `rkby_interactive_map/merge.py` importing `scripts.rkby_maps.geocoding.
geocode_record_if_needed`. `scripts.rkby_maps.clustering.find_overlap_groups` gains two
optional, backward-compatible parameters (`distance_fn`, `min_group_size`) so this
feature's training-cluster detection reuses the exact same connected-components
algorithm instead of a second copy (research.md §7) — zero new dependency, one small
generalization of existing tested code. Dev-only: `pytest` (already a dependency); no
new dev dependency.

**Storage**: Local filesystem only. Read-only against every season under
`RKBY_DATA_DIR/seasons/<label>/applicants/*.yaml` — never writes a `.yaml` record, never
triggers a new geocode (FR-011). The one thing this feature writes is
`$RKBY_DATA_DIR/reports/rider_pairings.md` (auto-committed, FR-014) and, on request,
`$RKBY_DATA_DIR/reports/rider_pairings.pdf` (derived, gitignored, never committed —
same treatment as the map PNGs). `reports/` already exists as a shared, gitignored
output folder (created by feature 005's `rkby_report.frame.
ensure_reports_dir_and_gitignore`, reused here directly rather than duplicated,
research.md §8). No database (Constitution IV).

**Testing**: `pytest`, entirely offline, against a new synthetic multi-season fixture
set, `tests/fixtures/pairing_seasons/` — the existing `tests/fixtures/report_seasons/`
fixtures (feature 005) lack addresses and `num_previous_seasons` values this feature
needs and belong to a different feature's test scope, so this feature gets its own
(research.md §12), following the established per-feature-fixture-directory convention.
All eligibility/history/ranking/clustering logic lives in plain, pure functions in
`rkby_pairing/` and gets full red-green coverage; the CLI entrypoint script and the
Markdown/PDF rendering glue stay thin and get lighter, still-real, coverage — the same
proportionality 002 and 005 both already applied to their own orchestration code.

**Target Platform**: Linux/macOS developer machine, run on demand via `uv run` — same
as every other script. Not a server, not scheduled/deployed anywhere.

**Project Type**: One script (Constitution II's "one artifact"), `scripts/
generate_rider_pairings.py`, plus one small internal package private to it, `scripts/
rkby_pairing/` (mirrors `rkby_maps/`/`rkby_report/`'s precedent). One existing shared
module, `scripts/rkby_maps/clustering.py`, gains two optional parameters on one function
(research.md §7); two existing modules, `scripts/rkby_report/geo.py` and `scripts/
rkby_report/frame.py`, are imported from directly (no change to either) rather than
promoted into `scripts/rkby_records.py` — the same cross-package-import precedent
`rkby_interactive_map/merge.py` already established for `rkby_maps.geocoding`, applied
here instead of forcing every shared helper up into one module.

**Performance Goals**: No SC target needed — the whole computation is an O(n²)
pairwise ranking/clustering pass over one season's roster (today: roughly 200
members), entirely in memory, zero network I/O (no geocoding, no scraping, FR-011). A
full run completes in well under a few seconds on a typical laptop; the PDF export step
(pure-Python HTML rendering) is the slower part but still runs in low single-digit
seconds for a report this size.

**Constraints**: Must never trigger a new geocoding lookup or intranet scrape (FR-011)
— strictly local computation over already-cached coordinates. Must never write to any
`seasons/*/applicants/*.yaml` record (read-only, nothing for Principle III to clobber
here). The generated `.md` report and any `.pdf` exported from it MUST stay out of this
git repository (FR-008) — both live only under `$RKBY_DATA_DIR/reports/`. A later
regeneration MUST NOT be the only copy of a hand-edited report: FR-014's auto-commit
into the `RKBY_DATA_DIR` git repo (a no-op there if it isn't one) is what keeps the
prior hand-edited version recoverable. PDF export MUST work from the report's current
on-disk Markdown content, independent of and without re-running the pairing
computation (FR-012), so a hand-edit made after generation is reflected in the PDF.

**Scale/Scope**: Same small scale as 002/005 — roughly 200 member records in the
latest season on file today. Out of scope: the birthday-calendar script from
REQUIREMENTS.md (a separate future feature per Constitution II); any new scraping or
geocoding; cross-referencing detail-map images per pairing (spec.md Assumptions,
explicitly deferred); per-rider or per-cluster output files (spec.md Assumptions: one
combined Markdown file only).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Member Data Privacy First | No new third-party calls of any kind — FR-011 forbids new geocoding or scraping, so this feature is strictly local computation over data the scraper/map-generator already fetched and cached; the geocoding exception (Principle I's own carve-out) simply isn't exercised here at all. FR-009 deliberately includes full contact info (name, address, phone/email) and FR-013 a photo link, per person, in the report — this is the one artifact in the project explicitly scoped as *internal-team-only*, where members already have mutual visibility into each other's contact details (spec.md FR-009 rationale), so the "minimum data necessary" clause that applies to *externally shared* artifacts (interactive map, printed graphics) does not narrow this one; the file itself still stays local and uncommitted (FR-008), which is what Principle I actually requires regardless of an artifact's audience. `ignore: true` and `excluded` members are dropped from every role in the output (new rider, mentor candidate, cluster member) — the same opt-out mechanism every other artifact already honors (FR-010). | PASS |
| II. One Script, One Artifact | New, independent artifact: `scripts/generate_rider_pairings.py`. Its own non-trivial logic lives in a private internal package, `scripts/rkby_pairing/` (mirrors 002's `rkby_maps/` and 005's `rkby_report/` precedent) — not a second artifact, nothing outside this feature imports it. Two pieces of genuinely reusable logic are consumed directly from their existing homes rather than duplicated: `haversine_km` (`rkby_report/geo.py`) and `ensure_reports_dir_and_gitignore` (`rkby_report/frame.py`), both already public functions, imported cross-package exactly as `rkby_interactive_map/merge.py` already imports `rkby_maps.geocoding.geocode_record_if_needed` — an established pattern, not a new one. The one piece of shared logic that needs to *change* (connected-components grouping, needed by both this feature's training clusters and 002's overlap-pin fallback) gets two new optional, backward-compatible parameters on the existing `rkby_maps.clustering.find_overlap_groups` rather than a second copy of the same ~15-line union-find algorithm — the same real-duplication threshold that justified `rkby_records.py`'s own creation (002's research.md §10) and the `canonical_match_keys` promotion (005's research.md §7). | PASS |
| III. Local Data Is the Editable Source of Truth | Read-only with respect to `seasons/*/applicants/*.yaml`: never geocodes, never scrapes, never writes a record (FR-011). Nothing here for a later run to silently clobber. The one thing this feature does overwrite on every run — its own `reports/rider_pairings.md` — is explicitly *not* a manually-corrected source-of-truth record; FR-014's auto-commit is the safeguard that keeps a hand-edited prior version recoverable from git history even though the working copy is fully regenerated (spec.md Edge Cases), the same "derived artifact, reproducible on demand" treatment 002 already gives the map PNGs. | PASS |
| IV. Python, Minimal Dependencies | Two new runtime deps, both pure-Python with no system-level native libraries: `markdown` (the de facto standard Markdown parser) and `xhtml2pdf` (HTML→PDF via `reportlab`, no Cairo/Pango/GTK/wkhtmltopdf/LaTeX install required on the maintainer's machine — research.md §9 rejects `weasyprint` for exactly that system-dependency friction, and rejects shelling out to an external `pandoc` binary because it would be the project's first dependency on a tool outside the Python/uv toolchain and PATH it doesn't already assume). No geo/clustering library added — great-circle distance and connected-components grouping both reuse existing in-house code (research.md §2, §7). | PASS |
| V. Test-First Development (Red-Green) | All the logic that can actually be wrong — eligibility filtering, cross-season "has ridden as a Rider" resolution, ranking order, cluster formation, Markdown rendering, PDF rendering — lives in `rkby_pairing/` as plain functions over a new synthetic fixture set (`tests/fixtures/pairing_seasons/`), fully covered by `pytest`, developed red-green, no real data (Principle V, Principle I). The CLI entrypoint script stays thin and gets lighter, still-real, coverage of arg parsing/config/exit-code behavior — the same split 002 and 005 both already established between their tested internal packages and lightly-tested CLI orchestration. The `find_overlap_groups` generalization is itself developed red-green: existing tests (`tests/unit/test_clustering.py`) must keep passing unchanged (default parameter values preserve current behavior exactly), and new tests cover the added `distance_fn`/`min_group_size` parameters before this feature's cluster code depends on them. | PASS |

**Post-Phase-1 re-check**: data-model.md and contracts/ confirm the design stays
within one script + one internal package + one small backward-compatible parameter
addition to an existing shared function, with no dependency introduced during Phase 1
beyond Phase 0's list (`markdown`, `xhtml2pdf`). All gates above still hold at **PASS**
— no Complexity Tracking entries are needed.

## Project Structure

### Documentation (this feature)

```text
specs/006-rider-pairing-suggester/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── cli-and-env.md         # how to run this script and its two PDF modes
│   └── report-output.md       # the generated Markdown/PDF file's structure contract
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
scripts/
├── rkby_records.py                  # existing — unchanged
├── rkby_report/
│   ├── geo.py                       # existing — haversine_km() imported directly
│   │                                 #   by rkby_pairing/ranking.py (research.md §2)
│   └── frame.py                     # existing — ensure_reports_dir_and_gitignore()
│                                     #   imported directly by generate_rider_pairings.py
├── rkby_maps/
│   └── clustering.py                # existing — find_overlap_groups() gains optional
│                                     #   distance_fn/min_group_size params, default
│                                     #   behavior unchanged (research.md §7)
├── rkby_pairing/                    # NEW — internal package, private to this feature
│   │                                 #   (still one artifact, per Constitution II)
│   ├── __init__.py
│   ├── roles.py                     # recognized-role classification (Rider/Service
│   │                                 #   Crew/Supporter incl. unrecognized/blank
│   │                                 #   handling), reusing rkby_maps.rendering.
│   │                                 #   ROLE_COLORS' key set as the recognized-spelling
│   │                                 #   source of truth (research.md §4)
│   ├── eligibility.py               # new-rider / mentor-candidate pools (FR-002/003/
│   │                                 #   004/010), cross-season "has ridden before"
│   │                                 #   resolution via rkby_records.canonical_match_keys
│   │                                 #   (research.md §3)
│   ├── ranking.py                   # per-new-rider mentor candidate sort (proximity /
│   │                                 #   age-gap / same-sex tie-break, FR-005/006,
│   │                                 #   research.md §5, §6)
│   ├── clusters.py                  # training-cluster detection (FR-007) via the
│   │                                 #   generalized find_overlap_groups (research.md §7)
│   ├── report.py                    # Markdown rendering: pairing lists + clusters +
│   │                                 #   contact info + photo links (FR-009/013,
│   │                                 #   research.md §8)
│   └── pdf.py                       # Markdown -> HTML -> PDF conversion (FR-012,
│                                     #   research.md §9)
└── generate_rider_pairings.py       # NEW — the one artifact: thin CLI orchestration
                                      #   (config, arg parsing, auto-commit, --pdf/
                                      #   --pdf-only modes), imports rkby_pairing

tests/
├── unit/
│   ├── test_rkby_pairing_roles.py        # recognized/unrecognized role classification
│   ├── test_rkby_pairing_eligibility.py  # new-rider/mentor-candidate pools, cross-
│   │                                     #   season history, excluded/ignored/ungeocoded
│   ├── test_rkby_pairing_ranking.py      # proximity/age-gap/sex sort order, max cap
│   ├── test_rkby_pairing_clusters.py     # training-cluster formation, riders-only scope
│   ├── test_rkby_pairing_report.py       # Markdown structure, contact info, photo links
│   ├── test_rkby_pairing_pdf.py          # Markdown -> PDF rendering, hand-edit fidelity
│   ├── test_clustering.py                # existing — extended with distance_fn/
│   │                                     #   min_group_size coverage, existing cases
│   │                                     #   unchanged (research.md §7)
│   └── test_generate_rider_pairings_cli.py  # arg parsing, config, --pdf/--pdf-only,
│                                             #   auto-commit scope
└── fixtures/
    └── pairing_seasons/              # NEW — synthetic multi-season applicant YAML
                                       #   fixtures with known role/history/address/
                                       #   birthday/sex combinations (research.md §12)

data/                                 # NOT used by this feature — real data lives under
                                       # RKBY_DATA_DIR outside this repo (already gitignored)
```

**Structure Decision**: One script, `scripts/generate_rider_pairings.py`, is the
deliverable (Constitution II). Its own logic is split into a small private package,
`scripts/rkby_pairing/`, purely so the error-prone parts (eligibility, cross-season
history, ranking, clustering, rendering) are plain, pure, fully pytest-covered
functions rather than CLI-script code — it is not a second artifact, nothing outside
this feature imports it. Two existing public helpers (`rkby_report.geo.haversine_km`,
`rkby_report.frame.ensure_reports_dir_and_gitignore`) are imported directly rather than
duplicated or promoted, following the cross-package-import precedent
`rkby_interactive_map/merge.py` already set. One existing shared function
(`rkby_maps.clustering.find_overlap_groups`) gains two optional parameters — a
backward-compatible refactor, not a behavior change to its existing callers — because a
second, independent feature now needs the identical connected-components algorithm
(the same real-duplication threshold 002 and 005 both already used to justify their own
promotions). Tests follow the existing `tests/unit` + `tests/fixtures` convention, with
a new feature-scoped fixture directory (`tests/fixtures/pairing_seasons/`) rather than
extending 005's `report_seasons/` fixtures, which lack fields this feature needs and
belong to a different feature's test scope.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — every Constitution Check row above passed without qualification, so
this table is intentionally left empty.
