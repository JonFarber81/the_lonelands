from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, List, Optional, Tuple


from lonelands import (actions, character, color, config, events, overworld_map,
                       path_icons, path_tree, perks)
from lonelands.events import CENTER, KeySym, Modifier
from lonelands.render_functions import endurance_color
from lonelands.actions import (
    Action,
    ActivateAbilityAction,
    BumpAction,
    DropItem,
    EquipAction,
    ItemAction,
    PickupAction,
    TakeInteractAction,
    WaitAction,
)
from lonelands.config import MAP_HEIGHT, MAP_WIDTH, SCREEN_HEIGHT, SCREEN_WIDTH
from lonelands.exceptions import Impossible, QuitWithoutSaving

if TYPE_CHECKING:
    from lonelands.display import Console
    from lonelands.engine import Engine
    from lonelands.entity import Actor, Item

MOVE_KEYS = {
    KeySym.UP: (0, -1), KeySym.DOWN: (0, 1),
    KeySym.LEFT: (-1, 0), KeySym.RIGHT: (1, 0),
    KeySym.HOME: (-1, -1), KeySym.PAGEUP: (1, -1),
    KeySym.END: (-1, 1), KeySym.PAGEDOWN: (1, 1),
    KeySym.k: (0, -1), KeySym.j: (0, 1),
    KeySym.h: (-1, 0), KeySym.l: (1, 0),
    KeySym.y: (-1, -1), KeySym.u: (1, -1),
    KeySym.b: (-1, 1), KeySym.n: (1, 1),
    KeySym.KP_8: (0, -1), KeySym.KP_2: (0, 1),
    KeySym.KP_4: (-1, 0), KeySym.KP_6: (1, 0),
    KeySym.KP_7: (-1, -1), KeySym.KP_9: (1, -1),
    KeySym.KP_1: (-1, 1), KeySym.KP_3: (1, 1),
}
WAIT_KEYS = {KeySym.PERIOD, KeySym.KP_5, KeySym.z, KeySym.CLEAR}
CONFIRM_KEYS = {KeySym.RETURN, KeySym.KP_ENTER}
# Menu-cursor keys. Only the arrows/keypad move a list cursor — never h/j/k/l,
# which double as letter accelerators in the node and ability lists.
_CURSOR_UP = {KeySym.UP, KeySym.KP_8}
_CURSOR_DOWN = {KeySym.DOWN, KeySym.KP_2}
_CURSOR_LEFT = {KeySym.LEFT, KeySym.KP_4}
_CURSOR_RIGHT = {KeySym.RIGHT, KeySym.KP_6}
# The number-row keys 1..5 that fire hotbar deeds (ADR 0011 Phase 2).
_HOTBAR_KEYS = (KeySym.N1, KeySym.N2, KeySym.N3, KeySym.N4, KeySym.N5)


# ===========================================================================
# Base handlers
# ===========================================================================
class BaseEventHandler(events.BaseEventHandler):
    def handle_events(self, event) -> "BaseEventHandler":
        state = self.dispatch(event)
        if isinstance(state, BaseEventHandler):
            return state
        return self

    def on_render(self, console: "Console") -> None:
        raise NotImplementedError()

    def ev_quit(self, event: "events.Quit") -> Optional["BaseEventHandler"]:
        raise SystemExit()

    def ev_mousemotion(self, event: "events.MouseMotion") -> Optional["BaseEventHandler"]:
        return None


class PopupMessage(BaseEventHandler):
    def __init__(self, parent: BaseEventHandler, text: str):
        self.parent = parent
        self.text = text

    def on_render(self, console: "Console") -> None:
        self.parent.on_render(console)

    def on_render_native(self, display) -> None:
        self.parent.on_render_native(display)  # the layer beneath (HUD or a menu)
        display.ui.scrim()
        ui = display.ui
        lines = self.text.split("\n")
        w = max(ui.measure(ln)[0] for ln in lines) + ui.pad * 4
        h = ui.line * len(lines) + ui.line + ui.pad * 3
        r = ui.centered(int(w), int(h))
        inner = ui.panel(r.x, r.y, r.w, r.h)
        cx, y = display.win_w // 2, inner.y
        for ln in lines:
            ui.text_center(cx, y, ln, color.white, ui.body)
            y += ui.line
        ui.hint(cx, inner.bottom - ui.small.get_linesize(), "any key to continue")

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        return self.parent


class EventHandler(BaseEventHandler):
    def __init__(self, engine: "Engine"):
        self.engine = engine

    def handle_events(self, event) -> BaseEventHandler:
        action_or_state = self.dispatch(event)
        if isinstance(action_or_state, BaseEventHandler):
            return action_or_state
        if self.handle_action(action_or_state):
            if not self.engine.player.fighter or self.engine.player.fighter._dead:
                return GameOverEventHandler(self.engine)
            return self.engine.event_handler
        return self

    def handle_action(self, action: Optional[Action]) -> bool:
        if action is None:
            return False
        try:
            action.perform()
        except Impossible as exc:
            self.engine.message_log.add_message(exc.args[0], color.impossible)
            return False
        # A player turn has passed: advance node cooldowns/stances, then foes act.
        hero = getattr(self.engine.player, "hero", None)
        if hero is not None:
            hero.end_player_turn()
        self.engine.handle_enemy_turns()
        self.engine.update_fov()
        return True

    def ev_mousemotion(self, event: "events.MouseMotion") -> None:
        # event.tile is a *view* cell; only hovers inside the map viewport name a
        # tile. Convert to a world tile through the camera; store (-1, -1) when
        # the cursor is over the sidebar/Chronicle so no name is shown.
        cx, cy = event.tile.x, event.tile.y
        if 0 <= cx < MAP_WIDTH and 0 <= cy < MAP_HEIGHT:
            wx, wy = self.engine.camera.view_to_world(cx, cy)
            if self.engine.game_map.in_bounds(wx, wy):
                self.engine.mouse_location = (wx, wy)
                return
        self.engine.mouse_location = (-1, -1)

    def on_render(self, console: "Console") -> None:
        self.engine.render(console)

    def on_render_native(self, display) -> None:
        # The always-on HUD (sidebar + Chronicle) sits on the native layer,
        # over the blitted map grid. Overlays draw a scrimmed backdrop instead.
        self.engine.render_hud(display)

    def _scrimmed_backdrop(self, display) -> None:
        """Draw the HUD, then dim the whole screen — the top-layer backdrop an
        open panel (menu, dialog, shop) reads against."""
        self.engine.render_hud(display)
        display.ui.scrim()


# ===========================================================================
# Main game
# ===========================================================================
class MainGameEventHandler(EventHandler):
    def __init__(self, engine: "Engine"):
        super().__init__(engine)
        engine.event_handler = self

    def ev_keydown(self, event: "events.KeyDown"):
        key = event.sym
        player = self.engine.player

        if key in MOVE_KEYS:
            dx, dy = MOVE_KEYS[key]
            return BumpAction(player, dx, dy)
        if key in WAIT_KEYS:
            return WaitAction(player)
        if key in CONFIRM_KEYS or key in (KeySym.GREATER, KeySym.LESS):
            return TakeInteractAction(player)

        if key == KeySym.f:
            return self._begin_ranged()
        if key == KeySym.s:
            return self._toggle_sneak()
        if key == KeySym.g:
            return PickupAction(player)
        if key == KeySym.i:
            return InventoryActivateHandler(self.engine)
        if key == KeySym.d:
            return InventoryDropHandler(self.engine)
        if key == KeySym.c:
            return CharacterScreenHandler(self.engine)
        if key == KeySym.p:
            return PathsHandler(self.engine)
        if key == KeySym.a:
            return AbilitiesHandler(self.engine)
        if key in _HOTBAR_KEYS:
            return self._fire_hotbar(_HOTBAR_KEYS.index(key))
        if key == KeySym.q:
            return QuestScreenHandler(self.engine)
        if key == KeySym.m:
            return OverworldMapHandler(self.engine)
        if key in (KeySym.SLASH, KeySym.QUESTION):
            return HelpHandler(self.engine)
        if key == KeySym.F12 and config.DEBUG:
            return DebugMenuHandler(self.engine)  # cheat menu (ADR 0012)
        if key == KeySym.ESCAPE:
            return EscapeMenuHandler(self.engine)
        return None

    def _toggle_sneak(self) -> None:
        """Toggle the Sneak stance (ADR 0014). Free — a stance, not an action —
        so it returns no Action and passes no turn; it just re-lights the FOV at
        the new (narrowed or full) radius and notes the change. Foes re-evaluate
        against the Ranger's live Stealth on their own next turn."""
        engine = self.engine
        engine.sneaking = not engine.sneaking
        engine.update_fov()
        if engine.sneaking:
            engine.message_log.add_message(
                "You sink into a crouch, senses narrowed, moving as a shadow.",
                color.ranger_green)
        else:
            engine.message_log.add_message(
                "You rise from your crouch and walk openly.", color.gray)
        return None

    def _fire_hotbar(self, slot: int) -> Optional[Action]:
        """Fire the active bound to hotbar slot ``slot`` (0-based; keys 1–5,
        ADR 0011). An empty or not-ready slot just reports why and costs no turn."""
        hero = self.engine.player.hero
        bar = hero.hotbar()
        if slot >= len(bar):
            self.engine.message_log.add_message(
                "No deed is bound to that key.", color.impossible)
            return None
        node = bar[slot]
        if not hero.ability_ready(node.id):
            cd = hero.cooldown_left(node.id)
            why = f" ({cd} to ready)" if cd > 0 else ""
            self.engine.message_log.add_message(
                f"{node.active.name} is not ready{why}.", color.impossible)
            return None
        # Targeted deeds (Shadowstep/Snare/Pinning) open a targeting handler;
        # untargeted ones fire at once.
        if node.active.targeted:
            return begin_active(self.engine, node)
        return fire_untargeted(self.engine, node)

    def _begin_ranged(self) -> Optional[BaseEventHandler]:
        """Enter lock-on firing mode (ADR 0006). Refuses with no bow readied or
        an empty quiver, and if nothing is in sight to shoot."""
        player = self.engine.player
        f = player.fighter
        if f is None or not f.has_ranged_weapon:
            self.engine.message_log.add_message("You have no bow readied.", color.impossible)
            return None
        if actions._ammo_stack(player) is None:
            self.engine.message_log.add_message("Your quiver is empty.", color.impossible)
            return None
        handler = RangedTargetHandler(self.engine)
        if handler.target is None:
            self.engine.message_log.add_message(
                "There is nothing in sight to shoot.", color.impossible)
            return MainGameEventHandler(self.engine)
        return handler


# ===========================================================================
# Lock-on targeting (ADR 0006) — the game's first targeting UI, built reusable
# ===========================================================================
class LockOnHandler(EventHandler):
    """Pick a visible foe with a clear line, nearest pre-selected; cycle with Tab
    or the move-keys, confirm to act, Esc to cancel. Subclasses define what
    confirming does (``on_target``). A future 'look' mode can reuse this."""

    prompt = "Take aim"

    def __init__(self, engine: "Engine"):
        super().__init__(engine)
        self.targets: List["Actor"] = self._gather_targets()
        self.index = 0  # the nearest foe, pre-selected
        engine.event_handler = self

    def _gather_targets(self) -> List["Actor"]:
        """Living, non-friendly fighters in sight (FOV is the range cap, and a
        visible tile has a clear line under symmetric shadowcasting), sorted
        nearest-first by grid distance."""
        engine = self.engine
        gm = engine.game_map
        player = engine.player
        foes = [
            a for a in gm.actors
            if a is not player and actions.is_hostile_actor(a)
            and gm.visible[a.x, a.y]
        ]
        foes.sort(key=lambda a: (actions._chebyshev(player, a),
                                 (a.x - player.x) ** 2 + (a.y - player.y) ** 2))
        return foes

    @property
    def target(self) -> Optional["Actor"]:
        if not self.targets:
            return None
        return self.targets[self.index % len(self.targets)]

    def _cycle(self, step: int) -> None:
        if self.targets:
            self.index = (self.index + step) % len(self.targets)

    def _status_text(self, target: "Actor") -> str:
        """The shooting readout for the current mark: distance, and whether the
        Shot suffers falloff (long shot) or point-blank Disadvantage."""
        player = self.engine.player
        f = player.fighter
        dist = actions._chebyshev(player, target)
        parts = [f"{dist} tiles"]
        penalty = f.range_penalty(dist)
        if penalty:
            parts.append(f"long shot -{penalty}")
        if actions._has_adjacent_hostile(self.engine, player):
            parts.append("point-blank!")
        return " · ".join(parts)

    def on_render(self, console) -> None:
        self.engine.render(console)
        target = self.target
        if target is not None:
            # A bright reticle over the mark, and its name/range across the top.
            vx, vy = self.engine.camera.world_to_view(target.x, target.y)
            if 0 <= vx < MAP_WIDTH and 0 <= vy < MAP_HEIGHT:
                console.rgb["bg"][vx, vy] = color.needs_target
                console.rgb["fg"][vx, vy] = color.near_black
            banner = (f" {self.prompt} — the {target.name}  "
                      f"({self._status_text(target)}) ")
        else:
            banner = f" {self.prompt} — nothing in sight "
        console.draw_rect(x=0, y=0, width=MAP_WIDTH, height=1, ch=ord(" "),
                          bg=(0x24, 0x1E, 0x12))
        console.print(x=1, y=0, string=banner[: MAP_WIDTH - 2], fg=color.needs_target)
        console.print(x=1, y=MAP_HEIGHT - 1,
                      string="[Tab] cycle  [f/Enter] loose  [Esc] cancel",
                      fg=color.gray)

    def on_render_native(self, display) -> None:
        # The HUD, but without the location banner — the targeting prompt (drawn
        # on the grid in on_render) owns the map's top row while aiming.
        self.engine.render_hud(display, banner=False)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        key = event.sym
        if key == KeySym.ESCAPE:
            return self._cancel()
        if key == KeySym.TAB:
            self._cycle(1)
            return None
        if key in MOVE_KEYS:
            dx, dy = MOVE_KEYS[key]
            # Right/down step forward through the ring, left/up step back.
            self._cycle(1 if (dx + dy) > 0 else -1)
            return None
        if key in (KeySym.f,) or key in CONFIRM_KEYS:
            target = self.target
            if target is None:
                return self._cancel()
            return self.on_target(target)
        return None

    def _cancel(self) -> BaseEventHandler:
        self.engine.event_handler = MainGameEventHandler(self.engine)
        return self.engine.event_handler

    def on_target(self, target: "Actor") -> Optional[BaseEventHandler]:
        raise NotImplementedError()


class RangedTargetHandler(LockOnHandler):
    """Lock-on that looses an arrow at the chosen foe (a full turn)."""

    def on_target(self, target: "Actor") -> Optional[BaseEventHandler]:
        self.handle_action(actions.RangedAttackAction(self.engine.player, target))
        if self.engine.player.fighter is None or self.engine.player.fighter._dead:
            return GameOverEventHandler(self.engine)
        return MainGameEventHandler(self.engine)


class PinningTargetHandler(LockOnHandler):
    """Lock-on that pins the chosen foe in place (the Hidden Path's Pinning).
    Only foes within the deed's reach are offered."""

    prompt = "Pin a foe"

    def __init__(self, engine: "Engine", node_id: str):
        self.node_id = node_id
        super().__init__(engine)

    def _gather_targets(self) -> List["Actor"]:
        reach = perks.ALL_NODES[self.node_id].active.reach
        p = self.engine.player
        return [f for f in super()._gather_targets()
                if actions.king_dist(p.x, p.y, f.x, f.y) <= reach]

    def on_target(self, target: "Actor") -> Optional[BaseEventHandler]:
        self.handle_action(
            actions.PinningAction(self.engine.player, self.node_id, target))
        return MainGameEventHandler(self.engine)


# ===========================================================================
# Tile targeting — pick an empty tile within reach (Shadowstep / Snare, #77)
# ===========================================================================
class TileTargetHandler(EventHandler):
    """Move a reticle over open tiles within a deed's reach and confirm one. The
    cursor starts on the nearest legal tile; arrow keys nudge it, Enter fires,
    Esc cancels. Subclasses say what confirming does (:meth:`on_confirm`)."""

    prompt = "Choose a tile"

    def __init__(self, engine: "Engine", node_id: str):
        super().__init__(engine)
        self.node_id = node_id
        self.reach = perks.ALL_NODES[node_id].active.reach
        self.cx, self.cy = self._initial_tile()
        engine.event_handler = self

    def _initial_tile(self) -> Tuple[int, int]:
        p = self.engine.player
        gm = self.engine.game_map
        best, best_d = (p.x, p.y), 999
        for x in range(max(0, p.x - self.reach), min(gm.width, p.x + self.reach + 1)):
            for y in range(max(0, p.y - self.reach), min(gm.height, p.y + self.reach + 1)):
                if self._valid(x, y):
                    d = actions.king_dist(p.x, p.y, x, y)
                    if d < best_d:
                        best, best_d = (x, y), d
        return best

    def _valid(self, x: int, y: int) -> bool:
        # The same legal-tile predicate the resolving Action enforces, plus the
        # subclass's extra rule (e.g. no snare already laid there).
        p = self.engine.player
        return (actions.tile_targetable(self.engine.game_map, p.x, p.y, x, y,
                                        self.reach)
                and self._extra_valid(x, y))

    def _extra_valid(self, x: int, y: int) -> bool:
        return True

    def any_valid(self) -> bool:
        return self._valid(self.cx, self.cy)

    def on_render(self, console) -> None:
        self.engine.render(console)
        ok = self._valid(self.cx, self.cy)
        vx, vy = self.engine.camera.world_to_view(self.cx, self.cy)
        if 0 <= vx < MAP_WIDTH and 0 <= vy < MAP_HEIGHT:
            console.rgb["bg"][vx, vy] = (
                color.needs_target if ok else color.impossible)
            console.rgb["fg"][vx, vy] = color.near_black
        console.draw_rect(x=0, y=0, width=MAP_WIDTH, height=1, ch=ord(" "),
                          bg=(0x24, 0x1E, 0x12))
        console.print(x=1, y=0, string=f" {self.prompt} "[: MAP_WIDTH - 2],
                      fg=color.needs_target)
        console.print(x=1, y=MAP_HEIGHT - 1,
                      string="[arrows] aim  [Enter] confirm  [Esc] cancel",
                      fg=color.gray)

    def on_render_native(self, display) -> None:
        self.engine.render_hud(display, banner=False)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        key = event.sym
        if key == KeySym.ESCAPE:
            return self._cancel()
        if key in MOVE_KEYS:
            dx, dy = MOVE_KEYS[key]
            gm = self.engine.game_map
            nx, ny = self.cx + dx, self.cy + dy
            if gm.in_bounds(nx, ny):
                self.cx, self.cy = nx, ny
            return None
        if key in CONFIRM_KEYS:
            if not self._valid(self.cx, self.cy):
                self.engine.message_log.add_message(
                    "You cannot target that tile.", color.impossible)
                return None
            return self.on_confirm()
        return None

    def _cancel(self) -> BaseEventHandler:
        self.engine.event_handler = MainGameEventHandler(self.engine)
        return self.engine.event_handler

    def on_confirm(self) -> Optional[BaseEventHandler]:
        raise NotImplementedError()


class ShadowstepTargetHandler(TileTargetHandler):
    prompt = "Shadowstep — pick a tile"

    def on_confirm(self) -> Optional[BaseEventHandler]:
        self.handle_action(actions.ShadowstepAction(
            self.engine.player, self.node_id, (self.cx, self.cy)))
        return MainGameEventHandler(self.engine)


class SnareTargetHandler(TileTargetHandler):
    prompt = "Snare — pick a tile"

    def _extra_valid(self, x: int, y: int) -> bool:
        return (x, y) not in self.engine.game_map.traps

    def on_confirm(self) -> Optional[BaseEventHandler]:
        self.handle_action(actions.SnareAction(
            self.engine.player, self.node_id, (self.cx, self.cy)))
        return MainGameEventHandler(self.engine)


class ActiveFoeTargetHandler(LockOnHandler):
    """Lock-on for a foe-targeted Path deed — the Far Shot volley (Multishot,
    Piercing Shot, Harrying Shot), Hunter's Mark, and (later) the Long Watch's
    Charge. Offers only foes within the deed's reach and fires its Action on
    confirm. (Pinning keeps its own handler for its shooting-readout niceties.)"""

    def __init__(self, engine: "Engine", node_id: str):
        self.node_id = node_id
        self._spec = perks.ALL_NODES[node_id].active
        super().__init__(engine)

    @property
    def prompt(self) -> str:  # type: ignore[override]
        return f"{self._spec.name} — pick a foe"

    def _gather_targets(self) -> List["Actor"]:
        reach = self._spec.reach
        p = self.engine.player
        return [f for f in super()._gather_targets()
                if actions.king_dist(p.x, p.y, f.x, f.y) <= reach]

    def on_target(self, target: "Actor") -> Optional[BaseEventHandler]:
        action_cls = _FOE_DEED_ACTIONS[self._spec.kind]
        self.handle_action(action_cls(self.engine.player, self.node_id, target))
        if self.engine.player.fighter is None or self.engine.player.fighter._dead:
            return GameOverEventHandler(self.engine)
        return MainGameEventHandler(self.engine)


# node active kind -> the Action its lock-on fires.
_FOE_DEED_ACTIONS = {
    "arc_shot": actions.MultishotAction,
    "line_shot": actions.PiercingShotAction,
    "harry": actions.HarryingShotAction,
    "mark": actions.HuntersMarkAction,
    "charge": actions.ChargeAction,
}


def fire_untargeted(engine: "Engine", node) -> Action:
    """The Action for a ready untargeted deed. Most resolve in the Hero
    (ActivateAbilityAction), but a map-bound one (Sweeping Blow strikes the tiles
    around you) needs an Action of its own."""
    if node.active.kind == "sweep":
        return actions.SweepAction(engine.player, node.id)
    return ActivateAbilityAction(engine.player, node.id)


def begin_active(engine: "Engine", node) -> Optional[BaseEventHandler]:
    """Route a ready owned active: untargeted deeds return None (the caller fires
    the ActivateAbilityAction), while targeted deeds open a targeting handler. If
    nothing can be targeted, report why and hand back a fresh main handler (as
    ``_begin_ranged`` does) so ``engine.event_handler`` isn't left on the
    discarded targeting handler."""
    spec = node.active
    if spec.kind == "root":
        h = PinningTargetHandler(engine, node.id)
        if h.target is None:
            engine.message_log.add_message(
                "There is no foe in reach to pin.", color.impossible)
            return MainGameEventHandler(engine)
        return h
    if spec.kind in ("dash", "place_tile"):
        h = (ShadowstepTargetHandler if spec.kind == "dash"
             else SnareTargetHandler)(engine, node.id)
        if not h.any_valid():
            engine.message_log.add_message(
                "There is no open ground within reach.", color.impossible)
            return MainGameEventHandler(engine)
        return h
    if spec.kind in _FOE_DEED_ACTIONS:
        # The three volley shots need a bow and an arrow before we even aim
        # (Hunter's Mark and Charge don't).
        if spec.kind in ("arc_shot", "line_shot", "harry"):
            f = engine.player.fighter
            if f is None or not f.has_ranged_weapon:
                engine.message_log.add_message(
                    "You have no bow readied.", color.impossible)
                return MainGameEventHandler(engine)
            if actions._ammo_stack(engine.player) is None:
                engine.message_log.add_message(
                    "Your quiver is empty.", color.impossible)
                return MainGameEventHandler(engine)
        h = ActiveFoeTargetHandler(engine, node.id)
        if h.target is None:
            engine.message_log.add_message(
                "There is no foe within reach.", color.impossible)
            return MainGameEventHandler(engine)
        return h
    return None  # an untargeted active — caller fires ActivateAbilityAction


class GameOverEventHandler(EventHandler):
    def on_render(self, console: "Console") -> None:
        self.engine.render(console)  # the map, as it fell

    def on_render_native(self, display) -> None:
        display.ui.scrim(200)  # the world goes dark; no HUD for the fallen
        ui = display.ui
        cx, cy = display.win_w // 2, display.win_h // 2
        ui.text_center(cx, cy - ui.title.get_linesize(), "Here ends the road.",
                       color.player_die, ui.title)
        ui.text_center(cx, cy + ui.line, "[Enter] to return to the title    [Esc] to quit",
                       color.gray, ui.body)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        from lonelands import savegame
        if event.sym == KeySym.ESCAPE:
            savegame.delete_save()  # the fallen do not walk again
            raise QuitWithoutSaving()
        if event.sym in CONFIRM_KEYS:
            savegame.delete_save()
            return MainMenuHandler()
        return None


# ===========================================================================
# Overlay base: renders game underneath, closes on Esc
# ===========================================================================
class AskUserHandler(EventHandler):
    # on_render inherits EventHandler's map-only grid draw; the dimmed HUD
    # backdrop and the panel are drawn on the native layer (on_render_native).
    def on_render_native(self, display) -> None:
        # Subclasses call super() for the scrimmed HUD backdrop, then paint
        # their panel on top at full brightness.
        self._scrimmed_backdrop(display)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        if event.sym in (KeySym.ESCAPE,) or event.sym in CONFIRM_KEYS:
            return self.on_exit()
        return None

    def on_exit(self) -> Optional[BaseEventHandler]:
        self.engine.event_handler = MainGameEventHandler(self.engine)
        return self.engine.event_handler


# ===========================================================================
# Inventory
# ===========================================================================
class InventorySelectHandler(AskUserHandler):
    title = "Inventory"

    def __init__(self, engine: "Engine"):
        super().__init__(engine)
        self.cursor = 0

    def on_render_native(self, display) -> None:
        super().on_render_native(display)  # scrimmed HUD backdrop
        ui = display.ui
        items = self.engine.player.inventory.items
        w = int(display.win_w * 0.62)
        rows = max(1, len(items))
        h = ui.pad * 3 + ui.head.get_linesize() + rows * ui.line + ui.line
        r = ui.centered(w, int(h))
        inner = ui.panel(r.x, r.y, r.w, r.h, self.title)
        y = inner.y
        if not items:
            ui.text(inner.x, y, "(your pack is empty)", color.tier_label)
        else:
            self.cursor = max(0, min(self.cursor, len(items) - 1))
            eq = self.engine.player.equipment
            kx = inner.x + ui.measure("(x)  ")[0]
            for i, item in enumerate(items):
                sel = i == self.cursor
                if sel:
                    ui.selection(inner.x - ui.pad // 2, y, inner.w + ui.pad, ui.line)
                ui.text(inner.x, y, f"({chr(ord('a') + i)})", color.tier_label)
                head = f"{item.char} {item.name}{item.count_label}"
                hx = ui.text(kx, y, head, color.tier_value if sel else color.tier_body)
                worn = " (worn)" if eq.item_is_equipped(item) else ""
                stats = (f"  [{item.equippable.stat_line()}]"
                         if item.equippable is not None else "")
                if worn or stats:
                    ui.text(kx + hx + ui.pad, y, f"{worn}{stats}".strip(),
                            color.tier_label, ui.small)
                y += ui.line
        ui.hint(display.win_w // 2, inner.bottom - ui.small.get_linesize(),
                "up/down move · Enter use/equip · a-z select · Esc close")

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        items = self.engine.player.inventory.items
        if items and event.sym in _CURSOR_UP:
            self.cursor = (self.cursor - 1) % len(items)
            return None
        if items and event.sym in _CURSOR_DOWN:
            self.cursor = (self.cursor + 1) % len(items)
            return None
        if items and event.sym in CONFIRM_KEYS:
            return self.on_item_selected(items[self.cursor])
        index = event.sym - KeySym.a
        if 0 <= index < len(items):
            return self.on_item_selected(items[index])
        return super().ev_keydown(event)

    def on_item_selected(self, item: "Item") -> Optional[BaseEventHandler]:
        raise NotImplementedError()

    def _resolve(self, action: Action) -> BaseEventHandler:
        self.handle_action(action)
        if self.engine.player.fighter._dead:
            return GameOverEventHandler(self.engine)
        return MainGameEventHandler(self.engine)


class InventoryActivateHandler(InventorySelectHandler):
    title = "Use / Equip which?"

    def on_item_selected(self, item: "Item") -> Optional[BaseEventHandler]:
        if item.consumable:
            return self._resolve(item.consumable.get_action(self.engine.player))
        if item.equippable:
            return self._resolve(EquipAction(self.engine.player, item))
        self.engine.message_log.add_message("You cannot use that.", color.invalid)
        return None


class InventoryDropHandler(InventorySelectHandler):
    title = "Drop which?"

    def on_item_selected(self, item: "Item") -> Optional[BaseEventHandler]:
        return self._resolve(DropItem(self.engine.player, item))


# ===========================================================================
# Character sheet
# ===========================================================================
class CharacterScreenHandler(AskUserHandler):
    # What each attribute governs — shown beside its modifier so the sheet reads
    # on its own.
    _ATTR_GOVERNS = {
        "Brawn": "melee hit & damage, HP",
        "Wits": "ranged, Defence, stealth",
        "Will": "morale, healing, Paths",
    }

    def on_render_native(self, display) -> None:
        super().on_render_native(display)  # scrimmed HUD backdrop
        ui = display.ui
        hero = self.engine.player.hero
        f = self.engine.player.fighter
        w, h = int(display.win_w * 0.56), int(display.win_h * 0.84)
        r = ui.centered(w, h)
        inner = ui.panel(r.x, r.y, r.w, r.h, "Character")
        x, iw = inner.x, inner.w
        y = inner.y
        c2 = x + iw // 3           # value / second column

        # Identity — the header block.
        ident = f"{self.engine.player.name} · {hero.culture} · {hero.calling}"
        ui.selection(x - ui.pad // 2, y, iw + ui.pad, ui.line)
        ui.text(x, y, ident, color.tier_value, ui.bold)
        y += ui.line
        if hero.true_name:
            ui.text(x, y, hero.true_name, color.ranger_green)
            y += ui.line
        y += ui.pad // 2

        # Advancement strip.
        ui.text(x, y, "Level", color.tier_label)
        ui.text(x + ui.measure("Level  ")[0], y, str(hero.level), color.tier_value)
        ui.text(c2, y, "XP", color.tier_label)
        ui.text(c2 + ui.measure("XP  ")[0], y, f"{hero.xp}/{hero.xp_to_next}", color.tier_value)
        y += ui.line
        pp = hero.path_points
        ui.text(x, y, "Path points", color.tier_label)
        ui.text(x + ui.measure("Path points  ")[0], y, str(pp),
                color.hope_gain if pp else color.tier_body)
        ui.text(c2, y, "Coins", color.tier_label)
        ui.text(c2 + ui.measure("Coins  ")[0], y, str(hero.coins), color.gold_c)
        y += ui.line + ui.pad // 2

        # ATTRIBUTES.
        y = ui.section(x, y, iw, "ATTRIBUTES")
        for attr in character.ATTRIBUTES:
            ui.text(x, y, attr, color.tier_body)
            ui.text(x + ui.measure("Brawn   ")[0], y, f"{hero.modifier(attr):+d}", color.tier_value)
            ui.text(c2, y, self._ATTR_GOVERNS.get(attr, ""), color.tier_label, ui.small)
            y += ui.line
        y += ui.pad // 2

        # IN THE FIELD.
        y = ui.section(x, y, iw, "IN THE FIELD")
        ui.text(x, y, "Endurance", color.tier_body)
        ui.text(c2, y, f"{f.endurance}/{f.max_endurance}",
                endurance_color(f.endurance, f.max_endurance))
        y += ui.line
        stats = [("Defence", str(f.defence)), ("Attack", f"+{f.attack_bonus}"),
                 ("Soak", str(f.soak)), ("Load", str(hero.load))]
        sx = x
        for label, val in stats:
            ui.text(sx, y, label, color.tier_label)
            ui.text(sx + ui.measure(label + " ")[0], y, val, color.tier_value)
            sx += iw // 4
        y += ui.line
        ui.text(x, y, "Wielding", color.tier_label)
        ui.text(c2, y, f.weapon_name, color.weapon_c)
        y += ui.line
        if hero.is_weary:
            ui.text(x, y, "Weary — burdened past your vigour.", color.enemy_atk)
            y += ui.line
        y += ui.pad // 2

        # PATH — the committed Path's tree (pathless until level 2).
        y = ui.section(x, y, iw, "PATH")
        ui.text(x, y, "Path", color.tier_label)
        pname = perks.PATHS_BY_ID[hero.path].name if hero.path else "Pathless"
        ui.text(x + ui.measure("Path  ")[0], y, pname,
                color.ranger_green if hero.path else color.tier_label)
        y += ui.line
        if hero.path is None:
            ui.text(x, y, "Commit to a Path at level 2 (press p).",
                    color.tier_label, ui.small)
            y += ui.line
        else:
            path = perks.PATHS_BY_ID[hero.path]
            ranks = sum(hero.rank_of(n.id) for n in path.nodes)   # ranks bought
            caps = sum(n.max_rank for n in path.nodes)             # ranks reachable
            ui.text(x, y, "Nodes taken", color.tier_label)
            ui.text(x + ui.measure("Nodes taken  ")[0], y, f"{ranks}/{caps}",
                    color.tier_value if ranks else color.tier_label)
            y += ui.line

        ui.hint(display.win_w // 2, inner.bottom - ui.small.get_linesize(),
                "p Path & nodes · a abilities · Esc close")

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        if event.sym == KeySym.p:
            return PathsHandler(self.engine)
        if event.sym == KeySym.a:
            return AbilitiesHandler(self.engine)
        return super().ev_keydown(event)


# ===========================================================================
# Paths & nodes (ADR 0011)
# ===========================================================================
class PathsHandler(AskUserHandler):
    """The Path tree screen (ADR 0011, Phase 2 — #74), drawn as a top-down tree:
    a shared **trunk** at the top forking into two **branches**, tiers
    descending, nodes as labelled boxes joined by prereq lines. Ranked passives
    show pips (filled ``•`` per bought rank); state is read off colour — owned
    (green), buyable now (gold), locked (dim, with the reason).

    While **pathless** the screen is the level-2 **chooser**: every Path is
    browsable (``Tab`` / ``←``/``→`` switch trees), fully readable before
    deciding; ``Enter`` throws a permanent-choice confirm and, on yes, commits
    and drops into that tree to spend the first point. Once **committed** it
    shows only that Path's tree, and ``Enter`` buys or ranks the cursor node.

    Arrow keys walk between connected nodes (:mod:`lonelands.path_tree`)."""

    def __init__(self, engine: "Engine"):
        super().__init__(engine)
        hero = engine.player.hero
        # In chooser mode the player browses each Path in turn; once committed
        # the view is pinned to the committed Path.
        self.view_idx = self._committed_idx(hero) if hero.path else 0
        self.cursor_id = self._viewed_path().nodes[0].id

    # --- which Path is on screen ------------------------------------------
    @staticmethod
    def _committed_idx(hero) -> int:
        return next((i for i, p in enumerate(perks.PATHS) if p.id == hero.path), 0)

    def _chooser(self) -> bool:
        return self.engine.player.hero.path is None

    def _viewed_path(self) -> "perks.Path":
        hero = self.engine.player.hero
        if hero.path is not None:
            return perks.PATHS_BY_ID[hero.path]
        return perks.PATHS[self.view_idx % len(perks.PATHS)]

    def _cursor_node(self) -> "perks.Node":
        path = self._viewed_path()
        return perks.ALL_NODES.get(self.cursor_id) or path.nodes[0]

    def _clamp_cursor(self) -> None:
        """Keep the cursor on a node of the Path currently shown."""
        path = self._viewed_path()
        if perks.ALL_NODES.get(self.cursor_id, None) not in path.nodes:
            self.cursor_id = path.nodes[0].id

    # --- pip suffix -------------------------------------------------------
    @staticmethod
    def _pips(node, rank) -> str:
        """A pip string for a rankable node — filled ``•`` for bought ranks, faint
        ``·`` for the rest (``••·``); empty for a one-and-done active. (Filled/open
        circles aren't in the UI face, so bullet + middot stand in.)"""
        if node.max_rank <= 1:
            return ""
        return "• " * rank + "· " * (node.max_rank - rank)

    @staticmethod
    def _locked_reason(hero, node) -> str:
        if hero.path_points < node.cost:
            return "need pts"
        if not perks.tier_unlocked(node, hero.points_in_path):
            return f"need {perks.points_for_tier(node.tier)} in Path"
        if not perks.parent_met(node, hero.nodes.keys()):
            parent = perks.ALL_NODES.get(node.parent)
            return f"need {parent.name}" if parent else "locked"
        return "locked"

    # --- render -----------------------------------------------------------
    def on_render_native(self, display) -> None:
        super().on_render_native(display)  # scrimmed HUD backdrop
        ui = display.ui
        hero = self.engine.player.hero
        self._clamp_cursor()
        w, h = int(display.win_w * 0.84), int(display.win_h * 0.94)
        r = ui.centered(w, h)
        title = "Choose your Path" if self._chooser() else "Paths of the Ranger"
        inner = ui.panel(r.x, r.y, r.w, r.h, title)
        top = self._render_header(ui, inner, hero)
        sls = ui.small.get_linesize()
        footer_y = inner.bottom - sls
        # A fixed two-line detail strip sits above the hint; the tree gives up
        # its height (its width — which keeps forked siblings apart — is untouched).
        strip_h = 2 * sls + ui.pad // 4
        strip_y = footer_y - ui.pad // 2 - strip_h
        self._render_tree(ui, inner, top, strip_y - ui.pad // 4, hero)
        self._render_detail(ui, inner, strip_y, hero)
        if self._chooser():
            hint = "↑/↓ read · ←/→ or Tab switch Path · Enter walk this Path · Esc close"
        else:
            hint = "arrows move · Enter buy/rank · Esc close"
        ui.hint(display.win_w // 2, footer_y, hint)

    def _render_header(self, ui, inner, hero) -> int:
        """Path-points line plus the tab bar (chooser) or the committed name.
        Returns the y where the tree may start."""
        x, y = inner.x, inner.y
        ui.text(x, y, "Path points", color.tier_label, ui.small)
        px = x + ui.small.size("Path points  ")[0]
        ui.text(px, y, str(hero.path_points),
                color.hope_gain if hero.path_points else color.tier_body, ui.small)
        blurb = self._viewed_path().blurb
        ui.text_right(inner.right, y, ui.truncate(blurb, inner.w // 2, ui.small),
                      color.tier_label, ui.small)
        y += ui.small.get_linesize() + ui.pad // 4
        if self._chooser():
            # A tab bar of all three Paths; the viewed one is lit.
            tx = x
            for i, path in enumerate(perks.PATHS):
                lit = i == self.view_idx % len(perks.PATHS)
                label = f" {path.name} "
                wlab = ui.body.size(label)[0]
                if lit:
                    ui.selection(tx, y, wlab, ui.line)
                ui.text(tx, y, label, color.selected if lit else color.tier_label, ui.body)
                tx += wlab + ui.pad
        else:
            ui.text(x, y, f"Committed — {self._viewed_path().name}",
                    color.ranger_green, ui.body)
        return y + ui.line + ui.pad // 3

    def _render_detail(self, ui, inner, y, hero) -> None:
        """The bottom detail strip for the cursor node (ADR 0011 legibility):
        its name + the "what a point buys" framing on line 1, its full
        description on line 2. Mode-aware — pathless it's pure reference (the
        price only), committed it reads the live buy/rank/locked state."""
        node = self._cursor_node()
        rank = hero.rank_of(node.id)
        committed = not self._chooser()
        buyable = committed and hero.can_buy(node)
        summary = perks.buy_summary(
            node, rank, committed=committed, buyable=buyable,
            locked_reason=self._locked_reason(hero, node))
        sls = ui.small.get_linesize()
        ui.connector(inner.x, y - ui.pad // 4, inner.right, y - ui.pad // 4,
                     color.rule)
        name = ("* " if node.capstone else "") + node.name
        nx = ui.text(inner.x, y, name, color.tier_value, ui.small)
        ui.text(inner.x + nx + ui.pad // 2, y, f"· {summary}",
                color.hope_gain if buyable else color.tier_label, ui.small)
        ui.text(inner.x, y + sls, ui.truncate(node.desc, inner.w, ui.small),
                color.tier_body, ui.small)

    def _render_tree(self, ui, inner, top, bottom, hero) -> None:
        path = self._viewed_path()
        placements = path_tree.layout(path)
        rows = max((p.row for p in placements), default=0) + 1
        rowstep = max(1, (bottom - top) // max(1, rows))

        # Card width is uniform. Cards are centred at ``inner.x + box_w/2 +
        # x*usable`` where ``usable = inner.w - box_w``, so the pixel gap between
        # the tightest same-row pair (Ambush's forked children, ``dx`` apart) is
        # ``dx*usable``. Size the card to leave a fixed gutter inside that:
        #   box_w = dx*(inner.w - box_w) - gutter  ->  solve for box_w.
        by_row: dict = {}
        for p in placements:
            by_row.setdefault(p.row, []).append(p.x)
        dx = min((b - a for xs in by_row.values() if len(xs) > 1
                  for a, b in zip(sorted(xs), sorted(xs)[1:])), default=1.0)
        gutter = ui.pad
        box_w = int((dx * inner.w - gutter) / (1 + dx))
        box_w = max(int(inner.w * 0.14), min(box_w, int(inner.w * 0.32)))
        box_h = min(rowstep - ui.pad // 3, int(ui.line * 4.6))
        usable = inner.w - box_w

        def centre(p):
            cx = inner.x + box_w // 2 + int(p.x * usable)
            cy = top + p.row * rowstep + rowstep // 2
            return cx, cy

        at = {p.node.id: p for p in placements}
        # Orthogonal prereq connectors, drawn first so cards sit on top. Each
        # parent drops a stem to a bus between the rows, the bus spans its
        # children, and a riser drops to each child — no diagonals, ever.
        kids_of: dict = {}
        for p in placements:
            if p.node.parent in at:
                kids_of.setdefault(p.node.parent, []).append(p)
        for pid, kids in kids_of.items():
            px, py = centre(at[pid])
            child_xy = [centre(k) for k in kids]
            child_top = min(cy for _, cy in child_xy) - box_h // 2
            bus_y = (py + box_h // 2 + child_top) // 2
            ui.connector(px, py + box_h // 2, px, bus_y, color.rule)
            xs = [px] + [cx for cx, _ in child_xy]
            ui.connector(min(xs), bus_y, max(xs), bus_y, color.rule)
            for cx, _ in child_xy:
                ui.connector(cx, bus_y, cx, child_top, color.rule)
        # A trunk stem joins consecutive parentless roots (the Long Watch's two
        # trunk deeds), so the shared stem reads as one column, not floating boxes.
        stem = sorted((p for p in placements if p.node.parent is None),
                      key=lambda p: p.row)
        for a, b in zip(stem, stem[1:]):
            if b.row - a.row == 1 and abs(a.x - b.x) < 1e-6:
                ax, ay = centre(a)
                bx, by = centre(b)
                ui.connector(ax, ay + box_h // 2, bx, by - box_h // 2, color.rule)
        for p in placements:
            cx, cy = centre(p)
            self._draw_node(ui, p.node, cx - box_w // 2, cy - box_h // 2,
                            box_w, box_h, hero)

    def _draw_node(self, ui, node, x, y, w, h, hero) -> None:
        rank = hero.rank_of(node.id)
        maxed = rank >= node.max_rank and rank > 0
        buyable = (not self._chooser()) and hero.can_buy(node)
        selected = node.id == self.cursor_id

        if maxed:
            # A one-and-done active reads "learned"; a maxed passive shows its cap.
            badge = "learned" if node.active else f"rank {rank}/{node.max_rank}"
            border, name_col, badge_col, icon_col = (
                color.ranger_green,) * 4
        elif buyable:
            # Affordable now — the gold "highlighted" state, whether a first buy
            # or a rank-up on a node already owned.
            verb = "rank up" if rank > 0 else "buy"
            border, name_col, badge, badge_col, icon_col = (
                color.section_head, color.tier_value,
                f"{verb} · {node.cost}pp", color.hope_gain, color.section_head)
        elif rank > 0:
            # Owned but not rankable right now (capped elsewhere or unaffordable).
            border, name_col, badge, badge_col, icon_col = (
                color.ranger_green, color.ranger_green,
                f"rank {rank}/{node.max_rank}", color.ranger_green, color.ranger_green)
        elif self._chooser():
            border, name_col, badge, badge_col, icon_col = (
                color.frame_bright, color.tier_body, f"{node.cost}pp",
                color.tier_label, color.frame_bright)
        else:
            border, name_col, badge, badge_col, icon_col = (
                color.rule, color.tier_label, self._locked_reason(hero, node),
                color.tier_label, color.tier_label)

        fill = (*color.bar_accent, 120) if selected else None
        if selected:
            border = color.selected
        ui.outline(x, y, w, h, border, fill=fill, width=3 if selected else 2)

        cx = x + w // 2
        ls = ui.small.get_linesize()
        top_pad = ui.pad // 4
        bot_pad = ui.pad // 5
        avail = h - top_pad - bot_pad
        # Name and badge are mandatory; the rank pips are decorative (the badge
        # already spells out the rank), so on a short card — a deep Path packed
        # into the panel — they're the first thing dropped rather than spilling a
        # row past the border.
        rows = [(("* " if node.capstone else "") + node.name, name_col)]
        pips = self._pips(node, rank).strip()
        if pips and 3 * ls <= avail:
            rows.append((pips, color.ranger_green if rank else color.tier_label))
        rows.append((badge, badge_col))
        text_h = len(rows) * ls
        # The icon crowns the card in the room the text rows leave, capped by
        # width and a pleasant maximum; on a tight card it shrinks and finally
        # gives way rather than shoving the text out the bottom.
        icon_size = int(min(w * 0.36, h * 0.42, avail - text_h))
        if icon_size >= ls:
            path_icons.draw(ui.screen, node, cx, y + top_pad + icon_size // 2,
                            icon_size, icon_col)
            text_top = y + top_pad + icon_size
            text_bot = y + h - bot_pad
            gap = max(0, (text_bot - text_top - text_h) // max(1, len(rows) - 1))
        else:
            # Too short for an icon — centre the text block with tight, even
            # spacing so it reads as deliberate rather than pinned to the edges.
            gap = ls // 3
            text_top = y + (h - text_h - gap * (len(rows) - 1)) // 2
        ry = text_top
        for text, col in rows:
            ui.text_center(cx, ry, ui.truncate(text, w - ui.pad, ui.small), col, ui.small)
            ry += ls + gap

    # --- input ------------------------------------------------------------
    def _buy_cursor(self) -> None:
        hero = self.engine.player.hero
        node = self._cursor_node()
        rank = hero.rank_of(node.id)
        if rank >= node.max_rank and rank > 0:
            self.engine.message_log.add_message(
                f"You have mastered {node.name} already.", color.invalid)
            return
        if hero.buy_node(node):
            self.engine.message_log.add_message(
                f"You take up {node.name}. {node.desc}", color.xp_filled)
        else:
            self.engine.message_log.add_message(
                f"You cannot take {node.name} yet — {self._locked_reason(hero, node)}.",
                color.impossible)

    def _commit_viewed(self) -> Optional[BaseEventHandler]:
        """Throw the permanent-choice confirm for the Path on screen."""
        path = self._viewed_path()

        def go() -> BaseEventHandler:
            self.engine.player.hero.commit_path(path.id)
            self.engine.message_log.add_message(
                f"You commit to {path.name}. There is no turning back.",
                color.xp_filled)
            return PathsHandler(self.engine)

        return ConfirmHandler(
            self.engine,
            f"This is permanent — walk the Path of {path.name}?",
            on_confirm=go, cancel_to=self)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        # While pathless, ←/→/Tab switch which Path is browsed (so the cursor
        # keys ←/→ can't also walk the tree — only ↑/↓ do in the chooser). Once
        # committed there's one tree, and all four arrows walk it.
        if self._chooser() and event.sym in ({KeySym.TAB} | _CURSOR_LEFT | _CURSOR_RIGHT):
            step = -1 if event.sym in _CURSOR_LEFT else 1
            self.view_idx = (self.view_idx + step) % len(perks.PATHS)
            self.cursor_id = self._viewed_path().nodes[0].id
            return None
        delta = {**{k: (0, -1) for k in _CURSOR_UP}, **{k: (0, 1) for k in _CURSOR_DOWN},
                 **{k: (-1, 0) for k in _CURSOR_LEFT}, **{k: (1, 0) for k in _CURSOR_RIGHT}}
        if event.sym in delta:
            dx, dy = delta[event.sym]
            placements = path_tree.layout(self._viewed_path())
            self.cursor_id = path_tree.move(placements, self.cursor_id, dx, dy)
            return None
        if event.sym in CONFIRM_KEYS:
            if self._chooser():
                return self._commit_viewed()
            self._buy_cursor()
            return None
        return super().ev_keydown(event)


class ConfirmHandler(AskUserHandler):
    """A small yes/no modal. ``on_confirm`` is a zero-arg callable returning the
    handler to move to on **yes**; ``cancel_to`` is returned on **no**/Esc
    (defaults to the main game). Used for the Path's permanent-choice confirm."""

    def __init__(self, engine: "Engine", prompt: str, on_confirm,
                 cancel_to: Optional[BaseEventHandler] = None):
        super().__init__(engine)
        self.prompt = prompt
        self.on_confirm = on_confirm
        self.cancel_to = cancel_to

    def on_render_native(self, display) -> None:
        super().on_render_native(display)  # scrimmed HUD backdrop
        ui = display.ui
        w = int(display.win_w * 0.46)
        lines = ui.wrap(self.prompt, w - ui.pad * 3, ui.body)
        h = ui.pad * 3 + ui.head.get_linesize() + len(lines) * ui.line + ui.line
        r = ui.centered(w, int(h))
        inner = ui.panel(r.x, r.y, r.w, r.h, "A permanent choice")
        y = inner.y
        for line in lines:
            ui.text(inner.x, y, line, color.tier_value, ui.body)
            y += ui.line
        ui.hint(display.win_w // 2, inner.bottom - ui.small.get_linesize(),
                "[Y] yes, walk it    [N] not yet")

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        if event.sym == KeySym.y:
            return self.on_confirm()
        if event.sym in (KeySym.n, KeySym.ESCAPE):
            return self.cancel_to if self.cancel_to is not None else self.on_exit()
        return None


class AbilitiesHandler(AskUserHandler):
    """List the hero's owned Path actives with their charge/cooldown state and
    fire a ready one. Firing produces an ActivateAbilityAction (a full turn):
    heal/stance resolve at once, a Wrath-style active primes the next melee hit."""

    def __init__(self, engine: "Engine"):
        super().__init__(engine)
        self.cursor = 0

    def on_render_native(self, display) -> None:
        super().on_render_native(display)  # scrimmed HUD backdrop
        ui = display.ui
        hero = self.engine.player.hero
        actives = hero.actives()
        w = int(display.win_w * 0.62)
        rows = max(1, len(actives))
        h = ui.pad * 3 + ui.head.get_linesize() + rows * ui.line + ui.line
        r = ui.centered(w, int(h))
        inner = ui.panel(r.x, r.y, r.w, r.h, "Deeds & Abilities")
        x, iw, y = inner.x, inner.w, inner.y
        if not actives:
            ui.text(x, y, "You have learned no active deeds yet.", color.tier_label)
        else:
            self.cursor = max(0, min(self.cursor, len(actives) - 1))
            c_name = x + ui.measure("(a)  ")[0]
            c_state = x + int(iw * 0.34)
            c_desc = x + int(iw * 0.52)
            for i, pk in enumerate(actives):
                cd = hero.cooldown_left(pk.id)
                if hero.is_primed(pk.id):
                    state, scol = "primed", color.hope_gain
                elif cd > 0:
                    state, scol = f"cooldown {cd}", color.tier_label
                else:
                    state, scol = "ready", color.end_full
                sel = i == self.cursor
                if sel:
                    ui.selection(x - ui.pad // 2, y, iw + ui.pad, ui.line)
                ui.text(x, y, f"({chr(ord('a') + i)})", color.tier_label)
                ui.text(c_name, y, pk.active.name, color.tier_value if sel else color.tier_body)
                ui.text(c_state, y, state, scol, ui.small)
                ui.text(c_desc, y, ui.truncate(pk.desc, inner.right - c_desc, ui.small),
                        color.tier_body if sel else color.tier_label, ui.small)
                y += ui.line
        ui.hint(display.win_w // 2, inner.bottom - ui.small.get_linesize(),
                "up/down move · Enter use · a-z use · Esc close")

    def _use(self, pk) -> Optional[BaseEventHandler]:
        hero = self.engine.player.hero
        if not hero.ability_ready(pk.id):
            self.engine.message_log.add_message(
                f"{pk.active.name} is not ready.", color.impossible)
            return None
        if pk.active.targeted:
            # Hand off to the targeting handler (which falls back to the main
            # handler itself when there is nothing in reach to target).
            return begin_active(self.engine, pk)
        self.handle_action(fire_untargeted(self.engine, pk))
        return MainGameEventHandler(self.engine)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        hero = self.engine.player.hero
        actives = hero.actives()
        if actives and event.sym in _CURSOR_UP:
            self.cursor = (self.cursor - 1) % len(actives)
            return None
        if actives and event.sym in _CURSOR_DOWN:
            self.cursor = (self.cursor + 1) % len(actives)
            return None
        if actives and event.sym in CONFIRM_KEYS:
            return self._use(actives[self.cursor])
        index = event.sym - KeySym.a
        if 0 <= index < len(actives):
            return self._use(actives[index])
        return super().ev_keydown(event)


# ===========================================================================
# Quest screen
# ===========================================================================
class QuestScreenHandler(AskUserHandler):
    def on_render_native(self, display) -> None:
        super().on_render_native(display)  # scrimmed HUD backdrop
        ui = display.ui
        w, h = int(display.win_w * 0.6), int(display.win_h * 0.82)
        r = ui.centered(w, h)
        inner = ui.panel(r.x, r.y, r.w, r.h, "Errands & Tidings")
        x, iw, y = inner.x, inner.w, inner.y
        shown = [q for q in self.engine.quest_log.quests.values()
                 if q.state.name != "UNSTARTED"]
        if not shown:
            ui.text(x, y, "You carry no errands yet. Seek out the folk of Bree.",
                    color.tier_label)
        for q in shown:
            head_col = {
                "DONE": color.health_recovered,
                "READY": color.hope_gain,
            }.get(q.state.name, color.section_head)
            ui.text(x, y, q.status_line(), head_col, ui.bold)
            y += ui.line
            y = ui.paragraph(x + ui.pad, y, q.summary, color.tier_body, iw - ui.pad)
            y += ui.pad // 3
        ui.hint(display.win_w // 2, inner.bottom - ui.small.get_linesize(), "Esc close")


# ===========================================================================
# Help
# ===========================================================================
HELP_TEXT = """The Lonelands — a solo Ranger in Eriador, TA 2965

MOVEMENT   arrows, hjkl, yubn, or numpad. Move into a foe to strike;
           move into a townsfolk to speak.
WAIT       . (period) or z
ENTER/> <  use a gate, stair, or barrow-entrance you stand upon
f          loose an arrow — lock onto the nearest foe in sight, then
           Tab/move to cycle, f or Enter to shoot, Esc to cancel
s          sneak — crouch to move unseen (narrows your own sight); free
g          pick up what lies underfoot
i          use or equip from your pack
d          set down an item
c          your character sheet
p          your Path's tree — at level 2 choose a Path, then spend points on it
1-5        loose an active deed from your hotbar (see a)
a          your active deeds (abilities on cooldown/charge)
q          your errands and tidings
M          the Overworld Map — all of Eriador at a glance
?          this help
Esc        the wayfarer's menu

THE ROLL   Deeds are tested with a d20 plus an attribute (Brawn, Wits, or
           Will) against a Target Number. A natural 20 is a Critical; a
           natural 1 a Fumble. Slaying foes grants XP; levels come often,
           each granting +HP, a periodic +to-hit, and — from level 2 — a Path
           point to spend on your committed Path.

THE BOW    A bow rides the ranged slot beside your melee weapon — no swap.
           A Shot is keyed off Wits and spends an arrow; it flies true within
           the bow's range, then falls off past it, and a foe at your elbow
           spoils the aim. Half your arrows can be gathered up again (g).

STEALTH    Sneak (s) to slip past foes: your Stealth (Wits + Silent Tread +
           gear) shrinks a foe's sight, and a foe that never spots you can be
           Ambushed — an unseen strike that hits with advantage and bonus
           damage. A struck or watching foe wakes (!), hunts your last spot
           (?), then loses the trail. Re-hide and the Ambush comes round again.

VITALS     Endurance is your vigour — at 0 you fall. Grow Weary as burdens
           mount past your strength; a Bleed wound worsens each round until
           it's staunched. Athelas mends flesh and stops the bleeding.
"""


class HelpHandler(AskUserHandler):
    def on_render_native(self, display) -> None:
        super().on_render_native(display)  # scrimmed HUD backdrop
        ui = display.ui
        lines = HELP_TEXT.strip("\n").splitlines()
        w, h = int(display.win_w * 0.74), int(display.win_h * 0.92)
        r = ui.centered(w, h)
        inner = ui.panel(r.x, r.y, r.w, r.h, "Lore of the Wayfarer")
        # A monospace face keeps the help's aligned columns; size it to fit,
        # leaving a row clear at the bottom for the footer hint.
        avail = inner.height - ui.line * 2
        font = ui.mono_fit(len(lines) + 1, avail)
        step = font.get_linesize()
        y = inner.y
        for i, line in enumerate(lines):
            col = color.section_head if i == 0 else color.tier_body
            ui.text(inner.x, y, line, col, font)
            y += step
        ui.hint(display.win_w // 2, inner.bottom - ui.small.get_linesize(), "any key to close")

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        return self.on_exit()


# ===========================================================================
# Overworld Map (issue #63) — the full-reveal atlas of the whole Region grid
# ===========================================================================
class OverworldMapHandler(AskUserHandler):
    """A modal, full-screen chart of the entire 15×9 Region grid (CONTEXT.md →
    *World & navigation*). A cursor roves cell-to-cell; the footer reads the
    selected Region's name, note, and deeps (or the Sea / Misty Mountains off the
    grid). No turn passes — it is a reference atlas, available even in the deeps,
    where it marks the Region overhead. Data and layout come from
    :mod:`lonelands.overworld_map`; this handler only blits and drives the cursor.
    """

    def __init__(self, engine: "Engine"):
        super().__init__(engine)
        # Start the cursor on the player's own Region.
        self.cursor: Tuple[int, int] = engine.game_world.coord

    # --- layout -----------------------------------------------------------
    _GX = (SCREEN_WIDTH - overworld_map.GRID_W) // 2   # centred left margin
    _GY = 2                                            # title rides rows 0–1
    _FOOTER_HINT = " arrows/hjkl move · M or Esc close "  # subclasses override

    def on_render(self, console: "Console") -> None:
        # The atlas is a two-layer page. The terrain — band-tinted Region blocks,
        # the threaded Great Roads, and the role/deeps/@ markers — is a cell grid
        # drawn here. Every piece of *text* (the title, Region names, legend, and
        # cursor footer) is drawn natively in on_render_native, in the
        # proportional UI font, so it reads as words instead of one wide glyph per
        # map cell (which sprawled and ran off the screen). We stash the buffer so
        # the native pass can place names over the very blocks drawn here.
        console.rgb["ch"] = ord(" ")
        console.rgb["fg"] = color.gray
        console.rgb["bg"] = color.near_black
        gw = self.engine.game_world
        self._buf = overworld_map.render_map(gw.coord, self.cursor)
        self._blit(console, self._buf)

    def on_render_native(self, display) -> None:
        ui = display.ui
        cw, ch = display.cell_w, display.cell_h
        ox, oy = display.offset
        buf = getattr(self, "_buf", None)
        if buf is None:  # native pass without a prior on_render (defensive)
            buf = overworld_map.render_map(self.engine.game_world.coord, self.cursor)

        def px(col: int, row: int) -> "Tuple[int, int]":
            """Pixel top-left of atlas buffer cell (col, row)."""
            return ox + (self._GX + col) * cw, oy + (self._GY + row) * ch

        # Title — centred over the atlas, in the menu title face.
        tcx = ox + int((self._GX + overworld_map.GRID_W / 2) * cw)
        ui.text_center(tcx, oy + ch // 3, "The Ranger's Atlas — Eriador",
                       color.menu_title, ui.head)

        # Region names — proportional, each on a dim plate so it reads over the
        # band tint. place_labels reserved each a run clear of the markers, so
        # the (narrower) proportional text never buries a glyph or a neighbour.
        for p in buf.placements:
            x, y = px(p.col, p.row)
            ui.plate(x, y, p.text, p.fg, ui.small)

        self._render_legend(ui, px, buf.height)
        self._render_footer(ui, px, cw, in_deeps=self.engine.game_world.level_index < 0)

    def _blit(self, console, buf) -> None:
        for r in range(buf.height):
            row_ch, row_fg, row_bg = buf.ch[r], buf.fg[r], buf.bg[r]
            sy = self._GY + r
            for c in range(buf.width):
                console.print(self._GX + c, sy, row_ch[c],
                              fg=row_fg[c] or color.gray,
                              bg=row_bg[c] or color.near_black)

    def _render_legend(self, ui, px, grid_h) -> None:
        for i, (row, label_fg) in enumerate((
            (overworld_map.band_legend(), color.tier_body),
            (overworld_map.role_legend(), color.tier_label),
        )):
            x, y = px(0, grid_h + 1 + i)
            for entry in row:
                x += ui.text(x, y, entry.glyph, entry.fg, ui.small) + ui.pad // 3
                x += ui.text(x, y, entry.label, label_fg, ui.small) + ui.pad

    def _render_footer(self, ui, px, cw, in_deeps) -> None:
        d = overworld_map.describe(self.cursor)
        x, y = px(0, overworld_map.GRID_H + 4)
        maxw = overworld_map.GRID_W * cw
        head = d.title
        if not d.off_grid and d.deeps:
            head += f"   {d.deeps} deep{'s' if d.deeps != 1 else ''} below"
        ui.text(x, y, head, color.section_head, ui.bold)
        y += ui.body.get_linesize()
        for line in ui.wrap(d.note, maxw, ui.body):
            ui.text(x, y, line, color.tier_body, ui.body)
            y += ui.body.get_linesize()
        if in_deeps and self.cursor == self.engine.game_world.coord:
            ui.text(x, y, "You are below the surface here.", color.ambient, ui.body)
        # The key hint pinned to the last screen row.
        _, hy = px(0, SCREEN_HEIGHT - self._GY - 1)
        ui.text(x, hy, self._FOOTER_HINT, color.tier_label, ui.small)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        key = event.sym
        if key in MOVE_KEYS:
            dx, dy = MOVE_KEYS[key]
            x = min(overworld_map.X_MAX, max(overworld_map.X_MIN, self.cursor[0] + dx))
            y = min(overworld_map.Y_MAX, max(overworld_map.Y_MIN, self.cursor[1] + dy))
            self.cursor = (x, y)
            return None
        if key in (KeySym.ESCAPE, KeySym.m):
            return self.on_exit()
        return None


# ===========================================================================
# Debug menu (ADR 0012) — a developer cheat panel, reachable only under --debug
# ===========================================================================
class DebugMenuHandler(AskUserHandler):
    """The single door to the cheats (ADR 0012). Opened with F12 while
    ``config.DEBUG`` is set; a cursor picks a cheat (or its hotkey letter fires
    it directly). Every cheat prints a Chronicle line; god mode is the only
    toggle, the rest act once. Never reachable without --debug."""

    def __init__(self, engine: "Engine"):
        super().__init__(engine)
        self.cursor = 0

    # (hotkey, label, method-name). God mode's label gains a live on/off suffix
    # in _label; the rest are static.
    _ROWS = (
        (KeySym.g, "God mode", "_toggle_god"),
        (KeySym.l, "Gain a level", "_gain_level"),
        (KeySym.t, "Teleport to a Region…", "_teleport"),
        (KeySym.h, "Heal to full", "_heal"),
        (KeySym.r, "Reveal the local map", "_reveal"),
        (KeySym.k, "Kill every foe here", "_kill_all"),
    )

    def _label(self, key: KeySym, label: str) -> str:
        if key is KeySym.g:
            return f"{label}  ({'ON' if self.engine.god_mode else 'off'})"
        return label

    def on_render_native(self, display) -> None:
        super().on_render_native(display)  # scrimmed HUD backdrop
        ui = display.ui
        w = int(display.win_w * 0.42)
        h = ui.pad * 3 + ui.head.get_linesize() + len(self._ROWS) * ui.line + ui.line
        r = ui.centered(w, int(h))
        inner = ui.panel(r.x, r.y, r.w, r.h, "Debug — cheats")
        x, y = inner.x, inner.y
        kx = x + ui.measure("[G]   ")[0]
        for i, (key, label, _m) in enumerate(self._ROWS):
            sel = i == self.cursor
            if sel:
                ui.selection(x - ui.pad // 2, y, inner.w + ui.pad, ui.line)
            ui.text(x, y, f"[{chr(key.value).upper()}]", color.section_head, ui.bold)
            ui.text(kx, y, self._label(key, label),
                    color.tier_value if sel else color.tier_body)
            y += ui.line
        ui.hint(display.win_w // 2, inner.bottom - ui.small.get_linesize(),
                "up/down move · Enter do · letter shortcut · Esc close")

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        key = event.sym
        if key in _CURSOR_UP:
            self.cursor = (self.cursor - 1) % len(self._ROWS)
            return None
        if key in _CURSOR_DOWN:
            self.cursor = (self.cursor + 1) % len(self._ROWS)
            return None
        if key in CONFIRM_KEYS:
            return self._fire(self._ROWS[self.cursor][2])
        for row_key, _label, method in self._ROWS:
            if key == row_key:
                return self._fire(method)
        return super().ev_keydown(event)  # Esc closes

    def _fire(self, method: str) -> Optional[BaseEventHandler]:
        return getattr(self, method)()

    def _note(self, text: str) -> None:
        self.engine.message_log.add_message(text, color.welcome_text)

    # --- the cheats -------------------------------------------------------
    def _toggle_god(self) -> Optional[BaseEventHandler]:
        self.engine.god_mode = not self.engine.god_mode
        self._note(f"Debug: god mode {'ON' if self.engine.god_mode else 'OFF'}.")
        return None  # stay in the menu so the state read updates in place

    def _gain_level(self) -> Optional[BaseEventHandler]:
        hero = self.engine.player.hero
        if hero.xp_to_next <= 0:
            self._note("Debug: already at the level cap.")
            return None
        hero.add_xp(hero.xp_to_next)  # one clean level-up (announces its gains)
        return self.on_exit()

    def _teleport(self) -> Optional[BaseEventHandler]:
        return DebugTeleportHandler(self.engine)

    def _heal(self) -> Optional[BaseEventHandler]:
        f = self.engine.player.fighter
        healed = f.heal(f.max_endurance)
        self._note(f"Debug: healed to full (+{healed}).")
        return self.on_exit()

    def _reveal(self) -> Optional[BaseEventHandler]:
        self.engine.game_map.explored[:] = True
        self._note("Debug: the land lies revealed.")
        return self.on_exit()

    def _kill_all(self) -> Optional[BaseEventHandler]:
        gm = self.engine.game_map
        foes = [a for a in list(gm.actors) if actions.is_hostile_actor(a)]
        for foe in foes:
            foe.fighter.endurance = 0  # trips die(): corpse, loot, XP, quests
        self._note(f"Debug: struck down {len(foes)} foe(s).")
        return self.on_exit()


class DebugTeleportHandler(OverworldMapHandler):
    """The teleport cheat's picker (ADR 0012): the Ranger's Atlas driven as a
    Region chooser. Enter drops the player onto the selected Region's Surface at
    its arrival point (Region-to-Region, Surface-only); an impassable cell just
    refuses. Esc/M backs out to the game."""

    _FOOTER_HINT = " arrows/hjkl move · Enter teleport · M or Esc cancel "

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        key = event.sym
        if key in MOVE_KEYS:
            return super().ev_keydown(event)  # move the cursor
        if key in CONFIRM_KEYS:
            if self.engine.game_world.teleport_to(self.cursor):
                self.engine.message_log.add_message(
                    f"Debug: teleported to {self.engine.game_map.name}.",
                    color.welcome_text)
                return self.on_exit()
            self.engine.message_log.add_message(
                "Debug: no Region there (Sea or Mountain).", color.impossible)
            return None
        if key in (KeySym.ESCAPE, KeySym.m):
            return self.on_exit()
        return None


# ===========================================================================
# Escape menu
# ===========================================================================
class EscapeMenuHandler(AskUserHandler):
    def on_render_native(self, display) -> None:
        super().on_render_native(display)  # scrimmed HUD backdrop
        ui = display.ui
        rows = (
            ("[Enter]", "return to the road"),
            ("[S]", "save and continue"),
            ("[T]", "save & quit to title"),
            ("[Q]", "quit to the outer dark"),
        )
        w = int(display.win_w * 0.4)
        h = ui.pad * 3 + ui.head.get_linesize() + len(rows) * (ui.line + ui.pad // 2)
        r = ui.centered(w, int(h))
        inner = ui.panel(r.x, r.y, r.w, r.h, "The wayfarer pauses")
        x, y = inner.x, inner.y
        dx = ui.measure("[Enter]   ")[0]
        for key, desc in rows:
            ui.text(x, y, key, color.section_head, ui.bold)
            ui.text(x + dx, y, desc, color.tier_body)
            y += ui.line + ui.pad // 2

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        from lonelands import savegame
        if event.sym in (KeySym.s,):
            savegame.save_game(self.engine)
            self.engine.message_log.add_message("The road is remembered. (Game saved.)",
                                                color.welcome_text)
            return self.on_exit()
        if event.sym in (KeySym.t,):
            savegame.save_game(self.engine)
            return MainMenuHandler()
        if event.sym in (KeySym.q,):
            savegame.save_game(self.engine)
            raise QuitWithoutSaving()
        if event.sym in CONFIRM_KEYS or event.sym == KeySym.ESCAPE:
            return self.on_exit()
        return None


# ===========================================================================
# Dialog
# ===========================================================================
class DialogHandler(EventHandler):
    def __init__(self, engine: "Engine", npc_actor: "Actor"):
        super().__init__(engine)
        self.npc = npc_actor.npc
        self.speaker = npc_actor
        self.node_id = self.npc.start
        self.cursor = 0
        engine.event_handler = self
        self._notify_talk(opening=True)  # the hello is itself a talk-to beat

    def _node(self):
        return self.npc.tree[self.node_id]

    def _notify_talk(self, opening: bool = False) -> None:
        """Tell the quest log the player is speaking with this NPC at this node,
        advancing any talk-to quest that wants them (see Quest.talk_target)."""
        self.engine.quest_log.notify_talk(
            self.speaker.name, self.engine, self.node_id, opening=opening)

    def _visible_options(self):
        opts = []
        for o in self._node()["options"]:
            show = o.get("show")
            if show is None or show(self.engine):
                opts.append(o)
        return opts

    def _text(self):
        t = self._node()["text"]
        return t(self.engine) if callable(t) else t

    def on_render(self, console) -> None:
        self.engine.render(console)  # map grid; the dimmed HUD backdrop is native

    def on_render_native(self, display) -> None:
        self._scrimmed_backdrop(display)  # dimmed HUD behind the panel
        ui = display.ui
        opts = self._visible_options()
        self.cursor = max(0, min(self.cursor, len(opts) - 1)) if opts else 0
        w = int(display.win_w * 0.72)
        text_lines = ui.wrap(self._text(), w - ui.pad * 2, ui.prose)
        h = (ui.pad * 3 + ui.head.get_linesize() + len(text_lines) * ui.prose_line
             + ui.pad + len(opts) * ui.line + ui.line)
        x = (display.win_w - w) // 2
        # Anchor near the bottom, but never let a long speech run off the top.
        y = max(ui.pad, display.win_h - h - int(display.win_h * 0.05))
        inner = ui.panel(x, y, w, int(h), f"{self.speaker.name} — {self.npc.title}")
        cx, cy = inner.x, inner.y
        for line in text_lines:  # speech is prose: read it, in the serif face
            ui.text(cx, cy, line, color.white, ui.prose)
            cy += ui.prose_line
        cy += ui.pad // 2
        ox = cx + ui.measure("  1.  ")[0]
        for i, o in enumerate(opts):
            sel = i == self.cursor
            if sel:
                ui.selection(cx - ui.pad // 2, cy, inner.w + ui.pad, ui.line)
            ui.text(cx, cy, f"{'›' if sel else ' '}{i + 1}.", color.tier_label)
            ui.text(ox, cy, o["text"], color.tier_value if sel else color.tier_body)
            cy += ui.line
        ui.hint(display.win_w // 2, inner.bottom - ui.small.get_linesize(),
                "up/down move · Enter choose · number choose · Esc end")

    def _choose(self, chosen) -> Optional[BaseEventHandler]:
        do = chosen.get("do")
        if do:
            do(self.engine)
        handler_factory = chosen.get("handler")
        if handler_factory is not None:
            new_handler = handler_factory(self.engine)
            self.engine.event_handler = new_handler
            return new_handler
        goto = chosen.get("goto")
        if goto is None:
            self.engine.event_handler = MainGameEventHandler(self.engine)
            return self.engine.event_handler
        self.node_id = goto
        self.cursor = 0  # a new node starts its choices from the top
        self._notify_talk()  # reaching a node can satisfy a node-pinned talk-to
        return None

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        opts = self._visible_options()
        if event.sym == KeySym.ESCAPE:
            self.engine.event_handler = MainGameEventHandler(self.engine)
            return self.engine.event_handler
        if not opts:
            return None
        if event.sym in _CURSOR_UP:
            self.cursor = (self.cursor - 1) % len(opts)
            return None
        if event.sym in _CURSOR_DOWN:
            self.cursor = (self.cursor + 1) % len(opts)
            return None
        if event.sym in CONFIRM_KEYS:
            return self._choose(opts[self.cursor])
        idx = None
        if KeySym.N1 <= event.sym <= KeySym.N9:
            idx = event.sym - KeySym.N1
        elif KeySym.KP_1 <= event.sym <= KeySym.KP_9:
            idx = event.sym - KeySym.KP_1
        if idx is None or idx >= len(opts):
            return None
        return self._choose(opts[idx])


# ===========================================================================
# Shop
# ===========================================================================
class ShopHandler(EventHandler):
    """A merchant's stall with a Buy view (the merchant's stock, priced at each
    item's Value) and a Sell view (the hero's sellable items, priced at
    `content.sell_price`). Tab toggles between the two."""

    def __init__(self, engine: "Engine", title: str, stock: List["Item"]):
        super().__init__(engine)
        self.title = title
        self.stock = stock
        self.mode = "buy"  # or "sell"
        self.cursor = 0
        engine.event_handler = self

    # --- Views ------------------------------------------------------------
    def _sell_items(self) -> List["Item"]:
        from lonelands import content
        return [it for it in self.engine.player.inventory.items
                if content.sell_price(it) > 0]

    def _rows(self) -> List[Tuple["Item", int]]:
        """(item, price) pairs for the active view: buy = Value, sell = sell_price."""
        from lonelands import content
        if self.mode == "buy":
            return [(it, it.value) for it in self.stock]
        return [(it, content.sell_price(it)) for it in self._sell_items()]

    def on_render(self, console) -> None:
        self.engine.render(console)  # map grid; the dimmed HUD backdrop is native

    def on_render_native(self, display) -> None:
        self._scrimmed_backdrop(display)  # dimmed HUD behind the panel
        ui = display.ui
        rows = self._rows()
        hero = self.engine.player.hero
        w = int(display.win_w * 0.6)
        h = (ui.pad * 3 + ui.head.get_linesize() + ui.line + ui.pad // 2
             + ui.bold.get_linesize() + max(len(rows), 1) * ui.line + ui.line)
        r = ui.centered(w, int(h))
        inner = ui.panel(r.x, r.y, r.w, r.h, self.title)
        x, iw, y = inner.x, inner.w, inner.y

        # Purse strip — label dim, coins glinting gold.
        ui.text(x, y, "Coins", color.tier_label)
        ui.text(x + ui.measure("Coins  ")[0], y, str(hero.coins), color.gold_c)
        y += ui.line + ui.pad // 3

        y = ui.section(x, y, iw, "BUYING" if self.mode == "buy" else "SELLING")
        if not rows:
            ui.text(x, y, "(nothing to buy)" if self.mode == "buy" else "(nothing to sell)",
                    color.tier_label)
        for i, (item, price) in enumerate(rows):
            sel = i == self.cursor
            if sel:
                ui.selection(x - ui.pad // 2, y, iw + ui.pad, ui.line)
            afford = (color.gold_c if hero.coins >= price else color.impossible) \
                if self.mode == "buy" else color.gold_c
            head = f"{'›' if sel else ' '} {item.char} {item.name}{item.count_label}"
            ui.text(x, y, head, color.tier_value if sel else color.tier_body)
            ui.text_right(inner.right, y, f"{price} c", afford)
            y += ui.line
        hint = ("Tab buy/sell · Enter buy · Esc leave" if self.mode == "buy"
                else "Tab buy/sell · Enter sell 1 · Shift+Enter all · Esc leave")
        ui.hint(display.win_w // 2, inner.bottom - ui.small.get_linesize(), hint)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        rows = self._rows()
        if event.sym == KeySym.TAB:
            self.mode = "sell" if self.mode == "buy" else "buy"
            self.cursor = 0
            return None
        if rows:
            if event.sym in (KeySym.UP, KeySym.k):
                self.cursor = (self.cursor - 1) % len(rows)
                return None
            if event.sym in (KeySym.DOWN, KeySym.j):
                self.cursor = (self.cursor + 1) % len(rows)
                return None
            if event.sym in CONFIRM_KEYS:
                if self.mode == "buy":
                    self._buy()
                else:
                    whole = bool(event.mod & Modifier.SHIFT)
                    self._sell(whole_stack=whole)
                return None
        if event.sym == KeySym.ESCAPE:
            self.engine.event_handler = MainGameEventHandler(self.engine)
            return self.engine.event_handler
        return None

    def _buy(self) -> None:
        import copy
        item = self.stock[self.cursor]
        price = item.value
        hero = self.engine.player.hero
        inv = self.engine.player.inventory
        if hero.coins < price:
            self.engine.message_log.add_message("You cannot afford that.", color.impossible)
            return
        clone = copy.deepcopy(item)
        clone.quantity = 1
        try:
            inv.add(clone)
        except Impossible as exc:
            self.engine.message_log.add_message(str(exc), color.impossible)
            return
        hero.coins -= price
        self.engine.message_log.add_message(
            f"You buy the {item.name} for {price} coins.", color.item_c)

    def _sell(self, whole_stack: bool) -> None:
        from lonelands import content
        rows = self._rows()
        if not rows:
            return
        item = rows[self.cursor][0]
        hero = self.engine.player.hero
        inv = self.engine.player.inventory
        unit = content.sell_price(item)
        count = item.quantity if (whole_stack and item.stackable) else 1
        gained = unit * count
        # Selling worn gear: take it off first.
        eq = self.engine.player.equipment
        if eq and eq.item_is_equipped(item):
            eq.toggle_equip(item, add_message=False)
        if item.stackable and item.quantity > count:
            item.quantity -= count
        else:
            inv.remove(item)
        hero.coins += gained
        noun = item.name if count == 1 else f"{count}× {item.name}"
        self.engine.message_log.add_message(
            f"You sell {noun} for {gained} coins.", color.gold_c)
        if self.cursor >= len(self._rows()) and self.cursor > 0:
            self.cursor -= 1


# ===========================================================================
# Main menu / title
# ===========================================================================
TITLE_ART = [
    "The Lonelands",
    "",
    "A Ranger of the North, alone upon the roads of Eriador",
    "in the year 2965 of the Third Age.",
]


class MainMenuHandler(BaseEventHandler):
    def on_render(self, console: "Console") -> None:
        console.rgb["bg"] = color.near_black  # the title page is drawn natively

    def on_render_native(self, display) -> None:
        from lonelands import savegame
        ui = display.ui
        cx = display.win_w // 2
        y = int(display.win_h * 0.17)
        ui.text_center(cx, y, TITLE_ART[0], color.menu_title, ui.title)
        y += ui.title.get_linesize() + ui.pad
        for line in TITLE_ART[2:]:
            ui.text_center(cx, y, line, color.menu_text, ui.subtitle)
            y += ui.subtitle.get_linesize()

        options = []
        if savegame.has_save():
            options.append("[C]  Continue your journey")
        options.append("[N]  Take up the grey cloak — new game")
        options.append("[Q]  Depart")
        y = int(display.win_h * 0.5)
        for o in options:
            ui.text_center(cx, y, o, color.selected, ui.subtitle)
            y += ui.subtitle.get_linesize() + ui.pad // 2
        ui.hint(cx, display.win_h - ui.line * 2,
                "A Middle-earth roguelike · the Third Age, 2965 · d20 core")

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        from lonelands import savegame, setup_game
        if event.sym in (KeySym.q, KeySym.ESCAPE):
            raise SystemExit()
        if event.sym in (KeySym.c,) and savegame.has_save():
            try:
                engine = savegame.load_game()
            except Exception as exc:  # a corrupt or incompatible save
                traceback.print_exc()
                return PopupMessage(self, f"Failed to load save:\n{exc}")
            return MainGameEventHandler(engine)
        if event.sym in (KeySym.n, KeySym.RETURN, KeySym.KP_ENTER):
            return DifficultySelectHandler()
        return None


class DifficultySelectHandler(BaseEventHandler):
    """Chosen before a new game begins: the peril of the road ahead. The pick
    only scales the damage the player takes (see config.DIFFICULTIES)."""

    def on_render(self, console: "Console") -> None:
        console.rgb["bg"] = color.near_black  # drawn natively

    def on_render_native(self, display) -> None:
        from lonelands import config
        ui = display.ui
        cx = display.win_w // 2
        y = int(display.win_h * 0.2)
        ui.text_center(cx, y, "How hard is the road?", color.menu_title, ui.title)
        y += ui.title.get_linesize() + ui.pad * 2
        for i, (key, name, _mult, blurb) in enumerate(config.DIFFICULTIES):
            fg = color.selected if key == config.DEFAULT_DIFFICULTY else color.menu_text
            ui.text_center(cx, y, f"[{i + 1}]  {name}", fg, ui.subtitle)
            y += ui.subtitle.get_linesize()
            ui.text_center(cx, y, blurb, color.gray, ui.small)
            y += ui.small.get_linesize() + ui.pad
        ui.hint(cx, display.win_h - ui.line * 2, "Press 1–3 to set out · [Esc] back")

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        from lonelands import config, setup_game
        if event.sym == KeySym.ESCAPE:
            return MainMenuHandler()
        choice = {KeySym.N1: 0, KeySym.KP_1: 0, KeySym.N2: 1, KeySym.KP_2: 1,
                  KeySym.N3: 2, KeySym.KP_3: 2}.get(event.sym)
        if choice is not None and choice < len(config.DIFFICULTIES):
            key = config.DIFFICULTIES[choice][0]
            engine = setup_game.new_game(difficulty=key)
            return MainGameEventHandler(engine)
        return None
