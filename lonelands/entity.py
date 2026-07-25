"""Entities: anything with a position and a glyph. Actors act; Items are used."""
from __future__ import annotations

import copy
import math
from typing import TYPE_CHECKING, Optional, Tuple, Type, TypeVar, Union

from lonelands.render_order import RenderOrder

if TYPE_CHECKING:
    from lonelands.components.ai import BaseAI
    from lonelands.components.consumable import Consumable
    from lonelands.components.equipment import Equipment
    from lonelands.components.equippable import Equippable
    from lonelands.components.fighter import Fighter
    from lonelands.components.hero import Hero
    from lonelands.components.inventory import Inventory
    from lonelands.components.level import Level
    from lonelands.components.npc import NPC
    from lonelands.game_map import GameMap

T = TypeVar("T", bound="Entity")


class Entity:
    parent: Union["GameMap", "Inventory"]

    def __init__(
        self,
        parent: Optional["GameMap"] = None,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<unnamed>",
        blocks_movement: bool = False,
        render_order: RenderOrder = RenderOrder.CORPSE,
    ) -> None:
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.blocks_movement = blocks_movement
        self.render_order = render_order
        if parent is not None:
            self.parent = parent
            parent.entities.add(self)

    @property
    def gamemap(self) -> "GameMap":
        return self.parent.gamemap

    def spawn(self: T, gamemap: "GameMap", x: int, y: int) -> T:
        clone = copy.deepcopy(self)
        clone.x = x
        clone.y = y
        clone.parent = gamemap
        gamemap.entities.add(clone)
        return clone

    def place(self, x: int, y: int, gamemap: Optional["GameMap"] = None) -> None:
        self.x = x
        self.y = y
        if gamemap is not None:
            current = getattr(self, "parent", None)
            if current is not None and hasattr(current, "entities"):
                current.entities.discard(self)
            self.parent = gamemap
            gamemap.entities.add(self)

    def distance(self, x: int, y: int) -> float:
        return math.hypot(x - self.x, y - self.y)

    def move(self, dx: int, dy: int) -> None:
        self.x += dx
        self.y += dy


class Actor(Entity):
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "@",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<unnamed>",
        ai_cls: Optional[Type["BaseAI"]] = None,
        fighter: Optional["Fighter"] = None,
        hero: Optional["Hero"] = None,
        inventory: Optional["Inventory"] = None,
        equipment: Optional["Equipment"] = None,
        level: Optional["Level"] = None,
        npc: Optional["NPC"] = None,
    ) -> None:
        super().__init__(
            x=x,
            y=y,
            char=char,
            color=color,
            name=name,
            blocks_movement=True,
            render_order=RenderOrder.ACTOR,
        )
        self.ai: Optional["BaseAI"] = ai_cls(self) if ai_cls else None

        self.fighter = fighter
        if fighter:
            fighter.parent = self

        self.hero = hero
        if hero:
            hero.parent = self

        self.inventory = inventory
        if inventory:
            inventory.parent = self

        self.equipment = equipment
        if equipment:
            equipment.parent = self

        self.level = level
        if level:
            level.parent = self

        self.npc = npc
        if npc:
            npc.parent = self

    @property
    def is_alive(self) -> bool:
        return bool(self.ai) or self.npc is not None


class Item(Entity):
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "!",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<unnamed>",
        consumable: Optional["Consumable"] = None,
        equippable: Optional["Equippable"] = None,
        description: str = "",
    ) -> None:
        super().__init__(
            x=x,
            y=y,
            char=char,
            color=color,
            name=name,
            blocks_movement=False,
            render_order=RenderOrder.ITEM,
        )
        self.description = description

        self.consumable = consumable
        if consumable:
            consumable.parent = self

        self.equippable = equippable
        if equippable:
            equippable.parent = self
