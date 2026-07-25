"""TrueType tileset loading.

libtcod's built-in ``load_truetype_font`` sizes every glyph from the cell
*width*, so in a tall, narrow cell the text ends up tiny with a sea of empty
space above and below it — the root of the "unreadable font" problem. Instead
we render glyphs ourselves with FreeType (the technique from python-tcod's
``examples/ttf.py``), which lets us:

  * size the glyph to *fill* the cell (auto-fit picks the largest pixel size
    that fits both dimensions without clipping), and
  * lay every glyph on one shared baseline so prose reads as a clean line
    rather than bobbing letters.

Pair this with ``integer_scaling=True`` on ``present`` and a re-render on window
resize (see ``main.py``) and the text stays crisp at any window size.

If ``freetype-py`` is not installed we fall back to libtcod's loader so the game
still runs — just without the readability win.
"""
from __future__ import annotations

import os

import numpy as np
import tcod.tileset

from lonelands import config

try:
    import freetype  # type: ignore

    _HAVE_FREETYPE = True
except ImportError:  # pragma: no cover - optional dependency
    _HAVE_FREETYPE = False

# Glyphs we care about fitting: printable ASCII (map symbols, prose, menus) plus
# the accented vowels in Middle-earth names (Dúnedain, Talbrún) and the em-dash
# used throughout the prose. Auto-fit measures ink extents over this set so the
# tallest accent and deepest descender never clip.
_SAMPLE = [chr(c) for c in range(0x20, 0x7F)] + list("áéíóúÁÉÍÓÚâêîôûàèìòùñÑ—…“”‘’")


def _metrics(face: "freetype.Face", pixel_height: int) -> tuple[int, int, int, int]:
    """Return (advance, max_bitmap_width, ink_top, ink_bot) at a pixel height.

    ``ink_top``/``ink_bot`` are the greatest extents above/below the baseline
    across the sample set; ``advance`` is the monospace cell advance.
    """
    face.set_pixel_sizes(0, pixel_height)
    face.load_char("M")
    advance = face.glyph.advance.x // 64
    max_w = ink_top = ink_bot = 0
    for ch in _SAMPLE:
        face.load_char(ch)
        bitmap = face.glyph.bitmap
        if bitmap.rows == 0:
            continue
        max_w = max(max_w, bitmap.width)
        ink_top = max(ink_top, face.glyph.bitmap_top)
        ink_bot = max(ink_bot, bitmap.rows - face.glyph.bitmap_top)
    return advance, max_w, ink_top, ink_bot


def _best_pixel_height(face: "freetype.Face", width: int, height: int) -> tuple[int, int]:
    """Largest pixel height whose glyphs fit ``width``x``height``.

    Returns ``(pixel_height, baseline_row)``. The baseline is shared by every
    glyph so letters sit on one line; it is placed to vertically center the ink
    band, guaranteeing nothing clips top or bottom.
    """
    best = (8, height - 1)
    # Cap the search a bit above the cell height; glyphs never need to be taller
    # than the cell they live in.
    for pixel_height in range(8, height * 2):
        advance, max_w, ink_top, ink_bot = _metrics(face, pixel_height)
        if advance > width or max_w > width or (ink_top + ink_bot) > height:
            break
        # Center the ink band; the shared baseline sits below the top padding.
        top_pad = (height - (ink_top + ink_bot)) // 2
        best = (pixel_height, top_pad + ink_top)
    return best


def _render_freetype(path: str, width: int, height: int) -> tcod.tileset.Tileset:
    face = freetype.Face(path)
    pixel_height, baseline = _best_pixel_height(face, width, height)
    face.set_pixel_sizes(0, pixel_height)

    tileset = tcod.tileset.Tileset(width, height)
    for codepoint, glyph_index in face.get_chars():
        face.load_glyph(glyph_index)
        bitmap = face.glyph.bitmap
        if bitmap.rows == 0 or bitmap.width == 0:
            continue  # blank glyph (space, etc.)
        if bitmap.pixel_mode != freetype.FT_PIXEL_MODE_GRAY:
            continue  # skip anything we can't treat as an 8-bit coverage mask
        glyph = np.asarray(bitmap.buffer, dtype=np.uint8).reshape(
            (bitmap.rows, bitmap.width)
        )

        cell = np.zeros((height, width), dtype=np.uint8)
        # Horizontal: center the glyph in the cell. Vertical: place its top on
        # the shared baseline (baseline - bitmap_top).
        left = (width - bitmap.width) // 2
        top = baseline - face.glyph.bitmap_top
        # Intersect the glyph rect with the cell so an overhang clips cleanly
        # instead of raising.
        gy0 = max(0, -top)
        gx0 = max(0, -left)
        cy0 = max(0, top)
        cx0 = max(0, left)
        h = min(glyph.shape[0] - gy0, cell.shape[0] - cy0)
        w = min(glyph.shape[1] - gx0, cell.shape[1] - cx0)
        if h > 0 and w > 0:
            cell[cy0 : cy0 + h, cx0 : cx0 + w] = glyph[gy0 : gy0 + h, gx0 : gx0 + w]

        tileset.set_tile(codepoint, cell)
    return tileset


def load_tileset(width: int | None = None, height: int | None = None) -> tcod.tileset.Tileset:
    """Load the game font as a tileset sized ``width`` x ``height`` pixels.

    Defaults come from :mod:`lonelands.config`. Uses FreeType auto-fit rendering
    when available, otherwise libtcod's loader, otherwise a blank tileset.
    """
    if width is None:
        width = config.TILE_WIDTH
    if height is None:
        height = config.TILE_HEIGHT
    width = max(1, width)
    height = max(1, height)

    for path in config.FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        if _HAVE_FREETYPE:
            try:
                return _render_freetype(path, width, height)
            except Exception:  # noqa: BLE001 - fall back on any FreeType failure
                pass
        try:
            return tcod.tileset.load_truetype_font(path, width, height)
        except RuntimeError:
            continue

    return tcod.tileset.Tileset(width, height)
