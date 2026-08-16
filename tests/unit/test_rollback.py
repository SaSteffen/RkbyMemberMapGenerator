"""Unit tests for all-or-nothing rollback: a page-fetch failure mid-pagination
leaves the season directory byte-for-byte untouched (FR-018)."""

import responses
from conftest import (
    load_fixture,
    register_ajax_page,
    register_season_selector,
    register_successful_login,
)

from scripts.scrape_applicants import applicants_dir, main


@responses.activate
def test_a_mid_pagination_failure_leaves_applicants_dir_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("RKBY_INTRANET_USERNAME", "someone")
    monkeypatch.setenv("RKBY_INTRANET_PASSWORD", "secret")
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    register_successful_login()
    register_season_selector()
    register_ajax_page(0, load_fixture("applicants_page_1.html"))
    register_ajax_page(1, "", status=500)  # page 1 fails mid-pagination

    exit_code = main(["--season", "2025-26"])

    assert exit_code != 0
    a_dir = applicants_dir(tmp_path, "2025-26")
    assert not a_dir.exists() or list(a_dir.iterdir()) == []


@responses.activate
def test_a_mid_pagination_failure_leaves_pre_existing_records_byte_for_byte_unchanged(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RKBY_INTRANET_USERNAME", "someone")
    monkeypatch.setenv("RKBY_INTRANET_PASSWORD", "secret")
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    a_dir = applicants_dir(tmp_path, "2025-26")
    a_dir.mkdir(parents=True)
    existing_file = a_dir / "existing-person.yaml"
    existing_content = "match_key: existing-person\nfirst_name: Existing\n"
    existing_file.write_text(existing_content)

    register_successful_login()
    register_season_selector()
    register_ajax_page(0, load_fixture("applicants_page_1.html"))
    register_ajax_page(1, "", status=500)

    exit_code = main(["--season", "2025-26"])

    assert exit_code != 0
    assert existing_file.read_text() == existing_content
    assert list(a_dir.iterdir()) == [existing_file]
