---

description: "Task list for PMTiles Basemap for Interactive Map"
---

# Tasks: PMTiles Basemap for Interactive Map

**Input**: Design documents from `/specs/004-pmtiles-basemap/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-and-env.md,
contracts/output-artifact.md, contracts/map-data.schema.json, quickstart.md

**Tests**: Included. Constitution Principle V (Test-First Development, Red-Green) is a
project-wide, non-optional gate — plan.md's Constitution Check confirms new/changed
behavior needs new failing tests before implementation, same as every prior feature.

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P4) so each can
be implemented and (mostly) tested independently. US1 replaces the entire basemap
pipeline the other stories build on, so US2–US4 depend on it landing first even though
each has its own independent test criteria.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- File paths are relative to the repository root unless stated otherwise

## Path Conventions

Single project, two-language layout already established by spec 003 — no new
top-level structure (plan.md § Project Structure):

- Python: `scripts/generate_interactive_map.py`, `scripts/rkby_interactive_map/bundle.py`
- Frontend: `frontend/interactive-map/src/`
- Tests: `tests/unit/` (Python, pytest), `frontend/interactive-map/src/*.test.js` (Vitest)

---

## Phase 1: Setup

**Purpose**: Add the two frontend dependencies this feature needs before any code
touches them.

- [X] T001 [P] Add `pmtiles` (^4.5) and `protomaps-leaflet` (^5.1) to
  `frontend/interactive-map/package.json`'s `dependencies` (alongside the existing
  `leaflet` ^1.9.4); run `pnpm install` inside `frontend/interactive-map/` to update
  `pnpm-lock.yaml` (research.md §1).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Remove the old OSM-tile-baking code path this feature replaces, so US1's
new code has a clean slate instead of two conflicting basemap implementations
coexisting. `rkby_maps/basemap.py` itself is explicitly out of scope — it stays
untouched because `generate_member_maps.py` (spec 002) still depends on it directly.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Delete the OSM-tile-baking code path from
  `scripts/rkby_interactive_map/bundle.py`: remove `compute_positions`, `_base_level`,
  `_tile_levels`, `_write_level_tiles`, `generate_basemap`, and the
  `CANVAS_SIZE`/`MIN_WIDTH_KM`/`PADDING_KM`/`DEFAULT_CENTER`/`DEFAULT_ZOOM`/
  `BASEMAP_LEVELS`/`MAX_OSM_ZOOM`/`TILE_PX`/`_TILE_PAD_COLOR` constants, and the
  now-unused `math`, `PIL.Image`, and `scripts.rkby_maps.basemap`
  (`canvas_origin`/`lonlat_to_pixel`/`stitch_basemap`/`stitch_region`/
  `zoom_for_bounding_box`) imports (research.md §5, plan.md § Project Structure).
  `rkby_maps/basemap.py` itself is not touched.
- [X] T003 [P] Delete `frontend/interactive-map/src/basemapTiles.js` and
  `frontend/interactive-map/src/basemapTiles.test.js` — the chunk-grid math they
  implement/test no longer applies once the basemap is a real PMTiles archive
  (plan.md § Project Structure).
- [X] T004 In `tests/unit/test_rkby_interactive_map_bundle.py`, remove the top-level
  import of `compute_positions`/`generate_basemap` (T002 deleted them) and delete every
  test that exercises the deleted functions: `test_compute_positions_is_order_independent`,
  `test_compute_positions_handles_zero_members`,
  `test_assemble_map_data_describes_the_base_image_and_tile_levels`,
  `test_assemble_map_data_tile_level_grids_cover_the_full_scaled_canvas`,
  `test_generate_basemap_writes_a_jpeg_of_canvas_size`,
  `test_generate_basemap_writes_uniformly_sized_tile_chunks`,
  `test_generate_basemap_never_rewrites_an_already_baked_tile_chunk`. Keep every
  photo/placeholder-copying and idempotency test — those are unaffected by this
  feature.

**Checkpoint**: Old basemap-baking code is gone from both languages; `uv run pytest`
and `pnpm test` both still pass (with a smaller test suite) before US1 starts.

---

## Phase 3: User Story 1 - Generate the map from a supplied PMTiles basemap (Priority: P1) 🎯 MVP

**Goal**: Default (embedded) build: validate `<RKBY_DATA_DIR>/basemap.pmtiles`,
base64-embed it into the bundle, and render it with `protomaps-leaflet` using real
geographic marker positions — zero OSM tile-server requests at generation time.

**Independent Test**: With a valid PMTiles file at `<RKBY_DATA_DIR>/basemap.pmtiles`,
run `uv run scripts/generate_interactive_map.py` and confirm the produced bundle's
basemap comes from that file (open `index.html`, see the real map render), no
`tile.openstreetmap.org` traffic occurs, and no `basemap.jpg`/`tiles/` are produced
(quickstart.md Scenario 1).

### Backend: validation and embedding

- [X] T005 [US1] In `tests/unit/test_rkby_interactive_map_bundle.py`, add failing tests
  for a new PMTiles header-validation function: a file starting with ASCII `PMTiles`
  followed by a supported version byte (`<= 3`) passes; a missing file, an unreadable
  file, a file shorter than 8 bytes, and a file with the wrong magic bytes or an
  unsupported version byte each raise with a message naming
  `<RKBY_DATA_DIR>/basemap.pmtiles` (data-model.md § PMTiles Basemap File §
  Validation, research.md §3).
- [X] T006 [US1] In `scripts/rkby_interactive_map/bundle.py`, implement the validator
  (e.g. `validate_pmtiles_file(path: Path) -> None`): stdlib-only 8-byte header check,
  no new dependency (research.md §3). Makes T005 pass.
- [X] T007 [US1] In `tests/unit/test_rkby_interactive_map_bundle.py`, add failing tests
  for the base64-embedding step: given a valid PMTiles file, it writes
  `interactive_map/basemap-pmtiles.js` containing
  `window.RKBY_PMTILES_BASE64 = "…";` whose decoded bytes equal the original file
  byte-for-byte, and re-running with the same input file produces a byte-identical
  `basemap-pmtiles.js` (SC-002, research.md §2).
- [X] T008 [US1] In `scripts/rkby_interactive_map/bundle.py`, implement the embed step
  (e.g. `embed_basemap(interactive_map_dir: Path, pmtiles_path: Path) -> dict`
  returning the embedded-mode `basemap` object): base64-encodes the archive and writes
  `basemap-pmtiles.js` (research.md §2). Makes T007 pass.
- [X] T009 [US1] In `tests/unit/test_rkby_interactive_map_bundle.py`, update
  `SCHEMA_PATH` to point at
  `specs/004-pmtiles-basemap/contracts/map-data.schema.json`, then add/update failing
  tests for `assemble_map_data`'s payload: each `members[]` entry now carries `lat`/
  `lon` (passed straight through from the merged member's own `latitude`/`longitude`,
  no projection) instead of `x`/`y`; the top-level `image` block is gone; a top-level
  `basemap` object matching T008's embedded-mode shape (`{"mode": "embedded", "file":
  "basemap-pmtiles.js", "variable": "RKBY_PMTILES_BASE64"}`) is present; the whole
  payload still validates against the schema (data-model.md § Bundled Map Data).
- [X] T010 [US1] In `scripts/rkby_interactive_map/bundle.py`, update `assemble_map_data`
  to emit `lat`/`lon` from each merged member's `latitude`/`longitude` and the new
  `basemap` object (calling T008's embed step) instead of `image`; update the module's
  top docstring (currently describes "precomputed pixel positions... base flattened
  basemap image plus tiled levels") to describe the new validate-then-embed
  responsibility. Makes T009 pass.
- [X] T011 [US1] In `scripts/generate_interactive_map.py`'s `main()`, call T006's
  validator on `config.data_dir / "basemap.pmtiles"` immediately after config/arg
  loading and **before** `build_frontend()` runs (contracts/cli-and-env.md: a missing
  basemap file must fail fast without waiting on a frontend build); on failure, print
  an error to stderr naming the path and return non-zero, matching the existing
  `ConfigError` pattern. Replace the `generate_basemap(...)` call (T002 deleted it)
  with T008's embed step, called via `assemble_map_data` (T010) or directly — remove
  the now-unused `config.data_dir / ".tile_cache"` argument from this script (that
  cache stays in use only by `generate_member_maps.py`).

### Backend: tiles/ exemption cleanup (research.md §7)

- [X] T012 [P] [US1] In `tests/unit/test_generate_interactive_map_cli.py`, replace
  `test_ensure_interactive_map_dir_never_deletes_tiles` with a failing test asserting
  the **opposite**: a leftover `tiles/` folder from a prior (pre-this-feature) run is
  now deleted by `_ensure_interactive_map_dir`, exactly like every other regenerated
  file. This intentionally reverses the old "never delete `tiles/`" exemption — a
  deliberate, confirmed decision scoped to this feature (research.md §7): once T002's
  deletion ships, nothing ever writes to `tiles/` again, so the old exemption protects
  a folder no future run will populate.
- [X] T013 [US1] In `scripts/generate_interactive_map.py`, remove the `tiles/`
  exemption from `_ensure_interactive_map_dir` (the `if entry.name == "tiles":
  continue` branch) and update its docstring accordingly. Makes T012 pass.

### Frontend: PMTiles rendering

- [X] T014 [P] [US1] Add `frontend/interactive-map/src/basemapSource.test.js`
  (Vitest) with failing tests for a new pure-logic module (this feature's replacement
  for `basemapTiles.js` in the frontend structure, plan.md § Testing): a
  `base64ToBlob(base64String)` helper that round-trips known byte sequences, and a
  `BlobSource` class whose `getBytes(offset, length)` returns the correct byte range
  from a synthetic `Blob` (research.md §2's `FileSource` reference shape) and whose
  `getKey()` returns a stable string.
- [X] T015 [US1] Create `frontend/interactive-map/src/basemapSource.js` implementing
  `base64ToBlob` and `BlobSource` (satisfying `pmtiles`'s public `Source` interface:
  `getBytes`/`getKey`, research.md §2). Makes T014 pass.
- [X] T016 [US1] Rewrite `frontend/interactive-map/src/main.js`'s map setup: switch
  `crs: L.CRS.Simple` → `L.CRS.EPSG3857` (Leaflet's default), remove the
  `BasemapTileLayer`/`basemapTiles.js` import and the `L.imageOverlay` base layer;
  when `data.basemap.mode === "embedded"`, decode `window[data.basemap.variable]` via
  T015's `base64ToBlob`, wrap it in a `BlobSource`, construct
  `new pmtiles.PMTiles(source)`, and pass it as `protomaps-leaflet`'s `leafletLayer({
  url })` option using the package's default `flavor: "light"` paint/label rules
  (research.md §1). `main()` must become async (or use `.then` chaining) since
  constructing the layer now depends on an async `getHeader()` call (T018).
- [X] T017 [US1] In `main.js`, replace pixel-canvas marker positioning: drop
  `imageWidth`/`imageHeight`/`bounds`/`pixelToLatLng`, and position each marker
  directly via `L.marker([member.lat, member.lon])`; fit the map's initial view using
  the PMTiles archive's own bounds from `pmtiles.PMTiles#getHeader()` instead of the
  old image-pixel bounds (research.md §5).
- [X] T018 [US1] In `main.js`, read `minZoom`/`maxZoom` from
  `pmtiles.PMTiles#getHeader()` at runtime and set the `protomaps-leaflet` layer's
  `maxNativeZoom` to the header's `maxZoom` while the Leaflet map's own `maxZoom`
  stays higher, so panning past the archive's deepest baked zoom auto-scales that
  level instead of showing blank tiles (research.md §6, spec.md Edge Cases).
- [X] T019 [US1] In `main.js`, update the attribution control to source its text from
  the embedded archive's own attribution metadata (from `getHeader()`/PMTiles
  metadata) where available, falling back to the existing "© OpenStreetMap
  contributors" text (output-artifact.md § Attribution).
- [X] T020 [P] [US1] In `frontend/interactive-map/index.html`, add
  `<script src="./basemap-pmtiles.js"></script>` before the `map-data.js` script tag
  (embedded mode's classic-script asset, research.md §2). This tag is unconditional
  — the same built `index.html` is used for both build variants; in hosted mode (US4)
  the referenced file simply doesn't exist and the browser's failed local load has no
  effect, since `main.js` only reads `window[data.basemap.variable]` when
  `data.basemap.mode === "embedded"`.

**Checkpoint**: `uv run scripts/generate_interactive_map.py` against a real
`basemap.pmtiles` produces a bundle whose `index.html` renders the real basemap, pans
and zooms, and shows member markers at their real lat/lon — fully offline. This is the
MVP.

---

## Phase 4: User Story 2 - Fail clearly when the basemap file is missing (Priority: P2)

**Goal**: Missing or invalid `basemap.pmtiles` fails the whole run fast, before the
`pnpm` frontend build or any `interactive_map/` write, with an error naming the
expected path.

**Independent Test**: Delete (or corrupt) `<RKBY_DATA_DIR>/basemap.pmtiles`, run the
generator, and confirm it exits non-zero immediately with a message naming the path,
before any `interactive_map/` output appears (quickstart.md Scenario 2).

- [X] T021 [US2] In `tests/unit/test_generate_interactive_map_cli.py`, add failing
  CLI-level tests via `main()`: (a) `<RKBY_DATA_DIR>/basemap.pmtiles` missing, and (b)
  present but invalid (too short / wrong magic bytes) — both cases must return a
  non-zero exit code, print a message naming `<RKBY_DATA_DIR>/basemap.pmtiles`, never
  call `build_frontend` (mock/spy and assert not called), and leave no
  `interactive_map/` directory on disk (SC-003, contracts/cli-and-env.md's exit-code
  table).
- [X] T022 [US2] In `scripts/generate_interactive_map.py`, adjust T011's early
  validation call/error message as needed to satisfy T021 exactly (wording naming the
  full path, confirmed ordering strictly before `build_frontend()`).

**Checkpoint**: Both User Story 1 and User Story 2 work independently — the generator
still renders a correct map with a valid file, and fails fast and clearly without one.

---

## Phase 5: User Story 3 - Existing map interactions keep working (Priority: P3)

**Goal**: Confirm the basemap swap is invisible to a viewer — panning, zooming, photo
popups, season selection, and mobile mode all behave exactly as before, now driven by
real screen-projected marker positions instead of a precomputed pixel canvas.

**Independent Test**: Open a map generated under this feature and exercise pan/zoom
(gesture + buttons), hover/tap popups, season toggling, and mobile-mode/drawer;
confirm each behaves as it did before this change (quickstart.md Scenario 6).

- [X] T023 [US3] In `main.js`'s `renderMarkers`/`updateVisibleMarkers`, replace the
  `map.getZoomScale(map.getZoom(), 0)` + canvas-pixel `x`/`y` inputs to
  `declutterPositions` with each visible member's actual on-screen position via
  `map.latLngToContainerPoint([member.lat, member.lon])`, calling `declutterPositions`
  with its default `scale = 1` (container points are already real screen pixels); keep
  recomputing on `zoomend`, and also add a `moveend` listener (research.md §5).
- [X] T024 [P] [US3] Update `declutter.js`'s header comment (no functional change to
  the union-find/pack-grid algorithm) to describe its `x`/`y` inputs as Leaflet
  container points from `map.latLngToContainerPoint`, not precomputed canvas-pixel
  positions scaled by zoom (research.md §5).
- [X] T025 [US3] Manual regression pass against a bundle generated after Phase 3/4:
  run through `specs/003-interactive-photo-map/quickstart.md` Scenarios 3–7 (season
  toggles, cross-season popup, identical-address pair, idempotent member re-run,
  mobile mode/drawer) unchanged, per `specs/004-pmtiles-basemap/quickstart.md`
  Scenario 6 — confirm every interaction still behaves as documented there (FR-006).
  Verified with a headless-Chromium (Playwright) automated pass against a bundle
  generated from real `RKBY_DATA_DIR` data + the sample archive: zero non-`file://`
  network requests, zero console errors, basemap tile canvases render (including
  past the archive's max native zoom), markers render and re-declutter correctly
  after pan/zoom, season checkboxes change the visible member set, and hover popups
  open/close correctly on desktop. One pre-existing, feature-unrelated bug surfaced
  (not a regression from this feature — confirmed via `git log` that the
  `mouseover`/`mouseout` + `bindPopup` combo predates this feature, from spec 003's
  `93f4ca8`): on a touch device, the synthetic `mousemove`→`mouseover` from a tap
  opened the popup, then the tap's own `click` immediately toggled it closed again
  (Leaflet's default marker-click-toggles-its-bound-popup behavior), so tapping a
  marker on a real phone never showed a popup. Fixed (at the maintainer's request,
  after initially being flagged out-of-scope): `main.js`'s `renderMarkers` no longer
  calls `marker.bindPopup(...)`, which is what wired that internal toggling click
  handler; it now manages one `L.popup()` per marker directly, opened (never
  toggled) by both `mouseover` and `click`, closed by `mouseout` — Leaflet's own
  popup `autoClose` still closes a previously-open popup when a new one opens, and
  the map's own default click-elsewhere-closes-the-popup behavior is untouched.
  Re-verified with the same Playwright harness (mobile-viewport/touch-emulated
  context): a tap opens the popup, a second tap on the same marker leaves it open
  (no toggle-close), tapping a different marker switches to exactly one open popup,
  and tapping empty map area still closes it — with no console errors throughout.

**Checkpoint**: All three of User Stories 1–3 work together — correct basemap,
fail-fast validation, and zero regressions in existing interactions.

---

## Phase 6: User Story 4 - Optionally load the basemap from a maintainer-hosted URL (Priority: P4)

**Goal**: An opt-in `RKBY_BASEMAP_URL` env var makes the bundle reference a
maintainer-hosted PMTiles URL at view time instead of embedding the archive, while the
local file is still required and validated, and member data never goes to that URL.

**Independent Test**: Set `RKBY_BASEMAP_URL` to a reachable PMTiles archive URL, run
the generator, and confirm the bundle has no `basemap-pmtiles.js`, `map-data.js`'s
`basemap.mode` is `"hosted"`, and viewing the bundle fetches tiles only from that URL
(quickstart.md Scenario 5, SC-005).

- [X] T026 [P] [US4] In `tests/unit/test_generate_interactive_map_cli.py`, add failing
  tests for `load_config()`: `Config.basemap_url` equals `RKBY_BASEMAP_URL`'s value
  when the env var is set, and is `None` when unset.
- [X] T027 [US4] In `scripts/generate_interactive_map.py`, add a `basemap_url: str |
  None = None` field to the `Config` dataclass, populated in `load_config()` from
  `os.environ.get("RKBY_BASEMAP_URL")` (contracts/cli-and-env.md). Makes T026 pass.
- [X] T028 [P] [US4] In `tests/unit/test_rkby_interactive_map_bundle.py`, add failing
  tests: when a `basemap_url` is supplied to the embed/assemble step, `map-data.js`'s
  `basemap` object is `{"mode": "hosted", "url": "<value>"}` and `basemap-pmtiles.js`
  is **not** written; when omitted/`None`, T007/T009's embedded-mode behavior is
  unchanged (data-model.md § Bundled Map Data, research.md §8).
- [X] T029 [US4] In `scripts/rkby_interactive_map/bundle.py`, add an optional
  `basemap_url` parameter to the embed/assemble step (T008/T010): when set, skip the
  base64-embed step entirely and return the hosted `basemap` object instead; when
  unset, behavior is exactly T008/T010's embedded path. Makes T028 pass.
- [X] T030 [US4] In `scripts/generate_interactive_map.py`'s `main()`, pass
  `config.basemap_url` through to T029's function. The local
  `<RKBY_DATA_DIR>/basemap.pmtiles` file is still validated via T006/T011 first in
  both modes (FR-010) — this task only changes what happens with its bytes afterward.
- [X] T031 [P] [US4] Extend `basemapSource.js`/`main.js`: when `data.basemap.mode ===
  "hosted"`, construct `new pmtiles.PMTiles(data.basemap.url)` (the `pmtiles` package's
  own default `FetchSource`) instead of T015's `BlobSource`-backed instance, then pass
  it to `protomaps-leaflet`'s `leafletLayer({ url })` exactly as in embedded mode
  (research.md §8 — no new dependency, `FetchSource` is already part of the `pmtiles`
  package T001 added).
- [X] T032 [US4] Add tests to `basemapSource.test.js` (or a small extracted
  `selectBasemapSource(basemap, window)`-style helper + its own test) covering
  hosted-vs-embedded mode selection — given `data.basemap`, which `Source`/constructor
  form T031's code should choose.

**Checkpoint**: All four user stories work together. Default runs stay fully embedded
and offline; setting `RKBY_BASEMAP_URL` switches to the hosted, reference-by-URL
variant without touching any other behavior.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and final end-to-end validation across every story.

- [X] T033 [P] Update `README.md`'s "Getting started"/interactive-map section to
  document the new required local input (`<RKBY_DATA_DIR>/basemap.pmtiles`) and the
  optional `RKBY_BASEMAP_URL` env var for hosted mode (contracts/cli-and-env.md).
  Added a new "Running the interactive map generator" section (matching the existing
  per-script doc pattern) rather than only touching "Getting started", since no
  dedicated section existed yet.
- [X] T034 Run `uv run pytest` and (`cd frontend/interactive-map && pnpm install &&
  pnpm test`) to confirm the full automated suite passes end to end after all prior
  phases. 370 Python tests pass (`uv run pytest`), 30 Vitest tests pass
  (`pnpm test`), `uv run ruff check .` clean.
- [X] T035 Manually run `specs/004-pmtiles-basemap/quickstart.md` Scenarios 1–5 end to
  end against real `RKBY_DATA_DIR` data + the provided sample
  `trhharea11poi-stripped.pmtiles` archive (found in the maintainer's Downloads
  folder), confirming SC-001 through SC-005 all hold. Used a headless-Chromium
  (Playwright) harness for the parts a terminal can't observe (network tab, rendered
  canvas, DOM). Scenario 1 (embedded, offline): zero non-`file://` requests, no
  `basemap.jpg`/`tiles/`, basemap + 51 markers render. Scenario 2 (missing/invalid
  file fails fast): covered by T021's automated tests. Scenario 4 (swap archive):
  regenerated cleanly against a differently-scoped archive
  (`trhharea12poi-stripped.pmtiles`), no stale `tiles/`/`basemap.jpg`, new coverage
  renders. Scenario 5 (hosted mode): verified both the success path (a local
  Range-request-capable static server — basemap tiles fetch from that host only,
  zero OSM/member-data requests, canvas renders) and the failure path (an
  unreachable URL) — the latter surfaced a real bug, fixed during this task (see
  below).

  **Bug found and fixed**: spec.md's Story 4 Edge Case requires an unreachable/
  invalid `RKBY_BASEMAP_URL` to degrade only the basemap at view time (markers,
  popups, season controls keep working). The Phase 3/6 implementation instead let
  `pmtilesArchive.getHeader()`'s rejection propagate out of `main()` unhandled,
  aborting marker rendering and the season control entirely. Fixed in `main.js` by
  wrapping the header-fetch/tile-layer/attribution setup in a `try/catch`: on
  failure it logs the error, falls back to fitting the view around the bundled
  members' own lat/lon (no archive header to size against), and uses the default
  OSM attribution text — everything else proceeds unchanged. Re-verified with the
  same Playwright harness: markers, season control, and hover popups all still work
  against a bad `RKBY_BASEMAP_URL`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (deletes code
  US1's new code would otherwise conflict with).
- **User Story 1 (Phase 3)**: Depends on Foundational. This is the feature's core —
  every later story builds on its output (the new `basemap`/`lat`/`lon` schema and
  bundle contents), unlike a typical spec-kit feature where later stories are fully
  independent of earlier ones.
- **User Story 2 (Phase 4)**: Depends on US1 (the early-validation call US1 wires into
  `main()` is what US2 hardens and tests exhaustively). Its own independent test can
  still be run standalone once US1 is done.
- **User Story 3 (Phase 5)**: Depends on US1 (real lat/lon marker positions must exist
  before declutter can be re-pointed at real screen coordinates).
- **User Story 4 (Phase 6)**: Depends on US1 (extends its embed/assemble step with a
  hosted branch). Independent of US2 and US3.
- **Polish (Phase 7)**: Depends on all four user stories being complete.

### Within Each User Story

- Tests are written and confirmed failing before the implementation task that makes
  them pass (Constitution Principle V, Red-Green).
- Backend (Python) and frontend (JS) work within a story can generally proceed in
  parallel — they're independent files coordinated only by the fixed
  `contracts/map-data.schema.json` contract, not by import-time dependencies.

### Parallel Opportunities

- T001 (Setup) and the Foundational deletions (T002/T003) touch disjoint files and
  could be done together, though Foundational logically follows Setup.
- T003 (delete `basemapTiles.js`) is independent of T002/T004 (Python-side deletion).
- Within US1: the frontend chain (T014→T020) can proceed in parallel with the backend
  chain (T005→T013) — different files, coordinated only by the fixed schema contract.
- Within US4: T026/T027 (Python config), T028/T029 (Python bundle), and T031/T032
  (frontend) are three largely independent chains, parallelizable across different
  files.

---

## Parallel Example: User Story 1

```bash
# Backend chain (one developer/session):
Task: "T005 Add failing header-validation tests in test_rkby_interactive_map_bundle.py"
Task: "T006 Implement validate_pmtiles_file in bundle.py"
# ...continues through T013

# Frontend chain (a different developer/session, in parallel):
Task: "T014 Add failing basemapSource.test.js tests"
Task: "T015 Implement basemapSource.js"
Task: "T016 Rewrite main.js's map setup for protomaps-leaflet + real CRS"
# ...continues through T020
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (deletes the old pipeline — CRITICAL, blocks
   everything else).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: run `uv run scripts/generate_interactive_map.py` against a
   real `basemap.pmtiles` and open the resulting `index.html` — confirm the basemap
   renders, pans, and zooms, and members appear at their real positions.

### Incremental Delivery

1. Setup + Foundational → clean slate.
2. Add User Story 1 → validate independently → this is already a usable, shippable
   default build (MVP).
3. Add User Story 2 → validate the fail-fast path independently.
4. Add User Story 3 → validate that no existing interaction regressed.
5. Add User Story 4 → validate the opt-in hosted variant, entirely additive.
6. Polish: docs + full-suite + quickstart validation.

### Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability.
- Commit after each task or logical red-green pair.
- Stop at any checkpoint to validate a story independently before continuing.
