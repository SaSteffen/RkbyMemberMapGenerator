"""Assembles the interactive map's one shared artifact: validates the
maintainer-supplied PMTiles basemap file and base64-embeds it
(research.md §2, §3), each member's own already-geocoded lat/lon
(data-model.md § Merged Member), `map-data.js` (data-model.md § Bundled Map
Data), and the photo (downscaled to a thumbnail, research.md §9)/index.html
asset copy (research.md §11)."""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

from scripts.rkby_maps.rendering import (
    PLACEHOLDER_PHOTO_PATH,
    crop_square_thumbnail,
    scale_to_hover_size,
)
from scripts.rkby_records import season_dir

# data-model.md § PMTiles Basemap File § Validation, research.md §3: a
# valid v3 archive's first 8 bytes are the ASCII string "PMTiles" followed
# by a version byte this reader supports -- confirmed against both the
# upstream JS reader's own check and a hex dump of the sample archive.
PMTILES_MAGIC = b"PMTiles"
PMTILES_MAX_SUPPORTED_VERSION = 3

# research.md §2: the base64-embedding classic-script asset's filename and
# the global variable it sets on window -- named once here so bundle.py and
# map-data.js's `basemap` object can never drift out of sync on either.
PMTILES_EMBED_FILENAME = "basemap-pmtiles.js"
PMTILES_EMBED_VARIABLE = "RKBY_PMTILES_BASE64"


class InvalidPMTilesFileError(Exception):
    """`<RKBY_DATA_DIR>/basemap.pmtiles` is missing, unreadable, too short,
    or fails the header check (FR-003, data-model.md § PMTiles Basemap File
    § Validation)."""


def validate_pmtiles_file(path: Path) -> None:
    """Stdlib-only 8-byte header check -- no PMTiles-parsing dependency
    (research.md §3): a valid v3 archive's first 8 bytes are ASCII
    "PMTiles" followed by a supported version byte (`<= 3`). Never parses
    beyond that; all real tile reading happens browser-side."""
    try:
        with path.open("rb") as handle:
            header = handle.read(8)
    except OSError as exc:
        raise InvalidPMTilesFileError(
            f"Cannot read PMTiles basemap file at {path}: {exc}"
        ) from exc

    if len(header) < 8:
        raise InvalidPMTilesFileError(
            f"PMTiles basemap file at {path} is too short to be a valid archive "
            f"(expected at least 8 bytes)"
        )

    magic, version = header[:7], header[7]
    if magic != PMTILES_MAGIC:
        raise InvalidPMTilesFileError(
            f"PMTiles basemap file at {path} does not start with the expected "
            f'"PMTiles" header'
        )
    if version > PMTILES_MAX_SUPPORTED_VERSION:
        raise InvalidPMTilesFileError(
            f"PMTiles basemap file at {path} uses unsupported spec version "
            f"{version} (this reader supports up to version "
            f"{PMTILES_MAX_SUPPORTED_VERSION})"
        )


def embed_basemap(
    interactive_map_dir: Path, pmtiles_path: Path, basemap_url: str | None = None
) -> dict:
    """Base64-encode `pmtiles_path`'s full contents into
    `interactive_map_dir/basemap-pmtiles.js` as a classic-script global
    (research.md §2 -- Chromium blocks fetch()/XHR of a sibling file when
    `index.html` is opened via `file://`, so the archive's bytes must reach
    the page through a `<script src>` load instead). Returns the
    embedded-mode `basemap` object for `map-data.js` (data-model.md §
    Bundled Map Data).

    When `basemap_url` is set (Story 4, research.md §8), the embed step is
    skipped entirely -- the archive's own bytes are never read into the
    bundle, only the maintainer-supplied URL is -- and the hosted-mode
    `basemap` object is returned instead. The local `pmtiles_path` file is
    still required and validated identically either way (FR-010); this
    parameter only changes what happens with its bytes afterward."""
    if basemap_url is not None:
        return {"mode": "hosted", "url": basemap_url}

    encoded = base64.b64encode(pmtiles_path.read_bytes()).decode("ascii")
    js = f'window.{PMTILES_EMBED_VARIABLE} = "{encoded}";\n'
    (interactive_map_dir / PMTILES_EMBED_FILENAME).write_text(js)
    return {
        "mode": "embedded",
        "file": PMTILES_EMBED_FILENAME,
        "variable": PMTILES_EMBED_VARIABLE,
    }


def _member_photo_source(data_dir: Path, member: dict) -> Path | None:
    """The merged member's own real photo file on disk (their latest-
    eligible season's photo), or None when they have no photo on file or
    the file is missing -- shared by `_resolve_photo` and
    `_resolve_full_photo` so the two can never disagree on which source
    photo a member has."""
    relative = member.get("photo_relative_path")
    if relative:
        source_path = season_dir(data_dir, member["photo_season_label"]) / relative
        if source_path.exists():
            return source_path
    return None


def _resolve_photo(data_dir: Path, member: dict) -> tuple[str, Path]:
    """Output-relative photo path + its real source file, or the Team
    Rynkeby mascot placeholder when the member has no photo on file
    (research.md §9) -- the same fallback rule as generate_member_maps.py's
    own `_photo_path`. Real photos are always re-encoded to a `.jpg`
    thumbnail by `copy_assets` regardless of their source extension, so the
    output name is always `.jpg` too."""
    source_path = _member_photo_source(data_dir, member)
    if source_path is not None:
        return f"photos/{member['match_key']}.jpg", source_path
    return "photos/placeholder.png", PLACEHOLDER_PHOTO_PATH


def _resolve_full_photo(data_dir: Path, member: dict) -> tuple[str, Path]:
    """Same source-resolution rule as `_resolve_photo`, but under its own
    `-full` output filename -- the hover popup's full (uncropped) photo is a
    distinct derived file from the marker's square-cropped thumbnail, so the
    two must never collide on disk. The placeholder mascot is shared
    unchanged with the marker thumbnail: it's already well within
    HOVER_PHOTO_MAX_PX bounds and isn't square-cropped, so there's nothing
    to re-derive for it."""
    source_path = _member_photo_source(data_dir, member)
    if source_path is not None:
        return f"photos/{member['match_key']}-full.jpg", source_path
    return "photos/placeholder.png", PLACEHOLDER_PHOTO_PATH


def assemble_map_data(
    data_dir: Path,
    interactive_map_dir: Path,
    seasons: list[str],
    merged_members: list[dict],
    pmtiles_path: Path,
    basemap_url: str | None = None,
) -> None:
    """Write `window.RKBY_MAP_DATA = {...};` to `interactive_map_dir /
    map-data.js`, matching contracts/map-data.schema.json exactly -- never
    address/phone/email/birthday/etc. (Principle I minimization, research.md
    §12). Each member's position is their own already-geocoded lat/lon,
    passed straight through with no projection (data-model.md § Merged
    Member, research.md §5); `basemap` embeds `pmtiles_path` via
    `embed_basemap`, or references `basemap_url` instead when set (Story 4,
    research.md §8)."""
    members_payload = []
    for member in merged_members:
        photo_path, _source_path = _resolve_photo(data_dir, member)
        full_photo_path, _full_source_path = _resolve_full_photo(data_dir, member)
        members_payload.append(
            {
                "match_key": member["match_key"],
                "name": f"{member['first_name']} {member['last_name']}".strip(),
                "num_previous_seasons": member["num_previous_seasons"],
                "photo": photo_path,
                "photo_full": full_photo_path,
                "lat": member["latitude"],
                "lon": member["longitude"],
                "seasons": member["seasons"],
            }
        )

    basemap = embed_basemap(interactive_map_dir, pmtiles_path, basemap_url=basemap_url)

    payload = {
        "seasons": sorted(seasons),
        "members": members_payload,
        "basemap": basemap,
    }

    map_data_js = (
        "window.RKBY_MAP_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n"
    )
    (interactive_map_dir / "map-data.js").write_text(map_data_js)


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
    a slow-loading map with many members. Each member's own full (uncropped)
    photo is also written for the hover popup, downscaled to fit within
    `HOVER_PHOTO_MAX_PX`, but without the marker thumbnail's square crop."""
    photos_dir = interactive_map_dir / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PLACEHOLDER_PHOTO_PATH, photos_dir / "placeholder.png")

    for member in merged_members:
        photo_path, source_path = _resolve_photo(data_dir, member)
        target_name = Path(photo_path).name
        if target_name != "placeholder.png":
            thumbnail = crop_square_thumbnail(source_path)
            thumbnail.save(photos_dir / target_name, "JPEG", quality=85)

        full_photo_path, full_source_path = _resolve_full_photo(data_dir, member)
        full_target_name = Path(full_photo_path).name
        if full_target_name != "placeholder.png":
            full_photo = scale_to_hover_size(full_source_path)
            full_photo.save(photos_dir / full_target_name, "JPEG", quality=85)

    shutil.copyfile(dist_index_html_path, interactive_map_dir / "index.html")
