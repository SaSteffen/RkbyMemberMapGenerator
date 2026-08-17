"""Assembles the interactive map's one shared artifact: precomputed pixel
positions (research.md §3), the flattened basemap image (research.md §2),
`map-data.js` (research.md §10, §12; data-model.md § Bundled Map Data), and
the photo/index.html asset copy (research.md §9, §11)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from scripts.rkby_maps.basemap import (
    lonlat_to_pixel,
    stitch_basemap,
    zoom_for_bounding_box,
)
from scripts.rkby_maps.rendering import PLACEHOLDER_PHOTO_PATH
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


def _resolve_photo(data_dir: Path, member: dict) -> tuple[str, Path]:
    """Output-relative photo path + its real source file, or the Team
    Rynkeby mascot placeholder when the member has no photo on file
    (research.md §9) -- the same fallback rule as generate_member_maps.py's
    own `_photo_path`, applied to the merged member's own latest-eligible
    season's photo."""
    relative = member.get("photo_relative_path")
    if relative:
        source_path = season_dir(data_dir, member["photo_season_label"]) / relative
        if source_path.exists():
            ext = Path(relative).suffix or ".jpg"
            return f"photos/{member['match_key']}{ext}", source_path
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
    positions, _center, _zoom = compute_positions(merged_members)

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
        },
    }

    map_data_js = (
        "window.RKBY_MAP_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n"
    )
    (interactive_map_dir / "map-data.js").write_text(map_data_js)


def generate_basemap(
    interactive_map_dir: Path, merged_members: list[dict], tile_cache_dir: Path
) -> None:
    """Render `interactive_map_dir / basemap.jpg` at the same combined
    `(center, zoom, CANVAS_SIZE)` `compute_positions()` used, reusing the
    shared OSM tile cache (research.md §2, §11)."""
    _positions, center, zoom = compute_positions(merged_members)
    canvas = stitch_basemap(
        center=center, zoom=zoom, canvas_size=CANVAS_SIZE, cache_dir=tile_cache_dir
    )
    canvas.convert("RGB").save(interactive_map_dir / "basemap.jpg", quality=90)


def copy_assets(
    data_dir: Path,
    interactive_map_dir: Path,
    merged_members: list[dict],
    dist_index_html_path: Path,
) -> None:
    """Copy each merged member's own photo (or the placeholder mascot) into
    `interactive_map_dir/photos/`, and the built frontend's `index.html`
    verbatim (research.md §9, §11)."""
    photos_dir = interactive_map_dir / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PLACEHOLDER_PHOTO_PATH, photos_dir / "placeholder.png")

    for member in merged_members:
        photo_path, source_path = _resolve_photo(data_dir, member)
        target_name = Path(photo_path).name
        if target_name == "placeholder.png":
            continue
        shutil.copyfile(source_path, photos_dir / target_name)

    shutil.copyfile(dist_index_html_path, interactive_map_dir / "index.html")
