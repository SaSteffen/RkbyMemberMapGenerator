# Feature Specification: Pairing Report Maps

**Feature Branch**: `007-pairing-report-maps`

**Created**: 2026-08-27

**Status**: Draft

**Input**: User description: "i want to extend the report generation to include maps for the clusters and a general overview map. all members (not only riders) shall be dsiplayed in the maps. the cluster generation is not yet perfect, it seems to leave out riders? at worst, we need to form single person clusters. we already have a map generation script and can reuse that one"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - No rider silently missing from Training Clusters (Priority: P1)

A team organizer reviewing the rider pairing report's Training Clusters section wants
every current-season rider to actually show up somewhere in it — including a rider who
doesn't happen to live near two or more teammates — instead of that rider quietly
disappearing from the report because the current grouping rule requires at least three
people before it reports a group at all.

**Why this priority**: This is a correctness fix for a report the organizer already
relies on. The map additions in the other two stories are only trustworthy once the
underlying set of Training Clusters is actually complete — a beautiful map of an
incomplete cluster list still hides riders from the organizer.

**Independent Test**: Run the report against a data set containing one rider who lives
far from every other rider, two riders who live close to each other but far from
everyone else, and three riders who live close together. Confirm all six riders each
appear in exactly one Training Cluster in the generated report — the isolated rider
alone, the pair together, and the trio together — with none of them missing.

**Acceptance Scenarios**:

1. **Given** a current-season rider who lives farther than the configured cluster
   radius from every other eligible rider, **When** the report is generated, **Then**
   that rider still appears in the Training Clusters section, reported as a
   single-member cluster, rather than being left out of the section entirely.
2. **Given** two current-season riders who live close enough together to be linked,
   but no third rider nearby, **When** the report is generated, **Then** they are
   still reported together as a two-member Training Cluster, rather than being
   dropped for falling short of a three-person minimum.
3. **Given** three or more current-season riders who live close together, **When**
   the report is generated, **Then** they are grouped into one Training Cluster
   exactly as before — this larger-group behavior is unchanged.
4. **Given** a current-season rider who is excluded, opted out (`ignore`), or has no
   successfully geocoded location, **When** the report is generated, **Then** that
   rider is still absent from the Training Clusters section — eligibility itself is
   unchanged; only the "at least three members" reporting threshold is removed.

---

### User Story 2 - See each training cluster on a map (Priority: P2)

A team organizer looking at a Training Cluster in the report wants to see at a glance
where its members actually live relative to each other, instead of having to
cross-reference addresses in their head or in a separate map tool.

**Why this priority**: This is the visualization the requester specifically asked for
and directly amplifies the value of a section that already exists — but it only makes
sense once User Story 1 guarantees the cluster list itself is complete.

**Independent Test**: Run the report against a data set with one qualifying Training
Cluster and confirm that cluster's section in the generated report includes a map
image with that cluster's members plotted on it at their home locations.

**Acceptance Scenarios**:

1. **Given** a Training Cluster appears in the report, **When** the report is
   generated, **Then** that cluster's section includes a map image showing that
   cluster's members plotted at their home locations.
2. **Given** other current-season members of any role (Rider, Service Crew, or
   Supporter) live within the same geographic area shown on a cluster's map, **When**
   that map is rendered, **Then** those other members also appear on it for context,
   the same way the existing member-map generator already shows nearby members on its
   own detail maps rather than showing a group in isolation.
3. **Given** the report is regenerated after the underlying data changes (a rider's
   address is corrected, a new rider joins a cluster's area), **When** the script
   runs again, **Then** every cluster's map is freshly regenerated to reflect the
   current data.

---

### User Story 3 - See the whole current season's team on one map (Priority: P3)

A team organizer wants one map, alongside the pairing report, that shows everyone on
the team this season — Riders, Service Crew, and Supporters alike — so they have a
general sense of where the team lives, not just where the riders needing pairing or
clustering live.

**Why this priority**: Additive context that rounds out the report but isn't required
for the report's core pairing/clustering purpose to work — it's the last thing the
requester mentioned and the least critical of the three.

**Independent Test**: Run the report against a data set containing a mix of Riders,
Service Crew, and Supporters with known addresses, and confirm the generated report
includes one overview map on which members of all three roles appear.

**Acceptance Scenarios**:

1. **Given** the pairing report is generated for the latest season, **When** it's
   produced, **Then** the report includes one overview map showing every eligible
   current-season member regardless of role — not just riders.
2. **Given** a member has no address on file, or their address could not be
   geocoded, **When** the overview map is generated, **Then** that member is simply
   left off the map, without blocking report generation.
3. **Given** the latest season has zero eligible, plottable members, **When** the
   report is generated, **Then** the overview map is still produced (showing no
   members) rather than causing the report generation to fail.

---

### Edge Cases

- A rider who was part of a larger cluster becomes isolated after other cluster
  members are later excluded, opted out, or removed from the data: on the next run
  they appear as their own single-member cluster instead of vanishing from the
  report.
- Two riders share the exact same address (already a recognized case in the existing
  member-map generator): they still form their own two-member Training Cluster and
  its map renders them as one merged marker rather than trying to zoom in far enough
  to visually separate two identical points.
- A single Training Cluster is very large (e.g., most of the season's riders live in
  one metro area): its map still renders sensibly, using the same map-sizing behavior
  the existing member-map generator already applies to large groups.
- The report is run with no Training Clusters at all possible (e.g., a season with
  zero eligible riders): the Training Clusters section still renders its existing
  "no training clusters found" placeholder text, with no cluster maps and no attempt
  to render one.
- A member appears on both a Training Cluster's map and the general overview map
  (expected and fine) — each map is independent, so there is no cross-referencing
  requirement between them beyond both reflecting the same current data.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST include every current-season rider who passes the existing
  Training Cluster eligibility rule (not excluded, not opted out via `ignore`,
  successfully geocoded) in the Training Clusters section of the report, with no
  minimum group size — including a cluster of exactly one rider — replacing the
  previous three-or-more-member minimum.
- **FR-002**: System MUST continue to group riders into a Training Cluster using the
  existing proximity-linking rule (two riders within the configured cluster radius
  are linked, and linkage is transitive across the group) — only the minimum
  reportable group size changes, not how riders get linked together.
- **FR-003**: System MUST render one map image per Training Cluster, plotting that
  cluster's members at their home locations, and present that image as part of that
  cluster's section in the report.
- **FR-004**: Cluster maps MUST be produced by reusing the project's existing
  map-rendering capability (basemap tiles, role-colored member markers, and
  same-location/overlap handling) already used to generate the project's member maps,
  rather than building a separate rendering approach.
- **FR-005**: A Training Cluster's map MUST also show other current-season members of
  any role who fall within the same geographic area as that cluster's map, for
  context, consistent with how the existing member-map generator already shows
  nearby members on its own zoomed-in maps rather than isolating just the triggering
  group.
- **FR-006**: System MUST render one overview map per report showing every eligible
  current-season member regardless of role (Rider, Service Crew, or Supporter),
  distinguished by role the same way the existing member-map generator already
  visually distinguishes roles.
- **FR-007**: The overview map's member eligibility (who appears on it) MUST match
  the existing member-map generator's own eligibility rule for its overview map (not
  excluded, not opted out, successfully geocoded) — this is a superset of the
  Training Cluster pool, since it is not restricted to riders.
- **FR-008**: System MUST present the overview map as a distinct, prominent part of
  the report — a whole-team view, independent of and separate from the per-cluster
  maps and the per-new-rider suggested-contact content.
- **FR-009**: A member with no address on file, or whose address cannot be
  successfully geocoded, MUST simply be left off every map this feature produces —
  never causing report generation to fail.
- **FR-010**: System MUST regenerate every map this feature produces (cluster maps
  and the overview map) fresh on every report run, so they always reflect that run's
  current data rather than a stale image from a previous run.
- **FR-011**: All map images this feature produces MUST be written only inside the
  local data directory (`RKBY_DATA_DIR`) alongside the rest of the pairing report's
  output, and MUST NOT be committed to this project's own code repository — matching
  how every other artifact containing member location data is already handled.
- **FR-012**: System MUST remain runnable independently of the project's other
  scripts — producing its cluster maps and overview map without requiring the
  separate member-map generator to have already been run for the season.

### Key Entities

- **Training Cluster** *(revised)*: A group of one or more current-season riders
  whose home locations lie close enough together (per the existing proximity-linking
  rule) to be reported as a group. Previously required at least three members; that
  minimum is removed by this feature, so a cluster may now consist of a single
  isolated rider, a pair, or a larger group as before.
- **Cluster Map**: A map image tied to one Training Cluster, plotting that cluster's
  members (and any other nearby current-season members of any role, for context) at
  their home locations.
- **Overview Map**: A single map image per report run plotting every eligible
  current-season member regardless of role, giving a whole-team geographic view
  independent of the Training Clusters and pairing-suggestion content.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every current-season rider who is not excluded, not opted out, and
  successfully geocoded appears in exactly one Training Cluster in the generated
  report — zero eligible riders missing from the section.
- **SC-002**: Every Training Cluster shown in the report has an accompanying map
  image that visually locates its members.
- **SC-003**: The generated report includes exactly one overview map depicting the
  full current-season membership across all roles, viewable as part of the report
  itself.
- **SC-004**: Re-running the report generator after a data change (e.g., a corrected
  address, a newly excluded member) produces maps that reflect the new data, with no
  manual regeneration step beyond re-running the script.
- **SC-005**: No map produced by this feature is ever written outside the local data
  directory or committed to the project's code repository.

## Assumptions

- Map rendering reuses the project's existing map-rendering modules (the same basemap
  stitching, role-colored markers, and overlap handling already powering the member
  map generator) rather than a new, independent implementation — matching the
  requester's own "we already have a map generation script and can reuse that one."
- The new map images are treated as reproducible, derived output — like the existing
  member-map generator's own map files and this report's exported PDF — so they are
  not committed to the local data repository's git history; they are simply
  regenerated fresh on every run.
- This report generator renders its own overview map independently rather than
  depending on the separate member-map generator having already produced one for the
  season, preserving this script's existing independent-of-other-scripts behavior.
- "All members" for the overview map (and for the contextual members shown on cluster
  maps) means the same base eligibility the existing member-map generator already
  uses for its own overview map (not excluded, not opted out, successfully geocoded)
  — it is not limited to riders, and not limited to members who ended up in a
  Training Cluster or a suggested pairing.
- Removing the three-member minimum for Training Clusters does not change the
  underlying proximity radius or linking rule at all — only the smallest group size
  that gets reported changes, from three down to one.
- The report's existing configurable cluster radius keeps its current meaning and
  default value; this feature does not introduce a new or different distance
  configuration.
