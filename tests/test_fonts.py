"""The pygame glyph atlas (lonelands/fonts.py): prose, map tiles, and dice faces
baked to surfaces, keyed by the same codepoints the renderers print."""
from __future__ import annotations

import os

import pygame
import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from lonelands import config, dice_glyphs, fonts, tile_glyphs  # noqa: E402


@pytest.fixture(scope="module")
def atlas():
    pygame.display.init()
    return fonts.GlyphAtlas(config.TILE_WIDTH, config.TILE_HEIGHT)


def test_prose_glyph_renders_at_cell_size(atlas):
    surf = atlas.base_surface(ord("A"))
    assert surf is not None
    assert surf.get_size() == (config.TILE_WIDTH, config.TILE_HEIGHT)


def test_middle_earth_accents_and_marks_render(atlas):
    # Names like Dúnedain and the prose em-dash must not fall back to tofu.
    for ch in "úÚâîñ—…“”":
        assert atlas.base_surface(ord(ch)) is not None, ch


def test_box_drawing_is_blank(atlas):
    # The bundled font lacks box-drawing glyphs; SDL_ttf would draw a .notdef
    # tofu, so the atlas must blank them to keep draw_frame borders invisible
    # (as they were under tcod). Regression guard for the .notdef detector.
    for cp in (0x2500, 0x2502, 0x250C, 0x2510, 0x2514, 0x2518):
        assert atlas.base_surface(cp) is None, hex(cp)


def test_map_glyph_is_inked(atlas):
    # With the tilesheet installed this is a CP437 tile; without it, the prose
    # glyph for the same char. Either way, a wall/floor/player must show ink.
    for ch in "@#.":
        surf = atlas.base_surface(tile_glyphs.graphic_cp(ch))
        assert surf is not None, ch
        assert surf.get_size() == (config.TILE_WIDTH, config.TILE_HEIGHT)


def test_every_die_face_bakes_with_ink(atlas):
    def inked(codepoints):
        return any(atlas.base_surface(cp) is not None for cp in codepoints)

    for v in dice_glyphs.SUCCESS_VALUES:
        assert inked(dice_glyphs.success_codepoints(v)), f"success {v}"
    for v in dice_glyphs.FEAT_VALUES:
        assert inked(dice_glyphs.feat_codepoints(v)), f"feat {v}"


def test_special_die_faces_present(atlas):
    # 6 = tengwar rune, 11 = Eye of Sauron, 12 = Gandalf rune.
    assert any(atlas.base_surface(cp) for cp in dice_glyphs.success_codepoints(6))
    assert any(atlas.base_surface(cp) for cp in dice_glyphs.feat_codepoints(11))
    assert any(atlas.base_surface(cp) for cp in dice_glyphs.feat_codepoints(12))


def test_resize_rerasterises_at_new_cell_size():
    big = fonts.GlyphAtlas(config.TILE_WIDTH * 2, config.TILE_HEIGHT * 2)
    surf = big.base_surface(ord("A"))
    assert surf.get_size() == (config.TILE_WIDTH * 2, config.TILE_HEIGHT * 2)
