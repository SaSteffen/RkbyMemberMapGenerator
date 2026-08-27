"""New-rider / mentor-candidate pools for the latest season (FR-002/003/004/
010, data-model.md § New Rider / Mentor Candidate, research.md §3)."""

from __future__ import annotations

from scripts.rkby_pairing.roles import classify_role
from scripts.rkby_records import canonical_match_keys

RecordsBySeason = dict[str, dict[str, dict]]


def is_eligible_base(record: dict) -> bool:
    """Shared base eligibility (excluded/ignore/geocoded), reused unchanged
    by `clusters.py` (US2): not excluded, not opted-out, and successfully
    geocoded by a prior `generate_member_maps.py` run."""
    return (
        record.get("excluded") is not True
        and record.get("ignore") is not True
        and record.get("latitude") is not None
        and record.get("longitude") is not None
    )


def find_new_riders(by_season: RecordsBySeason, latest_season_label: str) -> list[dict]:
    """FR-002: latest-season role Rider, exactly zero previous seasons (not
    `None`), and base-eligible."""
    latest_records = by_season.get(latest_season_label, {})
    return [
        record
        for record in latest_records.values()
        if classify_role(record.get("role")) == "rider"
        and record.get("num_previous_seasons") == 0
        and is_eligible_base(record)
    ]


def _rider_history_canonical_keys(
    by_season: RecordsBySeason, canonical: dict[str, str]
) -> set[str]:
    """Canonical identities with at least one raw record, in any season,
    whose role classifies as Rider -- built over *every* record, not just
    eligible ones (research.md §3): an earlier season's excluded/ignored
    record still counts as historical "has ridden" evidence."""
    keys: set[str] = set()
    for records in by_season.values():
        for record in records.values():
            if classify_role(record.get("role")) == "rider":
                keys.add(canonical.get(record["match_key"], record["match_key"]))
    return keys


def find_mentor_candidates(
    by_season: RecordsBySeason, latest_season_label: str
) -> list[dict]:
    """FR-003/004: base-eligible latest-season record, not itself a New
    Rider, and either the latest-season role is Rider or an earlier season's
    record for the same canonical identity (via `alias_match_keys`) has role
    Rider. Current latest-season role is otherwise irrelevant."""
    latest_records = by_season.get(latest_season_label, {})
    new_rider_keys = {
        record["match_key"]
        for record in find_new_riders(by_season, latest_season_label)
    }

    canonical = canonical_match_keys(
        {label: list(records.values()) for label, records in by_season.items()}
    )
    rider_history_keys = _rider_history_canonical_keys(by_season, canonical)

    candidates = []
    for record in latest_records.values():
        if not is_eligible_base(record):
            continue
        if record["match_key"] in new_rider_keys:
            continue
        canonical_key = canonical.get(record["match_key"], record["match_key"])
        if canonical_key in rider_history_keys:
            candidates.append(record)
    return candidates
