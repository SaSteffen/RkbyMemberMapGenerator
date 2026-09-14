# Tasks: Applicant Note Field

**Input**: Design documents from `/specs/008-applicant-note-field/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/applicant-record.schema.json, quickstart.md

**Tests**: Constitution Principle V (Test-First Development, NON-NEGOTIABLE) overrides
the generic template's "Tests are OPTIONAL" default for this repo. Every task list here
is generated to strict test-first, red-green ordering: tests are written and confirmed
failing before the corresponding implementation task.

## Path Conventions

Single-script project (Constitution II) — this feature adds no new files. All tasks
edit one of four existing files:
- `scripts/scrape_applicants.py` (parsing, merge/conflict, persistence)
- `scripts/rkby_records.py` (field order / backfill)
- `scripts/schemas/applicant_record.schema.json` (schema)
- `tests/unit/test_parsing.py`, `tests/unit/test_store_merge.py`,
  `tests/unit/test_schema_validation.py`, and fixture `tests/fixtures/applicants_page_1.html`

Because almost every task touches one of a small handful of shared files, `[P]` is used
sparingly — only for genuinely independent files that can be edited without conflicting
with another in-flight task.

---

## Phase 1: Setup

- [ ] T001 Add a non-blank `Note` value to at least one `<tr>` in
  `tests/fixtures/applicants_page_1.html` (keep the rest blank, matching real-world
  sparsity), so parsing tests have both a populated and a blank case to assert against.

**Checkpoint**: Fixture has both a non-blank and a blank Note cell available for tests.

---

## Phase 2: Foundational

No cross-story blocking work beyond the fixture update above — both user stories read
from the same `note` field and share the same `_CONFLICT_FIELDS`-driven merge machinery
already in place for `role`/`address`/`phone`. Proceed directly to User Story 1.

---

## Phase 3: User Story 1 - Capture the internal note when scraping (Priority: P1) 🎯 MVP

**Goal**: Every retained applicant's persisted record carries their intranet Note text
(or `null` if blank), including backfill of records persisted before this feature
existed.

**Independent Test**: Scrape a season with one applicant whose Note is non-blank and one
whose Note is blank; verify the first's persisted `note` holds that text and the
second's is `null`.

### Tests for User Story 1 (write first, confirm RED)

- [ ] T002 [US1] Add
  `test_parse_applicant_rows_extracts_note_raw_from_the_note_column` to
  `tests/unit/test_parsing.py`, asserting `parse_applicant_rows` returns the non-blank
  Note text from T001's fixture row for `row["note"]`, mirroring
  `test_parse_applicant_rows_extracts_role_raw_from_the_role_column`.
- [ ] T003 [US1] Add
  `test_parse_applicant_rows_reports_none_note_when_note_column_is_blank` to
  `tests/unit/test_parsing.py`, asserting a blank Note cell yields `row["note"] is None`,
  mirroring `test_parse_applicant_rows_reports_none_role_when_role_column_is_blank`.
- [ ] T004 [US1] Add `test_validate_record_accepts_a_note_value` and
  `test_validate_record_accepts_a_record_missing_the_note_key_entirely` to
  `tests/unit/test_schema_validation.py`, mirroring
  `test_validate_record_accepts_a_role_value` /
  `test_validate_record_accepts_a_record_missing_the_role_key_entirely`.
- [ ] T005 [US1] Add `test_merge_record_fills_note_when_previously_empty` to
  `tests/unit/test_store_merge.py`, mirroring
  `test_merge_record_fills_role_when_previously_empty`.
- [ ] T006 [US1] Add `test_record_persisted_before_note_existed_can_still_be_rewritten`
  to `tests/unit/test_store_merge.py`, mirroring
  `test_record_persisted_before_role_existed_can_still_be_rewritten` — asserts a record
  YAML missing the `note` key entirely gets `note` backfilled (as `null` or scraped text)
  on the next run without disturbing any other field.
- [ ] T007 [US1] Run `uv run pytest tests/unit/test_parsing.py
  tests/unit/test_store_merge.py tests/unit/test_schema_validation.py` and confirm the
  five new tests from T002-T006 fail (RED) for the expected reason (missing `note`
  support), not for an unrelated error.

### Implementation for User Story 1

- [ ] T008 [US1] In `scripts/schemas/applicant_record.schema.json`, add the `note`
  property (`type: ["string", "null"]`, description as in data-model.md) directly after
  `role`, matching the copy already staged in
  `specs/008-applicant-note-field/contracts/applicant-record.schema.json`.
- [ ] T009 [US1] In `scripts/rkby_records.py`, add `"note"` to `_RECORD_FIELD_ORDER`
  directly after `"role"`, so `_dump_record_yaml`'s existing `.get()`-based backfill
  picks it up automatically.
- [ ] T010 [US1] In `scripts/scrape_applicants.py`'s `parse_applicant_rows`, extract
  `row["note"] = cell["Note"].get_text(strip=True) or None` alongside the existing
  `Role`/`Address`/`Phone` cell reads.
- [ ] T011 [US1] In `scripts/scrape_applicants.py`'s `persist_records`, add
  `"note": row.get("note")` to the new-record dict alongside the other list-row-sourced
  fields.
- [ ] T012 [US1] Run `uv run pytest tests/unit/test_parsing.py
  tests/unit/test_store_merge.py tests/unit/test_schema_validation.py` and confirm all
  tests from T002-T006 now pass (GREEN), along with the full pre-existing suite in those
  three files.

**Checkpoint**: User Story 1 is independently complete — new and backfilled records both
carry a correct `note` value.

---

## Phase 4: User Story 2 - Manual corrections and "ignore" survive re-runs (Priority: P2)

**Goal**: A hand-edited/cleared `note` and any `note` on an "ignore"-marked record are
never overwritten by a later scrape, reusing the fill-empty-only and ignore-freeze
guarantees already proven for `address`/`phone`/`role`.

**Independent Test**: Hand-edit a persisted `note`, re-run the scraper, and confirm it is
unchanged even though the intranet still shows Note text; separately, mark a record
"ignore" and confirm its `note` is untouched regardless of intranet content.

### Tests for User Story 2 (write first, confirm RED)

- [ ] T013 [US2] Add `test_merge_record_keeps_a_hand_corrected_note_even_when_scraped_value_differs`
  to `tests/unit/test_store_merge.py`, mirroring
  `test_merge_record_keeps_a_hand_corrected_role_even_when_scraped_value_differs`.
- [ ] T014 [US2] Extend `test_ignored_record_is_byte_for_byte_unchanged_even_if_person_reappears`
  in `tests/unit/test_store_merge.py` (or add a sibling case) so the ignored fixture
  record carries a non-null `note` and the assertion covers `note` staying byte-for-byte
  unchanged alongside the fields it already checks.
- [ ] T015 [US2] In `scripts/scrape_applicants.py`, add `"note"` to `_CONFLICT_FIELDS`.
  Add `test_deduplicate_scraped_rows_flags_conflicting_note_values_within_one_scrape` to
  `tests/unit/test_store_merge.py` (or the module already covering
  `deduplicate_scraped_rows` conflicts, per the file `_CONFLICT_FIELDS`-driven tests live
  in) asserting two same-person rows with disagreeing non-empty `note` values are flagged
  as a conflict and neither is persisted that run, mirroring the existing
  `address`/`phone`/`role` conflict-dedup coverage.
- [ ] T016 [US2] Run `uv run pytest tests/unit/test_store_merge.py` and confirm the three
  new tests from T013-T015 fail (RED) for the expected reason (note not yet in
  `_CONFLICT_FIELDS` / merge not yet fill-empty-only for note).

### Implementation for User Story 2

- [ ] T017 [US2] In `scripts/scrape_applicants.py`, add `"note"` to the
  `_CONFLICT_FIELDS` tuple (this single change drives `merge_record`'s fill-empty-only
  behavior, `_conflicting_fields`'s existing-vs-scraped conflict logging, and
  `deduplicate_scraped_rows`'s within-scrape conflict detection for `note`, per
  research.md §3 — no other code change is needed for this story).
- [ ] T018 [US2] Run `uv run pytest tests/unit/test_store_merge.py` and confirm all
  tests from T013-T015 now pass (GREEN), along with the full pre-existing suite in that
  file.

**Checkpoint**: User Story 2 is independently complete — manual edits and "ignore" both
protect `note` exactly as they already protect every other optional field.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T019 Run `uv run ruff check .` and `uv run ruff format .` across the whole repo
  and fix any issues introduced by this feature's changes.
- [ ] T020 Run the full suite with `uv run pytest` and confirm zero failures/regressions.
- [ ] T021 Walk through `specs/008-applicant-note-field/quickstart.md` Scenarios 1-4
  manually against `$RKBY_DATA_DIR` (real intranet credentials available via existing
  env/direnv setup) to confirm end-to-end behavior beyond unit-test coverage, if a live
  run is practical at this time; skip with a note in the PR/commit if not.

---

## Dependencies & Execution Order

- **Phase 1 (Setup)** has no dependencies; do it first — both stories' tests read the
  fixture it touches.
- **Phase 2 (Foundational)**: none — no additional blocking work exists for this feature.
- **User Story 1 (Phase 3)**: depends only on Phase 1. This is the MVP; it alone
  delivers SC-001.
- **User Story 2 (Phase 4)**: depends on User Story 1's implementation (T008-T011) being
  in place, since it exercises merge/conflict behavior on a `note`-bearing schema and
  field order that Phase 3 introduces. Delivers SC-002 and SC-003.
- **Polish (Phase 5)**: after both stories are complete.

## Parallel Execution Opportunities

Within each story's test-writing block, tasks that touch different test files are
parallelizable:
- T002-T003 (`test_parsing.py`) can run in parallel with T004 (`test_schema_validation.py`)
  and T005-T006 (`test_store_merge.py`), since these are three separate files with no
  shared state — but note T002/T003 are sequential with each other (same file), as are
  T005/T006.
- T013-T014 and T015 all edit `tests/unit/test_store_merge.py` and are therefore
  sequential, not parallel, despite all being tagged [US2].

## Implementation Strategy

**MVP = User Story 1 only** (T001-T012): capturing and backfilling `note` is the entire
user-visible value this feature adds per spec.md. User Story 2 (T013-T018) is a
safety-net extension of guarantees the scraper already provides for every other optional
field, reusing a single tuple addition (`_CONFLICT_FIELDS`) — low effort, but delivered
as its own red-green phase to keep test-first discipline explicit per field-level
behavior, matching how specs/001-scraper-persistence's tasks.md treated analogous
stories.
