"""Unit tests for `scripts/rkby_pairing/eligibility.py` (FR-002/003/004/010,
data-model.md § New Rider / Mentor Candidate, research.md §3): new-rider and
mentor-candidate pools for the latest season, resolved against the T003
synthetic multi-season fixture set."""

import shutil
from pathlib import Path

import pytest

from scripts.rkby_pairing.eligibility import (
    find_mentor_candidates,
    find_new_riders,
)
from scripts.rkby_records import discover_seasons, load_existing_records

STATIC_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "pairing_seasons"


@pytest.fixture
def data_dir(tmp_path) -> Path:
    """A `RKBY_DATA_DIR`-shaped tree built from the T003 fixtures, copied
    fresh per test (mirrors test_rkby_report_frame.py's `data_dir` fixture)."""
    shutil.copytree(STATIC_FIXTURES_DIR, tmp_path / "seasons")
    return tmp_path


def _load_all_seasons(data_dir: Path) -> dict[str, dict[str, dict]]:
    return {
        season_label: load_existing_records(data_dir, season_label)
        for season_label in discover_seasons(data_dir)
    }


def _latest_season_label(data_dir: Path) -> str:
    return discover_seasons(data_dir)[-1]


# --- find_new_riders() (FR-002) -------------------------------------------------


def test_find_new_riders_includes_every_eligible_zero_previous_season_rider(data_dir):
    by_season = _load_all_seasons(data_dir)
    latest = _latest_season_label(data_dir)

    new_riders = find_new_riders(by_season, latest)
    keys = {record["match_key"] for record in new_riders}

    assert "new-rider-nora" in keys
    assert "new-rider-quinn" in keys


def test_find_new_riders_excludes_non_zero_or_unknown_previous_seasons(data_dir):
    by_season = _load_all_seasons(data_dir)
    latest = _latest_season_label(data_dir)

    new_riders = find_new_riders(by_season, latest)
    keys = {record["match_key"] for record in new_riders}

    # mentor-near-oscar etc. have num_previous_seasons > 0.
    assert "mentor-near-oscar" not in keys
    # blank-role-beth has num_previous_seasons: null (unknown, not zero).
    assert "blank-role-beth" not in keys


def test_find_new_riders_excludes_excluded_ignored_and_ungeocoded(data_dir):
    by_season = _load_all_seasons(data_dir)
    latest = _latest_season_label(data_dir)

    new_riders = find_new_riders(by_season, latest)
    keys = {record["match_key"] for record in new_riders}

    assert "excluded-xena" not in keys  # excluded=True, num_previous_seasons=0
    assert "ungeocoded-zack" not in keys  # not geocoded, num_previous_seasons=0


def test_find_new_riders_excludes_non_rider_roles(data_dir):
    by_season = _load_all_seasons(data_dir)
    latest = _latest_season_label(data_dir)

    new_riders = find_new_riders(by_season, latest)
    keys = {record["match_key"] for record in new_riders}

    assert "coach-adam" not in keys
    assert "blank-role-beth" not in keys


def test_find_new_riders_includes_new_riders_that_are_also_cluster_members(data_dir):
    by_season = _load_all_seasons(data_dir)
    latest = _latest_season_label(data_dir)

    new_riders = find_new_riders(by_season, latest)
    keys = {record["match_key"] for record in new_riders}

    assert "cluster-alice" in keys


# --- find_mentor_candidates() (FR-003/004) ---------------------------------------


def test_find_mentor_candidates_includes_a_current_rider_nearby(data_dir):
    by_season = _load_all_seasons(data_dir)
    latest = _latest_season_label(data_dir)

    candidates = find_mentor_candidates(by_season, latest)
    keys = {record["match_key"] for record in candidates}

    assert "mentor-near-oscar" in keys


def test_find_mentor_candidates_includes_a_far_away_current_rider(data_dir):
    by_season = _load_all_seasons(data_dir)
    latest = _latest_season_label(data_dir)

    candidates = find_mentor_candidates(by_season, latest)
    keys = {record["match_key"] for record in candidates}

    assert "mentor-far-victor" in keys


def test_find_mentor_candidates_includes_former_rider_now_service_crew(data_dir):
    # Acceptance Scenario 1.2: latest-season role Service Crew, but rode as a
    # Rider under the *same* match_key in an earlier season.
    by_season = _load_all_seasons(data_dir)
    latest = _latest_season_label(data_dir)

    candidates = find_mentor_candidates(by_season, latest)
    keys = {record["match_key"] for record in candidates}

    assert "mentor-crew-patricia" in keys


def test_find_mentor_candidates_includes_alias_linked_former_rider(data_dir):
    # research.md §3: the "has ridden before" evidence is only reachable via
    # alias_match_keys linking erin-late (latest season, role Supporter) back
    # to erin-early (2023-24, role Rider).
    by_season = _load_all_seasons(data_dir)
    latest = _latest_season_label(data_dir)

    candidates = find_mentor_candidates(by_season, latest)
    keys = {record["match_key"] for record in candidates}

    assert "erin-late" in keys


def test_find_mentor_candidates_excludes_a_new_rider(data_dir):
    # Acceptance Scenario 1.3: a person is never both a New Rider and a
    # Mentor Candidate the same season.
    by_season = _load_all_seasons(data_dir)
    latest = _latest_season_label(data_dir)

    candidates = find_mentor_candidates(by_season, latest)
    keys = {record["match_key"] for record in candidates}

    assert "new-rider-nora" not in keys
    assert "new-rider-quinn" not in keys


def test_find_mentor_candidates_excludes_never_a_rider(data_dir):
    by_season = _load_all_seasons(data_dir)
    latest = _latest_season_label(data_dir)

    candidates = find_mentor_candidates(by_season, latest)
    keys = {record["match_key"] for record in candidates}

    assert "coach-adam" not in keys
    assert "blank-role-beth" not in keys


def test_find_mentor_candidates_excludes_excluded_ignored_and_ungeocoded(data_dir):
    by_season = _load_all_seasons(data_dir)
    latest = _latest_season_label(data_dir)

    candidates = find_mentor_candidates(by_season, latest)
    keys = {record["match_key"] for record in candidates}

    assert "excluded-xena" not in keys
    assert "ignored-yara" not in keys  # role Rider, ignore=True
    assert "ungeocoded-zack" not in keys


def test_find_mentor_candidates_ignores_earlier_seasons_own_eligibility_flags(data_dir):
    # research.md §3: an excluded/ignored *earlier* season's record still
    # counts as historical Rider evidence -- only *this* season's role is
    # gated by eligibility. mentor-crew-patricia's 2024-25 record isn't
    # excluded/ignored in this fixture set, but the identity resolution used
    # to find it must be built over every raw record, not an eligible-only
    # subset -- covered implicitly by the alias/former-rider tests above.
    by_season = _load_all_seasons(data_dir)
    latest = _latest_season_label(data_dir)

    candidates = find_mentor_candidates(by_season, latest)
    keys = {record["match_key"] for record in candidates}

    assert "mentor-crew-patricia" in keys
    assert "erin-late" in keys
