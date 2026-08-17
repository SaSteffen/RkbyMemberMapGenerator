---

description: "Task list for the Interactive Photo Map feature"
---

# Tasks: Interactive Photo Map

**Input**: Design documents from `/specs/003-interactive-photo-map/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
(all present)

**Tests**: Included. plan.md's Testing section and Constitution Principle V (Test-First,
Red-Green) commit to full `pytest` coverage for the Python merge/eligibility/bundling
logic and `vitest` coverage for the four pure client-side functions
(`defaultSeasonLabel`, `isVisible`/`popupData`, `declutterPositions`,
`shouldDefaultToMobile`) — same discipline as 002. Leaflet/DOM wiring in `main.js`
(map bootstrap, season checkboxes, hover popup, drawer, settings panel) is
deliberately left untested per plan.md's Constitution Check, verified instead via
quickstart.md's manual scenarios.

**Organization**: Tasks are grouped by user story (spec.md priorities P1-P5) to enable
independent implementation and testing of each story on top of a shared Foundational
layer (CLI skeleton, cross-season merge, pixel-position math).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1-US5)
- Every task names its exact file path(s)

**A note on [P] and shared files**: `scripts/generate_interactive_map.py`,
`scripts/rkby_interactive_map/bundle.py`,
`frontend/interactive-map/src/main.js`, and
`frontend/interactive-map/src/popupData.js` are each edited by several tasks across
this list (a small SPA's entry point and its one orchestration script naturally
accrete behavior). Tasks that touch the *same* file are listed sequentially and
never marked `[P]`, even when the underlying logic is conceptually independent —
concurrent edits to one file conflict regardless of logical independence.

## Path Conventions

Two-language project, both rooted at the repo root (plan.md § Project Structure):

- **Python** (generation script): `scripts/generate_interactive_map.py`,
  `scripts/rkby_interactive_map/` (new, private package), reusing
  `scripts/rkby_maps/` and `scripts/rkby_records.py` (both existing, unchanged).
  Tests: `tests/unit/`, fixtures: `tests/fixtures/`.
- **Frontend** (the generated SPA's source): `frontend/interactive-map/` — `src/*.js`
  + colocated `src/*.test.js` (Vitest convention), `index.html`, `vite.config.js`,
  `package.json`/`pnpm-lock.yaml` (committed; `dist/`, `node_modules/` are already
  gitignored at the repo root).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold both halves of the project so later tasks have somewhere to add code.

- [X] T001 Create `frontend/interactive-map/package.json` — `name`, `"private": true`,
  `scripts.build` = `"vite build"`, `scripts.test` = `"vitest run"`, dependency
  `leaflet` (^1.9), devDependencies `vite` (^8), `vitest` (^4),
  `vite-plugin-singlefile` (^2.3). Then run `pnpm install` inside
  `frontend/interactive-map/` to generate the committed `pnpm-lock.yaml`
  (research.md §1).
- [X] T002 [P] Create `scripts/rkby_interactive_map/__init__.py` (new, empty —
  internal package private to `generate_interactive_map.py`, plan.md § Project
  Structure).
- [X] T003 [P] Add synthetic multi-season applicant YAML fixtures under
  `tests/fixtures/` for the merge/bundle tests below: at least one `match_key`
  present in two season folders with a different `role`/`additional_roles` (and,
  for Scenario 5 coverage later, a second pair of records sharing one exact
  `address` string) — reuse the existing `nominatim_response_match.json`,
  `osm_tile_fixture.png`, and `sample_photo.jpg` fixtures rather than adding new
  binary fixtures (quickstart.md Prerequisites, Constitution V: synthetic only,
  never real member data).
- [X] T004 Create `frontend/interactive-map/vite.config.js` — `base: "./"` (relative
  asset base) and the `vite-plugin-singlefile` plugin registered so `pnpm run
  build` inlines JS/CSS into a single non-module `dist/index.html`
  (research.md §10; depends on T001's `package.json` declaring the dependency).

**Checkpoint**: Both subprojects exist and install cleanly.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The CLI skeleton, the frontend build wrapper, cross-season merge, and
pixel-position math every user story's implementation sits on top of.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational (write first, confirm they fail)

- [X] T005 [P] `tests/unit/test_generate_interactive_map_cli.py`: missing/invalid
  `RKBY_DATA_DIR` → `ConfigError`, exit code `1`; invoking with any CLI flag/arg is
  rejected or ignored per FR-002 (no season selector, no variant selector — unlike
  `generate_member_maps.py`'s two tuning flags).
- [X] T006 `tests/unit/test_generate_interactive_map_cli.py`: `pnpm` missing from
  `PATH`, `pnpm install --frozen-lockfile` failing, and `pnpm run build` failing
  each produce a non-zero exit and **no** write under `RKBY_DATA_DIR` (mock
  `subprocess.run`; contracts/cli-and-env.md). Same file as T005 — sequential.
- [X] T007 `tests/unit/test_generate_interactive_map_cli.py`: a first run creates
  `<RKBY_DATA_DIR>/interactive_map/` and adds an `interactive_map/` entry to
  `<RKBY_DATA_DIR>/.gitignore`; a second run is idempotent (no duplicate
  `.gitignore` entry, no stale file from the first run left behind). Same file as
  T005/T006 — sequential.
- [X] T008 [P] `tests/unit/test_rkby_interactive_map_merge.py`: per-season-record
  eligibility (drops `excluded`/`ignore`/no-address/ungeocodable-address records,
  logging each skip via the passed-in logger — FR-004/FR-005/SC-007), latest-
  eligible-record tie-break across two seasons for the same `match_key` by season
  label sort order (FR-010), every eligible season-record's own `role`/
  `additional_roles` retained (FR-015), and a person opted out (`excluded`/
  `ignore`) in *every* one of their seasons never appears in the merged output
  (SC-010). Mock geocoding via the same `responses`-registered Nominatim fixtures
  002 already uses.
- [X] T009 [P] `tests/unit/test_rkby_interactive_map_bundle.py`: a pixel-position
  helper produces the same `(x, y)` for the same `(lat, lon)` regardless of call
  order, using one fixed `(center, zoom, canvas_size)` computed from the combined
  bounding box of every merged member across all seasons (research.md §3).

### Implementation for Foundational

- [X] T010 `scripts/generate_interactive_map.py`: `ConfigError`, `Config` dataclass
  (`data_dir: Path`), `load_config()` reading `RKBY_DATA_DIR` (mirrors
  `generate_member_maps.py`'s `load_config`), `build_arg_parser()` with **no**
  flags (FR-002), and a `main()` skeleton returning `0`. Makes T005 pass.
- [X] T011 [P] `scripts/rkby_interactive_map/frontend_build.py`: `build_frontend()` —
  runs `pnpm install --frozen-lockfile` then `pnpm run build` inside
  `frontend/interactive-map/` via `subprocess`; raises a clear error (caught by
  `main()` to produce a non-zero exit, before any `RKBY_DATA_DIR` write) if `pnpm`
  isn't found on `PATH` or either subprocess exits non-zero. Makes T006 pass.
- [X] T012 `scripts/generate_interactive_map.py`: `_ensure_interactive_map_dir()` —
  delete `<RKBY_DATA_DIR>/interactive_map/` if present, recreate it, and add an
  `interactive_map/` entry to `<RKBY_DATA_DIR>/.gitignore` if not already there
  (data-model.md § Local Data Repository "Idempotency"; mirrors
  `generate_member_maps.py`'s `_ensure_output_dirs_and_gitignore`). Called only
  *after* `build_frontend()` succeeds (contracts/cli-and-env.md: pnpm failures are
  checked "before any `RKBY_DATA_DIR` write"). Same file as T010 — sequential.
  Makes T007 pass.
- [X] T013 [P] `scripts/rkby_interactive_map/merge.py`: for each season label, load
  records (`rkby_records.load_existing_records`), filter to `not excluded and not
  ignore`, `geocode_record_if_needed` (fill-empty-only, writing the record back
  via `_dump_record_yaml` exactly like `generate_member_maps.py` does), and
  `logger.warning(...)` + skip any record still missing an address or coordinates
  (FR-004/FR-005); then group every eligible record across *all* seasons by
  `match_key` and, per person, pick the latest-labeled eligible record for
  `first_name`/`last_name`/`num_previous_seasons`/`photo_relative_path`/
  `latitude`/`longitude` (FR-010) while keeping a `{season_label: {role,
  additional_roles}}` map built from *every* eligible season-record for that
  person (FR-009, FR-015). Makes T008 pass.
- [X] T014 [P] `scripts/rkby_interactive_map/bundle.py`: `compute_positions(merged_members)`
  — combined bounding box across every merged member's `(latitude, longitude)` via
  `scripts.rkby_maps.basemap.zoom_for_bounding_box`, then each member's `x`/`y` via
  `scripts.rkby_maps.basemap.lonlat_to_pixel` at that one resulting
  `(center, zoom, canvas_size)` (research.md §3). Makes T009 pass.

**Checkpoint**: Foundation ready — config/CLI skeleton, frontend build wrapper,
cross-season merge, and pixel-position math are all in place and tested.

---

## Phase 3: User Story 1 - Explore the current season on one navigable map (Priority: P1) 🎯 MVP

**Goal**: One `uv run scripts/generate_interactive_map.py` produces the single
artifact; opening `index.html` shows every eligible member of the FR-007 default
season positioned at their address over the basemap image, with scroll-zoom,
click-drag pan, and on-screen zoom/pan buttons all working.

**Independent Test**: quickstart.md Scenario 1 (generate) + relevant parts of
Scenario 3 (default season on first load) — confirm the default season's members
appear at correct positions and every pan/zoom mechanism works.

### Tests for User Story 1 (write first, confirm they fail)

- [X] T015 [P] [US1] Extend `tests/unit/test_rkby_interactive_map_bundle.py`: the
  assembled `map-data.js` payload validates against
  `specs/003-interactive-photo-map/contracts/map-data.schema.json`; each merged
  member's photo (or `photos/placeholder.png`) is copied into
  `interactive_map/photos/`; re-running the generator against a changed data set
  leaves no stale file from the previous run (data-model.md "Idempotency").
- [X] T016 [P] [US1] `frontend/interactive-map/src/defaultSeason.test.js`: July 31 vs.
  August 1 boundary, a year rollover, and falling back to the lexicographically-
  greatest bundled season label when the computed one isn't present (FR-007, Edge
  Cases) — against the not-yet-existing `defaultSeason.js`.
- [X] T017 [P] [US1] `frontend/interactive-map/src/declutter.test.js`: members sharing
  an exactly-equal precomputed `(x, y)` get a small fixed offset applied so each
  stays independently placeable; members at merely-nearby (non-identical)
  positions are left untouched (FR-021, Edge Cases) — against the not-yet-existing
  `declutter.js`.

### Implementation for User Story 1

- [X] T018 [US1] `scripts/rkby_interactive_map/bundle.py`: `assemble_map_data(...)` —
  build the `{seasons, members[], image}` payload matching
  `map-data.schema.json` from `merge.py`'s merged members and
  `compute_positions()` (T014), and write `window.RKBY_MAP_DATA = {...};` to
  `<RKBY_DATA_DIR>/interactive_map/map-data.js`.
- [X] T019 [US1] `bundle.py`: `generate_basemap(...)` — render
  `interactive_map/basemap.jpg` via `scripts.rkby_maps.basemap.stitch_basemap` at
  the same combined `(center, zoom, canvas_size)` `compute_positions()` used,
  reusing `<RKBY_DATA_DIR>/.tile_cache/`. Same file as T018 — sequential.
- [X] T020 [US1] `bundle.py`: `copy_assets(...)` — copy each merged member's own photo
  file (from its season folder) into `interactive_map/photos/<match_key>.<ext>`,
  or `scripts/rkby_maps/assets/rynke.png` into `interactive_map/photos/
  placeholder.png` when none is on file (research.md §9); copy
  `frontend/interactive-map/dist/index.html` verbatim into
  `interactive_map/index.html`. Same file as T018/T019 — sequential. Makes T015
  pass.
- [X] T021 [US1] Wire `scripts/generate_interactive_map.py main()`: `load_config()` →
  `frontend_build.build_frontend()` (T011) → `_ensure_interactive_map_dir()`
  (T012) → `discover_seasons()` + per-season `setup_run_logger()` (mirrors
  `generate_member_maps.py`'s loop) → `merge.py`'s merge (T013) → `bundle.py`'s
  `assemble_map_data`/`generate_basemap`/`copy_assets` (T018-T020) →
  `rkby_records.auto_commit()` for `seasons/*/applicants` + `.gitignore` (never
  `interactive_map/` itself, contracts/cli-and-env.md) → `return 0`. Same file as
  T010/T012 — sequential.
- [X] T022 [P] [US1] `frontend/interactive-map/src/defaultSeason.js`:
  `defaultSeasonLabel(date)` ported from `scrape_applicants.default_season_label`
  (Jan-Jul → previous August's season, Aug-Dec → this August's season), plus a
  fallback to the greatest bundled season label when the computed one is absent
  from `map-data.js`'s `seasons` list (FR-007, Edge Cases). Makes T016 pass.
- [X] T023 [P] [US1] `frontend/interactive-map/src/declutter.js`:
  `declutterPositions(members)` — groups members by exactly-equal `(x, y)` and
  applies a small fixed horizontal pixel offset within any group of 2+ (FR-021,
  research.md §7). Makes T017 pass.
- [X] T024 [US1] `frontend/interactive-map/index.html`: entry template with
  `<script src="./map-data.js"></script>` loaded *before* the bundled app script
  (research.md §10, never `fetch()`); `frontend/interactive-map/src/styles.css`:
  base map/marker layout (circular photo markers via `border-radius: 50%;
  object-fit: cover`).
- [X] T025 [US1] `frontend/interactive-map/src/main.js`: Leaflet bootstrap —
  `L.CRS.Simple` map, `L.imageOverlay("basemap.jpg", bounds)` sized from
  `window.RKBY_MAP_DATA.image.width`/`.height` (research.md §3).
- [X] T026 [US1] `main.js`: render one circular photo marker per member at its
  (`declutterPositions`-adjusted, T023) `x`/`y`, filtered to members visible in
  the `defaultSeasonLabel()` (T022) season. Same file as T025 — sequential.
- [X] T027 [US1] `main.js`: confirm/enable Leaflet's default mouse scroll-zoom
  (centered on the cursor) and click-and-drag pan (FR-013). Same file as
  T025/T026 — sequential.
- [X] T028 [US1] `main.js`: on-screen zoom-in/zoom-out via Leaflet's built-in
  `zoomControl`, plus a small custom four-direction pan control calling
  `map.panBy([dx, dy])` (FR-014, research.md §8). Same file — sequential.
- [X] T029 [US1] `main.js`: `attributionControl` set to `"© OpenStreetMap
  contributors"`, always visible bottom-right, never behind a toggle (FR-022,
  research.md §8). Same file — sequential.

**Checkpoint**: `uv run scripts/generate_interactive_map.py`, then open
`interactive_map/index.html` — the default season's members appear at correct
positions; scroll/drag and the on-screen buttons pan and zoom; overlapping-but-
distinct members separate on zoom; identical-address members stay individually
placeable. MVP complete.

---

## Phase 4: User Story 2 - Bring other seasons into view (Priority: P2)

**Goal**: One checkbox per season, any combination active at once; toggling updates
visible members immediately, with cross-season duplicates already collapsed to one
marker by `merge.py` (Foundational).

**Independent Test**: quickstart.md Scenario 3 — toggle a second season on, confirm
its members appear without reload and a person eligible in both shows once; toggle
every season off, confirm an empty (not erroring) map.

### Tests for User Story 2 (write first, confirm it fails)

- [ ] T030 [P] [US2] `frontend/interactive-map/src/popupData.test.js`:
  `isVisible(member, activeSeasons)` is `true` iff at least one key of
  `member.seasons` is in `activeSeasons`, `false` otherwise (FR-006) — against the
  not-yet-existing `popupData.js`.

### Implementation for User Story 2

- [ ] T031 [US2] `frontend/interactive-map/src/popupData.js`:
  `isVisible(member, activeSeasons)` pure function. Makes T030 pass.
- [ ] T032 [US2] `main.js`: one checkbox/toggle per entry in `map-data.js`'s
  `seasons` list, rendered directly on the map (desktop) — including a season
  with zero eligible members, still present and selectable (Edge Cases). Same
  file as US1's `main.js` edits — sequential.
- [ ] T033 [US2] `main.js`: wire checkbox state changes to `isVisible()` (T031) +
  Leaflet `LayerGroup.addLayer`/`removeLayer`, re-syncing visible markers
  immediately with no reload (FR-008); zero active seasons shows an empty map, not
  an error (Edge Cases). Same file — sequential.
- [ ] T034 [US2] `main.js`: on load, activate exactly the `defaultSeasonLabel()`
  (or its fallback, T022) season as the sole initially-checked control (FR-007),
  every other season control present but unchecked. Same file — sequential.

**Checkpoint**: Toggling any combination of seasons updates visible members
immediately; a person eligible in 2+ active seasons still renders as exactly one
marker (guaranteed by `merge.py`, T013).

---

## Phase 5: User Story 3 - Identify a member by hovering their photo (Priority: P3)

**Goal**: Hovering a marker shows name, previous-season count, and one role entry
per currently-active season that member belongs to; closes on mouseout.

**Independent Test**: quickstart.md Scenario 4 — with two seasons active for a member
who has different roles in each, hover shows two role entries; deactivating one
season live-updates the popup to one entry.

### Tests for User Story 3 (write first, confirm it fails)

- [ ] T035 [P] [US3] Extend `frontend/interactive-map/src/popupData.test.js`:
  `popupData(member, activeSeasons)` returns `{name, numPreviousSeasons, seasons:
  [...]}` restricted to the currently-active seasons the member belongs to, sorted
  by season label; `numPreviousSeasons` passes through as `null` when not on file
  (FR-015/FR-016) — against the not-yet-existing `popupData()`.

### Implementation for User Story 3

- [ ] T036 [US3] `popupData.js`: `popupData(member, activeSeasons)` — `{name,
  numPreviousSeasons, seasons: [{label, role, additionalRoles}, ...]}`. Same file
  as T031 — sequential. Makes T035 pass.
- [ ] T037 [US3] `main.js`: bind a Leaflet hover popup per marker — `mouseover`
  renders `popupData()`'s result (name + previous-seasons count with an explicit
  "unknown" label when `null`, one role entry per active season — FR-015/FR-016),
  `mouseout` closes it (FR-015). Same file as US1/US2's `main.js` edits —
  sequential.

**Checkpoint**: Hovering a member active in 2 seasons shows 2 role entries;
deactivating one season live-updates the popup to 1; moving the cursor off closes
it; a missing data point shows as "unknown", not blank or broken.

---

## Phase 6: User Story 4 - Share the map as a self-contained folder (Priority: P4)

**Goal**: The generated `interactive_map/` folder works fully offline in a standard
current browser, with nothing to install, build, or reconfigure.

**Independent Test**: quickstart.md Scenario 2 — copy the folder to a machine/profile
with networking disabled, open `index.html` in two different browsers, confirm zero
network requests and every US1-3 interaction still works.

### Tests for User Story 4 (write first, confirm it fails)

- [ ] T038 [P] [US4] Extend `tests/unit/test_rkby_interactive_map_bundle.py`: the
  copied `interactive_map/index.html` contains neither `"fetch("` nor
  `'type="module"'` (regression guard for research.md §10's `file://`
  compatibility constraints).

### Implementation for User Story 4

- [ ] T039 [US4] Audit `frontend/interactive-map/dist/index.html` (built via T001/
  T004/T011's config) against T038: confirm the single-file non-module bundle and
  that every emitted asset URL is relative to `index.html`'s own folder; fix
  `vite.config.js` if either check fails. Makes T038 pass.
- [ ] T040 [US4] Manual validation — quickstart.md Scenario 2: copy
  `interactive_map/` to a machine/profile with networking disabled, open
  `index.html` in Chrome and Firefox, confirm zero pending/failed requests in each
  browser's Network tab and that pan, zoom, buttons, season toggles, and hover
  popups all work exactly as they do online.

**Checkpoint**: The shared folder works fully offline in two different browsers, no
reconfiguration needed.

---

## Phase 7: User Story 5 - View and interact with the map from a mobile phone (Priority: P5)

**Goal**: Narrow-viewport/touch-primary contexts default to a tap-to-open bottom
drawer and a settings-housed season selector instead of hover popups and inline
checkboxes; a settings control can switch modes either way at any time.

**Independent Test**: quickstart.md Scenario 7 — simulate a phone-sized touch
viewport, confirm mobile mode is default, tap-drawer works and switches content
live, settings control switches modes both ways, resizing alone never silently
changes the active mode.

### Tests for User Story 5 (write first, confirm it fails)

- [ ] T041 [P] [US5] `frontend/interactive-map/src/mode.test.js`:
  `shouldDefaultToMobile(viewportWidth, isCoarsePointer)` — narrow viewport → true,
  coarse pointer → true (regardless of width), wide viewport + fine pointer →
  false, and the exact boundary at `BREAKPOINT_PX` (FR-023) — against the
  not-yet-existing `mode.js`.

### Implementation for User Story 5

- [ ] T042 [US5] `frontend/interactive-map/src/mode.js`:
  `shouldDefaultToMobile(viewportWidth, isCoarsePointer)` =
  `viewportWidth < BREAKPOINT_PX || isCoarsePointer`. Makes T041 pass.
- [ ] T043 [US5] `main.js`: call `shouldDefaultToMobile(window.innerWidth,
  window.matchMedia("(pointer: coarse)").matches)` once at startup, store the
  result in one in-memory mode variable; no `resize`/`orientationchange` listener
  ever re-runs it (FR-023, Edge Cases). Same file as prior `main.js` edits —
  sequential.
- [ ] T044 [US5] `main.js` + `frontend/interactive-map/src/styles.css`:
  settings-panel control (e.g. a gear icon, toggled open/closed) — always houses
  the mode switch; houses the season checkboxes (T032) too, but only while
  currently in mobile mode (FR-027); desktop mode keeps checkboxes inline on the
  map as already built in US2. Same file as prior `main.js` edits — sequential.
- [ ] T045 [US5] `main.js` + `styles.css`: bottom-sheet drawer (`position: fixed;
  bottom: 0; max-height: 50vh; overflow-y: auto;`) with its own close control and
  a full-viewport transparent backdrop; while in mobile mode, tapping a marker
  renders `popupData()`'s (T036) result into the drawer instead of opening the
  desktop hover popup (FR-025). Same file — sequential.
- [ ] T046 [US5] `main.js`: tapping a different marker while the drawer is open
  re-renders its content in place, no dismiss-then-reopen required (FR-026);
  tapping the close control or the backdrop closes the drawer (FR-026). Same file
  — sequential.
- [ ] T047 [US5] `main.js`: the settings-panel mode switch flips between
  desktop/mobile at any time; a manual choice holds for the rest of that page load
  and is never overridden by re-running `shouldDefaultToMobile()` (FR-024). Same
  file — sequential.

**Checkpoint**: quickstart.md Scenario 7 passes end to end. Every US1-US3 interaction
(pan, zoom, on-screen buttons, season selection, member identification) remains
reachable in mobile mode, adapted for touch where hover doesn't apply (FR-028) —
already true by construction of T044-T047 reusing T028/T032/T036 rather than
duplicating them.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Repo-wide verification and documentation once every story is built.

- [ ] T048 [P] Run `uv run ruff check .` and `uv run ruff format .` — confirm
  `scripts/generate_interactive_map.py` and `scripts/rkby_interactive_map/` are
  clean.
- [ ] T049 [P] Run `uv run pytest` and (`cd frontend/interactive-map && pnpm
  install && pnpm test`) — confirm every automated suite passes, entirely offline
  (Constitution V).
- [ ] T050 [P] `README.md`: add a "Running the interactive map generator" section
  documenting `scripts/generate_interactive_map.py`, its Node/pnpm prerequisite,
  and the `interactive_map/` output folder — matching the existing "Running the map
  generator" section's style.
- [ ] T051 Execute quickstart.md Scenarios 1, 3, 5, and 6 end-to-end against a
  throwaway synthetic `RKBY_DATA_DIR` (first-run artifact contents, default-season
  fallback when the computed season isn't present in the bundled data,
  identical-address decluttering, and idempotent re-run after a local data edit).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS every user story.
- **User Stories (Phase 3-7)**: All depend on Foundational. Functionally
  independent per spec.md (each has its own Independent Test), but this
  implementation concentrates UI wiring in one `main.js` and shared data-shaping
  in one `popupData.js`, so **implement them in priority order (US1 → US2 → US3 →
  US4 → US5) rather than in parallel** — see the file-sharing note under Format
  above. US4 (Story 4) is mostly a verification pass on top of Setup/US1's build
  config rather than new UI code, so it can slot in any time after US1.
- **Polish (Phase 8)**: Depends on every user story you intend to ship being
  complete.

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational. The MVP.
- **US2 (P2)**: Depends on Foundational + US1 (`main.js`'s marker-rendering loop
  and `defaultSeasonLabel()` already exist to filter/toggle against).
- **US3 (P3)**: Depends on Foundational + US1 (marker hover target) + US2
  (`isVisible`'s sibling `popupData` needs the same active-season-set concept
  US2 introduced).
- **US4 (P4)**: Depends on Setup/Foundational's build config (T001/T004/T011) and
  US1 producing a real artifact to test against; otherwise independent of
  US2/US3/US5.
- **US5 (P5)**: Depends on US1 (markers/panels to adapt), US2 (season checkboxes
  it relocates into settings), and US3 (`popupData()` it reuses for the drawer).

### Within Each User Story

- Tests MUST be written and confirmed failing before their corresponding
  implementation task.
- Pure logic modules (`defaultSeason.js`, `declutter.js`, `popupData.js`,
  `mode.js`) before the `main.js` wiring that calls them.
- Python bundling (`bundle.py`) and CLI wiring before any frontend task that reads
  its output.

### Parallel Opportunities

- All Setup tasks marked `[P]` (T002, T003) can run alongside T001.
- Within Foundational, the four independent modules — CLI/config (T005-T007,
  T010, T012), `frontend_build.py` (T006, T011), `merge.py` (T008, T013), and
  `bundle.py`'s `compute_positions` (T009, T014) — can be built in parallel by
  different people; only tasks sharing a file (T005/T006/T007 all extend the same
  test file; T010/T012 both edit `generate_interactive_map.py`) must stay
  sequential.
- Within US1, the three "Tests" tasks (T015-T017) are mutually parallel, as are
  their matching pure-logic implementations (T022 `defaultSeason.js`, T023
  `declutter.js`) — but `bundle.py`'s three functions (T018-T020) and every
  `main.js` task (T024-T029) share one file each and must stay sequential.

---

## Parallel Example: Foundational

```bash
# Launch the four independent Foundational test tasks together:
Task: "tests/unit/test_generate_interactive_map_cli.py: missing/invalid RKBY_DATA_DIR"
Task: "tests/unit/test_rkby_interactive_map_merge.py: eligibility + latest-record tie-break"
Task: "tests/unit/test_rkby_interactive_map_bundle.py: compute_positions() determinism"

# Then their independent implementations:
Task: "scripts/rkby_interactive_map/frontend_build.py: build_frontend()"
Task: "scripts/rkby_interactive_map/merge.py: cross-season eligibility + merge"
Task: "scripts/rkby_interactive_map/bundle.py: compute_positions()"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (blocks everything).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: run quickstart.md Scenario 1 + the pan/zoom parts of
   Scenario 3 against a throwaway synthetic `RKBY_DATA_DIR`.
5. Demo: a self-generated, pannable/zoomable photo map of the current season.

### Incremental Delivery

1. Setup + Foundational → generation pipeline exists, nothing to look at yet.
2. + US1 → MVP: one navigable map of the current season. **Demo-able.**
3. + US2 → multi-season toggling, cross-season dedup visible.
4. + US3 → hover popups with per-season role history.
5. + US4 → verified to survive being shared and opened with no network.
6. + US5 → usable on a phone.
7. Polish → lint/format/docs pass, full quickstart re-run.

Each increment adds value without breaking the previous one, since every later
story only *adds* to `main.js`'s behavior rather than changing US1's already-built
rendering path.
