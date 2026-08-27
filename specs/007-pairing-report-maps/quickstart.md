# Quickstart: Validating Pairing Report Maps

Prerequisites: `uv sync` has installed dependencies (no new ones this feature adds —
research.md, Technical Context), and you have a local `RKBY_DATA_DIR` — either a real
`generate_member_maps.py`-processed data repository, or a synthetic one shaped like
`tests/fixtures/pairing_seasons/` (never real scraped data in this repo, Constitution
Principle V). Network access to `tile.openstreetmap.org` is required for real map
rendering (no mock server in a manual run) — automated tests mock this instead (see
below).

## 1. Confirm no rider is silently dropped from Training Clusters (User Story 1)

```bash
export RKBY_DATA_DIR=/path/to/your/local/data-repo
uv run scripts/generate_rider_pairings.py
```

**Expected outcome**: `$RKBY_DATA_DIR/reports/rider_pairings.md`'s `## Training
Clusters` section now includes every current-season rider who is not excluded, not
opted out, and successfully geocoded — including a rider with no one else nearby, now
shown as their own `### Cluster <n> (1 rider)` instead of being missing from the
section entirely. Two riders near each other with no third nearby now show up as a
`(2 riders)` cluster instead of being dropped. Groups of three or more render exactly
as before.

## 2. Confirm every Training Cluster has a map (User Story 2)

Open `rider_pairings.md` (or the exported PDF, step 4) and check each
`### Cluster <n>` subsection.

**Expected outcome**: each subsection shows a map image
(`$RKBY_DATA_DIR/reports/maps/cluster_<n>.png`, same `<n>` as the heading) plotting
that cluster's own riders plus any other current-season member of any role who falls
within the same map area, for context — matching how `generate_member_maps.py`'s own
detail maps already show nearby members rather than an isolated group.

## 3. Confirm the whole-team overview map (User Story 3)

**Expected outcome**: `rider_pairings.md` opens with a `## Team Overview` section,
ahead of `## New Riders`, containing one map
(`$RKBY_DATA_DIR/reports/maps/overview.png`) showing every eligible current-season
member regardless of role (Rider, Service Crew, Supporter), role-color-coded the same
way `generate_member_maps.py`'s own overview map already is.

## 4. Confirm the maps carry through to the PDF export

```bash
uv run scripts/generate_rider_pairings.py --pdf-only
```

**Expected outcome**: `reports/rider_pairings.pdf` embeds the same Team Overview and
per-cluster map images the Markdown references — open it and visually confirm the
images render (not broken-image icons), matching `contracts/report-output.md`'s PDF
export contract.

## 5. Confirm regeneration replaces stale maps (FR-010)

```bash
# Edit or remove a rider's address in a season .yaml file so the clusters change
# shape, then re-run:
uv run scripts/generate_rider_pairings.py
```

**Expected outcome**: `reports/maps/` contains exactly the files matching the new
run's cluster list — a `cluster_<n>.png` left over from a cluster that no longer
exists (or whose number shifted) is gone, not stale-and-orphaned
(`contracts/map-output.md` § Regeneration semantics).

## 6. Confirm maps never leave `RKBY_DATA_DIR` or get committed (FR-011)

```bash
git -C "$RKBY_DATA_DIR" status --porcelain -- reports/maps/
```

**Expected outcome**: no output — `reports/maps/` is gitignored (inherited from the
blanket `reports/` entry `ensure_reports_dir_and_gitignore` already writes) and this
feature's `auto_commit` call never force-adds it, unlike `rider_pairings.md` itself.

## Automated coverage

The scenarios above are also covered by `pytest` against
`tests/fixtures/pairing_seasons/` and `responses`-mocked OSM tile requests (no real
data, no live network calls):

```bash
uv run pytest tests/unit/test_rkby_pairing_clusters.py \
              tests/unit/test_rkby_pairing_report.py \
              tests/unit/test_rkby_pairing_maps.py \
              tests/unit/test_rkby_maps_pin_map.py \
              tests/unit/test_generate_rider_pairings_cli.py \
              tests/unit/test_generate_member_maps_cli.py
```
