from __future__ import annotations

import textwrap
import traceback
from typing import TYPE_CHECKING, List, Optional, Tuple

import tcod

from lonelands import actions, character, color, perks
from lonelands.render_functions import (
    draw_filled_bar,
    draw_section,
    endurance_color,
)
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
    from lonelands.engine import Engine
    from lonelands.entity import Actor, Item

KeySym = tcod.event.KeySym

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
# which double as letter accelerators in the perk and ability lists.
_CURSOR_UP = {KeySym.UP, KeySym.KP_8}
_CURSOR_DOWN = {KeySym.DOWN, KeySym.KP_2}


# ===========================================================================
# Base handlers
# ===========================================================================
class BaseEventHandler(tcod.event.EventDispatch["BaseEventHandler"]):
    def handle_events(self, event: tcod.event.Event) -> "BaseEventHandler":
        state = self.dispatch(event)
        if isinstance(state, BaseEventHandler):
            return state
        return self

    def on_render(self, console: tcod.console.Console) -> None:
        raise NotImplementedError()

    def ev_quit(self, event: tcod.event.Quit) -> Optional["BaseEventHandler"]:
        raise SystemExit()

    def ev_mousemotion(self, event: tcod.event.MouseMotion) -> Optional["BaseEventHandler"]:
        return None


class PopupMessage(BaseEventHandler):
    def __init__(self, parent: BaseEventHandler, text: str):
        self.parent = parent
        self.text = text

    def on_render(self, console: tcod.console.Console) -> None:
        self.parent.on_render(console)
        console.rgb["fg"] //= 4
        console.rgb["bg"] //= 4
        console.print(
            SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, self.text,
            fg=color.white, bg=color.black, alignment=tcod.constants.CENTER,
        )

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        return self.parent


class EventHandler(BaseEventHandler):
    def __init__(self, engine: "Engine"):
        self.engine = engine

    def handle_events(self, event: tcod.event.Event) -> BaseEventHandler:
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
        # A player turn has passed: advance perk cooldowns/stances, then foes act.
        hero = getattr(self.engine.player, "hero", None)
        if hero is not None:
            hero.end_player_turn()
        self.engine.handle_enemy_turns()
        self.engine.update_fov()
        return True

    def ev_mousemotion(self, event: tcod.event.MouseMotion) -> None:
        if self.engine.game_map.in_bounds(event.tile.x, event.tile.y):
            self.engine.mouse_location = (event.tile.x, event.tile.y)

    def on_render(self, console: tcod.console.Console) -> None:
        self.engine.render(console)


# ===========================================================================
# Main game
# ===========================================================================
class MainGameEventHandler(EventHandler):
    def __init__(self, engine: "Engine"):
        super().__init__(engine)
        engine.event_handler = self

    def ev_keydown(self, event: tcod.event.KeyDown):
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
        if key == KeySym.q:
            return QuestScreenHandler(self.engine)
        if key in (KeySym.SLASH, KeySym.QUESTION):
            return HelpHandler(self.engine)
        if key == KeySym.ESCAPE:
            return EscapeMenuHandler(self.engine)
        return None

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
            console.rgb["bg"][target.x, target.y] = color.needs_target
            console.rgb["fg"][target.x, target.y] = color.near_black
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


class GameOverEventHandler(EventHandler):
    def on_render(self, console: tcod.console.Console) -> None:
        self.engine.render(console)
        console.rgb["fg"] //= 3
        console.rgb["bg"] //= 3
        cx, cy = MAP_WIDTH // 2, MAP_HEIGHT // 2
        console.print(cx, cy - 1, "Here ends the road.", fg=color.player_die,
                      alignment=tcod.constants.CENTER)
        console.print(cx, cy + 1, "[Enter] to return to the title    [Esc] to quit",
                      fg=color.gray, alignment=tcod.constants.CENTER)

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
    def on_render(self, console: tcod.console.Console) -> None:
        # Draw the game, then quiet it: a popup always reads as the top layer
        # (CONTEXT.md "Scrim"). Subclasses call super() then paint their panel
        # on top at full brightness.
        super().on_render(console)
        _scrim(console)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        if event.sym in (KeySym.ESCAPE,) or event.sym in CONFIRM_KEYS:
            return self.on_exit()
        return None

    def on_exit(self) -> Optional[BaseEventHandler]:
        self.engine.event_handler = MainGameEventHandler(self.engine)
        return self.engine.event_handler


def _scrim(console) -> None:
    """Dim the whole console to ~37% so an open popup reads as the top layer.

    Divide-then-multiply keeps the arithmetic inside uint8 (a bare ``* 3`` would
    overflow); the small precision loss is invisible at this brightness.
    """
    console.rgb["fg"] = (console.rgb["fg"] // 8) * 3
    console.rgb["bg"] = (console.rgb["bg"] // 8) * 3


def _panel(console, x, y, w, h, title):
    console.draw_frame(x, y, w, h, clear=True, fg=color.frame_bright, bg=color.panel_bg)
    if title:
        console.print(x + 2, y, f" {title} ", fg=color.menu_title)


# ===========================================================================
# Inventory
# ===========================================================================
class InventorySelectHandler(AskUserHandler):
    title = "Inventory"

    def __init__(self, engine: "Engine"):
        super().__init__(engine)
        self.cursor = 0

    def on_render(self, console: tcod.console.Console) -> None:
        super().on_render(console)
        items = self.engine.player.inventory.items
        h = max(6, len(items) + 4)
        w = 72
        x, y = 4, 4
        _panel(console, x, y, w, h, self.title)
        ix, iw = x + 2, w - 4
        if not items:
            console.print(ix, y + 2, "(your pack is empty)", fg=color.tier_label)
        else:
            self.cursor = max(0, min(self.cursor, len(items) - 1))
            eq = self.engine.player.equipment
            for i, item in enumerate(items):
                cy = y + 2 + i
                key = chr(ord("a") + i)
                sel = i == self.cursor
                if sel:  # the selection filled bar
                    console.draw_rect(ix, cy, iw, 1, ord(" "), bg=color.bar_accent)
                head = f"{item.char} {item.name}{item.count_label}"
                worn = " (worn)" if eq.item_is_equipped(item) else ""
                stats = (f"  [{item.equippable.stat_line()}]"
                         if item.equippable is not None else "")
                console.print(ix, cy, f"({key})", fg=color.tier_label)
                console.print(ix + 4, cy, head,
                              fg=color.tier_value if sel else color.tier_body)
                if worn or stats:
                    console.print(ix + 4 + len(head), cy, f"{worn}{stats}",
                                  fg=color.tier_label)
        console.print(ix, y + h - 1,
                      " up/down move · Enter use/equip · a-z select · Esc close ",
                      fg=color.tier_label)

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

    def on_render(self, console: tcod.console.Console) -> None:
        super().on_render(console)  # scrim applied by AskUserHandler
        hero = self.engine.player.hero
        f = self.engine.player.fighter
        w, h = 60, 31
        x, y = 4, 3
        _panel(console, x, y, w, h, "Character")
        ix, iw = x + 2, w - 4
        cy = y + 2

        # Identity — the one filled bar (the hero-name header).
        ident = f"{self.engine.player.name} · {hero.culture} · {hero.calling}"
        draw_filled_bar(console, ix, cy, iw, ident)
        if hero.true_name:
            cy += 1
            console.print(ix, cy, hero.true_name, fg=color.ranger_green)
        cy += 2

        # Advancement strip — label dim, value bright; Perk points glow gold
        # only while there are points to spend.
        xp = f"{hero.xp}/{hero.xp_to_next}"
        console.print(ix, cy, "Level", fg=color.tier_label)
        console.print(ix + 6, cy, str(hero.level), fg=color.tier_value)
        console.print(ix + 12, cy, "XP", fg=color.tier_label)
        console.print(ix + 15, cy, xp, fg=color.tier_value)
        console.print(ix + 16 + len(xp), cy, "to next", fg=color.tier_label)
        cy += 1
        pp = hero.perk_points
        console.print(ix, cy, "Perk points", fg=color.tier_label)
        console.print(ix + 12, cy, str(pp),
                      fg=color.hope_gain if pp else color.tier_body)
        console.print(ix + 24, cy, "Coins", fg=color.tier_label)
        console.print(ix + 30, cy, str(hero.coins), fg=color.gold_c)
        cy += 2

        # ATTRIBUTES
        cy = draw_section(console, ix, cy, iw, "ATTRIBUTES")
        for attr in character.ATTRIBUTES:
            console.print(ix + 2, cy, attr, fg=color.tier_body)
            console.print(ix + 9, cy, f"{hero.modifier(attr):+d}", fg=color.tier_value)
            console.print(ix + 14, cy, self._ATTR_GOVERNS.get(attr, ""),
                          fg=color.tier_label)
            cy += 1
        cy += 1

        # IN THE FIELD
        cy = draw_section(console, ix, cy, iw, "IN THE FIELD")
        console.print(ix + 2, cy, "Endurance", fg=color.tier_body)
        console.print(ix + 14, cy, f"{f.endurance}/{f.max_endurance}",
                      fg=endurance_color(f.endurance, f.max_endurance))
        cy += 1
        console.print(ix + 2, cy, "Defence", fg=color.tier_label)
        console.print(ix + 10, cy, str(f.defence), fg=color.tier_value)
        console.print(ix + 14, cy, "Attack", fg=color.tier_label)
        console.print(ix + 21, cy, f"+{f.attack_bonus}", fg=color.tier_value)
        console.print(ix + 26, cy, "Soak", fg=color.tier_label)
        console.print(ix + 31, cy, str(f.soak), fg=color.tier_value)
        console.print(ix + 35, cy, "Load", fg=color.tier_label)
        console.print(ix + 40, cy, str(hero.load), fg=color.tier_value)
        cy += 1
        console.print(ix + 2, cy, "Wielding", fg=color.tier_label)
        console.print(ix + 14, cy, f.weapon_name, fg=color.weapon_c)
        if hero.is_weary:
            cy += 1
            console.print(ix + 2, cy, "Weary — burdened past your vigour.",
                          fg=color.enemy_atk)
        cy += 2

        # PATHS
        cy = draw_section(console, ix, cy, iw, "PATHS")
        owned = hero.perks
        for path in perks.PATHS:
            count = sum(1 for pk in path.perks if pk.id in owned)
            console.print(ix + 2, cy, f"{path.name:<20}",
                          fg=color.ranger_green if count else color.tier_label)
            console.print(ix + 24, cy, f"{count}/{len(path.perks)}",
                          fg=color.tier_value if count else color.tier_label)
            cy += 1

        console.print(ix, y + h - 1,
                      " p Paths & perks · a abilities · Esc close ",
                      fg=color.tier_label)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        if event.sym == KeySym.p:
            return PathsHandler(self.engine)
        if event.sym == KeySym.a:
            return AbilitiesHandler(self.engine)
        return super().ev_keydown(event)


# ===========================================================================
# Paths & perks (issue #38)
# ===========================================================================
class PathsHandler(AskUserHandler):
    """Buy perks across the five Ranger Paths. Each perk gets a letter; press it
    to buy when it is affordable and its in-Path prerequisites (and capstone
    gating) are met. A Ranger blends freely across Paths."""

    def __init__(self, engine: "Engine"):
        super().__init__(engine)
        self.cursor = 0

    def _perk_list(self) -> List["perks.Perk"]:
        return [pk for path in perks.PATHS for pk in path.perks]

    @staticmethod
    def _locked_reason(hero, pk) -> str:
        if hero.perk_points < pk.cost:
            return "need pts"
        if not perks.prerequisites_met(pk, hero.perks):
            return "capstone locked" if pk.capstone else "prereq needed"
        return "-"

    def on_render(self, console) -> None:
        super().on_render(console)
        hero = self.engine.player.hero
        self.cursor = max(0, min(self.cursor, len(self._perk_list()) - 1))
        w, h = 78, 49
        x, y = 2, 2
        _panel(console, x, y, w, h, "Paths of the Ranger")
        ix, iw = x + 2, w - 4
        console.print(ix, y + 1, "Perk points", fg=color.tier_label)
        console.print(ix + 12, y + 1, str(hero.perk_points),
                      fg=color.hope_gain if hero.perk_points else color.tier_body)
        console.print(ix + 16, y + 1, "* capstone · blend freely across Paths",
                      fg=color.tier_label)
        cy = y + 3
        idx = 0
        for path in perks.PATHS:
            cy = draw_section(console, ix, cy, iw, path.name.upper())
            console.print(ix, cy, path.blurb, fg=color.tier_label)
            cy += 1
            for pk in path.perks:
                letter = chr(ord("a") + idx)
                sel = idx == self.cursor
                if hero.has_perk(pk.id):
                    status, scol = "owned", color.ranger_green
                elif hero.can_buy(pk):
                    status, scol = f"BUY ({pk.cost}pp)", color.selected
                else:
                    status, scol = self._locked_reason(hero, pk), color.tier_label
                tag = "*" if pk.capstone else " "
                if sel:  # the selection filled bar
                    console.draw_rect(ix, cy, iw, 1, ord(" "), bg=color.bar_accent)
                if hero.has_perk(pk.id):
                    name_col = color.ranger_green
                elif sel:
                    name_col = color.tier_value
                else:
                    name_col = color.tier_body
                console.print(ix, cy, f"({letter}){tag}", fg=color.tier_label)
                console.print(ix + 4, cy, f"{pk.name:<18}", fg=name_col)
                console.print(ix + 23, cy, f"T{pk.tier} {pk.cost}pp",
                              fg=color.tier_label)
                console.print(ix + 32, cy, f"{status:<15}", fg=scol)
                console.print(ix + 48, cy, pk.desc[:iw - 48],
                              fg=color.tier_body if sel else color.tier_label)
                cy += 1
                idx += 1
            cy += 1
        console.print(ix, y + h - 1,
                      " up/down move · Enter buy · a-t buy · Esc close ",
                      fg=color.tier_label)

    def _buy(self, pk) -> None:
        hero = self.engine.player.hero
        if hero.has_perk(pk.id):
            self.engine.message_log.add_message(
                f"You already walk that road ({pk.name}).", color.invalid)
        elif hero.buy_perk(pk):
            self.engine.message_log.add_message(
                f"You take up {pk.name}. {pk.desc}", color.xp_filled)
        else:
            self.engine.message_log.add_message(
                f"You cannot take {pk.name} yet.", color.impossible)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        rows = self._perk_list()
        if event.sym in _CURSOR_UP:
            self.cursor = (self.cursor - 1) % len(rows)
            return None
        if event.sym in _CURSOR_DOWN:
            self.cursor = (self.cursor + 1) % len(rows)
            return None
        if event.sym in CONFIRM_KEYS:
            self._buy(rows[self.cursor])
            return None
        index = event.sym - KeySym.a
        if 0 <= index < len(rows):
            self._buy(rows[index])
            return None
        return super().ev_keydown(event)


class AbilitiesHandler(AskUserHandler):
    """List the hero's owned Path actives with their charge/cooldown state and
    fire a ready one. Firing produces an ActivateAbilityAction (a full turn):
    heal/stance resolve at once, a Wrath-style active primes the next melee hit."""

    def __init__(self, engine: "Engine"):
        super().__init__(engine)
        self.cursor = 0

    def on_render(self, console) -> None:
        super().on_render(console)
        hero = self.engine.player.hero
        actives = hero.actives()
        w = 60
        h = max(7, len(actives) + 5)
        x, y = 4, 4
        _panel(console, x, y, w, h, "Deeds & Abilities")
        ix, iw = x + 2, w - 4
        if not actives:
            console.print(ix, y + 2,
                          "You have learned no active deeds yet.", fg=color.tier_label)
        else:
            self.cursor = max(0, min(self.cursor, len(actives) - 1))
            for i, pk in enumerate(actives):
                cy = y + 2 + i
                letter = chr(ord("a") + i)
                cd = hero.cooldown_left(pk.id)
                if hero.is_primed(pk.id):
                    state, scol = "primed", color.hope_gain
                elif cd > 0:
                    state, scol = f"cooldown {cd}", color.tier_label
                else:
                    state, scol = "ready", color.end_full
                sel = i == self.cursor
                if sel:  # the selection filled bar
                    console.draw_rect(ix, cy, iw, 1, ord(" "), bg=color.bar_accent)
                console.print(ix, cy, f"({letter})", fg=color.tier_label)
                console.print(ix + 4, cy, pk.active.name,
                              fg=color.tier_value if sel else color.tier_body)
                console.print(ix + 21, cy, state, fg=scol)
                console.print(ix + 33, cy, pk.desc[:iw - 33],
                              fg=color.tier_body if sel else color.tier_label)
        console.print(ix, y + h - 1,
                      " up/down move · Enter use · a-z use · Esc close ",
                      fg=color.tier_label)

    def _use(self, pk) -> Optional[BaseEventHandler]:
        hero = self.engine.player.hero
        if not hero.ability_ready(pk.id):
            self.engine.message_log.add_message(
                f"{pk.active.name} is not ready.", color.impossible)
            return None
        self.handle_action(ActivateAbilityAction(self.engine.player, pk.id))
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
    def on_render(self, console) -> None:
        super().on_render(console)
        w, h = 60, 40
        x, y = 4, 4
        _panel(console, x, y, w, h, "Errands & Tidings")
        ix, iw = x + 2, w - 4
        quests = list(self.engine.quest_log.quests.values())
        cy = y + 2
        shown = [q for q in quests if q.state.name != "UNSTARTED"]
        if not shown:
            console.print(ix, cy, "You carry no errands yet. Seek out the folk of Bree.",
                          fg=color.tier_label)
        for q in shown:
            head_col = {
                "DONE": color.health_recovered,
                "READY": color.hope_gain,
            }.get(q.state.name, color.section_head)
            console.print(ix, cy, q.status_line(), fg=head_col)
            cy += 1
            for line in textwrap.wrap(q.summary, iw - 2):
                console.print(ix + 2, cy, line, fg=color.white)  # prose: read it
                cy += 1
            cy += 1
        console.print(ix, y + h - 1, " Esc close ", fg=color.tier_label)


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
g          pick up what lies underfoot
i          use or equip from your pack
d          set down an item
c          your character sheet
p          your Paths & perks — spend perk points
a          your active deeds (abilities on cooldown/charge)
q          your errands and tidings
?          this help
Esc        the wayfarer's menu

THE ROLL   Deeds are tested with a d20 plus an attribute (Brawn, Wits, or
           Will) against a Target Number. A natural 20 is a Critical; a
           natural 1 a Fumble. Slaying foes grants XP; levels come often,
           each granting +HP, a periodic +to-hit, and now and then a perk point.

THE BOW    A bow rides the ranged slot beside your melee weapon — no swap.
           A Shot is keyed off Wits and spends an arrow; it flies true within
           the bow's range, then falls off past it, and a foe at your elbow
           spoils the aim. Half your arrows can be gathered up again (g).

VITALS     Endurance is your vigour — at 0 you fall. Grow Weary as burdens
           mount past your strength; a Bleed wound worsens each round until
           it's staunched. Athelas mends flesh and stops the bleeding.
"""


class HelpHandler(AskUserHandler):
    def on_render(self, console) -> None:
        super().on_render(console)
        lines = HELP_TEXT.strip("\n").splitlines()
        w, h = 68, len(lines) + 4  # size to the content so nothing spills
        x, y = 6, 3
        _panel(console, x, y, w, h, "Lore of the Wayfarer")
        for i, line in enumerate(lines):
            # The heading line reads as a caption; the rest is prose to read.
            col = color.section_head if i == 0 else color.white
            console.print(x + 2, y + 2 + i, line, fg=col)
        console.print(x + 2, y + h - 1, " any key to close ", fg=color.tier_label)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        return self.on_exit()


# ===========================================================================
# Escape menu
# ===========================================================================
class EscapeMenuHandler(AskUserHandler):
    def on_render(self, console) -> None:
        super().on_render(console)
        w, h = 36, 12
        x, y = MAP_WIDTH // 2 - w // 2, MAP_HEIGHT // 2 - h // 2
        _panel(console, x, y, w, h, "The wayfarer pauses")
        ix = x + 2
        for i, (key, desc) in enumerate((
            ("[Enter]", "return to the road"),
            ("[S]", "save and continue"),
            ("[T]", "save & quit to title"),
            ("[Q]", "quit to the outer dark"),
        )):
            cy = y + 2 + i * 2
            console.print(ix, cy, key, fg=color.section_head)
            console.print(ix + 9, cy, desc, fg=color.tier_body)

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

    def _node(self):
        return self.npc.tree[self.node_id]

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
        self.engine.render(console)
        _scrim(console)  # a popup reads as the top layer (CONTEXT.md "Scrim")
        w = 72
        x = (SCREEN_WIDTH - w) // 2
        text_lines: List[str] = []
        for para in self._text().split("\n"):
            text_lines.extend(textwrap.wrap(para, w - 4) or [""])
        opts = self._visible_options()
        self.cursor = max(0, min(self.cursor, len(opts) - 1)) if opts else 0
        h = len(text_lines) + len(opts) + 6
        y = SCREEN_HEIGHT - h - 2
        _panel(console, x, y, w, h, f"{self.speaker.name} — {self.npc.title}")
        ix, iw = x + 2, w - 4
        cy = y + 2
        for line in text_lines:
            console.print(ix, cy, line, fg=color.white)  # speech is prose: read it
            cy += 1
        cy += 1
        for i, o in enumerate(opts):
            sel = i == self.cursor
            if sel:  # the selection filled bar
                console.draw_rect(ix, cy, iw, 1, ord(" "), bg=color.bar_accent)
            marker = "›" if sel else " "
            console.print(ix, cy, f"{marker}{i + 1}.", fg=color.tier_label)
            console.print(ix + 4, cy, o["text"][:iw - 4],
                          fg=color.tier_value if sel else color.tier_body)
            cy += 1
        console.print(ix, y + h - 1,
                      " up/down move · Enter choose · number choose · Esc end ",
                      fg=color.tier_label)

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
        self.engine.render(console)
        rows = self._rows()
        w, h = 52, max(len(rows), 1) + 7
        x = (SCREEN_WIDTH - w) // 2
        y = 6
        _panel(console, x, y, w, h, self.title)
        hero = self.engine.player.hero
        verb = "Buy" if self.mode == "buy" else "Sell"
        console.print(x + 2, y + 1,
                      f"Your purse: {hero.coins} coins        [{verb}]", fg=color.gold_c)
        if not rows:
            console.print(x + 2, y + 3, "(nothing to sell)", fg=color.gray)
        for i, (item, price) in enumerate(rows):
            sel = i == self.cursor
            fg = color.selected if sel else color.menu_text
            if self.mode == "buy":
                afford = color.gold_c if hero.coins >= price else color.impossible
            else:
                afford = color.gold_c
            prefix = "> " if sel else "  "
            label = f"{prefix}{item.char} {item.name}{item.count_label}"
            console.print(x + 2, y + 3 + i, label[:w - 14], fg=fg)
            console.print(x + w - 10, y + 3 + i, f"{price:>3} c", fg=afford)
        hint = (" Tab buy/sell · Enter buy · Esc leave "
                if self.mode == "buy"
                else " Tab buy/sell · Enter sell 1 · Shift+Enter sell all · Esc leave ")
        console.print(x + 2, y + h - 1, hint, fg=color.gray)

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
                    whole = bool(event.mod & tcod.event.Modifier.SHIFT)
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
    def on_render(self, console: tcod.console.Console) -> None:
        console.rgb["bg"] = color.near_black
        cx = SCREEN_WIDTH // 2
        for i, line in enumerate(TITLE_ART):
            fg = color.menu_title if i == 0 else color.menu_text
            console.print(cx, 8 + i * 2, line, fg=fg, alignment=tcod.constants.CENTER)
        from lonelands import savegame
        options = []
        if savegame.has_save():
            options.append("[C]  Continue your journey")
        options.append("[N]  Take up the grey cloak — new game")
        options.append("[Q]  Depart")
        for i, o in enumerate(options):
            console.print(cx, 22 + i * 2, o, fg=color.selected,
                          alignment=tcod.constants.CENTER)
        console.print(cx, SCREEN_HEIGHT - 3,
                      "Powered by The One Ring · feat die + success dice",
                      fg=color.gray, alignment=tcod.constants.CENTER)

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

    def on_render(self, console: tcod.console.Console) -> None:
        from lonelands import config
        console.rgb["bg"] = color.near_black
        cx = SCREEN_WIDTH // 2
        console.print(cx, 8, "How hard is the road?", fg=color.menu_title,
                      alignment=tcod.constants.CENTER)
        row = 14
        for i, (_key, name, _mult, blurb) in enumerate(config.DIFFICULTIES):
            fg = color.selected if _key == config.DEFAULT_DIFFICULTY else color.menu_text
            console.print(cx, row, f"[{i + 1}]  {name}", fg=fg,
                          alignment=tcod.constants.CENTER)
            console.print(cx, row + 1, blurb, fg=color.gray,
                          alignment=tcod.constants.CENTER)
            row += 3
        console.print(cx, SCREEN_HEIGHT - 3,
                      "Press 1–3 to set out · [Esc] back",
                      fg=color.gray, alignment=tcod.constants.CENTER)

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
