# Quickstart: Validating the Rider Pairing Suggester

Prerequisites: `uv sync` has installed dependencies (including the two new ones this
feature adds, `markdown` and `xhtml2pdf`, once `pyproject.toml` is updated in the
implementation phase), and you have a local `RKBY_DATA_DIR` — either a real
`generate_member_maps.py`-processed data repository, or a synthetic one shaped like
`tests/fixtures/pairing_seasons/` (never real scraped data in this repo, Constitution
Principle V).

## 1. Generate the report

```bash
export RKBY_DATA_DIR=/path/to/your/local/data-repo
uv run scripts/generate_rider_pairings.py
```

**Expected outcome**: `$RKBY_DATA_DIR/reports/rider_pairings.md` exists (created if
absent) and contains:
- one `## New Riders` entry per latest-season member with role Rider, zero previous
  seasons, not excluded/ignored, geocoded — each with a ranked (possibly empty)
  suggested-contacts list, full contact info, and a photo link where one exists;
- one `## Training Clusters` entry per group of three or more geographically close
  current-season Riders.

If `RKBY_DATA_DIR` is a git work tree, `git log -1 -- reports/rider_pairings.md` in
that repository shows a new commit for this write.

## 2. Tune the ranking/clustering knobs

```bash
uv run scripts/generate_rider_pairings.py --max-suggestions 5 --cluster-radius-km 10
```

**Expected outcome**: New Riders who have more than 3 eligible candidates now show up
to 5 suggestions each; clusters may merge or grow relative to the default 5 km radius.
Both flags reject non-positive values (`SystemExit` from argparse), matching this
project's existing `--min-width-km`-style validation.

## 3. Hand-edit and export to PDF without recomputing

```bash
# Open reports/rider_pairings.md, make a manual edit (e.g. add a note under one
# New Rider's suggestions), save.
uv run scripts/generate_rider_pairings.py --pdf-only
```

**Expected outcome**: `reports/rider_pairings.pdf` is created/updated and reflects
your hand-edit verbatim — the pairing computation did not run (no new season data was
read, no `.md` overwrite happened). Confirm by diffing `rider_pairings.md`'s mtime/git
status before and after: it's unchanged by this command.

## 4. Confirm regeneration doesn't lose the hand-edit

```bash
uv run scripts/generate_rider_pairings.py
```

**Expected outcome**: `rider_pairings.md` is fully regenerated from current data (your
hand-edit is gone from the working copy — expected, per FR-014's design), but
`git log -p -- reports/rider_pairings.md` in the `RKBY_DATA_DIR` repository still shows
the hand-edited version as a prior commit, recoverable with `git show <commit>:
reports/rider_pairings.md`.

## 5. Compute-and-export in one step

```bash
uv run scripts/generate_rider_pairings.py --pdf
```

**Expected outcome**: both the freshly-recomputed `rider_pairings.md` and a
freshly-rendered `rider_pairings.pdf` (matching the fresh Markdown, not the earlier
hand-edit) exist after this one command.

## Automated coverage

The scenarios above are also covered by `pytest` against
`tests/fixtures/pairing_seasons/` (no real data, no network calls):

```bash
uv run pytest tests/unit/test_rkby_pairing_eligibility.py \
              tests/unit/test_rkby_pairing_ranking.py \
              tests/unit/test_rkby_pairing_clusters.py \
              tests/unit/test_rkby_pairing_report.py \
              tests/unit/test_rkby_pairing_pdf.py \
              tests/unit/test_clustering.py \
              tests/unit/test_generate_rider_pairings_cli.py
```
