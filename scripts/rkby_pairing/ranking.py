"""Per-new-rider mentor candidate ranking (FR-005/006, research.md §5/§6,
data-model.md § Suggested Pairing): proximity primary, age-gap secondary,
same-sex tertiary tie-break."""

from __future__ import annotations

import math
from dataclasses import dataclass

from scripts.rkby_report.geo import haversine_km


@dataclass(frozen=True)
class SuggestedPairing:
    new_rider_match_key: str
    mentor_match_key: str
    rank: int
    distance_km: float
    age_gap_years: int | None
    same_sex: bool | None


def _age_gap_years(a_birthday: str | None, b_birthday: str | None) -> int | None:
    if a_birthday is None or b_birthday is None:
        return None
    return abs(int(a_birthday[:4]) - int(b_birthday[:4]))


def _same_sex(a_sex: str | None, b_sex: str | None) -> bool | None:
    if a_sex is None or b_sex is None:
        return None
    return a_sex.strip().lower() == b_sex.strip().lower()


def rank_mentor_candidates(
    new_rider: dict, candidates: list[dict], max_suggestions: int
) -> list[SuggestedPairing]:
    """Sort every candidate ascending by `(distance_km, age_gap_years or
    math.inf, 0 if same_sex else 1)` and keep the top `max_suggestions`."""
    new_position = (new_rider["latitude"], new_rider["longitude"])

    scored = []
    for candidate in candidates:
        candidate_position = (candidate["latitude"], candidate["longitude"])
        distance_km = haversine_km(new_position, candidate_position)
        age_gap = _age_gap_years(new_rider.get("birthday"), candidate.get("birthday"))
        same_sex = _same_sex(new_rider.get("sex"), candidate.get("sex"))
        sort_key = (
            distance_km,
            age_gap if age_gap is not None else math.inf,
            0 if same_sex else 1,
        )
        scored.append((sort_key, candidate, distance_km, age_gap, same_sex))

    scored.sort(key=lambda item: item[0])

    return [
        SuggestedPairing(
            new_rider_match_key=new_rider["match_key"],
            mentor_match_key=candidate["match_key"],
            rank=rank,
            distance_km=distance_km,
            age_gap_years=age_gap,
            same_sex=same_sex,
        )
        for rank, (_sort_key, candidate, distance_km, age_gap, same_sex) in enumerate(
            scored[:max_suggestions], start=1
        )
    ]
