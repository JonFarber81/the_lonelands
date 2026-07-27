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

from lonelands import config, dice_glyphs, tile_glyphs

try:
    import freetype  # type: ignore

    _HAVE_FREETYPE = True
except ImportError:  # pragma: no cover - optional dependency
    _HAVE_FREETYPE = False

# Glyphs we care about fitting: printable ASCII (map symbols, prose, menus) plus
# the accented vowels in Middle-earth names (Dúnedain, Amon Sûl) and the em-dash
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

    _bake_dice(tileset, face, width, height)
    return tileset


# --- Die-face glyphs -------------------------------------------------------
# We draw the One Ring dice as pixel art and bake them into the tileset at the
# codepoints in dice_glyphs (see ADR 0001). Everything is drawn in white (255
# alpha); the tray renderer tints each die by printing it with a colour.


def _die_box(width: int, height: int) -> tuple[int, int, int]:
    """Return (x0, y0, side) of a square die centred in the canvas.

    ``width`` here is the *canvas* width — a die spans two cells, so this is
    twice the tile width, giving the face room for a legible numeral.
    """
    side = min(width - 2, height - 4)
    side = max(6, side)
    x0 = (width - side) // 2
    y0 = (height - side) // 2
    return x0, y0, side


def _draw_die_frame(cell: "np.ndarray", width: int, height: int) -> tuple[int, int, int, int]:
    x0, y0, side = _die_box(width, height)
    x1, y1 = x0 + side - 1, y0 + side - 1
    cell[y0, x0 : x1 + 1] = 255
    cell[y1, x0 : x1 + 1] = 255
    cell[y0 : y1 + 1, x0] = 255
    cell[y0 : y1 + 1, x1] = 255
    for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        cell[cy, cx] = 70  # knock back the corners for a rounded feel
    return x0, y0, x1, y1


def _rasterize(face, ch: str, px: int) -> "np.ndarray":
    face.set_pixel_sizes(0, px)
    face.load_char(ch)
    bmp = face.glyph.bitmap
    if bmp.rows == 0 or bmp.width == 0:
        return np.zeros((0, 0), dtype=np.uint8)
    return np.asarray(bmp.buffer, dtype=np.uint8).reshape((bmp.rows, bmp.width))


def _numeral_art(face, s: str, px: int) -> "np.ndarray":
    arts = [a for a in (_rasterize(face, c, px) for c in s) if a.size]
    if not arts:
        return np.zeros((0, 0), dtype=np.uint8)
    h = max(a.shape[0] for a in arts)
    arts = [np.pad(a, ((h - a.shape[0], 0), (0, 0))) for a in arts]  # bottom-align
    parts = []
    for i, a in enumerate(arts):
        if i:
            parts.append(np.zeros((h, 1), dtype=np.uint8))
        parts.append(a)
    return np.concatenate(parts, axis=1)


def _blit_center(cell, art, box) -> None:
    if art.size == 0:
        return
    x0, y0, x1, y1 = box
    bh, bw = art.shape
    oy = y0 + max(0, (y1 - y0 + 1 - bh) // 2)
    ox = x0 + max(0, (x1 - x0 + 1 - bw) // 2)
    h = min(bh, cell.shape[0] - oy)
    w = min(bw, cell.shape[1] - ox)
    if h > 0 and w > 0:
        cell[oy : oy + h, ox : ox + w] = np.maximum(cell[oy : oy + h, ox : ox + w], art[:h, :w])


def _numeral_face(width, height, face, value) -> "np.ndarray":
    """A die frame carrying its value as a centred numeral (rather than pips)."""
    cell = np.zeros((height, width), dtype=np.uint8)
    box = _draw_die_frame(cell, width, height)
    x0, y0, x1, y1 = box
    inner = (x0 + 2, y0 + 2, x1 - 2, y1 - 2)
    interior_h = (y1 - 2) - (y0 + 2)
    s = str(value)
    px = interior_h + 2 if len(s) == 1 else max(6, int(interior_h * 0.8))
    _blit_center(cell, _numeral_art(face, s, px), inner)
    return cell


def _tengwar(width, height) -> "np.ndarray":
    """The great-success rune on a Success die's 6 face.

    A Fëanorian letter shape: a vertical stem (telco) carrying a closed bow
    (lúva) on the upper right — recognisably a rune rather than a stray mark.
    """
    cell = np.zeros((height, width), dtype=np.uint8)
    x0, y0, x1, y1 = _draw_die_frame(cell, width, height)
    side = x1 - x0
    stem_x = x0 + 3
    top, bot = y0 + 3, y1 - 3
    mid = (top + bot) // 2
    cell[top : bot + 1, stem_x] = 255                 # telco (stem)
    bx = min(stem_x + max(3, side // 2), x1 - 2)      # bow's right edge
    cell[top : mid + 1, bx] = 255                     # bow right side
    cell[top, stem_x : bx + 1] = 255                  # bow top
    cell[mid, stem_x : bx + 1] = 255                  # bow bottom (closes the bowl)
    return cell


def _eye(width, height) -> "np.ndarray":
    """The Eye of Sauron on the Feat die's 11 face: a lidded eye with a slit."""
    cell = np.zeros((height, width), dtype=np.uint8)
    x0, y0, side = _die_box(width, height)
    x1, y1 = x0 + side - 1, y0 + side - 1
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    half_w = (x1 - x0) // 2 - 1
    for x in range(cx - half_w, cx + half_w + 1):    # almond lids (upper + lower arcs)
        t = (x - cx) / max(1, half_w)
        lid = int(round((1 - t * t) * (side * 0.30)))
        cell[cy - lid, x] = 220
        cell[cy + lid, x] = 220
    for y in range(cy - side // 5, cy + side // 5 + 1):  # vertical slit pupil
        cell[y, cx] = 255
    return cell


def _gandalf(width, height) -> "np.ndarray":
    """The Gandalf rune on the Feat die's 12 face: an angular auto-success mark."""
    cell = np.zeros((height, width), dtype=np.uint8)
    box = _draw_die_frame(cell, width, height)
    x0, y0, x1, y1 = box
    cx = (x0 + x1) // 2
    ix0, iy0, ix1, iy1 = x0 + 3, y0 + 3, x1 - 3, y1 - 3
    cell[iy0, ix0 : ix1 + 1] = 255           # top bar
    cell[iy0 : iy1 + 1, ix0] = 255           # left stem
    cell[iy1, ix0 : ix1 + 1] = 255           # bottom bar
    cell[iy1 - (iy1 - iy0) // 2 : iy1 + 1, ix1] = 255  # short right stem
    cell[iy1 - (iy1 - iy0) // 2, cx : ix1 + 1] = 255   # inward tongue
    return cell


def _success_art(canvas_w, height, face, v) -> "np.ndarray":
    if v == 6:
        return _tengwar(canvas_w, height)  # the great-success rune, not a "6"
    return _numeral_face(canvas_w, height, face, v)


def _feat_art(canvas_w, height, face, v) -> "np.ndarray":
    if v == 11:
        return _eye(canvas_w, height)
    if v == 12:
        return _gandalf(canvas_w, height)
    return _numeral_face(canvas_w, height, face, v)


def _bake_block(tileset, codepoints, art, width, height) -> None:
    """Bake a 2×2 die: split the canvas into four cell tiles (TL, TR, BL, BR)."""
    tl, tr, bl, br = codepoints
    quads = {
        tl: art[:height, :width],
        tr: art[:height, width : width * 2],
        bl: art[height : height * 2, :width],
        br: art[height : height * 2, width : width * 2],
    }
    for cp, quad in quads.items():
        tileset.set_tile(cp, np.ascontiguousarray(quad))


def _bake_dice(tileset, face, width, height) -> None:
    # Each die spans a DIE_COLS×DIE_ROWS block of cells; draw the art on a canvas
    # that large so the numeral faces read clearly, then split it into cell tiles.
    canvas_w = width * dice_glyphs.DIE_COLS
    canvas_h = height * dice_glyphs.DIE_ROWS
    for v in dice_glyphs.SUCCESS_VALUES:
        _bake_block(
            tileset, dice_glyphs.success_codepoints(v),
            _success_art(canvas_w, canvas_h, face, v), width, height,
        )
    for v in dice_glyphs.FEAT_VALUES:
        _bake_block(
            tileset, dice_glyphs.feat_codepoints(v),
            _feat_art(canvas_w, canvas_h, face, v), width, height,
        )


# --- Map tileset glyphs ----------------------------------------------------
# Map terrain and entity glyphs come from a Dwarf-Fortress-style 16x16 CP437
# tilesheet (Wanderlust by default; see config.TILESET_CANDIDATES). We bake each
# printable-ASCII cell into its Private-Use "graphic" codepoint (see
# tile_glyphs) so the map draws shaded tiles while prose keeps the TTF glyph on
# the plain ASCII codepoint. The sheet's glyphs are white with the shape carried
# in the alpha channel, so we bake alpha as a coverage mask — the map renderer
# then tints each tile with its terrain/entity colour, exactly as before.

_TILESHEET_UNSET = object()
_tilesheet_cache: "tcod.tileset.Tileset | None | object" = _TILESHEET_UNSET


def _load_tilesheet() -> "tcod.tileset.Tileset | None":
    """The map tilesheet (16x16 CP437), or ``None`` if none is installed.

    Cached module-wide: the sheet is resolution-independent, so a window resize
    reuses it and only re-resamples. Returns ``None`` when no candidate file
    exists or loading fails, so the caller can fall back to TTF glyphs.
    """
    global _tilesheet_cache
    if _tilesheet_cache is not _TILESHEET_UNSET:
        return _tilesheet_cache  # type: ignore[return-value]
    _tilesheet_cache = None
    for path in config.TILESET_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            _tilesheet_cache = tcod.tileset.load_tilesheet(
                path, 16, 16, tcod.tileset.CHARMAP_CP437
            )
            break
        except Exception:  # noqa: BLE001 - any load failure -> fall back to TTF
            continue
    return _tilesheet_cache  # type: ignore[return-value]


def _resample_nearest(mask: "np.ndarray", width: int, height: int) -> "np.ndarray":
    """Nearest-neighbour resample a 2-D coverage mask to ``height`` x ``width``.

    Nearest-neighbour (not bilinear) keeps the pixel-art crisp when the cell is
    an integer multiple of the source, and merely blocky otherwise — never
    blurred.
    """
    sh, sw = mask.shape
    if (sh, sw) == (height, width):
        return np.ascontiguousarray(mask)
    ys = (np.arange(height) * sh) // height
    xs = (np.arange(width) * sw) // width
    return np.ascontiguousarray(mask[ys][:, xs])


def _fit_square_centered(mask: "np.ndarray", width: int, height: int) -> "np.ndarray":
    """Resample a square tile to fill the smaller cell dimension, then centre it.

    The tilesheet art is square, so on a non-square cell we letterbox rather than
    stretch: the tile keeps its aspect (never distorted) and sits centred with a
    thin margin on the longer axis. On a square cell this fills it exactly.
    """
    side = min(width, height)
    art = _resample_nearest(mask, side, side)
    cell = np.zeros((height, width), dtype=np.uint8)
    oy, ox = (height - side) // 2, (width - side) // 2
    cell[oy : oy + side, ox : ox + side] = art
    return cell


def _bake_graphics(tileset: tcod.tileset.Tileset, width: int, height: int) -> None:
    """Bake map/entity tiles into their graphic codepoints.

    Uses the installed tilesheet when present; otherwise copies the TTF glyph
    already baked for the same character, so the map still renders (just in the
    plain font) when no sheet is available.
    """
    sheet = _load_tilesheet()
    for o in tile_glyphs.GRAPHIC_RANGE:
        cp = tile_glyphs.GRAPHIC_BASE + o
        if sheet is not None:
            cell = _fit_square_centered(sheet.get_tile(o)[..., 3], width, height)
        else:
            cell = tileset.get_tile(o)[..., 3]  # reuse the TTF glyph's coverage
        tileset.set_tile(cp, cell)

    # The extra map glyphs (box-drawing roads, the deeps ▼): the CP437 tilesheet
    # carries these where the prose TTF does not, so bake them from the sheet by
    # their real codepoint (CHARMAP_CP437 maps ▼/─/│/┼ to their cells). With no
    # sheet, reuse whatever the TTF baked — blank if it lacks the glyph.
    for ch, cp in tile_glyphs._EXTRA_CP.items():
        if sheet is not None:
            cell = _fit_square_centered(sheet.get_tile(ord(ch))[..., 3], width, height)
        else:
            cell = tileset.get_tile(ord(ch))[..., 3]
        tileset.set_tile(cp, cell)


def _build_base_tileset(width: int, height: int) -> tcod.tileset.Tileset:
    """The text tileset: FreeType auto-fit, else libtcod's loader, else blank."""
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


def load_tileset(width: int | None = None, height: int | None = None) -> tcod.tileset.Tileset:
    """Load the game tileset sized ``width`` x ``height`` pixels.

    Prose glyphs come from the bundled TrueType font (FreeType auto-fit when
    available); map terrain and entity glyphs are then baked in from the CP437
    tilesheet (see :func:`_bake_graphics`). Defaults come from
    :mod:`lonelands.config`.
    """
    if width is None:
        width = config.TILE_WIDTH
    if height is None:
        height = config.TILE_HEIGHT
    width = max(1, width)
    height = max(1, height)

    tileset = _build_base_tileset(width, height)
    _bake_graphics(tileset, width, height)
    return tileset
