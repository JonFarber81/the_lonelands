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

from lonelands import game_map, overworld, procgen, tile_types
from lonelands.game_map import GameMap

if TYPE_CHECKING:
    from lonelands.engine import Engine

Coord = Tuple[int, int]

# Cells with a hand-authored Surface; everything else uses the generic
# placeholder built from its plan Cell.
_AUTHORED_SURFACES: Dict[Coord, Callable[["Engine"], GameMap]] = {
    (0, 0): procgen.generate_bree,
    (2, 0): procgen.generate_weathertop,       # Amon Sûl watchtower
    (-1, 0): procgen.generate_barrow_downs,     # Tyrn Gorthad — the main quest barrow
    # Cluster 2 — Bree & environs (issue #17): the anchors ringing the crossroads.
    (0, -1): procgen.generate_chetwood,         # wooded country north of Bree (holds Archet)
    (1, 0): procgen.generate_breeland,          # the Bree-land east: Combe, Staddle, Forsaken Inn
    (1, -1): procgen.generate_midgewater,       # the biting Midgewater fen
    (-2, 1): procgen.generate_old_forest,       # the awake, ill-disposed wood
    (-1, 1): procgen.generate_sarn_ford,        # the Brandywine ford, Ranger post
    (0, 1): procgen.generate_south_downs,       # low downs south of the Road
    # Cluster 1 — The Shire & the green west (issue #16).
    (-7, 0): procgen.generate_grey_havens,      # Mithlond, the elven haven on the Gulf
    (-6, 0): procgen.generate_white_towers,     # Emyn Beraid, the three white towers
    (-5, 0): procgen.generate_far_downs,        # the Shire's green western downs
    (-4, 0): procgen.generate_michel_delving,   # chief Shire town; the Mathom-house
    (-3, -1): procgen.generate_hobbiton,        # the Hill and Bag End
    (-2, -1): procgen.generate_brandywine_bridge,  # the stone bridge onto the Road
    (-5, 1): procgen.generate_tower_hills,      # Emyn Beraid's green marches
    # Cluster 3 — The Lone-lands & the East-Road corridor (issue #18).
    (2, -2): procgen.generate_weather_hills,    # the ridge north from Weathertop
    (4, -1): procgen.generate_last_bridge,      # the Mitheithel bridge; last sure crossing
    (5, -1): procgen.generate_trollshaws,       # troll-country wooded rock
    (7, -1): procgen.generate_fords_of_bruinen,  # the guarded Bruinen crossing (gateway)
    (6, 0): procgen.generate_rivendell,         # Imladris, the Last Homely House
    # Cluster 4 — The North (Arnor ruins) (issue #19).
    (-3, -2): procgen.generate_annuminas,       # ruined royal city on Lake Nenuial
    (-1, -2): procgen.generate_fornost,         # Norbury of the Kings; wight-haunted ruin
    (1, -4): procgen.generate_north_downs,      # the high rolling downs on the north rim
    # Cluster 5 — The North-East marches (Dark) (issue #20).
    (4, -4): procgen.generate_mt_gram,          # orc-hold of the northern hills
    (5, -4): procgen.generate_ettenmoors,       # the troll-fells; NE gateway toward Angmar
}

# Cells whose deeps are authored this pass (ADR 0003 re-home): the barrow-wight
# deeps beneath Tyrn Gorthad hold the star-brooch; Amon Sûl's watch-vaults do not.
_AUTHORED_DEEPS: Dict[Coord, Callable[["Engine", int], GameMap]] = {
    (-1, 0): lambda e, depth: procgen.generate_ruin(
        e, depth, name="The Barrows of Tyrn Gorthad", max_depth=4, treasure=True),
    (2, 0): lambda e, depth: procgen.generate_ruin(
        e, depth, name="The Watch-vaults of Amon Sûl", max_depth=3, treasure=False),
}


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

    def __getstate__(self) -> dict:
        """Drop the (unpicklable) level-builder lambdas; savegame._rehydrate
        re-attaches them from a freshly-built Region on load."""
        state = self.__dict__.copy()
        state["_build_surface"] = None
        state["_build_deep"] = None
        return state

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

    def __getstate__(self) -> dict:
        """Drop the (unpicklable) Region factory table; savegame._rehydrate
        rebuilds it from self.engine on load."""
        state = self.__dict__.copy()
        state["_defs"] = None
        return state

    # --- the world grid ---------------------------------------------------
    def _region_defs(self) -> Dict[Coord, Callable[[], Region]]:
        """A factory per walkable cell of the overworld plan (`overworld.GRID`,
        ADR 0003): all 116 cells, keyed by coord. Impassable coords are simply
        absent, so their edges report as uncrossable (ADR 0002). Each entry is a
        factory so a Region is only generated when first visited.

        A handful of cells have **authored** Surfaces; every other cell falls
        back to `generate_placeholder_surface`, built from its plan `Cell` so it
        is walkable before its cluster refines it. Deeps are wired only for the
        cells whose dungeons are authored (`_AUTHORED_DEEPS`); the rest carry a
        `▼N` marker in the plan but are dug region-by-region in a later pass."""
        e = self.engine

        def make(cell: "overworld.Cell") -> Callable[[], Region]:
            surface = _AUTHORED_SURFACES.get(cell.coord)
            deep = _AUTHORED_DEEPS.get(cell.coord)
            build_surface = (lambda s=surface: s(e)) if surface \
                else (lambda c=cell: procgen.generate_placeholder_surface(e, c))
            build_deep = (lambda depth, d=deep: d(e, depth)) if deep else None
            return lambda c=cell: Region(
                c.coord, c.region_name, build_surface, build_deep)

        return {coord: make(cell) for coord, cell in overworld.GRID.items()}

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

    # --- debug: jump to any Region's Surface ------------------------------
    def teleport_to(self, coord: Coord) -> bool:
        """Debug fast-travel (ADR 0012): drop the player onto ``coord``'s Surface
        at its normal arrival point, wherever they were (deeps included). No turn
        passes. Returns False — and does nothing — for an impassable/off-grid
        cell (a Sea or Mountain coord absent from the grid)."""
        region = self.region(coord)
        if region is None:
            return False
        surface = region.level(0)
        self.coord = region.coord
        self.level_index = 0
        self._go(surface, getattr(surface, "start_xy", surface.entry_xy))
        self.engine.quest_log.notify_arrival(self.coord, self.engine)
        return True

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
        if sx > 0:      dest, arr = (0, py), "w"        # exit east  -> arrive west edge
        elif sx < 0:    dest, arr = (w - 1, py), "e"    # exit west  -> arrive east edge
        elif sy > 0:    dest, arr = (px, 0), "n"        # exit south -> arrive north edge
        else:           dest, arr = (px, h - 1), "s"    # exit north -> arrive south edge
        # Crossing a road edge lands the player on the road, so the Great Roads
        # stay continuous across every cluster seam (issue #14).
        on_road = procgen.snap_to_road(gm, arr, dest)
        dest = _nearest_walkable(gm, *(on_road or dest))

        self.coord = region.coord
        self.level_index = 0
        self._go(gm, dest)
        self.engine.quest_log.notify_arrival(self.coord, self.engine)
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
                self.engine.quest_log.notify_arrival(self.coord, self.engine)
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
        self.engine.quest_log.notify_arrival(self.coord, self.engine, level_index=index)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
# The expanding-ring search lives on `game_map` (it operates purely on a
# GameMap); kept here under its old name for the callers/tests that import it.
_nearest_walkable = game_map.nearest_walkable


def _ordinal(n: int) -> str:
    return {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}.get(
        n, f"{n}th"
    )
