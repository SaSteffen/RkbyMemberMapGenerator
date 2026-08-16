"""Web Mercator projection math and OSM raster tile fetch/cache/stitch
(research.md §1, §2, §5, §6). No static-map library -- see research.md §1 for
why the projection formulas are implemented directly instead."""

from __future__ import annotations

import io
import math
from pathlib import Path

import requests
from PIL import Image

TILE_SIZE = 256
OSM_TILE_URL_TEMPLATE = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = "RkbyMemberMapGenerator/1.0 (https://github.com/team-rynkeby-hamburg)"


def _global_pixel(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """Standard Web Mercator lon/lat -> pixel position in the zoom level's
    full world-pixel space (origin top-left, size `TILE_SIZE * 2**zoom`)."""
    scale = TILE_SIZE * 2**zoom
    x = (lon + 180.0) / 360.0 * scale
    sin_lat = min(max(math.sin(math.radians(lat)), -0.9999), 0.9999)
    y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * scale
    return x, y


def lonlat_to_pixel(
    lat: float,
    lon: float,
    center: tuple[float, float],
    zoom: int,
    canvas_size: tuple[int, int],
) -> tuple[float, float]:
    """Project `(lat, lon)` to its pixel position on a canvas of
    `canvas_size` centered on `center` at `zoom` -- independent of the
    renderer, so overlap/clustering (FR-011) and the scale bar (FR-008) can
    reason about positions directly (research.md §1)."""
    center_x, center_y = _global_pixel(*center, zoom)
    point_x, point_y = _global_pixel(lat, lon, zoom)
    canvas_width, canvas_height = canvas_size
    return (
        canvas_width / 2 + (point_x - center_x),
        canvas_height / 2 + (point_y - center_y),
    )


def meters_per_pixel(latitude: float, zoom: int) -> float:
    """Standard Web Mercator meters-per-pixel formula at a given zoom/latitude."""
    return 156543.03392 * math.cos(math.radians(latitude)) / (2**zoom)


def zoom_for_min_width_km(
    min_width_km: float, latitude: float, canvas_width_px: int, max_zoom: int = 19
) -> int:
    """Pick the tightest (highest) integer zoom whose covered real-world
    width is still >= `min_width_km` (research.md §5) -- OSM tiles only
    exist at discrete integer zoom levels, so this is a lower bound, never
    an exact target."""
    zoom = 0
    for candidate in range(1, max_zoom + 1):
        covered_km = meters_per_pixel(latitude, candidate) * canvas_width_px / 1000
        if covered_km < min_width_km:
            break
        zoom = candidate
    return zoom


def zoom_for_bounding_box(
    points: list[tuple[float, float]],
    padding_km: float,
    min_width_km: float,
    canvas_size: tuple[int, int],
    max_zoom: int = 19,
) -> tuple[tuple[float, float], int]:
    """Center on the midpoint of `points`' bounding box and pick the
    tightest integer zoom whose covered width is still >= `max(min_width_km,
    required_width)`, where `required_width` is the box's own span (aspect-
    corrected to the canvas) plus a fixed padding margin on each side
    (research.md §5). A single point has zero span, so `required_width`
    collapses to just the padding and `min_width_km` is the effective
    floor."""
    lats = [point[0] for point in points]
    lons = [point[1] for point in points]
    center = ((min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2)

    canvas_width_px, canvas_height_px = canvas_size
    aspect_ratio = canvas_width_px / canvas_height_px

    lat_span_km = (max(lats) - min(lats)) * 111.32
    lon_span_km = (max(lons) - min(lons)) * 111.32 * math.cos(math.radians(center[0]))
    required_width_km = max(lon_span_km, lat_span_km * aspect_ratio) + 2 * padding_km
    target_width_km = max(min_width_km, required_width_km)

    zoom = zoom_for_min_width_km(
        min_width_km=target_width_km,
        latitude=center[0],
        canvas_width_px=canvas_width_px,
        max_zoom=max_zoom,
    )
    return center, zoom


def fetch_tile(z: int, x: int, y: int, cache_dir: Path) -> bytes:
    """Fetch one OSM raster tile, reusing an on-disk cache entry if present
    (research.md §2) -- a tile already fetched by any past run is never
    re-requested."""
    cached_path = Path(cache_dir) / str(z) / str(x) / f"{y}.png"
    if cached_path.exists():
        return cached_path.read_bytes()

    response = requests.get(
        OSM_TILE_URL_TEMPLATE.format(z=z, x=x, y=y),
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    tile_bytes = response.content

    cached_path.parent.mkdir(parents=True, exist_ok=True)
    cached_path.write_bytes(tile_bytes)
    return tile_bytes


def stitch_basemap(
    center: tuple[float, float],
    zoom: int,
    canvas_size: tuple[int, int],
    cache_dir: Path,
) -> Image.Image:
    """Fetch every tile covering `canvas_size` centered on `center` at
    `zoom`, stitch them together, and crop to exactly `canvas_size`."""
    canvas_width, canvas_height = canvas_size
    center_x, center_y = _global_pixel(*center, zoom)
    left = center_x - canvas_width / 2
    top = center_y - canvas_height / 2

    first_tile_x = math.floor(left / TILE_SIZE)
    first_tile_y = math.floor(top / TILE_SIZE)
    last_tile_x = math.floor((left + canvas_width - 1) / TILE_SIZE)
    last_tile_y = math.floor((top + canvas_height - 1) / TILE_SIZE)

    tiles_per_axis = 2**zoom
    stitched_width = (last_tile_x - first_tile_x + 1) * TILE_SIZE
    stitched_height = (last_tile_y - first_tile_y + 1) * TILE_SIZE
    stitched = Image.new("RGB", (stitched_width, stitched_height))

    for tile_x in range(first_tile_x, last_tile_x + 1):
        for tile_y in range(first_tile_y, last_tile_y + 1):
            wrapped_x = tile_x % tiles_per_axis  # world wraps in x, not y
            tile_bytes = fetch_tile(zoom, wrapped_x, tile_y, cache_dir)
            tile_image = Image.open(io.BytesIO(tile_bytes)).convert("RGB")
            paste_x = (tile_x - first_tile_x) * TILE_SIZE
            paste_y = (tile_y - first_tile_y) * TILE_SIZE
            stitched.paste(tile_image, (paste_x, paste_y))

    crop_left = round(left - first_tile_x * TILE_SIZE)
    crop_top = round(top - first_tile_y * TILE_SIZE)
    return stitched.crop(
        (crop_left, crop_top, crop_left + canvas_width, crop_top + canvas_height)
    )
