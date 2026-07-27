from __future__ import annotations

import textwrap
import traceback
from typing import TYPE_CHECKING, List, Optional, Tuple


from lonelands import actions, character, color, events, overworld_map, perks
from lonelands.events import CENTER, KeySym, Modifier
from lonelands.tile_glyphs import graphic_char
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
# which double as letter accelerators in the perk and ability lists.
_CURSOR_UP = {KeySym.UP, KeySym.KP_8}
_CURSOR_DOWN = {KeySym.DOWN, KeySym.KP_2}


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
        console.rgb["fg"] //= 4
        console.rgb["bg"] //= 4

    def on_render_native(self, display) -> None:
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
        # A player turn has passed: advance perk cooldowns/stances, then foes act.
        hero = getattr(self.engine.player, "hero", None)
        if hero is not None:
            hero.end_player_turn()
        self.engine.handle_enemy_turns()
        self.engine.update_fov()
        return True

    def ev_mousemotion(self, event: "events.MouseMotion") -> None:
        if self.engine.game_map.in_bounds(event.tile.x, event.tile.y):
            self.engine.mouse_location = (event.tile.x, event.tile.y)

    def on_render(self, console: "Console") -> None:
        self.engine.render(console)


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
        if key == KeySym.m:
            return OverworldMapHandler(self.engine)
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
    def on_render(self, console: "Console") -> None:
        self.engine.render(console)
        console.rgb["fg"] //= 3
        console.rgb["bg"] //= 3
        cx, cy = MAP_WIDTH // 2, MAP_HEIGHT // 2
        console.print(cx, cy - 1, "Here ends the road.", fg=color.player_die,
                      alignment=CENTER)
        console.print(cx, cy + 1, "[Enter] to return to the title    [Esc] to quit",
                      fg=color.gray, alignment=CENTER)

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
    def on_render(self, console: "Console") -> None:
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


# ===========================================================================
# Inventory
# ===========================================================================
class InventorySelectHandler(AskUserHandler):
    title = "Inventory"

    def __init__(self, engine: "Engine"):
        super().__init__(engine)
        self.cursor = 0

    def on_render_native(self, display) -> None:
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
        pp = hero.perk_points
        ui.text(x, y, "Perk points", color.tier_label)
        ui.text(x + ui.measure("Perk points  ")[0], y, str(pp),
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

        # PATHS.
        y = ui.section(x, y, iw, "PATHS")
        owned = hero.perks
        for path in perks.PATHS:
            count = sum(1 for pk in path.perks if pk.id in owned)
            ui.text(x, y, path.name, color.ranger_green if count else color.tier_label)
            ui.text(c2, y, f"{count}/{len(path.perks)}",
                    color.tier_value if count else color.tier_label)
            y += ui.line

        ui.hint(display.win_w // 2, inner.bottom - ui.small.get_linesize(),
                "p Paths & perks · a abilities · Esc close")

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

    def on_render_native(self, display) -> None:
        ui = display.ui
        hero = self.engine.player.hero
        self.cursor = max(0, min(self.cursor, len(self._perk_list()) - 1))
        w, h = int(display.win_w * 0.84), int(display.win_h * 0.94)
        r = ui.centered(w, h)
        inner = ui.panel(r.x, r.y, r.w, r.h, "Paths of the Ranger")
        x, iw, y = inner.x, inner.w, inner.y
        ui.text(x, y, "Perk points", color.tier_label)
        px = x + ui.measure("Perk points  ")[0]
        px += ui.text(px, y, str(hero.perk_points),
                      color.hope_gain if hero.perk_points else color.tier_body)
        ui.text(px + ui.pad, y, "* capstone · blend freely across Paths", color.tier_label, ui.small)
        y += ui.line
        # A dense list: size a proportional font so every Path fits the panel
        # (2 lines of chrome per Path — header + blurb — plus one per perk).
        total_perks = sum(len(p.perks) for p in perks.PATHS)
        n_lines = len(perks.PATHS) * 2 + total_perks + 1
        # Reserve the footer row and the per-Path breathing gaps so prop_fit
        # sizes the rows to genuinely fit inside the panel.
        gaps = len(perks.PATHS) * (ui.pad // 4)
        avail = inner.bottom - y - ui.line - gaps
        font, step = ui.prop_fit(n_lines, avail)
        c_name = x + font.size("(a)*  ")[0]
        c_tier = x + int(iw * 0.26)
        c_stat = x + int(iw * 0.36)
        c_desc = x + int(iw * 0.54)
        idx = 0
        for path in perks.PATHS:
            ui.text(x, y, path.name.upper(), color.section_head, font)
            ui.hrule(x, y + step - 2, iw)
            y += step
            ui.text(x, y, path.blurb, color.tier_label, font)
            y += step
            for pk in path.perks:
                sel = idx == self.cursor
                if hero.has_perk(pk.id):
                    status, scol, name_col = "owned", color.ranger_green, color.ranger_green
                elif hero.can_buy(pk):
                    status, scol = f"BUY ({pk.cost}pp)", color.selected
                    name_col = color.tier_value if sel else color.tier_body
                else:
                    status, scol = self._locked_reason(hero, pk), color.tier_label
                    name_col = color.tier_value if sel else color.tier_body
                if sel:
                    ui.selection(x - ui.pad // 2, y, iw + ui.pad, step)
                tag = "*" if pk.capstone else " "
                ui.text(x, y, f"({chr(ord('a') + idx)}){tag}", color.tier_label, font)
                ui.text(c_name, y, pk.name, name_col, font)
                ui.text(c_tier, y, f"T{pk.tier} {pk.cost}pp", color.tier_label, font)
                ui.text(c_stat, y, status, scol, font)
                ui.text(c_desc, y, ui.truncate(pk.desc, inner.right - c_desc, font),
                        color.tier_body if sel else color.tier_label, font)
                y += step
                idx += 1
            y += ui.pad // 4
        ui.hint(display.win_w // 2, inner.bottom - ui.small.get_linesize(),
                "up/down move · Enter buy · a-t buy · Esc close")

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

    def on_render_native(self, display) -> None:
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
    def on_render_native(self, display) -> None:
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
g          pick up what lies underfoot
i          use or equip from your pack
d          set down an item
c          your character sheet
p          your Paths & perks — spend perk points
a          your active deeds (abilities on cooldown/charge)
q          your errands and tidings
M          the Overworld Map — all of Eriador at a glance
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
    def on_render_native(self, display) -> None:
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
    _GY = 2                                            # title sits on row 0

    def on_render(self, console: "Console") -> None:
        # A full-screen atlas: paint over the whole console rather than the game
        # + scrim, so the map reads as its own page.
        console.rgb["ch"] = ord(" ")
        console.rgb["fg"] = color.gray
        console.rgb["bg"] = color.near_black

        console.print(SCREEN_WIDTH // 2, 0, "The Ranger's Atlas — Eriador",
                      fg=color.menu_title, alignment=CENTER)

        gw = self.engine.game_world
        buf = overworld_map.render_map(gw.coord, self.cursor)
        self._blit(console, buf)
        self._render_legend(console, buf.height)
        self._render_footer(console, in_deeps=gw.level_index < 0)

    def _blit(self, console, buf) -> None:
        for r in range(buf.height):
            row_ch, row_fg, row_bg, row_g = buf.ch[r], buf.fg[r], buf.bg[r], buf.graphic[r]
            sy = self._GY + r
            for c in range(buf.width):
                ch = row_ch[c]
                string = graphic_char(ch) if row_g[c] else ch
                console.print(self._GX + c, sy, string,
                              fg=row_fg[c] or color.gray,
                              bg=row_bg[c] or color.near_black)

    def _render_legend(self, console, grid_h) -> None:
        y = self._GY + grid_h + 1
        for row, label_fg in ((overworld_map.band_legend(), color.tier_body),
                              (overworld_map.role_legend(), color.tier_label)):
            x = self._GX
            for entry in row:
                glyph = graphic_char(entry.glyph) if entry.graphic else entry.glyph
                console.print(x, y, glyph, fg=entry.fg)
                console.print(x + 2, y, entry.label, fg=label_fg)
                x += 4 + len(entry.label)
            y += 1

    def _render_footer(self, console, in_deeps) -> None:
        d = overworld_map.describe(self.cursor)
        y = self._GY + overworld_map.GRID_H + 4
        x = self._GX
        iw = overworld_map.GRID_W
        head = d.title
        if not d.off_grid and d.deeps:
            head += f"   {d.deeps} deep{'s' if d.deeps != 1 else ''} below"
        console.print(x, y, head, fg=color.section_head)
        y += 1
        for line in textwrap.wrap(d.note, iw):
            console.print(x, y, line, fg=color.tier_body)
            y += 1
        if in_deeps and self.cursor == self.engine.game_world.coord:
            console.print(x, y, "You are below the surface here.", fg=color.ambient)
        console.print(self._GX, SCREEN_HEIGHT - 1,
                      " arrows/hjkl move · M or Esc close ", fg=color.tier_label)

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
# Escape menu
# ===========================================================================
class EscapeMenuHandler(AskUserHandler):
    def on_render_native(self, display) -> None:
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
        self.engine.render(console)
        _scrim(console)  # a popup reads as the top layer (CONTEXT.md "Scrim")

    def on_render_native(self, display) -> None:
        ui = display.ui
        opts = self._visible_options()
        self.cursor = max(0, min(self.cursor, len(opts) - 1)) if opts else 0
        w = int(display.win_w * 0.72)
        text_lines = ui.wrap(self._text(), w - ui.pad * 2)
        h = (ui.pad * 3 + ui.head.get_linesize() + len(text_lines) * ui.line
             + ui.pad + len(opts) * ui.line + ui.line)
        x = (display.win_w - w) // 2
        # Anchor near the bottom, but never let a long speech run off the top.
        y = max(ui.pad, display.win_h - h - int(display.win_h * 0.05))
        inner = ui.panel(x, y, w, int(h), f"{self.speaker.name} — {self.npc.title}")
        cx, cy = inner.x, inner.y
        for line in text_lines:  # speech is prose: read it
            ui.text(cx, cy, line, color.white)
            cy += ui.line
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
        self.engine.render(console)
        _scrim(console)  # a popup reads as the top layer (CONTEXT.md "Scrim")

    def on_render_native(self, display) -> None:
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
                "Powered by The One Ring · feat die + success dice")

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
