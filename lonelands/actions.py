from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from lonelands import color
from lonelands import tile_types
from lonelands.components.fighter import CRIT_BLEED
from lonelands.dice import roll_check, roll_damage
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
            # The player walking off an edge crosses into the neighbouring
            # Region; anyone else is stopped by the bounds of the map.
            world = getattr(self.engine, "game_world", None)
            if (
                self.entity is self.engine.player
                and world is not None
                and world.cross_edge(self.dx, self.dy)
            ):
                return
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
        return self._resolve_attack(target)

    def _resolve_attack(self, target: "Actor") -> None:
        """One d20 attack, whoever swings: ``d20 + attack bonus vs Defence``. On
        a hit, roll damage and subtract the target's Soak. A natural 20 auto-hits
        for bonus damage and opens a Bleed; a natural 1 auto-misses. The dice
        tray only reflects the player's own rolls (``note_roll`` gates on that)."""
        attacker = self.entity
        af = attacker.fighter
        tf = target.fighter
        engine = self.engine
        is_player = attacker is engine.player

        result = roll_check(af.attack_bonus, tf.defence)
        engine.note_roll(result, attacker)  # feeds the dice tray (player rolls only)

        who = "You" if is_player else f"The {attacker.name}"
        target_name = "you" if target is engine.player else f"the {target.name}"
        atk_color = color.player_atk if is_player else color.enemy_atk

        if not result.is_success:
            verb = "swing wildly" if result.is_fumble else "miss"
            engine.message_log.add_message(
                f"{who} {af.attack_desc} at {target_name} but {verb}.",
                color.sauron_eye if result.is_fumble else color.gray,
            )
            return

        # A hit: roll damage, subtract Soak (a clean blow always stings for 1+).
        raw = roll_damage(af.damage)
        dmg = max(1, raw - tf.soak)
        crit = result.is_crit
        if crit:
            dmg += roll_damage(af.damage)  # the Critical carries a second roll
        result.damage = dmg  # surfaced in the dice tray (same object note_roll kept)
        tf.take_damage(dmg)

        flavour = " A CRITICAL blow!" if crit else ""
        engine.message_log.add_message(
            f"{who} {af.attack_desc} {target_name} for {dmg} endurance.{flavour}",
            atk_color,
        )

        # Crits (and heavy foes) leave the target bleeding.
        stacks = (CRIT_BLEED if crit else 0) + af.bleed_on_hit
        if stacks and tf.endurance > 0:
            tf.apply_bleed(stacks)
            engine.message_log.add_message(
                f"{target_name.capitalize()} {'are' if target is engine.player else 'is'} "
                f"left bleeding!",
                color.player_die if target is engine.player else color.enemy_atk,
            )


class BumpAction(ActionWithDirection):
    def perform(self) -> None:
        # A friendly NPC is spoken to, never struck; anyone else with a living
        # fighter (the player included) is a valid combat target. A corpse stays
        # on the map as a dead actor with a fighter, so gate on `not dead` — that
        # lets the player step onto the tile and pick up any loot underneath.
        target = self.target_actor
        if target and target.npc is not None:
            return TalkAction(self.entity, target).perform()
        if target and target.fighter and not target.fighter.dead:
            return MeleeAction(self.entity, self.dx, self.dy).perform()
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
                inv.add(item)  # merges fungible stacks; raises if the pack is full
                self.engine.game_map.entities.remove(item)
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
