# Feature Specification: PMTiles Basemap for Interactive Map

**Feature Branch**: `004-pmtiles-basemap`

**Created**: 2026-08-18

**Status**: Draft

**Input**: User description: "I want to change the interactive map feature a bit. i
want to use a map in pmtiles format for this. for now: let's not wory about sourcing
the file. i know how to do that and can do that manually, let's add a todo to
generate that automatically."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate the map from a supplied PMTiles basemap (Priority: P1)

As the tool's maintainer, when I run the interactive map generator, I want it to
draw the basemap from a single PMTiles file I've placed locally, instead of the
generator fetching and pre-baking a large custom grid of OpenStreetMap image tiles
on every run, so that generation is simpler, faster, and produces a smaller, less
sprawling output bundle.

**Why this priority**: This is the entire point of the change — without it, nothing
else in this feature has meaning. It replaces the current basemap-baking pipeline,
which downloads OSM tiles and stitches them into thousands of pre-rendered chunk
files, with reading directly from one pre-built map archive.

**Independent Test**: With a valid PMTiles file present at the expected location,
run the generator against a member dataset and confirm the produced interactive map
bundle's basemap comes from that file — no OpenStreetMap tile-fetching traffic
occurs during generation, and the bundle no longer contains the previous large
per-run tile-chunk pyramid.

**Acceptance Scenarios**:

1. **Given** a valid PMTiles basemap file is present at the expected location,
   **When** the maintainer runs the interactive map generator, **Then** the
   generated map bundle renders its basemap using that file and the run makes no
   network requests to an OpenStreetMap tile server.
2. **Given** the same member dataset is regenerated multiple times with the same
   PMTiles file, **When** each run completes, **Then** the basemap output is
   consistent across runs (no per-run re-fetching or re-baking of basemap imagery).

---

### User Story 2 - Fail clearly when the basemap file is missing (Priority: P2)

As the maintainer, if I run the generator before placing the required PMTiles file,
I want a clear, immediate error telling me what's missing and where it's expected,
instead of a broken or partially-generated map bundle.

**Why this priority**: Sourcing the PMTiles file is a manual, out-of-band step (see
Out of Scope). The generator must fail safely and obviously when that prerequisite
hasn't been met, rather than producing a silently broken artifact.

**Independent Test**: Run the generator with no PMTiles file present (or an
unreadable/invalid one) and confirm it stops immediately with an actionable error
message, producing no partial or corrupted output bundle.

**Acceptance Scenarios**:

1. **Given** no PMTiles file exists at the expected location, **When** the
   maintainer runs the generator, **Then** it fails before producing any output,
   with a message identifying the expected file location.
2. **Given** a file exists at the expected location but is not a valid PMTiles
   archive, **When** the maintainer runs the generator, **Then** it fails with a
   clear error rather than producing a broken map.

---

### User Story 3 - Existing map interactions keep working (Priority: P3)

As someone viewing the shared interactive map, I want panning, zooming, member
photo popups, season selection, and mobile mode to keep working exactly as they do
today, so that switching the basemap technology underneath is invisible to me.

**Why this priority**: This is a regression guard, not new value — it confirms the
basemap swap doesn't disturb the interactive-map capabilities already delivered in
the prior feature (photo popups, multi-season merge, mobile drawer, zoom/pan
controls).

**Independent Test**: Open a map generated under this feature and exercise each
existing interaction (scroll/button zoom, drag pan, hover/tap popups, season
switching, mobile-mode toggle) and confirm each behaves as it did before this
change.

**Acceptance Scenarios**:

1. **Given** a map generated with the new basemap, **When** a viewer pans and zooms
   using both gestures and on-screen controls, **Then** the map responds as before
   and the basemap stays visible and legible at every zoom level the archive
   supports.
2. **Given** a map generated with the new basemap, **When** a viewer hovers (desktop)
   or taps (mobile) a member's photo, **Then** the existing popup/drawer with name,
   roles, seasons, and job title still appears as specified in the interactive photo
   map feature.

### User Story 4 - Optionally load the basemap from a maintainer-hosted URL instead of embedding it (Priority: P4)

As the maintainer, I want the option to point a generated map bundle at a PMTiles
basemap URL I've published myself, instead of embedding the whole archive in the
bundle, so that viewers get a smaller, faster-loading bundle when I'm willing to
host the (non-member-data) basemap file somewhere — while member data still never
leaves local generation.

**Why this priority**: Purely additive to Story 1's default behavior — the
embedded, fully offline build remains the default and must keep working
unmodified. This story only adds a second, opt-in build variant; nothing else
depends on it.

**Independent Test**: Set the hosted-basemap option to a URL serving a valid
PMTiles archive, run the generator, and confirm the resulting bundle's basemap
requests go only to that URL at view time (never embedding the archive), while
every member-data field (photos, positions, names, roles) still ships local-only,
exactly as in the default build.

**Acceptance Scenarios**:

1. **Given** the maintainer has not set a hosted-basemap URL, **When** they run the
   generator, **Then** the bundle behaves exactly as in Story 1 — basemap fully
   embedded, zero network requests at view time.
2. **Given** the maintainer has set a hosted-basemap URL pointing at a real,
   reachable PMTiles archive, **When** they run the generator and a viewer opens
   the resulting bundle with network access, **Then** the basemap loads by
   fetching tiles from that URL, and the bundle contains no embedded copy of the
   archive.
3. **Given** hosted mode is selected, **When** the bundle is generated, **Then**
   no member data (photos, positions, names, roles, seasons) is ever sent to the
   hosted URL or any other network endpoint — only basemap tile requests go there,
   and only from the viewer's browser, never from the generator itself.

### Edge Cases

- What happens when a viewer zooms in past the deepest zoom level available in the
  supplied PMTiles archive? The map should stay usable (e.g. remain at the deepest
  available detail) rather than showing a blank area.
- What happens when the PMTiles file's covered area doesn't fully include every
  member's plotted position? Positions outside the archive's coverage should not
  crash generation; the affected area of the basemap may simply render blank
  underneath those markers.
- What happens if the PMTiles file is replaced with a different one between runs
  (different coverage area or zoom range)? The next generation run should pick up
  the new file's coverage without manual cleanup of stale basemap output from the
  previous file.
- What happens in hosted mode (Story 4) if the hosted URL is unreachable or serves
  something invalid when a viewer opens the map? The basemap fails to render (the
  rest of the map — member markers, popups, season controls — still works), rather
  than the generator being able to detect or prevent a hosting problem it has no
  visibility into at generation time.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The interactive map generator MUST render the map's basemap from a
  single, maintainer-supplied local PMTiles archive file, instead of fetching and
  pre-baking OpenStreetMap raster tiles at generation time.
- **FR-002**: The generator MUST NOT make network requests to an OpenStreetMap tile
  server, or any other basemap tile service, at generation time.
- **FR-003**: If the expected PMTiles file is missing, unreadable, or not a valid
  PMTiles archive, the generator MUST fail before producing output, with an error
  that identifies the expected file location.
- **FR-004**: By default, the generated interactive map bundle MUST remain a fully
  self-contained, offline-viewable standalone folder — the basemap data needed to
  render the map MUST be bundled with the output, not fetched from the network when
  someone views the map. (Story 4's opt-in hosted mode is the sole exception, scoped
  by FR-008–FR-011 below; every other artifact this feature produces stays fully
  local unconditionally.)
- **FR-005**: The rendered basemap MUST support panning and zooming across the full
  zoom range available in the supplied PMTiles archive.
- **FR-006**: All existing interactive-map capabilities unrelated to the basemap
  source — hover/tap member popups, multi-season selection and merge, mobile-mode
  auto-detection and switching, zoom/pan controls — MUST continue to work
  unchanged.
- **FR-007**: Automatically sourcing or generating the PMTiles basemap file itself
  is explicitly out of scope for this feature (see Out of Scope); the generator
  MUST treat the file as an existing local input it does not create.
- **FR-008**: The generator MUST support an explicit, opt-in hosted-basemap mode
  (Story 4), selected by the maintainer at generation time (e.g. an environment
  variable naming a URL), in which the generated bundle loads basemap tiles from
  that URL at view time instead of embedding the archive. Absent this opt-in, the
  generator MUST produce the default embedded bundle (FR-004).
- **FR-009**: Publishing the PMTiles file to the URL used in hosted mode is a
  manual step the maintainer performs themselves, outside this generator, the same
  way sourcing the file itself already is (FR-007). The generator MUST NOT upload,
  deploy, or otherwise manage remote hosting infrastructure — it only accepts a URL
  and, in hosted mode, tells the bundle to use it.
- **FR-010**: The local PMTiles file (FR-001/FR-003's validation) is still required
  and validated in hosted mode exactly as in the default mode — hosted mode changes
  only whether the archive is embedded or referenced by URL in the output, never
  whether it must exist and be valid locally first.
- **FR-011**: In hosted mode, member data (photos, names, positions, roles,
  seasons) MUST continue to ship local-only within the generated bundle exactly as
  in the default mode (Constitution Principle I) — hosting applies solely to the
  basemap tile archive, which contains no member data.

### Key Entities

- **PMTiles Basemap File**: A single local file, supplied manually by the
  maintainer ahead of running the generator, containing pre-built map tile data for
  the geographic area and zoom range the map needs. Replaces the previous per-run,
  generator-built grid of raster basemap tile-chunk files as the map's basemap
  source.

## Out of Scope

- **Automated sourcing/generation of the PMTiles file**: building or downloading
  the PMTiles basemap archive itself (e.g. extracting it from a larger source
  dataset, running a tile-build pipeline) is not part of this feature. The
  maintainer produces and places the file manually. **TODO (future feature):**
  automate sourcing/generating this PMTiles file as part of the pipeline, so a
  maintainer no longer has to produce it out of band.
- **Automated hosting/deployment of the PMTiles file** (Story 4/FR-009): choosing
  a hosting provider, provisioning it, or uploading the file there is not part of
  this feature. The generator only accepts a URL the maintainer already has a
  file published at; how that URL came to serve the file — and whether that host
  satisfies what an HTTP-range-addressable, CORS-permissive static file host needs
  to — is the maintainer's own concern, not something this feature configures,
  verifies, or automates. **TODO (possible future feature):** a guided or
  automated deploy step, if this turns out to be a recurring manual chore.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Generating the interactive map makes zero network requests to an
  OpenStreetMap (or other) basemap tile server, for any member dataset.
- **SC-002**: The generated map bundle's basemap is stored as a small, constant
  number of files, regardless of how geographically spread out the member data is
  — replacing the previous behavior where basemap output scaled up to thousands of
  files for widely spread data.
- **SC-003**: A maintainer who runs the generator without the required PMTiles file
  in place sees a clear failure identifying the missing file within seconds, before
  any other generation work happens.
- **SC-004**: Viewers of a generated map can pan and zoom smoothly across the
  entire area and zoom range the supplied PMTiles file covers, with no loss of the
  existing photo-popup, season-selection, or mobile-mode functionality.
- **SC-005**: In hosted mode, inspecting the network requests a generated bundle
  makes while viewed shows requests only to the maintainer-configured basemap URL
  (for basemap tiles) — never a request containing any member field (name, photo,
  position, role, season), and never an embedded copy of the archive in the
  bundle's own files.

## Assumptions

- The maintainer supplies one PMTiles file covering the geographic area and zoom
  range needed for the map, placed at a documented location before running the
  generator; a sample file has already been provided for development purposes.
- This feature fully replaces the existing OpenStreetMap tile-fetch-and-bake
  basemap pipeline; it is not kept as a fallback alongside the PMTiles path.
- Automatically sourcing or generating the PMTiles file is deliberately deferred to
  a future feature (see Out of Scope / FR-007), not designed for in this pass.
- The interactive map's other capabilities (member popups, season merge, mobile
  mode, offline standalone bundling) are unchanged in behavior; only how the
  basemap imagery is produced and rendered changes.
- Hosted mode (Story 4) is opt-in and additive: the maintainer decides per
  generation run whether to embed or reference a hosted URL; nothing about the
  default embedded build's behavior, contract, or guarantees changes because
  hosted mode exists.
- A host the maintainer chooses for hosted mode is assumed capable of serving a
  static file over HTTP range requests with a permissive CORS policy — standard
  behavior for common static-file hosts/CDNs, and the maintainer's own
  responsibility to confirm (FR-009); the generator does not detect or validate
  hosting-target capability.
