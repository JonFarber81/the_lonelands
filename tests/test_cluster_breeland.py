"""Bree-land content pass: the hamlets of Combe & Staddle and the Forsaken Inn
on the once-blank cell (1,0), and Archet seated in the Chetwood (0,-1).

Covers the content wiring (authored surface, NPCs/signposts placed, quest item
with its pickup event), the new quests turning in through the existing
kill/event machinery, the "settled villages stay beast-free" rule, and — the
load-bearing one — that every new speaking NPC's dialog tree survives save/load
via story.all_speaking_npcs (not just the Bree town list).
"""
from __future__ import annotations

import pytest

from lonelands import (
    content, savegame, setup_game, story, world,
)
from lonelands.dice import set_seed
from lonelands.quests import QuestState


@pytest.fixture
def game():
    set_seed(1)
    engine = setup_game.new_game()
    return engine, engine.game_world, engine.player


def _surface(gw, coord):
    return gw.region(coord).level(0)


def _speakers(gm):
    return {e.name: e for e in gm.entities if getattr(e, "npc", None) is not None}


# --- the Bree-land cell (1,0) is now authored, with its hamlet-folk ----------

def test_breeland_cell_is_authored():
    assert (1, 0) in world._AUTHORED_SURFACES


def test_breeland_seats_combe_staddle_and_the_inn(game):
    _, gw, _ = game
    names = _speakers(_surface(gw, (1, 0)))
    for who in ("Todi Heathertoes", "Rollo Tunnelly", "Mat Ferny", "Thulin"):
        assert who in names, f"{who} missing from the Bree-land"
    # bystanders + signposts are placed too
    assert "Nib Sandheaver" in names and "Mattock Mugwort" in names
    assert "the Bree-land crossroads post" in names


def test_archet_seated_in_the_chetwood_with_its_quest_axe(game):
    _, gw, _ = game
    gm = _surface(gw, (0, -1))
    names = _speakers(gm)
    assert "Baldo the Woodwright" in names
    assert "the Archet path-post" in names
    axe = next((e for e in gm.entities if e.name == content.felling_axe.name), None)
    assert axe is not None, "the felling-axe quest item is not in the Chetwood"
    assert getattr(axe, "pickup_event", None) == "archet_axe"


# --- settled villages stay beast-free (danger roams the wild cells) ----------

def test_breeland_villages_have_no_wandering_beasts(game):
    _, gw, player = game
    gm = _surface(gw, (1, 0))
    hostiles = [a for a in gm.actors if a is not player and a.fighter is not None]
    assert hostiles == [], f"a beast wandered into the Bree-land: {hostiles}"


# --- every new speaking NPC's tree survives save/load ------------------------

def test_new_npc_names_are_unique_for_tree_rehydration():
    # savegame restores dialog trees by NAME; a collision would cross-wire trees.
    names = [n.name for n in story.all_speaking_npcs()]
    assert len(names) == len(set(names)), "duplicate NPC/signpost name breaks rehydration"


def test_breeland_dialog_survives_save_load(game, tmp_path):
    engine, gw, _ = game
    gw.cross_edge(1, 0)                       # travel east into the Bree-land
    assert gw.coord == (1, 0)
    path = tmp_path / "breeland.sav"
    savegame.save_game(engine, str(path))
    after = savegame.load_game(str(path))
    gm = after.game_world.current_region.level(0)
    for name, npc in _speakers(gm).items():
        assert npc.npc.tree, f"{name} lost its dialog tree across save/load"
        assert npc.npc.start in npc.npc.tree


# --- the new quests drive through the existing machinery ---------------------

def test_breeland_and_archet_quests_are_registered(game):
    engine, _, _ = game
    for qid in ("combe_spiders", "road_east", "archet_axe"):
        assert engine.quest_log.get(qid) is not None


def test_combe_spider_quest_completes_on_kills(game):
    engine, _, _ = game
    log = engine.quest_log
    log.start("combe_spiders")
    for _ in range(3):
        log.notify_kill("great spider", engine)
    assert log.is_ready("combe_spiders")
    assert log.turn_in("combe_spiders", engine)
    assert log.get("combe_spiders").state == QuestState.DONE


def test_archet_axe_quest_completes_on_pickup_event(game):
    engine, _, _ = game
    log = engine.quest_log
    log.start("archet_axe")
    log.notify_event("archet_axe", engine)
    assert log.is_ready("archet_axe")
    before = len(engine.player.inventory.items)
    assert log.turn_in("archet_axe", engine)
    # on_complete presses a reward draught into the pack
    assert len(engine.player.inventory.items) == before + 1
