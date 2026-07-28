# Sprite tileset — implementation plan

**Superseded.** This was ADR-0013's phase plan (Kenney art, vendored into
`lonelands/assets/tiles/`); ADR-0013 was itself superseded by ADR-0015, then
ADR-0015 by ADR-0016, which took a different technical basis (licensed Oryx
monochrome masks, loaded locally via `LONELANDS_TILES`, never vendored). See
`docs/adr/0016-oryx-monochrome-tinted-tileset.md` and
`notes/oryx-tileset-mapping.md` for the current plan and sprite-key mapping.
Kept for the record of what was tried.

Turns ADR-0013 into a sequence of GitHub issues. Each is independently
shippable and leaves the game runnable; ASCII mode is the safety net throughout,
so a half-finished sprite swap is never a broken game. Phases are ordered by
dependency — later phases assume the seams built earlier.

Canonical terms: **Sprite mode / ASCII mode**, **Tile sheet**, **Sprite key**,
**Terrain layer / Entity layer**, **remembered / unseen** (CONTEXT.md →
Presentation → *The play field*).

Backbone art: Kenney **Roguelike Base + Characters + Dungeon** (CC0), vendored
into `lonelands/assets/tiles/`. Mockups of the target look:
`screenshots/mockup_bree_roguelike.png`, `mockup_barrow_roguelike.png`,
`mockup_shire_roguelike.png`.

---

## Phase 0 — Vertical slice (spike)  ·  *first, de-risks everything*

Prove the whole path end-to-end on one region behind a hidden flag, with
throwaway hard-coding allowed.

- Load one Roguelike sheet into the `GlyphAtlas`/display path.
- Resolve a handful of sprite keys (grass, road, stone, wall, door, tree,
  townsman, orc, ranger) to sheet coords.
- Two-layer blit (terrain then entity) for those cells only.
- Square 16×16 cells for the map view only.
- Render Bree surface in Sprite mode under `--sprites` (undocumented).

**Done when:** launching Bree with the flag shows sprites composited over
terrain, ASCII mode still default and unchanged. No data model, no toggle UI, no
coverage yet. Findings feed the phase list below.

## Phase 1 — Sprite-key model + data table

- Add a `sprite_key` to `tile_types` and to entities (parallel to `char`).
- Data-driven table: sprite key → `(sheet, col, row)`; one source of truth.
- Race→sprite table paralleling the ADR-0009 race→letter map (wandering crowd);
  `@` NPCs get explicit keys.
- ASCII path untouched.

**Done when:** every current drawable has a sprite key resolving to a tile (or an
explicit "falls back to glyph" marker); a unit test asserts no key is orphaned.

## Phase 2 — Two-layer Console + FOV dimming

- Extend the `Console` buffer to carry a terrain sprite-key + an ordered entity
  sprite-key stack per cell (today: one `(ch, fg, bg)`).
- Compositing blit: terrain, then entity layer with transparency.
- **Remembered/unseen** as a brightness multiply on the terrain sprite; verify
  interplay with the popup **scrim**.

**Done when:** a dropped item shows under a creature; remembered tiles dim,
unseen are black; ASCII mode still collapses to one glyph.

## Phase 3 — Square geometry + HUD reflow

- Map cells 16×20 → 16×16; re-proportion the map viewport, sidebar, and log grid.
- Confirm the native chrome (ADR-0010) is unaffected; re-tune any cell-derived
  layout constants in `config.py`/`hud.py`.

**Done when:** sprites are pixel-perfect (no letterbox/stretch) and the HUD/log
still fill the screen with no clipping, in both modes.

## Phase 4 — The toggle

- Persisted setting + in-game key; default = Sprite mode; ASCII fully renderable.
- Document the toggle (help page, README Screens).

**Done when:** a keypress swaps the play field live, the choice persists across
runs, and both modes are visually complete for the covered content.

## Phase 5 — Coverage: overworld terrain + townsfolk

- Map every overworld tile type + townsfolk/race sprites across the authored
  clusters (Shire corridor, Bree, the Lone-lands, north/NE, south, mountain-gates).
- Roads, fords/bridges, fences, signposts, water, trees per biome band.

**Done when:** walking the overworld shows sprites everywhere with no glyph
fallbacks except known gaps (Phase 7).

## Phase 6 — Coverage: dungeon/barrow + monsters & undead

- Roguelike Dungeon set for barrow deeps and other lower Levels: walls, floors,
  doors, torches, bones, gold.
- Monster roster: orcs, wargs, wights/ghosts, trolls, and the wandering threats
  (ADR-0007).

**Done when:** a barrow deep renders like `mockup_barrow_roguelike.png`,
including FOV darkness.

## Phase 7 — Custom art for stock-pack gaps  ·  *Shire hobbit-holes first*

The Roguelike pack has no adequate hobbit-hole tile (the Shire mockup shows the
gap). Author bespoke 16×16 tiles via the ADR-0001 glyph-baking seam for:

- Hobbit-holes (round green door in a grassy mound) — the priority.
- Any other gaps surfaced in Phases 5–6.

**Done when:** the Shire renders convincingly and the gap list from earlier
phases is closed or explicitly deferred.

---

### Cross-cutting

- **Accessibility:** ASCII mode is a first-class supported mode, never a debug
  leftover — it must stay complete as coverage grows.
- **Not covered by the mockups:** the combat HUD + dice tray under sprites (the
  dropped road-ambush scene). Verify during Phase 6.
- **Testing:** each phase keeps the suite green; add golden-image or key-coverage
  tests where cheap. Sprite rendering itself is validated by running the app
  (`/run`, `/verify`), not only unit tests.
