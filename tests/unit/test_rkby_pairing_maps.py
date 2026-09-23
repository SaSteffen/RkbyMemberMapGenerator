"""Unit tests for `scripts/rkby_pairing/maps.py` (FR-003/004/005/006/007,
data-model.md § Eligible Member Pool / Cluster Map / Overview Map):
cluster-map rendering (US2) and overview-map rendering (US3), using
`responses`-mocked OSM tile fetches only -- this feature geocodes nothing,
so no Nominatim mock is needed (mirror
`test_generate_member_maps_cli.py::_register_common_mocks`'s tile-only
half). Maps render member photos (faces), not role-colored pins --
mirroring `generate_member_maps.py`'s own photo variant, via the shared
`scripts.rkby_maps.photo_map` module."""

import re
from pathlib import Path

import responses
from PIL import Image

from scripts.rkby_maps import pin_map
from scripts.rkby_maps.basemap import (
    TILE_SIZE,
    zoom_for_bounding_box,
    zoom_for_min_width_km,
)
from scripts.rkby_maps.declutter import declutter_positions
from scripts.rkby_maps.rendering import (
    PHOTO_DIAMETER_PX,
    PHOTO_RADIUS_PX,
    PLACEHOLDER_PHOTO_PATH,
    crop_circular_photo,
)
from scripts.rkby_pairing.clusters import TrainingCluster
from scripts.rkby_pairing.eligibility import is_eligible_base
from scripts.rkby_pairing.maps import (
    eligible_member_pool,
    render_cluster_map,
    render_overview_map,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_PHOTO_PATH = FIXTURES_DIR / "sample_photo.jpg"
TILE_URL_PATTERN = re.compile(
    r"https://tile\.openstreetmap\.org/(\d+)/(\d+)/(\d+)\.png"
)

# Read back rather than hardcoded: JPEG's RGB<->YCbCr round-trip isn't
# perfectly lossless even for a solid-color source.
SAMPLE_PHOTO_COLOR = Image.open(SAMPLE_PHOTO_PATH).convert("RGB").getpixel((0, 0))
_PLACEHOLDER_CENTER = PHOTO_DIAMETER_PX // 2
PLACEHOLDER_PHOTO_COLOR = (
    crop_circular_photo(PLACEHOLDER_PHOTO_PATH)
    .convert("RGB")
    .getpixel((_PLACEHOLDER_CENTER, _PLACEHOLDER_CENTER))
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


def _member(match_key, lat, lon, photo=None, address=None, **overrides) -> dict:
    record = {
        "match_key": match_key,
        "latitude": lat,
        "longitude": lon,
        "photo": photo,
        "address": address,
        "excluded": False,
        "ignore": False,
    }
    record.update(overrides)
    return record


def _lon_at_pixel_x(center, zoom, target_x_px: float) -> float:
    scale = TILE_SIZE * 2**zoom
    canvas_width, _canvas_height = pin_map.CANVAS_SIZE
    dx_px = target_x_px - canvas_width / 2
    return center[1] + dx_px * 360 / scale


def _write_photo(s_dir: Path, relative_path: str) -> None:
    full_path = s_dir / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(SAMPLE_PHOTO_PATH.read_bytes())


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
def test_render_cluster_map_always_draws_every_cluster_members_own_photo(tmp_path):
    _write_photo(tmp_path, "photos/jane.jpg")
    cluster = TrainingCluster(
        member_match_keys=["jane", "john"], centroid=(53.55, 9.995)
    )
    eligible_pool = [
        _member("jane", 53.55, 9.99, photo="photos/jane.jpg"),
        _member("john", 53.55, 10.0, photo=None),  # gets the placeholder mascot
    ]
    _register_tile_mock()

    image = render_cluster_map(
        cluster, eligible_pool, tile_cache_dir=tmp_path / "tile_cache", s_dir=tmp_path
    )

    center, zoom = zoom_for_bounding_box(
        [(53.55, 9.99), (53.55, 10.0)],
        padding_px=pin_map.FRAME_PADDING_PX,
        min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM,
        canvas_size=pin_map.CANVAS_SIZE,
    )
    positions = pin_map.pixel_positions(eligible_pool, center, zoom)
    assert image.getpixel(tuple(round(v) for v in positions["jane"])) == (
        SAMPLE_PHOTO_COLOR
    )
    assert image.getpixel(tuple(round(v) for v in positions["john"])) == (
        PLACEHOLDER_PHOTO_COLOR
    )


@responses.activate
def test_render_cluster_map_draws_an_eligible_member_of_another_role_inside_the_frame(
    tmp_path,
):
    _write_photo(tmp_path, "photos/supporter.jpg")
    cluster = TrainingCluster(member_match_keys=["jane"], centroid=(53.55, 9.99))
    center, zoom = zoom_for_bounding_box(
        [(53.55, 9.99)],
        padding_px=pin_map.FRAME_PADDING_PX,
        min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM,
        canvas_size=pin_map.CANVAS_SIZE,
    )
    appearing_lon = _lon_at_pixel_x(center, zoom, 150)
    eligible_pool = [
        _member("jane", 53.55, 9.99, photo=None),
        _member("supporter-b", center[0], appearing_lon, photo="photos/supporter.jpg"),
    ]
    _register_tile_mock()

    image = render_cluster_map(
        cluster, eligible_pool, tile_cache_dir=tmp_path / "tile_cache", s_dir=tmp_path
    )

    positions = pin_map.pixel_positions(eligible_pool, center, zoom)
    pixel = tuple(round(v) for v in positions["supporter-b"])
    assert image.getpixel(pixel) == SAMPLE_PHOTO_COLOR


@responses.activate
def test_render_cluster_map_omits_an_eligible_member_well_outside_the_frame(tmp_path):
    _write_photo(tmp_path, "photos/far.jpg")
    cluster = TrainingCluster(member_match_keys=["jane"], centroid=(53.55, 9.99))
    eligible_pool = [
        _member("jane", 53.55, 9.99, photo=None),
        # ~200km away -- clearly past DEFAULT_MIN_WIDTH_KM's edge.
        _member("far-member", 51.5, 9.99, photo="photos/far.jpg"),
    ]
    _register_tile_mock()

    image = render_cluster_map(
        cluster, eligible_pool, tile_cache_dir=tmp_path / "tile_cache", s_dir=tmp_path
    )

    present_colors = {pixel for pixel in image.convert("RGB").getdata()}
    assert SAMPLE_PHOTO_COLOR not in present_colors


@responses.activate
def test_render_cluster_map_single_member_cluster_returns_a_valid_canvas_sized_image(
    tmp_path,
):
    cluster = TrainingCluster(member_match_keys=["jane"], centroid=(53.55, 9.99))
    eligible_pool = [_member("jane", 53.55, 9.99, photo=None)]
    _register_tile_mock()

    image = render_cluster_map(
        cluster, eligible_pool, tile_cache_dir=tmp_path / "tile_cache", s_dir=tmp_path
    )

    assert image.size == pin_map.CANVAS_SIZE


@responses.activate
def test_render_cluster_map_declutters_two_overlapping_members_into_a_grid(
    tmp_path,
):
    _write_photo(tmp_path, "photos/jane.jpg")
    _write_photo(tmp_path, "photos/john.jpg")
    cluster = TrainingCluster(
        member_match_keys=["jane", "john"], centroid=(53.55, 9.99)
    )
    same_address = "Marktplatz 1, 20095 Hamburg, Germany"
    eligible_pool = [
        _member("jane", 53.55, 9.99, photo="photos/jane.jpg", address=same_address),
        _member("john", 53.55, 9.99, photo="photos/john.jpg", address=same_address),
    ]
    _register_tile_mock()

    image = render_cluster_map(
        cluster, eligible_pool, tile_cache_dir=tmp_path / "tile_cache", s_dir=tmp_path
    )

    center, zoom = zoom_for_bounding_box(
        [(53.55, 9.99), (53.55, 9.99)],
        padding_px=pin_map.FRAME_PADDING_PX,
        min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM,
        canvas_size=pin_map.CANVAS_SIZE,
    )
    positions = pin_map.pixel_positions(eligible_pool, center, zoom)
    decluttered, _groups = declutter_positions(positions, marker_radius=PHOTO_RADIUS_PX)
    # Two fully-visible circles, spaced a full diameter apart by the same
    # decluttering the interactive map uses -- neither covering the other,
    # neither cropped by the other's overlap.
    for match_key in ("jane", "john"):
        x, y = decluttered[match_key]
        assert image.getpixel((round(x), round(y))) == SAMPLE_PHOTO_COLOR
    assert abs(decluttered["jane"][0] - decluttered["john"][0]) == PHOTO_DIAMETER_PX


@responses.activate
def test_render_cluster_map_wider_than_min_width_km_frames_around_its_own_bounding_box(
    tmp_path,
):
    # ~50km apart -- wider than DEFAULT_MIN_WIDTH_KM (15km), so the frame
    # must widen past the floor to fit the cluster's own full bounding box.
    _write_photo(tmp_path, "photos/jane.jpg")
    _write_photo(tmp_path, "photos/john.jpg")
    points = [(53.55, 9.99), (54.0, 9.99)]
    cluster = TrainingCluster(
        member_match_keys=["jane", "john"], centroid=(53.775, 9.99)
    )
    eligible_pool = [
        _member("jane", 53.55, 9.99, photo="photos/jane.jpg"),
        _member("john", 54.0, 9.99, photo="photos/john.jpg"),
    ]
    _register_tile_mock()

    image = render_cluster_map(
        cluster, eligible_pool, tile_cache_dir=tmp_path / "tile_cache", s_dir=tmp_path
    )

    expected_center, expected_zoom = zoom_for_bounding_box(
        points,
        padding_px=pin_map.FRAME_PADDING_PX,
        min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM,
        canvas_size=pin_map.CANVAS_SIZE,
    )
    assert image.size == pin_map.CANVAS_SIZE
    assert _requested_zoom_levels() == {expected_zoom}

    positions = pin_map.pixel_positions(eligible_pool, expected_center, expected_zoom)
    for record in eligible_pool:
        pixel = tuple(round(v) for v in positions[record["match_key"]])
        assert image.getpixel(pixel) == SAMPLE_PHOTO_COLOR


# --- render_overview_map (FR-006/007, data-model.md § Overview Map) ----------------


@responses.activate
def test_render_overview_map_draws_every_eligible_members_photo(tmp_path):
    _write_photo(tmp_path, "photos/jane.jpg")
    eligible_pool = [
        _member("jane", 53.55, 9.99, photo="photos/jane.jpg"),
        _member("no-photo-john", 53.56, 10.0, photo=None),
    ]
    _register_tile_mock()

    image = render_overview_map(
        eligible_pool, tile_cache_dir=tmp_path / "tile_cache", s_dir=tmp_path
    )

    center, zoom = pin_map.overview_center_and_zoom(
        eligible_pool, pin_map.DEFAULT_MIN_WIDTH_KM
    )
    positions = pin_map.pixel_positions(eligible_pool, center, zoom)
    assert image.getpixel(tuple(round(v) for v in positions["jane"])) == (
        SAMPLE_PHOTO_COLOR
    )
    assert image.getpixel(tuple(round(v) for v in positions["no-photo-john"])) == (
        PLACEHOLDER_PHOTO_COLOR
    )


@responses.activate
def test_render_overview_map_with_an_empty_pool_still_returns_a_valid_image(tmp_path):
    _register_tile_mock()

    image = render_overview_map(
        [], tile_cache_dir=tmp_path / "tile_cache", s_dir=tmp_path
    )

    assert image.size == pin_map.CANVAS_SIZE
    expected_zoom = zoom_for_min_width_km(
        min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM,
        latitude=pin_map.DEFAULT_CENTER[0],
        canvas_width_px=pin_map.CANVAS_SIZE[0],
    )
    assert _requested_zoom_levels() == {expected_zoom}
