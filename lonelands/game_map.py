from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Iterator, Optional

import numpy as np
from tcod.console import Console

from lonelands import tile_types
from lonelands.entity import Actor, Item
from lonelands.tile_glyphs import graphic_char

if TYPE_CHECKING:
    from lonelands.engine import Engine
    from lonelands.entity import Entity


class GameMap:
    def __init__(
        self,
        engine: "Engine",
        width: int,
        height: int,
        entities: Iterable["Entity"] = (),
        *,
        name: str = "",
        outdoors: bool = False,
    ):
        self.engine = engine
        self.width, self.height = width, height
        self.name = name
        self.outdoors = outdoors
        self.entities = set(entities)
        self.tiles = np.full((width, height), fill_value=tile_types.wall, order="F")
        self.visible = np.full((width, height), fill_value=False, order="F")
        self.explored = np.full((width, height), fill_value=False, order="F")
        # Where the player should land when arriving here from elsewhere.
        self.entry_xy = (width // 2, height // 2)

    @property
    def gamemap(self) -> "GameMap":
        return self

    @property
    def actors(self) -> Iterator[Actor]:
        yield from (
            e for e in self.entities if isinstance(e, Actor)
        )

    @property
    def items(self) -> Iterator[Item]:
        yield from (e for e in self.entities if isinstance(e, Item))

    def get_blocking_entity_at(self, x: int, y: int) -> Optional["Entity"]:
        for entity in self.entities:
            if entity.blocks_movement and entity.x == x and entity.y == y:
                return entity
        return None

    def get_actor_at(self, x: int, y: int) -> Optional[Actor]:
        for actor in self.actors:
            if actor.x == x and actor.y == y:
                return actor
        return None

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def render(self, console: Console) -> None:
        console.rgb[0 : self.width, 0 : self.height] = np.select(
            condlist=[self.visible, self.explored],
            choicelist=[self.tiles["light"], self.tiles["dark"]],
            default=tile_types.SHROUD,
        )

        entities_sorted = sorted(
            self.entities, key=lambda x: x.render_order.value
        )
        for entity in entities_sorted:
            if self.visible[entity.x, entity.y]:
                # Draw the entity's glyph from the map tileset (shaded art),
                # not the plain ASCII char — see lonelands.tile_glyphs.
                console.print(
                    x=entity.x, y=entity.y,
                    string=graphic_char(entity.char), fg=entity.color,
                )
