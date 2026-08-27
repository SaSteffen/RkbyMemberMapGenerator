"""Unit tests for `scripts/rkby_pairing/roles.py` (research.md §4, data-model.md
§ Role Classification): recognized-role classification against
`scripts.rkby_maps.rendering.ROLE_COLORS`'s keys."""

import pytest

from scripts.rkby_pairing.roles import classify_role


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Rider", "rider"),
        ("rider", "rider"),
        ("RIDER", "rider"),
        ("  Rider  ", "rider"),
        ("Service Crew", "service_crew"),
        ("service crew", "service_crew"),
        ("  SERVICE CREW  ", "service_crew"),
        ("Supporter", "supporter"),
        ("supporter", "supporter"),
        ("  Supporter  ", "supporter"),
    ],
)
def test_classify_role_recognizes_every_spelling_case_and_whitespace_variant(
    raw, expected
):
    assert classify_role(raw) == expected


@pytest.mark.parametrize("raw", ["Coach", "Volunteer", "typo-role", "123"])
def test_classify_role_returns_none_for_an_unrecognized_string(raw):
    assert classify_role(raw) is None


def test_classify_role_returns_none_for_none():
    assert classify_role(None) is None


def test_classify_role_returns_none_for_a_blank_string():
    assert classify_role("") is None
    assert classify_role("   ") is None
