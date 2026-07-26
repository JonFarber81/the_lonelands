"""Procedural loot: the affix generator (Phase 6, ADR 0005).

Ordinary gear rolls a **rarity** and, with it, up to two **affixes** — a
**prefix** (an adjective: *keen*, *stout*) and a **suffix** (an ``of`` clause:
*of ruin*, *of warding*). An affix only touches the numbers a piece already
speaks in (a weapon's +hit/damage, armour's Soak/+Defence, an accessory's
attribute pluses), so the piece's own :meth:`~Equippable.stat_line` shows the
full result — there is no identification, what you see is what it is.

Three bands:

* **Plain** — no affix; the base piece as authored.
* **Fine** — one affix (a prefix *or* a suffix).
* **Rare** — a prefix *and* a suffix.

Named **Uniques** are hand-authored (see ``content``) and sit *outside* these
bands: they are marked ``unique`` on their Equippable and never take an affix.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Callable, List, Optional

from lonelands.components.equippable import Equippable
from lonelands.dice import rng
from lonelands.entity import Item
from lonelands.equipment_types import EquipmentType

# --- Rarity bands -----------------------------------------------------------
PLAIN = "Plain"
FINE = "Fine"
RARE = "Rare"

# Base weights for the rarity roll. Plain dominates; Rare is a genuine find.
# Depth nudges the odds toward the richer bands (see ``roll_rarity``).
_RARITY_WEIGHTS = {PLAIN: 70, FINE: 25, RARE: 5}

# --- Gear categories an affix can suit --------------------------------------
WEAPON = "weapon"
ARMOUR = "armour"
ACCESSORY = "accessory"

_CATEGORY_FOR_TYPE = {
    EquipmentType.WEAPON: WEAPON,
    EquipmentType.RANGED: WEAPON,
    EquipmentType.ARMOUR: ARMOUR,
    EquipmentType.HELM: ARMOUR,
    EquipmentType.SHIELD: ARMOUR,
    EquipmentType.ACCESSORY: ACCESSORY,
}


def category_of(equippable: Equippable) -> str:
    """Which affix pool a piece of gear draws from."""
    return _CATEGORY_FOR_TYPE[equippable.equipment_type]


# --- Affix model ------------------------------------------------------------
def _add_damage(eq: Equippable, amount: int) -> None:
    """Raise a weapon's damage, whether it is a flat int or a dice spec."""
    dmg = eq.damage
    if isinstance(dmg, int):
        eq.damage = max(0, dmg + amount)
        return
    m = re.match(r"^\s*(\d+d\d+)\s*([+-]\s*\d+)?\s*$", str(dmg))
    if not m:  # an unrecognised spec is left untouched
        return
    bonus = int((m.group(2) or "0").replace(" ", "")) + amount
    eq.damage = m.group(1) + (f"{bonus:+d}" if bonus else "")


@dataclass(frozen=True)
class Affix:
    """One rollable modifier. ``word`` is slotted into the item's name; ``apply``
    mutates the piece's Equippable in place; ``value_add`` is added to the item's
    coin Value. Whether it reads as a prefix or a suffix is decided by which pool
    it lives in, not stored here. Only the effect survives on the item — the Affix
    object itself is never attached, so items stay plain-data and picklable."""

    word: str                          # e.g. "keen" (prefix) or "ruin" (suffix)
    category: str                      # WEAPON | ARMOUR | ACCESSORY it suits
    apply: Callable[[Equippable], None]
    value_add: int


def _bump_attr(eq: Equippable, attribute: str) -> None:
    eq.attributes[attribute] = eq.attributes.get(attribute, 0) + 1


def _apply_orc_bane(eq: Equippable) -> None:
    eq.bonus_vs = "orc"
    eq.bonus_vs_damage = eq.bonus_vs_damage + 2


# --- Affix pools ------------------------------------------------------------
# Prefixes read as an adjective ("keen short sword"); suffixes as an "of" clause
# ("short sword of ruin"). Each affix suits exactly one category so a rolled name
# always reads true, and every category has at least one prefix and one suffix so
# a Rare (prefix + suffix) is always possible whatever the piece.
_PREFIXES: List[Affix] = [
    # Weapons
    Affix("keen", WEAPON, lambda e: setattr(e, "attack_bonus", e.attack_bonus + 1), 10),
    Affix("cruel", WEAPON, lambda e: _add_damage(e, 1), 10),
    Affix("barbed", WEAPON, lambda e: setattr(e, "pierce", e.pierce + 1), 9),
    # Armour & shields
    Affix("stout", ARMOUR, lambda e: setattr(e, "soak_bonus", e.soak_bonus + 1), 10),
    Affix("supple", ARMOUR, lambda e: setattr(e, "defence_bonus", e.defence_bonus + 1), 10),
    # Accessories
    Affix("gleaming", ACCESSORY, lambda e: setattr(e, "stealth_bonus", e.stealth_bonus + 1), 8),
]

_SUFFIXES: List[Affix] = [
    # Weapons
    Affix("ruin", WEAPON, lambda e: _add_damage(e, 1), 10),
    Affix("orc-bane", WEAPON, _apply_orc_bane, 12),
    # Armour & shields
    Affix("warding", ARMOUR, lambda e: setattr(e, "defence_bonus", e.defence_bonus + 1), 10),
    Affix("the tortoise", ARMOUR, lambda e: setattr(e, "soak_bonus", e.soak_bonus + 1), 10),
    # Accessories — the "of the beast" tokens each lend one attribute
    Affix("the bear", ACCESSORY, lambda e: _bump_attr(e, "Brawn"), 12),
    Affix("the owl", ACCESSORY, lambda e: _bump_attr(e, "Wits"), 12),
    Affix("the steadfast", ACCESSORY, lambda e: _bump_attr(e, "Will"), 12),
]


def _pool(affixes: List[Affix], category: str) -> List[Affix]:
    return [a for a in affixes if a.category == category]


# --- Rolling ----------------------------------------------------------------
def is_affixable(item: Item) -> bool:
    """True for ordinary equippable gear. Consumables/trade-goods (no Equippable)
    and hand-authored Uniques are left alone."""
    eq = item.equippable
    return eq is not None and not eq.unique


def roll_rarity(depth: int = 0) -> str:
    """Weighted rarity roll. Deeper Levels tilt the odds toward Fine/Rare."""
    weights = dict(_RARITY_WEIGHTS)
    if depth > 0:
        shift = min(depth * 3, weights[PLAIN] - 10)
        weights[PLAIN] -= shift
        weights[FINE] += shift * 2 // 3
        weights[RARE] += shift - shift * 2 // 3
    bands = list(weights)
    return rng.choices(bands, weights=[weights[b] for b in bands])[0]


def _rename(item: Item, prefix: Optional[Affix], suffix: Optional[Affix]) -> None:
    name = item.name
    if prefix is not None:
        name = f"{prefix.word} {name}"
    if suffix is not None:
        name = f"{name} of {suffix.word}"
    item.name = name


def apply_affixes(item: Item, *, rarity: Optional[str] = None, depth: int = 0) -> Item:
    """Roll (or take) a rarity and stamp its affixes onto ``item`` **in place**,
    updating its stats, name, and Value; returns the same item. A Plain result,
    a non-equippable item, or a Unique is returned unchanged. There is no
    identification — the rolled numbers show at once on the stat line."""
    if not is_affixable(item):
        return item
    if rarity is None:
        rarity = roll_rarity(depth)
    if rarity == PLAIN:
        return item

    eq = item.equippable
    assert eq is not None  # guarded by is_affixable
    category = category_of(eq)
    prefixes = _pool(_PREFIXES, category)
    suffixes = _pool(_SUFFIXES, category)

    prefix: Optional[Affix] = None
    suffix: Optional[Affix] = None
    if rarity == RARE:
        prefix = rng.choice(prefixes) if prefixes else None
        suffix = rng.choice(suffixes) if suffixes else None
    else:  # FINE: one affix — a prefix or a suffix, whichever the coin lands on
        take_prefix = rng.random() < 0.5
        if (take_prefix and prefixes) or not suffixes:
            prefix = rng.choice(prefixes) if prefixes else None
        else:
            suffix = rng.choice(suffixes)

    for affix in (prefix, suffix):
        if affix is not None:
            affix.apply(eq)
            item.value += affix.value_add
    _rename(item, prefix, suffix)
    return item


def generate(base_item: Item, *, rarity: Optional[str] = None, depth: int = 0) -> Item:
    """Return a **fresh** affixed copy of a base template, leaving the template
    untouched. The pure counterpart to :func:`apply_affixes` (which mutates)."""
    clone = copy.deepcopy(base_item)
    return apply_affixes(clone, rarity=rarity, depth=depth)
