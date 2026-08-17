import { describe, expect, it } from "vitest";
import { defaultSeasonLabel } from "./defaultSeason.js";

describe("defaultSeasonLabel", () => {
  it("returns the previous August's season for a date in July", () => {
    expect(defaultSeasonLabel(new Date(2025, 6, 31), ["2024-25", "2025-26"])).toBe("2024-25");
  });

  it("returns this August's season for a date in August", () => {
    expect(defaultSeasonLabel(new Date(2025, 7, 1), ["2024-25", "2025-26"])).toBe("2025-26");
  });

  it("rolls over the year boundary correctly", () => {
    expect(defaultSeasonLabel(new Date(2026, 0, 15), ["2024-25", "2025-26"])).toBe("2025-26");
  });

  it("falls back to the lexicographically-greatest bundled season when the computed one is absent", () => {
    // Computed label would be "2025-26", but only older seasons are bundled.
    expect(defaultSeasonLabel(new Date(2026, 0, 15), ["2022-23", "2023-24", "2024-25"])).toBe(
      "2024-25",
    );
  });

  it("returns the computed label when it is present, even if not the greatest", () => {
    expect(
      defaultSeasonLabel(new Date(2025, 6, 31), ["2023-24", "2024-25", "2025-26"]),
    ).toBe("2024-25");
  });
});
