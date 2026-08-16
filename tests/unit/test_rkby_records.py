"""Unit tests for the shared `scripts/rkby_records.py` module (research.md §10):
season/record I/O extracted out of `scrape_applicants.py` so both it and
`generate_member_maps.py` share one tested implementation, plus the two names
only the map generator needs: `discover_seasons` and the generalized
`auto_commit` helper."""

import logging
import subprocess

import jsonschema
import pytest
import yaml

from scripts.rkby_records import (
    InvalidExistingRecordError,
    applicants_dir,
    auto_commit,
    discover_seasons,
    load_existing_records,
    load_schema,
    logs_dir,
    normalize_name,
    photos_dir,
    season_dir,
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


# --- Directory layout helpers -------------------------------------------------


def test_season_dir_joins_data_dir_seasons_and_label(tmp_path):
    assert season_dir(tmp_path, "2025-26") == tmp_path / "seasons" / "2025-26"


def test_applicants_dir_is_season_dir_slash_applicants(tmp_path):
    assert (
        applicants_dir(tmp_path, "2025-26")
        == season_dir(tmp_path, "2025-26") / "applicants"
    )


def test_photos_dir_is_season_dir_slash_photos(tmp_path):
    assert photos_dir(tmp_path, "2025-26") == season_dir(tmp_path, "2025-26") / "photos"


def test_logs_dir_is_season_dir_slash_logs(tmp_path):
    assert logs_dir(tmp_path, "2025-26") == season_dir(tmp_path, "2025-26") / "logs"


# --- Schema load/validate ------------------------------------------------------


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


def test_load_schema_includes_the_new_latitude_longitude_properties():
    schema = load_schema()

    assert schema["properties"]["latitude"]["type"] == ["number", "null"]
    assert schema["properties"]["longitude"]["type"] == ["number", "null"]


def test_validate_record_accepts_a_valid_record():
    validate_record(VALID_RECORD)  # must not raise


def test_validate_record_accepts_latitude_and_longitude():
    record = {**VALID_RECORD, "latitude": 53.55, "longitude": 9.99}
    validate_record(record)  # must not raise


def test_validate_record_raises_on_structurally_invalid_record():
    broken_record = {**VALID_RECORD, "match_key": None}
    with pytest.raises(jsonschema.exceptions.ValidationError):
        validate_record(broken_record)


# --- load_existing_records / InvalidExistingRecordError -----------------------


def test_load_existing_records_returns_empty_dict_when_no_applicants_dir(tmp_path):
    assert load_existing_records(tmp_path, "2025-26") == {}


def test_load_existing_records_loads_valid_records_keyed_by_match_key(tmp_path):
    a_dir = applicants_dir(tmp_path, "2025-26")
    a_dir.mkdir(parents=True)
    (a_dir / "jane-doe.yaml").write_text(yaml.safe_dump(VALID_RECORD))

    records = load_existing_records(tmp_path, "2025-26")

    assert records == {"jane-doe": VALID_RECORD}


def test_load_existing_records_raises_on_an_invalid_existing_file(tmp_path):
    a_dir = applicants_dir(tmp_path, "2025-26")
    a_dir.mkdir(parents=True)
    (a_dir / "broken.yaml").write_text("match_key: broken\nfirst_name: Broken\n")

    with pytest.raises(InvalidExistingRecordError):
        load_existing_records(tmp_path, "2025-26")


# --- normalize_name -------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Jane", "jane"),
        ("  Jane  ", "jane"),
        ("Jan-Åke", "jan-ake"),
        ("Müller", "muller"),
        ("O'Brien", "obrien"),
    ],
)
def test_normalize_name_strips_diacritics_case_and_whitespace(raw, expected):
    assert normalize_name(raw) == expected


# --- setup_run_logger ------------------------------------------------------------


def test_setup_run_logger_writes_warnings_to_file_and_streams_info_to_console(
    tmp_path, capsys
):
    logger, log_file = setup_run_logger(
        tmp_path, logger_name="test_rkby_records_logger"
    )

    logger.info("informational progress message")
    logger.warning("something worth reviewing")

    for handler in logger.handlers:
        handler.flush()

    assert log_file.parent == tmp_path
    assert log_file.exists()

    file_contents = log_file.read_text()
    assert "something worth reviewing" in file_contents
    assert "informational progress message" not in file_contents

    captured = capsys.readouterr()
    console_output = captured.out + captured.err
    assert "informational progress message" in console_output


# --- discover_seasons ------------------------------------------------------------


def test_discover_seasons_lists_only_season_folders_with_an_applicants_subdir(tmp_path):
    (tmp_path / "seasons" / "2024-25" / "applicants").mkdir(parents=True)
    (tmp_path / "seasons" / "2025-26" / "applicants").mkdir(parents=True)
    # A season folder with no applicants/ subdir yet must not be reported.
    (tmp_path / "seasons" / "2026-27").mkdir(parents=True)

    assert discover_seasons(tmp_path) == ["2024-25", "2025-26"]


def test_discover_seasons_returns_empty_list_when_no_seasons_dir(tmp_path):
    assert discover_seasons(tmp_path) == []


def test_discover_seasons_returns_empty_list_for_an_empty_seasons_dir(tmp_path):
    (tmp_path / "seasons").mkdir()
    assert discover_seasons(tmp_path) == []


# --- auto_commit (generalized) ---------------------------------------------------


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", cwd=path)
    _git("config", "user.email", "test@example.test", cwd=path)
    _git("config", "user.name", "Test User", cwd=path)


def _head(path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def test_auto_commit_creates_a_commit_for_the_given_paths_when_git_detected(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "some_dir").mkdir()
    (tmp_path / "some_dir" / "file.yaml").write_text("a: 1\n")

    logger = logging.getLogger("test_auto_commit_generic")
    auto_commit(tmp_path, ["some_dir"], "test commit message", logger)

    log_result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "test commit message" in log_result.stdout


def test_auto_commit_is_a_noop_when_nothing_changed(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "some_dir").mkdir()
    (tmp_path / "some_dir" / "file.yaml").write_text("a: 1\n")
    _git("add", "some_dir", cwd=tmp_path)
    _git("commit", "-m", "initial", cwd=tmp_path)
    head_before = _head(tmp_path)

    logger = logging.getLogger("test_auto_commit_generic_noop")
    auto_commit(tmp_path, ["some_dir"], "test commit message", logger)

    assert _head(tmp_path) == head_before


def test_auto_commit_is_a_noop_when_data_dir_is_not_a_git_repo(tmp_path):
    (tmp_path / "some_dir").mkdir()
    (tmp_path / "some_dir" / "file.yaml").write_text("a: 1\n")

    logger = logging.getLogger("test_auto_commit_generic_not_git")
    auto_commit(tmp_path, ["some_dir"], "test commit message", logger)  # must not raise

    assert not (tmp_path / ".git").exists()


def test_auto_commit_skips_paths_that_dont_exist(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "present").mkdir()
    (tmp_path / "present" / "file.yaml").write_text("a: 1\n")

    logger = logging.getLogger("test_auto_commit_generic_missing_path")
    # "absent" doesn't exist -- must not raise, and the existing path still commits.
    auto_commit(tmp_path, ["absent", "present"], "test commit message", logger)

    log_result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "test commit message" in log_result.stdout


def test_auto_commit_failure_logs_warning_without_raising(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    (tmp_path / "some_dir").mkdir()
    (tmp_path / "some_dir" / "file.yaml").write_text("a: 1\n")

    _git("config", "--unset", "user.email", cwd=tmp_path)
    _git("config", "--unset", "user.name", cwd=tmp_path)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "nonexistent-gitconfig"))
    monkeypatch.setenv(
        "GIT_CONFIG_SYSTEM", str(tmp_path / "nonexistent-system-gitconfig")
    )
    for var in (
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "EMAIL",
    ):
        monkeypatch.delenv(var, raising=False)

    logger, log_file = setup_run_logger(
        tmp_path / "logs", logger_name="test_auto_commit_generic_failure"
    )

    auto_commit(tmp_path, ["some_dir"], "test commit message", logger)  # must not raise

    for handler in logger.handlers:
        handler.flush()
    assert "WARNING" in log_file.read_text()
