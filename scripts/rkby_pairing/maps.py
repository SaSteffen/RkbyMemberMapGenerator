"""Map rendering/orchestration for the pairing report (FR-003/004/005/006/
007/010, data-model.md § Eligible Member Pool / Cluster Map / Overview Map,
research.md Decisions 2/3/5): the Team Overview map and one map per Training
Cluster, drawn with member photos (faces) via `scripts.rkby_maps.photo_map`
-- the framing/frame-selection math still comes from `scripts.rkby_maps.
pin_map` -- so they look identical to `generate_member_maps.py`'s own photo
maps."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from scripts.rkby_maps import pin_map
from scripts.rkby_maps.basemap import (
    meters_per_pixel,
    stitch_basemap,
    zoom_for_bounding_box,
)
from scripts.rkby_maps.photo_map import render_photo_layer
from scripts.rkby_maps.rendering import draw_attribution, draw_scale_bar
from scripts.rkby_pairing.clusters import TrainingCluster
from scripts.rkby_pairing.eligibility import is_eligible_base
from scripts.rkby_records import season_dir


def eligible_member_pool(latest_records: dict[str, dict]) -> list[dict]:
    """Every latest-season record for which `is_eligible_base` is `True`,
    with no role filter (data-model.md § Eligible Member Pool, FR-007) --
    reused unchanged both as the overview map's full membership and as the
    "other current-season members of any role" a cluster map draws for
    context (research.md Decision 3)."""
    return [record for record in latest_records.values() if is_eligible_base(record)]


def _finish_map(canvas: Image.Image, center: tuple[float, float], zoom: int) -> None:
    draw_scale_bar(canvas, meters_per_pixel=meters_per_pixel(center[0], zoom))
    draw_attribution(canvas)


def render_cluster_map(
    cluster: TrainingCluster,
    eligible_pool: list[dict],
    tile_cache_dir: Path,
    s_dir: Path,
) -> Image.Image:
    """One map per Training Cluster (data-model.md § Cluster Map): framed
    around the cluster's own bounding box (its members are always drawn,
    since they define the frame), plus any other eligible member of any
    role whose position lands inside that frame, for context (FR-005).
    Drawn with member photos (or the mascot placeholder), not role-colored
    pins."""
    by_key = {record["match_key"]: record for record in eligible_pool}
    cluster_records = [by_key[key] for key in cluster.member_match_keys]
    points = [(record["latitude"], record["longitude"]) for record in cluster_records]
    center, zoom = zoom_for_bounding_box(
        points,
        padding_px=pin_map.FRAME_PADDING_PX,
        min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM,
        canvas_size=pin_map.CANVAS_SIZE,
    )
    frame_records = pin_map.records_within_frame(
        eligible_pool,
        always_include=set(cluster.member_match_keys),
        center=center,
        zoom=zoom,
        canvas_size=pin_map.CANVAS_SIZE,
    )

    canvas = stitch_basemap(
        center=center,
        zoom=zoom,
        canvas_size=pin_map.CANVAS_SIZE,
        cache_dir=tile_cache_dir,
    )
    render_photo_layer(s_dir, canvas, frame_records, center, zoom)
    _finish_map(canvas, center, zoom)
    return canvas


def render_overview_map(
    eligible_pool: list[dict], tile_cache_dir: Path, s_dir: Path
) -> Image.Image:
    """The Team Overview map (data-model.md § Overview Map, FR-006/007):
    every eligible current-season member of any role, independent of
    Training Clusters -- an empty pool still renders a valid map, centered
    on `pin_map.DEFAULT_CENTER` at the `min_width_km` floor's zoom
    (Acceptance Scenario 3.3). Drawn with member photos (or the mascot
    placeholder), not role-colored pins."""
    center, zoom = pin_map.overview_center_and_zoom(
        eligible_pool, min_width_km=pin_map.DEFAULT_MIN_WIDTH_KM
    )
    canvas = stitch_basemap(
        center=center,
        zoom=zoom,
        canvas_size=pin_map.CANVAS_SIZE,
        cache_dir=tile_cache_dir,
    )
    render_photo_layer(s_dir, canvas, eligible_pool, center, zoom)
    _finish_map(canvas, center, zoom)
    return canvas


def write_report_maps(
    data_dir: Path,
    season_label: str,
    latest_records: dict[str, dict],
    clusters: list[TrainingCluster],
    tile_cache_dir: Path,
) -> None:
    """`reports/maps/` (FR-010/FR-011, research.md Decision 5): clear the
    directory's entire contents, then write a fresh `overview.png` plus one
    `cluster_<n>.png` per Training Cluster, `<n>` 1-based matching
    `render_report`'s own `enumerate(clusters, start=1)` numbering -- a full
    clear (not a prefix-glob one), since the cluster count/numbering can
    both shift between runs."""
    maps_dir = data_dir / "reports" / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    for existing_file in maps_dir.iterdir():
        existing_file.unlink()

    s_dir = season_dir(data_dir, season_label)
    pool = eligible_member_pool(latest_records)

    overview_image = render_overview_map(pool, tile_cache_dir, s_dir)
    overview_image.save(maps_dir / "overview.png")

    for index, cluster in enumerate(clusters, start=1):
        image = render_cluster_map(cluster, pool, tile_cache_dir, s_dir)
        image.save(maps_dir / f"cluster_{index}.png")
