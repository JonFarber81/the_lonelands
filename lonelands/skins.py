"""Vendored Kenney UI skin art (CC0) and a tiny 9-slice blitter.

The HUD panes are drawn natively (see :mod:`lonelands.hud` / :mod:`lonelands.ui`)
as flat dark-stone rects. This module adds the ornamental *frame* around them:
Kenney's "Fantasy UI Borders" — white line-art corners with a transparent centre,
so the frame tints to any palette colour via a multiply and overlays the existing
dark fill without touching the text drawn on top.

Deliberately small: load a PNG once, cut it into nine regions, and blit it to fill
any rect with the four corners kept crisp (scaled by a whole factor for weight)
and the four edges stretched. The centre is transparent, so we skip it entirely.

Assets live in ``assets/ui`` and are CC0 (Kenney Game Assets); see the README there.
"""
from __future__ import annotations

import functools
import os
from typing import Optional, Tuple

import pygame

Color = Tuple[int, int, int]

_UI = os.path.join(os.path.dirname(__file__), "assets", "ui")


@functools.lru_cache(maxsize=None)
def _sheet(name: str) -> "pygame.Surface":
    """The raw white-ink source surface for ``name`` (loaded once)."""
    return pygame.image.load(os.path.join(_UI, name)).convert_alpha()


@functools.lru_cache(maxsize=None)
def _tinted(name: str, tint: Optional[Color], alpha: int = 255) -> "pygame.Surface":
    """``name`` recoloured to ``tint`` and faded to ``alpha`` (white ink × tint ==
    tint; source coverage × alpha/255), cached per (colour, alpha). ``tint=None``
    with full ``alpha`` returns the untinted sheet."""
    base = _sheet(name)
    if tint is None and alpha == 255:
        return base
    surf = base.copy()
    surf.fill((*(tint or (255, 255, 255)), alpha), special_flags=pygame.BLEND_RGBA_MULT)
    return surf


class NineSlice:
    """A 9-slice frame cut from a square line-art tile.

    ``margin`` is the corner size in *source* pixels — the inset past which the
    edges are a uniform, stretchable strip (12 for Kenney's 48px border tile).
    """

    def __init__(self, name: str, margin: int):
        self.name = name
        self.margin = margin

    def draw(
        self,
        screen: "pygame.Surface",
        rect: "Tuple[int, int, int, int]",
        tint: Optional[Color] = None,
        scale: int = 2,
        alpha: int = 255,
        sides: str = "NESW",
    ) -> None:
        """Frame ``rect`` (x, y, w, h). Corners are drawn at ``margin*scale``
        screen pixels; edges stretch to fill the span between them.

        ``sides`` selects which of the North/East/South/West edges to draw — omit
        a side where the pane butts against a neighbour that already draws the
        seam (so abutting HUD panes don't double their shared border or collide
        corners). A corner is drawn only when *both* its sides are present; an
        edge whose end-corner is absent extends to the rect boundary instead."""
        src = _tinted(self.name, tint, alpha)
        m = self.margin
        sw, sh = src.get_size()
        x, y, w, h = rect
        c = min(m * scale, w // 2, h // 2)  # never overrun a small rect
        N, E, S, W = (d in sides for d in "NESW")

        def piece(sx: int, sy: int, spw: int, sph: int,
                  dx: int, dy: int, dw: int, dh: int) -> None:
            if spw <= 0 or sph <= 0 or dw <= 0 or dh <= 0:
                return
            sub = src.subsurface((sx, sy, spw, sph))
            if (spw, sph) != (dw, dh):
                sub = pygame.transform.scale(sub, (dw, dh))
            screen.blit(sub, (dx, dy))

        rx, by = x + w - c, y + h - c            # right/bottom corner origins
        sm = sw - m                              # source right/bottom inset
        # Corners — only where both adjacent sides are drawn.
        if N and W:
            piece(0, 0, m, m, x, y, c, c)
        if N and E:
            piece(sm, 0, m, m, rx, y, c, c)
        if S and W:
            piece(0, sm, m, m, x, by, c, c)
        if S and E:
            piece(sm, sm, m, m, rx, by, c, c)
        # Edges — extend to the boundary on any end whose corner is absent.
        hx0, hx1 = (x + c if W else x), (rx if E else x + w)
        vy0, vy1 = (y + c if N else y), (by if S else y + h)
        if N:
            piece(m, 0, sw - 2 * m, m, hx0, y, hx1 - hx0, c)
        if S:
            piece(m, sm, sw - 2 * m, m, hx0, by, hx1 - hx0, c)
        if W:
            piece(0, m, m, sh - 2 * m, x, vy0, c, vy1 - vy0)
        if E:
            piece(sm, m, m, sh - 2 * m, rx, vy0, c, vy1 - vy0)


# The frames we actually use. Kenney's border tile is 48×48 with a 12px corner.
FANTASY_BORDER = NineSlice("fantasy_border.png", margin=12)
