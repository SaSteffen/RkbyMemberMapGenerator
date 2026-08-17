"""Cross-season eligibility and merge (research.md §4, FR-004/FR-009/FR-010):
one entry per distinct `match_key` with at least one eligible season-record,
positioned/named/photographed from that person's own latest eligible
season-record, but carrying every eligible season-record's own role entry."""

from __future__ import annotations

import logging
from pathlib import Path

from scripts.rkby_maps.geocoding import geocode_record_if_needed
from scripts.rkby_records import (
    _dump_record_yaml,
    applicants_dir,
    load_existing_records,
)


def _resolve_eligible_records(
    data_dir: Path, season_label: str, logger: logging.Logger
) -> list[dict]:
    """Load one season's records, apply the shared eligibility filter
    (FR-004: not excluded/ignored, has an address, successfully geocoded),
    geocode-and-cache each eligible member still missing coordinates
    (fill-empty-only), and log-and-skip (FR-005) anyone left without a
    resolvable address -- identical rule to generate_member_maps.py's
    `_resolve_plottable_members`."""
    records = load_existing_records(data_dir, season_label)
    considered = [
        record
        for record in records.values()
        if not record.get("excluded") and not record.get("ignore")
    ]

    a_dir = applicants_dir(data_dir, season_label)
    eligible = []
    for record in considered:
        if not record.get("address"):
            logger.warning(
                "%s skipped from interactive map: no address on file",
                record["match_key"],
            )
            continue

        if geocode_record_if_needed(record):
            (a_dir / f"{record['match_key']}.yaml").write_text(
                _dump_record_yaml(record)
            )

        if record.get("latitude") is None:
            logger.warning(
                "%s skipped from interactive map: address could not be geocoded: %s",
                record["match_key"],
                record["address"],
            )
            continue

        eligible.append(record)

    return eligible


def merge_seasons(
    data_dir: Path,
    season_labels: list[str],
    loggers: dict[str, logging.Logger],
) -> list[dict]:
    """One merged member per `match_key` eligible in at least one season
    (data-model.md § Merged Member). `first_name`/`last_name`/
    `num_previous_seasons`/`photo_relative_path`/`latitude`/`longitude` come
    from the person's own latest-labeled eligible season-record (season
    labels sort correctly as plain strings); `seasons` carries every eligible
    season-record's own `role`/`additional_roles`, keyed by season label."""
    eligible_by_season: dict[str, list[dict]] = {
        season_label: _resolve_eligible_records(
            data_dir, season_label, loggers[season_label]
        )
        for season_label in season_labels
    }

    records_by_match_key: dict[str, dict[str, dict]] = {}
    for season_label, records in eligible_by_season.items():
        for record in records:
            records_by_match_key.setdefault(record["match_key"], {})[season_label] = (
                record
            )

    merged = []
    for match_key, records_by_season in records_by_match_key.items():
        latest_season_label = max(records_by_season)
        latest_record = records_by_season[latest_season_label]
        merged.append(
            {
                "match_key": match_key,
                "first_name": latest_record["first_name"],
                "last_name": latest_record["last_name"],
                "num_previous_seasons": latest_record.get("num_previous_seasons"),
                "photo_relative_path": latest_record.get("photo"),
                # Which season's own folder photo_relative_path is relative
                # to -- not part of the Bundled Map Data payload itself
                # (data-model.md), only used by bundle.py to locate the
                # source photo file on disk.
                "photo_season_label": latest_season_label,
                "latitude": latest_record["latitude"],
                "longitude": latest_record["longitude"],
                "seasons": {
                    season_label: {
                        "role": record.get("role"),
                        "additional_roles": record.get("additional_roles") or [],
                    }
                    for season_label, record in records_by_season.items()
                },
            }
        )

    return merged
