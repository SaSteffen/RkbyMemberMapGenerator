"""Unit tests for `scripts/rkby_interactive_map/bundle.py`: PMTiles header
validation (research.md §3), base64 embedding (research.md §2), the
assembled `map-data.js` payload against `contracts/map-data.schema.json`,
photo/placeholder copying, and idempotent regeneration (data-model.md §
Idempotency)."""

import base64
import json
import os
from pathlib import Path

import jsonschema
import pytest

from scripts.rkby_interactive_map.bundle import (
    PMTILES_EMBED_FILENAME,
    PMTILES_EMBED_VARIABLE,
    InvalidPMTilesFileError,
    assemble_map_data,
    copy_assets,
    embed_basemap,
    validate_pmtiles_file,
)
from scripts.rkby_maps.rendering import PLACEHOLDER_PHOTO_PATH

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SCHEMA_PATH = (
    Path(__file__).parent.parent.parent
    / "specs"
    / "004-pmtiles-basemap"
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


def _write_pmtiles_file(
    path: Path,
    *,
    version: int = 3,
    magic: bytes = b"PMTiles",
    extra: bytes = b"\x00" * 16,
) -> None:
    path.write_bytes(magic + bytes([version]) + extra)


# --- validate_pmtiles_file (T005) --------------------------------------------------


def test_validate_pmtiles_file_accepts_a_valid_header(tmp_path):
    pmtiles_path = tmp_path / "basemap.pmtiles"
    _write_pmtiles_file(pmtiles_path)

    validate_pmtiles_file(pmtiles_path)  # must not raise


def test_validate_pmtiles_file_accepts_every_supported_version(tmp_path):
    for version in (0, 1, 2, 3):
        pmtiles_path = tmp_path / f"basemap-v{version}.pmtiles"
        _write_pmtiles_file(pmtiles_path, version=version)

        validate_pmtiles_file(pmtiles_path)  # must not raise


def test_validate_pmtiles_file_rejects_a_missing_file(tmp_path):
    pmtiles_path = tmp_path / "basemap.pmtiles"

    with pytest.raises(InvalidPMTilesFileError, match=str(pmtiles_path)):
        validate_pmtiles_file(pmtiles_path)


def test_validate_pmtiles_file_rejects_an_unreadable_file(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root bypasses file permission checks")

    pmtiles_path = tmp_path / "basemap.pmtiles"
    _write_pmtiles_file(pmtiles_path)
    pmtiles_path.chmod(0o000)

    try:
        with pytest.raises(InvalidPMTilesFileError, match=str(pmtiles_path)):
            validate_pmtiles_file(pmtiles_path)
    finally:
        pmtiles_path.chmod(0o644)


def test_validate_pmtiles_file_rejects_a_file_shorter_than_8_bytes(tmp_path):
    pmtiles_path = tmp_path / "basemap.pmtiles"
    pmtiles_path.write_bytes(b"PMTiles")  # 7 bytes -- one short of the header

    with pytest.raises(InvalidPMTilesFileError, match=str(pmtiles_path)):
        validate_pmtiles_file(pmtiles_path)


def test_validate_pmtiles_file_rejects_wrong_magic_bytes(tmp_path):
    pmtiles_path = tmp_path / "basemap.pmtiles"
    _write_pmtiles_file(pmtiles_path, magic=b"NOTATIL")

    with pytest.raises(InvalidPMTilesFileError, match=str(pmtiles_path)):
        validate_pmtiles_file(pmtiles_path)


def test_validate_pmtiles_file_rejects_an_unsupported_version_byte(tmp_path):
    pmtiles_path = tmp_path / "basemap.pmtiles"
    _write_pmtiles_file(pmtiles_path, version=4)

    with pytest.raises(InvalidPMTilesFileError, match=str(pmtiles_path)):
        validate_pmtiles_file(pmtiles_path)


# --- embed_basemap (T007) -----------------------------------------------------------


def test_embed_basemap_writes_a_base64_script_whose_decoded_bytes_round_trip(tmp_path):
    pmtiles_path = tmp_path / "basemap.pmtiles"
    original_bytes = b"PMTiles\x03" + os.urandom(256)
    pmtiles_path.write_bytes(original_bytes)
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()

    basemap = embed_basemap(interactive_map_dir, pmtiles_path)

    assert basemap == {
        "mode": "embedded",
        "file": PMTILES_EMBED_FILENAME,
        "variable": PMTILES_EMBED_VARIABLE,
    }
    script_text = (interactive_map_dir / PMTILES_EMBED_FILENAME).read_text()
    prefix = f"window.{PMTILES_EMBED_VARIABLE} = " + '"'
    assert script_text.startswith(prefix)
    encoded = script_text[len(prefix) :].rstrip("\n").rstrip(";").rstrip('"')
    assert base64.b64decode(encoded) == original_bytes


def test_embed_basemap_is_byte_identical_across_reruns(tmp_path):
    """SC-002's "consistent across runs": re-running with the same input
    file produces a byte-identical basemap-pmtiles.js."""
    pmtiles_path = tmp_path / "basemap.pmtiles"
    pmtiles_path.write_bytes(b"PMTiles\x03" + os.urandom(256))
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()

    embed_basemap(interactive_map_dir, pmtiles_path)
    first_run_bytes = (interactive_map_dir / PMTILES_EMBED_FILENAME).read_bytes()

    embed_basemap(interactive_map_dir, pmtiles_path)
    second_run_bytes = (interactive_map_dir / PMTILES_EMBED_FILENAME).read_bytes()

    assert first_run_bytes == second_run_bytes


# --- embed_basemap: hosted mode (T028, US4, research.md §8) ------------------------


def test_embed_basemap_returns_hosted_object_and_writes_no_script_when_url_is_set(
    tmp_path,
):
    pmtiles_path = tmp_path / "basemap.pmtiles"
    _write_pmtiles_file(pmtiles_path)
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()

    basemap = embed_basemap(
        interactive_map_dir,
        pmtiles_path,
        basemap_url="https://example.com/basemap.pmtiles",
    )

    assert basemap == {
        "mode": "hosted",
        "url": "https://example.com/basemap.pmtiles",
    }
    assert not (interactive_map_dir / PMTILES_EMBED_FILENAME).exists()


def test_embed_basemap_embedded_mode_is_unchanged_when_basemap_url_is_omitted(
    tmp_path,
):
    pmtiles_path = tmp_path / "basemap.pmtiles"
    original_bytes = b"PMTiles\x03" + os.urandom(64)
    pmtiles_path.write_bytes(original_bytes)
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()

    basemap = embed_basemap(interactive_map_dir, pmtiles_path)

    assert basemap == {
        "mode": "embedded",
        "file": PMTILES_EMBED_FILENAME,
        "variable": PMTILES_EMBED_VARIABLE,
    }
    assert (interactive_map_dir / PMTILES_EMBED_FILENAME).exists()


# --- map-data.js schema conformance (T009) ------------------------------------------


def _load_map_data(interactive_map_dir: Path) -> dict:
    text = (interactive_map_dir / "map-data.js").read_text()
    prefix = "window.RKBY_MAP_DATA = "
    assert text.startswith(prefix)
    json_text = text[len(prefix) :].rstrip("\n").rstrip(";")
    return json.loads(json_text)


def _assemble(tmp_path, interactive_map_dir, seasons, members, basemap_url=None):
    pmtiles_path = tmp_path / "basemap.pmtiles"
    if not pmtiles_path.exists():
        _write_pmtiles_file(pmtiles_path)
    assemble_map_data(
        tmp_path,
        interactive_map_dir,
        seasons,
        members,
        pmtiles_path,
        basemap_url=basemap_url,
    )


def test_assemble_map_data_uses_hosted_basemap_when_basemap_url_is_set(tmp_path):
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("jane-doe", 53.55, 9.99)]

    _assemble(
        tmp_path,
        interactive_map_dir,
        ["2025-26"],
        members,
        basemap_url="https://example.com/basemap.pmtiles",
    )

    payload = _load_map_data(interactive_map_dir)
    assert payload["basemap"] == {
        "mode": "hosted",
        "url": "https://example.com/basemap.pmtiles",
    }
    assert not (interactive_map_dir / PMTILES_EMBED_FILENAME).exists()


def test_assemble_map_data_validates_against_the_schema(tmp_path):
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("jane-doe", 53.55, 9.99, first_name="Jane", last_name="Doe")]

    _assemble(tmp_path, interactive_map_dir, ["2025-26"], members)

    payload = _load_map_data(interactive_map_dir)
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(instance=payload, schema=schema)


def test_assemble_map_data_emits_lat_lon_passthrough_not_pixel_positions(tmp_path):
    """Marker position is the member's own already-geocoded lat/lon, passed
    straight through with no projection (data-model.md § Merged Member,
    research.md §5) -- no more x/y pixel positions or image block."""
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("jane-doe", 53.55, 9.99)]

    _assemble(tmp_path, interactive_map_dir, ["2025-26"], members)

    payload = _load_map_data(interactive_map_dir)
    assert "image" not in payload
    member_payload = payload["members"][0]
    assert member_payload["lat"] == 53.55
    assert member_payload["lon"] == 9.99
    assert "x" not in member_payload
    assert "y" not in member_payload


def test_assemble_map_data_includes_the_embedded_basemap_object(tmp_path):
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("jane-doe", 53.55, 9.99)]

    _assemble(tmp_path, interactive_map_dir, ["2025-26"], members)

    payload = _load_map_data(interactive_map_dir)
    assert payload["basemap"] == {
        "mode": "embedded",
        "file": PMTILES_EMBED_FILENAME,
        "variable": PMTILES_EMBED_VARIABLE,
    }
    assert (interactive_map_dir / PMTILES_EMBED_FILENAME).exists()


def test_assemble_map_data_never_null_photo_field(tmp_path):
    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()
    members = [_member("no-photo-member", 53.55, 9.99, photo_relative_path=None)]

    _assemble(tmp_path, interactive_map_dir, ["2025-26"], members)

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

    _assemble(tmp_path, interactive_map_dir, ["2025-26"], members)

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

    _assemble(tmp_path, interactive_map_dir, ["2025-26"], members)

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

    _assemble(tmp_path, interactive_map_dir, ["2025-26"], members)

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


# --- Photo/placeholder copying (T015 of spec 003, unaffected by this feature) ------


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


# --- Idempotency (T015 of spec 003, data-model.md § Idempotency) -------------------


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


def test_copy_assets_copied_index_html_has_no_file_protocol_incompatible_markers(
    tmp_path,
):
    """Regression guard for research.md §10 (spec 003): Chromium blocks
    ES-module <script> loading of local files under file://, and Vite's own
    modulepreload polyfill would unconditionally fetch() at load time if it
    ever leaked into the build -- either would silently break the shared
    folder for recipients. The actually-built frontend bundle -- not a fake
    stand-in -- must never contain either marker.

    Unlike spec 003, a blanket "no fetch( anywhere in the bundle" check no
    longer holds: this feature (research.md §8, Story 4) intentionally
    bundles pmtiles's FetchSource, whose fetch() call is real but reachable
    only when RKBY_BASEMAP_URL selects hosted mode -- never invoked, and
    never executed at load time, in the default embedded build this test
    exercises (empty member list, no RKBY_BASEMAP_URL)."""
    from scripts.generate_interactive_map import FRONTEND_DIR

    dist_index_html_path = FRONTEND_DIR / "dist" / "index.html"
    if not dist_index_html_path.exists():
        pytest.skip(
            "frontend not built -- run `pnpm run build` in "
            "frontend/interactive-map/ first"
        )

    interactive_map_dir = tmp_path / "interactive_map"
    interactive_map_dir.mkdir()

    copy_assets(tmp_path, interactive_map_dir, [], dist_index_html_path)

    copied_html = (interactive_map_dir / "index.html").read_text()
    assert "modulepreload" not in copied_html
    assert 'type="module"' not in copied_html
