from __future__ import annotations

from typing import TYPE_CHECKING, List

from lonelands.components.base_component import BaseComponent

if TYPE_CHECKING:
    from lonelands.entity import Actor, Item


class Inventory(BaseComponent):
    parent: "Actor"

    def __init__(self, capacity: int = 26):
        self.capacity = capacity
        self.items: List["Item"] = []

    def drop(self, item: "Item") -> None:
        self.items.remove(item)
        item.place(self.parent.x, self.parent.y, self.gamemap)
        self.engine.message_log.add_message(f"You set down the {item.name}.")

    def remove(self, item: "Item") -> None:
        if item in self.items:
            self.items.remove(item)
