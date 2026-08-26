# Quickstart: PMTiles Basemap for Interactive Map

Validation guide for this feature once implemented. Assumes the same prerequisites
as `specs/003-interactive-photo-map/quickstart.md` (`uv sync` run, Node.js + `pnpm`
on `PATH`, at least one season scraped into `RKBY_DATA_DIR`), **plus** a PMTiles
archive placed at `<RKBY_DATA_DIR>/basemap.pmtiles` (data-model.md § PMTiles
Basemap File) — for local dev, the sample archive already provided
(`trhharea11poi-stripped.pmtiles`, confirmed via `pmtiles show`: vector MVT,
Protomaps schema, zoom 0-11) works; copy or symlink it to that exact path.

Everything spec 003's quickstart already validates (season toggles, hover popups,
mobile mode/drawer, cross-season merge, idempotent re-run of member/photo data)
still applies unchanged — this guide only covers what's new or different because
the basemap is now a PMTiles archive instead of a baked raster pyramid.

## Prerequisites

```bash
export RKBY_DATA_DIR="/tmp/rkby-data"           # or wherever your real data lives
ls "$RKBY_DATA_DIR/seasons"                     # at least one season present
cp /path/to/trhharea11poi-stripped.pmtiles "$RKBY_DATA_DIR/basemap.pmtiles"
```

## Scenario 1 — First run: basemap comes from the PMTiles file, not OSM (Story 1, FR-001/FR-002, SC-001)

```bash
uv run scripts/generate_interactive_map.py
```

**Expect**:

- `$RKBY_DATA_DIR/interactive_map/index.html`, `map-data.js`, and
  `basemap-pmtiles.js` are created (data-model.md § Generated Interactive Map
  Artifact) — **no** `basemap.jpg` and **no** `tiles/` folder.
- The run makes zero requests to `tile.openstreetmap.org` — check the terminal
  output / a network sniffer if in doubt; `contracts/cli-and-env.md`'s Third-Party
  Network Calls table no longer lists that endpoint at all.
- `$RKBY_DATA_DIR/.tile_cache/` is not created or touched by this run (it's a
  spec-002-only concern now).
- Re-running with the exact same `basemap.pmtiles` and member set produces a
  byte-identical `basemap-pmtiles.js` (SC-002's "consistent across runs").

## Scenario 2 — Missing or invalid basemap file fails clearly (Story 2, FR-003, SC-003)

```bash
rm "$RKBY_DATA_DIR/basemap.pmtiles"
uv run scripts/generate_interactive_map.py; echo "exit: $?"
```

**Expect**: fails immediately (before the `pnpm` frontend build starts, before
`interactive_map/` is touched) with a message naming
`<RKBY_DATA_DIR>/basemap.pmtiles`. Non-zero exit code. No partial
`interactive_map/` output left behind.

```bash
echo "not a pmtiles file" > "$RKBY_DATA_DIR/basemap.pmtiles"
uv run scripts/generate_interactive_map.py; echo "exit: $?"
```

**Expect**: same fast, clear failure — the header check (data-model.md §
Validation) rejects it before any output is produced. Restore the real archive
before continuing to the next scenario.

## Scenario 3 — Fully offline viewing, real geographic pan/zoom (Story 3, FR-004/FR-005, SC-004)

```bash
cp "$RKBY_DATA_DIR/basemap.pmtiles" "$RKBY_DATA_DIR/basemap.pmtiles"  # restore if needed
uv run scripts/generate_interactive_map.py
# disable networking (Wi-Fi off / unplug), then:
open "$RKBY_DATA_DIR/interactive_map/index.html"   # or double-click it
```

**Expect**: the basemap, member photo markers, season controls, and popups all
load and work with zero network requests (check the browser's Network tab —
nothing pending or failed, matching spec 003's Scenario 2 but now also proving the
PMTiles archive itself loads without a request, research.md §2). Pan and
scroll/button-zoom across the archive's whole coverage area; zoom in past the
archive's deepest baked level (past OSM zoom 11 for the sample archive) and
confirm the map stays visibly usable — the deepest available detail scales up
rather than the basemap going blank (Edge Cases, research.md §6). Test in at least
Chrome (the browser `file://` restrictions are strictest in, research.md §2) and
one other browser.

## Scenario 4 — Swapping the PMTiles file needs no manual cleanup (Edge Cases)

```bash
cp /path/to/a-different-area.pmtiles "$RKBY_DATA_DIR/basemap.pmtiles"
uv run scripts/generate_interactive_map.py
open "$RKBY_DATA_DIR/interactive_map/index.html"
```

**Expect**: the regenerated bundle reflects the new archive's coverage and zoom
range with no leftover artifact from the previous archive (no stale `tiles/`
folder, no mixed old/new basemap content) — the whole `interactive_map/` folder is
fully regenerated every run (data-model.md, unchanged from spec 003).

## Scenario 5 — Existing interactions still work (Story 3, FR-006)

Run through `specs/003-interactive-photo-map/quickstart.md`'s Scenarios 3, 4, 5, 6,
7 unchanged (season toggles, cross-season popup, identical-address pair, idempotent
member re-run, mobile mode) against the bundle generated in Scenario 1/3 above —
all should behave exactly as documented there. The only difference under the hood
is that marker positions now come from each member's real `lat`/`lon`
(data-model.md) instead of a precomputed pixel canvas; this should be invisible
from the viewer's side.

## Running the automated test suites

```bash
uv run pytest                                                      # Python: header validation,
                                                                     #   base64 embedding, no more
                                                                     #   OSM-tile-pyramid tests
cd frontend/interactive-map && pnpm install && pnpm test && cd -    # Vitest: declutter against
                                                                     #   real screen-projected points,
                                                                     #   popupData, defaultSeason
```

**Expect**: all tests pass, entirely offline, none touching real member data, the
live Nominatim service, or (now) any OSM tile server (Constitution V — this
feature actually shrinks what the interactive map's own test suite needs to fake,
since there's no tile-fetch/tile-cache behavior left to stub for it).
