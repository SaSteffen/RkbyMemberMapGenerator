// Season-visibility filtering shared by the desktop hover popup and the
// mobile drawer (FR-006, research.md §6) -- a member is visible whenever at
// least one season they have an eligible record in is currently active.
export function isVisible(member, activeSeasons) {
  return Object.keys(member.seasons).some((season) => activeSeasons.has(season));
}

// Popup/drawer content shared by the desktop hover popup and the mobile
// drawer (FR-015/FR-016, research.md §6) -- restricted to just the
// currently-active seasons this member has an entry for, sorted by season
// label so multi-season role history reads chronologically.
export function popupData(member, activeSeasons) {
  const seasons = Object.keys(member.seasons)
    .filter((label) => activeSeasons.has(label))
    .sort()
    .map((label) => ({
      label,
      role: member.seasons[label].role,
      additionalRoles: member.seasons[label].additional_roles,
    }));
  return {
    name: member.name,
    numPreviousSeasons: member.num_previous_seasons,
    photoFull: member.photo_full,
    seasons,
  };
}
