---

description: "Task list for Pairing Report Maps"
---

# Tasks: Pairing Report Maps

**Input**: Design documents from `/specs/007-pairing-report-maps/`

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

No new script (Constitution II) — this feature extends `scripts/generate_rider_pairings.py`
(006) in place, plus two existing internal packages: `scripts/rkby_pairing/` (new module
`maps.py`; existing `clusters.py`/`report.py` extended) and `scripts/rkby_maps/` (new
module `pin_map.py`, promoted out of `scripts/generate_member_maps.py`'s (002) private
helpers). No new third-party dependency. Tests under `tests/unit/`, reusing the existing
`tests/fixtures/pairing_seasons/` fixture set (006) — it already contains everything US1
and US2/US3's fixture-backed tests need (a Rider trio, a Service-Crew member at the same
address as one of them, a Supporter, an excluded/ignored/ungeocoded record each) with no
new fixture files required.

---

## Phase 1: Setup

No setup tasks — this feature adds zero new dependencies (`pyproject.toml` unchanged)
and no new top-level package (`scripts/rkby_pairing/` and `scripts/rkby_maps/` both
already exist with `__init__.py` from 002/006). Proceed directly to Phase 2.

---

## Phase 2: Foundational — promote the shared pin-map rendering module

**Purpose**: `scripts/rkby_maps/pin_map.py` is new shared plumbing both User Story 2
(cluster maps) and User Story 3 (the overview map) render through (research.md Decision
2, FR-004). **User Story 1 does not depend on this phase at all** — it touches only
`scripts/rkby_pairing/clusters.py` — so US1 (Phase 3) may be done before, after, or in
parallel with this phase. Phases 4 and 5 (US2/US3) cannot start until this phase is
complete.

- [ ] T001 [P] Write failing tests in `tests/unit/test_rkby_maps_pin_map.py` for the
      promoted pin-map helpers that will live in `scripts/rkby_maps/pin_map.py`, mirroring
      the module-per-file convention `test_basemap.py`/`test_clustering.py`/
      `test_rendering.py` already establish for their own `scripts/rkby_maps/` siblings.
      None of these need network mocking — `render_pin_layer` only draws onto an
      in-memory `PIL.Image.new(...)` canvas; only a full `stitch_basemap` call would need
      that, and none of these helpers make one. Cover:
      - `CANVAS_SIZE == (1600 * RESOLUTION_SCALE, 1200 * RESOLUTION_SCALE)`,
        `DEFAULT_MIN_WIDTH_KM == 15`, `DEFAULT_CENTER == (51.1657, 10.4515)`,
        `PADDING_KM == 0.5`, `EDGE_MARGIN_PX == 50 * RESOLUTION_SCALE` — the exact values
        currently private in `scripts/generate_member_maps.py` as `CANVAS_SIZE`,
        `DEFAULT_MIN_WIDTH_KM`, `DEFAULT_CENTER`, `DETAIL_MAP_PADDING_KM`,
        `DETAIL_MAP_EDGE_MARGIN_PX`.
      - `pixel_positions(records, center, zoom)` matches `lonlat_to_pixel` per record.
      - `group_position(group, positions)` returns the mean pixel position of a group's
        members.
      - `records_within_frame(records, always_include, center, zoom, canvas_size,
        edge_margin_px)`: an `always_include` member is kept regardless of where it lands;
        another record inside the frame (well past the edge margin) is kept; one within
        `edge_margin_px` of the canvas border is omitted — mirror the exact edge-margin
        pixel math `test_generate_member_maps_cli.py::
        test_detail_map_includes_frame_members_and_omits_ones_too_close_to_the_edge`
        already uses.
      - `render_pin_layer(canvas, records, center, zoom)` draws an individual
        role-colored pin per non-overlapping record and one merged/badged pin per
        overlapping group (reusing `rkby_maps.rendering.draw_pin`/`draw_merged_pin`/
        `role_color`/`merged_role_color` unchanged), returning `(groups, by_key)`.
      - `overview_center_and_zoom(members, min_width_km)`: an empty `members` list falls
        back to `(DEFAULT_CENTER, zoom_for_min_width_km(min_width_km=min_width_km,
        latitude=DEFAULT_CENTER[0], canvas_width_px=CANVAS_SIZE[0]))`; a non-empty list
        matches `zoom_for_bounding_box(points, padding_km=PADDING_KM,
        min_width_km=min_width_km, canvas_size=CANVAS_SIZE)` computed independently in
        the test for comparison.
- [ ] T002 Implement `scripts/rkby_maps/pin_map.py`: move (not duplicate) `CANVAS_SIZE`,
      `DEFAULT_MIN_WIDTH_KM`, `DEFAULT_CENTER`, `PADDING_KM` (renamed from
      `DETAIL_MAP_PADDING_KM`), `EDGE_MARGIN_PX` (renamed from
      `DETAIL_MAP_EDGE_MARGIN_PX`), and public `pixel_positions()` (from
      `_pixel_positions`), `group_position()` (from `_group_position`),
      `records_within_frame()` (from `_records_within_frame`), `render_pin_layer()`
      (from `_draw_pin_layer`), `overview_center_and_zoom()` (from
      `_overview_center_and_zoom`) out of `scripts/generate_member_maps.py`, unchanged in
      behavior (research.md Decision 2) — makes T001 pass.
- [ ] T003 Refactor `scripts/generate_member_maps.py` to import `CANVAS_SIZE`,
      `DEFAULT_MIN_WIDTH_KM`, `DEFAULT_CENTER`, and the five promoted functions from
      `scripts.rkby_maps.pin_map` instead of defining its own private copies; delete the
      now-redundant private definitions (`_pixel_positions`, `_group_position`,
      `_records_within_frame`, `_draw_pin_layer`, `_overview_center_and_zoom`, and the
      module-level `CANVAS_SIZE`/`DEFAULT_MIN_WIDTH_KM`/`DEFAULT_CENTER`/
      `DETAIL_MAP_PADDING_KM`/`DETAIL_MAP_EDGE_MARGIN_PX` constants); update every call
      site (`_generate_detail_maps`, `_draw_photo_layer`, `_render_overview_pin_map`,
      `_process_season`) to the new public names. Behavior unchanged.
- [ ] T004 Update `tests/unit/test_generate_member_maps_cli.py`'s import of `CANVAS_SIZE`,
      `DETAIL_MAP_EDGE_MARGIN_PX`, `DETAIL_MAP_PADDING_KM` (used by
      `test_detail_map_includes_frame_members_and_omits_ones_too_close_to_the_edge`) to
      pull `CANVAS_SIZE`, `EDGE_MARGIN_PX`, `PADDING_KM` from `scripts.rkby_maps.pin_map`
      instead of `scripts.generate_member_maps` (`Config`/`ConfigError`/
      `build_arg_parser`/`load_config`/`main` keep importing from
      `scripts.generate_member_maps` unchanged). Run this file's full existing suite and
      confirm every test still passes with no change to any test body.

**Checkpoint**: `scripts/rkby_maps/pin_map.py` exists as the shared rendering module;
`generate_member_maps.py`'s own maps are unchanged. User Stories 2 and 3 can now begin.

---

## Phase 3: User Story 1 - No rider silently missing from Training Clusters (Priority: P1) 🎯 MVP

**Goal**: Every current-season rider who passes existing Training Cluster eligibility
(not excluded, not opted out, geocoded) appears in the Training Clusters section — as
part of a group of 3+, a pair, or alone — instead of being silently dropped for falling
short of the old three-member minimum.

**Independent Test**: Run the report against a data set containing one rider who lives
far from every other rider, two riders who live close to each other but far from
everyone else, and three riders who live close together. Confirm all six riders each
appear in exactly one Training Cluster — the isolated rider alone, the pair together, the
trio together — with none missing.

**Does not depend on Phase 2** — this story never touches map rendering.

### Tests for User Story 1 ⚠️

- [ ] T005 [P] [US1] Update `tests/unit/test_rkby_pairing_clusters.py` for the removed
      3-member minimum (research.md Decision 1, FR-001/FR-002):
      - Rewrite `test_two_nearby_riders_with_no_third_nearby_form_no_cluster` (rename to
        reflect the new expectation, e.g.
        `test_two_nearby_riders_with_no_third_nearby_still_form_a_two_member_cluster`) to
        assert `a`/`b` now form one 2-member cluster instead of `clusters == []`
        (Acceptance Scenario 1.2).
      - Rewrite `test_cluster_radius_km_changes_which_groups_qualify`'s `narrow`
        assertion: at the narrow radius, `a`/`b` now form a 2-member cluster (not `[]`);
        `wide` keeps asserting the unchanged 3-member trio.
      - Rewrite `test_excluded_ignored_and_ungeocoded_riders_are_never_cluster_nodes` to
        assert `clusters` now holds one 2-member cluster `{"a", "b"}` instead of `[]` —
        the excluded/ignored/ungeocoded records still never become cluster nodes
        (Acceptance Scenario 1.4).
      - Add a new test for a rider with no one else within `cluster_radius_km` forming
        their own one-member cluster (Acceptance Scenario 1.1).
      - Add a new test: a rider who was part of a larger cluster becomes a one-member
        cluster once every other member of that cluster is excluded/ignored/removed
        (Edge Cases).
      - `test_three_or_more_nearby_current_season_riders_form_one_cluster`,
        `test_non_rider_member_at_the_same_location_is_never_a_cluster_member`,
        `test_new_riders_and_experienced_riders_both_count_toward_cluster_membership`,
        `test_cluster_centroid_is_the_mean_position_of_its_members` (all against the
        3+-member fixture cluster) are unaffected and stay as-is (Acceptance Scenario
        1.3).

### Implementation for User Story 1

- [ ] T006 [US1] In `scripts/rkby_pairing/clusters.py::find_training_clusters`, change
      the `find_overlap_groups(...)` call's `min_group_size` argument from `3` to `1`
      (research.md Decision 1) — makes T005 pass. No other line in the function changes.

**Checkpoint**: User Story 1 is fully functional and independently testable — this is
the MVP. `uv run scripts/generate_rider_pairings.py` reports every eligible rider in
Training Clusters, singleton clusters included.

---

## Phase 4: User Story 2 - See each training cluster on a map (Priority: P2)

**Goal**: Each Training Cluster's section in the report includes a map image plotting
that cluster's members plus any other current-season member of any role nearby, for
context.

**Independent Test**: Run the report against a data set with one qualifying Training
Cluster and confirm that cluster's section includes a map image with that cluster's
members plotted at their home locations.

**Depends on Phase 2** (`scripts/rkby_maps/pin_map.py`).

### Tests for User Story 2 ⚠️

- [ ] T007 [P] [US2] Write failing tests in `tests/unit/test_rkby_pairing_maps.py`
      (new file) for cluster-map rendering (FR-003/FR-004/FR-005, data-model.md § Cluster
      Map), using `responses`-mocked OSM tile fetches only — no Nominatim mock needed,
      this feature geocodes nothing (mirror
      `test_generate_member_maps_cli.py::_register_common_mocks`'s tile-only half) — and
      small in-memory synthetic records (mirror `test_rkby_pairing_clusters.py`'s
      `_rider()` helper, generalized to carry a `role`). Test a not-yet-implemented
      `render_cluster_map(cluster, eligible_pool, tile_cache_dir) -> PIL.Image`:
      - Every one of the cluster's own members is drawn regardless of where it falls in
        the rendered frame.
      - An eligible member of any other role whose position lands inside the computed
        frame is drawn too (FR-005).
      - An eligible member well outside the frame (clearly past
        `pin_map.DEFAULT_MIN_WIDTH_KM`'s edge) is omitted from this map.
      - A single-member cluster still returns a valid `pin_map.CANVAS_SIZE`-sized image
        (Edge Cases: single-member cluster map).
      - Two cluster members sharing the exact same address render as one merged/badged
        pin, not two overlapping pins (Edge Cases).
      - A cluster spanning wider than `pin_map.DEFAULT_MIN_WIDTH_KM` frames around its
        own full bounding box — assert the same `(center, zoom)`
        `rkby_maps.basemap.zoom_for_bounding_box(cluster_points,
        padding_km=pin_map.PADDING_KM, min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM,
        canvas_size=pin_map.CANVAS_SIZE)` computed independently in the test would give
        (Edge Cases: very large single cluster).
- [ ] T008 [P] [US2] Extend `tests/unit/test_rkby_pairing_report.py` for the per-cluster
      map image (contracts/report-output.md): extend
      `test_populated_training_clusters_section_renders_one_subsection_per_cluster` and
      `test_multiple_clusters_each_get_their_own_numbered_subsection` to also assert
      `<img src="maps/cluster_1.png" alt="Cluster 1 map" width="100%">` (and
      `cluster_2.png` for the second cluster in the multi-cluster test) appears directly
      under each `### Cluster <n>` heading, before that cluster's member roster.

### Implementation for User Story 2

- [ ] T009 [US2] Implement `scripts/rkby_pairing/maps.py` (new file):
      - `eligible_member_pool(latest_records: dict[str, dict]) -> list[dict]`
        (data-model.md § Eligible Member Pool, FR-007) — every record in
        `latest_records.values()` for which `rkby_pairing.eligibility.is_eligible_base`
        is `True`, no role filter, reusing that function rather than re-deriving the rule
        (research.md Decision 3).
      - `render_cluster_map(cluster, eligible_pool, tile_cache_dir) -> PIL.Image`
        (data-model.md § Cluster Map): `center, zoom =
        rkby_maps.basemap.zoom_for_bounding_box(cluster_member_points,
        padding_km=pin_map.PADDING_KM, min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM,
        canvas_size=pin_map.CANVAS_SIZE)`; `frame_records =
        pin_map.records_within_frame(eligible_pool,
        always_include=set(cluster.member_match_keys), center, zoom,
        canvas_size=pin_map.CANVAS_SIZE, edge_margin_px=pin_map.EDGE_MARGIN_PX)`; then
        `rkby_maps.basemap.stitch_basemap` + `pin_map.render_pin_layer` +
        `rkby_maps.rendering.draw_scale_bar` + `draw_attribution`, mirroring
        `generate_member_maps.py`'s own `_generate_detail_maps` per-group rendering shape
        — makes T007 pass.
- [ ] T010 [US2] Extend `_render_cluster_section` in `scripts/rkby_pairing/report.py` to
      insert `<img src="maps/cluster_{index}.png" alt="Cluster {index} map"
      width="100%">` immediately after the `### Cluster <n> (...)` heading, before the
      member roster (contracts/report-output.md) — makes T008 pass. `{index}` is the
      same 1-based `enumerate(clusters, start=1)` value the heading already uses, so
      `render_report`'s signature does not change.
- [ ] T011 [P] [US2] Extend `tests/unit/test_generate_rider_pairings_cli.py` with
      `responses`-mocked-tile end-to-end tests (mirror
      `test_generate_member_maps_cli.py`'s tile-mock pattern) against the fixture seasons:
      - `main([])` writes `reports/maps/cluster_<n>.png` for every Training Cluster the
        run found, `<n>` matching `rider_pairings.md`'s own `### Cluster <n>` numbering.
      - Re-running after seeding a stale `reports/maps/cluster_9.png` (simulating a
        prior run's differently-shaped cluster list) removes it — a full-directory
        clear, not a prefix-glob one (FR-010, contracts/map-output.md § Regeneration
        semantics).
      - `--pdf-only` never touches `reports/maps/` at all (leave a marker file there
        beforehand and confirm it survives untouched).
      - `git status --porcelain -- reports/maps/` (reusing this file's existing
        `_init_repo`/`_git` helpers) shows nothing after a run inside a
        git-initialized `RKBY_DATA_DIR` (FR-011).
- [ ] T012 [US2] Wire cluster-map generation into `scripts/generate_rider_pairings.py`'s
      `main()`: after computing `clusters`, call a new
      `rkby_pairing.maps.write_report_maps(config.data_dir, latest_records, clusters,
      tile_cache_dir=config.data_dir / ".tile_cache")`. Implement `write_report_maps` in
      `scripts/rkby_pairing/maps.py` to: create `reports/maps/` if absent, then delete
      every existing file already inside it (research.md Decision 5 — this directory only,
      never any other directory such as a `tiles/` folder belonging to a different
      feature); then render and save `cluster_<n>.png` for every entry in `clusters` via
      T009's `render_cluster_map`, `<n>` 1-based matching `render_report`'s own numbering.
      Call this before writing `rider_pairings.md` (both reference the same run's fresh
      state). Makes T011's cluster-map assertions pass. (US3, T018 below, extends this
      same function to also write `overview.png` as part of the same single clear.)

**Checkpoint**: User Stories 1 and 2 are both independently functional. Every Training
Cluster's section now includes a map.

---

## Phase 5: User Story 3 - See the whole current season's team on one map (Priority: P3)

**Goal**: The report includes one overview map showing every eligible current-season
member of any role.

**Independent Test**: Run the report against a data set containing a mix of Riders,
Service Crew, and Supporters with known addresses, and confirm the generated report
includes one overview map on which members of all three roles appear.

**Depends on Phase 2** (`scripts/rkby_maps/pin_map.py`) and reuses Phase 4's
`eligible_member_pool()` (T009) and `write_report_maps()` (T012).

### Tests for User Story 3 ⚠️

- [ ] T013 [P] [US3] Extend `tests/unit/test_rkby_pairing_maps.py` with failing tests for
      a not-yet-implemented `render_overview_map(eligible_pool, tile_cache_dir) ->
      PIL.Image` (data-model.md § Overview Map, FR-006/FR-007):
      - Every role present in `eligible_pool` (Rider, Service Crew, Supporter) renders as
        its own role-colored pin (or a merged pin for an overlapping subset).
      - An empty `eligible_pool` still returns a valid `pin_map.CANVAS_SIZE`-sized image,
        centered via `pin_map.overview_center_and_zoom([],
        pin_map.DEFAULT_MIN_WIDTH_KM)`'s `DEFAULT_CENTER` fallback, without raising
        (Acceptance Scenario 3.3).
- [ ] T014 [P] [US3] Extend `tests/unit/test_rkby_pairing_report.py` with failing tests
      for the new `## Team Overview` section (contracts/report-output.md):
      - It is the first section after the intro line, appearing before `## New Riders`.
      - It contains exactly `<img src="maps/overview.png" alt="Team overview map"
        width="100%">`.
      - It is present with that same image reference even when `new_riders` and
        `clusters` are both empty (FR-008 — never conditionally omitted).
- [ ] T015 [P] [US3] Extend `tests/unit/test_generate_rider_pairings_cli.py` with
      `responses`-mocked-tile end-to-end tests against the fixture seasons:
      - `main([])` writes `reports/maps/overview.png` containing pins for members of
        every role present in the fixture set (Rider via `cluster-alice`, Service Crew
        via `cluster-crew-dave`, Supporter via `erin-late`).
      - `overview.png` is written even when the season has zero eligible, plottable
        members (construct a season with none — SC-003, Acceptance Scenario 3.3).
      - `--pdf-only` embeds the already-written `maps/overview.png` in
        `reports/rider_pairings.pdf` — extend
        `test_pdf_only_skips_computation_and_renders_current_md_content_verbatim`'s
        pattern to confirm the PDF's extracted content includes the Team Overview
        section text (`pdf.py` needs no code change for this, research.md §7).

### Implementation for User Story 3

- [ ] T016 [US3] Implement `render_overview_map(eligible_pool, tile_cache_dir) ->
      PIL.Image` in `scripts/rkby_pairing/maps.py` (data-model.md § Overview Map):
      `center, zoom = pin_map.overview_center_and_zoom(eligible_pool,
      min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM)`, then
      `rkby_maps.basemap.stitch_basemap` + `pin_map.render_pin_layer(canvas,
      eligible_pool, center, zoom)` + `draw_scale_bar` + `draw_attribution` — makes T013
      pass.
- [ ] T017 [US3] Add a new `## Team Overview` section to `render_report` in
      `scripts/rkby_pairing/report.py`, placed immediately after the intro line and
      before `## New Riders`, containing exactly `<img src="maps/overview.png"
      alt="Team overview map" width="100%">` — makes T014 pass. Always rendered,
      independent of whether `new_riders`/`clusters` are empty (FR-008).
- [ ] T018 [US3] Extend `rkby_pairing.maps.write_report_maps` (T012) to also render and
      save `overview.png` via T016's `render_overview_map`, using T009's
      `eligible_member_pool(latest_records)` as its member pool — inside the same single
      `reports/maps/` clear-then-write pass T012 already established, not a second clear
      (research.md Decision 5) — makes T015 pass.

**Checkpoint**: All three user stories are independently functional — feature complete.
`uv run scripts/generate_rider_pairings.py` produces a report with no rider missing from
Training Clusters, a map on every cluster's section, and a Team Overview map up top.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Bring documentation and the full test/lint suite in line with the
now-complete feature.

- [ ] T019 [P] Update README.md's "Running the rider pairing suggester" section (around
      line 176-186): change "training clusters of three or more current-season riders"
      to "training clusters of one or more current-season riders" (FR-001), and mention
      the new Team Overview map and per-cluster maps now written to
      `$RKBY_DATA_DIR/reports/maps/` (gitignored, never committed, regenerated fresh on
      every run).
- [ ] T020 [P] Walk through `specs/007-pairing-report-maps/quickstart.md` Scenarios 1-6
      end-to-end against a throwaway synthetic `RKBY_DATA_DIR` (never real member data,
      Constitution I/V) — confirm every documented "Expected outcome" holds, including
      the PDF export (Scenario 4), stale-map cleanup after a data change (Scenario 5),
      and the gitignored/uncommitted `reports/maps/` check (Scenario 6).
- [ ] T021 Run `uv run ruff check .`, `uv run ruff format .`, and `uv run pytest` for the
      full suite; fix any lint/format/test failures before considering the feature done.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: None — no tasks.
- **Foundational (Phase 2)**: No dependency on Setup (there was nothing there). T002
  depends on T001; T003 depends on T002; T004 depends on T003. **Blocks User Stories 2
  and 3 only** — User Story 1 has no dependency on this phase.
- **User Story 1 (Phase 3)**: No dependency on Phase 2 — can be done first, last, or in
  parallel with it. T006 depends on T005.
- **User Story 2 (Phase 4)**: Depends on Phase 2. Within US2: T009 depends on T007; T010
  depends on T008; T012 depends on T009, T010, and T011.
- **User Story 3 (Phase 5)**: Depends on Phase 2, and on Phase 4's T009
  (`eligible_member_pool`) and T012 (`write_report_maps` to extend) — implemented after
  US2 in practice, per spec.md's priority order. Within US3: T016 depends on T013; T017
  depends on T014; T018 depends on T016, T017, T015, and on T012.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Failing tests (marked ⚠️) are written and confirmed failing before their matching
  implementation task.
- US2/US3: rendering helpers (`rkby_pairing/maps.py`) before the report-template wiring
  (`report.py`) before the CLI orchestration (`generate_rider_pairings.py`'s `main()` /
  `write_report_maps`).
- Story complete (checkpoint) before moving to the next priority.

### Parallel Opportunities

- T001 (Foundational) has no same-phase task to run alongside.
- T005 (US1) can run in parallel with all of Phase 2, since US1 has no dependency on it.
- Within US2: T007, T008, T011 (three different files) run in parallel with each other.
- Within US3: T013, T014, T015 (three different files) run in parallel with each other.
- T019 and T020 (Polish) run in parallel — different concerns, no shared file.

---

## Parallel Example: User Story 2 Tests

```bash
# Launch all three US2 test-writing tasks together:
Task: "cluster-map rendering tests in tests/unit/test_rkby_pairing_maps.py (T007)"
Task: "per-cluster <img> tests in tests/unit/test_rkby_pairing_report.py (T008)"
Task: "cluster-map CLI end-to-end tests in tests/unit/test_generate_rider_pairings_cli.py (T011)"
```

## Parallel Example: User Story 3 Tests

```bash
# Launch all three US3 test-writing tasks together:
Task: "overview-map rendering tests in tests/unit/test_rkby_pairing_maps.py (T013)"
Task: "Team Overview section tests in tests/unit/test_rkby_pairing_report.py (T014)"
Task: "overview-map CLI end-to-end tests in tests/unit/test_generate_rider_pairings_cli.py (T015)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 3: User Story 1 (Phase 2 is not a prerequisite for this).
2. **STOP and VALIDATE**: run quickstart.md Scenario 1 against synthetic data — an
   isolated rider, a pair, and a trio each appear correctly in Training Clusters, none
   missing.
3. This is a usable deliverable on its own — a correctness fix for the existing report.

### Incremental Delivery

1. Add US1 → validate independently → MVP (no rider silently dropped).
2. Complete Phase 2: Foundational (`pin_map.py` promotion) → foundation for maps ready.
3. Add US2 → validate independently (every cluster's section has a map).
4. Add US3 → validate independently (one Team Overview map, all roles).
5. Polish → docs, full quickstart walkthrough, lint/format/test pass.

### Notes

- [P] tasks touch different files and have no unfinished same-phase dependency.
- Every implementation task has a preceding failing-test task per Constitution
  Principle V (red-green) — do not skip ahead to implementation.
- Commit after each task or logical group; stop at any checkpoint to validate a story
  independently.
- Never use real member data in any fixture or test (Constitution I/V) — the existing
  `tests/fixtures/pairing_seasons/` set is synthetic and already covers every role/
  eligibility case this feature's tests need.
- T002/T003's `pin_map.py` promotion is behavior-preserving for
  `generate_member_maps.py` — its existing test suite (`test_generate_member_maps_cli.py`,
  `test_basemap.py`, `test_clustering.py`, `test_rendering.py`) must keep passing
  unmodified in behavior, not be rewritten to match the move (only the one import-source
  change in T004).
- `render_cluster_map`/`render_overview_map` take no `min_width_km`/`show_scale_bar`
  parameters — this feature adds no new CLI flags to `generate_rider_pairings.py`
  (plan.md § Project Structure), so both always use `pin_map.DEFAULT_MIN_WIDTH_KM` and
  always draw the scale bar, matching `generate_member_maps.py`'s own default behavior.
