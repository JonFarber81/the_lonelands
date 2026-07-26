from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

import tcod
from tcod import libtcodpy

from lonelands import color, render_functions
from lonelands.config import LOG_TEXT_HEIGHT, LOG_TEXT_Y, MAP_WIDTH
from lonelands.exceptions import Impossible
from lonelands.message_log import MessageLog
from lonelands.quests import QuestLog

if TYPE_CHECKING:
    from lonelands.dice import RollResult
    from lonelands.entity import Actor
    from lonelands.game_map import GameMap
    from lonelands.world import GameWorld


class Engine:
    game_map: "GameMap"
    game_world: "GameWorld"

    def __init__(self, player: "Actor"):
        self.player = player
        self.message_log = MessageLog()
        self.quest_log = QuestLog()
        # The dice tray shows the player's most recent Test; None until they roll.
        self.last_roll: "RollResult | None" = None
        self.mouse_location = (0, 0)
        self.flags: Dict[str, Any] = {}
        self.turn_count = 0
        from lonelands import input_handlers
        self.event_handler = input_handlers.MainGameEventHandler(self)

    def __getstate__(self) -> Dict[str, Any]:
        """Drop transient UI state; savegame._rehydrate rebuilds it on load."""
        state = self.__dict__.copy()
        state["event_handler"] = None
        state["last_roll"] = None
        return state

    def note_roll(self, result: "RollResult", roller: "Actor") -> None:
        """Record a Test for the dice tray, but only when the player rolled it."""
        if roller is self.player:
            self.last_roll = result

    # --- turns ------------------------------------------------------------
    def handle_enemy_turns(self) -> None:
        self._tick_bleed()
        for entity in set(self.game_map.actors) - {self.player}:
            if entity.ai:
                try:
                    entity.ai.perform()
                except Impossible:
                    pass
        self.turn_count += 1
        self._passive_regen()

    def _tick_bleed(self) -> None:
        """Bleed damage-over-time on every living fighter, once per round."""
        for actor in list(self.game_map.actors):
            fighter = actor.fighter
            if fighter is None:
                continue
            lost = fighter.tick_bleed()  # a no-op (0) if dead or not bleeding
            if lost <= 0:
                continue
            if actor is self.player:
                self.message_log.add_message(
                    f"Your wounds bleed for {lost} endurance.", color.player_die
                )
            elif self.game_map.visible[actor.x, actor.y]:
                self.message_log.add_message(
                    f"The {actor.name} bleeds for {lost} endurance.", color.enemy_atk
                )

    def _passive_regen(self) -> None:
        # A slow trickle of Hope when out of danger and not miserable.
        hero = self.player.hero
        if hero is None:
            return
        enemies_near = any(
            self.game_map.visible[a.x, a.y]
            for a in self.game_map.actors
            if a.ai is not None
        )
        if not enemies_near and self.turn_count % 25 == 0 and not hero.is_miserable:
            if hero.hope < hero.max_hope:
                hero.hope += 1

    # --- vision -----------------------------------------------------------
    def update_fov(self) -> None:
        radius = 20 if self.game_map.outdoors else 8
        self.game_map.visible[:] = tcod.map.compute_fov(
            self.game_map.tiles["transparent"],
            (self.player.x, self.player.y),
            radius=radius,
            light_walls=True,
            algorithm=libtcodpy.FOV_SYMMETRIC_SHADOWCAST,
        )
        self.game_map.explored |= self.game_map.visible

    # --- rendering --------------------------------------------------------
    def render(self, console: tcod.console.Console) -> None:
        self.game_map.render(console)

        # Message log beneath the dice tray (left of the sidebar).
        self.message_log.render(
            console,
            x=1,
            y=LOG_TEXT_Y,
            width=MAP_WIDTH - 2,
            height=LOG_TEXT_HEIGHT,
        )
        render_functions.render_sidebar(console, self)
        render_functions.render_dice_tray(console, self)
        render_functions.render_location_banner(console, self)
        render_functions.render_names_at_mouse(console, self)
