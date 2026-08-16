# Feature Specification: Member Map Generator

**Feature Branch**: `002-map-generator`

**Created**: 2026-08-16

**Status**: Draft

**Input**: User description: "data acquisition works well. let's move on to the map
generator. i want: a png file showing dots/pins with the members addresses. if a
member has no address, log it, and move on. we should also create a map variant that
shows the member photos. these shall be round circles, with the photo, centered on
the address. I think we can crop the photos in the same way the website does in the
table, that seems to work well. i dont want the script to have any switches. just
generate everything for each season. this is a separately called script. the maps
shall be placed inside the same data directory where the people's data is, use the
env var we have already. put it at a folder on top level, flat structure. gitignore
that folder. prefix each file with the season name format like "2025_26_...". the
script should identify clusters of people (for instance, 2 people in Verden). in that
case, it should create additional detail maps. there should be a configurable (via cli
arg, use 50km as default minimium map size, which is a kilometer value that determines
the minimum covered width of the map. i want to color code pins for the three roles we
have. think of some neutral colors. no legend on the map needed. i want a ratio marker
on the maps though (bottom right). i mean the ruler like thing that shows how wide a
1km etc. projection on the map is. add a cli switch to turn that off (enabled by
default). the criterium for adding a clustered map: if pins or the circles of at least
2 people would overlap => add cluster where that wont happen. again: lower bound is
the limit we discussed earlier. there shall always be an overview map. if there would
be overlaps: show the people next to each other for the maps with the faces, and for
the pins variant show one pin in the center between the overlapping elements, with a
mulitplicity circle and the number of people. there is an obvious corner case: 2
people living at the same address. in that case, dont even try to create a cluster
only for these 2."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See where everyone lives on a pin map (Priority: P1)

As a team organizer, I want a single image per season showing a pin for every member
with a known address, so I can see at a glance who lives near whom and identify
possible neighbors or training partners.

**Why this priority**: This is the core value of the whole feature — a visual
overview of the team's geography — and is useful on its own even before any of the
richer variants exist.

**Independent Test**: Run the map generator against a season's local data folder and
confirm a single overview PNG is produced with one pin per member who has a
geocodable address, correctly color-coded by role, with a scale indicator in the
bottom-right corner.

**Acceptance Scenarios**:

1. **Given** a season folder containing members with valid addresses across several
   roles, **When** the map generator runs, **Then** it produces one overview pin-map
   PNG for that season, prefixed with the season label, with each member's pin colored
   according to their role and a scale bar shown in the bottom-right corner.
2. **Given** a member record with no address on file, **When** the map generator
   runs, **Then** that member is logged as skipped (with enough detail to identify who
   was skipped) and the run continues to completion for everyone else.
3. **Given** the map generator is run again after local data changed, **When** it
   completes, **Then** the previous overview PNG for that season is replaced with a
   freshly generated one reflecting the current data.

---

### User Story 2 - See everyone's face on a photo map (Priority: P2)

As a team organizer, I want a second map variant that shows each member's photo (as a
small circular portrait) at their address instead of a plain pin, so returning and new
members can visually recognize each other and connect names/faces to places.

**Why this priority**: Builds directly on Story 1's geocoding and layout logic, adding
recognizability, which is the specific "help old and new members connect" goal from
the project's purpose — but the plain pin map already delivers value without it.

**Independent Test**: Run the map generator and confirm a second overview PNG is
produced per season where each geocoded member is rendered as a circular, cropped
photo centered on their address instead of a colored pin.

**Acceptance Scenarios**:

1. **Given** a season folder containing members with addresses and photos on file,
   **When** the map generator runs, **Then** it produces one overview photo-map PNG
   for that season with each member shown as a circular cropped photo centered on
   their address.
2. **Given** a member has a valid address but no photo on file, **When** the map
   generator runs, **Then** that member still appears on the photo map, shown with a
   fixed placeholder image (the team mascot) in place of a personal photo, and the run
   continues.

---

### User Story 3 - Zoom into crowded areas with detail maps (Priority: P3)

As a team organizer, I want additional close-up maps automatically generated for any
area where members' markers are packed too closely to tell apart on the overview map,
so I don't lose information about who exactly lives in a crowded town just because the
overview is zoomed out.

**Why this priority**: This refines the two overview maps from Stories 1 and 2; it's
valuable but the overview maps already stand on their own without it.

**Independent Test**: Run the map generator against a data set that includes a known
cluster (e.g., three members in the same town whose markers would overlap on the
overview) and confirm additional detail-map PNGs are produced, zoomed in enough that
the cluster's members are individually distinguishable, while the overview map still
shows a readable stand-in for the whole cluster.

**Acceptance Scenarios**:

1. **Given** three or more members whose markers would overlap at the overview map's
   scale, **When** the map generator runs, **Then** it additionally produces a detail
   map (per variant) zoomed in on that group, wide enough to respect the configured
   minimum map width, and no longer showing overlap between those members' markers.
2. **Given** exactly two members whose markers would overlap at the overview scale and
   who share the exact same address, **When** the map generator runs, **Then** no
   detail map is generated for that pair — they are rendered directly on whichever map
   they appear on using the overlap fallback (merged multiplicity pin, or side-by-side
   photos).
3. **Given** an overlap remains even at the configured minimum map width (e.g., a pair
   sharing one address within a larger cluster), **When** the map generator renders
   that map, **Then** the pin variant shows one merged pin at the shared position with
   a multiplicity badge showing the count, and the photo variant shows the affected
   members' circular photos offset next to each other instead of stacked.

---

### Edge Cases

- A member has no address on file → logged, excluded from both map variants, run
  continues (Story 1 AC2).
- A member has an address but no photo on file → still included on the photo variant,
  shown with the fixed placeholder image instead of a personal photo (Story 2 AC2).
- A member's address exists but cannot be resolved to a geographic location → treated
  the same as "no address": logged and skipped, run continues.
- A member is marked `excluded` (declined participation) or `ignore` in their local
  record → left out of every map, consistent with supporting an opt-out (constitution
  Principle I).
- Two or more members share the exact same address → they always overlap regardless of
  zoom; never spawn a detail map for a group that is *only* that shared-address set
  (zooming in further cannot separate them) — render them with the overlap fallback
  wherever they appear.
- A cluster is large enough that even a detail map at the configured minimum width
  still has internal overlaps → those specific overlapping members use the fallback
  rendering (merged pin / offset photos) on that detail map; the generator does not
  recurse into further detail maps.
- A season folder exists but has zero members with usable addresses → an overview map
  is still produced if reasonably possible showing an empty/near-empty result is
  acceptable, and the run logs that nothing could be plotted rather than failing.
- The output maps folder does not yet exist for a given data directory → the generator
  creates it and ensures it is excluded from version control before writing any files
  into it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a standalone script, run independently of the
  scraper, that generates map images from the locally stored season data (constitution
  Principle II).
- **FR-002**: The system MUST process every season found under the local data
  directory in a single run, with no CLI option to select a subset of seasons.
- **FR-003**: For each season, the system MUST generate an overview pin-map PNG
  showing one marker per member who has a resolvable address, excluding members
  flagged `excluded` or `ignore` in their local record.
- **FR-004**: For each season, the system MUST generate an overview photo-map PNG
  showing every resolvable member (same eligibility rules as FR-003) as a circular
  cropped portrait centered on their address — their own photo where one is on file,
  otherwise the fixed placeholder image from FR-020.
- **FR-005**: The system MUST crop member photos to a circular portrait using a
  centered square crop of the source image (matching the existing intranet table
  presentation), before placing it on the photo-map variant.
- **FR-006**: The system MUST log (not crash on) any member skipped from a map variant
  due to a missing/unresolvable address, identifying which member and which variant
  they were skipped from, and continue processing the rest of the run. A missing photo
  is not a skip (see FR-004/FR-020) and is not logged as one.
- **FR-007**: The system MUST color-code pins on the pin-map variant by the member's
  role (read from the member's local record — see Assumptions), using a fixed,
  visually distinct, low-saturation ("neutral") color per role, plus one additional
  neutral color for members with no recognized role, with no legend rendered on the
  map image itself.
- **FR-008**: The system MUST render a scale indicator (a ruler-style bar showing
  real-world distance, e.g. 1 km) in the bottom-right corner of every generated map by
  default.
- **FR-009**: The system MUST provide a CLI switch to disable the scale indicator
  (FR-008); the indicator is shown unless this switch is used.
- **FR-010**: The system MUST provide a CLI argument for the minimum map width in
  kilometers (the minimum real-world distance the map's shorter/covered dimension must
  represent), defaulting to 50 km, applied as a lower bound to every generated map
  (overview and detail).
- **FR-011**: The system MUST detect, per season and per map, groups of two or more
  members whose markers (pins or photo circles) would visually overlap at that map's
  rendered scale.
- **FR-012**: For every detected overlap group that is not exactly two members sharing
  the identical address (see FR-014), the system MUST generate an additional detail
  map (per variant) zoomed in enough to resolve that overlap, while still respecting
  the FR-010 minimum width.
- **FR-013**: On any map where an overlap cannot be resolved by zooming (i.e. persists
  at the FR-010 minimum width, such as members sharing one exact address), the system
  MUST fall back to: a single merged pin with a multiplicity badge showing the member
  count for the pin variant, and members' circular photos offset to sit next to each
  other (not stacked) for the photo variant.
- **FR-014**: The system MUST NOT generate a detail map for an overlap group that
  consists of exactly two members sharing the identical address — such a pair is
  always rendered via the FR-013 fallback wherever it appears, never given its own
  detail map.
- **FR-015**: The system MUST write all generated map images into one flat,
  non-nested folder at the top level of the local data directory (identified by the
  existing `RKBY_DATA_DIR` environment variable), with no per-season subfolders.
- **FR-016**: The system MUST prefix every generated map filename with the season
  label in `YYYY_YY` underscore form (e.g. `2025_26_...`), derived from that season's
  hyphenated folder name (e.g. `2025-26`).
- **FR-017**: The system MUST ensure the top-level maps output folder (FR-015) is
  excluded from version control within the local data directory's own git repository,
  creating or updating that repository's ignore rules if needed, before writing any
  map files (constitution Principle I).
- **FR-018**: The system MUST NOT expose any CLI switches beyond the two named in
  FR-009 and FR-010 — no season selector, no variant selector, no other toggles.
- **FR-019**: The system MUST resolve a member's address to map coordinates via an
  online geocoding lookup at most once per address, caching the resolved coordinates
  back into that member's local data record so subsequent runs reuse the cached value
  instead of re-querying the geocoding service.
- **FR-020**: On the photo-map variant, for a resolvable member with no photo on file,
  the system MUST render a fixed placeholder image (the Team Rynkeby mascot, shipped as
  a project asset) in place of a personal photo, cropped the same way as FR-005, so
  every resolvable member appears on the photo map regardless of whether they have a
  photo on file.
- **FR-021**: Once a detail map's rendered area (FR-012) is determined, the system MUST
  render every other resolvable member of that season/variant whose marker position
  falls within that area — not just the overlap group that triggered the map — since
  the FR-010 minimum width commonly makes a detail map's covered area wider than the
  triggering group alone. A member whose marker would fall within a small margin of the
  map's own edge MUST instead be omitted from that specific detail map rather than
  rendered clipped or crowded against the border; they remain visible on the overview
  (and any detail map whose area does comfortably contain them).

### Key Entities

- **Member Location**: A member's address resolved to geographic coordinates for
  plotting; derived from the member's local record, not separately persisted unless
  needed for caching (see Assumptions).
- **Role**: One of the team's three participation roles (Rider, Service Crew,
  Supporter), used only to pick a pin's color on the pin-map variant. Assumed to
  already exist on each member's local record (see Assumptions); adding it is out of
  scope for this feature.
- **Map**: A single generated PNG — either an overview (one per season per variant) or
  a detail map (one per unresolved cluster per season per variant) — covering a
  specific geographic area at a specific scale.
- **Overlap Group / Cluster**: A set of two or more members whose map markers would
  visually overlap at a given map's scale; drives whether a detail map is generated
  (FR-012) and whether fallback rendering applies (FR-013).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running the map generator once produces a complete set of overview maps
  (both variants) for every season present in the local data directory, with no manual
  steps in between.
- **SC-002**: Every member skipped from a map (missing or unresolvable address) is
  individually identifiable from the run's log output, with zero skipped members
  causing the run to stop early. A missing photo never causes a skip (FR-020).
- **SC-003**: On every generated map, no two distinct members' markers visually
  overlap — each is either spatially separated, resolved onto its own detail map, or
  shown via the multiplicity/offset fallback.
- **SC-004**: A viewer with no access to the underlying data can read the real-world
  distance between two members' markers on any map using only the on-map scale
  indicator (when enabled).
- **SC-005**: A full run across all of this team's current seasons (roughly 200 member
  records total, in the low hundreds) completes in under 5 minutes on a typical laptop.
- **SC-006**: Re-running the generator after only correcting a couple of local member
  records regenerates a map set that reflects those corrections, with previously
  generated files for that season fully replaced (no stale markers left over from
  before the correction).
- **SC-007**: An address that has already been successfully resolved once is never
  sent to an external geocoding lookup again on subsequent runs.

## Assumptions

- **Eligibility filtering**: Members flagged `excluded` (declined participation) or
  `ignore` (manually excluded) in their local record are left off every map, matching
  the constitution's requirement to support excluding an opted-out member.
- **Photo crop shape**: "Crop the same way the website does in the table" is
  interpreted as a centered square crop of the source photo, then masked to a circle —
  matching a typical avatar/thumbnail presentation.
- **Cluster/overlap definition**: "Overlap" is evaluated purely from each map's
  rendered scale and each marker's on-image footprint (pin size or photo-circle
  diameter) — i.e., two members overlap on a given map if their geographic distance,
  projected at that map's scale, is smaller than the combined radius of their two
  markers. This is the single criterion driving both detail-map creation (FR-012) and
  the fallback rendering (FR-013), and it naturally terminates recursion since the
  minimum map width (FR-010) puts a floor on how far zooming in can shrink an overlap.
- **Detail map framing**: A detail map is centered on the overlapping group and sized
  to the smallest width that both resolves the overlap and respects the FR-010 minimum
  width; if the minimum width itself is too wide to resolve the overlap, FR-013's
  fallback rendering applies instead of an ever-tighter detail map. Whoever else falls
  inside that resulting area is drawn on the map too (FR-021), since the minimum width
  floor routinely makes the area wider than the group that triggered it.
- **Detail map file naming**: Detail map filenames additionally include a
  location-derived identifier (e.g., the resolved place name) after the season prefix,
  so multiple detail maps in one season run don't collide, e.g.
  `2025_26_detail_pins_verden.png`.
- **Role field**: A `role` field (Rider / Service Crew / Supporter) is assumed to
  already exist on each member's local record by the time this feature is built — it
  does not exist in the local data today, and adding it is explicitly out of scope
  here, tracked separately. A member whose `role` is unset/unrecognized is rendered
  with a 4th neutral "unassigned" pin color rather than being excluded.
- **Geocoding approach**: Addresses are resolved to coordinates via an online
  geocoding service (e.g. a Nominatim-style OpenStreetMap lookup), consistent with
  common practice for this kind of non-commercial hobby project. Each address is only
  ever geocoded once: the resolved coordinates are cached back into the member's local
  data record, so re-running the generator never re-sends an address that already has
  cached coordinates. This is the one deliberate, documented exception to Principle
  I's "no third-party upload" rule — scoped narrowly to address text only (never
  name, photo, phone, or birthday), one-time per address, cached locally afterward.
- **Idempotent output**: Every run fully regenerates and overwrites the flat maps
  folder's contents for the seasons it processes; there is no versioning or
  archiving of previous map runs.
- **Map geographic context**: Maps show enough real-world geographic context (e.g.
  place names, borders, or roads) for a reader to orient themselves — not just bare
  pins on a blank background — since that context is necessary to satisfy "see who
  might be a neighbor." The exact basemap source is a technical decision left to
  planning, chosen to avoid transmitting any member-identifying data (names, photos,
  exact addresses) to a third party — only the map's geographic bounding box is
  needed to fetch background context, which is not personal data.
- **Empty/degenerate seasons**: A season with no geocodable members still produces a
  (near-)empty overview map rather than being skipped outright, so the output set is
  predictable across seasons.
