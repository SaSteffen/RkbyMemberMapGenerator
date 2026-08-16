"""Unit tests for `scripts/rkby_maps/basemap.py` (research.md §1, §2, §5, §6):
Web Mercator projection math, meters-per-pixel, zoom-from-required-width
selection, and OSM tile fetch/on-disk-cache/stitch."""

import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import requests
import responses
from PIL import Image

from scripts.rkby_maps.basemap import (
    fetch_tile,
    lonlat_to_pixel,
    meters_per_pixel,
    stitch_basemap,
    zoom_for_bounding_box,
    zoom_for_min_width_km,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
TILE_FIXTURE_BYTES = (FIXTURES_DIR / "osm_tile_fixture.png").read_bytes()


# --- Web Mercator projection (lon/lat -> pixel at a given center/zoom) --------


def test_lonlat_to_pixel_places_the_center_point_at_the_canvas_center():
    center = (53.55, 9.99)  # (lat, lon)
    canvas_size = (800, 600)

    x, y = lonlat_to_pixel(53.55, 9.99, center=center, zoom=10, canvas_size=canvas_size)

    assert x == pytest.approx(400, abs=0.5)
    assert y == pytest.approx(300, abs=0.5)


def test_lonlat_to_pixel_moves_east_as_longitude_increases():
    center = (53.55, 9.99)
    canvas_size = (800, 600)

    x_center, _ = lonlat_to_pixel(
        53.55, 9.99, center=center, zoom=10, canvas_size=canvas_size
    )
    x_east, _ = lonlat_to_pixel(
        53.55, 10.5, center=center, zoom=10, canvas_size=canvas_size
    )

    assert x_east > x_center


def test_lonlat_to_pixel_moves_north_as_latitude_increases():
    center = (53.55, 9.99)
    canvas_size = (800, 600)

    _, y_center = lonlat_to_pixel(
        53.55, 9.99, center=center, zoom=10, canvas_size=canvas_size
    )
    _, y_north = lonlat_to_pixel(
        54.0, 9.99, center=center, zoom=10, canvas_size=canvas_size
    )

    assert y_north < y_center  # north is up -- smaller pixel y


def test_lonlat_to_pixel_distance_increases_with_zoom():
    center = (53.55, 9.99)
    canvas_size = (800, 600)

    x_low, _ = lonlat_to_pixel(
        53.55, 10.0, center=center, zoom=8, canvas_size=canvas_size
    )
    x_high, _ = lonlat_to_pixel(
        53.55, 10.0, center=center, zoom=12, canvas_size=canvas_size
    )
    x_center = canvas_size[0] / 2

    assert abs(x_high - x_center) > abs(x_low - x_center)


# --- meters-per-pixel ------------------------------------------------------------


def test_meters_per_pixel_decreases_as_zoom_increases():
    low_zoom = meters_per_pixel(latitude=53.55, zoom=8)
    high_zoom = meters_per_pixel(latitude=53.55, zoom=14)

    assert high_zoom < low_zoom


def test_meters_per_pixel_matches_standard_web_mercator_formula():
    latitude = 0.0
    zoom = 10
    expected = 156543.03392 * math.cos(math.radians(latitude)) / (2**zoom)

    assert meters_per_pixel(latitude=latitude, zoom=zoom) == pytest.approx(
        expected, abs=0.01
    )


# --- zoom-from-required-width selection (research.md §5) ----------------------


def test_zoom_for_min_width_km_picks_a_zoom_whose_width_is_at_least_the_target():
    canvas_width_px = 1600
    min_width_km = 50

    zoom = zoom_for_min_width_km(
        min_width_km=min_width_km, latitude=53.55, canvas_width_px=canvas_width_px
    )

    mpp = meters_per_pixel(latitude=53.55, zoom=zoom)
    covered_km = (mpp * canvas_width_px) / 1000
    assert covered_km >= min_width_km


def test_zoom_for_min_width_km_picks_the_tightest_zoom_satisfying_the_bound():
    canvas_width_px = 1600
    min_width_km = 50

    zoom = zoom_for_min_width_km(
        min_width_km=min_width_km, latitude=53.55, canvas_width_px=canvas_width_px
    )

    # One zoom level tighter (higher) must violate the minimum-width bound --
    # otherwise `zoom` wasn't actually the tightest (highest) integer zoom.
    mpp_tighter = meters_per_pixel(latitude=53.55, zoom=zoom + 1)
    covered_km_tighter = (mpp_tighter * canvas_width_px) / 1000
    assert covered_km_tighter < min_width_km


def test_zoom_for_min_width_km_smaller_width_yields_higher_zoom():
    zoom_wide = zoom_for_min_width_km(
        min_width_km=200, latitude=53.55, canvas_width_px=1600
    )
    zoom_narrow = zoom_for_min_width_km(
        min_width_km=10, latitude=53.55, canvas_width_px=1600
    )

    assert zoom_narrow > zoom_wide


# --- Tile fetch / on-disk cache / stitch --------------------------------------


@responses.activate
def test_fetch_tile_downloads_and_writes_to_the_cache_when_absent(tmp_path):
    responses.add(
        responses.GET,
        "https://tile.openstreetmap.org/3/4/2.png",
        body=TILE_FIXTURE_BYTES,
        status=200,
        content_type="image/png",
    )

    tile_bytes = fetch_tile(z=3, x=4, y=2, cache_dir=tmp_path)

    assert tile_bytes == TILE_FIXTURE_BYTES
    cached_path = tmp_path / "3" / "4" / "2.png"
    assert cached_path.exists()
    assert cached_path.read_bytes() == TILE_FIXTURE_BYTES


@responses.activate
def test_fetch_tile_sends_a_custom_identifying_user_agent(tmp_path):
    responses.add(
        responses.GET,
        "https://tile.openstreetmap.org/3/4/2.png",
        body=TILE_FIXTURE_BYTES,
        status=200,
        content_type="image/png",
    )

    fetch_tile(z=3, x=4, y=2, cache_dir=tmp_path)

    sent_headers = responses.calls[0].request.headers
    assert "User-Agent" in sent_headers
    assert sent_headers["User-Agent"] != requests.utils.default_headers()["User-Agent"]


@responses.activate
def test_fetch_tile_reuses_the_on_disk_cache_without_a_second_http_request(tmp_path):
    cache_path = tmp_path / "3" / "4" / "2.png"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_bytes(TILE_FIXTURE_BYTES)
    # No responses.add() -- any HTTP call would raise ConnectionError.

    tile_bytes = fetch_tile(z=3, x=4, y=2, cache_dir=tmp_path)

    assert tile_bytes == TILE_FIXTURE_BYTES
    assert len(responses.calls) == 0


@responses.activate
def test_fetch_tile_concurrent_writes_never_leave_a_corrupt_cache_file(tmp_path):
    # Parallel image creation means several threads can race to cache the
    # same missing tile; a reader landing between another thread's truncate
    # and its write must never see a corrupt (partial/empty) file.
    responses.add(
        responses.GET,
        "https://tile.openstreetmap.org/3/4/2.png",
        body=TILE_FIXTURE_BYTES,
        status=200,
        content_type="image/png",
    )

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(
            executor.map(
                lambda _: fetch_tile(z=3, x=4, y=2, cache_dir=tmp_path), range(16)
            )
        )

    assert all(result == TILE_FIXTURE_BYTES for result in results)
    cache_dir = tmp_path / "3" / "4"
    assert [p.name for p in cache_dir.iterdir()] == ["2.png"]
    assert (cache_dir / "2.png").read_bytes() == TILE_FIXTURE_BYTES


@responses.activate
def test_stitch_basemap_produces_a_canvas_of_the_requested_pixel_size(tmp_path):
    # Register every tile that could exist at zoom=3 (2**3 = 8 per axis) --
    # responses.activate makes any unregistered request raise, which would
    # fail the test loudly if the required-tile-range math is off.
    for x in range(8):
        for y in range(8):
            responses.add(
                responses.GET,
                f"https://tile.openstreetmap.org/3/{x}/{y}.png",
                body=TILE_FIXTURE_BYTES,
                status=200,
                content_type="image/png",
            )

    canvas = stitch_basemap(
        center=(53.55, 9.99), zoom=3, canvas_size=(400, 300), cache_dir=tmp_path
    )

    assert isinstance(canvas, Image.Image)
    assert canvas.size == (400, 300)


# --- Detail-map bounding-box sizing (research.md §5) -------------------------------


def test_zoom_for_bounding_box_centers_on_the_midpoint_of_the_points():
    points = [(53.50, 9.90), (53.60, 10.00)]

    center, _zoom = zoom_for_bounding_box(
        points, padding_km=1.0, min_width_km=50, canvas_size=(1600, 1200)
    )

    assert center[0] == pytest.approx(53.55, abs=1e-6)
    assert center[1] == pytest.approx(9.95, abs=1e-6)


def test_zoom_for_bounding_box_result_covers_at_least_the_configured_minimum_width():
    points = [(53.549, 9.989), (53.551, 9.991)]  # a tight cluster

    center, zoom = zoom_for_bounding_box(
        points, padding_km=1.0, min_width_km=50, canvas_size=(1600, 1200)
    )

    covered_km = meters_per_pixel(center[0], zoom) * 1600 / 1000
    assert covered_km >= 50


def test_zoom_for_bounding_box_widens_beyond_the_minimum_for_a_spread_out_group():
    tight_points = [(53.549, 9.989), (53.551, 9.991)]
    spread_points = [(53.0, 9.0), (54.0, 11.0)]  # far wider than 50km

    _center_tight, zoom_tight = zoom_for_bounding_box(
        tight_points, padding_km=1.0, min_width_km=50, canvas_size=(1600, 1200)
    )
    _center_spread, zoom_spread = zoom_for_bounding_box(
        spread_points, padding_km=1.0, min_width_km=50, canvas_size=(1600, 1200)
    )

    # A much wider bounding box must produce a wider (lower-zoom) map.
    assert zoom_spread < zoom_tight


def test_zoom_for_bounding_box_a_single_point_falls_back_to_the_minimum_width():
    center, zoom = zoom_for_bounding_box(
        [(53.55, 9.99)], padding_km=1.0, min_width_km=50, canvas_size=(1600, 1200)
    )

    assert center == (53.55, 9.99)
    covered_km = meters_per_pixel(center[0], zoom) * 1600 / 1000
    assert covered_km >= 50
    # And it's the tightest zoom satisfying that bound.
    covered_km_tighter = meters_per_pixel(center[0], zoom + 1) * 1600 / 1000
    assert covered_km_tighter < 50
