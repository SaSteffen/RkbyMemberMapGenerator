"""Shared test helpers: fixture loading and standard `responses` mock registration
for the intranet's login/season-selector endpoints (FR-021: no real network calls)."""

from pathlib import Path

import pytest
import responses

import scripts.rkby_maps.geocoding as _geocoding_module


@pytest.fixture(autouse=True)
def _reset_geocoding_throttle_state():
    """The Nominatim client's 1 req/sec throttle (research.md §3) tracks the
    last request time in module state so it holds across every call made
    during one real run -- reset it before each test so an earlier test's
    timestamp never causes an unrelated test to sleep for real."""
    _geocoding_module._last_request_monotonic = None
    yield


BASE_URL = "https://intranet.team-rynkeby.com"
LOGIN_URL = f"{BASE_URL}/login"
APPLICANTS_URL = f"{BASE_URL}/team/applicants"
AJAX_URL = f"{BASE_URL}/Ajax/team_application_manager.php"
PARTICIPANT_URL = f"{BASE_URL}/Ajax/showparticipant.php"

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def register_successful_login() -> None:
    responses.add(
        responses.POST,
        LOGIN_URL,
        body="<html><body>Welcome</body></html>",
        status=200,
    )


def register_failed_login() -> None:
    responses.add(
        responses.POST,
        LOGIN_URL,
        body=load_fixture("login_page.html"),
        status=200,
    )


def register_season_selector() -> None:
    responses.add(
        responses.GET,
        APPLICANTS_URL,
        body=load_fixture("season_selector_page.html"),
        status=200,
    )


def register_ajax_page(page: int, body: str, status: int = 200) -> None:
    responses.add(
        responses.GET,
        AJAX_URL,
        body=body,
        status=status,
        match=[
            responses.matchers.query_param_matcher(
                {
                    "tableSettings": "true",
                    "teamid": "740",
                    "season": "1181",
                    "filter_status": "",
                    "page": str(page),
                }
            )
        ],
    )


def register_participant_detail(
    applicant_id: int, body: str, season: int = 1181, status: int = 200
) -> None:
    responses.add(
        responses.GET,
        PARTICIPANT_URL,
        body=body,
        status=status,
        match=[
            responses.matchers.query_param_matcher(
                {
                    "season": str(season),
                    "mplc": "/team/applicants",
                    "userid": str(applicant_id),
                }
            )
        ],
    )
