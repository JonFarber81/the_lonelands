"""Tests for Paths & perks (issue #38).

Two layers:
  * unit tests on the data model + Hero ownership/spend/gating (prereqs,
    capstones, perk-point accounting);
  * end-to-end tests that drive a real MeleeAction against a real Engine/GameMap
    (both construct headless), pinning dice with `set_seed` and scanning for a
    seed that yields a wanted d20 face — the same technique tests/test_combat.py
    uses — to prove one PASSIVE and one ACTIVE perk are live in play.
"""
from __future__ import annotations

from lonelands import content, perks
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
def _hero_actor(brawn=3, wits=2, will=1, endurance=20, perk_points=0):
    actor = Actor(
        char="@", color=(255, 255, 255), name="Test",
        fighter=Fighter(endurance=endurance, defence=10, attack_bonus=1, damage=1),
        hero=Hero(attributes={"Brawn": brawn, "Wits": wits, "Will": will}),
    )
    actor.hero.perk_points = perk_points
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


P = perks.ALL_PERKS


# ---------------------------------------------------------------------------
# Data model sanity
# ---------------------------------------------------------------------------
def test_five_paths_each_with_perks():
    assert len(perks.PATHS) == 5
    ids = {p.id for p in perks.PATHS}
    assert ids == {"long_watch", "swift_wrath", "far_shot",
                   "hidden_path", "kindled_heart"}
    for path in perks.PATHS:
        assert len(path.perks) >= 3
        assert sum(1 for pk in path.perks if pk.capstone) == 1


def test_all_perks_lookup_is_complete_and_unique():
    flat = [pk for path in perks.PATHS for pk in path.perks]
    assert len(P) == len(flat)
    assert len(P) == len({pk.id for pk in flat})


# ---------------------------------------------------------------------------
# Prerequisite gating
# ---------------------------------------------------------------------------
def test_tier2_perk_needs_a_tier1_prereq_in_the_same_path():
    hero = _hero_actor(perk_points=5).hero
    guard = P["lw_guard"]        # tier 2 in Long Watch
    assert guard.tier == 2
    # No Long Watch perk owned yet -> the tier-2 perk is not buyable.
    assert not hero.can_buy(guard)
    assert not hero.buy_perk(guard)
    assert not hero.has_perk("lw_guard")
    # Take a tier-1 perk in the Path, and the prereq is now met.
    assert hero.buy_perk(P["lw_endure"])
    assert hero.can_buy(guard)
    assert hero.buy_perk(guard)
    assert hero.has_perk("lw_guard")


def test_a_tier1_perk_in_another_path_does_not_unlock_a_deeper_perk():
    hero = _hero_actor(perk_points=5).hero
    assert hero.buy_perk(P["sw_hone"])   # a Swift Wrath tier-1 perk
    # ...does nothing for Long Watch's tier-2 perk.
    assert not hero.can_buy(P["lw_guard"])


# ---------------------------------------------------------------------------
# Capstone gating
# ---------------------------------------------------------------------------
def test_capstone_locked_until_all_non_capstones_in_the_path_are_owned():
    hero = _hero_actor(perk_points=9).hero
    reaver = P["sw_reaver"]      # Swift Wrath capstone
    assert reaver.capstone
    assert not hero.can_buy(reaver)              # nothing owned
    hero.buy_perk(P["sw_hone"])
    hero.buy_perk(P["sw_wrath"])
    assert not hero.can_buy(reaver)              # still one non-capstone short
    hero.buy_perk(P["sw_might"])
    assert hero.can_buy(reaver)                  # every non-capstone now owned
    assert hero.buy_perk(reaver)
    assert hero.has_perk("sw_reaver")


# ---------------------------------------------------------------------------
# Perk-point accounting
# ---------------------------------------------------------------------------
def test_buying_deducts_cost_and_cannot_overspend():
    hero = _hero_actor(perk_points=1).hero
    assert hero.buy_perk(P["lw_soak"])           # cost 1
    assert hero.perk_points == 0
    # Broke: even a valid, unlocked perk cannot be bought.
    assert not hero.can_buy(P["lw_endure"])
    assert not hero.buy_perk(P["lw_endure"])
    assert not hero.has_perk("lw_endure")


def test_cannot_buy_the_same_perk_twice():
    hero = _hero_actor(perk_points=3).hero
    assert hero.buy_perk(P["lw_soak"])
    assert not hero.can_buy(P["lw_soak"])
    assert not hero.buy_perk(P["lw_soak"])
    assert hero.perk_points == 2                  # not charged twice


# ---------------------------------------------------------------------------
# PASSIVE perks change real combat numbers
# ---------------------------------------------------------------------------
def test_swift_wrath_honed_edge_raises_attack_bonus():
    actor = _hero_actor(brawn=3, perk_points=1)
    before = actor.fighter.attack_bonus
    assert actor.hero.buy_perk(P["sw_hone"])      # +1 to-hit
    assert actor.fighter.attack_bonus == before + 1


def test_long_watch_iron_skin_raises_soak():
    actor = _hero_actor(perk_points=1)
    before = actor.fighter.soak
    assert actor.hero.buy_perk(P["lw_soak"])      # +1 Soak
    assert actor.fighter.soak == before + 1


def test_steady_endurance_raises_max_endurance_at_once():
    actor = _hero_actor(endurance=20, perk_points=1)
    assert actor.hero.buy_perk(P["lw_endure"])    # +6 max Endurance
    assert actor.fighter.max_endurance == 26
    assert actor.fighter.endurance == 26          # healed by the gain


def test_kindled_heart_defiance_only_fires_while_badly_wounded():
    actor = _hero_actor(brawn=3, endurance=30, perk_points=1)
    assert actor.hero.buy_perk(P["kh_defiance"])  # +2 to-hit at <= 1/3 Endurance
    full = actor.fighter.attack_bonus
    actor.fighter.endurance = 9                    # 9/30 = 0.3 <= 1/3
    assert actor.fighter.attack_bonus == full + 2
    actor.fighter.endurance = 30                   # back to full -> trigger off
    assert actor.fighter.attack_bonus == full


# ---------------------------------------------------------------------------
# ACTIVE perk end-to-end: Wrath primes the next melee hit
# ---------------------------------------------------------------------------
def test_wrath_active_adds_damage_on_the_next_hit_then_goes_on_cooldown():
    engine, gm, player = make_world()
    hero = player.hero
    hero.perk_points = 1
    assert hero.buy_perk(P["sw_wrath"])

    foe = content.cave_goblin.spawn(gm, 3, 1)
    foe.fighter.base_defence = 2                   # trivial Defence -> always hits
    foe.fighter.base_soak = 0
    foe.fighter.max_endurance = 100
    foe.fighter.endurance = 100  # survive a big blow

    # Prime Wrath, then land a plain (non-crit) hit; compare against the same
    # seed's damage WITHOUT the primed charge.
    assert hero.ability_ready("sw_wrath")
    hero.activate_ability("sw_wrath")
    assert "sw_wrath" in hero._primed

    seed = _seed_where(player.fighter.attack_bonus, 2,
                       lambda r: r.is_success and not r.is_crit)

    # Baseline damage from this seed with no Wrath primed.
    set_seed(seed)
    baseline_engine, baseline_gm, baseline_player = make_world()
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

    assert wrath_dmg > baseline_dmg               # Wrath's +2d6 landed
    assert wrath_dmg - baseline_dmg >= 2          # at least 2d6 minimum
    assert "sw_wrath" not in hero._primed         # charge consumed
    assert hero.cooldown_left("sw_wrath") == P["sw_wrath"].active.cooldown
    assert not hero.ability_ready("sw_wrath")     # on cooldown now


def test_activate_ability_action_reports_impossible_when_not_ready():
    engine, gm, player = make_world()
    hero = player.hero
    hero.perk_points = 1
    hero.buy_perk(P["sw_wrath"])
    hero.activate_ability("sw_wrath")             # now primed, not ready again
    from lonelands.exceptions import Impossible
    try:
        ActivateAbilityAction(player, "sw_wrath").perform()
        assert False, "expected Impossible"
    except Impossible:
        pass


def test_tick_perks_counts_a_cooldown_down_to_ready():
    actor = _hero_actor(will=2, endurance=30, perk_points=1)
    hero = actor.hero
    actor.fighter.endurance = 10                   # room to heal
    assert hero.buy_perk(P["kh_wind"])             # Second Wind: heal, cooldown 6
    hero.activate_ability("kh_wind")
    cd = P["kh_wind"].active.cooldown
    assert hero.cooldown_left("kh_wind") == cd
    assert actor.fighter.endurance > 10            # healed at once
    for _ in range(cd):
        hero.tick_perks()
    assert hero.cooldown_left("kh_wind") == 0
    assert hero.ability_ready("kh_wind")


# ---------------------------------------------------------------------------
# ACTIVE stance: Hold the Line grants temporary Soak that decays
# ---------------------------------------------------------------------------
def test_hold_the_line_stance_grants_then_loses_temporary_soak():
    actor = _hero_actor(perk_points=9)
    hero = actor.hero
    # Buy the whole Long Watch path to unlock the capstone stance.
    for pid in ("lw_endure", "lw_soak", "lw_guard", "lw_hold"):
        assert hero.buy_perk(P[pid])
    base_soak = actor.fighter.soak
    hero.activate_ability("lw_hold")
    assert actor.fighter.soak == base_soak + P["lw_hold"].active.soak
    # The stance lasts `duration` rounds, then expires.
    for _ in range(P["lw_hold"].active.duration):
        hero.tick_perks()
    assert actor.fighter.soak == base_soak


# ---------------------------------------------------------------------------
# AMBUSH: Hidden Path opening blow hits harder on a fresh foe
# ---------------------------------------------------------------------------
def test_ambush_bonus_damage_lands_only_on_a_fresh_foe():
    engine, gm, player = make_world()
    hero = player.hero
    hero.perk_points = 1
    assert hero.buy_perk(P["hp_ambush"])           # advantage + 2 ambush damage

    foe = content.cave_goblin.spawn(gm, 3, 1)
    foe.fighter.base_defence = 2
    foe.fighter.base_soak = 0
    foe.fighter.max_endurance = 100
    foe.fighter.endurance = 100

    # First strike (fresh foe) -> ambush applies; message notes it.
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
    actor = _hero_actor(will=2, endurance=30, perk_points=1)
    hero = actor.hero
    actor.fighter.endurance = 10
    assert hero.buy_perk(P["kh_wind"])              # Second Wind: heal, cooldown 6
    cd = P["kh_wind"].active.cooldown
    hero.activate_ability("kh_wind")
    # The turn we activate on does not tick the cooldown it just set.
    hero.end_player_turn()
    assert hero.cooldown_left("kh_wind") == cd
    # Every later turn does: exactly `cd` more turns to become ready again.
    for _ in range(cd - 1):
        hero.end_player_turn()
        assert not hero.ability_ready("kh_wind")
    hero.end_player_turn()
    assert hero.ability_ready("kh_wind")


def test_stance_lasts_its_full_duration_after_the_activation_turn():
    actor = _hero_actor(perk_points=9)
    hero = actor.hero
    for pid in ("lw_endure", "lw_soak", "lw_guard", "lw_hold"):
        assert hero.buy_perk(P[pid])
    base_soak = actor.fighter.soak
    hero.activate_ability("lw_hold")
    duration = P["lw_hold"].active.duration
    hero.end_player_turn()                          # activation turn: no decay
    # The stance protects for its full authored duration of later turns.
    for _ in range(duration - 1):
        assert actor.fighter.soak > base_soak
        hero.end_player_turn()
    assert actor.fighter.soak > base_soak
    hero.end_player_turn()
    assert actor.fighter.soak == base_soak


# ---------------------------------------------------------------------------
# On-kill hook: Reaver's Instinct readies the hero's deeds on a slaying
# ---------------------------------------------------------------------------
def _full_swift_wrath(hero):
    for pid in ("sw_hone", "sw_wrath", "sw_might", "sw_reaver"):
        assert hero.buy_perk(P[pid])


def test_on_kill_readies_deeds_only_with_reavers_instinct():
    with_reaver = _hero_actor(perk_points=5).hero
    _full_swift_wrath(with_reaver)
    with_reaver._perk_cooldowns["sw_wrath"] = 3     # Wrath spent, cooling down
    with_reaver.on_kill()
    assert with_reaver.cooldown_left("sw_wrath") == 0
    assert with_reaver.ability_ready("sw_wrath")

    # Without the capstone, a kill changes nothing.
    without = _hero_actor(perk_points=2).hero
    assert without.buy_perk(P["sw_wrath"])
    without._perk_cooldowns["sw_wrath"] = 3
    without.on_kill()
    assert without.cooldown_left("sw_wrath") == 3


def test_slaying_a_foe_triggers_the_on_kill_hook():
    engine, gm, player = make_world()
    player.hero.perk_points = 5
    _full_swift_wrath(player.hero)
    player.hero._perk_cooldowns["sw_wrath"] = 3      # on cooldown before the kill

    foe = content.cave_goblin.spawn(gm, 3, 1)
    foe.fighter.base_defence = 2
    foe.fighter.endurance = 1                        # one blow fells it
    seed = _seed_where(player.fighter.attack_bonus, 2, lambda r: r.is_success)
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()
    assert foe.fighter.dead
    assert player.hero.cooldown_left("sw_wrath") == 0  # die() -> on_kill readied it


# ---------------------------------------------------------------------------
# Widened crit: the dice tray (RollResult.is_crit) agrees with the log
# ---------------------------------------------------------------------------
def test_reavers_instinct_natural_19_reads_as_a_crit_in_the_tray():
    engine, gm, player = make_world()
    player.hero.perk_points = 5
    _full_swift_wrath(player.hero)                   # Reaver's Instinct: crit on 19+
    assert player.fighter.crit_face == 19

    foe = content.cave_goblin.spawn(gm, 3, 1)
    foe.fighter.base_defence = 2
    foe.fighter.max_endurance = 100
    foe.fighter.endurance = 100

    seed = _seed_where(player.fighter.attack_bonus, 2, lambda r: r.die == 19)
    set_seed(seed)
    MeleeAction(player, 1, 0).perform()
    # The crit lands (its Bleed follow-up may be the very last line), so scan the
    # recent log rather than only messages[-1].
    recent = " ".join(m.plain_text for m in engine.message_log.messages[-2:])
    assert "CRITICAL" in recent
    # The tray keys off RollResult.is_crit — it must see the widened crit too.
    assert engine.last_roll.is_crit
