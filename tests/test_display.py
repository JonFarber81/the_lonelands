"""The render shim (lonelands/display.py): the Console surface renderers draw
through, plus a headless check of the pygame glyph cache and event translation."""
from __future__ import annotations

import os

import numpy as np
import pygame
import pytest

# Render to an off-screen buffer so these run without a real display.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from lonelands import config, display, events  # noqa: E402
from lonelands.display import Console  # noqa: E402


# --- Console: the surface the renderers use --------------------------------
def test_clear_fills_space_white_on_black():
    c = Console(4, 3)
    assert (c.rgb["ch"] == ord(" ")).all()
    assert (c.rgb["bg"] == 0).all()
    assert (c.rgb["fg"] == 255).all()


def test_print_writes_chars_and_keeps_bg_when_none():
    c = Console(10, 2)
    c.print(1, 0, "Hi", fg=(10, 20, 30))
    assert int(c.rgb["ch"][1, 0]) == ord("H")
    assert int(c.rgb["ch"][2, 0]) == ord("i")
    assert tuple(c.rgb["fg"][1, 0]) == (10, 20, 30)
    assert tuple(c.rgb["bg"][1, 0]) == (0, 0, 0)  # bg untouched


def test_print_center_alignment():
    c = Console(20, 1)
    c.print(10, 0, "abc", fg=(1, 2, 3), alignment=events.CENTER)
    assert int(c.rgb["ch"][9, 0]) == ord("a")  # 10 - len//2 = 9


def test_print_clips_out_of_bounds():
    c = Console(3, 1)
    c.print(-1, 0, "abcd", fg=(1, 1, 1))  # must not raise
    c.print(0, 5, "x", fg=(1, 1, 1))
    assert int(c.rgb["ch"][0, 0]) == ord("b")


def test_draw_rect_ch_zero_keeps_character():
    c = Console(5, 2)
    c.print(0, 0, "ABCDE", fg=(1, 1, 1))
    c.draw_rect(0, 0, 5, 1, 0, bg=(9, 9, 9))
    assert int(c.rgb["ch"][2, 0]) == ord("C")  # text preserved
    assert tuple(c.rgb["bg"][2, 0]) == (9, 9, 9)


def test_draw_frame_clears_interior_bg():
    c = Console(6, 6)
    c.draw_frame(0, 0, 6, 6, clear=True, fg=(1, 1, 1), bg=(4, 5, 6))
    assert tuple(c.rgb["bg"][3, 3]) == (4, 5, 6)


def test_rgb_slice_assignment_like_game_map():
    # game_map writes np.select(...) of graphic_dt straight into console.rgb.
    from lonelands.tile_types import graphic_dt
    c = Console(8, 8)
    patch = np.zeros((5, 5), dtype=graphic_dt, order="F")
    patch["ch"] = ord("#")
    patch["fg"] = (200, 100, 50)
    c.rgb[0:5, 0:5] = patch
    assert int(c.rgb["ch"][0, 0]) == ord("#")
    assert tuple(c.rgb["fg"][0, 0]) == (200, 100, 50)


def test_rgb_inplace_dim():
    c = Console(3, 3)
    c.rgb["fg"] = (200, 100, 40)
    c.rgb["fg"] //= 4
    assert tuple(c.rgb["fg"][0, 0]) == (50, 25, 10)


# --- Display: window, glyph cache, event translation -----------------------
@pytest.fixture(scope="module")
def disp():
    try:
        d = display.Display()
    except pygame.error as exc:  # no video subsystem at all
        pytest.skip(f"no pygame display available: {exc}")
    yield d
    pygame.display.quit()


def test_present_paints_without_error(disp):
    c = Console(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
    c.print(1, 1, "@", fg=(255, 0, 0))
    disp.present(c)  # exercises the full per-cell blit loop


def test_glyph_tinting_and_blank_glyph(disp):
    g = disp._glyph(ord("@"), (255, 0, 0))
    assert g is not None and g.get_size() == (disp.cell_w, disp.cell_h)
    # Box-drawing glyphs are blank in the bundled font -> no surface.
    assert disp._base_surface(0x2500) is None


def test_resize_keeps_whole_cells_and_centres(disp):
    disp.resize(1000, 800)
    assert disp.cell_w == 1000 // config.SCREEN_WIDTH
    assert disp.cell_h == 800 // config.SCREEN_HEIGHT
    grid_w = disp.cell_w * config.SCREEN_WIDTH
    assert disp.offset[0] == (1000 - grid_w) // 2


def test_translate_keydown_to_keysym(disp):
    ev = disp.translate(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP, mod=0))
    assert ev.sym == events.KeySym.UP
    # An unbound key becomes sym=None rather than raising.
    ev2 = disp.translate(pygame.event.Event(pygame.KEYDOWN, key=1_000_000_000, mod=0))
    assert ev2.sym is None


def test_translate_mousemotion_to_cell(disp):
    disp.resize(config.SCREEN_WIDTH * config.TILE_WIDTH,
                config.SCREEN_HEIGHT * config.TILE_HEIGHT)
    ox, oy = disp.offset
    ev = disp.translate(pygame.event.Event(
        pygame.MOUSEMOTION,
        pos=(ox + 3 * disp.cell_w + 1, oy + 4 * disp.cell_h + 1), rel=(0, 0), buttons=(0, 0, 0),
    ))
    assert (ev.tile.x, ev.tile.y) == (3, 4)


def test_translate_quit(disp):
    assert isinstance(disp.translate(pygame.event.Event(pygame.QUIT)), events.Quit)
