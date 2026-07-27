# The Prancing Pony is a surface building, not an interior Level

The Pony is drawn as a large multi-room **building on Bree's Surface** — the
player walks in through the door, no map change — rather than an enterable
**interior Level**. This is a deliberate deviation: the Level/Enter machinery
already exists (the barrow deeps), so a reader might expect the Pony, being *the*
attraction, to be entered the same way. We chose the surface building because the
Level machinery is barrow-shaped (negative `has_deeps` Levels, a
`KIND_RUIN_ENTRANCE` tile, "you pass beneath the broken arch" prose, a dungeon
generator that only takes a depth number), and generalizing it to positive
building interiors is real work for a single inn. A surface building ships on the
existing `building()` helper and keeps the whole hub — Butterbur, the shops, the
crowd — visible on one map.

## Considered options

- **Enterable interior Level** (rejected for now): most faithful to the drawn
  floor-plan and roomiest, but requires teaching the Region/Enter system about
  non-barrow interiors (a positive-index or differently-typed Level, a generic
  "entrance" tile and prose, an interior generator). Deferred, not foreclosed —
  if more buildings want interiors later, generalize the machinery then.

## Consequences

- The Pony's detail is bounded by Bree's 62×44 Surface, so its interior is a
  **focused grand common room + inn-yard + stables**, not the full named-room
  warren of the source map.
- Dropping the market **Square** (Pony-as-hub) means the Surface has room to make
  the Pony large without the map feeling crowded.
