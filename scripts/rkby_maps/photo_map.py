"""Shared circular-photo-map rendering plumbing: promoted out of
`generate_member_maps.py`'s (002) private photo-layer helpers so a second
caller -- `rkby_pairing/maps.py` -- can render its own maps with member
photos instead of role-colored pins, through the exact same overlap-aware
photo/frame logic instead of a lookalike reimplementation. Behavior is
unchanged from the original private functions; only the names and module
are new."""

from __future__ import annotations

from pathlib import Path

from scripts.rkby_maps.clustering import find_overlap_groups
from scripts.rkby_maps.pin_map import group_position, pixel_positions
from scripts.rkby_maps.rendering import (
    PHOTO_RADIUS_PX,
    PLACEHOLDER_PHOTO_PATH,
    crop_circular_photo,
    draw_offset_photo_circles,
    draw_photo_circle,
)


def photo_path(s_dir: Path, record: dict) -> Path:
    """The member's own photo if one is on file, otherwise the Team Rynkeby
    mascot placeholder -- every plottable member gets a circle on the photo
    map, picture or not."""
    photo_relative_path = record.get("photo")
    if photo_relative_path and (s_dir / photo_relative_path).exists():
        return s_dir / photo_relative_path
    return PLACEHOLDER_PHOTO_PATH


def render_photo_layer(
    s_dir: Path,
    canvas,
    records: list[dict],
    center: tuple[float, float],
    zoom: int,
) -> tuple[list[list[str]], dict[str, dict]]:
    """Draw an individual circular photo per record, or a set of offset
    overlapping circles per group overlapping at this canvas's own scale.
    Returns the detected overlap groups plus a match_key -> record
    lookup."""
    by_key = {record["match_key"]: record for record in records}
    positions = pixel_positions(records, center, zoom)
    groups = find_overlap_groups(positions, radius=PHOTO_RADIUS_PX)
    grouped_keys = {key for group in groups for key in group}

    for key, record in by_key.items():
        if key not in grouped_keys:
            circular_photo = crop_circular_photo(photo_path(s_dir, record))
            draw_photo_circle(canvas, positions[key], circular_photo)

    for group in groups:
        group_records = [by_key[key] for key in group]
        circles = [
            crop_circular_photo(photo_path(s_dir, record)) for record in group_records
        ]
        draw_offset_photo_circles(canvas, group_position(group, positions), circles)

    return groups, by_key
