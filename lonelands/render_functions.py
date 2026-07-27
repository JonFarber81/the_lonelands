"""Grid-layer helpers that draw inside the map region (the location banner and
mouse-hover names), plus the shared Endurance colour.

The sidebar and Chronicle used to live here too; they now render natively in
:mod:`lonelands.hud`. What remains draws onto the cell-grid ``console`` because
it sits over the map itself."""
from __future__ import annotations

from typing import TYPE_CHECKING

from lonelands import color
from lonelands.config import MAP_HEIGHT, MAP_WIDTH

if TYPE_CHECKING:
    from lonelands.engine import Engine


def endurance_color(cur: int, mx: int):
    """Stateful Endurance colour: green when hale, amber when hurt, red when low."""
    frac = cur / mx if mx else 0.0
    if frac >= 0.6:
        return color.end_full
    if frac >= 0.3:
        return color.end_mid
    return color.end_low


def get_names_at(x: int, y: int, engine: "Engine") -> str:
    gm = engine.game_map
    if not gm.in_bounds(x, y) or not gm.visible[x, y]:
        return ""
    return ", ".join(e.name for e in gm.entities if e.x == x and e.y == y)


def render_names_at_mouse(console, engine: "Engine") -> None:
    x, y = engine.mouse_location
    if x >= MAP_WIDTH or y >= MAP_HEIGHT:
        return
    names = get_names_at(x, y, engine)
    if names:
        console.print(x=1, y=MAP_HEIGHT - 1, string=names[: MAP_WIDTH - 2], fg=color.light_gray)
