"""Ambient **barks** — short, non-interactive flavor lines overheard as the
player moves near a source: a dog barking down a lane, chatter from an inn,
birdsong at a wood's eaves (issue #54).

Two picklable data pieces make up the machinery, both authored as data next to a
region's content (``story/<place>.py``) and attached to that region's
``GameMap`` in ``procgen``:

  * ``BarkSource`` — one thing that can be overheard: a point ``(x, y)``, a
    ``radius`` (Chebyshev, matching the game's other range checks), a pool of
    ``lines``, and a per-source ``cadence`` (the minimum turns before it may
    speak again).
  * ``BarkField`` — a map's whole set of sources plus the throttle that keeps
    them from spamming the log: a ``global_cadence`` (minimum turns between *any*
    two barks) and a ``chance`` that an eligible source actually speaks on a
    given move.

Both hold only ints, strings, and tuples, so they pickle straight into a save —
unlike dialog trees, they need no rehydration.

The selection/throttle is a *pure* seam: ``BarkField.choose`` takes ``roll`` and
``pick`` callables (the game passes the shared ``dice.rng``; tests pass stubs),
so the "which source, which line, or nothing" decision is unit-testable without
an engine. ``emit`` is the thin impure wrapper the movement code calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, List, Optional, Sequence, Tuple

from lonelands import color

if TYPE_CHECKING:
    from lonelands.engine import Engine

# A sentinel "never fired" far enough in the past that the first eligibility
# check always passes, whatever the starting turn count.
_NEVER = -1_000_000


def _chebyshev(ax: int, ay: int, bx: int, by: int) -> int:
    return max(abs(ax - bx), abs(ay - by))


@dataclass
class BarkSource:
    """One overhearable source on a map. ``last_fired`` is bookkeeping the field
    updates as it speaks; author it as -inf so a fresh source is always ready."""

    x: int
    y: int
    radius: int
    lines: Sequence[str]
    cadence: int = 14
    fg: Tuple[int, int, int] = color.ambient
    last_fired: int = _NEVER


class BarkField:
    """A map's ambient bark sources and the throttle over them."""

    def __init__(
        self,
        sources: Sequence[BarkSource],
        *,
        global_cadence: int = 5,
        chance: float = 0.3,
    ) -> None:
        self.sources: List[BarkSource] = list(sources)
        self.global_cadence = global_cadence
        self.chance = chance
        self.last_any = _NEVER

    def eligible(self, px: int, py: int, turn: int) -> List[BarkSource]:
        """Sources within range whose own cadence has elapsed. Ignores the
        global throttle and the dice — those are ``choose``'s job."""
        return [
            s
            for s in self.sources
            if turn - s.last_fired >= s.cadence
            and _chebyshev(px, py, s.x, s.y) <= s.radius
        ]

    def choose(
        self,
        px: int,
        py: int,
        turn: int,
        *,
        roll: Callable[[], float],
        pick: Callable[[Sequence], object],
    ) -> Optional[Tuple[BarkSource, str]]:
        """Decide what (if anything) is overheard from ``(px, py)`` on ``turn``.

        Returns ``(source, line)`` or ``None``. Pure: ``roll()`` yields a float in
        ``[0, 1)`` (the game passes ``rng.random``) and ``pick(seq)`` selects one
        element (``rng.choice``). Nothing is mutated — the caller ``commit``s the
        winner so a rejected roll leaves no trace."""
        if turn - self.last_any < self.global_cadence:
            return None
        candidates = self.eligible(px, py, turn)
        if not candidates:
            return None
        if roll() >= self.chance:
            return None
        source = pick(candidates)
        line = pick(list(source.lines))
        return source, line  # type: ignore[return-value]

    def commit(self, source: BarkSource, turn: int) -> None:
        """Record that ``source`` spoke on ``turn``: arms both its own cadence
        and the field-wide throttle."""
        source.last_fired = turn
        self.last_any = turn


def emit(engine: "Engine") -> None:
    """If the player's current map has a ``BarkField``, maybe emit one line to
    the message log. Called after the player moves; a no-op on maps without
    barks (older saves included) and whenever the throttle/dice decline."""
    gm = engine.game_map
    field = getattr(gm, "barks", None)
    if field is None:
        return
    from lonelands.dice import rng

    player = engine.player
    turn = engine.turn_count
    chosen = field.choose(
        player.x, player.y, turn, roll=rng.random, pick=rng.choice
    )
    if chosen is None:
        return
    source, line = chosen
    field.commit(source, turn)
    # Barks are atmosphere, not events: don't let identical lines stack a "(xN)"
    # counter in the log the way combat messages do.
    engine.message_log.add_message(line, source.fg, stack=False)
