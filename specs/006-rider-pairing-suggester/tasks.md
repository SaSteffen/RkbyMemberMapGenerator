---

description: "Task list for Rider Pairing Suggester"
---

# Tasks: Rider Pairing Suggester

**Input**: Design documents from `/specs/006-rider-pairing-suggester/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
(all present and read)

**Tests**: Included and REQUIRED — constitution Principle V (Test-First Development,
NON-NEGOTIABLE) mandates a failing test before implementation for all new functionality
in this repo; every implementation task below has a preceding failing-test task it makes
pass.

**Organization**: Tasks are grouped by user story (spec.md's US1/US2, priority order) so
each can be implemented and independently tested.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unfinished dependency)
- **[Story]**: Which user story this task belongs to (US1, US2)
- File paths are exact and relative to the repository root

## Path Conventions

One script, one internal package per Constitution II (see plan.md § Project Structure):
`scripts/generate_rider_pairings.py` (the one artifact), `scripts/rkby_pairing/` (new
internal package: `roles.py`, `eligibility.py`, `ranking.py`, `clusters.py`, `report.py`,
`pdf.py`). Two existing shared modules gain small, backward-compatible additions:
`scripts/rkby_records.py` (`auto_commit()` gains an optional `force` parameter) and
`scripts/rkby_maps/clustering.py` (`find_overlap_groups()` gains two optional
parameters). Two existing modules are imported unchanged: `scripts/rkby_report/geo.py`
(`haversine_km`) and `scripts/rkby_report/frame.py`
(`ensure_reports_dir_and_gitignore`). Tests under `tests/unit/`, fixtures under
`tests/fixtures/pairing_seasons/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding this feature needs before any code is written.

- [ ] T001 Add `markdown` and `xhtml2pdf` as runtime dependencies in `pyproject.toml`
      (`[project.dependencies]`) and run `uv sync` (research.md §9, plan.md § Technical
      Context)
- [ ] T002 [P] Create the new internal package `scripts/rkby_pairing/__init__.py`
      (empty) per plan.md § Project Structure

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The synthetic test data and the shared role-classification helper every
later test/implementation task in both user stories builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 [P] Create a synthetic multi-season fixture set under
      `tests/fixtures/pairing_seasons/<season-label>/applicants/*.yaml` (research.md
      §12), following the existing `_RECORD_FIELD_ORDER` YAML shape from
      `scripts/rkby_records.py` (see `tests/fixtures/report_seasons/` for the pattern —
      never real member data, Constitution I/V). At least 3 consecutive seasons,
      covering:
      - a new rider (latest-season role Rider, `num_previous_seasons: 0`, geocoded)
        with one or more geocoded experienced-Rider mentor candidates living nearby
        (a few km apart — real-world-plausible lat/lon pairs so `haversine_km`
        differences are meaningful) and at least one eligible candidate living far away
      - a mentor candidate whose latest-season role is Service Crew but who rode as a
        Rider in an earlier season (Acceptance Scenario 1.2)
      - a new rider who must never appear as a suggested contact for another new rider
        (Acceptance Scenario 1.3)
      - an `excluded: true` record, an `ignore: true` record, and an ungeocoded
        (`latitude`/`longitude` both null) record, each otherwise eligible on paper —
        absent from every role (Acceptance Scenario 1.5)
      - an unrecognized/blank-role record (e.g. `role: Coach` and a `role: null` record)
      - a birthday-unknown record and a sex-unknown record, each otherwise a plausible
        mentor candidate (ranking Edge Cases)
      - a `match_key` reachable only via `alias_match_keys` linking a later-season
        record back to an earlier-season record whose role is Rider (research.md §3)
      - a tight geographic group of 3+ current-season Riders (mixed experience levels)
        plus a Service Crew or Supporter member geocoded at the same location, for the
        training-cluster tests (Acceptance Scenarios 2.1-2.3)
- [ ] T004 [P] Write failing tests in `tests/unit/test_rkby_pairing_roles.py` for
      `classify_role()`: `"Rider"`/`"Service Crew"`/`"Supporter"` in mixed case and with
      surrounding whitespace, an unrecognized string (e.g. `"Coach"`), `None`, and a
      blank string (research.md §4, spec.md Edge Cases)
- [ ] T005 Implement `classify_role()` in `scripts/rkby_pairing/roles.py`, normalizing
      `role.strip().lower()` and matching against
      `scripts.rkby_maps.rendering.ROLE_COLORS`'s keys (imported directly, not
      re-declared) — makes T004 pass (research.md §4, data-model.md § Role
      Classification)

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - Suggest experienced contacts for a new rider (Priority: P1) 🎯 MVP

**Goal**: Every new rider in the latest season gets a ranked, possibly-empty list of
experienced mentor-candidate contacts (proximity primary, age-gap secondary, same-sex
tertiary tie-break), rendered as one Markdown report with full contact info and photo
links, auto-committed to `RKBY_DATA_DIR` on every write, with an independent `--pdf`
export path that honors hand-edits.

**Independent Test**: Run the script against a data set containing a mix of new riders,
returning riders, and a former rider now on Service Crew, all with known addresses.
Confirm every eligible new rider gets a non-empty, ranked list of suggested contacts,
and that every suggested contact has ridden before (currently or in a past season) and
is present in the latest season's roster.

### Tests for User Story 1 ⚠️

- [ ] T006 [P] [US1] Write failing tests in `tests/unit/test_rkby_pairing_eligibility.py`
      against the T003 fixtures for: `find_new_riders()` (FR-002 — role Rider,
      `num_previous_seasons == 0` exactly, never `None`; excluded/ignored/ungeocoded
      records absent); `find_mentor_candidates()` (FR-003/004 — latest-season Rider role,
      **or** any earlier season's record for the same canonical identity has role Rider,
      including via `alias_match_keys`; a person is never both a New Rider and a Mentor
      Candidate the same season; a latest-season Service Crew/Supporter role never
      disqualifies a Mentor Candidate as long as "has ridden before" holds; the "has
      ridden before" check finds Rider history even on an excluded/ignored *earlier*
      season's record, since eligibility only gates *this* season's role, research.md
      §3)
- [ ] T007 [P] [US1] Write failing tests in `tests/unit/test_rkby_pairing_ranking.py`
      against small in-memory synthetic records (no fixtures needed) for the ranking
      sort key (research.md §5, data-model.md § Suggested Pairing): closer
      `distance_km` always ranks first regardless of age gap or sex; smaller
      `age_gap_years` breaks a distance tie only when both birthdays are known (an
      unknown birthday sorts behind every pair with a known gap, never excluded);
      `same_sex` pairs rank ahead of an otherwise-tied opposite-sex or unknown-sex pair,
      but unknown sex is never penalized further than a known opposite-sex pair;
      `max_suggestions` caps the returned list length, and a new rider with fewer
      eligible candidates than the cap gets all of them, including zero
- [ ] T008 [P] [US1] Write failing tests in `tests/unit/test_rkby_pairing_report.py`
      against the T003 fixtures and small in-memory pairing data for the report
      renderer (contracts/report-output.md): one `## New Riders` `###` subsection per
      New Rider in deterministic (alphabetical by last name) order, present even with an
      empty suggestion list ("No eligible contacts found nearby."); full contact info
      (address, phone/email, omitting whichever is null) per FR-009; a Markdown image
      reference to a member's `photo` field resolved relative to the report file's own
      location (`../seasons/<season>/<photo path>`) when present, simply omitted when
      the record has no photo on file; suggested contacts ordered by `rank`, each
      annotated with distance (always) and age-gap/same-sex only when known; a
      `## Training Clusters` section that renders "No training clusters found this
      season." when given an empty cluster list (US2 extends this same file with
      populated-cluster-section coverage)
- [ ] T009 [P] [US1] Write failing tests in `tests/unit/test_rkby_pairing_pdf.py` for
      the PDF renderer (research.md §9, contracts/report-output.md § PDF export
      contract): given a `.md` file on disk — including one containing a hand-edit not
      present in any freshly-generated version — produces a non-empty PDF file whose
      extracted text contains that hand-edited content; a `.md` file with a photo
      reference renders without raising when the referenced photo file exists on disk
      relative to the `.md` file's own directory; the renderer never touches season
      data and never rewrites the `.md` file, so calling it twice with no edit in
      between leaves the `.md` file byte-identical and produces valid PDF output both
      times
- [ ] T010 [P] [US1] Write failing tests in `tests/unit/test_rkby_records.py`,
      extending the existing `auto_commit` (generalized) test section, for a new
      optional `force: bool = False` parameter: `force=True` successfully stages and
      commits a path even when it's excluded by the target repo's own `.gitignore`;
      every existing test in this section (default `force=False`) keeps passing
      unmodified, confirming the new parameter's default preserves current behavior
      exactly
- [ ] T011 [P] [US1] Write failing tests in `tests/unit/test_generate_rider_pairings_cli.py`
      against the T003 fixtures for: `load_config()`/`ConfigError` (missing/invalid
      `RKBY_DATA_DIR`, mirrors `generate_member_maps.py`); `build_arg_parser()`
      (`--max-suggestions` positive-int, default 3; `--pdf`/`--pdf-only` flags;
      non-positive `--max-suggestions` rejected via `SystemExit`, mirroring
      `--min-width-km`'s validation); `main()` writes `reports/rider_pairings.md` and,
      when `RKBY_DATA_DIR` is a git work tree, auto-commits exactly that file (never
      `reports/rider_pairings.pdf`) even though `ensure_reports_dir_and_gitignore` has
      already added a blanket `reports/` entry to that repo's `.gitignore` (assert the
      file is actually committed, not silently skipped — T010's `force=True` is what
      makes this work); `--pdf` also writes `reports/rider_pairings.pdf` in the same
      run; `--pdf-only` skips the pairing computation entirely (the `.md` file's
      content is left untouched) and exits non-zero when `reports/rider_pairings.md`
      doesn't exist yet; zero discovered seasons exits `0` without writing a report

### Implementation for User Story 1

- [ ] T012 [US1] Implement `find_new_riders()` and `find_mentor_candidates()` in
      `scripts/rkby_pairing/eligibility.py`, plus a shared, public
      `is_eligible_base()` (excluded/ignore/geocoded predicate, reused unchanged by
      `clusters.py` in US2) — resolve cross-season identity via
      `rkby_records.canonical_match_keys()` over every raw record from every season
      (not eligibility-filtered, research.md §3) — makes T006 pass
- [ ] T013 [US1] Implement the ranking sort key in `scripts/rkby_pairing/ranking.py`,
      using `scripts.rkby_report.geo.haversine_km` for `distance_km` — makes T007 pass
- [ ] T014 [US1] Implement the report renderer in `scripts/rkby_pairing/report.py`:
      document header, `## New Riders` section built on a shared contact-info+photo
      rendering helper (reused unchanged by US2's Training Clusters section), and a
      `## Training Clusters` placeholder that always renders "No training clusters
      found this season." until US2 wires in real clusters — makes T008 pass
- [ ] T015 [US1] Implement the PDF renderer in `scripts/rkby_pairing/pdf.py`:
      `markdown.markdown()` the report's on-disk content to HTML, then render that HTML
      to PDF via `xhtml2pdf`, with image paths resolved relative to the `.md` file's
      own directory — makes T009 pass
- [ ] T016 [US1] Add an optional `force: bool = False` parameter to `auto_commit()` in
      `scripts/rkby_records.py` (appends `-f` to the `git add` invocation only when
      `True`; every existing call site keeps its current default behavior) — makes T010
      pass. Needed because `ensure_reports_dir_and_gitignore` (research.md §8) adds a
      blanket `reports/` entry to `RKBY_DATA_DIR`'s `.gitignore`, and git cannot
      re-include a file via a `!negation` pattern once its parent directory itself is
      excluded — so a plain `git add reports/rider_pairings.md` would otherwise fail
      and FR-014's auto-commit would silently never happen
- [ ] T017 [US1] Implement `scripts/generate_rider_pairings.py`: `load_config()`/
      `ConfigError`, `build_arg_parser()` (`--max-suggestions`, `--pdf`, `--pdf-only`),
      and `main()` wiring `rkby_records.discover_seasons`/`load_existing_records`
      (every season, needed for cross-season history) →
      `rkby_pairing.eligibility` → `rkby_pairing.ranking` →
      `rkby_pairing.report`'s renderer → write `reports/rider_pairings.md` (after
      `rkby_report.frame.ensure_reports_dir_and_gitignore`) →
      `auto_commit(..., force=True)` → optional `rkby_pairing.pdf` render for
      `--pdf`/`--pdf-only`; log every skipped (excluded/ignored/ungeocoded) member via
      `rkby_records.setup_run_logger` (contracts/report-output.md § Skipped members) —
      makes T011 pass

**Checkpoint**: User Story 1 is fully functional and independently testable — this is
the MVP. `uv run scripts/generate_rider_pairings.py` produces a complete report with
mentor suggestions, contact info, and photos; `--pdf`/`--pdf-only` both work; hand-edits
survive a `--pdf-only` export and remain recoverable from git history after the next
regeneration.

---

## Phase 4: User Story 2 - Surface training clusters of nearby riders (Priority: P2)

**Goal**: Groups of three or more current-season Riders (any experience level) living
close enough together are reported as training clusters, riders-only, independent of
the one-to-one mentor suggestions.

**Independent Test**: Run the script against a data set with a tight geographic group of
three or more riders and confirm they are reported together as one cluster, separately
from the individual mentor suggestions.

### Tests for User Story 2 ⚠️

- [ ] T018 [P] [US2] Extend `tests/unit/test_clustering.py` with failing tests for
      `find_overlap_groups()`'s new optional `distance_fn` and `min_group_size`
      parameters (research.md §7): a custom `distance_fn` (e.g. real-valued distances)
      is used instead of the default pixel-Euclidean `_distance`; `min_group_size=3`
      excludes a connected component of size 2 that the existing default
      (`min_group_size=2`) would include; every existing test in this file keeps
      passing unmodified, confirming the new parameters' defaults preserve current
      behavior exactly
- [ ] T019 [P] [US2] Write failing tests in `tests/unit/test_rkby_pairing_clusters.py`
      against the T003 fixtures for `find_training_clusters()` (FR-007, data-model.md §
      Training Cluster, Acceptance Scenarios 2.1-2.3): 3+ nearby current-season Riders
      (any experience level) form one cluster; 2 nearby Riders with no third nearby
      form no cluster; a Service Crew/Supporter member living inside an
      otherwise-qualifying cluster's footprint is never a member of it (never even a
      node in the graph); `cluster_radius_km` changes which groups qualify
- [ ] T020 [P] [US2] Extend `tests/unit/test_rkby_pairing_report.py` with failing tests
      for a populated `## Training Clusters` section: one `### Cluster N (<count>
      riders)` subsection per cluster, each member shown with the same full
      contact-info+photo treatment as a New Rider/Suggested Contact (reusing T014's
      shared helper, not a second copy)
- [ ] T021 [P] [US2] Extend `tests/unit/test_generate_rider_pairings_cli.py` with
      failing tests for `--cluster-radius-km` (positive-number validation mirroring
      `--max-suggestions`, default `5`) and for the CLI's end-to-end wiring of computed
      clusters into the written report (a fixture-derived tight cluster from T003
      appears in the written `reports/rider_pairings.md`)

### Implementation for User Story 2

- [ ] T022 [US2] Generalize `find_overlap_groups()` in
      `scripts/rkby_maps/clustering.py` with two new optional, backward-compatible
      parameters — `distance_fn: Callable[[tuple[float, float], tuple[float, float]],
      float] = _distance` and `min_group_size: int = 2` — per the signature in
      research.md §7; both existing call sites in `scripts/generate_member_maps.py`
      keep working unchanged — makes T018 pass
- [ ] T023 [US2] Implement `find_training_clusters()` in
      `scripts/rkby_pairing/clusters.py`, calling `find_overlap_groups(positions,
      radius=cluster_radius_km / 2, distance_fn=haversine_km, min_group_size=3)` over
      the latest season's Rider-role-only pool (reusing `eligibility.is_eligible_base()`
      from T012 and `roles.classify_role()` from T005) — makes T019 pass
- [ ] T024 [US2] Extend the report renderer in `scripts/rkby_pairing/report.py` to
      render a populated `## Training Clusters` section from real
      `find_training_clusters()` output, reusing T014's shared contact-info+photo
      helper — makes T020 pass
- [ ] T025 [US2] Add `--cluster-radius-km` to `build_arg_parser()` and wire
      `find_training_clusters()` into `main()` in `scripts/generate_rider_pairings.py`
      — makes T021 pass

**Checkpoint**: Both user stories are independently functional — feature complete.
`uv run scripts/generate_rider_pairings.py --cluster-radius-km 8` reports training
clusters alongside mentor suggestions.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Bring documentation and the full test/lint suite in line with the
now-complete feature.

- [ ] T026 [P] Add a "Running the rider pairing suggester" section to `README.md`
      (mirroring the existing per-script sections, e.g. "Running the map generator")
      documenting `scripts/generate_rider_pairings.py`'s flags (`--max-suggestions`,
      `--cluster-radius-km`, `--pdf`, `--pdf-only`) and output location; update the
      project-structure listing and the "implemented" scripts statement near the top of
      the file to include it
- [ ] T027 [P] Walk through `specs/006-rider-pairing-suggester/quickstart.md` Scenarios
      1-5 end-to-end against a throwaway synthetic `RKBY_DATA_DIR` (never real member
      data) — confirm every documented "Expected outcome" holds, including that a
      hand-edit survives a `--pdf-only` export, and that a subsequent regeneration's
      auto-commit still leaves the hand-edited version recoverable via `git show
      <commit>:reports/rider_pairings.md` in that repo's history
- [ ] T028 Run `uv run ruff check .`, `uv run ruff format .`, and `uv run pytest` for
      the full suite; fix any lint/format/test failures before considering the feature
      done

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. T005 depends on T004. T003 is
  independent of T004/T005. **Blocks all user stories.**
- **User Stories (Phase 3-4)**: All depend on Foundational completion.
  - US1 (P1): No dependency on US2. Within US1: T012 depends on T006; T013 depends on
    T007; T014 depends on T008; T015 depends on T009; T016 depends on T010; T017
    depends on T011 and on T012-T016 all being in place (it wires all of them
    together, so it is implemented last within this story).
  - US2 (P2): Depends on Foundational, and reuses two US1 outputs by design —
    `eligibility.is_eligible_base()` (T012) and `report.py`'s shared contact-info+photo
    helper (T014) — so it is implemented after US1 in practice, per spec.md's priority
    order, even though it adds no new fields to any US1 entity. Within US2: T022
    depends on T018; T023 depends on T019 (and on T012); T024 depends on T020 (and on
    T014); T025 depends on T021 (and on T023, T024).
- **Polish (Phase 5)**: Depends on both user stories being complete.

### Within Each User Story

- Failing tests (T0xx marked ⚠️ section) are written and confirmed failing before their
  matching implementation task.
- `eligibility.py`/`clusters.py` (who's eligible) before `ranking.py` (how they're
  ranked) before `report.py` (how it's rendered) before `pdf.py`/the CLI (how it's
  exported/orchestrated).
- Story complete (checkpoint) before moving to the next priority.

### Parallel Opportunities

- T001 and T002 (Setup) run in parallel — different files.
- T003 and T004 (Foundational) run in parallel — different files, no dependency between
  them; T005 follows T004.
- Within US1: T006, T007, T008, T009, T010, T011 (six different files) run in
  parallel with each other.
- Within US2: T018, T019, T020, T021 (four different files) run in parallel with each
  other.
- T026 and T027 (Polish) run in parallel — different concerns, no shared file.

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all six US1 test-writing tasks together:
Task: "eligibility tests in tests/unit/test_rkby_pairing_eligibility.py (T006)"
Task: "ranking tests in tests/unit/test_rkby_pairing_ranking.py (T007)"
Task: "report tests in tests/unit/test_rkby_pairing_report.py (T008)"
Task: "PDF tests in tests/unit/test_rkby_pairing_pdf.py (T009)"
Task: "auto_commit force-param tests in tests/unit/test_rkby_records.py (T010)"
Task: "CLI tests in tests/unit/test_generate_rider_pairings_cli.py (T011)"
```

## Parallel Example: User Story 2 Tests

```bash
# Launch all four US2 test-writing tasks together:
Task: "find_overlap_groups distance_fn/min_group_size tests in tests/unit/test_clustering.py (T018)"
Task: "training-cluster tests in tests/unit/test_rkby_pairing_clusters.py (T019)"
Task: "populated Training Clusters section tests in tests/unit/test_rkby_pairing_report.py (T020)"
Task: "--cluster-radius-km CLI tests in tests/unit/test_generate_rider_pairings_cli.py (T021)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (fixtures, `classify_role()`).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: run quickstart.md Scenarios 1-4 against synthetic data — a
   new rider gets a ranked, non-empty suggestion list; an excluded/ignored/ungeocoded
   member never appears anywhere; a hand-edit survives `--pdf-only`; a regeneration's
   auto-commit leaves the prior hand-edited version recoverable from git history.
5. This is a usable deliverable on its own.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. Add US1 → validate independently → MVP (mentor suggestions, contact info, photos,
   PDF export, auto-commit).
3. Add US2 → validate independently (training clusters, riders-only).
4. Polish → docs, full quickstart walkthrough, lint/format/test pass.

### Notes

- [P] tasks touch different files and have no unfinished same-phase dependency.
- Every implementation task has a preceding failing-test task per Constitution
  Principle V (red-green) — do not skip ahead to implementation.
- Commit after each task or logical group; stop at any checkpoint to validate a story
  independently.
- `scripts/rkby_maps/clustering.py`'s `find_overlap_groups()` generalization (T022) and
  `scripts/rkby_records.py`'s `auto_commit()` `force` parameter (T016) are both
  behavior-preserving for every existing caller — their existing test suites must pass
  unmodified, not be rewritten to match the change.
- Never use real member data in any fixture or test (Constitution I/V) — T003's
  fixtures are synthetic, shaped like real records.
- T016's `force=True` auto-commit path only exists because `ensure_reports_dir_and_gitignore`
  gitignores the whole `reports/` directory in `RKBY_DATA_DIR` — don't remove or
  "simplify away" the `force` parameter without re-checking that FR-014's commit still
  actually happens (T011/T027 are what verify it).
