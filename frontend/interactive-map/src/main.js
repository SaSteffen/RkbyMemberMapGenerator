import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { PMTiles } from "pmtiles";
import { leafletLayer } from "protomaps-leaflet";
import { selectBasemapSource } from "./basemapSource.js";
import { ICON_SIZE_PX, declutterPositions } from "./declutter.js";
import { defaultSeasonLabel } from "./defaultSeason.js";
import { computeMemberBounds } from "./memberBounds.js";
import { isVisible, popupData } from "./popupData.js";

// protomaps-leaflet's own compiled bundle references a bare, non-imported
// `L` (built assuming Leaflet is loaded globally via <script>, matching its
// README's own usage example for "legacy Leaflet-based systems",
// research.md §1) -- since this app loads Leaflet as an ES import instead,
// the global has to be set explicitly so protomaps-leaflet's
// `class ... extends L.GridLayer` resolves at the point it constructs its
// layer class.
window.L = L;

// Attribution text sourced from the embedded archive's own JSON metadata
// (output-artifact.md § Attribution) -- pmtiles's own getMetadata(), a
// local in-memory read for the embedded archive, no network request.
async function resolveAttribution(pmtilesArchive) {
  const metadata = await pmtilesArchive.getMetadata();
  return (metadata && metadata.attribution) || "© OpenStreetMap contributors";
}

// Stripped of its "type=module" deferral by vite.config.js's post-build
// step (research.md §10: file://-opened Chromium blocks module script
// loading), this script now runs as soon as the parser reaches it -- which
// can be before both the #map div below it and map-data.js's own <script>
// tag have run. Deferring the real work to DOMContentLoaded restores the
// "runs after the DOM and map-data.js are ready" behavior a module script
// gave us for free, regardless of the two scripts' relative tag order.
async function main() {
  const data = window.RKBY_MAP_DATA;
  // Newest season label bundled in this run, same sort-as-plain-strings
  // order as discover_seasons/merge.py -- used to tell a still-current
  // rookie from a member whose only season is long since over.
  const newestBundledSeason = [...data.seasons].sort().at(-1);

  // Real Web Mercator (Leaflet's own default CRS) -- the basemap is now a
  // real geographic PMTiles archive, addressed by (z, x, y) tile
  // coordinates in standard Web Mercator space, not one baked flat image
  // in an arbitrary pixel space (research.md §5).
  const map = L.map("map", {
    attributionControl: false,
    minZoom: 0,
    maxZoom: 19,
  });

  // research.md §2/§8: embedded mode never fetch()es the .pmtiles file --
  // Chromium blocks fetch()/XHR of a sibling local file when index.html is
  // opened via file://, so its bytes are already in memory (decoded from
  // the base64-embedded classic-script global basemap-pmtiles.js sets),
  // wrapped in a Blob-backed Source with zero network calls. Hosted mode
  // (RKBY_BASEMAP_URL set) instead hands PMTiles a plain URL string, which
  // uses the package's own default FetchSource -- an ordinary cross-origin
  // fetch, unaffected by the file:// restriction above (research.md §8).
  const pmtilesArchive = new PMTiles(selectBasemapSource(data.basemap, window));

  // FR-007: on load, exactly the season considered "current" as of today
  // (the viewer's own device clock) is the sole active one; FR-008: any
  // combination of seasons can be active at once thereafter. Computed here,
  // ahead of the basemap fit below, so the initial view can already be
  // framed around this season's members rather than the whole archive.
  const defaultSeason = defaultSeasonLabel(new Date(), data.seasons);
  const activeSeasons = new Set([defaultSeason]);

  function currentlyVisibleMembers() {
    return data.members.filter((member) => isVisible(member, activeSeasons));
  }

  // Padding (px) around the tightest box containing every visible member,
  // so a marker sitting right on the envelope's edge isn't clipped by the
  // viewport border.
  const MEMBER_FIT_PADDING = [40, 40];

  // Frames the map around exactly the given members -- animated (flyTo) for
  // a season toggle's pan/zoom transition, or a plain jump for the initial
  // load, where there's no prior view to animate from. Returns false
  // without touching the view when there's nothing to frame (e.g. every
  // season just got unchecked), so callers can fall back to some other
  // framing instead.
  function fitToMembers(members, { animate = false } = {}) {
    const bounds = computeMemberBounds(members);
    if (!bounds) return false;
    const latLngBounds = L.latLngBounds(bounds);
    if (animate) {
      map.flyToBounds(latLngBounds, { padding: MEMBER_FIT_PADDING });
    } else {
      map.fitBounds(latLngBounds, { padding: MEMBER_FIT_PADDING });
    }
    return true;
  }

  // research.md §6: the archive is the single source of truth for its own
  // coverage and zoom range -- read at runtime via getHeader() rather than
  // duplicating minZoom/maxZoom/bounds in map-data.js, so a maintainer can
  // swap in a differently-scoped archive without regenerating anything
  // Python-side re-deriving zoom bounds.
  //
  // spec.md Edge Cases (Story 4): an unreachable or invalid RKBY_BASEMAP_URL
  // must degrade only the basemap at view time -- member markers, popups,
  // and season controls still work. getHeader() is this archive's first
  // network round-trip in hosted mode, so it's also the first point such a
  // failure surfaces; without this try/catch an unhandled rejection here
  // would abort the rest of main() before any marker ever renders.
  let attributionText;
  try {
    const header = await pmtilesArchive.getHeader();
    const bounds = L.latLngBounds(
      [header.minLat, header.minLon],
      [header.maxLat, header.maxLon],
    );
    // Frame the default season's members first; only when none are
    // eligible this season (Edge Cases) does the whole archive's coverage
    // area make a better starting view than an arbitrary fallback.
    if (!fitToMembers(currentlyVisibleMembers())) {
      map.fitBounds(bounds);
    }

    // maxNativeZoom (not maxZoom) is set to the header's deepest baked zoom
    // so Leaflet reuses and auto-scales those tiles once a viewer zooms in
    // past it, rather than the basemap going blank (spec.md Edge Cases).
    // flavor: "light" is protomaps-leaflet's ready-made default paint/label
    // style for a standard Protomaps schema (research.md §1) -- with no
    // flavor set, the layer would render nothing.
    leafletLayer({
      url: pmtilesArchive,
      flavor: "light",
      minZoom: header.minZoom,
      maxZoom: map.getMaxZoom(),
      maxNativeZoom: header.maxZoom,
      bounds,
    }).addTo(map);

    attributionText = await resolveAttribution(pmtilesArchive);
  } catch (error) {
    console.error("Basemap failed to load; continuing without it.", error);
    // No archive header to fit to -- fall back to framing the view around
    // the member markers themselves, which are always available locally.
    // Prefer the default season's members; if none are eligible this
    // season, frame every bundled member instead of an arbitrary box.
    if (!fitToMembers(currentlyVisibleMembers()) && !fitToMembers(data.members)) {
      map.setView([0, 0], 2);
    }
    attributionText = "© OpenStreetMap contributors";
  }

  // FR-022, research.md §8: real, always-legible attribution text, never
  // hidden behind a toggle -- Leaflet's own default bottom-right corner.
  L.control
    .attribution({ prefix: false, position: "bottomright" })
    .addAttribution(attributionText)
    .addTo(map);

  // One shared layer group, cleared and rebuilt on every season toggle
  // (FR-008) -- since renderMarkers always draws from the full, already-
  // deduped merged member list, a person eligible in 2+ active seasons is
  // filtered to a single list entry before this ever runs, so it always
  // renders as exactly one marker no matter how many of their seasons are
  // active (merge.py, T013).
  const markersLayer = L.layerGroup().addTo(map);

  // FR-015/FR-016, research.md §6: name + total-season count shown once,
  // one role entry per currently-active season the member belongs to;
  // missing data points render as an explicit "unknown" rather than blank.
  // The popup also shows the member's full (uncropped) photo -- unlike the
  // marker itself, which stays the small square-cropped thumbnail
  // (`member.photo`, bundle.py's HOVER_PHOTO_MAX_PX-capped `photo_full`).
  function renderPopupContent(member) {
    const data = popupData(member, activeSeasons);
    // "1st Season!" only reads as true if that one season is also the
    // newest one bundled -- a member whose sole (and by now lapsed) season
    // was years ago isn't a rookie anymore, just a former one-timer.
    const isCurrentRookie = data.totalSeasons === 1 && data.latestSeason === newestBundledSeason;
    const totalSeasonsText =
      data.totalSeasons === null
        ? "Total Seasons: unknown"
        : isCurrentRookie
          ? "1st Season!"
          : `Total Seasons: ${data.totalSeasons}`;
    const seasonItems = data.seasons
      .map((season) => {
        const roleText = season.role === null ? "unknown" : season.role;
        const additionalRolesText = season.additionalRoles.length
          ? `, ${season.additionalRoles.join(", ")}`
          : "";
        return `<li>${season.label}: ${roleText}${additionalRolesText}</li>`;
      })
      .join("");
    return (
      `<img class="rkby-popup-photo" src="${data.photoFull}" alt="${data.name}" />` +
      `<div class="rkby-popup-name">${data.name}</div>` +
      `<div>${totalSeasonsText}</div>` +
      `<ul class="rkby-popup-seasons">${seasonItems}</ul>`
    );
  }

  // FR-021, research.md §5: overlap is now a function of each member's
  // actual on-screen position under the real CRS, not a precomputed
  // canvas-pixel position scaled by a zoom ratio -- map.latLngToContainerPoint
  // already returns real screen pixels, so declutterPositions runs at its
  // default scale = 1.
  function renderMarkers(members) {
    markersLayer.clearLayers();
    const screenPositioned = members.map((member) => {
      const point = map.latLngToContainerPoint([member.lat, member.lon]);
      return { ...member, x: point.x, y: point.y };
    });
    for (const member of declutterPositions(screenPositioned)) {
      const icon = L.divIcon({
        className: "",
        html: `<img class="rkby-marker-photo" src="${member.photo}" alt="${member.name}" />`,
        iconSize: [ICON_SIZE_PX, ICON_SIZE_PX],
        iconAnchor: [ICON_SIZE_PX / 2, ICON_SIZE_PX / 2],
      });
      const latlng = map.containerPointToLatLng([member.x, member.y]);
      const marker = L.marker(latlng, { icon }).addTo(markersLayer);
      // A manually-managed popup, not marker.bindPopup() -- bindPopup wires
      // its own internal click handler that *toggles* the popup, which on a
      // touch device closes it again immediately: a tap synthesizes
      // mousemove (fires our mouseover below, opening it) then click
      // (toggles it right back closed) as part of the same single tap. This
      // popup instead opens (never toggles) on both mouseover and click, so
      // a tap and a mouse hover behave the same way; Leaflet's own
      // autoClose still closes any previously-open popup when a new one
      // opens, and clicking empty map area still closes it (Map's own
      // default behavior, untouched here). setContent's argument is a
      // function so it's re-evaluated against the live activeSeasons on
      // every open, not frozen at render time -- a toggle can change which
      // of this member's seasons are active between one open and the next
      // without needing a fresh renderMarkers() call.
      const popup = L.popup({ className: "rkby-popup" })
        .setLatLng(latlng)
        .setContent(() => renderPopupContent(member));
      const openPopup = () => popup.openOn(map);
      const closePopup = () => map.closePopup(popup);
      marker.on("mouseover", openPopup);
      marker.on("mouseout", closePopup);
      marker.on("click", openPopup);
    }
  }

  function updateVisibleMarkers() {
    renderMarkers(currentlyVisibleMembers());
  }

  updateVisibleMarkers();

  // Both zoom and pan change every member's on-screen container point (the
  // input declutterPositions now runs on, research.md §5), so both must
  // trigger a re-declutter -- panning alone couldn't change overlap under
  // the old fixed-canvas approach, but it can now.
  map.on("zoomend", updateVisibleMarkers);
  map.on("moveend", updateVisibleMarkers);

  // FR-006/FR-008, research.md §8: one checkbox per bundled season --
  // including seasons with zero eligible members (Edge Cases) -- rendered
  // directly on the map as a Leaflet control (desktop mode).
  const SeasonControl = L.Control.extend({
    options: { position: "topright" },
    onAdd() {
      const container = L.DomUtil.create("div", "rkby-season-control");
      for (const season of data.seasons) {
        const label = L.DomUtil.create("label", "", container);
        const checkbox = L.DomUtil.create("input", "", label);
        checkbox.type = "checkbox";
        checkbox.checked = activeSeasons.has(season);
        L.DomEvent.on(checkbox, "change", () => {
          if (checkbox.checked) {
            activeSeasons.add(season);
          } else {
            activeSeasons.delete(season);
          }
          updateVisibleMarkers();
          // Animated pan/zoom to the new season selection's members; a
          // moveend/zoomend from this re-runs updateVisibleMarkers once the
          // animation settles, correcting decluttering for the final view.
          // Left untouched when nothing is visible (e.g. every season just
          // got unchecked) rather than jumping to some arbitrary framing.
          fitToMembers(currentlyVisibleMembers(), { animate: true });
        });
        label.appendChild(document.createTextNode(` ${season}`));
      }
      L.DomEvent.disableClickPropagation(container);
      return container;
    },
  });
  map.addControl(new SeasonControl());

  // FR-014, research.md §8: a small custom four-direction pan control --
  // Leaflet has no built-in equivalent, and scroll-zoom (centered on the
  // cursor) + click-and-drag pan (FR-013) are already Leaflet's defaults,
  // left enabled here.
  const PAN_STEP_PX = 120;

  const PanControl = L.Control.extend({
    options: { position: "bottomright" },
    onAdd() {
      const container = L.DomUtil.create("div", "rkby-pan-control leaflet-bar");

      const makeButton = (className, label, dx, dy) => {
        const button = L.DomUtil.create("button", className, container);
        button.type = "button";
        button.textContent = label;
        L.DomEvent.on(button, "click", L.DomEvent.stop);
        L.DomEvent.on(button, "click", () => map.panBy([dx, dy]));
        return button;
      };

      makeButton("rkby-pan-up", "↑", 0, -PAN_STEP_PX);
      makeButton("rkby-pan-left", "←", -PAN_STEP_PX, 0);
      makeButton("rkby-pan-right", "→", PAN_STEP_PX, 0);
      makeButton("rkby-pan-down", "↓", 0, PAN_STEP_PX);

      L.DomEvent.disableClickPropagation(container);
      return container;
    },
  });
  map.addControl(new PanControl());
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", main);
} else {
  main();
}
