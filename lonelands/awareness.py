"""The stealth / awareness layer (ADR 0014).

A foe carries a per-enemy **Awareness** of the Ranger that rises *and* falls
through three states:

* **UNAWARE** — hasn't noticed you (idle or wandering).
* **ALERTED** (``!``) — has you, and hunts.
* **SEARCHING** (``?``) — lost you, and makes for your **last-known** tile.

Detection is **deterministic**, not rolled: a foe's *effective perception* is
its base Perception radius minus the Ranger's **Stealth**, reaching only through
line of sight. Stealth bites **only while the Ranger is sneaking** — standing
plainly he is seen at full range. There is no adjacency floor: reduce a foe's
effective perception to 0 (or below) and the Ranger can stand next to it unseen,
which is what makes a melee **Ambush** possible.

Ambush is gated on **UNAWARE** (or a primed active — Shadowstep/Vanish); this
module owns the awareness read the ambush helper consults, and the alerting a
blow triggers. It depends on nothing in ``actions``/``ai`` (both of which import
*it*), so the constants live here without a circular import.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import tcod.los

if TYPE_CHECKING:
    from lonelands.engine import Engine
    from lonelands.entity import Actor
    from lonelands.game_map import GameMap

# --- Awareness states -----------------------------------------------------
UNAWARE = "unaware"
ALERTED = "alerted"
SEARCHING = "searching"

# --- Base Perception radii (tiles), before Stealth shrinks them -----------
HOSTILE_PERCEPTION = 8  # a wary hostile
BEAST_PERCEPTION = 4    # a beast (folds in the old SkittishBeast ``distance <= 4``)

# The little glyphs a foe wears while it knows the Ranger is about.
MARKER = {ALERTED: "!", SEARCHING: "?"}


def has_los(game_map: "GameMap", x0: int, y0: int, x1: int, y1: int) -> bool:
    """True if an unbroken straight line joins ``(x0, y0)`` and ``(x1, y1)`` with
    no opaque tile *between* the endpoints (the endpoints themselves never block).
    One cheap ray — enough for a foe deciding whether it can see the Ranger."""
    transparent = game_map.tiles["transparent"]
    for px, py in tcod.los.bresenham((x0, y0), (x1, y1)).tolist():
        if (px, py) == (x0, y0) or (px, py) == (x1, y1):
            continue
        if not transparent[px, py]:
            return False
    return True


def stealth_of(engine: "Engine") -> int:
    """The Ranger's live Stealth score — but only while he is **sneaking**.
    Standing plainly he gets no concealment, so foes see him at full Perception."""
    if not getattr(engine, "sneaking", False):
        return 0
    hero = getattr(engine.player, "hero", None)
    return hero.stealth if hero is not None else 0


def effective_perception(engine: "Engine", base: int) -> int:
    """A foe's Perception after the Ranger's Stealth shrinks it. No floor — a
    clumsy (negative-Stealth) Ranger is *easier* to see, so this may exceed
    ``base``; a sufficiently stealthy one can drive it to 0 (adjacent-and-unseen)."""
    return base - stealth_of(engine)


def can_detect(engine: "Engine", seer: "Actor", base: int) -> bool:
    """Whether ``seer`` perceives the Ranger this instant: within its effective
    Perception radius (Chebyshev distance) *and* with a clear line to him."""
    player = engine.player
    dist = max(abs(player.x - seer.x), abs(player.y - seer.y))
    if dist > effective_perception(engine, base):
        return False
    return has_los(engine.game_map, seer.x, seer.y, player.x, player.y)


def search_duration(engine: "Engine") -> int:
    """Turns a foe keeps hunting the last-known tile before giving up:
    ``max(2, 5 − Stealth)`` — a stealthier Ranger shakes pursuers faster."""
    return max(2, 5 - stealth_of(engine))


def awareness_of(actor: "Actor") -> str:
    """``actor``'s awareness state — UNAWARE for anything without an aware AI
    (townsfolk, corpses), so callers never special-case those."""
    ai = getattr(actor, "ai", None)
    return getattr(ai, "awareness", UNAWARE)


def is_unaware(actor: "Actor") -> bool:
    """True if ``actor`` has not noticed the Ranger — the gate for a fresh
    Ambush (a primed active bypasses this)."""
    return awareness_of(actor) == UNAWARE


def alert(actor: "Actor", engine: "Engine") -> None:
    """Snap one foe to ALERTED at the Ranger's current tile (a no-op for anything
    without an aware AI)."""
    ai = getattr(actor, "ai", None)
    if ai is None or not hasattr(ai, "awareness"):
        return
    ai.awareness = ALERTED
    ai.last_known = (engine.player.x, engine.player.y)
    ai.search_turns = 0


def alert_on_attack(engine: "Engine", struck: "Actor") -> None:
    """A blow lands (or is swung): the struck foe, and every foe with a clear
    line to the fight, go ALERTED. Witnesses out of sight stay oblivious — a
    noise radius is a deliberate future extension (ADR 0014)."""
    alert(struck, engine)
    px, py = engine.player.x, engine.player.y
    for actor in engine.game_map.actors:
        if actor is engine.player or actor is struck:
            continue
        ai = getattr(actor, "ai", None)
        if ai is None or not hasattr(ai, "awareness"):
            continue
        if has_los(engine.game_map, actor.x, actor.y, px, py):
            alert(actor, engine)
