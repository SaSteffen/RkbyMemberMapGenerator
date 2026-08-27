# Phase 1 Data Model: Rider Pairing Suggester

No changes to `scripts/schemas/applicant_record.schema.json` or any persisted `.yaml`
record — this feature is purely derived/read-only (research.md §2, §3; Constitution
Check row III). Every entity below is computed in memory from records `rkby_records.
load_existing_records` already returns; none of them is persisted as its own file
format. The one thing this feature persists is the rendered report file described in
`contracts/report-output.md`.

## Latest Season

The season this entire feature operates on. Resolved as
`scripts.rkby_records.discover_seasons(data_dir)[-1]` — season labels (`YYYY-YY`) sort
correctly as plain strings, so the last discovered label is the most recent (matches
spec.md's Assumptions: "the last one returned by the project's existing season
discovery," not a hardcoded literal). If `discover_seasons` returns an empty list (no
season on file at all), the script logs that and exits `0` without writing a report —
there is nothing to report on yet, the same "empty input, still a valid run" handling
002/003 already give an empty `seasons/` folder.

## Role Classification

A derived value, not a stored field: `classify_role(raw_role: str | None) ->
Literal["rider", "service_crew", "supporter", None]`, computed by normalizing
`raw_role` (`.strip().lower()`) and matching it against `scripts.rkby_maps.rendering.
ROLE_COLORS`'s keys (research.md §4). `None` means "unrecognized or blank" — such a
record's `role` never counts as Rider evidence for any purpose in this feature (new
rider, mentor candidate, or historical "has ridden" evidence), matching spec.md's Edge
Cases.

## New Rider

**Source**: One latest-season record, filtered from `load_existing_records(data_dir,
latest_season)`.

**Fields used** (all read directly off the record, never modified): `match_key`,
`first_name`, `last_name`, `address`, `phone`, `email`, `photo`, `birthday`, `sex`,
`latitude`, `longitude`.

**Eligibility rule** (FR-002): included only if, on the latest-season record —
- `classify_role(role) == "rider"`
- `num_previous_seasons == 0` (not `None` — "the number of previous seasons is known
  and equal to zero," per FR-002; a `None` value means "unknown," not "zero," and must
  not be treated as a new rider)
- `excluded is not True` and `ignore is not True`
- `latitude is not None and longitude is not None` (successfully geocoded; this
  feature never geocodes on its own, FR-011 — an ungeocoded record is simply excluded,
  not geocoded-then-included)

**Cardinality**: Zero or more per latest season. A New Rider always appears in the
report (Acceptance Scenario 1.4, SC-001), even with zero Suggested Pairings.

## Mentor Candidate

**Source**: One latest-season record — the same pool `load_existing_records(data_dir,
latest_season)` draws from, minus whoever qualifies as a New Rider.

**Fields used**: same set as New Rider.

**Eligibility rule** (FR-003/FR-004):
- Latest-season record: `excluded is not True`, `ignore is not True`,
  `latitude is not None and longitude is not None` — identical base eligibility to New
  Rider.
- Not itself a New Rider (per the rule above) — a person can be a New Rider or a
  Mentor Candidate this season, never both (Acceptance Scenario 1.3).
- **Has ridden before**: `classify_role(latest_season_record.role) == "rider"`, **or**
  any earlier season's record for the same canonical identity (resolved via
  `rkby_records.canonical_match_keys` over *every* raw record across *every* season —
  research.md §3, not eligibility-filtered) has `classify_role(role) == "rider"`.
- Current role is otherwise irrelevant (FR-004) — a latest-season Service Crew or
  Supporter record passes as long as "has ridden before" holds.

**Cardinality**: Zero or more per latest season. The same Mentor Candidate may appear
in more than one New Rider's Suggested Pairing list — no cap (spec.md Edge Cases).

## Suggested Pairing

**Source**: Computed, not stored on any record — one instance per (New Rider, Mentor
Candidate) that survives ranking and the `--max-suggestions` cap.

**Fields**:
| Field | Type | Notes |
|---|---|---|
| `new_rider_match_key` | string | |
| `mentor_match_key` | string | |
| `rank` | int, 1-based | Position within this New Rider's own suggestion list, 1 = closest/best match. |
| `distance_km` | float | `haversine_km` between the two members' coordinates — primary ranking factor (FR-005). |
| `age_gap_years` | int or `None` | `None` when either birthday is unknown; never blocks the pairing (Edge Cases). |
| `same_sex` | bool or `None` | `None` when either `sex` is unknown; never blocks the pairing (Edge Cases). |

**Ranking rule** (FR-005/FR-006, research.md §5): for a given New Rider, all eligible
Mentor Candidates are sorted ascending by `(distance_km, age_gap_years or math.inf,
0 if same_sex else 1)`; the first `--max-suggestions` (default 3) become that New
Rider's Suggested Pairings, numbered `rank` 1..N. Fewer eligible candidates than the
cap → fewer (or zero) Suggested Pairings, never an error (SC-001).

## Training Cluster

**Source**: Computed — a connected component of size ≥ 3 among the latest season's
Rider-role pool (research.md §7).

**Membership rule** (FR-007, Acceptance Scenarios 2.1–2.3):
- Pool: latest-season records with `classify_role(role) == "rider"` (any
  `num_previous_seasons`, new or experienced alike), `excluded is not True`,
  `ignore is not True`, geocoded (`latitude`/`longitude` both set).
- Two pool members are linked if `haversine_km(a, b) <= cluster_radius_km` (default
  `5`, `--cluster-radius-km`).
- A cluster is one connected component (transitive — research.md §7 / 002's
  `find_overlap_groups` semantics) of at least 3 linked members. Components of size 1
  or 2 are not reported (Acceptance Scenario 2.2).
- Non-Rider members are never candidates for cluster membership, even when
  geographically inside a qualifying cluster's footprint (Acceptance Scenario 2.3) —
  they're simply never nodes in the graph.

**Fields**:
| Field | Type | Notes |
|---|---|---|
| `member_match_keys` | list[string] | Every Rider in this connected component. |
| `centroid` | (float, float) | Mean lat/lon of the group — for display/sorting only, not part of the eligibility rule. |

## Pairing Report (output file)

See `contracts/report-output.md` for the full file-structure contract. In brief: one
Markdown file, `$RKBY_DATA_DIR/reports/rider_pairings.md`, containing every New
Rider (with their Suggested Pairings, contact info, and photo link) and every Training
Cluster (with member contact info and photo links) for the latest season — regenerated
in full on every run (idempotent), auto-committed on write (FR-014), never containing
per-member roster data beyond what's already visible to the team internally (FR-009).

## PDF Export (derived output file)

`$RKBY_DATA_DIR/reports/rider_pairings.pdf` — a rendering of the Pairing Report's
*current on-disk content* (hand-edited or freshly generated) at the moment `--pdf` or
`--pdf-only` runs (FR-012). Not itself a data entity with its own fields; a pure
function of the `.md` file's bytes at export time. Gitignored, never auto-committed
(research.md §11).
