"""Unit tests for `scripts/rkby_records.canonical_match_keys()` (research.md §7):
promoted, unchanged in behavior, from `rkby_interactive_map/merge.py`'s private
`_canonical_match_keys` -- direct alias resolution, transitive multi-hop alias
chains, and cycle-safety."""

from scripts.rkby_records import canonical_match_keys


def test_no_aliases_resolves_to_empty_mapping():
    eligible_by_season = {
        "2025-26": [{"match_key": "jane-doe"}],
    }

    assert canonical_match_keys(eligible_by_season) == {}


def test_direct_alias_resolves_to_the_declaring_records_own_key():
    eligible_by_season = {
        "2024-25": [{"match_key": "erika-mustermann"}],
        "2025-26": [
            {"match_key": "erika-schmidt", "alias_match_keys": ["erika-mustermann"]}
        ],
    }

    assert canonical_match_keys(eligible_by_season) == {
        "erika-mustermann": "erika-schmidt"
    }


def test_transitive_multi_hop_alias_chain_resolves_to_the_final_key():
    eligible_by_season = {
        "2023-24": [{"match_key": "erika-mustermann"}],
        "2024-25": [
            {"match_key": "erika-schmidt", "alias_match_keys": ["erika-mustermann"]}
        ],
        "2025-26": [
            {
                "match_key": "erika-schmidt-meyer",
                "alias_match_keys": ["erika-schmidt"],
            }
        ],
    }

    result = canonical_match_keys(eligible_by_season)

    assert result["erika-mustermann"] == "erika-schmidt-meyer"
    assert result["erika-schmidt"] == "erika-schmidt-meyer"


def test_cycle_is_resolved_safely_without_infinite_loop():
    # An accidental alias cycle (a -> b -> a) must not hang; resolution stops
    # once a key already visited during this lookup would repeat.
    eligible_by_season = {
        "2025-26": [
            {"match_key": "a", "alias_match_keys": ["b"]},
            {"match_key": "b", "alias_match_keys": ["a"]},
        ],
    }

    # Must terminate rather than loop forever; a cycle has no well-defined
    # "correct" resolution, so each key's chain walk stops back where it
    # started once it would revisit an already-seen key.
    result = canonical_match_keys(eligible_by_season)

    assert result == {"a": "a", "b": "b"}


def test_null_alias_match_keys_is_treated_as_no_aliases():
    eligible_by_season = {
        "2025-26": [{"match_key": "jane-doe", "alias_match_keys": None}],
    }

    assert canonical_match_keys(eligible_by_season) == {}
