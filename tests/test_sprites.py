"""Sprite keys and the Oryx atlas (lonelands/sprites.py, ADR-0016).

Two concerns:
  * Parity — every drawable in content.py, tile_types.py, and the RACE_*
    dicts carries a sprite key that resolves in the registry, except the
    bespoke-four (which keep ASCII forever, by design).
  * The atlas itself — sheet loading, native-size detection, and per-key
    slicing. These need real Oryx art on disk (LONELANDS_TILES) and are
    skipped without it, exactly like the ASCII-toggle's auto-detect."""
from __future__ import annotations

import os

import pygame
import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from lonelands import config, content, sprites, tile_types  # noqa: E402
from lonelands.entity import Actor, Item  # noqa: E402
from lonelands.story._helpers import RACE_GLYPHS, RACE_SPRITES, make_npc, make_signpost  # noqa: E402

_TERRAIN_TILES = [
    "floor", "wall", "rubble", "down_stairs", "up_stairs", "door",
    "grass", "grass_low", "tree", "water", "road", "bridge", "hill",
    "cobble", "building_wall", "ruin_entrance",
]


def _content_drawables():
    """Every module-level Item/Actor template content.py defines."""
    return [
        v for v in vars(content).values() if isinstance(v, (Item, Actor))
    ]


# --- Parity: content.py --------------------------------------------------
def test_every_content_drawable_has_a_registered_sprite_key():
    missing = [d.name for d in _content_drawables() if not d.sprite]
    assert not missing, f"no sprite key: {missing}"
    unregistered = [d.name for d in _content_drawables() if d.sprite not in sprites.SPRITE_KEYS]
    assert not unregistered, f"sprite key not in registry: {unregistered}"


def test_player_is_the_hooded_ranger_key():
    assert content.make_player().sprite == "player"


def test_uniques_covered():
    for item in content.UNIQUES:
        assert item.sprite in sprites.SPRITE_KEYS


# --- Parity: terrain --------------------------------------------------------
def test_every_terrain_tile_has_a_registered_sprite_key():
    for name in _TERRAIN_TILES:
        tile = getattr(tile_types, name)
        sid = int(tile["light"]["sprite"])
        assert sid != 0, f"{name} has no sprite id"
        key = sprites.key_for_id(sid)
        assert key in sprites.SPRITE_KEYS, f"{name} -> {key!r} not registered"
        # dark/light share the same tile art (ADR-0016): only the tint differs.
        assert int(tile["dark"]["sprite"]) == sid


def test_shroud_has_no_sprite():
    assert int(tile_types.SHROUD["sprite"]) == 0


# --- Parity: RACE_SPRITES (ADR-0009 + ADR-0016) -----------------------------
def test_race_sprites_mirrors_race_glyphs():
    assert set(RACE_SPRITES) == set(RACE_GLYPHS)
    for key in RACE_SPRITES.values():
        assert key in sprites.SPRITE_KEYS


# --- Parity: NPC machinery ---------------------------------------------------
def test_authored_npc_defaults_to_the_standing_silhouette():
    npc = make_npc("@", (255, 255, 255), "Test", "a tester", {"root": {"text": "hi", "options": []}})
    assert npc.sprite == "npc_standing"
    assert npc.sprite in sprites.SPRITE_KEYS


def test_signpost_is_bespoke_ascii_only():
    # One of the four bespoke props (ADR-0016): no sprite key, ASCII forever.
    post = make_signpost("A signpost", "Bree, 3 miles.")
    assert post.sprite == ""


def test_hobbit_door_is_bespoke_ascii_only():
    assert int(tile_types.hobbit_door["light"]["sprite"]) == 0
    assert int(tile_types.hobbit_door["dark"]["sprite"]) == 0


def test_pony_archway_is_bespoke_ascii_only():
    assert int(tile_types.pony_archway["light"]["sprite"]) == 0
    assert int(tile_types.pony_archway["dark"]["sprite"]) == 0


def test_barrow_mound_is_bespoke_ascii_only():
    assert int(tile_types.barrow_mound["light"]["sprite"]) == 0
    assert int(tile_types.barrow_mound["dark"]["sprite"]) == 0


def test_bespoke_door_variants_keep_door_semantics():
    # kind=KIND_DOOR is unchanged, so "is this a door" game logic still holds.
    assert tile_types.hobbit_door["kind"] == tile_types.KIND_DOOR
    assert tile_types.pony_archway["kind"] == tile_types.KIND_DOOR


def test_barrow_mound_keeps_ruin_entrance_semantics():
    assert tile_types.barrow_mound["kind"] == tile_types.KIND_RUIN_ENTRANCE


# --- sprite_id allocation ----------------------------------------------------
def test_sprite_id_empty_key_is_zero():
    assert sprites.sprite_id("") == 0


def test_sprite_id_is_stable_and_round_trips():
    sid = sprites.sprite_id("floor")
    assert sprites.sprite_id("floor") == sid
    assert sprites.key_for_id(sid) == "floor"


def test_sprite_id_distinct_keys_get_distinct_ids():
    assert sprites.sprite_id("wolf") != sprites.sprite_id("warg")


# --- The atlas: needs real Oryx art on disk ----------------------------------
requires_tiles = pytest.mark.skipif(
    not sprites.available(), reason="LONELANDS_TILES not set to a real Oryx sheet directory"
)


@pytest.fixture(scope="module")
def sprite_atlas():
    # convert_alpha() needs a real video mode, not just pygame.display.init().
    try:
        pygame.display.set_mode((1, 1))
    except pygame.error as exc:
        pytest.skip(f"no pygame display available: {exc}")
    return sprites.SpriteAtlas(config.TILE_WIDTH, config.TILE_HEIGHT)


@requires_tiles
def test_sprite_atlas_bakes_a_registered_key_at_cell_size(sprite_atlas):
    sid = sprites.sprite_id("floor")
    surf = sprite_atlas.base_surface(sid)
    assert surf is not None
    assert surf.get_size() == (config.TILE_WIDTH, config.TILE_HEIGHT)


@requires_tiles
def test_sprite_atlas_returns_none_for_unset_sprite_id(sprite_atlas):
    assert sprite_atlas.base_surface(0) is None


def test_available_is_false_without_a_tiles_path(monkeypatch):
    monkeypatch.delenv("LONELANDS_TILES", raising=False)
    assert sprites.available() is False


def test_enabled_respects_the_ascii_toggle(monkeypatch):
    monkeypatch.setattr(sprites, "available", lambda: True)
    config.ASCII_ONLY = True
    try:
        assert sprites.enabled() is False
    finally:
        config.ASCII_ONLY = False
    assert sprites.enabled() is True


# --- Portraits (ADR-0016 follow-up; issue #125) -------------------------
def test_portrait_ref_defaults_to_the_shared_bust():
    entity = Actor(name="No Portrait")
    assert sprites.portrait_ref(entity) == sprites.DEFAULT_PORTRAIT


def test_portrait_ref_prefers_the_entity_s_own_cell():
    own = sprites.SpriteRef("Portraits", 0, 2)
    entity = Actor(name="Has Portrait", portrait=own)
    assert sprites.portrait_ref(entity) == own


@requires_tiles
def test_sprite_atlas_bakes_the_default_portrait(sprite_atlas):
    surf = sprite_atlas.portrait_surface(Actor(name="No Portrait"))
    assert surf is not None
    assert surf.get_size() == (48, 48)


@requires_tiles
def test_sprite_atlas_returns_none_for_a_portrait_cell_out_of_bounds(sprite_atlas):
    entity = Actor(name="Bad Portrait", portrait=sprites.SpriteRef("Portraits", 99, 99))
    assert sprite_atlas.portrait_surface(entity) is None


def test_portrait_surface_is_none_without_a_tiles_path(monkeypatch):
    monkeypatch.delenv("LONELANDS_TILES", raising=False)
    atlas = sprites.SpriteAtlas(config.TILE_WIDTH, config.TILE_HEIGHT)
    assert atlas.portrait_surface(Actor(name="No Art")) is None
