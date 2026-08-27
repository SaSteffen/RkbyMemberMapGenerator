"""Unit tests for `scripts/rkby_pairing/ranking.py` (FR-005/006, research.md
§5/§6, data-model.md § Suggested Pairing): the per-new-rider mentor candidate
sort key (proximity primary, age-gap secondary, same-sex tertiary tie-break)
and the `max_suggestions` cap. Small in-memory synthetic records only -- no
fixtures needed for pure ranking-order behavior."""

import math

from scripts.rkby_pairing.ranking import rank_mentor_candidates

NEW_RIDER = {
    "match_key": "new-rider",
    "latitude": 0.0,
    "longitude": 0.0,
    "birthday": "2000-01-01",
    "sex": "Female",
}


def _candidate(match_key, lat, lon, birthday=None, sex=None):
    return {
        "match_key": match_key,
        "latitude": lat,
        "longitude": lon,
        "birthday": birthday,
        "sex": sex,
    }


# --- Primary factor: distance -----------------------------------------------


def test_closer_distance_always_ranks_first_regardless_of_age_gap_or_sex():
    close_but_worse = _candidate(
        "close", 0.01, 0.0, birthday="1950-01-01", sex="Male"
    )  # ~1.1km, huge age gap, opposite sex
    far_but_better = _candidate(
        "far", 0.5, 0.0, birthday="2000-01-01", sex="Female"
    )  # ~55km, zero age gap, same sex

    pairings = rank_mentor_candidates(
        NEW_RIDER, [close_but_worse, far_but_better], max_suggestions=3
    )

    assert [p.mentor_match_key for p in pairings] == ["close", "far"]


# --- Secondary factor: age gap (only breaks a distance tie) -----------------


def test_smaller_age_gap_breaks_a_distance_tie_when_both_birthdays_known():
    same_spot = 0.02
    older_gap = _candidate(
        "older-gap", same_spot, 0.0, birthday="1950-01-01", sex="Male"
    )
    smaller_gap = _candidate(
        "smaller-gap", same_spot, 0.0, birthday="1998-01-01", sex="Male"
    )

    pairings = rank_mentor_candidates(
        NEW_RIDER, [older_gap, smaller_gap], max_suggestions=3
    )

    assert [p.mentor_match_key for p in pairings] == ["smaller-gap", "older-gap"]


def test_unknown_birthday_sorts_behind_every_pair_with_a_known_gap_but_is_not_excluded():
    same_spot = 0.02
    known_gap = _candidate(
        "known-gap", same_spot, 0.0, birthday="1950-01-01", sex="Male"
    )
    unknown_birthday = _candidate(
        "unknown-birthday", same_spot, 0.0, birthday=None, sex="Male"
    )

    pairings = rank_mentor_candidates(
        NEW_RIDER, [unknown_birthday, known_gap], max_suggestions=3
    )

    assert [p.mentor_match_key for p in pairings] == ["known-gap", "unknown-birthday"]
    unknown_pairing = next(
        p for p in pairings if p.mentor_match_key == "unknown-birthday"
    )
    assert unknown_pairing.age_gap_years is None


# --- Tertiary factor: same-sex tie-break -------------------------------------


def test_same_sex_pairs_rank_ahead_of_an_otherwise_tied_opposite_sex_pair():
    same_spot = 0.02
    same_birthday = "1990-01-01"
    same_sex_candidate = _candidate(
        "same-sex", same_spot, 0.0, birthday=same_birthday, sex="Female"
    )
    opposite_sex_candidate = _candidate(
        "opposite-sex", same_spot, 0.0, birthday=same_birthday, sex="Male"
    )

    pairings = rank_mentor_candidates(
        NEW_RIDER, [opposite_sex_candidate, same_sex_candidate], max_suggestions=3
    )

    assert [p.mentor_match_key for p in pairings] == ["same-sex", "opposite-sex"]


def test_unknown_sex_is_never_penalized_further_than_a_known_opposite_sex_pair():
    same_spot = 0.02
    same_birthday = "1990-01-01"
    same_sex_candidate = _candidate(
        "same-sex", same_spot, 0.0, birthday=same_birthday, sex="Female"
    )
    opposite_sex_candidate = _candidate(
        "opposite-sex", same_spot, 0.0, birthday=same_birthday, sex="Male"
    )
    unknown_sex_candidate = _candidate(
        "unknown-sex", same_spot, 0.0, birthday=same_birthday, sex=None
    )

    pairings = rank_mentor_candidates(
        NEW_RIDER,
        [opposite_sex_candidate, same_sex_candidate, unknown_sex_candidate],
        max_suggestions=3,
    )

    assert pairings[0].mentor_match_key == "same-sex"
    assert {pairings[1].mentor_match_key, pairings[2].mentor_match_key} == {
        "opposite-sex",
        "unknown-sex",
    }


# --- max_suggestions cap ------------------------------------------------------


def test_max_suggestions_caps_the_returned_list_length():
    candidates = [_candidate(f"c{i}", 0.01 * i, 0.0) for i in range(1, 6)]

    pairings = rank_mentor_candidates(NEW_RIDER, candidates, max_suggestions=3)

    assert len(pairings) == 3
    assert [p.rank for p in pairings] == [1, 2, 3]


def test_fewer_eligible_candidates_than_the_cap_returns_all_of_them():
    candidates = [_candidate("only-one", 0.01, 0.0)]

    pairings = rank_mentor_candidates(NEW_RIDER, candidates, max_suggestions=3)

    assert len(pairings) == 1
    assert pairings[0].rank == 1


def test_zero_eligible_candidates_returns_an_empty_list():
    pairings = rank_mentor_candidates(NEW_RIDER, [], max_suggestions=3)

    assert pairings == []


# --- Field content -------------------------------------------------------------


def test_pairing_fields_reflect_new_rider_and_mentor_match_keys_and_distance():
    candidate = _candidate("mentor-a", 0.01, 0.0, birthday="1990-01-01", sex="Male")

    pairings = rank_mentor_candidates(NEW_RIDER, [candidate], max_suggestions=3)

    pairing = pairings[0]
    assert pairing.new_rider_match_key == "new-rider"
    assert pairing.mentor_match_key == "mentor-a"
    assert isinstance(pairing.distance_km, float)
    assert not math.isnan(pairing.distance_km)
