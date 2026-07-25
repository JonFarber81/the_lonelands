# World as a grid of Regions; edge = horizontal, Enter = vertical

The world is modelled as a **grid of Regions**, each Region a stack of one or
more **Levels** (see `CONTEXT.md` → *World & navigation*). Movement has exactly
two axes: the player **walks off a Region's Surface edge** to reach an adjacent
Region (horizontal), and presses **Enter** on a stair/entrance to change Level
within the current Region (vertical). Only the Surface edge-connects to
neighbours; deeper Levels are reachable only by Enter. This replaced the earlier
special-cased `town → overworld → ruin` tiers with one uniform model that scales
to a full Eriador grid and to later fast-travel over that grid.

## Considered options

- **Named crossing-point tiles** (walk onto a "gate" tile, press Enter to leave)
  — rejected: not uniform, and every Region would need hand-authored exit tiles.
  Whole-edge crossing needs only each Region's grid neighbours, and terrain
  decides where the edge is reachable.
- **Keeping the intermediate overworld tier** — rejected as a special case; the
  hub (Bree) and the barrow-downs are now peer Regions on the grid.

## Consequences

- The town's hedge needs **gate-gaps** on the sides with neighbours, or the
  player can't reach the edge to cross.
- Arrival in a neighbour **mirrors** the crossing point onto the opposite edge,
  falling back to the nearest walkable tile.
- `Enter` (`TakeInteractAction`) is now vertical-only; the `KIND_TOWN_EXIT` tile
  was retired.
- Regions and their Levels are generated lazily and cached by grid coordinate,
  so a place revisited is exactly as it was left.
