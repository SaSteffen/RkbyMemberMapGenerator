"""Unit tests for `scripts/rkby_pairing/maps.py` (FR-003/004/005/006/007,
data-model.md § Eligible Member Pool / Cluster Map / Overview Map):
cluster-map rendering (US2) and overview-map rendering (US3), using
`responses`-mocked OSM tile fetches only -- this feature geocodes nothing,
so no Nominatim mock is needed (mirror
`test_generate_member_maps_cli.py::_register_common_mocks`'s tile-only
half)."""

import re
from pathlib import Path

import responses

from scripts.rkby_maps import pin_map
from scripts.rkby_maps.basemap import (
    TILE_SIZE,
    zoom_for_bounding_box,
    zoom_for_min_width_km,
)
from scripts.rkby_maps.rendering import role_color
from scripts.rkby_pairing.clusters import TrainingCluster
from scripts.rkby_pairing.eligibility import is_eligible_base
from scripts.rkby_pairing.maps import (
    eligible_member_pool,
    render_cluster_map,
    render_overview_map,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
TILE_URL_PATTERN = re.compile(
    r"https://tile\.openstreetmap\.org/(\d+)/(\d+)/(\d+)\.png"
)


def _register_tile_mock():
    responses.add(
        responses.GET,
        TILE_URL_PATTERN,
        body=(FIXTURES_DIR / "osm_tile_fixture.png").read_bytes(),
        status=200,
        content_type="image/png",
    )


def _requested_zoom_levels() -> set[int]:
    zooms = set()
    for call in responses.calls:
        match = TILE_URL_PATTERN.match(call.request.url)
        if match:
            zooms.add(int(match.group(1)))
    return zooms


def _member(match_key, lat, lon, role="Rider", address=None, **overrides) -> dict:
    record = {
        "match_key": match_key,
        "latitude": lat,
        "longitude": lon,
        "role": role,
        "address": address,
        "excluded": False,
        "ignore": False,
    }
    record.update(overrides)
    return record


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _lon_at_pixel_x(center, zoom, target_x_px: float) -> float:
    scale = TILE_SIZE * 2**zoom
    canvas_width, _canvas_height = pin_map.CANVAS_SIZE
    dx_px = target_x_px - canvas_width / 2
    return center[1] + dx_px * 360 / scale


# --- eligible_member_pool (data-model.md § Eligible Member Pool, FR-007) -------


def test_eligible_member_pool_matches_is_eligible_base_with_no_role_filter():
    records = {
        "rider": _member("rider", 53.55, 9.99, role="Rider"),
        "crew": _member("crew", 53.56, 10.0, role="Service Crew"),
        "supporter": _member("supporter", 53.57, 10.01, role="Supporter"),
        "excluded": _member("excluded", 53.58, 10.02, excluded=True),
        "ignored": _member("ignored", 53.59, 10.03, ignore=True),
        "ungeocoded": _member("ungeocoded", None, None),
    }

    pool = eligible_member_pool(records)

    pool_keys = {record["match_key"] for record in pool}
    assert pool_keys == {"rider", "crew", "supporter"}
    for record in records.values():
        assert (record["match_key"] in pool_keys) == is_eligible_base(record)


# --- render_cluster_map (FR-003/004/005, data-model.md § Cluster Map) ---------


@responses.activate
def test_render_cluster_map_always_draws_every_cluster_member(tmp_path):
    cluster = TrainingCluster(
        member_match_keys=["rider-a", "rider-b"], centroid=(53.55, 9.995)
    )
    eligible_pool = [
        _member("rider-a", 53.55, 9.99, role="Rider"),
        _member("rider-b", 53.55, 10.0, role="Rider"),
    ]
    _register_tile_mock()

    image = render_cluster_map(
        cluster, eligible_pool, tile_cache_dir=tmp_path / "tile_cache"
    )

    center, zoom = zoom_for_bounding_box(
        [(53.55, 9.99), (53.55, 10.0)],
        padding_km=pin_map.PADDING_KM,
        min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM,
        canvas_size=pin_map.CANVAS_SIZE,
    )
    positions = pin_map.pixel_positions(eligible_pool, center, zoom)
    for record in eligible_pool:
        pixel = tuple(round(v) for v in positions[record["match_key"]])
        assert image.getpixel(pixel) == _hex_to_rgb(role_color("Rider"))


@responses.activate
def test_render_cluster_map_draws_an_eligible_member_of_another_role_inside_the_frame(
    tmp_path,
):
    cluster = TrainingCluster(member_match_keys=["rider-a"], centroid=(53.55, 9.99))
    center, zoom = zoom_for_bounding_box(
        [(53.55, 9.99)],
        padding_km=pin_map.PADDING_KM,
        min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM,
        canvas_size=pin_map.CANVAS_SIZE,
    )
    appearing_lon = _lon_at_pixel_x(center, zoom, pin_map.EDGE_MARGIN_PX + 150)
    eligible_pool = [
        _member("rider-a", 53.55, 9.99, role="Rider"),
        _member("supporter-b", center[0], appearing_lon, role="Supporter"),
    ]
    _register_tile_mock()

    image = render_cluster_map(
        cluster, eligible_pool, tile_cache_dir=tmp_path / "tile_cache"
    )

    positions = pin_map.pixel_positions(eligible_pool, center, zoom)
    pixel = tuple(round(v) for v in positions["supporter-b"])
    assert image.getpixel(pixel) == _hex_to_rgb(role_color("Supporter"))


@responses.activate
def test_render_cluster_map_omits_an_eligible_member_well_outside_the_frame(tmp_path):
    cluster = TrainingCluster(member_match_keys=["rider-a"], centroid=(53.55, 9.99))
    eligible_pool = [
        _member("rider-a", 53.55, 9.99, role="Rider"),
        # ~200km away -- clearly past DEFAULT_MIN_WIDTH_KM's edge.
        _member("supporter-far", 51.5, 9.99, role="Supporter"),
    ]
    _register_tile_mock()

    image = render_cluster_map(
        cluster, eligible_pool, tile_cache_dir=tmp_path / "tile_cache"
    )

    present_colors = {pixel for pixel in image.convert("RGB").getdata()}
    assert _hex_to_rgb(role_color("Supporter")) not in present_colors


@responses.activate
def test_render_cluster_map_single_member_cluster_returns_a_valid_canvas_sized_image(
    tmp_path,
):
    cluster = TrainingCluster(member_match_keys=["rider-a"], centroid=(53.55, 9.99))
    eligible_pool = [_member("rider-a", 53.55, 9.99, role="Rider")]
    _register_tile_mock()

    image = render_cluster_map(
        cluster, eligible_pool, tile_cache_dir=tmp_path / "tile_cache"
    )

    assert image.size == pin_map.CANVAS_SIZE


@responses.activate
def test_render_cluster_map_merges_two_same_address_members_into_one_pin(tmp_path):
    cluster = TrainingCluster(
        member_match_keys=["rider-a", "rider-b"], centroid=(53.55, 9.99)
    )
    same_address = "Marktplatz 1, 20095 Hamburg, Germany"
    eligible_pool = [
        _member("rider-a", 53.55, 9.99, role="Rider", address=same_address),
        _member("rider-b", 53.55, 9.99, role="Rider", address=same_address),
    ]
    _register_tile_mock()

    image = render_cluster_map(
        cluster, eligible_pool, tile_cache_dir=tmp_path / "tile_cache"
    )

    # draw_merged_pin's counter badge is always drawn in solid black -- a
    # reliable signal the FR-013 merge path (not two overlapping same-color
    # pins) was actually taken.
    present_colors = {pixel for pixel in image.convert("RGB").getdata()}
    assert (0, 0, 0) in present_colors


@responses.activate
def test_render_cluster_map_wider_than_min_width_km_frames_around_its_own_bounding_box(
    tmp_path,
):
    # ~50km apart -- wider than DEFAULT_MIN_WIDTH_KM (15km), so the frame
    # must widen past the floor to fit the cluster's own full bounding box.
    points = [(53.55, 9.99), (54.0, 9.99)]
    cluster = TrainingCluster(
        member_match_keys=["rider-a", "rider-b"], centroid=(53.775, 9.99)
    )
    eligible_pool = [
        _member("rider-a", 53.55, 9.99, role="Rider"),
        _member("rider-b", 54.0, 9.99, role="Rider"),
    ]
    _register_tile_mock()

    image = render_cluster_map(
        cluster, eligible_pool, tile_cache_dir=tmp_path / "tile_cache"
    )

    expected_center, expected_zoom = zoom_for_bounding_box(
        points,
        padding_km=pin_map.PADDING_KM,
        min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM,
        canvas_size=pin_map.CANVAS_SIZE,
    )
    assert image.size == pin_map.CANVAS_SIZE
    assert _requested_zoom_levels() == {expected_zoom}

    positions = pin_map.pixel_positions(eligible_pool, expected_center, expected_zoom)
    for record in eligible_pool:
        pixel = tuple(round(v) for v in positions[record["match_key"]])
        assert image.getpixel(pixel) == _hex_to_rgb(role_color("Rider"))


# --- render_overview_map (FR-006/007, data-model.md § Overview Map) ----------------


@responses.activate
def test_render_overview_map_draws_every_role_present_in_the_pool(tmp_path):
    eligible_pool = [
        _member("rider-a", 53.55, 9.99, role="Rider"),
        _member("crew-b", 53.56, 10.0, role="Service Crew"),
        _member("supporter-c", 53.54, 9.98, role="Supporter"),
    ]
    _register_tile_mock()

    image = render_overview_map(eligible_pool, tile_cache_dir=tmp_path / "tile_cache")

    center, zoom = pin_map.overview_center_and_zoom(
        eligible_pool, pin_map.DEFAULT_MIN_WIDTH_KM
    )
    positions = pin_map.pixel_positions(eligible_pool, center, zoom)
    for record in eligible_pool:
        pixel = tuple(round(v) for v in positions[record["match_key"]])
        assert image.getpixel(pixel) == _hex_to_rgb(role_color(record["role"]))


@responses.activate
def test_render_overview_map_with_an_empty_pool_still_returns_a_valid_image(tmp_path):
    _register_tile_mock()

    image = render_overview_map([], tile_cache_dir=tmp_path / "tile_cache")

    assert image.size == pin_map.CANVAS_SIZE
    expected_zoom = zoom_for_min_width_km(
        min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM,
        latitude=pin_map.DEFAULT_CENTER[0],
        canvas_width_px=pin_map.CANVAS_SIZE[0],
    )
    assert _requested_zoom_levels() == {expected_zoom}
