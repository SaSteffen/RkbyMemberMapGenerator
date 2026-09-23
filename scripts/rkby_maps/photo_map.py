"""Shared circular-photo-map rendering plumbing: promoted out of
`generate_member_maps.py`'s (002) private photo-layer helpers so a second
caller -- `rkby_pairing/maps.py` -- can render its own maps with member
photos instead of role-colored pins, through the exact same overlap-aware
photo/frame logic instead of a lookalike reimplementation. Behavior is
unchanged from the original private functions; only the names and module
are new."""

from __future__ import annotations

from pathlib import Path

from scripts.rkby_maps.declutter import declutter_positions
from scripts.rkby_maps.pin_map import pixel_positions
from scripts.rkby_maps.rendering import (
    PHOTO_RADIUS_PX,
    PLACEHOLDER_PHOTO_PATH,
    crop_circular_photo,
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
    """Draw one full circular photo per record -- members overlapping at this
    canvas's own scale are decluttered into a grid around their shared
    position (`rkby_maps.declutter`, as on the interactive map) rather than
    stacked into a row of part-covered circles, so every face stays whole
    and visible. Returns the detected overlap groups (which still decide
    which detail maps get generated) plus a match_key -> record lookup."""
    by_key = {record["match_key"]: record for record in records}
    positions = pixel_positions(records, center, zoom)
    drawn_positions, groups = declutter_positions(
        positions, marker_radius=PHOTO_RADIUS_PX
    )

    for key, record in by_key.items():
        circular_photo = crop_circular_photo(photo_path(s_dir, record))
        draw_photo_circle(canvas, drawn_positions[key], circular_photo)

    return groups, by_key
