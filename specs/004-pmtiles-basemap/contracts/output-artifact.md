# Contract: Generated Interactive Map Artifact

What a team organizer (or a recipient of the shared folder) can rely on when
reading/opening `<RKBY_DATA_DIR>/interactive_map/`. Supersedes
`specs/003-interactive-photo-map/contracts/output-artifact.md` for the fields
listed below; the rest of that document (opening via double-click, season
controls, hover popup fields, pan/zoom controls, mobile mode, skipped-member
logging) is unchanged by this feature.

## Folder layout (changed)

```text
<RKBY_DATA_DIR>/interactive_map/
├── index.html
├── map-data.js
├── basemap-pmtiles.js      # NEW: base64-embedded PMTiles archive (data-model.md)
└── photos/
    ├── placeholder.png
    └── <match_key>.<ext>
```

`basemap.jpg` and `tiles/` (spec 003's flattened base image + chunked
higher-resolution raster pyramid) no longer exist — nothing in this feature's
generation path produces them. Every run still fully deletes and regenerates this
whole folder (data-model.md § Idempotency, spec 003).

## Opening the artifact — unchanged, but now load-bearing rather than incidental

Double-click (or otherwise open) `index.html` directly — no local server, no
network connection required. This was already true in spec 003; this feature's
entire technical design (research.md §2) exists specifically to keep it true once
the basemap is a real PMTiles archive rather than a baked static image — verified
directly against Chromium's actual `file://` fetch/XHR restrictions, not assumed.

## Visual & interaction contract (changed: Basemap, Markers)

- **Basemap**: rendered live from the embedded PMTiles archive via
  `protomaps-leaflet`, using Leaflet's real geographic CRS (`L.CRS.EPSG3857`) —
  real vector-tile basemap imagery, not a pre-baked raster image or chunk pyramid
  (research.md §1, §5). Panning/zooming covers the archive's own bounds and zoom
  range (FR-005); past the archive's deepest baked zoom, Leaflet reuses and
  auto-scales that deepest level rather than showing a blank area (Edge Cases,
  research.md §6).
- **Markers**: each member's photo marker is positioned at their real
  `latitude`/`longitude` (data-model.md § Merged Member), not a precomputed pixel
  position on a synthetic canvas. Visually and interactively identical otherwise —
  same circular photo marker, same declutter behavior at high member density
  (FR-012, FR-021), same hover/tap popup contract (spec 003, unchanged).
- **Attribution**: unchanged requirement (FR-022) — always-visible attribution
  text via Leaflet's built-in control; wording sourced from the embedded archive's
  own attribution metadata where available, otherwise the Protomaps/OpenStreetMap
  attribution the sample archive's own metadata carries (`pmtiles show`:
  `attribution: <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap
  contributors</a>`).

Everything else in spec 003's Visual & interaction contract (season controls,
hover popup fields, pan/zoom buttons, mobile mode, overlap/declutter rules,
skipped-member logging) applies unchanged.

## Data contract

See `map-data.schema.json` (this feature's version) for the exact shape of
`window.RKBY_MAP_DATA`.
