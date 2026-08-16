"""Minimal Nominatim geocoding client (research.md §3) and the fill-empty-only
cache-write helper that guarantees a hand-corrected latitude/longitude is
never overwritten by a later run (research.md §11, Constitution Principle III)."""

from __future__ import annotations

import time
from collections.abc import Callable

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "RkbyMemberMapGenerator/1.0 (https://github.com/team-rynkeby-hamburg)"
_MIN_SECONDS_BETWEEN_REQUESTS = 1.0

_last_request_monotonic: float | None = None


def _throttle() -> None:
    """Nominatim's usage policy caps requests at 1/second (research.md §3).
    Module-level state is intentional -- the throttle must hold across every
    call made during one run, not just within a single function."""
    global _last_request_monotonic
    if _last_request_monotonic is not None:
        elapsed = time.monotonic() - _last_request_monotonic
        remaining = _MIN_SECONDS_BETWEEN_REQUESTS - elapsed
        if remaining > 0:
            time.sleep(remaining)
    _last_request_monotonic = time.monotonic()


def geocode_address(address: str) -> tuple[float, float] | None:
    """Look up one address via Nominatim. Returns `(latitude, longitude)` on
    a successful match, `None` on no match or any HTTP/network error -- never
    raises (mirrors the scraper's photo/birthday fetch retry-on-failure
    pattern, FR-006)."""
    _throttle()
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        results = response.json()
    except (requests.RequestException, ValueError):
        return None

    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


def geocode_record_if_needed(
    record: dict,
    geocode_fn: Callable[[str], tuple[float, float] | None] = geocode_address,
) -> bool:
    """Fill `record["latitude"]`/`record["longitude"]` in place, once, the
    first time `record["address"]` resolves -- and never again (fill-empty-
    only, research.md §11). Returns whether the record was changed.

    Never called for a record that already has non-null coordinates, whether
    from a prior successful geocode or a human hand-correction: both fields
    already being non-null is exactly what "already resolved" means."""
    if record.get("latitude") is not None or record.get("longitude") is not None:
        return False
    if not record.get("address"):
        return False

    result = geocode_fn(record["address"])
    if result is None:
        return False

    record["latitude"], record["longitude"] = result
    return True
