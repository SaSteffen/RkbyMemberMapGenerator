// Same-exact-coordinate marker decluttering (FR-021, research.md §7) -- the
// Leaflet-marker-position counterpart of scripts/rkby_maps/rendering.py's
// draw_offset_photo_circles/PHOTO_OFFSET_FRACTION for the static photo map's
// FR-014 exception. Because this runs on already-projected pixel positions,
// "exactly equal" is a plain numeric equality check: two distinct real
// addresses essentially never project to byte-identical pixel floats, and an
// identical address always will.
const OFFSET_PX = 12;

export function declutterPositions(members) {
  const groups = new Map();
  for (const member of members) {
    const key = `${member.x},${member.y}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(member);
  }

  const result = [];
  for (const group of groups.values()) {
    if (group.length === 1) {
      result.push({ ...group[0] });
      continue;
    }
    group.forEach((member, index) => {
      result.push({ ...member, x: member.x + index * OFFSET_PX });
    });
  }
  return result;
}
