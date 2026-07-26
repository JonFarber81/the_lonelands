from __future__ import annotations

from typing import TYPE_CHECKING

from lonelands import color
from lonelands.actions import ItemAction
from lonelands.components.base_component import BaseComponent
from lonelands.exceptions import Impossible

if TYPE_CHECKING:
    from lonelands.entity import Item


class Consumable(BaseComponent):
    parent: "Item"

    def get_action(self, consumer):
        return ItemAction(consumer, self.parent)

    def activate(self, action: ItemAction) -> None:
        raise NotImplementedError()

    def consume(self) -> None:
        item = self.parent
        inventory = item.parent
        if item.stackable and item.quantity > 1:
            item.quantity -= 1
            return
        if hasattr(inventory, "items") and item in inventory.items:
            inventory.items.remove(item)


class HealingConsumable(Consumable):
    def __init__(self, amount: int):
        self.amount = amount

    def activate(self, action: ItemAction) -> None:
        consumer = action.entity
        recovered = consumer.fighter.heal(self.amount)
        if recovered > 0:
            self.engine.message_log.add_message(
                f"You tend your hurts with the {self.parent.name}, "
                f"recovering {recovered} endurance.",
                color.health_recovered,
            )
            self.consume()
        else:
            raise Impossible("Your endurance is already full.")


class HopeConsumable(Consumable):
    """Draughts and lembas that lift the heart."""

    def __init__(self, amount: int):
        self.amount = amount

    def activate(self, action: ItemAction) -> None:
        consumer = action.entity
        if consumer.hero is None:
            raise Impossible("This does nothing for you.")
        restored = consumer.hero.restore_hope(self.amount)
        if restored > 0:
            self.engine.message_log.add_message(
                f"The {self.parent.name} rekindles your heart (+{restored} Hope).",
                color.hope_gain,
            )
            self.consume()
        else:
            raise Impossible("Your heart is already high.")


class RemedyConsumable(Consumable):
    """Athelas: heals endurance and staunches Bleed."""

    def __init__(self, amount: int):
        self.amount = amount

    def activate(self, action: ItemAction) -> None:
        consumer = action.entity
        fighter = consumer.fighter
        did_something = False
        if fighter.bleed > 0:
            fighter.bleed = 0
            self.engine.message_log.add_message(
                f"The clean scent of {self.parent.name} staunches your bleeding.",
                color.health_recovered,
            )
            did_something = True
        recovered = fighter.heal(self.amount)
        if recovered:
            self.engine.message_log.add_message(
                f"You recover {recovered} endurance.", color.health_recovered
            )
            did_something = True
        if did_something:
            self.consume()
        else:
            raise Impossible("You are already hale and whole.")
