# Contract: Generated Map Output

What a team organizer (or a future script) can rely on when reading
`<RKBY_DATA_DIR>/maps/`.

## Folder layout

Flat, non-nested — every season's every map lives directly inside `maps/` (FR-015), no
per-season subfolders:

```
<RKBY_DATA_DIR>/maps/
├── 2025_26_overview_pins.png
├── 2025_26_overview_photos.png
├── 2025_26_detail_pins_verden.png
├── 2025_26_detail_photos_verden.png
└── ...
```

Every run fully regenerates and overwrites this folder's contents for every season it
processes — stale files from a since-changed cluster set are deleted, not left behind
(data-model.md § Local Data Repository, "Idempotency").

## Filename grammar

```
<season>_<kind>_<variant>[_<slug>].png
```

| Segment | Values | Notes |
|---|---|---|
| `<season>` | `YYYY_YY`, e.g. `2025_26` | Underscore form of the season folder's hyphenated name (FR-016). |
| `<kind>` | `overview` \| `detail` | Exactly one `overview` per season per variant; zero or more `detail` per season per variant. |
| `<variant>` | `pins` \| `photos` | The two map variants (US1/US2). |
| `<slug>` | present only when `kind == detail` | Location-derived, ASCII/hyphen-normalized city token (research.md §9); disambiguated with a trailing `_2`, `_3`, ... if two clusters in the same season/variant would otherwise collide. |

## Visual contract

- **Pin variant**: one filled circular pin per eligible member (data-model.md §
  Applicant Record eligibility), colored by role per the 4-color table in research.md
  §7. No legend is rendered on the image (FR-007) — color meaning is fixed and
  documented here/in research.md instead.
- **Photo variant**: one circular, center-square-cropped photo per eligible
  photographed member (research.md §8), same position as that member's pin would occupy.
- **Overlap fallback** (FR-013, applies on whichever map(s) a still-overlapping group
  appears on — an overview if no detail map was generated for it per FR-014, or a
  detail map that couldn't fully resolve it per research.md §5): pin variant shows one
  merged pin plus a small numeric multiplicity badge; photo variant shows the group's
  photo circles offset side-by-side (research.md §8).
- **Scale bar**: bottom-right corner, a labeled ruler bar (e.g. `"5 km"`) reflecting
  that specific map's actual rendered scale (research.md §6). Present by default,
  absent for a whole run when `--no-scale-bar` is passed.
- **Attribution**: bottom-left corner, `"© OpenStreetMap contributors"` (research.md
  §2) — always present, not affected by `--no-scale-bar`.

## Skipped members

Never silently dropped — every member excluded from a variant (no address, an address
that failed to geocode, or — photo variant only — no photo on file) is named in that
run's log output (FR-006, SC-002), not just absent from the image. Log location:
reuses the scraper's existing per-season `logs/<run-timestamp>.log` convention
(`seasons/<season-label>/logs/`), one log file per season this run touches.
