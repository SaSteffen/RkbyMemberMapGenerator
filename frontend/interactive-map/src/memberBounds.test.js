import { describe, expect, it } from "vitest";
import { computeMemberBounds } from "./memberBounds.js";

describe("computeMemberBounds", () => {
  it("returns null for an empty member list", () => {
    expect(computeMemberBounds([])).toBeNull();
  });

  it("returns a zero-size box around a single member", () => {
    const members = [{ lat: 53.55, lon: 10.0 }];
    expect(computeMemberBounds(members)).toEqual([
      [53.55, 10.0],
      [53.55, 10.0],
    ]);
  });

  it("returns the min/max envelope across several members", () => {
    const members = [
      { lat: 53.55, lon: 10.0 },
      { lat: 53.6, lon: 9.9 },
      { lat: 53.5, lon: 10.2 },
    ];
    expect(computeMemberBounds(members)).toEqual([
      [53.5, 9.9],
      [53.6, 10.2],
    ]);
  });

  it("ignores unrelated member fields", () => {
    const members = [{ lat: 1, lon: 2, name: "Jane Doe", photo: "x.jpg" }];
    expect(computeMemberBounds(members)).toEqual([
      [1, 2],
      [1, 2],
    ]);
  });
});
