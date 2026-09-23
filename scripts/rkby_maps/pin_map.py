"""Shared pin-map rendering plumbing (research.md Decision 2, FR-004):
promoted out of `generate_member_maps.py`'s (002) private helpers so a
second caller -- `rkby_pairing/maps.py` (007) -- renders its cluster/
overview maps through the exact same overlap-aware pin/frame logic instead
of a lookalike reimplementation.

Marker placement and map membership here now follow the interactive map's
own rules rather than the static maps' original ones: overlapping members
are decluttered into a grid (`rkby_maps.declutter`) instead of merged into
one badged pin, and framing keeps a fixed pixel margin free around the
bounding box (`FRAME_PADDING_PX`, mirroring Leaflet fitBounds padding)
instead of dropping members who land near the canvas edge."""

from __future__ import annotations

from scripts.rkby_maps.basemap import (
    lonlat_to_pixel,
    zoom_for_bounding_box,
    zoom_for_min_width_km,
)
from scripts.rkby_maps.declutter import declutter_positions
from scripts.rkby_maps.rendering import (
    PHOTO_DIAMETER_PX,
    PIN_RADIUS_PX,
    RESOLUTION_SCALE,
    draw_pin,
    role_color,
)

DEFAULT_MIN_WIDTH_KM = 15
CANVAS_SIZE = (1600 * RESOLUTION_SCALE, 1200 * RESOLUTION_SCALE)
# Geographic center of Germany -- used only as the overview map's center for
# a degenerate (empty) member set.
DEFAULT_CENTER = (51.1657, 10.4515)
# Pixel margin kept free around a bounding box -- of either an overlap group
# (cluster/detail maps) or a full member set (an overview) -- before
# flooring the result at --min-width-km, so a member sitting on the box's
# own edge still gets their whole marker drawn inside the canvas. One full
# photo circle (the larger of the two marker kinds, so pin and photo maps
# stay identically framed) mirrors the interactive map's own one-marker
# fitBounds padding (main.js MEMBER_FIT_PADDING == ICON_SIZE_PX).
FRAME_PADDING_PX = PHOTO_DIAMETER_PX


def pixel_positions(
    records: list[dict], center: tuple[float, float], zoom: int
) -> dict[str, tuple[float, float]]:
    return {
        record["match_key"]: lonlat_to_pixel(
            record["latitude"],
            record["longitude"],
            center=center,
            zoom=zoom,
            canvas_size=CANVAS_SIZE,
        )
        for record in records
    }


def records_within_frame(
    records: list[dict],
    always_include: set[str],
    center: tuple[float, float],
    zoom: int,
    canvas_size: tuple[int, int],
) -> list[dict]:
    """Every plottable member who actually lands inside a map's rendered
    frame at `(center, zoom)`, not just the group that triggered it.
    `always_include` members (the triggering group) are kept regardless of
    where they land, since they define the frame itself.

    Landing on the canvas at all is the whole test -- the same rule the
    interactive map applies, where every member inside the viewport is
    rendered no matter how close to its border they sit. Members near the
    edge used to be dropped here to avoid drawing them clipped; framing now
    keeps `FRAME_PADDING_PX` free around the box the map is built from
    instead, which is the actual cause of that clipping, so a member who is
    on this map has no reason to be left off it."""
    canvas_width, canvas_height = canvas_size
    positions = pixel_positions(records, center, zoom)
    selected = []
    for record in records:
        key = record["match_key"]
        x, y = positions[key]
        in_frame = 0 <= x <= canvas_width and 0 <= y <= canvas_height
        if key in always_include or in_frame:
            selected.append(record)
    return selected


def render_pin_layer(
    canvas, records: list[dict], center: tuple[float, float], zoom: int
) -> tuple[list[list[str]], dict[str, dict]]:
    """Draw one role-colored pin per record -- members overlapping at this
    canvas's own scale are decluttered into a grid around their shared
    position (`rkby_maps.declutter`, as on the interactive map) rather than
    collapsed into a single merged marker, so no member is ever hidden
    behind another. Returns the detected overlap groups (which still decide
    which detail maps get generated) plus a match_key -> record lookup."""
    by_key = {record["match_key"]: record for record in records}
    positions = pixel_positions(records, center, zoom)
    drawn_positions, groups = declutter_positions(
        positions, marker_radius=PIN_RADIUS_PX
    )

    for key, record in by_key.items():
        draw_pin(canvas, drawn_positions[key], color=role_color(record.get("role")))

    return groups, by_key


def overview_center_and_zoom(
    members: list[dict], min_width_km: float
) -> tuple[tuple[float, float], int]:
    """The overview's own bounding box (all of `members`, plus a
    `FRAME_PADDING_PX` margin), floored at `min_width_km` -- a nationally-
    spread team renders wider than the configured minimum so everyone fits,
    while a tight regional team is floored at the minimum. An empty
    `members` falls back to `DEFAULT_CENTER` at the `min_width_km` floor's
    zoom, so a degenerate (empty) member set still produces a valid map."""
    if not members:
        zoom = zoom_for_min_width_km(
            min_width_km=min_width_km,
            latitude=DEFAULT_CENTER[0],
            canvas_width_px=CANVAS_SIZE[0],
        )
        return DEFAULT_CENTER, zoom

    points = [(record["latitude"], record["longitude"]) for record in members]
    return zoom_for_bounding_box(
        points,
        padding_px=FRAME_PADDING_PX,
        min_width_km=min_width_km,
        canvas_size=CANVAS_SIZE,
    )
