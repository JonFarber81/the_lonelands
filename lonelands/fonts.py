"""Glyph atlas: prose, map tiles, and dice faces rasterised into pygame surfaces.

Issue #66 Phase 2 replaced the tcod ``Tileset`` (and the FreeType auto-fit
machine) with :class:`GlyphAtlas`, which bakes every glyph the game prints —
prose, map/entity tiles, and the One Ring dice — into per-codepoint pygame
surfaces at the current cell size. :mod:`lonelands.display` caches these and
tints each one by the cell's foreground colour on blit.

The three glyph families keep the codepoint contract they always had:

  * **Prose** — printable ASCII, accented vowels, and typographic marks are
    rendered from the bundled TrueType face with :mod:`pygame.font`, sized once
    to fill the cell (no more per-pixel FreeType fitting; pygame sizes natively).
    A codepoint the font lacks (e.g. box-drawing) yields ``None`` — a blank cell,
    exactly as under tcod.
  * **Map/entity tiles** — the Private-Use graphic codepoints
    (:mod:`lonelands.tile_glyphs`) come from the CP437 tilesheet, one 16×16 cell
    each, letterboxed into the cell. The shape lives in the sheet's alpha
    channel, so tiles are baked white and tinted like any other glyph. With no
    sheet installed they fall back to the prose glyph for the same character.
  * **Dice faces** — the pixel-art die faces (:mod:`lonelands.dice_glyphs`) are
    drawn as coverage masks (frame, tengwar, Eye, Gandalf rune) with numerals
    rasterised from the same TTF, then split into the 2×2 block of cell tiles.
"""
from __future__ import annotations

import os
from typing import Callable, Dict, Optional

import numpy as np
import pygame

from lonelands import config, dice_glyphs, tile_glyphs

# Glyphs the auto-fit must accommodate: printable ASCII plus the accented vowels
# in Middle-earth names (Dúnedain, Amon Sûl) and the typographic marks used in
# prose. The chosen size is the largest whose widest sample glyph still fits the
# cell, so nothing clips.
_SAMPLE = [chr(c) for c in range(0x20, 0x7F)] + list("áéíóúÁÉÍÓÚâêîôûàèìòùñÑ—…“”‘’")

# The extra map glyphs live at their CP437 byte positions in the tilesheet (the
# sheet is laid out in CP437 order), not at their Unicode codepoints. Keyed by
# the same chars tile_glyphs registers; the assert fails loudly if a glyph is
# appended there without a position here (which would else pick a garbage tile).
_CP437_EXTRA = {"─": 196, "│": 179, "┼": 197, "▼": 31}
assert set(_CP437_EXTRA) == set(tile_glyphs.GRAPHIC_EXTRA), (
    "fonts._CP437_EXTRA is out of sync with tile_glyphs.GRAPHIC_EXTRA"
)

_RasterizeFn = Callable[[str, int], "np.ndarray"]


# --- surface helpers -------------------------------------------------------
def _mask_to_surface(mask: "np.ndarray") -> "Optional[pygame.Surface]":
    """A white surface whose alpha is the coverage ``mask`` (rows, cols); the
    display tints it by the cell's foreground colour. ``None`` if fully blank."""
    if mask.size == 0 or int(mask.max()) == 0:
        return None
    h, w = mask.shape
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    rgb = pygame.surfarray.pixels3d(surf)
    rgb[:] = 255
    del rgb
    alpha = pygame.surfarray.pixels_alpha(surf)
    alpha[:] = np.ascontiguousarray(mask.T)  # numpy (h, w) -> pygame (w, h)
    del alpha
    return surf


def _resample_nearest(mask: "np.ndarray", width: int, height: int) -> "np.ndarray":
    """Nearest-neighbour resample a 2-D coverage mask to ``height`` x ``width``.

    Nearest (not bilinear) keeps the pixel-art crisp at integer multiples and
    merely blocky otherwise — never blurred."""
    sh, sw = mask.shape
    if (sh, sw) == (height, width):
        return np.ascontiguousarray(mask)
    ys = (np.arange(height) * sh) // height
    xs = (np.arange(width) * sw) // width
    return np.ascontiguousarray(mask[ys][:, xs])


def _fit_square_centered(mask: "np.ndarray", width: int, height: int) -> "np.ndarray":
    """Resample a square tile to the smaller cell dimension, then centre it.

    The tilesheet art is square, so on a non-square cell we letterbox rather than
    stretch: the tile keeps its aspect and sits centred with a thin margin on the
    longer axis. On a square cell it fills exactly."""
    side = min(width, height)
    art = _resample_nearest(mask, side, side)
    cell = np.zeros((height, width), dtype=np.uint8)
    oy, ox = (height - side) // 2, (width - side) // 2
    cell[oy : oy + side, ox : ox + side] = art
    return cell


# --- Die-face pixel art ----------------------------------------------------
# The One Ring dice are drawn as coverage masks and baked into the dice
# codepoints (see ADR 0001). Everything is white; the tray renderer tints each
# die by printing it with a colour. A die spans a DIE_COLS×DIE_ROWS block of
# cells, so the art is drawn on a canvas that large and split into cell tiles.


def _die_box(width: int, height: int) -> "tuple[int, int, int]":
    """Return (x0, y0, side) of a square die centred in the canvas. ``width`` is
    the canvas width — a die spans two cells, so the face has room for a legible
    numeral."""
    side = min(width - 2, height - 4)
    side = max(6, side)
    x0 = (width - side) // 2
    y0 = (height - side) // 2
    return x0, y0, side


def _draw_die_frame(cell: "np.ndarray", width: int, height: int) -> "tuple[int, int, int, int]":
    x0, y0, side = _die_box(width, height)
    x1, y1 = x0 + side - 1, y0 + side - 1
    cell[y0, x0 : x1 + 1] = 255
    cell[y1, x0 : x1 + 1] = 255
    cell[y0 : y1 + 1, x0] = 255
    cell[y0 : y1 + 1, x1] = 255
    for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        cell[cy, cx] = 70  # knock back the corners for a rounded feel
    return x0, y0, x1, y1


def _numeral_art(rasterize: _RasterizeFn, s: str, px: int) -> "np.ndarray":
    arts = [a for a in (rasterize(c, px) for c in s) if a.size]
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


def _numeral_face(width, height, rasterize: _RasterizeFn, value) -> "np.ndarray":
    """A die frame carrying its value as a centred numeral (rather than pips)."""
    cell = np.zeros((height, width), dtype=np.uint8)
    box = _draw_die_frame(cell, width, height)
    x0, y0, x1, y1 = box
    inner = (x0 + 2, y0 + 2, x1 - 2, y1 - 2)
    interior_h = (y1 - 2) - (y0 + 2)
    s = str(value)
    px = interior_h + 2 if len(s) == 1 else max(6, int(interior_h * 0.8))
    _blit_center(cell, _numeral_art(rasterize, s, px), inner)
    return cell


def _tengwar(width, height) -> "np.ndarray":
    """The great-success rune on a Success die's 6 face: a Fëanorian letter — a
    vertical stem (telco) carrying a closed bow (lúva) on the upper right."""
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


def _success_art(canvas_w, height, rasterize: _RasterizeFn, v) -> "np.ndarray":
    if v == 6:
        return _tengwar(canvas_w, height)  # the great-success rune, not a "6"
    return _numeral_face(canvas_w, height, rasterize, v)


def _feat_art(canvas_w, height, rasterize: _RasterizeFn, v) -> "np.ndarray":
    if v == 11:
        return _eye(canvas_w, height)
    if v == 12:
        return _gandalf(canvas_w, height)
    return _numeral_face(canvas_w, height, rasterize, v)


# --- Asset loading ---------------------------------------------------------
def _load_tilesheet() -> "Optional[pygame.Surface]":
    """The CP437 map tilesheet (16×16 cells), or ``None`` if none is installed.

    Loaded raw (not ``convert_alpha``): we only read each cell's alpha channel
    into numpy, so no display mode is required and the sheet is resolution
    independent (a resize just re-letterboxes it)."""
    for path in config.TILESET_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            return pygame.image.load(path)
        except Exception:  # noqa: BLE001 - any load failure -> fall back to TTF
            continue
    return None


def _fit_font(width: int, height: int) -> "Optional[pygame.font.Font]":
    """The largest bundled TTF size whose sample glyphs fit a ``width``×``height``
    cell. Native pygame sizing replaces the old FreeType auto-fit."""
    path = config.find_font()
    if path is None:
        return None
    pygame.font.init()
    best = 6
    for size in range(6, height * 2):
        font = pygame.font.Font(path, size)
        if font.get_height() > height:
            break
        widest = max(
            (font.size(c)[0] for c in _SAMPLE if font.metrics(c)[0] is not None),
            default=0,
        )
        if widest > width:
            break
        best = size
    return pygame.font.Font(path, best)


# --- The atlas -------------------------------------------------------------
class GlyphAtlas:
    """Per-codepoint white glyph surfaces at a fixed cell size, built lazily and
    cached. Rebuilt from scratch on a window resize (a new instance)."""

    def __init__(self, cell_w: int, cell_h: int):
        self.cell_w = cell_w
        self.cell_h = cell_h
        self._font_path = config.find_font()
        self._font = _fit_font(cell_w, cell_h)
        self._font_h = self._font.get_height() if self._font else cell_h
        # SDL_ttf draws a ".notdef" tofu box for any glyph the font lacks (and
        # reports metrics for it), unlike FreeType which skipped missing glyphs.
        # Cache the tofu rendered from a codepoint the font can't have, so we can
        # blank absent glyphs (e.g. box-drawing) and keep the tcod-era look.
        self._notdef = None
        if self._font is not None:
            tofu = self._font.render(chr(0x10FFFF), True, (255, 255, 255))
            self._notdef = pygame.surfarray.array_alpha(tofu)
        self._sheet = _load_tilesheet()
        self._digit_fonts: Dict[int, "pygame.font.Font"] = {}
        self._cache: Dict[int, Optional[pygame.Surface]] = {}
        self._dice = self._bake_dice()

    def base_surface(self, cp: int) -> "Optional[pygame.Surface]":
        """The white glyph surface for ``cp`` (tinted on blit by the display), or
        ``None`` for a blank/absent codepoint."""
        if cp in self._dice:
            return self._dice[cp]
        if cp not in self._cache:
            self._cache[cp] = self._make(cp)
        return self._cache[cp]

    # --- rasterisation -----------------------------------------------------
    def _make(self, cp: int) -> "Optional[pygame.Surface]":
        char = _graphic_source_char(cp)
        if char is not None:
            return self._graphic_surface(char)
        return self._prose_surface(cp)

    def _prose_surface(self, cp: int) -> "Optional[pygame.Surface]":
        if self._font is None:
            return None
        char = chr(cp)
        if not char.strip():
            return None
        glyph = self._font.render(char, True, (255, 255, 255))
        gw = glyph.get_width()
        # A glyph the font lacks renders as the .notdef tofu; blank it so
        # box-drawing (draw_frame) stays invisible, as it was under tcod.
        if gw == 0 or self._is_notdef(glyph):
            return None
        surf = pygame.Surface((self.cell_w, self.cell_h), pygame.SRCALPHA)
        # pygame renders on a constant-height line box, so a shared vertical
        # offset keeps every glyph on one baseline; centre horizontally.
        surf.blit(glyph, ((self.cell_w - gw) // 2, (self.cell_h - self._font_h) // 2))
        if int(pygame.surfarray.array_alpha(surf).max()) == 0:
            return None
        return surf

    def _is_notdef(self, glyph: "pygame.Surface") -> bool:
        """True if ``glyph`` is the font's .notdef tofu (i.e. the char is absent)."""
        if self._notdef is None:
            return False
        alpha = pygame.surfarray.array_alpha(glyph)
        return alpha.shape == self._notdef.shape and np.array_equal(alpha, self._notdef)

    def _graphic_surface(self, char: str) -> "Optional[pygame.Surface]":
        if self._sheet is None:
            return self._prose_surface(ord(char))  # no sheet -> plain font glyph
        pos = _CP437_EXTRA.get(char, ord(char))
        sx, sy = (pos % 16) * 16, (pos // 16) * 16
        tile = self._sheet.subsurface((sx, sy, 16, 16))
        alpha = np.ascontiguousarray(pygame.surfarray.array_alpha(tile).T)  # (16,16)
        return _mask_to_surface(_fit_square_centered(alpha, self.cell_w, self.cell_h))

    def _rasterize(self, s: str, px: int) -> "np.ndarray":
        """Rasterise digit string ``s`` at ~``px`` pixels as a coverage mask
        (rows, cols), for the dice numerals."""
        if self._font_path is None:
            return np.zeros((0, 0), dtype=np.uint8)
        size = max(6, px)
        font = self._digit_fonts.get(size)
        if font is None:
            font = pygame.font.Font(self._font_path, size)
            self._digit_fonts[size] = font
        surf = font.render(s, True, (255, 255, 255))
        if surf.get_width() == 0 or surf.get_height() == 0:
            return np.zeros((0, 0), dtype=np.uint8)
        return np.ascontiguousarray(pygame.surfarray.array_alpha(surf).T)

    def _bake_dice(self) -> "Dict[int, Optional[pygame.Surface]]":
        out: Dict[int, Optional[pygame.Surface]] = {}
        cw, ch = self.cell_w, self.cell_h
        canvas_w = cw * dice_glyphs.DIE_COLS
        canvas_h = ch * dice_glyphs.DIE_ROWS
        for v in dice_glyphs.SUCCESS_VALUES:
            self._split_block(
                out, dice_glyphs.success_codepoints(v),
                _success_art(canvas_w, canvas_h, self._rasterize, v),
            )
        for v in dice_glyphs.FEAT_VALUES:
            self._split_block(
                out, dice_glyphs.feat_codepoints(v),
                _feat_art(canvas_w, canvas_h, self._rasterize, v),
            )
        return out

    def _split_block(self, out, codepoints, art) -> None:
        """Split a 2×2 die canvas into four cell-sized surfaces (TL, TR, BL, BR)."""
        w, h = self.cell_w, self.cell_h
        tl, tr, bl, br = codepoints
        quads = {
            tl: art[:h, :w],
            tr: art[:h, w : w * 2],
            bl: art[h : h * 2, :w],
            br: art[h : h * 2, w : w * 2],
        }
        for cp, quad in quads.items():
            out[cp] = _mask_to_surface(np.ascontiguousarray(quad))


def _graphic_source_char(cp: int) -> "Optional[str]":
    """The source character for a Private-Use *graphic* codepoint (map/entity
    tiles), or ``None`` if ``cp`` is not in the graphic block."""
    base = tile_glyphs.GRAPHIC_BASE
    if base + 0x20 <= cp <= base + 0x7E:
        return chr(cp - base)
    for ch, ecp in tile_glyphs._EXTRA_CP.items():
        if ecp == cp:
            return ch
    return None
