"""Unit tests for `scripts/rkby_maps/pin_map.py` (research.md Decision 2,
FR-004): the promoted pin-map rendering helpers shared by
`generate_member_maps.py` (002) and `rkby_pairing/maps.py` (007). None of
these need network mocking -- `render_pin_layer` only draws onto an
in-memory `PIL.Image.new(...)` canvas; only a full `stitch_basemap` call
would need that, and none of these helpers make one."""

from PIL import Image

from scripts.rkby_maps import pin_map
from scripts.rkby_maps.basemap import (
    TILE_SIZE,
    lonlat_to_pixel,
    zoom_for_bounding_box,
    zoom_for_min_width_km,
)
from scripts.rkby_maps.declutter import declutter_positions
from scripts.rkby_maps.rendering import (
    PHOTO_DIAMETER_PX,
    PIN_RADIUS_PX,
    RESOLUTION_SCALE,
    role_color,
)

BACKGROUND = (255, 255, 255)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _record(match_key, lat, lon, role=None) -> dict:
    return {"match_key": match_key, "latitude": lat, "longitude": lon, "role": role}


# --- Promoted constants (exact values, unchanged from generate_member_maps.py) --


def test_canvas_size_is_1600x1200_scaled_by_resolution_scale():
    assert pin_map.CANVAS_SIZE == (1600 * RESOLUTION_SCALE, 1200 * RESOLUTION_SCALE)


def test_default_min_width_km_is_15():
    assert pin_map.DEFAULT_MIN_WIDTH_KM == 15


def test_default_center_is_the_geographic_center_of_germany():
    assert pin_map.DEFAULT_CENTER == (51.1657, 10.4515)


def test_frame_padding_px_is_one_full_marker_wide():
    # The interactive map pads its own fitBounds by one full marker
    # (MEMBER_FIT_PADDING == ICON_SIZE_PX, main.js); the static maps' biggest
    # marker is the photo circle, so one of those is the equivalent margin.
    assert pin_map.FRAME_PADDING_PX == PHOTO_DIAMETER_PX


# --- pixel_positions ---------------------------------------------------------------


def test_pixel_positions_matches_lonlat_to_pixel_per_record():
    center = (53.55, 9.99)
    zoom = 14
    records = [
        _record("a", 53.55, 9.99),
        _record("b", 53.6, 10.1),
    ]

    positions = pin_map.pixel_positions(records, center, zoom)

    for record in records:
        expected = lonlat_to_pixel(
            record["latitude"],
            record["longitude"],
            center=center,
            zoom=zoom,
            canvas_size=pin_map.CANVAS_SIZE,
        )
        assert positions[record["match_key"]] == expected


# --- records_within_frame -------------------------------------------------------------


def _lon_at_pixel_x(
    center: tuple[float, float], zoom: int, target_x_px: float
) -> float:
    dx_px = target_x_px - pin_map.CANVAS_SIZE[0] / 2
    return center[1] + dx_px * 360 / (TILE_SIZE * 2**zoom)


def test_records_within_frame_always_includes_regardless_of_position():
    center = (53.55, 9.99)
    zoom = 14

    # Far off the canvas entirely -- always_include keeps it regardless of
    # where it lands, since it defines the frame itself.
    always_include_lon = _lon_at_pixel_x(center, zoom, -500)
    records = [_record("triggering", center[0], always_include_lon)]

    selected = pin_map.records_within_frame(
        records,
        always_include={"triggering"},
        center=center,
        zoom=zoom,
        canvas_size=pin_map.CANVAS_SIZE,
    )

    assert [r["match_key"] for r in selected] == ["triggering"]


def test_records_within_frame_includes_a_member_well_inside_the_frame():
    center = (53.55, 9.99)
    zoom = 14
    appearing_lon = _lon_at_pixel_x(center, zoom, 150)
    records = [_record("appearing", center[0], appearing_lon)]

    selected = pin_map.records_within_frame(
        records,
        always_include=set(),
        center=center,
        zoom=zoom,
        canvas_size=pin_map.CANVAS_SIZE,
    )

    assert [r["match_key"] for r in selected] == ["appearing"]


def test_records_within_frame_includes_a_member_close_to_the_canvas_edge():
    # Same rule as the interactive map: nobody who actually lands on the map
    # is dropped from it for sitting near the border (main.js renders every
    # visible member, wherever in the viewport they fall).
    center = (53.55, 9.99)
    zoom = 14
    edge_lon = _lon_at_pixel_x(center, zoom, 5)
    records = [_record("edge-member", center[0], edge_lon)]

    selected = pin_map.records_within_frame(
        records,
        always_include=set(),
        center=center,
        zoom=zoom,
        canvas_size=pin_map.CANVAS_SIZE,
    )

    assert [r["match_key"] for r in selected] == ["edge-member"]


def test_records_within_frame_omits_a_member_off_the_canvas():
    center = (53.55, 9.99)
    zoom = 14
    omitted_lon = _lon_at_pixel_x(center, zoom, -20)
    records = [_record("omitted", center[0], omitted_lon)]

    selected = pin_map.records_within_frame(
        records,
        always_include=set(),
        center=center,
        zoom=zoom,
        canvas_size=pin_map.CANVAS_SIZE,
    )

    assert selected == []


# --- render_pin_layer ----------------------------------------------------------------


def test_render_pin_layer_draws_an_individual_role_colored_pin_per_record():
    center = (53.55, 9.99)
    zoom = 14
    canvas = Image.new("RGB", pin_map.CANVAS_SIZE, color=BACKGROUND)
    records = [
        _record("rider-a", 53.55, 9.99, role="Rider"),
        # ~1km away -- comfortably on-canvas at this zoom, but far enough in
        # pixel terms to never overlap.
        _record("supporter-b", 53.56, 10.0, role="Supporter"),
    ]

    groups, by_key = pin_map.render_pin_layer(canvas, records, center, zoom)

    assert groups == []
    assert set(by_key) == {"rider-a", "supporter-b"}
    positions = pin_map.pixel_positions(records, center, zoom)
    assert canvas.getpixel(tuple(round(v) for v in positions["rider-a"])) == (
        _hex_to_rgb(role_color("Rider"))
    )
    assert canvas.getpixel(tuple(round(v) for v in positions["supporter-b"])) == (
        _hex_to_rgb(role_color("Supporter"))
    )


def test_render_pin_layer_draws_every_member_of_an_overlapping_group_individually():
    # Same rule as the interactive map (declutter.js): an overlapping group is
    # spread into a grid so each member keeps their own role-colored pin --
    # never collapsed into one merged marker that hides who is in it.
    center = (53.55, 9.99)
    zoom = 14
    canvas = Image.new("RGB", pin_map.CANVAS_SIZE, color=BACKGROUND)
    # Same exact coordinates -- guaranteed to overlap at any zoom.
    records = [
        _record("rider-a", 53.55, 9.99, role="Rider"),
        _record("supporter-b", 53.55, 9.99, role="Supporter"),
    ]

    groups, by_key = pin_map.render_pin_layer(canvas, records, center, zoom)

    assert [sorted(group) for group in groups] == [["rider-a", "supporter-b"]]
    assert set(by_key) == {"rider-a", "supporter-b"}
    positions = pin_map.pixel_positions(records, center, zoom)
    decluttered, _groups = declutter_positions(positions, marker_radius=PIN_RADIUS_PX)
    assert canvas.getpixel(tuple(round(v) for v in decluttered["rider-a"])) == (
        _hex_to_rgb(role_color("Rider"))
    )
    assert canvas.getpixel(tuple(round(v) for v in decluttered["supporter-b"])) == (
        _hex_to_rgb(role_color("Supporter"))
    )


# --- overview_center_and_zoom --------------------------------------------------------


def test_overview_center_and_zoom_falls_back_to_default_center_when_empty():
    result = pin_map.overview_center_and_zoom([], pin_map.DEFAULT_MIN_WIDTH_KM)

    expected_zoom = zoom_for_min_width_km(
        min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM,
        latitude=pin_map.DEFAULT_CENTER[0],
        canvas_width_px=pin_map.CANVAS_SIZE[0],
    )
    assert result == (pin_map.DEFAULT_CENTER, expected_zoom)


def test_overview_center_and_zoom_matches_zoom_for_bounding_box_when_populated():
    members = [
        _record("a", 53.55, 9.99),
        _record("b", 53.6, 10.1),
        _record("c", 53.4, 9.8),
    ]

    result = pin_map.overview_center_and_zoom(members, pin_map.DEFAULT_MIN_WIDTH_KM)

    expected = zoom_for_bounding_box(
        [(53.55, 9.99), (53.6, 10.1), (53.4, 9.8)],
        padding_px=pin_map.FRAME_PADDING_PX,
        min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM,
        canvas_size=pin_map.CANVAS_SIZE,
    )
    assert result == expected
