"""Generate role-colored pin maps and circular-photo maps per season from a
local, human-editable, git-backed data store already populated by
`scrape_applicants.py` (001).

See specs/002-map-generator/ (spec.md, plan.md, research.md, data-model.md,
contracts/) for the full design. Configuration is env-var only:

    RKBY_DATA_DIR  absolute path to the local, git-backed data repository
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.rkby_maps.basemap import (
    lonlat_to_pixel,
    meters_per_pixel,
    stitch_basemap,
    zoom_for_bounding_box,
    zoom_for_min_width_km,
)
from scripts.rkby_maps.clustering import (
    detail_map_slug,
    find_overlap_groups,
    is_fr014_exception,
)
from scripts.rkby_maps.geocoding import geocode_record_if_needed
from scripts.rkby_maps.rendering import (
    PHOTO_RADIUS_PX,
    PIN_RADIUS_PX,
    crop_circular_photo,
    draw_attribution,
    draw_merged_pin,
    draw_offset_photo_circles,
    draw_photo_circle,
    draw_pin,
    draw_scale_bar,
    merged_role_color,
    role_color,
)
from scripts.rkby_records import (
    _dump_record_yaml,
    applicants_dir,
    auto_commit,
    discover_seasons,
    load_existing_records,
    season_dir,
    setup_run_logger,
)

DEFAULT_MIN_WIDTH_KM = 50
CANVAS_SIZE = (1600, 1200)
# Geographic center of Germany -- used only as the overview map's center for
# a season with zero plottable members (Assumptions: "Empty/degenerate
# seasons" still produce a near-empty overview rather than being skipped).
DEFAULT_CENTER = (51.1657, 10.4515)
# Fixed padding margin (research.md §5) added around a bounding box -- of
# either an overlap group (detail maps) or the season's full member set
# (the overview) -- before flooring the result at --min-width-km.
DETAIL_MAP_PADDING_KM = 0.5

_GITIGNORE_ENTRIES = ("maps/", ".tile_cache/")


class ConfigError(Exception):
    """A required environment variable is missing or invalid."""


@dataclass(frozen=True)
class Config:
    data_dir: Path


def load_config() -> Config:
    """Validate all required env vars are present and usable before any
    network request or file write (mirrors scrape_applicants.load_config)."""
    raw_data_dir = os.environ.get("RKBY_DATA_DIR")
    if not raw_data_dir:
        raise ConfigError("Missing required environment variable: RKBY_DATA_DIR")

    data_dir = Path(raw_data_dir)
    if not data_dir.is_dir():
        raise ConfigError(
            f"RKBY_DATA_DIR does not exist or is not a directory: {data_dir}"
        )

    return Config(data_dir=data_dir)


# --- CLI arg parsing (contracts/cli-and-env.md, FR-018) ------------------------


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive number: {value!r}")
    return parsed


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate role-colored pin maps and circular-photo maps for every "
            "season in RKBY_DATA_DIR."
        )
    )
    parser.add_argument(
        "--min-width-km",
        type=_positive_float,
        default=DEFAULT_MIN_WIDTH_KM,
        help=(
            "Lower bound, in kilometers, on the real-world width every "
            f"generated map must cover (default: {DEFAULT_MIN_WIDTH_KM})."
        ),
    )
    parser.add_argument(
        "--no-scale-bar",
        action="store_true",
        help="Suppress the bottom-right scale-bar ruler on every generated map.",
    )
    return parser


# --- Output-folder bootstrapping (research.md §12, FR-017) ---------------------


def _ensure_output_dirs_and_gitignore(data_dir: Path) -> None:
    """Create `maps/` and `.tile_cache/` under `data_dir` if absent, and
    create/update the data-dir `.gitignore` so both are ignored -- before any
    map file is written this run."""
    (data_dir / "maps").mkdir(exist_ok=True)
    (data_dir / ".tile_cache").mkdir(exist_ok=True)

    gitignore_path = data_dir / ".gitignore"
    existing_lines = (
        gitignore_path.read_text().splitlines() if gitignore_path.exists() else []
    )
    missing_entries = [
        entry for entry in _GITIGNORE_ENTRIES if entry not in existing_lines
    ]
    if missing_entries:
        updated_lines = [*existing_lines, *missing_entries]
        gitignore_path.write_text("\n".join(updated_lines) + "\n")


# --- Season processing: eligibility, geocoding, and overview pin map (US1) -----


def _season_file_prefix(season_label: str) -> str:
    """FR-016: `YYYY_YY` underscore form of a season's hyphenated folder name."""
    return season_label.replace("-", "_")


def _resolve_plottable_members(
    data_dir: Path, season_label: str, logger: logging.Logger
) -> list[dict]:
    """Load a season's records, apply the shared eligibility filter (FR-003:
    not excluded/ignored, has an address), geocode-and-cache each eligible
    member still missing coordinates (fill-empty-only, research.md §11), and
    log-and-skip (FR-006) anyone left without a resolvable address. Excluded/
    ignored members are silently left out entirely -- never logged
    (Assumptions: opt-out)."""
    records = load_existing_records(data_dir, season_label)
    considered = [
        record
        for record in records.values()
        if not record.get("excluded") and not record.get("ignore")
    ]

    a_dir = applicants_dir(data_dir, season_label)
    plottable = []
    for record in considered:
        if not record.get("address"):
            logger.warning(
                "%s skipped from all maps: no address on file", record["match_key"]
            )
            continue

        if geocode_record_if_needed(record):
            (a_dir / f"{record['match_key']}.yaml").write_text(
                _dump_record_yaml(record)
            )

        if record.get("latitude") is None:
            logger.warning(
                "%s skipped from all maps: address could not be geocoded: %s",
                record["match_key"],
                record["address"],
            )
            continue

        plottable.append(record)

    return plottable


def _overview_center_and_zoom(
    members: list[dict], min_width_km: float
) -> tuple[tuple[float, float], int]:
    """The overview's own bounding box (all of `members`, plus a fixed
    padding margin), floored at `min_width_km` (research.md §5's sizing
    formula, applied here to the full member set rather than a single
    overlap group) -- a nationally-spread team naturally renders wider than
    the configured minimum so everyone fits, while a tight regional team is
    floored at the minimum. Computed independently per variant (pin overview
    vs. photo overview), since their eligible member sets can differ."""
    if not members:
        zoom = zoom_for_min_width_km(
            min_width_km=min_width_km,
            latitude=DEFAULT_CENTER[0],
            canvas_width_px=CANVAS_SIZE[0],
        )
        return DEFAULT_CENTER, zoom

    points = [(record["latitude"], record["longitude"]) for record in members]
    return zoom_for_bounding_box(
        points,
        padding_km=DETAIL_MAP_PADDING_KM,
        min_width_km=min_width_km,
        canvas_size=CANVAS_SIZE,
    )


def _delete_existing_season_maps(maps_dir: Path, season_prefix: str) -> None:
    """Idempotent regeneration (data-model.md § Local Data Repository): a
    stale map from a since-changed data set is deleted, not left alongside a
    fresh set."""
    for stale_map in maps_dir.glob(f"{season_prefix}_*.png"):
        stale_map.unlink()


def _pixel_positions(
    records: list[dict], center: tuple[float, float], zoom: int
) -> dict[str, tuple[float, float]]:
    return {
        record["match_key"]: lonlat_to_pixel(
            record["latitude"],
            record["longitude"],
            center=center,
            zoom=zoom,
            canvas_size=CANVAS_SIZE,
        )
        for record in records
    }


def _group_position(
    group: list[str], positions: dict[str, tuple[float, float]]
) -> tuple[float, float]:
    xs = [positions[key][0] for key in group]
    ys = [positions[key][1] for key in group]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _draw_pin_layer(
    canvas, records: list[dict], center: tuple[float, float], zoom: int
) -> tuple[list[list[str]], dict[str, dict]]:
    """Draw an individual role-colored pin per record, or one merged
    fallback pin per group overlapping at this canvas's own scale
    (FR-011/FR-013, research.md §4/§8). Returns the detected overlap groups
    plus a match_key -> record lookup, for detail-map generation (FR-012)."""
    by_key = {record["match_key"]: record for record in records}
    positions = _pixel_positions(records, center, zoom)
    groups = find_overlap_groups(positions, radius=PIN_RADIUS_PX)
    grouped_keys = {key for group in groups for key in group}

    for key, record in by_key.items():
        if key not in grouped_keys:
            draw_pin(canvas, positions[key], color=role_color(record.get("role")))

    for group in groups:
        group_records = [by_key[key] for key in group]
        draw_merged_pin(
            canvas,
            _group_position(group, positions),
            count=len(group_records),
            color=merged_role_color(group_records),
        )

    return groups, by_key


def _draw_photo_layer(
    data_dir: Path,
    season_label: str,
    canvas,
    records: list[dict],
    center: tuple[float, float],
    zoom: int,
) -> tuple[list[list[str]], dict[str, dict]]:
    """Photo-variant counterpart of `_draw_pin_layer` (FR-011/FR-013,
    research.md §4/§8)."""
    s_dir = season_dir(data_dir, season_label)
    by_key = {record["match_key"]: record for record in records}
    positions = _pixel_positions(records, center, zoom)
    groups = find_overlap_groups(positions, radius=PHOTO_RADIUS_PX)
    grouped_keys = {key for group in groups for key in group}

    for key, record in by_key.items():
        if key not in grouped_keys:
            circular_photo = crop_circular_photo(s_dir / record["photo"])
            draw_photo_circle(canvas, positions[key], circular_photo)

    for group in groups:
        group_records = [by_key[key] for key in group]
        circles = [
            crop_circular_photo(s_dir / record["photo"]) for record in group_records
        ]
        draw_offset_photo_circles(canvas, _group_position(group, positions), circles)

    return groups, by_key


def _generate_detail_maps(
    data_dir: Path,
    season_label: str,
    maps_dir: Path,
    prefix: str,
    variant: str,
    groups: list[list[str]],
    by_key: dict[str, dict],
    min_width_km: float,
    show_scale_bar: bool,
    tile_cache_dir: Path,
) -> None:
    """FR-012: a separate, tighter-zoomed map per overlap group detected on
    the overview -- except the FR-014 same-exact-address pair, which stays
    merged on the overview forever (never gets its own detail map). Re-runs
    the same overlap check at the detail map's own (tighter) scale, so a
    subset still overlapping there falls back to FR-013 on that map too
    instead of recursing into an ever-tighter detail map (research.md §5)."""
    existing_slugs: set[str] = set()
    for group in groups:
        addresses = {key: by_key[key]["address"] for key in group}
        if is_fr014_exception(group, addresses):
            continue

        group_records = [by_key[key] for key in group]
        points = [(record["latitude"], record["longitude"]) for record in group_records]
        center, zoom = zoom_for_bounding_box(
            points,
            padding_km=DETAIL_MAP_PADDING_KM,
            min_width_km=min_width_km,
            canvas_size=CANVAS_SIZE,
        )
        canvas = stitch_basemap(
            center=center, zoom=zoom, canvas_size=CANVAS_SIZE, cache_dir=tile_cache_dir
        )
        if variant == "pins":
            _draw_pin_layer(canvas, group_records, center, zoom)
        else:
            _draw_photo_layer(
                data_dir, season_label, canvas, group_records, center, zoom
            )
        if show_scale_bar:
            draw_scale_bar(canvas, meters_per_pixel=meters_per_pixel(center[0], zoom))
        draw_attribution(canvas)

        slug = detail_map_slug(group_records[0]["address"], existing_slugs)
        existing_slugs.add(slug)
        canvas.save(maps_dir / f"{prefix}_detail_{variant}_{slug}.png")


def _render_overview_pin_map(
    plottable: list[dict],
    center: tuple[float, float],
    zoom: int,
    show_scale_bar: bool,
    tile_cache_dir: Path,
):
    canvas = stitch_basemap(
        center=center, zoom=zoom, canvas_size=CANVAS_SIZE, cache_dir=tile_cache_dir
    )
    groups, by_key = _draw_pin_layer(canvas, plottable, center, zoom)
    if show_scale_bar:
        draw_scale_bar(canvas, meters_per_pixel=meters_per_pixel(center[0], zoom))
    draw_attribution(canvas)
    return canvas, groups, by_key


def _photo_eligible_members(
    data_dir: Path, season_label: str, plottable: list[dict], logger: logging.Logger
) -> list[dict]:
    """US2's eligibility filter: reuses US1's `plottable` list (FR-004) plus
    requiring a photo file on disk; a plottable member with no photo is
    logged and skipped from the photo variant only (FR-006) -- they still
    appear on the pin map."""
    s_dir = season_dir(data_dir, season_label)
    eligible = []
    for record in plottable:
        photo_relative_path = record.get("photo")
        if not photo_relative_path or not (s_dir / photo_relative_path).exists():
            logger.warning(
                "%s skipped from photo map: no photo on file", record["match_key"]
            )
            continue
        eligible.append(record)
    return eligible


def _render_overview_photo_map(
    data_dir: Path,
    season_label: str,
    photo_eligible: list[dict],
    center: tuple[float, float],
    zoom: int,
    show_scale_bar: bool,
    tile_cache_dir: Path,
):
    canvas = stitch_basemap(
        center=center, zoom=zoom, canvas_size=CANVAS_SIZE, cache_dir=tile_cache_dir
    )
    groups, by_key = _draw_photo_layer(
        data_dir, season_label, canvas, photo_eligible, center, zoom
    )
    if show_scale_bar:
        draw_scale_bar(canvas, meters_per_pixel=meters_per_pixel(center[0], zoom))
    draw_attribution(canvas)
    return canvas, groups, by_key


def _process_season(
    data_dir: Path, season_label: str, args: argparse.Namespace, logger: logging.Logger
) -> None:
    plottable = _resolve_plottable_members(data_dir, season_label, logger)
    photo_eligible = _photo_eligible_members(data_dir, season_label, plottable, logger)

    maps_dir = data_dir / "maps"
    prefix = _season_file_prefix(season_label)
    _delete_existing_season_maps(maps_dir, prefix)

    tile_cache_dir = data_dir / ".tile_cache"
    show_scale_bar = not args.no_scale_bar

    pin_center, pin_zoom = _overview_center_and_zoom(plottable, args.min_width_km)
    pin_canvas, pin_groups, pin_by_key = _render_overview_pin_map(
        plottable,
        pin_center,
        pin_zoom,
        show_scale_bar=show_scale_bar,
        tile_cache_dir=tile_cache_dir,
    )
    pin_canvas.save(maps_dir / f"{prefix}_overview_pins.png")
    _generate_detail_maps(
        data_dir,
        season_label,
        maps_dir,
        prefix,
        "pins",
        pin_groups,
        pin_by_key,
        args.min_width_km,
        show_scale_bar,
        tile_cache_dir,
    )

    photo_center, photo_zoom = _overview_center_and_zoom(
        photo_eligible, args.min_width_km
    )
    photo_canvas, photo_groups, photo_by_key = _render_overview_photo_map(
        data_dir,
        season_label,
        photo_eligible,
        photo_center,
        photo_zoom,
        show_scale_bar=show_scale_bar,
        tile_cache_dir=tile_cache_dir,
    )
    photo_canvas.save(maps_dir / f"{prefix}_overview_photos.png")
    _generate_detail_maps(
        data_dir,
        season_label,
        maps_dir,
        prefix,
        "photos",
        photo_groups,
        photo_by_key,
        args.min_width_km,
        show_scale_bar,
        tile_cache_dir,
    )


# --- CLI entrypoint --------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    args = build_arg_parser().parse_args(argv)

    _ensure_output_dirs_and_gitignore(config.data_dir)

    seasons = discover_seasons(config.data_dir)
    last_logger = None
    for season_label in seasons:
        logger, _log_file = setup_run_logger(
            config.data_dir / "seasons" / season_label / "logs",
            logger_name=f"generate_member_maps.{season_label}",
        )
        logger.info(
            "Processing season %s (min_width_km=%s, scale_bar=%s)",
            season_label,
            args.min_width_km,
            not args.no_scale_bar,
        )
        _process_season(config.data_dir, season_label, args, logger)
        last_logger = logger

    # Auto-commit (research.md §12, contracts/cli-and-env.md § Auto-commit
    # behavior): newly-cached lat/lon per season, plus the top-level
    # .gitignore. maps/ and .tile_cache/ are never staged (gitignored).
    commit_logger = (
        last_logger
        or setup_run_logger(
            config.data_dir / "seasons" / ".generate_member_maps_logs",
            logger_name="generate_member_maps.commit",
        )[0]
    )
    commit_paths = [f"seasons/{label}/applicants" for label in seasons] + [".gitignore"]
    auto_commit(
        config.data_dir,
        commit_paths,
        "maps: cache newly-resolved coordinates",
        commit_logger,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
