import { describe, expect, it } from "vitest";
import { chunkRowForTileY, isTileInLevel, levelForZoom, tileUrl } from "./basemapTiles.js";

const TILE_LEVELS = [
  { scale: 2, cols: 19, rows: 15 },
  { scale: 4, cols: 38, rows: 29 },
  { scale: 16, cols: 150, rows: 113 },
];

describe("levelForZoom", () => {
  it("finds the level whose scale's log2 matches the zoom", () => {
    expect(levelForZoom(TILE_LEVELS, 1)).toEqual({ scale: 2, cols: 19, rows: 15 });
    expect(levelForZoom(TILE_LEVELS, 2)).toEqual({ scale: 4, cols: 38, rows: 29 });
    expect(levelForZoom(TILE_LEVELS, 4)).toEqual({ scale: 16, cols: 150, rows: 113 });
  });

  it("returns null for a zoom with no baked level (e.g. skipped by MAX_OSM_ZOOM capping)", () => {
    expect(levelForZoom(TILE_LEVELS, 3)).toBeNull();
    expect(levelForZoom(TILE_LEVELS, 0)).toBeNull();
    expect(levelForZoom(TILE_LEVELS, 5)).toBeNull();
  });
});

describe("isTileInLevel", () => {
  const level = { scale: 4, cols: 3, rows: 2 };

  it("accepts coordinates inside the grid, including the edges", () => {
    expect(isTileInLevel(level, 0, 0)).toBe(true);
    expect(isTileInLevel(level, 2, 1)).toBe(true);
  });

  it("rejects negative coordinates", () => {
    expect(isTileInLevel(level, -1, 0)).toBe(false);
    expect(isTileInLevel(level, 0, -1)).toBe(false);
  });

  it("rejects coordinates at or past cols/rows", () => {
    expect(isTileInLevel(level, 3, 0)).toBe(false);
    expect(isTileInLevel(level, 0, 2)).toBe(false);
  });
});

describe("tileUrl", () => {
  it("builds a path from the level's scale and the chunk's grid position", () => {
    expect(tileUrl({ scale: 4, cols: 3, rows: 2 }, 1, 0)).toBe("tiles/4/1_0.jpg");
  });
});

describe("chunkRowForTileY", () => {
  it("converts Leaflet's bottom-anchored tile y into our bottom-up chunk row", () => {
    // -1 is the tile immediately above the image's bottom edge (world-Y 0)
    // -- that's chunk row 0 in bundle.py's _write_level_tiles numbering.
    expect(chunkRowForTileY(-1)).toBe(0);
    expect(chunkRowForTileY(-2)).toBe(1);
    expect(chunkRowForTileY(-3)).toBe(2);
  });

  it("is its own inverse (row 0 <-> tile y -1, etc)", () => {
    for (const row of [0, 1, 2, 5]) {
      const tileY = -row - 1;
      expect(chunkRowForTileY(tileY)).toBe(row);
    }
  });
});
