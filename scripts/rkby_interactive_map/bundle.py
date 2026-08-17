"""Assembles the interactive map's one shared artifact: precomputed pixel
positions (research.md §3), the base flattened basemap image plus its
tiled higher-resolution levels (research.md §2, §2 addenda), `map-data.js`
(research.md §10, §12; data-model.md § Bundled Map Data), and the photo
(downscaled to a thumbnail, research.md §9)/index.html asset copy
(research.md §11)."""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

from PIL import Image

from scripts.rkby_maps.basemap import (
    canvas_origin,
    lonlat_to_pixel,
    stitch_basemap,
    stitch_region,
    zoom_for_bounding_box,
)
from scripts.rkby_maps.rendering import PLACEHOLDER_PHOTO_PATH, crop_square_thumbnail
from scripts.rkby_records import season_dir

# Combined-bounding-box canvas: one flattened image covering every merged
# member across every season, wider by default than a single season's own
# overview map since it may need to span more ground (implementation
# constant, tuned in code -- same pattern as generate_member_maps.py's
# DETAIL_MAP_PADDING_KM etc.).
CANVAS_SIZE = (2400, 1800)
MIN_WIDTH_KM = 25
PADDING_KM = 1.0
# Geographic center of Germany -- used only when there are zero merged
# members to bound (mirrors generate_member_maps.py's DEFAULT_CENTER).
DEFAULT_CENTER = (51.1657, 10.4515)
DEFAULT_ZOOM = 6

# research.md §2 addendum: on top of the base flattened image, bake a few
# extra resolution levels of the *same* geographic bounding box so the
# basemap looks less blurry once a viewer zooms in past the base level.
# Every level beyond the base is written as a grid of small TILE_PX chunk
# images rather than one giant flattened file -- a single image covering
# the whole 16x level's resolution would be a multi-gigapixel file that
# can't even be held in memory while generating it, let alone downloaded
# by a browser (research.md §2 2nd addendum has the numbers). Chunking
# means the frontend's custom Leaflet GridLayer (src/basemapTiles.js) only
# ever fetches the handful of chunks actually on screen, however deep the
# zoom goes. Each chunk is still a cropped/re-encoded composite of the
# underlying OSM tiles (never one passed through unmodified) in the
# general case -- the same "derived picture, not a re-servable OSM tile"
# distinction §2 leans on -- though because a chunk is the same pixel size
# as OSM's own native tile, a chunk that happens to land exactly on a tile
# boundary is close to indistinguishable from one. Baking this many levels
# is closer to the tile usage policy's own "pre-seeding... multiple zoom
# levels in advance" language than the original single-image decision was
# -- an accepted trade-off, confirmed by the user. Multipliers must be
# powers of two: one extra multiplier step == exactly one extra integer
# OSM tile zoom, which is what keeps every level's canvas covering the
# identical bounding box (research.md §2's zoom_for_bounding_box math).
BASEMAP_LEVELS = (1, 2, 4, 8, 16)
# OSM's own highest tile zoom -- a bounding box whose base zoom is already
# here (very tightly clustered members) has no higher-resolution tiles to
# fetch, so higher multipliers are skipped rather than re-fetching and
# re-flattening an identical raster under a different name.
MAX_OSM_ZOOM = 19
# Chunk size for every tiled resolution level (scale > 1) -- matches OSM's
# own native raster tile size, and is Leaflet's own GridLayer default, a
# sensible lazy-load granularity either way.
TILE_PX = 256
# Fills the last (partial) row/column of a level's chunk grid out to a full
# TILE_PX square, matching styles.css's #map background -- keeps every
# chunk file uniformly sized so the frontend never needs partial-tile
# handling.
_TILE_PAD_COLOR = (221, 221, 221)


def compute_positions(
    merged_members: list[dict],
) -> tuple[dict[str, tuple[float, float]], tuple[float, float], int]:
    """One fixed `(center, zoom)` for the whole artifact's single basemap
    image, from the combined bounding box of every merged member's
    `(latitude, longitude)` -- then each member's own pixel position at that
    one `(center, zoom, CANVAS_SIZE)` (research.md §3). A pure function of
    the member set's own lat/lon values, not of iteration order: `center`
    depends only on the set's min/max, and each member's own position
    depends only on their own coordinates once `(center, zoom)` is fixed."""
    if not merged_members:
        return {}, DEFAULT_CENTER, DEFAULT_ZOOM

    points = [(member["latitude"], member["longitude"]) for member in merged_members]
    center, zoom = zoom_for_bounding_box(
        points,
        padding_km=PADDING_KM,
        min_width_km=MIN_WIDTH_KM,
        canvas_size=CANVAS_SIZE,
    )
    positions = {
        member["match_key"]: lonlat_to_pixel(
            member["latitude"],
            member["longitude"],
            center=center,
            zoom=zoom,
            canvas_size=CANVAS_SIZE,
        )
        for member in merged_members
    }
    return positions, center, zoom


def _base_level(base_zoom: int) -> dict:
    """The always-present, single-file base (1x) level -- small enough at
    `CANVAS_SIZE` to ship as one flattened image with no chunking, and
    always shown underneath the tiled levels as the zoomed-out overview
    (research.md §2 addendum)."""
    return {"file": "basemap.jpg", "scale": 1, "zoom": base_zoom}


def _tile_levels(base_zoom: int) -> list[dict]:
    """Which `BASEMAP_LEVELS` multipliers beyond the base are actually
    distinct at this bounding box's own `base_zoom`, each described by its
    own OSM zoom and chunk-grid dimensions -- shared by `assemble_map_data`
    (which only needs the grid dimensions for map-data.js) and
    `generate_basemap` (which renders every chunk), so the two can never
    drift out of sync on what files exist."""
    levels = []
    seen_zoom: set[int] = {base_zoom}
    for scale in BASEMAP_LEVELS[1:]:
        zoom = min(base_zoom + (scale.bit_length() - 1), MAX_OSM_ZOOM)
        if zoom in seen_zoom:
            break
        seen_zoom.add(zoom)
        levels.append(
            {
                "scale": scale,
                "zoom": zoom,
                "cols": math.ceil(CANVAS_SIZE[0] * scale / TILE_PX),
                "rows": math.ceil(CANVAS_SIZE[1] * scale / TILE_PX),
            }
        )
    return levels


def _resolve_photo(data_dir: Path, member: dict) -> tuple[str, Path]:
    """Output-relative photo path + its real source file, or the Team
    Rynkeby mascot placeholder when the member has no photo on file
    (research.md §9) -- the same fallback rule as generate_member_maps.py's
    own `_photo_path`, applied to the merged member's own latest-eligible
    season's photo. Real photos are always re-encoded to a `.jpg` thumbnail
    by `copy_assets` regardless of their source extension, so the output
    name is always `.jpg` too."""
    relative = member.get("photo_relative_path")
    if relative:
        source_path = season_dir(data_dir, member["photo_season_label"]) / relative
        if source_path.exists():
            return f"photos/{member['match_key']}.jpg", source_path
    return "photos/placeholder.png", PLACEHOLDER_PHOTO_PATH


def assemble_map_data(
    data_dir: Path,
    interactive_map_dir: Path,
    seasons: list[str],
    merged_members: list[dict],
) -> None:
    """Write `window.RKBY_MAP_DATA = {...};` to `interactive_map_dir /
    map-data.js`, matching contracts/map-data.schema.json exactly -- never
    address/phone/email/birthday/etc. (Principle I minimization, research.md
    §12)."""
    positions, _center, base_zoom = compute_positions(merged_members)

    members_payload = []
    for member in merged_members:
        x, y = positions[member["match_key"]]
        photo_path, _source_path = _resolve_photo(data_dir, member)
        members_payload.append(
            {
                "match_key": member["match_key"],
                "name": f"{member['first_name']} {member['last_name']}".strip(),
                "num_previous_seasons": member["num_previous_seasons"],
                "photo": photo_path,
                "x": x,
                "y": y,
                "seasons": member["seasons"],
            }
        )

    payload = {
        "seasons": sorted(seasons),
        "members": members_payload,
        "image": {
            "file": "basemap.jpg",
            "width": CANVAS_SIZE[0],
            "height": CANVAS_SIZE[1],
            "tileSize": TILE_PX,
            "tileLevels": [
                {
                    "scale": level["scale"],
                    "cols": level["cols"],
                    "rows": level["rows"],
                }
                for level in _tile_levels(base_zoom)
            ],
        },
    }

    map_data_js = (
        "window.RKBY_MAP_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n"
    )
    (interactive_map_dir / "map-data.js").write_text(map_data_js)


def _write_level_tiles(
    interactive_map_dir: Path,
    center: tuple[float, float],
    level: dict,
    tile_cache_dir: Path,
) -> None:
    """Render one tiled resolution level's full `cols` x `rows` chunk grid
    into `interactive_map_dir/tiles/<scale>/<x>_<y>.jpg` -- factored out of
    `generate_basemap` so it's independently testable against a small
    synthetic `level` dict instead of `BASEMAP_LEVELS`' real (large,
    slow-to-stitch) grids.

    Row numbering is bottom-anchored (row 0 = the chunk nearest the
    image's *bottom* edge, increasing upward) to match Leaflet's own
    `CRS.Simple` tile grid exactly: `main.js`'s `pixelToLatLng` puts
    latitude 0 at the image's bottom edge, and Leaflet's tile math is
    always anchored to world-Y 0, so its tile row for our content is
    always <= -1 counting *up* from the bottom -- the exact mirror of a
    top-anchored (row 0 = top) numbering. Getting this backwards means
    every chunk request would straddle two different chunk files instead
    of landing on one, whenever a level's height isn't an exact multiple
    of TILE_PX (frontend's `basemapTiles.chunkRowForTileY` does the
    matching conversion). Only the last (topmost) row can be a partial,
    padded chunk under this numbering -- a partial last *column* still
    pads on the right, since Leaflet's x axis has no such flip."""
    scale = level["scale"]
    level_width, level_height = (CANVAS_SIZE[0] * scale, CANVAS_SIZE[1] * scale)
    left, top = canvas_origin(center, level["zoom"], (level_width, level_height))
    tiles_dir = interactive_map_dir / "tiles" / str(scale)
    tiles_dir.mkdir(parents=True, exist_ok=True)

    for row in range(level["rows"]):
        chunk_top = max(level_height - (row + 1) * TILE_PX, 0)
        chunk_bottom = level_height - row * TILE_PX
        chunk_height = chunk_bottom - chunk_top
        for col in range(level["cols"]):
            chunk_width = min(TILE_PX, level_width - col * TILE_PX)
            chunk = stitch_region(
                zoom=level["zoom"],
                left=left + col * TILE_PX,
                top=top + chunk_top,
                width=chunk_width,
                height=chunk_height,
                cache_dir=tile_cache_dir,
            )
            if chunk.size != (TILE_PX, TILE_PX):
                padded = Image.new("RGB", (TILE_PX, TILE_PX), _TILE_PAD_COLOR)
                # Right-align a partial column (pad on the right) and
                # bottom-align a partial row (pad above -- only the
                # topmost row is ever partial under this numbering).
                padded.paste(chunk, (0, TILE_PX - chunk_height))
                chunk = padded
            chunk.convert("RGB").save(tiles_dir / f"{col}_{row}.jpg", quality=85)


def generate_basemap(
    interactive_map_dir: Path, merged_members: list[dict], tile_cache_dir: Path
) -> None:
    """Render the base flattened image, then every `_tile_levels` entry's
    chunk grid -- every level covers the same combined bounding box
    `compute_positions()` used, only the OSM zoom and effective resolution
    scale up per level, never the geographic area (research.md §2
    addendum). Reuses the shared OSM tile cache (research.md §2, §11)."""
    _positions, center, base_zoom = compute_positions(merged_members)

    base = _base_level(base_zoom)
    canvas = stitch_basemap(
        center=center,
        zoom=base["zoom"],
        canvas_size=CANVAS_SIZE,
        cache_dir=tile_cache_dir,
    )
    canvas.convert("RGB").save(interactive_map_dir / base["file"], quality=90)

    for level in _tile_levels(base_zoom):
        _write_level_tiles(interactive_map_dir, center, level, tile_cache_dir)


def copy_assets(
    data_dir: Path,
    interactive_map_dir: Path,
    merged_members: list[dict],
    dist_index_html_path: Path,
) -> None:
    """Copy each merged member's own photo (or the placeholder mascot) into
    `interactive_map_dir/photos/`, and the built frontend's `index.html`
    verbatim (research.md §9, §11). Real photos are square-cropped and
    downscaled to `crop_square_thumbnail`'s fixed thumbnail size before
    being written -- shipping/decoding full-resolution originals for a
    marker the browser only ever renders at 40 CSS-px was the main cause of
    a slow-loading map with many members."""
    photos_dir = interactive_map_dir / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PLACEHOLDER_PHOTO_PATH, photos_dir / "placeholder.png")

    for member in merged_members:
        photo_path, source_path = _resolve_photo(data_dir, member)
        target_name = Path(photo_path).name
        if target_name == "placeholder.png":
            continue
        thumbnail = crop_square_thumbnail(source_path)
        thumbnail.save(photos_dir / target_name, "JPEG", quality=85)

    shutil.copyfile(dist_index_html_path, interactive_map_dir / "index.html")
