// Pure tile-grid math for the tiled basemap resolution levels (research.md
// §2 addenda) -- kept separate from main.js's Leaflet/DOM glue so it's
// testable without a browser environment.

// data.image.tileLevels entries are {scale, cols, rows} (bundle.py's
// _tile_levels); a level's own Leaflet zoom index is log2(scale) --
// BASEMAP_LEVELS are powers of two, so this is exactly how many times
// finer its chunk grid is than the base (1x) image at CRS.Simple zoom 0.
export function levelForZoom(tileLevels, zoom) {
  return tileLevels.find((level) => Math.log2(level.scale) === zoom) ?? null;
}

// Whether chunk (x, y) is inside a level's baked grid -- Leaflet's GridLayer
// requests tiles past the map's edge as the user pans there, and those must
// resolve to a blank tile rather than a request for a file that was never
// generated.
export function isTileInLevel(level, x, y) {
  return x >= 0 && y >= 0 && x < level.cols && y < level.rows;
}

export function tileUrl(level, x, y) {
  return `tiles/${level.scale}/${x}_${y}.jpg`;
}

// Leaflet's CRS.Simple tile grid is anchored to the *bottom* of the image
// (main.js's pixelToLatLng puts latitude 0 there, and Leaflet's own tile
// math is always anchored to world-Y 0) while our chunk files are
// numbered bottom-up to match (row 0 = bottom-most chunk, see bundle.py's
// _write_level_tiles and research.md §2 2nd addendum for the full
// derivation). A GridLayer tile's y coordinate is always <= -1 for any
// real content, so this is an exact sign-and-offset conversion, not an
// approximation -- getting it backwards would make every requested tile
// straddle two different chunk files instead of landing on one, whenever
// a level's height isn't an exact multiple of the chunk size.
export function chunkRowForTileY(tileY) {
  return -tileY - 1;
}
