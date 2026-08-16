"""Shared test helpers: fixture loading and standard `responses` mock registration
for the intranet's login/season-selector endpoints (FR-021: no real network calls)."""

from pathlib import Path

import responses

BASE_URL = "https://intranet.team-rynkeby.com"
LOGIN_URL = f"{BASE_URL}/login"
APPLICANTS_URL = f"{BASE_URL}/team/applicants"
AJAX_URL = f"{BASE_URL}/Ajax/team_application_manager.php"

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
