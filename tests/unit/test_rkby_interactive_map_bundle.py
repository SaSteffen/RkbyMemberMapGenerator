"""Unit tests for `scripts/rkby_interactive_map/bundle.py`: deterministic
pixel positioning (research.md §3), the assembled `map-data.js` payload
against `contracts/map-data.schema.json`, photo/placeholder copying, and
idempotent regeneration (data-model.md § Idempotency)."""

import json
from pathlib import Path

import jsonschema

from scripts.rkby_interactive_map.bundle import (
    CANVAS_SIZE,
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


def test_assemble_map_data_lists_the_base_basemap_level(tmp_path):
    """Every run bakes at least the base 1x level (research.md §2 addendum);
    higher-resolution levels are only added when the bounding box has room
    for them, covered separately in test_rkby_maps... this just checks the
    always-present base entry's shape."""
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("jane-doe", 53.55, 9.99)]

    assemble_map_data(tmp_path, interactive_map_dir, ["2025-26"], members)

    payload = _load_map_data(interactive_map_dir)
    levels = payload["image"]["levels"]
    assert levels[0] == {"file": "basemap.jpg", "scale": 1}
    assert [level["scale"] for level in levels] == sorted(
        level["scale"] for level in levels
    )


def test_assemble_map_data_never_null_photo_field(tmp_path):
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("no-photo-member", 53.55, 9.99, photo_relative_path=None)]

    assemble_map_data(tmp_path, interactive_map_dir, ["2025-26"], members)

    payload = _load_map_data(interactive_map_dir)
    assert payload["members"][0]["photo"] == "photos/placeholder.png"


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

    # Regeneration always starts from a freshly emptied interactive_map/
    # (generate_interactive_map.py's _ensure_interactive_map_dir) -- simulate
    # that here, then re-run with jane-doe no longer eligible.
    import shutil

    shutil.rmtree(interactive_map_dir)
    interactive_map_dir.mkdir()

    copy_assets(tmp_path, interactive_map_dir, [], dist_index)

    assert not (interactive_map_dir / "photos" / "jane-doe.jpg").exists()


def test_generate_basemap_writes_a_jpeg_of_canvas_size(tmp_path):
    """Uses the real stitch_basemap/tile-fetch path against a mocked HTTP
    tile response, matching the existing map-generator tests' pattern."""
    import re

    import responses
    from PIL import Image

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
    assert image.size == CANVAS_SIZE


def test_generate_basemap_writes_every_resolution_level_at_the_same_bounding_box(
    tmp_path,
):
    """research.md §2 addendum: basemap@2x.jpg/@4x.jpg cover the identical
    geographic area as basemap.jpg, just at a proportionally larger canvas
    -- so each level's own pixel size is an exact multiple of CANVAS_SIZE."""
    import re

    import responses
    from PIL import Image

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

    for scale, file_name in ((1, "basemap.jpg"), (2, "basemap@2x.jpg")):
        image = Image.open(interactive_map_dir / file_name)
        assert image.size == (CANVAS_SIZE[0] * scale, CANVAS_SIZE[1] * scale)
