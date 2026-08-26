// Bounding box of a list of members' coordinates -- used to frame the map
// around exactly the members visible for the active season(s), both on
// initial load and after every season toggle. Returns null for an empty
// list (nothing to frame) and Leaflet's own LatLngBoundsLiteral shape
// otherwise so main.js can hand the result straight to L.latLngBounds.
export function computeMemberBounds(members) {
  if (members.length === 0) return null;

  let minLat = Infinity;
  let maxLat = -Infinity;
  let minLon = Infinity;
  let maxLon = -Infinity;
  for (const member of members) {
    if (member.lat < minLat) minLat = member.lat;
    if (member.lat > maxLat) maxLat = member.lat;
    if (member.lon < minLon) minLon = member.lon;
    if (member.lon > maxLon) maxLon = member.lon;
  }
  return [
    [minLat, minLon],
    [maxLat, maxLon],
  ];
}
