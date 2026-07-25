from __future__ import annotations

import textwrap
import traceback
from typing import TYPE_CHECKING, List, Optional, Tuple

import tcod

from lonelands import actions, color, tor
from lonelands.render_functions import render_pips
from lonelands.actions import (
    Action,
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

        if key == KeySym.g:
            return PickupAction(player)
        if key == KeySym.i:
            return InventoryActivateHandler(self.engine)
        if key == KeySym.d:
            return InventoryDropHandler(self.engine)
        if key == KeySym.c:
            return CharacterScreenHandler(self.engine)
        if key == KeySym.q:
            return QuestScreenHandler(self.engine)
        if key in (KeySym.SLASH, KeySym.QUESTION):
            return HelpHandler(self.engine)
        if key == KeySym.ESCAPE:
            return EscapeMenuHandler(self.engine)
        return None


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
    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        if event.sym in (KeySym.ESCAPE,) or event.sym in CONFIRM_KEYS:
            return self.on_exit()
        return None

    def on_exit(self) -> Optional[BaseEventHandler]:
        self.engine.event_handler = MainGameEventHandler(self.engine)
        return self.engine.event_handler


def _panel(console, x, y, w, h, title):
    console.draw_frame(x, y, w, h, clear=True, fg=color.frame_bright, bg=color.near_black)
    if title:
        console.print(x + 2, y, f" {title} ", fg=color.menu_title)


# ===========================================================================
# Inventory
# ===========================================================================
class InventorySelectHandler(AskUserHandler):
    title = "Inventory"

    def on_render(self, console: tcod.console.Console) -> None:
        super().on_render(console)
        items = self.engine.player.inventory.items
        h = max(6, len(items) + 4)
        w = 48
        x, y = 4, 4
        _panel(console, x, y, w, h, self.title)
        if not items:
            console.print(x + 2, y + 2, "(your pack is empty)", fg=color.gray)
        else:
            eq = self.engine.player.equipment
            for i, item in enumerate(items):
                key = chr(ord("a") + i)
                worn = " (worn)" if eq.item_is_equipped(item) else ""
                console.print(x + 2, y + 2 + i, f"({key}) {item.char} {item.name}{worn}",
                              fg=color.menu_text)
        console.print(x + 2, y + h - 1, " a-z use/equip · Esc close ", fg=color.gray)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        index = event.sym - KeySym.a
        if 0 <= index <= 26:
            try:
                item = self.engine.player.inventory.items[index]
            except IndexError:
                self.engine.message_log.add_message("No such item.", color.invalid)
                return None
            return self.on_item_selected(item)
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
    def on_render(self, console: tcod.console.Console) -> None:
        super().on_render(console)
        hero = self.engine.player.hero
        w, h = 62, 40
        x, y = 4, 3
        _panel(console, x, y, w, h, f"{self.engine.player.name} — Character")
        cy = y + 2
        lineage = f"{hero.true_name} · " if hero.true_name else ""
        console.print(x + 2, cy, f"{lineage}{hero.culture} · {hero.calling}",
                      fg=color.ranger_green)
        cy += 1
        console.print(x + 2, cy, f"Valour {hero.valour}   Wisdom {hero.wisdom}   "
                                 f"Hope {hero.hope}/{hero.max_hope}   Coins {hero.coins}",
                      fg=color.menu_text)
        cy += 1
        console.print(x + 2, cy, f"Experience unspent: {hero.xp}   "
                                 f"(raise skills with [+] keys below)", fg=color.xp_filled)
        cy += 2

        for attr in tor.ATTRIBUTES:
            console.print(x + 2, cy, f"{attr}  {hero.attributes[attr]}  "
                                     f"(TN {hero.attr_tn(attr)})", fg=color.menu_title)
            cy += 1
            for skill in tor.SKILL_GROUPS[attr]:
                rk = hero.skills[skill]
                cost = hero.cost_to_raise_skill(skill)
                console.print(x + 4, cy, f"{skill:<11}", fg=color.menu_text)
                render_pips(console, x + 15, cy, rk, skill=skill)
                console.print(x + 22, cy, f"  raise: {cost}xp", fg=color.menu_text)
                cy += 1
            cy += 1

        # Proficiencies
        console.print(x + 2, cy, "Weapon proficiencies", fg=color.menu_title)
        cy += 1
        for prof in tor.PROFICIENCIES:
            rk = hero.proficiencies[prof]
            console.print(x + 4, cy, f"{prof:<11}", fg=color.menu_text)
            render_pips(console, x + 15, cy, rk, fill=color.pip_prof)
            console.print(x + 22, cy, f"  raise: {hero.cost_to_raise_prof(prof)}xp",
                          fg=color.menu_text)
            cy += 1
        console.print(x + 2, y + h - 1,
                      " Advancement: open [A] to spend experience · Esc close ", fg=color.gray)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        if event.sym == KeySym.a:
            self.engine.event_handler = AdvancementHandler(self.engine)
            return self.engine.event_handler
        return super().ev_keydown(event)


class AdvancementHandler(AskUserHandler):
    """Spend experience to raise skills and proficiencies."""

    def __init__(self, engine: "Engine"):
        super().__init__(engine)
        self.cursor = 0
        self.rows = [("skill", s) for s in tor.ALL_SKILLS] + \
                    [("prof", p) for p in tor.PROFICIENCIES]

    def on_render(self, console) -> None:
        super().on_render(console)
        hero = self.engine.player.hero
        w, h = 52, len(self.rows) + 6
        x, y = 6, 2
        _panel(console, x, y, w, h, "Advancement — spend experience")
        console.print(x + 2, y + 1, f"Unspent experience: {hero.xp}", fg=color.xp_filled)
        for i, (kind, name) in enumerate(self.rows):
            if kind == "skill":
                rk = hero.skills[name]
                cost = hero.cost_to_raise_skill(name)
            else:
                rk = hero.proficiencies[name]
                cost = hero.cost_to_raise_prof(name)
            sel = i == self.cursor
            fg = color.selected if sel else color.menu_text
            prefix = "> " if sel else "  "
            label = name if kind == "skill" else name + "*"
            affordable = "" if rk >= 6 else f"  ({cost}xp)"
            row = y + 3 + i
            console.print(x + 2, row, f"{prefix}{label:<12}", fg=fg)
            pip_fill = color.pip_prof if kind == "prof" else None
            render_pips(console, x + 16, row, rk, skill=name, fill=pip_fill)
            console.print(x + 23, row, affordable, fg=fg)
        console.print(x + 2, y + h - 1, " ↑/↓ move · Enter raise · Esc close ", fg=color.gray)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        if event.sym in (KeySym.UP, KeySym.k):
            self.cursor = (self.cursor - 1) % len(self.rows)
            return None
        if event.sym in (KeySym.DOWN, KeySym.j):
            self.cursor = (self.cursor + 1) % len(self.rows)
            return None
        if event.sym in CONFIRM_KEYS:
            kind, name = self.rows[self.cursor]
            hero = self.engine.player.hero
            ok = hero.raise_skill(name) if kind == "skill" else hero.raise_prof(name)
            if ok:
                self.engine.message_log.add_message(
                    f"Through long practice, your {name} improves.", color.status_effect_applied)
            else:
                self.engine.message_log.add_message(
                    "Not enough experience for that yet.", color.impossible)
            return None
        if event.sym == KeySym.ESCAPE:
            return self.on_exit()
        return None


# ===========================================================================
# Quest screen
# ===========================================================================
class QuestScreenHandler(AskUserHandler):
    def on_render(self, console) -> None:
        super().on_render(console)
        w, h = 60, 40
        x, y = 4, 4
        _panel(console, x, y, w, h, "Errands & Tidings")
        quests = list(self.engine.quest_log.quests.values())
        cy = y + 2
        shown = [q for q in quests if q.state.name != "UNSTARTED"]
        if not shown:
            console.print(x + 2, cy, "You carry no errands yet. Seek out the folk of Bree.",
                          fg=color.gray)
        for q in shown:
            head_col = {
                "DONE": color.health_recovered,
                "READY": color.hope_gain,
            }.get(q.state.name, color.menu_title)
            console.print(x + 2, cy, q.status_line(), fg=head_col)
            cy += 1
            for line in textwrap.wrap(q.summary, w - 6):
                console.print(x + 4, cy, line, fg=color.menu_text)
                cy += 1
            cy += 1
        console.print(x + 2, y + h - 1, " Esc close ", fg=color.gray)


# ===========================================================================
# Help
# ===========================================================================
HELP_TEXT = """The Lonelands — a solo Ranger in Eriador, TA 2965

MOVEMENT   arrows, hjkl, yubn, or numpad. Move into a foe to strike;
           move into a townsfolk to speak.
WAIT       . (period) or z
ENTER/> <  use a gate, stair, or barrow-entrance you stand upon
g          pick up what lies underfoot
i          use or equip from your pack
d          set down an item
c          your character sheet   (A within: spend experience)
q          your errands and tidings
?          this help
Esc        the wayfarer's menu

THE ROLL   Deeds are tested with a Feat die (d12) plus Success dice (d6),
           one per rank of the skill. Meet the Target Number to succeed.
           A 6 (tengwar) marks a great success; the Gandalf rune (12) never
           fails; the Eye (11) counts for nothing and courts ill fortune.

VITALS     Endurance is your vigour — at 0 you fall. Hope steels the heart.
           Grow Weary as burdens mount; a Wound is grave. Athelas mends both.
"""


class HelpHandler(AskUserHandler):
    def on_render(self, console) -> None:
        super().on_render(console)
        w, h = 68, 30
        x, y = 6, 6
        _panel(console, x, y, w, h, "Lore of the Wayfarer")
        for i, line in enumerate(HELP_TEXT.strip("\n").splitlines()):
            console.print(x + 2, y + 2 + i, line, fg=color.menu_text)
        console.print(x + 2, y + h - 1, " any key to close ", fg=color.gray)

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
        console.print(x + 2, y + 2, "[Enter]  return to the road", fg=color.menu_text)
        console.print(x + 2, y + 4, "[S]      save and continue", fg=color.menu_text)
        console.print(x + 2, y + 6, "[T]      save & quit to title", fg=color.menu_text)
        console.print(x + 2, y + 8, "[Q]      quit to the outer dark", fg=color.menu_text)

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
        w = 72
        x = (SCREEN_WIDTH - w) // 2
        text_lines: List[str] = []
        for para in self._text().split("\n"):
            text_lines.extend(textwrap.wrap(para, w - 4) or [""])
        opts = self._visible_options()
        h = len(text_lines) + len(opts) + 6
        y = SCREEN_HEIGHT - h - 2
        _panel(console, x, y, w, h, f"{self.speaker.name} — {self.npc.title}")
        cy = y + 2
        for line in text_lines:
            console.print(x + 2, cy, line, fg=color.white)
            cy += 1
        cy += 1
        for i, o in enumerate(opts):
            console.print(x + 2, cy, f"{i + 1}. {o['text']}", fg=color.menu_text)
            cy += 1
        console.print(x + 2, y + h - 1, " press a number · Esc to end ", fg=color.gray)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        opts = self._visible_options()
        if event.sym == KeySym.ESCAPE:
            self.engine.event_handler = MainGameEventHandler(self.engine)
            return self.engine.event_handler
        idx = None
        if KeySym.N1 <= event.sym <= KeySym.N9:
            idx = event.sym - KeySym.N1
        elif KeySym.KP_1 <= event.sym <= KeySym.KP_9:
            idx = event.sym - KeySym.KP_1
        if idx is None or idx >= len(opts):
            return None

        chosen = opts[idx]
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
        return None


# ===========================================================================
# Shop
# ===========================================================================
class ShopHandler(EventHandler):
    def __init__(self, engine: "Engine", title: str, stock: List[Tuple["Item", int]]):
        super().__init__(engine)
        self.title = title
        self.stock = stock
        self.cursor = 0
        engine.event_handler = self

    def on_render(self, console) -> None:
        self.engine.render(console)
        w, h = 52, len(self.stock) + 7
        x = (SCREEN_WIDTH - w) // 2
        y = 6
        _panel(console, x, y, w, h, self.title)
        hero = self.engine.player.hero
        console.print(x + 2, y + 1, f"Your purse: {hero.coins} coins", fg=color.gold_c)
        for i, (item, price) in enumerate(self.stock):
            sel = i == self.cursor
            fg = color.selected if sel else color.menu_text
            afford = color.gold_c if hero.coins >= price else color.impossible
            prefix = "> " if sel else "  "
            console.print(x + 2, y + 3 + i, f"{prefix}{item.char} {item.name:<26}", fg=fg)
            console.print(x + w - 10, y + 3 + i, f"{price:>3} c", fg=afford)
        console.print(x + 2, y + h - 1, " ↑/↓ · Enter buy · Esc leave ", fg=color.gray)

    def ev_keydown(self, event) -> Optional[BaseEventHandler]:
        if event.sym in (KeySym.UP, KeySym.k):
            self.cursor = (self.cursor - 1) % len(self.stock)
            return None
        if event.sym in (KeySym.DOWN, KeySym.j):
            self.cursor = (self.cursor + 1) % len(self.stock)
            return None
        if event.sym in CONFIRM_KEYS:
            self._buy()
            return None
        if event.sym == KeySym.ESCAPE:
            self.engine.event_handler = MainGameEventHandler(self.engine)
            return self.engine.event_handler
        return None

    def _buy(self) -> None:
        import copy
        item, price = self.stock[self.cursor]
        hero = self.engine.player.hero
        inv = self.engine.player.inventory
        if hero.coins < price:
            self.engine.message_log.add_message("You cannot afford that.", color.impossible)
            return
        if len(inv.items) >= inv.capacity:
            self.engine.message_log.add_message("Your pack is full.", color.impossible)
            return
        hero.coins -= price
        clone = copy.deepcopy(item)
        clone.parent = inv
        inv.items.append(clone)
        self.engine.message_log.add_message(
            f"You buy the {item.name} for {price} coins.", color.item_c)


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
            engine = setup_game.new_game()
            return MainGameEventHandler(engine)
        return None
