"""A small pixel-space UI layer for native menus and dialogs (issue #66 Phase 3).

The map view and HUD stay a cell grid (see :mod:`lonelands.display`), but menus,
dialogs, the sidebar prose and popups are drawn here as free-form pygame
surfaces with a proportional font — so they wrap and align in pixels instead of
snapping to cells, and read far better than the old character grid.

This is deliberately *not* a widget framework: :class:`UI` is a thin bundle of a
proportional font family (sized to the window) and a handful of drawing
primitives — panel, text, wrapped paragraph, section header, selection bar,
footer hint — bound to the pygame screen. Handlers call these from
``on_render_native``. :class:`lonelands.display.Display` owns one ``UI`` and
rebuilds it on resize so the fonts track the window size.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import pygame

from lonelands import color, skins

Color = Tuple[int, int, int]

# Two proportional faces, each a preference-ordered candidate list (SysFont
# falls back to pygame's bundled default if none are installed):
#   _SANS — the HUD chrome (sidebar stats, Chronicle log, menus): scanned, dense.
#   _PROSE — text that's *read* (NPC speech, quest descriptions): a humanist book
#            serif, warmer for Middle-earth and free of Avenir's restless 'u'.
_SANS = "Seravek,Helvetica Neue,Avenir Next,Segoe UI,DejaVu Sans,Arial"
_PROSE = "Iowan Old Style,Palatino,Georgia,DejaVu Serif,Times New Roman,serif"


def _font(size: int, bold: bool = False, face: str = _SANS) -> "pygame.font.Font":
    pygame.font.init()
    return pygame.font.SysFont(face, size, bold=bold)


class UI:
    """Fonts sized to the window plus drawing primitives bound to ``screen``."""

    def __init__(self, screen: "pygame.Surface", win_w: int, win_h: int):
        self.screen = screen
        self.w = win_w
        self.h = win_h
        base = max(15, win_h // 42)
        self.body = _font(base)
        self.bold = _font(base, bold=True)
        self.small = _font(max(12, int(base * 0.82)))
        self.head = _font(int(base * 1.02), bold=True)
        self.title = _font(int(base * 2.0), bold=True)
        self.subtitle = _font(int(base * 1.15))
        self.prose = _font(base, face=_PROSE)          # read text: NPC speech, quests
        self.prose_line = self.prose.get_linesize()
        self.pad = base                      # panel inner padding
        # The ornamental HUD frame (Kenney Fantasy UI Borders). Whole-pixel corner
        # scale tracks the window size; a dim gilt tint at partial alpha keeps the
        # frame reading as worked stone-edge, settled back rather than popping.
        self.frame_scale = max(2, base // 8)
        self.frame_tint = color.frame          # dim gilt, near the stone value
        self.frame_alpha = 200
        self.line = self.body.get_linesize()  # default row advance
        self._mono: dict = {}                # size -> monospace font (help page)
        self._prop: dict = {}                # size -> proportional font (dense lists)

    # --- measuring / wrapping ---------------------------------------------
    def measure(self, s: str, font=None) -> Tuple[int, int]:
        return (font or self.body).size(s)

    def wrap(self, s: str, max_w: int, font=None) -> List[str]:
        """Greedy word-wrap ``s`` to ``max_w`` pixels."""
        font = font or self.body
        lines: List[str] = []
        for para in s.split("\n"):
            cur = ""
            for word in para.split(" "):
                trial = f"{cur} {word}".strip()
                if not cur or font.size(trial)[0] <= max_w:
                    cur = trial
                else:
                    lines.append(cur)
                    cur = word
            lines.append(cur)
        return lines or [""]

    # --- text --------------------------------------------------------------
    def text(self, x: int, y: int, s: str, col: Color, font=None) -> int:
        font = font or self.body
        self.screen.blit(font.render(s, True, col), (x, y))
        return font.size(s)[0]

    def text_center(self, cx: int, y: int, s: str, col: Color, font=None) -> None:
        font = font or self.body
        self.text(cx - font.size(s)[0] // 2, y, s, col, font)

    def text_right(self, right: int, y: int, s: str, col: Color, font=None) -> None:
        font = font or self.body
        self.text(right - font.size(s)[0], y, s, col, font)

    def plate(self, x: int, y: int, s: str, fg: Color, font=None,
              bg: Color = (0x10, 0x0E, 0x0C), alpha: int = 200, pad: int = 5) -> int:
        """Draw ``s`` on a dim, rounded plate — a label legible over busy
        artwork (the overworld atlas Region names, laid over band-tinted
        terrain). Returns the text width."""
        font = font or self.small
        w, h = font.size(s)
        surf = pygame.Surface((w + 2 * pad, h + 2), pygame.SRCALPHA)
        pygame.draw.rect(surf, (*bg, alpha), surf.get_rect(), border_radius=4)
        self.screen.blit(surf, (x - pad, y - 1))
        self.text(x, y, s, fg, font)
        return w

    def truncate(self, s: str, max_w: int, font=None) -> str:
        """``s`` clipped with an ellipsis to fit ``max_w`` pixels."""
        font = font or self.body
        if font.size(s)[0] <= max_w:
            return s
        while s and font.size(s + "…")[0] > max_w:
            s = s[:-1]
        return s + "…"

    def paragraph(self, x: int, y: int, s: str, col: Color, max_w: int, font=None) -> int:
        """Draw wrapped prose; return the y just below the last line."""
        font = font or self.prose
        step = font.get_linesize()
        for line in self.wrap(s, max_w, font):
            self.text(x, y, line, col, font)
            y += step
        return y

    # --- chrome ------------------------------------------------------------
    def panel(self, x: int, y: int, w: int, h: int, title: Optional[str] = None) -> "pygame.Rect":
        """A translucent dark-stone panel wrapped in the Kenney "Fantasy UI
        Borders" gilt frame — the same ornament as the always-on HUD panes, so
        menus, the character sheet and dialogs read as one interface. Returns the
        inner content rect (padded); a ``title`` is drawn at its top and the rect
        advanced below it."""
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((*color.panel_bg, 240))
        self.screen.blit(surf, (x, y))
        skins.FANTASY_BORDER.draw(
            self.screen, (x, y, w, h), tint=self.frame_tint,
            scale=self.frame_scale, alpha=self.frame_alpha,
        )
        inner = pygame.Rect(x + self.pad, y + self.pad, w - 2 * self.pad, h - 2 * self.pad)
        if title:
            self.text(inner.x, inner.y, title, color.menu_title, self.head)
            drop = self.head.get_linesize() + self.pad // 2
            inner.y += drop
            inner.height -= drop
        return inner

    def centered(self, w: int, h: int) -> "pygame.Rect":
        """A ``w``×``h`` rect centred in the window."""
        return pygame.Rect((self.w - w) // 2, (self.h - h) // 2, w, h)

    def hud_panel(self, x: int, y: int, w: int, h: int,
                  sides: str = "NESW") -> "pygame.Rect":
        """A solid dark-stone panel docked to a screen edge (the HUD panes),
        wrapped in the vendored Kenney "Fantasy UI Borders" frame (issue #92
        follow-up). ``sides`` omits the border on any edge that butts a
        neighbouring pane, so abutting panes share one clean seam. Returns the
        padded inner content rect."""
        pygame.draw.rect(self.screen, color.panel_bg, (x, y, w, h))
        skins.FANTASY_BORDER.draw(
            self.screen, (x, y, w, h), tint=self.frame_tint,
            scale=self.frame_scale, alpha=self.frame_alpha, sides=sides,
        )
        p = self.pad
        return pygame.Rect(x + p, y + p // 2, w - 2 * p, h - p)

    def hud_seam(self, x: int, y: int, w: int, h: int, sides: str) -> None:
        """Draw only the ornamental frame edge(s) for ``sides`` over an existing
        pane (no fill), matching :meth:`hud_panel`. Used for the lone interior
        divider so the sidebar and Chronicle read as one L-shaped pane."""
        skins.FANTASY_BORDER.draw(
            self.screen, (x, y, w, h), tint=self.frame_tint,
            scale=self.frame_scale, alpha=self.frame_alpha, sides=sides,
        )

    def scrim(self, alpha: int = 165) -> None:
        """Dim the whole window (so an open panel reads as the top layer,
        CONTEXT.md 'Scrim'). Native replacement for the old console-grid dim."""
        s = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        s.fill((0, 0, 0, alpha))
        self.screen.blit(s, (0, 0))

    def bar(self, x: int, y: int, w: int, frac: float,
            fill: Color, empty: Color, label: str, value: str = "",
            label_col: Color = color.white) -> int:
        """A filled progress bar (Endurance, XP) with a label and optional
        right-aligned value. Returns the y below it."""
        h = int(self.line * 0.92)
        frac = max(0.0, min(1.0, frac))
        pygame.draw.rect(self.screen, empty, (x, y, w, h), border_radius=4)
        fw = int(w * frac)
        if fw > 0:
            pygame.draw.rect(self.screen, fill, (x, y, fw, h), border_radius=4)
        ty = y + (h - self.small.get_height()) // 2
        self.text(x + self.pad // 2, ty, label, label_col, self.small)
        if value:
            self.text_right(x + w - self.pad // 2, ty, value, label_col, self.small)
        return y + h

    def section(self, x: int, y: int, w: int, label: str) -> int:
        """A gold section header over a thin rule; returns the next free y."""
        self.text(x, y, label, color.section_head, self.bold)
        ry = y + self.bold.get_linesize()
        pygame.draw.line(self.screen, color.rule, (x, ry), (x + w, ry))
        return ry + max(4, self.pad // 3)

    def selection(self, x: int, y: int, w: int, h: int) -> None:
        """A translucent accent block behind the selected row."""
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((*color.bar_accent, 165))
        self.screen.blit(surf, (x, y))

    def hint(self, cx: int, y: int, s: str) -> None:
        """A dim, centred footer of key hints."""
        self.text_center(cx, y, s, color.tier_label, self.small)

    def tri_down(self, x: int, y: int, size: int, col: Color) -> int:
        """A small filled downward triangle — the atlas legend's ``deeps`` mark,
        which the proportional font has no glyph for (the map draws it from the
        tileset). Returns its width."""
        pygame.draw.polygon(self.screen, col,
                            [(x, y), (x + size, y), (x + size // 2, y + size)])
        return size

    def hrule(self, x: int, y: int, w: int) -> None:
        """A thin dim horizontal rule."""
        pygame.draw.line(self.screen, color.rule, (x, y), (x + w, y))

    def connector(self, x1: int, y1: int, x2: int, y2: int, col: Color, width: int = 1) -> None:
        """A straight line — the Path tree's prereq edges (ADR 0011)."""
        pygame.draw.line(self.screen, col, (x1, y1), (x2, y2), width)

    def outline(self, x: int, y: int, w: int, h: int, border: Color,
                fill: Optional[Tuple[int, ...]] = None, width: int = 2,
                radius: int = 8) -> None:
        """A rounded box — a Path-tree node's labelled card. ``fill`` may carry an
        alpha (RGBA) for a translucent interior; ``border`` is drawn opaque."""
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        if fill is not None:
            pygame.draw.rect(surf, fill, (0, 0, w, h), border_radius=radius)
        pygame.draw.rect(surf, border, (0, 0, w, h), width=width, border_radius=radius)
        self.screen.blit(surf, (x, y))

    def prop_fit(self, n_lines: int, max_h: int) -> "Tuple[pygame.font.Font, int]":
        """A proportional font (and its row step) sized so ``n_lines`` fit
        ``max_h`` pixels — for dense lists (the Paths screen) that must not spill
        the panel. Never larger than the body font."""
        step = max(1, max_h // max(1, n_lines))
        size = max(12, min(int(step / 1.25), self.body.get_height()))
        if size not in self._prop:
            self._prop[size] = _font(size)
        font = self._prop[size]
        return font, min(step, font.get_linesize() + 2)

    def mono_fit(self, n_lines: int, max_h: int) -> "pygame.font.Font":
        """The bundled monospace face, sized so ``n_lines`` fit ``max_h`` pixels.
        For preformatted, column-aligned prose (the help page) where a
        proportional font would misalign the columns. Falls back to pygame's
        default face only if the bundled monospace is somehow missing."""
        from lonelands import config
        target = max_h // max(1, n_lines)          # target line advance
        size = max(10, min(40, int(target / 1.2)))  # ~linesize/size for this face
        if size not in self._mono:
            self._mono[size] = pygame.font.Font(config.find_font(), size)
        return self._mono[size]
