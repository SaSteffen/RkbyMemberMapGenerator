# Quickstart: Interactive Photo Map

Validation guide for this feature once implemented. Assumes `uv sync` has already
been run in the repo root, that `specs/001-scraper-persistence`'s scraper has
populated at least one season of local data, and that **Node.js + `pnpm`** are
installed and on `PATH` — `generate_interactive_map.py` builds
`frontend/interactive-map/` itself on every run (research.md §1); there's no
separate "build the frontend first" step to remember.

## Prerequisites

- Node.js and `pnpm` available: `node --version && pnpm --version`.
- A local data directory with at least one (ideally two, for Scenario 3) seasons
  already scraped:

  ```bash
  export RKBY_DATA_DIR="/tmp/rkby-data"   # or wherever your real data lives
  ls "$RKBY_DATA_DIR/seasons"             # should list at least one season, e.g. 2025-26
  ```

  For an isolated dry run instead of touching real data: build a throwaway data dir
  with a couple of synthetic applicant YAML files (shaped like real records — never
  copy real member data, per Constitution I), including at least one `match_key`
  present in two different seasons with different `role` values (to exercise the
  cross-season merge, Story 2/3).

## Scenario 1 — First run: generate the one artifact (Story 1 + Story 2)

```bash
uv run scripts/generate_interactive_map.py
```

**Expect**:

- `$RKBY_DATA_DIR/interactive_map/index.html`, `map-data.js`, `basemap.jpg` (plus
  `basemap@2x.jpg`/`basemap@4x.jpg` when the member set's bounding box has room for
  the extra resolution, research.md §2 addendum), and `photos/` created — one
  artifact, not per season (FR-002, FR-018).
- Every newly-geocoded eligible member's YAML record now has non-null
  `latitude`/`longitude` (same cache `generate_member_maps.py` writes to — a warm
  cache from a prior run of either script speeds this up, research.md §11).
- Any season-record skipped (missing/unresolvable address) is named in that
  season's `logs/<timestamp>.log`, and the run still exits `0`.
- `$RKBY_DATA_DIR/.gitignore` now ignores `interactive_map/` alongside the existing
  `maps/`/`.tile_cache/` entries.

## Scenario 2 — Open the artifact fully offline (Story 4, SC-003)

```bash
# disable networking, e.g. turn off Wi-Fi / unplug ethernet, then:
open "$RKBY_DATA_DIR/interactive_map/index.html"   # or double-click it in a file browser
```

**Expect**: the map loads fully — basemap image, member photos, season controls —
with zero network requests (check the browser's Network tab: nothing pending or
failed). Scroll-zoom, click-drag pan, the on-screen zoom/pan buttons, season
toggles, and hover popups all work exactly as they would online. Try this in at
least two different browsers (e.g. Chrome and Firefox) — Chrome is the one most
likely to expose a `file://` loading mistake (research.md §10).

## Scenario 3 — Default season and manual season selection (Story 1 + Story 2)

```bash
open "$RKBY_DATA_DIR/interactive_map/index.html"
```

**Expect**: on first load, exactly the season considered "current" as of today (per
`default_season_label`'s August-start rule) is active — or, if that season isn't in
the bundled data, the most recent season that *is* present (Edge Cases). Toggle on a
second season control: members from that season appear immediately (no reload); a
person eligible in both active seasons appears as exactly one photo (FR-009,
SC-005). Toggle every season off: the map shows nobody, without erroring (Edge
Cases).

## Scenario 4 — Cross-season hover popup (Story 3)

With two seasons active for the synthetic member who has different roles in each
(Prerequisites):

**Expect**: hovering their photo shows their name and previous-season count once,
plus two separate role entries, one per active season, each showing that season's
own `role`/`additional_roles` (FR-015). Deactivate one of those two seasons: the
popup now shows only one role entry. Move the cursor off the photo: the popup
closes (FR-015).

## Scenario 5 — Identical-address pair stays individually discoverable (FR-021)

Use two synthetic records with byte-identical `address` strings (same pattern as
002's FR-014 test data).

**Expect**: both members' photos are visible and independently hoverable at every
zoom level — neither is permanently hidden behind the other, and zooming in further
never separates them (they share one exact coordinate, unlike a merely-nearby pair,
which *does* separate on zoom per FR-012).

## Scenario 6 — Re-run is idempotent (SC-009)

```bash
# hand-edit one member's role in their yaml, or remove a member entirely
uv run scripts/generate_interactive_map.py
```

**Expect**: `interactive_map/` reflects only the current data — no stale photo file
for a removed member, no stale role text in `map-data.js`.

## Scenario 7 — Mobile mode: auto-detect, drawer, and settings (Story 5)

```bash
open "$RKBY_DATA_DIR/interactive_map/index.html"
```

In the browser, open DevTools' device toolbar (or resize the window narrow) to
simulate a phone-sized, touch-primary viewport, then reload the page.

**Expect**: mobile mode is active by default (FR-023) — no hover popups; season
checkboxes are no longer directly on the map. Tap a member's photo: a drawer opens
from the bottom, at most half the viewport tall, scrollable, showing the same
name/previous-seasons/per-active-season-role fields as the desktop popup (FR-025).
Tap the drawer's close control, or tap elsewhere on the map: it closes (FR-026).
Tap a different member's photo while the drawer is open: its content switches in
place. Open the settings control: season selection is there alongside the mode
switch (FR-027); switch to desktop mode and confirm hover popups + inline season
checkboxes return; switch back. Resize/rotate the viewport without touching
settings: the active mode does not change on its own (Edge Cases).

## Running the automated test suites

```bash
uv run pytest                                              # Python: merge/eligibility/bundling logic
cd frontend/interactive-map && pnpm install && pnpm test && cd -   # Vitest: defaultSeasonLabel,
                                                             #   popupData, declutterPositions, mode
```

**Expect**: all tests pass, entirely offline, none touching real member data or the
live Nominatim/OSM services (Constitution V).
