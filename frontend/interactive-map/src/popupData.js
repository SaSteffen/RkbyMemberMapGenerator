// Season-visibility filtering shared by the desktop hover popup and the
// mobile drawer (FR-006, research.md §6) -- a member is visible whenever at
// least one season they have an eligible record in is currently active.
export function isVisible(member, activeSeasons) {
  return Object.keys(member.seasons).some((season) => activeSeasons.has(season));
}
