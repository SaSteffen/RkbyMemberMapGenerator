"""Unit tests for `scripts/rkby_report/geo.py`, `scripts/rkby_report/buckets.py`,
and `scripts/rkby_report/frame.py` (research.md §5, §6, §7, §8, §9; contracts/
member-season-frame.md)."""

import math
import shutil
from pathlib import Path

import pytest

from scripts.rkby_report import buckets
from scripts.rkby_report.frame import (
    build_member_season_frame,
    ensure_reports_dir_and_gitignore,
)
from scripts.rkby_report.geo import HAMBURG_CENTER, haversine_km

STATIC_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "report_seasons"

# --- geo.haversine_km() (research.md §5) --------------------------------------


def test_haversine_km_zero_distance_for_identical_points():
    assert haversine_km(HAMBURG_CENTER, HAMBURG_CENTER) == 0.0


def test_haversine_km_known_distance_hamburg_to_berlin():
    # Hamburg Rathaus to Berlin Reichstag is ~255km great-circle distance.
    berlin = (52.5186, 13.3762)
    distance = haversine_km(HAMBURG_CENTER, berlin)
    assert math.isclose(distance, 255, rel_tol=0.05)


def test_haversine_km_is_symmetric():
    berlin = (52.5186, 13.3762)
    assert math.isclose(
        haversine_km(HAMBURG_CENTER, berlin),
        haversine_km(berlin, HAMBURG_CENTER),
    )


def test_haversine_km_one_degree_latitude_is_about_111km():
    a = (53.0, 10.0)
    b = (54.0, 10.0)
    assert math.isclose(haversine_km(a, b), 111.2, rel_tol=0.01)


# --- buckets.age_bucket() (research.md §9) ------------------------------------


def test_age_bucket_none_is_unknown():
    assert buckets.age_bucket(None) == "unknown"


def test_age_bucket_boundaries():
    assert buckets.age_bucket(0) == "<20"
    assert buckets.age_bucket(19) == "<20"
    assert buckets.age_bucket(20) == "20-29"
    assert buckets.age_bucket(29) == "20-29"
    assert buckets.age_bucket(30) == "30-39"
    assert buckets.age_bucket(39) == "30-39"
    assert buckets.age_bucket(40) == "40-49"
    assert buckets.age_bucket(49) == "40-49"
    assert buckets.age_bucket(50) == "50-59"
    assert buckets.age_bucket(59) == "50-59"
    assert buckets.age_bucket(60) == "60+"
    assert buckets.age_bucket(90) == "60+"


# --- buckets.distance_bucket() (research.md §9) -------------------------------


def test_distance_bucket_none_is_unknown_not_geocoded():
    assert buckets.distance_bucket(None) == "unknown/not geocoded"


def test_distance_bucket_boundaries():
    assert buckets.distance_bucket(0) == "0-10km"
    assert buckets.distance_bucket(9.9) == "0-10km"
    assert buckets.distance_bucket(10) == "10-25km"
    assert buckets.distance_bucket(24.9) == "10-25km"
    assert buckets.distance_bucket(25) == "25-50km"
    assert buckets.distance_bucket(49.9) == "25-50km"
    assert buckets.distance_bucket(50) == "50-100km"
    assert buckets.distance_bucket(99.9) == "50-100km"
    assert buckets.distance_bucket(100) == "100km+"
    assert buckets.distance_bucket(500) == "100km+"


# --- build_member_season_frame() (contracts/member-season-frame.md) ----------


@pytest.fixture
def data_dir(tmp_path):
    """A `RKBY_DATA_DIR`-shaped tree built from the static T007 fixtures,
    copied fresh per test so a test can't observe another test's mutations
    (the contract also asserts nothing is ever written back, see below)."""
    shutil.copytree(STATIC_FIXTURES_DIR, tmp_path / "seasons")
    return tmp_path


def _row(df, season_label, match_key):
    matches = df[(df["season_label"] == season_label) & (df["match_key"] == match_key)]
    assert len(matches) == 1, (
        f"expected exactly one row for {match_key!r}/{season_label!r}, "
        f"found {len(matches)}"
    )
    return matches.iloc[0]


def _all_fixture_files(data_dir):
    return {
        path: path.read_bytes()
        for path in sorted((data_dir / "seasons").glob("*/applicants/*.yaml"))
    }


def test_frame_row_count_reflects_only_excluded_ignore_eligibility_filter(data_dir):
    df = build_member_season_frame(data_dir)

    # 2023-24: erika-mustermann, departed-member, skip-return-member eligible;
    # excluded-early/ignored-early dropped.
    # 2024-25: 10 eligible records (every bucket-coverage member); excluded-juliet/
    # ignored-kilo dropped.
    # 2025-26: skip-return-member, rider-alpha, newcomer-lima eligible.
    assert len(df) == 3 + 10 + 3


def test_frame_never_drops_a_row_for_missing_role_sex_birthday_or_coords(data_dir):
    df = build_member_season_frame(data_dir)

    # Each of these members is missing exactly one field, yet must still be a
    # row -- data-model.md Guarantee 1.
    assert (
        len(df[(df["season_label"] == "2024-25") & (df["match_key"] == "no-role-golf")])
        == 1
    )
    assert (
        len(df[(df["season_label"] == "2024-25") & (df["match_key"] == "no-sex-hotel")])
        == 1
    )
    assert (
        len(
            df[
                (df["season_label"] == "2024-25")
                & (df["match_key"] == "no-birthday-india")
            ]
        )
        == 1
    )
    assert (
        len(
            df[
                (df["season_label"] == "2024-25")
                & (df["match_key"] == "veteran-foxtrot")
            ]
        )
        == 1
    )


def test_frame_uses_unknown_sentinel_for_missing_role_and_sex(data_dir):
    df = build_member_season_frame(data_dir)

    assert _row(df, "2024-25", "no-role-golf")["role"] == "unknown"
    assert _row(df, "2024-25", "no-sex-hotel")["sex"] == "unknown"


def test_frame_keeps_raw_role_and_sex_verbatim_when_present(data_dir):
    df = build_member_season_frame(data_dir)

    row = _row(df, "2024-25", "coach-delta")
    assert row["role"] == "Coach"  # unrecognized role kept verbatim (FR-003)
    assert row["sex"] == "Female"


def test_frame_age_at_season_and_age_bucket_use_the_season_reference_date(data_dir):
    df = build_member_season_frame(data_dir)

    # Season "2024-25" -> reference date 2025-07-01 (research.md §6).
    assert _row(df, "2024-25", "rider-alpha")["age_at_season"] == 15
    assert _row(df, "2024-25", "rider-alpha")["age_bucket"] == "<20"
    assert _row(df, "2024-25", "service-bravo")["age_bucket"] == "20-29"
    assert _row(df, "2024-25", "supporter-charlie")["age_bucket"] == "30-39"
    assert _row(df, "2024-25", "coach-delta")["age_bucket"] == "40-49"
    assert _row(df, "2024-25", "elder-echo")["age_bucket"] == "50-59"
    assert _row(df, "2024-25", "veteran-foxtrot")["age_bucket"] == "60+"


def test_frame_missing_birthday_is_null_age_and_unknown_bucket(data_dir):
    df = build_member_season_frame(data_dir)

    row = _row(df, "2024-25", "no-birthday-india")
    assert row["age_at_season"] is None or math.isnan(row["age_at_season"])
    assert row["age_bucket"] == "unknown"


def test_frame_distance_km_and_bucket_derived_from_haversine_to_hamburg_center(
    data_dir,
):
    df = build_member_season_frame(data_dir)

    row = _row(df, "2024-25", "rider-alpha")
    expected = haversine_km(HAMBURG_CENTER, (53.5956, 9.9930))
    assert math.isclose(row["distance_km"], expected)
    assert row["distance_bucket"] == "0-10km"

    assert _row(df, "2024-25", "service-bravo")["distance_bucket"] == "10-25km"
    assert _row(df, "2024-25", "supporter-charlie")["distance_bucket"] == "25-50km"
    assert _row(df, "2024-25", "coach-delta")["distance_bucket"] == "50-100km"
    assert _row(df, "2024-25", "elder-echo")["distance_bucket"] == "100km+"


def test_frame_missing_coords_is_null_distance_and_unknown_bucket(data_dir):
    df = build_member_season_frame(data_dir)

    row = _row(df, "2024-25", "veteran-foxtrot")
    assert row["distance_km"] is None or math.isnan(row["distance_km"])
    assert row["distance_bucket"] == "unknown/not geocoded"


def test_frame_excluded_and_ignored_records_never_appear(data_dir):
    df = build_member_season_frame(data_dir)

    all_keys = set(df["match_key"])
    assert "excluded-early" not in all_keys
    assert "ignored-early" not in all_keys
    assert "excluded-juliet" not in all_keys
    assert "ignored-kilo" not in all_keys


def test_frame_match_key_is_canonical_across_a_recorded_alias(data_dir):
    df = build_member_season_frame(data_dir)

    # erika-mustermann's 2023-24 record is folded into erika-schmidt's
    # canonical identity (research.md §7) -- "erika-mustermann" must not
    # appear as its own match_key anywhere in the frame.
    assert "erika-mustermann" not in set(df["match_key"])
    row = _row(df, "2023-24", "erika-schmidt")
    assert row["role"] == "Rider"


def test_frame_retained_next_season_true_for_alias_retained_member(data_dir):
    df = build_member_season_frame(data_dir)

    assert _row(df, "2023-24", "erika-schmidt")["retained_next_season"] is True


def test_frame_retained_next_season_false_for_departed_member(data_dir):
    df = build_member_season_frame(data_dir)

    assert _row(df, "2023-24", "departed-member")["retained_next_season"] is False


def test_frame_retained_next_season_false_across_a_skipped_season(data_dir):
    df = build_member_season_frame(data_dir)

    # skip-return-member is absent from the immediately next season
    # ("2024-25"), so their 2023-24 row must be False, not True, even though
    # they return in "2025-26" (spec Edge Cases).
    assert _row(df, "2023-24", "skip-return-member")["retained_next_season"] is False


def test_frame_retained_next_season_is_none_for_the_last_discovered_season(data_dir):
    df = build_member_season_frame(data_dir)

    last_season_rows = df[df["season_label"] == "2025-26"]
    assert last_season_rows["retained_next_season"].isna().all()


def test_frame_never_writes_to_any_yaml_file(data_dir):
    before = _all_fixture_files(data_dir)

    build_member_season_frame(data_dir)

    after = _all_fixture_files(data_dir)
    assert before == after


# --- ensure_reports_dir_and_gitignore() (research.md §4, §10) -----------------


def test_ensure_reports_dir_and_gitignore_creates_reports_dir(tmp_path):
    ensure_reports_dir_and_gitignore(tmp_path)

    assert (tmp_path / "reports").is_dir()


def test_ensure_reports_dir_and_gitignore_creates_gitignore_when_absent(tmp_path):
    ensure_reports_dir_and_gitignore(tmp_path)

    gitignore = (tmp_path / ".gitignore").read_text()
    assert "reports/" in gitignore.splitlines()


def test_ensure_reports_dir_and_gitignore_running_twice_never_duplicates_entry(
    tmp_path,
):
    ensure_reports_dir_and_gitignore(tmp_path)
    ensure_reports_dir_and_gitignore(tmp_path)

    lines = (tmp_path / ".gitignore").read_text().splitlines()
    assert lines.count("reports/") == 1


def test_ensure_reports_dir_and_gitignore_leaves_existing_entries_untouched(tmp_path):
    (tmp_path / ".gitignore").write_text("maps/\n.tile_cache/\n")

    ensure_reports_dir_and_gitignore(tmp_path)

    lines = (tmp_path / ".gitignore").read_text().splitlines()
    assert lines == ["maps/", ".tile_cache/", "reports/"]
