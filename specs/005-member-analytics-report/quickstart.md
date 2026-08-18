# Quickstart: Member Analytics Report

Validation guide for this feature once implemented. Assumes `uv sync` has already been
run in the repo root, and that at least one season has already been scraped
(`specs/001-scraper-persistence`) — coordinates from a `generate_member_maps.py` run
(`specs/002-map-generator`) are optional (distance views just show "unknown/not
geocoded" without them, FR-006).

## Prerequisites

- A local data directory with at least one season already scraped:

  ```bash
  export RKBY_DATA_DIR="/tmp/rkby-data"   # or wherever your real data lives
  ls "$RKBY_DATA_DIR/seasons"             # should list at least one season, e.g. 2025_26
  ```

- For an isolated dry run instead of touching real data: build a throwaway data dir
  with two or more synthetic season folders under `seasons/<label>/applicants/*.yaml`
  (shaped like real records — never copy real member data, per Constitution I),
  with varying `role`/`sex`/`birthday`/`latitude`/`longitude` values, and at least one
  `match_key` that appears in two consecutive seasons (to exercise retention) and one
  that only appears in the earlier one (to exercise the "departed" case).

## Scenario 1 — Single-season snapshot (Story 1)

```bash
uv run --with jupyter jupyter lab scripts/report_member_analytics.ipynb
# inside Jupyter: Run All
```

**Expect**: for a chosen season, the notebook shows role counts (rider/service crew/
supporter/any other role present), a gender distribution, an age-bucket distribution,
and a distance-from-Hamburg-bucket distribution — with members missing a birthday,
`sex`, or coordinates showing up under an explicit "unknown" category in the relevant
chart rather than disappearing from the count.

## Scenario 2 — Season-to-season trends (Story 2)

With three or more synthetic seasons on file, re-run **Run All**.

**Expect**: total-member-count, rider-count, and service-count each plotted as a
single trend across all seasons in chronological order, plus charts showing how the
age/gender/distance distributions shift from one season to the next. With only one
season on disk, these views say plainly that there isn't enough data yet, rather than
plotting a misleading single point or erroring.

## Scenario 3 — Retention, overall and split (Story 3)

Using the two-consecutive-seasons fixture from Prerequisites, with a known returning
member and a known departing member:

**Expect**: the overall retention rate between those two seasons matches
`retained / (retained + departed)` for the known fixture, and the same rate is shown
again split by gender, by age bracket, and by distance-from-Hamburg bracket. A member
whose `match_key` changed between seasons via a recorded `alias_match_keys` counts as
retained; a member who skipped a season and returned two seasons later does **not**
count as retained across the skipped gap (spec Edge Cases).

## Scenario 4 — Export (Story 4)

```bash
uv run jupyter nbconvert --to html --execute \
  scripts/report_member_analytics.ipynb \
  --output-dir "$RKBY_DATA_DIR/reports"
ls "$RKBY_DATA_DIR"/reports/*.html
```

**Expect**: one `.html` file is produced under `$RKBY_DATA_DIR/reports/`, openable in
a browser with every chart and table visible and no re-run needed, and containing no
per-member list of names — aggregated numbers only (FR-015). Confirm it was **not**
written anywhere inside the git repository:

```bash
git status --porcelain   # should show nothing new under scripts/ or elsewhere in the repo
```

## Scenario 5 — Committed notebook never carries real output

```bash
# after running Scenario 1-3 locally (notebook now has real cell outputs in memory)
git add scripts/report_member_analytics.ipynb
git diff --cached scripts/report_member_analytics.ipynb | grep -i "output" | head
```

**Expect**: the `nbstripout` pre-commit hook strips every cell's output before the
commit is created — the staged/committed version of the notebook has no embedded
chart images or printed tables, only cell source code.

## Running the automated test suite

```bash
uv run pytest
```

**Expect**: all unit tests pass — eligibility filtering, age-at-season, distance,
cross-season identity/retention resolution, and season/trend/retention aggregation
(`tests/unit/test_rkby_report_*.py`), plus the promoted `canonical_match_keys()`
coverage (`test_rkby_records_canonical_match_keys.py`) — all offline, against
synthetic fixtures in `tests/fixtures/report_seasons/`, none touching real member
data (Constitution V).
