"""Overlap-graph/connected-components clustering (research.md §4), the FR-014
same-exact-address-pair short-circuit, and detail-map filename slug
derivation (research.md §9)."""

from __future__ import annotations

import math
import re

from scripts.rkby_records import normalize_name


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def find_overlap_groups(
    positions: dict[str, tuple[float, float]],
    radius: float,
) -> list[list[str]]:
    """Connected components of members whose pixel distance is within the
    combined marker radius (research.md §4: "distance is less than the sum
    of their marker radii" -- both markers share `radius` here, so the
    combined radius is `2 * radius`). Solo members with no overlapping
    partner are left out of the result entirely."""
    keys = list(positions.keys())
    parent = {key: key for key in keys}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    threshold = 2 * radius
    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            if _distance(positions[a], positions[b]) <= threshold:
                union(a, b)

    components: dict[str, list[str]] = {}
    for key in keys:
        components.setdefault(find(key), []).append(key)

    return [members for members in components.values() if len(members) >= 2]


def is_fr014_exception(group: list[str], addresses: dict[str, str | None]) -> bool:
    """FR-014: a group is exempt from ever getting its own detail map only
    when it's exactly two members sharing one identical address string --
    zooming in further could never visually separate them."""
    if len(group) != 2:
        return False
    address_a, address_b = addresses[group[0]], addresses[group[1]]
    if address_a is None or address_b is None:
        return False
    return address_a == address_b


def detail_map_slug(address: str, existing_slugs: set[str]) -> str:
    """Extract the city/town token from a `"<street>, <postal-code> <city>,
    <country>"` address, normalize it (diacritics/case), and append a
    collision suffix in encounter order if it's already in `existing_slugs`
    (research.md §9)."""
    parts = [part.strip() for part in address.split(",")]
    city_part = parts[-2] if len(parts) >= 2 else parts[-1]
    city = re.sub(r"^\d+\s*", "", city_part).strip()
    slug = normalize_name(city)

    if slug not in existing_slugs:
        return slug
    suffix = 2
    while f"{slug}_{suffix}" in existing_slugs:
        suffix += 1
    return f"{slug}_{suffix}"
