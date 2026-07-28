from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

import tcod  # retained headless: FOV only (tcod.map.compute_fov below)
from tcod import libtcodpy

from lonelands import color, config, render_functions
from lonelands.exceptions import Impossible
from lonelands.message_log import MessageLog
from lonelands.quests import QuestLog

if TYPE_CHECKING:
    from lonelands.dice import RollResult
    from lonelands.display import Console
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
        # Difficulty scales only the damage the player takes (see config and
        # Fighter.take_damage); setup_game.new_game overrides it per run.
        self.difficulty = config.DEFAULT_DIFFICULTY
        # God mode: a transient debug toggle (ADR 0012). Off by default, never
        # serialized (dropped below, reset on load) — it is a testing switch,
        # not a saved fact.
        self.god_mode = False
        from lonelands import input_handlers
        self.event_handler = input_handlers.MainGameEventHandler(self)

    def __getstate__(self) -> Dict[str, Any]:
        """Drop transient UI and debug state; savegame._rehydrate rebuilds it."""
        state = self.__dict__.copy()
        state["event_handler"] = None
        state["last_roll"] = None
        state["god_mode"] = False  # never persists — a fresh load is god-less
        return state

    def note_roll(self, result: "RollResult", roller: "Actor") -> None:
        """Record a Test for the dice tray, but only when the player rolled it."""
        if roller is self.player:
            self.last_roll = result

    # --- turns ------------------------------------------------------------
    def handle_enemy_turns(self) -> None:
        self._tick_bleed()
        self._tick_regen()
        for entity in set(self.game_map.actors) - {self.player}:
            if entity.ai:
                try:
                    entity.ai.perform()
                except Impossible:
                    pass
        self._tick_roots()
        self.turn_count += 1

    def _tick_roots(self) -> None:
        """Wear down every fighter's root by one round, after the foes have had
        their (possibly held-fast) turn. A Snare/Pinning set on the player's turn
        thus holds a foe through exactly the enemy phase it was cast against."""
        for actor in list(self.game_map.actors):
            if actor.fighter is not None:
                actor.fighter.tick_root()

    def _tick_regen(self) -> None:
        """Athelas heal-over-time on every fighter carrying it, once per round
        (only a hero ever does — the Long Watch's kingsfoil draught)."""
        for actor in list(self.game_map.actors):
            fighter = actor.fighter
            if fighter is None:
                continue
            healed = fighter.tick_regen()  # 0 unless an Athelas draught is active
            if healed > 0 and actor is self.player:
                self.message_log.add_message(
                    f"Athelas knits {healed} endurance back.", color.hope_gain)

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
    def render(self, console: "Console") -> None:
        """The cell-grid layer: the map, plus the mouse-hover names that label a
        map tile. The sidebar, Chronicle, and location banner are drawn natively
        — see :meth:`render_hud`."""
        self.game_map.render(console)
        render_functions.render_names_at_mouse(console, self)

    def render_hud(self, display, banner: bool = True) -> None:
        """The native pixel HUD around the map (sidebar, Chronicle, banner)."""
        from lonelands import hud
        hud.render(display, self, banner=banner)
