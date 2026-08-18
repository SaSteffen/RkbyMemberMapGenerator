# Phase 1 Data Model: Member Analytics Report

Entities as introduced in spec.md § Key Entities, expanded into concrete fields. This
feature only *reads* the existing Applicant Record (`specs/001-scraper-persistence/
data-model.md`, extended by `specs/002-map-generator/data-model.md`'s `latitude`/
`longitude`) — it defines no new persisted fields or files. Everything below is
derived, in-memory data, computed fresh on every run.

## Member-Season Observation (one row of the built DataFrame)

The output of `rkby_report.frame.build_member_season_frame(data_dir)`
(research.md §6-§8). One row per (member, season) that passed the eligibility filter
(§8): `excluded` false and `ignore` false. Ordered by `season_label`, then
`match_key`.

| Column | Type | Nullable | Derivation |
|---|---|---|---|
| `match_key` | string | no | The record's `match_key`, resolved to its canonical identity via `rkby_records.canonical_match_keys()` (research.md §7) so the same person's rows share one key across every season they appear in, even across a recorded alias. |
| `season_label` | string | no | `YYYY_YY`, from `discover_seasons()` (unchanged from 002). |
| `role` | string | yes (`"unknown"` sentinel, never a real null) | The record's raw `role` field verbatim (FR-003); `"unknown"` when `role` is null. |
| `sex` | string | yes (`"unknown"` sentinel) | The record's raw `sex` field verbatim (FR-005); `"unknown"` when null. |
| `age_at_season` | int | yes (`NaN`/`None`) | `birthday` full years as of that season's reference date (research.md §6); `None` when `birthday` is null — callers bucket this into `"unknown"` at aggregation time (§9), it is never dropped. |
| `age_bucket` | string | no (always resolvable, including `"unknown"`) | One of the fixed brackets in `rkby_report.buckets` (research.md §9), derived from `age_at_season`. |
| `distance_km` | float | yes (`NaN`/`None`) | Haversine distance from `rkby_report.geo.HAMBURG_CENTER` to `(latitude, longitude)` (research.md §5); `None` when either coordinate is null (FR-006/FR-007 — never newly geocoded here). |
| `distance_bucket` | string | no (always resolvable, including `"unknown/not geocoded"`) | One of the fixed brackets in `rkby_report.buckets` (research.md §9), derived from `distance_km`. |
| `retained_next_season` | bool | yes (`None` for a member's row in the *last* discovered season — genuinely unknown, not "no") | True iff this member's canonical `match_key` also has a row in the immediately next discovered season (FR-011/research.md §7); the basis for every retention computation in `rkby_report.aggregate`. |

## Season Summary (derived, not persisted)

The output of `rkby_report.aggregate.season_summary(df, season_label)` — one season's
worth of counts, feeding User Story 1's per-season snapshot views.

| Field | Type | Notes |
|---|---|---|
| `season_label` | string | Which season this summarizes. |
| `total_members` | int | Row count for that season after eligibility filtering (FR-012). |
| `role_counts` | dict[str, int] | `role` value → count, including `"unknown"` (FR-003). |
| `gender_counts` | dict[str, int] | `sex` value → count, including `"unknown"` (FR-005). |
| `age_bucket_counts` | dict[str, int] | `age_bucket` → count, in bracket order (FR-004). |
| `distance_bucket_counts` | dict[str, int] | `distance_bucket` → count, in bracket order, including `"unknown/not geocoded"` (FR-006). |

## Season Trend Table (derived, not persisted)

The output of `rkby_report.aggregate.season_trend(df)` — one row per discovered
season, in chronological order, feeding User Story 2's across-season views (FR-009,
FR-010).

| Column | Type | Notes |
|---|---|---|
| `season_label` | string | Chronological index. |
| `total_members`, `rider_count`, `service_count` | int | Headline counts per season (FR-009). |
| one column per age bucket, gender value, distance bucket | int | Same category set as Season Summary, pivoted wide across seasons, so a single line/bar chart can show how each distribution shifts season to season (FR-010). |

## Retention Cohort (derived, not persisted)

The output of `rkby_report.aggregate.retention_cohort(df, season_a, season_b)` for
one consecutive season pair, and `rkby_report.aggregate.retention_by_split(df,
split_column)` for the same rate broken down (FR-011, FR-012) — feeding User Story
3's retention views.

| Field | Type | Notes |
|---|---|---|
| `season_a`, `season_b` | string | The consecutive pair (`season_b` is the season immediately following `season_a` among discovered seasons). |
| `retained_count` | int | Members present in both seasons (by canonical `match_key`). |
| `departed_count` | int | Members present only in `season_a`. |
| `retention_rate` | float | `retained_count / (retained_count + departed_count)`. |
| `retention_rate_by_gender` | dict[str, float] | Same rate, grouped by `season_a`'s `sex` value. |
| `retention_rate_by_age_bucket` | dict[str, float] | Same rate, grouped by `season_a`'s `age_bucket`. |
| `retention_rate_by_distance_bucket` | dict[str, float] | Same rate, grouped by `season_a`'s `distance_bucket`. |

## Local Data Repository (read/write footprint)

```
<RKBY_DATA_DIR>/
├── seasons/                    # read-only for this feature — no new fields, no writes
│   └── <season-label>/applicants/*.yaml
└── reports/                    # NEW — created only by the export step (research.md §10),
    └── <timestamp-or-label>.html   #   gitignored the same way maps/ and .tile_cache/ are
```

No new fields are added to the Applicant Record schema, and no new season-folder
subdirectory is written by the notebook itself — only the optional export step writes
anything to disk, and only under the new `reports/` folder.
