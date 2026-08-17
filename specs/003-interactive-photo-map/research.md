# Phase 0 Research: Interactive Photo Map

Every decision below resolves a NEEDS CLARIFICATION from Technical Context or a
genuine "how do we actually build this" question the spec's Assumptions section
deliberately left to planning. Builds on `specs/002-map-generator`'s established
patterns (`scripts/rkby_maps/`, `scripts/rkby_records.py`) — only the delta specific
to this feature is worked out in full here.

## 1. Overall architecture: a small offline SPA, built fresh by the Python script

**Decision**: A two-part deliverable. (a) `frontend/interactive-map/` — a small
Vite + Vitest + Leaflet single-page app, source-controlled under
`frontend/interactive-map/src/`, `package.json`, `pnpm-lock.yaml`. Its build output
(`dist/`) is **not** committed — it's `.gitignore`d, same treatment as
`node_modules/`. (b) `scripts/generate_interactive_map.py` — a Python script that,
every run, first builds the frontend itself (`pnpm install --frozen-lockfile` then
`pnpm run build` inside `frontend/interactive-map/`, via `subprocess`), then
merges/geocodes/bundles data exactly like `generate_member_maps.py` does today, and
finally copies the fresh `dist/` output plus the per-run binaries (photos, basemap
image, generated `map-data.js`) straight into
`<RKBY_DATA_DIR>/interactive_map/` — itself already gitignored (data-model.md §
Local Data Repository), so the built artifact never risks landing in *this* repo's
git history either.

**Rationale**: User-directed (explicitly preferred over committing a pre-built
`dist/`: "the script runs pnpm install and build and place the artifact to the
output folder... would work for me"). Building fresh every run guarantees the
shipped bundle always matches `frontend/interactive-map/src/` — there's no way for
a contributor to forget to rebuild before committing, because nothing built is ever
committed. The trade-off, accepted explicitly: `generate_interactive_map.py` now
needs Node.js + pnpm on the maintainer's machine to run at all, not only to develop
the frontend — a real, if small, new tooling requirement for this one script,
documented as a Complexity Tracking entry in plan.md rather than silently assumed
away. `--frozen-lockfile` keeps installs reproducible (fails loudly on a
lockfile/`package.json` mismatch rather than silently drifting) and, once pnpm's
local content-addressable store is warm after the first run, both `install` and
`build` are fast (low single-digit seconds), comfortably inside SC-011's 15-minute
budget.

**Alternatives considered**: Committing a pre-built `dist/` to git, script never
touches Node (the original plan for this feature) — superseded by explicit user
direction; the risk of a silently-stale committed bundle after a forgotten rebuild
was the deciding factor against it. Hand-rolled vanilla JS with manually vendored
Leaflet files and no build step — rejected once the user asked for Vite/Vitest
(§5–§7's pure logic would otherwise have no test coverage, a real gap against
Principle V).

## 2. Basemap imagery: why not a bundled OSM tile pyramid

**Decision**: Do **not** bundle raw OpenStreetMap raster tiles for a Leaflet
`TileLayer` (i.e. no offline/interactive multi-zoom tile pyramid served from
`tile.openstreetmap.org` imagery). Instead, reuse `scripts/rkby_maps/basemap.py`'s
existing `zoom_for_bounding_box` + `stitch_basemap` exactly as `generate_member_maps.py`
already does, to fetch-once and flatten a **single large composite raster image**
covering the bounding box of every merged member's position across all seasons —
then display *that one image* in the browser via Leaflet's `L.CRS.Simple` +
`L.imageOverlay`, which gives native scroll-zoom/drag-pan over a plain picture with
no further tile requests, ever.

**Rationale**: OSM's tile usage policy (`operations.osmfoundation.org/policies/tiles/`)
explicitly prohibits exactly the pattern this feature would otherwise need:
*"pre-seeding large areas or multiple zoom levels in advance," "building tile
archives... for later distribution,"* and states plainly *"Offline use is not
permitted on tile.openstreetmap.org"* — enforcement is "blocked without notice."
`generate_member_maps.py`'s existing OSM use is compliant because it only ever
fetches the exact tiles for the *one* map it's about to render, then keeps the
already-cached tiles for next time (research.md §2 there) — it never repackages the
raw tiles themselves for someone else to pan/zoom through offline. This feature's
core ask (scroll-zoom, drag-pan, shareable folder, works with no network) is
*precisely* the "offline map" pattern the policy calls out — so satisfying it with
real OSM tiles would violate the policy regardless of how narrow the bounding box
or zoom range is. A single flattened image sidesteps this entirely: it's fetched
once (same "fetch what you're about to render" pattern already established as
compliant), then the raw tiles are discarded — what ships is a derivative picture,
not a re-servable OSM tile set, the same distinction that already lets the existing
*static* photo map be freely shared. Attribution stays required regardless (§8).

This does mean the basemap's own pixel detail has a ceiling — zooming far enough in
shows a magnified, eventually-blurry version of the same picture, rather than ever
finer real street-level tiles. That's an acceptable, explicitly-scoped trade-off:
FR-012's actual requirement is that overlapping *member markers* separate on zoom,
and markers are independent DOM elements positioned by real projected coordinates
(§4) — they separate with full precision regardless of the backing image's
sharpness. General geographic orientation (FR-017) is what the image needs to
provide, not infinite cartographic detail.

**Alternatives considered**: A commercial/self-hosted vector or raster tile
provider that explicitly permits offline bundling (e.g. MapTiler, Stadia Maps) —
rejected for the same reason 002 rejected a commercial tile provider: signup/API-key
friction and an ongoing external account dependency disproportionate to a small
volunteer tool (Constitution IV). Self-hosting a tile server — rejected outright,
"heavier dependencies (databases, web servers...) require explicit justification,"
and this project has none of that infrastructure today. A bundled simplified vector
basemap (country/state outlines only, no imagery) — rejected as a worse visual match
to "looks very similar to the map with the pictures," which already uses real OSM
raster imagery; the flattened-composite-image approach preserves that look exactly
while staying compliant.

### Addendum: a few extra flattened resolution levels (post-launch perf/UX fix)

**Superseded by the 2nd addendum below** — kept for the historical record of how this
started. `src/basemapLevel.js` and the single-flattened-image-per-level design it
describes no longer exist in the code; see the 2nd addendum for why and what replaced
them.

**Decision**: On top of the base flattened image above, `bundle.py` now bakes up to
two more flattened rasters of the *exact same* bounding box (`BASEMAP_LEVELS = (1, 2,
4)`) at correspondingly higher OSM zoom/canvas size, so the basemap looks sharper once
a viewer zooms in past the base level. `src/basemapLevel.js` swaps which raster backs
the Leaflet `imageOverlay` based on the current zoom; bounds and every precomputed
marker `x`/`y` stay unchanged across levels since all of them cover the identical
geographic area, just at higher pixel density.

**Rationale**: User-directed follow-up ("we need to change map resolution when
zooming in/out"), explicitly choosing this over two more-conservative options offered
(bump the single base image's own resolution/quality; or a live OSM `TileLayer`) after
being shown the trade-off below.

**Compliance note, read together with the policy discussion above**: each level is
still fetched once and immediately flattened into a plain raster, never re-served as
raw OSM tiles — the same distinction the base design leans on. But baking *more than
one* such level is closer to the tile usage policy's literal "pre-seeding large areas
or **multiple zoom levels** in advance" language than the original single-image
decision was. This was surfaced to and accepted by the user as a real, if small,
compliance-risk trade-off — not a novel exemption discovered here. `BASEMAP_LEVELS`
is deliberately short (3 levels, powers of two only) rather than an arbitrary tile
pyramid, and `MAX_OSM_ZOOM`-capping (`bundle.py._basemap_levels`) skips levels a
bounding box has no genuine extra detail for, so a tightly-clustered member set never
bakes redundant duplicate rasters.

### 2nd addendum: chunked tiling instead of swapping whole images (post-launch fix)

**Decision**: The 1st addendum's "one flattened image per level, swapped on zoom"
design didn't scale to more resolution levels — a full 16x-scale image would be
~1.1 gigapixels (~3.3GB uncompressed in memory just to stitch it, before even saving
a likely-hundreds-of-MB file). Two more levels were added (`BASEMAP_LEVELS = (1, 2, 4,
8, 16)`), but every level beyond the base is now written as a `cols` x `rows` grid of
small `TILE_PX` (256px) chunk files — `interactive_map/tiles/<scale>/<x>_<y>.jpg` —
instead of one image. The base (1x) level is unchanged: one small flattened
`basemap.jpg`, always shown via a plain `L.imageOverlay` at every zoom. A custom
Leaflet `GridLayer` (`src/basemapTiles.js`'s pure grid math, wired up in `src/main.js`)
sits on top of it, active only across the zoom range the tiled levels cover, and
requests only the chunks intersecting the current viewport — never the whole level at
once, however deep the zoom goes.

**Rationale**: User-directed follow-up ("i would like to not have all tiles in the
page at same time... cant we just save the tiles and show the ones that are needed?"),
after being shown the 1.1-gigapixel/3.3GB number for what "2 more levels" would mean
under the old swap-one-whole-image design. Leaflet's `GridLayer` already implements
exactly this — viewport-based tile loading/unloading — so this reuses well-trodden
Leaflet behavior (`options.minZoom`/`maxZoom` hiding the layer outside its baked
range) rather than hand-rolling a loading scheme; `createTile` is the only override
needed, backed by `basemapTiles.js`'s three pure helpers (unit-tested without a
browser: which level a zoom maps to, whether a chunk coordinate was actually baked,
and the chunk's URL).

**Compliance note, read together with the two discussions above**: a chunk is still a
cropped/re-encoded composite of the underlying OSM source tile(s) in the general case
— the same "derived picture" distinction §2 and the 1st addendum lean on — but because
`TILE_PX` (256px) matches OSM's own native tile size, a chunk that happens to land
exactly on a tile boundary is close to indistinguishable from that one source tile
passed through unmodified. This is a materially thinner version of the same argument
than the 1st addendum's, on top of an already-accepted trade-off; presented plainly to
the user as such rather than asserted as clean compliance.

**Known cost, called out explicitly rather than left implicit**: chunking fixes the
in-browser problem (no single request or in-memory image ever covers a whole
high-resolution level) but does **not** reduce the total OSM tile-fetch volume,
generation time, or disk space needed to pre-bake full offline coverage at every
level — every possible chunk across the whole bounding box still has to be generated
up front, since there's no live tile server at view time to fetch the rest of the
world lazily from. Rough chunk counts at `CANVAS_SIZE = (2400, 1800)`: 1x has no
chunks (single image); 2x ≈ 285; 4x ≈ 1100; 8x ≈ 4275; 16x ≈ 16950 — roughly summing to
~22,600 chunk files for one full run, most of it from the 16x level alone. The
underlying OSM tile *download* volume doesn't multiply on top of that (adjacent chunks
reuse the same cached OSM tiles via `fetch_tile`'s on-disk cache, same total bytes as
before, just chopped into more output files) — but the sheer number of small
PIL crop/save calls is real added generation-time and disk-usage cost per run, on top
of `.tile_cache/`'s existing warm-cache benefit. Not re-scoped down in response to
this — the user's ask was specifically "more detail, and don't load it all at once,"
which chunking delivers — but worth revisiting `BASEMAP_LEVELS`/`TILE_PX` if
generation time against SC-011's budget or `interactive_map/`'s on-disk size becomes a
real problem in practice.

### 3rd addendum: dropped the 16x level, 8x is now the deepest baked level (post-launch fix)

**Decision**: `BASEMAP_LEVELS` is now `(1, 2, 4, 8)` — the 16x level from the 2nd
addendum is gone. Zooming in past 8x (the deepest baked level) no longer hides the
tile layer; `src/main.js` sets the `GridLayer`'s `maxNativeZoom` to 8x's zoom instead
of its `maxZoom` (which is now the map's own `maxZoom`), so Leaflet's built-in
GridLayer overzoom behavior keeps reusing and auto-scaling the already-fetched 8x
chunks for every zoom level beyond it, rather than requesting a level that was never
generated.

**Rationale**: User-directed follow-up ("the 16x tiles appear to never load" ... "the
16x is not manageable anyway... let's keep the 8 folder as the most zoomed in
resolution. and keep showing them as we keep zooming in"). Two separate problems, one
fix each: (1) the 16x level was ~16950 of the ~22,600 chunks a full run generated (2nd
addendum's own numbers) for the least-visited zoom level — dropped as not worth its
share of generation time/disk space, matching the "worth revisiting `BASEMAP_LEVELS`"
note the 2nd addendum already flagged. (2) Independently, the tile layer's own
`maxZoom` option (previously set to the deepest baked level) was making Leaflet hide
the whole `GridLayer` once a viewer zoomed in past it — `GridLayer`'s own
`_setView` sets `_tileZoom` to `undefined` (no tiles at all) once the map's zoom
exceeds a layer's `maxZoom`, which is what actually produced "the tiles never load"
regardless of which multiplier was the deepest. `maxNativeZoom` is the option
`GridLayer` already ships for exactly this — reuse and auto-scale the deepest
available level past its own native zoom — so this is config, not new tile logic.

### 4th addendum: reinstated the 16x level by doubling TILE_PX instead (post-launch fix)

**Decision**: `BASEMAP_LEVELS` is `(1, 2, 4, 8, 16)` again and `TILE_PX` is now 512
(was 256). 16x is a real Leaflet zoom level once more — `maxNativeZoom` in
`src/main.js` again tracks whatever the deepest baked level is (now 16x), with
overzoom kicking in only past that.

**Rationale**: User-directed follow-up asking for "a bit more resolution" than the
3rd addendum's 8x-and-overzoom ceiling. First checked whether a true in-between
level (e.g. a 12x tier) was possible: it isn't — `src/basemapTiles.js`'s
`levelForZoom` matches a level to a Leaflet zoom via `Math.log2(level.scale)`, and
`GridLayer` only ever requests tiles at an integer native zoom, so any level's
`scale` must be a power of two or it's simply never requested. The only two real
options were "reinstate 16x" or "sharpen the existing levels via a bigger
`CANVAS_SIZE`"; the user chose reinstating 16x.

The 3rd addendum dropped 16x specifically because it was ~16,950 of ~22,600 total
chunk files (2nd addendum's numbers) at `TILE_PX = 256`. Chunk count per level is
`ceil(CANVAS_SIZE * scale / TILE_PX)` in each dimension, so it scales with
`1/TILE_PX²` — doubling `TILE_PX` to 512 quarters every level's chunk count,
including a reinstated 16x's. At the real `CANVAS_SIZE = (2400, 1800)`: 2x ≈ 80
chunks, 4x ≈ 285, 8x ≈ 1102, 16x ≈ 4275 — the reinstated 16x level now costs about
what 8x alone cost before, and the whole pyramid's total (~5,742 chunks) is close
to the old 8x-only total (~5,660), not the ~22,600 the original 16x attempt cost.
Trade-off: each chunk file is ~4x the pixel area of before, so panning/zooming
downloads fewer but bigger files — not revisited, since the whole point was more
visible detail per chunk.

## 3. Marker positioning: reuse the existing projection math, computed once in Python

**Decision**: Because the whole artifact uses exactly one fixed `(center, zoom,
canvas_size)` triple for its one basemap image (§2), every merged member's on-image
pixel position can be computed **once, in Python**, at generation time, using the
already-tested `lonlat_to_pixel(lat, lon, center, zoom, canvas_size)` from
`scripts/rkby_maps/basemap.py` — the exact same function `generate_member_maps.py`
uses to place pins. The generated data file ships each member's final `x`/`y` pixel
coordinates directly; the frontend never re-derives a projection from raw lat/lon at
all. Leaflet's `L.CRS.Simple` treats the image's own pixel space as its coordinate
system (image bounds `[[0, 0], [canvasHeightPx, canvasWidthPx]]`, with Leaflet's `y`
negated relative to raw pixel `y` — a well-known `CRS.Simple` convention, since
Leaflet's "latitude" increases upward while image pixel rows increase downward).

**Rationale**: Avoids re-implementing (and re-testing) Web Mercator projection math
twice, in two languages — one of the exact kinds of duplication Constitution II
allows factoring out, except here the simpler fix is to just not need it client-side
at all. It also shrinks the amount of client-side logic that would otherwise need
JS test coverage (§1) down to genuinely pure, small functions.

**Alternatives considered**: Feeding Leaflet real lat/lon with a geographic CRS
(`L.CRS.EPSG3857`) and an `ImageOverlay` whose bounds are also lat/lon — rejected as
extra indirection for no benefit, since there are no live geographic tiles to align
to (§2) and `CRS.Simple` + precomputed pixel coordinates is simpler and requires no
projection code in the browser at all.

## 4. Cross-season merge, eligibility, and the bundled data shape (FR-004, FR-009, FR-010)

**Decision**: A new `scripts/rkby_interactive_map/merge.py` module, unit-tested via
`pytest` against synthetic fixtures (Constitution V), that:

1. Loads every season via `rkby_records.discover_seasons` +
   `rkby_records.load_existing_records` (reused, no change).
2. Applies the same eligibility filter as `generate_member_maps.py`
   (`not excluded and not ignore`, then geocode-if-needed via
   `rkby_maps.geocoding.geocode_record_if_needed`, fill-empty-only, written back to
   that season's YAML exactly like today — FR-020) per season-record.
3. Groups eligible season-records by `match_key` across every season.
4. For each match_key, picks the **latest** eligible record by season label — season
   labels sort correctly as plain strings (`"2024-25" < "2025-26"`, matching
   `discover_seasons`' existing sort) — as the source of that person's merged
   `name`/`photo`/position (FR-010), and keeps *every* eligible season-record's
   `role`/`additional_roles` as a small per-season map for the popup (FR-015).

The output is one Python object per distinct eligible person: `{match_key, first_name,
last_name, num_previous_seasons, photo_relative_path, latitude, longitude, seasons:
{season_label: {role, additional_roles}, ...}}`. This *is* the data later turned into
pixel coordinates (§3) and serialized into the bundle (§9) — no separate
representation.

**Rationale**: This is exactly the FR-009/FR-010/FR-004 logic as specified, and the
one piece of new logic risky enough to matter for Principle V's "merge logic is
exactly where things silently break" rationale — so it lives in Python with full
pytest coverage rather than as client-side JS. Season-active-set *visibility*
filtering (does this person show right now) and *which* role entries to display are
NOT baked in here — they depend on live UI toggle state, so they stay a thin,
separately-tested pure function in the frontend (§6/§7) that filters this
already-computed per-season map.

**Alternatives considered**: Computing the merge in JS, from a raw per-season-record
dump — rejected; larger, riskier client logic with weaker test tooling, for a
computation that has no dependency on live browser state and is trivially a
generation-time concern.

## 5. Default-season rule ported to JS, evaluated at view time (FR-007)

**Decision**: Port `scrape_applicants.default_season_label(today)` to a small, pure
`defaultSeasonLabel(date)` function in `frontend/interactive-map/src/defaultSeason.js`,
unit-tested with Vitest against the same boundary cases the Python version implies
(July 31 vs. August 1 across a year boundary). Evaluated once at page load using
`new Date()` (the viewer's own device clock, per spec). If the computed label isn't
in the bundled season list, fall back to the lexicographically-greatest bundled
season label (same sort order as `discover_seasons`).

**Rationale**: FR-007 requires this to run "at view time (using the viewer's own
device clock)" — it cannot be baked in at generation time, since the artifact is
generated once and viewed potentially much later/by other people. The logic itself
is a direct, faithful port of an already-pytest-tested five-line function, so the
risk of the JS and Python versions silently diverging is low and cheaply checked.

```js
function defaultSeasonLabel(date) {
  const year = date.getFullYear();
  const month = date.getMonth() + 1; // JS months are 0-indexed
  if (month <= 7) return `${year - 1}-${String(year % 100).padStart(2, "0")}`;
  return `${year}-${String((year + 1) % 100).padStart(2, "0")}`;
}
```

## 6. Season-selection visibility and per-season popup data (FR-006, FR-008, FR-015, FR-016)

**Decision**: Two small, pure, Vitest-tested functions in
`frontend/interactive-map/src/popupData.js`:

- `isVisible(member, activeSeasons: Set<string>)` — `true` iff any key of
  `member.seasons` is in `activeSeasons`.
- `popupData(member, activeSeasons)` — returns `{name, numPreviousSeasons: number |
  null, seasons: [{label, role, additionalRoles}, ...]}`, restricted to just the
  currently-active seasons the member has an entry for, sorted by season label.
  `numPreviousSeasons` stays `null` when not on file; the (untested, DOM-only)
  render step turns `null` into an "unknown" label rather than a blank (FR-016).

Toggling a season control re-runs both functions over the full bundled member list
and re-syncs Leaflet's marker layer (add/remove, no page reload) — Leaflet's
`LayerGroup.addLayer`/`removeLayer` do this without any tile/network activity,
satisfying FR-008's "immediately, no reload."

**Rationale**: Keeps FR-006/FR-008's live, UI-state-dependent behavior client-side
(where it has to be) while keeping the *logic* itself small, pure, and testable —
same reasoning as §5.

## 7. Same-coordinate marker decluttering (FR-021, Edge Cases)

**Decision**: A pure `declutterPositions(members)` function
(`frontend/interactive-map/src/declutter.js`, Vitest-tested) that groups members by
exactly-equal precomputed `(x, y)` pixel position (§3) and, within any group of 2+,
applies a small fixed horizontal pixel offset per member — the same idea as
`scripts/rkby_maps/rendering.py`'s existing `draw_offset_photo_circles` /
`PHOTO_OFFSET_FRACTION` for the static photo map's FR-014 exception, ported to
operate on Leaflet marker positions instead of baked pixels. Because it runs on the
already-projected pixel coordinates, "exactly equal" is a simple numeric equality
check — no floating-point tolerance games, since two *distinct* real addresses will
essentially never project to byte-identical pixel floats, and an identical address
always will.

**Rationale**: Directly satisfies the Edge Case ("their photos remain stacked at
every zoom level... the viewer must still be able to discover and view each
individually") using a pattern the codebase already established and tested for the
same underlying problem in the static map — offsetting, not clustering/merging,
keeps every member independently hoverable.

## 8. Attribution and controls

**Decision**: Use Leaflet's built-in `attributionControl` (bottom-right, Leaflet's
own default corner) set to `"© OpenStreetMap contributors"`, rather than baking
attribution text into the raster image as `generate_member_maps.py` does — it's
real, always-legible HTML text, matching the tile policy's *"Do not hide attribution
beneath UI, behind toggles, or off-screen"* guidance directly. Zoom in/out buttons
use Leaflet's built-in `zoomControl` (pure CSS, no image assets needed). Directional
pan buttons (FR-014's "panning" control) are a small custom Leaflet control — four
arrow buttons calling `map.panBy([dx, dy])` — since Leaflet has no built-in
equivalent and one isn't worth a plugin dependency.

**Rationale**: Satisfies FR-014 and FR-022 with zero additional dependencies;
Leaflet's default marker-icon assets aren't needed at all since every marker is a
custom circular photo (§9), so nothing beyond `leaflet.js`/`leaflet.css` needs
vendoring.

## 9. Photo rendering: CSS crop instead of server-side cropping

**Decision**: Copy each merged member's own photo file as-is (no pre-processing)
into the output folder's `photos/` subfolder, or `photos/placeholder.png` (a direct
copy of the existing `scripts/rkby_maps/assets/rynke.png` mascot) when none is on
file. Render it circularly in the browser via CSS (`border-radius: 50%` +
`object-fit: cover` on the `<img>`/`L.divIcon` markup) rather than reusing
`rkby_maps.rendering.crop_circular_photo`.

**Rationale**: `object-fit: cover` on a square container reproduces exactly the same
"centered square crop, then circular mask" visual result `crop_circular_photo`
already bakes into a raster — satisfying FR-011's "same crop and placeholder logic"
*as an outcome*, achieved by a different (and here, better-suited) mechanism: CSS
cropping is resolution-independent (crisp at any zoom level, unlike a fixed-diameter
pre-baked circle) and needs zero Pillow work per member, which also helps the
SC-011 time budget. The placeholder image itself is still the exact same asset file,
satisfying the "otherwise the existing fixed placeholder image" requirement
literally, not just visually.

**Alternatives considered**: Reusing `crop_circular_photo` to pre-bake a fixed-size
circular PNG per member — rejected; adds Pillow work with no visual benefit over CSS,
and produces a lower, fixed resolution that looks worse than the source photo once
zoomed in.

### Addendum: server-side square downscale after all (post-launch perf fix)

**Decision reversed, partially**: real photos are no longer copied as-is. `bundle.py`
now crops each to a centered square and downscales it to a small fixed thumbnail
(`rkby_maps.rendering.crop_square_thumbnail`, 120px) before writing it into
`photos/`; the browser still does the *circular* crop via CSS exactly as decided
above — only the "copy as-is" half of the original decision is reversed.

**Rationale**: The "no visual benefit, worse once zoomed in" argument against
pre-processing assumed the photo would be displayed larger as the *map* zooms in.
It never is — the marker `<img>` is a fixed 40 CSS-px `L.divIcon` (`main.js`
`iconSize`) regardless of the map's own zoom level (research.md §3's marker
positioning is independent of the basemap's zoom-swapping addendum above). Shipping
and decoding full-resolution originals for hundreds of members at that fixed display
size was the main cause of a slow-loading map — bandwidth and per-image decode cost
that scale with the *source* photo's resolution, not the (constant) display size. A
small fixed-size thumbnail has no measurable quality cost at 40px and removes that
cost entirely.

## 10. Local `file://` compatibility (FR-019, Story 4, SC-003)

**Decision**: Three concrete constraints on the frontend build, all needed because
Chromium-family browsers (the most common "standard current browser") block
`fetch()`/XHR *and* ES-module (`<script type="module">`) loading of other local
files when a page is opened via `file://` — both are treated as cross-origin
requests from an opaque `file://` origin and rejected, even though plain resource
tags (`<img src>`, `<link rel="stylesheet">`, classic `<script src>`) load local
files under `file://` without issue in every mainstream browser:

1. **Single-file, non-module JS/CSS bundle**: `vite-plugin-singlefile` (MIT
   licensed, actively maintained — v2.3.3 as of this writing) inlines the built
   app's JS and CSS directly into `dist/index.html` as a plain (non-`module`)
   `<script>`/`<style>` block, so there's no separate-file module graph for the
   browser to reject under `file://`.
2. **Relative asset base**: `vite.config.js` sets `base: "./"` so any asset URL the
   build does emit is relative to `index.html`'s own folder, not the filesystem
   root (`file:///photos/...` would otherwise resolve wrong).
3. **Data injected via a classic external script, never `fetch()`**: the
   per-run-generated member/season data is written by Python into a plain
   `map-data.js` file — `window.RKBY_MAP_DATA = {...};` — referenced from
   `index.html` as `<script src="./map-data.js"></script>` (a classic external
   script, not a module, not a `fetch()` call), loaded *before* the bundled app
   script runs. This is the standard workaround for exactly this class of
   "self-contained offline HTML report" tool. Photos and the basemap image, loaded
   via plain `<img>`/CSS, need no such workaround.

**Rationale**: This is the single biggest concrete risk to Story 4/SC-003 actually
working as promised — a Vite app built with its own defaults silently fails to run
at all when double-clicked open from a shared folder in Chrome, which would be
exactly the failure mode a recipient hits first and can't self-diagnose. All three
points are ordinary, well-established Vite configuration; verifying the exact
`index.html` templating mechanics (getting `map-data.js`'s `<script>` tag to survive
Vite's HTML processing untouched) is a small, cheap thing to confirm early in
implementation.

## 11. Output artifact layout and generation performance (FR-018, SC-011)

**Decision**: `<RKBY_DATA_DIR>/interactive_map/` (gitignored, created + added to
`.gitignore` before any file is written — same bootstrapping pattern as
`generate_member_maps.py`'s `_ensure_output_dirs_and_gitignore`):

```
interactive_map/
├── index.html        # copied verbatim from frontend/interactive-map/dist/
├── map-data.js        # generated fresh every run (§10)
├── basemap.jpg         # generated fresh every run (§2)
└── photos/
    ├── placeholder.png
    └── <match_key>.<ext>   # one per merged member with a photo on file
```

The basemap fetch reuses the same `.tile_cache/` directory `generate_member_maps.py`
already populates (research.md §2 there) — a team that has already run the existing
map generator will typically hit a warm cache for most tiles, and either script
benefits from whichever ran first. Geocoding likewise reuses the shared per-address
cache on each season's YAML records (fill-empty-only, §4) — steady-state runs
geocode ~0 new addresses, matching SC-011's 15-minute budget with room to spare; the
dominant one-time cost is the basemap's own tile fetch for whatever combined
bounding box this team's data actually spans.

**Rationale**: One artifact, not season-prefixed, per FR-018; reusing both existing
caches (geocoding, tiles) rather than introducing separate ones avoids doing
redundant network work `generate_member_maps.py` may have already done, and keeps
this script's own cold-start cost bounded to whatever tiles the *other* script
hasn't already fetched.

## 12. Data minimization for the shared artifact (Constitution Principle I)

**Decision**: `map-data.js` carries only: `match_key`, full name, `num_previous_seasons`,
photo relative path, precomputed `x`/`y` position, and a per-season `{role,
additional_roles}` map. It explicitly never includes `address`, `phone`, `email`,
`birthday`, `sex`, `motive_for_participation`, `food_restrictions`, `status`, or the
`excluded`/`ignore` flags themselves — none of those are popup fields per spec's
Assumptions (`address`, name-only "job title" mapping is `role` +
`additional_roles`).

**Rationale**: Constitution Principle I names "interactive maps" directly as an
example of an artifact that "MUST expose only the minimum data necessary for its
stated purpose" — this is that principle applied literally to this feature's own
field list, not a new consideration. Excluded/ignored season-records are already
filtered out entirely before this stage (§4), satisfying the opt-out requirement
(SC-010) the same way `generate_member_maps.py` already does.

## 13. Mobile mode: auto-detection, drawer, and settings panel (FR-023-FR-028)

**Decision**: A pure predicate, `shouldDefaultToMobile(viewportWidth, isCoarsePointer)`
(`frontend/interactive-map/src/mode.js`, Vitest-tested — same pattern as §5–§7),
combining both signals the user asked for: `viewportWidth < BREAKPOINT_PX ||
isCoarsePointer`. `main.js` calls it once at startup with the real
`window.innerWidth` and `window.matchMedia("(pointer: coarse)").matches`, to pick
the initial mode (FR-023); from then on, mode lives in one in-memory variable for
the page's lifetime, changed only by the settings control (FR-024) — no
`resize`/`orientationchange` listener re-runs the predicate after load (matches the
Assumptions' "auto-detection only decides the mode at initial load" framing, and
spec's Edge Case about resizing not silently changing an already-loaded mode). No
persistence (`localStorage`) across reloads either — deliberately, since `file://`
origins have inconsistent `localStorage` semantics across browsers (some scope it
per-file, some disable it entirely for `file://`), and the spec's own Assumptions
(Mode-switch scope) only requires it to survive for the current page load.

**Desktop mode** (unchanged from the rest of this document): hover opens/mouseout
closes the existing Leaflet popup (§6); season checkboxes sit directly on the map.

**Mobile mode**: tapping a marker calls `popupData(member, activeSeasons)` (§6,
reused unchanged — the data-shaping logic doesn't care which UI consumes it) and
renders the result into a bottom-sheet `<div>` (CSS: `position: fixed; bottom: 0;
max-height: 50vh; overflow-y: auto;`, a close button, and a full-viewport
transparent backdrop `<div>` behind it that closes the drawer on tap — the standard
"tap-outside-to-dismiss" pattern, needing no click-outside-detection library).
Tapping a different marker while the drawer is open just re-renders its content in
place (FR-026) rather than requiring dismiss-then-reopen. Leaflet's own tap handling
(`marker.on("click", ...)` — Leaflet normalizes touch-tap and mouse-click to the
same `click` event) is what triggers this, so no separate touch-event library is
needed either.

**Settings panel**: a single small control (e.g. a gear icon, top corner) toggled
open/closed, containing the mode switch always, and — only when currently in mobile
mode — the same season checkboxes desktop shows inline (FR-027). In desktop mode the
settings panel holds just the mode switch; season checkboxes stay on the map as
already specified for desktop, unchanged by this feature.

**Rationale**: Keeps the one piece of genuinely risky new logic (the auto-detect
decision itself) small, pure, and Vitest-tested, consistent with how §5–§7 already
drew this line; the drawer/settings panel are DOM/CSS wiring comparable in risk to
the rest of `main.js`'s existing Leaflet glue, verified instead via quickstart.md
(Constitution V's "manually verified... in addition to automated tests" posture for
lower-risk code, same reasoning plan.md's Constitution Check already applies to
`main.js`). Reusing `popupData()` unchanged for both desktop and mobile means the
FR-015/FR-016 field logic is tested exactly once, not duplicated per display
mechanism.

**Alternatives considered**: A CSS-only responsive layout with no distinct "mode"
concept at all (media queries reshaping the same popup) — rejected; the user
explicitly asked for hover-vs-drawer as genuinely different interaction patterns
(hover has no touch equivalent) and a manual settings override, neither of which a
pure-CSS approach can express. Persisting the manual mode choice via `localStorage`
— rejected for the `file://`-origin inconsistency reason above; revisit only if a
real user complaint about "resets every time" surfaces.
