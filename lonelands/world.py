"""The GameWorld: owns every map, persists them, and moves the player between
the town, the wilderness, and the descending barrow."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from lonelands import procgen, tile_types
from lonelands.game_map import GameMap

if TYPE_CHECKING:
    from lonelands.engine import Engine


class GameWorld:
    def __init__(self, engine: "Engine"):
        self.engine = engine
        self.town: Optional[GameMap] = None
        self.overworld: Optional[GameMap] = None
        self.ruin_levels: Dict[int, GameMap] = {}
        self.location = "town"
        self.depth = 0

    # --- construction -----------------------------------------------------
    def new_game(self) -> None:
        self.town = procgen.generate_town(self.engine)
        self.location = "town"
        self._go(self.town, self.town.start_xy)

    def _ensure_overworld(self) -> GameMap:
        if self.overworld is None:
            self.overworld = procgen.generate_overworld(self.engine)
        return self.overworld

    def _ensure_ruin(self, depth: int) -> GameMap:
        if depth not in self.ruin_levels:
            self.ruin_levels[depth] = procgen.generate_ruin(self.engine, depth)
        return self.ruin_levels[depth]

    # --- movement between maps -------------------------------------------
    def _go(self, gamemap: GameMap, xy) -> None:
        player = self.engine.player
        old = getattr(player, "parent", None)
        if old is not None and hasattr(old, "entities"):
            old.entities.discard(player)
        player.parent = gamemap
        player.x, player.y = xy
        gamemap.entities.add(player)
        self.engine.game_map = gamemap
        self.engine.update_fov()

    # --- transitions driven by the tile the player stands on -------------
    def use_tile(self) -> Optional[str]:
        x, y = self.engine.player.x, self.engine.player.y
        kind = int(self.engine.game_map.tiles["kind"][x, y])

        if self.location == "town" and kind == tile_types.KIND_TOWN_EXIT:
            ow = self._ensure_overworld()
            self.location = "overworld"
            self._go(ow, ow.entry_xy)
            return "You pass the south gate; the Wild opens before you."

        if self.location == "overworld" and kind == tile_types.KIND_TOWN_EXIT:
            self.location = "town"
            self._go(self.town, self.town.entry_xy)
            return "You return through the gate of Talbrún."

        if self.location == "overworld" and kind == tile_types.KIND_RUIN_ENTRANCE:
            ruin = self._ensure_ruin(1)
            self.location = "ruin"
            self.depth = 1
            self._go(ruin, ruin.entry_xy)
            return "You pass beneath the broken arch into the old dark of Amon Gûl."

        if self.location == "ruin" and kind == tile_types.KIND_DOWN:
            self.depth += 1
            ruin = self._ensure_ruin(self.depth)
            self._go(ruin, ruin.entry_xy)
            return f"You descend to the {_ordinal(self.depth)} deep of the barrow."

        if self.location == "ruin" and kind == tile_types.KIND_UP:
            if self.depth <= 1:
                ow = self._ensure_overworld()
                self.location = "overworld"
                self.depth = 0
                self._go(ow, getattr(ow, "from_ruin_xy", ow.entry_xy))
                return "You climb back into daylight and the clean wind of the hills."
            self.depth -= 1
            ruin = self._ensure_ruin(self.depth)
            dest = getattr(ruin, "down_xy", ruin.entry_xy)
            self._go(ruin, dest)
            return f"You climb to the {_ordinal(self.depth)} deep of the barrow."

        return None


def _ordinal(n: int) -> str:
    return {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}.get(n, f"{n}th")
