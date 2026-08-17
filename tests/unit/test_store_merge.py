"""Unit tests for the persistence/merge behavior across user stories.

Story 1 (this phase): first-run happy path -- multi-page fetch, "no"-status
exclusion, default-season selection (FR-016, SC-005). Later phases (US2-US4)
append their own tests to this same file per plan.md's test-module layout.
"""

from datetime import date

import responses
import yaml
from conftest import (
    load_fixture,
    register_ajax_page,
    register_participant_detail,
    register_season_selector,
    register_successful_login,
)

from scripts.scrape_applicants import (
    main,
    merge_record,
    persist_records,
    setup_run_logger,
    validate_record,
)

BASE_URL = "https://intranet.team-rynkeby.com"


def _register_photo(path_no_query: str) -> None:
    responses.add(
        responses.GET,
        BASE_URL + path_no_query,
        body=b"fake-jpeg-bytes",
        status=200,
        content_type="image/jpeg",
    )


@responses.activate
def test_first_run_persists_multi_page_non_no_applicants_with_default_season(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RKBY_INTRANET_USERNAME", "someone")
    monkeypatch.setenv("RKBY_INTRANET_PASSWORD", "secret")
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    register_successful_login()
    register_season_selector()
    register_ajax_page(0, load_fixture("applicants_page_1.html"))
    register_ajax_page(1, load_fixture("applicants_page_2.html"))
    register_ajax_page(2, load_fixture("applicants_page_2.html"))  # no new rows -> stop
    _register_photo("/uploaded/webusers/1001_1700000000_11111111/max.jpg")
    _register_photo("/uploaded/webusers/1004_1700000003_44444444/petra.jpg")
    _register_photo("/uploaded/webusers/1005_1700000004_55555555/lena.jpg")
    birthday_html = load_fixture("applicant_detail_popup.html")
    for applicant_id in (1001, 1003, 1004, 1005):  # not 1002 (erika): status "no"
        register_participant_detail(applicant_id, birthday_html)

    # No --season passed: default_season_label(2026-03-01) == "2025-26",
    # matching the 1181 season id in season_selector_page.html (FR-022).
    exit_code = main([], today=date(2026, 3, 1))

    assert exit_code == 0

    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    written = {p.stem for p in a_dir.glob("*.yaml")}
    assert written == {
        "max-mustermann",
        "jonas-beispiel",
        "petra-beispiel",
        "lena-beispiel",
    }
    assert "erika-beispiel" not in written  # status "no" -> excluded from persistence

    log_files = list((tmp_path / "seasons" / "2025-26" / "logs").glob("*.log"))
    assert len(log_files) == 1
    assert "WARNING" not in log_files[0].read_text()

    for record_file in a_dir.glob("*.yaml"):
        record = yaml.safe_load(record_file.read_text())
        validate_record(record)  # must not raise -- SC-005
        assert record["birthday"] == "1990-03-15"  # fetched from the detail popup
        assert record["sex"] == "Female"  # ditto
        assert record["num_previous_seasons"] == 0  # ditto

    max_record = yaml.safe_load((a_dir / "max-mustermann.yaml").read_text())
    assert max_record["role"] == "Rider"  # scraped straight from the Role column


# --- Story 2: re-run without losing manual corrections (FR-009, SC-002, SC-003) ---


def _base_record(**overrides) -> dict:
    record = {
        "match_key": "jane-doe",
        "first_name": "Jane",
        "last_name": "Doe",
        "address": None,
        "phone": None,
        "role": None,
        "birthday": None,
        "status": "yes",
        "excluded": False,
        "excluded_observed_at": None,
        "ignore": False,
        "photo": None,
    }
    record.update(overrides)
    return record


def test_merge_record_keeps_a_hand_corrected_field_even_when_scraped_value_differs():
    existing = _base_record(address="Hand-corrected street 1")
    scraped = {"address": "Some Other Street 5", "phone": None, "birthday": None}

    merged = merge_record(existing, scraped)

    assert merged["address"] == "Hand-corrected street 1"


def test_merge_record_fills_a_field_that_was_previously_empty():
    existing = _base_record(phone=None)
    scraped = {"address": None, "phone": "01701234567", "birthday": None}

    merged = merge_record(existing, scraped)

    assert merged["phone"] == "01701234567"


def test_merge_record_fills_role_when_previously_empty():
    existing = _base_record(role=None)
    scraped = {"address": None, "phone": None, "birthday": None, "role": "Rider"}

    merged = merge_record(existing, scraped)

    assert merged["role"] == "Rider"


def test_merge_record_keeps_a_hand_corrected_role_even_when_scraped_value_differs():
    existing = _base_record(role="Service Crew")
    scraped = {"address": None, "phone": None, "birthday": None, "role": "Rider"}

    merged = merge_record(existing, scraped)

    assert merged["role"] == "Service Crew"


def test_merge_record_backfills_role_on_a_pre_existing_record_missing_the_key():
    # A record persisted before the "role" field existed has no "role" key
    # at all -- merge must still fill it in, not KeyError.
    existing = _base_record()
    del existing["role"]
    scraped = {"address": None, "phone": None, "birthday": None, "role": "Rider"}

    merged = merge_record(existing, scraped)

    assert merged["role"] == "Rider"


def test_merge_record_never_rewrites_the_frozen_status_field():
    existing = _base_record(status="yes")
    scraped = {"address": None, "phone": None, "birthday": None, "status": "no"}

    merged = merge_record(existing, scraped)

    assert merged["status"] == "yes"


@responses.activate
def test_rerun_preserves_manual_edit_and_still_adds_a_genuinely_new_applicant(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RKBY_INTRANET_USERNAME", "someone")
    monkeypatch.setenv("RKBY_INTRANET_PASSWORD", "secret")
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    p_dir = tmp_path / "seasons" / "2025-26" / "photos"
    a_dir.mkdir(parents=True)
    p_dir.mkdir(parents=True)
    (a_dir / "max-mustermann.yaml").write_text(
        yaml.safe_dump(
            _base_record(
                match_key="max-mustermann",
                first_name="Max",
                last_name="Mustermann",
                address="A hand-corrected address",
                phone="0000000000",
            )
        )
    )

    register_successful_login()
    register_season_selector()
    register_ajax_page(0, load_fixture("applicants_page_1.html"))
    register_ajax_page(1, load_fixture("applicants_page_2.html"))
    register_ajax_page(2, load_fixture("applicants_page_2.html"))
    _register_photo("/uploaded/webusers/1004_1700000003_44444444/petra.jpg")
    _register_photo("/uploaded/webusers/1005_1700000004_55555555/lena.jpg")

    exit_code = main(["--season", "2025-26"])

    assert exit_code == 0

    max_record = yaml.safe_load((a_dir / "max-mustermann.yaml").read_text())
    assert max_record["address"] == "A hand-corrected address"
    assert max_record["phone"] == "0000000000"

    assert (a_dir / "lena-beispiel.yaml").exists()  # genuinely new applicant added


@responses.activate
def test_rerun_with_no_upstream_changes_touches_zero_files(tmp_path, monkeypatch):
    monkeypatch.setenv("RKBY_INTRANET_USERNAME", "someone")
    monkeypatch.setenv("RKBY_INTRANET_PASSWORD", "secret")
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    register_successful_login()
    register_season_selector()
    register_ajax_page(0, load_fixture("applicants_page_1.html"))
    register_ajax_page(1, load_fixture("applicants_page_2.html"))
    register_ajax_page(2, load_fixture("applicants_page_2.html"))
    _register_photo("/uploaded/webusers/1001_1700000000_11111111/max.jpg")
    _register_photo("/uploaded/webusers/1004_1700000003_44444444/petra.jpg")
    _register_photo("/uploaded/webusers/1005_1700000004_55555555/lena.jpg")

    assert main(["--season", "2025-26"]) == 0

    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    mtimes_before = {p.name: p.stat().st_mtime_ns for p in a_dir.glob("*.yaml")}

    # Second run: same upstream data, but photos already exist on disk so no
    # new HTTP calls for them are registered/expected this time.
    register_ajax_page(0, load_fixture("applicants_page_1.html"))
    register_ajax_page(1, load_fixture("applicants_page_2.html"))
    register_ajax_page(2, load_fixture("applicants_page_2.html"))

    assert main(["--season", "2025-26"]) == 0

    mtimes_after = {p.name: p.stat().st_mtime_ns for p in a_dir.glob("*.yaml")}
    assert mtimes_before == mtimes_after  # SC-002: zero files touched


# --- Story 3: an ignore == true record is never touched or recreated (FR-010/011) --


class _NoPhotoClient:
    """A client whose photo fetch would fail the test if ever called -- the
    ignore short-circuit must skip photo handling entirely for that record."""

    def fetch_photo_bytes(self, thumbnail_url: str) -> bytes:
        raise AssertionError("must not fetch a photo for an ignored record")


def test_ignored_record_is_byte_for_byte_unchanged_even_if_person_reappears(tmp_path):
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    a_dir.mkdir(parents=True)
    ignored_file = a_dir / "jane-doe.yaml"
    ignored_content = yaml.safe_dump(
        _base_record(
            match_key="jane-doe",
            first_name="Jane",
            last_name="Doe",
            status="yes",
            ignore=True,
        )
    )
    ignored_file.write_text(ignored_content)

    logger, _ = setup_run_logger(tmp_path / "logs")

    # Same person reappears in the scrape with different (even conflicting) data.
    rows = [
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "phone": "0000000000",
            "address": "Somewhere Else 9",
            "status": "no",
            "photo_thumbnail_url": "/jane.jpg?w=60",
        }
    ]

    summary = persist_records(tmp_path, "2025-26", 1181, rows, _NoPhotoClient(), logger)

    assert ignored_file.read_text() == ignored_content
    assert summary["created"] == 0
    assert summary["updated"] == 0
    assert summary["photos_fetched"] == 0


# --- Story 4: automatic exclusion on disapproval (FR-015, FR-016) -----------


def test_status_flip_to_no_sets_excluded_and_timestamp_leaving_other_fields_unchanged(
    tmp_path,
):
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    a_dir.mkdir(parents=True)
    (a_dir / "jane-doe.yaml").write_text(
        yaml.safe_dump(
            _base_record(
                match_key="jane-doe",
                first_name="Jane",
                last_name="Doe",
                address="Original Street 1",
                status="yes",
            )
        )
    )

    logger, log_file = setup_run_logger(tmp_path / "logs")
    rows = [
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "phone": None,
            "address": "A Different Street 2",  # would-be update, ignored per FR-015
            "status": "no",
            "photo_thumbnail_url": None,
        }
    ]

    summary = persist_records(tmp_path, "2025-26", 1181, rows, _NoPhotoClient(), logger)
    for handler in logger.handlers:
        handler.flush()

    updated_record = yaml.safe_load((a_dir / "jane-doe.yaml").read_text())
    assert updated_record["excluded"] is True
    assert updated_record["excluded_observed_at"] is not None
    assert updated_record["status"] == "yes"  # frozen, never rewritten
    assert updated_record["address"] == "Original Street 1"  # left unchanged
    assert summary["updated"] == 1
    assert "jane-doe" in log_file.read_text()  # FR-016: warning landed in the run log


def test_record_persisted_before_role_existed_can_still_be_rewritten(tmp_path):
    # Regression: a record written before "role" was added to the schema has
    # no "role" key at all on disk. Any later write path (here: the FR-015
    # exclusion flip) must backfill it as null rather than KeyError.
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    a_dir.mkdir(parents=True)
    pre_role_record = _base_record(
        match_key="jane-doe", first_name="Jane", last_name="Doe", status="yes"
    )
    del pre_role_record["role"]
    (a_dir / "jane-doe.yaml").write_text(yaml.safe_dump(pre_role_record))

    logger, _log_file = setup_run_logger(tmp_path / "logs")
    rows = [
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "phone": None,
            "address": None,
            "status": "no",
            "photo_thumbnail_url": None,
        }
    ]

    summary = persist_records(tmp_path, "2025-26", 1181, rows, _NoPhotoClient(), logger)

    assert summary["validation_errors"] == 0
    updated_record = yaml.safe_load((a_dir / "jane-doe.yaml").read_text())
    assert updated_record["excluded"] is True
    assert updated_record["role"] is None


def test_ignored_record_observing_no_status_produces_no_exclusion_and_no_log(
    tmp_path,
):
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    a_dir.mkdir(parents=True)
    ignored_content = yaml.safe_dump(
        _base_record(
            match_key="jane-doe",
            first_name="Jane",
            last_name="Doe",
            status="yes",
            ignore=True,
        )
    )
    ignored_file = a_dir / "jane-doe.yaml"
    ignored_file.write_text(ignored_content)

    logger, log_file = setup_run_logger(tmp_path / "logs")
    rows = [
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "phone": None,
            "address": None,
            "status": "no",
            "photo_thumbnail_url": None,
        }
    ]

    persist_records(tmp_path, "2025-26", 1181, rows, _NoPhotoClient(), logger)
    for handler in logger.handlers:
        handler.flush()

    assert ignored_file.read_text() == ignored_content  # untouched (ignore wins)
    assert log_file.read_text() == ""


def test_a_never_before_seen_no_status_applicant_is_still_never_persisted(tmp_path):
    logger, _ = setup_run_logger(tmp_path / "logs")
    rows = [
        {
            "first_name": "Fresh",
            "last_name": "Rejection",
            "phone": None,
            "address": None,
            "status": "no",
            "photo_thumbnail_url": None,
        }
    ]

    summary = persist_records(tmp_path, "2025-26", 1181, rows, _NoPhotoClient(), logger)

    assert summary["created"] == 0
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    assert not (a_dir / "fresh-rejection.yaml").exists()
