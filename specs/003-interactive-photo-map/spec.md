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

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Explore the whole team on one navigable map (Priority: P1)

As a team organizer, I want an interactive version of the photo map that I can scroll
to zoom, drag to pan, and control with on-screen zoom/pan buttons, so I can freely
explore where everyone lives without being limited to one fixed, pre-cropped view like
the static photo map.

**Why this priority**: This is the core new capability of the feature — turning a
fixed image into something explorable — and stands on its own as useful even before
any hover details exist.

**Independent Test**: Generate the interactive map for a season and confirm it opens
showing every eligible member's photo at their address, and that scrolling over the
map zooms in/out, click-and-drag pans the view, and the on-screen zoom and pan buttons
each produce the same effect as their corresponding mouse gesture.

**Acceptance Scenarios**:

1. **Given** a generated interactive map for a season, **When** it is opened, **Then**
   it shows every eligible member (same eligibility as the existing photo map) as a
   circular photo positioned at their geocoded address, on top of recognizable
   geographic context.
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

### User Story 2 - Identify a member by hovering their photo (Priority: P2)

As a team organizer or member browsing the map, I want to hover over a photo and see
that person's name, role(s), number of previous seasons, and job title in a popup, so
I can identify who I'm looking at without leaving the map.

**Why this priority**: Adds the "who is this" identification layer on top of Story
1's navigation; valuable but the map is already useful for spotting geographic
patterns without it.

**Independent Test**: Open a generated interactive map, hover over an individual
member's photo, and confirm a popup appears showing that member's name, role(s),
number of previous seasons, and job title, and that the popup disappears or updates
when the cursor moves away or to a different photo.

**Acceptance Scenarios**:

1. **Given** the map is open, **When** the viewer hovers over a member's photo,
   **Then** a popup appears near that photo showing the member's full name, their
   role(s), their number of previous seasons, and their job title.
2. **Given** a member is missing one of the popup's data points (e.g. previous-season
   count not on file), **When** their popup is shown, **Then** that field is shown as
   unknown/omitted rather than blank, broken, or crashing the popup.
3. **Given** the cursor moves off a photo, **When** no other photo is hovered,
   **Then** the popup closes.

---

### User Story 3 - Share the map as a self-contained folder (Priority: P3)

As a team organizer, I want to hand the generated map to teammates as a folder they
can open on their own computer with no internet connection and no software to
install, so I can freely share it (email, USB stick, shared drive) without depending
on any online service staying available.

**Why this priority**: Makes Stories 1 and 2 distributable beyond the organizer's own
machine; the map is already fully functional locally without this, but sharing is a
named goal of the feature.

**Independent Test**: Copy a generated season's interactive-map output folder to a
machine with no network access, open it in a standard current web browser, and
confirm panning, zooming, and hover popups all work exactly as they did on the
generating machine.

**Acceptance Scenarios**:

1. **Given** a generated interactive-map folder, **When** the network connection is
   disabled and the folder is opened in a standard current web browser, **Then** the
   map loads fully and every interaction from Stories 1 and 2 still works.
2. **Given** the generated folder, **When** it is copied as a whole to a different
   computer, **Then** nothing about it needs to be reconfigured, installed, or built
   before it works there.

---

### Edge Cases

- A member has no address on file, or an address that cannot be resolved to a
  location → logged as skipped (same as the existing photo map) and excluded from the
  interactive map; the run continues.
- A member is flagged `excluded` or `ignore` in their local record → left off the
  interactive map entirely, consistent with supporting an opted-out member.
- A member has a resolvable address but no photo on file → still appears on the map,
  shown with the same fixed placeholder image used by the existing photo map.
- Two or more members share the exact same address → their photos remain stacked at
  every zoom level (no amount of zooming can separate identical coordinates); the
  viewer must still be able to discover and view each of those members individually
  (e.g. not permanently hidden behind whichever photo happens to render on top).
- A season has zero members with a usable address → the map still generates (showing
  an empty/near-empty view) rather than the run failing.
- The interactive map's output folder does not yet exist for a given data directory →
  it is created and excluded from version control before any files are written into
  it.
- A viewer opens the shared folder on a machine with no network access at all → the
  map still fully loads and every interaction still works (Story 3).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a standalone script, run independently of the
  scraper and of the existing static map generator, that produces the interactive map
  (constitution Principle II).
- **FR-002**: The system MUST process every season found under the local data
  directory in a single run, with no CLI option to select a subset of seasons
  (matching the existing map generator's convention).
- **FR-003**: For each season, the system MUST generate one interactive map showing
  every member eligible under the same rules as the existing photo map: a resolvable
  address, and not flagged `excluded` or `ignore`.
- **FR-004**: The system MUST render each eligible member as a circular cropped
  photo — their own photo where one is on file, otherwise the existing fixed
  placeholder image — positioned at their geocoded address, using the same crop and
  placeholder logic as the existing photo map.
- **FR-005**: The system MUST log (not crash on) any member skipped due to a
  missing/unresolvable address, identifying which member, and continue processing the
  rest of the run.
- **FR-006**: The system MUST allow members' photos to visually overlap on the map
  rather than automatically generating separate detail maps or merged/multiplicity
  markers; overlap is expected to be resolved by the viewer zooming and panning
  interactively.
- **FR-007**: The system MUST support zooming via mouse scroll and panning via
  click-and-drag directly on the map.
- **FR-008**: The system MUST provide on-screen buttons for zooming in, zooming out,
  and panning, each producing the same effect as the corresponding mouse gesture.
- **FR-009**: The system MUST show a popup when a member's photo is hovered,
  containing that member's full name, role(s) (primary role and any additional
  roles), number of previous seasons, and job title (see Assumptions for how these
  map to the local record's fields); moving the cursor off the photo MUST close the
  popup.
- **FR-010**: When one of the popup's data points is not on file for a member, the
  system MUST show that field as unknown/omitted rather than leaving it blank in a
  way that looks broken or omitting the rest of the popup.
- **FR-011**: The system MUST render the map's photos over recognizable geographic
  context (matching the existing map generator's approach to orienting the viewer),
  bundled into the output so it remains visible with no network access (see FR-013).
- **FR-012**: The system MUST write the interactive map's output into the local data
  directory identified by the `RKBY_DATA_DIR` environment variable, ensuring that
  location is excluded from version control before writing any files into it, and
  naming the output per season consistently with the existing maps' season-prefix
  convention (constitution Principle I).
- **FR-013**: The generated interactive map MUST be fully self-contained: every
  resource it needs (code, styling, geographic imagery, member photos, and member
  data shown in popups) MUST be bundled inside its own output folder, such that
  opening and fully using the map on another computer requires no network/internet
  access and no additional software beyond a standard, current web browser.
- **FR-014**: The system MUST resolve member addresses to coordinates using the same
  cached-geocoding mechanism as the existing map generator, reusing already-cached
  coordinates and never re-geocoding an address that already has one cached
  (constitution Principle I's geocoding exception).
- **FR-015**: When multiple members share the exact same coordinates, the system MUST
  still allow the viewer to discover and view each individual member's popup, not
  only whichever member's photo happens to render on top.
- **FR-016**: If the interactive map bundles third-party geographic imagery, the
  system MUST comply with that imagery source's usage and attribution requirements,
  consistent with how the existing map generator already attributes its basemap.

### Key Entities

- **Interactive Map Artifact**: The self-contained, shareable output for one season —
  a folder of bundled files that together form a working offline website; independent
  from every other season's artifact.
- **Member Marker**: A member's circular photo (or placeholder) positioned at their
  geocoded address on the map; carries the popup data described in FR-009.
- **Popup Detail**: The name, role(s), previous-season count, and job title shown when
  a marker is hovered (FR-009/FR-010).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A viewer can pan and zoom to inspect any member's photo individually,
  including members who appear stacked together at the default view.
- **SC-002**: A viewer can identify any visible member's name, role(s), previous-season
  count, and job title within one hover, with no click or navigation required.
- **SC-003**: A recipient with no involvement in generating the map can open the
  shared folder on their own computer, with their network connection off, in a
  standard current web browser, and fully use every interaction (pan, zoom, buttons,
  hover popups) — zero installation steps, zero network requests.
- **SC-004**: Every member skipped from the map (missing/unresolvable address) is
  individually identifiable from the run's log output, and no skipped member stops the
  run.
- **SC-005**: An address already resolved by a prior run (by this script or the
  existing map generator) is never sent to an external geocoding lookup again.
- **SC-006**: Re-running the generator after a local data correction produces an
  updated map for that season with no stale data left over from before the
  correction.
- **SC-007**: A member flagged as opted-out (`excluded` or `ignore`) never appears
  anywhere in the shared artifact, including in popup data.
- **SC-008**: Generating the interactive maps for all of this team's current seasons
  (roughly 200 member records total) completes in under 10 minutes on a typical
  laptop.

## Assumptions

- **New, separate script**: Per constitution Principle II, this is a new standalone
  script rather than a mode/flag added to `generate_member_maps.py` — it is a
  different kind of artifact (an interactive bundle vs. static PNGs), even though it
  reuses that script's eligibility rules, photo-crop/placeholder logic, and
  address-geocoding cache.
- **Popup field mapping**: The user's requested popup fields map onto the existing
  local record's fields as follows: "name" = first/last name; "roles" = the
  `additional_roles` list; "job title" = the primary `role` field (e.g. Rider /
  Service Crew / Supporter); "number of previous seasons" = `num_previous_seasons`.
  No separate real-world job-title field exists (or is scraped) in this project — the
  primary participation role is the closest concept the local data has to a "title."
- **Photo-only variant**: The interactive map mirrors the existing *photo* map
  specifically (per "looks very similar to the map with the picturees"); it does not
  also provide a plain-pin interactive variant.
- **One map per season**: Matching the existing map generator's behavior, one
  interactive map artifact is produced per season, and a single run processes every
  season found in the local data directory.
- **No forced non-overlap logic**: Unlike the existing static map generator, this
  feature deliberately does not detect overlaps or generate detail maps/merged
  markers — the user explicitly asked for overlap to be resolved by the viewer's own
  zoom/pan, which is a simpler and sufficient substitute once the map is interactive.
- **Basemap bundling mechanism**: How geographic context imagery is captured and
  bundled offline (e.g. pre-rendered composite images or a small set of cached map
  tiles covering the needed area/zoom range) is a technical decision left to
  planning, the same way the existing map generator's basemap source was. Whatever
  approach is chosen must respect its source's usage/attribution terms (FR-016).
- **No access control on the shared artifact**: Once shared, the folder can be opened
  by anyone who receives it; this feature does not add a password or other access
  restriction. This matches the existing photo map's precedent (already shareable as
  an image) — deciding who receives the folder remains a human/organizational
  decision outside this tool's scope.
- **Browser support**: "Standard, current web browser" means a recent version of a
  mainstream desktop browser (e.g. Chrome, Firefox, Edge, Safari); older or niche
  browsers are out of scope.
