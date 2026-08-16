# Implementation Plan: Member Map Generator

**Branch**: `002-map-generator` | **Date**: 2026-08-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-map-generator/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

A second, independent CLI script (`scripts/generate_member_maps.py`) reads every
season already persisted by the scraper (001), geocodes each eligible member's address
via Nominatim (caching the result back into their record, once, forever), and renders
two PNG map variants per season — role-colored pins and circular member photos — onto
an in-house-fetched OpenStreetMap raster basemap. It detects marker overlaps at each
map's rendered scale and spawns additional zoomed-in detail maps for crowded areas
(down to a configurable minimum covered width), falling back to a merged/offset
rendering where even that minimum can't fully separate a group. All output lands in one
flat, gitignored `maps/` folder inside the same `RKBY_DATA_DIR` the scraper already
uses. See research.md for every technical decision and data-model.md/contracts/ for the
extended record shape and the CLI/output interfaces.

## Technical Context

**Language/Version**: Python 3.11+ (matches `.python-version` / existing
`pyproject.toml`, same as the scraper).

**Primary Dependencies**: `requests` (already a dependency — reused for both the
Nominatim geocoding call and raw OSM tile fetches, research.md §2–3); `Pillow` (**new**
— tile stitching, circular photo crop, pin/badge/scale-bar/attribution drawing,
research.md §1); `PyYAML`, `jsonschema` (already dependencies — reused via the new
shared `scripts/rkby_records.py` module, research.md §10). No new geocoding or
static-map library is added — Web Mercator projection and tile-fetch/stitch are
implemented in-house (research.md §1) to get the exact pixel-level control this feature
needs. Dev-only: `pytest`, `responses` (already dev dependencies — reused to mock
Nominatim + tile HTTP, research.md §13).

**Storage**: Local filesystem only, under the same `RKBY_DATA_DIR` the scraper uses —
extends 001's `seasons/<label>/applicants/*.yaml` with two new optional fields
(`latitude`, `longitude`, data-model.md), adds a flat `maps/` folder of generated PNGs
(FR-015) and a `.tile_cache/` folder of cached OSM raster tiles (research.md §2), both
gitignored. No database (Constitution IV).

**Testing**: `pytest`, with `responses` intercepting all Nominatim/tile HTTP calls
against synthetic fixtures — no real network calls, no real member data (research.md
§13, Constitution V).

**Target Platform**: Linux/macOS developer machine, run on demand via `uv run`. Not a
server, not scheduled/deployed anywhere — same as the scraper.

**Project Type**: Single CLI script (Constitution II) plus one small shared module
(`scripts/rkby_records.py`, research.md §10) and one internal package
(`scripts/rkby_maps/`) holding this script's own implementation detail (geocoding,
projection/tiles, clustering, rendering) — still one artifact, one entrypoint.

**Performance Goals**: SC-005 — a full run across all of this team's current seasons
(~200 member records total) completes in under 5 minutes on a typical laptop. Dominated
by network I/O (geocoding + tile fetch); mitigated by permanent geocode caching
(FR-019, so steady-state runs geocode ~0 new addresses) and a persistent, unbounded tile
cache shared across maps/runs (research.md §2).

**Constraints**: Nominatim: max 1 request/second, custom identifying User-Agent,
address-text-only payload, cache permanently, never re-request an already-resolved
address (research.md §3). OSM tiles: custom User-Agent, fetch-what-you-render only (no
bulk pre-seeding), on-image attribution required (research.md §2). Geocode-cache writes
must never overwrite a human hand-correction (fill-empty-only, research.md §11,
Constitution III). No CLI switches beyond `--min-width-km` and `--no-scale-bar`
(FR-018).

**Scale/Scope**: ~200 member records across a handful of seasons; up to 2 variants × (1
overview + N detail maps) PNGs per season. Out of scope: the pairing-suggestion and
birthday-calendar scripts mentioned in REQUIREMENTS.md (separate future features per
Constitution II); any interactive/zoomable map format (spec is PNG-only, FR-001).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Member Data Privacy First | Name, photo, phone, and birthday are never transmitted anywhere. Address *text* is sent to Nominatim (a third-party service) to geocode it, under the narrow exception constitution v2.0.0 adds to this NON-NEGOTIABLE principle: address-only payload, geocoded at most once per address ever, cached locally and reused thereafter (research.md §3) — exactly the conditions that exception requires. Generated maps themselves stay local (written under `RKBY_DATA_DIR`, gitignored) — this feature doesn't add any new sharing/upload path for the *maps*, only for the one-time address lookup that makes them possible. Excluded/ignored members are already left off every map (FR-003/FR-004), supporting the opt-out requirement. | **PASS** |
| II. One Script, One Artifact | New, independent script `scripts/generate_member_maps.py`; does not bolt a mode onto `scrape_applicants.py`. The new `scripts/rkby_records.py` shared module and `scripts/rkby_maps/` internal package hold logic either genuinely duplicated across both scripts (season/record I/O, research.md §10 — explicitly permitted once duplication is real, not anticipated) or private to this one script's own implementation (geocoding/projection/clustering/rendering) — neither is a second artifact or a shared framework. | PASS |
| III. Local Data Is the Editable Source of Truth | `latitude`/`longitude` follow the exact fill-empty-only discipline every other optional field already uses (research.md §11) — a hand-correction in the YAML is never overwritten by a later run. Schema stays hand-readable YAML with the same JSON Schema validation gate as before (contracts/applicant-record.schema.json). | PASS |
| IV. Python, Minimal Dependencies | One new runtime dependency, `Pillow` — small, extremely widely-used, does exactly the image compositing this feature needs. Deliberately *not* adding a static-map or geocoding library (research.md §1, §3) to keep the dependency count minimal; Web Mercator math implemented directly instead (well-understood, ~30 lines). No database, no web framework, no cloud SDK. | PASS |
| V. Test-First Development (Red-Green) | All new logic (projection math, overlap/clustering, geocoding, tile fetch/stitch, photo crop, rendering) is unit-testable offline via `pytest` + the existing `responses` dependency, against synthetic fixtures only (research.md §13) — no real data, matching the constraint already proven out by the scraper's test suite. | PASS |

**Resolved 2026-08-16**: the Principle I exception this row relies on was ratified in
constitution v2.0.0 (see `.specify/memory/constitution.md`'s Sync Impact Report and the
`docs: amend constitution to v2.0.0` commit) — the Complexity Tracking entry below is
retained as historical justification for why the exception exists, not an open gate.

**Post-Phase-1 re-check**: data-model.md and contracts/ confirm the design stays within
one script + one shared I/O module + one internal package + one extended schema, with
no new dependency introduced during Phase 1 beyond the `Pillow` already identified in
Phase 0. All gates above hold at **PASS**; the Principle I exception is no longer
conditional — constitution v2.0.0 ratified it (see above).

## Project Structure

### Documentation (this feature)

```text
specs/002-map-generator/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── applicant-record.schema.json   # extended schema snapshot (+ latitude/longitude)
│   ├── cli-and-env.md
│   └── map-output.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
scripts/
├── scrape_applicants.py             # existing (001) — refactored to import shared
│                                     #   season/record I/O from rkby_records instead of
│                                     #   defining it locally (research.md §10)
├── generate_member_maps.py          # NEW — the one script for this feature (Constitution II):
│                                     #   CLI entrypoint, per-season orchestration
├── rkby_records.py                  # NEW — shared module (research.md §10): season_dir/
│                                     #   applicants_dir/photos_dir, discover_seasons,
│                                     #   load/validate/save applicant records,
│                                     #   normalize_name, auto-commit helper
├── rkby_maps/                       # NEW — internal package, private to
│   │                                 #   generate_member_maps.py (still one artifact)
│   ├── __init__.py
│   ├── geocoding.py                 # Nominatim client + cache read/write (research.md §3, §11)
│   ├── basemap.py                   # Web Mercator projection + OSM tile fetch/stitch/cache
│   │                                 #   (research.md §1, §2, §5, §6)
│   ├── clustering.py                # overlap graph / connected components (research.md §4)
│   └── rendering.py                 # pins, photo circles, fallback badges/offsets, scale
│                                     #   bar, attribution, photo circular crop (research.md §6–8)
└── schemas/
    └── applicant_record.schema.json # extended in place: + latitude/longitude (shared with 001)

tests/
├── unit/
│   ├── test_rkby_records.py         # extracted shared module, incl. discover_seasons
│   ├── test_geocoding.py            # Nominatim success/no-match/error, cache reuse, rate limit
│   ├── test_basemap.py              # projection math, meters-per-pixel, zoom-from-width,
│   │                                 #   tile fetch/stitch/cache (mocked HTTP)
│   ├── test_clustering.py           # overlap graph, same-address special case (FR-014),
│   │                                 #   unresolved-at-min-width fallback trigger
│   ├── test_rendering.py            # role-color pins, photo crop, scale bar, attribution,
│   │                                 #   fallback badge/offset rendering — pixel-level asserts
│   └── test_generate_member_maps_cli.py  # arg parsing, defaults, no season/variant switches
└── fixtures/
    ├── nominatim_response_*.json    # mocked geocoder responses (match / no-match)
    ├── osm_tile_fixture.png         # tiny synthetic tile for offline stitch tests
    └── sample_photo.jpg             # small synthetic photo for circular-crop tests

data/                                 # NOT used by this feature — real data lives under
                                       # RKBY_DATA_DIR outside this repo (already gitignored)
```

**Structure Decision**: Single-script layout per Constitution II — the deliverable is
one script, `scripts/generate_member_maps.py`. Its own non-trivial internal logic
(geocoding, projection/tiles, clustering, rendering) is split into a small private
package, `scripts/rkby_maps/`, purely for file-size/testability reasons — it is not a
second artifact or a shared framework, nothing outside this script imports it. The one
piece that *is* shared across scripts, `scripts/rkby_records.py`, holds only logic that
was already duplicated-in-need-not-in-anticipation between the scraper and this feature
(research.md §10) — extracting it also means `scrape_applicants.py` changes as part of
this feature's implementation (a refactor, not a behavior change; its existing test
suite must keep passing unmodified in behavior). Tests follow the existing `tests/unit`
+ `tests/fixtures` convention, split by concern, entirely offline per Constitution V.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Address text sent to a third-party service (Nominatim), in tension with Principle I's unqualified "MUST NOT be uploaded to third-party cloud services, analytics platforms, or public repositories" | The feature's entire purpose — plotting members on a map — is impossible without converting a street address into geographic coordinates. There is no way to deliver Story 1/2/3 without some form of geocoding. | **Bundling an offline/local geocoding database**: rejected — a country/region-scale offline geocoder is a heavy dependency (large data file, non-trivial matching logic) wildly out of proportion to Constitution IV's "smallest footprint" goal and to a project serving ~200 addresses total. **Asking each member to supply lat/lon manually instead of an address**: rejected — contradicts the existing scraped `address` field members already have on file, and pushes real manual effort onto every team member for no benefit over a single, narrowly-scoped, one-time-per-address automated lookup. **Mitigation actually applied** (research.md §3): only `address` text is ever sent, never name/photo/phone/birthday; each address is geocoded at most once, ever, then cached locally forever (FR-019/SC-007) — no third party accumulates an ongoing feed of member data, only a one-time, address-only, self-hosted-adjacent (OSMF's own community geocoder, not a commercial data broker) lookup. **Status**: ratified in constitution v2.0.0 (2026-08-16) — Principle I's text now explicitly permits this narrow exception under the stated conditions (see `.specify/memory/constitution.md`); this table is retained as historical justification for why the exception exists, not an open gate. |
