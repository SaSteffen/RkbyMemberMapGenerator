"""Unit tests for schema validation: a valid record passes, a structurally
invalid record raises a clear error (FR-017)."""

import jsonschema
import pytest
import responses
import yaml
from conftest import (
    load_fixture,
    register_ajax_page,
    register_season_selector,
    register_successful_login,
)

import scripts.scrape_applicants as scrape_applicants_module
from scripts.scrape_applicants import (
    InvalidExistingRecordError,
    load_existing_records,
    load_schema,
    main,
    persist_records,
    setup_run_logger,
    validate_record,
)

VALID_RECORD = {
    "match_key": "jane-doe",
    "first_name": "Jane",
    "last_name": "Doe",
    "address": None,
    "phone": None,
    "birthday": None,
    "status": "yes",
    "excluded": False,
    "excluded_observed_at": None,
    "ignore": False,
    "photo": None,
}


def test_load_schema_returns_a_dict_with_expected_required_fields():
    schema = load_schema()

    assert isinstance(schema, dict)
    assert set(schema["required"]) == {
        "match_key",
        "first_name",
        "last_name",
        "status",
        "excluded",
        "ignore",
    }


def test_validate_record_accepts_a_valid_record():
    validate_record(VALID_RECORD)  # must not raise


def test_validate_record_accepts_an_empty_last_name_single_name_applicant():
    # The intranet sometimes has just one name on file for a person -- no
    # last name, and no separator to split one out of.
    record = {**VALID_RECORD, "match_key": "robin", "last_name": ""}
    validate_record(record)  # must not raise


@pytest.mark.parametrize(
    "broken_record",
    [
        {**VALID_RECORD, "match_key": None},  # wrong type
        {
            k: v for k, v in VALID_RECORD.items() if k != "status"
        },  # missing required field
        {
            **VALID_RECORD,
            "extra_unexpected_field": "nope",
        },  # additionalProperties: false
        {
            **VALID_RECORD,
            "excluded": True,
            "excluded_observed_at": None,
        },  # conditional rule
    ],
)
def test_validate_record_raises_on_structurally_invalid_record(broken_record):
    with pytest.raises(jsonschema.exceptions.ValidationError):
        validate_record(broken_record)


# --- FR-017 edge case: a schema-invalid existing record aborts the run -------


def test_load_existing_records_raises_on_an_invalid_existing_file(tmp_path):
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    a_dir.mkdir(parents=True)
    (a_dir / "broken.yaml").write_text("match_key: broken\nfirst_name: Broken\n")

    with pytest.raises(InvalidExistingRecordError):
        load_existing_records(tmp_path, "2025-26")


@responses.activate
def test_a_schema_invalid_existing_record_aborts_the_run_without_writing_or_losing_data(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RKBY_INTRANET_USERNAME", "someone")
    monkeypatch.setenv("RKBY_INTRANET_PASSWORD", "secret")
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    a_dir.mkdir(parents=True)
    broken_file = a_dir / "broken.yaml"
    broken_content = (
        "match_key: broken\nfirst_name: Broken\n"  # missing required fields
    )
    broken_file.write_text(broken_content)

    register_successful_login()
    register_season_selector()
    register_ajax_page(0, load_fixture("applicants_page_1.html"))
    register_ajax_page(1, load_fixture("applicants_page_2.html"))
    register_ajax_page(2, load_fixture("applicants_page_2.html"))

    exit_code = main(["--season", "2025-26"])

    assert exit_code != 0
    assert broken_file.read_text() == broken_content
    assert [p.name for p in a_dir.iterdir()] == ["broken.yaml"]


# --- A schema-invalid *scraped* record is logged and skipped, not a crash ---


class _NoPhotoClient:
    """A client whose photo fetch would fail the test if ever called -- these
    tests don't exercise photo handling."""

    def fetch_photo_bytes(self, thumbnail_url: str) -> bytes:
        raise AssertionError("photo fetch not needed for these tests")


def test_a_schema_invalid_new_row_is_logged_with_the_full_record_and_skipped_not_crashed(
    tmp_path,
):
    logger, log_file = setup_run_logger(tmp_path / "logs")
    rows = [
        {
            # Empty first_name -> fails minLength AND yields an invalid
            # match_key (normalize_name("") == "", so match_key == "-doe",
            # which fails the schema's leading-hyphen-forbidding pattern).
            # A real-world equivalent: a Name cell with no space to split on.
            "first_name": "",
            "last_name": "Doe",
            "phone": None,
            "address": None,
            "status": "yes",
            "photo_thumbnail_url": None,
        },
        {
            "first_name": "Jane",
            "last_name": "Ok",
            "phone": None,
            "address": None,
            "status": "yes",
            "photo_thumbnail_url": None,
        },
    ]

    summary = persist_records(tmp_path, "2025-26", rows, _NoPhotoClient(), logger)
    for handler in logger.handlers:
        handler.flush()

    # The whole run must not crash uncaught (that was the bug: an unhandled
    # jsonschema.ValidationError here previously killed the process before
    # any logger call fired, leaving the run log empty), and the one bad row
    # must not block the rest of the season from being persisted.
    assert summary["validation_errors"] == 1
    assert summary["created"] == 1

    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    assert [p.stem for p in a_dir.glob("*.yaml")] == ["jane-ok"]

    log_contents = log_file.read_text()
    assert "failed schema validation" in log_contents
    # The problematic data itself must be dumped into the log, not just a
    # generic message -- otherwise the failure is undiagnosable after the fact.
    assert "Doe" in log_contents


def test_a_schema_invalid_merged_record_is_logged_and_skipped_leaving_existing_file_untouched(
    tmp_path, monkeypatch
):
    a_dir = tmp_path / "seasons" / "2025-26" / "applicants"
    a_dir.mkdir(parents=True)
    existing_content = yaml.safe_dump(VALID_RECORD)
    (a_dir / "jane-doe.yaml").write_text(existing_content)

    def fake_validate_record(record):
        # Only reject the freshly-merged record (phone now filled in), not
        # the unmodified existing record load_existing_records re-validates
        # first -- that one must still pass so we reach the merge/update path.
        if record["match_key"] == "jane-doe" and record.get("phone") == "0123456789":
            raise jsonschema.exceptions.ValidationError("forced failure for test")
        validate_record(record)

    monkeypatch.setattr(
        scrape_applicants_module, "validate_record", fake_validate_record
    )

    logger, log_file = setup_run_logger(tmp_path / "logs")
    rows = [
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "phone": "0123456789",  # would otherwise trigger an update
            "address": None,
            "status": "yes",
            "photo_thumbnail_url": None,
        }
    ]

    summary = persist_records(tmp_path, "2025-26", rows, _NoPhotoClient(), logger)
    for handler in logger.handlers:
        handler.flush()

    assert summary["validation_errors"] == 1
    assert summary["updated"] == 0
    assert (a_dir / "jane-doe.yaml").read_text() == existing_content

    log_contents = log_file.read_text()
    assert "failed schema validation" in log_contents
    assert "forced failure for test" in log_contents
