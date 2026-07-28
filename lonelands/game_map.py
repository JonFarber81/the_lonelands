from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Iterator, Optional

import numpy as np

from lonelands import awareness, color, config, tile_types
from lonelands.entity import Actor, Item

if TYPE_CHECKING:
    from lonelands.camera import Camera
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

    def render(self, console: Console, camera: "Camera") -> None:
        # Only the camera's window onto the region is drawn, into the top-left
        # MAP_WIDTH×MAP_HEIGHT viewport of the console. World tile (wx, wy) maps
        # to view cell (wx - sx, wy - sy); the slice is clamped to the map so a
        # region smaller than the viewport just letterboxes.
        sx, sy = camera.x, camera.y
        ex = min(sx + config.MAP_WIDTH, self.width)
        ey = min(sy + config.MAP_HEIGHT, self.height)
        w, h = ex - sx, ey - sy
        console.rgb[0:w, 0:h] = np.select(
            condlist=[self.visible[sx:ex, sy:ey], self.explored[sx:ex, sy:ey]],
            choicelist=[self.tiles["light"][sx:ex, sy:ey],
                        self.tiles["dark"][sx:ex, sy:ey]],
            default=tile_types.SHROUD,
        )

        # Laid Snares sit under the entities: a small glyph on a visible tile.
        for (tx, ty), trap in self.traps.items():
            vx, vy = tx - sx, ty - sy
            if 0 <= vx < w and 0 <= vy < h and self.visible[tx, ty]:
                console.print(x=vx, y=vy, string=trap.char,
                              fg=color.snare_c, sprite="snare")

        entities_sorted = sorted(
            self.entities, key=lambda x: x.render_order.value
        )
        for entity in entities_sorted:
            vx, vy = entity.x - sx, entity.y - sy
            if 0 <= vx < w and 0 <= vy < h and self.visible[entity.x, entity.y]:
                console.print(
                    x=vx, y=vy,
                    string=entity.char, fg=entity.color, sprite=entity.sprite,
                )

        # Awareness tags (ADR 0014): a small !/? floated over a foe's head once
        # it has noticed the Ranger (Alerted / Searching), so the deterministic
        # stealth model reads on the board rather than feeling like dice.
        for actor in self.actors:
            mark = awareness.MARKER.get(awareness.awareness_of(actor))
            if mark is None:
                continue
            vx, vy = actor.x - sx, actor.y - sy - 1
            if 0 <= vx < w and 0 <= vy < h and self.visible[actor.x, actor.y]:
                console.print(x=vx, y=vy, string=mark,
                              fg=color.sauron_eye)


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
