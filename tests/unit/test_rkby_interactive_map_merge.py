"""Unit tests for `scripts/rkby_interactive_map/merge.py`: per-season-record
eligibility (FR-004/FR-005), cross-season merge by `match_key` with a
latest-eligible-record tie-break (FR-010), every eligible season-record's own
role retained (FR-009/FR-015), and full opt-out across every season
(SC-010)."""

import logging
from pathlib import Path

import responses
import yaml

from scripts.rkby_interactive_map.merge import merge_seasons

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

_BASE_RECORD = {
    "first_name": "First",
    "last_name": "Last",
    "phone": None,
    "role": None,
    "additional_roles": None,
    "birthday": None,
    "num_previous_seasons": None,
    "status": "yes",
    "excluded": False,
    "excluded_observed_at": None,
    "ignore": False,
    "photo": None,
    "address": None,
    "latitude": None,
    "longitude": None,
}


def _write_record(
    data_dir: Path, season_label: str, match_key: str, **overrides
) -> None:
    a_dir = data_dir / "seasons" / season_label / "applicants"
    a_dir.mkdir(parents=True, exist_ok=True)
    record = {**_BASE_RECORD, "match_key": match_key}
    record.update(overrides)
    (a_dir / f"{match_key}.yaml").write_text(yaml.safe_dump(record))


def _loggers_for(data_dir: Path, season_labels: list[str]) -> dict[str, logging.Logger]:
    loggers = {}
    for label in season_labels:
        logger = logging.getLogger(f"test.{label}")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())
        loggers[label] = logger
    return loggers


def _register_nominatim_match() -> None:
    responses.add(
        responses.GET,
        NOMINATIM_URL,
        body=(FIXTURES_DIR / "nominatim_response_match.json").read_text(),
        status=200,
        content_type="application/json",
    )


def _register_nominatim_no_match() -> None:
    responses.add(
        responses.GET,
        NOMINATIM_URL,
        body=(FIXTURES_DIR / "nominatim_response_no_match.json").read_text(),
        status=200,
        content_type="application/json",
    )


# --- Eligibility (FR-004/FR-005) -------------------------------------------------


def test_excluded_record_is_dropped(tmp_path):
    _write_record(
        tmp_path,
        "2025-26",
        "excluded-member",
        address="Somewhere 1",
        latitude=53.5,
        longitude=10.0,
        excluded=True,
        excluded_observed_at="2026-01-01T00:00:00+00:00",
    )
    loggers = _loggers_for(tmp_path, ["2025-26"])

    merged = merge_seasons(tmp_path, ["2025-26"], loggers)

    assert merged == []


def test_ignored_record_is_dropped(tmp_path):
    _write_record(
        tmp_path,
        "2025-26",
        "ignored-member",
        address="Somewhere 1",
        latitude=53.5,
        longitude=10.0,
        ignore=True,
    )
    loggers = _loggers_for(tmp_path, ["2025-26"])

    merged = merge_seasons(tmp_path, ["2025-26"], loggers)

    assert merged == []


def test_no_address_record_is_dropped_and_logged(tmp_path, caplog):
    _write_record(tmp_path, "2025-26", "no-address-member")
    loggers = _loggers_for(tmp_path, ["2025-26"])

    with caplog.at_level(logging.WARNING, logger="test.2025-26"):
        merged = merge_seasons(tmp_path, ["2025-26"], loggers)

    assert merged == []
    assert "no-address-member" in caplog.text


@responses.activate
def test_ungeocodable_address_record_is_dropped_and_logged(tmp_path, caplog):
    _write_record(tmp_path, "2025-26", "bad-address-member", address="Nowhere at all")
    _register_nominatim_no_match()
    loggers = _loggers_for(tmp_path, ["2025-26"])

    with caplog.at_level(logging.WARNING, logger="test.2025-26"):
        merged = merge_seasons(tmp_path, ["2025-26"], loggers)

    assert merged == []
    assert "bad-address-member" in caplog.text


@responses.activate
def test_eligible_record_is_geocoded_and_cached_back_to_yaml(tmp_path):
    _write_record(tmp_path, "2025-26", "jane-doe", address="Musterstr. 1, Hamburg")
    _register_nominatim_match()
    loggers = _loggers_for(tmp_path, ["2025-26"])

    merged = merge_seasons(tmp_path, ["2025-26"], loggers)

    assert len(merged) == 1
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    saved = yaml.safe_load((a_dir / "jane-doe.yaml").read_text())
    assert saved["latitude"] is not None
    assert saved["longitude"] is not None


# --- Cross-season merge (FR-009/FR-010/FR-015) -----------------------------------


def test_latest_eligible_record_wins_by_season_label_sort_order(tmp_path):
    _write_record(
        tmp_path,
        "2024-25",
        "jane-doe",
        first_name="Old",
        last_name="Name",
        address="Old address",
        latitude=53.0,
        longitude=9.0,
        role="Rider",
        photo="photos/old.jpg",
    )
    _write_record(
        tmp_path,
        "2025-26",
        "jane-doe",
        first_name="New",
        last_name="Name",
        address="New address",
        latitude=53.5,
        longitude=10.0,
        role="Service Crew",
        photo="photos/new.jpg",
    )
    loggers = _loggers_for(tmp_path, ["2024-25", "2025-26"])

    merged = merge_seasons(tmp_path, ["2024-25", "2025-26"], loggers)

    assert len(merged) == 1
    member = merged[0]
    assert member["match_key"] == "jane-doe"
    assert member["first_name"] == "New"
    assert member["latitude"] == 53.5
    assert member["longitude"] == 10.0
    assert member["photo_relative_path"] == "photos/new.jpg"


def test_every_eligible_season_record_contributes_its_own_role(tmp_path):
    _write_record(
        tmp_path,
        "2024-25",
        "jane-doe",
        address="Old address",
        latitude=53.0,
        longitude=9.0,
        role="Rider",
        additional_roles=["Steering Committee"],
    )
    _write_record(
        tmp_path,
        "2025-26",
        "jane-doe",
        address="New address",
        latitude=53.5,
        longitude=10.0,
        role="Service Crew",
        additional_roles=None,
    )
    loggers = _loggers_for(tmp_path, ["2024-25", "2025-26"])

    merged = merge_seasons(tmp_path, ["2024-25", "2025-26"], loggers)

    assert len(merged) == 1
    seasons = merged[0]["seasons"]
    assert seasons == {
        "2024-25": {"role": "Rider", "additional_roles": ["Steering Committee"]},
        "2025-26": {"role": "Service Crew", "additional_roles": []},
    }


def test_ineligible_season_record_never_contributes_position_or_role(tmp_path):
    _write_record(
        tmp_path,
        "2024-25",
        "jane-doe",
        address="Old address",
        latitude=53.0,
        longitude=9.0,
        role="Rider",
    )
    # 2025-26's own record for the same person is ineligible (excluded) --
    # the merge must skip it entirely, including from the per-season role map.
    _write_record(
        tmp_path,
        "2025-26",
        "jane-doe",
        address="New address",
        latitude=53.5,
        longitude=10.0,
        role="Service Crew",
        excluded=True,
        excluded_observed_at="2026-01-01T00:00:00+00:00",
    )
    loggers = _loggers_for(tmp_path, ["2024-25", "2025-26"])

    merged = merge_seasons(tmp_path, ["2024-25", "2025-26"], loggers)

    assert len(merged) == 1
    member = merged[0]
    assert member["latitude"] == 53.0
    assert set(member["seasons"]) == {"2024-25"}


def test_person_excluded_in_every_season_never_appears(tmp_path):
    _write_record(
        tmp_path,
        "2024-25",
        "jane-doe",
        address="Old address",
        latitude=53.0,
        longitude=9.0,
        excluded=True,
        excluded_observed_at="2026-01-01T00:00:00+00:00",
    )
    _write_record(
        tmp_path,
        "2025-26",
        "jane-doe",
        address="New address",
        latitude=53.5,
        longitude=10.0,
        ignore=True,
    )
    loggers = _loggers_for(tmp_path, ["2024-25", "2025-26"])

    merged = merge_seasons(tmp_path, ["2024-25", "2025-26"], loggers)

    assert merged == []
