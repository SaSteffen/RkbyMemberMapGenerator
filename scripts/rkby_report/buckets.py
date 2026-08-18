"""Fixed age/distance bracket boundaries (research.md §9). Named constants in
one file so they're trivial to retune later without touching any computation
logic."""

from __future__ import annotations

AGE_BRACKETS = ("<20", "20-29", "30-39", "40-49", "50-59", "60+")
AGE_UNKNOWN = "unknown"

DISTANCE_BRACKETS = ("0-10km", "10-25km", "25-50km", "50-100km", "100km+")
DISTANCE_UNKNOWN = "unknown/not geocoded"

_AGE_BOUNDARIES = (20, 30, 40, 50, 60)
_DISTANCE_BOUNDARIES_KM = (10, 25, 50, 100)


def age_bucket(age: float | None) -> str:
    if age is None:
        return AGE_UNKNOWN
    for boundary, bracket in zip(_AGE_BOUNDARIES, AGE_BRACKETS):
        if age < boundary:
            return bracket
    return AGE_BRACKETS[-1]


def distance_bucket(distance_km: float | None) -> str:
    if distance_km is None:
        return DISTANCE_UNKNOWN
    for boundary, bracket in zip(_DISTANCE_BOUNDARIES_KM, DISTANCE_BRACKETS):
        if distance_km < boundary:
            return bracket
    return DISTANCE_BRACKETS[-1]
