"""Unit tests for schema validation: a valid record passes, a structurally
invalid record raises a clear error (FR-017)."""

import jsonschema
import pytest
import responses
from conftest import (
    load_fixture,
    register_ajax_page,
    register_season_selector,
    register_successful_login,
)

from scripts.scrape_applicants import (
    InvalidExistingRecordError,
    load_existing_records,
    load_schema,
    main,
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
