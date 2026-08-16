"""Unit tests for `scripts/generate_member_maps.py`'s CLI skeleton
(contracts/cli-and-env.md, FR-017): arg parsing (`--min-width-km`,
`--no-scale-bar`, no other switches), config loading (`RKBY_DATA_DIR` only,
no intranet credentials), and output-folder bootstrapping (`maps/` +
`.tile_cache/` creation and data-dir `.gitignore` creation/update before any
map file is written)."""

import re
from pathlib import Path

import pytest
import responses
import yaml
from PIL import Image

from scripts.generate_member_maps import (
    CANVAS_SIZE,
    DETAIL_MAP_EDGE_MARGIN_PX,
    DETAIL_MAP_PADDING_KM,
    Config,
    ConfigError,
    build_arg_parser,
    load_config,
    main,
)
from scripts.rkby_maps.basemap import TILE_SIZE, zoom_for_bounding_box
from scripts.rkby_maps.rendering import (
    NEUTRAL_COLOR,
    PHOTO_DIAMETER_PX,
    PLACEHOLDER_PHOTO_PATH,
    crop_circular_photo,
    role_color,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
TILE_URL_PATTERN = re.compile(r"https://tile\.openstreetmap\.org/\d+/\d+/\d+\.png")

# --- CLI arg parsing -----------------------------------------------------------


def test_min_width_km_defaults_to_15():
    args = build_arg_parser().parse_args([])
    assert args.min_width_km == 15


def test_min_width_km_accepts_a_positive_number():
    args = build_arg_parser().parse_args(["--min-width-km", "120"])
    assert args.min_width_km == 120


def test_min_width_km_rejects_a_non_positive_number():
    with pytest.raises(SystemExit):
        build_arg_parser().parse_args(["--min-width-km", "0"])
    with pytest.raises(SystemExit):
        build_arg_parser().parse_args(["--min-width-km", "-5"])


def test_no_scale_bar_defaults_to_off():
    args = build_arg_parser().parse_args([])
    assert args.no_scale_bar is False


def test_no_scale_bar_flag_sets_it_true():
    args = build_arg_parser().parse_args(["--no-scale-bar"])
    assert args.no_scale_bar is True


def test_parser_rejects_an_unknown_switch():
    with pytest.raises(SystemExit):
        build_arg_parser().parse_args(["--season", "2025-26"])


def test_parser_accepts_no_arguments_at_all():
    build_arg_parser().parse_args([])  # must not raise


# --- Config loading --------------------------------------------------------------


def test_load_config_requires_rkby_data_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("RKBY_DATA_DIR", raising=False)
    with pytest.raises(ConfigError):
        load_config()


def test_load_config_requires_rkby_data_dir_to_exist(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path / "does-not-exist"))
    with pytest.raises(ConfigError):
        load_config()


def test_load_config_does_not_require_any_intranet_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("RKBY_INTRANET_USERNAME", raising=False)
    monkeypatch.delenv("RKBY_INTRANET_PASSWORD", raising=False)
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    config = load_config()

    assert isinstance(config, Config)
    assert config.data_dir == tmp_path


# --- Output-folder bootstrapping (FR-017) -----------------------------------------


def test_main_creates_maps_and_tile_cache_dirs(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    exit_code = main([])

    assert exit_code == 0
    assert (tmp_path / "maps").is_dir()
    assert (tmp_path / ".tile_cache").is_dir()


def test_main_creates_a_gitignore_covering_maps_and_tile_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    main([])

    gitignore = (tmp_path / ".gitignore").read_text()
    assert "maps/" in gitignore
    assert ".tile_cache/" in gitignore


def test_main_appends_missing_entries_to_an_existing_gitignore(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    (tmp_path / ".gitignore").write_text("some_other_dir/\n")

    main([])

    gitignore = (tmp_path / ".gitignore").read_text()
    assert "some_other_dir/" in gitignore
    assert "maps/" in gitignore
    assert ".tile_cache/" in gitignore


def test_main_does_not_duplicate_gitignore_entries_already_present(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    (tmp_path / ".gitignore").write_text("maps/\n.tile_cache/\n")

    main([])

    gitignore = (tmp_path / ".gitignore").read_text()
    assert gitignore.count("maps/") == 1
    assert gitignore.count(".tile_cache/") == 1


def test_main_returns_nonzero_and_creates_nothing_when_config_is_invalid(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("RKBY_DATA_DIR", raising=False)

    exit_code = main([])

    assert exit_code != 0


def test_main_with_no_seasons_present_exits_zero(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    assert main([]) == 0


def test_main_accepts_min_width_km_and_no_scale_bar_flags(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    assert main(["--min-width-km", "100", "--no-scale-bar"]) == 0


# --- US1/US2 end-to-end shared helpers ----------------------------------------

# Read back rather than hardcoded: JPEG's RGB<->YCbCr round-trip isn't
# perfectly lossless even for a solid-color source.
SAMPLE_PHOTO_COLOR = (
    Image.open(FIXTURES_DIR / "sample_photo.jpg").convert("RGB").getpixel((0, 0))
)

# The placeholder mascot goes through the same crop-to-circle pipeline as a
# real member photo, so read back its rendered center pixel rather than a
# raw pixel off the source file.
_PLACEHOLDER_CENTER = PHOTO_DIAMETER_PX // 2
PLACEHOLDER_PHOTO_COLOR = (
    crop_circular_photo(PLACEHOLDER_PHOTO_PATH)
    .convert("RGB")
    .getpixel((_PLACEHOLDER_CENTER, _PLACEHOLDER_CENTER))
)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


_BASE_RECORD = {
    "first_name": "First",
    "last_name": "Last",
    "phone": None,
    "role": None,
    "birthday": None,
    "status": "yes",
    "excluded": False,
    "excluded_observed_at": None,
    "ignore": False,
    "photo": None,
    "latitude": None,
    "longitude": None,
}


def _write_record(a_dir: Path, match_key: str, **overrides) -> None:
    record = {**_BASE_RECORD, "match_key": match_key, "address": None}
    record.update(overrides)
    (a_dir / f"{match_key}.yaml").write_text(yaml.safe_dump(record))


def _register_common_mocks():
    responses.add(
        responses.GET,
        NOMINATIM_URL,
        body=(FIXTURES_DIR / "nominatim_response_match.json").read_text(),
        status=200,
        content_type="application/json",
    )
    responses.add(
        responses.GET,
        TILE_URL_PATTERN,
        body=(FIXTURES_DIR / "osm_tile_fixture.png").read_bytes(),
        status=200,
        content_type="image/png",
    )


@responses.activate
def test_overview_pin_map_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    a_dir.mkdir(parents=True)

    _write_record(
        a_dir,
        "jane-doe",
        first_name="Jane",
        last_name="Doe",
        address="Musterstr. 1, 22111 Hamburg, Germany",
        role="Rider",
    )
    _write_record(
        a_dir,
        "john-smith",
        first_name="John",
        last_name="Smith",
        address="Cached Street 5, 21000 Somewhere, Germany",
        role="Supporter",
        latitude=53.6,
        longitude=10.0,
    )
    _write_record(
        a_dir,
        "no-address-member",
        first_name="No",
        last_name="Address",
        role="Service Crew",
    )
    _write_record(
        a_dir,
        "excluded-member",
        first_name="Excluded",
        last_name="Member",
        address="Excluded Street 1, 20000 Hamburg, Germany",
        role="Rider",
        excluded=True,
        excluded_observed_at="2026-01-01T00:00:00+00:00",
    )
    _write_record(
        a_dir,
        "ignored-member",
        first_name="Ignored",
        last_name="Member",
        address="Ignored Street 1, 20000 Hamburg, Germany",
        role="Supporter",
        ignore=True,
    )

    _register_common_mocks()

    exit_code = main([])

    assert exit_code == 0

    # One overview pin map produced, containing both eligible members' role colors.
    map_path = tmp_path / "maps" / "2025_26_overview_pins.png"
    assert map_path.exists()
    image = Image.open(map_path).convert("RGB")
    present_colors = {pixel for pixel in image.getdata()}
    assert _hex_to_rgb(role_color("Rider")) in present_colors  # Jane's pin
    assert _hex_to_rgb(role_color("Supporter")) in present_colors  # John's pin

    # Nominatim was only called once -- for Jane; John's cached coords were reused.
    nominatim_calls = [
        call for call in responses.calls if call.request.url.startswith(NOMINATIM_URL)
    ]
    assert len(nominatim_calls) == 1

    # Jane's record now has cached coordinates from the mocked response.
    jane_record = yaml.safe_load((a_dir / "jane-doe.yaml").read_text())
    assert jane_record["latitude"] == pytest.approx(53.5505000)
    assert jane_record["longitude"] == pytest.approx(9.9935000)

    # John's pre-existing cached coordinates were never touched.
    john_record = yaml.safe_load((a_dir / "john-smith.yaml").read_text())
    assert john_record["latitude"] == 53.6
    assert john_record["longitude"] == 10.0

    # The no-address member is logged as skipped; excluded/ignored members are not.
    log_dir = tmp_path / "seasons" / "2025-26" / "logs"
    log_contents = "\n".join(p.read_text() for p in log_dir.glob("*.log"))
    assert "no-address-member" in log_contents
    assert "excluded-member" not in log_contents
    assert "ignored-member" not in log_contents


@responses.activate
def test_overview_pin_map_regeneration_removes_stale_files(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    a_dir.mkdir(parents=True)
    _write_record(
        a_dir,
        "jane-doe",
        first_name="Jane",
        last_name="Doe",
        address="Musterstr. 1, 22111 Hamburg, Germany",
        role="Rider",
    )
    _register_common_mocks()

    assert main([]) == 0

    maps_dir = tmp_path / "maps"
    stale_file = maps_dir / "2025_26_detail_pins_stale-cluster.png"
    stale_file.write_bytes(b"stale")

    assert main([]) == 0

    assert not stale_file.exists()
    assert (maps_dir / "2025_26_overview_pins.png").exists()


# --- US2 end-to-end: overview photo map (T020) -------------------------------------


@responses.activate
def test_overview_photo_map_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    a_dir.mkdir(parents=True)
    photos_dir = tmp_path / "seasons" / "2025-26" / "photos"
    photos_dir.mkdir(parents=True)

    _write_record(
        a_dir,
        "jane-doe",
        first_name="Jane",
        last_name="Doe",
        address="Musterstr. 1, 22111 Hamburg, Germany",
        role="Rider",
        photo="photos/jane-doe.jpg",
    )
    (photos_dir / "jane-doe.jpg").write_bytes(
        (FIXTURES_DIR / "sample_photo.jpg").read_bytes()
    )
    _write_record(
        a_dir,
        "john-smith",
        first_name="John",
        last_name="Smith",
        address="Cached Street 5, 21000 Somewhere, Germany",
        role="Supporter",
        latitude=53.6,
        longitude=10.0,
        # no photo on file -- gets the placeholder mascot on the photo map
    )

    _register_common_mocks()

    exit_code = main([])

    assert exit_code == 0

    pin_map_path = tmp_path / "maps" / "2025_26_overview_pins.png"
    photo_map_path = tmp_path / "maps" / "2025_26_overview_photos.png"
    assert pin_map_path.exists()
    assert photo_map_path.exists()

    # Both members still get a pin on the pin map.
    pin_colors = set(Image.open(pin_map_path).convert("RGB").getdata())
    assert _hex_to_rgb(role_color("Rider")) in pin_colors
    assert _hex_to_rgb(role_color("Supporter")) in pin_colors

    # Jane's real photo and John's placeholder mascot both appear on the photo
    # map -- no one is skipped from it for lacking a picture.
    photo_colors = set(Image.open(photo_map_path).convert("RGB").getdata())
    assert SAMPLE_PHOTO_COLOR in photo_colors
    assert PLACEHOLDER_PHOTO_COLOR in photo_colors


# --- US3 end-to-end: detail maps for crowded areas (T027) --------------------------


@responses.activate
def test_detail_maps_resolve_a_cluster_and_respect_the_fr014_exception(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    a_dir.mkdir(parents=True)
    photos_dir = tmp_path / "seasons" / "2025-26" / "photos"
    photos_dir.mkdir(parents=True)

    def _add(match_key, **overrides):
        overrides.setdefault("photo", f"photos/{match_key}.jpg")
        _write_record(a_dir, match_key, **overrides)
        (photos_dir / f"{match_key}.jpg").write_bytes(
            (FIXTURES_DIR / "sample_photo.jpg").read_bytes()
        )

    # A lone member ~223km away -- forces the overview's own bounding box (and
    # therefore its zoom) to stay far coarser than --min-width-km, so the
    # 3-member cluster below overlaps on the overview but can still be
    # resolved by a tighter, --min-width-km-floored detail map.
    _add(
        "anchor-member",
        first_name="Anchor",
        last_name="Member",
        address="Fernstr. 100, 12345 Woanders, Germany",
        role=None,
        latitude=50.9241,
        longitude=9.2255,
    )

    # Three members ~150-300m apart in Verden -- distinct roles, so a
    # resolved detail map shows three distinct role colors, while an
    # unresolved (still-merged) rendering would show only the neutral color.
    _add(
        "cluster-one",
        first_name="Cluster",
        last_name="One",
        address="Lindenstr. 1, 27283 Verden, Germany",
        role="Rider",
        latitude=52.9241,
        longitude=9.2255,
    )
    _add(
        "cluster-two",
        first_name="Cluster",
        last_name="Two",
        address="Lindenstr. 3, 27283 Verden, Germany",
        role="Supporter",
        latitude=52.9261,
        longitude=9.2255,
    )
    _add(
        "cluster-three",
        first_name="Cluster",
        last_name="Three",
        address="Bahnhofsallee 5, 27283 Verden, Germany",
        role="Service Crew",
        latitude=52.9241,
        longitude=9.2285,
    )

    # A pair sharing one identical address (FR-014) -- always overlaps (same
    # coordinates), but must never get its own detail map.
    _add(
        "fr014-a",
        first_name="Same",
        last_name="Address A",
        address="Marktplatz 2, 28195 Bremen, Germany",
        role="Rider",
        latitude=52.9691,
        longitude=9.2255,
    )
    _add(
        "fr014-b",
        first_name="Same",
        last_name="Address B",
        address="Marktplatz 2, 28195 Bremen, Germany",
        role="Rider",
        latitude=52.9691,
        longitude=9.2255,
    )

    _register_common_mocks()

    exit_code = main(["--min-width-km", "2"])

    assert exit_code == 0

    maps_dir = tmp_path / "maps"

    # A detail map was generated for the Verden cluster, for both variants.
    pin_detail_candidates = list(maps_dir.glob("2025_26_detail_pins_verden*.png"))
    photo_detail_candidates = list(maps_dir.glob("2025_26_detail_photos_verden*.png"))
    assert len(pin_detail_candidates) == 1
    assert len(photo_detail_candidates) == 1

    # At the tighter detail zoom, the cluster's three distinct roles are each
    # individually visible -- not merged into one neutral badge.
    pin_detail_colors = set(
        Image.open(pin_detail_candidates[0]).convert("RGB").getdata()
    )
    assert _hex_to_rgb(role_color("Rider")) in pin_detail_colors
    assert _hex_to_rgb(role_color("Supporter")) in pin_detail_colors
    assert _hex_to_rgb(role_color("Service Crew")) in pin_detail_colors

    # The FR-014 pair never gets its own detail map (no "bremen"-slugged file).
    bremen_candidates = list(maps_dir.glob("2025_26_detail_*bremen*.png"))
    assert bremen_candidates == []

    # The overview still exists and shows at least one merged/fallback marker
    # (FR-013) for a group that overlaps at the overview's own coarse scale.
    overview_path = maps_dir / "2025_26_overview_pins.png"
    assert overview_path.exists()
    overview_colors = set(Image.open(overview_path).convert("RGB").getdata())
    assert _hex_to_rgb(NEUTRAL_COLOR) in overview_colors


# --- Detail-map frame membership (research.md §5) -----------------------------------


@responses.activate
def test_detail_map_includes_frame_members_and_omits_ones_too_close_to_the_edge(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    a_dir.mkdir(parents=True)

    # A tight pair, ~20m apart -- the overlap group that triggers a detail map.
    cluster_lat, cluster_lon_a, cluster_lon_b = 52.9241, 9.2255, 9.2258
    _write_record(
        a_dir,
        "cluster-one",
        first_name="Cluster",
        last_name="One",
        address="Clusterstr. 1, 27283 Verden, Germany",
        role=None,
        latitude=cluster_lat,
        longitude=cluster_lon_a,
    )
    _write_record(
        a_dir,
        "cluster-two",
        first_name="Cluster",
        last_name="Two",
        address="Clusterstr. 2, 27283 Verden, Germany",
        role=None,
        latitude=cluster_lat,
        longitude=cluster_lon_b,
    )

    # Compute the exact frame (center/zoom) this detail map will be rendered
    # at -- a pure function of the pair's own bounding box, independent of
    # the other records below -- so the two extra members can be placed at
    # precise pixel offsets from it.
    min_width_km = 5
    center, zoom = zoom_for_bounding_box(
        [(cluster_lat, cluster_lon_a), (cluster_lat, cluster_lon_b)],
        padding_km=DETAIL_MAP_PADDING_KM,
        min_width_km=min_width_km,
        canvas_size=CANVAS_SIZE,
    )
    scale = TILE_SIZE * 2**zoom
    canvas_width, _canvas_height = CANVAS_SIZE

    def _lon_at_pixel_x(target_x_px: float) -> float:
        dx_px = target_x_px - canvas_width / 2
        return center[1] + dx_px * 360 / scale

    # Well clear of the edge margin -- must appear on the detail map even
    # though it's no part of the triggering pair.
    appearing_lon = _lon_at_pixel_x(DETAIL_MAP_EDGE_MARGIN_PX + 150)
    # Inside the edge margin -- must be omitted from this detail map.
    omitted_lon = _lon_at_pixel_x(DETAIL_MAP_EDGE_MARGIN_PX - 20)

    _write_record(
        a_dir,
        "appearing-member",
        first_name="Appearing",
        last_name="Member",
        address="Farstr. 1, 27283 Verden, Germany",
        role="Rider",
        latitude=center[0],
        longitude=appearing_lon,
    )
    _write_record(
        a_dir,
        "omitted-member",
        first_name="Omitted",
        last_name="Member",
        address="Edgestr. 1, 27283 Verden, Germany",
        role="Supporter",
        latitude=center[0],
        longitude=omitted_lon,
    )

    _register_common_mocks()

    exit_code = main(["--min-width-km", str(min_width_km)])
    assert exit_code == 0

    maps_dir = tmp_path / "maps"
    detail_candidates = list(maps_dir.glob("2025_26_detail_pins_*.png"))
    assert len(detail_candidates) == 1

    detail_colors = set(Image.open(detail_candidates[0]).convert("RGB").getdata())
    assert _hex_to_rgb(role_color("Rider")) in detail_colors
    assert _hex_to_rgb(role_color("Supporter")) not in detail_colors
