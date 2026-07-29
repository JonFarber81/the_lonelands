"""pygame window, render surface, and the ``Console`` shim (issue #66).

The renderers (`game_map`, `render_functions`, every handler's ``on_render``)
draw through a ``console`` object using a small surface: ``clear``, ``print``,
``draw_rect``, ``draw_frame`` and the ``.rgb`` numpy view. :class:`Console` keeps
that surface identical to tcod's console, so none of those call sites change; it
just backs the grid with a plain numpy structured array instead of a tcod
console.

:class:`Display` owns the pygame window and paints a :class:`Console` to it. Each
cell is a glyph blitted from a cache keyed by codepoint, tinted by the cell's
foreground colour, over the cell's background. The white glyph surfaces come
from :class:`lonelands.fonts.GlyphAtlas` (prose, map tiles, and dice, all baked
natively in pygame); the display tints and caches them per foreground colour.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pygame

from lonelands import config, events, fonts, sprites, ui

# An RGB colour as the renderers pass it (a bare 3-tuple, matching tcod).
Color = Tuple[int, int, int]

# The console cell dtype — identical (field-for-field) to ``tile_types.
# graphic_dt`` (ch + fg + bg + sprite), so ``game_map`` can assign a slice of
# terrain graphics straight into ``console.rgb`` exactly as before. ``sprite``
# is a sprites.sprite_id() (ADR 0016); 0 means "ASCII only, no sprite key".
console_dt = np.dtype([("ch", np.int32), ("fg", "3B"), ("bg", "3B"), ("sprite", np.int32)])

# The default frame decoration, matching tcod's ``draw_frame``: top-left, top,
# top-right, left, middle, right, bottom-left, bottom, bottom-right. The bundled
# font carries no box-drawing ink (these glyphs are blank), so frames read as a
# filled background rather than ruled borders — exactly as under tcod today.
_FRAME = "┌─┐│ │└─┘"


class Console:
    """A grid of cells drawn into by the renderers; a drop-in for the subset of
    ``tcod.console.Console`` the game uses."""

    def __init__(self, width: int, height: int, order: str = "F"):
        self.width = width
        self.height = height
        # ``order='F'`` matches tcod so ``console.rgb[x, y]`` indexes column-major
        # just like the map arrays that get assigned into it.
        self._buf = np.zeros((width, height), dtype=console_dt, order=order)
        self.clear()

    @property
    def rgb(self) -> np.ndarray:
        """The raw cell buffer. Renderers read/modify it in place (e.g. dimming
        ``console.rgb['fg'] //= 4`` or writing terrain into a slice)."""
        return self._buf

    def clear(self) -> None:
        self._buf["ch"] = ord(" ")
        self._buf["fg"] = (255, 255, 255)
        self._buf["bg"] = (0, 0, 0)
        self._buf["sprite"] = 0

    def print(
        self, x: int, y: int, string: str,
        fg: Optional[Color] = None, bg: Optional[Color] = None,
        alignment: int = events.LEFT, sprite: str = "",
    ) -> None:
        """Write ``string`` at cell ``(x, y)``. ``fg``/``bg`` left ``None`` keep
        whatever colour the cell already holds (matching tcod's ``print``).
        ``sprite`` is a sprite key (ADR 0016) drawn instead of ``string`` when
        sprites are enabled; every printed cell gets the same one, so a
        multi-char ``string`` should only pass ``sprite`` for single glyphs."""
        for line in string.split("\n"):
            self._print_line(x, y, line, fg, bg, alignment, sprite)
            y += 1

    def _print_line(
        self, x: int, y: int, line: str,
        fg: Optional[Color], bg: Optional[Color], alignment: int, sprite: str = "",
    ) -> None:
        if alignment == events.CENTER:
            x -= len(line) // 2
        elif alignment == events.RIGHT:
            x -= len(line) - 1
        if not (0 <= y < self.height):
            return
        sid = sprites.sprite_id(sprite)
        for offset, ch in enumerate(line):
            cx = x + offset
            if 0 <= cx < self.width:
                cell = self._buf[cx, y]
                cell["ch"] = ord(ch)
                cell["sprite"] = sid
                if fg is not None:
                    cell["fg"] = fg
                if bg is not None:
                    cell["bg"] = bg

    def draw_rect(
        self, x: int, y: int, width: int, height: int, ch: int,
        fg: Optional[Color] = None, bg: Optional[Color] = None,
    ) -> None:
        """Fill a rectangle. ``ch=0`` leaves each cell's character intact
        (used to recolour a background without disturbing text)."""
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + width), min(self.height, y + height)
        if x1 <= x0 or y1 <= y0:
            return
        region = self._buf[x0:x1, y0:y1]
        if ch:
            region["ch"] = ch
            region["sprite"] = 0
        if fg is not None:
            region["fg"] = fg
        if bg is not None:
            region["bg"] = bg

    def draw_frame(
        self, x: int, y: int, width: int, height: int,
        title: str = "", clear: bool = True,
        fg: Optional[Color] = None, bg: Optional[Color] = None,
        decoration: str = _FRAME,
    ) -> None:
        """Draw a box border, optionally clearing the interior first."""
        if width < 2 or height < 2:
            return
        if clear:
            self.draw_rect(x, y, width, height, ord(" "), fg=fg, bg=bg)
        tl, t, tr, left, _mid, right, bl, b, br = decoration
        x2, y2 = x + width - 1, y + height - 1
        self._put(x, y, tl, fg, bg)
        self._put(x2, y, tr, fg, bg)
        self._put(x, y2, bl, fg, bg)
        self._put(x2, y2, br, fg, bg)
        for i in range(x + 1, x2):
            self._put(i, y, t, fg, bg)
            self._put(i, y2, b, fg, bg)
        for j in range(y + 1, y2):
            self._put(x, j, left, fg, bg)
            self._put(x2, j, right, fg, bg)
        if title:
            self.print(x + 1, y, title, fg=fg, bg=bg)

    def _put(
        self, x: int, y: int, ch: str,
        fg: Optional[Color], bg: Optional[Color],
    ) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            cell = self._buf[x, y]
            cell["ch"] = ord(ch)
            cell["sprite"] = 0
            if fg is not None:
                cell["fg"] = fg
            if bg is not None:
                cell["bg"] = bg


class Display:
    """The pygame window: builds the glyph cache, paints a Console to the
    screen, and translates pygame events into :mod:`lonelands.events`."""

    def __init__(self, title: str = config.WINDOW_TITLE):
        pygame.display.init()
        self.cell_w = config.TILE_WIDTH
        self.cell_h = config.TILE_HEIGHT
        self.win_w = config.SCREEN_WIDTH * self.cell_w
        self.win_h = config.SCREEN_HEIGHT * self.cell_h
        self.offset = (0, 0)
        self.screen = pygame.display.set_mode(
            (self.win_w, self.win_h), pygame.RESIZABLE
        )
        pygame.display.set_caption(title)
        self._load_glyphs()
        # The pixel-space UI layer for native menus (Phase 3); rebuilt on resize.
        self.ui = ui.UI(self.screen, self.win_w, self.win_h)

    # --- glyph cache -------------------------------------------------------
    def _load_glyphs(self) -> None:
        # The atlas owns the white per-codepoint surfaces (and caches them); the
        # display only caches the tinted copies keyed by foreground colour.
        self._atlas = fonts.GlyphAtlas(self.cell_w, self.cell_h)
        self._sprite_atlas = sprites.SpriteAtlas(self.cell_w, self.cell_h)
        self._tinted: Dict[Tuple[int, Color], Optional[pygame.Surface]] = {}
        self._sprite_tinted: Dict[Tuple[int, Color], Optional[pygame.Surface]] = {}

    def _base_surface(self, cp: int) -> Optional[pygame.Surface]:
        return self._atlas.base_surface(cp)

    def _glyph(self, cp: int, fg: Color, sid: int = 0) -> Optional[pygame.Surface]:
        """The tinted surface for a cell: its sprite (ADR 0016) when sprites
        are on and one resolves, else its ASCII glyph — the same per-cell
        fallback that keeps the bespoke-four (and anything else without a
        sprite key) drawn, never blank."""
        if sid and sprites.enabled():
            tinted = self._tinted_sprite(sid, fg)
            if tinted is not None:
                return tinted
        return self._tinted_glyph(cp, fg)

    def _tinted_glyph(self, cp: int, fg: Color) -> Optional[pygame.Surface]:
        key = (cp, fg)
        if key in self._tinted:
            return self._tinted[key]
        tinted = self._tint(self._base_surface(cp), fg)
        self._tinted[key] = tinted
        return tinted

    def _tinted_sprite(self, sid: int, fg: Color) -> Optional[pygame.Surface]:
        key = (sid, fg)
        if key in self._sprite_tinted:
            return self._sprite_tinted[key]
        tinted = self._tint(self._sprite_atlas.base_surface(sid), fg)
        self._sprite_tinted[key] = tinted
        return tinted

    def portrait_surface(self, entity: object) -> Optional[pygame.Surface]:
        """The entity's tinted portrait bust (see
        :meth:`lonelands.sprites.SpriteAtlas.portrait_surface`), or ``None``
        with no atlas on disk — headers using this should skip the portrait
        entirely rather than draw a placeholder box (issues #126, #127)."""
        return self._sprite_atlas.portrait_surface(entity)

    @staticmethod
    def _tint(base: Optional[pygame.Surface], fg: Color) -> Optional[pygame.Surface]:
        if base is None:
            return None
        tinted = base.copy()
        # White ink × fg == fg, preserving the coverage alpha.
        tinted.fill((*fg, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return tinted

    # --- painting ----------------------------------------------------------
    def present(self, console: Console) -> None:
        """Blit the console grid and flip. (Native overlays, when a handler has
        them, go between :meth:`blit_console` and :meth:`flip` — see main.py.)"""
        self.blit_console(console)
        self.flip()

    def flip(self) -> None:
        pygame.display.flip()

    def blit_console(self, console: Console) -> None:
        """Blit ``console``'s cell grid to the window (no flip).

        Backgrounds go down in a single upscaled-array blit, and glyphs in one
        batched ``blits`` call over only the inked cells — so there is no
        per-cell fill/blit loop over the whole grid (the spec's frame-time
        watch-item). We render only on input anyway, never in a busy loop."""
        buf = console.rgb
        cw, ch = self.cell_w, self.cell_h
        ox, oy = self.offset
        screen = self.screen
        screen.fill((0, 0, 0))  # letterbox margins outside the grid

        # Backgrounds: one cell-per-pixel surface from the (w, h, 3) colour
        # array, upscaled to the grid. ``transform.scale`` does not sample, so
        # at integer cell sizes it duplicates pixels (crisp, no blur) in C.
        cell_bg = pygame.surfarray.make_surface(np.ascontiguousarray(buf["bg"]))
        screen.blit(pygame.transform.scale(cell_bg, (cw * console.width, ch * console.height)), (ox, oy))

        # Glyphs: gather (surface, dest) for every non-blank cell, blit in one go.
        ch_a = buf["ch"]
        fg_a = buf["fg"]
        sprite_a = buf["sprite"]
        xs, ys = np.nonzero((ch_a != 0) & (ch_a != ord(" ")))
        sequence: List[Tuple[pygame.Surface, Tuple[int, int]]] = []
        for gx, gy in zip(xs.tolist(), ys.tolist()):
            glyph = self._glyph(int(ch_a[gx, gy]), tuple(fg_a[gx, gy]), int(sprite_a[gx, gy]))
            if glyph is not None:
                sequence.append((glyph, (ox + gx * cw, oy + gy * ch)))
        if sequence:
            screen.blits(sequence, doreturn=False)

    # --- window / resize ---------------------------------------------------
    def resize(self, win_w: int, win_h: int) -> None:
        """Fit the largest whole-pixel cell into the new window and recentre.

        Integer cell sizing replaces tcod's ``integer_scaling`` so glyphs stay
        crisp; leftover pixels become a black letterbox margin."""
        self.win_w, self.win_h = win_w, win_h
        self.screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
        cw = max(1, win_w // config.SCREEN_WIDTH)
        ch = max(1, win_h // config.SCREEN_HEIGHT)
        grid_w = cw * config.SCREEN_WIDTH
        grid_h = ch * config.SCREEN_HEIGHT
        self.offset = ((win_w - grid_w) // 2, (win_h - grid_h) // 2)
        if (cw, ch) != (self.cell_w, self.cell_h):
            self.cell_w, self.cell_h = cw, ch
            self._load_glyphs()
        # The new screen surface and window size need a fresh UI (fonts scale
        # to the window height).
        self.ui = ui.UI(self.screen, win_w, win_h)

    # --- event translation -------------------------------------------------
    def translate(self, event: "pygame.event.Event") -> "Optional[object]":
        """Map a pygame event to a :mod:`lonelands.events` event, or ``None`` to
        ignore it. Resize is handled by the caller (it drives :meth:`resize`)."""
        if event.type == pygame.QUIT:
            return events.Quit()
        if event.type == pygame.KEYDOWN:
            try:
                sym = events.KeySym(event.key)
            except ValueError:
                sym = None  # a key we don't bind (e.g. a media key)
            return events.KeyDown(sym=sym, mod=event.mod)
        if event.type == pygame.MOUSEMOTION:
            px, py = event.pos
            cx = (px - self.offset[0]) // self.cell_w
            cy = (py - self.offset[1]) // self.cell_h
            return events.MouseMotion(events.Point(int(cx), int(cy)))
        return None
