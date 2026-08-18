"""Unit tests for per-applicant detail-popup fetch failure isolation, mirroring
test_photo_fetch.py: other data is still persisted, a failure is logged as a
warning, and any field the popup didn't yield is left `null`/unset for retry on
a later run (FR-005, research.md §15 revision: birthday, sex, and
num_previous_seasons all live in the per-applicant detail popup, not the
applicant list view). All three fields are parsed from a single popup fetch
rather than one fetch per field."""

import logging
from pathlib import Path

import yaml

from scripts.scrape_applicants import (
    _parse_birthday,
    fetch_participant_details,
    persist_records,
    setup_run_logger,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


def _birthday_html(raw: str) -> str:
    return f'<p class="profile_birthday"><span>Birthday: </span>{raw}</p>'


# --- Birthday separator variance (live site renders this field
# inconsistently per-applicant, not just as dd-mm-yyyy) -----------------


def test_parse_birthday_accepts_dash_separator():
    assert _parse_birthday(_birthday_html("15-03-1990")) == "1990-03-15"


def test_parse_birthday_accepts_dot_separator():
    assert _parse_birthday(_birthday_html("15.03.1990")) == "1990-03-15"


def test_parse_birthday_accepts_no_separator():
    assert _parse_birthday(_birthday_html("15031990")) == "1990-03-15"


def test_parse_birthday_returns_none_for_site_garbage_value():
    # A handful of live records render the literal text "NaN-NaN-NaN" -- a
    # bug on the site's own side, not something the scraper can recover.
    assert _parse_birthday(_birthday_html("NaN-NaN-NaN")) is None


class _StubClient:
    def __init__(self, detail_html_by_id=None, raise_for_ids=()):
        self._detail_html_by_id = detail_html_by_id or {}
        self._raise_for_ids = set(raise_for_ids)

    def fetch_participant_detail(self, season_id: int, applicant_id: int) -> str:
        if applicant_id in self._raise_for_ids:
            raise ConnectionError("simulated network failure")
        return self._detail_html_by_id[applicant_id]


def test_fetch_participant_details_returns_none_and_logs_warning_on_failure(caplog):
    client = _StubClient(raise_for_ids={1001})
    logger = logging.getLogger("test_fetch_participant_details")
    logger.setLevel(logging.WARNING)

    with caplog.at_level(logging.WARNING, logger="test_fetch_participant_details"):
        result = fetch_participant_details(
            client, 1181, 1001, "Rider", logger, "jane-doe"
        )

    assert result is None
    assert any("jane-doe" in record.message for record in caplog.records)


def test_fetch_participant_details_returns_every_field_on_success():
    client = _StubClient(detail_html_by_id={1001: _load("applicant_detail_popup.html")})
    logger = logging.getLogger("test_fetch_participant_details_success")

    result = fetch_participant_details(client, 1181, 1001, "Rider", logger, "jane-doe")

    assert result == {
        "birthday": "1990-03-15",
        "sex": "Female",
        "num_previous_seasons": 0,
        "email": "jane.doe@example.test",
        "additional_roles": [],  # only the primary role (Rider) is on file
        "motive_for_participation": "Synthetic test motivation text.",
        "food_restrictions": None,  # site's literal "None" normalizes to null
    }


def test_fetch_participant_details_parses_a_nonzero_participated_count():
    client = _StubClient(
        detail_html_by_id={1001: _load("applicant_detail_popup_returning.html")}
    )
    logger = logging.getLogger("test_fetch_participant_details_returning")

    result = fetch_participant_details(
        client, 1181, 1001, "Service", logger, "jane-doe"
    )

    assert result == {
        "birthday": "1985-11-22",
        "sex": "Male",
        "num_previous_seasons": 3,
        "email": "john.smith@example.test",
        "additional_roles": ["Steering Committee", "Finance Manager"],
        "motive_for_participation": (
            "Synthetic first line,\nsynthetic second line of test motivation text."
        ),
        "food_restrictions": "Synthetic test restriction: no nuts.",
    }


def test_fetch_participant_details_returns_none_when_no_applicant_id():
    client = _StubClient()
    logger = logging.getLogger("test_fetch_participant_details_none")

    assert (
        fetch_participant_details(client, 1181, None, "Rider", logger, "jane-doe")
        is None
    )


def test_fetch_participant_details_reports_missing_fields_as_none():
    client = _StubClient(
        detail_html_by_id={1001: _load("applicant_detail_popup_no_birthday.html")}
    )
    logger = logging.getLogger("test_fetch_participant_details_missing")

    result = fetch_participant_details(client, 1181, 1001, "Rider", logger, "jane-doe")

    assert result == {
        "birthday": None,
        "sex": None,
        "num_previous_seasons": None,
        "email": None,
        "additional_roles": None,
        "motive_for_participation": None,
        "food_restrictions": None,
    }


def test_persist_records_isolates_a_single_detail_fetch_failure(tmp_path):
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
    assert summary["details_fetched"] == 1

    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    lucky_record = yaml.safe_load((a_dir / "lucky-person.yaml").read_text())
    assert lucky_record["birthday"] == "1990-03-15"
    assert lucky_record["sex"] == "Female"
    assert lucky_record["num_previous_seasons"] == 0

    unlucky_record = yaml.safe_load((a_dir / "unlucky-person.yaml").read_text())
    assert unlucky_record["birthday"] is None
    assert unlucky_record["sex"] is None
    assert unlucky_record["num_previous_seasons"] is None


# --- Already-known fields are never re-fetched or overwritten --------------


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
                "email": "jane.doe@example.test",
                "additional_roles": [],
                "birthday": "1975-12-24",
                "sex": "Female",
                "num_previous_seasons": 2,
                "motive_for_participation": "Already on file.",
                "food_restrictions": "Already on file.",
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
            raise AssertionError("must not fetch details already fully on file")

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

    assert summary["details_fetched"] == 0
    record = yaml.safe_load((a_dir / "jane-doe.yaml").read_text())
    assert record["birthday"] == "1975-12-24"
    assert record["sex"] == "Female"
    assert record["num_previous_seasons"] == 2


def test_persist_records_does_not_refetch_when_num_previous_seasons_is_already_zero(
    tmp_path,
):
    # Regression guard: 0 is a real, meaningful "first-time applicant" value,
    # not "not yet known" -- a naive truthiness check on this field would
    # treat an existing 0 as still-missing and re-fetch forever.
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
                "email": "jane.doe@example.test",
                "additional_roles": [],
                "birthday": "1975-12-24",
                "sex": "Female",
                "num_previous_seasons": 0,
                "motive_for_participation": "Already on file.",
                "food_restrictions": "Already on file.",
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
            raise AssertionError("must not fetch details already fully on file")

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

    assert summary["details_fetched"] == 0
    record = yaml.safe_load((a_dir / "jane-doe.yaml").read_text())
    assert record["num_previous_seasons"] == 0


def test_persist_records_still_fetches_when_only_num_previous_seasons_is_missing(
    tmp_path,
):
    # birthday, sex, and the other detail-popup fields are already known, but
    # num_previous_seasons isn't -- the popup must still be fetched, and only
    # the missing field filled in.
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
                "email": "jane.doe@example.test",
                "additional_roles": [],
                "birthday": "1975-12-24",
                "sex": "Female",
                "num_previous_seasons": None,
                "motive_for_participation": "Already on file.",
                "food_restrictions": "Already on file.",
                "status": "yes",
                "excluded": False,
                "excluded_observed_at": None,
                "ignore": False,
                "photo": None,
            }
        )
    )

    logger, _ = setup_run_logger(tmp_path / "logs")
    client = _StubClient(
        detail_html_by_id={9001: _load("applicant_detail_popup_returning.html")}
    )
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

    summary = persist_records(tmp_path, "2025-26", 1181, rows, client, logger)

    assert summary["details_fetched"] == 1
    record = yaml.safe_load((a_dir / "jane-doe.yaml").read_text())
    assert record["birthday"] == "1975-12-24"  # unchanged, still hand-corrected
    assert record["sex"] == "Female"  # unchanged
    assert record["num_previous_seasons"] == 3  # filled from the popup
    assert record["email"] == "jane.doe@example.test"  # unchanged
    assert record["additional_roles"] == []  # unchanged
    assert record["motive_for_participation"] == "Already on file."  # unchanged
    assert record["food_restrictions"] == "Already on file."  # unchanged
