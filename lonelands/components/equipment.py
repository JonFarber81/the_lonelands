"""Worn/wielded gear and the aggregated bonuses it grants."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from lonelands.components.base_component import BaseComponent
from lonelands.equipment_types import EquipmentType

if TYPE_CHECKING:
    from lonelands.entity import Actor, Item

_SLOT_FOR_TYPE = {
    EquipmentType.WEAPON: "weapon",
    EquipmentType.RANGED: "ranged",
    EquipmentType.SHIELD: "shield",
    EquipmentType.ARMOUR: "body",
    EquipmentType.HELM: "head",
}


class Equipment(BaseComponent):
    parent: "Actor"

    def __init__(
        self,
        weapon: Optional["Item"] = None,
        ranged: Optional["Item"] = None,
        shield: Optional["Item"] = None,
        body: Optional["Item"] = None,
        head: Optional["Item"] = None,
    ) -> None:
        self.slots: Dict[str, Optional["Item"]] = {
            "weapon": weapon,
            "ranged": ranged,
            "shield": shield,
            "body": body,
            "head": head,
        }

    @property
    def weapon(self) -> Optional["Item"]:
        return self.slots["weapon"]

    @property
    def ranged(self) -> Optional["Item"]:
        return self.slots["ranged"]

    def _sum(self, attr: str) -> int:
        total = 0
        for item in self.slots.values():
            if item is not None and item.equippable is not None:
                total += getattr(item.equippable, attr, 0)
        return total

    @property
    def load(self) -> int:
        return self._sum("load")

    @property
    def defence_bonus(self) -> int:
        return self._sum("defence_bonus")

    @property
    def protection_bonus(self) -> int:
        return self._sum("protection_bonus")

    def item_is_equipped(self, item: "Item") -> bool:
        return item in self.slots.values()

    def slot_for(self, item: "Item") -> Optional[str]:
        if item.equippable is None:
            return None
        return _SLOT_FOR_TYPE.get(item.equippable.equipment_type)

    def unequip_message(self, item_name: str) -> None:
        self.engine.message_log.add_message(f"You put away the {item_name}.")

    def equip_message(self, item_name: str) -> None:
        self.engine.message_log.add_message(f"You ready the {item_name}.")

    def _equip_to_slot(self, slot: str, item: "Item", add_message: bool) -> None:
        current = self.slots[slot]
        if current is not None:
            self._unequip_from_slot(slot, add_message)
        self.slots[slot] = item
        if add_message:
            self.equip_message(item.name)

    def _unequip_from_slot(self, slot: str, add_message: bool) -> None:
        current = self.slots[slot]
        if current is not None and add_message:
            self.unequip_message(current.name)
        self.slots[slot] = None

    def toggle_equip(self, item: "Item", add_message: bool = True) -> None:
        slot = self.slot_for(item)
        if slot is None:
            return
        if self.slots[slot] is item:
            self._unequip_from_slot(slot, add_message)
        else:
            self._equip_to_slot(slot, item, add_message)
