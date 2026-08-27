"""Unit tests for `scripts/rkby_maps/photo_map.py`: the promoted
circular-photo-map rendering helpers shared by `generate_member_maps.py`
(002) and `rkby_pairing/maps.py` (007+). None of these need network
mocking -- `render_photo_layer` only draws onto an in-memory
`PIL.Image.new(...)` canvas; only a full `stitch_basemap` call would need
that, and none of these helpers make one."""

from pathlib import Path

from PIL import Image

from scripts.rkby_maps import photo_map, pin_map
from scripts.rkby_maps.rendering import (
    PHOTO_DIAMETER_PX,
    PHOTO_OFFSET_FRACTION,
    PLACEHOLDER_PHOTO_PATH,
    crop_circular_photo,
)

BACKGROUND = (255, 255, 255)
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_PHOTO_PATH = FIXTURES_DIR / "sample_photo.jpg"
# Read back rather than hardcoded: JPEG's RGB<->YCbCr round-trip isn't
# perfectly lossless even for a solid-color source.
SAMPLE_PHOTO_COLOR = Image.open(SAMPLE_PHOTO_PATH).convert("RGB").getpixel((0, 0))
_PLACEHOLDER_CENTER = PHOTO_DIAMETER_PX // 2
PLACEHOLDER_PHOTO_COLOR = (
    crop_circular_photo(PLACEHOLDER_PHOTO_PATH)
    .convert("RGB")
    .getpixel((_PLACEHOLDER_CENTER, _PLACEHOLDER_CENTER))
)


def _record(match_key, lat, lon, photo=None) -> dict:
    return {"match_key": match_key, "latitude": lat, "longitude": lon, "photo": photo}


# --- photo_path ----------------------------------------------------------------------


def test_photo_path_returns_the_members_own_photo_when_it_exists_on_disk(tmp_path):
    (tmp_path / "photos").mkdir()
    photo_file = tmp_path / "photos" / "jane.jpg"
    photo_file.write_bytes(SAMPLE_PHOTO_PATH.read_bytes())
    record = _record("jane", 53.55, 9.99, photo="photos/jane.jpg")

    assert photo_map.photo_path(tmp_path, record) == photo_file


def test_photo_path_falls_back_to_the_placeholder_when_no_photo_is_on_file(tmp_path):
    record = _record("jane", 53.55, 9.99, photo=None)

    assert photo_map.photo_path(tmp_path, record) == PLACEHOLDER_PHOTO_PATH


def test_photo_path_falls_back_to_the_placeholder_when_the_referenced_file_is_missing(
    tmp_path,
):
    record = _record("jane", 53.55, 9.99, photo="photos/does-not-exist.jpg")

    assert photo_map.photo_path(tmp_path, record) == PLACEHOLDER_PHOTO_PATH


# --- render_photo_layer ---------------------------------------------------------------


def test_render_photo_layer_draws_an_individual_photo_circle_per_record(tmp_path):
    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "jane.jpg").write_bytes(SAMPLE_PHOTO_PATH.read_bytes())
    center = (53.55, 9.99)
    zoom = 14
    canvas = Image.new("RGB", pin_map.CANVAS_SIZE, color=BACKGROUND)
    records = [
        _record("jane", 53.55, 9.99, photo="photos/jane.jpg"),
        # ~1km away -- comfortably on-canvas, far enough to never overlap.
        _record("no-photo-john", 53.56, 10.0, photo=None),
    ]

    groups, by_key = photo_map.render_photo_layer(
        tmp_path, canvas, records, center, zoom
    )

    assert groups == []
    assert set(by_key) == {"jane", "no-photo-john"}
    positions = pin_map.pixel_positions(records, center, zoom)
    assert canvas.getpixel(tuple(round(v) for v in positions["jane"])) == (
        SAMPLE_PHOTO_COLOR
    )
    assert canvas.getpixel(tuple(round(v) for v in positions["no-photo-john"])) == (
        PLACEHOLDER_PHOTO_COLOR
    )


def test_render_photo_layer_draws_offset_circles_for_an_overlapping_group(tmp_path):
    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "jane.jpg").write_bytes(SAMPLE_PHOTO_PATH.read_bytes())
    (tmp_path / "photos" / "john.jpg").write_bytes(SAMPLE_PHOTO_PATH.read_bytes())
    center = (53.55, 9.99)
    zoom = 14
    canvas = Image.new("RGB", pin_map.CANVAS_SIZE, color=BACKGROUND)
    # Same exact coordinates -- guaranteed to overlap at any zoom.
    records = [
        _record("jane", 53.55, 9.99, photo="photos/jane.jpg"),
        _record("john", 53.55, 9.99, photo="photos/john.jpg"),
    ]

    groups, by_key = photo_map.render_photo_layer(
        tmp_path, canvas, records, center, zoom
    )

    assert groups == [["jane", "john"]] or groups == [["john", "jane"]]
    assert set(by_key) == {"jane", "john"}
    positions = pin_map.pixel_positions(records, center, zoom)
    group_position = pin_map.group_position(groups[0], positions)
    offset_step = round(PHOTO_DIAMETER_PX * PHOTO_OFFSET_FRACTION)
    x, y = group_position
    assert canvas.getpixel((round(x), round(y))) == SAMPLE_PHOTO_COLOR
    assert canvas.getpixel((round(x) + offset_step, round(y))) == SAMPLE_PHOTO_COLOR
