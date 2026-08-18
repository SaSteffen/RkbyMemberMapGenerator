"""Thin matplotlib chart builders, one per view in spec.md (research.md §3).
Every function here only renders an already-computed
`rkby_report.aggregate` result -- it never decides a count or a rate itself,
so it stays deliberately under-tested relative to `aggregate.py`
(research.md §2)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from scripts.rkby_report.buckets import (
    AGE_BRACKETS,
    AGE_UNKNOWN,
    DISTANCE_BRACKETS,
    DISTANCE_UNKNOWN,
)

# Ordinal splits (bucket order carries meaning) get a single light->dark hue so
# the stack reads low-to-high; nominal splits (e.g. gender) get distinct hues.
# Both ramps are pulled from the dataviz skill's validated default palette
# rather than matplotlib's default cycle. "Unknown"/"not geocoded" is always
# the same muted gray so missing data never competes visually with real data.
_BUCKET_ORDER = {
    "age": (*AGE_BRACKETS, AGE_UNKNOWN),
    "distance": (*DISTANCE_BRACKETS, DISTANCE_UNKNOWN),
}
_ORDINAL_RAMP = ("#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b")
_CATEGORICAL = (
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#4a3aa7",
    "#e34948",
)
_UNKNOWN_COLOR = "#898781"
_UNKNOWN_LABELS = {"unknown", "unknown/not geocoded"}


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


def _bucket_columns(trend: pd.DataFrame, prefix: str) -> list[str]:
    present = {
        column[len(prefix) + 1 :]
        for column in trend.columns
        if column.startswith(f"{prefix}_")
    }
    order = _BUCKET_ORDER.get(prefix)
    labels = (
        [label for label in order if label in present]
        if order is not None
        else sorted(present, key=lambda label: (label in _UNKNOWN_LABELS, label))
    )
    return [f"{prefix}_{label}" for label in labels]


def _bucket_colors(prefix: str, columns: list[str]) -> list[str]:
    ordinal = prefix in _BUCKET_ORDER
    colors = []
    slot = 0
    for column in columns:
        label = column[len(prefix) + 1 :]
        if label in _UNKNOWN_LABELS:
            colors.append(_UNKNOWN_COLOR)
        elif ordinal:
            colors.append(_ORDINAL_RAMP[slot])
            slot += 1
        else:
            colors.append(_CATEGORICAL[slot % len(_CATEGORICAL)])
            slot += 1
    return colors


def _stacked_bar_chart(trend: pd.DataFrame, prefix: str, title: str) -> Figure:
    columns = _bucket_columns(trend, prefix)
    colors = _bucket_colors(prefix, columns)

    fig, ax = plt.subplots()
    bottoms = pd.Series(0, index=trend.index, dtype=float)
    for column, color in zip(columns, colors):
        label = column[len(prefix) + 1 :]
        ax.bar(
            trend["season_label"],
            trend[column],
            bottom=bottoms,
            label=label,
            color=color,
        )
        bottoms = bottoms + trend[column]
    ax.set_title(title)
    ax.set_ylabel("Members")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    fig.tight_layout()
    return fig


def _distribution_shift_chart(trend: pd.DataFrame, prefix: str, title: str) -> Figure:
    if len(trend) < 2:
        return _not_enough_data_figure(title)
    return _stacked_bar_chart(trend, prefix, title)


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
