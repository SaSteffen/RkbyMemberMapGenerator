"""Great-circle distance from a fixed Hamburg city-center reference point
(research.md §5). In-house haversine implementation -- no geo dependency,
mirroring 002's precedent of implementing its own projection math."""

from __future__ import annotations

import math

# Hamburg Rathaus (city hall) -- the conventional "city center" landmark.
HAMBURG_CENTER = (53.5507, 9.9930)

_EARTH_RADIUS_KM = 6371.0


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(haversine))
