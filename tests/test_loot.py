"""Loot & economy tests.

Covers the three seams called out in issue #31: the Value → sell-price math, a
weighted loot-roll resolution, and inventory stack-merging — plus an end-to-end
check that `Fighter.die()` pays a slain foe's loot into the purse / onto its
corpse tile."""
from __future__ import annotations

import pytest

from lonelands import content
from lonelands.components.fighter import Coins, resolve_roll
from lonelands.components.inventory import Inventory
from lonelands.dice import set_seed
from lonelands.engine import Engine
from lonelands.entity import Actor, Item
from lonelands.exceptions import Impossible
from lonelands.game_map import GameMap


def make_world():
    player = content.make_player()
    engine = Engine(player)
    gm = GameMap(engine, 10, 10)
    engine.game_map = gm
    player.place(5, 5, gm)
    return engine, gm, player


# --- Value → sell price ------------------------------------------------------

def test_sell_price_is_floor_of_half_value():
    assert content.sell_price(content.short_sword) == 6   # 12 → 6
    assert content.sell_price(content.buckler) == 4        # 8 → 4


def test_sell_price_floors_and_has_a_one_coin_minimum():
    assert content.sell_price(content.lembas) == 1         # floor(1.5) → 1
    assert content.sell_price(Item(name="chip", value=1)) == 1  # max(1, 0) → 1


def test_value_zero_item_is_not_sellable():
    assert content.sell_price(content.star_brooch) == 0
    assert content.sell_price(content.dunedain_sword) == 0


def test_buy_prices_are_unchanged_from_the_old_shop_prices():
    # Values were seeded from the pre-#31 shop prices; buying must cost the same.
    expected = {
        content.short_sword: 12, content.war_spear: 10, content.buckler: 8,
        content.leather_gear: 10, content.travellers_hood: 6,
        content.healing_herbs: 4, content.athelas: 6, content.lembas: 3,
        content.hunting_dagger: 7,
    }
    for item, price in expected.items():
        assert item.value == price


# --- Weighted roll resolution ------------------------------------------------

def test_roll_with_a_single_slice_always_returns_it():
    sentinel = object()
    assert resolve_roll([(sentinel, 5)]) is sentinel


def test_roll_respects_weights_over_many_draws():
    set_seed(1234)
    a, b = object(), object()
    counts = {a: 0, b: 0}
    for _ in range(4000):
        counts[resolve_roll([(a, 90), (b, 10)])] += 1
    # ~90/10 split; wide tolerance so the test isn't seed-fragile.
    assert counts[a] > counts[b] * 4


def test_roll_can_yield_nothing():
    # A roll that is entirely the "nothing" slice always resolves to None.
    assert resolve_roll([(None, 1)]) is None


# --- Inventory stacking ------------------------------------------------------

def _stackable(name="wolf-pelt", value=6):
    return Item(name=name, value=value, stackable=True)


def test_add_merges_stackable_items_of_the_same_name():
    inv = Inventory(capacity=10)
    inv.add(_stackable())
    inv.add(_stackable())
    assert len(inv.items) == 1
    assert inv.items[0].quantity == 2


def test_add_merges_incoming_quantity():
    inv = Inventory(capacity=10)
    inv.add(_stackable())
    incoming = _stackable()
    incoming.quantity = 3
    inv.add(incoming)
    assert inv.items[0].quantity == 4


def test_distinct_stackables_take_separate_slots():
    inv = Inventory(capacity=10)
    inv.add(_stackable("wolf-pelt"))
    inv.add(_stackable("warg-pelt"))
    assert len(inv.items) == 2


def test_equipment_never_stacks():
    inv = Inventory(capacity=10)
    from lonelands import content as c
    import copy
    inv.add(copy.deepcopy(c.short_sword))
    inv.add(copy.deepcopy(c.short_sword))
    assert len(inv.items) == 2  # equipment is one-per-slot


def test_merging_into_a_full_pack_still_works():
    inv = Inventory(capacity=1)
    inv.add(_stackable())
    inv.add(_stackable())  # no new slot needed
    assert inv.items[0].quantity == 2


def test_add_raises_when_a_new_slot_is_needed_and_pack_is_full():
    inv = Inventory(capacity=1)
    inv.add(_stackable("wolf-pelt"))
    with pytest.raises(Impossible):
        inv.add(_stackable("warg-pelt"))


# --- Fighter.die() loot resolution ------------------------------------------

def _kill(foe):
    foe.fighter.endurance = 0  # setter triggers die()


def test_coins_go_straight_into_the_purse():
    engine, gm, player = make_world()
    foe = content.cave_goblin.spawn(gm, 3, 3)
    foe.fighter.loot = [[(Coins(4, 4), 1)]]  # guaranteed 4 coins
    start = player.hero.coins
    _kill(foe)
    assert player.hero.coins == start + 4


def test_trade_goods_drop_onto_the_corpse_tile():
    engine, gm, player = make_world()
    foe = content.wolf.spawn(gm, 3, 3)
    foe.fighter.loot = [[(content.wolf_pelt, 1)]]  # guaranteed pelt
    _kill(foe)
    dropped = [it for it in gm.items if it.x == 3 and it.y == 3]
    assert any(it.name == "wolf-pelt" for it in dropped)


def test_nothing_slice_drops_nothing():
    engine, gm, player = make_world()
    foe = content.wolf.spawn(gm, 3, 3)
    foe.fighter.loot = [[(None, 1)]]
    start = player.hero.coins
    _kill(foe)
    assert player.hero.coins == start
    assert not [it for it in gm.items if it.x == 3 and it.y == 3]


def test_wight_grants_xp_and_carries_loot():
    # Post-ADR-0005 (#37) every foe grants XP; the wight, as a tough named
    # undead, still pays the largest kill-XP and keeps its grave-hoard loot.
    assert content.wight.fighter.xp_reward > 0
    assert content.wight.fighter.loot  # grave-hoard coin roll


def test_every_routine_foe_has_a_loot_table():
    for foe in (content.cave_goblin, content.orc_soldier, content.orc_archer,
                content.great_spider, content.wolf, content.warg, content.wight):
        assert foe.fighter.loot, f"{foe.name} has no loot table"
