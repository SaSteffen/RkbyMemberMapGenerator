---

description: "Task list template for feature implementation"
---

# Tasks: Member Analytics Report

**Input**: Design documents from `/specs/005-member-analytics-report/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
(all present and read)

**Tests**: Included and REQUIRED — constitution Principle V (Test-First Development,
NON-NEGOTIABLE) mandates a failing test before implementation for all new functionality
in this repo; every implementation task below has a preceding failing-test task it makes
pass.

**Organization**: Tasks are grouped by user story (spec.md's US1/US2/US3/US4, priority
order) so each can be implemented and independently tested.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unfinished dependency)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- File paths are exact and relative to the repository root

## Path Conventions

Notebook + internal-package layout per Constitution II (see plan.md § Project
Structure): `scripts/report_member_analytics.ipynb` (the one artifact), `scripts/
rkby_report/` (new internal package: `geo.py`, `buckets.py`, `frame.py`,
`aggregate.py`, `plots.py`), `scripts/rkby_records.py` (existing shared module, gains
one promoted function), `scripts/rkby_interactive_map/merge.py` (existing, refactored
not rewritten). Tests under `tests/unit/`, fixtures under `tests/fixtures/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding this feature needs before any code is written.

- [ ] T001 Add `pandas`, `matplotlib`, `jupyterlab`, `ipykernel`, and `nbconvert` as runtime dependencies in `pyproject.toml` (`[project.dependencies]`) and run `uv sync` (plan.md § Technical Context)
- [ ] T002 [P] Add `nbstripout` as a dev-only dependency in `pyproject.toml` (`[dependency-groups.dev]`) and run `uv sync`
- [ ] T003 [P] Add an `nbstripout` pre-commit hook entry to `.pre-commit-config.yaml` so `scripts/report_member_analytics.ipynb`'s cell outputs are stripped before every commit (research.md §4)
- [ ] T004 [P] Create the new internal package `scripts/rkby_report/__init__.py` (empty) and a minimal `scripts/report_member_analytics.ipynb` skeleton (a title markdown cell plus a cell that reads and validates `RKBY_DATA_DIR` is set, per contracts/cli-and-env.md) per plan.md § Project Structure

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one thing every user story is built on — a correct, fully-tested
`build_member_season_frame()` DataFrame (contracts/member-season-frame.md) — plus the
shared cross-season identity resolution it depends on. None of this is independently
"a story" on its own, but every story needs all of it.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T005 [P] Write failing tests in `tests/unit/test_rkby_records_canonical_match_keys.py` for `canonical_match_keys()`: direct alias resolution, transitive multi-hop alias chains, and cycle-safety — the same coverage `rkby_interactive_map/merge.py`'s private `_canonical_match_keys` already had, now targeting the shared public function (research.md §7)
- [ ] T006 Promote `_canonical_match_keys` out of `scripts/rkby_interactive_map/merge.py` into `scripts/rkby_records.py` as public `canonical_match_keys()` (unchanged behavior); update `merge.py` to import and call the shared function instead of defining its own copy; confirm `merge.py`'s existing tests still pass unmodified in behavior — makes T005 pass (research.md §7, plan.md § Structure Decision)
- [ ] T007 [P] Add synthetic multi-season applicant YAML fixtures under `tests/fixtures/report_seasons/<season-label>/applicants/*.yaml` (at least 2 consecutive seasons) covering: every primary role (`Rider`, `Service Crew`, `Supporter`) plus one unrecognized role plus one null role; `sex` values `Male`/`Female`/null; birthdays spanning every age bracket from research.md §9 plus one null; `latitude`/`longitude` landing in every distance bracket from research.md §9 plus one null pair; `excluded`/`ignore` flags set on at least one record each; a `match_key` retained across two consecutive seasons via a recorded `alias_match_keys`; a `match_key` present only in the earlier season (departed); a `match_key` that skips one season and returns in a later one — never real member data (Constitution I/V)
- [ ] T008 [P] Write failing tests in `tests/unit/test_rkby_report_frame.py` for `geo.haversine_km()` (known-distance coordinate pairs, symmetry, zero distance) and `buckets.age_bucket()`/`buckets.distance_bucket()` (every bracket boundary from research.md §9, plus the `"unknown"`/`"unknown/not geocoded"` sentinel for `None` input)
- [ ] T009 Implement `scripts/rkby_report/geo.py` (`HAMBURG_CENTER` constant + `haversine_km()`) and `scripts/rkby_report/buckets.py` (bracket boundary constants + `age_bucket()`/`distance_bucket()` helpers) — makes T008 pass (research.md §5, §9)
- [ ] T010 Extend `tests/unit/test_rkby_report_frame.py` with failing tests for `build_member_season_frame()` against the T007 fixtures, asserting every guarantee in `contracts/member-season-frame.md`: the eligibility filter drops only `excluded`/`ignore` records (never for a missing birthday/sex/coordinates/role); every column from data-model.md § Member-Season Observation is present with correct values, including `"unknown"` categories for missing fields rather than dropped rows; `match_key` is the canonical identity (via T006) even across a recorded alias; `retained_next_season` is `True` for the alias-retained fixture, `False` for the departed one, `None` for every row in the chronologically last discovered season, and correctly `False` (not `True`) for the skip-and-return fixture's skipped season; the function performs no geocode lookups and writes nothing to any `.yaml` file
- [ ] T011 Implement `scripts/rkby_report/frame.py`: `build_member_season_frame(data_dir)` using `rkby_records.discover_seasons`/`load_existing_records`, the T006 `canonical_match_keys`, T009's `geo`/`buckets` helpers, and the age-at-season reference date from research.md §6 — makes T010 pass

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - See this season's team makeup at a glance (Priority: P1) 🎯 MVP

**Goal**: For a single selected season, show role counts, gender distribution,
age-bucket distribution, and distance-from-Hamburg-bucket distribution, with missing
data shown as an explicit "unknown" category rather than dropped.

**Independent Test**: Point the report at one season's synthetic data and confirm the
resulting counts and charts match a manual count of that season's fixture records.

### Tests for User Story 1 ⚠️

- [ ] T012 [P] [US1] Write failing tests in `tests/unit/test_rkby_report_aggregate.py` for `season_summary(df, season_label)`: `total_members`, `role_counts`, `gender_counts`, `age_bucket_counts`, `distance_bucket_counts` — including `"unknown"`/`"unknown/not geocoded"` categories — against the T007 fixtures
- [ ] T013 [P] [US1] Write failing tests in `tests/unit/test_rkby_report_plots.py` for the four single-season chart-builder functions (role, gender, age-bucket, distance-bucket bar charts): each returns a populated matplotlib `Figure` without raising, given a `season_summary()`-shaped input — smoke-level only (research.md §2)

### Implementation for User Story 1

- [ ] T014 [US1] Implement `season_summary()` in `scripts/rkby_report/aggregate.py` — makes T012 pass
- [ ] T015 [US1] Implement the four single-season chart-builder functions in `scripts/rkby_report/plots.py` — makes T013 pass
- [ ] T016 [US1] Add cells to `scripts/report_member_analytics.ipynb`: import `rkby_report`, call `build_member_season_frame(RKBY_DATA_DIR)` once, select a season (defaulting to the most recently discovered one), and render the four T015 charts for it

**Checkpoint**: User Story 1 is fully functional and independently testable — this is
the MVP.

---

## Phase 4: User Story 2 - See how the team has changed season to season (Priority: P2)

**Goal**: Across every discovered season, trend total/rider/service-crew counts and
show how age/gender/distance distributions shift season to season, with a clear
"not enough data yet" signal when only one season is on file.

**Independent Test**: Point the report at three or more synthetic seasons and confirm
each trend view plots one point/bar per season in chronological order, matching a
manual count per season; with only one season on file, confirm the "not enough data"
signal appears instead of a misleading single-point trend.

### Tests for User Story 2 ⚠️

- [ ] T017 [P] [US2] Write failing tests in `tests/unit/test_rkby_report_aggregate.py` for `season_trend(df)`: one row per discovered season in chronological order with `total_members`/`rider_count`/`service_count` plus wide-pivoted age-bucket/gender/distance-bucket columns, against the T007 multi-season fixtures; and that a single-season input produces a result callers can detect as "not enough data yet"
- [ ] T018 [P] [US2] Write failing tests in `tests/unit/test_rkby_report_plots.py` for the trend chart-builder functions (member/rider/service-count line chart; age/gender/distance distribution-shift charts): smoke-level against a `season_trend()`-shaped table, plus the single-season case rendering a clear "not enough data yet" placeholder instead of a chart

### Implementation for User Story 2

- [ ] T019 [US2] Implement `season_trend()` in `scripts/rkby_report/aggregate.py` — makes T017 pass
- [ ] T020 [US2] Implement the trend chart-builder functions in `scripts/rkby_report/plots.py`, including the single-season placeholder path — makes T018 pass
- [ ] T021 [US2] Add cells to `scripts/report_member_analytics.ipynb` rendering the T020 trend charts across every discovered season

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Understand member retention (Priority: P2)

**Goal**: For every consecutive discovered season pair, the season-over-season
retention rate — overall, and split by gender, age bracket, and distance bracket.

**Independent Test**: Using two consecutive synthetic seasons with a known returning
member and a known departing member, confirm the computed retention rate (overall and
each split) matches that known outcome.

### Tests for User Story 3 ⚠️

- [ ] T022 [P] [US3] Write failing tests in `tests/unit/test_rkby_report_aggregate.py` for `retention_cohort(df, season_a, season_b)` (`retained_count`/`departed_count`/`retention_rate`) and `retention_by_split(df, season_a, season_b, split_column)` (grouped by `sex`, `age_bucket`, `distance_bucket`), against the T007 fixtures' alias-retained, departed, and skip-and-return cases — a skip-and-return member must NOT count as retained across the season they skipped
- [ ] T023 [P] [US3] Write failing tests in `tests/unit/test_rkby_report_plots.py` for the retention chart-builder functions (overall-rate chart plus one bar chart per split dimension): smoke-level against T022-shaped input

### Implementation for User Story 3

- [ ] T024 [US3] Implement `retention_cohort()` in `scripts/rkby_report/aggregate.py` — makes the `retention_cohort` half of T022 pass
- [ ] T025 [US3] Implement `retention_by_split()` in `scripts/rkby_report/aggregate.py` — makes the `retention_by_split` half of T022 pass
- [ ] T026 [US3] Implement the retention chart-builder functions in `scripts/rkby_report/plots.py` — makes T023 pass
- [ ] T027 [US3] Add cells to `scripts/report_member_analytics.ipynb` rendering overall retention plus gender/age/distance splits for every consecutive discovered season pair

**Checkpoint**: User Stories 1, 2, and 3 all work independently.

---

## Phase 6: User Story 4 - Share the finished report (Priority: P3)

**Goal**: Export the completed run's charts and summary tables to one shareable HTML
file, landing outside the git repo, containing aggregates only.

**Independent Test**: Run the export command from `contracts/cli-and-env.md` and
confirm a single HTML file is produced under `$RKBY_DATA_DIR/reports/` with every
chart/table visible and no per-member roster, and that nothing new appears under
`git status` in the repo.

### Tests for User Story 4 ⚠️

- [ ] T028 [US4] Extend `tests/unit/test_rkby_report_frame.py` with failing tests for `ensure_reports_dir_and_gitignore(data_dir)`: creates `<data_dir>/reports/` if missing; adds a `reports/` entry to `<data_dir>/.gitignore`, creating the file if absent; running it twice never duplicates the entry; leaves any pre-existing unrelated `.gitignore` entries untouched (research.md §4, §10)

### Implementation for User Story 4

- [ ] T029 [US4] Implement `ensure_reports_dir_and_gitignore()` in `scripts/rkby_report/frame.py` — makes T028 pass
- [ ] T030 [US4] Add an early cell to `scripts/report_member_analytics.ipynb` calling `ensure_reports_dir_and_gitignore(RKBY_DATA_DIR)` unconditionally on every run, and a markdown cell documenting the `jupyter nbconvert --to html --execute ... --output-dir "$RKBY_DATA_DIR/reports"` export command from `contracts/cli-and-env.md`

**Checkpoint**: All four user stories are independently functional — feature complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Bring documentation and the full test/lint suite in line with the now-complete feature.

- [ ] T031 [P] Update `README.md`'s script status/usage section: add `scripts/report_member_analytics.ipynb` with its run command and export command (contracts/cli-and-env.md), marking it implemented alongside the other scripts
- [ ] T032 [P] Walk through `specs/005-member-analytics-report/quickstart.md` Scenarios 1-5 end-to-end against a throwaway synthetic `RKBY_DATA_DIR` (never real member data); confirm every documented "Expect" holds, including that the committed notebook carries no cell output after being run locally (`nbstripout`) and that the exported HTML never lands inside the git repo
- [ ] T033 Run `uv run pre-commit install --install-hooks` (picks up the new `nbstripout` hook from T003), then `uv run ruff check .`, `uv run ruff format .`, and `uv run pytest` for the full suite; fix any lint/format/test failures before considering the feature done

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. T006 depends on T005; T009 depends on
  T008; T010 depends on T007 and T009 (extends the same file T008 wrote to, and
  exercises the T009 helpers); T011 depends on T006, T009, and T010. **Blocks all user
  stories.**
- **User Stories (Phase 3-6)**: All depend on Foundational completion.
  - US1 (P1): No dependency on US2/US3/US4.
  - US2 (P2): No functional dependency on US1's code, but implemented after it in
    practice, per spec.md's priority order.
  - US3 (P2): No functional dependency on US1/US2's code beyond the shared
    `aggregate.py`/`plots.py` files; implemented after both in practice.
  - US4 (P3): Its own code (`ensure_reports_dir_and_gitignore`) has no functional
    dependency on US1-3, but exporting something meaningful requires the notebook
    cells US1-3 add — implemented last.
- **Polish (Phase 7)**: Depends on all four user stories being complete.

### Within Each User Story

- Failing tests (T0xx marked ⚠️ section) are written and confirmed failing before their
  matching implementation task.
- `aggregate.py` functions before `plots.py` chart builders before notebook cells.
- Story complete (checkpoint) before moving to the next priority.

### Parallel Opportunities

- T002, T003, T004 (Setup) run in parallel with each other and with T001 — different
  files.
- Within Foundational: T005, T007, T008 (three different files/concerns) run in
  parallel; T010 extends the same file T008 wrote to, so it follows T008 (and T009)
  rather than running alongside them.
- Within US1: T012 and T013 (different files) run in parallel.
- Within US2: T017 and T018 (different files) run in parallel.
- Within US3: T022 and T023 (different files) run in parallel; T024/T025 (both in
  `aggregate.py`) and T026 (in `plots.py`) are sequential implementation steps.
- T031 and T032 (Polish) run in parallel — different concerns, no shared file.

---

## Parallel Example: Foundational Phase

```bash
# Launch the three parallel Foundational tasks together:
Task: "Write failing tests in tests/unit/test_rkby_records_canonical_match_keys.py (T005)"
Task: "Add synthetic multi-season fixtures under tests/fixtures/report_seasons/ (T007)"
Task: "Write failing tests in tests/unit/test_rkby_report_frame.py for geo/buckets helpers (T008)"
```

## Parallel Example: User Story 3

```bash
# Launch both US3 test-writing tasks together:
Task: "retention_cohort/retention_by_split tests in tests/unit/test_rkby_report_aggregate.py (T022)"
Task: "Retention chart-builder tests in tests/unit/test_rkby_report_plots.py (T023)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (`canonical_match_keys` promotion, `geo`/`buckets`,
   `build_member_season_frame`) — blocks everything else.
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: run quickstart.md Scenario 1 against synthetic data — role/
   gender/age/distance breakdown for one season, with "unknown" categories showing
   correctly.
5. This is a usable deliverable on its own.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. Add US1 → validate independently → MVP (single-season snapshot).
3. Add US2 → validate independently (season-to-season trends).
4. Add US3 → validate independently (retention, overall and split).
5. Add US4 → validate independently (export to a shareable HTML file, outside the
   repo, aggregates only).
6. Polish → docs, full quickstart walkthrough, lint/format/test pass.

### Notes

- [P] tasks touch different files and have no unfinished same-phase dependency.
- Every implementation task has a preceding failing-test task per Constitution
  Principle V (red-green) — do not skip ahead to implementation.
- Commit after each task or logical group; stop at any checkpoint to validate a story
  independently.
- `scripts/rkby_interactive_map/merge.py`'s refactor (T006) is behavior-preserving —
  its existing test suite must pass unmodified, not be rewritten to match the refactor.
- Never use real member data in any fixture or test (Constitution I/V) — T007's
  fixtures are synthetic, shaped like real records.
