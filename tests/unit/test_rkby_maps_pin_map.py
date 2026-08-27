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
from scripts.rkby_maps.rendering import RESOLUTION_SCALE, merged_role_color, role_color

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


def test_padding_km_is_half_a_kilometer():
    assert pin_map.PADDING_KM == 0.5


def test_edge_margin_px_is_50_scaled_by_resolution_scale():
    assert pin_map.EDGE_MARGIN_PX == 50 * RESOLUTION_SCALE


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


# --- group_position ------------------------------------------------------------------


def test_group_position_returns_the_mean_pixel_position_of_a_groups_members():
    positions = {"a": (10.0, 20.0), "b": (30.0, 40.0), "c": (50.0, 60.0)}

    result = pin_map.group_position(["a", "b", "c"], positions)

    assert result == (30.0, 40.0)


# --- records_within_frame -------------------------------------------------------------


def test_records_within_frame_always_includes_regardless_of_position():
    # Placed at the exact canvas center's own lat/lon -- would be "in frame"
    # anyway, but this test asserts the always_include path specifically by
    # also covering the always_include member below at a position that is
    # NOT well inside the frame (right at the edge margin boundary).
    center = (53.55, 9.99)
    zoom = 14
    canvas_size = pin_map.CANVAS_SIZE
    edge_margin_px = pin_map.EDGE_MARGIN_PX

    scale = TILE_SIZE * 2**zoom

    def _lon_at_pixel_x(target_x_px: float) -> float:
        dx_px = target_x_px - canvas_size[0] / 2
        return center[1] + dx_px * 360 / scale

    # Inside the edge margin -- would normally be omitted, but always_include
    # keeps it regardless of where it lands (it defines the frame itself).
    always_include_lon = _lon_at_pixel_x(edge_margin_px - 20)
    records = [_record("triggering", center[0], always_include_lon)]

    selected = pin_map.records_within_frame(
        records,
        always_include={"triggering"},
        center=center,
        zoom=zoom,
        canvas_size=canvas_size,
        edge_margin_px=edge_margin_px,
    )

    assert [r["match_key"] for r in selected] == ["triggering"]


def test_records_within_frame_includes_a_member_well_inside_the_frame():
    center = (53.55, 9.99)
    zoom = 14
    canvas_size = pin_map.CANVAS_SIZE
    edge_margin_px = pin_map.EDGE_MARGIN_PX
    scale = TILE_SIZE * 2**zoom

    def _lon_at_pixel_x(target_x_px: float) -> float:
        dx_px = target_x_px - canvas_size[0] / 2
        return center[1] + dx_px * 360 / scale

    appearing_lon = _lon_at_pixel_x(edge_margin_px + 150)
    records = [_record("appearing", center[0], appearing_lon)]

    selected = pin_map.records_within_frame(
        records,
        always_include=set(),
        center=center,
        zoom=zoom,
        canvas_size=canvas_size,
        edge_margin_px=edge_margin_px,
    )

    assert [r["match_key"] for r in selected] == ["appearing"]


def test_records_within_frame_omits_a_member_too_close_to_the_edge():
    center = (53.55, 9.99)
    zoom = 14
    canvas_size = pin_map.CANVAS_SIZE
    edge_margin_px = pin_map.EDGE_MARGIN_PX
    scale = TILE_SIZE * 2**zoom

    def _lon_at_pixel_x(target_x_px: float) -> float:
        dx_px = target_x_px - canvas_size[0] / 2
        return center[1] + dx_px * 360 / scale

    omitted_lon = _lon_at_pixel_x(edge_margin_px - 20)
    records = [_record("omitted", center[0], omitted_lon)]

    selected = pin_map.records_within_frame(
        records,
        always_include=set(),
        center=center,
        zoom=zoom,
        canvas_size=canvas_size,
        edge_margin_px=edge_margin_px,
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


def test_render_pin_layer_draws_one_merged_badged_pin_per_overlapping_group():
    center = (53.55, 9.99)
    zoom = 14
    canvas = Image.new("RGB", pin_map.CANVAS_SIZE, color=BACKGROUND)
    # Same exact coordinates -- guaranteed to overlap at any zoom.
    records = [
        _record("rider-a", 53.55, 9.99, role="Rider"),
        _record("rider-b", 53.55, 9.99, role="Rider"),
    ]

    groups, by_key = pin_map.render_pin_layer(canvas, records, center, zoom)

    assert groups == [["rider-a", "rider-b"]] or groups == [["rider-b", "rider-a"]]
    assert set(by_key) == {"rider-a", "rider-b"}
    positions = pin_map.pixel_positions(records, center, zoom)
    merged_position = pin_map.group_position(groups[0], positions)
    assert canvas.getpixel(tuple(round(v) for v in merged_position)) == _hex_to_rgb(
        merged_role_color([records[0], records[1]])
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
        padding_km=pin_map.PADDING_KM,
        min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM,
        canvas_size=pin_map.CANVAS_SIZE,
    )
    assert result == expected
