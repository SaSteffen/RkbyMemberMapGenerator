import { describe, expect, it } from "vitest";
import { declutterPositions } from "./declutter.js";

describe("declutterPositions", () => {
  it("leaves members at merely-nearby (non-identical) positions untouched", () => {
    const members = [
      { matchKey: "a", x: 100, y: 100 },
      { matchKey: "b", x: 100.5, y: 100 },
    ];

    const result = declutterPositions(members);

    expect(result.find((m) => m.matchKey === "a")).toMatchObject({ x: 100, y: 100 });
    expect(result.find((m) => m.matchKey === "b")).toMatchObject({ x: 100.5, y: 100 });
  });

  it("applies a small fixed offset to members sharing an exactly-equal position", () => {
    const members = [
      { matchKey: "a", x: 200, y: 200 },
      { matchKey: "b", x: 200, y: 200 },
    ];

    const result = declutterPositions(members);

    const a = result.find((m) => m.matchKey === "a");
    const b = result.find((m) => m.matchKey === "b");
    expect(a.x).not.toBe(b.x);
    expect(a.y).toBe(200);
    expect(b.y).toBe(200);
  });

  it("keeps every member independently placeable in a group of 3+", () => {
    const members = [
      { matchKey: "a", x: 50, y: 50 },
      { matchKey: "b", x: 50, y: 50 },
      { matchKey: "c", x: 50, y: 50 },
    ];

    const result = declutterPositions(members);

    const xs = result.map((m) => m.x);
    expect(new Set(xs).size).toBe(3);
  });

  it("does not mutate the input array", () => {
    const members = [
      { matchKey: "a", x: 10, y: 10 },
      { matchKey: "b", x: 10, y: 10 },
    ];

    declutterPositions(members);

    expect(members[0].x).toBe(10);
    expect(members[1].x).toBe(10);
  });
});
