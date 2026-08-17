import { describe, expect, it } from "vitest";
import { ICON_SIZE_PX, declutterPositions } from "./declutter.js";

describe("declutterPositions", () => {
  it("leaves members farther apart than the overlap threshold untouched", () => {
    const members = [
      { matchKey: "a", x: 100, y: 100 },
      { matchKey: "b", x: 100 + ICON_SIZE_PX * 2, y: 100 },
    ];

    const result = declutterPositions(members);

    expect(result.find((m) => m.matchKey === "a")).toMatchObject({ x: 100, y: 100 });
    expect(result.find((m) => m.matchKey === "b")).toMatchObject({
      x: 100 + ICON_SIZE_PX * 2,
      y: 100,
    });
  });

  it("rearranges members whose icons overlap at the given scale", () => {
    const members = [
      { matchKey: "a", x: 200, y: 200 },
      { matchKey: "b", x: 200, y: 200 },
    ];

    const result = declutterPositions(members, 1);

    const a = result.find((m) => m.matchKey === "a");
    const b = result.find((m) => m.matchKey === "b");
    expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeGreaterThanOrEqual(ICON_SIZE_PX);
  });

  it("packs an overlapping group into a compact grid, not a single line", () => {
    const members = [
      { matchKey: "a", x: 50, y: 50 },
      { matchKey: "b", x: 50, y: 50 },
      { matchKey: "c", x: 50, y: 50 },
      { matchKey: "d", x: 50, y: 50 },
    ];

    const result = declutterPositions(members, 1);

    // A space-saving grid uses both axes; a single-direction line would not.
    expect(new Set(result.map((m) => m.x)).size).toBeGreaterThan(1);
    expect(new Set(result.map((m) => m.y)).size).toBeGreaterThan(1);
  });

  it("keeps every member in a group of 3+ pairwise non-overlapping", () => {
    const members = [
      { matchKey: "a", x: 50, y: 50 },
      { matchKey: "b", x: 50, y: 50 },
      { matchKey: "c", x: 50, y: 50 },
    ];

    const result = declutterPositions(members, 1);

    for (let i = 0; i < result.length; i++) {
      for (let j = i + 1; j < result.length; j++) {
        const distance = Math.hypot(result[i].x - result[j].x, result[i].y - result[j].y);
        expect(distance).toBeGreaterThanOrEqual(ICON_SIZE_PX);
      }
    }
  });

  it("re-declutters the same members differently depending on zoom scale", () => {
    const members = [
      { matchKey: "a", x: 100, y: 100 },
      { matchKey: "b", x: 120, y: 100 },
    ];

    // Zoomed in (scale 4): overlap threshold is 10px, 20px apart is fine.
    const zoomedIn = declutterPositions(members, 4);
    expect(zoomedIn.find((m) => m.matchKey === "a")).toMatchObject({ x: 100, y: 100 });
    expect(zoomedIn.find((m) => m.matchKey === "b")).toMatchObject({ x: 120, y: 100 });

    // Zoomed out (scale 0.25): overlap threshold is 160px, 20px apart collides.
    const zoomedOut = declutterPositions(members, 0.25);
    const a = zoomedOut.find((m) => m.matchKey === "a");
    const b = zoomedOut.find((m) => m.matchKey === "b");
    expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeGreaterThanOrEqual(ICON_SIZE_PX / 0.25);
  });

  it("does not mutate the input array", () => {
    const members = [
      { matchKey: "a", x: 10, y: 10 },
      { matchKey: "b", x: 10, y: 10 },
    ];

    declutterPositions(members, 1);

    expect(members[0].x).toBe(10);
    expect(members[1].x).toBe(10);
  });
});
