"""Unit tests for per-applicant birthday-fetch failure isolation, mirroring
test_photo_fetch.py: other data is still persisted, a failure is logged as a
warning, and birthday is left `null` for retry on a later run (FR-005,
research.md §15 revision: birthday lives in the per-applicant detail popup,
not the applicant list view)."""

import logging
from pathlib import Path

import yaml

from scripts.scrape_applicants import fetch_birthday, persist_records, setup_run_logger

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


class _StubClient:
    def __init__(self, detail_html_by_id=None, raise_for_ids=()):
        self._detail_html_by_id = detail_html_by_id or {}
        self._raise_for_ids = set(raise_for_ids)

    def fetch_participant_detail(self, season_id: int, applicant_id: int) -> str:
        if applicant_id in self._raise_for_ids:
            raise ConnectionError("simulated network failure")
        return self._detail_html_by_id[applicant_id]


def test_fetch_birthday_returns_none_and_logs_warning_on_failure(caplog):
    client = _StubClient(raise_for_ids={1001})
    logger = logging.getLogger("test_fetch_birthday")
    logger.setLevel(logging.WARNING)

    with caplog.at_level(logging.WARNING, logger="test_fetch_birthday"):
        result = fetch_birthday(client, 1181, 1001, logger, "jane-doe")

    assert result is None
    assert any("jane-doe" in record.message for record in caplog.records)


def test_fetch_birthday_returns_iso_date_on_success():
    client = _StubClient(detail_html_by_id={1001: _load("applicant_detail_popup.html")})
    logger = logging.getLogger("test_fetch_birthday_success")

    result = fetch_birthday(client, 1181, 1001, logger, "jane-doe")

    assert result == "1990-03-15"


def test_fetch_birthday_returns_none_when_no_applicant_id():
    client = _StubClient()
    logger = logging.getLogger("test_fetch_birthday_none")

    assert fetch_birthday(client, 1181, None, logger, "jane-doe") is None


def test_fetch_birthday_returns_none_when_popup_has_no_birthday():
    client = _StubClient(
        detail_html_by_id={1001: _load("applicant_detail_popup_no_birthday.html")}
    )
    logger = logging.getLogger("test_fetch_birthday_missing")

    assert fetch_birthday(client, 1181, 1001, logger, "jane-doe") is None


def test_persist_records_isolates_a_single_birthday_failure(tmp_path):
    logger, _ = setup_run_logger(tmp_path / "logs")
    client = _StubClient(
        detail_html_by_id={1001: _load("applicant_detail_popup.html")},
        raise_for_ids={1002},
    )
    rows = [
        {
            "first_name": "Lucky",
            "last_name": "Person",
            "phone": None,
            "address": None,
            "status": "yes",
            "photo_thumbnail_url": None,
            "applicant_id": 1001,
        },
        {
            "first_name": "Unlucky",
            "last_name": "Person",
            "phone": None,
            "address": None,
            "status": "yes",
            "photo_thumbnail_url": None,
            "applicant_id": 1002,
        },
    ]

    summary = persist_records(tmp_path, "2025-26", 1181, rows, client, logger)

    assert summary["created"] == 2
    assert summary["birthdays_fetched"] == 1

    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    lucky_record = yaml.safe_load((a_dir / "lucky-person.yaml").read_text())
    assert lucky_record["birthday"] == "1990-03-15"

    unlucky_record = yaml.safe_load((a_dir / "unlucky-person.yaml").read_text())
    assert unlucky_record["birthday"] is None


# --- An existing birthday is never re-fetched or overwritten ---------------


def test_persist_records_does_not_refetch_an_existing_birthday(tmp_path):
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    a_dir.mkdir(parents=True)
    (a_dir / "jane-doe.yaml").write_text(
        yaml.safe_dump(
            {
                "match_key": "jane-doe",
                "first_name": "Jane",
                "last_name": "Doe",
                "address": None,
                "phone": None,
                "birthday": "1975-12-24",
                "status": "yes",
                "excluded": False,
                "excluded_observed_at": None,
                "ignore": False,
                "photo": None,
            }
        )
    )

    logger, _ = setup_run_logger(tmp_path / "logs")

    class _FailIfCalledClient:
        def fetch_participant_detail(self, season_id: int, applicant_id: int) -> str:
            raise AssertionError("must not fetch a birthday that is already on file")

    rows = [
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "phone": None,
            "address": None,
            "status": "yes",
            "photo_thumbnail_url": None,
            "applicant_id": 9001,
        }
    ]

    summary = persist_records(
        tmp_path, "2025-26", 1181, rows, _FailIfCalledClient(), logger
    )

    assert summary["birthdays_fetched"] == 0
    record = yaml.safe_load((a_dir / "jane-doe.yaml").read_text())
    assert record["birthday"] == "1975-12-24"
