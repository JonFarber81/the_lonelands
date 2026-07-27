# The Lonelands

A Dwarf-Fortress-style CP437 roguelike set in **Eriador in TA 2965** and powered
by mechanics adapted from **The One Ring** TTRPG.

You play **Tarandir**, a lone **Ranger of the North** whom the Bree-folk call
**Greycloak** (a single player-hero, TOR's solo **"Strider mode"**), walking out
from **Bree** into the Wild and down into the barrow-ruin east of it in the
Weather Hills.

## Running

```bash
cd the_lonelands
python3 -m pip install -r requirements.txt   # tcod + numpy
python3 main.py
```

The map and its creatures are drawn from a **Wanderlust** 16×16 CP437 tilesheet
(a Dwarf-Fortress-style sheet, kept local — see
`lonelands/assets/tiles/README.md`); prose, menus, and the dice tray render from
the bundled **Atkinson Hyperlegible Mono** font via FreeType. If the tilesheet
is absent the map falls back to the font's own glyphs, so the game always runs.

## What's in this slice

- **A grid of Regions** (see `docs/adr/0002`): **Bree**, the town hub with
  speaking NPCs and a shop, sits at the centre of a plus, edge-connected to the
  **Weather Hills** (east, holding the barrow entrance), the **Barrow-downs**
  (west), the **Chetwood** (north), and the **South Downs** (south). Below the
  Weather Hills lies a **3-level barrow** dungeon (rooms-and-corridors,
  depth-scaled monsters and loot).
- **The One Ring dice**: every deed is a Feat die (d12) + Success dice (d6),
  with the **Gandalf rune** (auto-success), the **Eye of Sauron**, **tengwar**
  great-successes, and the **Weary** condition. See the bottom of the log for
  the raw roll, e.g. `[7|4+6=17 vs 14]`.
- **TOR character sheet**: Strength / Heart / Wits, the eighteen skills, weapon
  proficiencies, **Hope**, **Endurance**, Wounds, and XP-based advancement
  (press `c`, then `a`).
- **Combat**: proficiency test vs a Parry-derived TN; great successes threaten a
  **Piercing Blow** → Protection test vs the weapon's Injury → a **Wound**.
- **Quests & dialog trees**: a main quest (recover the star-brooch of Arnor) and
  two side quests, given and resolved through branching conversations.
- **Equipment, inventory, consumables** (athelas mends wounds), and
  Middle-earth-appropriate creatures (orcs, cave-goblins, great spiders, wargs,
  a barrow-wight in the deep).
- **A living economy** (see `docs/adr/0004`): slain foes drop **loot** — coins
  into your purse, sellable **trade-goods** (pelts, spider-silk, orc-trophies)
  onto the corpse tile. Haul them back to **Halbarad's shop** in Bree and toggle
  to the **Sell** view (`Tab`) to turn them into coin; fungible goods and
  consumables **stack** (`×N`). Every item carries a Value the merchant buys and
  sells against — so the kill → loot → sell → spend loop is closed.
- **A single-slot save**: pause with `Esc` to save-and-continue or save-and-quit,
  and pick up where you left off from the title screen's **Continue** option.

## Controls

| Key | Action |
|-----|--------|
| arrows / `hjkl` / `yubn` / numpad | move; into a foe to attack, into a townsperson to talk |
| `.` / `z` | wait |
| `Enter` | use the gate / stair / barrow-entrance you stand on |
| `g` | pick up |
| `i` | use / equip from pack |
| `d` | drop |
| `c` | character sheet (`a` = spend XP) |
| `q` | errands (quests) |
| `?` | help |
| `Esc` | pause menu — save & continue, save & quit, or quit |

## Layout of the code

```
main.py              entry point + tcod context / resize loop
lonelands/
  config.py          screen/layout constants, font + tileset candidates
  fonts.py           FreeType TTF auto-fit + CP437 tilesheet loading
  tile_glyphs.py     map/entity char → tilesheet code-point mapping
  dice.py            The One Ring feat + success dice engine
  dice_glyphs.py     die-face glyphs for the dice tray
  tor.py             attributes, skills, proficiencies, TN mapping
  content.py         player, creatures, weapons, armour, consumables (templates)
  story/             per-location NPCs, dialog trees & quests (bree, breeland, chetwood)
  quests.py          quest definitions + quest log
  procgen.py         Bree / wilderness / barrow generation
  world.py           the Region grid + travel between Regions and Levels
  game_map.py        one map's tiles + entities
  entity.py          the base entity + actor plumbing
  engine.py          turn loop, FOV, rendering orchestration
  actions.py         player/actor actions
  input_handlers.py  all game states (main game, dialog, shop, sheet, menus…)
  setup_game.py      new-game construction
  savegame.py        single-slot save / load / delete
  components/        fighter, hero, ai, inventory, equipment, consumable, npc
  tile_types.py      numpy tiles with lit / remembered graphics
  render_functions.py the sidebar, banners, bars
  message_log.py     the scrolling Chronicle
```

## Designed to grow

This is a deliberately small, fully-wired vertical slice. Natural next steps:
ranged archery, the Journey/Travel minigame, Fellowship-phase downtime, more of
Eriador (the wider Barrow-downs, Rivendell), and Shadow & Corruption.
