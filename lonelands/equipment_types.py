from __future__ import annotations

from enum import Enum, auto


class EquipmentType(Enum):
    WEAPON = auto()
    RANGED = auto()
    SHIELD = auto()
    ARMOUR = auto()
    HELM = auto()
    ACCESSORY = auto()  # cloak/ring/token: pluses to non-combat stats
