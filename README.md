# The Lonelands

A Dwarf-Fortress-style CP437 roguelike set in **Eriador in TA 2965**, told with
a lightweight **d20** ruleset of our own (originally adapted from **The One
Ring** TTRPG, since de-coupled — see `docs/adr/0005`).

You play **Tarandir**, a lone **Ranger of the North** whom the Bree-folk call
**Greycloak**, walking out from **Bree** into the Wild — west to the barrow-ruins
of **Tyrn Gorthad** to recover a lost star-brooch of Arnor.

## Running

```bash
python3 -m pip install -r requirements.txt   # pygame, tcod, numpy
python3 main.py
```

The window, rendering, and input run on **pygame**; **tcod** is retained only as
a headless library for field-of-view and pathfinding (see `docs/adr/0010`). The
map and its creatures are drawn from a **Wanderlust** 16×16 CP437 tilesheet (a
Dwarf-Fortress-style sheet, kept local — see `lonelands/assets/tiles/README.md`)
and the map/HUD keep the bundled **Atkinson Hyperlegible Mono** font; menus and
dialogs render natively in a proportional font. If the tilesheet is absent the
map falls back to the font's own glyphs, so the game always runs.

## What's in this slice

- **A live 15×9 overworld** (see `docs/adr/0002`, `0003`): all 116 walkable
  Regions exist and are enterable, built lazily from the plan-as-data in
  `lonelands/overworld.py` (traced from the Eriador Journey Map). You cross from
  one Region to a neighbour by **walking off its edge**; the **Great Roads** (the
  East Road, the Greenway) stay continuous across every seam. **Bree** `(0,0)` is
  the hub; the **Barrow-downs** `(-1,0)` to the west hold a multi-level barrow
  dungeon (the main quest); **Weathertop** `(2,0)` lies east along the road with
  its own deeps. Most cells are band-tinted placeholder wilds, refined
  cluster-by-cluster.
- **Authored Bree-land content**: beyond Bree's town hub (speaking NPCs, quest-
  givers, and **Halbarad's shop**), the **Hamlets** of **Combe** and **Staddle**
  and the lonely **Forsaken Inn** sit out on the Bree-land cell, and **Archet**
  nestles in the Chetwood — each with its own bystanders, signposts, and errands.
- **Ambient barks**: short, non-interactive flavor lines overheard as you move
  near a **bark source** — *a dog barks somewhere down the Staddle lane*, the
  knock of a tankard from the Forsaken Inn, birdsong at the Chetwood eaves. Each
  source is data (a point, a radius, a pool of lines, a **cadence**) authored
  next to a region's content and throttled per-map so the log stays sparse.
- **Errands with varied objectives**: quests run a small state machine
  (unstarted → active → ready-to-report → done) and advance off game events, not
  just combat. Beyond **slay-N** and **fetch/trigger** goals, the log tracks
  **courier** deliveries (carry a named item to an NPC), **talk-to** goals (seek
  someone out and speak with them), and **travel-to** goals (reach a named
  Region) — each begun and turned in through the same dialog flow.
- **A d20 resolution core** (see `docs/adr/0005`): every action is a **Check** —
  `d20 + attribute (+ node/gear)` vs a **Target Number**. A natural 20 is a
  **Critical** (auto-hit + bonus damage), a natural 1 a **Fumble** (auto-miss);
  **Advantage/Disadvantage** roll two dice and keep the higher/lower. The dice
  tray at the top of the log shows the player's latest roll; the tray owns all
  the numbers, the message log stays pure prose.
- **A committed-skill-tree hero** (see `docs/adr/0011`): three attributes —
  **Brawn**, **Wits**, **Will** — a single **Endurance** HP pool, and XP-driven
  **Level**s that grant HP, to-hit, and **Path points**. At level 2 the Ranger
  **commits to one of three Paths** — the **Long Watch** (tank), the **Far Shot**
  (ranged), or the **Hidden Path** (stealth) — then pours every point down that
  Path's deep, branching tree of **Nodes** (ranked passives, one-and-done
  actives), tipped by two hard-won **capstones**. A future **Kindled Heart**
  Path is deferred.
- **Melee & ranged combat** (see `docs/adr/0006`): melee is a **bump**
  (`d20 + attack bonus vs Defence`, then `weapon damage − soak`); ranged is a
  deliberate aimed **Shot** keyed off Wits, with **bows**, spendable and
  recoverable **arrows**, an **effective range** with fall-off, and **lock-on**
  targeting that cycles through visible foes. Criticals can open **Bleed**; heavy
  armour provides **Soak**.
- **A living economy with procedural loot** (see `docs/adr/0004`): slain foes
  grant **XP** and may drop **loot** — coins into your purse, sellable
  **trade-goods** onto the corpse tile. Gear is generated with **affixes** at
  three rarities — **Plain**, **Fine**, **Rare** — alongside hand-authored named
  **Uniques**; nothing needs identifying. Haul goods back to Halbarad's shop and
  toggle to the **Sell** view (`Tab`) to turn them into coin.
- **A shared chrome visual language** (see `CONTEXT.md` → *The chrome visual
  language*): every panel — the sidebar, character sheet, dialog, menus, and the
  shop — speaks one vocabulary, so highlighting means the same thing everywhere:
  three **luminance tiers** (dim label · normal body · bright glowing value), a
  **filled bar** for the single "this is the thing" emphasis, **header-and-rule**
  section breaks, **stateful colour** used only where hue drives a decision
  (Endurance green→amber→red, spendable perk points in gold), and a **scrim**
  that dims the world behind any open popup.
- **A title-screen difficulty selector**: pick **Merciful**, **Wayfarer**
  (intended balance), or **Grim** — it scales *only the damage the player takes*,
  never enemy Endurance or aim, and rides along in the save.
- **A single-slot save**: pause with `Esc` to save-and-continue or save-and-quit,
  and resume from the title screen's **Continue** option.

## Controls

| Key | Action |
|-----|--------|
| arrows / `hjkl` / `yubn` / numpad | move; into a foe to attack, into a townsperson to talk |
| `.` / `z` | wait |
| `Enter` / `>` / `<` | use the gate / stair / barrow-entrance you stand on |
| `f` | fire a ranged shot (lock-on targeting) |
| `g` | pick up |
| `i` | use / equip from pack |
| `d` | drop |
| `c` | character sheet |
| `p` | Paths & perks (spend perk points) |
| `a` | abilities (active perks) |
| `q` | errands (quests) |
| `?` | help |
| `Esc` | pause menu — save & continue, save & quit, or quit |

## Layout of the code

```
main.py              entry point + pygame window / event / resize loop
lonelands/
  config.py          screen/layout constants, fonts, tilesets, difficulties
  fonts.py           pygame glyph atlas: prose + CP437 tiles + dice faces
  tile_glyphs.py     map/entity char → tilesheet code-point mapping
  color.py           the palette
  dice.py            the d20 Check engine (Critical / Fumble / Advantage)
  dice_glyphs.py     die-face glyphs for the dice tray
  character.py       attributes, Level curve, the hero's derived stats
  perks.py           the five Paths and their perks
  content.py         creatures, weapons, armour, consumables (templates)
  equipment_types.py base-item / slot / property definitions
  affixes.py         the prefix/suffix generator → Plain / Fine / Rare loot
  story/             per-location NPCs, dialog trees & quests (bree, breeland, chetwood)
  quests.py          quest definitions + quest log
  barks.py           ambient proximity-triggered flavor lines (bark sources/fields)
  overworld.py       the 15×9 Region plan-as-data (cells, bands, road edges)
  world.py           the Region grid + travel between Regions and Levels
  procgen.py         Bree / wilderness / barrow generation
  game_map.py        one map's tiles + entities
  entity.py          the base entity + actor plumbing
  engine.py          turn loop, FOV, rendering orchestration
  actions.py         player/actor actions
  input_handlers.py  all game states (main game, dialog, shop, sheet, menus…)
  display.py         pygame window + the Console grid shim + glyph cache
  events.py          input dispatch + KeySym/Modifier shim (SDL keycodes)
  ui.py              pixel-space UI layer for the native menus (panels, text)
  setup_game.py      new-game construction
  savegame.py        single-slot save / load / delete
  components/        fighter, hero, ai, inventory, equipment, equippable, consumable, npc
  tile_types.py      numpy tiles with lit / remembered graphics
  render_order.py    entity draw ordering
  render_functions.py the sidebar, banners, bars
  message_log.py     the scrolling Chronicle
```

## Designed to grow

This is a deliberately small, fully-wired vertical slice. Natural next steps:
the Journey/Travel minigame, Fellowship-phase downtime, more of Eriador (the
wider Barrow-downs, Rivendell), and Shadow & Corruption.
