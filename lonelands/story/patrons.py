"""Wandering Bystanders — the Prancing Pony's hubbub (CONTEXT.md).

A *patron* is a generated speaking NPC: a random **kind** (Bree-man, Bree-hobbit,
dwarf of the Blue Mountains, road-worn traveller), a random name, one static line
of colour (and, now and then, a rumour), and the peaceful `IdleWanderer` AI that
drifts it about. Unlike the hand-authored, stationary NPCs, patrons are minted
fresh when Bree is built and have no authored twin to rehydrate from — so their
single-node, lambda-free dialog tree is flagged `keep_tree` and pickled as-is.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from lonelands.components.ai import IdleWanderer
from lonelands.components.equipment import Equipment
from lonelands.components.inventory import Inventory
from lonelands.components.npc import NPC
from lonelands.dice import rng
from lonelands.entity import Actor
from lonelands.story._helpers import RACE_GLYPHS, opt


# One rumour in four, roughly: mostly the patrons are pure colour, and only
# now and then does one let slip something of the wider dark (as chosen when
# the crowd is minted — a patron keeps its one line and may wander off with it).
_RUMOUR_CHANCE = 0.28

# Rumours leak across every kind: the barrow-chill west, the bold wolves, the
# roads, far news. Deliberately vague — the fixed NPCs carry the real hooks.
_RUMOURS: List[str] = [
    "\"Green mounds west of here,\" the voice drops, \"and folk that walk in "
    "after dark don't walk out. Barrow-wights, my gaffer called them.\"",
    "\"Wolves off the hills, bolder than any winter I mind. Something's got "
    "them stirred, and it isn't hunger.\"",
    "\"Rangers about again — grey folk, quiet folk. When they gather, trouble's "
    "not far behind, mark me.\"",
    "\"There's a cold crept into the old downs. The dogs won't go near, and the "
    "dogs are wiser than most here.\"",
    "\"Fewer travellers on the East Road this year, and those that come look "
    "back over their shoulders.\"",
]


# Each kind: a `race` (its map glyph comes from RACE_GLYPHS — ADR-0009, so the
# wandering crowd reads by race at a glance), a colour, a dialog title, a name
# pool, and a colour-line pool.
Kind = Dict[str, Any]

_KINDS: List[Kind] = [
    {
        "title": "a Bree-man",
        "race": "man",
        "color": (0xC0, 0x9A, 0x6E),
        "names": ["Rowlie Appledore", "Tom Mugwort", "Harry Heathertoes",
                  "Matt Thistlewool", "Sam Butcher", "Will Chubb"],
        "lines": [
            "A Bree-man tips his mug your way and says nothing much at all.",
            "\"Best beer this side of the Brandywine,\" he allows, \"and the "
            "worst singing. You'll hear both tonight.\"",
            "He grumbles companionably about the weather and the roads and the "
            "price of a pint.",
            "\"New face, eh? We don't get many, and we watch the ones we do.\"",
        ],
    },
    {
        "title": "a Bree-hobbit",
        "race": "hobbit",
        "color": (0xB8, 0x8A, 0x50),
        "names": ["Nob Thistlewool", "Old Noakes", "Mat Heathertoes",
                  "Rufus Banks", "Perry Mugwort"],
        "lines": [
            "A stout hobbit peers up at you over the rim of a very large mug.",
            "\"Second supper's the best supper,\" the hobbit confides, \"though "
            "the fourth has its admirers.\"",
            "The hobbit is telling a long tale to no one in particular and does "
            "not pause for you.",
            "\"You're a tall one. Mind your elbows and my ale, in that order.\"",
        ],
    },
    {
        "title": "a dwarf of the Blue Mountains",
        "race": "dwarf",
        "color": (0x9A, 0x9E, 0xA6),
        "names": ["Nár", "Flói", "Grár", "Thrin", "Dwalin son of Fundin"],
        "lines": [
            "A broad dwarf nurses his drink and eyes the door out of old habit.",
            "\"Slow roads and slower tolls,\" the dwarf mutters into his beard. "
            "\"A poor season for honest carriage.\"",
            "The dwarf says little; his glance takes the measure of your gear "
            "and finds it passable.",
            "\"Ered Luin to the Iron Hills and back, and the Pony's the one bed "
            "worth the coin between.\"",
        ],
    },
    {
        # A hooded wayfarer of no stated kind, but a Man for all that walks the
        # East Road — so he takes the Man's glyph.
        "title": "a road-worn traveller",
        "race": "man",
        "color": (0x86, 0x94, 0x74),
        "names": ["A traveller", "A hooded wayfarer", "A weathered stranger"],
        "lines": [
            "A traveller warms cold hands at the fire and keeps their own counsel.",
            "\"A dry corner and a full mug. A body asks no more of a night like "
            "this,\" the stranger says.",
            "The wayfarer watches the room from the shadow of a hood and says "
            "nothing.",
            "\"I've come a long way, and I'll go further. That's all the road "
            "there is.\"",
        ],
    },
]


def _make_patron(kind: Kind) -> Actor:
    name = rng.choice(kind["names"])
    if rng.random() < _RUMOUR_CHANCE:
        line = rng.choice(_RUMOURS)
    else:
        line = rng.choice(kind["lines"])
    tree = {"root": {"text": line, "options": [opt("(turn back to the room)")]}}
    return Actor(
        char=RACE_GLYPHS[kind["race"]], color=kind["color"], name=name,
        ai_cls=IdleWanderer,
        inventory=Inventory(0), equipment=Equipment(),
        npc=NPC(title=kind["title"], tree=tree, keep_tree=True),
    )


def make_patrons(count: int) -> List[Actor]:
    """A crowd of `count` wandering Bystanders, kinds drawn at random. Hobbits
    and Bree-men are the common folk of the room; a dwarf or a lone traveller
    turns up rarer."""
    weights = [4, 4, 2, 2]  # Bree-man, hobbit, dwarf, traveller
    return [_make_patron(rng.choices(_KINDS, weights=weights, k=1)[0])
            for _ in range(count)]
