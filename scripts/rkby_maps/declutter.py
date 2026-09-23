"""Marker-overlap decluttering: the Python port of the interactive map's own
`frontend/interactive-map/src/declutter.js`, so the static maps lay an
overlapping group out exactly the way the interactive one does -- a compact
grid centered on the group's shared position, every member keeping their own
full-size marker.

It replaces the static maps' original overlap fallbacks (a merged pin with a
multiplicity badge; a row of photo circles each offset by a fraction of a
diameter, so every face but the last was partly covered): both hid who was
actually there, which is the one thing these maps exist to show.

The pixel positions this works on are `pin_map.pixel_positions` output --
already projected onto one map's own canvas at its own zoom -- which is the
static-render equivalent of the browser's `map.latLngToContainerPoint`, so
no separate scale factor is needed here (declutter.js's `scale` parameter
exists only because the browser re-declutters live at every zoom level)."""

from __future__ import annotations

import math

from scripts.rkby_maps.clustering import find_overlap_groups


def declutter_positions(
    positions: dict[str, tuple[float, float]], marker_radius: float
) -> tuple[dict[str, tuple[float, float]], list[list[str]]]:
    """Positions to actually draw markers at, plus the overlap groups found
    on the way there (callers need those anyway -- to decide which detail
    maps to generate -- and computing them once keeps the two from ever
    disagreeing about what overlaps).

    Members with no overlapping partner keep their exact projected position;
    each overlap group is packed into a grid around its own centroid
    instead. The input mapping is never modified."""
    groups = find_overlap_groups(positions, radius=marker_radius)

    decluttered = dict(positions)
    for group in groups:
        packed = _pack_group(
            [positions[key] for key in group], spacing=2 * marker_radius
        )
        decluttered.update(zip(group, packed))
    return decluttered, groups


def _pack_group(
    group_positions: list[tuple[float, float]], spacing: float
) -> list[tuple[float, float]]:
    """Space-saving square-ish grid -- not a single-direction row -- centered
    on the group's own centroid, with cell spacing equal to the overlap
    threshold: the minimum gap that guarantees no two members of the group
    still overlap each other once rearranged."""
    count = len(group_positions)
    center_x = sum(x for x, _y in group_positions) / count
    center_y = sum(y for _x, y in group_positions) / count

    columns = math.ceil(math.sqrt(count))
    rows = math.ceil(count / columns)
    start_x = center_x - (columns - 1) * spacing / 2
    start_y = center_y - (rows - 1) * spacing / 2

    return [
        (start_x + (index % columns) * spacing, start_y + (index // columns) * spacing)
        for index in range(count)
    ]
