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
