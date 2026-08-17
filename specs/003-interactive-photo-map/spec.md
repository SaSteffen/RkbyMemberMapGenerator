# Feature Specification: Interactive Photo Map

**Feature Branch**: `003-interactive-photo-map`

**Created**: 2026-08-17

**Status**: Draft

**Input**: User description: "i want to add an interactive map that looks very
similar to the map with the picturees but can be interacted with: scroll zoom, pan by
dragging, (also add buttons for zoom and pan), when picture is hovered, then a popup
shows name, roles, number of previous seasons, job title. put the pictures to their
actual address, can overlap, because that can be resolved via zoom. map should be a
shareable artifact. but a folder with a standalone website that needs no online
dependencies (all bundled) should be fine"

**Amendment (2026-08-17)**: "i also want to generate this map only oncce, for all
seasons. there shall be a button, that auto-selects the current season (logic for
this is the same as in the scraper flag default) but all the other seasons can be
selected as well in parallel. since some people are part of more than one season, we
need to merge records. use the match_key for this. information is taken from the
latest record/season available for that person. since roles change: show them
separately for each season in the hover."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Explore the current season on one navigable map (Priority: P1)

As a team organizer, I want a single generated interactive map — covering every
season the team has data for — that opens showing the current season by default, and
that I can scroll to zoom, drag to pan, and control with on-screen zoom/pan buttons,
so I can freely explore where everyone lives without being limited to one fixed,
pre-cropped view like the static photo map, and without having to regenerate anything
each season.

**Why this priority**: This is the core new capability of the feature — turning a
fixed image into something explorable, generated once for all seasons instead of
per-season — and stands on its own as useful even before season-switching or hover
details exist.

**Independent Test**: Generate the interactive map once and confirm it opens showing
every eligible member of whichever season is "current" as of today (using the same
rule the scraper uses to pick its own default season) as a photo at their address, and
that scrolling zooms in/out, click-and-drag pans the view, and the on-screen zoom and
pan buttons each produce the same effect as their corresponding mouse gesture.

**Acceptance Scenarios**:

1. **Given** the map has just been generated and opened for the first time, **When**
   no season selection has been changed yet, **Then** it shows every eligible member
   of the season considered "current" as of today (same rule as the scraper's default
   season), positioned at their geocoded address over recognizable geographic
   context.
2. **Given** the map is open, **When** the viewer scrolls over it, **Then** the map
   zooms in or out centered on the cursor; **When** the viewer clicks and drags,
   **Then** the visible area pans in the drag direction.
3. **Given** the map is open, **When** the viewer uses the on-screen zoom-in,
   zoom-out, and pan controls, **Then** the map responds the same way it does to the
   corresponding scroll/drag gesture.
4. **Given** two or more members' photos are close enough to visually overlap at the
   current zoom level, **When** the viewer zooms in further, **Then** the photos
   separate enough to be individually distinguishable (unless they share the exact
   same address — see Edge Cases).

---

### User Story 2 - Bring other seasons into view (Priority: P2)

As a team organizer, I want to select additional seasons alongside (not instead of)
the current one, so I can see who else has been part of the team over the years — with
anyone active in more than one selected season shown once, not duplicated.

**Why this priority**: Builds directly on Story 1's single generated artifact; the
map is already useful showing only the current season, but the feature was explicitly
requested to cover every season from one generation run.

**Independent Test**: Open the generated map, toggle on one or more additional
seasons alongside the default one, and confirm members from those seasons appear
immediately (no regeneration or reload), and that anyone who belongs to more than one
of the now-active seasons appears as exactly one photo, not one per season.

**Acceptance Scenarios**:

1. **Given** the map is open showing only the default (current) season, **When** the
   viewer selects an additional season's control, **Then** that season's eligible
   members appear on the map immediately, in addition to (not replacing) the
   already-shown season's members.
2. **Given** two or more season controls are active at once, **When** a person has an
   eligible record in more than one of those active seasons, **Then** they appear as
   a single photo, using their most recent eligible record's photo, name, and
   position (see FR-010 for precedence when records disagree).
3. **Given** any combination of season controls is active, **When** the viewer
   deselects a season, **Then** members who were only shown because of that season
   disappear, while members still covered by another active season remain.

---

### User Story 3 - Identify a member by hovering their photo (Priority: P3)

As a team organizer or member browsing the map, I want to hover over a photo and see
that person's name, number of previous seasons, and their role(s) for each season
shown, so I can identify who I'm looking at — including how their role has changed
over time — without leaving the map.

**Why this priority**: Adds the "who is this" identification layer on top of Stories
1 and 2; valuable but the map is already useful for spotting geographic patterns
without it.

**Independent Test**: Open the generated map with at least two seasons active for a
member who participated in both with different roles, hover over that member's photo,
and confirm the popup shows their name and number of previous seasons once, plus a
separate role entry for each active season they belong to.

**Acceptance Scenarios**:

1. **Given** the map is open, **When** the viewer hovers over a member's photo,
   **Then** a popup appears near that photo showing the member's full name and number
   of previous seasons, plus one role entry (their job title / primary role and any
   additional roles) for each currently active season that member belongs to.
2. **Given** a member belongs to only one currently active season, **When** their
   popup is shown, **Then** it shows exactly one season's role entry.
3. **Given** a member is missing one of the popup's data points (e.g. previous-season
   count not on file), **When** their popup is shown, **Then** that field is shown as
   unknown/omitted rather than blank, broken, or crashing the popup.
4. **Given** the cursor moves off a photo, **When** no other photo is hovered,
   **Then** the popup closes.

---

### User Story 4 - Share the map as a self-contained folder (Priority: P4)

As a team organizer, I want to hand the generated map to teammates as a folder they
can open on their own computer with no internet connection and no software to
install, so I can freely share it (email, USB stick, shared drive) without depending
on any online service staying available.

**Why this priority**: Makes Stories 1 and 2 distributable beyond the organizer's own
machine; the map is already fully functional locally without this, but sharing is a
named goal of the feature.

**Independent Test**: Copy the generated interactive-map output folder to a machine
with no network access, open it in a standard current web browser, and confirm
panning, zooming, season selection, and hover popups all work exactly as they did on
the generating machine.

**Acceptance Scenarios**:

1. **Given** the generated interactive-map folder, **When** the network connection is
   disabled and the folder is opened in a standard current web browser, **Then** the
   map loads fully and every interaction from Stories 1-3 still works, including
   switching which seasons are active.
2. **Given** the generated folder, **When** it is copied as a whole to a different
   computer, **Then** nothing about it needs to be reconfigured, installed, or built
   before it works there.

---

### Edge Cases

- A member has no address on file, or an address that cannot be resolved to a
  location, in a given season's record → that season's record is logged as skipped
  (same as the existing photo map) and does not contribute to that person's marker;
  the run continues.
- A member is flagged `excluded` or `ignore` in a given season's record → that
  season's record is treated as if it doesn't exist for map purposes (it never
  triggers inclusion, never supplies "latest" identity data, and never contributes a
  role entry to the hover popup), consistent with supporting an opted-out member.
- A member who is flagged `excluded`/`ignore` (or otherwise ineligible) in every
  season they have a record for → never appears on the map, regardless of which
  seasons are active.
- A member has a resolvable, eligible address but no photo on file → still appears on
  the map, shown with the same fixed placeholder image used by the existing photo
  map.
- Two or more distinct members share the exact same address → their photos remain
  stacked at every zoom level (no amount of zooming can separate identical
  coordinates); the viewer must still be able to discover and view each of those
  members individually (e.g. not permanently hidden behind whichever photo happens to
  render on top).
- A person belongs to more than one season, and their most recent eligible record
  differs from an earlier one (moved address, new photo, different role) → their
  marker uses the most recent eligible record's photo/name/position; older active
  seasons still each contribute their own role entry to the hover popup.
- No season control is active (the viewer deselected all of them, including the
  default) → the map shows no members rather than erroring; this is a valid, if
  empty, state.
- The season considered "current" as of the moment the map is opened (per the
  scraper's default-season rule) is not among the seasons the data actually contains
  yet (e.g. the map is opened before that season has been scraped) → the default
  selection falls back to the most recent season that is actually present in the
  bundled data.
- A season has zero eligible members → it still exists as a selectable control that,
  when active, simply contributes nobody to the map.
- The interactive map's output folder does not yet exist for a given data directory →
  it is created and excluded from version control before any files are written into
  it.
- A viewer opens the shared folder on a machine with no network access at all → the
  map still fully loads and every interaction still works (Story 4).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a standalone script, run independently of the
  scraper and of the existing static map generator, that produces the interactive map
  (constitution Principle II).
- **FR-002**: The system MUST generate the interactive map in a single run that
  produces exactly one artifact covering every season found under the local data
  directory, with no CLI option to select a subset of seasons — never one artifact
  per season.
- **FR-003**: The system MUST bundle every season's eligible member data into that
  one artifact at generation time, so that switching which seasons are active while
  viewing (FR-006-FR-008) never requires regenerating the artifact or any further
  network access.
- **FR-004**: A season's record for a member is eligible for the map if, and only if,
  it has a resolvable address and is not flagged `excluded` or `ignore` — matching
  the existing photo map's rules, applied per season-record.
- **FR-005**: The system MUST log (not crash on) any season-record skipped due to a
  missing/unresolvable address, identifying which member and which season, and
  continue processing the rest of the run.
- **FR-006**: The system MUST present one selectable control per season present in
  the data, and MUST allow any combination of them to be active at the same time
  (selecting one MUST NOT deselect another) — members are shown if at least one of
  their eligible season-records belongs to a currently active season.
- **FR-007**: On first opening the map, before the viewer changes anything, the
  system MUST default to having exactly the season considered "current" as of that
  moment active, determined at view time (using the viewer's own device clock) by the
  same rule the scraper uses for its own default season argument: seasons run
  August-July, so a date in January-July belongs to the season that started the
  previous August. If that computed season is not present in the bundled data, the
  system MUST fall back to defaulting to the most recent season that is present.
- **FR-008**: Changing which seasons are active MUST update the displayed members
  immediately, without a page reload.
- **FR-009**: When the same person (matched by each record's existing person-matching
  key, used to link one person's records across seasons) has an eligible record in
  more than one currently active season, the system MUST render them as a single
  marker, never one marker per season.
- **FR-010**: For a merged person (FR-009), the marker's photo, name, and map
  position MUST be taken from that person's most recently dated eligible
  season-record among all their seasons (not only the currently active ones) —
  ineligible (FR-004) season-records are never used as this "latest" source.
- **FR-011**: The system MUST render each shown member as a circular cropped photo —
  their own photo where one is on file, otherwise the existing fixed placeholder
  image — positioned at the map location from FR-010, using the same crop and
  placeholder logic as the existing photo map.
- **FR-012**: The system MUST allow members' photos to visually overlap on the map
  rather than automatically generating separate detail maps or merged/multiplicity
  markers; overlap between distinct people is expected to be resolved by the viewer
  zooming and panning interactively.
- **FR-013**: The system MUST support zooming via mouse scroll and panning via
  click-and-drag directly on the map.
- **FR-014**: The system MUST provide on-screen buttons for zooming in, zooming out,
  and panning, each producing the same effect as the corresponding mouse gesture.
- **FR-015**: The system MUST show a popup when a member's photo is hovered,
  containing that member's full name and number of previous seasons (each shown
  once), plus one role entry — primary role/job title and any additional roles — for
  every currently active season that member has an eligible record in (see
  Assumptions for how these map to the local record's fields); moving the cursor off
  the photo MUST close the popup.
- **FR-016**: When one of the popup's data points is not on file for a member, the
  system MUST show that field as unknown/omitted rather than leaving it blank in a
  way that looks broken or omitting the rest of the popup.
- **FR-017**: The system MUST render the map's photos over recognizable geographic
  context (matching the existing map generator's approach to orienting the viewer),
  bundled into the output so it remains visible with no network access (see FR-019).
- **FR-018**: The system MUST write the interactive map's output into the local data
  directory identified by the `RKBY_DATA_DIR` environment variable, as a single
  artifact (not season-prefixed, since it spans every season), ensuring that location
  is excluded from version control before writing any files into it (constitution
  Principle I).
- **FR-019**: The generated interactive map MUST be fully self-contained: every
  resource it needs (code, styling, geographic imagery, member photos, and member
  data shown in popups, for every season) MUST be bundled inside its own output
  folder, such that opening and fully using the map — including switching active
  seasons — on another computer requires no network/internet access and no
  additional software beyond a standard, current web browser.
- **FR-020**: The system MUST resolve member addresses to coordinates using the same
  cached-geocoding mechanism as the existing map generator, reusing already-cached
  coordinates and never re-geocoding an address that already has one cached
  (constitution Principle I's geocoding exception).
- **FR-021**: When multiple distinct people share the exact same coordinates, the
  system MUST still allow the viewer to discover and view each individual person's
  popup, not only whichever photo happens to render on top.
- **FR-022**: If the interactive map bundles third-party geographic imagery, the
  system MUST comply with that imagery source's usage and attribution requirements,
  consistent with how the existing map generator already attributes its basemap.

### Key Entities

- **Interactive Map Artifact**: The single self-contained, shareable output — a
  folder of bundled files that together form a working offline website covering
  every season in the local data directory, generated once per run.
- **Season Selection**: The set of currently active season controls (FR-006-FR-008);
  determines which members are shown and which seasons contribute role entries to
  each shown member's popup.
- **Member Marker**: One real person's circular photo (or placeholder) positioned at
  their most-recent eligible address (FR-009/FR-010) — a single marker even when that
  person has eligible records in more than one currently active season.
- **Popup Detail**: The name and previous-season count (each single-valued, from the
  person's latest eligible record) plus a per-active-season list of role entries,
  shown when a marker is hovered (FR-015/FR-016).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A viewer can pan and zoom to inspect any member's photo individually,
  including members who appear stacked together at the default view.
- **SC-002**: A viewer can identify any visible member's name, previous-season count,
  and role(s)/job title for each season currently active within one hover, with no
  click or navigation required.
- **SC-003**: A recipient with no involvement in generating the map can open the
  shared folder on their own computer, with their network connection off, in a
  standard current web browser, and fully use every interaction (pan, zoom, buttons,
  season selection, hover popups) — zero installation steps, zero network requests.
- **SC-004**: Opening the map for the first time, with no season deliberately chosen
  yet, shows exactly the members eligible for whichever season is "current" as of
  that moment on the viewer's own device — reproducing the scraper's own
  default-season rule.
- **SC-005**: A person with eligible records in two or more currently active seasons
  is never shown as more than one photo on the map.
- **SC-006**: Selecting or deselecting a season control changes the displayed members
  immediately, with no reload and no regeneration of the artifact.
- **SC-007**: Every season-record skipped from the map (missing/unresolvable address)
  is individually identifiable from the run's log output, and no skipped record stops
  the run.
- **SC-008**: An address already resolved by a prior run (by this script or the
  existing map generator) is never sent to an external geocoding lookup again.
- **SC-009**: Re-running the generator after a local data correction (in any season)
  produces an updated single artifact with no stale data left over from before the
  correction.
- **SC-010**: A member flagged as opted-out (`excluded` or `ignore`) in every one of
  their season records never appears anywhere in the shared artifact, including in
  popup data, regardless of which seasons are active; a member opted out in only
  some of their seasons is never shown or described using an opted-out record.
- **SC-011**: Generating the single interactive-map artifact across all of this
  team's current seasons (several seasons, roughly 200 member records each) completes
  in under 15 minutes on a typical laptop.

## Assumptions

- **New, separate script**: Per constitution Principle II, this is a new standalone
  script rather than a mode/flag added to `generate_member_maps.py` — it is a
  different kind of artifact (an interactive bundle vs. static PNGs), even though it
  reuses that script's eligibility rules, photo-crop/placeholder logic, and
  address-geocoding cache.
- **Popup field mapping**: The user's requested popup fields map onto the existing
  local record's fields as follows: "name" = first/last name; "number of previous
  seasons" = `num_previous_seasons`; "roles" and "job title" are combined into one
  per-season role entry made of the primary `role` field (e.g. Rider / Service Crew /
  Supporter) plus the `additional_roles` list. They are combined and shown per
  season, rather than "job title" being a single latest-only value, because both
  fields live in each season's own record and both are equally subject to changing
  season to season — singling out only `additional_roles` as season-varying while
  freezing the primary role to one snapshot would hide real role history. No separate
  real-world job-title field exists (or is scraped) in this project — the primary
  participation role is the closest concept the local data has to a "title."
- **Photo-only variant**: The interactive map mirrors the existing *photo* map
  specifically (per "looks very similar to the map with the picturees"); it does not
  also provide a plain-pin interactive variant.
- **Single combined artifact**: Unlike the existing static map generator (one output
  per season), this feature generates exactly one interactive-map artifact per run,
  spanning every season in the local data directory; season filtering happens inside
  the already-open map (FR-006-FR-008), not by generating separate files.
- **"Latest" is scoped to that person, not to the whole dataset**: FR-010's
  latest-eligible-record rule is evaluated per person (by their person-matching key)
  across all of their own season records — it does not compare across different
  people, and it skips over any of that person's own season-records that are
  ineligible (FR-004) when deciding which one is "latest."
- **Season boundary for the default-season rule (FR-007)**: mirrors the scraper's
  existing `default_season_label` logic exactly — a season is labeled by its August
  start year; a date in January-July belongs to the season that started the previous
  August, a date in August-December belongs to the season starting that same August.
- **No forced non-overlap logic**: Unlike the existing static map generator, this
  feature deliberately does not detect overlaps or generate detail maps/merged
  markers — the user explicitly asked for overlap to be resolved by the viewer's own
  zoom/pan, which is a simpler and sufficient substitute once the map is interactive.
- **Basemap bundling mechanism**: How geographic context imagery is captured and
  bundled offline (e.g. pre-rendered composite images or a small set of cached map
  tiles covering the needed area/zoom range) is a technical decision left to
  planning, the same way the existing map generator's basemap source was. Whatever
  approach is chosen must respect its source's usage/attribution terms (FR-022).
- **No access control on the shared artifact**: Once shared, the folder can be opened
  by anyone who receives it; this feature does not add a password or other access
  restriction. This matches the existing photo map's precedent (already shareable as
  an image) — deciding who receives the folder remains a human/organizational
  decision outside this tool's scope.
- **Browser support**: "Standard, current web browser" means a recent version of a
  mainstream desktop browser (e.g. Chrome, Firefox, Edge, Safari); older or niche
  browsers are out of scope.
