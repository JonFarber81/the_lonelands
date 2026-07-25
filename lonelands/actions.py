from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from lonelands import color
from lonelands import tile_types
from lonelands.dice import skill_check
from lonelands.exceptions import Impossible

if TYPE_CHECKING:
    from lonelands.engine import Engine
    from lonelands.entity import Actor, Entity, Item


class Action:
    def __init__(self, entity: "Actor") -> None:
        self.entity = entity

    @property
    def engine(self) -> "Engine":
        return self.entity.gamemap.engine

    def perform(self) -> None:
        raise NotImplementedError()


class WaitAction(Action):
    def perform(self) -> None:
        pass


class ActionWithDirection(Action):
    def __init__(self, entity: "Actor", dx: int, dy: int):
        super().__init__(entity)
        self.dx = dx
        self.dy = dy

    @property
    def dest_xy(self) -> Tuple[int, int]:
        return self.entity.x + self.dx, self.entity.y + self.dy

    @property
    def blocking_entity(self) -> Optional["Entity"]:
        return self.engine.game_map.get_blocking_entity_at(*self.dest_xy)

    @property
    def target_actor(self) -> Optional["Actor"]:
        return self.engine.game_map.get_actor_at(*self.dest_xy)

    def perform(self) -> None:
        raise NotImplementedError()


class MovementAction(ActionWithDirection):
    def perform(self) -> None:
        dest_x, dest_y = self.dest_xy
        gm = self.engine.game_map
        if not gm.in_bounds(dest_x, dest_y):
            raise Impossible("That way lies the edge of the known world.")
        if not gm.tiles["walkable"][dest_x, dest_y]:
            raise Impossible("The way is blocked.")
        if gm.get_blocking_entity_at(dest_x, dest_y):
            raise Impossible("Something bars the way.")
        self.entity.move(self.dx, self.dy)


class MeleeAction(ActionWithDirection):
    def perform(self) -> None:
        target = self.target_actor
        if target is None or target.fighter is None:
            raise Impossible("There is nothing there to strike.")

        attacker = self.entity
        af = attacker.fighter
        engine = self.engine
        is_player = attacker is engine.player

        weary = attacker.hero.is_weary if attacker.hero else False
        tn = target.fighter.defence
        result = skill_check(tn, af.prowess, weary=weary)

        who = "You" if is_player else f"The {attacker.name}"
        target_name = "you" if target is engine.player else f"the {target.name}"
        atk_color = color.player_atk if is_player else color.enemy_atk

        if result.is_eye:
            engine.message_log.add_message(
                f"{who} strike wildly — the Shadow stirs. {result.describe()}",
                color.sauron_eye,
            )

        if not result.is_success:
            engine.message_log.add_message(
                f"{who} {af.attack_desc} at {target_name} but miss. {result.describe()}",
                color.gray,
            )
            return

        dmg = af.damage + result.tengwar * af.edge
        target.fighter.take_damage(dmg)
        flavour = ""
        if result.tengwar:
            flavour = f" A tengwar flares — {result.tengwar} extra!"
        engine.message_log.add_message(
            f"{who} {af.attack_desc} {target_name} for {dmg} endurance."
            f"{flavour} {result.describe()}",
            atk_color,
        )

        # A great success threatens a Piercing Blow.
        if result.is_great and target.fighter.endurance > 0:
            if not target.fighter.protection_test(af.injury):
                mortal = target.fighter.inflict_wound()
                if mortal:
                    engine.message_log.add_message(
                        f"A mortal blow! {target_name.capitalize()} is struck down.",
                        color.player_die if target is engine.player else color.enemy_die,
                    )
                    target.fighter.endurance = 0
                else:
                    engine.message_log.add_message(
                        f"A piercing blow wounds {target_name}!",
                        color.enemy_atk if is_player else color.player_die,
                    )


class BumpAction(ActionWithDirection):
    def perform(self) -> None:
        if self.target_actor and self.target_actor.fighter and self.target_actor.ai:
            return MeleeAction(self.entity, self.dx, self.dy).perform()
        if self.target_actor and self.target_actor.npc is not None:
            return TalkAction(self.entity, self.target_actor).perform()
        return MovementAction(self.entity, self.dx, self.dy).perform()


class TalkAction(Action):
    def __init__(self, entity: "Actor", target: "Actor"):
        super().__init__(entity)
        self.target = target

    def perform(self) -> None:
        from lonelands import input_handlers

        if self.target.npc is None:
            raise Impossible("They have nothing to say.")
        self.engine.event_handler = input_handlers.DialogHandler(
            self.engine, self.target
        )


class PickupAction(Action):
    def perform(self) -> None:
        actor = self.entity
        x, y = actor.x, actor.y
        inv = actor.inventory
        for item in list(self.engine.game_map.items):
            if item.x == x and item.y == y:
                if len(inv.items) >= inv.capacity:
                    raise Impossible("Your pack is full.")
                self.engine.game_map.entities.remove(item)
                item.parent = inv
                inv.items.append(item)
                self.engine.message_log.add_message(f"You take the {item.name}.", color.item_c)
                event = getattr(item, "pickup_event", None)
                if event:
                    self.engine.quest_log.notify_event(event, self.engine)
                return
        raise Impossible("There is nothing here to pick up.")


class ItemAction(Action):
    def __init__(self, entity: "Actor", item: "Item", target_xy: Optional[Tuple[int, int]] = None):
        super().__init__(entity)
        self.item = item
        self.target_xy = target_xy or (entity.x, entity.y)

    @property
    def target_actor(self) -> Optional["Actor"]:
        return self.engine.game_map.get_actor_at(*self.target_xy)

    def perform(self) -> None:
        if self.item.consumable:
            self.item.consumable.activate(self)


class DropItem(ItemAction):
    def perform(self) -> None:
        if self.entity.equipment and self.entity.equipment.item_is_equipped(self.item):
            self.entity.equipment.toggle_equip(self.item)
        self.entity.inventory.drop(self.item)


class EquipAction(Action):
    def __init__(self, entity: "Actor", item: "Item"):
        super().__init__(entity)
        self.item = item

    def perform(self) -> None:
        self.entity.equipment.toggle_equip(self.item)


class TakeInteractAction(Action):
    """Use whatever the tile the actor stands on offers: stairs, entrances, exits."""

    def perform(self) -> None:
        engine = self.engine
        message = engine.game_world.use_tile()
        if message is None:
            raise Impossible("There is nothing here to enter.")
        engine.message_log.add_message(message, color.welcome_text)
