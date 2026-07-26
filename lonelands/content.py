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
from lonelands.components.fighter import Fighter
from lonelands.components.hero import Hero
from lonelands.components.inventory import Inventory
from lonelands.entity import Actor, Item
from lonelands.equipment_types import EquipmentType

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
        fighter=Fighter(
            endurance=26, defence=14, prowess=0, damage=1,
            injury=14, protection=0, attack_desc="strikes",
        ),
        hero=hero,
        inventory=Inventory(capacity=26),
        equipment=Equipment(),
    )
    return player


# ---------------------------------------------------------------------------
# Weapons & gear
# ---------------------------------------------------------------------------
def _weapon(name, char, dmg, injury, prof, load, edge=1, desc="") -> Item:
    return Item(
        char=char, color=color.weapon_c, name=name, description=desc,
        equippable=Equippable(
            EquipmentType.WEAPON, load=load, damage=dmg, edge=edge,
            injury=injury, proficiency=prof,
        ),
    )


dunedain_sword = _weapon(
    "Dúnedain sword", "/", 5, 16, "Swords", 2,
    desc="A long, leaf-bladed sword of the North-kingdom, its make older than any town near.",
)
short_sword = _weapon("short sword", "/", 4, 14, "Swords", 1, desc="A plain, serviceable blade.")
hunting_dagger = _weapon("hunting dagger", "-", 3, 12, "Daggers", 0, edge=2,
                         desc="Keen and quick; it bites deep on a true stroke.")
war_spear = _weapon("war spear", "|", 4, 16, "Spears", 2, desc="An ash-hafted spear.")

ranger_bow = Item(
    char="}", color=color.weapon_c, name="Ranger's bow",
    description="A tall bow of yew. (Ranged mastery awaits a later day on the road.)",
    equippable=Equippable(
        EquipmentType.RANGED, load=1, damage=4, edge=1, injury=14,
        proficiency="Bows", ranged=True,
    ),
)

leather_gear = Item(
    char="[", color=color.beast_c, name="Ranger's leathers",
    description="Weathered leather and a travel-worn cloak of Rangers' grey-green.",
    equippable=Equippable(EquipmentType.ARMOUR, load=1, protection_bonus=1),
)
mail_corslet = Item(
    char="[", color=(0x9A, 0x9E, 0xA6), name="corslet of mail",
    description="A shirt of riveted rings, heavy but stalwart.",
    equippable=Equippable(EquipmentType.ARMOUR, load=3, protection_bonus=2),
)
buckler = Item(
    char=")", color=(0x8A, 0x6E, 0x44), name="buckler",
    description="A small round shield, easy to bear.",
    equippable=Equippable(EquipmentType.SHIELD, load=1, defence_bonus=1),
)
travellers_hood = Item(
    char="^", color=color.beast_c, name="reinforced hood",
    description="A hood sewn with hidden bands of leather.",
    equippable=Equippable(EquipmentType.HELM, load=0, defence_bonus=1),
)

# ---------------------------------------------------------------------------
# Consumables
# ---------------------------------------------------------------------------
athelas = Item(
    char="*", color=color.herb_c, name="athelas leaves",
    description="Kingsfoil. Of little worth to the unlearned, but of virtue in the hands of a healer.",
    consumable=consumable.RemedyConsumable(amount=8),
)
healing_herbs = Item(
    char="*", color=color.herb_c, name="healing herbs",
    description="Bundled field herbs to bind a hurt.",
    consumable=consumable.HealingConsumable(amount=6),
)
lembas = Item(
    char="%", color=(0xD8, 0xD0, 0xA0), name="waybread",
    description="Wrapped in leaves; a small bite lifts the heart on a long road.",
    consumable=consumable.HopeConsumable(amount=3),
)
miruvor = Item(
    char="!", color=color.hope_gain, name="draught of the Dúnedain",
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
# Creatures of Eriador
# ---------------------------------------------------------------------------
def _beast(char, name, col, endurance, defence, prowess, damage, xp,
           injury=13, protection=0, ai=HostileEnemy, desc="mauls", edge=1,
           attack=12) -> Actor:
    return Actor(
        char=char, color=col, name=name, ai_cls=ai,
        fighter=Fighter(
            endurance=endurance, defence=defence, prowess=prowess, damage=damage,
            injury=injury, protection=protection, attack_desc=desc, xp_reward=xp,
            edge=edge, attack=attack,
        ),
        inventory=Inventory(0),
        equipment=Equipment(),
    )


# Routine foes grant no experience: advancement is meant to come from quests
# (and the rare, formidable foe below), not from clearing rank-and-file mobs.
# `attack` is the TN the player's Parry (Battle) test must meet when the foe
# strikes: higher = harder to turn aside. Tuned for a "moderate" feel against a
# starting Battle of 2 — a lone foe is manageable, a pack is deadly.
cave_goblin = _beast("g", "cave-goblin", color.orc_c, 8, 11, 1, 3, 0,
                     desc="claws", attack=12)
orc_soldier = _beast("o", "orc soldier", color.orc_c, 14, 12, 2, 4, 0,
                     injury=14, protection=1, desc="hacks at", attack=13)
orc_archer = _beast("o", "orc bowman", (0x94, 0xA8, 0x60), 11, 12, 2, 3, 0,
                    desc="looses at", attack=12)
great_spider = _beast("s", "great spider", color.beast_c, 12, 13, 2, 3, 0,
                      desc="bites", edge=2, attack=13)
# The barrow-wight is the one foe worth experience: a tough, named undead that
# only stirs in the deep barrow. Kept modest so quests remain the main path.
wight = _beast("W", "barrow-wight", color.undead_c, 22, 13, 3, 5, 10,
               injury=16, protection=2, desc="chills", attack=15)

wolf = _beast("w", "grey wolf", color.wolf_c, 10, 13, 2, 3, 0, ai=SkittishBeast,
              desc="snaps at", attack=12)
warg = _beast("W", "warg", color.wolf_c, 16, 13, 3, 4, 0, desc="savages", attack=14)


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
