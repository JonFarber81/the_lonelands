"""The three Ranger Paths and the nodes bought along their trees (ADR 0011).

This module is **pure data + tiny effect-hook objects**: it imports no engine,
no tcod, no live game state. The Hero owns which Path is committed, which nodes
are bought and at what **rank**, and the per-node runtime (cooldowns, primed
hits, stances); the Fighter and the combat actions *query* these declarative
fields to fold node effects into real numbers.

Model (ADR 0011)
----------------
A Path is a **committed skill-tree**: a shared **trunk** that forks into two
**branches**, tipped by a **capstone**. A :class:`Node` is a frozen dataclass
carrying:

* identity — ``id`` / ``path`` / ``branch`` / ``name`` / ``desc``
* economy — ``cost`` (Path points per rank; capstones cost 2) and ``tier`` (its
  depth within the Path)
* ``max_rank`` — how many times it may be bought. **Passives are rankable**
  (``max_rank`` > 1, shown as pips — Iron Skin I→III); **actives are
  one-and-done** (``max_rank`` == 1) and scale via other nodes.
* ``capstone`` — a branch's deepest node, gated behind real investment
* ``parent`` — a light parent-edge: a node id that must be owned first (tree
  shape). ``None`` for the trunk's tier-1 roots.
* passive modifier fields — flat bonuses the Fighter reads **per rank**
  (``atk_bonus``, ``defence_bonus``, ``soak_bonus``, ``max_endurance_bonus``,
  ``melee_damage_bonus``, ``crit_range``, the Far Shot ranged fields
  ``ranged_bonus`` / ``ranged_damage_bonus`` read by the Shot flow — ADR 0006,
  and ``stealth_bonus`` for the stealth layer not yet built)
* ambush fields — a first-strike advantage / bonus damage the melee flow reads
* rally fields — a low-Endurance trigger the Fighter reads live (unused by the
  ported placeholder trees; kept for a future Kindled Heart Path)
* ``active`` — an optional :class:`ActiveSpec` for a charge/cooldown ability

Gating (documented here, enforced in :meth:`Hero.can_buy`)
----------------------------------------------------------
* **Points-in-Path tier gate (Diablo-2 style):** a node of ``tier`` N is buyable
  only once at least ``points_for_tier(N)`` Path points have been spent in
  *this* Path (see :func:`points_for_tier`). Tier-1 roots are always open.
* **Parent-edge:** if a node names a ``parent``, that parent must already be
  owned (rank ≥ 1).

Prerequisites only ever look within a single Path — a Ranger commits to one
Path and every Path point after level 1 goes only into its tree.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Points-in-Path tier gate
# ---------------------------------------------------------------------------
# A deeper tier opens once enough Path points have been sunk into *this* Path.
# Step of 2 per tier: tier 1 is free, tier 2 asks 2 points spent, tier 3 asks 4…
TIER_GATE_STEP = 2


def points_for_tier(tier: int) -> int:
    """Path points that must already be spent in a Path before a node of
    ``tier`` becomes buyable. Tier 1 (the roots) is always open."""
    return TIER_GATE_STEP * max(0, tier - 1)


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
      * ``"dash"``   — the Hidden Path blink (Shadowstep/Disengage): step to a
                        chosen empty tile within ``reach``. If ``primes_ambush``
                        the next strike lands as an ambush (see the melee flow).
                        Needs a **target tile** — resolved in an Action.
      * ``"place_tile"`` — lay a Snare trap on a chosen tile within ``reach``:
                        the first foe to step onto it is hurt (``magnitude`` dice)
                        and rooted for ``duration`` rounds. Needs a target tile.
      * ``"root"``   — pin a chosen visible foe within ``reach`` in place for
                        ``duration`` rounds (Pinning). Needs a **target foe**.
      * ``"vanish"`` — the Trapper capstone (untargeted): slip into shadow —
                        your next strike is a guaranteed ambush and every deed is
                        readied. Scoped to the existing ambush trigger (ADR 0011;
                        a true unseen state waits on a stealth/visibility layer).

    The ``dash``/``place_tile``/``root`` kinds are **targeted** — the hotbar
    routes them through a targeting handler, and an Action (with map access)
    resolves the effect and starts the cooldown, rather than :meth:`Hero.
    activate_ability`, which handles only the untargeted kinds.
    """

    name: str
    kind: str
    cooldown: int = 0           # player-turns before it may be used again
    magnitude: str = "0"        # dice spec for wrath/heal/trap effects
    soak: int = 0               # stance: extra Soak while active
    duration: int = 0           # stance/root/trap: rounds the effect persists
    reach: int = 0              # dash/place_tile/root: target range in tiles
    primes_ambush: bool = False  # dash: the blink sets up an ambush strike

    # The targeted kinds resolve in an Action against a chosen tile/foe.
    TARGETED = frozenset({"dash", "place_tile", "root"})

    @property
    def targeted(self) -> bool:
        """Whether firing this active needs a target tile/foe picked first."""
        return self.kind in self.TARGETED


@dataclass(frozen=True)
class Node:
    id: str
    path: str
    branch: str                  # "trunk" or a branch id (e.g. "warden")
    name: str
    desc: str
    cost: int = 1                # Path points per rank; capstones cost 2
    tier: int = 1               # depth within the Path (drives the points gate)
    max_rank: int = 1            # 1 = one-and-done (actives); >1 = rankable passive
    capstone: bool = False
    parent: Optional[str] = None  # light parent-edge: node id owned before this

    # --- live passive combat modifiers (read by Fighter, scaled by rank) ---
    atk_bonus: int = 0
    defence_bonus: int = 0
    soak_bonus: int = 0
    max_endurance_bonus: int = 0  # raises the single Endurance pool at once
    melee_damage_bonus: int = 0
    crit_range: int = 0          # lowers the crit face by this (20 -> 20-crit_range)

    # --- on-kill trigger (read by Fighter.die when the hero slays a foe) ---
    readies_actives_on_kill: bool = False  # a kill clears this hero's active cooldowns

    # --- Far Shot ranged fields (read by the Shot flow — ADR 0006) --------
    ranged_bonus: int = 0        # +to-hit added to a Shot's d20 (via Hero/Fighter)
    ranged_damage_bonus: int = 0  # flat damage added to a landed Shot
    # --- field for a system not yet built ---------------------------------
    stealth_bonus: int = 0       # TODO: consumed by a future stealth/detection layer

    # --- ambush (read by MeleeAction on a first strike) -------------------
    ambush_advantage: bool = False   # advantage on the opening blow vs a fresh foe
    ambush_bonus_damage: int = 0     # flat extra damage on that opening blow

    # --- Poisoned Blade (read by MeleeAction on any landed hit) -----------
    melee_bleed: int = 0             # Bleed stacks the hero's melee hits inflict

    # --- low-Endurance rally trigger (read live by Fighter) ---------------
    # Unused by the ported placeholder trees; kept for a future Kindled Heart.
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
    branches: Dict[str, str]              # branch id -> display name
    nodes: List[Node] = field(default_factory=list)


# Placeholder trees (ADR 0011): the three Paths, each a trunk forking into two
# branches. These port the old five Paths' *effects* into the new shape so the
# game still runs — the real, deep tree content lands in the per-Path issues
# (#75 Far Shot, #76 Long Watch, #77 Hidden Path). The old Swift Wrath melee
# offence becomes the Long Watch's Reaver branch; Kindled Heart's Second Wind
# folds into the Long Watch trunk; the rest of Kindled Heart is deferred.
PATHS: List[Path] = [
    Path(
        "long_watch", "The Long Watch",
        "Endure and protect — the Ranger who holds the line.",
        {"warden": "Warden", "reaver": "Reaver"},
        [
            # --- trunk ---
            Node("lw_endure", "long_watch", "trunk", "Steady Endurance",
                 "Long years in the wild have hardened you. +4 max Endurance per rank.",
                 cost=1, tier=1, max_rank=3, max_endurance_bonus=4),
            Node("lw_wind", "long_watch", "trunk", "Second Wind",
                 "Draw on hidden reserves: restore 2d6 Endurance.",
                 cost=1, tier=1,
                 active=ActiveSpec("Second Wind", "heal", cooldown=6, magnitude="2d6")),
            # --- Warden branch (defence) ---
            Node("lw_soak", "long_watch", "warden", "Iron Skin",
                 "You shrug off blows that would fell lesser folk. +1 Soak per rank.",
                 cost=1, tier=2, max_rank=3, parent="lw_endure", soak_bonus=1),
            Node("lw_guard", "long_watch", "warden", "Watchful Guard",
                 "Ever wary, ever ready. +1 Defence.",
                 cost=1, tier=2, parent="lw_soak", defence_bonus=1),
            Node("lw_hold", "long_watch", "warden", "Hold the Line",
                 "Set your feet and weather the storm: +4 Soak for 3 rounds.",
                 cost=2, tier=3, capstone=True, parent="lw_guard",
                 active=ActiveSpec("Hold the Line", "stance",
                                   cooldown=6, soak=4, duration=3)),
            # --- Reaver branch (melee offence) ---
            Node("lw_hone", "long_watch", "reaver", "Honed Edge",
                 "Your strokes find the gap. +1 to-hit in melee per rank.",
                 cost=1, tier=2, max_rank=3, parent="lw_endure", atk_bonus=1),
            Node("lw_might", "long_watch", "reaver", "Killing Might",
                 "Every blow carries your full weight. +2 melee damage.",
                 cost=1, tier=2, parent="lw_hone", melee_damage_bonus=2),
            Node("lw_wrath", "long_watch", "reaver", "Wrath",
                 "Loose your fury: your next hit deals +2d6 damage.",
                 cost=1, tier=2, parent="lw_hone",
                 active=ActiveSpec("Wrath", "wrath", cooldown=4, magnitude="2d6")),
            Node("lw_reaver", "long_watch", "reaver", "Reaver's Instinct",
                 "You feel the killing stroke before it lands: melee crits on a "
                 "natural 19 or 20, and every kill readies your active deeds anew.",
                 cost=2, tier=3, capstone=True, parent="lw_might", crit_range=1,
                 readies_actives_on_kill=True),
        ],
    ),
    Path(
        "far_shot", "The Far Shot",
        "Marksmanship — the Ranger who kills before the foe closes.",
        {"marksman": "Marksman", "skirmisher": "Skirmisher"},
        [
            # The Shot flow reads these ranged_* fields live (ADR 0006).
            # --- trunk ---
            Node("fs_aim", "far_shot", "trunk", "Steady Aim",
                 "A patient eye down the shaft. +1 to-hit with bows per rank. (ranged)",
                 cost=1, tier=1, max_rank=3, ranged_bonus=1),
            # --- Marksman branch (damage/reach) ---
            Node("fs_fletcher", "far_shot", "marksman", "Fletcher's Eye",
                 "Your arrows bite deep. +1 ranged damage per rank. (ranged)",
                 cost=1, tier=2, max_rank=3, parent="fs_aim", ranged_damage_bonus=1),
            Node("fs_deadeye", "far_shot", "marksman", "Deadeye",
                 "No range is too far. +2 to-hit and +2 damage with bows. (ranged)",
                 cost=2, tier=3, capstone=True, parent="fs_fletcher",
                 ranged_bonus=2, ranged_damage_bonus=2),
            # --- Skirmisher branch (footwork) ---
            Node("fs_footwork", "far_shot", "skirmisher", "Skirmisher",
                 "You keep the enemy at bay and yourself hard to pin. +1 Defence.",
                 cost=1, tier=2, parent="fs_aim", defence_bonus=1),
        ],
    ),
    Path(
        "hidden_path", "The Hidden Path",
        "Stealth and ambush — the Ranger who strikes from the shadows.",
        {"assassin": "Assassin", "trapper": "Trapper"},
        [
            # --- trunk: stealth, the ambush opener, and light footwork --------
            Node("hp_stealth", "hidden_path", "trunk", "Silent Tread",
                 "You move as a shadow among shadows. +2 Stealth per rank. (stealth)",
                 cost=1, tier=1, max_rank=3, stealth_bonus=2),
            Node("hp_ambush", "hidden_path", "trunk", "Ambush",
                 "Your opening blow against an unmarked foe strikes with "
                 "advantage and +2 damage.",
                 cost=1, tier=1, parent="hp_stealth",
                 ambush_advantage=True, ambush_bonus_damage=2),
            Node("hp_evasion", "hidden_path", "trunk", "Evasion",
                 "Quick feet and quicker senses. +1 Defence per rank.",
                 cost=1, tier=1, max_rank=2, parent="hp_stealth", defence_bonus=1),
            # --- Assassin branch (burst melee) --------------------------------
            Node("hp_shadowstep", "hidden_path", "assassin", "Shadowstep",
                 "Blink through the shadows to a nearby tile; your next strike "
                 "lands as an ambush.",
                 cost=1, tier=2, parent="hp_ambush",
                 active=ActiveSpec("Shadowstep", "dash", cooldown=5, reach=4,
                                   primes_ambush=True)),
            Node("hp_poison", "hidden_path", "assassin", "Poisoned Blade",
                 "Your blade drips venom: every melee hit leaves the foe bleeding.",
                 cost=1, tier=2, parent="hp_ambush", melee_bleed=1),
            Node("hp_deathblow", "hidden_path", "assassin", "Deathblow",
                 "The unseen strike is a killing one. Advantage and +6 damage on "
                 "an ambush.",
                 cost=2, tier=3, capstone=True, parent="hp_poison",
                 ambush_advantage=True, ambush_bonus_damage=6),
            # --- Trapper branch (control) -------------------------------------
            Node("hp_snare", "hidden_path", "trapper", "Snare",
                 "Lay a hidden snare on a nearby tile; the first foe onto it is "
                 "hurt (1d6) and rooted for 2 rounds.",
                 cost=1, tier=2, parent="hp_evasion",
                 active=ActiveSpec("Snare", "place_tile", cooldown=5, reach=3,
                                   magnitude="1d6", duration=2)),
            Node("hp_pinning", "hidden_path", "trapper", "Pinning",
                 "Pin a foe in sight where it stands — it cannot move for a round.",
                 cost=1, tier=3, parent="hp_snare",
                 active=ActiveSpec("Pinning", "root", cooldown=5, reach=6,
                                   duration=1)),
            Node("hp_disengage", "hidden_path", "trapper", "Disengage",
                 "Slip out of reach: blink to a nearby tile, breaking away clean.",
                 cost=1, tier=3, parent="hp_pinning",
                 active=ActiveSpec("Disengage", "dash", cooldown=4, reach=3)),
            Node("hp_vanish", "hidden_path", "trapper", "Vanish",
                 "Melt into shadow: your next strike is a sure ambush and every "
                 "deed is readied anew.",
                 cost=2, tier=3, capstone=True, parent="hp_disengage",
                 active=ActiveSpec("Vanish", "vanish", cooldown=8)),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Lookups & rules
# ---------------------------------------------------------------------------
ALL_NODES: Dict[str, Node] = {n.id: n for path in PATHS for n in path.nodes}

PATHS_BY_ID: Dict[str, Path] = {path.id: path for path in PATHS}


def nodes_in_path(path_id: str) -> List[Node]:
    path = PATHS_BY_ID.get(path_id)
    return list(path.nodes) if path else []


def tier_unlocked(node: Node, points_in_path: int) -> bool:
    """Whether ``node``'s points-in-Path tier gate is satisfied by
    ``points_in_path`` (the Path points already spent in its Path)."""
    return points_in_path >= points_for_tier(node.tier)


def parent_met(node: Node, owned) -> bool:
    """Whether ``node``'s light parent-edge is satisfied by ``owned`` (a set/
    collection of owned node ids). Roots (no parent) are always met."""
    return node.parent is None or node.parent in set(owned)
