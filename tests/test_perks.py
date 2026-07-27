"""Tests for Paths & nodes — the committed skill-tree model (ADR 0011, #73).

Two layers:
  * unit tests on the data model + Hero commitment/spend/gating (pathless L1,
    commit-at-L2, point income, ranks, the points-in-Path tier gate, parent-
    edges, capstone gating);
  * end-to-end tests that drive a real MeleeAction against a real Engine/GameMap
    (both construct headless), pinning dice with `set_seed` and scanning for a
    seed that yields a wanted d20 face — the same technique tests/test_combat.py
    uses — to prove one PASSIVE and one ACTIVE node are live in play.
"""
from __future__ import annotations

from lonelands import character, content, perks
from lonelands.actions import ActivateAbilityAction, MeleeAction
from lonelands.components.fighter import Fighter
from lonelands.components.hero import Hero
from lonelands.dice import roll_check, set_seed
from lonelands.engine import Engine
from lonelands.entity import Actor
from lonelands.game_map import GameMap


# ---------------------------------------------------------------------------
# Helpers (mirrors test_hero._hero_actor / test_combat.make_world)
# ---------------------------------------------------------------------------
def _hero_actor(brawn=3, wits=2, will=1, endurance=20, path_points=0, path=None):
    actor = Actor(
        char="@", color=(255, 255, 255), name="Test",
        fighter=Fighter(endurance=endurance, defence=10, attack_bonus=1, damage=1),
        hero=Hero(attributes={"Brawn": brawn, "Wits": wits, "Will": will}),
    )
    actor.hero.path_points = path_points
    if path is not None:
        actor.hero.commit_path(path)
    return actor


def make_world():
    player = content.make_player()
    engine = Engine(player)
    gm = GameMap(engine, 10, 10)
    engine.game_map = gm
    player.place(2, 1, gm)
    return engine, gm, player


def _seed_where(mod, tn, predicate):
    for seed in range(10000):
        set_seed(seed)
        if predicate(roll_check(mod, tn)):
            return seed
    raise AssertionError("no seed satisfied the predicate")


def _buy_all(hero, *node_ids):
    """Buy each node id in order, asserting each purchase succeeds. Useful for
    walking a branch down to a capstone."""
    for nid in node_ids:
        assert hero.buy_node(N[nid]), f"could not buy {nid}"


N = perks.ALL_NODES


# ---------------------------------------------------------------------------
# Data model sanity — three Paths, each a trunk forking into two branches
# ---------------------------------------------------------------------------
def test_three_paths_each_a_trunk_and_two_branches():
    assert len(perks.PATHS) == 3
    ids = {p.id for p in perks.PATHS}
    assert ids == {"long_watch", "far_shot", "hidden_path"}
    for path in perks.PATHS:
        assert len(path.branches) == 2                 # exactly two branches
        branch_ids = set(path.branches) | {"trunk"}
        # Every node sits in the trunk or one of the declared branches.
        assert all(n.branch in branch_ids for n in path.nodes)
        # At least one trunk root and at least one capstone.
        assert any(n.branch == "trunk" and n.tier == 1 for n in path.nodes)
        assert any(n.capstone for n in path.nodes)


def test_all_nodes_lookup_is_complete_and_unique():
    flat = [n for path in perks.PATHS for n in path.nodes]
    assert len(N) == len(flat)
    assert len(N) == len({n.id for n in flat})


def test_capstones_cost_two_nodes_cost_one():
    for node in N.values():
        assert node.cost == (2 if node.capstone else 1)


def test_parent_edges_point_at_real_nodes_in_the_same_path():
    for node in N.values():
        if node.parent is not None:
            assert node.parent in N
            assert N[node.parent].path == node.path


# ---------------------------------------------------------------------------
# Pathless level 1 → commit at level 2 (permanent, no cross-Path buys)
# ---------------------------------------------------------------------------
def test_a_pathless_hero_can_buy_nothing():
    hero = _hero_actor(path_points=5).hero
    assert hero.path is None
    assert not hero.can_buy(N["lw_endure"])
    assert not hero.buy_node(N["lw_endure"])
    assert hero.path_points == 5                        # nothing spent


def test_commit_is_one_time_and_permanent():
    hero = _hero_actor(path_points=5).hero
    assert hero.commit_path("long_watch")
    assert hero.path == "long_watch"
    # A second commit — to any Path, even the same one — is refused.
    assert not hero.commit_path("far_shot")
    assert not hero.commit_path("long_watch")
    assert hero.path == "long_watch"


def test_commit_rejects_an_unknown_path():
    hero = _hero_actor(path_points=5).hero
    assert not hero.commit_path("kindled_heart")        # deferred; not a Path now
    assert hero.path is None


def test_buys_outside_the_committed_path_are_rejected():
    hero = _hero_actor(path_points=5, path="long_watch").hero
    assert not hero.can_buy(N["fs_aim"])                # a Far Shot node
    assert not hero.buy_node(N["fs_aim"])
    assert not hero.has_node("fs_aim")
    # ...but a node in the committed Path is fine.
    assert hero.buy_node(N["lw_endure"])


# ---------------------------------------------------------------------------
# Point income — pathless L1, then 1 Path point per level from level 2
# ---------------------------------------------------------------------------
def test_level_one_is_pathless_with_no_points():
    hero = _hero_actor().hero
    assert hero.level == 1
    assert hero.path is None
    assert hero.path_points == 0


def test_one_path_point_per_level_from_level_two():
    hero = _hero_actor().hero
    hero.add_xp(character.xp_to_next(1))                # -> level 2
    assert hero.level == 2
    assert hero.path_points == 1                        # first point at level 2
    hero.add_xp(character.xp_to_next(2))                # -> level 3
    assert hero.level == 3
    assert hero.path_points == 2                        # one more each level


# ---------------------------------------------------------------------------
# Rank purchase — passives are rankable, actives one-and-done
# ---------------------------------------------------------------------------
def test_a_rankable_passive_buys_up_to_its_cap_and_scales():
    actor = _hero_actor(path_points=9, path="long_watch")
    hero = actor.hero
    node = N["lw_endure"]                               # +4 max Endurance per rank, cap 3
    assert node.max_rank == 3
    start = actor.fighter.max_endurance
    _buy_all(hero, "lw_endure", "lw_endure", "lw_endure")
    assert hero.rank_of("lw_endure") == 3
    assert actor.fighter.max_endurance == start + 12    # +4 × 3 ranks
    # A fourth rank is refused; nothing is charged.
    pts = hero.path_points
    assert not hero.can_buy(node)
    assert not hero.buy_node(node)
    assert hero.path_points == pts


def test_an_active_is_one_and_done():
    hero = _hero_actor(path_points=5, path="long_watch").hero
    wind = N["lw_wind"]                                 # Second Wind: an active
    assert wind.max_rank == 1
    assert hero.buy_node(wind)
    assert not hero.can_buy(wind)                       # cannot buy a second rank
    assert hero.rank_of("lw_wind") == 1


# ---------------------------------------------------------------------------
# Points-in-Path tier gate (Diablo-2 style) + parent-edges
# ---------------------------------------------------------------------------
def test_a_deeper_tier_is_gated_by_points_spent_in_the_path():
    hero = _hero_actor(path_points=9, path="far_shot").hero
    fletcher = N["fs_fletcher"]                         # tier 2, parent fs_aim
    assert perks.points_for_tier(2) == 2
    # One point in Path (fs_aim rank 1): parent owned, but the tier gate isn't met.
    assert hero.buy_node(N["fs_aim"])
    assert hero.points_in_path == 1
    assert not hero.can_buy(fletcher)                   # needs 2 points in Path
    # A second point reaches the gate; now the tier-2 node is buyable.
    assert hero.buy_node(N["fs_aim"])
    assert hero.points_in_path == 2
    assert hero.can_buy(fletcher)
    assert hero.buy_node(fletcher)


def test_a_node_needs_its_parent_owned_even_past_the_tier_gate():
    hero = _hero_actor(path_points=9, path="hidden_path").hero
    # Spend points in the trunk so the tier gate is satisfied with points to spare.
    _buy_all(hero, "hp_stealth", "hp_ambush", "hp_evasion")
    assert hero.points_in_path == 3
    deathblow = N["hp_deathblow"]                       # capstone, parent hp_poison
    # Even with points to spare, the capstone stays locked until its parent chain
    # (Ambush -> Poisoned Blade) is owned.
    assert not hero.can_buy(deathblow)
    assert hero.buy_node(N["hp_poison"])               # the capstone's parent
    assert hero.has_node("hp_poison")


# ---------------------------------------------------------------------------
# Capstone gating — deep tier + parent + cost 2
# ---------------------------------------------------------------------------
def test_capstone_gated_by_points_in_path_and_its_parent():
    hero = _hero_actor(path_points=12, path="far_shot").hero
    deadeye = N["fs_deadeye"]                           # tier 3, cost 2, parent fs_fletcher
    assert deadeye.capstone and deadeye.cost == 2
    assert perks.points_for_tier(3) == 4
    _buy_all(hero, "fs_aim", "fs_aim", "fs_fletcher")   # 3 points in Path
    assert not hero.can_buy(deadeye)                    # short of the tier-3 gate (4)
    assert hero.buy_node(N["fs_fletcher"])             # 4 points in Path now
    assert hero.can_buy(deadeye)
    assert hero.buy_node(deadeye)
    assert hero.has_node("fs_deadeye")


# ---------------------------------------------------------------------------
# Path-point accounting
# ---------------------------------------------------------------------------
def test_buying_deducts_cost_and_cannot_overspend():
    hero = _hero_actor(path_points=1, path="long_watch").hero
    assert hero.buy_node(N["lw_endure"])               # cost 1
    assert hero.path_points == 0
    # Broke: even a valid, unlocked node cannot be bought.
    assert not hero.can_buy(N["lw_wind"])
    assert not hero.buy_node(N["lw_wind"])
    assert not hero.has_node("lw_wind")


def test_capstone_costs_two_points():
    hero = _hero_actor(path_points=1, path="hidden_path").hero
    # A capstone with only 1 point banked is unaffordable regardless of gating.
    assert N["hp_deathblow"].cost == 2
    assert hero.path_points < N["hp_deathblow"].cost


# ---------------------------------------------------------------------------
# PASSIVE nodes change real combat numbers (scaled by rank)
# ---------------------------------------------------------------------------
def test_iron_skin_raises_soak_by_one_per_rank():
    actor = _hero_actor(path_points=9, path="long_watch")
    hero = actor.hero
    before = actor.fighter.soak
    _buy_all(hero, "lw_endure", "lw_endure")            # unlock tier 2 + parent
    _buy_all(hero, "lw_soak", "lw_soak")               # +1 Soak × 2 ranks
    assert hero.rank_of("lw_soak") == 2
    assert actor.fighter.soak == before + 2


def test_honed_edge_raises_attack_bonus():
    actor = _hero_actor(brawn=3, path_points=9, path="long_watch")
    hero = actor.hero
    _buy_all(hero, "lw_endure", "lw_endure")            # unlock tier 2 + parent
    before = actor.fighter.attack_bonus
    assert hero.buy_node(N["lw_hone"])                 # +1 to-hit
    assert actor.fighter.attack_bonus == before + 1


def test_steady_endurance_raises_max_endurance_at_once():
    actor = _hero_actor(endurance=20, path_points=1, path="long_watch")
    assert actor.hero.buy_node(N["lw_endure"])         # +4 max Endurance
    assert actor.fighter.max_endurance == 24
    assert actor.fighter.endurance == 24               # healed by the gain


# ---------------------------------------------------------------------------
# ACTIVE node end-to-end: Wrath primes the next melee hit
# ---------------------------------------------------------------------------
def _learn_wrath(hero):
    """Walk the Reaver branch far enough to own Wrath (tier 2, parent lw_hone)."""
    _buy_all(hero, "lw_endure", "lw_endure", "lw_hone", "lw_wrath")


def test_wrath_active_adds_damage_on_the_next_hit_then_goes_on_cooldown():
    engine, gm, player = make_world()
    hero = player.hero
    hero.path_points = 5
    hero.commit_path("long_watch")
    _learn_wrath(hero)

    foe = content.cave_goblin.spawn(gm, 3, 1)
    foe.fighter.base_defence = 2                        # trivial Defence -> always hits
    foe.fighter.base_soak = 0
    foe.fighter.max_endurance = 100
    foe.fighter.endurance = 100                         # survive a big blow

    assert hero.ability_ready("lw_wrath")
    hero.activate_ability("lw_wrath")
    assert "lw_wrath" in hero._primed

    seed = _seed_where(player.fighter.attack_bonus, 2,
                       lambda r: r.is_success and not r.is_crit)

    # Baseline damage from this seed with no Wrath primed.
    set_seed(seed)
    _b_engine, baseline_gm, baseline_player = make_world()
    bfoe = content.cave_goblin.spawn(baseline_gm, 3, 1)
    bfoe.fighter.base_defence = 2
    bfoe.fighter.base_soak = 0
    bfoe.fighter.max_endurance = 100
    bfoe.fighter.endurance = 100
    MeleeAction(baseline_player, 1, 0).perform()
    baseline_dmg = 100 - bfoe.fighter.endurance

    set_seed(seed)
    start = foe.fighter.endurance
    MeleeAction(player, 1, 0).perform()
    wrath_dmg = start - foe.fighter.endurance

    assert wrath_dmg > baseline_dmg                     # Wrath's +2d6 landed
    assert wrath_dmg - baseline_dmg >= 2                # at least 2d6 minimum
    assert "lw_wrath" not in hero._primed               # charge consumed
    assert hero.cooldown_left("lw_wrath") == N["lw_wrath"].active.cooldown
    assert not hero.ability_ready("lw_wrath")           # on cooldown now


def test_activate_ability_action_reports_impossible_when_not_ready():
    engine, gm, player = make_world()
    hero = player.hero
    hero.path_points = 5
    hero.commit_path("long_watch")
    _learn_wrath(hero)
    hero.activate_ability("lw_wrath")                   # now primed, not ready again
    from lonelands.exceptions import Impossible
    try:
        ActivateAbilityAction(player, "lw_wrath").perform()
        assert False, "expected Impossible"
    except Impossible:
        pass


def test_tick_nodes_counts_a_cooldown_down_to_ready():
    actor = _hero_actor(will=2, endurance=30, path_points=1, path="long_watch")
    hero = actor.hero
    actor.fighter.endurance = 10                        # room to heal
    assert hero.buy_node(N["lw_wind"])                 # Second Wind: heal, cooldown 6
    hero.activate_ability("lw_wind")
    cd = N["lw_wind"].active.cooldown
    assert hero.cooldown_left("lw_wind") == cd
    assert actor.fighter.endurance > 10                 # healed at once
    for _ in range(cd):
        hero.tick_nodes()
    assert hero.cooldown_left("lw_wind") == 0
    assert hero.ability_ready("lw_wind")


# ---------------------------------------------------------------------------
# ACTIVE stance: Hold the Line grants temporary Soak that decays
# ---------------------------------------------------------------------------
def _learn_hold_the_line(hero):
    """Walk the Warden branch to its capstone stance."""
    _buy_all(hero, "lw_endure", "lw_endure", "lw_soak", "lw_guard", "lw_hold")


def test_hold_the_line_stance_grants_then_loses_temporary_soak():
    actor = _hero_actor(path_points=9, path="long_watch")
    hero = actor.hero
    _learn_hold_the_line(hero)
    base_soak = actor.fighter.soak
    hero.activate_ability("lw_hold")
    assert actor.fighter.soak == base_soak + N["lw_hold"].active.soak
    for _ in range(N["lw_hold"].active.duration):
        hero.tick_nodes()
    assert actor.fighter.soak == base_soak


# ---------------------------------------------------------------------------
# AMBUSH: Hidden Path opening blow hits harder on a fresh foe
# ---------------------------------------------------------------------------
def test_ambush_bonus_damage_lands_only_on_a_fresh_foe():
    engine, gm, player = make_world()
    hero = player.hero
    hero.path_points = 5
    hero.commit_path("hidden_path")
    _buy_all(hero, "hp_stealth", "hp_stealth", "hp_ambush")  # advantage + 2 ambush dmg

    foe = content.cave_goblin.spawn(gm, 3, 1)
    foe.fighter.base_defence = 2
    foe.fighter.base_soak = 0
    foe.fighter.max_endurance = 100
    foe.fighter.endurance = 100

    seed = _seed_where(player.fighter.attack_bonus, 2,
                       lambda r: r.is_success and not r.is_crit)
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()
    assert "shadows" in engine.message_log.messages[-1].plain_text.lower()
    # Foe is no longer fresh: a second strike carries no ambush note.
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()
    assert "shadows" not in engine.message_log.messages[-1].plain_text.lower()


# ---------------------------------------------------------------------------
# Turn bookkeeping: the activation turn must not shorten a freshly-set timer
# ---------------------------------------------------------------------------
def test_end_player_turn_does_not_shorten_the_activation_turn():
    actor = _hero_actor(will=2, endurance=30, path_points=1, path="long_watch")
    hero = actor.hero
    actor.fighter.endurance = 10
    assert hero.buy_node(N["lw_wind"])                 # Second Wind: heal, cooldown 6
    cd = N["lw_wind"].active.cooldown
    hero.activate_ability("lw_wind")
    hero.end_player_turn()                              # activation turn: no decay
    assert hero.cooldown_left("lw_wind") == cd
    for _ in range(cd - 1):
        hero.end_player_turn()
        assert not hero.ability_ready("lw_wind")
    hero.end_player_turn()
    assert hero.ability_ready("lw_wind")


def test_stance_lasts_its_full_duration_after_the_activation_turn():
    actor = _hero_actor(path_points=9, path="long_watch")
    hero = actor.hero
    _learn_hold_the_line(hero)
    base_soak = actor.fighter.soak
    hero.activate_ability("lw_hold")
    duration = N["lw_hold"].active.duration
    hero.end_player_turn()                              # activation turn: no decay
    for _ in range(duration - 1):
        assert actor.fighter.soak > base_soak
        hero.end_player_turn()
    assert actor.fighter.soak > base_soak
    hero.end_player_turn()
    assert actor.fighter.soak == base_soak


# ---------------------------------------------------------------------------
# On-kill hook: Reaver's Instinct readies the hero's deeds on a slaying
# ---------------------------------------------------------------------------
def _full_reaver(hero):
    """Walk the Reaver branch to its capstone (Reaver's Instinct)."""
    _buy_all(hero, "lw_endure", "lw_endure", "lw_hone", "lw_might",
             "lw_wrath", "lw_reaver")


def test_on_kill_readies_deeds_only_with_reavers_instinct():
    with_reaver = _hero_actor(path_points=9, path="long_watch").hero
    _full_reaver(with_reaver)
    with_reaver._node_cooldowns["lw_wrath"] = 3         # Wrath spent, cooling down
    with_reaver.on_kill()
    assert with_reaver.cooldown_left("lw_wrath") == 0
    assert with_reaver.ability_ready("lw_wrath")

    # Without the capstone, a kill changes nothing.
    without = _hero_actor(path_points=5, path="long_watch").hero
    _learn_wrath(without)
    without._node_cooldowns["lw_wrath"] = 3
    without.on_kill()
    assert without.cooldown_left("lw_wrath") == 3


def test_slaying_a_foe_triggers_the_on_kill_hook():
    engine, gm, player = make_world()
    player.hero.path_points = 9
    player.hero.commit_path("long_watch")
    _full_reaver(player.hero)
    player.hero._node_cooldowns["lw_wrath"] = 3         # on cooldown before the kill

    foe = content.cave_goblin.spawn(gm, 3, 1)
    foe.fighter.base_defence = 2
    foe.fighter.endurance = 1                           # one blow fells it
    seed = _seed_where(player.fighter.attack_bonus, 2, lambda r: r.is_success)
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()
    assert foe.fighter.dead
    assert player.hero.cooldown_left("lw_wrath") == 0   # die() -> on_kill readied it


# ---------------------------------------------------------------------------
# Widened crit: the dice tray (RollResult.is_crit) agrees with the log
# ---------------------------------------------------------------------------
def test_reavers_instinct_natural_19_reads_as_a_crit_in_the_tray():
    engine, gm, player = make_world()
    player.hero.path_points = 9
    player.hero.commit_path("long_watch")
    _full_reaver(player.hero)                           # Reaver's Instinct: crit on 19+
    assert player.fighter.crit_face == 19

    foe = content.cave_goblin.spawn(gm, 3, 1)
    foe.fighter.base_defence = 2
    foe.fighter.max_endurance = 100
    foe.fighter.endurance = 100

    seed = _seed_where(player.fighter.attack_bonus, 2, lambda r: r.die == 19)
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()
    recent = " ".join(m.plain_text for m in engine.message_log.messages[-2:])
    assert "CRITICAL" in recent
    assert engine.last_roll.is_crit
