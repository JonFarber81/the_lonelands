"""Tests for the d20 resolution core.

Two styles here:
  * `RollResult` outcome logic is pure, so we construct results directly and
    assert on the derived properties (no RNG needed).
  * `roll_check` / `roll_damage` are exercised through the seedable `rng`,
    asserting invariants and determinism rather than specific faces.
"""
from __future__ import annotations

import pytest

from lonelands import dice
from lonelands.dice import RollResult, roll_check, roll_damage, set_seed


# --- RollResult outcome logic (pure) ---------------------------------------

def test_total_is_die_plus_modifier():
    r = RollResult(die=12, mod=4, tn=14)
    assert r.total == 16


def test_success_when_total_meets_tn():
    r = RollResult(die=10, mod=4, tn=14)
    assert r.is_success
    assert not r.is_crit and not r.is_fumble


def test_failure_when_total_below_tn():
    r = RollResult(die=8, mod=1, tn=14)
    assert not r.is_success


def test_natural_twenty_is_a_crit_and_always_succeeds():
    # A modest modifier that would miss a high TN on the number, but a 20 crits.
    r = RollResult(die=20, mod=0, tn=99)
    assert r.is_crit
    assert r.is_success


def test_natural_one_is_a_fumble_and_always_fails():
    # A big modifier that would clear the TN on the number, but a 1 fumbles.
    r = RollResult(die=1, mod=50, tn=5)
    assert r.is_fumble
    assert not r.is_success


def test_describe_marks_special_faces():
    assert "CRIT" in RollResult(die=20, mod=0, tn=14).describe()
    assert "FUMBLE" in RollResult(die=1, mod=0, tn=14).describe()
    assert "hit" in RollResult(die=12, mod=4, tn=14).describe()
    assert "miss" in RollResult(die=3, mod=0, tn=14).describe()


# --- roll_check invariants & determinism -----------------------------------

def test_roll_check_single_die_in_range():
    set_seed(1234)
    r = roll_check(mod=4, tn=14)
    assert len(r.dice) == 1
    assert 1 <= r.die <= 20
    assert r.total == r.die + 4


def test_roll_check_is_deterministic_under_a_seed():
    set_seed(42)
    a = roll_check(mod=3, tn=15)
    set_seed(42)
    b = roll_check(mod=3, tn=15)
    assert (a.die, a.dice, a.total) == (b.die, b.dice, b.total)


def test_advantage_rolls_two_dice_and_keeps_the_higher():
    set_seed(7)
    r = roll_check(mod=0, tn=10, advantage=1)
    assert len(r.dice) == 2
    assert r.die == max(r.dice)


def test_disadvantage_keeps_the_lower():
    set_seed(7)
    r = roll_check(mod=0, tn=10, advantage=-1)
    assert len(r.dice) == 2
    assert r.die == min(r.dice)


def test_advantage_beats_disadvantage_on_average():
    def mean_die(adv):
        set_seed(500)
        return sum(roll_check(0, 10, advantage=adv).die for _ in range(1000))
    assert mean_die(1) > mean_die(0) > mean_die(-1)


def test_crit_and_fumble_appear_over_many_rolls():
    set_seed(2024)
    saw_crit = saw_fumble = False
    for _ in range(2000):
        r = roll_check(mod=0, tn=14)
        saw_crit |= r.is_crit
        saw_fumble |= r.is_fumble
    assert saw_crit and saw_fumble


# --- roll_damage -----------------------------------------------------------

def test_roll_damage_flat_int_passthrough():
    assert roll_damage(5) == 5
    assert roll_damage(0) == 0


def test_roll_damage_negative_int_floors_at_zero():
    assert roll_damage(-3) == 0


def test_roll_damage_dice_notation_within_bounds():
    set_seed(3)
    for _ in range(200):
        v = roll_damage("2d6")
        assert 2 <= v <= 12


def test_roll_damage_dice_with_bonus():
    set_seed(11)
    for _ in range(200):
        v = roll_damage("1d8+1")
        assert 2 <= v <= 9


def test_roll_damage_rejects_garbage():
    with pytest.raises(ValueError):
        roll_damage("not-dice")


def test_roll_dice_sum_is_within_bounds():
    set_seed(3)
    for _ in range(100):
        total = dice.roll_dice(2, 6)
        assert 2 <= total <= 12
