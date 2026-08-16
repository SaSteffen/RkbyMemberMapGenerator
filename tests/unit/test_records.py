"""Unit tests for normalize_name()/match_key() normalization (FR-013), and for
within-scrape / against-persisted-record deduplication and conflict handling
(FR-013, FR-014, FR-020, Story 5)."""

import logging

import pytest
import yaml

from scripts.scrape_applicants import (
    deduplicate_scraped_rows,
    match_key,
    normalize_name,
    persist_records,
    setup_run_logger,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Jane", "jane"),
        ("  Jane  ", "jane"),
        ("Jan-Åke", "jan-ake"),
        ("Müller", "muller"),
        ("O'Brien", "obrien"),
        ("Anne Marie", "anne-marie"),
    ],
)
def test_normalize_name_strips_diacritics_case_and_whitespace(raw, expected):
    assert normalize_name(raw) == expected


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [
        ("Jane", "Doe", "jane-doe"),
        ("jane", "doe", "jane-doe"),
        ("  Jane ", " Doe  ", "jane-doe"),
        ("Jan-Åke", "Müller", "jan-ake-muller"),
    ],
)
def test_match_key_joins_normalized_first_and_last_name(first, last, expected):
    assert match_key(first, last) == expected


def test_match_key_is_case_and_whitespace_insensitive():
    assert match_key("JANE", "DOE") == match_key("  jane  ", "  doe  ")


def test_match_key_drops_the_separator_when_last_name_is_empty():
    # A Name cell with no last name on file at all (no separator to split
    # on) must not produce a trailing hyphen -- the schema's match_key
    # pattern forbids one.
    assert match_key("Jane", "") == "jane"


# --- Story 5: within-scrape deduplication (AC1/AC2, FR-013) -----------------


class _NoPhotoClient:
    def fetch_photo_bytes(self, thumbnail_url: str) -> bytes:
        raise AssertionError("photo fetch not needed for these tests")


def _row(**overrides) -> dict:
    row = {
        "first_name": "Jane",
        "last_name": "Doe",
        "phone": None,
        "address": None,
        "status": "yes",
        "photo_thumbnail_url": None,
    }
    row.update(overrides)
    return row


def test_consistent_within_scrape_duplicates_merge_to_one_record(caplog):
    logger = logging.getLogger("test_dedup_consistent")
    rows = [
        _row(address="Musterstr. 1"),
        _row(phone="01701234567"),  # same person, complementary field
    ]

    with caplog.at_level(logging.WARNING, logger=logger.name):
        result = deduplicate_scraped_rows(rows, logger)

    assert len(result) == 1
    assert result[0]["address"] == "Musterstr. 1"
    assert result[0]["phone"] == "01701234567"
    assert caplog.records == []


def test_conflicting_within_scrape_duplicates_are_flagged_and_dropped(caplog):
    logger = logging.getLogger("test_dedup_conflict")
    rows = [
        _row(address="Musterstr. 1"),
        _row(address="A Totally Different Street 9"),  # meaningful conflict
    ]

    with caplog.at_level(logging.WARNING, logger=logger.name):
        result = deduplicate_scraped_rows(rows, logger)

    assert result == []  # neither persisted this run
    assert any("jane-doe" in record.message for record in caplog.records)


def test_deduplication_leaves_unrelated_applicants_untouched(caplog):
    logger = logging.getLogger("test_dedup_passthrough")
    rows = [_row(), _row(first_name="John", last_name="Smith")]

    result = deduplicate_scraped_rows(rows, logger)

    assert len(result) == 2


# --- Story 5 / FR-014: conflict against an already-persisted record ---------


def test_scraped_row_conflicting_with_persisted_record_is_flagged_and_existing_kept(
    tmp_path,
):
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    a_dir.mkdir(parents=True)
    (a_dir / "jane-doe.yaml").write_text(
        yaml.safe_dump(
            {
                "match_key": "jane-doe",
                "first_name": "Jane",
                "last_name": "Doe",
                "address": "Original Street 1",
                "phone": None,
                "birthday": None,
                "status": "yes",
                "excluded": False,
                "excluded_observed_at": None,
                "ignore": False,
                "photo": None,
            }
        )
    )

    logger, log_file = setup_run_logger(tmp_path / "logs")
    rows = [_row(address="A Conflicting Street 2")]

    persist_records(tmp_path, "2025-26", 1181, rows, _NoPhotoClient(), logger)
    for handler in logger.handlers:
        handler.flush()

    existing_after = yaml.safe_load((a_dir / "jane-doe.yaml").read_text())
    assert existing_after["address"] == "Original Street 1"  # untouched
    log_content = log_file.read_text()
    assert "jane-doe" in log_content
    assert "A Conflicting Street 2" in log_content  # full new snapshot logged


# --- Regression: a Name cell with no last name on file must still persist ---


def test_a_single_token_name_with_no_last_name_is_persisted_not_skipped(tmp_path):
    """Previously: last_name="" failed the schema's minLength, and the
    resulting match_key ("robin-", trailing hyphen) failed the pattern too
    -- the applicant was silently skipped every run, logged only as a
    validation error. Both are now valid."""
    logger, _log_file = setup_run_logger(tmp_path / "logs")
    rows = [_row(first_name="Robin", last_name="")]

    summary = persist_records(tmp_path, "2025-26", 1181, rows, _NoPhotoClient(), logger)

    assert summary["validation_errors"] == 0
    assert summary["created"] == 1
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    assert [p.stem for p in a_dir.glob("*.yaml")] == ["robin"]


# --- FR-020: matching never crosses season boundaries ------------------------


def test_matching_never_crosses_season_boundaries(tmp_path):
    season_a_dir = tmp_path / "seasons" / "2024-25" / "applicants"
    season_a_dir.mkdir(parents=True)
    (season_a_dir / "jane-doe.yaml").write_text(
        yaml.safe_dump(
            {
                "match_key": "jane-doe",
                "first_name": "Jane",
                "last_name": "Doe",
                "address": "Season A Street 1",
                "phone": None,
                "birthday": None,
                "status": "yes",
                "excluded": False,
                "excluded_observed_at": None,
                "ignore": False,
                "photo": None,
            }
        )
    )
    season_a_snapshot = (season_a_dir / "jane-doe.yaml").read_text()

    logger, _ = setup_run_logger(tmp_path / "logs-b")
    rows = [_row(address="Season B Street 9")]

    summary = persist_records(tmp_path, "2025-26", 1181, rows, _NoPhotoClient(), logger)

    # Season A's record is untouched -- no cross-season match/conflict.
    assert (season_a_dir / "jane-doe.yaml").read_text() == season_a_snapshot
    # Season B gets its own independent new record.
    assert summary["created"] == 1
    season_b_record = yaml.safe_load(
        (tmp_path / "seasons" / "2025-26" / "applicants" / "jane-doe.yaml").read_text()
    )
    assert season_b_record["address"] == "Season B Street 9"
