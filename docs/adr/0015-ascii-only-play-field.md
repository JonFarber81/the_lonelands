# ASCII-only play field

## Status

Accepted. **Supersedes ADR-0013** (full-colour sprite tileset), which is now
retired. Amends ADR-0001: the glyph-baking seam survives for the dice only, not
for map/entity art.

## Context

ADR-0013 added a full-colour sprite play field (Kenney Roguelike art) as the
default, with ASCII kept behind a toggle. Only its **Phase 0** ever shipped: a
throwaway vertical slice behind the hidden `--sprites` flag, off by default and
covering one region. The data model, the toggle UI, and the coverage plan were
never built.

Two costs stayed unpaid the whole time. The **sprite path itself** was dead
weight — 500+ lines gated off, plus vendored Kenney sheets. And the map's
default look was never actually ASCII: a separate **CP437 tilesheet**
(Wanderlust, via `tile_glyphs.py`'s Private-Use `graphic_cp` block) drew the
terrain and entities, so the map read as "deluxe ASCII" from tiles a fresh
clone didn't even have (the sheet was gitignored; clones already fell back to
plain TTF glyphs).

We have decided the game is a **classic ASCII roguelike**. The sprite ambition
is dropped, not deferred.

## Decision

The play field is drawn **one way**: each drawable prints its own ASCII
letter/glyph from the bundled TrueType face, tinted per-cell by its foreground
colour, exactly as text is. There is no sprite mode, no tilesheet, and no
separate graphic codepoint.

Concretely:

1. **No sprite path.** `sprites.py`, the Kenney sheets, the `--sprites` flag and
   its debug tone-tuner, and the sprite compositing in `display.py` are removed.
2. **No graphic-codepoint tileset.** `tile_glyphs.py` (the `graphic_cp` /
   `graphic_char` Private-Use mapping) is gone. Tiles store their plain
   `ord(ch)`; the renderers print the character. `fonts.py:GlyphAtlas` bakes
   **prose only** for the map, plus the dice (see below) — no tilesheet loader.
3. **ASCII substitutes for non-ASCII map shapes.** The overworld's connected
   road lines (`─ │ ┼`) and deeps mark (`▼`), glyphs the bundled Atkinson font
   lacks and only rendered via the CP437 sheet, become ASCII `- | +` and `v`.
4. **One cell, one glyph.** No terrain/entity layering; a cell is a single
   `(ch, fg, bg)` again.

## Consequences

- The rendering stack shrinks to a single path. The `Console`/`GlyphAtlas`
  seam from ADR-0010 stays, now feeding prose + dice glyphs only.
- The map's on-screen look is unchanged from what a clean clone already showed
  (plain TTF glyphs) — the change deletes the local-only "deluxe" tile layer.
- Every drawable needs a glyph and nothing else; the standing "glyph *and*
  sprite key" maintenance cost from ADR-0013 is gone.
- If full-colour art is ever wanted again, this ADR and ADR-0013 are the record
  of what was tried and why it was dropped; it would be a fresh decision, not a
  toggle we left wired up.
