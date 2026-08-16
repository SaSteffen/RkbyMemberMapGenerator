"""Unit tests for default-season computation and season-label parsing (FR-022)."""

from datetime import date

import pytest

from scripts.scrape_applicants import default_season_label, parse_season_arg


@pytest.mark.parametrize(
    ("today", "expected_label"),
    [
        (date(2026, 1, 1), "2025-26"),
        (date(2026, 6, 15), "2025-26"),
        (
            date(2026, 7, 31),
            "2025-26",
        ),  # July still belongs to the season ending that year
        (date(2026, 8, 1), "2026-27"),  # August starts the new season's bucket
        (date(2026, 8, 31), "2026-27"),
        (date(2026, 12, 31), "2026-27"),
    ],
)
def test_default_season_label_follows_july_august_boundary(today, expected_label):
    assert default_season_label(today) == expected_label


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2025-26", "2025-26"),
        ("2025/26", "2025-26"),
    ],
)
def test_parse_season_arg_normalizes_to_hyphen_form(raw, expected):
    assert parse_season_arg(raw) == expected


@pytest.mark.parametrize("invalid", ["2025", "25-26", "2025_26", "", "abcd-ef"])
def test_parse_season_arg_rejects_malformed_input(invalid):
    with pytest.raises(ValueError):
        parse_season_arg(invalid)
