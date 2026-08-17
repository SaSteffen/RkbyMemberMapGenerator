# Quickstart: Member Map Generator

Validation guide for this feature once implemented. Assumes `uv sync` has already been
run in the repo root (see root `CLAUDE.md`), and that
`specs/001-scraper-persistence`'s scraper has already been used at least once to
populate a local data directory — this feature only reads/enriches that data, it never
scrapes anything itself.

## Prerequisites

- A local data directory with at least one season already scraped, e.g.:

  ```bash
  export RKBY_DATA_DIR="/tmp/rkby-data"   # or wherever your real data lives
  ls "$RKBY_DATA_DIR/seasons"             # should list at least one season, e.g. 2025-26
  ```

- For an isolated dry run instead of touching real data: build a throwaway data dir
  with a couple of synthetic applicant YAML files (shaped like real records — never
  copy real member data for this, per Constitution I) under
  `seasons/2025-26/applicants/*.yaml`, each with an `address` field. Include at least
  two records with addresses close enough together to exercise clustering.

## Scenario 1 — First run: geocode, render, cache (Story 1 + Story 2)

```bash
uv run scripts/generate_member_maps.py
```

**Expect**:

- `$RKBY_DATA_DIR/maps/pins/2025_26_overview_pins.png` and
  `$RKBY_DATA_DIR/maps/photos/2025_26_overview_photos.png` created (one pair per
  season present).
- Every geocoded member's YAML record now has non-null `latitude`/`longitude`.
- Any member with no address, an unresolvable address, or (photo variant only) no
  photo is named in that season's `logs/<timestamp>.log`, and the run still exits `0`.
- `$RKBY_DATA_DIR/.gitignore` now exists and ignores `maps/` and `.tile_cache/`.
- If `RKBY_DATA_DIR` is a git repo, the geocode-cache writes + `.gitignore` are
  auto-committed (`git -C "$RKBY_DATA_DIR" log --oneline -1`); `maps/` and
  `.tile_cache/` themselves are untracked (`git -C "$RKBY_DATA_DIR" status
  --porcelain` shows nothing for them).

## Scenario 2 — Re-run never re-geocodes (SC-007)

```bash
uv run scripts/generate_member_maps.py 2>&1 | grep -i geocod
```

**Expect**: no new geocode lookups logged for any member whose record already has
`latitude`/`longitude` from Scenario 1 — only members still missing coordinates (if
any) are looked up.

## Scenario 3 — A crowded area produces a detail map (Story 3)

Use a synthetic data dir with 3+ members whose addresses are close enough together
that their overview-scale markers would overlap (e.g. same small town).

```bash
uv run scripts/generate_member_maps.py
ls "$RKBY_DATA_DIR"/maps/pins/2025_26_detail_* "$RKBY_DATA_DIR"/maps/photos/2025_26_detail_*
```

**Expect**: a `2025_26_detail_pins_<slug>.png` and/or
`2025_26_detail_photos_<slug>.png` file exists, zoomed in enough that those members'
markers no longer overlap on it (unless the group is still too tight even at
`--min-width-km`'s floor — then check that map for the FR-013 fallback rendering
instead, per `contracts/map-output.md` § Visual contract).

## Scenario 4 — Exact same-address pair never gets its own detail map (FR-014)

Use two synthetic records with byte-identical `address` strings.

```bash
uv run scripts/generate_member_maps.py
ls "$RKBY_DATA_DIR"/maps/pins/2025_26_detail_* "$RKBY_DATA_DIR"/maps/photos/2025_26_detail_* 2>/dev/null
```

**Expect**: no detail map is generated for that pair specifically (other, unrelated
clusters in the same run may still produce their own detail maps) — the pair appears
on whichever overview/detail map it naturally falls on, rendered via the FR-013
fallback (merged pin+badge, or offset photo circles).

## Scenario 5 — `--min-width-km` and `--no-scale-bar`

```bash
uv run scripts/generate_member_maps.py --min-width-km 100 --no-scale-bar
```

**Expect**: every generated map (overview and any detail maps) covers at least 100km
of real-world width, and none of them show a scale-bar ruler — attribution text
(`contracts/map-output.md` § Visual contract) is still present regardless.

## Scenario 6 — Idempotent regeneration (SC-006)

```bash
# hand-edit one member's address in their yaml, clearing latitude/longitude so it
# will be re-geocoded, or just add a brand-new synthetic member
uv run scripts/generate_member_maps.py
```

**Expect**: `maps/` for that season reflects only the current data — no stale marker
left from before the edit, and no leftover detail-map file for a cluster that no
longer exists.

## Running the automated test suite

```bash
uv run pytest
```

**Expect**: all unit tests pass — Web Mercator projection math, overlap/clustering
graph logic, geocoding (mocked via `responses`), tile fetch/stitch (mocked tile
bytes), photo circular crop, and CLI argument parsing, all offline, none touching real
member data or the live Nominatim/OSM services (Constitution V).
