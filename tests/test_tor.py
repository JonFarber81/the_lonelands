"""Tests for the TOR character-model data (attributes, skills, TN mapping)."""
from __future__ import annotations

from lonelands import tor


def test_eighteen_common_skills():
    assert len(tor.ALL_SKILLS) == 18
    assert len(set(tor.ALL_SKILLS)) == 18  # no duplicates


def test_every_skill_maps_back_to_its_attribute():
    for attr, skills in tor.SKILL_GROUPS.items():
        for skill in skills:
            assert tor.SKILL_TO_ATTR[skill] == attr


def test_skill_to_attr_covers_all_skills():
    assert set(tor.SKILL_TO_ATTR) == set(tor.ALL_SKILLS)


def test_three_attributes():
    assert tor.ATTRIBUTES == ("Strength", "Heart", "Wits")
    assert set(tor.SKILL_GROUPS) == set(tor.ATTRIBUTES)


def test_higher_attribute_gives_lower_tn():
    assert tor.attribute_tn(7) < tor.attribute_tn(2)


def test_attribute_tn_is_clamped_to_band():
    assert tor.attribute_tn(100) == 10   # floor
    assert tor.attribute_tn(-100) == 18  # ceiling


def test_attribute_tn_linear_in_band():
    # TN = 20 - rating inside the clamped band [10, 18].
    for rating in range(2, 8):
        assert tor.attribute_tn(rating) == 20 - rating
