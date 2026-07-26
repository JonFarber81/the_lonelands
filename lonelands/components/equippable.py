"""Gear that can be worn or wielded, carrying TOR combat statistics."""
from __future__ import annotations

from typing import TYPE_CHECKING

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
        # Weapons:
        damage: int = 0,
        edge: int = 1,       # bonus damage per tengwar (a 6) rolled
        injury: int = 0,     # Injury rating = Protection TN inflicted on a piercing blow
        proficiency: str = "",  # which weapon proficiency governs its use
        ranged: bool = False,
        # Defence:
        defence_bonus: int = 0,  # light gear/shields: adds to Defence (harder to hit)
        soak_bonus: int = 0,     # heavy armour: adds to Soak (subtracts from damage)
    ) -> None:
        self.equipment_type = equipment_type
        self.load = load
        self.damage = damage
        self.edge = edge
        self.injury = injury
        self.proficiency = proficiency
        self.ranged = ranged
        self.defence_bonus = defence_bonus
        self.soak_bonus = soak_bonus
