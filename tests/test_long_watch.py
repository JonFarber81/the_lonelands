"""Tests for the full Long Watch (Tank) tree and its new effect primitives
(ADR 0011, issue #76): Charge (a dash-to-foe strike), Sweeping Blow (an adjacent
multi-target), Thornguard (on-being-hit reflect), Immovable/Unbroken (root
immunity), Executioner (a context-conditional vs a wounded foe), Athelas (cleanse
+ heal-over-time), and Rally (a low-Endurance to-hit trigger).

Effect tests grant nodes directly (bypassing the buy gating, which
tests/test_perks.py covers) and drive real Actions against a headless
Engine/GameMap, pinning dice with ``set_seed`` where a face matters.
"""
from __future__ import annotations

from lonelands import content, perks, tile_types
from lonelands.actions import (
    ChargeAction,
    MeleeAction,
    SweepAction,
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
    """A headless, fully-lit open floor with a committed Long Watch hero."""
    player = content.make_player()
    engine = Engine(player)
    gm = GameMap(engine, 24, 12)
    gm.tiles[:] = tile_types.floor
    gm.visible[:] = True
    gm.explored[:] = True
    engine.game_map = gm
    player.place(5, 6, gm)
    player.hero.path_points = 30
    player.hero.commit_path("long_watch")
    return engine, gm, player


def grant(hero, *node_ids):
    for nid in node_ids:
        hero.nodes[nid] = max(1, hero.nodes.get(nid, 0))


def spawn_foe(gm, x, y, endurance=200, defence=-100):
    foe = content.cave_goblin.spawn(gm, x, y)
    foe.fighter.base_defence = defence
    foe.fighter.base_soak = 0
    foe.fighter.max_endurance = endurance
    foe.fighter.endurance = endurance
    return foe


def _seed_where(mod, tn, predicate):
    for seed in range(20000):
        set_seed(seed)
        if predicate(roll_check(mod, tn)):
            return seed
    raise AssertionError("no seed satisfied the predicate")


# ---------------------------------------------------------------------------
# Tree shape — the two branches and their capstones (ADR 0011)
# ---------------------------------------------------------------------------
def test_long_watch_branches_and_capstones():
    lw = perks.PATHS_BY_ID["long_watch"]
    assert set(lw.branches) == {"warden", "reaver"}
    caps = {n.id for n in lw.nodes if n.capstone}
    assert caps == {"lw_unbroken", "lw_reaver"}
    # Steady Endurance is the single branching root; the sustain deeds are the
    # childless trunk stem above it.
    roots = [n.id for n in lw.nodes if n.parent is None]
    assert set(roots) == {"lw_wind", "lw_rally", "lw_athelas", "lw_endure"}
    assert N["lw_soak"].parent == "lw_endure"           # Warden head
    assert N["lw_hone"].parent == "lw_endure"           # Reaver head


# ---------------------------------------------------------------------------
# Charge — rush a foe and strike with bonus damage (a reused dash)
# ---------------------------------------------------------------------------
def test_charge_closes_the_gap_and_strikes():
    engine, gm, player = make_world()
    grant(player.hero, "lw_charge")
    foe = spawn_foe(gm, 10, 6)                           # five tiles east
    set_seed(_seed_where(player.fighter.attack_bonus, foe.fighter.defence,
                         lambda r: r.is_success and not r.is_fumble))
    ChargeAction(player, "lw_charge", foe).perform()
    assert max(abs(player.x - foe.x), abs(player.y - foe.y)) == 1  # now adjacent
    assert foe.fighter.endurance < foe.fighter.max_endurance
    assert player.hero.cooldown_left("lw_charge") == N["lw_charge"].active.cooldown


def test_charge_refuses_a_foe_beyond_reach():
    engine, gm, player = make_world()
    grant(player.hero, "lw_charge")
    reach = N["lw_charge"].active.reach
    foe = spawn_foe(gm, 5 + reach + 3, 6)
    try:
        ChargeAction(player, "lw_charge", foe).perform()
        assert False, "expected Impossible"
    except Impossible:
        pass
    assert player.x == 5                                 # did not move


def test_charge_lends_its_rush_to_the_blow():
    # Same seed, same foe placement: a Charge strike out-damages a plain melee by
    # its bonus dice (both land adjacent, so only the +magnitude differs).
    engine, gm, player = make_world()
    grant(player.hero, "lw_charge")
    foe = spawn_foe(gm, 6, 6)                            # already adjacent (no move)
    seed = _seed_where(player.fighter.attack_bonus, foe.fighter.defence,
                       lambda r: r.is_success and not r.is_crit and not r.is_fumble)
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()
    plain = foe.fighter.max_endurance - foe.fighter.endurance

    foe.fighter.endurance = foe.fighter.max_endurance
    set_seed(seed)
    ChargeAction(player, "lw_charge", foe).perform()
    charged = foe.fighter.max_endurance - foe.fighter.endurance
    assert charged > plain                               # the +1d6 rush landed


# ---------------------------------------------------------------------------
# Sweeping Blow — one arc against every adjacent foe
# ---------------------------------------------------------------------------
def test_sweeping_blow_strikes_every_adjacent_foe():
    engine, gm, player = make_world()
    grant(player.hero, "lw_sweep")
    near = [spawn_foe(gm, 4, 6), spawn_foe(gm, 6, 6), spawn_foe(gm, 5, 5)]
    far = spawn_foe(gm, 8, 6)                            # not adjacent — spared
    set_seed(7)
    SweepAction(player, "lw_sweep").perform()
    for foe in near:
        assert foe.fighter.endurance < foe.fighter.max_endurance
    assert far.fighter.endurance == far.fighter.max_endurance
    assert player.hero.cooldown_left("lw_sweep") == N["lw_sweep"].active.cooldown


def test_sweeping_blow_needs_a_foe_in_reach():
    engine, gm, player = make_world()
    grant(player.hero, "lw_sweep")
    spawn_foe(gm, 9, 6)                                  # far off
    try:
        SweepAction(player, "lw_sweep").perform()
        assert False, "expected Impossible"
    except Impossible:
        pass


# ---------------------------------------------------------------------------
# Thornguard — a foe is pricked for landing a melee blow on the hero
# ---------------------------------------------------------------------------
def test_thornguard_bites_a_foe_that_hits_the_hero():
    engine, gm, player = make_world()
    grant(player.hero, "lw_thorn")
    player.fighter.max_endurance = 200
    player.fighter.endurance = 200
    foe = spawn_foe(gm, 6, 6, defence=2)                 # adjacent, east
    # The foe swings and lands: it should take Thornguard's bite in return.
    seed = _seed_where(foe.fighter.attack_bonus, player.fighter.defence,
                       lambda r: r.is_success and not r.is_crit)
    set_seed(seed)
    MeleeAction(foe, -1, 0).perform()                    # foe strikes the hero
    assert foe.fighter.endurance == foe.fighter.max_endurance - N["lw_thorn"].thorns_damage


def test_thornguard_is_silent_on_a_miss():
    engine, gm, player = make_world()
    grant(player.hero, "lw_thorn")
    foe = spawn_foe(gm, 6, 6, defence=2)
    seed = _seed_where(foe.fighter.attack_bonus, player.fighter.defence,
                       lambda r: r.is_fumble)
    set_seed(seed)
    MeleeAction(foe, -1, 0).perform()                    # a swing that misses
    assert foe.fighter.endurance == foe.fighter.max_endurance   # no bite on a miss


# ---------------------------------------------------------------------------
# Immovable / Unbroken — the hero cannot be held fast
# ---------------------------------------------------------------------------
def test_immovable_shrugs_off_a_root():
    engine, gm, player = make_world()
    grant(player.hero, "lw_immovable")
    assert player.fighter.root_immune
    player.fighter.apply_root(3)
    assert not player.fighter.is_rooted                  # the hold never takes

    # A plain hero (no node) is rooted as usual.
    _, _, plain = make_world()
    plain.fighter.apply_root(3)
    assert plain.fighter.is_rooted


# ---------------------------------------------------------------------------
# Executioner — bonus melee damage to a foe under a third of its Endurance
# ---------------------------------------------------------------------------
def test_executioner_adds_damage_only_to_a_wounded_foe():
    engine, gm, player = make_world()
    grant(player.hero, "lw_execute")
    foe = spawn_foe(gm, 6, 6, endurance=90)
    seed = _seed_where(player.fighter.attack_bonus, foe.fighter.defence,
                       lambda r: r.is_success and not r.is_crit and not r.is_fumble)

    # Healthy foe: no Executioner bonus.
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()
    healthy = 90 - foe.fighter.endurance

    # Wounded to under a third: the finishing blow lands +4.
    foe.fighter.endurance = 20                           # 20/90 < 1/3
    set_seed(seed)
    start = foe.fighter.endurance
    MeleeAction(player, 1, 0).perform()
    wounded = start - foe.fighter.endurance
    assert wounded == healthy + N["lw_execute"].execute_damage


# ---------------------------------------------------------------------------
# Athelas — cleanse Bleed and knit Endurance over several rounds
# ---------------------------------------------------------------------------
def test_athelas_cleanses_bleed_and_heals_over_time():
    engine, gm, player = make_world()
    grant(player.hero, "lw_athelas")
    f = player.fighter
    f.max_endurance = 60
    f.endurance = 30
    f.apply_bleed(4)

    player.hero.activate_ability("lw_athelas")
    assert f.bleed == 0                                  # cleansed at once
    assert f.regen_rounds == N["lw_athelas"].active.duration

    before = f.endurance
    healed = f.tick_regen()
    assert healed >= 1                                   # a round of knitting
    assert f.endurance == before + healed
    assert f.regen_rounds == N["lw_athelas"].active.duration - 1


def test_athelas_regen_ticks_through_the_engine_round():
    engine, gm, player = make_world()
    grant(player.hero, "lw_athelas")
    f = player.fighter
    f.max_endurance = 60
    f.endurance = 30
    player.hero.activate_ability("lw_athelas")
    before = f.endurance
    engine.handle_enemy_turns()                          # a full round elapses
    assert f.endurance > before
    assert any("Athelas" in m.plain_text for m in engine.message_log.messages)


# ---------------------------------------------------------------------------
# Rally — +to-hit while at or below half Endurance
# ---------------------------------------------------------------------------
def test_rally_adds_to_hit_only_while_badly_wounded():
    engine, gm, player = make_world()
    grant(player.hero, "lw_rally")
    f = player.fighter
    f.max_endurance = 40
    f.endurance = 40
    healthy = f.attack_bonus
    f.endurance = 18                                     # below half
    assert f.attack_bonus == healthy + N["lw_rally"].rally_atk_bonus
