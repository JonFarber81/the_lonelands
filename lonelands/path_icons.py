"""Vector node icons for the Path tree (#77 follow-up).

Every node on the tree screen wears a little icon so the tree can be *read* at a
glance — mobility deed, control deed, rankable trait, capstone. The icons are
drawn from :mod:`pygame` primitives (no art assets) into a square on the card and
**tinted by the node's state colour** (owned green / buyable gold / locked dim),
so the glyph reinforces the border.

The vocabulary is *hybrid* (see the #77 design grill): a small set of **semantic
archetypes** keyed off the node's data — an active's :class:`~perks.ActiveSpec`
kind, or a passive's dominant stat bonus — plus a **bespoke detail** for the ten
Hidden Path nodes, dispatched by id in :data:`_BY_ID`. Capstones wrap their base
glyph in a ring with a spark, so "the payoff" reads even before you know the art.

Each drawer takes ``(screen, cx, cy, s, col, w)`` — the icon centre, the half-box
``s``, the tint ``col`` and a stroke width ``w`` — and paints within the box
``[cx-s, cx+s] x [cy-s, cy+s]``. :func:`draw` is the only entry point.
"""
from __future__ import annotations

import math
from typing import Callable, Tuple

import pygame

Color = Tuple[int, ...]


# --- tiny primitives in a centred, normalised frame -----------------------
def _pts(cx, cy, s, coords):
    """Map ``[-1, 1]`` fractional ``coords`` to pixels within the icon box."""
    return [(round(cx + fx * s), round(cy + fy * s)) for fx, fy in coords]


def _lines(screen, col, w, cx, cy, s, coords, closed=False):
    pygame.draw.lines(screen, col, closed, _pts(cx, cy, s, coords), w)


def _poly(screen, col, cx, cy, s, coords, w=0):
    pygame.draw.polygon(screen, col, _pts(cx, cy, s, coords), w)


def _dot(screen, col, cx, cy, s, fx, fy, r):
    pygame.draw.circle(screen, col, (round(cx + fx * s), round(cy + fy * s)), max(1, round(r)))


def _ring(screen, col, cx, cy, s, r, w):
    pygame.draw.circle(screen, col, (round(cx), round(cy)), round(r * s), w)


def _arc(screen, col, w, cx, cy, s, hw, hh, a0, a1):
    rect = pygame.Rect(round(cx - hw * s), round(cy - hh * s), round(2 * hw * s), round(2 * hh * s))
    pygame.draw.arc(screen, col, rect, a0, a1, w)


# --- archetype glyphs ------------------------------------------------------
def _footprint(screen, cx, cy, s, col, w):
    """Silent Tread — a footprint stealing forward, with motion dashes behind."""
    sole = pygame.Rect(round(cx - 0.32 * s), round(cy - 0.42 * s), round(0.64 * s), round(1.0 * s))
    pygame.draw.ellipse(screen, col, sole, w)
    for fx in (-0.26, -0.08, 0.1, 0.28):                # toe pads above the sole
        _dot(screen, col, cx, cy, s, fx, -0.64, 0.075 * s)
    for fy in (-0.2, 0.28):                             # motion dashes trailing behind
        _lines(screen, col, w, cx, cy, s, [(-0.95, fy), (-0.6, fy)])


def _chevrons(screen, cx, cy, s, col, w, away=False):
    """Dash — a double chevron blinking across, with a faint origin dot."""
    sign = -1 if away else 1
    for off in (-0.18, 0.34):
        _lines(screen, col, w, cx, cy, s,
               [(sign * (-0.5) + off * sign, -0.55), (sign * 0.5 + off * sign, 0.0),
                (sign * (-0.5) + off * sign, 0.55)])
    _dot(screen, col, cx, cy, s, -0.72 * sign, 0.0, 0.09 * s)


def _blade(screen, cx, cy, s, col, w, droplet=False):
    """A blade point-up; with a venom droplet at the tip for Poisoned Blade."""
    _poly(screen, col, cx, cy, s, [(0, -0.85), (0.26, 0.2), (0, 0.42), (-0.26, 0.2)], w)
    _lines(screen, col, w, cx, cy, s, [(0, 0.42), (0, 0.8)])            # grip
    _lines(screen, col, w, cx, cy, s, [(-0.3, 0.5), (0.3, 0.5)])        # guard
    if droplet:
        _dot(screen, col, cx, cy, s, 0.44, -0.5, 0.13 * s)
        _poly(screen, col, cx, cy, s, [(0.44, -0.74), (0.56, -0.48), (0.32, -0.48)])


def _reticle_dagger(screen, cx, cy, s, col, w):
    """Ambush — a dagger striking down between target brackets."""
    for sx in (-1, 1):                                  # corner brackets framing the mark
        for sy in (-1, 1):
            _lines(screen, col, w, cx, cy, s,
                   [(sx * 0.85, sy * 0.5), (sx * 0.85, sy * 0.85), (sx * 0.5, sy * 0.85)])
    _poly(screen, col, cx, cy, s, [(0, 0.72), (0.2, -0.2), (0, -0.42), (-0.2, -0.2)], w)  # blade down
    _lines(screen, col, w, cx, cy, s, [(-0.28, -0.2), (0.28, -0.2)])   # guard
    _lines(screen, col, w, cx, cy, s, [(0, -0.42), (0, -0.68)])        # grip up


def _dodge(screen, cx, cy, s, col, w):
    """Evasion — a sidestep: a swept arc flicking off to one side."""
    _arc(screen, col, w, cx, cy, s, 0.72, 0.85, math.radians(20), math.radians(200))
    _poly(screen, col, cx, cy, s, [(0.66, -0.28), (0.86, -0.12), (0.6, 0.0)])
    _dot(screen, col, cx, cy, s, -0.62, 0.42, 0.09 * s)


def _trap(screen, cx, cy, s, col, w):
    """Snare — a noose loop drawn over its tightening knot and stake."""
    loop = pygame.Rect(round(cx - 0.5 * s), round(cy - 0.75 * s), round(1.0 * s), round(0.8 * s))
    pygame.draw.ellipse(screen, col, loop, w)
    _lines(screen, col, w, cx, cy, s, [(-0.14, 0.05), (0.14, 0.05)])   # knot
    _lines(screen, col, w, cx, cy, s, [(0, 0.05), (0, 0.85)])          # stake
    _dot(screen, col, cx, cy, s, 0, 0.85, 0.09 * s)


def _pin(screen, cx, cy, s, col, w):
    """Pinning — a spike driven down through a ring, holding a foe in place."""
    _ring(screen, col, cx, cy - 0.1 * s, s, 0.34, w)
    _lines(screen, col, w, cx, cy, s, [(0, -0.8), (0, 0.7)])
    _poly(screen, col, cx, cy, s, [(0, 0.9), (-0.18, 0.55), (0.18, 0.55)])
    _lines(screen, col, w, cx, cy, s, [(-0.55, 0.8), (0.55, 0.8)])      # ground line


def _wisp(screen, cx, cy, s, col, w):
    """Vanish — a curl of smoke dispersing upward into fading motes."""
    _lines(screen, col, w, cx, cy, s,
           [(-0.1, 0.85), (0.28, 0.5), (-0.28, 0.12), (0.2, -0.24)])
    for (fx, fy, r) in ((-0.05, -0.44, 0.11), (0.28, -0.66, 0.08), (-0.24, -0.72, 0.055)):
        _dot(screen, col, cx, cy, s, fx, fy, r * s)


def _shield(screen, cx, cy, s, col, w):
    """Defence / stance — a shield."""
    _poly(screen, col, cx, cy, s,
          [(0, -0.8), (0.65, -0.5), (0.65, 0.2), (0, 0.85), (-0.65, 0.2), (-0.65, -0.5)], w)


def _plates(screen, cx, cy, s, col, w):
    """Soak — layered plates (Iron Skin)."""
    for fy in (-0.5, -0.05, 0.4):
        _lines(screen, col, w, cx, cy, s, [(-0.6, fy + 0.18), (0, fy - 0.18), (0.6, fy + 0.18)])


def _cross(screen, cx, cy, s, col, w):
    """Heal — a soft cross (Second Wind)."""
    _lines(screen, col, w, cx, cy, s, [(0, -0.6), (0, 0.6)])
    _lines(screen, col, w, cx, cy, s, [(-0.6, 0), (0.6, 0)])
    _ring(screen, col, cx, cy, s, 0.85, w)


def _burst(screen, cx, cy, s, col, w):
    """Wrath / crit — a radiating strike."""
    for k in range(8):
        a = math.radians(k * 45)
        r0, r1 = (0.3, 0.9) if k % 2 == 0 else (0.24, 0.6)
        _lines(screen, col, w, cx, cy, s,
               [(r0 * math.cos(a), r0 * math.sin(a)), (r1 * math.cos(a), r1 * math.sin(a))])


def _arrow(screen, cx, cy, s, col, w):
    """Ranged — an arrow on the rise."""
    _lines(screen, col, w, cx, cy, s, [(-0.7, 0.7), (0.7, -0.7)])
    _poly(screen, col, cx, cy, s, [(0.7, -0.7), (0.3, -0.62), (0.62, -0.3)])
    _lines(screen, col, w, cx, cy, s, [(-0.7, 0.7), (-0.7, 0.34)])
    _lines(screen, col, w, cx, cy, s, [(-0.7, 0.7), (-0.34, 0.7)])


def _volley(screen, cx, cy, s, col, w):
    """Arc shot (Multishot / Arrow Storm) — a fan of arrows spreading outward."""
    for fx in (-0.5, 0.0, 0.5):
        _lines(screen, col, w, cx, cy, s, [(fx * 0.5, 0.8), (fx, -0.8)])
        head = fx
        _poly(screen, col, cx, cy, s,
              [(head, -0.8), (head - 0.16, -0.5), (head + 0.16, -0.5)])


def _pierce(screen, cx, cy, s, col, w):
    """Line shot (Piercing Shot) — one long arrow driven through two marks."""
    _lines(screen, col, w, cx, cy, s, [(-0.85, 0.85), (0.85, -0.85)])
    _poly(screen, col, cx, cy, s, [(0.85, -0.85), (0.42, -0.74), (0.74, -0.42)])
    for (fx, fy) in ((-0.2, 0.2), (0.34, -0.34)):        # the marks it passes
        _dot(screen, col, cx, cy, s, fx, fy, 0.12 * s)


def _harry(screen, cx, cy, s, col, w):
    """Harrying Shot — an arrow loosed forward over a backward hop chevron."""
    _lines(screen, col, w, cx, cy, s, [(-0.5, -0.15), (0.8, -0.15)])
    _poly(screen, col, cx, cy, s, [(0.8, -0.15), (0.5, -0.34), (0.5, 0.04)])
    for off in (0.0, 0.32):                              # a double chevron stepping back
        _lines(screen, col, max(1, w - 1), cx, cy, s,
               [(-0.3 + off, 0.35), (-0.62 + off, 0.6), (-0.3 + off, 0.85)])


def _crosshair(screen, cx, cy, s, col, w):
    """Hunter's Mark — a ringed reticle over the quarry."""
    _ring(screen, col, cx, cy, s, 0.6, w)
    for a in (0, 90, 180, 270):
        rad = math.radians(a)
        _lines(screen, col, w, cx, cy, s,
               [(0.6 * math.cos(rad), 0.6 * math.sin(rad)),
                (0.95 * math.cos(rad), 0.95 * math.sin(rad))])
    _dot(screen, col, cx, cy, s, 0, 0, 0.11 * s)


def _focus(screen, cx, cy, s, col, w):
    """Aimed Shot — an arrowhead sighted through a steadying ring."""
    _ring(screen, col, cx, cy, s, 0.85, max(1, w - 1))
    _poly(screen, col, cx, cy, s, [(0, -0.6), (0.34, 0.1), (0, -0.1), (-0.34, 0.1)], w)
    _lines(screen, col, w, cx, cy, s, [(0, -0.1), (0, 0.62)])


def _sweep_arc(screen, cx, cy, s, col, w):
    """Sweeping Blow — a blade swung in a wide crescent arc."""
    _arc(screen, col, w, cx, cy, s, 0.85, 0.85, math.radians(200), math.radians(340))
    _lines(screen, col, w, cx, cy, s, [(0.55, 0.5), (0.9, 0.85)])   # the hilt trailing
    _dot(screen, col, cx, cy, s, -0.7, -0.35, 0.09 * s)             # the arc's spark


def _leaf(screen, cx, cy, s, col, w):
    """Athelas — a kingsfoil leaf with its central vein."""
    _poly(screen, col, cx, cy, s, [(0, -0.85), (0.45, 0.0), (0, 0.85), (-0.45, 0.0)], w)
    _lines(screen, col, w, cx, cy, s, [(0, -0.7), (0, 0.7)])        # the midrib
    for fy in (-0.32, 0.02, 0.36):                                  # side veins
        _lines(screen, col, max(1, w - 1), cx, cy, s, [(0, fy), (0.3, fy - 0.18)])
        _lines(screen, col, max(1, w - 1), cx, cy, s, [(0, fy), (-0.3, fy - 0.18)])


def _thorns(screen, cx, cy, s, col, w):
    """Thornguard — a spiked guard bristling outward."""
    _arc(screen, col, w, cx, cy, s, 0.7, 0.7, math.radians(200), math.radians(340))
    for a in (215, 250, 290, 325):
        rad = math.radians(a)
        _lines(screen, col, w, cx, cy, s,
               [(0.7 * math.cos(rad), 0.7 * math.sin(rad)),
                (1.0 * math.cos(rad), 1.0 * math.sin(rad))])
    _lines(screen, col, w, cx, cy, s, [(-0.5, 0.55), (0.5, 0.55)])  # the vambrace


def _execute(screen, cx, cy, s, col, w):
    """Executioner — a heavy blade falling on a marked line (the finishing blow)."""
    _poly(screen, col, cx, cy, s, [(0, -0.15), (0.28, -0.75), (-0.28, -0.75)], w)  # head
    _lines(screen, col, w, cx, cy, s, [(0, -0.15), (0, 0.45)])      # the haft
    _lines(screen, col, w, cx, cy, s, [(-0.6, 0.75), (0.6, 0.75)])  # the block
    for fx in (-0.35, 0.0, 0.35):
        _lines(screen, col, max(1, w - 1), cx, cy, s, [(fx, 0.55), (fx, 0.75)])


def _banner(screen, cx, cy, s, col, w):
    """Rally — a raised banner, defiance in the last of the light."""
    _lines(screen, col, w, cx, cy, s, [(-0.45, 0.85), (-0.45, -0.8)])   # the staff
    _poly(screen, col, cx, cy, s,
          [(-0.45, -0.8), (0.7, -0.6), (0.4, -0.3), (0.7, 0.0), (-0.45, -0.2)], w)


def _pool(screen, cx, cy, s, col, w):
    """Endurance — a reserve filling a vessel."""
    _arc(screen, col, w, cx, cy, s, 0.7, 0.7, math.radians(180), math.radians(360))
    _lines(screen, col, w, cx, cy, s, [(-0.7, 0), (-0.7, -0.5)])
    _lines(screen, col, w, cx, cy, s, [(0.7, 0), (0.7, -0.5)])
    _lines(screen, col, w, cx, cy, s, [(-0.4, 0.24), (0.4, 0.24)])


def _diamond(screen, cx, cy, s, col, w):
    """Generic trait — a filled chevron/diamond."""
    _poly(screen, col, cx, cy, s, [(0, -0.7), (0.6, 0), (0, 0.7), (-0.6, 0)], w)


# --- capstone wrapper ------------------------------------------------------
def _spark(screen, cx, cy, s, col, w):
    for a in (0, 90, 45, 135):
        r = 0.28 if a % 90 else 0.4
        rad = math.radians(a)
        _lines(screen, col, max(1, w - 1), cx, cy, s,
               [(-r * math.cos(rad), -r * math.sin(rad)), (r * math.cos(rad), r * math.sin(rad))])


# --- dispatch --------------------------------------------------------------
_BY_ID: dict = {
    "hp_stealth": _footprint,
    "hp_ambush": _reticle_dagger,
    "hp_evasion": _dodge,
    "hp_shadowstep": _chevrons,
    "hp_poison": lambda sc, cx, cy, s, c, w: _blade(sc, cx, cy, s, c, w, droplet=True),
    "hp_deathblow": _blade,
    "hp_snare": _trap,
    "hp_pinning": _pin,
    "hp_disengage": lambda sc, cx, cy, s, c, w: _chevrons(sc, cx, cy, s, c, w, away=True),
    "hp_vanish": _wisp,
}


def _archetype(node) -> Callable:
    """Pick a glyph from the node's data for Paths without a bespoke icon."""
    if node.active is not None:
        kind = node.active.kind
        return {
            "dash": lambda sc, cx, cy, s, c, w: _chevrons(sc, cx, cy, s, c, w),
            "place_tile": _trap,
            "root": _pin,
            "vanish": _wisp,
            "heal": _cross,
            "stance": _shield,
            "wrath": _burst,
            "arc_shot": _volley,
            "line_shot": _pierce,
            "harry": _harry,
            "mark": _crosshair,
            "aim": _focus,
            "charge": lambda sc, cx, cy, s, c, w: _chevrons(sc, cx, cy, s, c, w),
            "sweep": _sweep_arc,
            "athelas": _leaf,
        }.get(kind, _diamond)
    if node.thorns_damage:
        return _thorns
    if node.execute_damage:
        return _execute
    if node.rally_atk_bonus or node.rally_soak_bonus:
        return _banner
    if node.soak_bonus:
        return _plates
    if node.defence_bonus:
        return _shield
    if node.stealth_bonus:
        return _footprint
    if node.melee_bleed:
        return lambda sc, cx, cy, s, c, w: _blade(sc, cx, cy, s, c, w, droplet=True)
    if node.ambush_bonus_damage or node.ambush_advantage:
        return _reticle_dagger
    if node.ranged_bonus or node.ranged_damage_bonus:
        return _arrow
    if node.crit_range:
        return _burst
    if node.atk_bonus or node.melee_damage_bonus:
        return _blade
    if node.max_endurance_bonus:
        return _pool
    return _diamond


def draw(screen: "pygame.Surface", node, cx: int, cy: int, size: int, col: Color) -> None:
    """Paint ``node``'s icon centred at ``(cx, cy)`` filling a ``size``-px box,
    tinted ``col``. Capstones get a ring-and-spark surround."""
    s = size / 2
    w = max(2, round(size * 0.085))
    drawer = _BY_ID.get(node.id) or _archetype(node)
    if node.capstone:
        _ring(screen, col, cx, cy, s, 0.98, max(2, w - 1))
        drawer(screen, cx, cy, int(s * 0.66), col, max(2, w - 1))
        _spark(screen, cx + int(0.7 * s), cy - int(0.7 * s), int(s * 0.4), col, w)
    else:
        drawer(screen, cx, cy, int(s * 0.86), col, w)
