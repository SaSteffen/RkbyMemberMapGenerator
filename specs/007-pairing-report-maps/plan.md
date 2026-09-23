# Implementation Plan: Pairing Report Maps

**Branch**: `007-pairing-report-maps` | **Date**: 2026-08-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-pairing-report-maps/spec.md`

## Summary

Two fixes to `scripts/generate_rider_pairings.py`'s Training Clusters section, plus
maps: (1) remove the existing 3-member minimum so every eligible current-season rider
appears in the Training Clusters section, including as a single-member cluster
(FR-001/002); (2) render one map image per Training Cluster, plotting that cluster's
riders plus any other current-season member of any role nearby, for context
(FR-003/004/005); (3) render one whole-team overview map per report, covering every
role (FR-006/007/008). All map rendering reuses the existing OSM-tile/role-colored-pin
machinery `generate_member_maps.py` already built (002-map-generator) — the
overlap-aware pin-layer logic that currently lives privately inside that script is
promoted into a new shared `scripts/rkby_maps/pin_map.py` module so both scripts draw
identical maps without duplicating that logic. No new third-party dependency, no new
geocoding calls, no schema change.

## Technical Context

**Language/Version**: Python 3.11+ (existing project baseline, `pyproject.toml`
`requires-python = ">=3.11"`)

**Primary Dependencies**: Pillow (map raster drawing), requests (OSM tile fetch) —
both already project dependencies, reused unchanged via `scripts/rkby_maps/`. No new
dependency: this feature adds no Nominatim geocoding calls of its own (Decision 4,
research.md) and no new output format beyond PNG (already produced by 002) and the
existing Markdown/PDF report (already produced by 006).

**Storage**: Local YAML records under `RKBY_DATA_DIR/seasons/<season>/applicants/`
(read-only for this feature — no schema or record change); newly written PNG files
under `RKBY_DATA_DIR/reports/maps/`.

**Testing**: `pytest` (`uv run pytest`), with the `responses` library mocking OSM tile
HTTP fetches — the same pattern `tests/unit/test_generate_member_maps_cli.py` and
`tests/unit/test_detail_fetch.py` already use. Pure-logic pieces (frame/pool
selection, no-minimum clustering, Markdown section assembly, map filename numbering)
get plain synthetic-record unit tests with no network mocking, matching
`tests/unit/test_rkby_pairing_clusters.py`'s existing style.

**Target Platform**: Linux/macOS CLI, run locally via `uv run scripts/<name>.py`
(existing project convention, no server/service component).

**Project Type**: Single Python CLI project — one script per artifact
(`scripts/generate_rider_pairings.py`), backed by small focused packages
(`scripts/rkby_pairing/`, `scripts/rkby_maps/`). No frontend/backend split.

**Performance Goals**: Not independently specified by spec.md; inherits 002's proven
characteristics (concurrent per-map rendering via `ThreadPoolExecutor`, on-disk OSM
tile cache so a re-run never re-fetches a tile already seen). No new performance
target introduced.

**Constraints**: FR-012 — must run and produce its own maps without requiring
`generate_member_maps.py` to have already run for the season this run. FR-011 — every
map PNG this feature writes stays inside `RKBY_DATA_DIR` and is never committed to
this project's code repository or to `RKBY_DATA_DIR`'s own git history. FR-010 — every
map is regenerated fresh on every run (no stale image reused).

**Scale/Scope**: Bounded by one team's season roster (tens to low hundreds of
members) — same scale 002/006 already operate at; no scale-related design change.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Verdict |
|---|---|---|
| I. Member Data Privacy First | No new third-party upload: OSM tile fetches send only tile z/x/y coordinates (never member data), unchanged from 002's already-accepted design; no new Nominatim geocoding call is added (Decision 4, research.md) so the existing address-only geocoding exception isn't exercised any further by this feature. Every map PNG is written only under `RKBY_DATA_DIR/reports/maps/` and never committed (FR-011, Decision 5) — same local-only handling as every other artifact holding member location data. Excluded/opted-out members are already never candidates for any map (FR-009, inherited from `is_eligible_base`). | PASS |
| II. One Script, One Artifact | This feature extends `generate_rider_pairings.py` (its own script) rather than adding a mode to `generate_member_maps.py`. Promoting `generate_member_maps.py`'s private pin-layer/frame-selection logic into `scripts/rkby_maps/pin_map.py` (Decision 2, research.md) is exactly the "shared logic MAY be factored out once duplication is real" carve-out this principle already grants — mirrors how `canonical_match_keys` was promoted into `rkby_records.py` for 006. No shared CLI, no new framework. | PASS |
| III. Local Data Is the Editable Source of Truth | No `.yaml` record is read differently or written by this feature (Decision 4: no on-demand geocoding, so no record mutation). Purely additive, derived output (map PNGs, extra report sections). | PASS |
| IV. Python, Minimal Dependencies | Zero new dependencies (Technical Context above). | PASS |
| V. Test-First Development | New/changed behavior (no-minimum clustering, cluster maps, overview map, report section wiring) gets failing tests first in the tasks phase, following this project's established `pytest` + `responses`-mocked-network pattern; no real data used in tests (Constitution Principle I). Existing tests in `tests/unit/test_rkby_pairing_clusters.py` that currently assert `clusters == []` for 1-2-member groups encode the *old* 3-minimum behavior and must be updated as part of that same red-green cycle (research.md Decision 1) — flagged here so the tasks phase doesn't miss it. | PASS (flagged for tasks) |

No violations requiring a Complexity Tracking entry.

## Project Structure

### Documentation (this feature)

```text
specs/007-pairing-report-maps/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── map-output.md
│   └── report-output.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
scripts/
├── generate_rider_pairings.py     # existing script (006) -- CLI entrypoint, extended (no new flags)
├── rkby_pairing/
│   ├── clusters.py                # existing (006) -- find_training_clusters: min_group_size 3 -> 1
│   ├── eligibility.py             # existing (006) -- is_eligible_base reused unchanged, no edit
│   ├── report.py                  # existing (006) -- render_report: + "## Team Overview" section,
│   │                               #   + per-cluster map <img>, image-path params added
│   ├── pdf.py                     # existing (006) -- unchanged, already renders embedded <img> tags
│   ├── ranking.py, roles.py       # existing (006) -- unchanged
│   └── maps.py                    # NEW -- builds the overview map + one map per Training Cluster,
│                                   #   using scripts/rkby_maps/pin_map.py for the actual rendering
├── rkby_maps/
│   ├── basemap.py                 # existing (002) -- stitch_basemap/zoom_for_bounding_box, unchanged
│   ├── clustering.py               # existing (002) -- find_overlap_groups, unchanged
│   ├── geocoding.py                # existing (002) -- unchanged, not called by this feature
│   ├── rendering.py                # existing (002) -- draw_pin/role_color, unchanged
│   └── pin_map.py                  # NEW -- promoted from generate_member_maps.py's private helpers:
│                                   #   CANVAS_SIZE, DEFAULT_MIN_WIDTH_KM, FRAME_PADDING_PX,
│                                   #   pixel_positions(), records_within_frame(),
│                                   #   render_pin_layer(), overview_center_and_zoom()
└── generate_member_maps.py        # existing (002) -- refactored to import the above from pin_map.py
                                    #   instead of its own private copies; behavior unchanged

tests/unit/
├── test_rkby_pairing_clusters.py           # existing -- updated for the removed 3-minimum
├── test_rkby_pairing_report.py             # existing -- extended for the new sections/params
├── test_generate_rider_pairings_cli.py     # existing -- extended for map-file output assertions
├── test_generate_member_maps_cli.py        # existing -- updated for the pin_map.py import move
├── test_rkby_maps_pin_map.py               # NEW -- promoted-helper unit tests
└── test_rkby_pairing_maps.py               # NEW -- cluster-map/overview-map unit tests
```

**Structure Decision**: No new script (Principle II) — this remains
`generate_rider_pairings.py`'s feature, extended in place, matching how 006 itself was
added to a script that started in 002. The only new modules are (a) `rkby_pairing/
maps.py`, this feature's own map-orchestration logic (which cluster gets which frame,
which files get written, in what order), living alongside its sibling modules the same
way `clusters.py`/`ranking.py` already do; and (b) `rkby_maps/pin_map.py`, the
promoted, now-shared rendering plumbing both `generate_member_maps.py` and
`rkby_pairing/maps.py` call — a "small shared module" in the sense Principle II
explicitly permits once duplication is real, not a new framework or shared CLI.

## Complexity Tracking

*No entries — Constitution Check reported no violations.*
