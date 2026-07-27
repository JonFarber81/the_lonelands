"""The always-on HUD, drawn natively in pixel space (issue #66 follow-up).

The map/game view stays a cell grid, but the two chrome panes around it — the
**sidebar** (right) and the **Chronicle** (bottom: dice tray + message log) — are
docked native panels here, sharing the proportional look of the menus so the
whole frame reads as one interface. This is where prose lives, so the message
log wraps freely and reads like text, not a character grid.

:meth:`lonelands.engine.Engine.render_hud` calls :func:`render`; the pixel rects
are derived from the map's cell dimensions so the panes fill exactly the screen
the grid map does not.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

import pygame

from lonelands import character, color
from lonelands.config import MAP_HEIGHT, MAP_WIDTH, SCREEN_HEIGHT, SCREEN_WIDTH
from lonelands.render_functions import endurance_color

if TYPE_CHECKING:
    from lonelands.display import Display
    from lonelands.engine import Engine
    from lonelands.ui import UI


def _rects(display: "Display") -> "Tuple[Tuple[int,int,int,int], Tuple[int,int,int,int]]":
    """(sidebar, chronicle) pixel rects, docked to the right of and below the
    grid map."""
    cw, ch = display.cell_w, display.cell_h
    ox, oy = display.offset
    map_w, map_h = MAP_WIDTH * cw, MAP_HEIGHT * ch
    sidebar = (ox + map_w, oy, (SCREEN_WIDTH - MAP_WIDTH) * cw, SCREEN_HEIGHT * ch)
    chronicle = (ox, oy + map_h, map_w, (SCREEN_HEIGHT - MAP_HEIGHT) * ch)
    return sidebar, chronicle


def render(display: "Display", engine: "Engine", banner: bool = True) -> None:
    sidebar, chronicle = _rects(display)
    _sidebar(display.ui, sidebar, engine)
    _chronicle(display.ui, chronicle, engine)
    if banner:
        # Suppressed during lock-on targeting, whose own prompt owns the map's
        # top row (see LockOnHandler).
        _banner(display, engine)


def _banner(display: "Display", engine: "Engine") -> None:
    """The location name in a slim translucent bar across the top of the map."""
    ui = display.ui
    cw, ch = display.cell_w, display.cell_h
    ox, oy = display.offset
    map_w = MAP_WIDTH * cw
    h = int(ui.subtitle.get_linesize() * 1.15)
    bar = pygame.Surface((map_w, h), pygame.SRCALPHA)
    bar.fill((0x14, 0x12, 0x10, 235))
    ui.screen.blit(bar, (ox, oy))
    ty = oy + (h - ui.subtitle.get_height()) // 2
    ui.text(ox + ui.pad // 2, ty, engine.game_map.name, color.menu_title, ui.subtitle)


# --- sidebar ---------------------------------------------------------------
def _sidebar(ui: "UI", rect, engine: "Engine") -> None:
    x, y, w, h = rect
    inner = ui.hud_panel(x, y, w, h)
    ix, iw = inner.x, inner.w
    cy = inner.y
    p = engine.player
    hero, f = p.hero, p.fighter
    step = ui.small.get_linesize()

    # Identity — the header block.
    ui.selection(ix - ui.pad // 2, cy, iw + ui.pad, ui.line)
    ui.text(ix, cy, p.name, color.tier_value, ui.bold)
    cy += ui.line
    ui.text(ix, cy, hero.culture, color.ranger_green, ui.small)
    cy += step + ui.pad // 3

    # Vitals — the always-on bars.
    cy = ui.bar(ix, cy, iw, f.endurance / max(1, f.max_endurance),
                color.bar_filled, color.bar_empty, "END",
                f"{f.endurance}/{f.max_endurance}") + ui.pad // 4
    cy = ui.bar(ix, cy, iw, hero.xp / max(1, hero.xp_to_next),
                color.xp_filled, color.xp_empty, f"LVL {hero.level}",
                f"{hero.xp}/{hero.xp_to_next}") + ui.pad // 3

    # Conditions.
    conds: List[Tuple[str, Color]] = []
    if hero.is_weary:
        conds.append(("Weary", color.enemy_atk))
    if f.bleed > 0:
        conds.append((f"Bleeding ({f.bleed})", color.player_die))
    if not conds:
        conds.append(("Hale", color.health_recovered))
    ui.text(ix, cy, "· " + "   ".join(c[0] for c in conds), conds[0][1], ui.small)
    cy += step + ui.pad // 3

    # Attributes.
    cy = ui.section(ix, cy, iw, "ATTRIBUTES")
    for attr in character.ATTRIBUTES:
        ui.text(ix, cy, attr, color.tier_body, ui.small)
        ui.text_right(inner.right, cy, f"{hero.modifier(attr):+d}", color.tier_value, ui.small)
        cy += step
    cy += ui.pad // 3

    # Advancement.
    cy = ui.section(ix, cy, iw, "ADVANCEMENT")
    ui.text(ix, cy, "Path points", color.tier_label, ui.small)
    pp = hero.path_points
    ui.text_right(inner.right, cy, str(pp),
                  color.hope_gain if pp else color.tier_body, ui.small)
    cy += step
    ui.text(ix, cy, "Coins", color.tier_label, ui.small)
    ui.text_right(inner.right, cy, str(hero.coins), color.gold_c, ui.small)
    cy += step + ui.pad // 3

    # Wielded.
    cy = ui.section(ix, cy, iw, "WIELDED")
    ui.text(ix, cy, ui.truncate(f.weapon_name, iw, ui.small), color.weapon_c, ui.small)
    cy += step
    half = ix + iw // 2
    for (la, va), (lb, vb), cyy in (
        (("Def", str(f.defence)), ("Atk", f"+{f.attack_bonus}"), cy),
        (("Soak", str(f.soak)), ("Load", str(hero.load)), cy + step),
    ):
        ui.text(ix, cyy, la, color.tier_label, ui.small)
        ui.text(ix + ui.small.size("Soak  ")[0], cyy, va, color.tier_value, ui.small)
        ui.text(half, cyy, lb, color.tier_label, ui.small)
        ui.text(half + ui.small.size("Load  ")[0], cyy, vb, color.tier_value, ui.small)
    cy += 2 * step + ui.pad // 3

    # Errands.
    cy = ui.section(ix, cy, iw, "ERRANDS")
    actives = engine.quest_log.active_quests()
    if not actives:
        ui.text(ix, cy, "— none —", color.tier_label, ui.small)
    else:
        for q in actives[:4]:
            col = color.hope_gain if q.state.name == "READY" else color.tier_body
            for seg in ui.wrap(q.status_line(), iw, ui.small):
                ui.text(ix, cy, seg, col, ui.small)
                cy += step

    # Footer.
    ui.text(ix, inner.bottom - step, "[?] help    [C] sheet", color.tier_label, ui.small)


# --- Chronicle (dice tray + message log) -----------------------------------
def _chronicle(ui: "UI", rect, engine: "Engine") -> None:
    x, y, w, h = rect
    inner = ui.hud_panel(x, y, w, h)
    ix, iw = inner.x, inner.w
    # A compact header row: the "Chronicle" caption on the left, the dice tray
    # filling the rest — keeping as much height as possible for the prose log.
    ui.text(ix, inner.y, "CHRONICLE", color.section_head, ui.small)
    tx = ix + ui.small.size("CHRONICLE  ")[0]
    _dice_tray(ui, tx, inner.y, inner.right - tx, engine)
    ry = inner.y + ui.small.get_linesize() + 2
    ui.hrule(ix, ry, iw)
    _message_log(ui, ix, ry + max(4, ui.pad // 4), iw, inner.bottom, engine)


def _dice_tray(ui: "UI", x: int, y: int, w: int, engine: "Engine") -> None:
    roll = getattr(engine, "last_roll", None)
    if roll is None:
        ui.text(x, y, "the die lies still", color.dark_gray, ui.small)
        return
    die_fg = (color.gandalf_rune if roll.is_crit
              else color.sauron_eye if roll.is_fumble else color.light_gray)
    cx = x + ui.text(x, y, "d20", color.dark_gray, ui.small) + ui.pad // 3
    cx += ui.text(cx, y, f"[{roll.die:>2}]", die_fg, ui.small) + ui.pad // 4
    line = f"{roll.mod:+d} = {roll.total}   vs {roll.tn}"
    if roll.damage is not None:
        line += f"   {roll.damage} dmg"
    ui.text(cx, y, line, color.gray, ui.small)
    if roll.is_crit:
        word, fg = "CRITICAL", color.gandalf_rune
    elif roll.is_fumble:
        word, fg = "FUMBLE", color.sauron_eye
    elif roll.is_success:
        word, fg = "HIT", color.success_roll
    else:
        word, fg = "MISS", color.gray
    ui.text_right(x + w, y, word, fg, ui.small)


def _message_log(ui: "UI", x: int, top: int, w: int, bottom: int, engine: "Engine") -> None:
    """The scrolling log, newest at the bottom, wrapped as prose."""
    step = ui.small.get_linesize()
    lines: List[Tuple[str, Color]] = []
    for msg in reversed(engine.message_log.messages):
        for seg in reversed(ui.wrap(msg.full_text, w, ui.small)):
            lines.append((seg, msg.fg))
        if top + len(lines) * step > bottom:
            break
    yy = bottom - step
    for seg, col in lines:
        if yy < top:
            break
        ui.text(x, yy, seg, col, ui.small)
        yy -= step
