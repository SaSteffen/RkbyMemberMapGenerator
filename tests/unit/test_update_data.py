"""Unit tests for --update-data: a shortcut that re-scrapes every season that
already has data under RKBY_DATA_DIR, instead of requiring the caller to invoke
this script once per season with --season."""

import pytest
import responses
from conftest import (
    load_fixture,
    register_ajax_page,
    register_season_selector,
    register_successful_login,
)

from scripts.scrape_applicants import applicants_dir, build_arg_parser, main

# season_selector_page.html maps 2024-25 -> 504, 2025-26 -> 1181, 2026-27 -> 1182.


def _seed_existing_season(tmp_path, season_label):
    a_dir = applicants_dir(tmp_path, season_label)
    a_dir.mkdir(parents=True)


def test_season_and_update_data_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        build_arg_parser().parse_args(["--season", "2025-26", "--update-data"])


def test_update_data_with_no_existing_seasons_makes_zero_http_calls_and_exits_zero(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RKBY_INTRANET_USERNAME", "someone")
    monkeypatch.setenv("RKBY_INTRANET_PASSWORD", "secret")
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    with responses.RequestsMock() as mocked:  # any HTTP call -> ConnectionError
        exit_code = main(["--update-data"])
        assert len(mocked.calls) == 0

    assert exit_code == 0


@responses.activate
def test_update_data_scrapes_only_seasons_that_already_have_data(tmp_path, monkeypatch):
    monkeypatch.setenv("RKBY_INTRANET_USERNAME", "someone")
    monkeypatch.setenv("RKBY_INTRANET_PASSWORD", "secret")
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    _seed_existing_season(tmp_path, "2024-25")
    _seed_existing_season(tmp_path, "2025-26")
    # 2026-27 is on the site (season selector) but was never scraped locally
    # -- --update-data must leave it untouched.

    register_successful_login()
    register_season_selector()
    page_html = load_fixture("applicants_page_1.html")
    register_ajax_page(0, page_html, season=504)
    register_ajax_page(1, page_html, season=504)  # same rows again -> stop
    register_ajax_page(0, page_html, season=1181)
    register_ajax_page(1, page_html, season=1181)

    exit_code = main(["--update-data"])

    assert exit_code == 0
    assert list(applicants_dir(tmp_path, "2024-25").glob("*.yaml"))
    assert list(applicants_dir(tmp_path, "2025-26").glob("*.yaml"))
    assert not (tmp_path / "seasons" / "2026-27").exists()

    login_calls = [
        call
        for call in responses.calls
        if call.request.url.startswith("https://intranet.team-rynkeby.com/login")
    ]
    assert len(login_calls) == 1  # one shared login, not one per season


@responses.activate
def test_update_data_continues_past_a_failed_season_and_reports_non_zero(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RKBY_INTRANET_USERNAME", "someone")
    monkeypatch.setenv("RKBY_INTRANET_PASSWORD", "secret")
    monkeypatch.setenv("RKBY_DATA_DIR", str(tmp_path))

    _seed_existing_season(tmp_path, "2024-25")
    _seed_existing_season(tmp_path, "2025-26")

    register_successful_login()
    register_season_selector()
    register_ajax_page(0, "", status=500, season=504)  # 2024-25 fails immediately
    page_html = load_fixture("applicants_page_1.html")
    register_ajax_page(0, page_html, season=1181)
    register_ajax_page(1, page_html, season=1181)  # 2025-26 succeeds

    exit_code = main(["--update-data"])

    assert exit_code != 0
    assert list(applicants_dir(tmp_path, "2024-25").glob("*.yaml")) == []
    assert list(applicants_dir(tmp_path, "2025-26").glob("*.yaml"))
