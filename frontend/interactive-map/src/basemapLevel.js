// Which baked basemap resolution level (bundle.py's BASEMAP_LEVELS,
// research.md §2 addendum) to display for a given Leaflet zoom -- all
// levels cover the identical geographic bounding box at increasing pixel
// density, so swapping which raster backs the imageOverlay (this module's
// job) never needs to touch marker x/y positions or the overlay's bounds.
const ZOOM_THRESHOLD_BY_SCALE = { 1: -Infinity, 2: 2, 4: 4 };

// levels: [{file, scale}], not required to be pre-sorted or complete (a
// tightly-clustered member set may only ever need the base 1x level --
// bundle.py._basemap_levels skips levels a bounding box's own zoom has no
// room for).
export function pickBasemapLevel(levels, zoom) {
  const sorted = [...levels].sort((a, b) => a.scale - b.scale);
  let chosen = sorted[0];
  for (const level of sorted) {
    const threshold = ZOOM_THRESHOLD_BY_SCALE[level.scale] ?? -Infinity;
    if (zoom >= threshold) {
      chosen = level;
    }
  }
  return chosen;
}
