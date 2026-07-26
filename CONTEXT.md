# Context & Ubiquitous Language

The shared vocabulary of The Lonelands. Terms here are the canonical names —
use them in code, comments, UI copy, and conversation. This file is a glossary,
not a spec: it defines *what words mean*, never *how things are built*.

## World & navigation

- **Region** — one cell of the world grid. A Region is a stack of one or more
  **Levels**; most Regions have just the surface Level, but many may run deeper.
  The player crosses from one Region to an adjacent one by walking off an edge.
  Never interchangeably called a "zone" or "square".
- **Level** — one horizontal layer of a Region, stacked vertically. **Enter** on
  a stair or entrance moves the player up or down between a Region's Levels. The
  barrow's "deeps" are the lower Levels of the Barrow-downs Region (Tyrn Gorthad).
- **Surface** — a Region's topmost Level: the one the player arrives on when
  walking in from a neighbour. *Only the Surface edge-connects to neighbouring
  Regions*; deeper Levels are reached only by Enter, from within their Region.
- **Square** — the town's central plaza only. *Not* a synonym for Region.

The whole **15×9 overworld grid** is live: all 116 walkable cells exist and are
enterable, built lazily from `lonelands/overworld.py` (the plan-as-data twin of
`notes/overworld-map.md`, traced from the Eriador Journey Map — see `references/`
and ADR 0003). Impassable Sea/Mountain cells are simply *absent* from the grid,
so their edges are uncrossable. A few cells are hand-authored; the rest are
generic **placeholder surfaces** built from their plan `Cell` (band-tinted
terrain + band-driven wandering beasts + a diegetic Sea/Mountain border where a
neighbour is missing), to be refined cluster-by-cluster later.

The **Great Roads** (the East Road, the Greenway, the Shire Road) are **edge
metadata**, not decoration: `overworld.ROAD_EDGES` records, per cell, which of
its four edges a road crosses (diagonal path steps staircase into orthogonal
knees, since movement is 4-neighbour). Each road enters and leaves a cell at the
**midpoint of the edge it crosses**, so the shared midpoint is the same tile on
both sides of a seam and the road meets its neighbour there; between edges it
meanders through the cell centre. A road that crosses water lays a **ford/bridge**
so it never drowns. Crossing a road edge **snaps the player onto the road**, so
the Great Roads stay continuous across every cluster seam.

Landmarks around the Bree hub:

- **Bree** `(0,0)` — the hub Region, the town at the meeting of the roads. Where
  a Ranger of the North is met. *(Replaces the former invented "Talbrún".)*
- **the Barrow-downs** `(-1,0)` — the **west** Region (Tyrn Gorthad); holds the
  barrow entrance down to the deeps where the barrow-wights and the star-brooch
  lie — the main quest. *(Re-homed here from the Weather Hills per ADR 0003.)*
- **Weathertop** `(2,0)` — **east** along the Great East Road; the ruined
  watchtower of Amon Sûl, with its own deeps (the watch-vaults).
- **the Chetwood** `(0,-1)` — the **north** Region; close-grown woodland the
  Greenway climbs through (Cluster 2, issue #17).
- **the South Downs** `(0,1)` — the **south** Region; low rolling downs south of
  the Great Road, the Greenway crossing them (Cluster 2, issue #17).
- **Midgewater** `(1,-1)`, **Sarn Ford** `(-1,1)`, **the Old Forest** `(-2,1)` —
  the rest of the Bree cluster: the biting fen, the Rangers' Brandywine ford, and
  the awake, ill-disposed ancient wood (Cluster 2, issue #17).

## The One Ring dice

- **Test** — a single roll resolving an action: one Feat die plus zero or more
  Success dice, summed and compared to a Target Number.
- **Feat die** — the d12 rolled on every Test. Two faces are magic:
  - **Eye of Sauron** — the 11 face. Counts as 0 and invites ill fortune.
  - **Gandalf rune** — the 12 face. An automatic success regardless of TN.
- **Success die** — a d6. A Test rolls one per point of skill/proficiency
  **rank**. Its 6 face is special:
  - **Tengwar** — the rune on a Success die's 6 face; a great-success marker.
    "Tengwar count" is how many 6s a Test rolled.
- **Target Number (TN)** — the value a Test's total must reach to succeed.
- **Rank** — the number of Success dice a Test rolls.

## Test outcomes

- **Success / failure** — total meets the TN (or the Gandalf rune shows).
- **Great success** — a success carrying at least one Tengwar (or the Gandalf
  rune).
- **Extraordinary success** — a success carrying two or more Tengwar.

## Conditions on a Test

- **Favoured / ill-favoured** — roll two Feat dice, keep the higher / lower.
- **Weary** — Success dice showing 1–3 count as 0.

## Combat

The hero rolls *every* die in a fight — on offence and on defence — so the dice
tray never falls silent. A foe never rolls.

- **Attack roll** — when the hero strikes, a proficiency Test against the foe's
  Defence. On a hit, the weapon deals damage.
- **Attack TN** — a foe's rating for how hard its blow is to turn aside; it is
  the Target Number of the hero's Parry, not a roll the foe makes.
- **Parry** — when a foe strikes the hero, the hero rolls a **Battle** Test
  against the foe's Attack TN (shield and helm add to the total). Success turns
  the blow aside for no harm; failure lets it land for the foe's damage.
- **Piercing Blow** — a wound threat. On the hero's *great* attack it is forced
  on the foe; on a **fumbled Parry** (the Eye) it is forced on the hero. The
  defender rolls a **Protection** Test against the weapon's **Injury** rating to
  avoid it.
- **Wound** — the result of a failed Protection Test. A second Wound is mortal.

## Trade & loot

The Wild pays in goods, not glory: routine foes grant no experience (that is the
quests' domain), but their remains and purses are worth something to a Ranger who
hauls them back to Bree. This is the game's material reward loop.

- **Coins** — the single currency, carried in the hero's **purse** (never on the
  ground as an item). A slain humanoid may yield coins straight into the purse.
  *Avoid*: gold, silver, money.
- **Value** — an item's base worth in coins. A merchant **sells** it to the hero
  at its Value and **buys** it from the hero at a fraction of Value (the **sell
  fraction**), so he always pays less than he charges. Value `0` means the item
  cannot be sold.
- **Trade-good** — an item whose only purpose is to be sold: a **pelt**, a fang,
  spider-silk, an orc-trophy. Distinct from gear and consumables, which are used
  but *also* carry a Value and so can be sold. *Avoid*: junk, treasure (treasure
  is the quest star-brooch, not loot).
- **Loot** — what a foe may leave on death: zero or more drops resolved from the
  creature's **loot table**. A **pelt** and kin drop onto the corpse tile to be
  picked up; coins go straight to the purse.
- **Loot table** — a creature's drop specification: one or more independent
  **rolls**, each a weighted table of outcomes that includes a "nothing" slice.
  A single kill may resolve several rolls (coins *and* a trophy).
- **Stack** — a single inventory slot holding a count of one fungible item
  (trade-goods and consumables, which have no per-instance state). Equipment
  never stacks. *Avoid*: bundle, pile.

## Presentation

- **Dice tray** — the fixed, single-row panel pinned to the top of the
  bottom-left (log) pane. It shows the player's **latest** Test rendered as
  die-face glyphs: the Feat die, each Success die, the total vs the TN, and the
  outcome. It only ever reflects the *player's* rolls, never an enemy's. The
  scrolling **message log** beneath it carries pure narrative prose with no dice
  math — the tray is the sole home for the numbers.
