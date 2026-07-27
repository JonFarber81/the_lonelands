"""Tests for the full Far Shot (Ranged) tree and its new effect primitives
(ADR 0011, issue #75): Hunter's Mark (a mark status + bonus damage vs the mark),
Aimed Shot (a primed guaranteed Critical), Multishot / Arrow Storm (an arc shot),
Piercing Shot (a line shot), and Harrying Shot (fire-then-backstep).

Effect tests grant nodes directly (bypassing the buy gating, which
tests/test_perks.py covers) and drive real Actions against a headless
Engine/GameMap, pinning dice with ``set_seed`` where a specific face matters.
"""
from __future__ import annotations

import copy

from lonelands import content, perks, tile_types
from lonelands.actions import (
    HarryingShotAction,
    HuntersMarkAction,
    MeleeAction,
    MultishotAction,
    PiercingShotAction,
    RangedAttackAction,
    _ammo_stack,
)
from lonelands.dice import roll_check, set_seed
from lonelands.engine import Engine
from lonelands.exceptions import Impossible
from lonelands.game_map import GameMap

N = perks.ALL_NODES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_world():
    """A headless, fully-lit open floor with a Far Shot hero holding a bow."""
    player = content.make_player()
    engine = Engine(player)
    gm = GameMap(engine, 40, 12)
    gm.tiles[:] = tile_types.floor
    gm.visible[:] = True
    gm.explored[:] = True
    engine.game_map = gm
    player.place(4, 6, gm)
    player.hero.path_points = 30
    player.hero.commit_path("far_shot")
    arm(player)
    return engine, gm, player


def arm(player, arrows: int = 20):
    bow = copy.deepcopy(content.shortbow)
    player.equipment.toggle_equip(bow, add_message=False)
    quiver = copy.deepcopy(content.arrows)
    quiver.quantity = arrows
    player.inventory.add(quiver)
    return bow


def grant(hero, *node_ids):
    for nid in node_ids:
        hero.nodes[nid] = max(1, hero.nodes.get(nid, 0))


def spawn_foe(gm, x, y, endurance=200):
    foe = content.cave_goblin.spawn(gm, x, y)
    foe.fighter.base_defence = -100    # any non-fumble roll lands
    foe.fighter.base_soak = 0
    foe.fighter.max_endurance = endurance
    foe.fighter.endurance = endurance
    return foe


def _seed_no_fumble(mod, tn):
    """A seed whose next d20 is a plain success (not a natural 1)."""
    for seed in range(20000):
        set_seed(seed)
        r = roll_check(mod, tn)
        if r.is_success and not r.is_fumble and not r.is_crit:
            return seed
    raise AssertionError("no non-crit success seed found")


def last(engine):
    return engine.message_log.messages[-1].plain_text


# ---------------------------------------------------------------------------
# Tree shape — the two branches and their capstones (ADR 0011)
# ---------------------------------------------------------------------------
def test_far_shot_branches_and_capstones():
    far = perks.PATHS_BY_ID["far_shot"]
    assert set(far.branches) == {"sharpshooter", "volley"}
    caps = {n.id for n in far.nodes if n.capstone}
    assert caps == {"fs_deadeye", "fs_storm"}
    # Steady Aim is the shared root; both branch-heads hang off it.
    assert N["fs_aim"].parent is None
    assert N["fs_fletcher"].parent == "fs_aim"
    assert N["fs_footwork"].parent == "fs_aim"


# ---------------------------------------------------------------------------
# Hunter's Mark — a mark status + bonus damage vs the marked foe
# ---------------------------------------------------------------------------
def test_hunters_mark_adds_damage_on_a_shot_against_the_marked_foe():
    engine, gm, player = make_world()
    grant(player.hero, "fs_mark")
    foe = spawn_foe(gm, 10, 6)

    seed = _seed_no_fumble(player.fighter.ranged_attack_bonus, foe.fighter.defence)

    # Baseline: an unmarked shot.
    set_seed(seed)
    start = foe.fighter.endurance
    RangedAttackAction(player, foe).perform()
    base = start - foe.fighter.endurance

    # Same seed, but now the foe is marked: +3 damage.
    foe.fighter.endurance = start
    HuntersMarkAction(player, "fs_mark", foe).perform()
    assert foe.fighter.marked
    set_seed(seed)
    RangedAttackAction(player, foe).perform()
    marked = start - foe.fighter.endurance
    assert marked == base + N["fs_mark"].marked_damage


def test_hunters_mark_bonus_applies_in_melee_too():
    engine, gm, player = make_world()
    grant(player.hero, "fs_mark")
    foe = spawn_foe(gm, 5, 6)  # adjacent
    HuntersMarkAction(player, "fs_mark", foe).perform()
    seed = _seed_no_fumble(player.fighter.attack_bonus, foe.fighter.defence)
    set_seed(seed)
    start = foe.fighter.endurance
    MeleeAction(player, 1, 0).perform()
    assert start - foe.fighter.endurance >= N["fs_mark"].marked_damage


def test_hunters_mark_marks_only_one_foe_at_a_time():
    engine, gm, player = make_world()
    grant(player.hero, "fs_mark")
    a = spawn_foe(gm, 9, 6)
    b = spawn_foe(gm, 11, 6)
    HuntersMarkAction(player, "fs_mark", a).perform()
    assert a.fighter.marked and not b.fighter.marked
    player.hero._node_cooldowns.clear()                # skip the wait for the test
    HuntersMarkAction(player, "fs_mark", b).perform()
    assert b.fighter.marked and not a.fighter.marked   # the old mark is cleared


def test_hunters_mark_refuses_a_foe_beyond_reach():
    engine, gm, player = make_world()
    grant(player.hero, "fs_mark")
    reach = N["fs_mark"].active.reach
    foe = spawn_foe(gm, 4 + reach + 2, 6)
    try:
        HuntersMarkAction(player, "fs_mark", foe).perform()
        assert False, "expected Impossible"
    except Impossible:
        pass
    assert not foe.fighter.marked


# ---------------------------------------------------------------------------
# Aimed Shot — a primed guaranteed Critical
# ---------------------------------------------------------------------------
def test_aimed_shot_forces_a_critical_on_the_next_shot():
    engine, gm, player = make_world()
    grant(player.hero, "fs_aimed")
    foe = spawn_foe(gm, 10, 6)

    seed = _seed_no_fumble(player.fighter.ranged_attack_bonus, foe.fighter.defence)

    player.hero.activate_ability("fs_aimed")
    assert player.hero.aimed_shot
    set_seed(seed)
    RangedAttackAction(player, foe).perform()
    assert "CRITICAL shot" in last(engine)
    assert not player.hero.aimed_shot                  # the prime is spent
    assert player.hero.cooldown_left("fs_aimed") == N["fs_aimed"].active.cooldown


def test_aimed_shot_is_spent_by_one_shot_only():
    engine, gm, player = make_world()
    grant(player.hero, "fs_aimed")
    foe = spawn_foe(gm, 10, 6)
    player.hero.activate_ability("fs_aimed")
    set_seed(_seed_no_fumble(player.fighter.ranged_attack_bonus, foe.fighter.defence))
    RangedAttackAction(player, foe).perform()
    assert not player.hero.aimed_shot


# ---------------------------------------------------------------------------
# Multishot / Arrow Storm — an arc shot around the mark
# ---------------------------------------------------------------------------
def test_multishot_strikes_the_mark_and_foes_within_the_radius():
    engine, gm, player = make_world()
    grant(player.hero, "fs_multishot")
    center = spawn_foe(gm, 12, 6)
    near = spawn_foe(gm, 12, 7)     # within radius 1 of the centre
    far = spawn_foe(gm, 12, 9)      # two tiles away — spared
    quiver = _ammo_stack(player)
    before = quiver.quantity

    set_seed(3)
    MultishotAction(player, "fs_multishot", center).perform()
    assert center.fighter.endurance < center.fighter.max_endurance
    assert near.fighter.endurance < near.fighter.max_endurance
    assert far.fighter.endurance == far.fighter.max_endurance
    assert quiver.quantity == before - 1               # one draw, one arrow
    assert player.hero.cooldown_left("fs_multishot") == \
        N["fs_multishot"].active.cooldown


def test_arrow_storm_has_a_wider_radius_than_multishot():
    assert N["fs_storm"].active.radius > N["fs_multishot"].active.radius
    assert N["fs_storm"].active.kind == "arc_shot"


# ---------------------------------------------------------------------------
# Piercing Shot — a line shot through every foe on the ray
# ---------------------------------------------------------------------------
def test_piercing_shot_strikes_every_foe_on_the_line():
    engine, gm, player = make_world()
    grant(player.hero, "fs_pierce")
    player.place(4, 6, gm)
    on1 = spawn_foe(gm, 6, 6)       # on the ray
    on2 = spawn_foe(gm, 8, 6)       # further along the same ray
    off = spawn_foe(gm, 7, 8)       # off the line — spared

    set_seed(3)
    PiercingShotAction(player, "fs_pierce", on2).perform()
    assert on1.fighter.endurance < on1.fighter.max_endurance
    assert on2.fighter.endurance < on2.fighter.max_endurance
    assert off.fighter.endurance == off.fighter.max_endurance


# ---------------------------------------------------------------------------
# Harrying Shot — fire, then hop one tile straight back from the foe
# ---------------------------------------------------------------------------
def test_harrying_shot_hits_then_steps_the_hero_back():
    engine, gm, player = make_world()
    grant(player.hero, "fs_harry")
    player.place(6, 6, gm)
    foe = spawn_foe(gm, 9, 6)       # to the east

    set_seed(3)
    HarryingShotAction(player, "fs_harry", foe).perform()
    assert foe.fighter.endurance < foe.fighter.max_endurance
    assert (player.x, player.y) == (5, 6)              # one tile west, away from the foe


def test_harrying_shot_stays_put_when_the_backstep_is_blocked():
    engine, gm, player = make_world()
    grant(player.hero, "fs_harry")
    player.place(1, 6, gm)
    gm.tiles[0, 6] = tile_types.wall  # nowhere to fade to
    foe = spawn_foe(gm, 4, 6)
    set_seed(3)
    HarryingShotAction(player, "fs_harry", foe).perform()
    assert (player.x, player.y) == (1, 6)              # held ground; still fired
    assert foe.fighter.endurance < foe.fighter.max_endurance
