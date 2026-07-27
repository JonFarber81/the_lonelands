from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np
import tcod

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


class HostileEnemy(BaseAI):
    def __init__(self, entity: "Actor"):
        super().__init__(entity)
        self.path: List[Tuple[int, int]] = []

    def perform(self) -> None:
        target = self.engine.player
        dx = target.x - self.entity.x
        dy = target.y - self.entity.y
        distance = max(abs(dx), abs(dy))

        if self.engine.game_map.visible[self.entity.x, self.entity.y]:
            if distance <= 1:
                return BumpAction(self.entity, dx, dy).perform()
            self.path = self.get_path_to(target.x, target.y)

        if self.path:
            dest_x, dest_y = self.path.pop(0)
            return MovementAction(
                self.entity, dest_x - self.entity.x, dest_y - self.entity.y
            ).perform()

        return WaitAction(self.entity).perform()


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


class SkittishBeast(BaseAI):
    """Beasts that wander, and only close in when the player is very near."""

    def __init__(self, entity: "Actor"):
        super().__init__(entity)
        self.path: List[Tuple[int, int]] = []

    def perform(self) -> None:
        from lonelands import dice

        target = self.engine.player
        dx = target.x - self.entity.x
        dy = target.y - self.entity.y
        distance = max(abs(dx), abs(dy))

        if self.engine.game_map.visible[self.entity.x, self.entity.y] and distance <= 4:
            if distance <= 1:
                return BumpAction(self.entity, dx, dy).perform()
            self.path = self.get_path_to(target.x, target.y)
            if self.path:
                dest_x, dest_y = self.path.pop(0)
                return MovementAction(
                    self.entity, dest_x - self.entity.x, dest_y - self.entity.y
                ).perform()

        # wander
        ddx, ddy = dice.rng.choice([(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)])
        if ddx or ddy:
            try:
                return MovementAction(self.entity, ddx, ddy).perform()
            except Exception:
                return WaitAction(self.entity).perform()
        return WaitAction(self.entity).perform()
