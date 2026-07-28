from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Tuple

from lonelands import awareness
from lonelands import color
from lonelands.components.fighter import CRIT_BLEED
from lonelands.dice import rng, roll_check, roll_damage
from lonelands.exceptions import Impossible

if TYPE_CHECKING:
    from lonelands.engine import Engine
    from lonelands.entity import Actor, Item
    from lonelands.game_map import GameMap


# --- Hidden Path traps (Snare) --------------------------------------------
@dataclass
class Trap:
    """A snare laid on a tile by the Hidden Path's Trapper. The first foe to
    step onto it springs it: it takes ``damage`` (a dice spec, rolled at trigger)
    and is rooted for ``root_rounds`` rounds, then the trap is spent. The hero
    who set it (and other townsfolk) pass over harmlessly."""

    x: int
    y: int
    damage: str = "1d6"
    root_rounds: int = 2
    char: str = "^"


def _spring_trap(engine: "Engine", actor: "Actor") -> None:
    """Spring a Snare under ``actor`` if one is laid on its tile: roll the trap's
    damage, root the foe, spend the trap, and log the catch when it's in sight."""
    trap = engine.game_map.traps.pop((actor.x, actor.y), None)
    if trap is None:
        return
    tf = actor.fighter
    if tf is None or tf.dead:
        return
    dmg = max(1, roll_damage(trap.damage))
    tf.take_damage(dmg)
    if tf.dead:
        return  # the snare finished it; die() already logged the slaying
    tf.apply_root(trap.root_rounds)
    if engine.game_map.visible[actor.x, actor.y]:
        engine.message_log.add_message(
            f"The {actor.name} springs a hidden snare — {dmg} endurance, and held fast!",
            color.enemy_atk,
        )


# --- Shared combat helpers ------------------------------------------------
def resolve_ambush(hero, target_fighter) -> Tuple[bool, int, int]:
    """The Hidden Path ambush, shared by melee and ranged (ADR 0006, 0014): an
    unseen strike against an **Unaware** foe lands with advantage and bonus
    damage. Returns ``(is_ambush, advantage, bonus_damage)``.

    Stealth is the sole gate — the old "fresh foe" opener is gone; a foe that has
    noticed you (Alerted/Searching) cannot be ambushed until you re-hide and it
    lapses back to Unaware. A **primed** ambush (Shadowstep/Vanish) fires against
    *any* foe regardless of awareness — the blink or vanish has manufactured the
    unseen strike. Advantage is +1 only when a node grants it (or an ambush is
    primed), so a bonus-damage-only ambush still counts as an ambush (its flavour
    and damage) without a second die. A foe (no Hero) never ambushes."""
    if hero is None:
        return False, 0, 0
    bonus = hero.node_bonus("ambush_bonus_damage")
    primed = getattr(hero, "ambush_primed", False)
    target = getattr(target_fighter, "parent", None)
    unseen_opener = (
        target is not None and awareness.is_unaware(target)
        and (hero.ambush_advantage or bonus)
    )
    is_ambush = bool(primed or unseen_opener)
    advantage = 1 if (is_ambush and (hero.ambush_advantage or primed)) else 0
    return is_ambush, advantage, bonus


def _second_person(desc: str) -> str:
    """A creature's third-person attack verb (``"hacks at"``, ``"snaps at"``,
    ``"strikes"``) read in the second person for the player (``"hack at"``,
    ``"snap at"``, ``"strike"``): only the leading verb sheds its ``-s``, so a
    trailing preposition is kept. Without this the melee log reads "You strikes".
    """
    head, sep, rest = desc.partition(" ")
    if head.endswith("s"):
        head = head[:-1]
    return head + (sep + rest if rest else "")


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
    def target_actor(self) -> Optional["Actor"]:
        return self.engine.game_map.get_actor_at(*self.dest_xy)

    def perform(self) -> None:
        raise NotImplementedError()


class MovementAction(ActionWithDirection):
    def perform(self) -> None:
        f = getattr(self.entity, "fighter", None)
        if f is not None and f.is_rooted:
            # Held fast by a Snare/Pinning — the foe strains but cannot move (the
            # Engine ticks the root down each round). The AI catches this and waits.
            raise Impossible("Held fast, it cannot move.")
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
        # A foe that steps onto a laid Snare springs it (the hero and townsfolk
        # pass over harmlessly).
        if self.entity is not self.engine.player and is_hostile_actor(self.entity):
            _spring_trap(self.engine, self.entity)
        # Only the player overhears ambient barks, and only on their own steps
        # (foes move through this same action). Throttled inside barks.emit.
        if self.entity is self.engine.player:
            from lonelands import barks
            barks.emit(self.engine)


class MeleeAction(ActionWithDirection):
    def __init__(self, entity: "Actor", dx: int, dy: int, *, bonus_damage: int = 0):
        super().__init__(entity, dx, dy)
        # Extra damage the strike carries beyond the usual roll (the Long Watch's
        # Charge lends its rush to the blow it lands).
        self.bonus_damage = bonus_damage

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
        hero = getattr(attacker, "hero", None)

        # Hidden Path ambush: an unseen blow against an Unaware foe strikes with
        # advantage and bonus damage (ADR 0014). Read awareness *before* the
        # strike alerts the board — the Shot flow calls the same helper (ADR 0006).
        ambush, advantage, ambush_dmg = resolve_ambush(hero, tf)
        if is_player:
            # A blow — hit or miss — alerts the struck foe and any witness in sight.
            awareness.alert_on_attack(engine, target)

        result = roll_check(af.attack_bonus, tf.defence, advantage=advantage)
        # Tell the roll its Crit threshold (Swift Wrath widens it below 20) so the
        # dice tray and the log agree on a widened Critical.
        result.crit_face = af.crit_face
        engine.note_roll(result, attacker)  # feeds the dice tray (player rolls only)

        who = "You" if is_player else f"The {attacker.name}"
        target_name = "you" if target is engine.player else f"the {target.name}"
        # The player is addressed in the second person ("You strike"), a foe in
        # the third ("The warg savages").
        attack_desc = _second_person(af.attack_desc) if is_player else af.attack_desc
        atk_color = color.player_atk if is_player else color.enemy_atk

        # A Critical is a natural crit-face or higher (Swift Wrath widens it); a
        # natural 1 always fumbles.
        crit = result.is_crit
        if not (crit or result.is_success):
            verb = "swing wildly" if result.is_fumble else "miss"
            engine.message_log.add_message(
                f"{who} {attack_desc} at {target_name} but {verb}.",
                color.sauron_eye if result.is_fumble else color.gray,
            )
            return

        # A hit: roll damage (+ any flat melee-damage perk and a weapon's bonus-
        # vs-kind), subtract Soak — which a piercing weapon partly ignores (a
        # clean blow always stings for 1+).
        raw = roll_damage(af.damage) + af.melee_damage_bonus + af.bonus_vs_damage(target)
        soak = max(0, tf.soak - af.pierce)
        dmg = max(1, raw - soak)
        if crit:
            dmg += roll_damage(af.damage)  # the Critical carries a second roll
        if ambush:
            dmg += ambush_dmg
        dmg += marked_bonus(hero, tf)     # Hunter's Mark: bonus vs the marked foe
        dmg += execute_bonus(hero, tf)    # Executioner: bonus vs a near-dead foe
        dmg += self.bonus_damage          # Charge: the rush behind the blow
        if hero is not None:
            dmg += hero.consume_primed()  # Swift Wrath: spend a primed next-hit
            hero.consume_ambush_prime()   # Shadowstep/Vanish: the unseen strike lands
        result.damage = dmg  # surfaced in the dice tray (same object note_roll kept)
        tf.take_damage(dmg)

        flavour = " A CRITICAL blow!" if crit else ""
        if ambush:
            flavour += " From the shadows!"
        engine.message_log.add_message(
            f"{who} {attack_desc} {target_name} for {dmg} endurance.{flavour}",
            atk_color,
        )

        # Crits (and heavy foes) leave the target bleeding; the Hidden Path's
        # Poisoned Blade envenoms every hero blow the same way.
        stacks = (CRIT_BLEED if crit else 0) + af.bleed_on_hit + af.melee_bleed
        if stacks and tf.endurance > 0:
            tf.apply_bleed(stacks)
            engine.message_log.add_message(
                f"{target_name.capitalize()} {'are' if target is engine.player else 'is'} "
                f"left bleeding!",
                color.player_die if target is engine.player else color.enemy_atk,
            )

        # Thornguard (Long Watch Warden): a foe that lands a blow on the hero
        # takes bite-back damage. Only a hero's guard bristles, and only a foe
        # (not the hero themselves) is pricked by it.
        if target is engine.player and not is_player:
            hero_t = getattr(target, "hero", None)
            thorns = hero_t.node_bonus("thorns_damage") if hero_t is not None else 0
            if thorns and not af.dead:
                af.take_damage(thorns)
                if not af.dead and engine.game_map.visible[attacker.x, attacker.y]:
                    engine.message_log.add_message(
                        f"The {attacker.name} is pricked by your guard for "
                        f"{thorns} endurance.", color.enemy_atk)


# --- Ranged: arrows & the Shot (ADR 0006, issue #46) ----------------------
# Arrow recovery: this fraction of loosed arrows can be picked back up (they
# land on the target's tile). A deliberate future perk lever.
ARROW_RECOVERY_CHANCE = 0.5


def _ammo_stack(actor: "Actor"):
    """The actor's arrow Stack, if the pack holds one (matched by the canonical
    ammo name, since arrows are a fungible Stack, not distinct gear)."""
    from lonelands import content
    inv = getattr(actor, "inventory", None)
    if inv is None:
        return None
    for item in inv.items:
        if item.stackable and item.name == content.AMMO_NAME:
            return item
    return None


def _spend_one_arrow(stack: "Item", actor: "Actor") -> None:
    """Consume a single arrow from ``stack``, removing the empty Stack."""
    stack.quantity -= 1
    if stack.quantity <= 0 and actor.inventory is not None:
        actor.inventory.remove(stack)


def king_dist(x1: int, y1: int, x2: int, y2: int) -> int:
    """Grid (king-move / Chebyshev) distance between two tiles — the metric a
    Shot's range falloff and every Path deed's reach use. Shared with the
    targeting handlers in :mod:`lonelands.input_handlers`."""
    return max(abs(x1 - x2), abs(y1 - y2))


def _chebyshev(a: "Actor", b: "Actor") -> int:
    """King-move distance between two actors."""
    return king_dist(a.x, a.y, b.x, b.y)


def _sign(n: int) -> int:
    """-1, 0, or +1 — the per-axis step toward a target (a line/backstep ray)."""
    return (n > 0) - (n < 0)


def is_hostile_actor(actor: "Actor") -> bool:
    """Whether ``actor`` is a living combatant (not a townsfolk) — a valid mark
    for a Shot and the thing whose adjacency spoils one. Callers exclude the
    acting hero themselves (the hero also matches this shape)."""
    return (
        actor.npc is None
        and actor.fighter is not None and not actor.fighter.dead
    )


def _has_adjacent_hostile(engine: "Engine", actor: "Actor") -> bool:
    """Whether a living, non-friendly fighter stands in any of ``actor``'s eight
    neighbours — the point-blank condition that spoils a Shot (Disadvantage)."""
    gm = engine.game_map
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            other = gm.get_actor_at(actor.x + dx, actor.y + dy)
            if other is not None and other is not actor and is_hostile_actor(other):
                return True
    return False


def _maybe_recover_arrow(engine: "Engine", target: "Actor") -> None:
    """Half of loosed arrows survive to be picked up: drop one on the target's
    tile on a coin-flip (ADR 0006). Recovery rate is a future perk lever."""
    if rng.random() >= ARROW_RECOVERY_CHANCE:
        return
    from lonelands import content
    content.arrows.spawn(engine.game_map, target.x, target.y)


def marked_bonus(hero, target_fighter) -> int:
    """Extra damage the hero deals to a **marked** foe (Far Shot's Hunter's Mark
    — a status + context-conditional). 0 for a foe attacker or an unmarked
    target."""
    if hero is None or target_fighter is None or not target_fighter.marked:
        return 0
    return hero.node_bonus("marked_damage")


def execute_bonus(hero, target_fighter) -> int:
    """Extra melee damage the Long Watch's Executioner deals to a foe at or below
    a third of its Endurance (a context-conditional). 0 without the node, for a
    healthy foe, or for a foe attacker."""
    if hero is None or target_fighter is None or target_fighter.max_endurance <= 0:
        return 0
    frac = target_fighter.endurance / target_fighter.max_endurance
    total = 0
    for n in hero.owned_nodes():
        if n.execute_threshold > 0 and frac <= n.execute_threshold:
            total += n.execute_damage * hero.nodes.get(n.id, 0)
    return total


def resolve_shot(engine: "Engine", attacker: "Actor", target: "Actor", *,
                 aimed: bool = False, recover: bool = True) -> None:
    """Resolve a single arrow from ``attacker`` at ``target`` (ADR 0006): the d20
    core keyed off Wits, range falloff, point-blank Disadvantage, the shared
    Hidden Path ambush, and Hunter's Mark bonus damage. **Spends no ammo** — the
    caller does (one draw may loose several arrows, e.g. Multishot). ``aimed``
    forces a guaranteed Critical (Aimed Shot). No Bleed on a Shot Critical."""
    af = attacker.fighter
    tf = target.fighter
    if tf is None or tf.dead:
        return
    is_player = attacker is engine.player
    hero = getattr(attacker, "hero", None)

    distance = _chebyshev(attacker, target)
    penalty = af.range_penalty(distance)

    # A foe at your elbow spoils the aim (Disadvantage); the Hidden Path ambush
    # lends Advantage. The two fold into one signed advantage int.
    adjacent = _has_adjacent_hostile(engine, attacker)
    ambush, ambush_adv, ambush_dmg = resolve_ambush(hero, tf)
    if is_player:
        # Loosing an arrow alerts the mark and any foe with a line to the fight
        # (read awareness first, above, so this Shot still lands as an ambush).
        awareness.alert_on_attack(engine, target)
    advantage = ambush_adv + (-1 if adjacent else 0)

    # A Shot Crits only on a natural 20 — Swift Wrath's widened melee crit does
    # not carry to the bow (ADR 0006), so the default crit_face stands.
    result = roll_check(af.ranged_attack_bonus - penalty, tf.defence,
                        advantage=advantage)
    engine.note_roll(result, attacker)  # feeds the dice tray (player rolls only)

    who = "You" if is_player else f"The {attacker.name}"
    target_name = "you" if target is engine.player else f"the {target.name}"
    loose = "loose" if is_player else "looses"
    strike = "strike" if is_player else "strikes"
    atk_color = color.player_atk if is_player else color.enemy_atk

    # Aimed Shot lands a sure Critical even on a wayward roll (never on a Fumble).
    crit = result.is_crit or (aimed and not result.is_fumble)
    if not (crit or result.is_success):
        verb = "the arrow flies wild" if result.is_fumble else "miss"
        engine.message_log.add_message(
            f"{who} {loose} an arrow at {target_name} but {verb}.",
            color.sauron_eye if result.is_fumble else color.gray,
        )
        if recover:
            _maybe_recover_arrow(engine, target)
        return

    # A hit: roll the bow's damage (+ any Far Shot damage node), subtract Soak —
    # a clean shot always stings for 1+. No pierce, no Bleed.
    raw = roll_damage(af.ranged_damage) + af.ranged_damage_bonus
    dmg = max(1, raw - tf.soak)
    if crit:
        dmg += roll_damage(af.ranged_damage)  # the Critical carries a second roll
    if ambush:
        dmg += ambush_dmg
    dmg += marked_bonus(hero, tf)             # Hunter's Mark: bonus vs the marked foe
    if hero is not None:
        hero.consume_ambush_prime()   # Shadowstep/Vanish: the unseen shot lands
    result.damage = dmg  # surfaced in the dice tray (same object note_roll kept)
    tf.take_damage(dmg)

    flavour = " A CRITICAL shot!" if crit else ""
    if ambush:
        flavour += " From the shadows!"
    engine.message_log.add_message(
        f"{who} {loose} an arrow and {strike} {target_name} for {dmg} endurance.{flavour}",
        atk_color,
    )
    if recover:
        _maybe_recover_arrow(engine, target)


class RangedAttackAction(Action):
    """Loose an arrow at a chosen foe (ADR 0006): a full turn, one arrow spent.
    The single-shot resolution lives in :func:`resolve_shot`, shared with the Far
    Shot volley deeds (Multishot/Piercing Shot/Harrying Shot)."""

    def __init__(self, entity: "Actor", target: "Actor"):
        super().__init__(entity)
        self.target = target

    def perform(self) -> None:
        attacker = self.entity
        af = attacker.fighter
        engine = self.engine
        if af is None or not af.has_ranged_weapon:
            raise Impossible("You have no bow readied.")
        target = self.target
        if target is None or target.fighter is None or target.fighter.dead:
            raise Impossible("There is nothing there to shoot.")
        ammo = _ammo_stack(attacker)
        if ammo is None:
            raise Impossible("Your quiver is empty.")

        _spend_one_arrow(ammo, attacker)  # an arrow is spent, hit or miss
        hero = getattr(attacker, "hero", None)
        aimed = hero.consume_aimed_shot() if hero is not None else False
        resolve_shot(engine, attacker, target, aimed=aimed)


# --- Far Shot volley & mark deeds (ADR 0011, #75) -------------------------
# Multishot/Arrow Storm (arc), Piercing Shot (line), Harrying Shot (fire + hop
# back), Hunter's Mark (mark a foe). Each is picked with a lock-on handler and
# resolved here with map access; a bow and an arrow are spent, and the deed's
# cooldown is charged. All count as the player's turn.
def _spend_shot_ammo(entity: "Actor") -> None:
    """Guard a Far Shot deed on a readied bow and a nocked arrow, then spend one
    (the single special draw). Raises Impossible with neither."""
    af = entity.fighter
    if af is None or not af.has_ranged_weapon:
        raise Impossible("You have no bow readied.")
    ammo = _ammo_stack(entity)
    if ammo is None:
        raise Impossible("Your quiver is empty.")
    _spend_one_arrow(ammo, entity)


def _hostiles_in_sight(engine: "Engine", exclude: "Actor"):
    """Every living non-friendly fighter the player can see (not ``exclude``)."""
    gm = engine.game_map
    return [a for a in gm.actors
            if a is not exclude and is_hostile_actor(a) and gm.visible[a.x, a.y]]


class _FoeDeedAction(Action):
    """A Path deed aimed at a single chosen foe — the Far Shot volley and mark,
    the Long Watch's Charge. Carries the firing node id and the target foe, and
    shares the ready-check + still-there guard each such deed opens with."""

    def __init__(self, entity: "Actor", node_id: str, target: "Actor"):
        super().__init__(entity)
        self.node_id = node_id
        self.target = target

    def _begin(self, verb: str):
        """The hero and its ready active node, with the target re-validated (it
        may have died between the lock-on and the strike). Raises Impossible if
        the deed isn't ready or the foe is gone."""
        hero, node = _ready_active(self.entity, self.node_id)
        target = self.target
        if target is None or target.fighter is None or target.fighter.dead:
            raise Impossible(f"There is nothing there to {verb}.")
        return hero, node, target


class MultishotAction(_FoeDeedAction):
    """Loose a spread (Multishot / Arrow Storm): a Shot at the marked foe and at
    every other foe within the deed's ``radius`` tiles of it. One arrow, one
    turn."""

    def perform(self) -> None:
        hero, node, target = self._begin("shoot")
        engine = self.engine
        _spend_shot_ammo(self.entity)
        radius = node.active.radius
        # The mark first, then the spread around it — nearest-first so the log
        # reads outward from the centre.
        foes = [target] + sorted(
            (a for a in _hostiles_in_sight(engine, self.entity)
             if a is not target and king_dist(target.x, target.y, a.x, a.y) <= radius),
            key=lambda a: king_dist(target.x, target.y, a.x, a.y))
        engine.message_log.add_message(
            "You loose a spread of arrows!", color.player_atk)
        for foe in foes:
            resolve_shot(engine, self.entity, foe, recover=False)
        hero.begin_cooldown(self.node_id)


class PiercingShotAction(_FoeDeedAction):
    """A shaft that passes clean through (Piercing Shot): a Shot at every foe on
    the line from the hero through the chosen foe, out to the deed's reach. One
    arrow, one turn."""

    def perform(self) -> None:
        hero, node, target = self._begin("shoot")
        engine = self.engine
        _spend_shot_ammo(self.entity)
        ox, oy = self.entity.x, self.entity.y
        stepx = _sign(target.x - ox)
        stepy = _sign(target.y - oy)
        reach = node.active.reach
        gm = engine.game_map
        engine.message_log.add_message(
            "You loose a piercing shaft!", color.player_atk)
        # Walk the ray outward, striking each foe standing on it (the wall behind
        # the last foe stops nothing — the reach cap does).
        for step in range(1, reach + 1):
            x, y = ox + stepx * step, oy + stepy * step
            if not gm.in_bounds(x, y):
                break
            foe = gm.get_actor_at(x, y)
            if foe is not None and is_hostile_actor(foe):
                resolve_shot(engine, self.entity, foe, recover=False)
        hero.begin_cooldown(self.node_id)


class HarryingShotAction(_FoeDeedAction):
    """Fire and fade (Harrying Shot): a Shot at the chosen foe, then a hop one
    tile straight back from it if that ground is open. One arrow, one turn."""

    def perform(self) -> None:
        hero, _node, target = self._begin("shoot")
        engine = self.engine
        _spend_shot_ammo(self.entity)
        resolve_shot(engine, self.entity, target)
        # Hop one tile directly away from the foe, if that ground is clear.
        gm = engine.game_map
        me = self.entity
        bx = me.x - _sign(target.x - me.x)
        by = me.y - _sign(target.y - me.y)
        if ((bx, by) != (me.x, me.y) and gm.in_bounds(bx, by)
                and gm.tiles["walkable"][bx, by]
                and gm.get_blocking_entity_at(bx, by) is None):
            me.x, me.y = bx, by
            engine.message_log.add_message(
                "You loose and fade back a step.", color.hope_gain)
        hero.begin_cooldown(self.node_id)


class HuntersMarkAction(_FoeDeedAction):
    """Mark a chosen visible foe within reach (Hunter's Mark): it takes bonus
    damage from your every hit until another is marked. Marks one foe at a time,
    so the previous mark is cleared first. A full turn."""

    def perform(self) -> None:
        hero, node, target = self._begin("mark")
        engine = self.engine
        if _chebyshev(target, self.entity) > node.active.reach:
            raise Impossible("That foe is too far to mark.")
        if not engine.game_map.visible[target.x, target.y]:
            raise Impossible("You cannot see that foe.")
        # Only one mark at a time — clear any existing mark first.
        for a in engine.game_map.actors:
            if a.fighter is not None:
                a.fighter.marked = False
        target.fighter.marked = True
        hero.begin_cooldown(self.node_id)
        engine.message_log.add_message(
            f"You mark the {target.name} as your quarry!", color.hope_gain)


# --- Long Watch Reaver deeds (ADR 0011, #76) ------------------------------
# Charge (rush a foe and strike with bonus damage — a dash reused from the
# Hidden Path's blink) and Sweeping Blow (one melee attack against every foe
# pressed around you). Both count as the player's turn.
class ChargeAction(_FoeDeedAction):
    """Rush to a chosen foe within reach and strike it with bonus damage. Picked
    with a lock-on; resolves the dash here, then a real melee blow (so every
    passive — crit range, Executioner, on-hit Bleed — folds in as usual)."""

    def perform(self) -> None:
        hero, node, target = self._begin("charge")
        engine = self.engine
        me = self.entity
        reach = node.active.reach
        if _chebyshev(me, target) > reach:
            raise Impossible("That foe is too far to charge.")
        gm = engine.game_map
        # Trace the rush toward the foe *without* moving, tile by tile, until we
        # stand adjacent (or a wall/creature bars the lane) — so a blocked charge
        # fails cleanly, without stranding the hero mid-lane and eating the turn.
        cx, cy, steps = me.x, me.y, 0
        while king_dist(cx, cy, target.x, target.y) > 1 and steps < reach:
            nx, ny = cx + _sign(target.x - cx), cy + _sign(target.y - cy)
            if (not gm.in_bounds(nx, ny) or not gm.tiles["walkable"][nx, ny]
                    or gm.get_blocking_entity_at(nx, ny) is not None):
                break
            cx, cy, steps = nx, ny, steps + 1
        if king_dist(cx, cy, target.x, target.y) > 1:
            raise Impossible("Something bars your charge.")
        me.x, me.y = cx, cy
        if steps:
            engine.message_log.add_message("You charge in!", color.player_atk)
        hero.begin_cooldown(self.node_id)
        bonus = max(0, roll_damage(node.active.magnitude))
        MeleeAction(me, _sign(target.x - me.x), _sign(target.y - me.y),
                    bonus_damage=bonus).perform()


class SweepAction(Action):
    """One great arc: a melee attack against every foe adjacent to the hero
    (Sweeping Blow). Untargeted, but map-bound — so it resolves in an Action
    rather than :meth:`Hero.activate_ability`."""

    def __init__(self, entity: "Actor", node_id: str):
        super().__init__(entity)
        self.node_id = node_id

    def perform(self) -> None:
        hero, _node = _ready_active(self.entity, self.node_id)
        engine = self.engine
        me = self.entity
        gm = engine.game_map
        dirs = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if (dx or dy) and (a := gm.get_actor_at(me.x + dx, me.y + dy)) is not None
                and is_hostile_actor(a)]
        if not dirs:
            raise Impossible("There is no one pressed close to sweep.")
        engine.message_log.add_message(
            "You sweep your blade in a wide arc!", color.player_atk)
        hero.begin_cooldown(self.node_id)
        for dx, dy in dirs:
            try:
                MeleeAction(me, dx, dy).perform()
            except Impossible:
                pass  # a foe felled mid-sweep by an earlier strike is simply gone


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
                # Gear shows its full stat line on the spot — there is no
                # identification (ADR 0005).
                line = ""
                if item.equippable is not None:
                    line = f" [{item.equippable.stat_line()}]"
                self.engine.message_log.add_message(
                    f"You take the {item.name}.{line}", color.item_c)
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


class ActivateAbilityAction(Action):
    """Fire one of the hero's Path actives (a node's active — ADR 0011).

    A heal/stance resolves at once; a "wrath"-style active primes the hero's next
    melee hit. Either way this counts as the player's turn, so cooldowns tick and
    foes act afterwards. Impossible if the ability isn't ready."""

    def __init__(self, entity: "Actor", node_id: str):
        super().__init__(entity)
        self.node_id = node_id

    def perform(self) -> None:
        hero = getattr(self.entity, "hero", None)
        if hero is None or not hero.ability_ready(self.node_id):
            raise Impossible("That ability is not ready.")
        message = hero.activate_ability(self.node_id)
        if message is None:
            raise Impossible("That ability is not ready.")
        self.engine.message_log.add_message(message, color.hope_gain)


# --- Hidden Path targeted deeds (ADR 0011, #77) ---------------------------
# Shadowstep/Disengage (blink to a tile), Snare (lay a trap), Pinning (root a
# foe). Each is picked with a targeting handler, resolves here with map access,
# and charges its cooldown via the Hero. All count as the player's turn.
def _ready_active(entity: "Actor", node_id: str):
    """The hero and the ready active node for ``node_id`` — raising Impossible if
    the deed isn't the hero's, isn't owned, or isn't off cooldown."""
    hero = getattr(entity, "hero", None)
    if hero is None or not hero.ability_ready(node_id):
        raise Impossible("That deed is not ready.")
    from lonelands import perks
    node = perks.ALL_NODES.get(node_id)
    if node is None or node.active is None:
        raise Impossible("That deed is not ready.")
    return hero, node


def tile_targetable(gm: "GameMap", ox: int, oy: int, x: int, y: int,
                    reach: int) -> bool:
    """Whether ``(x, y)`` is a legal blink/snare destination from ``(ox, oy)``:
    on the map, a *different* tile within ``reach``, in sight, and open (walkable
    and unblocked). The single predicate the targeting reticle
    (:class:`input_handlers.TileTargetHandler`) and the resolving Actions share,
    so what counts as a legal tile can't drift between them."""
    return (
        gm.in_bounds(x, y)
        and (x, y) != (ox, oy)
        and king_dist(ox, oy, x, y) <= reach
        and bool(gm.visible[x, y])
        and bool(gm.tiles["walkable"][x, y])
        and gm.get_blocking_entity_at(x, y) is None
    )


def _tile_reachable(engine: "Engine", actor: "Actor", x: int, y: int,
                    reach: int) -> None:
    """Backstop guard for a resolving blink/snare (the targeting reticle already
    pre-validates with the same :func:`tile_targetable` predicate). Raises
    Impossible when the tile isn't a legal target."""
    if not tile_targetable(engine.game_map, actor.x, actor.y, x, y, reach):
        raise Impossible("You cannot reach that spot.")


class _TileTargetedAction(Action):
    """A deed aimed at a chosen tile (Shadowstep/Disengage's blink, Snare's laid
    trap): it carries the firing node and the target tile."""

    def __init__(self, entity: "Actor", node_id: str, target_xy: Tuple[int, int]):
        super().__init__(entity)
        self.node_id = node_id
        self.target_xy = target_xy


class ShadowstepAction(_TileTargetedAction):
    """Blink to a chosen empty tile within reach (Shadowstep/Disengage). If the
    deed primes an ambush, the next strike lands unseen. A full turn."""

    def perform(self) -> None:
        hero, node = _ready_active(self.entity, self.node_id)
        spec = node.active
        x, y = self.target_xy
        _tile_reachable(self.engine, self.entity, x, y, spec.reach)
        self.entity.x, self.entity.y = x, y
        if spec.primes_ambush:
            hero.prime_ambush()
        hero.begin_cooldown(self.node_id)
        tail = " — you ready an unseen strike." if spec.primes_ambush else "."
        self.engine.message_log.add_message(
            f"You slip through the shadows{tail}", color.hope_gain)


class SnareAction(_TileTargetedAction):
    """Lay a Snare trap on a chosen tile within reach (a full turn)."""

    def perform(self) -> None:
        hero, node = _ready_active(self.entity, self.node_id)
        spec = node.active
        x, y = self.target_xy
        _tile_reachable(self.engine, self.entity, x, y, spec.reach)
        if (x, y) in self.engine.game_map.traps:
            raise Impossible("A snare is already laid there.")
        self.engine.game_map.traps[(x, y)] = Trap(
            x, y, damage=spec.magnitude, root_rounds=spec.duration)
        hero.begin_cooldown(self.node_id)
        self.engine.message_log.add_message(
            "You set a hidden snare among the shadows.", color.hope_gain)


class PinningAction(Action):
    """Root a chosen visible foe within reach for the deed's duration (a full
    turn)."""

    def __init__(self, entity: "Actor", node_id: str, target: "Actor"):
        super().__init__(entity)
        self.node_id = node_id
        self.target = target

    def perform(self) -> None:
        hero, node = _ready_active(self.entity, self.node_id)
        spec = node.active
        target = self.target
        if target is None or target.fighter is None or target.fighter.dead:
            raise Impossible("There is nothing there to pin.")
        if _chebyshev(target, self.entity) > spec.reach:
            raise Impossible("That foe is too far to pin.")
        if not self.engine.game_map.visible[target.x, target.y]:
            raise Impossible("You cannot see that foe.")
        target.fighter.apply_root(spec.duration)
        hero.begin_cooldown(self.node_id)
        self.engine.message_log.add_message(
            f"You pin the {target.name} where it stands!", color.hope_gain)


class TakeInteractAction(Action):
    """Use whatever the tile the actor stands on offers: stairs, entrances, exits."""

    def perform(self) -> None:
        engine = self.engine
        message = engine.game_world.use_tile()
        if message is None:
            raise Impossible("There is nothing here to enter.")
        engine.message_log.add_message(message, color.welcome_text)
