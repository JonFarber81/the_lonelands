"""Tests for the full Hidden Path (Stealth) tree and its new effect primitives
(ADR 0011, issue #77): Shadowstep/Disengage (dash blink), Poisoned Blade (Bleed
on a melee hit), Snare (a laid trap that hurts + roots), Pinning (root a foe),
and Vanish (the untargeted stealth-reset capstone).

The effect tests grant nodes directly (bypassing the buy gating, which
tests/test_perks.py already covers) and drive real Actions against a headless
Engine/GameMap, pinning dice with ``set_seed`` where a specific d20 face matters.
"""
from __future__ import annotations

from lonelands import content, perks, tile_types
from lonelands.actions import (
    MeleeAction,
    MovementAction,
    PinningAction,
    ShadowstepAction,
    SnareAction,
    Trap,
    _spring_trap,
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
    """A headless world with an open, fully-lit floor so blinks and traps have
    somewhere legal to land."""
    player = content.make_player()
    engine = Engine(player)
    gm = GameMap(engine, 20, 10)
    gm.tiles[:] = tile_types.floor
    gm.visible[:] = True
    gm.explored[:] = True
    engine.game_map = gm
    player.place(4, 5, gm)
    player.hero.path_points = 20
    player.hero.commit_path("hidden_path")
    return engine, gm, player


def grant(hero, *node_ids):
    """Own each node at rank 1 (bypassing gating) so a deed/passive is live."""
    for nid in node_ids:
        hero.nodes[nid] = max(1, hero.nodes.get(nid, 0))


def spawn_foe(gm, x, y, endurance=100):
    foe = content.cave_goblin.spawn(gm, x, y)
    foe.fighter.base_defence = 2      # trivial Defence -> the hero always hits
    foe.fighter.base_soak = 0
    foe.fighter.max_endurance = endurance
    foe.fighter.endurance = endurance
    return foe


def _seed_where(mod, tn, predicate):
    for seed in range(10000):
        set_seed(seed)
        if predicate(roll_check(mod, tn)):
            return seed
    raise AssertionError("no seed satisfied the predicate")


# ---------------------------------------------------------------------------
# Tree shape — a trunk forking into Assassin (burst) and Trapper (control)
# ---------------------------------------------------------------------------
def test_hidden_path_has_assassin_and_trapper_branches():
    path = perks.PATHS_BY_ID["hidden_path"]
    assert set(path.branches) == {"assassin", "trapper"}
    branches = {n.branch for n in path.nodes}
    assert {"trunk", "assassin", "trapper"} <= branches
    # Each branch is tipped by a capstone.
    caps = {n.branch for n in path.nodes if n.capstone}
    assert caps == {"assassin", "trapper"}


def test_hidden_path_actives_carry_their_primitive_kinds():
    kinds = {nid: N[nid].active.kind for nid in
             ("hp_shadowstep", "hp_snare", "hp_pinning", "hp_disengage", "hp_vanish")}
    assert kinds == {
        "hp_shadowstep": "dash", "hp_snare": "place_tile",
        "hp_pinning": "root", "hp_disengage": "dash", "hp_vanish": "vanish",
    }
    # dash/place-tile/root are targeted; vanish is not.
    assert N["hp_shadowstep"].active.targeted
    assert N["hp_snare"].active.targeted
    assert N["hp_pinning"].active.targeted
    assert not N["hp_vanish"].active.targeted


def test_deathblow_stacks_onto_ambush_damage():
    engine, gm, player = make_world()
    grant(player.hero, "hp_ambush", "hp_poison", "hp_deathblow")
    # Ambush (+2) and Deathblow (+6) both feed the shared ambush-damage sum.
    assert player.hero.node_bonus("ambush_bonus_damage") == 8


# ---------------------------------------------------------------------------
# Poisoned Blade — a hero melee hit leaves the foe bleeding
# ---------------------------------------------------------------------------
def test_poisoned_blade_bleeds_the_foe_on_a_hit():
    engine, gm, player = make_world()
    grant(player.hero, "hp_poison")           # melee hits apply Bleed
    foe = spawn_foe(gm, 5, 5, endurance=40)
    foe.fighter.endurance = 20                # not fresh -> no ambush muddying it
    seed = _seed_where(player.fighter.attack_bonus, 2,
                       lambda r: r.is_success and not r.is_crit)
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()
    assert foe.fighter.bleed >= 1             # Poisoned Blade opened a Bleed


def test_without_poisoned_blade_a_plain_hit_does_not_bleed():
    engine, gm, player = make_world()
    foe = spawn_foe(gm, 5, 5, endurance=40)
    foe.fighter.endurance = 20
    seed = _seed_where(player.fighter.attack_bonus, 2,
                       lambda r: r.is_success and not r.is_crit)
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()
    assert foe.fighter.bleed == 0


# ---------------------------------------------------------------------------
# Shadowstep — blink to a tile, then the next strike is a sure ambush
# ---------------------------------------------------------------------------
def test_shadowstep_blinks_and_sets_up_an_ambush():
    engine, gm, player = make_world()
    grant(player.hero, "hp_shadowstep")
    start = (player.x, player.y)
    ShadowstepAction(player, "hp_shadowstep", (6, 5)).perform()
    assert (player.x, player.y) == (6, 5) != start
    assert player.hero.ambush_primed
    assert player.hero.cooldown_left("hp_shadowstep") == N["hp_shadowstep"].active.cooldown


def test_a_primed_ambush_fires_even_on_a_wounded_foe_then_clears():
    engine, gm, player = make_world()
    grant(player.hero, "hp_ambush", "hp_shadowstep")
    foe = spawn_foe(gm, 6, 5, endurance=40)
    foe.fighter.endurance = 15                # wounded: no *fresh-opener* ambush
    # Blink adjacent and prime the unseen strike.
    ShadowstepAction(player, "hp_shadowstep", (5, 5)).perform()
    assert player.hero.ambush_primed
    seed = _seed_where(player.fighter.attack_bonus, 2,
                       lambda r: r.is_success and not r.is_crit)
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()
    assert "shadows" in engine.message_log.messages[-1].plain_text.lower()
    assert not player.hero.ambush_primed      # the primed ambush was spent


def test_disengage_blinks_without_priming_an_ambush():
    engine, gm, player = make_world()
    grant(player.hero, "hp_disengage")
    ShadowstepAction(player, "hp_disengage", (2, 5)).perform()
    assert (player.x, player.y) == (2, 5)
    assert not player.hero.ambush_primed      # a pure escape, no ambush set up


def test_shadowstep_refuses_a_tile_out_of_reach():
    engine, gm, player = make_world()
    grant(player.hero, "hp_shadowstep")       # reach 4
    far = (player.x + 6, player.y)
    try:
        ShadowstepAction(player, "hp_shadowstep", far).perform()
        assert False, "expected Impossible"
    except Impossible:
        pass
    assert player.hero.cooldown_left("hp_shadowstep") == 0  # no turn spent


# ---------------------------------------------------------------------------
# Snare — a laid trap springs on the first foe onto it
# ---------------------------------------------------------------------------
def test_snare_lays_a_trap_on_a_chosen_tile():
    engine, gm, player = make_world()
    grant(player.hero, "hp_snare")
    SnareAction(player, "hp_snare", (6, 5)).perform()
    assert (6, 5) in gm.traps
    assert player.hero.cooldown_left("hp_snare") == N["hp_snare"].active.cooldown


def test_a_foe_stepping_onto_a_snare_is_hurt_and_rooted():
    engine, gm, player = make_world()
    gm.traps[(6, 5)] = Trap(6, 5, damage="1d6", root_rounds=2)
    foe = spawn_foe(gm, 7, 5, endurance=40)
    before = foe.fighter.endurance
    MovementAction(foe, -1, 0).perform()      # step west, onto the snare
    assert (foe.x, foe.y) == (6, 5)
    assert foe.fighter.endurance < before     # the snare bit
    assert foe.fighter.is_rooted              # ...and held it fast
    assert (6, 5) not in gm.traps             # a snare is spent when sprung


def test_the_hero_does_not_spring_their_own_snare():
    engine, gm, player = make_world()
    gm.traps[(5, 5)] = Trap(5, 5)
    before = player.fighter.endurance
    MovementAction(player, 1, 0).perform()    # the hero walks onto the tile
    assert (5, 5) in gm.traps                  # still armed
    assert player.fighter.endurance == before


# ---------------------------------------------------------------------------
# Pinning + the root status — a rooted foe cannot move
# ---------------------------------------------------------------------------
def test_pinning_roots_a_foe_in_sight():
    engine, gm, player = make_world()
    grant(player.hero, "hp_pinning")
    foe = spawn_foe(gm, 7, 5)
    PinningAction(player, "hp_pinning", foe).perform()
    assert foe.fighter.is_rooted
    assert player.hero.cooldown_left("hp_pinning") == N["hp_pinning"].active.cooldown


def test_a_rooted_foe_cannot_move_and_the_root_wears_off():
    engine, gm, player = make_world()
    foe = spawn_foe(gm, 10, 5)
    foe.fighter.apply_root(2)
    # Held fast: a step is Impossible while rooted.
    try:
        MovementAction(foe, -1, 0).perform()
        assert False, "expected Impossible"
    except Impossible:
        pass
    assert (foe.x, foe.y) == (10, 5)
    foe.fighter.tick_root()
    foe.fighter.tick_root()
    assert not foe.fighter.is_rooted
    MovementAction(foe, -1, 0).perform()      # free to move now
    assert (foe.x, foe.y) == (9, 5)


def test_engine_ticks_a_root_down_once_per_round():
    engine, gm, player = make_world()
    foe = spawn_foe(gm, 10, 5)
    foe.ai = None                             # keep the round quiet and deterministic
    foe.fighter.apply_root(1)
    engine.handle_enemy_turns()               # end-of-phase tick clears a 1-round root
    assert not foe.fighter.is_rooted


# ---------------------------------------------------------------------------
# Vanish — the untargeted capstone: sure ambush + readied deeds
# ---------------------------------------------------------------------------
def test_vanish_primes_a_sure_ambush_and_readies_every_deed():
    engine, gm, player = make_world()
    hero = player.hero
    grant(hero, "hp_shadowstep", "hp_vanish")
    hero._node_cooldowns["hp_shadowstep"] = 3   # a deed mid-cooldown
    msg = hero.activate_ability("hp_vanish")
    assert msg is not None
    assert hero.ambush_primed
    assert hero.cooldown_left("hp_shadowstep") == 0     # readied by Vanish
    assert hero.cooldown_left("hp_vanish") == N["hp_vanish"].active.cooldown
