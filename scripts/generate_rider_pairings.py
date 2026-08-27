"""Generate ranked mentor-candidate suggestions for every new rider, plus
training clusters of nearby current-season riders, from a local,
human-editable, git-backed data store already populated by
`scrape_applicants.py` (001) and geocoded by `generate_member_maps.py` (002).

See specs/006-rider-pairing-suggester/ (spec.md, plan.md, research.md,
data-model.md, contracts/) for the full design. Configuration is env-var
only:

    RKBY_DATA_DIR  absolute path to the local, git-backed data repository
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.rkby_pairing.clusters import (
    DEFAULT_CLUSTER_RADIUS_KM,
    find_training_clusters,
)
from scripts.rkby_pairing.eligibility import find_mentor_candidates, find_new_riders
from scripts.rkby_pairing.pdf import render_pdf
from scripts.rkby_pairing.ranking import rank_mentor_candidates
from scripts.rkby_pairing.report import render_report
from scripts.rkby_records import (
    auto_commit,
    discover_seasons,
    load_existing_records,
    setup_run_logger,
)
from scripts.rkby_report.frame import ensure_reports_dir_and_gitignore

DEFAULT_MAX_SUGGESTIONS = 3


class ConfigError(Exception):
    """A required environment variable is missing or invalid."""


@dataclass(frozen=True)
class Config:
    data_dir: Path


def load_config() -> Config:
    """Validate all required env vars are present and usable before any file
    write (mirrors generate_member_maps.load_config)."""
    raw_data_dir = os.environ.get("RKBY_DATA_DIR")
    if not raw_data_dir:
        raise ConfigError("Missing required environment variable: RKBY_DATA_DIR")

    data_dir = Path(raw_data_dir)
    if not data_dir.is_dir():
        raise ConfigError(
            f"RKBY_DATA_DIR does not exist or is not a directory: {data_dir}"
        )

    return Config(data_dir=data_dir)


# --- CLI arg parsing (contracts/cli-and-env.md) ---------------------------------


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer: {value!r}")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive number: {value!r}")
    return parsed


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate ranked mentor-candidate suggestions and training "
            "clusters for the latest season in RKBY_DATA_DIR."
        )
    )
    parser.add_argument(
        "--max-suggestions",
        type=_positive_int,
        default=DEFAULT_MAX_SUGGESTIONS,
        help=(
            "Upper bound on how many Suggested Pairings each New Rider gets "
            f"(default: {DEFAULT_MAX_SUGGESTIONS})."
        ),
    )
    parser.add_argument(
        "--cluster-radius-km",
        type=_positive_float,
        default=DEFAULT_CLUSTER_RADIUS_KM,
        help=(
            "Two current-season Riders are linked into the same Training "
            "Cluster when their home locations are within this many "
            f"kilometers (default: {DEFAULT_CLUSTER_RADIUS_KM})."
        ),
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Also render reports/rider_pairings.pdf from the freshly-written report.",
    )
    parser.add_argument(
        "--pdf-only",
        action="store_true",
        help=(
            "Skip the pairing computation entirely and render the report's "
            "current on-disk Markdown content to reports/rider_pairings.pdf."
        ),
    )
    return parser


# --- Skipped-member logging (contracts/report-output.md § Skipped members) -----


def _log_skipped_members(records: dict[str, dict], logger: logging.Logger) -> None:
    for record in records.values():
        if record.get("excluded"):
            reason = "excluded"
        elif record.get("ignore"):
            reason = "ignored"
        elif record.get("latitude") is None or record.get("longitude") is None:
            reason = "not geocoded"
        else:
            continue
        logger.warning(
            "%s skipped from rider pairing report: %s", record["match_key"], reason
        )


# --- CLI entrypoint --------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    args = build_arg_parser().parse_args(argv)

    reports_dir = config.data_dir / "reports"
    md_path = reports_dir / "rider_pairings.md"
    pdf_path = reports_dir / "rider_pairings.pdf"

    if args.pdf_only:
        if not md_path.exists():
            print(
                f"Cannot render PDF: {md_path} does not exist yet. Run without "
                "--pdf-only first.",
                file=sys.stderr,
            )
            return 1
        render_pdf(md_path, pdf_path)
        return 0

    seasons = discover_seasons(config.data_dir)
    if not seasons:
        logger, _log_file = setup_run_logger(
            config.data_dir / "seasons" / ".generate_rider_pairings_logs",
            logger_name="generate_rider_pairings",
        )
        logger.info("No seasons found under RKBY_DATA_DIR -- nothing to report.")
        return 0

    latest = seasons[-1]
    logger, _log_file = setup_run_logger(
        config.data_dir / "seasons" / latest / "logs",
        logger_name=f"generate_rider_pairings.{latest}",
    )
    logger.info(
        "Processing season %s (max_suggestions=%s, cluster_radius_km=%s)",
        latest,
        args.max_suggestions,
        args.cluster_radius_km,
    )

    ensure_reports_dir_and_gitignore(config.data_dir)

    by_season = {
        season_label: load_existing_records(config.data_dir, season_label)
        for season_label in seasons
    }
    latest_records = by_season[latest]
    _log_skipped_members(latest_records, logger)

    new_riders = find_new_riders(by_season, latest)
    mentor_candidates = find_mentor_candidates(by_season, latest)

    suggestions_by_new_rider = {
        new_rider["match_key"]: rank_mentor_candidates(
            new_rider, mentor_candidates, args.max_suggestions
        )
        for new_rider in new_riders
    }

    clusters = find_training_clusters(latest_records, args.cluster_radius_km)

    text = render_report(
        latest,
        datetime.datetime.now().astimezone().date().isoformat(),
        new_riders,
        suggestions_by_new_rider,
        latest_records,
        clusters,
    )
    md_path.write_text(text)

    auto_commit(
        config.data_dir,
        ["reports/rider_pairings.md"],
        "reports: regenerate rider pairing suggestions",
        logger,
        force=True,
    )

    if args.pdf:
        render_pdf(md_path, pdf_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
