"""Unit tests for `scripts/rkby_report/aggregate.py`: season summaries
(data-model.md § Season Summary) and the FR-017 data-gap list
(data-model.md § Data Gap List), against the T007 synthetic fixtures."""

import shutil
from pathlib import Path

import pytest

from scripts.rkby_report.aggregate import (
    data_gaps,
    retention_by_split,
    retention_cohort,
    season_summary,
    season_trend,
)
from scripts.rkby_report.frame import build_member_season_frame

STATIC_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "report_seasons"


@pytest.fixture
def df(tmp_path):
    shutil.copytree(STATIC_FIXTURES_DIR, tmp_path / "seasons")
    return build_member_season_frame(tmp_path)


# --- season_summary() ----------------------------------------------------------


def test_season_summary_total_members_counts_only_that_seasons_eligible_rows(df):
    summary = season_summary(df, "2024-25")

    assert summary["season_label"] == "2024-25"
    assert summary["total_members"] == 10


def test_season_summary_role_counts_include_unknown(df):
    summary = season_summary(df, "2024-25")

    assert summary["role_counts"] == {
        "Rider": 4,
        "Service Crew": 3,
        "Supporter": 1,
        "Coach": 1,
        "unknown": 1,
    }


def test_season_summary_gender_counts_include_unknown(df):
    summary = season_summary(df, "2024-25")

    assert summary["gender_counts"] == {
        "Female": 5,
        "Male": 4,
        "unknown": 1,
    }


def test_season_summary_age_bucket_counts_include_unknown(df):
    summary = season_summary(df, "2024-25")

    assert summary["age_bucket_counts"] == {
        "<20": 1,
        "20-29": 2,
        "30-39": 2,
        "40-49": 2,
        "50-59": 1,
        "60+": 1,
        "unknown": 1,
    }


def test_season_summary_distance_bucket_counts_include_unknown_not_geocoded(df):
    summary = season_summary(df, "2024-25")

    assert summary["distance_bucket_counts"] == {
        "0-10km": 3,
        "10-25km": 2,
        "25-50km": 2,
        "50-100km": 1,
        "100km+": 1,
        "unknown/not geocoded": 1,
    }


def test_season_summary_for_a_different_season_reflects_only_that_seasons_rows(df):
    summary = season_summary(df, "2023-24")

    assert summary["total_members"] == 3
    assert summary["role_counts"] == {"Rider": 1, "Service Crew": 1, "Supporter": 1}


# --- data_gaps() (FR-017) -------------------------------------------------------


def test_data_gaps_one_row_per_observation_missing_a_field(df):
    gaps = data_gaps(df)

    by_key = {row["match_key"]: row["missing_fields"] for _, row in gaps.iterrows()}
    assert by_key == {
        "no-role-golf": ["role"],
        "no-sex-hotel": ["sex"],
        "no-birthday-india": ["age"],
        "veteran-foxtrot": ["distance"],
    }


def test_data_gaps_missing_birthday_reports_age_not_birthday(df):
    gaps = data_gaps(df)

    row = gaps[gaps["match_key"] == "no-birthday-india"].iloc[0]
    assert row["missing_fields"] == ["age"]


def test_data_gaps_a_fully_known_row_produces_no_output_row(df):
    gaps = data_gaps(df)

    assert "rider-alpha" not in set(gaps["match_key"])


def test_data_gaps_columns_are_only_match_key_season_label_missing_fields(df):
    gaps = data_gaps(df)

    assert set(gaps.columns) == {"match_key", "season_label", "missing_fields"}


# --- season_trend() (FR-009/FR-010) --------------------------------------------


def test_season_trend_one_row_per_season_in_chronological_order(df):
    trend = season_trend(df)

    assert list(trend["season_label"]) == ["2023-24", "2024-25", "2025-26"]


def test_season_trend_headline_counts_per_season(df):
    trend = season_trend(df)

    by_season = trend.set_index("season_label")
    assert list(by_season["total_members"]) == [3, 10, 3]
    assert list(by_season["rider_count"]) == [1, 4, 1]
    assert list(by_season["service_count"]) == [1, 3, 1]


def test_season_trend_pivots_age_gender_distance_wide_with_zero_for_absent_buckets(df):
    trend = season_trend(df)
    by_season = trend.set_index("season_label")

    # 2023-24 has no <20/50-59/60+/unknown age members -- must be 0, not
    # a missing column or NaN.
    assert by_season.loc["2023-24", "age_20-29"] == 1
    assert by_season.loc["2023-24", "age_<20"] == 0
    assert by_season.loc["2023-24", "age_unknown"] == 0

    assert by_season.loc["2024-25", "gender_Female"] == 5
    assert by_season.loc["2024-25", "gender_Male"] == 4
    assert by_season.loc["2024-25", "gender_unknown"] == 1

    assert by_season.loc["2025-26", "distance_0-10km"] == 1
    assert by_season.loc["2025-26", "distance_100km+"] == 0
    assert by_season.loc["2025-26", "distance_unknown/not geocoded"] == 0


def test_season_trend_single_season_is_detectable_as_not_enough_data(df):
    single_season_df = df[df["season_label"] == "2024-25"]

    trend = season_trend(single_season_df)

    assert len(trend) < 2


# --- retention_cohort() / retention_by_split() (FR-011/FR-012) ----------------


def test_retention_cohort_counts_and_rate_between_two_consecutive_seasons(df):
    cohort = retention_cohort(df, "2023-24", "2024-25")

    assert cohort["season_a"] == "2023-24"
    assert cohort["season_b"] == "2024-25"
    # erika-mustermann/erika-schmidt (alias-retained) is the only retained
    # member; departed-member and skip-return-member (skipped, not retained
    # across the gap) both count as departed.
    assert cohort["retained_count"] == 1
    assert cohort["departed_count"] == 2
    assert cohort["retention_rate"] == pytest.approx(1 / 3)


def test_retention_cohort_alias_retained_member_counts_as_retained(df):
    # Sanity check on the underlying mechanism: canonical match_key folding
    # (research.md §7) is what makes erika count as retained at all.
    cohort = retention_cohort(df, "2023-24", "2024-25")
    assert cohort["retained_count"] >= 1


def test_retention_by_split_groups_by_season_as_own_column_value(df):
    by_gender = retention_by_split(df, "2023-24", "2024-25", "sex")

    assert by_gender == {"Female": pytest.approx(0.5), "Male": pytest.approx(0.0)}


def test_retention_by_split_age_bucket(df):
    by_age = retention_by_split(df, "2023-24", "2024-25", "age_bucket")

    assert by_age == {
        "20-29": pytest.approx(1.0),
        "30-39": pytest.approx(0.0),
        "40-49": pytest.approx(0.0),
    }


def test_retention_by_split_distance_bucket(df):
    by_distance = retention_by_split(df, "2023-24", "2024-25", "distance_bucket")

    assert by_distance == {
        "0-10km": pytest.approx(1.0),
        "10-25km": pytest.approx(0.0),
        "25-50km": pytest.approx(0.0),
    }
