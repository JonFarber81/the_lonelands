"""Shared building blocks for the per-location story modules.

A dialog *node* is {"text": str|callable, "options": [option, ...]}.
An *option* is a dict with:
    text   : the line the player may choose
    goto   : next node id, or None to end the conversation
    show   : optional callable(engine)->bool gating visibility
    do     : optional callable(engine)->None side effect
    handler: optional callable(engine)->EventHandler to switch UI (e.g. a shop)
"""
from __future__ import annotations

from typing import Any, Dict

from lonelands.components.equipment import Equipment
from lonelands.components.inventory import Inventory
from lonelands.components.npc import NPC
from lonelands.entity import Actor


def opt(text, goto=None, do=None, show=None, handler=None) -> Dict[str, Any]:
    return {"text": text, "goto": goto, "do": do, "show": show, "handler": handler}


# --- NPC map glyphs (ADR-0009) ---------------------------------------------
# The one rule for how a friendly reads on the map. The *generated wandering
# crowd* is lettered by race so a roomful of folk parses at a glance; the player
# and every *hand-authored* NPC — questgiver, merchant, or fixed bystander alike
# — keep the roguelike '@', reserving that glyph for the folk you seek out by
# name. RACE_GLYPHS is the single source of truth: a new lettered NPC draws its
# glyph from here by race, and a new race adds exactly one entry. Glyphs are
# printable ASCII and never collide with the beast letters in content.py.
NPC_GLYPH = "@"  # player + hand-authored principals and fixed bystanders
RACE_GLYPHS: Dict[str, str] = {
    "man": "m",
    "hobbit": "h",
    "dwarf": "d",
}
# The sprite-key twin of RACE_GLYPHS (ADR 0016): the same wandering crowd,
# drawn as an Avatar-sheet silhouette tinted per-race instead of a letter.
# A new race adds exactly one entry to each dict.
RACE_SPRITES: Dict[str, str] = {
    "man": "race_man",
    "hobbit": "race_hobbit",
    "dwarf": "race_dwarf",
}

# The generic sprite every hand-authored NPC gets by default: a standing
# figure tinted to that NPC's own colour (portrait art is a deferred, later
# issue — ADR 0016). A bespoke prop (e.g. the signpost) overrides it with "".
NPC_SPRITE = "npc_standing"


def make_npc(char, col, name, title, tree, sprite=NPC_SPRITE) -> Actor:
    """A speaking, non-combatant Actor carrying a dialog `tree`."""
    return Actor(char=char, color=col, name=name, ai_cls=None, sprite=sprite,
                 inventory=Inventory(0), equipment=Equipment(),
                 npc=NPC(title=title, tree=tree))


# A wooden signpost: an examinable prop the player bumps to read (reuses the NPC
# dialog machinery — a single node of text and one line to step away).
SIGNPOST_COLOR = (0x9A, 0x7C, 0x54)


def make_signpost(name: str, text: str) -> Actor:
    """A readable wayfinding/flavor post standing on the map. `text` is shown
    when the player bumps it; the only option steps away. One of the four
    bespoke props (ADR 0016) — ASCII forever, its own sprite a follow-up issue."""
    tree = {"root": {"text": text, "options": [opt("(step away)", goto=None)]}}
    return make_npc("?", SIGNPOST_COLOR, name, "a weathered signpost", tree, sprite="")
