"""The native HUD (lonelands/hud.py): the sidebar + Chronicle render without
error, the panes tile the screen the map grid does not, and the message log
fits its pane."""
from __future__ import annotations

import os

import pygame
import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from lonelands import color, config, dice, display, hud, setup_game  # noqa: E402


@pytest.fixture(scope="module")
def env():
    try:
        disp = display.Display()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no display: {exc}")
    engine = setup_game.new_game()
    engine.update_fov()
    return disp, engine


def test_hud_renders_with_content(env):
    disp, engine = env
    for i in range(12):  # more lines than fit — exercises the scroll/clip path
        engine.message_log.add_message(f"Line {i}: the road runs on and on.", color.white)
    engine.last_roll = dice.RollResult(die=20, mod=2, tn=15, dice=[20], damage=8)
    hud.render(disp, engine)  # must not raise


def test_hud_renders_with_empty_log_and_no_roll(env):
    disp, _ = env
    fresh = setup_game.new_game()
    fresh.update_fov()
    hud.render(disp, fresh)  # no roll, quests, or messages yet


def test_sidebar_renders_with_a_portrait(env, monkeypatch):
    # No LONELANDS_TILES art on disk in CI, so fake the atlas hit (issue
    # #126) to exercise the portrait-present branch of the header.
    disp, engine = env
    surf = pygame.Surface((48, 48), pygame.SRCALPHA)
    monkeypatch.setattr(disp, "portrait_surface", lambda entity: surf)
    hud.render(disp, engine)  # must not raise


def test_hud_panes_tile_the_non_map_screen(env):
    disp, _ = env
    (sx, sy, sw, sh), (cx, cy, cw, ch) = hud._rects(disp)
    ox, oy = disp.offset
    map_w = config.MAP_WIDTH * disp.cell_w
    map_h = config.MAP_HEIGHT * disp.cell_h
    # Sidebar starts where the map ends horizontally and spans full height.
    assert sx == ox + map_w
    assert sh == config.SCREEN_HEIGHT * disp.cell_h
    # Chronicle sits below the map and spans the map's width.
    assert cy == oy + map_h
    assert cw == map_w
