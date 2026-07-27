"""Tests for the Hero character sheet: attribute-derived combat numbers and the
XP/level advancement curve."""
from __future__ import annotations

from lonelands import character, content
from lonelands.components.fighter import Fighter
from lonelands.components.hero import Hero
from lonelands.entity import Actor


def _hero_actor(brawn=3, wits=2, will=1, endurance=20):
    """A bare hero+fighter Actor, unplaced (so levelling stays message-free)."""
    return Actor(
        char="@", color=(255, 255, 255), name="Test",
        fighter=Fighter(endurance=endurance, defence=10, attack_bonus=1, damage=1),
        hero=Hero(attributes={"Brawn": brawn, "Wits": wits, "Will": will}),
    )


# --- Attributes feed the derived combat numbers -----------------------------

def test_brawn_adds_to_the_attack_bonus():
    actor = _hero_actor(brawn=3)
    # base_attack_bonus (1) + Brawn (3) + level to-hit (0 at level 1)
    assert actor.fighter.attack_bonus == 1 + 3


def test_wits_adds_to_defence():
    actor = _hero_actor(wits=2)
    assert actor.fighter.defence == 10 + 2


def test_modifier_defaults_to_zero_for_unknown_attribute():
    hero = _hero_actor().hero
    assert hero.modifier("Luck") == 0


# --- The level curve --------------------------------------------------------

def test_a_fresh_hero_starts_at_level_one_pathless_with_no_points():
    hero = _hero_actor().hero
    assert hero.level == 1
    assert hero.xp == 0
    assert hero.path is None          # level 1 is pathless (ADR 0011)
    assert hero.path_points == 0


def test_enough_xp_levels_up_and_grants_hp():
    actor = _hero_actor(endurance=20)
    hero = actor.hero
    hero.add_xp(character.xp_to_next(1))
    assert hero.level == 2
    assert hero.xp == 0  # spent exactly to the threshold
    assert actor.fighter.max_endurance == 20 + character.HP_PER_LEVEL
    assert actor.fighter.endurance == 20 + character.HP_PER_LEVEL  # healed by the gain


def test_leftover_xp_carries_toward_the_next_level():
    hero = _hero_actor().hero
    hero.add_xp(character.xp_to_next(1) + 3)
    assert hero.level == 2
    assert hero.xp == 3


def test_a_big_haul_levels_multiple_times():
    hero = _hero_actor().hero
    total = character.xp_to_next(1) + character.xp_to_next(2) + character.xp_to_next(3)
    hero.add_xp(total)
    assert hero.level == 4
    assert hero.xp == 0


def test_periodic_to_hit_lands_on_schedule():
    actor = _hero_actor(brawn=3)
    hero = actor.hero
    base_attack = actor.fighter.attack_bonus
    # Advance to exactly the first TOHIT_EVERY level.
    for lvl in range(1, character.TOHIT_EVERY + 1):
        hero.add_xp(character.xp_to_next(hero.level))
    assert hero.level == character.TOHIT_EVERY + 1
    assert actor.fighter.attack_bonus == base_attack + 1


def test_path_points_accrue_one_per_level_from_level_two():
    hero = _hero_actor().hero
    # Level 1 is pathless: no point yet.
    assert hero.path_points == 0
    hero.add_xp(character.xp_to_next(1))          # -> level 2: first point
    assert hero.level == 2
    assert hero.path_points == 1
    hero.add_xp(character.xp_to_next(2))          # -> level 3: one more
    assert hero.level == 3
    assert hero.path_points == 2


def test_add_xp_ignores_nonpositive():
    hero = _hero_actor().hero
    hero.add_xp(0)
    hero.add_xp(-5)
    assert hero.level == 1
    assert hero.xp_total == 0


# --- The active hotbar (Phase 2, ADR 0011) ----------------------------------

def test_hotbar_lists_owned_actives_in_declaration_order():
    hero = _hero_actor().hero
    hero.path = "long_watch"
    # Own two actives (plus a passive), "bought" in reverse declaration order.
    hero.nodes = {"lw_wrath": 1, "lw_wind": 1, "lw_endure": 3}
    ids = [n.id for n in hero.hotbar()]
    # Declaration order (lw_wind before lw_wrath); the passive is not on the bar.
    assert ids == ["lw_wind", "lw_wrath"]


def test_hotbar_caps_at_the_slot_count():
    hero = _hero_actor().hero
    hero.path = "long_watch"
    hero.nodes = {"lw_wind": 1, "lw_wrath": 1, "lw_hold": 1}
    assert len(hero.hotbar(size=2)) == 2


def test_hotbar_is_empty_while_pathless():
    hero = _hero_actor().hero
    assert hero.hotbar() == []


# --- The authored player starts sane ---------------------------------------

def test_make_player_uses_the_new_attribute_names():
    hero = content.make_player().hero
    assert set(hero.attributes) == set(character.ATTRIBUTES)
    assert not hasattr(hero, "skills")
    assert not hasattr(hero, "hope")
