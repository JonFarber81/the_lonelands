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
    _grant(player, content.ranger_bow, equip=True)
    _grant(player, content.hunting_dagger)
    _grant(player, content.healing_herbs)
    _grant(player, content.healing_herbs)
    _grant(player, content.lembas)

    engine.message_log.add_message(
        "The year is 2965 of the Third Age. You come to Talbrún, a hamlet of "
        "the Dúnedain upon the Weather Hills.",
        color.welcome_text,
    )
    engine.message_log.add_message(
        "Speak with the folk here (walk into them), then seek the barrow in the "
        "wild to the east. Press ? for the lore of the wayfarer.",
        color.welcome_text,
    )
    return engine
