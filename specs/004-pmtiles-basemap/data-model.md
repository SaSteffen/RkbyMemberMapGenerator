# Data Model: PMTiles Basemap for Interactive Map

Entities touched by this feature. Everything not listed here (season records,
applicant YAML, `Merged Member`'s non-position fields) is unchanged from
`specs/003-interactive-photo-map/data-model.md`.

## PMTiles Basemap File

A single local file, supplied manually by the maintainer, containing a Protomaps
vector-tile archive (v3 PMTiles format) for the geographic area and zoom range the
map needs. Replaces the previous per-run, generator-built grid of raster basemap
tile-chunk files as the map's basemap source (spec.md § Key Entities).

| Field | Value |
|---|---|
| Location | `<RKBY_DATA_DIR>/basemap.pmtiles` (research.md §4) — fixed, maintainer-placed, never written by the generator |
| Validation | First 8 bytes must equal ASCII `PMTiles` followed by a spec-version byte the reader supports (`<= 3`); checked before any other generation work (FR-003, research.md §3) |
| Failure modes | Missing file, unreadable file, file shorter than 8 bytes, or a magic/version mismatch — all fail the run before any output is produced, with an error naming `<RKBY_DATA_DIR>/basemap.pmtiles` |
| Consumed by | `generate_interactive_map.py` reads it once, as raw bytes, to base64-embed into the bundle (research.md §2) — never parsed/interpreted Python-side beyond the 8-byte header check |
| Replaces | `bundle.py`'s `generate_basemap` output (`basemap.jpg` + `tiles/<scale>/<x>_<y>.jpg` chunk grid) and its OSM-tile-cache dependency (`<RKBY_DATA_DIR>/.tile_cache/`, for the interactive map only) |

## Merged Member — position fields (changed)

Same entity spec 003 defined (`merge_seasons` output, one per distinct `match_key`
eligible in at least one season). Only the *bundled, output-facing* position
representation changes:

| Field | Before (spec 003) | After (this feature) |
|---|---|---|
| Marker position | `x`/`y`: pixel position precomputed against one fixed synthetic `(center, zoom, CANVAS_SIZE)` (`bundle.py`'s `compute_positions`) | `lat`/`lon`: the member's own already-geocoded `latitude`/`longitude` (`merge.py:109-110`), passed straight through — no projection step (research.md §5) |

`compute_positions`, and the `zoom_for_bounding_box`/`lonlat_to_pixel`/
`canvas_origin` calls it made into `rkby_maps/basemap.py`, are deleted from
`bundle.py` entirely. Those functions themselves stay in `rkby_maps/basemap.py`
unchanged — `generate_member_maps.py` still calls them directly for its own static
maps.

## Bundled Map Data (`window.RKBY_MAP_DATA`, `map-data.js`) — schema changes

Same delivery mechanism as spec 003 (`<script>window.RKBY_MAP_DATA = {...};</script>`
written to `map-data.js`, loaded via `<script src>`, never `fetch()`'d). Shape
changes from `specs/003-interactive-photo-map/contracts/map-data.schema.json`:

- **`members[].x`/`members[].y`** → **`members[].lat`/`members[].lon`** (see table
  above). Every other member field (`match_key`, `name`, `num_previous_seasons`,
  `photo`, `photo_full`, `seasons`) is unchanged — still never includes address,
  phone, email, birthday, or any other Principle-I-excluded field.
- **`image` object removed entirely** (`file`/`width`/`height`/`tileSize`/
  `tileLevels`) — there is no more precomputed pixel canvas or chunk-grid pyramid
  to describe.
- **New `basemap` object added**:

  | Field | Description |
  |---|---|
  | `file` | Filename of the base64-embedding script relative to `interactive_map/`, e.g. `"basemap-pmtiles.js"` (research.md §2) |
  | `variable` | Global variable name that script sets (e.g. `"RKBY_PMTILES_BASE64"`) — frontend reads `window[basemap.variable]` rather than a hardcoded name, so `bundle.py` and `main.js` can't silently drift apart on it |

  `minZoom`/`maxZoom` are deliberately **not** included here — the frontend reads
  them straight from the embedded archive's own header at runtime via
  `pmtiles.PMTiles#getHeader()` (research.md §6), so there's exactly one source of
  truth for the archive's own coverage/zoom range, not two that could disagree.

Full updated shape lives in `contracts/map-data.schema.json` (this feature's
version, replacing spec 003's).

## Generated Interactive Map Artifact — folder layout (changed)

From `specs/003-interactive-photo-map/contracts/output-artifact.md`:

```text
<RKBY_DATA_DIR>/interactive_map/
├── index.html
├── map-data.js
├── basemap-pmtiles.js      # NEW — base64-embedded PMTiles archive (research.md §2)
└── photos/
    ├── placeholder.png
    └── <match_key>.<ext>
```

`basemap.jpg` and `tiles/` are gone — nothing in this feature's generation path
writes them. (research.md §7 flags `tiles/`'s prior wipe-exemption as recommended
for removal at implementation time, since nothing will ever populate it again.)

Full updated contract lives in `contracts/output-artifact.md` (this feature's
version, replacing spec 003's).
