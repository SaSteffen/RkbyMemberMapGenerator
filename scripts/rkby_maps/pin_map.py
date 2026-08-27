"""Shared pin-map rendering plumbing (research.md Decision 2, FR-004):
promoted out of `generate_member_maps.py`'s (002) private helpers so a
second caller -- `rkby_pairing/maps.py` (007) -- renders its cluster/
overview maps through the exact same overlap-aware pin/frame logic instead
of a lookalike reimplementation. Behavior is unchanged from the original
private functions; only the names and module are new."""

from __future__ import annotations

from scripts.rkby_maps.basemap import (
    lonlat_to_pixel,
    zoom_for_bounding_box,
    zoom_for_min_width_km,
)
from scripts.rkby_maps.clustering import find_overlap_groups
from scripts.rkby_maps.rendering import (
    PIN_RADIUS_PX,
    RESOLUTION_SCALE,
    draw_merged_pin,
    draw_pin,
    merged_role_color,
    role_color,
)

DEFAULT_MIN_WIDTH_KM = 15
CANVAS_SIZE = (1600 * RESOLUTION_SCALE, 1200 * RESOLUTION_SCALE)
# Geographic center of Germany -- used only as the overview map's center for
# a degenerate (empty) member set.
DEFAULT_CENTER = (51.1657, 10.4515)
# Fixed padding margin added around a bounding box -- of either an overlap
# group (cluster/detail maps) or a full member set (an overview) -- before
# flooring the result at --min-width-km.
PADDING_KM = 0.5
# A map is framed around its triggering group, but --min-width-km often
# floors that frame far wider than the group itself -- other plottable
# members frequently fall inside it too and must be drawn, not just the
# group that triggered it. A member within this many pixels of the canvas
# edge is left off that specific map instead: a marker clipped by (or
# crowding right up against) the border reads worse than one member simply
# not appearing on this particular map.
EDGE_MARGIN_PX = 50 * RESOLUTION_SCALE


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


def group_position(
    group: list[str], positions: dict[str, tuple[float, float]]
) -> tuple[float, float]:
    xs = [positions[key][0] for key in group]
    ys = [positions[key][1] for key in group]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def records_within_frame(
    records: list[dict],
    always_include: set[str],
    center: tuple[float, float],
    zoom: int,
    canvas_size: tuple[int, int],
    edge_margin_px: float,
) -> list[dict]:
    """Every plottable member who actually lands inside a map's rendered
    frame at `(center, zoom)`, not just the group that triggered it.
    `always_include` members (the triggering group) are kept regardless of
    where they land, since they define the frame itself; everyone else
    within `edge_margin_px` of the canvas border is left off this
    particular map."""
    canvas_width, canvas_height = canvas_size
    positions = pixel_positions(records, center, zoom)
    selected = []
    for record in records:
        key = record["match_key"]
        x, y = positions[key]
        in_frame = (
            edge_margin_px <= x <= canvas_width - edge_margin_px
            and edge_margin_px <= y <= canvas_height - edge_margin_px
        )
        if key in always_include or in_frame:
            selected.append(record)
    return selected


def render_pin_layer(
    canvas, records: list[dict], center: tuple[float, float], zoom: int
) -> tuple[list[list[str]], dict[str, dict]]:
    """Draw an individual role-colored pin per record, or one merged
    fallback pin per group overlapping at this canvas's own scale. Returns
    the detected overlap groups plus a match_key -> record lookup."""
    by_key = {record["match_key"]: record for record in records}
    positions = pixel_positions(records, center, zoom)
    groups = find_overlap_groups(positions, radius=PIN_RADIUS_PX)
    grouped_keys = {key for group in groups for key in group}

    for key, record in by_key.items():
        if key not in grouped_keys:
            draw_pin(canvas, positions[key], color=role_color(record.get("role")))

    for group in groups:
        group_records = [by_key[key] for key in group]
        draw_merged_pin(
            canvas,
            group_position(group, positions),
            count=len(group_records),
            color=merged_role_color(group_records),
        )

    return groups, by_key


def overview_center_and_zoom(
    members: list[dict], min_width_km: float
) -> tuple[tuple[float, float], int]:
    """The overview's own bounding box (all of `members`, plus a fixed
    padding margin), floored at `min_width_km` -- a nationally-spread team
    naturally renders wider than the configured minimum so everyone fits,
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
        padding_km=PADDING_KM,
        min_width_km=min_width_km,
        canvas_size=CANVAS_SIZE,
    )
