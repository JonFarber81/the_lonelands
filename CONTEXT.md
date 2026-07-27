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
  Greenway climbs through, holding the woodwrights' **Hamlet** of **Archet** at
  its south eaves (Cluster 2, issue #17).
- **the Bree-land** `(1,0)` — the settled country **east** of Bree-hill; holds
  the Hamlets of **Combe** (woodsmen) and **Staddle** (hobbits), and the lonely
  **Forsaken Inn** further out on the Great East Road. First content authored
  onto a former placeholder cell.
- **the South Downs** `(0,1)` — the **south** Region; low rolling downs south of
  the Great Road, the Greenway crossing them (Cluster 2, issue #17).
- **Midgewater** `(1,-1)`, **Sarn Ford** `(-1,1)`, **the Old Forest** `(-2,1)` —
  the rest of the Bree cluster: the biting fen, the Rangers' Brandywine ford, and
  the awake, ill-disposed ancient wood (Cluster 2, issue #17).

## Inhabitants & content

The folk and props authored onto a Region's Surface. Speaking characters and
signposts alike use the one **NPC** dialog component (a node-graph `tree`); the
player **bumps** any of them to open the conversation.

- **Hamlet** — a small settlement authored *onto* a wilderness Surface,
  subordinate to a hub town: far smaller than Bree, and several may share one
  Region (Combe, Staddle, and the Forsaken Inn all sit on the Bree-land cell;
  Archet sits within the Chetwood). A Hamlet is not a Region and never its own
  overworld cell — it is content placed on a cell's Surface.
- **Bystander** — a speaking NPC with dialog but *no* shop or quest: colour and
  rumour only. Distinct from the functional NPCs — the quest-givers and
  **merchants** (shopkeepers) — who move the game state.
- **Signpost** — an examinable wayfinding/flavor prop: a readable post the
  player bumps, built on the same NPC machinery with a single dialog node. Each
  carries a unique name so its text restores correctly on save/load.

## The d20 core

Our own system (de-coupled from The One Ring — see ADR 0005). Every action
resolves the same way; combat is that same primitive.

- **Check** — a single roll resolving an action: `d20 + attribute (+ perk/gear)`
  compared to a **Target Number**. *(Replaces the former "Test".)*
- **Target Number (TN)** — the value a Check's total must **meet or beat** to
  succeed.
- **Critical** — a **natural 20** on the d20: an automatic success/hit, and in
  combat extra damage. *(Replaces the Gandalf rune.)*
- **Fumble** — a **natural 1** on the d20: an automatic failure/miss. *(Replaces
  the Eye of Sauron.)*
- **Advantage / Disadvantage** — roll two d20 and keep the **higher / lower**.
  *(Replaces favoured / ill-favoured.)*

## Character

The hero is a single **Ranger of the North** (flavour identity, not a stat).

- **Attribute** — one of three small modifiers added to the d20: **Brawn**
  (melee hit/damage, HP, athletics) · **Wits** (ranged, Defence, stealth,
  senses) · **Will** (morale, social, healing, Path abilities). *(Replaces the
  TOR Strength/Heart/Wits attributes; there are no skills or weapon
  proficiencies — specialisation lives in perks.)*
- **Level** — rises **often** from XP (see Trade & loot). Each level grants an
  automatic **+HP** and, periodically, **+to-hit**; every few levels it also
  grants a **perk point**.
- **Perk** — a bought, permanent upgrade: a passive bonus or an active ability
  (actives run on **charges** or **cooldowns**; there is no spendable resource
  pool). *(Replaces buying skill/proficiency ranks.)*
- **Path** — one of five themed trees a perk belongs to, each a *style* of
  Ranger with its own feel: **the Long Watch** (endure/protect), **the Swift
  Wrath** (melee offence), **the Far Shot** (marksman), **the Hidden Path**
  (stealth/ambush), **the Kindled Heart** (spirit/defiance). A Ranger **blends
  freely** across Paths; a **capstone** (a Path's deepest perk) needs real
  investment in that Path.
- **Perk point** — the currency spent to buy a perk. Deeper perks in a Path
  require prior perks *in that Path*.

## Combat

`d20 + attack bonus vs Defence` to hit; on a hit, `weapon damage − soak`. The
hero rolls; a foe never rolls (the dice tray stays the player's).

- **Attack bonus** — what the hero adds to the attack d20 (attribute + level +
  perks + weapon).
- **Defence** — the TN an attacker's roll must meet to hit. Raised by **light
  armour and shields** (dodge/parry), by Wits, and by level.
- **Damage** — rolled from the weapon (e.g. `2d6+2`) on a hit; a **Critical**
  adds bonus damage.
- **Soak** — damage subtracted by **heavy armour** when a hit lands (mitigation,
  as opposed to Defence's avoidance).
- **Bleed** — a status a Critical or a heavy foe may inflict: damage over time /
  a penalty. *(The only remnant of the old Wound mechanic; there is no second
  death track.)*
- **Endurance** — the single HP pool; grows with level. **0 Endurance = death.**
- **Difficulty** — a per-run tier chosen on the title screen (**Merciful**,
  **Wayfarer**, **Grim**) that scales **only the damage the player takes** —
  foes' Endurance and aim are untouched. Wayfarer (×1.0) is the intended
  balance; a landed blow never softens below 1. Stored on the Engine, so it
  rides along in the save. *(Defined in `config.DIFFICULTIES`; applied at the
  single seam `Fighter.take_damage`.)*

## Ranged combat

Loosing arrows is the same `d20` core as melee, but keyed off **Wits** rather
than Brawn and reaching across the map (see ADR 0006). Melee is a **bump**;
ranged is a deliberate, aimed act.

- **Bow** — a ranged weapon held in the **ranged** slot, *alongside* a melee
  weapon in the weapon slot: the Ranger nocks an arrow at range, then draws steel
  when a foe closes — no swap step. A bow carries damage dice and an **effective
  range** (a shortbow reaches less far than a longbow). *Avoid*: gun, sling.
- **Arrow** — the ammunition a bow spends. A fungible **Stack** in the pack; each
  **Shot** spends one, and an empty quiver refuses to fire. A share of spent
  arrows are **recoverable** — left on the target's tile to be picked up.
- **Shot** — one ranged attack: `d20 + Wits + level + ranged perks + bow − range
  penalty vs Defence`, then `bow damage − soak` on a hit. A **Critical** still
  hits and adds damage, but a Shot's Critical opens **no Bleed** (Bleed stays a
  melee/heavy-foe signature). Costs the hero a full turn. *(The hero rolls; the
  dice tray shows the Shot exactly as it shows a swing.)*
- **Lock-on** — the targeting mode a Shot begins in: the **nearest visible foe**
  is pre-selected; the Ranger **cycles** through the other visible foes and looses
  at the chosen one. A foe must be **in sight with a clear line** to be shot.
- **Effective range** — the distance (a per-bow stat) within which a Shot takes no
  **range penalty**. Beyond it, accuracy falls off with distance; combined with a
  point-blank penalty (a Shot loosed with a foe **adjacent** is at
  **Disadvantage**), a bow's sweet spot is short-to-medium range. The Far Shot
  Path pushes that reach outward.

## Trade & loot

The Wild pays in **both** glory and goods. A slain foe grants **XP** (quests
grant larger chunks) *and* may leave loot — its remains and purse worth
something to a Ranger who hauls them back to Bree. XP feeds **Level**s; the loot
below is the parallel **material** reward loop. *(Kill-XP reverses ADR 0004's
no-XP rule per ADR 0005; the economy below is otherwise unchanged.)*

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

## Equipment

Gear shows its full stat line on pickup — there is **no identification**.

- **Base item** — a gear template (a longsword, mail, a cloak) carrying its
  intrinsic line (damage dice, soak/Defence, load, slot).
- **Affix** — a generated modifier attached to a base item. A **prefix** reads
  as an adjective before the name (a *keen* longsword); a **suffix** reads as
  "**of ...**" after it (a longsword *of warding*).
- **Rarity** — how many affixes an item rolled: **Plain** (base only) · **Fine**
  (one affix) · **Rare** (a prefix *and* a suffix). Higher rarity = rarer drop.
- **Unique** — a hand-authored named item with fixed, characterful stats (e.g.
  *Angolar, the Ford-blade*), outside the Plain/Fine/Rare bands.
- **Property** — a weapon's special line beyond +hit/damage: e.g. **pierce**
  (ignore some soak) or **bonus-vs-type** (extra damage vs orcs, beasts…).
- **Accessory** — a non-weapon, non-armour slot (cloak/ring/token) whose pluses
  touch *non-combat* stats: +attribute, +stealth, a Path synergy, ability
  charges. The lever for "pluses to different things".

## Presentation

- **Dice tray** — the fixed, single-row panel pinned to the top of the
  bottom-left (log) pane. It shows the player's **latest** Check: the d20, the
  bonus added, the total vs the TN (for combat, the damage roll), and the
  outcome — flagging a **Critical** or **Fumble**. It only ever reflects the
  *player's* rolls, never an enemy's. The scrolling **message log** beneath it
  carries pure narrative prose with no dice math — the tray is the sole home for
  the numbers.
