"""Unit tests for `scripts/rkby_pairing/clusters.py` (FR-007, data-model.md §
Training Cluster, Acceptance Scenarios 2.1-2.3): training-cluster detection
over the latest season's Rider-role pool."""

import shutil
from pathlib import Path

import pytest

from scripts.rkby_pairing.clusters import find_training_clusters
from scripts.rkby_records import load_existing_records

STATIC_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "pairing_seasons"


@pytest.fixture
def latest_records(tmp_path) -> dict[str, dict]:
    shutil.copytree(STATIC_FIXTURES_DIR, tmp_path / "seasons")
    return load_existing_records(tmp_path, "2025-26")


# --- Against the T003 fixtures --------------------------------------------------


def test_three_or_more_nearby_current_season_riders_form_one_cluster(latest_records):
    clusters = find_training_clusters(latest_records, cluster_radius_km=5)

    matching = [
        c
        for c in clusters
        if {"cluster-alice", "cluster-bob", "cluster-carol"} <= set(c.member_match_keys)
    ]
    assert len(matching) == 1


def test_non_rider_member_at_the_same_location_is_never_a_cluster_member(
    latest_records,
):
    clusters = find_training_clusters(latest_records, cluster_radius_km=5)

    for cluster in clusters:
        assert "cluster-crew-dave" not in cluster.member_match_keys


def test_new_riders_and_experienced_riders_both_count_toward_cluster_membership(
    latest_records,
):
    # cluster-alice has num_previous_seasons=0 (a New Rider), cluster-bob and
    # cluster-carol have non-zero previous seasons -- mixed experience levels
    # all still count as pool members (Acceptance Scenario 2.1).
    clusters = find_training_clusters(latest_records, cluster_radius_km=5)

    matching = [c for c in clusters if "cluster-alice" in c.member_match_keys]
    assert len(matching) == 1
    assert "cluster-bob" in matching[0].member_match_keys
    assert "cluster-carol" in matching[0].member_match_keys


def test_cluster_centroid_is_the_mean_position_of_its_members(latest_records):
    clusters = find_training_clusters(latest_records, cluster_radius_km=5)

    matching = next(c for c in clusters if "cluster-alice" in c.member_match_keys)
    expected_lat = sum(
        latest_records[key]["latitude"] for key in matching.member_match_keys
    ) / len(matching.member_match_keys)
    assert matching.centroid[0] == pytest.approx(expected_lat)


# --- Small in-memory synthetic records for radius-sensitive edge cases --------


def _rider(match_key, lat, lon, role="Rider", **overrides):
    record = {
        "match_key": match_key,
        "first_name": match_key,
        "last_name": "Test",
        "role": role,
        "excluded": False,
        "ignore": False,
        "latitude": lat,
        "longitude": lon,
    }
    record.update(overrides)
    return record


def test_two_nearby_riders_with_no_third_nearby_form_no_cluster():
    records = {
        "a": _rider("a", 53.55, 9.99),
        "b": _rider("b", 53.5501, 9.9901),  # a few meters from a
        "c": _rider("c", 50.0, 10.0),  # far away, not part of any group
    }

    clusters = find_training_clusters(records, cluster_radius_km=5)

    assert clusters == []


def test_cluster_radius_km_changes_which_groups_qualify():
    # a-b ~1km apart, c ~3km from b -- forms one trio only once the radius is
    # wide enough to bridge every pairwise link the connected-component needs.
    records = {
        "a": _rider("a", 53.550, 9.990),
        "b": _rider("b", 53.559, 9.990),
        "c": _rider("c", 53.586, 9.990),
    }

    narrow = find_training_clusters(records, cluster_radius_km=2)
    wide = find_training_clusters(records, cluster_radius_km=10)

    assert narrow == []
    assert len(wide) == 1
    assert set(wide[0].member_match_keys) == {"a", "b", "c"}


def test_excluded_ignored_and_ungeocoded_riders_are_never_cluster_nodes():
    records = {
        "a": _rider("a", 53.55, 9.99),
        "b": _rider("b", 53.5501, 9.9901),
        "excluded-c": _rider("excluded-c", 53.5502, 9.9902, excluded=True),
        "ignored-d": _rider("ignored-d", 53.5503, 9.9903, ignore=True),
        "ungeocoded-e": _rider("ungeocoded-e", None, None),
    }
    records["ungeocoded-e"]["latitude"] = None
    records["ungeocoded-e"]["longitude"] = None

    clusters = find_training_clusters(records, cluster_radius_km=5)

    assert clusters == []  # only "a"/"b" would be eligible -- size 2, below the cap
