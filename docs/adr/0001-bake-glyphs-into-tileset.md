# Bake custom pixel-art glyphs into the FreeType tileset

## Context

We render the game font ourselves with FreeType (`lonelands/fonts.py`) instead
of letting libtcod size glyphs from the cell — this gives us full control over
the tileset's pixel data. The dice tray needs die-face symbols (d6 pip faces, a
d12 feat die, and the tengwar / Eye of Sauron / Gandalf runes) that no
monospace font ships, and certainly not our bundled Atkinson Hyperlegible Mono
(360 glyphs, ASCII + accents only).

## Decision

Draw those symbols as pixel art in code and **bake them into the tileset at
Private Use Area codepoints** (U+E000+), rather than sourcing a second symbol
font or an image-tile atlas. The renderer then prints them like any other
character (`console.print(x, y, feat_char(9), fg=...)`), so they inherit the
grid, per-cell colour, and the crisp integer-scaled resize path for free.

## Consequences

- Symbols live wherever the text does — one tileset, one code path, no separate
  atlas to align or a second font to license and fall back from.
- The art is bound to the cell size and re-rasterised on every resize, alongside
  the letters. Pixel-art routines must be written against the live cell
  dimensions, not hardcoded pixels.
- PUA codepoints are ours to assign; `lonelands/dice_glyphs.py` is the single
  registry so the baker and the tray renderer never disagree on which codepoint
  is which face.
- This is the reusable seam for any future bespoke glyph (map icons, UI marks):
  add a codepoint to the registry and a draw routine to the baker.
- **Amended by ADR-0015.** The map-art use of this seam (a CP437 tilesheet baked
  into a separate `graphic_cp` codepoint block) has been retired with the move to
  an ASCII-only play field. The dice faces in `dice_glyphs.py` are now the sole
  remaining bake — the seam still exists for them, and for any future bespoke
  glyph, but the map and its entities render as plain TTF glyphs.
