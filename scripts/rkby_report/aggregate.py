"""Season summaries, season-to-season trend tables, retention rate + splits,
and the FR-017 data-gap list -- every plain aggregation function that turns
`build_member_season_frame()`'s output into what `rkby_report.plots` and the
notebook render (data-model.md)."""

from __future__ import annotations

import pandas as pd


def season_summary(df: pd.DataFrame, season_label: str) -> dict:
    season_df = df[df["season_label"] == season_label]

    return {
        "season_label": season_label,
        "total_members": len(season_df),
        "role_counts": season_df["role"].value_counts().to_dict(),
        "gender_counts": season_df["sex"].value_counts().to_dict(),
        "age_bucket_counts": season_df["age_bucket"].value_counts().to_dict(),
        "distance_bucket_counts": season_df["distance_bucket"].value_counts().to_dict(),
    }


def _missing_fields(row: pd.Series) -> list[str]:
    missing = []
    if row["role"] == "unknown":
        missing.append("role")
    if row["sex"] == "unknown":
        missing.append("sex")
    if row["age_bucket"] == "unknown":
        missing.append("age")
    if row["distance_bucket"] == "unknown/not geocoded":
        missing.append("distance")
    return missing


def data_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """One row per Member-Season Observation missing at least one of
    role/sex/age/distance (FR-017). Never carries name/address/phone/
    birthday -- only `match_key`/`season_label`/`missing_fields`."""
    rows = []
    for _, row in df.iterrows():
        missing = _missing_fields(row)
        if missing:
            rows.append(
                {
                    "match_key": row["match_key"],
                    "season_label": row["season_label"],
                    "missing_fields": missing,
                }
            )

    return pd.DataFrame(rows, columns=["match_key", "season_label", "missing_fields"])


def _pivot_wide(df: pd.DataFrame, column: str, prefix: str) -> pd.DataFrame:
    pivoted = (
        df.groupby(["season_label", column])
        .size()
        .unstack(fill_value=0)
        .add_prefix(f"{prefix}_")
    )
    return pivoted


def season_trend(df: pd.DataFrame) -> pd.DataFrame:
    """One row per discovered season, in chronological order (season labels
    sort correctly as plain strings), with headline counts plus every age
    bucket/gender value/distance bucket pivoted wide (FR-009/FR-010). A
    single-season input still returns one row -- callers detect "not enough
    data yet" from `len(result) < 2` rather than a separate sentinel type."""
    headline = df.groupby("season_label").agg(
        total_members=("match_key", "size"),
        rider_count=("role", lambda roles: (roles == "Rider").sum()),
        service_count=("role", lambda roles: (roles == "Service Crew").sum()),
    )

    age_wide = _pivot_wide(df, "age_bucket", "age")
    gender_wide = _pivot_wide(df, "sex", "gender")
    distance_wide = _pivot_wide(df, "distance_bucket", "distance")

    trend = headline.join([age_wide, gender_wide, distance_wide]).sort_index()
    return trend.reset_index()


def retention_cohort(df: pd.DataFrame, season_a: str, season_b: str) -> dict:
    """Overall retention between one consecutive season pair (FR-011). A
    member counts as retained only if their canonical `match_key` (already
    resolved in `df` by `build_member_season_frame`) has a row in `season_b`
    -- a skipped season in between never counts as retained."""
    keys_a = set(df.loc[df["season_label"] == season_a, "match_key"])
    keys_b = set(df.loc[df["season_label"] == season_b, "match_key"])

    retained_count = len(keys_a & keys_b)
    departed_count = len(keys_a - keys_b)
    total = retained_count + departed_count

    return {
        "season_a": season_a,
        "season_b": season_b,
        "retained_count": retained_count,
        "departed_count": departed_count,
        "retention_rate": retained_count / total if total else None,
    }


def retention_by_split(
    df: pd.DataFrame, season_a: str, season_b: str, split_column: str
) -> dict[str, float]:
    """The same retention rate as `retention_cohort`, grouped by `season_a`'s
    own value of `split_column` (`sex`/`age_bucket`/`distance_bucket`,
    FR-012)."""
    season_a_rows = df[df["season_label"] == season_a]
    keys_b = set(df.loc[df["season_label"] == season_b, "match_key"])

    rates = {}
    for split_value, group in season_a_rows.groupby(split_column):
        keys = set(group["match_key"])
        retained_count = len(keys & keys_b)
        rates[split_value] = retained_count / len(keys)
    return rates
