"""The scrolling viewport (issue: map zoom).

A region is generated larger than the on-screen viewport (``REGION_*`` vs the
viewport ``MAP_*`` in :mod:`lonelands.config`), so the map scrolls to keep the
player near centre and tiles can be drawn larger. A :class:`Camera` is simply
the top-left *world* tile currently shown; it converts between **world** tiles
(what game logic and the map arrays use) and **view** cells (what the renderers
draw into the console / blit as sprites).

The engine recomputes the camera each frame from the player's position (see
:meth:`lonelands.engine.Engine.render`) and stores it on ``engine.camera`` so
the map renderer, the sprite overlay, and the targeting reticles all share one
consistent scroll offset.
"""
from __future__ import annotations

from typing import Tuple

from lonelands import config


def _clamp_top(top: int, map_size: int, view_size: int) -> int:
    """Left/top edge of the view, kept inside ``[0, map_size - view_size]`` so
    the viewport never scrolls past the region. If the region is no larger than
    the viewport it simply pins to 0 (the whole thing fits, letterboxed)."""
    if map_size <= view_size:
        return 0
    return max(0, min(top, map_size - view_size))


class Camera:
    """The top-left world tile shown in the viewport."""

    __slots__ = ("x", "y")

    def __init__(self, x: int = 0, y: int = 0):
        self.x = x
        self.y = y

    @classmethod
    def centered(
        cls,
        px: int,
        py: int,
        map_w: int,
        map_h: int,
        view_w: int = config.MAP_WIDTH,
        view_h: int = config.MAP_HEIGHT,
    ) -> "Camera":
        """A camera centred on world tile ``(px, py)`` and clamped to the map."""
        return cls(
            _clamp_top(px - view_w // 2, map_w, view_w),
            _clamp_top(py - view_h // 2, map_h, view_h),
        )

    def world_to_view(self, wx: int, wy: int) -> Tuple[int, int]:
        return wx - self.x, wy - self.y

    def view_to_world(self, vx: int, vy: int) -> Tuple[int, int]:
        return vx + self.x, vy + self.y

    def in_view(self, wx: int, wy: int) -> bool:
        """True if world tile ``(wx, wy)`` currently falls inside the viewport."""
        vx, vy = wx - self.x, wy - self.y
        return 0 <= vx < config.MAP_WIDTH and 0 <= vy < config.MAP_HEIGHT
