"""The GameWorld: the grid of **Regions** the player travels, and the machinery
that carries them between Regions (walking off an edge) and between the
**Levels** within a Region (Enter on a stair or entrance).

Two movement axes, and only two:
  * **Horizontal** — walk off a Region's Surface edge into the adjacent Region.
  * **Vertical**   — press Enter on a stair/entrance to change Level within the
                     current Region. Only the Surface (Level 0) edge-connects;
                     the deeps (negative Levels) are reached only by Enter.

See `CONTEXT.md` → *World & navigation* for the vocabulary.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, Optional, Tuple

from lonelands import procgen, tile_types
from lonelands.game_map import GameMap

if TYPE_CHECKING:
    from lonelands.engine import Engine

Coord = Tuple[int, int]


class Region:
    """One cell of the world grid: a stack of Levels keyed by index (0 = the
    Surface, negative = the deeps). Levels are built lazily and cached, so a
    Region the player returns to is exactly as they left it."""

    def __init__(
        self,
        coord: Coord,
        name: str,
        build_surface: Callable[[], GameMap],
        build_deep: Optional[Callable[[int], GameMap]] = None,
    ) -> None:
        self.coord = coord
        self.name = name
        self._build_surface = build_surface
        self._build_deep = build_deep  # (depth: 1..N) -> GameMap
        self.levels: Dict[int, GameMap] = {}

    @property
    def has_deeps(self) -> bool:
        return self._build_deep is not None

    def level(self, index: int) -> GameMap:
        if index not in self.levels:
            if index == 0:
                self.levels[index] = self._build_surface()
            elif self._build_deep is not None:
                self.levels[index] = self._build_deep(-index)  # Level -1 -> depth 1
            else:
                raise ValueError(f"Region {self.coord} has no Level {index}")
        return self.levels[index]


class GameWorld:
    def __init__(self, engine: "Engine"):
        self.engine = engine
        self.regions: Dict[Coord, Region] = {}
        self.coord: Coord = (0, 0)     # which Region the player is in
        self.level_index: int = 0      # which Level within it (0 = Surface)
        self._defs = self._region_defs()

    # --- the world grid ---------------------------------------------------
    def _region_defs(self) -> Dict[Coord, Callable[[], Region]]:
        """The starting plus-grid, mirroring the Eriador Journey map: Bree at
        the centre, four neighbours around it. Each entry is a factory so a
        Region is only generated when first visited."""
        e = self.engine
        return {
            (0, 0): lambda: Region(
                (0, 0), "Bree, at the meeting of the roads",
                lambda: procgen.generate_bree(e),
            ),
            (1, 0): lambda: Region(
                (1, 0), "The Weather Hills, east of Bree",
                lambda: procgen.generate_weather_hills(e),
                lambda depth: procgen.generate_ruin(e, depth),
            ),
            (-1, 0): lambda: Region(
                (-1, 0), "The Barrow-downs",
                lambda: procgen.generate_barrow_downs(e),
            ),
            (0, -1): lambda: Region(
                (0, -1), "The Chetwood",
                lambda: procgen.generate_chetwood(e),
            ),
            (0, 1): lambda: Region(
                (0, 1), "The South Downs",
                lambda: procgen.generate_south_downs(e),
            ),
        }

    def region(self, coord: Coord) -> Optional[Region]:
        if coord not in self._defs:
            return None
        if coord not in self.regions:
            self.regions[coord] = self._defs[coord]()
        return self.regions[coord]

    @property
    def current_region(self) -> Region:
        region = self.region(self.coord)
        assert region is not None, f"player stranded off the grid at {self.coord}"
        return region

    # --- construction -----------------------------------------------------
    def new_game(self) -> None:
        self.coord = (0, 0)
        self.level_index = 0
        surface = self.current_region.level(0)
        self._go(surface, getattr(surface, "start_xy", surface.entry_xy))

    # --- low-level placement ---------------------------------------------
    def _go(self, gamemap: GameMap, xy: Coord) -> None:
        player = self.engine.player
        old = getattr(player, "parent", None)
        if old is not None and hasattr(old, "entities"):
            old.entities.discard(player)
        player.parent = gamemap
        player.x, player.y = xy
        gamemap.entities.add(player)
        self.engine.game_map = gamemap
        self.engine.update_fov()

    # --- horizontal: walk off an edge ------------------------------------
    def cross_edge(self, dx: int, dy: int) -> bool:
        """Called when the player tries to step off the map edge. If a
        neighbouring Region lies that way, carry them into it (arriving at the
        mirrored point on the opposite edge) and return True. Otherwise False,
        and the caller reports the edge as impassable."""
        if self.level_index != 0:
            return False  # only the Surface edge-connects to neighbours
        sx = 1 if dx > 0 else -1 if dx < 0 else 0
        sy = 1 if dy > 0 else -1 if dy < 0 else 0
        if sx != 0 and sy != 0:
            return False  # a diagonal move off a corner leaves on two axes — block
        region = self.region((self.coord[0] + sx, self.coord[1] + sy))
        if region is None:
            return False

        gm = region.level(0)
        px, py = self.engine.player.x, self.engine.player.y
        w, h = gm.width, gm.height
        if sx > 0:      dest = (0, py)          # exit east  -> arrive west edge
        elif sx < 0:    dest = (w - 1, py)      # exit west  -> arrive east edge
        elif sy > 0:    dest = (px, 0)          # exit south -> arrive north edge
        else:           dest = (px, h - 1)      # exit north -> arrive south edge
        dest = _nearest_walkable(gm, *dest)

        self.coord = region.coord
        self.level_index = 0
        self._go(gm, dest)
        return True

    # --- vertical: Enter a stair or entrance ------------------------------
    def use_tile(self) -> Optional[str]:
        player = self.engine.player
        gm = self.engine.game_map
        kind = int(gm.tiles["kind"][player.x, player.y])
        region = self.current_region

        # Enter a Region's deeps from its Surface.
        if self.level_index == 0 and kind == tile_types.KIND_RUIN_ENTRANCE \
                and region.has_deeps:
            self._enter_level(-1, arrive="entry")
            return "You pass beneath the broken arch into the old dark of the barrow."

        # Deeper still.
        if self.level_index < 0 and kind == tile_types.KIND_DOWN:
            self._enter_level(self.level_index - 1, arrive="entry")
            return f"You descend to the {_ordinal(-self.level_index)} deep of the barrow."

        # Back up — and out to the Surface from the topmost deep.
        if self.level_index < 0 and kind == tile_types.KIND_UP:
            if self.level_index == -1:
                surface = region.level(0)
                self.level_index = 0
                dest = getattr(surface, "barrow_entrance_xy", None) \
                    or getattr(surface, "entry_xy", surface.start_xy)
                self._go(surface, dest)
                return "You climb back into daylight and the clean wind of the hills."
            self._enter_level(self.level_index + 1, arrive="down")
            return f"You climb to the {_ordinal(-self.level_index)} deep of the barrow."

        return None

    def _enter_level(self, index: int, arrive: str) -> None:
        """Move to Level `index` of the current Region. `arrive` picks the
        landing spot: 'entry' = the Level's up-stair, 'down' = its down-stair."""
        gm = self.current_region.level(index)
        self.level_index = index
        if arrive == "down":
            dest = getattr(gm, "down_xy", gm.entry_xy)
        else:
            dest = gm.entry_xy
        self._go(gm, dest)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _nearest_walkable(gm: GameMap, x: int, y: int) -> Coord:
    """The tile itself if walkable and unblocked, else the closest one that is
    (expanding-ring search). Keeps arrivals out of walls, water, and trees."""
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


def _ordinal(n: int) -> str:
    return {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}.get(
        n, f"{n}th"
    )
