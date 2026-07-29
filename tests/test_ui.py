"""lonelands/ui.py drawing primitives that need real coverage beyond eyeballing."""
from __future__ import annotations

import os

import pygame
import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from lonelands import ui  # noqa: E402


@pytest.fixture()
def screen():
    try:
        return pygame.display.set_mode((200, 200))
    except pygame.error as exc:
        pytest.skip(f"no pygame display available: {exc}")


def test_portrait_is_a_no_op_without_a_surface(screen):
    # No atlas on disk (LONELANDS_TILES unset) -> nothing to blit (ADR-0016).
    u = ui.UI(screen, 200, 200)
    u.portrait(0, 0, 48, 48, None)  # must not raise


def test_portrait_blits_the_surface_scaled_into_the_rect(screen):
    u = ui.UI(screen, 200, 200)
    src = pygame.Surface((48, 48), pygame.SRCALPHA)
    src.fill((255, 255, 255, 255))
    before = screen.get_at((10, 10))
    u.portrait(0, 0, 20, 20, src)
    assert screen.get_at((10, 10)) != before
