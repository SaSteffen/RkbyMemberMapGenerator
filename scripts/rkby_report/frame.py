"""Build the one member-season DataFrame every other `rkby_report` function
consumes (contracts/member-season-frame.md). Read-only: never geocodes
(FR-007) and never writes to any `.yaml` record -- it only reads
`latitude`/`longitude` already cached by a prior `generate_member_maps.py`
run."""

from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd

from scripts.rkby_records import (
    canonical_match_keys,
    discover_seasons,
    load_existing_records,
)

_GITIGNORE_ENTRIES = ("reports/",)
from scripts.rkby_report.buckets import age_bucket, distance_bucket
from scripts.rkby_report.geo import HAMBURG_CENTER, haversine_km


def _is_eligible(record: dict) -> bool:
    """Narrower than the interactive map's filter (research.md §8): only
    `excluded`/`ignore` remove a member, never a missing address/geocode."""
    return not record.get("excluded") and not record.get("ignore")


def _season_reference_date(season_label: str) -> datetime.date:
    """For a season labeled `YYYY-YY`, age is computed as of July 1 of the
    second year (`20YY`) -- the month the ride actually happens
    (research.md §6)."""
    start_year_text, end_suffix_text = season_label.split("-")
    second_year = int(start_year_text[:2] + end_suffix_text)
    return datetime.date(second_year, 7, 1)


def _age_at(birthday: str | None, reference_date: datetime.date) -> int | None:
    if birthday is None:
        return None
    born = datetime.date.fromisoformat(birthday)
    age = reference_date.year - born.year
    if (reference_date.month, reference_date.day) < (born.month, born.day):
        age -= 1
    return age


def build_member_season_frame(data_dir: Path) -> pd.DataFrame:
    season_labels = discover_seasons(data_dir)

    eligible_by_season: dict[str, list[dict]] = {}
    for season_label in season_labels:
        records = load_existing_records(data_dir, season_label)
        eligible_by_season[season_label] = [
            record for record in records.values() if _is_eligible(record)
        ]

    canonical = canonical_match_keys(eligible_by_season)

    # match_key -> set of season labels the canonical identity has a row in,
    # needed to compute retained_next_season without a second full pass.
    seasons_by_canonical_key: dict[str, set[str]] = {}
    for season_label, records in eligible_by_season.items():
        for record in records:
            key = canonical.get(record["match_key"], record["match_key"])
            seasons_by_canonical_key.setdefault(key, set()).add(season_label)

    last_season_label = season_labels[-1] if season_labels else None
    next_season_by_label = {
        season_labels[i]: season_labels[i + 1] for i in range(len(season_labels) - 1)
    }

    rows = []
    for season_label, records in eligible_by_season.items():
        reference_date = _season_reference_date(season_label)
        next_season_label = next_season_by_label.get(season_label)

        for record in records:
            match_key = canonical.get(record["match_key"], record["match_key"])

            age_at_season = _age_at(record.get("birthday"), reference_date)

            latitude = record.get("latitude")
            longitude = record.get("longitude")
            distance_km = (
                haversine_km(HAMBURG_CENTER, (latitude, longitude))
                if latitude is not None and longitude is not None
                else None
            )

            if season_label == last_season_label:
                retained_next_season = None
            else:
                retained_next_season = (
                    next_season_label in seasons_by_canonical_key.get(match_key, set())
                )

            rows.append(
                {
                    "match_key": match_key,
                    "season_label": season_label,
                    "role": record.get("role") or "unknown",
                    "sex": record.get("sex") or "unknown",
                    "age_at_season": age_at_season,
                    "age_bucket": age_bucket(age_at_season),
                    "distance_km": distance_km,
                    "distance_bucket": distance_bucket(distance_km),
                    "retained_next_season": retained_next_season,
                }
            )

    columns = [
        "match_key",
        "season_label",
        "role",
        "sex",
        "age_at_season",
        "age_bucket",
        "distance_km",
        "distance_bucket",
        "retained_next_season",
    ]
    df = pd.DataFrame(rows, columns=columns)
    if not df.empty:
        df = df.sort_values(["season_label", "match_key"]).reset_index(drop=True)
        df["retained_next_season"] = df["retained_next_season"].astype("object")
    return df


def ensure_reports_dir_and_gitignore(data_dir: Path) -> None:
    """Create `reports/` under `data_dir` if absent, and create/update the
    data-dir `.gitignore` so it's ignored -- the same pattern
    `generate_member_maps.py` already established for `maps/`/`.tile_cache/`
    (research.md §4, §10)."""
    (data_dir / "reports").mkdir(exist_ok=True)

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
