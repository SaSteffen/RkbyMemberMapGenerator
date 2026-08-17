# Implementation Plan: Interactive Photo Map

**Branch**: `003-interactive-photo-map` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-interactive-photo-map/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

A new, independent script (`scripts/generate_interactive_map.py`) merges every
season's eligible member records by `match_key` (latest eligible record wins for
photo/name/position; every eligible season-record still contributes its own role
entry), reuses `generate_member_maps.py`'s existing geocoding cache and OSM
tile-fetch/stitch pipeline to render one flattened basemap image covering everyone,
and bundles it all — plus each member's own photo — into one self-contained,
shareable folder under `<RKBY_DATA_DIR>/interactive_map/`. The folder's `index.html`
is a small pre-built Vite + Leaflet single-page app (source in
`frontend/interactive-map/`, built ahead of time and committed like any other
vendored asset) that reads a per-run-generated `map-data.js` to render pan/zoomable
circular photo markers with hover popups and live season toggling — no server, no
network, no install step required to view it. See research.md for why a real OSM
tile *layer* isn't viable here (offline redistribution is against OSM's tile usage
policy) and for every other technical decision; data-model.md/contracts/ for the
extended data shapes and interfaces.

## Technical Context

**Language/Version**: Python 3.11+ for the generation script (matches the existing
scripts). Frontend: plain JavaScript (ES2020+), no TypeScript, built by Node.js
(Node 18+ for Vite 8/Vitest 4) — a dev-only toolchain, never required to *view* the
generated artifact or to *run* `generate_interactive_map.py` (research.md §1).

**Primary Dependencies**: Python side — zero new dependencies; reuses `requests`,
`Pillow`, `PyYAML`, `jsonschema` and the existing `scripts/rkby_maps/` /
`scripts/rkby_records.py` modules verbatim. Frontend side (new,
`frontend/interactive-map/package.json`, dev-only) — `leaflet` (^1.9, BSD-2-Clause,
pan/zoom/marker/popup engine), `vite` (^8, build tool), `vitest` (^4, test runner),
`vite-plugin-singlefile` (^2.3, MIT — inlines the build into one non-module
`index.html` so it runs under `file://`, research.md §10).

**Storage**: Local filesystem only, under the same `RKBY_DATA_DIR`. Reads/writes the
same `seasons/<label>/applicants/*.yaml` records `generate_member_maps.py` already
extended with `latitude`/`longitude` — no schema change (data-model.md). Adds one
new gitignored top-level folder, `interactive_map/` (data-model.md § Local Data
Repository), and reuses (never duplicates) the existing gitignored `.tile_cache/`.

**Testing**: Python — `pytest`, `responses`-mocked Nominatim/tile HTTP, synthetic
fixtures only (Constitution V) — for the merge/eligibility/bundling logic
(research.md §4). Frontend — `vitest`, for the three pure, testable units of client
logic this feature actually needs: the ported default-season-date rule
(research.md §5), season-active-set visibility/popup-data filtering (research.md
§6), and same-coordinate marker decluttering (research.md §7). Leaflet wiring itself
(DOM/map glue) is intentionally kept thin and untested — verified instead via
quickstart.md's manual browser scenarios, same posture the constitution's
Development Workflow section already expects for anything not worth automating.

**Target Platform**: Generation — Linux/macOS developer machine, run on demand via
`uv run`, same as the other scripts. Viewing — any standard current desktop browser
(Chrome, Firefox, Edge, Safari) on any OS, opened directly from the filesystem, no
network required (FR-019, SC-003).

**Project Type**: One Python CLI script (Constitution II) plus one small internal
package (`scripts/rkby_interactive_map/`, private to it) that also *reuses*
`scripts/rkby_maps/` (no longer private to `generate_member_maps.py` alone, per
Project Structure below) — plus one small, source-controlled frontend subproject
(`frontend/interactive-map/`) whose *build output* is what the Python script treats
as an input. Still one generated artifact per Constitution II; the frontend
subproject is this artifact's implementation, not a second use case.

**Performance Goals**: SC-011 — a full run across all of this team's current seasons
(several seasons, ~200 records each) completes in under 15 minutes on a typical
laptop. Dominated by the one-time basemap tile fetch for the combined bounding box;
geocoding is near-zero-cost in steady state since it shares 002's permanent
per-address cache (research.md §11).

**Constraints**: OSM tile usage policy forbids bundling an offline/multi-zoom tile
pyramid outright (research.md §2) — resolved by shipping one flattened composite
image instead of a live tile layer. Nominatim: same 1 req/sec, address-only,
cache-forever discipline as 002 (reused code, not re-implemented). Principle I data
minimization: the bundled `map-data.js` carries only the fields data-model.md's
Bundled Map Data table lists — never address/phone/email/birthday/etc. (research.md
§12). `file://`-opened compatibility requires a non-module, single-file JS/CSS
bundle with data injected via a classic script tag, never `fetch()` (research.md
§10). No CLI flags (FR-002).

**Scale/Scope**: ~200 member records × a handful of seasons, merged down to however
many *distinct* people that represents. One basemap image, one data file, one photo
per merged member. Out of scope: any way to select a season subset before viewing
(FR-002); any change to the existing static pin/photo maps (002 is untouched);
account-based/paid tile or geocoding providers (research.md §2).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Member Data Privacy First | Name, phone, birthday, address, email, and every other non-popup field are never written into the shared artifact — `map-data.js` is limited to exactly the fields data-model.md's Bundled Map Data table lists (research.md §12), matching Principle I's own explicit "interactive maps... MUST expose only the minimum data necessary" example. Address *text* is still sent to Nominatim under the same narrow, already-ratified exception 002 uses (constitution v2.0.0), via the same reused code path — no new third-party data flow is introduced. Excluded/ignored season-records are filtered out before merge (FR-004), satisfying the opt-out requirement (SC-010). | **PASS** |
| II. One Script, One Artifact | New, independent script `scripts/generate_interactive_map.py`; not a mode on `generate_member_maps.py`. `scripts/rkby_maps/` — previously documented as "private to `generate_member_maps.py`" (002 plan.md) — is now reused by a second script too; this is exactly the "shared logic... once duplication is real" case Principle II already permits (same projection math, tile fetch/cache, geocoding cache would otherwise be re-implemented twice). The new `scripts/rkby_interactive_map/` package holds logic private to this one script (merge/eligibility, bundle assembly). `frontend/interactive-map/` is this one artifact's implementation, not a second artifact — see Project Structure. | PASS |
| III. Local Data Is the Editable Source of Truth | Writes exactly one thing back to the season YAMLs — `latitude`/`longitude`, fill-empty-only, via the exact same `geocode_record_if_needed` helper 002 already uses and is already governed by this rule. `map-data.js`/`interactive_map/` are pure, disposable exports (data-model.md § Bundled Map Data, "Not a source of truth") — regenerated from scratch every run, never read back. | PASS |
| IV. Python, Minimal Dependencies | Zero new *Python* dependencies. The frontend's Node/npm toolchain (Leaflet, Vite, Vitest, vite-plugin-singlefile) is a dev-only build chain for a generated web artifact's own implementation — analogous to Pillow producing PNG bytes that aren't "Python code" either — not a new dependency of the `generate_interactive_map.py` script itself, which needs neither Node nor network access beyond what 002's script already needs (geocoding, tiles). Each frontend library is the standard, minimal-footprint choice for its one job (Leaflet: pan/zoom/marker engine; Vite: bundler; Vitest: its zero-config test runner; vite-plugin-singlefile: the one plugin that makes `file://` viewing actually work) — no framework, no state-management library, no CSS framework. | PASS |
| V. Test-First Development (Red-Green) | All Python logic (cross-season merge, eligibility, latest-record selection, bundle/photo/basemap assembly) is unit-tested via `pytest` against synthetic fixtures, same discipline as 002. The one genuinely new question — client-side JS has no established test tooling in this project — is resolved by adopting Vitest (user-directed) for exactly the three pure logic units that need it (research.md §5–§7); the remaining Leaflet/DOM wiring is deliberately kept thin enough that manual quickstart verification is a proportionate substitute, consistent with the Development Workflow section's existing "SHOULD be manually verified... in addition to automated tests" posture for lower-risk code. | PASS |

**Post-Phase-1 re-check**: data-model.md and contracts/ confirm the design stays
within one Python script + one reused package + one new private Python package +
one source-controlled frontend subproject producing a single generated artifact, no
new Python dependency introduced during Phase 1 beyond what Phase 0 already
identified (none). All gates above hold at **PASS**; no Complexity Tracking entry is
needed.

## Project Structure

### Documentation (this feature)

```text
specs/003-interactive-photo-map/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/             # Phase 1 output (/speckit-plan command)
│   ├── cli-and-env.md
│   ├── output-artifact.md
│   └── map-data.schema.json
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
scripts/
├── generate_member_maps.py          # existing (002) — unchanged
├── generate_interactive_map.py      # NEW — the one script for this feature (Constitution II):
│                                     #   CLI entrypoint, cross-season orchestration
├── rkby_records.py                  # existing (001/002) — reused unchanged
├── rkby_maps/                       # existing (002) — no longer private to
│   │                                 #   generate_member_maps.py alone; also imported by
│   │                                 #   generate_interactive_map.py (Constitution II: real,
│   │                                 #   not anticipated, duplication avoided)
│   ├── geocoding.py                 # reused as-is: geocode_record_if_needed
│   ├── basemap.py                   # reused as-is: zoom_for_bounding_box, stitch_basemap,
│   │                                 #   lonlat_to_pixel, fetch_tile/.tile_cache
│   ├── clustering.py                # NOT reused (no forced non-overlap logic, spec Assumptions)
│   └── rendering.py                 # PLACEHOLDER_PHOTO_PATH reused; crop_circular_photo NOT
│                                     #   reused (CSS crop instead, research.md §9)
├── rkby_interactive_map/            # NEW — internal package, private to
│   │                                 #   generate_interactive_map.py (still one artifact)
│   ├── __init__.py
│   ├── merge.py                     # cross-season eligibility + latest-record merge
│   │                                 #   (research.md §4, FR-004/FR-009/FR-010)
│   └── bundle.py                    # assembles map-data.js payload, positions members
│                                     #   (research.md §3), copies photos/placeholder,
│                                     #   writes interactive_map/ (data-model.md)
└── schemas/
    └── applicant_record.schema.json # unchanged — no new fields this feature

frontend/
└── interactive-map/                 # NEW — small Vite + Leaflet SPA, source-controlled
    ├── package.json                 # leaflet, vite, vitest, vite-plugin-singlefile (all dev
    │                                 #   except leaflet itself, bundled into the output)
    ├── vite.config.js               # base: "./", vite-plugin-singlefile (research.md §10)
    ├── index.html                   # entry template incl. the map-data.js <script> tag
    ├── src/
    │   ├── main.js                  # Leaflet bootstrap: CRS.Simple, ImageOverlay, markers,
    │   │                             #   popups, season controls, pan buttons (untested glue)
    │   ├── defaultSeason.js         # + defaultSeason.test.js (research.md §5, FR-007)
    │   ├── popupData.js             # + popupData.test.js (research.md §6, FR-006/FR-015/FR-016)
    │   ├── declutter.js             # + declutter.test.js (research.md §7, FR-021)
    │   └── styles.css
    └── dist/                        # BUILT OUTPUT — committed to git (data-model.md §
                                      #   Frontend Build Output); generate_interactive_map.py
                                      #   reads dist/index.html as a required input, never builds it

tests/
├── unit/
│   ├── test_rkby_interactive_map_merge.py    # cross-season eligibility, latest-record
│   │                                          #   selection, per-season role-entry retention
│   ├── test_rkby_interactive_map_bundle.py   # map-data.js payload shape, photo/placeholder
│   │                                          #   copy, pixel-position computation, idempotent
│   │                                          #   folder regeneration
│   └── test_generate_interactive_map_cli.py  # env var handling, no-flags CLI, exit codes,
│                                              #   missing frontend/dist/index.html error path
└── fixtures/
    └── (reuses existing nominatim_response_*.json / osm_tile_fixture.png / sample_photo.jpg)

data/                                 # NOT used by this feature — real data lives under
                                       # RKBY_DATA_DIR outside this repo (already gitignored)
```

**Structure Decision**: One Python script per Constitution II —
`scripts/generate_interactive_map.py` — with its own private package
(`scripts/rkby_interactive_map/`) for logic genuinely specific to this feature
(merge, bundle assembly), and re-importing `scripts/rkby_maps/` for the projection,
tile-fetch, and geocoding logic that's now genuinely shared between two scripts
(002's own Structure Decision already anticipated this package might outgrow being
private to one script). The one new thing this feature adds beyond "another Python
script" is a small, source-controlled frontend subproject
(`frontend/interactive-map/`) — its *build output* is treated by the Python side as
a plain, versioned input file, keeping the constitution's "Language: Python 3"
framing intact for the actual generation script while still delivering the SPA the
feature needs. Tests follow the existing `tests/unit` + `tests/fixtures` convention
on the Python side, and Vitest's own colocated `*.test.js` convention on the
frontend side — each toolchain uses its own idiomatic layout rather than forcing
one onto the other.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No entries — the Constitution Check above holds at PASS with no unresolved
violation. The dual-toolchain (Python + Node/npm) design decision is documented
transparently in Technical Context and the Constitution Check table rather than
recorded here, since it introduces no tension with a stated principle: the
generation script itself remains pure Python with zero new Python dependencies, and
Node is a dev-only build tool for the generated artifact's own implementation.*
