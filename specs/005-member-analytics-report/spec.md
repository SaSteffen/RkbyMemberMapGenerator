# Feature Specification: Member Analytics Report

**Feature Branch**: `005-member-analytics-report`

**Created**: 2026-08-18

**Status**: Draft

**Input**: User description: "plan the report. what i want is osmething that can for
instance be a python notebook, anything easy to start and export. should build a data
frame first, then wokr with it, make visualizations. obviously of importance: age and
gender distribution, distance from hamburg city center, number of riders, number of
service, from season to season. you get the picture i suppose. member retention. (also:
split over gender, age, distance form hamburg)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See this season's team makeup at a glance (Priority: P1)

As the team organizer, I want to see, for a single season, how many riders/service
crew/supporters we have and how the team breaks down by age, gender, and distance from
Hamburg, so I understand who this season's team actually is.

**Why this priority**: This is the foundational view — every other view in this report
(trends, retention) is this same per-season breakdown repeated or compared across
seasons. Without it working correctly for one season, nothing built on top of it can be
trusted.

**Independent Test**: Point the report at the local data store, select one season with
known member data, and confirm the resulting counts and distribution charts (role,
age, gender, distance-from-Hamburg) match a manual count of that season's records.

**Acceptance Scenarios**:

1. **Given** one season's worth of member records, **When** the report is run,
   **Then** it shows the count of riders, count of service crew, and count of any other
   role present in that season.
2. **Given** that same season, **When** the report is run, **Then** it shows the
   season's age distribution, gender distribution, and distance-from-Hamburg
   distribution as separate views.
3. **Given** a member record with no birthday, no sex, or no resolved coordinates on
   file, **When** the report is run, **Then** that member is still counted, shown under
   an explicit "unknown" category for the field that's missing, rather than being
   silently dropped or misreported.

---

### User Story 2 - See how the team has changed season to season (Priority: P2)

As the team organizer, I want to see how total member count, rider count, service
count, age mix, gender mix, and distance-from-Hamburg mix have moved across every
season we have data for, so I can spot growth, shrinkage, or shifting demographics
over time.

**Why this priority**: This is the "from season to season" comparison the request
explicitly calls out, and is the main reason to look at more than one season at once.
It depends on User Story 1's per-season numbers being correct, but adds the
across-season view on top.

**Independent Test**: Point the report at a local data store with multiple seasons on
file and confirm each trend view (total members, rider count, service count, age mix,
gender mix, distance mix) plots one point/bar per season, in chronological order,
matching a manual count for each season.

**Acceptance Scenarios**:

1. **Given** three or more seasons of member records, **When** the report is run,
   **Then** it shows total-member-count, rider-count, and service-count each as a
   single trend across all seasons in chronological order.
2. **Given** the same seasons, **When** the report is run, **Then** it shows how the
   age distribution, gender distribution, and distance-from-Hamburg distribution shift
   from one season to the next.
3. **Given** only one season of data exists on disk, **When** the report is run,
   **Then** it clearly indicates there isn't enough data yet for a trend, rather than
   drawing a misleading single-point trend or erroring.

---

### User Story 3 - Understand member retention (Priority: P2)

As the team organizer, I want to know what fraction of each season's members return
the following season — overall, and split by gender, age, and distance from Hamburg —
so I can tell who we're losing and where to focus retention efforts.

**Why this priority**: Retention is the other headline metric explicitly requested,
alongside the season-to-season trends from User Story 2. It's ranked alongside User
Story 2 rather than above it because it depends on the same per-season member
identification and is naturally the next question once the trends are visible.

**Independent Test**: Point the report at a local data store with at least two
consecutive seasons where the returning/departing members are known ahead of time, and
confirm the computed retention rate (overall, and each gender/age/distance split)
matches that known outcome.

**Acceptance Scenarios**:

1. **Given** two consecutive seasons of member records, **When** the report is run,
   **Then** it shows the percentage of the earlier season's members who are also
   present in the later season.
2. **Given** the same two seasons, **When** the report is run, **Then** it shows that
   same retention rate separately for each gender, each age bracket, and each
   distance-from-Hamburg bracket.
3. **Given** a member whose identity is known to have changed between seasons (e.g. a
   recorded alias from a name change) and one whose identity change was never
   recorded, **When** retention is computed, **Then** the known alias is resolved to
   one person while the unrecorded change is treated as two different people —
   matching how the rest of the tool already resolves identity across seasons.

---

### User Story 4 - Share the finished report (Priority: P3)

As the team organizer, I want to export the finished set of charts and summary
numbers to a single file, so I can hand it to someone else on the team without them
needing to install or run anything themselves.

**Why this priority**: Valuable but secondary — the analysis in User Stories 1-3 is
useful to the organizer even before it can be shared with anyone else.

**Independent Test**: After running the report, trigger the export step and confirm a
single output file is produced that opens and displays every chart and summary table
without re-running any analysis.

**Acceptance Scenarios**:

1. **Given** a completed report run, **When** the export step is triggered, **Then**
   a single shareable file is produced containing every chart and summary table from
   that run.
2. **Given** that exported file, **When** it is opened by someone without the
   analysis tool set up, **Then** every chart and table is visible without needing to
   re-run anything, and no per-member roster of names is exposed — only the aggregated
   counts, rates, and distributions.

---

### Edge Cases

- A season has zero members with resolved coordinates: distance-from-Hamburg views for
  that season show an explicit "unknown/not geocoded" category rather than an empty or
  misleading chart.
- Only one season of data exists on disk: season-to-season trend and retention views
  say so plainly instead of erroring or plotting a single misleading point.
- A member's `match_key` changes between seasons without a recorded alias linking it to
  their earlier key: they are treated as two different people, the same known
  limitation the existing interactive map already has — not something this report is
  expected to solve.
- A member skips a season and returns two seasons later: they are not counted as
  "retained" for the season they skipped, but do count again once they reappear.
- A role value shows up that isn't Rider, Service Crew, or Supporter (e.g. a
  newly-introduced committee role): it appears as its own labeled category rather than
  being dropped or folded into an "other" bucket.
- A member has an address on file but it was never successfully geocoded (no
  latitude/longitude): they're still counted in role/age/gender views, just excluded
  from distance-based views.
- A member is marked `excluded` or `ignore`: they are left out of every count and
  chart, consistent with how the rest of the tool treats those flags.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load every season currently discoverable in the local data
  store into one structured per-member-per-season dataset, reusing the existing
  season-discovery and record-loading logic rather than re-implementing it.
- **FR-002**: System MUST exclude any record marked `excluded` or `ignore` from every
  count, distribution, and chart.
- **FR-003**: System MUST report, per season, the count of members by role (Rider,
  Service Crew, Supporter, and any other role value present), including a distinct
  category for members with no role on file.
- **FR-004**: System MUST compute each member's age as of that particular season
  (derived from their birthday and the season) wherever birthday is known, and MUST
  report members with no birthday on file under a distinct "unknown" category rather
  than dropping them.
- **FR-005**: System MUST report each season's gender distribution from the raw `sex`
  field, with a distinct "unknown" category for members with no value on file.
- **FR-006**: System MUST compute each member's distance from a single fixed Hamburg
  city-center reference point using their existing geocoded coordinates, for every
  member who already has coordinates on file; members without coordinates MUST be
  reported under a distinct "unknown/not geocoded" category rather than dropped or
  excluded silently.
- **FR-007**: System MUST NOT perform new geocoding lookups; distance-from-Hamburg
  analysis uses only coordinates already present in local records.
- **FR-008**: System MUST show, for any single selected season, the role, age, gender,
  and distance-from-Hamburg distributions for that season.
- **FR-009**: System MUST show, across every discovered season in chronological order,
  the trend of total member count, rider count, and service-crew count.
- **FR-010**: System MUST show, across every discovered season, how the age, gender,
  and distance-from-Hamburg distributions shift from season to season.
- **FR-011**: System MUST compute a season-over-season retention rate: the proportion
  of one season's members who are also present in the immediately following discovered
  season, resolving each member's identity across seasons the same way the existing
  interactive map's cross-season merge already does (via `match_key`, resolving
  `alias_match_keys` where present).
- **FR-012**: System MUST break the retention rate down by gender, by age bracket, and
  by distance-from-Hamburg bracket, in addition to the overall rate, for every
  consecutive season pair available.
- **FR-013**: System MUST be runnable, end to end, starting from the local data store
  with no manual data wrangling beyond pointing it at that data, and MUST reflect newly
  added season data on a re-run without any code changes.
- **FR-014**: System MUST be able to export a completed run's charts and summary
  tables to a single file that can be opened and read without re-running any analysis.
- **FR-015**: Exported/shareable output MUST show only aggregated counts, rates, and
  distributions — never a per-member roster of names alongside personal fields — per
  the project's rule that shareable artifacts expose the minimum data necessary.
- **FR-016**: System MUST NOT read from, write to, or commit anything under the
  project's gitignored member-data or credential locations beyond loading the existing
  local records it analyzes, and MUST NOT transmit any member data to a third-party or
  cloud service.

### Key Entities

- **Member-Season Observation**: One row per (member, season) — that member's role,
  age at that season, gender, and distance from Hamburg for that season, plus whether
  they also appear in the immediately following season. The basis for every
  distribution and trend view.
- **Season Summary**: The aggregated counts and distributions (role counts, age
  buckets, gender counts, distance buckets, total member count) for one season.
- **Retention Cohort**: One consecutive season-to-season pair — the members present in
  both, the members present only in the earlier season, the computed retention rate,
  and that rate split by gender, age bracket, and distance bracket.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running the report against the local data store produces a summary
  covering every season currently on disk, with no code changes required to include a
  newly added season on the next run.
- **SC-002**: For any single season, a viewer can see rider count, service-crew count,
  gender split, age-bracket split, and distance-from-Hamburg split for that season in
  one place.
- **SC-003**: A viewer can see total member count, rider count, and service-crew count
  plotted across every available season in one trend view.
- **SC-004**: A viewer can see the season-over-season retention rate for every
  consecutive season pair available, plus that same rate split by gender, age bracket,
  and distance bracket.
- **SC-005**: A completed report run can be exported to one shareable file, in a
  single step, that a person without the analysis tool installed can open and read.
- **SC-006**: No exported file contains a per-member list of names or other personal
  fields — only aggregated statistics.

## Assumptions

- Output shape: a single, easy-to-start, easy-to-export Python analysis document (a
  notebook), consistent with the project's existing Python/minimal-dependency
  approach — its own independent artifact rather than a new mode of an existing
  script.
- "Riders" and "service" refer to the raw `role` field values "Rider" and "Service
  Crew" (the team's two primary participation roles besides Supporter); any other role
  value present in the data is shown as its own category rather than merged away.
- Age is computed as of each season (using that season's point in time), not the
  member's current age, since the report's purpose is explicitly to compare across
  seasons.
- The Hamburg city-center reference point is a single fixed landmark coordinate,
  chosen once and reused for every distance calculation; distance is straight-line
  (great-circle), not driving distance — consistent with the project's existing
  geocoding-only, no-routing-API approach.
- Retention is defined as presence in the immediately next discovered season, not any
  later season — a member who skips one season and returns later is not counted as
  "retained" across the gap.
- Member identity across seasons is resolved the same way the existing interactive
  map's cross-season merge already does (`match_key`, resolved through
  `alias_match_keys`); an unrecorded identity change (no alias on file) is a known,
  accepted limitation, not something this report needs to solve independently.
- Eligibility filtering mirrors the rest of the codebase: `excluded` and `ignore`
  records are left out of every view.
- This report is read-only with respect to the local data store: it does not write,
  correct, or geocode any member record — it only reads what earlier scraper/map-
  generator runs have already produced.
