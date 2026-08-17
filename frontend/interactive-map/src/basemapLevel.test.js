import { describe, expect, it } from "vitest";
import { pickBasemapLevel } from "./basemapLevel.js";

const LEVELS = [
  { file: "basemap.jpg", scale: 1 },
  { file: "basemap@2x.jpg", scale: 2 },
  { file: "basemap@4x.jpg", scale: 4 },
];

describe("pickBasemapLevel", () => {
  it("picks the base 1x level when zoomed out", () => {
    expect(pickBasemapLevel(LEVELS, -5).file).toBe("basemap.jpg");
    expect(pickBasemapLevel(LEVELS, 1).file).toBe("basemap.jpg");
  });

  it("picks the 2x level once the 2x threshold is reached", () => {
    expect(pickBasemapLevel(LEVELS, 2).file).toBe("basemap@2x.jpg");
    expect(pickBasemapLevel(LEVELS, 3).file).toBe("basemap@2x.jpg");
  });

  it("picks the 4x level once the 4x threshold is reached", () => {
    expect(pickBasemapLevel(LEVELS, 4).file).toBe("basemap@4x.jpg");
    expect(pickBasemapLevel(LEVELS, 5).file).toBe("basemap@4x.jpg");
  });

  it("is independent of the input array's order", () => {
    const shuffled = [LEVELS[2], LEVELS[0], LEVELS[1]];
    expect(pickBasemapLevel(shuffled, 3).file).toBe("basemap@2x.jpg");
  });

  it("falls back to the only available level when higher-resolution levels were never baked", () => {
    const onlyBase = [{ file: "basemap.jpg", scale: 1 }];
    expect(pickBasemapLevel(onlyBase, 5).file).toBe("basemap.jpg");
  });
});
