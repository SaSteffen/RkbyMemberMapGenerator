---

description: "Task list template for feature implementation"
---

# Tasks: Applicant Scraper & Data Persistence

**Input**: Design documents from `/specs/001-scraper-persistence/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: FR-021 explicitly requires automated unit tests covering the happy path and
every named edge case, using recorded/obfuscated fixtures and zero real network calls.
Constitution Principle V (Test-First Development / Red-Green, **NON-NEGOTIABLE**, added
in v1.1.0 after this task list was first drafted) requires every task list to be
regenerated to strict **test-first, red-green** ordering: within every phase below, the
test task(s) for a unit of behavior are written — and MUST be confirmed failing — before
the implementation task(s) that make them pass. `[P]`-marked test tasks in the same
block may be written in any order/parallel; the implementation tasks that follow depend
on their corresponding tests already existing and failing.

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P1/P2/P2/P3/P3)
to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task in this batch)
- **[Story]**: Which user story this task belongs to (US1–US6)
- Every task names an exact file path

## Path Conventions

Single-script project (Constitution II — one script, one artifact; see plan.md
"Structure Decision"), **not** the generic `src/`+`tests/` layout:

- `scripts/scrape_applicants.py` — the one script this whole feature lives in
- `scripts/schemas/applicant_record.schema.json` — runtime copy of the JSON Schema contract
- `tests/unit/*.py`, `tests/fixtures/*.html` — at repo root, per existing project convention

Because almost every implementation task edits the same single file
(`scripts/scrape_applicants.py`), most implementation tasks are **sequential** even
within a phase — `[P]` is reserved for genuinely different files (fixtures, distinct
test modules, the schema copy, README).

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding for this feature. No behavior yet, so no test-first
cycle applies.

- [X] T001 Create directory structure: `scripts/`, `scripts/schemas/`, `tests/unit/`, `tests/fixtures/`
- [X] T002 Add `requests`, `beautifulsoup4`, `PyYAML`, `jsonschema` to `[project] dependencies` and `responses` to `[dependency-groups] dev` in `pyproject.toml`, then run `uv sync`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infrastructure every user story needs before its own logic can be written —
config validation, season-label handling, match-key normalization, schema validation,
storage layout, logging.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational (write first — confirm RED before any implementation below)

- [X] T003 [P] Copy `specs/001-scraper-persistence/contracts/applicant-record.schema.json` to `scripts/schemas/applicant_record.schema.json` (data asset, prerequisite for T007's schema-validation tests; not itself behavior under test)
- [X] T004 [P] Write unit tests for `default_season_label(today)` (Jan–Jul → `(Y-1)-Y`, Aug–Dec → `Y-(Y+1)`) and `parse_season_arg(value)` (accepts `YYYY/YY` or `YYYY-YY`, normalizes to hyphen form), including the July/August boundary, in `tests/unit/test_season.py` (FR-022). Run `uv run pytest tests/unit/test_season.py` and confirm it fails (the functions don't exist yet).
- [X] T005 [P] Write unit tests for `Config`/`load_config()`: each missing/invalid required env var (`RKBY_INTRANET_USERNAME`, `RKBY_INTRANET_PASSWORD`, `RKBY_DATA_DIR`) fails clearly before any network or file I/O, in `tests/unit/test_config.py` (FR-023). Confirm RED.
- [X] T006 [P] Write unit tests for `normalize_name()`/`match_key(first_name, last_name)` (unicodedata NFKD strip, lowercase, hyphen-join) in `tests/unit/test_records.py` (FR-013). Confirm RED.
- [X] T007 [P] Write unit tests for schema validation: a valid record passes, a structurally invalid record raises a clear error, in `tests/unit/test_schema_validation.py` (FR-017). Depends on T003's schema file existing. Confirm RED.
- [X] T008 [P] Write a unit test asserting the run logger writes a per-run timestamped `WARNING`+ file under `<season>/logs/` and streams `INFO`+ to the console, in `tests/unit/test_logging.py` (FR-016). Confirm RED.

### Implementation for Foundational (make T004–T008 pass — GREEN)

- [X] T009 Create `scripts/scrape_applicants.py` with a `Config` dataclass and `load_config()` that validates `RKBY_INTRANET_USERNAME`, `RKBY_INTRANET_PASSWORD`, and `RKBY_DATA_DIR` (present, `RKBY_DATA_DIR` exists and is a directory) before any network request or file write, making T005 pass (FR-023)
- [X] T010 Add `default_season_label(today)`/`parse_season_arg(value)` to `scripts/scrape_applicants.py`, making T004 pass (FR-022)
- [X] T011 Add `normalize_name()`/`match_key(first_name, last_name)` to `scripts/scrape_applicants.py`, making T006 pass (FR-013)
- [X] T012 Add `load_schema()`/`validate_record(record: dict)` using `jsonschema` against `scripts/schemas/applicant_record.schema.json` to `scripts/scrape_applicants.py`, making T007 pass (FR-017)
- [X] T013 Add season directory-layout helpers (`season_dir`, `applicants_dir`, `photos_dir`, `logs_dir` under `RKBY_DATA_DIR/seasons/<label>/`) and run-logger setup (per-run timestamped `WARNING`+ `FileHandler` under `<season>/logs/`, `INFO` `StreamHandler` to console) to `scripts/scrape_applicants.py`, making T008 pass (FR-016)

**Checkpoint**: Foundation ready and green (`uv run pytest tests/unit/test_season.py tests/unit/test_config.py tests/unit/test_records.py tests/unit/test_schema_validation.py tests/unit/test_logging.py`) — user story implementation can now begin.

---

## Phase 3: User Story 1 - First-time scrape of a season (Priority: P1) 🎯 MVP

**Goal**: Running the scraper against a season with no prior local data persists one
record + photo for every non-"no" applicant, across every result page, defaulting the
season from today's date when `--season` is omitted.

**Independent Test**: Run the scraper once against a season with no prior local data;
verify a season folder is created containing one persisted record (with photo) per
non-"no" applicant, and no record for any "no"-status applicant.

### Fixtures + Tests for User Story 1 (write first — confirm RED before implementation)

- [X] T014 [P] [US1] Create obfuscated fixture `tests/fixtures/login_page.html` (synthetic login form)
- [X] T015 [P] [US1] Create obfuscated fixture `tests/fixtures/applicants_page_1.html` (synthetic table including one "no"-status applicant)
- [X] T016 [P] [US1] Create obfuscated fixture `tests/fixtures/applicants_page_2.html` (synthetic second page, proving pagination)
- [X] T017 [P] [US1] Create obfuscated fixture `tests/fixtures/photo_popup.html` (synthetic full-resolution photo link; adapted per research.md §15 — the real site has no popup page, so this fixture instead demonstrates the thumbnail→full-res URL-transform pattern). Also added `tests/fixtures/season_selector_page.html` (not originally scoped, needed for T023's season resolution).
- [X] T018 [P] [US1] Write unit tests for `parse_applicant_rows()` and photo-popup URL resolution in `tests/unit/test_parsing.py`, using T015–T017's fixtures. Confirm RED (function doesn't exist yet).
- [X] T019 [P] [US1] Write unit tests for all-or-nothing rollback: a page-fetch failure mid-pagination leaves the season directory byte-for-byte untouched, in `tests/unit/test_rollback.py` (FR-018). Confirm RED.
- [X] T020 [P] [US1] Write unit tests for per-applicant photo-fetch failure isolation (other data still persisted, warning logged, photo left `null` for retry) in `tests/unit/test_photo_fetch.py` (FR-005). Confirm RED.
- [X] T021 [P] [US1] Write unit tests for the first-run persistence happy path: multi-page fetch, "no"-status exclusion, default-season selection, in `tests/unit/test_store_merge.py` (Story 1 AC1–AC3). Also assert: (a) a log file exists under `<season>/logs/` after the run even though it produced no warnings (FR-016 "every execution"); (b) every newly-written record, read back and parsed, validates against `applicant-record.schema.json` (SC-005's completed-run half). Confirm RED.

### Implementation for User Story 1 (make T018–T021 pass — GREEN)

- [X] T022 [US1] Add `IntranetClient.login()` (POST credentials to the login form, retain the session cookie, detect an auth failure) to `scripts/scrape_applicants.py`, using T014's fixture
- [X] T023 [US1] Add season-selector fetch + label→(team_id, season_id) resolution to `scripts/scrape_applicants.py` (research.md §5, empirically confirmed §15)
- [X] T024 [US1] Add `parse_applicant_rows(html)` using BeautifulSoup to extract name/status/profile fields and the photo thumbnail URL per row to `scripts/scrape_applicants.py`, making T018 pass. Empirically confirmed (research.md §15): address/phone ARE present in-row; birthday is NOT and no detail-page endpoint exists from this view, so `birthday` is left `null` (documented, not silently dropped).
- [X] T025 [US1] Add `fetch_all_pages(client, team_id, season_id)` iterating the `team_application_manager.php` AJAX endpoint until a page adds no previously-unseen applicant — network + parse only, no disk writes — to `scripts/scrape_applicants.py`, making T019 pass and contributing to T021 (FR-001, all-or-nothing phase split per research.md §10)
- [X] T026 [US1] Add `fetch_photo(client, thumbnail_url, logger, match_key)` resolving (strip the `?w=` resize query string, research.md §15) and downloading the full-resolution image, catching/logging any failure without raising, to `scripts/scrape_applicants.py`, making T020 pass (FR-005)
- [X] T027 [US1] Add create-only persistence (`persist_new_records`: write a new `ApplicantRecord` YAML + photo per non-"no" row for a season with no prior data) to `scripts/scrape_applicants.py`, making T021 pass (FR-003, FR-004, FR-006)
- [X] T028 [US1] Wire the CLI entrypoint (`argparse --season`, `main()`) orchestrating login → resolve season → fetch all pages → filter "no" → persist → log run summary, in `scripts/scrape_applicants.py`, fully making T021 pass. `main()` calls `load_config()` (T009) first and lets it raise before `IntranetClient.login()` or any file write is reachable — this is what actually satisfies FR-023 for the MVP; T044 only adds Story 6's explicit end-to-end verification on top of this, it does not introduce a second validation path

**Checkpoint**: User Story 1 is fully functional and independently testable (MVP), all US1 tests green.

---

## Phase 4: User Story 2 - Re-run without losing manual corrections (Priority: P1)

**Goal**: Re-running the scraper for a season with existing, possibly hand-edited data
never overwrites a field or photo that already has a value, while still adding
genuinely new applicants.

**Independent Test**: Manually edit a field and replace a photo in an already-persisted
record, re-run the scraper against the same season, and verify the edit and photo are
unchanged while any genuinely new applicant is still added.

### Tests for User Story 2 (write first — confirm RED before implementation)

- [X] T029 [P] [US2] Unit tests: a hand-edited field survives a re-run; a genuinely new applicant is still added, in `tests/unit/test_store_merge.py` (Story 2 AC1, AC3). Also assert the pure-idempotency case (SC-002): merging identical, unchanged scraped input against an already-persisted season twice in a row writes/touches zero files the second time. Confirm RED.
- [X] T030 [P] [US2] Unit tests: an existing photo file is never overwritten by a later run, in `tests/unit/test_photo_fetch.py` (Story 2 AC2). Confirm RED.
- [X] T031 [P] [US2] Unit tests: a schema-invalid existing record aborts the run without writing or losing data, in `tests/unit/test_schema_validation.py` (FR-017 edge case). Confirm RED.

### Implementation for User Story 2 (make T029–T031 pass — GREEN)

- [X] T032 [US2] Add `load_existing_records(data_dir, season_label)` validating each file against the schema and raising `InvalidExistingRecordError` on any invalid file to `scripts/scrape_applicants.py`, making T031 pass (FR-017)
- [X] T033 [US2] Add `merge_record(existing, scraped)` applying the fill-empty-only field rule — `status` frozen at creation, never rewritten — to `scripts/scrape_applicants.py`, contributing to T029 (FR-009)
- [X] T034 [US2] Add a photo overwrite guard (`_photo_file_exists`): skip photo fetch/write when the season's photo file for a `match_key` already exists on disk, in `scripts/scrape_applicants.py`, making T030 pass (Story 2 AC2)
- [X] T035 [US2] Replace the create-only `persist_new_records` from T027 with the load-existing → merge → write-only-changed `persist_records()` flow, wired into `main()`, in `scripts/scrape_applicants.py`, fully making T029 pass. (T027's US1 tests were updated in place to call the renamed `persist_records` — behavior on a from-scratch season is unchanged, so they still verify the same guarantees per tasks.md's regression-check intent.)

**Checkpoint**: User Stories 1 and 2 both work independently, all US1+US2 tests green.

---

## Phase 5: User Story 3 - Marking a record ignored (Priority: P2)

**Goal**: A record marked `ignore: true` is never modified or recreated by any future
run, regardless of what the scraper observes for that person.

**Independent Test**: Mark a persisted record "ignore", re-run the scraper against the
same season multiple times, and verify the record is never modified and never
duplicated even if the same person still appears in the scrape.

### Tests for User Story 3 (write first — confirm RED before implementation)

- [X] T036 [US3] Unit tests: an `ignore == true` record is byte-for-byte unchanged across repeated runs, even when the same person reappears in the scrape, in `tests/unit/test_store_merge.py` (Story 3 AC1). Confirm RED.

### Implementation for User Story 3 (make T036 pass — GREEN)

- [X] T037 [US3] Add an `ignore`-flag short-circuit to the `persist_records()` orchestration loop: a persisted record with `ignore == true` is skipped entirely — no field writes, no photo fetch, no recreation — in `scripts/scrape_applicants.py`, making T036 pass (FR-010, FR-011)

**Checkpoint**: User Stories 1–3 independently functional, all green.

---

## Phase 6: User Story 4 - Automatic exclusion on disapproval (Priority: P2)

**Goal**: When a previously-persisted, non-ignored applicant is later observed with
status "no", the record is marked excluded with an observed-at timestamp (not deleted),
its other fields stay untouched, and a warning is logged — unless the record is already
ignored, in which case nothing happens.

**Independent Test**: Persist a record with a non-"no" status, then have a later scrape
observe status "no" for that same applicant, and verify the record remains present but
is marked excluded with an observed-at timestamp, and a warning appears in that run's
log.

### Tests for User Story 4 (write first — confirm RED before implementation)

- [X] T038 [US4] Unit tests: a status flip to "no" sets `excluded`+timestamp+warning with other fields unchanged (AC1); an ignored record observing "no" produces no exclusion flag and no log entry (AC2); a never-before-seen "no" is still never persisted (FR-003 stays correct now that main() no longer pre-filters), in `tests/unit/test_store_merge.py` (Story 4). Confirm RED.

### Implementation for User Story 4 (make T038 pass — GREEN)

- [X] T039 [US4] Add status-flip-to-"no" detection directly in `persist_records()`'s loop (not `merge_record()`, which stays a pure fill-empty-only helper): for a non-ignored existing record, set `excluded = true` + `excluded_observed_at = now` and log a `WARNING`, leaving every other field untouched — the T037 ignore short-circuit already prevents this from firing on ignored records — in `scripts/scrape_applicants.py`, making T038 pass (FR-015, FR-016). Also moved the FR-003 "no"-status filter from `main()` into `persist_records()` itself, since that decision now depends on whether a matching record already exists (create-skip vs. mark-excluded), not on the row alone.

**Checkpoint**: User Stories 1–4 independently functional, all green.

---

## Phase 7: User Story 5 - Deduplicating repeated entries within a season (Priority: P3)

**Goal**: The same person appearing twice within one season's scrape (overlapping
pages, duplicate applications) results in a single persisted record when details agree,
and is flagged for human review rather than silently merged when they don't — the same
rule applies when a fresh scrape conflicts with an already-persisted record.

**Independent Test**: Feed the scraper a mocked applicant list containing the same
first and last name twice within one season, and verify only one persisted record
results (or a logged conflict, per the differing-details case).

### Tests for User Story 5 (write first — confirm RED before implementation)

- [X] T040 [US5] Unit tests: consistent within-scrape duplicates merge to one record (AC1); conflicting within-scrape duplicates are flagged and neither is persisted (AC2); a scraped row conflicting with an existing persisted record is flagged with its full snapshot and the existing file stays untouched (FR-014), in `tests/unit/test_records.py`. Also assert cross-season independence (FR-020): the same first+last name persisted in two different season folders never triggers matching, merging, or conflict-detection between them. Confirm RED.

### Implementation for User Story 5 (make T040 pass — GREEN)

- [X] T041 [US5] Add `deduplicate_scraped_rows()` to the persistence flow (called from `main()` right after `fetch_all_pages()`): group scraped rows by `match_key`, merge consistent duplicates into one candidate, log a `WARNING` and drop both from this run on a meaningful field conflict, in `scripts/scrape_applicants.py`, contributing to T040 (FR-013, Story 5)
- [X] T042 [US5] Add conflict-vs-persisted-record detection (`_conflicting_fields()`) in `persist_records()`'s normal-merge branch: a non-empty field disagreement between an existing record and a newly-scraped row logs a `WARNING` with the full new snapshot and leaves the existing file untouched (still via `merge_record()`'s existing fill-empty-only protection), in `scripts/scrape_applicants.py`, fully making T040 pass (FR-014). Cross-season independence (FR-020) holds by construction — `existing_records`/`persist_records` are always scoped to one `season_label` at a time.

**Checkpoint**: User Stories 1–5 independently functional, all green.

---

## Phase 8: User Story 6 - Credentials and storage location kept out of the repository (Priority: P3)

**Goal**: The scraper authenticates and persists successfully using only environment
variables for credentials and the data-folder path, and fails clearly — before any
network request or file write — when a required variable is missing.

**Independent Test**: Run the scraper with credentials and the data-folder path set
only via environment variables, confirm it authenticates and persists successfully;
then confirm a missing required variable fails clearly with no partial run.

### Tests for User Story 6 (write first — confirm RED before implementation)

- [X] T043 [US6] Unit tests: with valid env vars (mocked HTTP + a temp dir) a run authenticates and writes only under the configured `RKBY_DATA_DIR` (AC1); with a required env var missing, `main()` exits non-zero and makes zero HTTP calls and zero filesystem writes (AC2), in `tests/unit/test_config.py` (Story 6). Both passed immediately (GREEN on first run) — confirms T009/T028's existing ordering already satisfies this end-to-end.

### Implementation for User Story 6 (make T043 pass — GREEN)

- [X] T044 [US6] Verified (did not reimplement) that `load_config()` (T009) is the very first call in `main()`, strictly before `IntranetClient.login()` (T022) or any file write is reachable, per T028's ordering guarantee — guard/assertion pass only, no new validation function; T043 passed without any code change, confirming the ordering already holds.

**Checkpoint**: All 6 user stories independently functional, all green.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: The conditional git auto-commit behavior (spans every story's successful
run, not any single one) plus final verification.

### Tests (write first — confirm RED before implementation)

- [X] T045 [P] Unit test: force an `IntranetClient.login()` auth failure and assert the raw `RKBY_INTRANET_PASSWORD` value never appears in the run log file, console output, or any raised exception's message, in `tests/unit/test_config.py` (FR-002, SC-007 — Constitution I is NON-NEGOTIABLE). Passed immediately (GREEN) — `login()` never logs request/response bodies, so this stands as the regression guard for that invariant.
- [X] T046 Unit tests for auto-commit: a git-detected run creates a commit; a no-change re-run creates no commit; a non-git `RKBY_DATA_DIR` is a no-op; a commit failure logs a warning without changing the exit code, in `tests/unit/test_auto_commit.py`. Confirm RED.

### Implementation

- [X] T047 Add conditional git auto-commit (`auto_commit_season`) after a successful run — detect `RKBY_DATA_DIR` as a git work tree via `git rev-parse --is-inside-work-tree`, stage `seasons/<label>/`, skip if nothing staged, commit with a generated message (using the run's `created`/`excluded`/`photos_fetched` counts, now tracked in `persist_records()`'s summary), catch/log a commit failure as `WARNING` without affecting the run's exit code — to `scripts/scrape_applicants.py`, making T046 pass and wired into `main()` (research.md §14)
- [X] T048 [P] Update `README.md`: mark `scripts/scrape_applicants.py` as implemented, document the required env vars and `uv run scripts/scrape_applicants.py [--season ...]` usage

### Final verification

- [X] T049 Run `uv run ruff check .` and `uv run ruff format .` and fix any findings across `scripts/scrape_applicants.py` and `tests/`
- [X] T050 Run `uv run pytest` (full suite) and confirm every FR-021 edge case passes with zero real network calls — 78/78 passed
- [X] T051 Executed quickstart.md scenarios 1–4 for real against the live intranet and the actual `RKBY_DATA_DIR` (not a disposable dir — the real one was already an empty git repo, per the user). Scenario 1: 49 applicants created, 44 photos fetched, all 49 validate against the schema, auto-commit fired. Scenario 2: found and fixed a real bug this run surfaced (see below) — re-run is now a true no-op (identical HEAD, empty `git status`). Scenario 3: hand-edited a real record's address, re-ran, edit survived (and correctly triggered the FR-014 conflict warning). Scenario 4: hand-set `ignore: true` on a real record, re-ran, file byte-for-byte unchanged; test edits were reverted afterward with a clear commit message. Scenario 5 (status flip to "no") is, per quickstart.md itself, not easily reproduced against the live site on demand — already covered by T038's automated tests.
  - **Bug found via this live run, not caught by any prior unit test**: every run creates a fresh timestamped log file (FR-016) even when no applicant data changes; the original `auto_commit_season` staged the whole `seasons/<label>/` tree (per research.md §14's literal wording), so a pure no-op re-run still produced a new commit — violating SC-002/quickstart Scenario 2. Fixed by scoping `auto_commit_season` to `applicants/` + `photos/` (+ a one-time `.gitignore` for `logs/`, added via `_ensure_logs_gitignored()` in `setup_run_logger()`) instead of the whole season folder. Two new regression tests added test-first in `tests/unit/test_auto_commit.py` (confirmed RED, then GREEN) before the fix: `test_auto_commit_ignores_a_new_log_file_when_no_applicant_data_changed` and the integration-level `test_a_second_real_run_with_no_upstream_changes_leaves_git_status_empty`. Full suite: 80/80 passing.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories. Its own tests
  (T004–T008) must be written and confirmed RED before its implementation (T009–T013).
- **User Stories (Phase 3–8)**: All depend on Foundational completion. Written here in
  priority order (P1, P1, P2, P2, P3, P3) and each phase's implementation tasks build
  directly on the single script file the previous phase left off at — so, unlike a
  multi-service project, these phases are best executed **sequentially** in the order
  given, not fanned out to different contributors, even though each is independently
  *testable* once reached. Within each phase, its tests must be written and confirmed
  RED before its implementation tasks begin (Constitution Principle V).
- **Polish (Phase 9)**: Depends on all six user stories being complete (T047's
  auto-commit wraps the run these stories already built).

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational. Establishes the fetch→parse→persist
  pipeline every later story extends.
- **US2 (P1)**: Depends on US1 (extends US1's create-only persistence into a merge).
- **US3 (P2)**: Depends on US2 (`merge_record()` must exist before it can be
  short-circuited).
- **US4 (P2)**: Depends on US3 (the ignore short-circuit must exist before this story
  can rely on it taking precedence).
- **US5 (P3)**: Depends on US2 (`merge_record()`) and reuses `match_key()` from
  Foundational.
- **US6 (P3)**: Depends only on Foundational (`Config`/`load_config()` already do the
  heavy lifting from T009; this phase verifies the end-to-end guarantee, per T043/T044).

> **Note on "depends only on Foundational" above**: this describes *logical*
> requirement-dependency, not build order. US5 and US6 still can't actually be
> implemented before US1–US4 in practice — every implementation task in every phase
> edits the same `scripts/scrape_applicants.py`, so the phases must still be done in
> the sequential order given (see "Phase Dependencies" above) to avoid merge conflicts,
> even though nothing in US5/US6's own requirements forces that order.

### Within Each User Story

- Tests are written first and MUST be confirmed failing (red) before any implementation
  task in that phase begins (Constitution Principle V, NON-NEGOTIABLE).
- Implementation tasks touching `scripts/scrape_applicants.py` are sequential (same
  file).
- Fixture creation and test-writing tasks in different files are parallelizable with
  each other.

### Parallel Opportunities

- T004–T008 (Foundational tests) — five different files.
- T014–T017 (US1 fixtures) — four different files.
- T018–T021 (US1 tests) — four different files, once fixtures exist.
- T029–T031 (US2 tests) — three different files.
- T048 (README) can happen any time after the CLI interface is stable (effectively any
  time after Phase 3).
- T045 (credential-in-log test) — different file from T046–T051, only needs T013/T022
  done, so it can happen any time from Phase 3 onward, not just at the end.

---

## Parallel Example: Foundational tests

```bash
# Before any Foundational implementation task starts, these five can be written in any order/by anyone, then confirmed failing:
Task: "Unit tests for default-season computation in tests/unit/test_season.py"
Task: "Unit tests for Config env-var validation in tests/unit/test_config.py"
Task: "Unit tests for normalize_name/match_key in tests/unit/test_records.py"
Task: "Unit tests for schema validation in tests/unit/test_schema_validation.py"
Task: "Unit test for run-logger file+console output in tests/unit/test_logging.py"
```

## Parallel Example: User Story 1 fixtures

```bash
# Written before T018-T021's tests, which are in turn written before T022-T028's implementation:
Task: "Create tests/fixtures/login_page.html"
Task: "Create tests/fixtures/applicants_page_1.html"
Task: "Create tests/fixtures/applicants_page_2.html"
Task: "Create tests/fixtures/photo_popup.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks everything else; tests red, then green)
3. Complete Phase 3: User Story 1 (tests red, then green)
4. **STOP and VALIDATE**: run quickstart.md Scenario 1 against fixture-backed unit
   tests (`uv run pytest`); a first-time scrape persisting non-"no" applicants with
   photos, across pages, is a usable MVP on its own.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → test independently → usable MVP (first-time scrape works).
3. US2 → test independently → now safe to re-run without losing manual edits (the
   real "safe to run repeatedly" guarantee the feature exists for).
4. US3 → ignore flag respected.
5. US4 → status-flip exclusion tracked instead of silently vanishing.
6. US5 → within-season duplicates handled.
7. US6 → env-var-only config guarantee explicitly verified end-to-end.
8. Polish → auto-commit, lint, full test run, quickstart walkthrough.

Each increment adds value without breaking the previous one, and per-story unit tests
keep every earlier guarantee regression-checked as later stories are added.

---

## Notes

- `[P]` tasks = different files, no dependency on an incomplete task in the same batch.
- `[Story]` label maps a task to its user story for traceability.
- This is a single-script feature (Constitution II) — most parallelism opportunities
  are in fixtures/tests, not implementation, since implementation tasks share one file.
- Test-first, red-green ordering (Constitution Principle V, NON-NEGOTIABLE): within
  every phase, write and confirm-failing the phase's test task(s) before starting its
  implementation task(s); write the minimal code needed to go green; refactor only once
  green, without changing behavior.
- Commit after each task or logical group (see root `CLAUDE.md` — never touch `data/`
  or `.env`; only files under `scripts/`, `tests/`, and this feature's `specs/`
  directory are ever committed to this repository).
- Verify tests pass after each phase; stop at any checkpoint to validate a story
  independently before continuing.
