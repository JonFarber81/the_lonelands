"""Gear that can be worn or wielded, carrying its legible d20 stat line.

Gear reads as plain numbers (ADR 0005 — no identification): a **weapon** carries
+hit, damage, and an optional **property** (``pierce`` ignores some Soak;
``bonus_vs`` adds damage against a foe *kind*); **armour** is either heavy
**Soak** (subtracts from damage) or light **+Defence** (harder to hit), shields
add +Defence; an **accessory** (cloak/ring/token) carries only *non-combat*
pluses — +attribute, +Stealth, a Path synergy, spare ability charges.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Union

from lonelands.components.base_component import BaseComponent
from lonelands.equipment_types import EquipmentType

if TYPE_CHECKING:
    from lonelands.entity import Item


class Equippable(BaseComponent):
    parent: "Item"

    def __init__(
        self,
        equipment_type: EquipmentType,
        *,
        load: int = 0,
        # --- Weapons -----------------------------------------------------
        damage: Union[int, str] = 0,  # damage roll: a flat int or dice spec ("2d6+1")
        attack_bonus: int = 0,    # +hit the weapon adds to the wielder's d20
        ranged: bool = False,
        # A weapon *property* (ADR 0005): pierce ignores some Soak, and a
        # bonus-vs applies extra damage against foes of a given kind.
        pierce: int = 0,          # Soak ignored on a landed blow
        bonus_vs: str = "",       # foe kind the weapon bites (e.g. "orc", "beast")
        bonus_vs_damage: int = 0, # extra damage dealt to a foe of that kind
        # --- Armour & shields --------------------------------------------
        defence_bonus: int = 0,   # light gear/shields: adds to Defence (harder to hit)
        soak_bonus: int = 0,      # heavy armour: adds to Soak (subtracts from damage)
        # --- Accessory pluses (non-combat) -------------------------------
        attributes: Optional[Dict[str, int]] = None,  # +Brawn/+Wits/+Will
        stealth_bonus: int = 0,   # sharpens the (future) stealth/detection layer
        path_synergy: str = "",   # a Path this token favours (flavour + future hooks)
        ability_charges: int = 0, # spare charges lent to Path actives (future hook)
        # A hand-authored named Unique sits *outside* the Plain/Fine/Rare affix
        # bands (ADR 0005); the affix generator never enchants it (see affixes.py).
        unique: bool = False,
    ) -> None:
        self.equipment_type = equipment_type
        self.load = load
        self.damage = damage
        self.attack_bonus = attack_bonus
        self.ranged = ranged
        self.pierce = pierce
        self.bonus_vs = bonus_vs
        self.bonus_vs_damage = bonus_vs_damage
        self.defence_bonus = defence_bonus
        self.soak_bonus = soak_bonus
        self.attributes: Dict[str, int] = dict(attributes or {})
        self.stealth_bonus = stealth_bonus
        self.path_synergy = path_synergy
        self.ability_charges = ability_charges
        self.unique = unique

    @property
    def is_weapon(self) -> bool:
        return self.equipment_type in (EquipmentType.WEAPON, EquipmentType.RANGED)

    def stat_line(self) -> str:
        """The gear's full stats as one legible line, shown on pickup and in the
        pack (there is no identification — what you see is what it is)."""
        parts: List[str] = []
        if self.is_weapon:
            parts.append(f"dmg {self.damage}")
            if self.attack_bonus:
                parts.append(f"{self.attack_bonus:+d} hit")
            if self.pierce:
                parts.append(f"pierce {self.pierce}")
            if self.bonus_vs and self.bonus_vs_damage:
                parts.append(f"+{self.bonus_vs_damage} vs {self.bonus_vs}s")
        else:
            if self.soak_bonus:
                parts.append(f"soak {self.soak_bonus}")
            if self.defence_bonus:
                parts.append(f"{self.defence_bonus:+d} Defence")
            for attr, amt in self.attributes.items():
                parts.append(f"{amt:+d} {attr}")
            if self.stealth_bonus:
                parts.append(f"{self.stealth_bonus:+d} Stealth")
            if self.ability_charges:
                parts.append(f"+{self.ability_charges} charge"
                             + ("s" if self.ability_charges != 1 else ""))
            if self.path_synergy:
                parts.append(f"favours {self.path_synergy}")
        if self.load:
            parts.append(f"load {self.load}")
        return " · ".join(parts) if parts else "no bonuses"
