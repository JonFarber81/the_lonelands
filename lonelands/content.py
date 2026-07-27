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
        attributes={"Brawn": 3, "Wits": 2, "Will": 2},
        culture="Ranger of the North",
        calling="Warden",
        true_name="Tarandir",
    )
    player = Actor(
        char="@",
        color=color.player_c,
        name="Greycloak",
        ai_cls=None,
        # The hero's Defence and to-hit fold in his attributes (Wits → Defence,
        # Brawn → attack); the base numbers here are the residue on top of those.
        fighter=Fighter(
            endurance=26, defence=12, attack_bonus=1, damage=1,
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
def _weapon(name, char, dmg, load, *, attack_bonus=0, pierce=0,
            bonus_vs="", bonus_vs_damage=0, desc="", value=0, unique=False) -> Item:
    return Item(
        char=char, color=color.weapon_c, name=name, description=desc, value=value,
        equippable=Equippable(
            EquipmentType.WEAPON, load=load, damage=dmg, attack_bonus=attack_bonus,
            pierce=pierce, bonus_vs=bonus_vs, bonus_vs_damage=bonus_vs_damage,
            unique=unique,
        ),
    )


dunedain_sword = _weapon(
    "Dúnedain sword", "/", 5, 2, attack_bonus=1,
    desc="A long, leaf-bladed sword of the North-kingdom, its make older than any town near.",
)
short_sword = _weapon("short sword", "/", 4, 1, value=12,
                      desc="A plain, serviceable blade.")
hunting_dagger = _weapon("hunting dagger", "-", 3, 0, attack_bonus=1, value=7,
                         desc="Keen and quick; it bites deep on a true stroke.")
# A spear's reach lets it slip past armour: a small pierce is its property.
war_spear = _weapon("war spear", "|", 4, 2, pierce=1, value=10,
                    desc="An ash-hafted spear; its point slips past mail.")
# Dwarf-make: a short, heavy hand-axe of the Blue-Mountain smiths, sold on the
# East Road by travelling Dwarves. Blunt reliability over a Ranger's finesse.
dwarf_axe = _weapon("dwarf-make hand-axe", "/", 5, 2, attack_bonus=1, value=16,
                    desc="A stout single-hand axe forged in the Blue Mountains; "
                         "its bearded head bites through a shield.")

# Bows go in the `ranged` slot and are loosed with `f` (ADR 0006). Each carries
# damage dice and an **effective range** — the reach within which a Shot takes no
# falloff. A bow is keyed off Wits, not Brawn, and spends an arrow per Shot.
def _bow(name, dmg, effective_range, load, *, attack_bonus=0, desc="", value=0,
         unique=False) -> Item:
    return Item(
        char="}", color=color.weapon_c, name=name, description=desc, value=value,
        equippable=Equippable(
            EquipmentType.RANGED, load=load, damage=dmg, ranged=True,
            effective_range=effective_range, attack_bonus=attack_bonus,
            unique=unique,
        ),
    )


shortbow = _bow(
    "shortbow", "1d6", 4, 1, value=15,
    desc="A short bow of horn and yew, quick to draw; its arrows carry true out "
         "to middling range.",
)
longbow = _bow(
    "longbow", "1d8", 6, 2, value=30,
    desc="A tall war-bow of the Dúnedain, its long stave sending shafts far and hard.",
)

# Arrows: the ammunition a bow spends — a fungible Stack in the pack, one spent
# per Shot, half of them recoverable off the target's tile (ADR 0006). Matched
# by AMMO_NAME wherever the Shot flow needs "the quiver".
AMMO_NAME = "arrows"


def _quiver(n: int) -> Item:
    return Item(
        char="\\", color=(0xB8, 0xA0, 0x78), name=AMMO_NAME, value=1,
        stackable=True, quantity=n,
        description="A sheaf of grey-fletched arrows for a bow.",
    )


arrows = _quiver(1)          # the canonical single-arrow template (shop unit, drops)
arrow_bundle = _quiver(4)    # a small sheaf a bow-foe leaves behind

# Armour splits two ways (ADR 0005): heavy gear grants **Soak** (subtracts from a
# blow), light gear and shields grant **+Defence** (harder to hit in the first
# place). So leathers now dodge rather than soak, mail soaks, shields add Defence.
leather_gear = Item(
    char="[", color=color.beast_c, name="Ranger's leathers", value=10,
    description="Weathered leather and a travel-worn cloak of Rangers' grey-green; "
                "light enough to slip a blow.",
    equippable=Equippable(EquipmentType.ARMOUR, load=1, defence_bonus=1),
)
mail_corslet = Item(
    char="[", color=(0x9A, 0x9E, 0xA6), name="corslet of mail", value=30,
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
# Accessories — the cloak/ring/token slot. Their pluses touch *non-combat*
# stats: +attribute, +Stealth, a Path synergy (ADR 0005). A +Wits token still
# sharpens Defence downstream, since Wits feeds it.
# ---------------------------------------------------------------------------
ranger_star = Item(
    char="*", color=(0xC0, 0xC4, 0xCE), name="star of the Dúnedain", value=14,
    description="A six-rayed silver star, the badge worn at a Ranger's shoulder. "
                "It quickens the wary eye.",
    equippable=Equippable(EquipmentType.ACCESSORY, attributes={"Wits": 1}),
)
elven_brooch = Item(
    char="*", color=(0x8E, 0xC8, 0x9A), name="leaf-brooch of green", value=12,
    description="A brooch shaped as a beech-leaf, elven-made; the eye slides "
                "past the one who wears it.",
    equippable=Equippable(EquipmentType.ACCESSORY, stealth_bonus=2,
                          path_synergy="the Hidden Path"),
)

# ---------------------------------------------------------------------------
# Uniques — hand-authored, named gear with fixed, characterful stats, outside
# the (later) Plain/Fine/Rare affix bands (ADR 0005). What you see is what it
# is; there is no identification.
# ---------------------------------------------------------------------------
angolar = _weapon(
    "Angolar, the Ford-blade", "/", "2d6", 2, attack_bonus=2, pierce=1,
    bonus_vs="orc", bonus_vs_damage=2, value=120, unique=True,
    desc="A grey Númenórean blade drawn from the Brandywine ford, its edge cold "
         "against the Enemy's brood. Runes name it Angolar.",
)
mail_of_the_last_watch = Item(
    char="[", color=(0xB6, 0xBE, 0xC8), name="Mail of the Last Watch", value=110,
    description="A hauberk of star-silver rings borne by the last warden of Amon "
                "Sûl; blows turn from it as rain from stone.",
    equippable=Equippable(EquipmentType.ARMOUR, load=3, soak_bonus=3, unique=True),
)
cloak_of_lorien = Item(
    char="(", color=(0x7C, 0xA6, 0x86), name="Grey Mantle of Lórien", value=90,
    description="A leaf-woven cloak out of the Golden Wood; the wearer walks "
                "unseen and thinks the clearer for it.",
    equippable=Equippable(EquipmentType.ACCESSORY, attributes={"Wits": 1},
                          stealth_bonus=3, path_synergy="the Hidden Path", unique=True),
)

UNIQUES: List[Item] = [angolar, mail_of_the_last_watch, cloak_of_lorien]

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
    description="Wrapped in leaves; a small bite restores vigour on a long road.",
    consumable=consumable.HealingConsumable(amount=4),
)
miruvor = Item(
    char="!", color=color.hope_gain, name="draught of the Dúnedain", value=8, stackable=True,
    description="A cordial that kindles new strength in the weary body.",
    consumable=consumable.HealingConsumable(amount=8),
)
# Southlinch — the pipe-weed grown on the sunny south slopes of Bree-hill, prized
# leaf the Staddle hobbits cure and sell. A quiet pipe eases a traveller's hurts.
pipe_weed = Item(
    char="%", color=(0x9C, 0x7A, 0x54), name="Southlinch pipe-weed", value=3, stackable=True,
    description="A twist of fragrant leaf grown on Bree-hill's south slope; a "
                "quiet pipe of it settles the nerves and eases small hurts.",
    consumable=consumable.HealingConsumable(amount=3),
)

# Quest item — the goal of the main quest.
star_brooch = Item(
    char="*", color=(0xE6, 0xE0, 0xC0), name="star-brooch of Arnor",
    description="A silver brooch wrought as a many-rayed star: the token of the last "
                "warden of Amon Gûl. Old Dírhael will wish to see this.",
)

# Quest item — the Archet woodcutters' lost felling-axe, an heirloom left in the
# Chetwood when fell things drove the coppice-gangs out. Carry it back to Archet.
felling_axe = Item(
    char="/", color=(0x8C, 0x6E, 0x46), name="woodwright's felling-axe",
    description="A broad, worn felling-axe, its haft dark with the grip of many "
                "hands; the Archet woodcutters will know it, and grieve or rejoice.",
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
           soak=0, bleed_on_hit=0, kind="", ai=HostileEnemy, desc="mauls",
           loot=None) -> Actor:
    return Actor(
        char=char, color=col, name=name, ai_cls=ai,
        fighter=Fighter(
            endurance=endurance, defence=defence, attack_bonus=attack_bonus,
            damage=damage, soak=soak, bleed_on_hit=bleed_on_hit, kind=kind,
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
# XP rewards (ADR-0005): every combat foe now grants experience, and levels come
# thick and fast — the curve asks 20 XP for level 1→2, so ~4-5 routine kills earns
# an early level. Reward tracks danger: weak skirmishers pay little, pack-hunters
# and the barrow-wight pay best. (Anchor: level 1→2 = 20 XP; see character.xp_to_next.)
cave_goblin = _beast("g", "cave-goblin", color.orc_c, 8, 11, 3, "1d4", 4,
                     kind="orc", desc="claws",
                     loot=[[(None, 60), (Coins(1, 2), 40)]])
orc_soldier = _beast("o", "orc soldier", color.orc_c, 14, 12, 4, "1d6", 7,
                     soak=1, kind="orc", desc="hacks at",
                     loot=[
                         [(None, 35), (Coins(2, 4), 60), (Coins(4, 6), 5)],
                         [(None, 88), (orc_trophy, 12)],
                     ])
orc_archer = _beast("o", "orc bowman", (0x94, 0xA8, 0x60), 11, 12, 4, "1d4", 5,
                    kind="orc", desc="looses at",
                    loot=[
                        [(None, 50), (Coins(1, 3), 50)],
                        [(None, 45), (arrow_bundle, 55)],  # a bowman leaves shafts
                    ])
great_spider = _beast("s", "great spider", color.beast_c, 12, 13, 4, "1d6", 6,
                      bleed_on_hit=1, kind="beast", desc="bites",
                      loot=[[(None, 45), (spider_silk, 55)]])
# The barrow-wight is the deadliest routine foe: a tough, named undead that only
# stirs in the deep barrow. It pays the richest XP of any foe and additionally
# drops a grave-hoard of coins.
wight = _beast("W", "barrow-wight", color.undead_c, 22, 13, 6, "1d8+1", 14,
               soak=2, bleed_on_hit=1, kind="undead", desc="chills",
               loot=[[(None, 40), (Coins(5, 10), 60)]])

wolf = _beast("w", "grey wolf", color.wolf_c, 10, 13, 4, "1d4", 5, ai=SkittishBeast,
              kind="beast", desc="snaps at",
              loot=[[(None, 35), (wolf_pelt, 60), (wolf_fang, 5)]])
warg = _beast("W", "warg", color.wolf_c, 16, 13, 5, "1d6", 8, bleed_on_hit=1,
              kind="beast", desc="savages",
              loot=[[(None, 25), (warg_pelt, 72), (wolf_fang, 3)]])

# --- Brigands (ADR 0007) -----------------------------------------------------
# Human predators who work the roads. The footpad is a weak knife-man; the
# highwayman a solid swordsman. Both are `kind="man"` with the plain HostileEnemy
# AI (they close and fight, they do not skulk like a beast). Loot is coin plus,
# now and then, the weapon off their belt.
footpad = _beast("b", "footpad", color.orc_c, 8, 11, 3, "1d4", 4,
                 kind="man", desc="knifes",
                 loot=[
                     [(None, 45), (Coins(1, 3), 55)],
                     [(None, 90), (hunting_dagger, 10)],
                 ])
highwayman = _beast("b", "highwayman", (0xB0, 0x7A, 0x4A), 14, 12, 4, "1d6", 7,
                    soak=1, kind="man", desc="cuts at",
                    loot=[
                        [(None, 30), (Coins(2, 5), 65), (Coins(5, 9), 5)],
                        [(None, 85), (short_sword, 15)],
                    ])

# --- Boar (ADR 0007) ---------------------------------------------------------
# An aggressive wild animal that hunts alone — no pack AI, just a bad temper and
# a goring tusk that opens a wound.
boar = _beast("q", "wild boar", (0x6B, 0x5A, 0x3E), 12, 11, 4, "1d6", 6,
              bleed_on_hit=1, kind="beast", desc="gores")


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
        (healing_herbs, 24), (lembas, 12), (hunting_dagger, 6), (arrow_bundle, 10),
    ]
    if depth >= 1:
        table += [(athelas, 8), (short_sword, 5), (buckler, 4), (leather_gear, 4),
                  (ranger_star, 3), (shortbow, 3)]
    if depth >= 2:
        table += [(miruvor, 6), (travellers_hood, 4), (war_spear, 4),
                  (elven_brooch, 3), (longbow, 2)]
    if depth >= 3:
        # The deeps hold the richest gear — and, rarely, a named Unique.
        table += [(mail_corslet, 4), (angolar, 1),
                  (mail_of_the_last_watch, 1), (cloak_of_lorien, 1)]
    return table


# ---------------------------------------------------------------------------
# Band → wandering-threat model (ADR 0007, was ADR 0003)
# ---------------------------------------------------------------------------
# Every Surface seeds **wandering threats** from its Region's **band**, regardless
# of terrain. A threat is one of three **kinds** — BRIGAND, WILD_ANIMAL, MONSTER —
# and a band is a *blend* of them, not one flat table: the blend (which kinds, in
# what proportion) is what makes settled country read differently from the Dark,
# not just the count. Free is animals-and-a-lone-footpad; Wild is brigands-and-
# animals with monsters *rare* (this is what keeps spiders and orcs off Bree's
# doorstep); Dark/Perilous are monster country.
#
# `procgen.apply_band_threats` reads this: for each of `randint(lo, hi)` threats it
# picks a kind by weight, then a member of that kind by weight (via `members_for`),
# then places it — honouring the road safety buffer for animals/monsters and the
# road-bias for brigands (see procgen). Tune it all here, in one place.
BRIGAND = "brigand"
WILD_ANIMAL = "wild_animal"
MONSTER = "monster"

# Members of each kind, as (template, weight) tables.
_BRIGANDS = [(footpad, 3), (highwayman, 2)]
_WILD_ANIMALS = [(wolf, 3), (boar, 2)]
_MONSTERS = [(great_spider, 3), (warg, 2), (orc_soldier, 2), (orc_archer, 1)]

BAND_MEMBERS = {
    BRIGAND: _BRIGANDS,
    WILD_ANIMAL: _WILD_ANIMALS,
    MONSTER: _MONSTERS,
}

# A band may narrow a kind's roster: settled Free country sees only the weak
# **lone footpad**, never the swordsman highwayman of the open road (ADR 0007).
_BAND_MEMBER_OVERRIDES = {
    (overworld.FREE, BRIGAND): [(footpad, 1)],
}


def members_for(band: str, kind: str):
    """The (template, weight) roster to draw a `kind` threat from in `band` —
    a band-specific override where one exists, else the kind's default."""
    return _BAND_MEMBER_OVERRIDES.get((band, kind), BAND_MEMBERS[kind])


# Per-band kind blend, as (count_range, [(kind, weight), ...]).
#   Free  — animals mostly, a rare lone footpad, no monsters.
#   Wild  — brigands + animals dominant; monsters ~10% (weight 1 vs 9).
#   Dark  — monsters dominant, a few animals, no brigands.
#   Perilous — monsters only.
BAND_THREATS = {
    overworld.FREE:     ((0, 1), [(WILD_ANIMAL, 9), (BRIGAND, 1)]),
    overworld.WILD:     ((1, 3), [(BRIGAND, 5), (WILD_ANIMAL, 4), (MONSTER, 1)]),
    overworld.DARK:     ((3, 5), [(MONSTER, 8), (WILD_ANIMAL, 2)]),
    overworld.PERILOUS: ((4, 6), [(MONSTER, 1)]),
}
