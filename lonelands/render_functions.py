from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

import tcod

from lonelands import color, tor
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


_ATTR_PIP = {
    "Strength": color.pip_strength,
    "Heart": color.pip_heart,
    "Wits": color.pip_wits,
}

# A skill/proficiency's rank drawn as a row of pips. Filled pips glow in the
# governing attribute's colour (or steel for a weapon proficiency); empty pips
# recede into an unlit slot. Returns the width consumed so callers can lay out
# whatever follows.
def render_pips(
    console, x: int, y: int, rank: int, skill: str = "",
    max_rank: int = 6, fill=None,
) -> int:
    if fill is None:
        fill = _ATTR_PIP.get(tor.SKILL_TO_ATTR.get(skill, ""), color.pip_prof)
    # "●" (U+25CF) is absent from the game font, so filled pips must use the
    # bullet "•" (present); empty pips use the smaller middot "·". Colour then
    # carries the real signal: a lit pip glows, an unlit one recedes.
    for i in range(max_rank):
        lit = i < rank
        console.print(x + i, y, "•" if lit else "·",
                      fg=fill if lit else color.pip_empty)
    return max_rank


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
        title="", clear=True, fg=color.frame, bg=color.black,
    )
    # Log frame
    console.draw_frame(
        x=0, y=LOG_Y, width=MAP_WIDTH, height=LOG_HEIGHT,
        title="", clear=False, fg=color.frame, bg=color.black,
    )
    console.print(x=2, y=LOG_Y, string=" Chronicle ", fg=color.frame_bright)

    p = engine.player
    hero = p.hero
    f = p.fighter
    ix = x0 + 2
    w = SIDEBAR_WIDTH - 4
    y = 1

    console.print(x=x0 + 1, y=y, string=f" {p.name} ", fg=color.menu_title)
    y += 1
    console.print(x=ix, y=y, string=hero.culture, fg=color.ranger_green)
    y += 1
    console.print(x=ix, y=y, string=f"{hero.calling} · Solo", fg=color.gray)
    y += 2

    render_bar(console, ix, y, w, f.endurance, f.max_endurance,
               color.bar_filled, color.bar_empty, "END")
    y += 1
    render_bar(console, ix, y, w, hero.hope, hero.max_hope,
               color.hope_filled, color.hope_empty, "HOPE")
    y += 2

    # Conditions
    conds = []
    if hero.is_weary:
        conds.append(("Weary", color.enemy_atk))
    if f.bleed > 0:
        conds.append((f"Bleeding ({f.bleed})", color.player_die))
    if hero.is_miserable:
        conds.append(("Miserable", color.sauron_eye))
    if not conds:
        conds.append(("Hale", color.health_recovered))
    console.print(x=ix, y=y, string="· " + "  ".join(c[0] for c in conds), fg=conds[0][1])
    y += 2

    # Attributes
    console.print(x=ix, y=y, string="ATTRIBUTES", fg=color.frame_bright)
    y += 1
    for attr in ("Strength", "Heart", "Wits"):
        rating = hero.attributes[attr]
        tn = hero.attr_tn(attr)
        console.print(x=ix, y=y, string=f"{attr:<9}{rating}  (TN {tn})", fg=color.menu_text)
        y += 1
    y += 1

    # Key skills / proficiencies
    console.print(x=ix, y=y, string="OF NOTE", fg=color.frame_bright)
    y += 1
    notable = [
        ("Swords", hero.proficiencies.get("Swords", 0)),
        ("Bows", hero.proficiencies.get("Bows", 0)),
        ("Battle", hero.skills.get("Battle", 0)),
        ("Hunting", hero.skills.get("Hunting", 0)),
        ("Stealth", hero.skills.get("Stealth", 0)),
        ("Explore", hero.skills.get("Explore", 0)),
    ]
    for i, (nm, rk) in enumerate(notable):
        col = ix + (0 if i % 2 == 0 else (w // 2 + 1))
        console.print(x=col, y=y, string=f"{nm[:6]:<6}", fg=color.menu_text)
        render_pips(console, col + 6, y, rk, skill=nm)
        if i % 2 == 1:
            y += 1
    if len(notable) % 2 == 1:
        y += 1
    y += 1

    # Wielded
    console.print(x=ix, y=y, string="WIELDED", fg=color.frame_bright)
    y += 1
    console.print(x=ix, y=y, string=f.weapon_name[: w], fg=color.weapon_c)
    y += 1
    console.print(x=ix, y=y, string=f"Def {f.defence}  Atk +{f.attack_bonus}  Soak {f.soak}  Load {hero.load}",
                  fg=color.menu_text)
    y += 2

    # Coins & XP
    console.print(x=ix, y=y, string=f"Coins {hero.coins}    XP {hero.xp}",
                  fg=color.gold_c)
    y += 2

    # Quests
    console.print(x=ix, y=y, string="ERRANDS", fg=color.frame_bright)
    y += 1
    actives = engine.quest_log.active_quests()
    if not actives:
        console.print(x=ix, y=y, string="— none —", fg=color.gray)
        y += 1
    else:
        for q in actives[:4]:
            line = q.status_line()
            col = color.hope_gain if q.state.name == "READY" else color.menu_text
            for seg in _wrap(line, w):
                console.print(x=ix, y=y, string=seg, fg=col)
                y += 1

    # Footer
    console.print(x=ix, y=SCREEN_HEIGHT - 2,
                  string="[?] help  [C] sheet", fg=color.gray)


def _wrap(text: str, width: int):
    import textwrap
    return textwrap.wrap(text, width) or [""]
