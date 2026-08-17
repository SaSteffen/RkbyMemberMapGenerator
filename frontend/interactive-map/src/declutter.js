// Marker-overlap decluttering (FR-021, research.md §7) -- whenever two or
// more member photo markers would visually overlap on screen at the current
// zoom, they're rearranged into a compact non-overlapping grid centered on
// their shared position, instead of rendering as a single unreadable stack.
//
// "Overlap" is a function of on-screen pixel distance, not raw world
// distance: main.js's L.CRS.Simple map scales world-coordinate distance by
// `scale` (2^zoom) to get screen pixels, so the world-space distance two
// icons can be apart and still visually collide shrinks as the viewer zooms
// in and grows as they zoom out. Positions are therefore recomputed from the
// original member coordinates on every zoom change (main.js's `zoomend`
// handler calls this again with the new scale) rather than once at load --
// a fixed offset chosen for one zoom would drift apart (zoom in) or fail to
// separate overlapping-but-distinct members (zoom out) at any other zoom.
export const ICON_SIZE_PX = 40; // must match main.js's L.divIcon iconSize

export function declutterPositions(members, scale = 1) {
  const threshold = ICON_SIZE_PX / scale;
  const groups = clusterByProximity(members, threshold);

  const result = [];
  for (const group of groups) {
    if (group.length === 1) {
      result.push({ ...group[0] });
      continue;
    }
    result.push(...packGroup(group, threshold));
  }
  return result;
}

// Union-find over every pair closer than `threshold`: a marker that doesn't
// directly overlap a given one, but is close enough to a third marker that
// does, still joins the same group -- so the group as a whole ends up
// mutually non-overlapping instead of leaving an unresolved pairwise
// collision at the edge of a chain.
function clusterByProximity(members, threshold) {
  const parent = members.map((_, index) => index);
  function find(index) {
    while (parent[index] !== index) {
      parent[index] = parent[parent[index]];
      index = parent[index];
    }
    return index;
  }
  function union(a, b) {
    const rootA = find(a);
    const rootB = find(b);
    if (rootA !== rootB) parent[rootA] = rootB;
  }

  for (let i = 0; i < members.length; i++) {
    for (let j = i + 1; j < members.length; j++) {
      const dx = members[i].x - members[j].x;
      const dy = members[i].y - members[j].y;
      if (Math.hypot(dx, dy) < threshold) union(i, j);
    }
  }

  const groups = new Map();
  members.forEach((member, index) => {
    const root = find(index);
    if (!groups.has(root)) groups.set(root, []);
    groups.get(root).push(member);
  });
  return [...groups.values()];
}

// Space-saving square-ish grid -- not a single-direction line -- centered
// on the group's own centroid, with cell spacing equal to the overlap
// threshold: the minimum gap that guarantees no two members in the group
// still overlap each other once rearranged.
function packGroup(group, spacing) {
  const centerX = group.reduce((sum, member) => sum + member.x, 0) / group.length;
  const centerY = group.reduce((sum, member) => sum + member.y, 0) / group.length;
  const cols = Math.ceil(Math.sqrt(group.length));
  const rows = Math.ceil(group.length / cols);
  const startX = centerX - ((cols - 1) * spacing) / 2;
  const startY = centerY - ((rows - 1) * spacing) / 2;

  return group.map((member, index) => ({
    ...member,
    x: startX + (index % cols) * spacing,
    y: startY + Math.floor(index / cols) * spacing,
  }));
}
