"""Unit tests for `scripts/rkby_maps/declutter.py`: the Python port of the
interactive map's own marker decluttering
(`frontend/interactive-map/src/declutter.js`), mirroring that module's own
test cases (`declutter.test.js`) so the static and interactive maps can
never drift apart on how they lay overlapping members out."""

import math

from scripts.rkby_maps.declutter import declutter_positions

# Stand-in marker radius: the overlap threshold is the 2*RADIUS diameter,
# exactly as `find_overlap_groups` already defines it for pins/photos.
RADIUS = 20.0
DIAMETER = 2 * RADIUS


def test_leaves_markers_farther_apart_than_the_overlap_threshold_untouched():
    positions = {"a": (100.0, 100.0), "b": (100.0 + 2 * DIAMETER, 100.0)}

    decluttered, groups = declutter_positions(positions, marker_radius=RADIUS)

    assert decluttered == positions
    assert groups == []


def test_separates_two_markers_stacked_on_the_same_position():
    positions = {"a": (200.0, 200.0), "b": (200.0, 200.0)}

    decluttered, groups = declutter_positions(positions, marker_radius=RADIUS)

    assert [sorted(group) for group in groups] == [["a", "b"]]
    assert math.dist(decluttered["a"], decluttered["b"]) >= DIAMETER


def test_spaces_a_packed_group_by_exactly_the_marker_diameter():
    positions = {"a": (200.0, 200.0), "b": (200.0, 200.0)}

    decluttered, _groups = declutter_positions(positions, marker_radius=RADIUS)

    assert math.dist(decluttered["a"], decluttered["b"]) == DIAMETER


def test_packs_an_overlapping_group_into_a_compact_grid_not_a_single_line():
    positions = {key: (50.0, 50.0) for key in ("a", "b", "c", "d")}

    decluttered, _groups = declutter_positions(positions, marker_radius=RADIUS)

    # A space-saving grid uses both axes; a single-direction line would not.
    assert len({x for x, _y in decluttered.values()}) > 1
    assert len({y for _x, y in decluttered.values()}) > 1


def test_keeps_every_member_of_a_group_of_three_pairwise_non_overlapping():
    positions = {key: (50.0, 50.0) for key in ("a", "b", "c")}

    decluttered, _groups = declutter_positions(positions, marker_radius=RADIUS)

    placed = list(decluttered.values())
    for index, first in enumerate(placed):
        for second in placed[index + 1 :]:
            assert math.dist(first, second) >= DIAMETER


def test_centers_a_packed_group_on_its_own_centroid():
    # Four mutually-overlapping members, centroid (120, 310) -- a full 2x2
    # grid, so the packed positions' own mean is that same centroid.
    positions = {
        "a": (100.0, 300.0),
        "b": (140.0, 300.0),
        "c": (100.0, 320.0),
        "d": (140.0, 320.0),
    }

    decluttered, _groups = declutter_positions(positions, marker_radius=RADIUS)

    packed_x = sum(x for x, _y in decluttered.values()) / len(decluttered)
    packed_y = sum(y for _x, y in decluttered.values()) / len(decluttered)
    assert packed_x == 120.0
    assert packed_y == 310.0


def test_a_larger_marker_radius_spreads_the_same_group_further_apart():
    positions = {"a": (200.0, 200.0), "b": (210.0, 200.0)}

    tight, _tight_groups = declutter_positions(positions, marker_radius=RADIUS)
    wide, _wide_groups = declutter_positions(positions, marker_radius=2 * RADIUS)

    assert math.dist(tight["a"], tight["b"]) == DIAMETER
    assert math.dist(wide["a"], wide["b"]) == 2 * DIAMETER


def test_leaves_a_member_outside_every_overlap_group_exactly_where_they_are():
    positions = {
        "stacked-a": (50.0, 50.0),
        "stacked-b": (50.0, 50.0),
        "lone": (500.0, 500.0),
    }

    decluttered, _groups = declutter_positions(positions, marker_radius=RADIUS)

    assert decluttered["lone"] == (500.0, 500.0)


def test_does_not_mutate_the_positions_it_was_given():
    positions = {"a": (10.0, 10.0), "b": (10.0, 10.0)}

    declutter_positions(positions, marker_radius=RADIUS)

    assert positions == {"a": (10.0, 10.0), "b": (10.0, 10.0)}
