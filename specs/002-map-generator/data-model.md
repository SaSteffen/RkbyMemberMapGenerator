# Phase 1 Data Model: Member Map Generator

Entities as introduced in spec.md § Key Entities, expanded into concrete fields and
write rules. Builds on top of the persisted shape from
`specs/001-scraper-persistence/data-model.md` — only the delta is repeated here in
full; everything else about the Applicant Record is unchanged.

## Applicant Record (extended)

Same file, same location as before —
`<RKBY_DATA_DIR>/seasons/<season-label>/applicants/<match_key>.yaml` — with two new
optional fields appended to `_RECORD_FIELD_ORDER` (after `photo`):

| Field | Type | Required | Write rule |
|---|---|---|---|
| `latitude` | number \| null | no | Set once, by this feature, the first time `address` is successfully geocoded (research.md §3, §11). Fill-empty-only: never rewritten once non-null, whether by a later run's re-geocode or a human hand-edit — matches every other optional field's freeze-once-set discipline (Principle III). `null`/absent until first successful geocode. |
| `longitude` | number \| null | no | Same rule as `latitude`; always written together as a pair, never one without the other. |

Both fields are `additionalProperties: false`-safe additions to
`scripts/schemas/applicant_record.schema.json` (research.md §3; see
`contracts/applicant-record.schema.json` for the full post-extension schema). Existing
records written before this feature simply lack the keys — `rkby_records`'s `.get()`
-based read/write pattern (already used for `role` per the precedent commit) handles
that without a migration step.

**Eligibility derived from existing fields** (no new fields needed): a member is
eligible for the pin-map variant when `excluded == false`, `ignore == false`, and
`address` is non-null and successfully geocoded (`latitude`/`longitude` both non-null
after this run's geocoding pass). Eligible for the photo-map variant when additionally
`photo` is non-null and the referenced file exists on disk.

## Season (reused, extended read-only usage)

Unchanged shape from 001's data-model.md. This feature adds one new read: instead of
being told a single season label via `--season`, it discovers every season by listing
`<RKBY_DATA_DIR>/seasons/*/` that contains an `applicants/` subfolder
(`discover_seasons`, research.md §10) and processes all of them in one run (FR-002).

## Member Location (ephemeral — not separately persisted)

Not its own file; it's the runtime pairing of an eligible Applicant Record with its
`(latitude, longitude)` and, per rendered map, its projected canvas pixel position
(research.md §1, §4). Exists only for the duration of one map's render.

| Field | Type | Notes |
|---|---|---|
| `match_key` | string | Foreign key back to the Applicant Record. |
| `role_color` | one of the 4 hex values (research.md §7) | Derived from `role`, case-insensitive match against the three known roles, else the "unrecognized" color. |
| `latitude`, `longitude` | number | Copied from the Applicant Record. |
| `pixel_x`, `pixel_y` | number | Computed per-map from the map's center/zoom (research.md §1); not persisted, recomputed for every map. |

## Map (generated artifact)

A single PNG under `<RKBY_DATA_DIR>/maps/`. Not a data record with its own file format
beyond the image bytes; its identity is entirely encoded in its filename (see
`contracts/map-output.md` for the full naming grammar). One row per PNG this feature
produces in a run:

| Field | Type | Notes |
|---|---|---|
| `season_label` | string | `YYYY_YY` underscore form, e.g. `2025_26` (FR-016). |
| `variant` | `"pins"` \| `"photos"` | Which of the two rendering modes (US1/US2). |
| `kind` | `"overview"` \| `"detail"` | One overview per season per variant (FR-003/FR-004); zero or more detail maps per season per variant (FR-012). |
| `slug` | string \| absent | Only present for `kind == "detail"` (research.md §9); absent/omitted from the filename for overviews. |
| `center`, `covered_width_km`, `zoom` | computed | Not part of the filename; internal render parameters derived per research.md §5. |

## Overlap Group / Cluster (ephemeral — not persisted)

Computed independently for each `(season, variant, map)` combination (research.md §4).
Not written to disk in any form; exists only during rendering to decide (a) whether a
detail map is generated for that group (FR-012), and (b) whether the FR-013 fallback
rendering applies on whichever map(s) that group appears on.

| Field | Type | Notes |
|---|---|---|
| `members` | list of Member Location | Size ≥ 2 by definition (connected component). |
| `same_address_pair` | bool | True iff exactly 2 members, identical `address` string (FR-014) — short-circuits detail-map generation for this group entirely; it's rendered via the FR-013 fallback wherever it naturally appears, with no detail map ever attempted for it. |
| `resolved_at_detail_width` | bool | Set after rendering the group's detail map (when one is generated): whether the overlap was fully resolved at `max(min_width_km, required_width_km)` (research.md §5). False triggers the FR-013 fallback on that detail map instead of further recursion. |

## Tile Cache Entry

Not schema-validated — a binary file. `<RKBY_DATA_DIR>/.tile_cache/<z>/<x>/<y>.png`, one
file per OSM tile ever fetched by any run of this tool (research.md §2). No expiry;
never read by any other script; safe to delete entirely at any time to force fresh
tiles on the next run.

## Local Data Repository (layout addition)

Extends 001's layout with two new top-level siblings of `seasons/`:

```
<RKBY_DATA_DIR>/
├── .gitignore                 # NEW — created/updated by this feature (research.md §12);
│                               #  adds "maps/" and ".tile_cache/" entries
├── .tile_cache/                # NEW — OSM raster tile cache, gitignored, no expiry
│   └── <z>/<x>/<y>.png
├── maps/                       # NEW — flat, all seasons' generated PNGs together (FR-015), gitignored
│   ├── 2025_26_overview_pins.png
│   ├── 2025_26_overview_photos.png
│   ├── 2025_26_detail_pins_verden.png
│   ├── 2025_26_detail_photos_verden.png
│   └── ...
└── seasons/                    # unchanged from 001, except applicants/*.yaml now may
    └── <season-label>/         #   also carry latitude/longitude
        ├── applicants/
        ├── photos/
        └── logs/
```

**Idempotency**: every run fully regenerates and overwrites `maps/`'s contents for
every season it processes (spec Assumptions: "Idempotent output") — a stale detail map
from a since-resolved cluster is deleted, not just left alongside a fresh set. Concrete
rule: at the start of a run, for each season being processed, remove every existing
`maps/<season_label>_*.png` file before writing that season's fresh set, so a run that
now produces fewer detail maps than a previous run doesn't leave orphaned files behind.
