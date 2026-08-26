# Research: PMTiles Basemap for Interactive Map

Phase 0 output for [plan.md](plan.md). Each section resolves one unknown from the
Technical Context as Decision / Rationale / Alternatives considered. §1 and §2 were
verified empirically and against upstream source, not just documentation, because
they determine whether the whole approach works at all — see the verification notes
inline.

## §1. Vector-tile rendering library

**Decision**: Render the basemap with **`protomaps-leaflet`** (npm, currently 5.1.0)
+ **`pmtiles`** (npm, currently 4.5.0), added to
`frontend/interactive-map/package.json` alongside the existing `leaflet` ^1.9.4.
`protomaps-leaflet` renders Protomaps-schema vector tiles (exactly what the sample
archive contains — confirmed via `pmtiles show`: MVT, layers water/earth/
boundaries/roads/pois/transit/places) as a Leaflet `GridLayer`, using canvas
painting rather than WebGL — no MapLibre GL / WebGL dependency needed.

**Rationale**: The existing frontend is Leaflet-based end to end (`main.js`'s
custom marker popups, pan control, season-checkbox control, mobile drawer — see
`specs/003-interactive-photo-map/`). `protomaps-leaflet` keeps every one of those
Leaflet APIs working unchanged; only the basemap layer itself is replaced. Its own
`leafletLayer()` accepts a `PMTiles` instance directly, not just a URL string
(confirmed by reading the source: `protomaps-leaflet` `src/frontends/leaflet.ts:57`,
`url?: PMTiles | string`) — this is what makes §2's custom-Source approach possible.
It also ships ready-made default styling for a standard Protomaps schema
(`src/default_style/style.ts`'s `paintRules(flavor)`/`labelRules(flavor, lang)`,
`flavor: "light"` etc., matching the README's own usage example) — no custom style
sheet has to be authored from scratch to get a legible basemap.

Unpacked package size is `protomaps-leaflet` ~1.1 MB + `pmtiles` ~0.4 MB ≈ 1.5 MB
combined, vs. `maplibre-gl` alone at ~19.5 MB (`npm view <pkg> dist.unpackedSize`) —
consistent with the project's minimal-dependency ethos even though that's a Python
constitution principle (IV), not a formal frontend rule.

**Alternatives considered**:
- **MapLibre GL JS + its own `pmtiles://` protocol** (the officially "recommended
  for new projects" path per `protomaps-leaflet`'s own README: *"This library is
  now in maintenance mode. New features will not be added, and its use is
  recommended only for legacy Leaflet-based systems."*) — rejected for this feature.
  This project **is** exactly the "legacy Leaflet-based system" that sentence
  describes: swapping to MapLibre would mean reimplementing every existing
  Leaflet-specific interaction (marker popups, the custom pan control, the season
  control, the mobile drawer) against a different, WebGL-based API, a much larger
  lift than FR-001–FR-007 call for and a ~13x heavier dependency, for a feature
  whose entire point is *replacing the basemap*, not the rendering stack. The one
  capability this project actually needs from `protomaps-leaflet` — accepting a
  custom-Source `PMTiles` instance instead of fetching a URL — is a `pmtiles`
  package feature (see §2), not something that requires `protomaps-leaflet` itself
  to still be under active development. If a future need outgrows
  `protomaps-leaflet` (e.g. requiring a style feature only MapLibre has), that's a
  new feature's problem, not this one's.
- **Raw MVT parsing + hand-rolled canvas renderer**: rejected — reimplements what
  `protomaps-leaflet` already does, with no offsetting benefit.

## §2. Loading the PMTiles archive when the bundle is opened via `file://`

**Decision**: Never `fetch()` the `.pmtiles` file. Instead, base64-encode the whole
archive at generation time into a small classic-script asset (mirrors the existing
`map-data.js` pattern exactly), decode it to a `Blob` in the browser, and hand a
custom `Source` implementation backed by `Blob.slice()` to a `PMTiles` instance,
which is then passed directly as `protomaps-leaflet`'s `url` option (§1).

**Rationale — this is not optional, it's required**: `vite.config.js` already notes
Chromium blocks module-script loading for `file://`-opened pages, which is why
`map-data.js` is loaded via `<script src="map-data.js">` rather than `fetch()`
(research.md §10 of spec 003). This feature needed to know whether that restriction
extends to fetching a *sibling binary asset* too, since every PMTiles JS library's
default loading path (`pmtiles`'s `FetchSource`, and MapLibre's `pmtiles://`
protocol) uses `fetch()` with HTTP Range requests.

It does — verified directly, not from documentation: a real Chromium binary
(headless, same rendering engine an installed Chrome uses) opened a `file://` test
page next to a sibling binary file and attempted `fetch()` (relative and absolute
path) and `XMLHttpRequest` (plain and with a `Range` header). All four attempts
failed before any request was sent, with Chromium's console reporting:

> Access to fetch at 'file:///…/data.bin' from origin 'null' has been blocked by
> CORS policy: Cross origin requests are only supported for protocol schemes:
> chrome, chrome-extension, chrome-untrusted, data, http, https, isolated-app.

`file` is not in that list — so this is a hard, unconditional block, not a
Range-request nuance: **no `fetch()`- or `XHR`-based Source can ever read a local
sibling file from a `file://`-opened page in Chromium**, regardless of path form or
headers. This rules out `pmtiles`'s built-in `FetchSource` and MapLibre's
`pmtiles://` protocol outright for this project's "double-click `index.html`, no
server" requirement (FR-004).

The fix follows directly from the same test: `data:` URLs *are* in Chromium's
allowed-scheme list above, and the existing bundle already proves that non-fetch
loading mechanisms (`<script src>`, `<img src>`) work fine over `file://` — they
don't go through the Fetch/XHR CORS check at all. So the archive's bytes need to
reach the page through one of those mechanisms instead of a network request. Once
the bytes are already in memory as a `Blob` (however they got there), `pmtiles`'s
own public `Source` interface reads them with **zero network calls**:

```ts
// pmtiles npm package, js/src/index.ts:295-329 (exported, documented, stable API)
export interface Source {
  getBytes: (offset: number, length: number, signal?: AbortSignal, etag?: string)
    => Promise<RangeResponse>;
  getKey: () => string;
}

export class FileSource implements Source {
  constructor(file: File) { this.file = file; }
  getKey() { return this.file.name; }
  async getBytes(offset: number, length: number) {
    const blob = this.file.slice(offset, offset + length);
    return { data: await blob.arrayBuffer() };
  }
}
```

`Blob.slice()`/`.arrayBuffer()` are local memory operations, not network requests —
completely exempt from the CORS restriction above. `FileSource` is typed for a
`File`, but the interface only needs `.slice()`, so a plain `Blob` (constructed from
the decoded base64 bytes) satisfies a same-shaped `Source` without needing a `File`
at all (a `File` normally requires user-initiated selection, which this bundle
can't do on load). Concretely: `generate_interactive_map.py` writes
`interactive_map/basemap-pmtiles.js` containing
`window.RKBY_PMTILES_BASE64 = "…";`, loaded via `<script src="basemap-pmtiles.js">`
next to the existing `<script src="map-data.js">`; `main.js` decodes it once
(`Uint8Array.fromBase64` / manual `atob` loop), wraps it in a `Blob`, and constructs
`new pmtiles.PMTiles(mySource)` where `mySource` is a ~10-line class matching the
interface above.

Base64 inflates size by ~33% (the 19.7 MB sample archive → ~26 MB of embedded
text) — worth noting as a size trade-off, not a blocker: the bundle already ships
every member's photo uncompressed-ish alongside `index.html` in a locally-shared
folder, not over the wire to a stranger; SC-002 only requires the basemap to stay a
*small, constant number of files*, which this satisfies (exactly one extra file,
`basemap-pmtiles.js`, regardless of archive size or member spread).

**Alternatives considered**:
- **Serve the bundle from a tiny local HTTP server** instead of opening
  `index.html` directly — rejected: breaks the "double-click to open" contract
  every existing viewer relies on (`specs/003-interactive-photo-map/contracts/
  output-artifact.md` § Opening the artifact) and this spec's Out of Scope /
  Assumptions don't call for a viewing-time server.
- **Rely on the default `FetchSource` and just accept it might not work for some
  viewers**: rejected — it wouldn't work for *any* viewer opening the bundle the
  documented way (`file://`), not an edge case.
- **Use the `pmtiles` package's `FileSource` via `<input type="file">`, requiring
  the viewer to manually pick `basemap.pmtiles`** — rejected: defeats FR-001's
  "renders automatically," and there'd be nothing stopping a viewer from picking
  the wrong file.

## §3. Validating the PMTiles file (FR-003)

**Decision**: Validate with a stdlib-only header check — no PMTiles-parsing Python
dependency. A valid v3 archive's first 8 bytes are the ASCII string `PMTiles`
followed by a version byte (confirmed against both the upstream JS reader's own
check, `pmtiles` `js/src/index.ts:589` — `v.getUint16(0, true) !== 0x4d50` i.e.
bytes `50 4d` = `"PM"` — and a hex dump of the sample archive: `50 4d 54 69 6c 65
73 03 …` = `"PMTiles"` + version `3`). `load_config`/an early generation step reads
the first 8 bytes of `<RKBY_DATA_DIR>/basemap.pmtiles` and fails with a message
naming the expected path if the file is missing, unreadable, shorter than 8 bytes,
or those bytes don't match `b"PMTiles"` + a supported version byte.

**Rationale**: FR-003 only needs "is this plausibly a PMTiles archive," not full
archive parsing — all real tile reading happens browser-side (§2). Matches
Constitution Principle IV (minimal deps): adding a Python PMTiles-parsing package
just to check 8 bytes would be dependency weight with no behavior gained.

**Alternatives considered**: add the `pmtiles` *Python* package (a separate,
lower-profile package from the JS one) purely for validation — rejected as
unjustified weight for a magic-byte check.

## §4. Where the PMTiles file lives

**Decision**: `<RKBY_DATA_DIR>/basemap.pmtiles` — one fixed, top-level,
maintainer-placed input file, analogous to how `.tile_cache/` and `seasons/`
already anchor other inputs/caches directly under `RKBY_DATA_DIR`.

**Rationale**: Spec 004's Assumptions say the file is placed "at a documented
location" but the spec (correctly, per its own scope) doesn't name a path — that's
an implementation detail, not a user-facing requirement, so it's settled here. A
single top-level file keeps the contract simple (no new subfolder to document) and
matches the "one file, one purpose" pattern the rest of `RKBY_DATA_DIR` already
uses.

## §5. Marker positions: real geographic CRS instead of a precomputed pixel canvas

**Decision**: Switch the Leaflet map from `L.CRS.Simple` (an arbitrary pixel space,
used because the old basemap was one baked flat image) to Leaflet's default
`L.CRS.EPSG3857` (real Web Mercator), and position every member marker directly
from their already-geocoded `latitude`/`longitude` (`merge.py` already puts these
on every merged member — `scripts/rkby_interactive_map/merge.py:109-110`) via
`L.marker([lat, lon])`. `map-data.js`'s per-member `x`/`y` fields (precomputed
pixel positions baked for one fixed synthetic canvas) are replaced by `lat`/`lon`
passthrough fields; the whole `image` block (`file`/`width`/`height`/`tileSize`/
`tileLevels`) is removed, replaced by a small `basemap` block naming the embedded
asset (§2).

**Rationale**: A PMTiles archive is addressed by real `(z, x, y)` tile coordinates
in standard Web Mercator space — there's no "one fixed canvas" left to precompute
pixel positions against once the basemap itself is a real geographic tile source,
and the whole point of this feature is deleting that baking step (`bundle.py`'s
`compute_positions`, `generate_basemap`, `_tile_levels`, `_write_level_tiles`,
`_base_level`, and their `BASEMAP_LEVELS`/`TILE_PX`/`MAX_OSM_ZOOM` constants) along
with it. `zoom_for_bounding_box`/`lonlat_to_pixel`/`canvas_origin`/`stitch_basemap`
in `rkby_maps/basemap.py` **stay untouched** — `generate_member_maps.py` (the
static-PNG map generator, spec 002) still calls them directly for its own
overview/detail maps, which this feature does not touch.

One knock-on change: `declutter.js`'s overlap math currently compares precomputed
canvas-pixel distances scaled by a zoom ratio (`main.js` passes
`map.getZoomScale(map.getZoom(), 0)`). Under a real CRS, the equivalent input is
each marker's actual on-screen position, which Leaflet can compute directly via
`map.latLngToContainerPoint(latlng)` — recomputed on every `zoomend`/`moveend`, same
event-driven pattern already in place, just a different source of x/y. This is an
implementation detail for `tasks.md`, not a requirement change: FR-021's declutter
behavior itself is unaffected.

**Alternatives considered**: keep `CRS.Simple` and re-derive a synthetic pixel
canvas from the PMTiles archive's own coverage — rejected, fights the tile
source's native coordinate system for no benefit and keeps dead pixel-projection
code alive on the Python side for a feature explicitly about deleting it.

## §6. Zoom range at the deepest/shallowest available detail

**Decision**: Read `minZoom`/`maxZoom` from the PMTiles archive's own header at
runtime (`pmtiles.PMTiles#getHeader()`, part of the same public API as §2) rather
than duplicating those numbers in `map-data.js`. Configure `protomaps-leaflet`'s
layer with `maxNativeZoom` set to the header's `maxZoom` (11 for the sample
archive) while the Leaflet map's own `maxZoom` stays higher — Leaflet then reuses
and auto-scales the deepest baked zoom instead of showing blank tiles, the same
`maxNativeZoom`-vs-`maxZoom` split `basemapTiles.js` already relies on today for
the old raster pyramid, and exactly what the spec's Edge Case ("stay usable... at
the deepest available detail") asks for.

**Rationale**: The archive is the single source of truth for its own coverage and
zoom range (Assumptions: "a maintainer supplies one PMTiles file... a sample file
has already been provided" — Edge Case 3 also requires swapping files between runs
to "pick up the new file's coverage without manual cleanup"). Reading the header at
view time means the Python generator never needs to know or duplicate this — it
just copies/embeds the file (§2) — and a maintainer can swap in a differently-scoped
archive without regenerating anything Python-side re-deriving zoom bounds.

## §7. Retiring the OSM raster-tile chunk pyramid and its `tiles/` exemption

**Observation, not yet a code change**: `generate_interactive_map.py`'s
`_ensure_interactive_map_dir` currently exempts `interactive_map/tiles/` from its
per-run wipe specifically so previously-baked OSM raster chunks survive across runs
(a hard rule from prior guidance: never `rmtree` that folder). Once this feature
ships, nothing writes to `tiles/` or reads `<RKBY_DATA_DIR>/.tile_cache/` for the
*interactive* map ever again — `generate_basemap`/`_write_level_tiles` (the only
code that ever populated it) are deleted outright by §5. The exemption becomes
inert: it protects a folder no future run will ever populate or need, on an
existing maintainer's data directory it may still be sitting in from before this
feature.

**Decision** (confirmed with the maintainer, since it overrides established "never
delete `tiles/`" guidance whose original reasoning — protecting expensive,
re-fetchable OSM bakes from accidental loss — no longer applies once nothing bakes
them): remove the `tiles/`-exemption from `_ensure_interactive_map_dir` as part of
this feature's implementation. A one-time cleanup, not a standing policy change —
once this feature ships, `tiles/` is simply never populated again, so any leftover
folder from a pre-PMTiles run is wiped like every other regenerated file on the
next run, rather than silently orphaned forever. This is a tasks.md/
implementation-phase change, not something this plan performs itself.

## §8. Hosted-basemap mode (Story 4, FR-008–FR-011)

**Decision**: One new optional environment variable, `RKBY_BASEMAP_URL`. Unset (the
default): unchanged embedded behavior from §1–§6. Set: the generator skips the
base64-embed step (§2) and instead writes `{"mode": "hosted", "url": "<value>"}`
into `map-data.js`'s `basemap` object (data-model.md); `main.js` then constructs
`new pmtiles.PMTiles("<value>")` — the package's **default, unmodified**
`FetchSource` — rather than the custom Blob-backed `Source` from §2, and passes
that straight to `protomaps-leaflet`'s `leafletLayer({ url })` exactly as in
embedded mode (§1's `url?: PMTiles | string` accepts either).

**Rationale**: §2's `file://` CORS block is specific to the `file` scheme as a
*fetch target* — Chromium's own error message lists `http`/`https` as allowed
target schemes regardless of the requesting page's origin. A `file://`-opened
bundle fetching an `https://` URL is therefore unaffected by §2's finding; it's an
ordinary cross-origin fetch from an opaque (`null`) origin, which works exactly
like any other page embedding a resource from a CDN, provided the host answers
with a permissive CORS header (`Access-Control-Allow-Origin`, wildcard or `null`-
tolerant) — standard for public static-file hosts, and exactly the "maintainer's
own responsibility" scope FR-009/the spec's new Assumption already draws the line
at. This means hosted mode needs **no new library code at all** beyond what §1/§2
already add to the frontend: `pmtiles`'s `FetchSource` is the package's ordinary,
first-class, actively-used path (it's what every *other* PMTiles deployment on the
web already relies on) — the custom `Source` from §2 is what's unusual here, built
specifically to route around `file://`'s restriction that simply doesn't apply
once the target is a real hosted URL.

Env var (not a new CLI flag) matches `RKBY_DATA_DIR`'s existing sole-config-surface
pattern for this script and keeps FR-002 of spec 003 ("no CLI arguments") literally
true — this feature adds a second optional env var alongside it, not a flag.

The local `<RKBY_DATA_DIR>/basemap.pmtiles` file stays required and validated
identically in both modes (FR-010) — hosted mode only changes the *output*
(embed vs. reference-by-URL), never the generation-time input contract. This keeps
exactly one validated local file as ground truth regardless of build variant,
and means the same `basemap.pmtiles` a maintainer already validated locally is
what they separately publish to get the URL hosted mode then references — no
second, ungoverned copy of "the real basemap" to keep in sync by hand.

No new Python or JS dependency: `FetchSource` is already part of the `pmtiles`
package §1 added; the only new code is the small conditional in `bundle.py`
(embed vs. write a URL reference) and in `main.js` (which `Source`/constructor
form to use), both driven by whether `RKBY_BASEMAP_URL` is set.

**Alternatives considered**:
- **A CLI flag instead of an env var** (`--basemap-url`) — rejected: breaks spec
  003's "no CLI arguments" contract for a config value that fits the existing
  env-var surface just as well; no behavioral benefit to a flag here.
- **Generator uploads/deploys the file itself** — rejected per the maintainer's
  explicit choice (spec.md FR-009): a materially bigger feature (hosting-provider
  choice, credentials, deploy pipeline) than a basemap-delivery toggle.
- **Embed as a fallback even in hosted mode** — rejected per the maintainer's
  explicit choice (spec.md Story 4/Edge Cases): keeps two clean, distinct build
  variants rather than a hybrid that both stays large *and* still needs live
  network access to benefit from hosting.
- **Generator verifies the hosted URL is reachable/valid at generation time** —
  rejected: the generator runs before the maintainer has necessarily finished
  publishing the file to that URL (FR-009's manual, out-of-band step could happen
  before or after generation), and the generator has no way to check the target
  host's actual CORS/Range support beyond a single fetch, which would need network
  access at generation time — reintroducing exactly the kind of generation-time
  network dependency FR-002 (unchanged) forbids. Left as a viewer-side failure
  (spec.md Edge Cases: basemap alone fails to render; rest of the map still
  works), consistent with FR-009 putting hosting-target correctness on the
  maintainer.
