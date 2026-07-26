"""Affix generator (Phase 6, issue #40).

Procedural loot per ADR 0005: a rarity roll (Plain/Fine/Rare) drives up to two
affixes — a prefix adjective and a suffix ``of`` clause — that touch only the
numbers a piece already speaks in, so its own stat line shows the full result
(no identification). Covers the three called-out seams: seeded generation
determinism, name assembly, and the rarity distribution.
"""
from __future__ import annotations

import copy

from lonelands import affixes, content, procgen, setup_game
from lonelands.dice import set_seed
from lonelands.equipment_types import EquipmentType


# --- Rarity roll ------------------------------------------------------------

def test_rarity_roll_is_one_of_the_three_bands():
    set_seed(0)
    seen = {affixes.roll_rarity() for _ in range(200)}
    assert seen <= {affixes.PLAIN, affixes.FINE, affixes.RARE}


def test_rarity_distribution_favours_plain_over_rare():
    set_seed(7)
    counts = {affixes.PLAIN: 0, affixes.FINE: 0, affixes.RARE: 0}
    for _ in range(6000):
        counts[affixes.roll_rarity()] += 1
    # Plain dominates; Rare is the genuine find. Wide margins keep it seed-stable.
    assert counts[affixes.PLAIN] > counts[affixes.FINE] > counts[affixes.RARE]
    assert counts[affixes.RARE] > 0  # but Rare does happen


def test_depth_tilts_the_odds_toward_the_richer_bands():
    def rare_share(depth):
        set_seed(99)
        n = sum(affixes.roll_rarity(depth) == affixes.RARE for _ in range(6000))
        return n
    assert rare_share(3) > rare_share(0)


# --- Rarity → affix count ---------------------------------------------------

def test_plain_returns_the_base_unchanged():
    item = affixes.generate(content.short_sword, rarity=affixes.PLAIN)
    assert item.name == "short sword"
    assert item.value == content.short_sword.value
    assert item.equippable.attack_bonus == 0


def test_fine_adds_exactly_one_affix():
    # Across seeds a Fine roll adds either a prefix (no " of ") or a suffix, never
    # both — the name gains exactly one of the two slots.
    for seed in range(40):
        set_seed(seed)
        item = affixes.generate(content.short_sword, rarity=affixes.FINE)
        has_prefix = not item.name.startswith("short sword")
        has_suffix = " of " in item.name
        assert has_prefix ^ has_suffix, item.name


def test_rare_adds_a_prefix_and_a_suffix():
    set_seed(3)
    item = affixes.generate(content.short_sword, rarity=affixes.RARE)
    assert not item.name.startswith("short sword")  # a prefix leads
    assert " of " in item.name                      # a suffix trails


# --- Name assembly ----------------------------------------------------------

def test_name_reads_prefix_base_of_suffix():
    # Force a specific, legible pairing by seeding to a known-good draw.
    for seed in range(500):
        set_seed(seed)
        item = affixes.generate(content.short_sword, rarity=affixes.RARE)
        if item.name == "keen short sword of ruin":
            break
    else:
        raise AssertionError("expected a 'keen … of ruin' pairing under some seed")
    assert item.equippable.attack_bonus == 1   # keen
    # 'of ruin' adds +1 damage on top of the base 4.
    assert item.equippable.damage == 5


def test_stat_line_is_visible_and_reflects_the_affixes():
    # No identification: the rolled numbers show straight away on the stat line.
    item = affixes.generate(content.short_sword, rarity=affixes.RARE)
    assert item.equippable.stat_line() != content.short_sword.equippable.stat_line()


# --- Determinism ------------------------------------------------------------

def test_same_seed_generates_the_identical_item():
    set_seed(2024)
    a = affixes.generate(content.short_sword)
    set_seed(2024)
    b = affixes.generate(content.short_sword)
    assert a.name == b.name
    assert a.value == b.value
    assert a.equippable.stat_line() == b.equippable.stat_line()


def test_generate_leaves_the_base_template_untouched():
    before_name = content.short_sword.name
    before_hit = content.short_sword.equippable.attack_bonus
    before_value = content.short_sword.value
    set_seed(5)
    for _ in range(20):
        affixes.generate(content.short_sword, rarity=affixes.RARE)
    assert content.short_sword.name == before_name
    assert content.short_sword.equippable.attack_bonus == before_hit
    assert content.short_sword.value == before_value


# --- Affixes suit the gear category -----------------------------------------

def test_weapon_only_takes_weapon_affixes():
    # A weapon's rolled words come from the weapon pool: hit/damage/pierce/bane —
    # never a Defence/attribute word meant for armour or a token.
    weapon_words = {a.word for a in affixes._PREFIXES + affixes._SUFFIXES
                    if a.category == affixes.WEAPON}
    for seed in range(60):
        set_seed(seed)
        item = affixes.generate(content.short_sword, rarity=affixes.RARE)
        # Nothing but the base numbers should have moved off-category.
        assert item.equippable.defence_bonus == 0
        assert item.equippable.soak_bonus == 0
        assert item.equippable.attributes == {}
        words = item.name.replace("short sword", "").replace(" of ", " ").split()
        assert set(words) <= weapon_words


def test_armour_affix_raises_soak_or_defence():
    set_seed(1)
    moved = False
    for _ in range(40):
        item = affixes.generate(content.mail_corslet, rarity=affixes.RARE)
        eq = item.equippable
        if eq.soak_bonus > content.mail_corslet.equippable.soak_bonus or \
                eq.defence_bonus > content.mail_corslet.equippable.defence_bonus:
            moved = True
    assert moved


def test_accessory_of_the_beast_lends_an_attribute():
    for seed in range(200):
        set_seed(seed)
        item = affixes.generate(content.ranger_star, rarity=affixes.FINE)
        if " of the bear" in item.name:
            assert item.equippable.attributes.get("Brawn") == 1
            return
    raise AssertionError("no seed rolled the '+Brawn' accessory suffix")


# --- Value ------------------------------------------------------------------

def test_an_affix_raises_the_coin_value():
    item = affixes.generate(content.short_sword, rarity=affixes.RARE)
    assert item.value > content.short_sword.value


# --- Uniques & non-gear are passed over -------------------------------------

def test_a_named_unique_is_never_affixed():
    clone = copy.deepcopy(content.angolar)
    out = affixes.apply_affixes(clone, rarity=affixes.RARE)
    assert out.name == "Angolar, the Ford-blade"
    assert out is clone  # returned unchanged, in place


def test_is_affixable_rejects_consumables_and_uniques():
    assert affixes.is_affixable(content.short_sword)
    assert not affixes.is_affixable(content.healing_herbs)   # consumable
    assert not affixes.is_affixable(content.angolar)         # Unique
    assert not affixes.is_affixable(content.star_brooch)     # plain quest item


def test_apply_affixes_on_a_consumable_returns_it_unchanged():
    clone = copy.deepcopy(content.lembas)
    out = affixes.apply_affixes(clone, rarity=affixes.RARE)
    assert out is clone
    assert out.name == "waybread"


# --- Category coverage: every category can roll a Rare ----------------------

def test_every_category_has_a_prefix_and_a_suffix():
    for cat in (affixes.WEAPON, affixes.ARMOUR, affixes.ACCESSORY):
        assert affixes._pool(affixes._PREFIXES, cat), f"{cat} has no prefix"
        assert affixes._pool(affixes._SUFFIXES, cat), f"{cat} has no suffix"


def test_category_of_maps_every_slot_type():
    for etype in EquipmentType:
        assert affixes._CATEGORY_FOR_TYPE[etype] in (
            affixes.WEAPON, affixes.ARMOUR, affixes.ACCESSORY)


# --- Procgen integration: gear drops roll affixes ---------------------------

def _all_gear(gm):
    return [it for it in gm.items
            if it.equippable is not None and not it.equippable.unique]


def test_generated_gear_is_legible_and_some_is_affixed():
    # Build many deep Levels; every ordinary piece of gear reads as numbers, and
    # across the run at least one has rolled an affix (a changed name).
    set_seed(11)
    engine = setup_game.new_game()
    affixed = 0
    total = 0
    for seed in range(40):
        set_seed(1000 + seed)
        gm = procgen.generate_ruin(engine, depth=3, treasure=False)
        for item in _all_gear(gm):
            total += 1
            assert item.equippable.stat_line()  # legible, no identification
            base_names = {
                "short sword", "war spear", "buckler", "Ranger's leathers",
                "reinforced hood", "corslet of mail", "star of the Dúnedain",
                "leaf-brooch of green", "hunting dagger",
            }
            if item.name not in base_names:
                affixed += 1
    assert total > 0
    assert affixed > 0, "no generated gear ever rolled an affix"


def test_generated_uniques_are_never_affixed():
    engine = setup_game.new_game()
    for seed in range(60):
        set_seed(2000 + seed)
        gm = procgen.generate_ruin(engine, depth=3, treasure=False)
        for item in gm.items:
            if item.equippable is not None and item.equippable.unique:
                assert item.name in {u.name for u in content.UNIQUES}


def test_a_foe_drop_of_gear_rolls_its_affixes():
    # "Done when: Foes … can yield generated Fine/Rare items" (#40). A foe whose
    # loot table drops gear hands it over already affixed.
    from lonelands.components.fighter import Fighter
    from lonelands.engine import Engine
    from lonelands.game_map import GameMap

    player = content.make_player()
    engine = Engine(player)
    gm = GameMap(engine, 10, 10)
    engine.game_map = gm
    player.place(5, 5, gm)

    for seed in range(60):
        set_seed(3000 + seed)
        foe = content.orc_soldier.spawn(gm, 3, 3)
        foe.fighter.loot = [[(content.short_sword, 1)]]  # guaranteed sword drop
        foe.fighter.endurance = 0  # setter triggers die() → loot resolution
        dropped = [it for it in gm.items if it.x == 3 and it.y == 3]
        swords = [it for it in dropped if "sword" in it.name]
        assert swords, "the foe dropped no sword"
        if any(it.name != "short sword" for it in swords):
            return  # a Fine/Rare roll landed — seam confirmed
        for it in list(gm.items):  # clear the tile for the next seed
            gm.entities.discard(it)
    raise AssertionError("no foe drop ever rolled an affix across 60 seeds")


def test_add_damage_handles_a_dice_spec():
    eq = copy.deepcopy(content.short_sword.equippable)
    eq.damage = "2d6+1"
    affixes._add_damage(eq, 1)
    assert eq.damage == "2d6+2"
    eq.damage = "1d8"
    affixes._add_damage(eq, 2)
    assert eq.damage == "1d8+2"
