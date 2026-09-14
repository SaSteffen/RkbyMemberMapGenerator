# Quickstart: Applicant Note Field

Validation guide for this feature once implemented. Prerequisites and general
scraper setup are unchanged from specs/001-scraper-persistence/quickstart.md — this
adds only the scenarios specific to `note`.

## Scenario 1 — A new applicant's Note is captured (User Story 1)

```bash
uv run scripts/scrape_applicants.py --season 2025-26
```

**Expect**: for an applicant whose intranet row has non-blank Note text, the persisted
`$RKBY_DATA_DIR/seasons/2025-26/applicants/<match_key>.yaml` has `note: "<that text>"`.
For an applicant with a blank Note, that record's `note` is `null`.

```bash
grep -A0 '^note:' "$RKBY_DATA_DIR/seasons/2025-26/applicants/<match_key>.yaml"
```

## Scenario 2 — A manually-set or cleared note survives a re-run (User Story 2)

```bash
# hand-edit `note:` in one applicant's yaml file
uv run scripts/scrape_applicants.py --season 2025-26
```

**Expect**: the hand-edited `note` value is unchanged after the re-run, even if the
intranet still shows some Note text for that applicant (fill-empty-only).

## Scenario 3 — An "ignore"-marked record's note is untouched (User Story 2)

```bash
# set `ignore: true` by hand in one applicant's yaml file
uv run scripts/scrape_applicants.py --season 2025-26
```

**Expect**: that file, including `note`, is byte-for-byte unchanged.

## Scenario 4 — A pre-existing record is backfilled

```bash
# remove the `note:` line entirely from an already-persisted record, then re-run
uv run scripts/scrape_applicants.py --season 2025-26
```

**Expect**: `note` reappears (as `null`, or as the observed text) with every other field
in that record unchanged.

## Running the automated test suite

```bash
uv run pytest
```

**Expect**: all unit tests pass, including the new `note` coverage in
`tests/unit/test_parsing.py`, `tests/unit/test_store_merge.py`, and
`tests/unit/test_schema_validation.py` — no real network calls.
