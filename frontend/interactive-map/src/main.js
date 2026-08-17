import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { declutterPositions } from "./declutter.js";
import { defaultSeasonLabel } from "./defaultSeason.js";

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
  L.imageOverlay(data.image.file, bounds).addTo(map);
  map.fitBounds(bounds);

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

  function renderMarkers(members) {
    const declutteredMembers = declutterPositions(members);
    for (const member of declutteredMembers) {
      const icon = L.divIcon({
        className: "",
        html: `<img class="rkby-marker-photo" src="${member.photo}" alt="${member.name}" />`,
        iconSize: [40, 40],
        iconAnchor: [20, 20],
      });
      L.marker(pixelToLatLng(member.x, member.y), { icon }).addTo(map);
    }
  }

  // FR-007: on load, exactly the season considered "current" as of today
  // (the viewer's own device clock) is active.
  const defaultSeason = defaultSeasonLabel(new Date(), data.seasons);
  const defaultSeasonMembers = data.members.filter(
    (member) => member.seasons[defaultSeason] !== undefined,
  );
  renderMarkers(defaultSeasonMembers);

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
