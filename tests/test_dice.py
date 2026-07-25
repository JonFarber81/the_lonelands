"""Tests for the One Ring dice engine.

Two styles here:
  * `RollResult` outcome logic is pure, so we construct results directly and
    assert on the derived properties (no RNG needed).
  * `skill_check` is exercised through the seedable `rng`, asserting invariants
    and determinism rather than specific faces.
"""
from __future__ import annotations

from lonelands import dice
from lonelands.dice import EYE, GANDALF, RollResult, set_seed, skill_check


# --- RollResult outcome logic (pure) ---------------------------------------

def test_plain_success_when_total_meets_tn():
    r = RollResult(total=14, tn=14, feat=8, feat_raw=8, success_dice=[6])
    # tengwar defaults to 0 here, so this is a plain success, not great
    assert r.is_success
    assert r.quality == "success"


def test_failure_when_total_below_tn():
    r = RollResult(total=9, tn=14, feat=9, feat_raw=9)
    assert not r.is_success
    assert not r.is_great
    assert r.quality == "failure"


def test_gandalf_rune_always_succeeds_regardless_of_tn():
    r = RollResult(total=0, tn=18, feat=0, feat_raw=GANDALF, is_gandalf=True)
    assert r.is_success
    assert r.is_great          # the Gandalf rune counts as a great success
    assert r.quality == "great"


def test_eye_counts_as_zero_and_can_fail():
    r = RollResult(total=3, tn=14, feat=0, feat_raw=EYE, is_eye=True,
                   success_dice=[3])
    assert not r.is_success
    assert r.quality == "failure"


def test_great_success_needs_a_tengwar():
    r = RollResult(total=16, tn=14, feat=10, feat_raw=10,
                   success_dice=[6], tengwar=1)
    assert r.is_great
    assert not r.is_extraordinary
    assert r.quality == "great"


def test_extraordinary_success_needs_two_tengwar():
    r = RollResult(total=20, tn=14, feat=8, feat_raw=8,
                   success_dice=[6, 6], tengwar=2)
    assert r.is_extraordinary
    assert r.quality == "extraordinary"


def test_tengwar_on_a_failed_roll_is_not_a_great_success():
    # A 6 was rolled (tengwar) but the total still misses the TN.
    r = RollResult(total=8, tn=14, feat=2, feat_raw=2,
                   success_dice=[6], tengwar=1)
    assert not r.is_success
    assert not r.is_great
    assert r.quality == "failure"


def test_describe_marks_special_faces():
    assert "G" in RollResult(0, 14, 0, GANDALF, is_gandalf=True).describe()
    assert "Eye" in RollResult(0, 14, 0, EYE, is_eye=True).describe()
    assert "7" in RollResult(7, 14, 7, 7).describe()


# --- skill_check invariants & determinism ----------------------------------

def test_skill_check_rolls_one_success_die_per_rank():
    set_seed(1234)
    r = skill_check(tn=14, rank=3)
    assert len(r.success_dice) == 3
    assert all(1 <= d <= 6 for d in r.success_dice)


def test_skill_check_rank_zero_rolls_no_success_dice():
    set_seed(1)
    r = skill_check(tn=14, rank=0)
    assert r.success_dice == []


def test_skill_check_is_deterministic_under_a_seed():
    set_seed(42)
    a = skill_check(tn=15, rank=4)
    set_seed(42)
    b = skill_check(tn=15, rank=4)
    assert (a.feat_raw, a.success_dice, a.total) == (b.feat_raw, b.success_dice, b.total)


def test_weary_zeroes_success_dice_of_three_or_less():
    # Find a seed whose success dice include a 1-3, then compare weary vs not.
    for seed in range(200):
        set_seed(seed)
        normal = skill_check(tn=14, rank=5, weary=False)
        if any(d <= 3 for d in normal.success_dice):
            set_seed(seed)
            weary = skill_check(tn=14, rank=5, weary=True)
            assert weary.total < normal.total
            assert weary.weary is True
            return
    raise AssertionError("no seed produced a low success die to test weariness")


def test_modifier_is_added_to_total():
    set_seed(7)
    base = skill_check(tn=14, rank=2, modifier=0)
    set_seed(7)
    bumped = skill_check(tn=14, rank=2, modifier=5)
    assert bumped.total == base.total + 5


def test_tengwar_count_matches_number_of_sixes():
    set_seed(99)
    r = skill_check(tn=14, rank=6)
    assert r.tengwar == r.success_dice.count(6)


def test_special_feat_faces_appear_over_many_rolls():
    set_seed(2024)
    saw_eye = saw_gandalf = False
    for _ in range(2000):
        r = skill_check(tn=14, rank=1)
        saw_eye |= r.is_eye
        saw_gandalf |= r.is_gandalf
    assert saw_eye and saw_gandalf


def test_favoured_keeps_the_higher_of_two_feat_dice():
    # Averaged over many rolls, favoured feat values beat ill-favoured ones.
    def mean_feat(favoured):
        set_seed(500)
        return sum(skill_check(14, 0, favoured=favoured).feat_raw
                   for _ in range(1000))
    assert mean_feat(1) > mean_feat(0) > mean_feat(-1)


def test_roll_dice_sum_is_within_bounds():
    set_seed(3)
    for _ in range(100):
        total = dice.roll_dice(2, 6)
        assert 2 <= total <= 12
