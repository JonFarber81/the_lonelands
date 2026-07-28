"""The sprite spike (lonelands/sprites.py, issue #92, ADR-0013 Phase 0).

The rendering itself is validated by running Bree under ``--sprites`` (see the
ticket); these tests pin the parts that *can* be checked headlessly: that no
spike sprite key is orphaned, that Bree's terrain and folk each resolve to a key
the table knows, and that the flag defaults off so the ASCII path is untouched.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from lonelands import config, sprites, tile_types  # noqa: E402
from lonelands.story._helpers import RACE_GLYPHS  # noqa: E402

# The nine keys the spike promises (ticket #92).
SPIKE_KEYS = {
    "grass", "road", "stone", "wall", "door", "tree",
    "townsman", "orc", "ranger",
}


def test_table_covers_the_nine_spike_keys():
    assert SPIKE_KEYS <= set(sprites.SPRITE_KEYS)


def test_every_key_points_at_a_sheet_cell():
    for key, (sheet, col, row) in sprites.SPRITE_KEYS.items():
        assert sheet in sprites.SHEET_CANDIDATES, key
        assert col >= 0 and row >= 0, key


# --- terrain resolution: Bree's tiles each land on a known key -------------
BREE_TERRAIN = [
    (tile_types.grass, "grass"),
    (tile_types.grass_low, "grass"),
    (tile_types.hill, "grass"),
    (tile_types.tree, "tree"),
    (tile_types.road, "road"),
    (tile_types.bridge, "road"),
    (tile_types.cobble, "stone"),
    (tile_types.floor, "stone"),
    (tile_types.building_wall, "wall"),
    (tile_types.wall, "wall"),
    (tile_types.door, "door"),
]


@pytest.mark.parametrize("tile, expected", BREE_TERRAIN)
def test_terrain_resolves_to_expected_key(tile, expected):
    key = sprites.resolve_terrain(int(tile["kind"]), int(tile["light"]["ch"]))
    assert key == expected
    assert key in sprites.SPRITE_KEYS  # never orphaned


# --- entity resolution: the player, orcs, and the race-lettered crowd ------
def test_player_and_principals_resolve_to_ranger():
    assert sprites.resolve_entity("@") == "ranger"


def test_orc_letters_resolve_to_orc():
    assert sprites.resolve_entity("o") == "orc"
    assert sprites.resolve_entity("O") == "orc"


def test_every_race_glyph_resolves_to_a_known_key():
    for glyph in RACE_GLYPHS.values():
        key = sprites.resolve_entity(glyph)
        assert key in sprites.SPRITE_KEYS, glyph


def test_unmapped_char_falls_through():
    # Dropped items and creatures the spike doesn't cover draw nothing.
    assert sprites.resolve_entity("!") is None
    assert sprites.resolve_entity("*") is None


# --- the layered crowd: body + clothing + hair, mixed per wanderer ---------
def test_crowd_layers_only_for_the_race_lettered():
    assert sprites.crowd_layers("@", 1) is None   # the player
    assert sprites.crowd_layers("o", 1) is None   # orcs
    assert sprites.crowd_layers("!", 1) is None   # an item
    for glyph in RACE_GLYPHS.values():
        assert sprites.crowd_layers(glyph, 1) is not None


def test_crowd_layers_is_deterministic_per_seed():
    assert sprites.crowd_layers("m", 42) == sprites.crowd_layers("m", 42)


def test_crowd_layers_varies_across_the_crowd():
    stacks = {sprites.crowd_layers("m", s) for s in range(50)}
    assert len(stacks) > 5  # a street of men is not a row of clones


def test_crowd_stack_is_body_then_clothing_then_optional_hair():
    for s in range(30):
        stack = sprites.crowd_layers("m", s)
        assert stack[0] in sprites._BODIES          # body first
        assert stack[1] in sprites._CLOTHES         # clothing over it
        assert 2 <= len(stack) <= 3                 # hair is optional


def test_dwarves_are_bearded_and_hobbits_are_not():
    beards = set(sprites._HAIR_BEARD)
    for s in range(40):
        dwarf = sprites.crowd_layers("d", s)
        assert any(layer in beards for layer in dwarf[2:])
        hobbit = sprites.crowd_layers("h", s)
        assert all(layer not in beards for layer in hobbit[2:])


def test_every_crowd_layer_points_at_the_characters_sheet():
    pools = (sprites._BODIES, sprites._CLOTHES,
             sprites._HAIR_PLAIN, sprites._HAIR_BEARD)
    for pool in pools:
        for sheet, col, row in pool:
            assert sheet == "chars"
            assert col >= 0 and row >= 0


# --- the tone grade: darker, desaturated, earthier -------------------------
def _fresh_surface(rgb):
    import pygame

    pygame.display.init()
    pygame.display.set_mode((16, 16))
    surf = pygame.Surface((4, 4), pygame.SRCALPHA)
    surf.fill((*rgb, 255))
    return surf


def test_grade_identity_leaves_pixels_untouched():
    surf = _fresh_surface((100, 150, 200))
    old = dict(sprites.GRADE)
    sprites.GRADE = {"darken": 1.0, "desat": 0.0, "tint": (1, 1, 1)}
    try:
        sprites._grade(surf)
        assert tuple(surf.get_at((0, 0)))[:3] == (100, 150, 200)
    finally:
        sprites.GRADE = old


def test_grade_darkens_and_desaturates_bright_grass():
    surf = _fresh_surface((80, 200, 60))  # a bright, saturated green
    sprites._grade(surf)                   # the default earthy grade
    r, g, b = tuple(surf.get_at((0, 0)))[:3]
    assert g < 200                         # darker
    assert (g - r) < (200 - 80)            # desaturated: green less dominant
    assert (surf.get_at((0, 0)))[3] == 255  # alpha untouched


# --- the flag defaults off: the ASCII path is unchanged --------------------
def test_sprite_mode_defaults_off():
    assert config.SPRITES is False
    assert config.TILE_HEIGHT == 20  # non-square ASCII cell (main() squares it)


# --- with the sheets present, every key bakes a real tile ------------------
def _base_sheet_installed() -> bool:
    return any(os.path.exists(p) for p in sprites.SHEET_CANDIDATES["base"])


@pytest.mark.skipif(
    not _base_sheet_installed(),
    reason="Kenney sheets not installed (see assets/tiles/README.md)",
)
def test_all_keys_bake_a_tile_when_sheets_present():
    import pygame

    pygame.display.init()
    pygame.display.set_mode((64, 64))  # convert_alpha needs a display mode
    sm = sprites.SpriteMap(16)
    assert sm.ready
    for key in sprites.SPRITE_KEYS:
        assert sm._tile(key, dim=False) is not None, key
        assert sm._tile(key, dim=True) is not None, key
    # a mixed body+clothing+hair stack composites to a single surface
    assert sm._composite(sprites.crowd_layers("m", 3), dim=False) is not None
