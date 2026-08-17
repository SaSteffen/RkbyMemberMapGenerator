import { describe, expect, it } from "vitest";
import { isVisible, popupData } from "./popupData.js";

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

describe("popupData", () => {
  it("restricts seasons to the active set, sorted by label", () => {
    const member = {
      name: "Jane Doe",
      num_previous_seasons: 3,
      photo_full: "photos/jane-doe-full.jpg",
      seasons: {
        "2025-26": { role: "Service Crew", additional_roles: [] },
        "2023-24": { role: "Rider", additional_roles: ["Steering Committee"] },
        "2024-25": { role: "Rider", additional_roles: [] },
      },
    };
    expect(popupData(member, new Set(["2025-26", "2023-24"]))).toEqual({
      name: "Jane Doe",
      numPreviousSeasons: 3,
      photoFull: "photos/jane-doe-full.jpg",
      seasons: [
        { label: "2023-24", role: "Rider", additionalRoles: ["Steering Committee"] },
        { label: "2025-26", role: "Service Crew", additionalRoles: [] },
      ],
    });
  });

  it("excludes seasons the member has no entry for, even if active", () => {
    const member = {
      name: "Jane Doe",
      num_previous_seasons: 1,
      photo_full: "photos/jane-doe-full.jpg",
      seasons: { "2024-25": { role: "Rider", additional_roles: [] } },
    };
    expect(popupData(member, new Set(["2024-25", "2025-26"]))).toEqual({
      name: "Jane Doe",
      numPreviousSeasons: 1,
      photoFull: "photos/jane-doe-full.jpg",
      seasons: [{ label: "2024-25", role: "Rider", additionalRoles: [] }],
    });
  });

  it("returns an empty seasons array when none of the member's seasons are active", () => {
    const member = {
      name: "Jane Doe",
      num_previous_seasons: 1,
      photo_full: "photos/jane-doe-full.jpg",
      seasons: { "2024-25": { role: "Rider", additional_roles: [] } },
    };
    expect(popupData(member, new Set(["2025-26"]))).toEqual({
      name: "Jane Doe",
      numPreviousSeasons: 1,
      photoFull: "photos/jane-doe-full.jpg",
      seasons: [],
    });
  });

  it("passes num_previous_seasons through as null when not on file", () => {
    const member = {
      name: "Jane Doe",
      num_previous_seasons: null,
      photo_full: "photos/jane-doe-full.jpg",
      seasons: { "2024-25": { role: "Rider", additional_roles: [] } },
    };
    expect(popupData(member, new Set(["2024-25"])).numPreviousSeasons).toBeNull();
  });

  it("passes role through as null when not on file", () => {
    const member = {
      name: "Jane Doe",
      num_previous_seasons: 1,
      photo_full: "photos/jane-doe-full.jpg",
      seasons: { "2024-25": { role: null, additional_roles: [] } },
    };
    expect(popupData(member, new Set(["2024-25"])).seasons).toEqual([
      { label: "2024-25", role: null, additionalRoles: [] },
    ]);
  });

  it("passes photo_full through as photoFull, for the hover popup's full picture", () => {
    const member = {
      name: "Jane Doe",
      num_previous_seasons: 1,
      photo_full: "photos/jane-doe-full.jpg",
      seasons: { "2024-25": { role: "Rider", additional_roles: [] } },
    };
    expect(popupData(member, new Set(["2024-25"])).photoFull).toBe(
      "photos/jane-doe-full.jpg"
    );
  });
});
