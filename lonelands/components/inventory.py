from __future__ import annotations

from typing import TYPE_CHECKING, List

from lonelands.components.base_component import BaseComponent
from lonelands.exceptions import Impossible

if TYPE_CHECKING:
    from lonelands.entity import Actor, Item


class Inventory(BaseComponent):
    parent: "Actor"

    def __init__(self, capacity: int = 26):
        self.capacity = capacity
        self.items: List["Item"] = []

    def add(self, item: "Item") -> "Item":
        """Take an item into the pack, merging fungible stacks by name. Returns
        the resulting slot (the merged-into stack, or the item itself). Raises
        Impossible if a *new* slot is needed and the pack is full; merging into
        an existing stack never needs a slot."""
        if item.stackable:
            for existing in self.items:
                if existing.stackable and existing.name == item.name:
                    existing.quantity += item.quantity
                    return existing
        if len(self.items) >= self.capacity:
            raise Impossible("Your pack is full.")
        item.parent = self
        self.items.append(item)
        return item

    def drop(self, item: "Item") -> None:
        self.items.remove(item)
        item.place(self.parent.x, self.parent.y, self.gamemap)
        self.engine.message_log.add_message(f"You set down the {item.name}.")

    def remove(self, item: "Item") -> None:
        if item in self.items:
            self.items.remove(item)
