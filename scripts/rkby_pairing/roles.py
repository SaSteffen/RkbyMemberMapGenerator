"""Recognized-role classification (research.md §4, data-model.md § Role
Classification), reusing `rkby_maps.rendering.ROLE_COLORS`'s keys as the one
source of truth for recognized role spellings, rather than a second,
driftable list of the same strings."""

from __future__ import annotations

from typing import Literal

from scripts.rkby_maps.rendering import ROLE_COLORS

_ROLE_SLUGS: dict[str, Literal["rider", "service_crew", "supporter"]] = {
    "rider": "rider",
    "service crew": "service_crew",
    "supporter": "supporter",
}
assert set(_ROLE_SLUGS) == set(ROLE_COLORS)


def classify_role(
    raw_role: str | None,
) -> Literal["rider", "service_crew", "supporter"] | None:
    """`None` means unrecognized or blank -- such a record's `role` never
    counts as Rider/Service Crew/Supporter evidence for any purpose in this
    feature (new rider, mentor candidate, or historical "has ridden"
    evidence)."""
    if raw_role is None:
        return None
    normalized = raw_role.strip().lower()
    return _ROLE_SLUGS.get(normalized)
