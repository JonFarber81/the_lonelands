from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np
import tcod

from lonelands import awareness
from lonelands.actions import Action, BumpAction, MovementAction, WaitAction
from lonelands.exceptions import Impossible

if TYPE_CHECKING:
    from lonelands.entity import Actor


class BaseAI(Action):
    parent: "Actor"

    def perform(self) -> None:
        raise NotImplementedError()

    def get_path_to(self, dest_x: int, dest_y: int) -> List[Tuple[int, int]]:
        cost = np.array(self.entity.gamemap.tiles["walkable"], dtype=np.int8)

        for entity in self.entity.gamemap.entities:
            if entity.blocks_movement and cost[entity.x, entity.y]:
                cost[entity.x, entity.y] += 10

        graph = tcod.path.SimpleGraph(cost=cost, cardinal=2, diagonal=3)
        pathfinder = tcod.path.Pathfinder(graph)
        pathfinder.add_root((self.entity.x, self.entity.y))
        path = pathfinder.path_to((dest_x, dest_y))[1:].tolist()
        return [(index[0], index[1]) for index in path]


class PerceptiveAI(BaseAI):
    """Shared stealth-aware pursuit (ADR 0014). A foe carries a per-enemy
    :mod:`awareness` state that rises to **Alerted** the instant it perceives the
    Ranger (within its effective Perception radius, through line of sight), decays
    through **Searching** — hunting the Ranger's ``last_known`` tile for
    ``max(2, 5 − Stealth)`` turns — and finally falls back to **Unaware**. Losing
    sight no longer resets awareness instantly; re-detection refreshes the timer.

    Subclasses set the base ``perception`` radius and, via :meth:`_idle`, what an
    Unaware foe does when it has nothing to chase."""

    perception: int = awareness.HOSTILE_PERCEPTION

    def __init__(self, entity: "Actor"):
        super().__init__(entity)
        self.path: List[Tuple[int, int]] = []
        self.awareness: str = awareness.UNAWARE
        self.last_known: Optional[Tuple[int, int]] = None
        self.search_turns: int = 0

    def perform(self) -> None:
        engine = self.engine
        target = engine.player

        # Perceived this turn: (re)alert, and refresh the last-known tile + timer.
        if awareness.can_detect(engine, self.entity, self.perception):
            awareness.alert(self.entity, engine)  # -> Alerted, last_known, timer 0
            return self._advance_toward(target.x, target.y, attack=True)

        # Not perceived. On the turn sight is *first* lost, open a Search of the
        # last-known tile — its full ``max(2, 5 − Stealth)`` turns start now and
        # the Ranger is pursued *this* turn (no same-turn decrement). Every later
        # Searching turn spends one from the clock.
        if self.awareness == awareness.ALERTED:
            self.awareness = awareness.SEARCHING
            self.search_turns = awareness.search_duration(engine)
        elif self.awareness == awareness.SEARCHING:
            self.search_turns -= 1

        if self.awareness == awareness.SEARCHING:
            here = (self.entity.x, self.entity.y)
            if self.search_turns > 0 and self.last_known is not None \
                    and here != self.last_known:
                return self._advance_toward(*self.last_known, attack=False)
            # Reached the last-known tile, or the trail's gone cold: give up.
            self.awareness = awareness.UNAWARE
            self.last_known = None

        return self._idle()

    def _advance_toward(self, tx: int, ty: int, *, attack: bool) -> None:
        """Step toward ``(tx, ty)``. When ``attack`` and already adjacent, strike
        instead (only the pursue-the-Ranger path passes ``attack=True``, so a foe
        homing on an empty last-known tile never swings at thin air)."""
        dx, dy = tx - self.entity.x, ty - self.entity.y
        if attack and max(abs(dx), abs(dy)) <= 1:
            return BumpAction(self.entity, dx, dy).perform()
        self.path = self.get_path_to(tx, ty)
        if self.path:
            nx, ny = self.path.pop(0)
            return MovementAction(
                self.entity, nx - self.entity.x, ny - self.entity.y
            ).perform()
        return WaitAction(self.entity).perform()

    def _idle(self) -> None:
        """What an Unaware foe does with no quarry — hold position by default."""
        return WaitAction(self.entity).perform()


class HostileEnemy(PerceptiveAI):
    """A foe that closes and fights once it perceives the Ranger, then holds
    ground while Unaware (it lurks, it doesn't drift)."""

    perception = awareness.HOSTILE_PERCEPTION


class IdleWanderer(BaseAI):
    """A peaceful townsperson — a *wandering Bystander* (CONTEXT.md). Never
    fights and never seeks the player; it just drifts, standing most turns and
    now and then stepping onto an open neighbour, so a crowd of them gently
    mills. Bumping it opens talk, not a blow (BumpAction gates on `npc`), so it
    reads as a friendly obstacle in the throng."""

    def perform(self) -> None:
        from lonelands import dice

        # Idle most turns: the crowd should drift, not twitch every step.
        if dice.rng.random() < 0.6:
            return WaitAction(self.entity).perform()
        ddx, ddy = dice.rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        try:
            return MovementAction(self.entity, ddx, ddy).perform()
        except Impossible:
            return WaitAction(self.entity).perform()


class SkittishBeast(PerceptiveAI):
    """Beasts with a short Perception — they only close in when the Ranger comes
    near (the old ``distance <= 4`` now folds into the perception model) and
    drift idly while Unaware."""

    perception = awareness.BEAST_PERCEPTION

    def _idle(self) -> None:
        from lonelands import dice

        ddx, ddy = dice.rng.choice([(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)])
        if ddx or ddy:
            try:
                return MovementAction(self.entity, ddx, ddy).perform()
            except Exception:
                return WaitAction(self.entity).perform()
        return WaitAction(self.entity).perform()
