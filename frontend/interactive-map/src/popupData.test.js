import { describe, expect, it } from "vitest";
import { isVisible } from "./popupData.js";

describe("isVisible", () => {
  it("is true when the member's only season is active", () => {
    const member = { seasons: { "2024-25": { role: "Rider", additional_roles: [] } } };
    expect(isVisible(member, new Set(["2024-25"]))).toBe(true);
  });

  it("is true when only one of several seasons the member belongs to is active", () => {
    const member = {
      seasons: {
        "2023-24": { role: "Rider", additional_roles: [] },
        "2024-25": { role: "Service Crew", additional_roles: [] },
      },
    };
    expect(isVisible(member, new Set(["2024-25", "2025-26"]))).toBe(true);
  });

  it("is false when none of the member's seasons are active", () => {
    const member = { seasons: { "2023-24": { role: "Rider", additional_roles: [] } } };
    expect(isVisible(member, new Set(["2024-25", "2025-26"]))).toBe(false);
  });

  it("is false when no seasons are active at all", () => {
    const member = { seasons: { "2024-25": { role: "Rider", additional_roles: [] } } };
    expect(isVisible(member, new Set())).toBe(false);
  });
});
