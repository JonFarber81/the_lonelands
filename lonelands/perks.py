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
  and ``stealth_bonus`` fed into ``Hero.stealth`` by the stealth layer — ADR 0014)
* ambush fields — a first-strike advantage / bonus damage the melee flow reads
* rally fields — a low-Endurance trigger the Fighter reads live (the Long Watch's
  Rally grants ``rally_atk_bonus``; ``rally_soak_bonus`` awaits a future node)
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
                        readied. Primes a sure ambush that bypasses enemy
                        awareness (ADR 0011; the stealth/awareness layer is
                        ADR 0014).

    Far Shot (#75) — multi-target shots, a kiting shot, a mark, and a primed crit:
      * ``"arc_shot"``  — Multishot: loose at a chosen foe and every foe within
                        ``radius`` tiles of it, resolving a Shot against each.
      * ``"line_shot"`` — Piercing Shot: a Shot along the line from the hero
                        through a chosen foe, striking every foe on it out to
                        ``reach``.
      * ``"harry"``     — Harrying Shot: loose at a chosen foe, then hop one tile
                        straight back from it (the kiting shot). Needs a foe.
      * ``"mark"``      — Hunter's Mark: mark a chosen foe within ``reach``; while
                        marked it takes the marking node's ``marked_damage`` extra
                        on every hero hit. Only one foe is marked at a time.
      * ``"aim"``       — Aimed Shot (untargeted): spend a turn steadying — your
                        next Shot lands as a guaranteed Critical.

    Long Watch (#76) — a charge, a sweep, and a cleansing regen:
      * ``"charge"``    — Charge: rush to a chosen foe within ``reach`` and strike
                        it for ``magnitude`` extra melee damage. Needs a foe.
      * ``"sweep"``     — Sweeping Blow (untargeted): one melee attack against
                        every foe adjacent to the hero.
      * ``"athelas"``   — Athelas (untargeted): cleanse the hero's Bleed and grant
                        ``magnitude`` Endurance regen per round for ``duration``
                        rounds (kingsfoil's slow healing).

    The **targeted** kinds (see :data:`TARGETED`) are picked with a targeting
    handler and resolved in an Action with map access, which starts the cooldown;
    the untargeted kinds resolve in :meth:`Hero.activate_ability`.
    """

    name: str
    kind: str
    cooldown: int = 0           # player-turns before it may be used again
    magnitude: str = "0"        # dice spec for wrath/heal/trap/charge/athelas
    soak: int = 0               # stance: extra Soak while active
    duration: int = 0           # stance/root/trap/athelas: rounds the effect lasts
    reach: int = 0              # dash/place_tile/root/shot/charge: range in tiles
    radius: int = 0             # arc_shot: tiles around the mark also struck
    primes_ambush: bool = False  # dash: the blink sets up an ambush strike

    # The targeted kinds resolve in an Action against a chosen tile/foe. A blink/
    # snare needs a tile; a root/shot/charge needs a foe (picked with lock-on).
    TARGETED = frozenset({"dash", "place_tile", "root",
                          "arc_shot", "line_shot", "harry", "mark", "charge"})
    # The lock-on (foe-targeted) subset — the rest of TARGETED pick a tile.
    FOE_TARGETED = frozenset({"root", "arc_shot", "line_shot", "harry",
                              "mark", "charge"})

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
    # --- stealth (Silent Tread; read into Hero.stealth — ADR 0014) --------
    stealth_bonus: int = 0       # per-rank Stealth: shrinks a foe's Perception

    # --- ambush (read by MeleeAction on a first strike) -------------------
    ambush_advantage: bool = False   # advantage on the opening blow vs a fresh foe
    ambush_bonus_damage: int = 0     # flat extra damage on that opening blow

    # --- Poisoned Blade (read by MeleeAction on any landed hit) -----------
    melee_bleed: int = 0             # Bleed stacks the hero's melee hits inflict

    # --- Hunter's Mark (Far Shot): bonus damage vs the currently-marked foe --
    marked_damage: int = 0           # extra damage on any hero hit vs a marked foe

    # --- Executioner (Long Watch): a context-conditional vs a wounded foe ---
    execute_threshold: float = 0.0   # fires vs a foe at/below this fraction of max
    execute_damage: int = 0          # extra melee damage on that finishing blow

    # --- Thornguard / Immovable (Long Watch Warden passives) --------------
    thorns_damage: int = 0           # damage a foe takes for landing a melee hit on you
    root_immune: bool = False        # cannot be rooted / knocked back (holds ground)

    # --- low-Endurance rally trigger (read live by Fighter) ---------------
    # The Long Watch's Rally grants rally_atk_bonus; rally_soak_bonus is unused
    # until a future node (a Kindled Heart Path) grants it.
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


# The three Paths (ADR 0011), each a trunk forking into two branches, tipped by
# capstones — the Long Watch (#76), the Far Shot (#75), and the Hidden Path
# (#77) are all fully built out. The old Swift Wrath melee offence lives on as
# the Long Watch's Reaver branch (Wrath included); Kindled Heart's Second Wind,
# Rally, and Athelas fold into the Long Watch trunk; the rest of Kindled Heart
# (Daunt, Light of the West) is deferred to a future Path.
PATHS: List[Path] = [
    Path(
        "long_watch", "The Long Watch",
        "Endure and protect — the Ranger who holds the line.",
        {"warden": "Warden", "reaver": "Reaver"},
        [
            # --- trunk (survival + sustain) -----------------------------------
            # Steady Endurance is the shared branching root; the sustain
            # deeds/passives are childless trunk roots that stack as a stem above
            # it, and it forks into the two branches below (#76).
            Node("lw_endure", "long_watch", "trunk", "Steady Endurance",
                 "Long years in the wild have hardened you. +4 max Endurance per rank.",
                 cost=1, tier=1, max_rank=3, max_endurance_bonus=4),
            Node("lw_wind", "long_watch", "trunk", "Second Wind",
                 "Draw on hidden reserves: restore 2d6 Endurance.",
                 cost=1, tier=1,
                 active=ActiveSpec("Second Wind", "heal", cooldown=6, magnitude="2d6")),
            Node("lw_rally", "long_watch", "trunk", "Rally",
                 "Cornered and grim, you fight all the harder: +2 to-hit while at "
                 "or below half Endurance.",
                 cost=1, tier=1, rally_threshold=0.5, rally_atk_bonus=2),
            Node("lw_athelas", "long_watch", "trunk", "Athelas",
                 "Crush kingsfoil into a healing draught: cleanse your Bleed and "
                 "knit 1d4 Endurance a round for 3 rounds.",
                 cost=1, tier=1,
                 active=ActiveSpec("Athelas", "athelas", cooldown=8,
                                   magnitude="1d4", duration=3)),
            # --- Warden branch (defence) --------------------------------------
            Node("lw_soak", "long_watch", "warden", "Iron Skin",
                 "You shrug off blows that would fell lesser folk. +1 Soak per rank.",
                 cost=1, tier=2, max_rank=3, parent="lw_endure", soak_bonus=1),
            Node("lw_guard", "long_watch", "warden", "Watchful Guard",
                 "Ever wary, ever ready. +1 Defence.",
                 cost=1, tier=2, parent="lw_soak", defence_bonus=1),
            Node("lw_hold", "long_watch", "warden", "Hold the Line",
                 "Set your feet and weather the storm: +4 Soak for 3 rounds.",
                 cost=1, tier=2, parent="lw_guard",
                 active=ActiveSpec("Hold the Line", "stance",
                                   cooldown=6, soak=4, duration=3)),
            Node("lw_thorn", "long_watch", "warden", "Thornguard",
                 "Your bristling guard bites back: a foe takes 2 damage for every "
                 "melee blow it lands on you.",
                 cost=1, tier=3, parent="lw_hold", thorns_damage=2),
            Node("lw_immovable", "long_watch", "warden", "Immovable",
                 "Rooted like an old oak: you cannot be held fast or driven back, "
                 "and stand +1 Defence for it.",
                 cost=1, tier=3, parent="lw_thorn",
                 root_immune=True, defence_bonus=1),
            Node("lw_unbroken", "long_watch", "warden", "Unbroken",
                 "Nothing moves you. +2 Soak, +2 Defence, and you can never be "
                 "held fast.",
                 cost=2, tier=3, capstone=True, parent="lw_immovable",
                 soak_bonus=2, defence_bonus=2, root_immune=True),
            # --- Reaver branch (melee offence) --------------------------------
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
            Node("lw_charge", "long_watch", "reaver", "Charge",
                 "Close the gap in a heartbeat: rush a foe and strike for +1d6 "
                 "damage.",
                 cost=1, tier=3, parent="lw_might",
                 active=ActiveSpec("Charge", "charge", cooldown=5, reach=5,
                                   magnitude="1d6")),
            Node("lw_sweep", "long_watch", "reaver", "Sweeping Blow",
                 "One great arc: strike every foe pressed around you at once.",
                 cost=1, tier=3, parent="lw_charge",
                 active=ActiveSpec("Sweeping Blow", "sweep", cooldown=4)),
            Node("lw_execute", "long_watch", "reaver", "Executioner",
                 "You know a killing chance when you see one: +4 melee damage to a "
                 "foe under a third of its Endurance.",
                 cost=1, tier=3, parent="lw_sweep",
                 execute_threshold=1 / 3, execute_damage=4),
            Node("lw_reaver", "long_watch", "reaver", "Reaver's Instinct",
                 "You feel the killing stroke before it lands: melee crits on a "
                 "natural 19 or 20, and every kill readies your active deeds anew.",
                 cost=2, tier=3, capstone=True, parent="lw_execute", crit_range=1,
                 readies_actives_on_kill=True),
        ],
    ),
    Path(
        "far_shot", "The Far Shot",
        "Marksmanship — the Ranger who kills before the foe closes.",
        {"sharpshooter": "Sharpshooter", "volley": "Volley"},
        [
            # The Shot flow reads these ranged_* fields live (ADR 0006). Steady
            # Aim is the shared root; it forks into Fletcher's Eye (heading the
            # precision branch) and Skirmisher (heading the mobility branch),
            # mirroring the Hidden Path's fork-at-the-root shape (#75).
            # --- trunk ---
            Node("fs_aim", "far_shot", "trunk", "Steady Aim",
                 "A patient eye down the shaft. +1 to-hit with bows per rank. (ranged)",
                 cost=1, tier=1, max_rank=3, ranged_bonus=1),
            Node("fs_fletcher", "far_shot", "trunk", "Fletcher's Eye",
                 "Your arrows bite deep. +1 ranged damage per rank. (ranged)",
                 cost=1, tier=1, max_rank=3, parent="fs_aim", ranged_damage_bonus=1),
            Node("fs_footwork", "far_shot", "trunk", "Skirmisher",
                 "You keep the enemy at bay and yourself hard to pin. +1 Defence.",
                 cost=1, tier=1, parent="fs_aim", defence_bonus=1),
            # --- Sharpshooter branch (precision) ------------------------------
            Node("fs_mark", "far_shot", "sharpshooter", "Hunter's Mark",
                 "Single out your quarry: while marked, a foe takes +3 from every "
                 "shot and stroke you land. Marks one foe at a time.",
                 cost=1, tier=2, parent="fs_fletcher", marked_damage=3,
                 active=ActiveSpec("Hunter's Mark", "mark", cooldown=4, reach=8)),
            Node("fs_aimed", "far_shot", "sharpshooter", "Aimed Shot",
                 "Steady the shaft and hold your breath: your next Shot flies as a "
                 "guaranteed Critical.",
                 cost=1, tier=2, parent="fs_mark",
                 active=ActiveSpec("Aimed Shot", "aim", cooldown=4)),
            Node("fs_deadeye", "far_shot", "sharpshooter", "Deadeye",
                 "No range is too far. +2 to-hit and +2 damage with bows. (ranged)",
                 cost=2, tier=3, capstone=True, parent="fs_aimed",
                 ranged_bonus=2, ranged_damage_bonus=2),
            # --- Volley branch (mobility / multi-target) ----------------------
            Node("fs_multishot", "far_shot", "volley", "Multishot",
                 "Loose a spread: strike your mark and every foe within a tile of "
                 "it in one draw.",
                 cost=1, tier=2, parent="fs_footwork",
                 active=ActiveSpec("Multishot", "arc_shot", cooldown=5, reach=8,
                                   radius=1)),
            Node("fs_harry", "far_shot", "volley", "Harrying Shot",
                 "Fire and fade: loose at a foe, then slip one tile back out of "
                 "its reach — the kiting shot.",
                 cost=1, tier=2, parent="fs_multishot",
                 active=ActiveSpec("Harrying Shot", "harry", cooldown=4, reach=8)),
            Node("fs_pierce", "far_shot", "volley", "Piercing Shot",
                 "A shaft loosed with such force it passes clean through: strike "
                 "every foe in a line.",
                 cost=1, tier=3, parent="fs_harry",
                 active=ActiveSpec("Piercing Shot", "line_shot", cooldown=5,
                                   reach=8)),
            Node("fs_storm", "far_shot", "volley", "Arrow Storm",
                 "Empty your quiver skyward: a hail of arrows falls on your mark "
                 "and every foe around it.",
                 cost=2, tier=3, capstone=True, parent="fs_pierce",
                 active=ActiveSpec("Arrow Storm", "arc_shot", cooldown=8, reach=8,
                                   radius=2)),
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


def tier_unlocked(node: Node, points_in_path: int) -> bool:
    """Whether ``node``'s points-in-Path tier gate is satisfied by
    ``points_in_path`` (the Path points already spent in its Path)."""
    return points_in_path >= points_for_tier(node.tier)


def parent_met(node: Node, owned) -> bool:
    """Whether ``node``'s light parent-edge is satisfied by ``owned`` (a set/
    collection of owned node ids). Roots (no parent) are always met."""
    return node.parent is None or node.parent in set(owned)


def buy_summary(node: Node, rank: int, *, committed: bool,
                buyable: bool, locked_reason: str = "locked") -> str:
    """The one-line "what a point buys" framing for the Paths detail strip —
    the marginal cost/effect of the *next* point on ``node``, given the hero's
    current ``rank`` in it. Pure: the caller resolves ``buyable`` and
    ``locked_reason`` (which read the hero) and passes them in.

    While **pathless** (``committed`` is False) nothing is purchasable, so the
    strip is pure reference and this is just the price (``2pp`` for a capstone).
    Once committed it reads the live state: a one-and-done active becomes
    ``learned`` and a rankable passive ``maxed`` when exhausted; an affordable
    node shows ``buy · 1pp`` (first take) or ``rank 1→2 · 1pp`` (a rank-up);
    an unaffordable/gated node shows the ``locked_reason``."""
    if not committed:
        return f"{node.cost}pp"
    if rank > 0 and rank >= node.max_rank:
        return "learned" if node.active else "maxed"
    if buyable:
        verb = f"rank {rank}→{rank + 1}" if rank > 0 else "buy"
        return f"{verb} · {node.cost}pp"
    return locked_reason
