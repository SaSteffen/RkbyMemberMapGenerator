"""Smoke tests for `scripts/rkby_report/plots.py`'s chart-builder functions
(research.md §2): each must return a populated matplotlib Figure without
raising, given a `season_summary()`-shaped input. Numerical correctness is
already covered by `test_rkby_report_aggregate.py` -- these only check the
render step doesn't blow up."""

import matplotlib

matplotlib.use("Agg")

import pandas as pd
from matplotlib.figure import Figure

from scripts.rkby_report import plots

SUMMARY = {
    "season_label": "2024-25",
    "total_members": 10,
    "role_counts": {"Rider": 4, "Service Crew": 3, "Supporter": 1, "unknown": 2},
    "gender_counts": {"Female": 5, "Male": 4, "unknown": 1},
    "age_bucket_counts": {
        "<20": 1,
        "20-29": 2,
        "30-39": 2,
        "40-49": 2,
        "50-59": 1,
        "60+": 1,
        "unknown": 1,
    },
    "distance_bucket_counts": {
        "0-10km": 3,
        "10-25km": 2,
        "25-50km": 2,
        "50-100km": 1,
        "100km+": 1,
        "unknown/not geocoded": 1,
    },
}


def _assert_populated_figure(fig):
    assert isinstance(fig, Figure)
    assert len(fig.axes) > 0
    ax = fig.axes[0]
    assert len(ax.patches) > 0 or len(ax.lines) > 0 or len(ax.containers) > 0


def test_role_chart_returns_a_populated_figure():
    _assert_populated_figure(plots.role_chart(SUMMARY))


def test_gender_chart_returns_a_populated_figure():
    _assert_populated_figure(plots.gender_chart(SUMMARY))


def test_age_bucket_chart_returns_a_populated_figure():
    _assert_populated_figure(plots.age_bucket_chart(SUMMARY))


def test_distance_bucket_chart_returns_a_populated_figure():
    _assert_populated_figure(plots.distance_bucket_chart(SUMMARY))


# --- trend charts (season_trend()-shaped input) --------------------------------

TREND = pd.DataFrame(
    {
        "season_label": ["2023-24", "2024-25", "2025-26"],
        "total_members": [3, 10, 3],
        "rider_count": [1, 4, 1],
        "service_count": [1, 3, 1],
        "age_<20": [0, 1, 1],
        "age_20-29": [1, 2, 0],
        "age_30-39": [1, 2, 1],
        "age_40-49": [1, 2, 1],
        "age_50-59": [0, 1, 0],
        "age_60+": [0, 1, 0],
        "age_unknown": [0, 1, 0],
        "gender_Female": [2, 5, 2],
        "gender_Male": [1, 4, 1],
        "gender_unknown": [0, 1, 0],
        "distance_0-10km": [1, 3, 1],
        "distance_10-25km": [1, 2, 1],
        "distance_25-50km": [1, 2, 1],
        "distance_50-100km": [0, 1, 0],
        "distance_100km+": [0, 1, 0],
        "distance_unknown/not geocoded": [0, 1, 0],
    }
)
SINGLE_SEASON_TREND = TREND.iloc[[0]].reset_index(drop=True)


def test_member_count_trend_chart_returns_a_populated_figure():
    _assert_populated_figure(plots.member_count_trend_chart(TREND))


def test_age_distribution_shift_chart_returns_a_populated_figure():
    _assert_populated_figure(plots.age_distribution_shift_chart(TREND))


def test_gender_distribution_shift_chart_returns_a_populated_figure():
    _assert_populated_figure(plots.gender_distribution_shift_chart(TREND))


def test_distance_distribution_shift_chart_returns_a_populated_figure():
    _assert_populated_figure(plots.distance_distribution_shift_chart(TREND))


def test_member_count_trend_chart_renders_not_enough_data_placeholder():
    fig = plots.member_count_trend_chart(SINGLE_SEASON_TREND)
    assert isinstance(fig, Figure)
    ax = fig.axes[0]
    texts = " ".join(text.get_text().lower() for text in ax.texts)
    assert "not enough data" in texts


def test_age_distribution_shift_chart_renders_not_enough_data_placeholder():
    fig = plots.age_distribution_shift_chart(SINGLE_SEASON_TREND)
    ax = fig.axes[0]
    texts = " ".join(text.get_text().lower() for text in ax.texts)
    assert "not enough data" in texts


# --- retention charts (retention_cohort()/retention_by_split()-shaped input) --

COHORT = {
    "season_a": "2023-24",
    "season_b": "2024-25",
    "retained_count": 1,
    "departed_count": 2,
    "retention_rate": 1 / 3,
}
RETENTION_BY_GENDER = {"Female": 0.5, "Male": 0.0}
RETENTION_BY_AGE_BUCKET = {"20-29": 1.0, "30-39": 0.0, "40-49": 0.0}
RETENTION_BY_DISTANCE_BUCKET = {"0-10km": 1.0, "10-25km": 0.0, "25-50km": 0.0}


def test_overall_retention_chart_returns_a_populated_figure():
    _assert_populated_figure(plots.overall_retention_chart(COHORT))


def test_retention_by_split_chart_returns_a_populated_figure_for_gender():
    _assert_populated_figure(
        plots.retention_by_split_chart(RETENTION_BY_GENDER, "Gender")
    )


def test_retention_by_split_chart_returns_a_populated_figure_for_age_bucket():
    _assert_populated_figure(
        plots.retention_by_split_chart(RETENTION_BY_AGE_BUCKET, "Age bracket")
    )


def test_retention_by_split_chart_returns_a_populated_figure_for_distance_bucket():
    _assert_populated_figure(
        plots.retention_by_split_chart(RETENTION_BY_DISTANCE_BUCKET, "Distance bracket")
    )
