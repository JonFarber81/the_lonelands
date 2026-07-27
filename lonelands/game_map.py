from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Iterator, Optional

import numpy as np

from lonelands import tile_types
from lonelands.entity import Actor, Item
from lonelands.tile_glyphs import graphic_char

if TYPE_CHECKING:
    from lonelands.display import Console
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
    def traps(self) -> dict:
        """Hidden Path Snares laid on this map, keyed by ``(x, y)`` (ADR 0011,
        #77). Lazily created so a map unpickled from an older save still has one."""
        return self.__dict__.setdefault("_traps", {})

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

        # Laid Snares sit under the entities: a small glyph on a visible tile.
        for (tx, ty), trap in self.traps.items():
            if self.visible[tx, ty]:
                console.print(x=tx, y=ty, string=graphic_char(trap.char),
                              fg=(0x86, 0x6A, 0x3C))

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


def nearest_walkable(gm: "GameMap", x: int, y: int) -> "tuple[int, int]":
    """The tile itself if walkable and unblocked, else the closest one that is
    (expanding-ring search). Keeps arrivals out of walls, water, and trees — used
    both when carrying the player across a Region edge and when landing them on a
    freshly-generated Surface whose centre may be painted over."""
    def ok(tx: int, ty: int) -> bool:
        return (
            gm.in_bounds(tx, ty)
            and bool(gm.tiles["walkable"][tx, ty])
            and gm.get_blocking_entity_at(tx, ty) is None
        )

    if ok(x, y):
        return (x, y)
    for radius in range(1, max(gm.width, gm.height)):
        for tx in range(x - radius, x + radius + 1):
            for ty in range(y - radius, y + radius + 1):
                if max(abs(tx - x), abs(ty - y)) == radius and ok(tx, ty):
                    return (tx, ty)
    return (x, y)  # nothing walkable at all — should never happen
