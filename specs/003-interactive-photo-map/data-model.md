# Phase 1 Data Model: Interactive Photo Map

Entities as introduced in spec.md § Key Entities, expanded into concrete fields and
write rules. Reads (never writes new fields to) the same Applicant Record shape
`specs/002-map-generator/data-model.md` already established — no schema change in
this feature. Adds one new generated-artifact shape (`map-data.js`'s payload) that
is exported, never persisted as a source of truth (see § Local Data Repository).

## Applicant Record (read-only for this feature, one write path reused unchanged)

Same file, same location, same schema as today —
`<RKBY_DATA_DIR>/seasons/<season-label>/applicants/<match_key>.yaml`. This feature
reads every field needed for eligibility/merge/popup and writes exactly one thing
back, using the exact same code path `generate_member_maps.py` already uses:
`latitude`/`longitude`, fill-empty-only, via
`scripts.rkby_maps.geocoding.geocode_record_if_needed` (research.md §4, §11 of
002's data-model.md). No new fields are added to
`scripts/schemas/applicant_record.schema.json` by this feature.

**Eligibility** (per season-record, FR-004 — identical rule to 002): `excluded ==
false`, `ignore == false`, `address` non-null, and successfully geocoded
(`latitude`/`longitude` both non-null after this run's geocode pass).

**Addendum**: `alias_match_keys` (array\<string\> | null, manual-only like `ignore`)
was added to the shared schema after this feature originally shipped, specifically
for this feature's cross-season merge — see `specs/001-scraper-persistence/data-model.md`
for the field definition and `_canonical_match_keys` in merge.py below for how it's
resolved.

## Merged Member (generation-time, ephemeral — not persisted as its own file)

Computed once per run by `scripts/rkby_interactive_map/merge.py` (research.md §4):
one entry per distinct `match_key` that has at least one eligible season-record in
*any* season. Exists only in memory during generation; its final, minimized form is
what gets serialized into `map-data.js` (see below) — this row describes the full
intermediate shape before minimization drops fields Principle I doesn't allow into
the shared artifact.

| Field | Type | Source | Notes |
|---|---|---|---|
| `match_key` | string | latest eligible record | Immutable identity key (shared with the Applicant Record). |
| `first_name`, `last_name` | string | latest eligible record | FR-010: from the person's own most-recent eligible season-record, across all their seasons (not only active ones). |
| `num_previous_seasons` | integer \| null | latest eligible record | Single-valued per spec's Popup field mapping; `null` when not on file (FR-016). |
| `photo_relative_path` | string \| null | latest eligible record | Path to the source photo file (relative to that season's folder) if one is on file, else `null` (→ placeholder, research.md §9). |
| `latitude`, `longitude` | number | latest eligible record | FR-010 position source. |
| `seasons` | `{season_label: {role, additional_roles}}` | **every** eligible season-record for this person | Not limited to the latest — Edge Cases: "older active seasons still each contribute their own role entry." `additional_roles` is `[]` when known-empty, matching the existing schema's null-vs-empty-array distinction upstream. |

**"Latest" tie-break**: season labels sort correctly as plain strings
(`"2024-25" < "2025-26"`); the greatest label among a person's own eligible
season-records wins (research.md §4). Ineligible season-records for that same
person are skipped when picking "latest" (never contribute position/name/photo),
matching spec's Assumptions ("skips over any of that person's own season-records
that are ineligible").

**Cross-season key aliasing**: before grouping eligible season-records by
`match_key`, merge.py resolves each record's `alias_match_keys` into an
old-key → canonical-key mapping (followed transitively, so a chain of
renames across more than two seasons still collapses onto one final key) and
regroups every season-record — including the record that itself declares the
alias — under that canonical key. This is how a person whose `match_key`
changed between seasons (e.g. the intranet recomputed it after a spelling or
married-name correction) still produces one Merged Member instead of two.

## Bundled Map Data (`map-data.js` payload — the artifact's one exported dataset)

Written fresh every run as `window.RKBY_MAP_DATA = {...}` (research.md §10). This
*is* the minimized, browser-facing projection of Merged Member — see research.md §12
for exactly which fields are deliberately excluded and why.

```json
{
  "seasons": ["2023-24", "2024-25", "2025-26"],
  "members": [
    {
      "match_key": "jane-doe",
      "name": "Jane Doe",
      "num_previous_seasons": 3,
      "photo": "photos/jane-doe.jpg",
      "x": 1830.4,
      "y": 942.1,
      "seasons": {
        "2024-25": { "role": "Rider", "additional_roles": ["Steering Committee"] },
        "2025-26": { "role": "Service Crew", "additional_roles": [] }
      }
    }
  ],
  "image": {
    "file": "basemap.jpg",
    "width": 4800,
    "height": 3600,
    "tileSize": 256,
    "tileLevels": [
      { "scale": 2, "cols": 38, "rows": 29 },
      { "scale": 4, "cols": 75, "rows": 57 }
    ]
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `seasons` | list of string | **Every** season `discover_seasons` finds, sorted — including a season with zero eligible members (Edge Cases: still a selectable, empty control). Drives the season-toggle UI and the FR-007 default/fallback computation (research.md §5). |
| `members[].x`, `.y` | number | Precomputed pixel position (research.md §3) in the single fixed `(center, zoom, canvas_size)` the base (1x) basemap level was rendered at — every level in `image.tileLevels` covers the identical geographic area at a higher pixel density, so the frontend never re-projects for any of them. |
| `members[].photo` | string | Always set — `"photos/placeholder.png"` when the person has no photo on file (research.md §9); never `null`, unlike the intermediate Merged Member shape, so the frontend has no null-check branch here. Real photos are a server-side-downscaled square JPEG thumbnail, not the original source file (perf fix: the browser only ever renders it at a fixed marker size). |
| `members[].seasons` | object | Same shape as Merged Member's `seasons` field, carried through unminimized — the frontend's `popupData()` (research.md §6) filters this live by the active season set; it is *not* pre-filtered at generation time. |
| `image` | object | Metadata the frontend needs to render the basemap (research.md §3, §2 addenda). `file`/`width`/`height` describe the always-present base (1x) image, shown via a plain `L.imageOverlay` at every zoom. `tileLevels` lists every baked higher-resolution level as a `cols` x `rows` grid of `tileSize`-square chunk files (`interactive_map/tiles/<scale>/<x>_<y>.jpg`); `src/basemapTiles.js` + `src/main.js`'s custom Leaflet `GridLayer` request only the chunks intersecting the current viewport, so no single request or in-memory image ever covers the whole map at high resolution. |

**Not a source of truth**: this file is a pure export. Re-running the generator
always rebuilds it from the season YAMLs from scratch; nothing ever reads it back
into the local data store (mirrors 002's `maps/` folder being disposable/idempotent
output, data-model.md §"Idempotency" there).

## Basemap Image (generated artifact)

One raster file, `interactive_map/basemap.jpg`, covering the bounding box of every
Merged Member's `(latitude, longitude)` across the whole run (research.md §2) — not
per-season, since the same single image and pixel space is shared by every season's
markers. Produced via the same `zoom_for_bounding_box` + `stitch_basemap` pipeline
`generate_member_maps.py` already uses, at a canvas size and `min_width_km` floor
sized for this feature's wider, all-seasons-combined extent (implementation
constants, tuned in code — same pattern as 002's `DETAIL_MAP_PADDING_KM` etc.). No
attribution is baked into the pixels (research.md §8 — attribution is a Leaflet
control instead).

## Season (reused, read-only)

Unchanged from 001/002 — `discover_seasons(data_dir)` lists every
`seasons/<label>/applicants/`-containing folder. This feature processes every
season found, with no `--season` filter (FR-002), same discovery call
`generate_member_maps.py` already uses.

## Local Data Repository (layout addition)

Extends the existing layout with one new top-level sibling of `seasons/` and
`maps/`:

```
<RKBY_DATA_DIR>/
├── .gitignore                 # updated by this feature: adds "interactive_map/"
├── .tile_cache/                # shared with 002 — reused, not duplicated
├── maps/                       # unchanged, owned by 002
├── interactive_map/            # NEW — this feature's one artifact (FR-018)
│   ├── index.html               # copied verbatim from frontend/interactive-map/dist/
│   ├── map-data.js              # generated fresh every run
│   ├── basemap.jpg              # generated fresh every run
│   └── photos/
│       ├── placeholder.png
│       └── <match_key>.<ext>
└── seasons/                    # unchanged; latitude/longitude fill-empty-only shared with 002
```

**Idempotency**: every run fully regenerates and overwrites `interactive_map/`'s
contents — no stale `photos/<match_key>.<ext>` left behind for someone no longer
eligible in any season, no stale `map-data.js`. Concrete rule: delete
`interactive_map/` (if present) at the start of a run, before writing anything new
into it — simpler than 002's glob-based partial deletion since this feature has
exactly one artifact, not per-season files to selectively prune.

## Frontend Build (generated per-run, not source-controlled)

`frontend/interactive-map/dist/index.html` — produced fresh, every run, by
`scripts/generate_interactive_map.py` itself shelling out to `pnpm install
--frozen-lockfile` then `pnpm run build` inside `frontend/interactive-map/` (Vite +
`vite-plugin-singlefile`, research.md §1, §10) before doing anything else. `dist/`
is gitignored — nothing built ever lands in this repo's git history; only
`frontend/interactive-map/src/`, `package.json`, and `pnpm-lock.yaml` are
source-controlled. The script errors clearly (non-zero exit, before any
`RKBY_DATA_DIR` write) if `pnpm` isn't on `PATH` or either subprocess fails.

## View Mode (client-side, ephemeral — not part of the generated data)

Not written into `map-data.js` at all — purely a runtime UI state living in the
browser tab for as long as the page stays loaded (research.md §13). `"desktop"` or
`"mobile"`, chosen once at load by `shouldDefaultToMobile(viewportWidth,
isCoarsePointer)`, thereafter changed only by the settings control. Determines
*how* the same `popupData()` result (§ Bundled Map Data, unchanged either way) is
displayed — a Leaflet hover popup in desktop mode, a bottom drawer in mobile mode —
never what data is available.
