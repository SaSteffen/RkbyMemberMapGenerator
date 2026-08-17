import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { chunkRowForTileY, isTileInLevel, levelForZoom, tileUrl } from "./basemapTiles.js";
import { ICON_SIZE_PX, declutterPositions } from "./declutter.js";
import { defaultSeasonLabel } from "./defaultSeason.js";
import { isVisible, popupData } from "./popupData.js";

// Renders the tiled higher-resolution basemap levels (research.md §2
// addenda): each `createTile` call resolves to one small, independently
// cached/lazily-loaded chunk file instead of one giant per-level image, so
// however deep the zoom goes only the handful of chunks actually on
// screen are ever fetched. The base (1x) level stays a single always-
// mounted L.imageOverlay underneath this layer -- small enough (research.md
// §2) that it needs no chunking, and it's what's visible at zoom levels
// below this layer's own minZoom (no baked tiles exist that far out).
const BasemapTileLayer = L.GridLayer.extend({
  createTile(coords, done) {
    const img = document.createElement("img");
    const level = levelForZoom(this.options.tileLevels, coords.z);
    const row = chunkRowForTileY(coords.y);
    if (!level || !isTileInLevel(level, coords.x, row)) {
      // Past the baked grid's edge (the user panned beyond map bounds) or
      // this zoom has no tiled level -- a blank tile, never a request for
      // a chunk file that was never generated.
      done(null, img);
      return img;
    }
    img.onload = () => done(null, img);
    img.onerror = () => done(new Error(`basemap tile failed to load: ${img.src}`), img);
    img.src = tileUrl(level, coords.x, row);
    return img;
  },
});

// Stripped of its "type=module" deferral by vite.config.js's post-build
// step (research.md §10: file://-opened Chromium blocks module script
// loading), this script now runs as soon as the parser reaches it -- which
// can be before both the #map div below it and map-data.js's own <script>
// tag have run. Deferring the real work to DOMContentLoaded restores the
// "runs after the DOM and map-data.js are ready" behavior a module script
// gave us for free, regardless of the two scripts' relative tag order.
function main() {
  const data = window.RKBY_MAP_DATA;
  const imageWidth = data.image.width;
  const imageHeight = data.image.height;

  // L.CRS.Simple treats the basemap image's own pixel space as the map's
  // coordinate system -- there are no live geographic tiles to align to
  // (research.md §2, §3), so a plain image overlay + precomputed pixel
  // positions is simpler than a geographic CRS.
  const map = L.map("map", {
    crs: L.CRS.Simple,
    minZoom: -5,
    maxZoom: 5,
    attributionControl: false,
  });

  const bounds = [
    [0, 0],
    [imageHeight, imageWidth],
  ];
  map.fitBounds(bounds);

  // Always-present base layer (research.md §2): one small flattened image,
  // visible at every zoom, and the only thing shown below the tiled
  // levels' own minZoom (i.e. zoomed out further than any baked tile
  // grid covers).
  L.imageOverlay(data.image.file, bounds).addTo(map);

  // Tiled higher-resolution levels (research.md §2 addenda) layer on top,
  // only across the zoom range they were actually baked for -- Leaflet
  // hides a GridLayer entirely outside its own minZoom/maxZoom, so at
  // zooms below this the base imageOverlay above is what's visible.
  //
  // pane: "overlayPane" is required, not cosmetic -- L.imageOverlay
  // defaults to Leaflet's own "overlayPane" (z-index 400), while a plain
  // GridLayer defaults to "tilePane" (z-index 200), a *lower* stacking
  // context. Without this, the always-present base image silently paints
  // over every tile regardless of zoom or how correctly the tiles
  // themselves load -- exactly what happened here (only ever "the
  // overview" was visible) until caught in a real browser, since a
  // same-content test fixture made the two layers visually identical.
  const tileZooms = data.image.tileLevels.map((level) => Math.log2(level.scale));
  if (tileZooms.length > 0) {
    new BasemapTileLayer({
      tileLevels: data.image.tileLevels,
      tileSize: data.image.tileSize,
      minZoom: Math.min(...tileZooms),
      maxZoom: Math.max(...tileZooms),
      bounds,
      pane: "overlayPane",
    }).addTo(map);
  }

  // FR-022, research.md §8: real, always-legible attribution text, never
  // hidden behind a toggle -- Leaflet's own default bottom-right corner.
  L.control
    .attribution({ prefix: false, position: "bottomright" })
    .addAttribution("© OpenStreetMap contributors")
    .addTo(map);

  // Leaflet's "latitude" increases upward while the image's pixel rows
  // increase downward (CRS.Simple convention, research.md §3) -- y is
  // negated relative to the raw pixel y computed at generation time.
  function pixelToLatLng(x, y) {
    return L.latLng(imageHeight - y, x);
  }

  // One shared layer group, cleared and rebuilt on every season toggle
  // (FR-008) -- since renderMarkers always draws from the full, already-
  // deduped merged member list, a person eligible in 2+ active seasons is
  // filtered to a single list entry before this ever runs, so it always
  // renders as exactly one marker no matter how many of their seasons are
  // active (merge.py, T013).
  const markersLayer = L.layerGroup().addTo(map);

  // FR-015/FR-016, research.md §6: name + previous-season count shown once,
  // one role entry per currently-active season the member belongs to;
  // missing data points render as an explicit "unknown" rather than blank.
  function renderPopupContent(member) {
    const data = popupData(member, activeSeasons);
    const previousSeasonsText =
      data.numPreviousSeasons === null ? "unknown" : String(data.numPreviousSeasons);
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
      `<div class="rkby-popup-name">${data.name}</div>` +
      `<div>Previous seasons: ${previousSeasonsText}</div>` +
      `<ul class="rkby-popup-seasons">${seasonItems}</ul>`
    );
  }

  function renderMarkers(members) {
    markersLayer.clearLayers();
    // Overlap is a screen-pixel concept (declutter.js), so the current
    // zoom's world-to-screen scale has to be passed in every time this
    // runs -- the same members can be non-overlapping at one zoom and
    // overlapping at another.
    const scale = map.getZoomScale(map.getZoom(), 0);
    const declutteredMembers = declutterPositions(members, scale);
    for (const member of declutteredMembers) {
      const icon = L.divIcon({
        className: "",
        html: `<img class="rkby-marker-photo" src="${member.photo}" alt="${member.name}" />`,
        iconSize: [ICON_SIZE_PX, ICON_SIZE_PX],
        iconAnchor: [ICON_SIZE_PX / 2, ICON_SIZE_PX / 2],
      });
      const marker = L.marker(pixelToLatLng(member.x, member.y), { icon }).addTo(markersLayer);
      // bindPopup's content is a function so it's re-evaluated against the
      // live activeSeasons on every open, not frozen at render time -- a
      // toggle can change which of this member's seasons are active between
      // one hover and the next without needing a fresh renderMarkers() call.
      marker.bindPopup(() => renderPopupContent(member), { className: "rkby-popup" });
      marker.on("mouseover", () => marker.openPopup());
      marker.on("mouseout", () => marker.closePopup());
    }
  }

  // FR-007: on load, exactly the season considered "current" as of today
  // (the viewer's own device clock) is the sole active one; FR-008: any
  // combination of seasons can be active at once thereafter.
  const defaultSeason = defaultSeasonLabel(new Date(), data.seasons);
  const activeSeasons = new Set([defaultSeason]);

  function updateVisibleMarkers() {
    renderMarkers(data.members.filter((member) => isVisible(member, activeSeasons)));
  }

  updateVisibleMarkers();

  // FR-021, research.md §7: which members' icons overlap on screen depends
  // on the current zoom (declutter.js), so a zoom change can both create
  // new overlaps (zooming out) and resolve old ones (zooming in) -- markers
  // are re-decluttered from their original coordinates on every zoom change
  // rather than nudged incrementally, since re-running declutterPositions
  // is cheap and avoids compounding rounding drift across many zoom steps.
  map.on("zoomend", updateVisibleMarkers);

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
