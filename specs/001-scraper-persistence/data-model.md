# Phase 1 Data Model: Applicant Scraper & Data Persistence

Entities as introduced in spec.md § Key Entities, expanded into concrete fields, types,
and validation/lifecycle rules. The persisted shape below is normative for
`contracts/applicant-record.schema.json`.

## Season

Not a persisted record itself — it's the folder + the label↔id resolution described in
research.md §5.

| Field | Type | Notes |
|---|---|---|
| label | string | Canonical hyphen form, e.g. `"2025-26"`. Also the folder name under `seasons/`. |
| intranet_season_id | int | Resolved per run from the season-selector page (research.md §5); never persisted — re-resolved every run. |
| intranet_team_id | int | Same as above. |

## Applicant Record

One YAML file per retained applicant, at
`<RKBY_DATA_DIR>/seasons/<season-label>/applicants/<match_key>.yaml`.

| Field | Type | Required | Write rule |
|---|---|---|---|
| `match_key` | string | yes | Set once at creation from `normalize(first_name)-normalize(last_name)` (research.md §9). Immutable — it's also the filename, so it is never rewritten in place; renaming a record is a manual human action (rename the file + edit the field together). |
| `alias_match_keys` | array\<string\> \| null | no | Exclusively human-set (like `ignore`). Other `match_key` value(s) — typically from an earlier season — that identify this same person after the intranet recomputed the key (spelling/married-name change). Not read by this feature; consumed only by 003-interactive-photo-map's cross-season merge to fold that season's record into this same person instead of a separate one. The scraper never writes it. |
| `first_name` | string | yes | Frozen once non-empty (FR-009). |
| `last_name` | string | yes | Frozen once non-empty (FR-009). |
| `address` | string \| null | no | Frozen once non-empty (FR-009). `null`/absent until first observed. |
| `phone` | string \| null | no | Frozen once non-empty (FR-009). |
| `role` | string \| null | no | Frozen once non-empty (FR-009). Raw text from the applicant list's `Role` column (research.md §15), e.g. `"Rider"`, `"Service Crew"`, `"Supporter"` — stored as scraped, not normalized/mapped. |
| `birthday` | string (`YYYY-MM-DD`) \| null | no | Frozen once non-empty (FR-009). Stored ISO 8601 regardless of the intranet's display format. |
| `status` | string | yes | The application status text as first observed (e.g. `"yes"`, `"maybe"`). Frozen at creation — never rewritten by later scrapes, per research.md §8 / FR-015 ("other fields left unchanged"). |
| `excluded` | boolean | yes | Default `false`. Set to `true` automatically, once, the first time a later scrape observes `status == "no"` for this (non-ignored) record (FR-015). Never auto-reverts; only a human edits it back. |
| `excluded_observed_at` | string (ISO 8601 datetime) \| null | no | Set together with `excluded: true`. `null` while `excluded` is `false`. |
| `ignore` | boolean | yes | Default `false`. Exclusively human-set/human-cleared (FR-010). The scraper reads it (to skip touching/recreating the record, FR-011) but **never writes it**. |
| `photo` | string (relative path) \| null | no | Relative path to the photo file under the season's `photos/` folder, e.g. `"photos/jane-doe.jpg"`. `null` until a photo fetch succeeds; a retry each run while `null` (FR-005). Once non-null, the referenced file is never overwritten (Story 2 AC2) — but see Photo Asset below for the actual overwrite-guard mechanism (it's file-existence-based, not this field). |

Notes:
- No `created_at`/`updated_at` metadata field — deliberately omitted; the local data
  repo's own git history is the source of truth for "when did this change"
  (research.md §6).
- `match_key` doubles as the natural primary key; there is no separate numeric id,
  consistent with FR-013/FR-020 restricting matching to normalized name within one
  season's folder only.

### State transitions

```
(not persisted)
   │  first scrape observes status != "no", not a name conflict
   ▼
excluded=false, ignore=false  ──(scrape observes status == "no")──▶ excluded=true
   │                                                                     │
   │ (human sets ignore=true at any point, from either state) ──────────┤
   ▼                                                                     ▼
ignore=true  (scraper never modifies this record again, in any field, from here on)
```

- `ignore=true` short-circuits everything: research.md's merge step (§8) and the
  exclusion check (§FR-015) both check `ignore` first and skip the record entirely if
  set (Story 3 AC1, Story 4 AC2).
- A record can reach `ignore=true` from any other state, including after already being
  `excluded=true` — the two flags are independent booleans, not a single enum, exactly
  because a human may want to ignore an excluded record, or ignore a still-active one,
  or (rare) later flip `excluded` back to `false` by hand while leaving `ignore` alone.

## Photo Asset

Not a schema-validated document — a binary file. Its "record" is simply: does
`seasons/<season>/photos/<match_key>.<ext>` exist on disk?

| Rule | Behavior |
|---|---|
| File does not exist | Scraper attempts to fetch it this run (research.md §4). Success → file written, `photo` field set. Failure → file left absent, `photo` stays `null`, a warning is logged (FR-005), retried next run. |
| File exists | Never read, fetched, or overwritten again by the scraper — regardless of whether the scraper or a human originally put it there (Story 2 AC2). |

Extension (`.jpg`/`.png`/etc.) is taken from the fetched image's actual content-type/
URL at write time, not assumed.

## Run Log

Not schema-validated (it's a log, not editable data). One file per run:
`seasons/<season>/logs/<run-timestamp>.log` (research.md §11). Every line is a
stdlib-`logging`-formatted record; only `WARNING`+ records land in the file. Warning
occurrences this feature defines (FR-016):

- newly observed status-to-`no` exclusion (record's `match_key`, prior status context)
- unresolved possible-duplicate/conflict match (both conflicting field sets, per
  research.md §9)
- per-applicant photo-fetch failure (`match_key`, underlying error)

## Local Data Repository

The root directory named by `RKBY_DATA_DIR`. Not created by this feature (per spec
Assumptions — it's expected to already exist as a git repo). Layout:

```
<RKBY_DATA_DIR>/
└── seasons/
    └── <season-label>/           # e.g. "2025-26"
        ├── applicants/
        │   └── <match_key>.yaml
        ├── photos/
        │   └── <match_key>.<ext>
        └── logs/
            └── <run-timestamp>.log
```

Multiple seasons live side-by-side under `seasons/`, each fully independent (FR-006,
FR-020) — no cross-season references anywhere in this data model.

**Auto-commit**: if this directory is (or is inside) a git work tree, a successful run
stages and commits only the `seasons/<season-label>/` subtree it just wrote to — see
research.md §14 for the detection/staging/commit rules and failure handling. If it is
not a git repository, this feature reads/writes the files above and nothing else.
