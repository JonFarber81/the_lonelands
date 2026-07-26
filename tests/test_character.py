"""Tests for the character-model data: the three attributes and the level curve."""
from __future__ import annotations

from lonelands import character


def test_three_attributes():
    assert character.ATTRIBUTES == ("Brawn", "Wits", "Will")


def test_no_skills_or_proficiencies_survive():
    # The TOR skill/proficiency layer is gone from the module entirely.
    for gone in ("SKILL_GROUPS", "ALL_SKILLS", "PROFICIENCIES", "SKILL_TO_ATTR",
                 "attribute_tn"):
        assert not hasattr(character, gone), f"{gone} should be removed"


def test_xp_to_next_is_positive_and_rises_with_level():
    prev = 0
    for level in range(1, character.MAX_LEVEL):
        cost = character.xp_to_next(level)
        assert cost > 0
        assert cost > prev  # each level asks a little more than the last
        prev = cost


def test_early_levels_are_cheap():
    # Frequent, roguelike cadence: the first level-up is a modest ask.
    assert character.xp_to_next(1) <= 30
