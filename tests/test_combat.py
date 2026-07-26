"""Combat resolution tests.

These drive the real `MeleeAction.perform()` against a real Engine/GameMap
(both construct fine headless — no display needed) so we exercise the actual
branch logic, not a re-implementation. Dice are pinned via `set_seed`, and
where we need a *specific* face we scan for a seed that produces it and re-seed
before the call (the resolution reproduces the same roll stream).
"""
from __future__ import annotations

import pytest

from lonelands import content
from lonelands.actions import MeleeAction
from lonelands.dice import set_seed, skill_check
from lonelands.engine import Engine
from lonelands.game_map import GameMap


def make_world():
    """A player at (2,1) with a foe at (1,1), adjacent for a melee bump."""
    player = content.make_player()
    engine = Engine(player)
    gm = GameMap(engine, 10, 10)
    engine.game_map = gm
    player.place(2, 1, gm)  # foes spawn adjacent at (1,1) or (3,1)
    return engine, gm, player


def spawn_foe(gm, template, x=1, y=1):
    return template.spawn(gm, x, y)


def last_message(engine):
    return engine.message_log.messages[-1].plain_text


# --- Attack-TN wiring -------------------------------------------------------

def test_fighter_exposes_attack_tn():
    assert content.orc_soldier.fighter.attack == 13
    assert content.warg.fighter.attack == 14


def test_wounded_foe_strikes_less_surely():
    f = content.orc_soldier.fighter
    base = f.attack
    f.wounded = True
    assert f.attack == base - 2
    f.wounded = False


# --- Incoming attacks: the player parries -----------------------------------

def test_player_parries_when_the_roll_succeeds():
    engine, gm, player = make_world()
    foe = spawn_foe(gm, content.cave_goblin)
    foe.fighter.base_attack = 2  # trivial TN -> the parry always succeeds
    start = player.fighter.endurance

    MeleeAction(foe, 1, 0).perform()  # foe at (1,1) strikes player at (2,1)

    assert player.fighter.endurance == start          # no damage
    assert "turn the blow aside" in last_message(engine)
    # A parry is the player's own roll, so it feeds the dice tray.
    assert engine.last_roll is not None


def test_failed_parry_takes_the_foes_damage():
    engine, gm, player = make_world()
    foe = spawn_foe(gm, content.cave_goblin)
    foe.fighter.base_attack = 99  # unreachable TN -> the parry fails

    # Find a seed whose parry roll fails outright (not the Gandalf auto-success).
    seed = _seed_where(99, lambda r: not r.is_success and not r.is_eye)
    set_seed(seed)
    start = player.fighter.endurance

    MeleeAction(foe, 1, 0).perform()

    assert player.fighter.endurance == start - foe.fighter.damage
    assert f"for {foe.fighter.damage} endurance" in last_message(engine)
    assert not player.fighter.wounded  # a plain failure does not wound


def test_eye_on_a_failed_parry_inflicts_a_wound():
    engine, gm, player = make_world()
    foe = spawn_foe(gm, content.cave_goblin)
    foe.fighter.base_attack = 99

    # Seed where the parry rolls the Eye (fumble) AND the follow-up protection
    # test also fails, so a wound lands. Player protection is 0.
    injury = foe.fighter.injury

    def ok(seed):
        set_seed(seed)
        parry = skill_check(99, player.hero.skills["Battle"])
        if not parry.is_eye:
            return False
        prot = skill_check(injury, player.fighter.protection)
        return not prot.is_success

    seed = next(s for s in range(10000) if ok(s))
    set_seed(seed)

    assert not player.fighter.wounded
    MeleeAction(foe, 1, 0).perform()

    assert player.fighter.wounded
    assert "wounds you" in last_message(engine)


def test_second_wound_is_mortal():
    engine, gm, player = make_world()
    foe = spawn_foe(gm, content.cave_goblin)
    foe.fighter.base_attack = 99
    player.fighter.wounded = True  # already carrying one wound

    injury = foe.fighter.injury

    def ok(seed):
        set_seed(seed)
        parry = skill_check(99, player.hero.skills["Battle"])
        if not parry.is_eye:
            return False
        prot = skill_check(injury, player.fighter.protection)
        return not prot.is_success

    seed = next(s for s in range(10000) if ok(s))
    set_seed(seed)

    MeleeAction(foe, 1, 0).perform()
    assert player.fighter.endurance == 0  # struck down


# --- Outgoing attacks: the player still rolls to hit (regression) -----------

def test_player_attacking_a_foe_uses_the_attacker_roll_path():
    engine, gm, player = make_world()
    foe = content.cave_goblin.spawn(gm, 3, 1)  # to the player's right
    foe.fighter.base_defence = 2  # trivial TN -> the player always hits
    start = foe.fighter.endurance

    set_seed(1)
    MeleeAction(player, 1, 0).perform()  # player at (2,1) strikes foe at (3,1)

    assert foe.fighter.endurance < start  # the foe took the hit


# --- Enemy AI actually reaches the player (regression) ----------------------

def test_adjacent_foe_ai_strikes_the_player():
    """A foe's turn must route a bump into the player through to a melee.

    Regression: BumpAction gated melee on the target having an .ai, which the
    player never has, so enemy attacks were silently swallowed as Impossible.
    """
    from lonelands.actions import BumpAction

    engine, gm, player = make_world()
    foe = spawn_foe(gm, content.cave_goblin)  # adjacent at (1,1)
    foe.fighter.base_attack = 99  # unreachable parry TN -> the blow lands
    start = player.fighter.endurance

    BumpAction(foe, 1, 0).perform()  # foe at (1,1) bumps player at (2,1)

    assert player.fighter.endurance < start  # the player took the hit
    assert "for" in last_message(engine)


# --- helpers ---------------------------------------------------------------

def _seed_where(tn, predicate, rank=2):
    for seed in range(10000):
        set_seed(seed)
        if predicate(skill_check(tn, rank)):
            return seed
    raise AssertionError("no seed satisfied the predicate")
