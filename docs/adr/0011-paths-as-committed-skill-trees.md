---
status: accepted (supersedes parts of ADR 0005)
---

# Paths as committed skill-trees

ADR 0005 gave the Ranger five perk-**Paths** she **blends freely** across, each a
shallow line of four perks in three tiers. That model made the Path pick weak
(you dabble in all five) and the trees too thin to plan a build around. We are
**re-shaping Paths into committed, Diablo-style skill-trees**: a Path is now the
Ranger's *class*, chosen once and walked for the whole game, and each Path is a
deep branching tree you level up over a playthrough. This is the game's primary
character-personalisation surface — hence the investment in making it deep and
legible. Setting and the d20 core (ADR 0005) are untouched; only the
advancement layer changes.

## Decisions

- **A Path is a one-time class commitment, not a blend.** Level 1 is
  **pathless**. At **level 2** the player browses all Paths in full, then
  **commits to one behind a permanent-choice confirm**; every point thereafter
  goes only into that Path's tree. *Supersedes ADR 0005's "a Ranger blends
  freely across Paths."* The weight of the pick *is* the personalisation.
  *Rejected:* free blending (dilutes identity, makes the pick meaningless);
  hard-forked exclusive branches (too punishing with no respec); picking at
  character creation (level 1 is a short prologue before you find your calling).

- **Three deep Paths now, more later.** The five thin Paths collapse to three
  well-branched ones: **the Long Watch** (Tank), **the Hidden Path** (Stealth),
  **the Far Shot** (Ranged). The old **Swift Wrath** melee offence becomes the
  Long Watch's **Reaver** branch; the old **Kindled Heart**'s survival bits
  (Second Wind, rally, Athelas) fold into the Long Watch trunk, and the rest
  (Daunt, Light of the West) is **deferred to a future Kindled Heart Path**.
  Three Paths filled out beats five left shallow.

- **Each Path is a trunk that forks into two branches.** A shared **trunk**
  splits into two **branches** (e.g. the Long Watch's **Warden** / **Reaver**),
  ~10–12 **nodes** across 5–6 tiers, each branch tipped by a **capstone**.
  Branches are **point-gated, never mutually exclusive** — a long enough game
  could reach anywhere, but a single character fills only **~⅔** of the tree, so
  *which* branches and ranks you favour keep two same-Path Rangers distinct.

- **Deeper tiers unlock by points-spent-in-Path (Diablo-2 gate).** A tier opens
  once enough **Path points** have been sunk into *this* Path, plus a light
  parent-edge for tree shape. *Supersedes ADR 0005's "owning one shallower perk
  unlocks the next."* This makes levelling the Path literal — pour in more,
  reach deeper.

- **Ranked passives, one-and-done actives.** Passive stat nodes take **multiple
  points** (ranks, shown as pips — Iron Skin I→III); active abilities and
  special attacks are **learned once** and scale via other nodes. Gives
  continuous "keeps adding" growth without a mushy 5-points-in-one-stat feel or
  50 bespoke abilities.

- **One Path point per level from level 2.** *Supersedes ADR 0005's "a perk point
  every few levels."* Nodes/ranks cost 1 point, capstones 2. Steady, tactile
  growth every level; a full Path runs ~18–20 points.

- **New effect primitives fill the trees.** ~6 reusable primitives — `dash`
  (move-and-strike), `multi-target` (adjacent/line/arc), `status`
  (root/slow/mark/fear/Bleed), `on-event` triggers, `place-tile` (traps),
  `context-conditional` (vs Band / terrain) — back the new special attacks:
  Charge, Sweeping Blow, Multishot, Harrying Shot, Piercing Shot, Hunter's Mark,
  Pinning Shot, Snare, Shadowstep, Poisoned Blade, Athelas, Aimed Shot, and
  band-conditional passives. Built once, reused across nodes, rather than a
  bespoke mechanic per node.

- **Actives fire from a number-key hotbar.** Owned actives auto-bind to `1`–`5`,
  shown in the HUD with cooldown/charge state; the ability menu stays as
  overflow/fallback. The prior menu-only flow doesn't scale to a deep Path's
  4–6 actives mid-combat.

## Consequences

- Broad rewrite of the advancement layer: `perks.py` (trunk/branch/tier/rank
  data model, points-in-Path gating, the new primitives), `character.py` (Path
  commitment, Path-point income, pathless level 1), `content.py` (rebuild the
  three trees), `input_handlers.py` (the level-2 chooser, the tree-render
  Paths screen, the hotbar), `hud.py` (hotbar strip), and the test-suite.
- **Saves are broken; no migration.** The hero data shape changes (committed
  Path, ranked nodes, points-in-Path, hotbar bindings); pre-release, we reset
  the save format and the starting hero rather than write migration code.
- **CONTEXT.md** is re-glossed: **Path** redefined (commitment, not blend);
  **Perk** renamed to **Node**; **perk point** renamed to **Path point**; new
  terms **pathless**, **trunk**, **branch**, **rank**, **points-in-Path gate**.
- Supersedes ADR 0005's blend-freely rule, five-Path count, flat perk model, and
  perk-point cadence. ADR 0005's d20 core, attributes, kill-XP, single-Endurance
  pool, and equipment/affix decisions remain authoritative.
