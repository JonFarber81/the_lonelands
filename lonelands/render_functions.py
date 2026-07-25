from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

import tcod

from lonelands import color
from lonelands.config import (
    LOG_HEIGHT,
    LOG_Y,
    MAP_HEIGHT,
    MAP_WIDTH,
    SCREEN_HEIGHT,
    SIDEBAR_WIDTH,
    SIDEBAR_X,
)

if TYPE_CHECKING:
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
    if f.wounded:
        conds.append(("Wounded", color.player_die))
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
        dots = "●" * rk + "·" * (6 - rk)
        console.print(x=col, y=y, string=f"{nm[:6]:<6}{dots}", fg=color.menu_text)
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
    console.print(x=ix, y=y, string=f"Def TN {f.defence}  Prot {f.protection}d  Load {hero.load}",
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
