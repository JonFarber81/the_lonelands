# pygame for windowing, rendering, and input; tcod retained for FOV + pathfinding

## Context

The hardest, most bespoke code in the repo existed only to force readable,
cell-filling fonts through tcod's fixed character-grid model: the FreeType
auto-fit machine in `fonts.py`, the pixel-art dice baked into Private-Use
codepoints, the CP437 tilesheet nearest-neighbour resampling. tcod also owned
the window, the event loop, and glyph rasterisation — a lot of surface for what
is, outside the map, a menu-and-dialog game that wants proportional text and
free-form layout.

`pygame.font` renders any TrueType face at any pixel size natively, and surfaces
can be positioned freely rather than snapped to cells. The map/game view,
though, genuinely *is* a grid, and should stay one.

## Decision

Move the **window, render, and input layer to pygame**; keep the map/game view a
tile grid behind a thin `Console` shim. tcod stays a dependency but **only as a
headless library** for `tcod.map.compute_fov` (`engine.py`) and
`tcod.path.SimpleGraph` / `Pathfinder` (`components/ai.py`). It no longer owns
the window, the event loop, or font rendering.

The migration shipped in four phases, each independently runnable:

1. **Window + Console shim + event loop.** `lonelands/display.py` owns the pygame
   window and a `Console` backed by a numpy structured `(ch, fg, bg)` buffer —
   the same surface the renderers already drew through (`print`, `draw_rect`,
   `draw_frame`, `.rgb`), so the map view and every screen kept working
   unchanged. `lonelands/events.py` replaces `tcod.event.EventDispatch` with our
   own dispatch and vendors `KeySym` / `Modifier` (the SDL keycodes tcod and
   pygame both report), so handler bodies still read `KeySym.UP`,
   `event.mod & Modifier.SHIFT`, `event.tile.x`.
2. **Native glyph atlas.** `fonts.py` became `GlyphAtlas`, baking prose
   (`pygame.font`), CP437 map tiles, and the dice faces into per-codepoint
   pygame surfaces. FreeType and the tcod `Tileset` are gone; `freetype-py` was
   dropped from requirements.
3. **Native menus.** Menus, dialogs, and popups render as free-form pygame
   surfaces with a proportional font (`lonelands/ui.py`) via an
   `on_render_native(display)` hook, drawn over the blitted console grid. The
   map view, HUD, lock-on targeting, the Overworld atlas, and the game-over
   screen stay on the grid.
4. **Cleanup + this ADR.** The only remaining tcod use is FOV + pathfinding.

This **supersedes the rendering side of ADR-0001**: the glyph-baking *contract*
survives untouched — the dice/tile Private-Use codepoint registries
(`dice_glyphs.py`, `tile_glyphs.py`) are still the single source of truth, and
the pixel-art die faces are still drawn in code — only the *backend* changed
(pygame surfaces instead of tcod tileset tiles).

## Consequences

- Menus escape the cell grid: proportional text, free wrap/align, translucent
  panels — they read far better than the old character grid. The map stays a
  crisp integer-scaled grid, re-rasterised on resize as before.
- Two clean seams made this tractable and keep it reversible: every renderer
  draws through `console`, and every handler dispatches `ev_*`. The `Console`
  shim and the event shim are where tcod met the game; both are small.
- tcod's FOV and pathfinding are ~40 lines each to vendor if we ever want zero
  tcod; that is deliberately still out of scope. FOV/path run headless with no
  window/SDL context in the pygame process.
- On macOS, pygame and tcod each bundle their own SDL2, so startup prints
  harmless `objc[...] Class ... implemented in both` warnings. Functionally
  inert — tcod is only used headless.
- The menu font is resolved via `pygame.font.SysFont` (a proportional system
  face), falling back to pygame's bundled default; the bundled Atkinson mono is
  still used for the map/HUD grid and the columnar help page.
