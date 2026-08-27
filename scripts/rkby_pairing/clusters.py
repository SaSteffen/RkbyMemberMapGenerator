"""Training-cluster detection (FR-001/002, data-model.md § Training Cluster,
research.md Decision 1): every current-season Rider (any experience level)
who passes base eligibility ends up in exactly one cluster -- alone, paired,
or grouped with whoever else lives close enough to plausibly train together
-- via the generalized `find_overlap_groups`."""

from __future__ import annotations

from dataclasses import dataclass

from scripts.rkby_maps.clustering import find_overlap_groups
from scripts.rkby_pairing.eligibility import is_eligible_base
from scripts.rkby_pairing.roles import classify_role
from scripts.rkby_report.geo import haversine_km

DEFAULT_CLUSTER_RADIUS_KM = 5


@dataclass(frozen=True)
class TrainingCluster:
    member_match_keys: list[str]
    centroid: tuple[float, float]


def find_training_clusters(
    latest_records: dict[str, dict],
    cluster_radius_km: float = DEFAULT_CLUSTER_RADIUS_KM,
) -> list[TrainingCluster]:
    """Pool: latest-season Rider-role, base-eligible records only -- Service
    Crew/Supporter members are never nodes in this graph at all, so they can
    never end up "in" a cluster. Two pool members are linked when
    `haversine_km(a, b) <= cluster_radius_km`; a cluster is one connected
    component of at least 1 linked member (FR-001/002) -- an isolated rider
    still forms their own one-member cluster instead of being dropped."""
    positions = {
        match_key: (record["latitude"], record["longitude"])
        for match_key, record in latest_records.items()
        if classify_role(record.get("role")) == "rider" and is_eligible_base(record)
    }

    groups = find_overlap_groups(
        positions,
        radius=cluster_radius_km / 2,
        distance_fn=haversine_km,
        min_group_size=1,
    )

    clusters = []
    for group in sorted(groups, key=sorted):
        members = sorted(group)
        lats = [positions[key][0] for key in members]
        lons = [positions[key][1] for key in members]
        centroid = (sum(lats) / len(lats), sum(lons) / len(lons))
        clusters.append(TrainingCluster(member_match_keys=members, centroid=centroid))
    return clusters
