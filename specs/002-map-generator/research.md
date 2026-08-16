# Phase 0 Research: Member Map Generator

Each unknown from the Technical Context is resolved below as Decision / Rationale /
Alternatives considered.

## 1. Basemap rendering approach

**Decision**: Implement a small, in-house Web Mercator tile-fetch/stitch module
(`scripts/rkby_maps/basemap.py`) rather than adopting a static-map library — fetch
256px OSM raster tiles over `requests`, stitch them into a canvas with `Pillow`, then
crop to the exact target pixel size.

**Rationale**: The feature needs three things no off-the-shelf static-map library
cleanly gives together: (1) explicit control over the map's real-world covered width in
km, not just "auto-fit to markers" (needed for FR-010's configurable minimum width and
FR-012's "smallest width that resolves the overlap"); (2) the exact pixel coordinate of
every member's lat/lon on the rendered canvas, computed independently of the renderer,
so the overlap/clustering logic (FR-011) and the scale bar (FR-008) can reason about
positions without round-tripping through a library's internal state; (3) a Pillow-only
render path with no system-level dependency (Cairo). Web Mercator tile math (lon/lat →
tile/pixel, meters-per-pixel at a given zoom/latitude) is a well-known, ~30-line
closed-form formula — implementing it directly is smaller and more predictable than
adapting a general-purpose library's abstractions to fit, and keeps the total new
runtime dependency count to one (`Pillow`), which the code already needs for photo
cropping, scale-bar drawing, and fallback badges regardless of the basemap approach
(Constitution IV: smallest footprint that does the job).

**Alternatives considered**: `py-staticmaps` (actively maintained, Pillow-renderable,
supports image markers — but its documented API is "auto-compute center+zoom from
added objects," with no documented way to read back a marker's rendered pixel position
or to pin an exact real-world km-width, which is exactly the control this feature
needs); `staticmap` (komoot) and `contextily` (pulls in `matplotlib`
+ `rasterio`/`geopandas`, far heavier than this project's footprint goal) — rejected
for the same lack-of-control or dependency-weight reasons.

## 2. Tile source & usage-policy compliance

**Decision**: Fetch raster tiles from the standard OSM tile server
(`https://tile.openstreetmap.org/{z}/{x}/{y}.png`) with a custom, identifying
`User-Agent` header (never the default `requests` UA), and persist every fetched tile
to an on-disk cache (`<RKBY_DATA_DIR>/.tile_cache/{z}/{x}/{y}.png`, no expiry) so a tile
already fetched by any past run of this tool is never re-requested. Render a small "©
OpenStreetMap contributors" attribution string into the bottom-left corner of every
generated map.

**Rationale**: The OSMF tile usage policy requires a valid identifying User-Agent,
prohibits *bulk* pre-seeding (systematic scans of areas/zooms nobody asked to see) but
explicitly allows fetching what you're about to display, and requires attribution. This
tool only ever fetches the tiles covering a bounding box it is about to render into an
actual output map — normal "fetch what you show" usage, not bulk downloading. The
persistent cache both keeps the tool a good citizen of a donation-funded shared service
(never re-fetching a tile it already has) and helps meet SC-005's 5-minute budget on
repeat runs (SC-006), since overview and detail maps for the same season/variant
routinely share tiles. Tiles aren't personal data, so caching them locally raises no
Principle I concern; the cache dir is added to the data repo's `.gitignore` alongside
`maps/` (see §12).

**Alternatives considered**: A commercial/paid tile provider (rejected — unnecessary
cost/signup friction for a volunteer hobby tool, OSM's own tiles are the natural choice
already implied by the spec's Nominatim/OSM framing); no caching (rejected — wastes the
shared service's capacity on every re-run and risks throttling under SC-005/SC-006).

## 3. Geocoding

**Decision**: A minimal Nominatim client using plain `requests` (no `geopy`) against
`https://nominatim.openstreetmap.org/search`, sending only the member's address text as
the `q` parameter, one request per address that doesn't already have cached
coordinates, throttled to 1 request/second (Nominatim's documented limit), with a
custom identifying `User-Agent`. On a successful response, cache `latitude`/
`longitude` back into that member's YAML record (fill-empty-only — see §11); on no
match or an HTTP/network error, leave both fields `null`, log the member as skipped
(FR-006), and retry on the next run (mirrors the scraper's existing photo/birthday
retry-until-success pattern).

**Rationale**: `requests` is already a project dependency; Nominatim's search endpoint
is a single GET call, so adding `geopy` purely to wrap that one call would be an
unjustified dependency per Constitution IV. Rate-limiting and a real User-Agent are
non-negotiable per Nominatim's usage policy. Caching-on-first-success plus
retry-on-failure exactly mirrors the established, already-tested pattern in
`scrape_applicants.py` for photo/birthday fetch, keeping the codebase's conventions
consistent.

**Constitutional note**: sending address text to Nominatim is, literally, "uploading"
member data to a third-party service — in tension with Principle I's unqualified "MUST
NOT be uploaded to third-party cloud services" wording, even though spec.md's
Assumptions section already scopes this narrowly (address text only, never name/photo/
phone/birthday; once per address, ever; cached locally afterward) and treats it as a
deliberate, documented exception. A spec's Assumptions section cannot, on its own,
override a NON-NEGOTIABLE constitutional principle — see Constitution Check in plan.md
and the recommendation to formally ratify this exception via `/speckit-constitution`
before/alongside implementation.

**Alternatives considered**: `geopy` (thin wrapper around exactly the HTTP call
`requests` already handles — rejected, extra dependency for no capability gained);
bundling an offline geocoding database (rejected — far too heavy for Constitution IV,
and out of proportion to a project serving ~200 addresses total).

## 4. Overlap detection & clustering algorithm

**Decision**: For a given rendered map (a specific center + zoom + variant), project
every eligible member's lat/lon to canvas pixel coordinates (§1's Web Mercator math),
then build a graph with an edge between any two members whose pixel distance is less
than the sum of their marker radii (pin radius for the pin variant, photo-circle radius
for the photo variant — see §7 for default sizes). Connected components of size ≥ 2 are
overlap groups (FR-011); this graph is transitive, so three markers in a row where only
adjacent pairs touch still form one cluster, matching the "identify clusters" framing
in the original request.

**Rationale**: A simple pairwise-distance-vs-combined-radius test is exactly what
"markers would visually overlap" means for circular markers (pins are rendered as a
circular head in this design — see §7), and connected components is the standard,
easily-tested way to turn pairwise overlap edges into groups without hand-rolling
bespoke merge logic. Because canvas pixel distance between two fixed geographic points
strictly increases as the map's covered width (km) decreases (more zoomed in ⇒ more
pixels per km), overlap can only be *resolved*, never newly introduced, by zooming in —
which is what makes the detail-map algorithm in §5 terminate without recursion.

**Note — computed per variant**: pin and photo markers have different radii (§7), so a
pair that overlaps as photo circles may not overlap as pins, and vice versa. Clusters,
and therefore which detail maps get generated, are computed independently for the
pin-map and photo-map passes over the same season (FR-011's "per map" already implies
this; stated explicitly here since it means detail-map generation runs twice per
season, independently parameterized).

## 5. Detail-map sizing

**Decision**: For an overlap group (that isn't the FR-014 exact-same-address pair
exception), compute the smallest bounding box containing the group's members plus a
fixed padding margin, convert that to a required covered width in km, then render the
detail map at `max(configured minimum width, required width)`. Re-run the §4 overlap
check against that render; any member pair still overlapping at that width uses the
FR-013 fallback (§8) on that same detail map — the generator does not recurse into an
ever-tighter detail map.

**Rationale**: This is a direct implementation of spec.md's own "Detail map framing"
Assumption — "sized to the smallest width that both resolves the overlap and respects
the FR-010 minimum width; if the minimum width itself is too wide to resolve the
overlap, FR-013's fallback rendering applies" — so no new design judgment call is being
made here, only the concrete formula. Because OSM tiles only exist at discrete integer
zoom levels, "smallest width" in practice means: pick the tightest (highest) integer
zoom level whose resulting covered width is still ≥ `max(configured minimum, required
width)`; each step up in zoom roughly halves covered width, so this converges in at
most ~20 steps and the discretization only ever makes a map slightly *wider* than the
exact target, never narrower than the configured minimum (still satisfies FR-010 as a
strict lower bound).

**Alternatives considered**: Continuous (non-integer-zoom) rendering via upsampling +
cropping stitched tiles to a fractional scale — rejected as unnecessary complexity;
snapping to the nearest coarser integer zoom already satisfies every functional
requirement (a lower bound, not an exact target) with far simpler, more testable code.

## 6. Scale bar (ruler) rendering

**Decision**: Compute meters-per-pixel at the map's actual rendered zoom and center
latitude (`156543.03392 * cos(latitude) / 2^zoom`, standard Web Mercator formula), pick
a "nice" round bar length (1/2/5/10/20/50/100 km, whichever best fits ~15% of the
canvas width), draw it as a filled horizontal bar with end-ticks and a text label (e.g.
`"5 km"`) in the bottom-right corner via `Pillow.ImageDraw`, per FR-008. Suppressed
entirely when `--no-scale-bar` is passed (FR-009).

**Rationale**: This is the standard "map ruler" construction and needs no library
beyond `Pillow`, which is already required for compositing. Deriving it from the same
Web Mercator formula used for pixel placement (§1, §4) guarantees the scale bar is
always geometrically consistent with where markers are actually drawn.

## 7. Marker rendering: pins, photo circles, role colors

**Decision**: Pins are drawn as a filled circle (a simplified "pin head", radius 10px
on the default 1600×1200px canvas — see below) rather than a teardrop shape, to keep
the overlap math in §4 an exact circle-vs-circle test. Photo markers are a 48px-diameter
circular crop (§8) centered on the member's position. Default canvas size: 1600×1200px
(landscape, print/share-friendly, small enough to keep tile-fetch volume and render
time low per SC-005). Role colors (FR-007, low-saturation/neutral, four total —
distinct hue and roughly equal lightness so no one role visually dominates):

| Role (raw scraped text, case-insensitive match) | Color | Hex |
|---|---|---|
| Rider | muted teal | `#4C8C86` |
| Service Crew | muted amber | `#B08A4E` |
| Supporter | muted slate blue | `#5B6C8F` |
| unset / unrecognized | neutral gray | `#8A8A8A` |

**Rationale**: A circular pin makes "does marker A overlap marker B" the same simple
test for both variants (§4), instead of needing a separate overlap footprint for a
teardrop shape. The four colors are chosen for roughly equal visual weight (no role
reads as more "important" than another) and clear pairwise distinction at small marker
size, per the request's "neutral colors" / "no legend needed" framing — a reader
distinguishes roles by consistent color alone. These are default/starting values;
Constitution IV and the "no legend" requirement don't demand a particular palette, so
this table is a proposal the implementer (tasks phase) can freely retune without a
spec/plan change.

## 8. Photo circular crop & offset-stack fallback

**Decision**: Match the intranet table's presentation by taking a centered square crop
of the source photo (side length = `min(width, height)`), resizing to the target
diameter, then masking to a circle with `Pillow` (`ImageDraw.ellipse` alpha mask +
`Image.composite`). For the FR-013 photo-variant fallback (an unresolved overlap),
render each affected member's circle at the shared position but horizontally offset by
a configurable fraction (`PHOTO_OFFSET_FRACTION`, `rkby_maps/rendering.py`; currently
80%) of the circle's diameter per additional member, so faces stay individually visible
instead of fully stacking. For the pin-variant fallback, draw one merged pin at the
shared position plus a small counter badge (a filled circle with the member count as
white text) offset to its upper-right — the same visual language commonly used for
map-marker clusters. A merged pin uses the shared role color if every member in the
group shares one role, otherwise the neutral "unrecognized" color (§7) to signal a
mixed group.

**Rationale**: "Same as the website's table" is already interpreted in spec.md's
Assumptions as a centered-square-then-circle crop; this section just names the concrete
Pillow calls. The offset-stack and multiplicity-badge behaviors are exactly what
FR-013 describes ("side-by-side... offset", "merged pin with a multiplicity badge");
the mixed-role color rule is a natural, minor resolution of an otherwise-unstated case
that the plan surfaces explicitly rather than deciding silently in code.

## 9. Detail-map filename slug

**Decision**: Derive the location slug from the cluster's own already-cached address
text (no reverse-geocoding call): take the first member's cached address, extract the
city/town token (the address is stored as `"<street>, <postal-code> <city>, <country>"`
per the scraper's `_parse_applicant_row`; strip the leading postal-code digits from the
middle segment), then run it through the scraper's existing `normalize_name()`
ASCII/hyphenation logic. If two different clusters in the same season/variant run
normalize to the same slug, append `_2`, `_3`, ... in encounter order.

**Rationale**: Reverse-geocoding to get a place name would be a second, unnecessary
third-party address lookup per cluster (more privacy surface, more network calls, more
rate-limit exposure) when the member's own already-fetched address text already
contains a usable city name. Reusing `normalize_name()` (moved into the new shared
module, §10) keeps slug formatting consistent with the rest of the codebase's filename
conventions instead of inventing a second slugification scheme.

## 10. Shared season/record I/O module

**Decision**: Extract `season_dir`, `applicants_dir`, `photos_dir`, `load_schema`,
`validate_record`, `load_existing_records`, `_dump_record_yaml` (record write), and
`normalize_name` out of `scripts/scrape_applicants.py` into a new shared module,
`scripts/rkby_records.py`, imported by both the existing scraper and the new
`scripts/generate_member_maps.py`. Add a new `discover_seasons(data_dir) -> list[str]`
function (list every subfolder of `<data_dir>/seasons/` that has an `applicants/`
directory) needed only by the map generator.

**Rationale**: Constitution Principle II allows a shared module "once duplication is
real and causing bugs — not in anticipation of it." This is the case here, not
anticipation: the map generator needs the *exact same* season-folder layout, YAML
load/validate, and record-write logic the scraper already has and already tests: A
map-generator reimplementation of that logic would either subtly diverge from the
scraper's (risking two slightly different ideas of "a valid record" reading/writing the
same files) or be a verbatim copy — both worse than one tested shared module. This
keeps each script's own file focused on what's unique to it (HTTP scraping vs. map
rendering) per Principle II's intent, while removing genuine, current, cross-script
duplication.

## 11. Geocode cache write rule

**Decision**: `latitude`/`longitude` are written with the same fill-empty-only
discipline as every other mutable field in `merge_record`/`_fetch_*_if_needed` (§existing
scraper code): only ever set when both are currently `null`, never overwritten on a
later run — including when a later run's geocoding attempt would produce a
(marginally) different result for the same address text.

**Rationale**: Required by Constitution Principle III — a human may hand-correct
`latitude`/`longitude` directly in the YAML (e.g., after noticing a Nominatim
mis-geocode) exactly as they already hand-correct `birthday` or `photo`; a future run
must never silently clobber that correction. This also directly delivers SC-007 ("an
address that has already been successfully resolved once is never sent to an external
geocoding lookup again") for free, since "already resolved" and "fields already
non-null, skip re-geocoding" are the same check.

## 12. Output layout & git handling

**Decision**: Two new top-level folders under `RKBY_DATA_DIR`, both added to a
top-level `<RKBY_DATA_DIR>/.gitignore` (created if absent, appended to if present and
missing an entry) before any file is written into either:

- `maps/` — flat, all generated PNGs for every season directly inside it (FR-015),
  named per `contracts/map-output.md`.
- `.tile_cache/` — the OSM tile cache (§2); not a generated artifact, so it sits
  outside `maps/` to keep that folder exactly "the generated maps" for a human
  browsing it.

Every run's newly-cached `latitude`/`longitude` writes into `seasons/<label>/
applicants/*.yaml`, plus a first-time `.gitignore` creation/update, are staged and
committed at the end of a successful run when `RKBY_DATA_DIR` is a git work tree —
reusing/extending the scraper's existing `auto_commit_season`-style helper (moved into
`rkby_records.py`, §10), scoped to those paths only. `maps/` and `.tile_cache/` are
never staged (they're gitignored).

**Rationale**: Matches FR-015/FR-017 directly. Reusing the scraper's established
auto-commit pattern (detect git work tree, no-op if not a repo, log-not-raise on commit
failure) keeps the two scripts' data-repo interactions consistent instead of inventing
a second convention, and gives the maintainer the same per-run history for geocode-cache
writes that they already get for scraped field writes.

## 13. Testing strategy

**Decision**: All new tests run offline via `pytest` + the existing `responses` dev
dependency (already used for the scraper's HTTP mocking) — mocked Nominatim JSON
responses and mocked OSM tile bytes (a handful of tiny synthetic fixture PNGs). Pure
geometry (Web Mercator projection, meters-per-pixel, overlap/connected-components,
detail-map width selection) is tested as plain functions with synthetic coordinates, no
I/O needed. Rendering tests assert on the output PNG's dimensions, that pixel colors at
known marker positions match the expected role color, and that the scale bar/attribution
region is non-blank when enabled and unchanged (absent scale bar) when
`--no-scale-bar` is passed. Photo-crop tests use one small synthetic fixture image.
Per Constitution V, none of this touches real data under `data/` or `.env`.

**Rationale**: Directly follows the existing test conventions in this repo (`responses`
for HTTP, fixtures under `tests/fixtures/`, no network in CI) and Constitution V's
red-green/no-real-data requirements; pixel-level assertions on a small, deterministic
canvas are a practical way to test image-generation code without snapshot-testing full
PNGs.
