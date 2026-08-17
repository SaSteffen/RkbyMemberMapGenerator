# Contract: Generated Interactive Map Artifact

What a team organizer (or a recipient of the shared folder) can rely on when
reading/opening `<RKBY_DATA_DIR>/interactive_map/`.

## Folder layout

One flat artifact, not split or prefixed by season (FR-018 — a single combined
artifact, unlike `maps/`'s per-season-prefixed files):

```
<RKBY_DATA_DIR>/interactive_map/
├── index.html
├── map-data.js
├── basemap.jpg
└── photos/
    ├── placeholder.png
    └── <match_key>.<ext>      # one per merged member with a photo on file
```

Every run fully deletes and regenerates this whole folder — no file from a previous
run (a since-removed member's photo, a stale `map-data.js`) is ever left behind
(data-model.md § Local Data Repository, "Idempotency").

## Opening the artifact (Story 4, SC-003)

Double-click (or otherwise open) `index.html` directly in a standard current
desktop browser (Chrome, Firefox, Edge, Safari) — no local server, no build step, no
install step, network connection off or on, makes no difference. See research.md
§10 for exactly why this works (single-file non-module JS/CSS bundle, relative
asset paths, data injected via a classic `<script src="map-data.js">` rather than
`fetch()`).

## Visual & interaction contract

- **Basemap**: one static raster image (`basemap.jpg`) covering the bounding box of
  every shown member, displayed via Leaflet `CRS.Simple` + `ImageOverlay` — real OSM
  imagery, not a live/offline OSM tile layer (research.md §2).
- **Markers**: one circular member photo per merged person (data-model.md § Merged
  Member), CSS-cropped from the source photo (or `photos/placeholder.png` when none
  is on file), positioned at the precomputed `x`/`y` from `map-data.js` (research.md
  §3, §9).
- **Season controls**: one checkbox/toggle per entry in `map-data.js`'s `seasons`
  list — including a season with zero eligible members, still present and inert
  (Edge Cases). On load, exactly the FR-007 default (or its present-data fallback)
  season is active; any combination can be active at once (FR-006); toggling
  updates visible markers immediately, no reload (FR-008).
- **Hover popup**: appears on mouseover of a marker, closes on mouseout (FR-015).
  Shows the member's name and `num_previous_seasons` (or an explicit "unknown" label
  when `null` — FR-016) once, plus one role entry (`role` + `additional_roles`) for
  every currently-active season that member has an entry for in `map-data.js`
  (research.md §6).
- **Pan/zoom**: mouse scroll zooms centered on the cursor; click-and-drag pans
  (FR-013). On-screen zoom-in/zoom-out buttons (Leaflet's built-in `zoomControl`)
  and four directional pan buttons (a small custom control, research.md §8) each
  reproduce the corresponding gesture's effect (FR-014).
- **Overlapping/identical-coordinate members**: two members at genuinely distinct
  addresses separate visually as the viewer zooms in (FR-012) — no forced
  declustering. Two members at the *exact same* coordinates never separate by
  zooming (identical position, by definition) but are each still independently
  discoverable and hoverable via a small fixed offset applied only in that exact
  case (FR-021, research.md §7).
- **Attribution**: `"© OpenStreetMap contributors"`, always visible via Leaflet's
  built-in bottom-right attribution control, never hidden behind a toggle
  (research.md §8, FR-022).

## Skipped members

Never silently dropped — every season-record excluded from the bundle for a missing
or unresolvable address is named in that run's log output (FR-005, SC-007), not just
absent from the map. Log location: reuses the existing per-season
`seasons/<season-label>/logs/<run-timestamp>.log` convention, one log file per
season this run touches (same as `generate_member_maps.py`).

## Data contract

See `map-data.schema.json` for the exact shape of `window.RKBY_MAP_DATA` as written
into `map-data.js`.
