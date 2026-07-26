"""Assemble a fresh game: the Ranger, their gear, the world, and the opening
tidings."""
from __future__ import annotations

import copy

from lonelands import color, content, story
from lonelands.engine import Engine
from lonelands.world import GameWorld


def _grant(player, template, equip: bool = False):
    item = copy.deepcopy(template)
    item.parent = player.inventory
    player.inventory.items.append(item)
    if equip:
        player.equipment.toggle_equip(item, add_message=False)
    return item


def new_game() -> Engine:
    player = content.make_player()
    engine = Engine(player)
    engine.game_world = GameWorld(engine)

    story.build_quests(engine)
    engine.game_world.new_game()

    # Starting gear of a Ranger walking alone.
    _grant(player, content.short_sword, equip=True)
    _grant(player, content.leather_gear, equip=True)
    _grant(player, content.shortbow, equip=True)  # a bow in the ranged slot (ADR 0006)
    quiver = _grant(player, content.arrows)        # a small starting quiver
    quiver.quantity = 20
    _grant(player, content.hunting_dagger)
    _grant(player, content.healing_herbs)
    _grant(player, content.healing_herbs)
    _grant(player, content.lembas)

    engine.message_log.add_message(
        "You are Tarandir, a Ranger of the North — though in Bree they know you "
        "only as Greycloak.",
        color.welcome_text,
    )
    engine.message_log.add_message(
        "The year is 2965 of the Third Age. You come to Bree, at the meeting of "
        "the Great East Road and the Greenway.",
        color.welcome_text,
    )
    engine.message_log.add_message(
        "Speak with the folk here (walk into them). Walk off an edge to travel "
        "to the next land; the barrow lies east, in the Weather Hills. Press ? "
        "for the lore of the wayfarer.",
        color.welcome_text,
    )
    return engine
