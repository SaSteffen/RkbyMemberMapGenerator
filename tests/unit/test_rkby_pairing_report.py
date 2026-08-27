"""Unit tests for `scripts/rkby_pairing/report.py` (contracts/report-output.md):
Markdown structure for the `## New Riders` section (US1) and the
`## Training Clusters` section (US1 empty-state placeholder here; US2 extends
this file with populated-cluster-section coverage in T020)."""

from scripts.rkby_pairing.clusters import TrainingCluster
from scripts.rkby_pairing.ranking import SuggestedPairing
from scripts.rkby_pairing.report import render_report

SEASON_LABEL = "2025-26"
GENERATED_AT = "2026-08-27"

ALPHA_NEW_RIDER = {
    "match_key": "alpha-new",
    "first_name": "Alpha",
    "last_name": "Newrider",
    "address": "Erststr. 1, 20095 Hamburg, Germany",
    "phone": "+49 40 1000000",
    "email": None,
    "photo": "photos/alpha-new.jpg",
}
ZETA_NEW_RIDER = {
    "match_key": "zeta-new",
    "first_name": "Zeta",
    "last_name": "Zuletzt",
    "address": "Letztstr. 2, 20095 Hamburg, Germany",
    "phone": None,
    "email": "zeta.zuletzt@example.test",
    "photo": None,
}
MENTOR_ONE = {
    "match_key": "mentor-one",
    "first_name": "Mentor",
    "last_name": "One",
    "address": "Mentorstr. 3, 20095 Hamburg, Germany",
    "phone": "+49 40 2000000",
    "email": "mentor.one@example.test",
    "photo": "photos/mentor-one.jpg",
}
MENTOR_TWO = {
    "match_key": "mentor-two",
    "first_name": "Mentor",
    "last_name": "Two",
    "address": "Mentorstr. 4, 20095 Hamburg, Germany",
    "phone": None,
    "email": None,
    "photo": None,
}

MEMBERS_BY_KEY = {
    record["match_key"]: record
    for record in (ALPHA_NEW_RIDER, ZETA_NEW_RIDER, MENTOR_ONE, MENTOR_TWO)
}


def test_one_subsection_per_new_rider_in_alphabetical_last_name_order():
    suggestions = {"alpha-new": [], "zeta-new": []}

    text = render_report(
        SEASON_LABEL,
        GENERATED_AT,
        [ZETA_NEW_RIDER, ALPHA_NEW_RIDER],
        suggestions,
        MEMBERS_BY_KEY,
        [],
    )

    assert "## New Riders" in text
    alpha_index = text.index("Alpha Newrider")
    zeta_index = text.index("Zeta Zuletzt")
    assert alpha_index < zeta_index


def test_new_rider_with_empty_suggestion_list_still_appears_with_placeholder_text():
    suggestions = {"alpha-new": []}

    text = render_report(
        SEASON_LABEL, GENERATED_AT, [ALPHA_NEW_RIDER], suggestions, MEMBERS_BY_KEY, []
    )

    assert "Alpha Newrider" in text
    assert "No eligible contacts found nearby." in text


def test_contact_info_shows_address_and_omits_null_phone_or_email():
    suggestions = {"zeta-new": []}

    text = render_report(
        SEASON_LABEL, GENERATED_AT, [ZETA_NEW_RIDER], suggestions, MEMBERS_BY_KEY, []
    )

    assert "Letztstr. 2, 20095 Hamburg, Germany" in text
    assert "zeta.zuletzt@example.test" in text
    # Zeta has no phone on file -- no dangling "Phone: None".
    assert "Phone: None" not in text


def test_photo_reference_resolved_relative_to_report_location_when_present():
    suggestions = {"alpha-new": []}

    text = render_report(
        SEASON_LABEL, GENERATED_AT, [ALPHA_NEW_RIDER], suggestions, MEMBERS_BY_KEY, []
    )

    assert "../seasons/2025-26/photos/alpha-new.jpg" in text


def test_no_photo_reference_when_record_has_none_on_file():
    suggestions = {"zeta-new": []}

    text = render_report(
        SEASON_LABEL, GENERATED_AT, [ZETA_NEW_RIDER], suggestions, MEMBERS_BY_KEY, []
    )

    assert (
        "!["
        not in text.split("## Training Clusters")[0]
        .split("Zeta Zuletzt", 1)[1]
        .split("### ", 1)[0]
    )


def test_suggested_contacts_ordered_by_rank_with_distance_always_shown():
    pairings = [
        SuggestedPairing(
            new_rider_match_key="alpha-new",
            mentor_match_key="mentor-one",
            rank=1,
            distance_km=1.234,
            age_gap_years=None,
            same_sex=None,
        ),
        SuggestedPairing(
            new_rider_match_key="alpha-new",
            mentor_match_key="mentor-two",
            rank=2,
            distance_km=9.876,
            age_gap_years=None,
            same_sex=None,
        ),
    ]

    text = render_report(
        SEASON_LABEL,
        GENERATED_AT,
        [ALPHA_NEW_RIDER],
        {"alpha-new": pairings},
        MEMBERS_BY_KEY,
        [],
    )

    first_index = text.index("Mentor One")
    second_index = text.index("Mentor Two")
    assert first_index < second_index
    assert "1.2" in text  # distance always shown (rounded)
    assert "9.9" in text


def test_age_gap_and_same_sex_annotations_shown_only_when_known():
    pairings = [
        SuggestedPairing(
            new_rider_match_key="alpha-new",
            mentor_match_key="mentor-one",
            rank=1,
            distance_km=1.0,
            age_gap_years=5,
            same_sex=True,
        ),
        SuggestedPairing(
            new_rider_match_key="alpha-new",
            mentor_match_key="mentor-two",
            rank=2,
            distance_km=2.0,
            age_gap_years=None,
            same_sex=None,
        ),
    ]

    text = render_report(
        SEASON_LABEL,
        GENERATED_AT,
        [ALPHA_NEW_RIDER],
        {"alpha-new": pairings},
        MEMBERS_BY_KEY,
        [],
    )

    mentor_one_block = text[text.index("Mentor One") : text.index("Mentor Two")]
    assert "5 years apart" in mentor_one_block
    assert "same sex" in mentor_one_block

    mentor_two_block = text[text.index("Mentor Two") :]
    assert "years apart" not in mentor_two_block


# --- Training Clusters section (empty-state, US1 scope) -----------------------


def test_empty_training_clusters_section_shows_placeholder_text():
    text = render_report(
        SEASON_LABEL,
        GENERATED_AT,
        [ALPHA_NEW_RIDER],
        {"alpha-new": []},
        MEMBERS_BY_KEY,
        [],
    )

    assert "## Training Clusters" in text
    assert "No training clusters found this season." in text


CLUSTER_MEMBER_ONE = {
    "match_key": "cluster-member-one",
    "first_name": "Clustera",
    "last_name": "Riderone",
    "address": "Clusterstr. 1, 20095 Hamburg, Germany",
    "phone": "+49 40 9000001",
    "email": None,
    "photo": "photos/cluster-member-one.jpg",
}
CLUSTER_MEMBER_TWO = {
    "match_key": "cluster-member-two",
    "first_name": "Clusterb",
    "last_name": "Ridertwo",
    "address": "Clusterstr. 2, 20095 Hamburg, Germany",
    "phone": None,
    "email": "clusterb.ridertwo@example.test",
    "photo": None,
}
CLUSTER_MEMBER_THREE = {
    "match_key": "cluster-member-three",
    "first_name": "Clusterc",
    "last_name": "Riderthree",
    "address": "Clusterstr. 3, 20095 Hamburg, Germany",
    "phone": "+49 40 9000003",
    "email": None,
    "photo": None,
}

CLUSTER_MEMBERS_BY_KEY = {
    **MEMBERS_BY_KEY,
    "cluster-member-one": CLUSTER_MEMBER_ONE,
    "cluster-member-two": CLUSTER_MEMBER_TWO,
    "cluster-member-three": CLUSTER_MEMBER_THREE,
}


def test_populated_training_clusters_section_renders_one_subsection_per_cluster():
    cluster = TrainingCluster(
        member_match_keys=[
            "cluster-member-one",
            "cluster-member-two",
            "cluster-member-three",
        ],
        centroid=(53.6, 10.1),
    )

    text = render_report(
        SEASON_LABEL, GENERATED_AT, [], {}, CLUSTER_MEMBERS_BY_KEY, [cluster]
    )

    assert "## Training Clusters" in text
    assert "No training clusters found this season." not in text
    assert "Cluster 1 (3 riders)" in text
    assert "Clustera Riderone" in text
    assert "Clusterb Ridertwo" in text
    assert "Clusterc Riderthree" in text


def test_cluster_members_get_the_same_contact_info_and_photo_treatment():
    cluster = TrainingCluster(
        member_match_keys=["cluster-member-one", "cluster-member-two"],
        centroid=(53.6, 10.1),
    )

    text = render_report(
        SEASON_LABEL, GENERATED_AT, [], {}, CLUSTER_MEMBERS_BY_KEY, [cluster]
    )

    clusters_section = text[text.index("## Training Clusters") :]
    assert "Clusterstr. 1, 20095 Hamburg, Germany" in clusters_section
    assert "../seasons/2025-26/photos/cluster-member-one.jpg" in clusters_section
    assert "clusterb.ridertwo@example.test" in clusters_section
    # Clusterb has no phone on file -- omitted, not "Phone: None".
    assert "Phone: None" not in clusters_section


def test_multiple_clusters_each_get_their_own_numbered_subsection():
    cluster_one = TrainingCluster(
        member_match_keys=["cluster-member-one", "cluster-member-two"],
        centroid=(53.6, 10.1),
    )
    cluster_two = TrainingCluster(
        member_match_keys=["cluster-member-three", "mentor-one"],
        centroid=(53.7, 10.2),
    )

    text = render_report(
        SEASON_LABEL,
        GENERATED_AT,
        [],
        {},
        CLUSTER_MEMBERS_BY_KEY,
        [cluster_one, cluster_two],
    )

    assert "Cluster 1 (2 riders)" in text
    assert "Cluster 2 (2 riders)" in text
    assert text.index("Cluster 1") < text.index("Cluster 2")


def test_report_header_includes_season_label_and_generated_date():
    text = render_report(
        SEASON_LABEL,
        GENERATED_AT,
        [ALPHA_NEW_RIDER],
        {"alpha-new": []},
        MEMBERS_BY_KEY,
        [],
    )

    assert SEASON_LABEL in text.splitlines()[0]
    assert GENERATED_AT in text
