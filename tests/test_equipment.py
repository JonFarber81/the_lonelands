"""Equipment overhaul (Phase 5, issue #39).

Exercises the legible gear stat model of ADR 0005: heavy Soak vs light +Defence,
weapon properties (pierce / bonus-vs-kind), non-combat accessory pluses, and the
hand-authored named Uniques — all against the real components (no display needed).
"""
from __future__ import annotations

from lonelands import content
from lonelands.actions import MeleeAction
from lonelands.components.equipment import Equipment
from lonelands.components.equippable import Equippable
from lonelands.dice import roll_check, set_seed
from lonelands.engine import Engine
from lonelands.equipment_types import EquipmentType
from lonelands.game_map import GameMap


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


# --- Slots ------------------------------------------------------------------

def test_accessory_type_maps_to_the_token_slot():
    eq = Equipment()
    assert "token" in eq.slots
    assert eq.slot_for(content.ranger_star) == "token"


# --- Aggregation: soak vs Defence, load -------------------------------------

def test_worn_gear_aggregates_soak_defence_and_load():
    eq = Equipment()
    eq.toggle_equip(content.mail_corslet, add_message=False)   # soak 2, load 3
    eq.toggle_equip(content.buckler, add_message=False)        # +1 Defence, load 1
    eq.toggle_equip(content.travellers_hood, add_message=False)  # +1 Defence, load 0
    assert eq.soak_bonus == 2
    assert eq.defence_bonus == 2
    assert eq.load == 4


def test_heavy_and_light_armour_read_differently_on_the_fighter():
    # Mail is heavy: it raises Soak, not Defence. Leathers are light: the reverse.
    _, _, player = make_world()
    base_def, base_soak = player.fighter.defence, player.fighter.soak
    player.equipment.toggle_equip(content.mail_corslet, add_message=False)
    assert player.fighter.soak == base_soak + 2
    assert player.fighter.defence == base_def  # heavy armour never dodges

    player.equipment.toggle_equip(content.mail_corslet, add_message=False)  # off
    player.equipment.toggle_equip(content.leather_gear, add_message=False)
    assert player.fighter.defence == base_def + 1  # light armour dodges
    assert player.fighter.soak == base_soak


# --- Weapon properties ------------------------------------------------------

def test_weapon_lends_its_hit_bonus_to_the_wielder():
    _, _, player = make_world()
    base = player.fighter.attack_bonus
    player.equipment.toggle_equip(content.dunedain_sword, add_message=False)  # +1 hit
    assert player.fighter.attack_bonus == base + 1


def test_pierce_ignores_some_soak_in_a_melee_blow():
    engine, gm, player = make_world()
    player.equipment.toggle_equip(content.war_spear, add_message=False)  # pierce 1
    foe = content.orc_soldier.spawn(gm, 1, 1)  # soak 1
    foe.fighter.base_defence = 2  # trivial Defence -> the player always hits
    # pierce 1 cancels the orc's soak 1: effective soak is 0.
    assert player.fighter.pierce == 1
    seed = _seed_where(player.fighter.attack_bonus, foe.fighter.defence,
                       lambda r: r.is_success and not r.is_crit)
    set_seed(seed)
    before = foe.fighter.endurance
    MeleeAction(player, -1, 0).perform()
    dealt = before - foe.fighter.endurance
    # War spear rolls a flat 4; with soak fully pierced the full 4 lands.
    assert dealt == 4


def test_bonus_vs_kind_adds_damage_only_against_that_kind():
    engine, gm, player = make_world()
    player.equipment.toggle_equip(content.angolar, add_message=False)  # +2 vs orc
    orc = content.orc_soldier.spawn(gm, 1, 1)   # kind "orc"
    spider = content.great_spider.spawn(gm, 3, 1)  # kind "beast"
    assert player.fighter.bonus_vs_damage(orc) == 2
    assert player.fighter.bonus_vs_damage(spider) == 0


# --- Accessories: non-combat pluses -----------------------------------------

def test_accessory_attribute_plus_raises_the_attribute_and_downstream_defence():
    _, _, player = make_world()
    hero = player.hero
    wits_before = hero.wits
    def_before = player.fighter.defence
    player.equipment.toggle_equip(content.ranger_star, add_message=False)  # +1 Wits
    assert hero.wits == wits_before + 1
    assert hero.modifier("Wits") == wits_before + 1
    # Wits feeds Defence, so the token sharpens it downstream.
    assert player.fighter.defence == def_before + 1


def test_accessory_stealth_and_charges_aggregate():
    eq = Equipment()
    eq.toggle_equip(content.elven_brooch, add_message=False)   # +2 Stealth
    eq.toggle_equip(content.cloak_of_lorien, add_message=False)  # +1 Wits, +3 Stealth
    # Both are accessories and share the one token slot, so the cloak displaces
    # the brooch: only its bonuses remain.
    assert eq.stealth_bonus == 3
    assert eq.attribute_bonus("Wits") == 1


# --- Uniques ----------------------------------------------------------------

def test_a_named_unique_carries_fixed_characterful_stats():
    e = content.angolar.equippable
    assert content.angolar.name == "Angolar, the Ford-blade"
    assert e.equipment_type == EquipmentType.WEAPON
    assert e.damage == "2d6"
    assert e.attack_bonus == 2
    assert e.pierce == 1
    assert (e.bonus_vs, e.bonus_vs_damage) == ("orc", 2)
    assert content.angolar in content.UNIQUES


def test_unique_armour_and_accessory_exist_and_read_legibly():
    assert content.mail_of_the_last_watch.equippable.soak_bonus == 3
    cloak = content.cloak_of_lorien.equippable
    assert cloak.equipment_type == EquipmentType.ACCESSORY
    assert cloak.attributes.get("Wits") == 1
    assert cloak.stealth_bonus == 3


# --- Stat line (visible on pickup, no identification) -----------------------

def test_stat_line_reads_as_legible_numbers():
    assert content.angolar.equippable.stat_line() == (
        "dmg 2d6 · +2 hit · pierce 1 · +2 vs orcs · load 2"
    )
    assert content.mail_corslet.equippable.stat_line() == "soak 2 · load 3"
    assert content.ranger_star.equippable.stat_line() == "+1 Wits"


def test_accessories_and_uniques_are_reachable_in_play():
    # Authored gear must be obtainable, not test-only: accessories appear in the
    # depth item tables and a Unique waits in the deeps.
    deep = dict(content.items_for_depth(3))
    assert content.ranger_star in dict(content.items_for_depth(1))
    assert content.elven_brooch in dict(content.items_for_depth(2))
    for unique in content.UNIQUES:
        assert unique in deep


def test_pickup_message_shows_the_stat_line():
    engine, gm, player = make_world()
    item = content.short_sword.spawn(gm, 2, 1)  # on the player's tile
    from lonelands.actions import PickupAction
    PickupAction(player).perform()
    msg = engine.message_log.messages[-1].plain_text
    assert "short sword" in msg and item.equippable.stat_line() in msg
