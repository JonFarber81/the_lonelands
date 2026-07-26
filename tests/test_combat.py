"""Combat resolution tests.

These drive the real `MeleeAction.perform()` against a real Engine/GameMap
(both construct fine headless — no display needed) so we exercise the actual
branch logic, not a re-implementation. Dice are pinned via `set_seed`, and
where we need a *specific* d20 face we scan for a seed that produces it and
re-seed before the call (the resolution reproduces the same roll stream).
"""
from __future__ import annotations

from lonelands import content
from lonelands.actions import BumpAction, MeleeAction
from lonelands.components.fighter import BLEED_DAMAGE, CRIT_BLEED
from lonelands.dice import roll_check, set_seed
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


def _seed_where(mod, tn, predicate):
    """First seed whose `d20 + mod vs tn` roll satisfies `predicate`."""
    for seed in range(10000):
        set_seed(seed)
        if predicate(roll_check(mod, tn)):
            return seed
    raise AssertionError("no seed satisfied the predicate")


# --- New combat fields ------------------------------------------------------

def test_foes_expose_the_new_d20_fields():
    f = content.orc_soldier.fighter
    assert f.attack_bonus == 4
    assert f.defence == 12
    assert f.soak == 1
    assert f.damage == "1d6"


def test_heavy_foes_are_flagged_to_bleed_on_hit():
    assert content.warg.fighter.bleed_on_hit == 1
    assert content.cave_goblin.fighter.bleed_on_hit == 0


# --- Attack resolution: the attacker rolls ----------------------------------

def test_a_hit_deals_damage_reduced_by_soak():
    engine, gm, player = make_world()
    foe = content.cave_goblin.spawn(gm, 3, 1)  # to the player's right
    foe.fighter.base_defence = 2  # trivial Defence -> the player always hits
    start = foe.fighter.endurance

    # A plain hit (not a crit): the player's d20 clears the TN without a 20.
    seed = _seed_where(player.fighter.attack_bonus, 2,
                       lambda r: r.is_success and not r.is_crit)
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()

    assert foe.fighter.endurance < start
    assert "endurance" in last_message(engine)


def test_a_miss_deals_no_damage():
    engine, gm, player = make_world()
    foe = content.cave_goblin.spawn(gm, 3, 1)
    foe.fighter.base_defence = 99  # unreachable Defence -> a plain miss
    start = foe.fighter.endurance

    seed = _seed_where(player.fighter.attack_bonus, 99,
                       lambda r: not r.is_success and not r.is_fumble)
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()

    assert foe.fighter.endurance == start
    assert "but miss" in last_message(engine)


def test_a_players_attack_feeds_the_dice_tray_with_its_damage():
    engine, gm, player = make_world()
    foe = content.cave_goblin.spawn(gm, 3, 1)
    foe.fighter.base_defence = 2
    start = foe.fighter.endurance

    seed = _seed_where(player.fighter.attack_bonus, 2, lambda r: r.is_success)
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()

    assert engine.last_roll is not None
    # The tray reports the blow's damage (issue #35: the d20 line shows damage).
    assert engine.last_roll.damage == start - foe.fighter.endurance


def test_a_missed_attack_shows_no_damage_in_the_tray():
    engine, gm, player = make_world()
    foe = content.cave_goblin.spawn(gm, 3, 1)
    foe.fighter.base_defence = 99
    seed = _seed_where(player.fighter.attack_bonus, 99,
                       lambda r: not r.is_success and not r.is_fumble)
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()
    assert engine.last_roll.damage is None


def test_soak_floors_a_clean_hit_at_one():
    engine, gm, player = make_world()
    foe = content.cave_goblin.spawn(gm, 3, 1)
    foe.fighter.base_defence = 2
    foe.fighter.base_soak = 99  # soak swallows the whole damage roll
    start = foe.fighter.endurance

    seed = _seed_where(player.fighter.attack_bonus, 2,
                       lambda r: r.is_success and not r.is_crit)
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()

    assert foe.fighter.endurance == start - 1  # a landed blow always stings for 1


# --- Criticals --------------------------------------------------------------

def test_a_crit_hits_through_high_defence_and_opens_a_bleed():
    engine, gm, player = make_world()
    foe = content.cave_goblin.spawn(gm, 3, 1)
    foe.fighter.base_defence = 99  # only a natural 20 gets through
    start = foe.fighter.endurance

    seed = _seed_where(player.fighter.attack_bonus, 99, lambda r: r.is_crit)
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()

    assert foe.fighter.endurance < start  # the crit landed despite the Defence
    assert foe.fighter.bleed == CRIT_BLEED
    assert "CRITICAL" in engine.message_log.messages[-2].plain_text \
        or "CRITICAL" in last_message(engine)


# --- Incoming attacks: the foe rolls ----------------------------------------

def test_a_foe_hits_the_player_for_its_damage():
    engine, gm, player = make_world()
    foe = spawn_foe(gm, content.cave_goblin)
    foe.fighter.base_defence = 0
    start = player.fighter.endurance

    # Make the foe's attack land without a crit against the player's Defence.
    seed = _seed_where(foe.fighter.attack_bonus, player.fighter.defence,
                       lambda r: r.is_success and not r.is_crit)
    set_seed(seed)
    MeleeAction(foe, 1, 0).perform()  # foe at (1,1) strikes player at (2,1)

    assert player.fighter.endurance < start
    assert "endurance" in last_message(engine)


def test_a_heavy_foe_leaves_the_player_bleeding_on_a_hit():
    engine, gm, player = make_world()
    foe = spawn_foe(gm, content.warg)  # bleed_on_hit = 1

    seed = _seed_where(foe.fighter.attack_bonus, player.fighter.defence,
                       lambda r: r.is_success and not r.is_crit)
    set_seed(seed)
    MeleeAction(foe, 1, 0).perform()

    assert player.fighter.bleed == foe.fighter.bleed_on_hit


# --- Bleed status -----------------------------------------------------------

def test_bleed_ticks_down_and_drains_endurance():
    engine, gm, player = make_world()
    player.fighter.apply_bleed(2)
    start = player.fighter.endurance

    engine.handle_enemy_turns()  # one round: one bleed tick

    assert player.fighter.bleed == 1
    assert player.fighter.endurance == start - BLEED_DAMAGE
    assert "bleed" in last_message(engine).lower()


def test_bleed_stops_when_stacks_run_out():
    engine, gm, player = make_world()
    player.fighter.apply_bleed(1)
    engine.handle_enemy_turns()
    assert player.fighter.bleed == 0
    resting = player.fighter.endurance
    engine.handle_enemy_turns()  # no stacks left -> no further drain
    assert player.fighter.endurance == resting


# --- Enemy AI actually reaches the player (regression) ----------------------

def test_adjacent_foe_ai_strikes_the_player():
    """A foe's turn must route a bump into the player through to a melee.

    Regression: BumpAction gated melee on the target having an .ai, which the
    player never has, so enemy attacks were silently swallowed as Impossible.
    """
    engine, gm, player = make_world()
    foe = spawn_foe(gm, content.cave_goblin)  # adjacent at (1,1)
    foe.fighter.base_attack_bonus = 99  # unreachable -> the blow always lands
    start = player.fighter.endurance

    BumpAction(foe, 1, 0).perform()  # foe at (1,1) bumps player at (2,1)

    assert player.fighter.endurance < start  # the player took the hit
    assert "for" in last_message(engine)
