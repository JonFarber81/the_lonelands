# Overworld traced from the Eriador Journey Map onto a 15×9 Region grid

The full overworld is planned as a **square 15 × 9 grid of Regions** traced
one-to-one from the TOR **Eriador Journey Map** (`references/`), extending the
5-cell starter plus of ADR 0002 to the whole playable region. The plan itself
lives in `notes/overworld-map.md` (master table + overlay + schematic); this ADR
records the *decisions* that shaped it.

## Decisions

- **Hybrid resolution, not one-Region-per-hex.** Named **anchor** Regions
  (towns/landmarks/gateways) with **wilderness** filler between, at a stride of
  ~3 map-hexes per Region. Gives a continuous walkable field at a density a human
  can author and a player wants to explore. One-Region-per-hex (hundreds of
  featureless cells) and one-Region-per-named-place (breaks edge-crossing
  continuity) were both rejected.
- **Square, 4-neighbour grid.** Keeps the existing movement model
  (`world.py::cross_edge`, N/E/S/W only) unchanged; diagonal map features
  staircase into orthogonal steps. A true hex grid was rejected as a movement-
  model rewrite that this planning step doesn't need — the *content* plan
  survives a later geometry change; only adjacencies re-thread.
- **Playable-Eriador window** (Blue Mts → Misty Mts, North Downs/Ettenmoors →
  Tharbad/Enedwaith), not the full sheet. The Sea and mountains form a natural
  frame; Rohan/Forochel/Harlindon are dropped as content no early quest reaches.
- **Origin `(0,0)` at the window's geographic centre**, which coincides with the
  **Bree crossroads** — not by fiat but because Bree is the hub of the road-net.
  The **Great East Road** is row `y = 0`; the **Greenway** is column `x = 0`.
  Bree remains the `new_game` start regardless of where the origin sits.
- **Two-axis cell taxonomy:** a **role** (Town · Landmark · Wilderness ·
  Gateway · Impassable) and a **band** (Free · Wild · Dark · Perilous) traced
  from the legend colours. Role is authored; band is read off the map and drives
  encounter tables.
- **Roads are edge metadata** (road / track / trackless per border), not just
  map decoration — they give wayfinding and an encounter-difficulty lever.
- **Impassable = absence** of a Region (consistent with ADR 0002: `region()`
  returns `None`, the edge is uncrossable). The **bordering** Region paints the
  barrier diegetically (mountains/cliff/water on that edge). Real crossings in
  the wall are **Gateway** Regions, not walls.
- **Deeps are flagged, not designed.** Each cell carries a `▼N` marker for a
  down-stair into N Levels; the dungeons themselves are a later pass.

## Consequences

- `world.py::_region_defs` will grow from the hard-coded plus to this grid,
  keyed by the coordinates in `notes/overworld-map.md`; lazy generation and
  per-coord caching (ADR 0002) already scale to 135 cells.
- Each **band** needs a procgen encounter table; each **road** cell a road tile
  the arrival-mirroring logic snaps onto.
- Region generators bordering a missing neighbour must apply the diegetic-border
  rule.
- The barrow's deeps re-home from the Weather Hills to the **Barrow-downs** cell
  `(-1,0)`; **Weathertop** `(2,0)` gains the Amon Sûl deeps. This revises the
  current in-code wiring and should be confirmed when the grid is coded.

## Status

Accepted, and **implemented** (issue #13, "Infra A"). `world.py::_region_defs`
is now data-driven from `lonelands/overworld.py` (the plan-as-data grid); all 116
walkable cells build enterable placeholder Surfaces via `procgen`'s terrain
toolkit, beasts are seeded per band, and the barrow deeps re-homed from the
Weather Hills to the Barrow-downs `(-1,0)` with Weathertop `(2,0)` gaining the
Amon Sûl watch-vaults (the accompanying quest/dialog narrative moved with them).
Deeps for the plan's other `▼N` cells remain flagged-not-built, a later per-cell
pass. Supersedes nothing (extends ADR 0002's model to the full map).

**Roads** are now threaded too (issue #14, "Infra C"): `overworld.ROAD_EDGES`
resolves the traced cell-paths into per-edge road metadata (diagonal steps
staircase into orthogonal knees), `procgen.thread_road` paints the meandering
road from each shared edge midpoint through the cell centre (fording any water it
crosses), and `world.cross_edge` snaps an arriving player onto the road — so the
Great East Road (Bree→Rivendell) and the Greenway (Fornost→Tharbad) stay
continuous across every seam. The named landmark river-crossings (Last Bridge,
Sarn Ford, the Fords of Bruinen) get their rivers when their clusters are
authored; the ford/bridge mechanism already handles them.
