# Implementation Plan: PMTiles Basemap for Interactive Map

**Branch**: `004-pmtiles-basemap` | **Date**: 2026-08-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-pmtiles-basemap/spec.md`

## Summary

Replace the interactive map's basemap source: instead of `generate_interactive_map.py`
fetching and pre-baking a large per-run pyramid of OpenStreetMap raster tiles
(`rkby_interactive_map/bundle.py`'s `generate_basemap`), the generator copies one
maintainer-supplied local PMTiles archive (`<RKBY_DATA_DIR>/basemap.pmtiles`) into
the bundle, base64-embedded so it can be read entirely offline despite Chromium's
`file://` fetch/XHR restrictions (research.md §2), and the frontend renders it with
`protomaps-leaflet` + `pmtiles` (research.md §1) using real geographic coordinates
(`L.CRS.EPSG3857`) instead of the old precomputed-pixel-canvas approach
(research.md §5). This deletes the OSM-tile-baking code path for the *interactive*
map only — `generate_member_maps.py`'s own static-PNG maps keep using
`rkby_maps/basemap.py`'s OSM fetch/stitch code unchanged.

## Technical Context

**Language/Version**: Python 3.11 (generator, unchanged) + JavaScript/Vite 8
(frontend, unchanged toolchain — `frontend/interactive-map/`, built every run via
`pnpm`, per `specs/003-interactive-photo-map/contracts/cli-and-env.md`)

**Primary Dependencies**: Python: none added — validation is a stdlib 8-byte header
check (research.md §3); `Pillow`/`requests` stay (still used elsewhere:
`rkby_maps/basemap.py` for `generate_member_maps.py`, `rkby_interactive_map/
rendering.py` for photo thumbnails). Frontend: add `pmtiles` (^4.5) and
`protomaps-leaflet` (^5.1) to `frontend/interactive-map/package.json`; existing
`leaflet` ^1.9.4, `vite`, `vite-plugin-singlefile` stay (research.md §1).

**Storage**: Local files only. New required input: one maintainer-supplied
`<RKBY_DATA_DIR>/basemap.pmtiles` (research.md §4). No change to `seasons/`
storage. `<RKBY_DATA_DIR>/.tile_cache/` and `interactive_map/tiles/` stop being
written by this script (research.md §7) but `.tile_cache/` stays in use by
`generate_member_maps.py`.

**Testing**: `pytest` (`uv run pytest`) for the generator; `vitest` (`pnpm test`,
already wired into the frontend build) for frontend pure-logic modules
(`declutter.js`, `basemapTiles.js`'s replacement, `popupData.js`) — same tooling as
spec 003, no new test framework.

**Target Platform**: Self-contained `interactive_map/index.html`, opened directly
via `file://` (no server) in a current desktop or mobile browser — identical
contract to spec 003's output artifact; this feature does not change how the
bundle is opened or shared.

**Project Type**: Single project, two-language (Python generator + Vite/Leaflet
frontend) — same shape spec 003 already established, not a new structure.

**Performance Goals**: No new SLA introduced by this spec. Embedding the sample
19.7 MB archive as base64 adds ~26 MB of text to the bundle (research.md §2) —
acceptable given the artifact is a locally-shared folder, not a hosted web page.

**Constraints**: Zero network requests at generation time (FR-002) or view time
(FR-004) for the basemap. Must keep working when `index.html` is opened directly
via `file://`, which is what makes this feature's core technical problem
(research.md §2) real rather than theoretical — verified empirically against a
real Chromium binary, not assumed from documentation.

**Scale/Scope**: One script (`generate_interactive_map.py`) and its existing
helper modules (`rkby_interactive_map/bundle.py`, plus frontend `src/main.js`,
`src/basemapTiles.js`, `src/declutter.js`). `generate_member_maps.py` and
`rkby_maps/basemap.py`'s OSM fetch/stitch functions are explicitly out of scope —
unchanged by this feature (research.md §5).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Member Data Privacy First | No new third-party network call is introduced — this feature *removes* the interactive map's only recurring third-party dependency at generation time (the OSM tile server, FR-002/SC-001). The Nominatim geocoding exception is untouched by this feature. The PMTiles basemap file itself carries no member data. | **PASS** |
| II. One Script, One Artifact | Still exactly one script (`generate_interactive_map.py`) for one artifact. Changes are internal to its existing helper modules; no new script, no new CLI flag/mode. | **PASS** |
| III. Local Data Is Editable Source of Truth | Not touched — no scraped-data merge/persistence logic is changed by this feature. | **PASS (unaffected)** |
| IV. Python, Minimal Dependencies | No Python dependency added (research.md §3). Two small, well-maintained JS packages added to the frontend (`pmtiles`, `protomaps-leaflet`, both maintained by the Protomaps project, combined ~1.5 MB unpacked vs. the ~19.5 MB MapLibre GL alternative that was rejected specifically to avoid a heavier dependency, research.md §1) — directly required by FR-001. | **PASS** |
| V. Test-First Development (Red-Green) | Procedural gate for `/speckit-implement`, not a design-time blocker. Affected existing tests are named in Phase 1 (`data-model.md`); new/changed behavior (PMTiles header validation, base64 embedding, real-CRS marker positioning) needs new failing tests before implementation, same as every prior feature. | **PASS (procedural, enforced at implement time)** |

No violations. Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/004-pmtiles-basemap/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

No new top-level structure — this feature modifies files inside the existing
layout spec 003 established (see `README.md`'s Project structure section):

```text
scripts/
├── generate_interactive_map.py       # CLI entrypoint (unchanged shape; new basemap.pmtiles
│                                      # existence/validity check added before build, FR-003)
├── rkby_interactive_map/
│   ├── bundle.py                     # generate_basemap/_tile_levels/_write_level_tiles/
│   │                                  # _base_level/compute_positions DELETED; replaced by a
│   │                                  # small embed-and-validate step (research.md §2, §3, §5)
│   └── merge.py                      # unchanged — already emits latitude/longitude per member
└── rkby_maps/
    └── basemap.py                    # UNCHANGED — generate_member_maps.py (spec 002) still
                                       # depends on stitch_basemap/lonlat_to_pixel/
                                       # zoom_for_bounding_box for its own static PNG maps

frontend/interactive-map/
├── package.json                      # add pmtiles, protomaps-leaflet
└── src/
    ├── main.js                       # CRS.Simple -> CRS.EPSG3857; real-latlng markers;
    │                                  # construct PMTiles from a Blob-backed custom Source
    ├── basemapTiles.js                # DELETED — chunk-grid math no longer applies
    ├── basemapTiles.test.js           # DELETED with it
    └── declutter.js                   # overlap math moves from precomputed canvas-pixel
                                        # distance to map.latLngToContainerPoint (research.md §5)

tests/unit/
├── test_basemap.py                          # UNCHANGED — tests rkby_maps/basemap.py, which
│                                             # this feature does not touch
├── test_rkby_interactive_map_bundle.py      # tests for deleted functions removed; new tests
│                                             # for basemap.pmtiles validation/embedding added
└── test_generate_interactive_map_cli.py     # extended: missing/invalid basemap.pmtiles -> FR-003
```

**Structure Decision**: No structural change to the repository. This feature edits
existing files inside the single-project, two-language layout `specs/
003-interactive-photo-map/` already established (Constitution Principle II — no
new script). `rkby_maps/basemap.py` is explicitly preserved unchanged because
`generate_member_maps.py` (a separate script, spec 002) still depends on it for its
own, unrelated static-map basemap rendering.

## Complexity Tracking

*No entries — Constitution Check above has no violations to justify.*
