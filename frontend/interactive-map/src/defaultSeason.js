// Ported from scripts/scrape_applicants.default_season_label (FR-007,
// research.md §5) -- evaluated at view time using the viewer's own device
// clock, since the artifact is generated once but may be viewed much later.
function computeSeasonLabel(date) {
  const year = date.getFullYear();
  const month = date.getMonth() + 1; // JS months are 0-indexed
  if (month <= 7) return `${year - 1}-${String(year % 100).padStart(2, "0")}`;
  return `${year}-${String((year + 1) % 100).padStart(2, "0")}`;
}

// Falls back to the lexicographically-greatest bundled season label (same
// sort order as discover_seasons) when the computed one isn't present in
// this run's bundled data (FR-007, Edge Cases).
export function defaultSeasonLabel(date, bundledSeasons) {
  const computed = computeSeasonLabel(date);
  if (bundledSeasons.includes(computed)) return computed;
  return [...bundledSeasons].sort().at(-1);
}
