"""Ranged combat: bows, arrows, and the Shot (ADR 0006, issue #46).

Drives the real ``RangedAttackAction`` against a real Engine/GameMap (both
construct headless) so we exercise the actual branch logic, not a
re-implementation. Dice are pinned with ``set_seed``; where a specific d20 face
is needed we scan for a seed that produces it and re-seed before the call.
"""
from __future__ import annotations

import copy

from lonelands import content
from lonelands.actions import (
    MeleeAction,
    RangedAttackAction,
    _ammo_stack,
    _has_adjacent_hostile,
    resolve_ambush,
)
from lonelands.dice import roll_check, set_seed
from lonelands.engine import Engine
from lonelands.game_map import GameMap


def make_world():
    player = content.make_player()
    engine = Engine(player)
    gm = GameMap(engine, 40, 10)
    engine.game_map = gm
    player.place(2, 5, gm)
    return engine, gm, player


def grant(hero, *node_ids):
    """Grant node ownership directly (rank 1), bypassing purchase gating — these
    tests exercise the derived-stat plumbing, not the buy flow."""
    for nid in node_ids:
        hero.nodes[nid] = max(1, hero.nodes.get(nid, 0))


def arm(player, bow=None, arrows: int = 10):
    """Equip a bow in the ranged slot and stock the quiver."""
    bow = copy.deepcopy(bow if bow is not None else content.shortbow)
    player.equipment.toggle_equip(bow, add_message=False)
    if arrows:
        quiver = copy.deepcopy(content.arrows)
        quiver.quantity = arrows
        player.inventory.add(quiver)
    return bow


def spawn_foe(gm, template, x, y=5):
    return template.spawn(gm, x, y)


def last_message(engine):
    return engine.message_log.messages[-1].plain_text


def _messages(engine):
    return [m.plain_text for m in engine.message_log.messages]


def _seed_where(mod, tn, predicate, advantage=0):
    for seed in range(20000):
        set_seed(seed)
        if predicate(roll_check(mod, tn, advantage=advantage)):
            return seed
    raise AssertionError("no seed satisfied the predicate")


# --- Bow stats & derived numbers -------------------------------------------

def test_bows_carry_damage_and_effective_range():
    assert content.shortbow.equippable.effective_range == 4
    assert content.shortbow.equippable.damage == "1d6"
    assert content.longbow.equippable.effective_range == 6
    assert content.longbow.equippable.damage == "1d8"


def test_stat_line_shows_the_effective_range():
    assert content.shortbow.equippable.stat_line() == "dmg 1d6 · range 4 · load 1"


def test_ranged_to_hit_is_keyed_off_wits_not_brawn():
    _, _, player = make_world()
    arm(player)
    hero = player.hero
    # A shortbow adds no +hit; the bonus is Wits + level to-hit (0 at level 1).
    assert player.fighter.ranged_attack_bonus == hero.wits
    # Brawn drives melee, Wits drives the Shot — bumping either apart proves it.
    hero.attributes["Brawn"] = 9
    hero.attributes["Wits"] = 1
    assert player.fighter.ranged_attack_bonus == 1       # tracks Wits
    assert player.fighter.attack_bonus != player.fighter.ranged_attack_bonus


def test_no_bow_means_no_ranged_weapon():
    _, _, player = make_world()
    assert not player.fighter.has_ranged_weapon
    assert player.fighter.ranged_attack_bonus == 0


def test_range_penalty_is_zero_within_range_then_minus_one_per_three_tiles():
    _, _, player = make_world()
    arm(player)  # shortbow, effective range 4
    f = player.fighter
    assert f.range_penalty(1) == 0
    assert f.range_penalty(4) == 0    # at the edge of effective range
    assert f.range_penalty(5) == 1    # one tile past -> -1
    assert f.range_penalty(7) == 1
    assert f.range_penalty(8) == 2    # four tiles past -> -2


# --- The Shot resolves ------------------------------------------------------

def test_a_shot_hits_for_bow_damage_reduced_by_soak():
    engine, gm, player = make_world()
    arm(player)
    foe = spawn_foe(gm, content.cave_goblin, 6)  # four tiles east, in range
    foe.fighter.base_defence = 2                 # trivial Defence -> always hits
    start = foe.fighter.endurance

    seed = _seed_where(player.fighter.ranged_attack_bonus, 2,
                       lambda r: r.is_success and not r.is_crit)
    set_seed(seed)
    RangedAttackAction(player, foe).perform()

    assert foe.fighter.endurance < start
    assert "endurance" in last_message(engine)


def test_a_shot_spends_one_arrow():
    engine, gm, player = make_world()
    arm(player, arrows=3)
    foe = spawn_foe(gm, content.cave_goblin, 6)
    foe.fighter.base_defence = 2
    seed = _seed_where(player.fighter.ranged_attack_bonus, 2, lambda r: r.is_success)
    set_seed(seed)
    RangedAttackAction(player, foe).perform()
    assert _ammo_stack(player).quantity == 2


def test_an_empty_quiver_refuses_to_fire():
    engine, gm, player = make_world()
    arm(player, arrows=0)
    foe = spawn_foe(gm, content.cave_goblin, 6)
    import pytest
    with pytest.raises(Exception) as exc:
        RangedAttackAction(player, foe).perform()
    assert "quiver" in str(exc.value).lower()


def test_no_bow_refuses_to_fire():
    engine, gm, player = make_world()
    # arrows but no bow
    quiver = copy.deepcopy(content.arrows)
    quiver.quantity = 5
    player.inventory.add(quiver)
    foe = spawn_foe(gm, content.cave_goblin, 6)
    import pytest
    with pytest.raises(Exception) as exc:
        RangedAttackAction(player, foe).perform()
    assert "bow" in str(exc.value).lower()


def test_a_shot_feeds_the_dice_tray_with_its_damage():
    engine, gm, player = make_world()
    arm(player)
    foe = spawn_foe(gm, content.cave_goblin, 6)
    foe.fighter.base_defence = 2
    start = foe.fighter.endurance
    seed = _seed_where(player.fighter.ranged_attack_bonus, 2, lambda r: r.is_success)
    set_seed(seed)
    RangedAttackAction(player, foe).perform()
    assert engine.last_roll is not None
    assert engine.last_roll.damage == start - foe.fighter.endurance


# --- Range falloff bites at distance ---------------------------------------

def test_the_range_penalty_folds_into_the_roll():
    engine, gm, player = make_world()
    arm(player)
    # A foe eight tiles east: shortbow range 4, so a -2 falloff.
    foe = spawn_foe(gm, content.cave_goblin, 10)
    assert max(abs(foe.x - player.x), abs(foe.y - player.y)) == 8
    bonus = player.fighter.ranged_attack_bonus
    # A reachable Defence where the top dice hit unpenalised but the -2 falloff
    # drags them under: die+bonus >= TN but die+bonus-2 < TN.
    tn = bonus + 15
    foe.fighter.base_defence = tn
    seed = _seed_where(bonus - 2, tn,
                       lambda r: not r.is_success and not r.is_fumble
                       and (r.die + bonus) >= tn)
    set_seed(seed)
    RangedAttackAction(player, foe).perform()
    # Without the penalty this die would have hit; with it, a miss.
    assert "but miss" in last_message(engine)


# --- Point-blank disadvantage ----------------------------------------------

def test_a_foe_at_your_elbow_gives_the_shot_disadvantage():
    engine, gm, player = make_world()
    arm(player)
    spawn_foe(gm, content.cave_goblin, 3)          # adjacent (point-blank)
    mark = spawn_foe(gm, content.orc_soldier, 6)   # the mark, in range
    mark.fighter.base_defence = 2
    assert _has_adjacent_hostile(engine, player)
    seed = _seed_where(player.fighter.ranged_attack_bonus, 2, lambda r: True)
    set_seed(seed)
    RangedAttackAction(player, mark).perform()
    # Disadvantage rolls two dice and keeps the lower.
    roll = engine.last_roll
    assert len(roll.dice) == 2
    assert roll.die == min(roll.dice)


def test_no_adjacent_foe_rolls_a_single_die():
    engine, gm, player = make_world()
    arm(player)
    mark = spawn_foe(gm, content.orc_soldier, 6)
    mark.fighter.base_defence = 2
    assert not _has_adjacent_hostile(engine, player)
    set_seed(1)
    RangedAttackAction(player, mark).perform()
    assert len(engine.last_roll.dice) == 1


# --- Criticals: hit and bonus damage, but no Bleed --------------------------

def test_a_ranged_crit_hits_hard_but_opens_no_bleed():
    engine, gm, player = make_world()
    arm(player)
    foe = spawn_foe(gm, content.cave_goblin, 6)
    foe.fighter.base_defence = 99  # only a natural 20 lands
    start = foe.fighter.endurance
    seed = _seed_where(player.fighter.ranged_attack_bonus, 99, lambda r: r.is_crit)
    set_seed(seed)
    RangedAttackAction(player, foe).perform()
    assert foe.fighter.endurance < start   # the crit landed
    assert foe.fighter.bleed == 0          # ...but a Shot never bleeds
    assert "CRITICAL shot" in last_message(engine)


def test_reaver_widened_crit_does_not_carry_to_the_bow():
    engine, gm, player = make_world()
    arm(player)
    # Reaver's Instinct widens melee crit to 19-20; a Shot still crits only on 20.
    grant(player.hero, "lw_reaver")
    foe = spawn_foe(gm, content.cave_goblin, 6)
    foe.fighter.base_defence = 99
    # A natural 19: a melee crit under Reaver's, but a ranged miss.
    seed = _seed_where(player.fighter.ranged_attack_bonus, 99, lambda r: r.die == 19)
    set_seed(seed)
    RangedAttackAction(player, foe).perform()
    assert not engine.last_roll.is_crit
    assert "but miss" in last_message(engine)


# --- The Far Shot Path feeds the Shot --------------------------------------

def test_far_shot_nodes_add_ranged_to_hit_and_damage():
    _, _, player = make_world()
    arm(player)
    hero = player.hero
    base_hit = player.fighter.ranged_attack_bonus
    grant(hero, "fs_aim", "fs_fletcher")  # +1 hit, +1 damage
    assert player.fighter.ranged_attack_bonus == base_hit + 1
    assert player.fighter.ranged_damage_bonus == 1
    grant(hero, "fs_deadeye")  # +2 hit, +2 damage
    assert player.fighter.ranged_attack_bonus == base_hit + 3
    assert player.fighter.ranged_damage_bonus == 3


# --- Ambush: the shared helper, applied to a Shot ---------------------------

def test_the_shared_ambush_helper_reads_hidden_path_nodes():
    _, _, player = make_world()
    hero = player.hero
    foe = content.cave_goblin.spawn(GameMap(Engine(player), 5, 5), 1, 1)
    # No nodes: no ambush.
    assert resolve_ambush(hero, foe.fighter) == (False, 0, 0)
    # Ambush node: advantage + bonus damage against a fresh foe.
    grant(hero, "hp_ambush")
    is_ambush, adv, bonus = resolve_ambush(hero, foe.fighter)
    assert is_ambush and adv == 1 and bonus == 2
    # A bloodied foe cannot be ambushed.
    foe.fighter.endurance = foe.fighter.max_endurance - 1
    assert resolve_ambush(hero, foe.fighter)[0] is False


def test_ambush_bonus_damage_lands_on_a_shot():
    engine, gm, player = make_world()
    # A bow that rolls flat 0 damage isolates the ambush bonus arithmetic.
    flat_bow = copy.deepcopy(content.shortbow)
    flat_bow.equippable.damage = 0
    arm(player, bow=flat_bow)
    grant(player.hero, "hp_ambush")  # advantage + 2 bonus damage
    foe = spawn_foe(gm, content.cave_goblin, 6)  # at full Endurance -> ambushable
    foe.fighter.base_defence = 2
    foe.fighter.base_soak = 0
    start = foe.fighter.endurance

    # A plain (non-crit) hit; ambush grants advantage so keep the higher die.
    seed = _seed_where(player.fighter.ranged_attack_bonus, 2,
                       lambda r: r.is_success and not r.is_crit, advantage=1)
    set_seed(seed)
    RangedAttackAction(player, foe).perform()

    # raw 0 -> floored to 1, then +2 ambush = 3.
    assert start - foe.fighter.endurance == 3
    assert "From the shadows!" in last_message(engine)


# --- Arrow recovery ---------------------------------------------------------

def test_about_half_of_loosed_arrows_are_recoverable():
    engine, gm, player = make_world()
    arm(player, arrows=0)
    foe = spawn_foe(gm, content.orc_soldier, 6)
    foe.fighter.base_defence = 2
    drops = 0
    trials = 200
    for i in range(trials):
        # Keep the quiver topped up and the foe alive for each independent shot.
        quiver = copy.deepcopy(content.arrows)
        quiver.quantity = 1
        player.inventory.add(quiver)
        foe.fighter.endurance = foe.fighter.max_endurance
        before = sum(1 for it in gm.items if it.name == content.AMMO_NAME)
        set_seed(i)
        RangedAttackAction(player, foe).perform()
        after = sum(1 for it in gm.items if it.name == content.AMMO_NAME)
        drops += after - before
    # ~50%: assert both outcomes occur and the rate is in a sane band.
    assert 0 < drops < trials
    assert 0.30 * trials < drops < 0.70 * trials


def test_a_recovered_arrow_can_be_picked_up():
    engine, gm, player = make_world()
    arm(player, arrows=1)
    foe = spawn_foe(gm, content.orc_soldier, 6)
    foe.fighter.base_defence = 2
    # Find a shot that leaves a recoverable arrow on the foe's tile.
    for seed in range(2000):
        engine, gm, player = make_world()
        arm(player, arrows=1)
        foe = spawn_foe(gm, content.orc_soldier, 6)
        foe.fighter.base_defence = 2
        set_seed(seed)
        RangedAttackAction(player, foe).perform()
        dropped = [it for it in gm.items if it.name == content.AMMO_NAME
                   and it.x == foe.x and it.y == foe.y]
        if dropped:
            break
    else:
        raise AssertionError("no seed produced a recoverable arrow")
    assert dropped  # a spent arrow lies on the target tile, ready for `g`


# --- Both weapons wielded at once (no swap) --------------------------------

def test_melee_and_ranged_read_their_own_slots_at_once():
    _, _, player = make_world()
    player.equipment.toggle_equip(copy.deepcopy(content.short_sword), add_message=False)
    arm(player)  # bow in the ranged slot, sword still in the weapon slot
    assert player.equipment.weapon is not None
    assert player.equipment.ranged is not None
    # Melee reads the sword's damage; the Shot reads the bow's.
    assert player.fighter.damage == content.short_sword.equippable.damage
    assert player.fighter.ranged_damage == content.shortbow.equippable.damage


# --- Content reachability & shop -------------------------------------------

def test_bows_and_arrows_are_reachable_in_play():
    d2 = dict(content.items_for_depth(2))
    assert content.shortbow in d2
    assert content.longbow in d2
    assert content.arrow_bundle in dict(content.items_for_depth(0))
    # A bow-foe drops arrows.
    dropped_names = [
        outcome.name
        for roll in content.orc_archer.fighter.loot
        for outcome, _w in roll
        if hasattr(outcome, "name")
    ]
    assert content.AMMO_NAME in dropped_names


def test_the_fletcher_stocks_bows_and_arrows():
    from lonelands import story, input_handlers
    fletcher = story.make_fletcher()
    # Walk the dialogue tree to the shop option and open it.
    engine, _, player = make_world()
    opened = {}
    for node in fletcher.npc.tree.values():
        for o in node["options"]:
            h = o.get("handler")
            if h is not None:
                shop = h(engine)
                opened["names"] = [it.name for it in shop.stock]
    assert content.longbow.name in opened["names"]
    assert content.shortbow.name in opened["names"]
    assert content.AMMO_NAME in opened["names"]
