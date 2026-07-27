from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

import tcod

from lonelands import character, color
from lonelands.config import (
    LOG_HEIGHT,
    LOG_Y,
    MAP_HEIGHT,
    MAP_WIDTH,
    SCREEN_HEIGHT,
    SIDEBAR_WIDTH,
    SIDEBAR_X,
    TRAY_DIVIDER_Y,
    TRAY_Y,
)

if TYPE_CHECKING:
    from lonelands.dice import RollResult
    from lonelands.engine import Engine


def render_bar(
    console, x: int, y: int, width: int, value: int, maximum: int,
    fg_full, fg_empty, label: str,
) -> None:
    maximum = max(1, maximum)
    fill = int(width * value / maximum)
    console.draw_rect(x=x, y=y, width=width, height=1, ch=ord(" "), bg=fg_empty)
    if fill > 0:
        console.draw_rect(x=x, y=y, width=fill, height=1, ch=ord(" "), bg=fg_full)
    console.print(x=x + 1, y=y, string=f"{label} {value}/{maximum}", fg=color.white)


# --- Chrome visual language (CONTEXT.md "chrome visual language") -----------
# Shared primitives so every panel — sidebar and popups alike — speaks one
# language: luminance tiers, header-over-rule, filled bars, stateful colour.
def draw_rule(console, x: int, y: int, w: int) -> None:
    """A thin dim horizontal rule (under a section header). The bundled font has
    no box-drawing ink, so we rule with hyphens (as the dice tray does)."""
    console.print(x, y, "-" * w, fg=color.rule)


def draw_section(console, x: int, y: int, w: int, text: str) -> int:
    """A section header (bright gold) over a dim rule; returns the next free y."""
    console.print(x, y, text, fg=color.section_head)
    draw_rule(console, x, y + 1, w)
    return y + 2


def draw_filled_bar(console, x: int, y: int, w: int, text: str,
                    fg=color.tier_value, bg=color.bar_accent) -> None:
    """A reverse-video filled bar spanning ``w`` cells: 'this is the thing'."""
    console.draw_rect(x, y, w, 1, ord(" "), fg=fg, bg=bg)
    console.print(x + 1, y, text, fg=fg, bg=bg)


def endurance_color(cur: int, mx: int):
    """Stateful Endurance colour: green when hale, amber when hurt, red when low."""
    frac = cur / mx if mx else 0.0
    if frac >= 0.6:
        return color.end_full
    if frac >= 0.3:
        return color.end_mid
    return color.end_low


def get_names_at(x: int, y: int, engine: "Engine") -> str:
    gm = engine.game_map
    if not gm.in_bounds(x, y) or not gm.visible[x, y]:
        return ""
    names = ", ".join(
        e.name for e in gm.entities if e.x == x and e.y == y
    )
    return names


def render_names_at_mouse(console, engine: "Engine") -> None:
    x, y = engine.mouse_location
    if x >= MAP_WIDTH or y >= MAP_HEIGHT:
        return
    names = get_names_at(x, y, engine)
    if names:
        console.print(x=1, y=MAP_HEIGHT - 1, string=names[: MAP_WIDTH - 2], fg=color.light_gray)


def render_location_banner(console, engine: "Engine") -> None:
    name = engine.game_map.name
    console.draw_rect(x=0, y=0, width=MAP_WIDTH, height=1, ch=ord(" "), bg=(0x14, 0x12, 0x10))
    console.print(x=1, y=0, string=name[: MAP_WIDTH - 2], fg=color.menu_title)


def render_dice_tray(console, engine: "Engine") -> None:
    """The player's latest Check, rendered as a d20 line above the log.

    Reads ``engine.last_roll`` (set only for the player's rolls). Reflects
    nothing until the first roll of the game. The line reads
    ``d20  N +mod = total  vs TN`` with the verdict (CRIT/FUMBLE/HIT/MISS)
    stacked beneath.
    """
    ix = 2
    inner_w = MAP_WIDTH - 4
    # Thin rule separating the tray from the prose below. (The bundled font has
    # no box-drawing glyphs, so we rule with hyphens.)
    console.print(x=ix, y=TRAY_DIVIDER_Y, string="-" * inner_w, fg=color.frame)

    roll: "RollResult | None" = getattr(engine, "last_roll", None)
    if roll is None:
        console.print(x=ix, y=TRAY_Y, string="the die lies still", fg=color.dark_gray)
        return

    top_y, bot_y = TRAY_Y, TRAY_Y + 1

    # The kept d20 face, coloured by its fortune.
    if roll.is_crit:
        die_fg = color.gandalf_rune
    elif roll.is_fumble:
        die_fg = color.sauron_eye
    else:
        die_fg = color.light_gray
    console.print(x=ix, y=top_y, string="d20", fg=color.dark_gray)
    x = ix + 4
    console.print(x=x, y=top_y, string=f"[{roll.die:>2}]", fg=die_fg)
    x += 5
    line = f"{roll.mod:+d} = {roll.total}   vs {roll.tn}"
    if roll.damage is not None:
        line += f"   {roll.damage} dmg"
    console.print(x=x, y=top_y, string=line, fg=color.gray)

    if roll.is_crit:
        word, fg = ("CRITICAL", color.gandalf_rune)
    elif roll.is_fumble:
        word, fg = ("FUMBLE", color.sauron_eye)
    elif roll.is_success:
        word, fg = ("HIT", color.success_roll)
    else:
        word, fg = ("MISS", color.gray)
    console.print(x=ix + 4, y=bot_y, string=word, fg=fg)


def render_sidebar(console, engine: "Engine") -> None:
    x0 = SIDEBAR_X
    console.draw_frame(
        x=x0, y=0, width=SIDEBAR_WIDTH, height=SCREEN_HEIGHT,
        title="", clear=True, fg=color.frame, bg=color.panel_bg,
    )
    # Chronicle box. Paint the interior stone first (ch=0 keeps the message
    # text the log already drew, recolouring only the cells behind it), then the
    # frame border on top.
    console.draw_rect(
        x=0, y=LOG_Y, width=MAP_WIDTH, height=LOG_HEIGHT,
        ch=0, bg=color.panel_bg,
    )
    console.draw_frame(
        x=0, y=LOG_Y, width=MAP_WIDTH, height=LOG_HEIGHT,
        title="", clear=False, fg=color.frame, bg=color.panel_bg,
    )
    console.print(x=2, y=LOG_Y, string=" Chronicle ", fg=color.frame_bright)

    p = engine.player
    hero = p.hero
    f = p.fighter
    ix = x0 + 2
    w = SIDEBAR_WIDTH - 4
    y = 1

    # Identity — the one filled bar (the hero-name header).
    draw_filled_bar(console, x0 + 1, y, SIDEBAR_WIDTH - 2, p.name)
    y += 1
    console.print(x=ix, y=y, string=hero.culture, fg=color.ranger_green)
    y += 1
    console.print(x=ix, y=y, string=f"{hero.calling} · Solo", fg=color.tier_label)
    y += 2

    # Vitals — the always-on filled bars.
    render_bar(console, ix, y, w, f.endurance, f.max_endurance,
               color.bar_filled, color.bar_empty, "END")
    y += 1
    render_bar(console, ix, y, w, hero.xp, max(1, hero.xp_to_next),
               color.xp_filled, color.xp_empty, f"LVL {hero.level}")
    y += 2

    # Conditions
    conds = []
    if hero.is_weary:
        conds.append(("Weary", color.enemy_atk))
    if f.bleed > 0:
        conds.append((f"Bleeding ({f.bleed})", color.player_die))
    if not conds:
        conds.append(("Hale", color.health_recovered))
    console.print(x=ix, y=y, string="· " + "  ".join(c[0] for c in conds), fg=conds[0][1])
    y += 2

    # Attributes — label dim, modifier bright.
    y = draw_section(console, ix, y, w, "ATTRIBUTES")
    for attr in character.ATTRIBUTES:
        console.print(x=ix, y=y, string=attr, fg=color.tier_body)
        console.print(x=ix + 9, y=y, string=f"{hero.modifier(attr):+d}",
                      fg=color.tier_value)
        y += 1
    y += 1

    # Advancement — Perk points glow gold only while there are points to spend.
    y = draw_section(console, ix, y, w, "ADVANCEMENT")
    xp = f"{hero.xp}/{hero.xp_to_next}"
    console.print(x=ix, y=y, string="Level", fg=color.tier_label)
    console.print(x=ix + 6, y=y, string=str(hero.level), fg=color.tier_value)
    console.print(x=ix + 12, y=y, string="XP", fg=color.tier_label)
    console.print(x=ix + 15, y=y, string=xp, fg=color.tier_value)
    y += 1
    pp = hero.perk_points
    console.print(x=ix, y=y, string="Perk points", fg=color.tier_label)
    console.print(x=ix + 12, y=y, string=str(pp),
                  fg=color.hope_gain if pp else color.tier_body)
    y += 2

    # Wielded — weapon name, then the combat line split to fit the panel.
    y = draw_section(console, ix, y, w, "WIELDED")
    console.print(x=ix, y=y, string=f.weapon_name[:w], fg=color.weapon_c)
    y += 1
    console.print(x=ix, y=y, string="Def", fg=color.tier_label)
    console.print(x=ix + 4, y=y, string=str(f.defence), fg=color.tier_value)
    console.print(x=ix + 9, y=y, string="Atk", fg=color.tier_label)
    console.print(x=ix + 13, y=y, string=f"+{f.attack_bonus}", fg=color.tier_value)
    y += 1
    console.print(x=ix, y=y, string="Soak", fg=color.tier_label)
    console.print(x=ix + 5, y=y, string=str(f.soak), fg=color.tier_value)
    console.print(x=ix + 9, y=y, string="Load", fg=color.tier_label)
    console.print(x=ix + 14, y=y, string=str(hero.load), fg=color.tier_value)
    y += 1
    console.print(x=ix, y=y, string="Coins", fg=color.tier_label)
    console.print(x=ix + 6, y=y, string=str(hero.coins), fg=color.gold_c)
    y += 2

    # Quests
    y = draw_section(console, ix, y, w, "ERRANDS")
    actives = engine.quest_log.active_quests()
    if not actives:
        console.print(x=ix, y=y, string="— none —", fg=color.tier_label)
        y += 1
    else:
        for q in actives[:4]:
            line = q.status_line()
            col = color.hope_gain if q.state.name == "READY" else color.tier_body
            for seg in _wrap(line, w):
                console.print(x=ix, y=y, string=seg, fg=col)
                y += 1

    # Footer
    console.print(x=ix, y=SCREEN_HEIGHT - 2,
                  string="[?] help  [C] sheet", fg=color.tier_label)


def _wrap(text: str, width: int):
    import textwrap
    return textwrap.wrap(text, width) or [""]
