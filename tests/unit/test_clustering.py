"""Unit tests for `scripts/rkby_maps/clustering.py` (research.md §4, §9):
overlap-graph/connected-components detection, the FR-014 same-exact-address
pair short-circuit, and detail-map filename slug derivation."""

from scripts.rkby_maps.clustering import (
    detail_map_slug,
    find_overlap_groups,
    is_fr014_exception,
)

# --- Overlap detection (FR-011, research.md §4) -----------------------------------


def test_two_close_members_form_one_overlap_group():
    positions = {"a": (0, 0), "b": (5, 0)}

    groups = find_overlap_groups(positions, radius=10)

    assert groups == [["a", "b"]]


def test_two_far_apart_members_form_no_overlap_group():
    positions = {"a": (0, 0), "b": (1000, 0)}

    groups = find_overlap_groups(positions, radius=10)

    assert groups == []


def test_overlap_is_transitive_across_a_chain():
    # a-b overlap, b-c overlap, a-c do not directly overlap -- still one
    # connected component (research.md §4: "transitive").
    positions = {"a": (0, 0), "b": (15, 0), "c": (30, 0)}

    groups = find_overlap_groups(positions, radius=10)

    assert len(groups) == 1
    assert set(groups[0]) == {"a", "b", "c"}


def test_two_separate_pairs_form_two_independent_groups():
    positions = {"a": (0, 0), "b": (5, 0), "c": (1000, 0), "d": (1005, 0)}

    groups = find_overlap_groups(positions, radius=10)

    assert len(groups) == 2
    group_sets = {frozenset(group) for group in groups}
    assert group_sets == {frozenset({"a", "b"}), frozenset({"c", "d"})}


def test_a_solo_member_with_no_overlap_produces_no_group():
    positions = {"a": (0, 0), "b": (5, 0), "solo": (999999, 999999)}

    groups = find_overlap_groups(positions, radius=10)

    assert all("solo" not in group for group in groups)


def test_larger_radius_can_merge_previously_separate_groups():
    positions = {"a": (0, 0), "b": (5, 0), "c": (30, 0)}

    small_radius_groups = find_overlap_groups(positions, radius=10)
    large_radius_groups = find_overlap_groups(positions, radius=20)

    assert len(small_radius_groups) == 1  # just a-b
    assert len(large_radius_groups) == 1
    assert set(large_radius_groups[0]) == {"a", "b", "c"}  # now all three


def test_find_overlap_groups_with_no_members_returns_empty_list():
    assert find_overlap_groups({}, radius=10) == []


# --- Near-miss tolerance (margin, photo variant only) ------------------------------


def test_margin_folds_in_a_near_miss_just_outside_the_combined_radius():
    # a-b are 23px apart -- 3px past the strict 2*10=20px combined-radius
    # test, so no group forms without slack.
    positions = {"a": (0, 0), "b": (23, 0)}

    assert find_overlap_groups(positions, radius=10) == []
    assert find_overlap_groups(positions, radius=10, margin=8) == [["a", "b"]]


def test_margin_still_excludes_a_member_beyond_the_slack():
    positions = {"a": (0, 0), "b": (23, 0), "c": (1000, 0)}

    groups = find_overlap_groups(positions, radius=10, margin=8)

    assert all("c" not in group for group in groups)


def test_margin_defaults_to_zero_and_matches_base_behavior():
    positions = {"a": (0, 0), "b": (23, 0)}

    assert find_overlap_groups(positions, radius=10) == find_overlap_groups(
        positions, radius=10, margin=0
    )


# --- FR-014 same-exact-address-pair short-circuit ---------------------------------


def test_is_fr014_exception_true_for_a_pair_sharing_the_identical_address():
    addresses = {
        "a": "Musterstr. 1, 22111 Hamburg, Germany",
        "b": "Musterstr. 1, 22111 Hamburg, Germany",
    }

    assert is_fr014_exception(["a", "b"], addresses) is True


def test_is_fr014_exception_false_for_a_pair_with_different_addresses():
    addresses = {
        "a": "Street One 1, 22111 Hamburg, Germany",
        "b": "Street Two 2, 22111 Hamburg, Germany",
    }

    assert is_fr014_exception(["a", "b"], addresses) is False


def test_is_fr014_exception_false_for_a_group_larger_than_two():
    addresses = {"a": "Same St 1", "b": "Same St 1", "c": "Same St 1"}

    assert is_fr014_exception(["a", "b", "c"], addresses) is False


def test_is_fr014_exception_false_when_address_is_none():
    addresses = {"a": None, "b": None}

    assert is_fr014_exception(["a", "b"], addresses) is False


# --- Detail-map filename slug derivation (research.md §9) -------------------------


def test_detail_map_slug_extracts_the_city_token():
    slug = detail_map_slug("Musterstr. 1, 27283 Verden, Germany", set())

    assert slug == "verden"


def test_detail_map_slug_strips_postal_code_digits():
    slug = detail_map_slug("Some Street 9, 20099 Hamburg, Germany", set())

    assert slug == "hamburg"


def test_detail_map_slug_normalizes_diacritics_and_case():
    slug = detail_map_slug("Musterstr. 1, 27283 Müllerstadt, Germany", set())

    assert slug == "mullerstadt"


def test_detail_map_slug_appends_a_collision_suffix_in_encounter_order():
    used = set()
    first = detail_map_slug("Street 1, 27283 Verden, Germany", used)
    used.add(first)
    second = detail_map_slug("Other Street 2, 27283 Verden, Germany", used)
    used.add(second)
    third = detail_map_slug("Third Street 3, 27283 Verden, Germany", used)

    assert first == "verden"
    assert second == "verden_2"
    assert third == "verden_3"
