# The Lonelands

A text-and-glyph roguelike in the style of *Brogue* and *Cogmind*, set in
**Eriador in TA 2965** and powered by mechanics adapted from **The One Ring** TTRPG.

You play a lone **Ranger of the North** (a solo "Strider" in TOR's parlance),
walking out from the Dúnedain hamlet of **Talbrún** on the Weather Hills into the
Wild, and down into the barrow-ruin of **Amon Gûl**.

## Running

```bash
cd the_lonelands
python3 -m pip install -r requirements.txt   # tcod + numpy
python3 main.py
```

Rendered with SF Mono (or another system monospace) for crisp, coloured glyphs.

## What's in this slice

- **Three connected worlds**: the town hub (safe, with speaking NPCs), the
  wilderness overworld (river, ford, roaming wolves), and a **3-level barrow**
  dungeon (rooms-and-corridors, depth-scaled monsters and loot).
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
- **Equipment, inventory, a shop, consumables** (athelas mends wounds), and
  Middle-earth-appropriate creatures (orcs, cave-goblins, great spiders, wargs,
  a barrow-wight in the deep).

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
| `Esc` | menu |

## Layout of the code

```
main.py              entry point + tcod context / font loading
lonelands/
  dice.py            The One Ring feat + success dice engine
  tor.py             attributes, skills, proficiencies, TN mapping
  content.py         player, creatures, weapons, armour, consumables (templates)
  story.py           quests, NPCs, and dialog trees
  procgen.py         town / overworld / barrow generation
  world.py           the multi-map world + travel between maps
  engine.py          turn loop, FOV, rendering orchestration
  input_handlers.py  all game states (main game, dialog, shop, sheet, menus…)
  components/        fighter, hero, ai, inventory, equipment, consumable, npc
  tile_types.py      numpy tiles with lit / remembered graphics
  render_functions.py the sidebar, banners, bars
```

## Designed to grow

This is a deliberately small, fully-wired vertical slice. Natural next steps:
ranged archery, the Journey/Travel minigame, Fellowship-phase downtime, more of
Eriador (Bree, the Barrow-downs, Rivendell), Shadow & Corruption, and saving.
