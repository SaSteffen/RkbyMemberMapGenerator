---

description: "Task list template for feature implementation"
---

# Tasks: Member Map Generator

**Input**: Design documents from `/specs/002-map-generator/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
(all present and read)

**Tests**: Included and REQUIRED — constitution Principle V (Test-First Development,
NON-NEGOTIABLE) mandates a failing test before implementation for all new functionality
in this repo; every implementation task below has a preceding failing-test task it makes
pass.

**Organization**: Tasks are grouped by user story (spec.md's US1/US2/US3, priority
order) so each can be implemented and independently tested.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unfinished dependency)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact and relative to the repository root

## Path Conventions

Single-script layout per Constitution II (see plan.md § Project Structure):
`scripts/generate_member_maps.py` (new CLI entrypoint), `scripts/rkby_records.py` (new
shared module), `scripts/rkby_maps/` (new internal package: `geocoding.py`,
`basemap.py`, `clustering.py`, `rendering.py`), `scripts/scrape_applicants.py`
(refactored, not rewritten), `scripts/schemas/applicant_record.schema.json` (extended
in place). Tests under `tests/unit/`, fixtures under `tests/fixtures/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding this feature needs before any code is written.

- [ ] T001 Add `Pillow` as a runtime dependency in `pyproject.toml` (`[project.dependencies]`) and run `uv sync` — first new runtime dependency this feature introduces (plan.md § Technical Context)
- [ ] T002 [P] Create the new internal package `scripts/rkby_maps/__init__.py` (empty) per plan.md § Project Structure
- [ ] T003 [P] Add synthetic test fixtures used across this feature's tests: `tests/fixtures/nominatim_response_match.json`, `tests/fixtures/nominatim_response_no_match.json`, `tests/fixtures/osm_tile_fixture.png` (tiny valid PNG), `tests/fixtures/sample_photo.jpg` (small synthetic photo) — never real member data (Constitution I/V)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infrastructure shared identically by all three user stories (schema, shared
record I/O, geocoding client, basemap/projection, CLI skeleton) — none of it is an
independently-testable "story" on its own, but every story needs all of it.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T004 Extend `scripts/schemas/applicant_record.schema.json` with the `latitude`/`longitude` fields exactly as specified in `specs/002-map-generator/contracts/applicant-record.schema.json` (nullable number, `-90..90` / `-180..180` bounds, `additionalProperties: false`-safe)
- [ ] T005 [P] Write failing tests in `tests/unit/test_rkby_records.py` for the shared module's extracted functions (`season_dir`, `applicants_dir`, `photos_dir`, `logs_dir`, `load_schema`, `validate_record`, `load_existing_records`, `_dump_record_yaml`, `normalize_name`, `setup_run_logger`) plus the new `discover_seasons(data_dir) -> list[str]` and a generalized `auto_commit(data_dir, paths, message, logger)` helper (research.md §10, §12)
- [ ] T006 Extract the functions listed in T005 from `scripts/scrape_applicants.py` into new `scripts/rkby_records.py`; generalize `auto_commit_season`'s `_run_git`/`_is_git_work_tree`/commit logic into the reusable `auto_commit()`; add `discover_seasons()`; refactor `scripts/scrape_applicants.py` to import and re-export the moved names so its own behavior and its existing test suite (`test_records.py`, `test_season.py`, `test_rollback.py`, `test_auto_commit.py`, `test_logging.py`, `test_schema_validation.py`) keep passing unmodified — makes T005 pass (research.md §10)
- [ ] T007 [P] Write failing tests in `tests/unit/test_geocoding.py` for a Nominatim client: successful match, no-match, HTTP/network error, 1 request/second throttling, that an address with already-cached coordinates is never re-requested, and that a record pre-seeded with a hand-corrected (even implausible-looking) `latitude`/`longitude` is left byte-for-byte untouched by a run — the fill-empty-only guarantee never overwrites a human correction, per Constitution Principle III (research.md §3, §11) — mock HTTP via `responses` and `tests/fixtures/nominatim_response_match.json` / `nominatim_response_no_match.json`
- [ ] T008 Implement `scripts/rkby_maps/geocoding.py`: a minimal `requests`-based Nominatim client (`https://nominatim.openstreetmap.org/search`, address text only as `q`, custom identifying `User-Agent`, 1 req/sec throttle) and a fill-empty-only cache-write helper — makes T007 pass (research.md §3, §11)
- [ ] T009 [P] Write failing tests in `tests/unit/test_basemap.py` for Web Mercator projection (lon/lat → pixel at a given center/zoom), meters-per-pixel at a given zoom/latitude, zoom-from-required-width selection, and OSM tile fetch/on-disk-cache/stitch — mock HTTP via `responses` and `tests/fixtures/osm_tile_fixture.png` (research.md §1, §2, §5, §6)
- [ ] T010 Implement `scripts/rkby_maps/basemap.py`: Web Mercator projection math, meters-per-pixel, zoom-from-width selection, and tile fetch/`<RKBY_DATA_DIR>/.tile_cache/`-persistence/stitch-to-canvas with a custom `User-Agent` — makes T009 pass (research.md §1, §2)
- [ ] T011 [P] Write failing tests in `tests/unit/test_generate_member_maps_cli.py` for CLI arg parsing (`--min-width-km` positive number, default `50`; `--no-scale-bar` flag, default off; no other switches), config loading (`RKBY_DATA_DIR` required and must exist; no intranet credentials needed), and output-folder bootstrapping (a run creates `maps/` and `.tile_cache/` under `RKBY_DATA_DIR` if absent, and creates/updates the data-dir `.gitignore` to ignore both, before any map file is written) (contracts/cli-and-env.md, FR-017)
- [ ] T012 Implement `scripts/generate_member_maps.py` skeleton: `Config`/`load_config`, `build_arg_parser`, per-season logger setup (reusing `rkby_records.setup_run_logger`), `maps/` + `.tile_cache/` folder creation, top-level data-dir `.gitignore` creation/update so both are ignored before any file is written, and a `main()` that discovers every season via `rkby_records.discover_seasons` and loops over them doing nothing yet — makes T011 pass (research.md §12, FR-017)

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - See where everyone lives on a pin map (Priority: P1) 🎯 MVP

**Goal**: One overview pin-map PNG per season, one role-colored pin per member with a
resolvable address, scale bar bottom-right, missing/unresolvable addresses logged and
skipped without stopping the run.

**Independent Test**: Run `uv run scripts/generate_member_maps.py` against a season
folder with members across several roles; confirm one overview pin-map PNG is produced,
prefixed with the season label, each pin colored by role, with a scale bar in the
bottom-right corner, and any member with no address is named in the run's log.

### Tests for User Story 1 ⚠️

- [ ] T013 [P] [US1] Write failing tests in `tests/unit/test_rendering.py` for role→color mapping (research.md §7's 4-color table, case-insensitive role match, neutral color for unset/unrecognized role), filled-circle pin drawing, scale-bar (ruler) rendering in the bottom-right corner (suppressible), and attribution text in the bottom-left corner (always present) — pixel-level asserts on a small deterministic canvas
- [ ] T014 [P] [US1] Write a failing end-to-end test in `tests/unit/test_generate_member_maps_cli.py` using a synthetic season fixture (mocked Nominatim + tile HTTP via `responses`): running the script produces `maps/<season>_overview_pins.png` with one pin per eligible geocodable member colored by role, a member with no address is logged and skipped (run still exits `0`), a member whose record already has cached `latitude`/`longitude` is never re-geocoded, and a member flagged `excluded` or `ignore` has no pin on the map at all (not even logged as skipped)

### Implementation for User Story 1

- [ ] T015 [US1] Implement in `scripts/rkby_maps/rendering.py`: role→color mapping, filled-circle pin drawing, scale-bar (ruler) drawing derived from `basemap`'s meters-per-pixel, and OSM attribution text drawing — makes T013 pass
- [ ] T016 [US1] Implement per-season pin-map orchestration in `scripts/generate_member_maps.py`: eligibility filter (`excluded == false`, `ignore == false`, non-null `address`), fill-empty-only geocode-and-cache each eligible member still missing `latitude`/`longitude` via `rkby_maps.geocoding` (writing back to the season's YAML record), log-and-skip members with no or unresolvable address (FR-006), compute the overview map's center/zoom from `--min-width-km`, fetch+stitch the basemap, draw pins + scale bar (unless `--no-scale-bar`) + attribution, write `maps/<season>_overview_pins.png` — makes T014 pass
- [ ] T017 [US1] Wire idempotent regeneration into `generate_member_maps.py`: before writing a season's fresh map set, delete any existing `maps/<season_label>_*.png` files for that season (data-model.md § Local Data Repository "Idempotency")
- [ ] T018 [US1] Wire auto-commit into `generate_member_maps.py`'s `main()`: after a successful run, call `rkby_records.auto_commit` scoped to `seasons/*/applicants` (newly-cached lat/lon) and the top-level `.gitignore`, logging (not raising) on commit failure, no-op if `RKBY_DATA_DIR` isn't a git work tree (research.md §12, contracts/cli-and-env.md § Auto-commit behavior)

**Checkpoint**: User Story 1 is fully functional and independently testable — this is
the MVP.

---

## Phase 4: User Story 2 - See everyone's face on a photo map (Priority: P2)

**Goal**: A second overview PNG per season showing each geocoded, photographed member
as a circular cropped photo at their address instead of a pin.

**Independent Test**: Run the generator and confirm a second overview PNG per season
where each geocoded member with a photo on file is rendered as a circular cropped
photo; a member with an address but no photo is logged and skipped from this variant
only (still present on the pin map).

### Tests for User Story 2 ⚠️

- [ ] T019 [P] [US2] Write failing tests in `tests/unit/test_rendering.py` for circular photo cropping (centered square crop of the source image, resize to target diameter, circle mask) using `tests/fixtures/sample_photo.jpg`
- [ ] T020 [P] [US2] Extend `tests/unit/test_generate_member_maps_cli.py` with a failing test: running the script produces `maps/<season>_overview_photos.png` with a circular cropped photo per eligible photographed member at the same position their pin would occupy; a member with an address but no photo is logged and skipped from the photo map only, and still appears on `overview_pins.png`

### Implementation for User Story 2

- [ ] T021 [US2] Implement circular photo cropping (centered square crop, resize, circle mask via `ImageDraw.ellipse` alpha mask + `Image.composite`) in `scripts/rkby_maps/rendering.py` — makes T019 pass
- [ ] T022 [US2] Implement per-season photo-map orchestration in `scripts/generate_member_maps.py`: reuse US1's eligibility filter plus a "photo file exists" check, log-and-skip eligible-but-photo-less members from this variant only (FR-006), draw photo circles at each member's projected position + scale bar + attribution, write `maps/<season>_overview_photos.png` — makes T020 pass

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Zoom into crowded areas with detail maps (Priority: P3)

**Goal**: Detect marker groups that would visually overlap on a given map and spawn
additional zoomed-in detail maps that resolve them, down to the configured minimum
width, falling back to a merged/offset rendering where even that can't fully separate a
group — with the FR-014 same-exact-address exception never getting its own detail map.

**Independent Test**: Run the generator against a data set with three or more members
in one town whose overview-scale markers would overlap; confirm additional detail-map
PNGs are produced, zoomed in enough that the cluster's members are individually
distinguishable, while the overview map still shows a readable stand-in for the group.
Separately, confirm two members sharing one exact address never get their own detail
map.

### Tests for User Story 3 ⚠️

- [ ] T023 [P] [US3] Write failing tests in `tests/unit/test_clustering.py` for overlap detection: build a graph with an edge between any two members whose projected pixel distance is less than the sum of their marker radii, connected components ≥ 2 are overlap groups, computed independently per variant (pin radius vs. photo-circle radius) (FR-011, research.md §4)
- [ ] T024 [P] [US3] Extend `tests/unit/test_clustering.py` with failing tests for the FR-014 same-exact-address-pair short-circuit (an overlap group of exactly two members with an identical `address` string is never treated as detail-map-worthy) and the detail-map filename slug derivation (city-token extraction from a cluster member's cached `address` text + `normalize_name` + `_2`/`_3` collision suffixing) (FR-014, research.md §9)
- [ ] T025 [P] [US3] Write failing tests in `tests/unit/test_basemap.py` for detail-map sizing: bounding box + fixed padding around a group's members → required covered width in km → snapped to the tightest integer zoom level whose resulting width is still ≥ `max(min_width_km, required_width)` (research.md §5)
- [ ] T026 [P] [US3] Write failing tests in `tests/unit/test_rendering.py` for FR-013 fallback rendering: a single merged pin with a numeric multiplicity badge (shared role color if the group is single-role, else the neutral "unrecognized" color) for the pin variant, and photo circles horizontally offset by 60% of the circle diameter per additional member (not stacked) for the photo variant (research.md §8)
- [ ] T027 [P] [US3] Write a failing end-to-end test in `tests/unit/test_generate_member_maps_cli.py` using a synthetic season fixture with a 3+-member cluster (mocked Nominatim + tile HTTP via `responses`): running the script additionally produces one or more `maps/<season>_detail_<variant>_<slug>.png` files (correct filename grammar per contracts/map-output.md), zoomed in enough that no two of that cluster's markers overlap on them — or, for any pair still overlapping at `--min-width-km`, that the FR-013 fallback is used instead of a further detail map; and, separately, that a two-member group sharing one exact address never gets its own detail map (FR-014), for both the pin and photo variants

### Implementation for User Story 3

- [ ] T028 [US3] Implement overlap-graph/connected-components clustering (per-variant marker radii) and the FR-014 same-address-pair short-circuit in `scripts/rkby_maps/clustering.py` — makes T023/T024's clustering tests pass
- [ ] T029 [US3] Implement the detail-map filename slug derivation (city-token extraction + `normalize_name` + collision suffixing) in `scripts/rkby_maps/clustering.py` — makes T024's slug tests pass
- [ ] T030 [US3] Implement detail-map bounding-box sizing + integer-zoom selection in `scripts/rkby_maps/basemap.py` — makes T025 pass
- [ ] T031 [US3] Implement FR-013 fallback rendering (merged pin + multiplicity badge; offset photo-circle stack) in `scripts/rkby_maps/rendering.py` — makes T026 pass
- [ ] T032 [US3] Wire cluster detection + detail-map generation + fallback rendering into `generate_member_maps.py`'s per-season, per-variant orchestration: for every overlap group that isn't the FR-014 exception, render a detail map at the size from T030, re-run the T028 overlap check against that render, and apply the T031 fallback to any pair still overlapping instead of recursing into a further detail map; verify the T017 idempotent-regeneration cleanup (`maps/<season_label>_*.png` glob-delete-then-regenerate) also removes stale detail-map files for clusters that no longer exist — makes T027 pass

**Checkpoint**: All three user stories are independently functional — feature complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Bring documentation and the full test/lint suite in line with the now-complete feature.

- [ ] T033 [P] Update `README.md`'s script status/usage section: rename the `scripts/generate_map.py` reference to `scripts/generate_member_maps.py`, add its usage snippet (`--min-width-km`, `--no-scale-bar`), and mark it implemented alongside the scraper
- [ ] T034 [P] Walk through `specs/002-map-generator/quickstart.md` Scenarios 1–6 end-to-end against a throwaway synthetic `RKBY_DATA_DIR` (never real member data) and confirm every documented "Expect" holds
- [ ] T035 Run `uv run ruff check .`, `uv run ruff format .`, and `uv run pytest` for the full suite; fix any lint/format/test failures before considering the feature done

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. T006 depends on T005; T008 depends on
  T007; T010 depends on T009; T012 depends on T006 and T011. **Blocks all user
  stories.**
- **User Stories (Phase 3-5)**: All depend on Foundational completion.
  - US1 (P1): No dependency on US2/US3.
  - US2 (P2): Builds on US1's eligibility filter and render/write plumbing
    (`generate_member_maps.py`, `rendering.py`) — implement after US1 in practice, even
    though its own tests (T019/T020) don't require US1's tests to exist first.
  - US3 (P3): Builds on both variants' rendering paths existing (it adds detail maps
    *for* each variant) — implement after US1 and US2.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Failing tests (T0xx marked ⚠️ section) are written and confirmed failing before their
  matching implementation task.
- Rendering primitives before orchestration wiring (e.g., T015 before T016).
- Story complete (checkpoint) before moving to the next priority.

### Parallel Opportunities

- T002 and T003 (Setup) run in parallel — different files.
- Within Foundational: T005, T007, T009, T011 (all test-writing tasks, four different
  files) can run in parallel; each one's matching implementation task (T006/T008/T010/
  T012) must wait for its own test task but not for the others.
- Within US1: T013 and T014 (different files) run in parallel.
- Within US2: T019 and T020 (different files) run in parallel.
- Within US3: T023, T024, T025, T026, T027 (test tasks across `test_clustering.py`,
  `test_basemap.py`, `test_rendering.py`, `test_generate_member_maps_cli.py` — four
  distinct files) run in parallel; their implementation tasks (T028-T032) are mostly
  sequential — T028/T029 share `clustering.py`, T030 shares `basemap.py` with prior
  foundational work, T031 shares `rendering.py` with prior US1/US2 work, and T032
  (the orchestration wiring, `generate_member_maps.py`) depends on T028, T030, and T031
  all being done.
- T033 and T034 (Polish) run in parallel — different concerns, no shared file.

---

## Parallel Example: Foundational Phase

```bash
# Launch all four Foundational test-writing tasks together:
Task: "Write failing tests in tests/unit/test_rkby_records.py for discover_seasons + extracted module (T005)"
Task: "Write failing tests in tests/unit/test_geocoding.py for the Nominatim client (T007)"
Task: "Write failing tests in tests/unit/test_basemap.py for projection + tile fetch/cache (T009)"
Task: "Write failing tests in tests/unit/test_generate_member_maps_cli.py for CLI parsing + config (T011)"
```

## Parallel Example: User Story 3

```bash
# Launch all four US3 test-writing tasks together:
Task: "Overlap detection tests in tests/unit/test_clustering.py (T023)"
Task: "FR-014 short-circuit + slug tests in tests/unit/test_clustering.py (T024)"
Task: "Detail-map sizing tests in tests/unit/test_basemap.py (T025)"
Task: "FR-013 fallback rendering tests in tests/unit/test_rendering.py (T026)"
Task: "Detail-map generation + fallback end-to-end test in tests/unit/test_generate_member_maps_cli.py (T027)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (schema, shared record I/O, geocoding, basemap/
   projection, CLI skeleton) — blocks everything else.
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: run the quickstart Scenario 1/2 checks against synthetic
   data — an overview pin map per season, correct colors, scale bar, skip logging,
   no re-geocoding on a second run.
5. This is a usable deliverable on its own.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. Add US1 → validate independently → MVP.
3. Add US2 → validate independently (photo map alongside the pin map).
4. Add US3 → validate independently (detail maps + fallback rendering for crowded
   areas).
5. Polish → docs, full quickstart walkthrough, lint/format/test pass.

### Notes

- [P] tasks touch different files and have no unfinished same-phase dependency.
- Every implementation task has a preceding failing-test task per Constitution
  Principle V (red-green) — do not skip ahead to implementation.
- Commit after each task or logical group; stop at any checkpoint to validate a story
  independently.
- `scripts/scrape_applicants.py`'s refactor (T006) is behavior-preserving — its
  existing test suite must pass unmodified, not be rewritten to match the refactor.
