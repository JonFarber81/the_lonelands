"""Narrative content — quests, speaking characters, and dialog trees — split by
location, one module per place (mirroring procgen's one-generator-per-region).

Each location module exposes two aggregate seams:
  * ``build_quests(engine)`` — register that place's quests, and
  * ``make_npcs()`` — fresh copies of its speaking NPCs (dialog trees attached).

``build_quests`` and ``all_speaking_npcs`` below fan across every module in
``_LOCATIONS``, so adding a new place is a one-line edit here and both the
quest-registration and savegame tree-rehydration paths pick it up automatically.

A dialog *node*/*option* schema and the ``opt``/``make_npc`` helpers live in
``story/_helpers.py``.
"""
from __future__ import annotations

from typing import List

from lonelands.entity import Actor
from lonelands.story import breeland, bree, chetwood
from lonelands.story.bree import (  # re-exported for callers (procgen, tests)
    make_elder,
    make_fletcher,
    make_halbarad,
    make_healer,
    make_innkeeper,
    make_town_npcs,
)

# Every location that contributes quests and/or speaking NPCs. Append new
# location modules here as content lands — both build_quests and
# all_speaking_npcs fan across this list, so registration and savegame
# tree-rehydration pick up a new place from this one edit.
_LOCATIONS = [bree, breeland, chetwood]


def build_quests(engine) -> None:
    """Register every location's quests into ``engine.quest_log``."""
    for loc in _LOCATIONS:
        loc.build_quests(engine)


def all_speaking_npcs() -> List[Actor]:
    """Fresh copies of every speaking NPC across all locations. Savegame uses
    these to restore dialog trees by name on load, so it must span every place
    the player might have a saved conversation in — not just Bree."""
    npcs: List[Actor] = []
    for loc in _LOCATIONS:
        npcs.extend(loc.make_npcs())
    return npcs


__all__ = [
    "build_quests",
    "all_speaking_npcs",
    "make_town_npcs",
    "make_elder",
    "make_healer",
    "make_halbarad",
    "make_innkeeper",
    "make_fletcher",
]
