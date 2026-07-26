"""The five Ranger Paths and the perks bought along them.

This module is **pure data + tiny effect-hook objects**: it imports no engine,
no tcod, no live game state. The Hero owns which perks are bought and the
per-perk runtime (cooldowns, primed hits, stances); the Fighter and the combat
actions *query* these declarative fields to fold perk effects into real numbers.

Model
-----
A :class:`Perk` is a frozen dataclass carrying:

* identity — ``id`` / ``path`` / ``name`` / ``desc``
* economy — ``cost`` (perk points) and ``tier`` (its depth within the Path)
* ``capstone`` — a Path-defining perk gated behind full investment
* passive modifier fields — flat bonuses the Fighter reads (``atk_bonus``,
  ``defence_bonus``, ``soak_bonus``, ``max_endurance_bonus``,
  ``melee_damage_bonus``, ``crit_range``) plus fields for systems not yet built
  (``ranged_bonus``,
  ``ranged_damage_bonus``, ``stealth_bonus`` — see the TODOs where they'd apply)
* ambush fields — a first-strike advantage / bonus damage the melee flow reads
* rally fields — a low-Endurance trigger the Fighter reads live
* ``active`` — an optional :class:`ActiveSpec` for a charge/cooldown ability

Prerequisite rule (documented, enforced in Hero.can_buy)
--------------------------------------------------------
* A non-capstone perk of ``tier`` N requires owning **at least one** perk of a
  lower tier *in the same Path* (tier-1 perks are always available).
* A ``capstone`` requires owning **every** non-capstone perk in its Path.

A Ranger blends freely across Paths — prerequisites only ever look within a
single Path, never across them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Effect hooks
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ActiveSpec:
    """A charge/cooldown active ability. Interpreted by the Hero/actions layer.

    ``kind`` selects the mechanic:
      * ``"wrath"``  — prime the next successful melee hit for ``magnitude``
                        extra damage (a dice spec). Cooldown starts when the
                        primed hit lands.
      * ``"heal"``   — immediately restore ``magnitude`` Endurance (dice spec).
                        Cooldown starts at once.
      * ``"stance"`` — grant ``soak`` extra Soak for ``duration`` rounds.
                        Cooldown starts at once.
    """

    name: str
    kind: str
    cooldown: int = 0           # player-turns before it may be used again
    magnitude: str = "0"        # dice spec for wrath/heal effects
    soak: int = 0               # stance: extra Soak while active
    duration: int = 0           # stance: rounds the effect persists


@dataclass(frozen=True)
class Perk:
    id: str
    path: str
    name: str
    desc: str
    cost: int = 1
    tier: int = 1
    capstone: bool = False

    # --- live passive combat modifiers (read by Fighter) ------------------
    atk_bonus: int = 0
    defence_bonus: int = 0
    soak_bonus: int = 0
    max_endurance_bonus: int = 0  # raises the single Endurance pool at once
    melee_damage_bonus: int = 0
    crit_range: int = 0          # lowers the crit face by this (20 -> 20-crit_range)

    # --- on-kill trigger (read by Fighter.die when the hero slays a foe) ---
    readies_actives_on_kill: bool = False  # a kill clears this hero's active cooldowns

    # --- fields for systems not yet built (wired where cheap, else TODO) ---
    ranged_bonus: int = 0        # TODO: to-hit for a future ranged attack action
    ranged_damage_bonus: int = 0  # TODO: damage for a future ranged attack action
    stealth_bonus: int = 0       # TODO: consumed by a future stealth/detection layer

    # --- ambush (read by MeleeAction on a first strike) -------------------
    ambush_advantage: bool = False   # advantage on the opening blow vs a fresh foe
    ambush_bonus_damage: int = 0     # flat extra damage on that opening blow

    # --- low-Endurance rally trigger (read live by Fighter) ---------------
    rally_threshold: float = 0.0     # fires while endurance <= threshold * max
    rally_atk_bonus: int = 0
    rally_soak_bonus: int = 0

    # --- active ability ---------------------------------------------------
    active: Optional[ActiveSpec] = None


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Path:
    id: str
    name: str
    blurb: str
    perks: List[Perk] = field(default_factory=list)


PATHS: List[Path] = [
    Path(
        "long_watch", "The Long Watch",
        "Endure and protect — the Ranger who holds the line.",
        [
            Perk("lw_endure", "long_watch", "Steady Endurance",
                 "Long years in the wild have hardened you. +6 max Endurance.",
                 cost=1, tier=1, max_endurance_bonus=6),
            Perk("lw_soak", "long_watch", "Iron Skin",
                 "You shrug off blows that would fell lesser folk. +1 Soak.",
                 cost=1, tier=1, soak_bonus=1),
            Perk("lw_guard", "long_watch", "Watchful Guard",
                 "Ever wary, ever ready. +1 Defence.",
                 cost=1, tier=2, defence_bonus=1),
            Perk("lw_hold", "long_watch", "Hold the Line",
                 "Set your feet and weather the storm: +4 Soak for 3 rounds.",
                 cost=2, tier=3, capstone=True,
                 active=ActiveSpec("Hold the Line", "stance",
                                   cooldown=6, soak=4, duration=3)),
        ],
    ),
    Path(
        "swift_wrath", "The Swift Wrath",
        "Melee offence — the Ranger whose blade strikes first and hardest.",
        [
            Perk("sw_hone", "swift_wrath", "Honed Edge",
                 "Your strokes find the gap. +1 to-hit in melee.",
                 cost=1, tier=1, atk_bonus=1),
            Perk("sw_wrath", "swift_wrath", "Wrath",
                 "Loose your fury: your next hit deals +2d6 damage.",
                 cost=1, tier=1,
                 active=ActiveSpec("Wrath", "wrath", cooldown=4, magnitude="2d6")),
            Perk("sw_might", "swift_wrath", "Killing Might",
                 "Every blow carries your full weight. +2 melee damage.",
                 cost=1, tier=2, melee_damage_bonus=2),
            Perk("sw_reaver", "swift_wrath", "Reaver's Instinct",
                 "You feel the killing stroke before it lands: melee crits on a "
                 "natural 19 or 20, and every kill readies your active deeds anew.",
                 cost=2, tier=3, capstone=True, crit_range=1,
                 readies_actives_on_kill=True),
        ],
    ),
    Path(
        "far_shot", "The Far Shot",
        "Marksmanship — the Ranger who kills before the foe closes.",
        [
            # NOTE: no ranged attack action exists yet. The ranged_* fields are
            # authored so a future ranged flow can read them; only fs_footwork's
            # Defence is live today. See TODO(ranged) in fighter.py / actions.py.
            Perk("fs_aim", "far_shot", "Steady Aim",
                 "A patient eye down the shaft. +1 to-hit with bows. (ranged)",
                 cost=1, tier=1, ranged_bonus=1),
            Perk("fs_fletcher", "far_shot", "Fletcher's Eye",
                 "Your arrows bite deep. +1 ranged damage. (ranged)",
                 cost=1, tier=1, ranged_damage_bonus=1),
            Perk("fs_footwork", "far_shot", "Skirmisher",
                 "You keep the enemy at bay and yourself hard to pin. +1 Defence.",
                 cost=1, tier=2, defence_bonus=1),
            Perk("fs_deadeye", "far_shot", "Deadeye",
                 "No range is too far. +2 to-hit and +2 damage with bows. (ranged)",
                 cost=2, tier=3, capstone=True,
                 ranged_bonus=2, ranged_damage_bonus=2),
        ],
    ),
    Path(
        "hidden_path", "The Hidden Path",
        "Stealth and ambush — the Ranger who strikes from the shadows.",
        [
            Perk("hp_stealth", "hidden_path", "Silent Tread",
                 "You move as a shadow among shadows. +2 Stealth. (stealth)",
                 cost=1, tier=1, stealth_bonus=2),
            Perk("hp_ambush", "hidden_path", "Ambush",
                 "Your opening blow against an unmarked foe strikes with "
                 "advantage and +2 damage.",
                 cost=1, tier=1, ambush_advantage=True, ambush_bonus_damage=2),
            Perk("hp_shadow", "hidden_path", "Shadowstep",
                 "You slip aside as the blow falls. +1 Defence.",
                 cost=1, tier=2, defence_bonus=1),
            Perk("hp_deathblow", "hidden_path", "Deathblow",
                 "The unseen strike is a killing one. +6 damage on an ambush.",
                 cost=2, tier=3, capstone=True,
                 ambush_advantage=True, ambush_bonus_damage=6),
        ],
    ),
    Path(
        "kindled_heart", "The Kindled Heart",
        "Spirit and defiance — the Ranger whose will outlasts the dark.",
        [
            Perk("kh_wind", "kindled_heart", "Second Wind",
                 "Draw on hidden reserves: restore 2d6 Endurance.",
                 cost=1, tier=1,
                 active=ActiveSpec("Second Wind", "heal", cooldown=6, magnitude="2d6")),
            Perk("kh_defiance", "kindled_heart", "Defiance",
                 "Cornered and bloodied, you fight all the harder: +2 to-hit "
                 "while at or below a third of your Endurance.",
                 cost=1, tier=1, rally_threshold=1 / 3, rally_atk_bonus=2),
            Perk("kh_dread", "kindled_heart", "Dreadful Aspect",
                 "Foes flinch from the grey terror in your eyes. +1 Defence.",
                 cost=1, tier=2, defence_bonus=1),
            Perk("kh_undaunted", "kindled_heart", "Undaunted",
                 "Half-dead is not dead: +2 to-hit and +2 Soak while at or below "
                 "half your Endurance.",
                 cost=2, tier=3, capstone=True,
                 rally_threshold=1 / 2, rally_atk_bonus=2, rally_soak_bonus=2),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Lookups & rules
# ---------------------------------------------------------------------------
ALL_PERKS: Dict[str, Perk] = {
    p.id: p for path in PATHS for p in path.perks
}

PATHS_BY_ID: Dict[str, Path] = {path.id: path for path in PATHS}


def perks_in_path(path_id: str) -> List[Perk]:
    path = PATHS_BY_ID.get(path_id)
    return list(path.perks) if path else []


def _non_capstones(path_id: str) -> List[Perk]:
    return [p for p in perks_in_path(path_id) if not p.capstone]


def prerequisites_met(perk: Perk, owned) -> bool:
    """Whether ``perk``'s in-Path prerequisites are satisfied by ``owned`` (a
    set/collection of owned perk ids). Does not consider cost or ownership."""
    owned = set(owned)
    if perk.capstone:
        return is_capstone_unlocked(perk, owned)
    if perk.tier <= 1:
        return True
    # A deeper perk needs at least one shallower perk already taken in the Path.
    return any(
        p.id in owned and p.tier < perk.tier and p.path == perk.path
        for p in perks_in_path(perk.path)
    )


def is_capstone_unlocked(perk: Perk, owned) -> bool:
    """A capstone unlocks only once every non-capstone perk in its Path is owned."""
    owned = set(owned)
    return all(p.id in owned for p in _non_capstones(perk.path))
