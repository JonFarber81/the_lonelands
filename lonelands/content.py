"""Concrete game content: the player, creatures, and items of the Lonelands.

Everything here is a *template*. Call `template.spawn(gamemap, x, y)` to drop a
fresh copy into the world."""
from __future__ import annotations

from typing import List, Tuple

from lonelands import color, overworld
from lonelands.components import consumable
from lonelands.components.ai import HostileEnemy, SkittishBeast
from lonelands.components.equipment import Equipment
from lonelands.components.equippable import Equippable
from lonelands.components.fighter import Coins, Fighter
from lonelands.components.hero import Hero
from lonelands.components.inventory import Inventory
from lonelands.entity import Actor, Item
from lonelands.equipment_types import EquipmentType

# ---------------------------------------------------------------------------
# Economy: a merchant sells at an item's Value and buys it back at a fraction.
# ---------------------------------------------------------------------------
SELL_FRACTION = 0.5


def sell_price(item: Item) -> int:
    """What a merchant pays the hero for `item`: floor(Value × SELL_FRACTION),
    at least 1 coin. Value 0 (not sellable) yields 0."""
    if item.value <= 0:
        return 0
    return max(1, int(item.value * SELL_FRACTION))

# ---------------------------------------------------------------------------
# The player: Tarandir, a Ranger of the North whom the Bree-folk call
# "Greycloak", alone in the Wild (TOR's solo "Strider mode").
# ---------------------------------------------------------------------------
def make_player() -> Actor:
    hero = Hero(
        attributes={"Strength": 6, "Heart": 4, "Wits": 5},
        skills={
            "Awe": 1, "Athletics": 2, "Awareness": 3, "Hunting": 3, "Craft": 1,
            "Enhearten": 1, "Travel": 3, "Insight": 2, "Healing": 2, "Battle": 2,
            "Persuade": 1, "Stealth": 2, "Scan": 3, "Explore": 3, "Lore": 2,
        },
        proficiencies={"Swords": 3, "Bows": 2, "Spears": 1, "Daggers": 1},
        max_hope=12,
        valour=2,
        wisdom=2,
        culture="Ranger of the North",
        calling="Warden",
        true_name="Tarandir",
    )
    player = Actor(
        char="@",
        color=color.player_c,
        name="Greycloak",
        ai_cls=None,
        # Phase 1: a temporary flat attack bonus stands in until the attribute-
        # and perk-derived to-hit of Phase 2 lands.
        fighter=Fighter(
            endurance=26, defence=14, attack_bonus=4, damage=1,
            soak=0, attack_desc="strikes",
        ),
        hero=hero,
        inventory=Inventory(capacity=26),
        equipment=Equipment(),
    )
    return player


# ---------------------------------------------------------------------------
# Weapons & gear
# ---------------------------------------------------------------------------
# Values seed from the current shop prices so buy prices are unchanged; items
# not sold in Bree keep Value 0 (not sellable) for now — selling gear you can't
# rebuy is deferred (issue #31, out of scope).
def _weapon(name, char, dmg, injury, prof, load, edge=1, desc="", value=0) -> Item:
    return Item(
        char=char, color=color.weapon_c, name=name, description=desc, value=value,
        equippable=Equippable(
            EquipmentType.WEAPON, load=load, damage=dmg, edge=edge,
            injury=injury, proficiency=prof,
        ),
    )


dunedain_sword = _weapon(
    "Dúnedain sword", "/", 5, 16, "Swords", 2,
    desc="A long, leaf-bladed sword of the North-kingdom, its make older than any town near.",
)
short_sword = _weapon("short sword", "/", 4, 14, "Swords", 1, value=12,
                      desc="A plain, serviceable blade.")
hunting_dagger = _weapon("hunting dagger", "-", 3, 12, "Daggers", 0, edge=2, value=7,
                         desc="Keen and quick; it bites deep on a true stroke.")
war_spear = _weapon("war spear", "|", 4, 16, "Spears", 2, value=10,
                    desc="An ash-hafted spear.")

ranger_bow = Item(
    char="}", color=color.weapon_c, name="Ranger's bow",
    description="A tall bow of yew. (Ranged mastery awaits a later day on the road.)",
    equippable=Equippable(
        EquipmentType.RANGED, load=1, damage=4, edge=1, injury=14,
        proficiency="Bows", ranged=True,
    ),
)

leather_gear = Item(
    char="[", color=color.beast_c, name="Ranger's leathers", value=10,
    description="Weathered leather and a travel-worn cloak of Rangers' grey-green.",
    equippable=Equippable(EquipmentType.ARMOUR, load=1, soak_bonus=1),
)
mail_corslet = Item(
    char="[", color=(0x9A, 0x9E, 0xA6), name="corslet of mail",
    description="A shirt of riveted rings, heavy but stalwart.",
    equippable=Equippable(EquipmentType.ARMOUR, load=3, soak_bonus=2),
)
buckler = Item(
    char=")", color=(0x8A, 0x6E, 0x44), name="buckler", value=8,
    description="A small round shield, easy to bear.",
    equippable=Equippable(EquipmentType.SHIELD, load=1, defence_bonus=1),
)
travellers_hood = Item(
    char="^", color=color.beast_c, name="reinforced hood", value=6,
    description="A hood sewn with hidden bands of leather.",
    equippable=Equippable(EquipmentType.HELM, load=0, defence_bonus=1),
)

# ---------------------------------------------------------------------------
# Consumables
# ---------------------------------------------------------------------------
athelas = Item(
    char="*", color=color.herb_c, name="athelas leaves", value=6, stackable=True,
    description="Kingsfoil. Of little worth to the unlearned, but of virtue in the hands of a healer.",
    consumable=consumable.RemedyConsumable(amount=8),
)
healing_herbs = Item(
    char="*", color=color.herb_c, name="healing herbs", value=4, stackable=True,
    description="Bundled field herbs to bind a hurt.",
    consumable=consumable.HealingConsumable(amount=6),
)
lembas = Item(
    char="%", color=(0xD8, 0xD0, 0xA0), name="waybread", value=3, stackable=True,
    description="Wrapped in leaves; a small bite lifts the heart on a long road.",
    consumable=consumable.HopeConsumable(amount=3),
)
miruvor = Item(
    char="!", color=color.hope_gain, name="draught of the Dúnedain", stackable=True,
    description="A cordial that kindles new strength in the weary heart.",
    consumable=consumable.HopeConsumable(amount=5),
)

# Quest item — the goal of the main quest.
star_brooch = Item(
    char="*", color=(0xE6, 0xE0, 0xC0), name="star-brooch of Arnor",
    description="A silver brooch wrought as a many-rayed star: the token of the last "
                "warden of Amon Gûl. Old Dírhael will wish to see this.",
)

# ---------------------------------------------------------------------------
# Trade-goods — sold for coin in Bree; their only purpose is their Value.
# ---------------------------------------------------------------------------
def _trade_good(name, char, col, value, desc) -> Item:
    return Item(char=char, color=col, name=name, description=desc,
                value=value, stackable=True)


wolf_pelt = _trade_good("wolf-pelt", "~", color.wolf_c, 6,
                        "The grey hide of a wolf, worth coin to a Bree furrier.")
warg_pelt = _trade_good("warg-pelt", "~", color.wolf_c, 10,
                        "The great pelt of a warg — worth more than a common wolf's.")
spider_silk = _trade_good("spider-silk", "~", color.beast_c, 8,
                          "A skein of tough, glistening silk drawn from a great spider.")
orc_trophy = _trade_good("orc-trophy", "\"", color.orc_c, 5,
                         "A crude token stripped from a slain orc; proof of the deed.")
wolf_fang = _trade_good("wolf-fang", "'", color.wolf_c, 4,
                        "A long curved fang — a curio the folk of Bree will pay a little for.")


# ---------------------------------------------------------------------------
# Creatures of Eriador
# ---------------------------------------------------------------------------
def _beast(char, name, col, endurance, defence, attack_bonus, damage, xp,
           soak=0, bleed_on_hit=0, ai=HostileEnemy, desc="mauls", loot=None) -> Actor:
    return Actor(
        char=char, color=col, name=name, ai_cls=ai,
        fighter=Fighter(
            endurance=endurance, defence=defence, attack_bonus=attack_bonus,
            damage=damage, soak=soak, bleed_on_hit=bleed_on_hit,
            attack_desc=desc, xp_reward=xp, loot=loot,
        ),
        inventory=Inventory(0),
        equipment=Equipment(),
    )


# Combat is the d20 core: a foe rolls `d20 + attack_bonus` against the hero's
# Defence, and the hero rolls the same against the foe's `defence`. `damage` is a
# dice spec, rolled and then reduced by the target's `soak`. `bleed_on_hit` marks
# a heavy/venomous foe that opens a Bleed on any landed blow.
# Tuned for a "moderate" feel — a lone foe is manageable, a pack is deadly.
# Loot tables: each is a list of independent weighted rolls (see fighter.Coins /
# resolve_roll). A `None` slice is "nothing"; a kill may resolve several rolls.
# Danger and reward climb together — warg/orc-packs (Dark/Perilous bands) pay
# best. Balance anchor: healing herb = 4 coins, short sword = 12.
cave_goblin = _beast("g", "cave-goblin", color.orc_c, 8, 11, 3, "1d4", 0,
                     desc="claws",
                     loot=[[(None, 60), (Coins(1, 2), 40)]])
orc_soldier = _beast("o", "orc soldier", color.orc_c, 14, 12, 4, "1d6", 0,
                     soak=1, desc="hacks at",
                     loot=[
                         [(None, 35), (Coins(2, 4), 60), (Coins(4, 6), 5)],
                         [(None, 88), (orc_trophy, 12)],
                     ])
orc_archer = _beast("o", "orc bowman", (0x94, 0xA8, 0x60), 11, 12, 4, "1d4", 0,
                    desc="looses at",
                    loot=[[(None, 50), (Coins(1, 3), 50)]])
great_spider = _beast("s", "great spider", color.beast_c, 12, 13, 4, "1d6", 0,
                      bleed_on_hit=1, desc="bites",
                      loot=[[(None, 45), (spider_silk, 55)]])
# The barrow-wight is the one foe worth experience: a tough, named undead that
# only stirs in the deep barrow. Kept modest so quests remain the main path. It
# keeps its XP and additionally drops a grave-hoard of coins.
wight = _beast("W", "barrow-wight", color.undead_c, 22, 13, 6, "1d8+1", 10,
               soak=2, bleed_on_hit=1, desc="chills",
               loot=[[(None, 40), (Coins(5, 10), 60)]])

wolf = _beast("w", "grey wolf", color.wolf_c, 10, 13, 4, "1d4", 0, ai=SkittishBeast,
              desc="snaps at",
              loot=[[(None, 35), (wolf_pelt, 60), (wolf_fang, 5)]])
warg = _beast("W", "warg", color.wolf_c, 16, 13, 5, "1d6", 0, bleed_on_hit=1,
              desc="savages",
              loot=[[(None, 25), (warg_pelt, 72), (wolf_fang, 3)]])


# Depth-weighted spawn tables: (template, weight)
def monsters_for_depth(depth: int) -> List[Tuple[Actor, int]]:
    table: List[Tuple[Actor, int]] = [(cave_goblin, 30)]
    if depth >= 1:
        table += [(orc_soldier, 20), (great_spider, 12)]
    if depth >= 2:
        table += [(orc_archer, 12), (warg, 8)]
    if depth >= 3:
        table += [(wight, 6)]
    return table


def items_for_depth(depth: int) -> List[Tuple[Item, int]]:
    table: List[Tuple[Item, int]] = [
        (healing_herbs, 24), (lembas, 12), (hunting_dagger, 6),
    ]
    if depth >= 1:
        table += [(athelas, 8), (short_sword, 5), (buckler, 4), (leather_gear, 4)]
    if depth >= 2:
        table += [(miruvor, 6), (travellers_hood, 4), (war_spear, 4)]
    if depth >= 3:
        table += [(mail_corslet, 4)]
    return table


WILD_BEASTS = [(wolf, 3), (great_spider, 1)]


# ---------------------------------------------------------------------------
# Band → wandering-beast model (ADR 0003)
# ---------------------------------------------------------------------------
# Every Surface seeds wandering beasts from its Region's **band**, regardless of
# terrain: a (count_range, weighted-table) pair. "Level" is expressed as *which*
# creatures roam — Free lands see a lone wolf at worst; Perilous lands crawl with
# wargs, spiders, and the Enemy's orcs. Tune the counts/weights here, in one
# place. Keyed by the band constants in `overworld` so the names can't drift.
BAND_BEASTS = {
    overworld.FREE:     ((0, 1), [(wolf, 1)]),
    overworld.WILD:     ((2, 4), WILD_BEASTS),
    overworld.DARK:     ((3, 5), [(wolf, 2), (warg, 2), (orc_soldier, 2), (great_spider, 1)]),
    overworld.PERILOUS: ((4, 6), [(warg, 2), (great_spider, 3), (orc_soldier, 2), (orc_archer, 1)]),
}
