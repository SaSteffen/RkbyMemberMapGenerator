"""Thin matplotlib chart builders, one per view in spec.md (research.md §3).
Every function here only renders an already-computed
`rkby_report.aggregate` result -- it never decides a count or a rate itself,
so it stays deliberately under-tested relative to `aggregate.py`
(research.md §2)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure


def _bar_chart(counts: dict[str, int], title: str, ylabel: str) -> Figure:
    fig, ax = plt.subplots()
    ax.bar(list(counts.keys()), list(counts.values()))
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def role_chart(summary: dict) -> Figure:
    return _bar_chart(
        summary["role_counts"],
        f"Roles — {summary['season_label']}",
        "Members",
    )


def gender_chart(summary: dict) -> Figure:
    return _bar_chart(
        summary["gender_counts"],
        f"Gender — {summary['season_label']}",
        "Members",
    )


def age_bucket_chart(summary: dict) -> Figure:
    return _bar_chart(
        summary["age_bucket_counts"],
        f"Age — {summary['season_label']}",
        "Members",
    )


def distance_bucket_chart(summary: dict) -> Figure:
    return _bar_chart(
        summary["distance_bucket_counts"],
        f"Distance from Hamburg — {summary['season_label']}",
        "Members",
    )


# --- Season-to-season trend charts (User Story 2) ------------------------------


def _not_enough_data_figure(title: str) -> Figure:
    fig, ax = plt.subplots()
    ax.set_title(title)
    ax.text(
        0.5,
        0.5,
        "Not enough data yet — at least two seasons are needed for a trend.",
        ha="center",
        va="center",
        wrap=True,
        transform=ax.transAxes,
    )
    ax.set_axis_off()
    return fig


def _line_chart(trend: pd.DataFrame, columns: list[str], title: str) -> Figure:
    fig, ax = plt.subplots()
    for column in columns:
        ax.plot(trend["season_label"], trend[column], marker="o", label=column)
    ax.set_title(title)
    ax.set_ylabel("Members")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    fig.tight_layout()
    return fig


def member_count_trend_chart(trend: pd.DataFrame) -> Figure:
    if len(trend) < 2:
        return _not_enough_data_figure("Member counts across seasons")
    return _line_chart(
        trend,
        ["total_members", "rider_count", "service_count"],
        "Member counts across seasons",
    )


def _distribution_shift_chart(trend: pd.DataFrame, prefix: str, title: str) -> Figure:
    if len(trend) < 2:
        return _not_enough_data_figure(title)
    columns = [column for column in trend.columns if column.startswith(f"{prefix}_")]
    return _line_chart(trend, columns, title)


def age_distribution_shift_chart(trend: pd.DataFrame) -> Figure:
    return _distribution_shift_chart(trend, "age", "Age distribution across seasons")


def gender_distribution_shift_chart(trend: pd.DataFrame) -> Figure:
    return _distribution_shift_chart(
        trend, "gender", "Gender distribution across seasons"
    )


def distance_distribution_shift_chart(trend: pd.DataFrame) -> Figure:
    return _distribution_shift_chart(
        trend, "distance", "Distance-from-Hamburg distribution across seasons"
    )


# --- Retention charts (User Story 3) -------------------------------------------


def overall_retention_chart(cohort: dict) -> Figure:
    fig, ax = plt.subplots()
    ax.bar(
        ["retained", "departed"],
        [cohort["retained_count"], cohort["departed_count"]],
    )
    ax.set_title(
        f"Retention {cohort['season_a']} → {cohort['season_b']} "
        f"({cohort['retention_rate']:.0%})"
    )
    ax.set_ylabel("Members")
    fig.tight_layout()
    return fig


def retention_by_split_chart(rates: dict[str, float], split_title: str) -> Figure:
    return _bar_chart(rates, f"Retention rate by {split_title}", "Retention rate")
