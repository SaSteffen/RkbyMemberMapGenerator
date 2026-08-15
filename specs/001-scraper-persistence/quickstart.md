# Quickstart: Applicant Scraper & Data Persistence

Validation guide for this feature once implemented. Assumes `uv sync` has already been
run in the repo root (see root `CLAUDE.md`).

## Prerequisites

- A local, already-initialized git repository to act as the data store (spec
  Assumptions — this feature does not create it). Any empty git repo works for
  validation, e.g.:

  ```bash
  mkdir -p /tmp/rkby-data && cd /tmp/rkby-data && git init -q && cd -
  ```

- A `.env` (gitignored, repo root) or exported shell variables providing:

  ```bash
  export RKBY_INTRANET_USERNAME="..."
  export RKBY_INTRANET_PASSWORD="..."
  export RKBY_DATA_DIR="/tmp/rkby-data"
  ```

## Scenario 1 — First-time scrape of a season (Story 1)

```bash
uv run scripts/scrape_applicants.py --season 2025-26
```

**Expect**: `$RKBY_DATA_DIR/seasons/2025-26/applicants/*.yaml` created, one file per
non-"no" applicant across every result page; `photos/` populated for applicants whose
photo fetch succeeded; a `logs/<timestamp>.log` file exists. No file for any applicant
whose observed status was `"no"`. Since the Prerequisites step above `git init`'d
`RKBY_DATA_DIR`, this run auto-commits its own changes (contracts/cli-and-env.md §Auto-
commit behavior) — confirm with:

```bash
git -C "$RKBY_DATA_DIR" log --oneline -1
```

## Scenario 2 — Re-run is a no-op on unchanged data (Story 2, SC-002)

```bash
git -C "$RKBY_DATA_DIR" rev-parse HEAD > /tmp/head-before
uv run scripts/scrape_applicants.py --season 2025-26
git -C "$RKBY_DATA_DIR" status --porcelain
git -C "$RKBY_DATA_DIR" rev-parse HEAD > /tmp/head-after
diff /tmp/head-before /tmp/head-after
```

**Expect**: empty `git status` output and identical HEAD before/after — zero changes
and no new commit from the second run when nothing changed upstream.

## Scenario 3 — Manual corrections survive a re-run (Story 2, SC-003)

```bash
# hand-edit one field the scraper already filled in, e.g. birthday, in
# $RKBY_DATA_DIR/seasons/2025-26/applicants/<someone>.yaml
uv run scripts/scrape_applicants.py --season 2025-26
```

**Expect**: the hand-edited field is unchanged after the re-run; any genuinely new
applicant since the last run is still added as a new file.

## Scenario 4 — Marking a record ignored (Story 3, SC-004)

```bash
# set `ignore: true` by hand in one applicant's yaml file
uv run scripts/scrape_applicants.py --season 2025-26
```

**Expect**: that file is byte-for-byte unchanged; the record is not recreated even if
the same person still appears in the scrape.

## Scenario 5 — Status flips to "no" for an already-persisted applicant (Story 4)

Requires a fixture/mocked run where a previously non-"no" applicant is now observed as
"no" (covered by the automated unit tests, not easily reproduced against the live site
on demand).

**Expect**: the record stays present with `excluded: true` and a populated
`excluded_observed_at`; all its other fields are unchanged; a warning line appears in
that run's log.

## Running the automated test suite

```bash
uv run pytest
```

**Expect**: all unit tests pass using recorded/obfuscated fixtures under
`tests/fixtures/` — no real network calls are made (FR-021). This is the primary way to
exercise the edge cases (overwrite protection, ignore handling, status-flip exclusion,
within-season deduplication, schema validation failure, all-or-nothing rollback on
mid-pagination failure, per-applicant photo-fetch failure, missing/invalid environment
variables) without touching the live intranet or any real member data.

## After a real run: reviewing data changes

If `RKBY_DATA_DIR` is a git repository, the run already committed its own changes
(scoped to `seasons/<season-label>/`, research.md §14) — review what it did with:

```bash
git -C "$RKBY_DATA_DIR" show --stat HEAD
```

If `RKBY_DATA_DIR` is not a git repository, nothing is committed automatically; the
written files are still there under `seasons/<season-label>/`, just without any git
history layered on top.
