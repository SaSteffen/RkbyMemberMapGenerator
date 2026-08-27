"""Markdown rendering: `## New Riders` (pairing lists + contact info + photo
links, FR-009/013, research.md §8) and `## Training Clusters` (US1: always
the empty-state placeholder here; US2/T024 wires in real clusters,
contracts/report-output.md)."""

from __future__ import annotations

from scripts.rkby_pairing.ranking import SuggestedPairing


def _full_name(record: dict) -> str:
    return f"{record['first_name']} {record['last_name']}".strip()


def _photo_line(record: dict, season_label: str) -> str | None:
    photo = record.get("photo")
    if not photo:
        return None
    return f"![{_full_name(record)}](../seasons/{season_label}/{photo})"


def _contact_lines(record: dict, *, indent: str = "") -> list[str]:
    """Shared contact-info+photo helper's non-photo half -- name, address,
    and whichever of phone/email are on file (FR-009), omitting whichever
    field is null. Reused unchanged by New Rider headers, Suggested Contact
    entries, and Training Cluster members."""
    lines = []
    if record.get("address"):
        lines.append(f"{indent}- Address: {record['address']}")
    if record.get("phone"):
        lines.append(f"{indent}- Phone: {record['phone']}")
    if record.get("email"):
        lines.append(f"{indent}- Email: {record['email']}")
    return lines


def _sort_key(record: dict) -> tuple[str, str]:
    return (record.get("last_name") or "", record.get("first_name") or "")


def _suggestion_annotation(pairing: SuggestedPairing) -> str:
    parts = [f"{pairing.distance_km:.1f} km away"]
    if pairing.age_gap_years is not None:
        parts.append(f"{pairing.age_gap_years} years apart")
    if pairing.same_sex is not None:
        parts.append("same sex" if pairing.same_sex else "different sex")
    return ", ".join(parts)


def _render_suggested_contacts(
    pairings: list[SuggestedPairing], members_by_key: dict[str, dict], season_label: str
) -> list[str]:
    if not pairings:
        return ["No eligible contacts found nearby."]

    lines = []
    for pairing in sorted(pairings, key=lambda p: p.rank):
        mentor = members_by_key[pairing.mentor_match_key]
        lines.append(
            f"{pairing.rank}. **{_full_name(mentor)}** — {_suggestion_annotation(pairing)}"
        )
        photo_line = _photo_line(mentor, season_label)
        if photo_line:
            lines.append(f"   {photo_line}")
        lines.extend(_contact_lines(mentor, indent="   "))
    return lines


def _render_new_rider_section(
    new_rider: dict,
    pairings: list[SuggestedPairing],
    members_by_key: dict[str, dict],
    season_label: str,
) -> list[str]:
    lines = [f"### {_full_name(new_rider)}"]
    photo_line = _photo_line(new_rider, season_label)
    if photo_line:
        lines.append(photo_line)
    lines.append("")
    lines.extend(_contact_lines(new_rider))
    lines.append("")
    lines.append("Suggested contacts:")
    lines.append("")
    lines.extend(_render_suggested_contacts(pairings, members_by_key, season_label))
    lines.append("")
    return lines


def _render_cluster_section(
    index: int, cluster, members_by_key: dict, season_label: str
) -> list[str]:
    lines = [f"### Cluster {index} ({len(cluster.member_match_keys)} riders)", ""]
    for match_key in cluster.member_match_keys:
        member = members_by_key[match_key]
        lines.append(f"- **{_full_name(member)}**")
        photo_line = _photo_line(member, season_label)
        if photo_line:
            lines.append(f"  {photo_line}")
        lines.extend(_contact_lines(member, indent="  "))
    lines.append("")
    return lines


def render_report(
    season_label: str,
    generated_at: str,
    new_riders: list[dict],
    suggestions_by_new_rider: dict[str, list[SuggestedPairing]],
    members_by_key: dict[str, dict],
    clusters: list,
) -> str:
    lines = [
        f"# Rider Pairing Suggestions — {season_label}",
        "",
        (
            f"Generated {generated_at}. Hand-edit this file freely — re-running the "
            "script overwrites it, but every prior version stays recoverable from "
            "this repository's git history."
        ),
        "",
        "## New Riders",
        "",
    ]

    for new_rider in sorted(new_riders, key=_sort_key):
        pairings = suggestions_by_new_rider.get(new_rider["match_key"], [])
        lines.extend(
            _render_new_rider_section(new_rider, pairings, members_by_key, season_label)
        )

    lines.append("## Training Clusters")
    lines.append("")
    if not clusters:
        lines.append("No training clusters found this season.")
    else:
        for index, cluster in enumerate(clusters, start=1):
            lines.extend(
                _render_cluster_section(index, cluster, members_by_key, season_label)
            )

    return "\n".join(lines) + "\n"
