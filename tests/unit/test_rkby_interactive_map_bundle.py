"""Unit tests for `scripts/rkby_interactive_map/bundle.py`: deterministic
pixel positioning (research.md §3), the assembled `map-data.js` payload
against `contracts/map-data.schema.json`, photo/placeholder copying, and
idempotent regeneration (data-model.md § Idempotency)."""

import json
from pathlib import Path

import jsonschema

from scripts.rkby_interactive_map import bundle as bundle_module
from scripts.rkby_interactive_map.bundle import (
    assemble_map_data,
    compute_positions,
    copy_assets,
    generate_basemap,
)
from scripts.rkby_maps.rendering import PLACEHOLDER_PHOTO_PATH

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SCHEMA_PATH = (
    Path(__file__).parent.parent.parent
    / "specs"
    / "003-interactive-photo-map"
    / "contracts"
    / "map-data.schema.json"
)


def _member(match_key, latitude, longitude, **overrides):
    base = {
        "match_key": match_key,
        "first_name": "First",
        "last_name": "Last",
        "num_previous_seasons": None,
        "photo_relative_path": None,
        "photo_season_label": "2025-26",
        "latitude": latitude,
        "longitude": longitude,
        "seasons": {"2025-26": {"role": "Rider", "additional_roles": []}},
    }
    base.update(overrides)
    return base


# --- compute_positions determinism (T009) ----------------------------------------


def test_compute_positions_is_order_independent():
    members = [
        _member("alice", 53.55, 9.99),
        _member("bob", 53.60, 10.05),
        _member("carol", 53.50, 9.95),
    ]

    positions_forward, center_forward, zoom_forward = compute_positions(members)
    positions_reversed, center_reversed, zoom_reversed = compute_positions(
        list(reversed(members))
    )

    assert center_forward == center_reversed
    assert zoom_forward == zoom_reversed
    for match_key in ("alice", "bob", "carol"):
        assert positions_forward[match_key] == positions_reversed[match_key]


def test_compute_positions_handles_zero_members():
    positions, center, zoom = compute_positions([])

    assert positions == {}
    assert center is not None
    assert isinstance(zoom, int)


# --- map-data.js schema conformance (T015) ----------------------------------------


def _load_map_data(interactive_map_dir: Path) -> dict:
    text = (interactive_map_dir / "map-data.js").read_text()
    prefix = "window.RKBY_MAP_DATA = "
    assert text.startswith(prefix)
    json_text = text[len(prefix) :].rstrip("\n").rstrip(";")
    return json.loads(json_text)


def test_assemble_map_data_validates_against_the_schema(tmp_path):
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("jane-doe", 53.55, 9.99, first_name="Jane", last_name="Doe")]

    assemble_map_data(tmp_path, interactive_map_dir, ["2025-26"], members)

    payload = _load_map_data(interactive_map_dir)
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(instance=payload, schema=schema)


def test_assemble_map_data_describes_the_base_image_and_tile_levels(tmp_path):
    """The base (1x) image is always a single file (research.md §2); any
    resolution levels beyond it are described as cols x rows chunk grids,
    not files, sorted ascending by scale (research.md §2 2nd addendum)."""
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("jane-doe", 53.55, 9.99)]

    assemble_map_data(tmp_path, interactive_map_dir, ["2025-26"], members)

    payload = _load_map_data(interactive_map_dir)
    image = payload["image"]
    assert image["file"] == "basemap.jpg"
    assert image["tileSize"] > 0
    scales = [level["scale"] for level in image["tileLevels"]]
    assert scales == sorted(scales)
    for level in image["tileLevels"]:
        assert level["cols"] > 0
        assert level["rows"] > 0


def test_assemble_map_data_tile_level_grids_cover_the_full_scaled_canvas(tmp_path):
    """Each tileLevels entry's cols x rows grid, at tileSize per chunk, must
    cover at least the level's own (base width/height * scale) canvas --
    the same bounding box as every other level, just chunked instead of one
    file (research.md §2 2nd addendum)."""
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("jane-doe", 53.55, 9.99)]

    assemble_map_data(tmp_path, interactive_map_dir, ["2025-26"], members)

    payload = _load_map_data(interactive_map_dir)
    image = payload["image"]
    for level in image["tileLevels"]:
        scale = level["scale"]
        assert level["cols"] * image["tileSize"] >= image["width"] * scale
        assert level["rows"] * image["tileSize"] >= image["height"] * scale


def test_assemble_map_data_never_null_photo_field(tmp_path):
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("no-photo-member", 53.55, 9.99, photo_relative_path=None)]

    assemble_map_data(tmp_path, interactive_map_dir, ["2025-26"], members)

    payload = _load_map_data(interactive_map_dir)
    assert payload["members"][0]["photo"] == "photos/placeholder.png"


def test_assemble_map_data_includes_a_never_null_full_photo_field(tmp_path):
    """The hover popup's full (uncropped) photo (spec addendum: full picture
    on hover) is a separate field from the marker's square-cropped `photo`,
    following the same never-null placeholder-fallback rule (research.md
    §9)."""
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("no-photo-member", 53.55, 9.99, photo_relative_path=None)]

    assemble_map_data(tmp_path, interactive_map_dir, ["2025-26"], members)

    payload = _load_map_data(interactive_map_dir)
    assert payload["members"][0]["photo_full"] == "photos/placeholder.png"


def test_assemble_map_data_full_photo_uses_a_distinct_filename_from_the_marker_thumbnail(
    tmp_path,
):
    season_photos_dir = tmp_path / "seasons" / "2025-26" / "photos"
    season_photos_dir.mkdir(parents=True)
    (season_photos_dir / "jane-doe.jpg").write_bytes(
        (FIXTURES_DIR / "sample_photo.jpg").read_bytes()
    )
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [
        _member(
            "jane-doe",
            53.55,
            9.99,
            photo_relative_path="photos/jane-doe.jpg",
            photo_season_label="2025-26",
        )
    ]

    assemble_map_data(tmp_path, interactive_map_dir, ["2025-26"], members)

    payload = _load_map_data(interactive_map_dir)
    member_payload = payload["members"][0]
    assert member_payload["photo"] != member_payload["photo_full"]


def test_assemble_map_data_excludes_non_popup_fields(tmp_path):
    """Principle I minimization (research.md §12): the payload must never
    carry address/phone/email/etc -- enforced structurally by
    additionalProperties: false in the schema, checked again explicitly."""
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("jane-doe", 53.55, 9.99)]

    assemble_map_data(tmp_path, interactive_map_dir, ["2025-26"], members)

    payload = _load_map_data(interactive_map_dir)
    member_payload = payload["members"][0]
    for forbidden_field in (
        "address",
        "phone",
        "email",
        "birthday",
        "excluded",
        "ignore",
    ):
        assert forbidden_field not in member_payload


# --- Photo/placeholder copying (T015) ----------------------------------------------


def test_copy_assets_copies_a_members_own_photo(tmp_path):
    season_photos_dir = tmp_path / "seasons" / "2025-26" / "photos"
    season_photos_dir.mkdir(parents=True)
    (season_photos_dir / "jane-doe.jpg").write_bytes(
        (FIXTURES_DIR / "sample_photo.jpg").read_bytes()
    )
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    dist_index = tmp_path / "dist_index.html"
    dist_index.write_text("<html>fake build output</html>")

    members = [
        _member(
            "jane-doe",
            53.55,
            9.99,
            photo_relative_path="photos/jane-doe.jpg",
            photo_season_label="2025-26",
        )
    ]

    copy_assets(tmp_path, interactive_map_dir, members, dist_index)

    copied = interactive_map_dir / "photos" / "jane-doe.jpg"
    assert copied.exists()
    assert (interactive_map_dir / "photos" / "placeholder.png").exists()
    assert (
        interactive_map_dir / "index.html"
    ).read_text() == "<html>fake build output</html>"


def test_copy_assets_downscales_a_members_photo_to_a_square_thumbnail(tmp_path):
    """Perf fix: full-resolution source photos must never ship as-is -- the
    browser only ever renders the marker at a fixed 40 CSS-px, so shipping
    (and decoding) full-size originals for hundreds of members was the main
    cause of a slow-loading map."""
    from PIL import Image

    from scripts.rkby_maps.rendering import INTERACTIVE_MAP_THUMBNAIL_PX

    season_photos_dir = tmp_path / "seasons" / "2025-26" / "photos"
    season_photos_dir.mkdir(parents=True)
    (season_photos_dir / "jane-doe.jpg").write_bytes(
        (FIXTURES_DIR / "sample_photo.jpg").read_bytes()
    )
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    dist_index = tmp_path / "dist_index.html"
    dist_index.write_text("<html></html>")

    members = [
        _member(
            "jane-doe",
            53.55,
            9.99,
            photo_relative_path="photos/jane-doe.jpg",
            photo_season_label="2025-26",
        )
    ]

    copy_assets(tmp_path, interactive_map_dir, members, dist_index)

    thumbnail = Image.open(interactive_map_dir / "photos" / "jane-doe.jpg")
    assert thumbnail.size == (
        INTERACTIVE_MAP_THUMBNAIL_PX,
        INTERACTIVE_MAP_THUMBNAIL_PX,
    )


def test_copy_assets_writes_a_full_uncropped_hover_photo_scaled_to_hd_bounds(tmp_path):
    """The hover popup shows the applicant's full picture, not just the
    marker's square-cropped thumbnail -- but an oversized source photo must
    still be downscaled (to HOVER_PHOTO_MAX_PX, aspect ratio preserved) so
    it never ships/decodes at its original resolution."""
    from PIL import Image

    from scripts.rkby_maps.rendering import HOVER_PHOTO_MAX_PX

    season_photos_dir = tmp_path / "seasons" / "2025-26" / "photos"
    season_photos_dir.mkdir(parents=True)
    # Exactly 2x Full HD at the same 16:9 ratio -- lands on HOVER_PHOTO_MAX_PX
    # exactly, no rounding ambiguity in the assertion.
    Image.new("RGB", (3840, 2160), color=(10, 20, 30)).save(
        season_photos_dir / "jane-doe.jpg", "JPEG"
    )
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    dist_index = tmp_path / "dist_index.html"
    dist_index.write_text("<html></html>")

    members = [
        _member(
            "jane-doe",
            53.55,
            9.99,
            photo_relative_path="photos/jane-doe.jpg",
            photo_season_label="2025-26",
        )
    ]

    copy_assets(tmp_path, interactive_map_dir, members, dist_index)

    payload_photo_full = "jane-doe-full.jpg"
    full_photo = Image.open(interactive_map_dir / "photos" / payload_photo_full)
    assert full_photo.size == HOVER_PHOTO_MAX_PX
    # Not square-cropped, unlike the marker thumbnail.
    assert full_photo.size[0] != full_photo.size[1]


def test_copy_assets_does_not_upscale_a_smaller_than_hd_photo_for_the_hover_popup(
    tmp_path,
):
    from PIL import Image

    season_photos_dir = tmp_path / "seasons" / "2025-26" / "photos"
    season_photos_dir.mkdir(parents=True)
    (season_photos_dir / "jane-doe.jpg").write_bytes(
        (FIXTURES_DIR / "sample_photo.jpg").read_bytes()
    )
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    dist_index = tmp_path / "dist_index.html"
    dist_index.write_text("<html></html>")

    members = [
        _member(
            "jane-doe",
            53.55,
            9.99,
            photo_relative_path="photos/jane-doe.jpg",
            photo_season_label="2025-26",
        )
    ]

    copy_assets(tmp_path, interactive_map_dir, members, dist_index)

    full_photo = Image.open(interactive_map_dir / "photos" / "jane-doe-full.jpg")
    assert full_photo.size == (120, 80)


def test_copy_assets_falls_back_to_placeholder_when_no_photo_on_file(tmp_path):
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    dist_index = tmp_path / "dist_index.html"
    dist_index.write_text("<html></html>")

    members = [_member("no-photo-member", 53.55, 9.99, photo_relative_path=None)]

    copy_assets(tmp_path, interactive_map_dir, members, dist_index)

    placeholder = interactive_map_dir / "photos" / "placeholder.png"
    assert placeholder.exists()
    assert placeholder.read_bytes() == PLACEHOLDER_PHOTO_PATH.read_bytes()
    # No stray per-member file was created for the photo-less member.
    assert list((interactive_map_dir / "photos").iterdir()) == [placeholder]


def test_copy_assets_falls_back_to_placeholder_when_photo_file_is_missing_on_disk(
    tmp_path,
):
    """photo_relative_path is set but the actual file was never fetched --
    must not crash, must fall back cleanly (mirrors generate_member_maps.py's
    _photo_path existence check)."""
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    dist_index = tmp_path / "dist_index.html"
    dist_index.write_text("<html></html>")

    members = [
        _member(
            "ghost-photo-member",
            53.55,
            9.99,
            photo_relative_path="photos/does-not-exist.jpg",
            photo_season_label="2025-26",
        )
    ]

    copy_assets(tmp_path, interactive_map_dir, members, dist_index)

    assert list((interactive_map_dir / "photos").iterdir()) == [
        interactive_map_dir / "photos" / "placeholder.png"
    ]


# --- Idempotency (T015, data-model.md § Idempotency) -------------------------------


def test_regeneration_leaves_no_stale_photo_from_a_removed_member(tmp_path):
    season_photos_dir = tmp_path / "seasons" / "2025-26" / "photos"
    season_photos_dir.mkdir(parents=True)
    (season_photos_dir / "jane-doe.jpg").write_bytes(
        (FIXTURES_DIR / "sample_photo.jpg").read_bytes()
    )
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    dist_index = tmp_path / "dist_index.html"
    dist_index.write_text("<html></html>")

    first_run_members = [
        _member(
            "jane-doe",
            53.55,
            9.99,
            photo_relative_path="photos/jane-doe.jpg",
            photo_season_label="2025-26",
        )
    ]
    copy_assets(tmp_path, interactive_map_dir, first_run_members, dist_index)
    assert (interactive_map_dir / "photos" / "jane-doe.jpg").exists()
    assert (interactive_map_dir / "photos" / "jane-doe-full.jpg").exists()

    # Regeneration always starts from a freshly emptied interactive_map/
    # (generate_interactive_map.py's _ensure_interactive_map_dir) -- simulate
    # that here, then re-run with jane-doe no longer eligible.
    import shutil

    shutil.rmtree(interactive_map_dir)
    interactive_map_dir.mkdir()

    copy_assets(tmp_path, interactive_map_dir, [], dist_index)

    assert not (interactive_map_dir / "photos" / "jane-doe.jpg").exists()
    assert not (interactive_map_dir / "photos" / "jane-doe-full.jpg").exists()


def test_generate_basemap_writes_a_jpeg_of_canvas_size(tmp_path, monkeypatch):
    """Uses the real stitch_basemap/tile-fetch path against a mocked HTTP
    tile response, matching the existing map-generator tests' pattern.
    CANVAS_SIZE is patched tiny so the tiled resolution levels
    (BASEMAP_LEVELS' scale=2/4/8/16, always generated alongside the base
    image) stay fast to stitch here -- production runs use the real,
    much larger CANVAS_SIZE (research.md §2 2nd addendum has the real
    chunk-count numbers)."""
    import re

    import responses
    from PIL import Image

    monkeypatch.setattr(bundle_module, "CANVAS_SIZE", (64, 64))

    tile_url_pattern = re.compile(r"https://tile\.openstreetmap\.org/\d+/\d+/\d+\.png")
    tile_cache_dir = tmp_path / ".tile_cache"
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("jane-doe", 53.55, 9.99)]

    with responses.RequestsMock() as mocked:
        mocked.add(
            responses.GET,
            tile_url_pattern,
            body=(FIXTURES_DIR / "osm_tile_fixture.png").read_bytes(),
            status=200,
            content_type="image/png",
        )
        generate_basemap(interactive_map_dir, members, tile_cache_dir)

    image = Image.open(interactive_map_dir / "basemap.jpg")
    assert image.size == bundle_module.CANVAS_SIZE


def test_generate_basemap_writes_uniformly_sized_tile_chunks(tmp_path, monkeypatch):
    """research.md §2 2nd addendum: resolution levels beyond the base are
    written as a grid of tileSize-square chunk files under
    tiles/<scale>/<x>_<y>.jpg, never one big image -- including the grid's
    last (partial) row/column, padded out to a full tileSize square so the
    frontend never needs partial-tile handling."""
    import re

    import responses
    from PIL import Image

    monkeypatch.setattr(bundle_module, "CANVAS_SIZE", (64, 64))

    tile_url_pattern = re.compile(r"https://tile\.openstreetmap\.org/\d+/\d+/\d+\.png")
    tile_cache_dir = tmp_path / ".tile_cache"
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("jane-doe", 53.55, 9.99)]

    with responses.RequestsMock() as mocked:
        mocked.add(
            responses.GET,
            tile_url_pattern,
            body=(FIXTURES_DIR / "osm_tile_fixture.png").read_bytes(),
            status=200,
            content_type="image/png",
        )
        generate_basemap(interactive_map_dir, members, tile_cache_dir)

    tiles_root = interactive_map_dir / "tiles"
    scale_dirs = sorted(tiles_root.iterdir(), key=lambda p: int(p.name))
    assert scale_dirs  # at least one tiled level exists at this bounding box

    first_level_dir = scale_dirs[0]
    chunk_files = list(first_level_dir.glob("*.jpg"))
    assert chunk_files
    for chunk_file in chunk_files:
        assert Image.open(chunk_file).size == (
            bundle_module.TILE_PX,
            bundle_module.TILE_PX,
        )


def test_generate_basemap_never_rewrites_an_already_baked_tile_chunk(
    tmp_path, monkeypatch
):
    """A chunk file already on disk (baked by an earlier run) is reused as
    -- is: generate_basemap must not re-stitch it or re-fetch the OSM tiles
    under it, so a fully-baked tiles/ tree makes later runs a no-network
    no-op for tiles (tiles/ is also never deleted -- see
    generate_interactive_map._ensure_interactive_map_dir)."""
    import re

    import responses

    monkeypatch.setattr(bundle_module, "CANVAS_SIZE", (64, 64))

    tile_url_pattern = re.compile(r"https://tile\.openstreetmap\.org/\d+/\d+/\d+\.png")
    tile_cache_dir = tmp_path / ".tile_cache"
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("jane-doe", 53.55, 9.99)]

    with responses.RequestsMock() as mocked:
        mocked.add(
            responses.GET,
            tile_url_pattern,
            body=(FIXTURES_DIR / "osm_tile_fixture.png").read_bytes(),
            status=200,
            content_type="image/png",
        )
        generate_basemap(interactive_map_dir, members, tile_cache_dir)

    tiles_root = interactive_map_dir / "tiles"
    scale_dirs = sorted(tiles_root.iterdir(), key=lambda p: int(p.name))
    first_chunk = min((scale_dirs[0]).glob("*.jpg"))
    sentinel = b"already-baked-sentinel-bytes"
    first_chunk.write_bytes(sentinel)

    with responses.RequestsMock(assert_all_requests_are_fired=False) as mocked:
        mocked.add(
            responses.GET,
            tile_url_pattern,
            body=(FIXTURES_DIR / "osm_tile_fixture.png").read_bytes(),
            status=200,
            content_type="image/png",
        )
        generate_basemap(interactive_map_dir, members, tile_cache_dir)

    assert first_chunk.read_bytes() == sentinel
